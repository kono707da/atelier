from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class LargeSceneApiTests(unittest.TestCase):
    """大场景接口测试：所有数据均写入临时测试库。"""

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
        self.project = self.manager.create_project("大场景测试项目")
        self.chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )

    def endpoint(self, chapter_id: str | None = None) -> str:
        return (
            f"/api/chapters/{chapter_id or self.chapter['id']}/large-scenes"
        )

    def test_empty_chapter_returns_empty_list(self) -> None:
        response = self.client.get(self.endpoint())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_create_large_scene_returns_full_shape(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        self.assertEqual(response.status_code, 201)
        large_scene = response.json()["large_scene"]
        self.assertEqual(large_scene["chapter_id"], self.chapter["id"])
        self.assertEqual(large_scene["name"], "公共沙滩")
        self.assertEqual(large_scene["sort_order"], 1)
        for key in ("id", "created_at", "updated_at"):
            self.assertIn(key, large_scene)

    def test_list_is_sorted_by_sort_order(self) -> None:
        for name in ("公共沙滩", "浅水区", "度假屋"):
            self.client.post(self.endpoint(), json={"name": name})
        payload = self.client.get(self.endpoint()).json()
        self.assertEqual(
            [item["name"] for item in payload["items"]],
            ["公共沙滩", "浅水区", "度假屋"],
        )
        self.assertEqual(
            [item["sort_order"] for item in payload["items"]], [1, 2, 3]
        )

    def test_name_is_cleaned_before_storage(self) -> None:
        response = self.client.post(
            self.endpoint(), json={"name": "  公共   沙滩  "}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["large_scene"]["name"], "公共 沙滩")

    def test_blank_name_is_rejected(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "   "})
        self.assertEqual(response.status_code, 422)

    def test_too_long_name_is_rejected(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "场" * 81})
        self.assertEqual(response.status_code, 422)

    def test_duplicate_name_in_same_chapter_is_rejected(self) -> None:
        self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        response = self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        self.assertEqual(response.status_code, 409)

    def test_missing_chapter_returns_404(self) -> None:
        self.assertEqual(self.client.get(self.endpoint("missing")).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.endpoint("missing"), json={"name": "孤立场景"}
            ).status_code,
            404,
        )

    def test_same_name_is_allowed_in_different_chapters(self) -> None:
        other = self.manager.create_chapter(str(self.project["id"]), "第二章")
        self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        response = self.client.post(
            self.endpoint(str(other["id"])), json={"name": "公共沙滩"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.manager.list_large_scenes(str(other["id"]))), 1)

    def test_rename_large_scene_updates_name(self) -> None:
        large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "旧名称"
        )
        response = self.client.patch(
            f"/api/large-scenes/{large_scene['id']}",
            json={"name": "  新   名称  "},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["large_scene"]["name"], "新 名称")
        self.assertEqual(
            self.manager.get_large_scene(str(large_scene["id"]))["name"],
            "新 名称",
        )

    def test_rename_large_scene_rejects_duplicate_name(self) -> None:
        first = self.manager.create_large_scene(
            str(self.chapter["id"]), "公共沙滩"
        )
        self.manager.create_large_scene(str(self.chapter["id"]), "浅水区")
        response = self.client.patch(
            f"/api/large-scenes/{first['id']}", json={"name": "浅水区"}
        )
        self.assertEqual(response.status_code, 409)

    def test_rename_large_scene_rejects_blank_name(self) -> None:
        large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "公共沙滩"
        )
        response = self.client.patch(
            f"/api/large-scenes/{large_scene['id']}", json={"name": "   "}
        )
        self.assertEqual(response.status_code, 422)

    def test_rename_missing_large_scene_returns_404(self) -> None:
        response = self.client.patch(
            "/api/large-scenes/missing-id", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_large_scene_removes_only_target(self) -> None:
        first = self.manager.create_large_scene(
            str(self.chapter["id"]), "公共沙滩"
        )
        second = self.manager.create_large_scene(
            str(self.chapter["id"]), "浅水区"
        )
        response = self.client.delete(f"/api/large-scenes/{first['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"]["id"], first["id"])
        remaining = self.manager.list_large_scenes(str(self.chapter["id"]))
        self.assertEqual([item["id"] for item in remaining], [second["id"]])

    def test_delete_missing_large_scene_returns_404(self) -> None:
        response = self.client.delete("/api/large-scenes/missing-id")
        self.assertEqual(response.status_code, 404)


class LargeSceneDatabaseTests(unittest.TestCase):
    def test_large_scene_is_written_only_to_test_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(
                Path(directory),
                environment="test",
                locked_environment="test",
            )
            project = manager.create_project("隔离项目")
            chapter = manager.create_chapter(str(project["id"]), "第一章")
            manager.create_large_scene(str(chapter["id"]), "公共沙滩")

            self.assertEqual(
                len(manager.list_large_scenes(str(chapter["id"]), "test")), 1
            )
            self.assertEqual(
                len(manager.list_large_scenes(str(chapter["id"]), "production")), 0
            )

    def test_sort_order_is_independent_per_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("排序项目")
            first = manager.create_chapter(str(project["id"]), "第一章")
            second = manager.create_chapter(str(project["id"]), "第二章")
            a = manager.create_large_scene(str(first["id"]), "A")
            b = manager.create_large_scene(str(first["id"]), "B")
            c = manager.create_large_scene(str(second["id"]), "C")
            self.assertEqual([a["sort_order"], b["sort_order"]], [1, 2])
            self.assertEqual(c["sort_order"], 1)

    def test_chapter_delete_cascades_to_large_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("级联项目")
            chapter = manager.create_chapter(str(project["id"]), "第一章")
            manager.create_large_scene(str(chapter["id"]), "公共沙滩")
            with manager.connection() as connection:
                connection.execute(
                    "DELETE FROM chapters WHERE id = ?", (str(chapter["id"]),)
                )
            self.assertEqual(
                manager.list_large_scenes(str(chapter["id"])), []
            )


if __name__ == "__main__":
    unittest.main()
