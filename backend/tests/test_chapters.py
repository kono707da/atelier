from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class ChapterApiTests(unittest.TestCase):
    """章节接口层测试：使用临时目录锁定测试库。"""

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
        self.project = self.manager.create_project("章节测试项目")

    # --- 创建与读取 ---

    def test_create_chapter_returns_201_with_full_shape(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/chapters",
            json={"name": "第一章"},
        )
        self.assertEqual(response.status_code, 201)
        chapter = response.json()["chapter"]
        self.assertEqual(chapter["project_id"], self.project["id"])
        self.assertEqual(chapter["name"], "第一章")
        self.assertEqual(chapter["sort_order"], 1)
        for key in ("id", "created_at", "updated_at"):
            self.assertIn(key, chapter)

    def test_list_returns_chapters_sorted_by_sort_order(self) -> None:
        for name in ("一", "二", "三"):
            self.client.post(
                f"/api/projects/{self.project['id']}/chapters", json={"name": name}
            )
        response = self.client.get(
            f"/api/projects/{self.project['id']}/chapters"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual([i["sort_order"] for i in body["items"]], [1, 2, 3])
        self.assertEqual([i["name"] for i in body["items"]], ["一", "二", "三"])

    def test_empty_project_returns_empty_list(self) -> None:
        response = self.client.get(
            f"/api/projects/{self.project['id']}/chapters"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["items"], [])

    def test_name_is_cleaned_before_storage(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/chapters",
            json={"name": "  第一章  "},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["chapter"]["name"], "第一章")

    # --- 校验 ---

    def test_empty_name_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/chapters", json={"name": ""}
        )
        self.assertEqual(response.status_code, 422)

    def test_whitespace_only_name_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/chapters", json={"name": "   "}
        )
        self.assertEqual(response.status_code, 422)

    def test_too_long_name_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/chapters",
            json={"name": "字" * 81},
        )
        self.assertEqual(response.status_code, 422)

    def test_duplicate_chapter_name_in_same_project_rejected(self) -> None:
        self.client.post(
            f"/api/projects/{self.project['id']}/chapters", json={"name": "同名章节"}
        )
        response = self.client.post(
            f"/api/projects/{self.project['id']}/chapters", json={"name": "同名章节"}
        )
        self.assertEqual(response.status_code, 409)

    def test_nonexistent_project_returns_404_on_get(self) -> None:
        response = self.client.get("/api/projects/missing-id/chapters")
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_project_returns_404_on_post(self) -> None:
        response = self.client.post(
            "/api/projects/missing-id/chapters", json={"name": "孤儿章节"}
        )
        self.assertEqual(response.status_code, 404)

    # --- 改名与删除 ---

    def test_rename_chapter_updates_name(self) -> None:
        chapter = self.manager.create_chapter(
            str(self.project["id"]), "旧章节名"
        )
        response = self.client.patch(
            f"/api/chapters/{chapter['id']}",
            json={"name": "  新   章节名  "},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["chapter"]["name"], "新 章节名")
        self.assertEqual(
            self.manager.get_chapter(str(chapter["id"]))["name"], "新 章节名"
        )

    def test_rename_chapter_rejects_duplicate_name(self) -> None:
        first = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )
        self.manager.create_chapter(str(self.project["id"]), "第二章")
        response = self.client.patch(
            f"/api/chapters/{first['id']}", json={"name": "第二章"}
        )
        self.assertEqual(response.status_code, 409)

    def test_rename_chapter_rejects_blank_name(self) -> None:
        chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )
        response = self.client.patch(
            f"/api/chapters/{chapter['id']}", json={"name": "   "}
        )
        self.assertEqual(response.status_code, 422)

    def test_rename_missing_chapter_returns_404(self) -> None:
        response = self.client.patch(
            "/api/chapters/missing-id", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_chapter_removes_its_large_scenes(self) -> None:
        chapter = self.manager.create_chapter(
            str(self.project["id"]), "待删除章节"
        )
        self.manager.create_large_scene(str(chapter["id"]), "子场景")
        response = self.client.delete(f"/api/chapters/{chapter['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"]["id"], chapter["id"])
        self.assertIsNone(self.manager.get_chapter(str(chapter["id"])))
        self.assertEqual(
            self.manager.list_large_scenes(str(chapter["id"])), []
        )

    def test_delete_missing_chapter_returns_404(self) -> None:
        response = self.client.delete("/api/chapters/missing-id")
        self.assertEqual(response.status_code, 404)

    # --- 跨项目隔离 ---

    def test_chapters_do_not_mix_between_projects(self) -> None:
        other = self.manager.create_project("另一个项目")
        self.client.post(
            f"/api/projects/{self.project['id']}/chapters", json={"name": "共享名"}
        )
        # 同名章节在不同项目下允许创建
        response = self.client.post(
            f"/api/projects/{other['id']}/chapters", json={"name": "共享名"}
        )
        self.assertEqual(response.status_code, 201)

        own = self.client.get(
            f"/api/projects/{self.project['id']}/chapters"
        ).json()["items"]
        other_items = self.client.get(
            f"/api/projects/{other['id']}/chapters"
        ).json()["items"]
        self.assertEqual(len(own), 1)
        self.assertEqual(len(other_items), 1)
        self.assertEqual(own[0]["project_id"], self.project["id"])
        self.assertEqual(other_items[0]["project_id"], other["id"])

    # --- 双数据库隔离 ---

    def test_chapter_written_only_to_test_database(self) -> None:
        self.client.post(
            f"/api/projects/{self.project['id']}/chapters", json={"name": "隔离章节"}
        )
        self.assertEqual(
            len(self.manager.list_chapters(self.project["id"], "test")), 1
        )
        self.assertEqual(
            len(self.manager.list_chapters(self.project["id"], "production")), 0
        )
        self.assertEqual(self.manager.list_projects(environment="production")["total"], 0)
        self.assertEqual(self.manager.list_projects(environment="test")["total"], 1)


class ChapterDatabaseTests(unittest.TestCase):
    """章节数据库层测试：直接操作 DatabaseManager，验证隔离与级联。"""

    def test_create_chapter_does_not_touch_production(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(
                Path(directory),
                environment="test",
                locked_environment="test",
            )
            project = manager.create_project("隔离项目")
            manager.create_chapter(str(project["id"]), "章节 A")

            self.assertEqual(
                len(manager.list_chapters(str(project["id"]), "test")), 1
            )
            self.assertEqual(
                len(manager.list_chapters(str(project["id"]), "production")), 0
            )
            self.assertIsNone(
                manager.get_project(str(project["id"]), "production")
            )

    def test_create_chapter_rejects_nonexistent_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            with self.assertRaises(ValueError):
                manager.create_chapter("missing-id", "孤儿章节")

    def test_create_chapter_rejects_duplicate_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("重名测试")
            manager.create_chapter(str(project["id"]), "唯一章节")
            with self.assertRaises(ValueError):
                manager.create_chapter(str(project["id"]), "唯一章节")

    def test_sort_order_starts_at_one_and_increments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("排序项目")
            c1 = manager.create_chapter(str(project["id"]), "一")
            c2 = manager.create_chapter(str(project["id"]), "二")
            c3 = manager.create_chapter(str(project["id"]), "三")
            self.assertEqual(
                [c1["sort_order"], c2["sort_order"], c3["sort_order"]], [1, 2, 3]
            )

    def test_cascade_delete_removes_chapters_when_project_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("级联项目")
            manager.create_chapter(str(project["id"]), "章节一")
            self.assertEqual(
                len(manager.list_chapters(str(project["id"]))), 1
            )
            with manager.connection() as connection:
                connection.execute(
                    "DELETE FROM projects WHERE id = ?", (str(project["id"]),)
                )
            self.assertEqual(
                len(manager.list_chapters(str(project["id"]))), 0
            )


if __name__ == "__main__":
    unittest.main()
