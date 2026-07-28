from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class ScenePagesApiTests(unittest.TestCase):
    """场景页 CRUD 接口测试（前端契约接口 /api/small-scenes/{id}/pages）。"""

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

    def pages_endpoint(self, small_scene_id: str | None = None) -> str:
        return f"/api/small-scenes/{small_scene_id or self.small_scene['id']}/pages"

    def test_create_scene_page(self) -> None:
        response = self.client.post(
            self.pages_endpoint(), json={"name": "场景页1", "description": "说明"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "场景页1")
        self.assertEqual(body["description"], "说明")
        self.assertEqual(body["small_scene_id"], self.small_scene["id"])
        self.assertEqual(body["sort_order"], 1)
        self.assertIn("id", body)

    def test_create_uses_name_not_title(self) -> None:
        response = self.client.post(self.pages_endpoint(), json={"name": "命名页"})
        body = response.json()
        self.assertIn("name", body)
        self.assertNotIn("title", body)

    def test_create_blank_name_returns_422(self) -> None:
        response = self.client.post(self.pages_endpoint(), json={"name": ""})
        self.assertEqual(response.status_code, 422)

    def test_create_whitespace_name_returns_422(self) -> None:
        response = self.client.post(self.pages_endpoint(), json={"name": "   "})
        self.assertEqual(response.status_code, 422)

    def test_create_duplicate_name_case_insensitive_returns_422(self) -> None:
        self.client.post(self.pages_endpoint(), json={"name": "PageA"})
        response = self.client.post(self.pages_endpoint(), json={"name": "pagea"})
        self.assertEqual(response.status_code, 422)

    def test_create_missing_small_scene_returns_404(self) -> None:
        response = self.client.post(
            "/api/small-scenes/missing-id/pages", json={"name": "孤立页"}
        )
        self.assertEqual(response.status_code, 404)

    def test_update_scene_page_name(self) -> None:
        created = self.client.post(self.pages_endpoint(), json={"name": "旧名"}).json()
        response = self.client.patch(
            f"/api/small-scene-pages/{created['id']}", json={"name": "新名"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "新名")

    def test_delete_scene_page(self) -> None:
        created = self.client.post(self.pages_endpoint(), json={"name": "待删页"}).json()
        response = self.client.delete(f"/api/small-scene-pages/{created['id']}")
        self.assertEqual(response.status_code, 200)
        again = self.client.delete(f"/api/small-scene-pages/{created['id']}")
        self.assertEqual(again.status_code, 404)

    def test_reorder_scene_pages(self) -> None:
        a = self.client.post(self.pages_endpoint(), json={"name": "A"}).json()
        b = self.client.post(self.pages_endpoint(), json={"name": "B"}).json()
        c = self.client.post(self.pages_endpoint(), json={"name": "C"}).json()
        response = self.client.put(
            self.pages_endpoint() + "/order",
            json={"page_ids": [c["id"], a["id"], b["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        pages = response.json()["pages"]
        self.assertEqual([p["name"] for p in pages], ["C", "A", "B"])
        self.assertEqual([p["sort_order"] for p in pages], [1, 2, 3])

    def test_delete_renumbers_remaining(self) -> None:
        self.client.post(self.pages_endpoint(), json={"name": "A"})
        b = self.client.post(self.pages_endpoint(), json={"name": "B"}).json()
        self.client.post(self.pages_endpoint(), json={"name": "C"})
        self.client.delete(f"/api/small-scene-pages/{b['id']}")
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        pages = ws["pages"]
        self.assertEqual([p["name"] for p in pages], ["A", "C"])
        self.assertEqual([p["sort_order"] for p in pages], [1, 2])


if __name__ == "__main__":
    unittest.main()
