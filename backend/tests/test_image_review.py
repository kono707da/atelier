"""MOD-08 增强：图片评分、颜色标记、备注与标签测试。

测试范围：
- 评分（star_rating 0-5）
- 颜色标记（color_label）
- 备注（review_note）
- 图片标签 CRUD
- 标签与图片实例的关联管理
- API 端点
"""
from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.output_receiver import (
    add_tag_to_image,
    create_image_tag,
    delete_image_tag,
    get_image_tags_for_instance,
    list_image_tags,
    remove_tag_from_image,
    update_image_review,
)


def _make_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class ImageReviewBase(unittest.TestCase):
    """公共 fixture。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.app = create_app(
            data_root=self.tmp_path,
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager
        self.images_dir = self.tmp_path / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.instance_id = self._create_image_instance()

    def _create_image_instance(self) -> str:
        """创建一个图片实例用于测试。"""
        from backend.app.output_receiver import create_file_record, create_image_instance

        file_id = f"file-{uuid4()}"
        storage_key = f"{file_id}.png"
        (self.images_dir / storage_key).write_bytes(_make_png(64, 64, (100, 150, 200)))
        create_file_record(
            self.manager,
            {
                "file_id": file_id,
                "storage_key": storage_key,
                "original_name": "test.png",
                "mime_type": "image/png",
                "size_bytes": 1024,
                "content_hash": f"hash-{uuid4()}",
            },
        )
        # 创建完整的 project -> chapter -> large_scene -> small_scene -> shot_page 链路
        now = "2026-01-01T00:00:00Z"
        project_id = f"proj-{uuid4()}"
        chapter_id = f"ch-{uuid4()}"
        large_scene_id = f"ls-{uuid4()}"
        small_scene_id = f"ss-{uuid4()}"
        shot_page_id = f"sp-{uuid4()}"
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT INTO projects(id, name, status, revision, created_at, updated_at) "
                "VALUES (?, ?, 'draft', 1, ?, ?)",
                (project_id, "test-project", now, now),
            )
            conn.execute(
                "INSERT INTO chapters(id, project_id, name, sort_order, revision, created_at, updated_at) "
                "VALUES (?, ?, 'ch1', 1, 1, ?, ?)",
                (chapter_id, project_id, now, now),
            )
            conn.execute(
                "INSERT INTO large_scenes(id, chapter_id, name, scene_type, sort_order, revision, created_at, updated_at) "
                "VALUES (?, ?, 'ls1', 'content', 1, 1, ?, ?)",
                (large_scene_id, chapter_id, now, now),
            )
            conn.execute(
                "INSERT INTO small_scenes(id, large_scene_id, name, sort_order, revision, created_at, updated_at) "
                "VALUES (?, ?, 'ss1', 1, 1, ?, ?)",
                (small_scene_id, large_scene_id, now, now),
            )
            conn.execute(
                "INSERT INTO shot_pages(id, small_scene_id, branch_id, title, sort_order, revision, created_at, updated_at) "
                "VALUES (?, ?, NULL, 'sp1', 1, 1, ?, ?)",
                (shot_page_id, small_scene_id, now, now),
            )
            conn.commit()

        instance = create_image_instance(
            self.manager,
            project_id=project_id,
            shot_page_id=shot_page_id,
            task_id=None,
            attempt_id=None,
            file_id=file_id,
            node_id=None,
            workflow_version_id=None,
            prompt_id=None,
            width=64,
            height=64,
            img_format="PNG",
            seed=42,
            resolved_json=None,
            snapshot_json={},
        )
        return instance["id"]


class UpdateReviewTests(ImageReviewBase):
    """评分、颜色标记、备注。"""

    def test_update_star_rating(self) -> None:
        result = update_image_review(self.manager, self.instance_id, star_rating=4)
        self.assertEqual(result["star_rating"], 4)

    def test_update_color_label(self) -> None:
        result = update_image_review(self.manager, self.instance_id, color_label="blue")
        self.assertEqual(result["color_label"], "blue")

    def test_update_review_note(self) -> None:
        result = update_image_review(self.manager, self.instance_id, review_note="good")
        self.assertEqual(result["review_note"], "good")

    def test_update_all_fields(self) -> None:
        result = update_image_review(
            self.manager, self.instance_id,
            star_rating=5, color_label="green", review_note="excellent",
        )
        self.assertEqual(result["star_rating"], 5)
        self.assertEqual(result["color_label"], "green")
        self.assertEqual(result["review_note"], "excellent")

    def test_invalid_star_rating(self) -> None:
        with self.assertRaises(ValueError):
            update_image_review(self.manager, self.instance_id, star_rating=6)

    def test_invalid_color_label(self) -> None:
        with self.assertRaises(ValueError):
            update_image_review(self.manager, self.instance_id, color_label="pink")

    def test_update_nonexistent_instance(self) -> None:
        result = update_image_review(self.manager, "nonexistent", star_rating=3)
        self.assertIsNone(result)

    def test_partial_update_preserves_other_fields(self) -> None:
        update_image_review(self.manager, self.instance_id, star_rating=3, color_label="red")
        result = update_image_review(self.manager, self.instance_id, review_note="note")
        self.assertEqual(result["star_rating"], 3)
        self.assertEqual(result["color_label"], "red")
        self.assertEqual(result["review_note"], "note")


class TagCRUDTests(ImageReviewBase):
    """标签 CRUD。"""

    def test_create_tag(self) -> None:
        tag = create_image_tag(self.manager, "landscape")
        self.assertIn("id", tag)
        self.assertEqual(tag["name"], "landscape")
        self.assertEqual(tag["normalized_name"], "landscape")

    def test_create_tag_normalizes_name(self) -> None:
        tag = create_image_tag(self.manager, "  My  Tag  ")
        self.assertEqual(tag["normalized_name"], "my tag")
        self.assertEqual(tag["name"], "My  Tag")

    def test_create_duplicate_tag_returns_existing(self) -> None:
        tag1 = create_image_tag(self.manager, "portrait")
        tag2 = create_image_tag(self.manager, "Portrait")
        self.assertEqual(tag1["id"], tag2["id"])

    def test_create_tag_with_color(self) -> None:
        tag = create_image_tag(self.manager, "favorite", color="yellow")
        self.assertEqual(tag["color"], "yellow")

    def test_create_tag_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            create_image_tag(self.manager, "   ")

    def test_list_tags(self) -> None:
        create_image_tag(self.manager, "alpha")
        create_image_tag(self.manager, "beta")
        tags = list_image_tags(self.manager)
        self.assertEqual(len(tags), 2)
        # 应按名称排序
        self.assertEqual(tags[0]["name"], "alpha")

    def test_delete_tag(self) -> None:
        tag = create_image_tag(self.manager, "temp")
        deleted = delete_image_tag(self.manager, tag["id"])
        self.assertTrue(deleted)
        tags = list_image_tags(self.manager)
        self.assertEqual(len(tags), 0)

    def test_delete_nonexistent_tag(self) -> None:
        deleted = delete_image_tag(self.manager, "nonexistent")
        self.assertFalse(deleted)


class TagLinkTests(ImageReviewBase):
    """标签关联管理。"""

    def test_add_tag_to_image(self) -> None:
        tag = create_image_tag(self.manager, "outdoor")
        result = add_tag_to_image(self.manager, self.instance_id, tag["id"])
        self.assertIsNotNone(result)
        self.assertEqual(len(result["tags"]), 1)
        self.assertEqual(result["tags"][0]["name"], "outdoor")

    def test_add_tag_idempotent(self) -> None:
        tag = create_image_tag(self.manager, "indoor")
        add_tag_to_image(self.manager, self.instance_id, tag["id"])
        add_tag_to_image(self.manager, self.instance_id, tag["id"])
        result = get_image_tags_for_instance(self.manager, self.instance_id)
        self.assertEqual(len(result["tags"]), 1)

    def test_add_multiple_tags(self) -> None:
        t1 = create_image_tag(self.manager, "tag1")
        t2 = create_image_tag(self.manager, "tag2")
        t3 = create_image_tag(self.manager, "tag3")
        for t in [t1, t2, t3]:
            add_tag_to_image(self.manager, self.instance_id, t["id"])
        result = get_image_tags_for_instance(self.manager, self.instance_id)
        self.assertEqual(len(result["tags"]), 3)

    def test_remove_tag_from_image(self) -> None:
        tag = create_image_tag(self.manager, "removable")
        add_tag_to_image(self.manager, self.instance_id, tag["id"])
        removed = remove_tag_from_image(self.manager, self.instance_id, tag["id"])
        self.assertTrue(removed)
        result = get_image_tags_for_instance(self.manager, self.instance_id)
        self.assertEqual(len(result["tags"]), 0)

    def test_remove_tag_not_linked(self) -> None:
        tag = create_image_tag(self.manager, "unlinked")
        removed = remove_tag_from_image(self.manager, self.instance_id, tag["id"])
        self.assertFalse(removed)

    def test_add_tag_nonexistent_instance(self) -> None:
        tag = create_image_tag(self.manager, "test")
        result = add_tag_to_image(self.manager, "nonexistent", tag["id"])
        self.assertIsNone(result)

    def test_add_nonexistent_tag(self) -> None:
        result = add_tag_to_image(self.manager, self.instance_id, "nonexistent")
        self.assertIsNone(result)

    def test_get_tags_nonexistent_instance(self) -> None:
        result = get_image_tags_for_instance(self.manager, "nonexistent")
        self.assertIsNone(result)

    def test_list_tags_shows_usage_count(self) -> None:
        tag = create_image_tag(self.manager, "used")
        add_tag_to_image(self.manager, self.instance_id, tag["id"])
        tags = list_image_tags(self.manager)
        self.assertEqual(tags[0]["usage_count"], 1)


class APIEndpointTests(ImageReviewBase):
    """API 端点。"""

    def test_api_update_review(self) -> None:
        resp = self.client.patch(
            f"/api/image-instances/{self.instance_id}/review",
            json={"star_rating": 4, "color_label": "blue", "review_note": "nice"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["image_instance"]["star_rating"], 4)
        self.assertEqual(body["image_instance"]["color_label"], "blue")

    def test_api_update_review_invalid_rating(self) -> None:
        resp = self.client.patch(
            f"/api/image-instances/{self.instance_id}/review",
            json={"star_rating": 10},
        )
        self.assertEqual(resp.status_code, 400)

    def test_api_update_review_not_found(self) -> None:
        resp = self.client.patch(
            "/api/image-instances/nonexistent/review",
            json={"star_rating": 3},
        )
        self.assertEqual(resp.status_code, 404)

    def test_api_create_tag(self) -> None:
        resp = self.client.post(
            "/api/image-tags",
            json={"name": "sunset", "color": "orange"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["tag"]["name"], "sunset")

    def test_api_list_tags(self) -> None:
        self.client.post("/api/image-tags", json={"name": "a"})
        self.client.post("/api/image-tags", json={"name": "b"})
        resp = self.client.get("/api/image-tags")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["total"], 2)

    def test_api_delete_tag(self) -> None:
        create_resp = self.client.post("/api/image-tags", json={"name": "temp"})
        tag_id = create_resp.json()["tag"]["id"]
        resp = self.client.delete(f"/api/image-tags/{tag_id}")
        self.assertEqual(resp.status_code, 200)

    def test_api_delete_tag_not_found(self) -> None:
        resp = self.client.delete("/api/image-tags/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_api_add_tag_to_image(self) -> None:
        create_resp = self.client.post("/api/image-tags", json={"name": "cool"})
        tag_id = create_resp.json()["tag"]["id"]
        resp = self.client.post(
            f"/api/image-instances/{self.instance_id}/tags/{tag_id}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["result"]["tags"]), 1)

    def test_api_remove_tag_from_image(self) -> None:
        create_resp = self.client.post("/api/image-tags", json={"name": "gone"})
        tag_id = create_resp.json()["tag"]["id"]
        self.client.post(f"/api/image-instances/{self.instance_id}/tags/{tag_id}")
        resp = self.client.delete(
            f"/api/image-instances/{self.instance_id}/tags/{tag_id}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["removed"])

    def test_api_get_image_tags(self) -> None:
        create_resp = self.client.post("/api/image-tags", json={"name": "tag1"})
        tag_id = create_resp.json()["tag"]["id"]
        self.client.post(f"/api/image-instances/{self.instance_id}/tags/{tag_id}")
        resp = self.client.get(f"/api/image-instances/{self.instance_id}/tags")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()["result"]["tags"]), 1)


if __name__ == "__main__":
    unittest.main()
