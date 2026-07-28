from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class SmallSceneApiTests(unittest.TestCase):
    """小场景接口测试：所有数据均写入临时测试库。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager
        self.project = self.manager.create_project("小场景测试项目")
        self.chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )
        self.large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "公共沙滩"
        )

    def endpoint(self, large_scene_id: str | None = None) -> str:
        return (
            f"/api/large-scenes/{large_scene_id or self.large_scene['id']}/small-scenes"
        )

    def test_empty_large_scene_returns_empty_list(self) -> None:
        response = self.client.get(self.endpoint())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_list_is_sorted_by_sort_order(self) -> None:
        for name in ("晨曦小径", "浪花台", "瞭望塔"):
            self.client.post(self.endpoint(), json={"name": name})
        payload = self.client.get(self.endpoint()).json()
        self.assertEqual(
            [item["name"] for item in payload["items"]],
            ["晨曦小径", "浪花台", "瞭望塔"],
        )
        self.assertEqual(
            [item["sort_order"] for item in payload["items"]], [1, 2, 3]
        )

    def test_list_items_include_shot_page_count_and_branch_count(self) -> None:
        self.client.post(self.endpoint(), json={"name": "小场景A"})
        items = self.client.get(self.endpoint()).json()["items"]
        self.assertEqual(len(items), 1)
        self.assertIn("shot_page_count", items[0])
        self.assertIn("branch_count", items[0])
        self.assertEqual(items[0]["shot_page_count"], 0)
        self.assertEqual(items[0]["branch_count"], 0)

    def test_create_small_scene_returns_full_shape(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "晨曦小径"})
        self.assertEqual(response.status_code, 201)
        small_scene = response.json()["small_scene"]
        self.assertEqual(small_scene["large_scene_id"], self.large_scene["id"])
        self.assertEqual(small_scene["name"], "晨曦小径")
        self.assertEqual(small_scene["sort_order"], 1)
        self.assertEqual(small_scene["scene_type"], "content")
        self.assertEqual(small_scene["description"], "")
        for key in ("id", "created_at", "updated_at"):
            self.assertIn(key, small_scene)

    def test_create_with_scene_type_content(self) -> None:
        response = self.client.post(
            self.endpoint(), json={"name": "内容场景", "scene_type": "content"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["small_scene"]["scene_type"], "content")

    def test_create_with_scene_type_transition(self) -> None:
        response = self.client.post(
            self.endpoint(), json={"name": "过渡场景", "scene_type": "transition"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["small_scene"]["scene_type"], "transition")

    def test_create_with_invalid_scene_type_returns_422(self) -> None:
        response = self.client.post(
            self.endpoint(), json={"name": "非法", "scene_type": "invalid"}
        )
        self.assertEqual(response.status_code, 422)

    def test_name_is_cleaned_before_storage(self) -> None:
        response = self.client.post(
            self.endpoint(), json={"name": "  晨曦   小径  "}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["small_scene"]["name"], "晨曦   小径")

    def test_blank_name_is_rejected(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "   "})
        self.assertEqual(response.status_code, 422)

    def test_too_long_name_is_rejected(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "场" * 81})
        self.assertEqual(response.status_code, 422)

    def test_duplicate_name_in_same_large_scene_is_rejected(self) -> None:
        self.client.post(self.endpoint(), json={"name": "晨曦小径"})
        response = self.client.post(self.endpoint(), json={"name": "晨曦小径"})
        self.assertEqual(response.status_code, 409)

    def test_same_name_is_allowed_in_different_large_scenes(self) -> None:
        other = self.manager.create_large_scene(
            str(self.chapter["id"]), "另一个大场景"
        )
        self.client.post(self.endpoint(), json={"name": "晨曦小径"})
        response = self.client.post(
            self.endpoint(str(other["id"])), json={"name": "晨曦小径"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            len(self.manager.list_small_scenes(str(other["id"]))), 1
        )

    def test_missing_large_scene_returns_404_on_create(self) -> None:
        response = self.client.post(
            self.endpoint("missing"), json={"name": "孤立小场景"}
        )
        self.assertEqual(response.status_code, 404)

    def test_get_small_scene_returns_with_materials(self) -> None:
        small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "晨曦小径"
        )
        response = self.client.get(f"/api/small-scenes/{small_scene['id']}")
        self.assertEqual(response.status_code, 200)
        body = response.json()["small_scene"]
        self.assertEqual(body["id"], small_scene["id"])
        self.assertEqual(body["name"], "晨曦小径")
        self.assertIn("materials", body)
        self.assertEqual(body["materials"], [])

    def test_get_missing_small_scene_returns_404(self) -> None:
        response = self.client.get("/api/small-scenes/missing-id")
        self.assertEqual(response.status_code, 404)

    def test_update_name_only(self) -> None:
        small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "旧名称"
        )
        response = self.client.patch(
            f"/api/small-scenes/{small_scene['id']}",
            json={"name": "  新   名称  "},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["small_scene"]["name"], "新   名称")
        self.assertEqual(
            self.manager.get_small_scene(str(small_scene["id"]))["name"],
            "新   名称",
        )

    def test_update_scene_type_only(self) -> None:
        small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "场景1", scene_type="content"
        )
        response = self.client.patch(
            f"/api/small-scenes/{small_scene['id']}",
            json={"scene_type": "transition"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["small_scene"]["scene_type"], "transition"
        )

    def test_update_description(self) -> None:
        small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "场景1"
        )
        response = self.client.patch(
            f"/api/small-scenes/{small_scene['id']}",
            json={"description": "这是一段描述"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["small_scene"]["description"], "这是一段描述"
        )

    def test_clear_description(self) -> None:
        small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "场景1", description="旧描述"
        )
        response = self.client.patch(
            f"/api/small-scenes/{small_scene['id']}",
            json={"description": ""},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["small_scene"]["description"], "")

    def test_update_name_preserves_other_fields(self) -> None:
        small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "旧名", scene_type="transition",
            description="描述"
        )
        response = self.client.patch(
            f"/api/small-scenes/{small_scene['id']}", json={"name": "新名"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["small_scene"]
        self.assertEqual(body["name"], "新名")
        self.assertEqual(body["scene_type"], "transition")
        self.assertEqual(body["description"], "描述")
        self.assertEqual(body["sort_order"], 1)

    def test_update_duplicate_name_returns_409(self) -> None:
        first = self.manager.create_small_scene(
            str(self.large_scene["id"]), "晨曦小径"
        )
        self.manager.create_small_scene(
            str(self.large_scene["id"]), "浪花台"
        )
        response = self.client.patch(
            f"/api/small-scenes/{first['id']}", json={"name": "浪花台"}
        )
        self.assertEqual(response.status_code, 409)

    def test_update_missing_small_scene_returns_404(self) -> None:
        response = self.client.patch(
            "/api/small-scenes/missing-id", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 404)

    def test_update_at_least_one_field_required(self) -> None:
        small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "场景1"
        )
        response = self.client.patch(
            f"/api/small-scenes/{small_scene['id']}", json={}
        )
        self.assertEqual(response.status_code, 422)

    def test_move_forward_within_large_scene(self) -> None:
        a = self.manager.create_small_scene(str(self.large_scene["id"]), "A")
        b = self.manager.create_small_scene(str(self.large_scene["id"]), "B")
        c = self.manager.create_small_scene(str(self.large_scene["id"]), "C")
        response = self.client.post(
            f"/api/small-scenes/{a['id']}/move",
            json={"target_sort_order": 3},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [i["name"] for i in body["items"]], ["B", "C", "A"]
        )
        self.assertEqual(
            [i["sort_order"] for i in body["items"]], [1, 2, 3]
        )

    def test_move_backward_within_large_scene(self) -> None:
        a = self.manager.create_small_scene(str(self.large_scene["id"]), "A")
        b = self.manager.create_small_scene(str(self.large_scene["id"]), "B")
        c = self.manager.create_small_scene(str(self.large_scene["id"]), "C")
        response = self.client.post(
            f"/api/small-scenes/{c['id']}/move",
            json={"target_sort_order": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [i["name"] for i in response.json()["items"]],
            ["C", "A", "B"],
        )

    def test_move_target_sort_exceeds_length_appends_to_end(self) -> None:
        a = self.manager.create_small_scene(str(self.large_scene["id"]), "A")
        b = self.manager.create_small_scene(str(self.large_scene["id"]), "B")
        response = self.client.post(
            f"/api/small-scenes/{a['id']}/move",
            json={"target_sort_order": 999},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [i["name"] for i in response.json()["items"]], ["B", "A"]
        )

    def test_move_target_sort_below_one_treated_as_one(self) -> None:
        a = self.manager.create_small_scene(str(self.large_scene["id"]), "A")
        b = self.manager.create_small_scene(str(self.large_scene["id"]), "B")
        result = self.manager.move_small_scene(str(a["id"]), 0)
        self.assertEqual(result["sort_order"], 1)

    def test_move_missing_small_scene_returns_404(self) -> None:
        response = self.client.post(
            "/api/small-scenes/missing/move",
            json={"target_sort_order": 1},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_small_scene_removes_only_target(self) -> None:
        first = self.manager.create_small_scene(
            str(self.large_scene["id"]), "晨曦小径"
        )
        second = self.manager.create_small_scene(
            str(self.large_scene["id"]), "浪花台"
        )
        response = self.client.delete(f"/api/small-scenes/{first['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"]["id"], first["id"])
        remaining = self.manager.list_small_scenes(str(self.large_scene["id"]))
        self.assertEqual([item["id"] for item in remaining], [second["id"]])

    def test_delete_missing_small_scene_returns_404(self) -> None:
        response = self.client.delete("/api/small-scenes/missing-id")
        self.assertEqual(response.status_code, 404)

    def test_delete_renumbers_remaining_scenes(self) -> None:
        a = self.manager.create_small_scene(str(self.large_scene["id"]), "A")
        b = self.manager.create_small_scene(str(self.large_scene["id"]), "B")
        c = self.manager.create_small_scene(str(self.large_scene["id"]), "C")
        self.client.delete(f"/api/small-scenes/{b['id']}")
        remaining = self.manager.list_small_scenes(str(self.large_scene["id"]))
        self.assertEqual([s["name"] for s in remaining], ["A", "C"])
        self.assertEqual([s["sort_order"] for s in remaining], [1, 2])

    def test_v040_migration_creates_small_scenes_table_safely(self) -> None:
        with self.manager.connection("test") as conn:
            conn.execute("DROP TABLE IF EXISTS small_scenes")
        self.manager.initialize("test")
        with self.manager.connection("test") as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(small_scenes)").fetchall()]
            self.assertIn("scene_type", cols)
            self.assertIn("description", cols)
        self.manager.create_small_scene(
            str(self.large_scene["id"]), "迁移后场景"
        )
        items = self.manager.list_small_scenes(str(self.large_scene["id"]))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "迁移后场景")


class SmallSceneDatabaseTests(unittest.TestCase):
    def test_small_scene_is_written_only_to_test_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(
                Path(directory),
                environment="test",
                locked_environment="test",
            )
            project = manager.create_project("隔离项目")
            chapter = manager.create_chapter(str(project["id"]), "第一章")
            large_scene = manager.create_large_scene(
                str(chapter["id"]), "大场景"
            )
            manager.create_small_scene(str(large_scene["id"]), "小场景")
            self.assertEqual(
                len(manager.list_small_scenes(str(large_scene["id"]), "test")), 1
            )
            self.assertEqual(
                len(manager.list_small_scenes(str(large_scene["id"]), "production")), 0
            )

    def test_sort_order_is_independent_per_large_scene(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("排序项目")
            chapter = manager.create_chapter(str(project["id"]), "第一章")
            first = manager.create_large_scene(str(chapter["id"]), "大场景A")
            second = manager.create_large_scene(str(chapter["id"]), "大场景B")
            a = manager.create_small_scene(str(first["id"]), "A")
            b = manager.create_small_scene(str(first["id"]), "B")
            c = manager.create_small_scene(str(second["id"]), "C")
            self.assertEqual([a["sort_order"], b["sort_order"]], [1, 2])
            self.assertEqual(c["sort_order"], 1)

    def test_large_scene_delete_cascades_to_small_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("级联项目")
            chapter = manager.create_chapter(str(project["id"]), "第一章")
            large_scene = manager.create_large_scene(
                str(chapter["id"]), "大场景"
            )
            manager.create_small_scene(str(large_scene["id"]), "小场景")
            with manager.connection() as connection:
                connection.execute(
                    "DELETE FROM large_scenes WHERE id = ?",
                    (str(large_scene["id"]),),
                )
            self.assertEqual(
                manager.list_small_scenes(str(large_scene["id"])), []
            )


if __name__ == "__main__":
    unittest.main()
