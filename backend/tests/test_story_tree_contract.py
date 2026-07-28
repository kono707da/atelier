from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class StoryTreeContractTests(unittest.TestCase):
    """GET /api/projects/{project_id}/story-tree 契约测试。"""

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
        self.project = self.manager.create_project("测试项目")
        self.chapter = self.manager.create_chapter(str(self.project["id"]), "第一章")
        self.large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "大场景A"
        )
        self.small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "小场景A"
        )

    def test_empty_project_returns_empty_chapters(self) -> None:
        empty_project = self.manager.create_project("空项目")
        response = self.client.get(f"/api/projects/{empty_project['id']}/story-tree")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["chapters"], [])
        self.assertTrue(body["backendAvailable"])
        self.assertEqual(body["project_id"], empty_project["id"])

    def test_missing_project_returns_404(self) -> None:
        response = self.client.get("/api/projects/missing-id/story-tree")
        self.assertEqual(response.status_code, 404)

    def test_four_level_nesting(self) -> None:
        self.manager.create_shot_page(str(self.small_scene["id"]), "场景页1")
        response = self.client.get(f"/api/projects/{self.project['id']}/story-tree")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        chapters = body["chapters"]
        self.assertEqual(len(chapters), 1)
        chapter = chapters[0]
        self.assertEqual(chapter["id"], self.chapter["id"])
        self.assertEqual(len(chapter["large_scenes"]), 1)
        ls = chapter["large_scenes"][0]
        self.assertEqual(ls["id"], self.large_scene["id"])
        self.assertEqual(len(ls["small_scenes"]), 1)
        ss = ls["small_scenes"][0]
        self.assertEqual(ss["id"], self.small_scene["id"])
        self.assertEqual(len(ss["pages"]), 1)
        self.assertEqual(ss["pages"][0]["name"], "场景页1")

    def test_pages_use_name_not_title(self) -> None:
        self.manager.create_shot_page(str(self.small_scene["id"]), "命名页")
        response = self.client.get(f"/api/projects/{self.project['id']}/story-tree")
        page = (
            response.json()["chapters"][0]["large_scenes"][0]["small_scenes"][0]["pages"][0]
        )
        self.assertIn("name", page)
        self.assertNotIn("title", page)

    def test_backend_available_flag(self) -> None:
        response = self.client.get(f"/api/projects/{self.project['id']}/story-tree")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["backendAvailable"])

    def test_pages_sorted_by_sort_order(self) -> None:
        self.manager.create_shot_page(str(self.small_scene["id"]), "第一页")
        self.manager.create_shot_page(str(self.small_scene["id"]), "第二页")
        response = self.client.get(f"/api/projects/{self.project['id']}/story-tree")
        pages = response.json()["chapters"][0]["large_scenes"][0]["small_scenes"][0]["pages"]
        self.assertEqual([p["name"] for p in pages], ["第一页", "第二页"])
        self.assertEqual([p["sort_order"] for p in pages], [1, 2])

    def test_branch_pages_excluded(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        self.manager.create_shot_page(str(self.small_scene["id"]), "主线页")
        self.manager.create_shot_page(
            str(self.small_scene["id"]), "分支页", branch_id=str(branch["id"])
        )
        response = self.client.get(f"/api/projects/{self.project['id']}/story-tree")
        pages = response.json()["chapters"][0]["large_scenes"][0]["small_scenes"][0]["pages"]
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["name"], "主线页")


if __name__ == "__main__":
    unittest.main()
