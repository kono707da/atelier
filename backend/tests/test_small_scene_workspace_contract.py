from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class SmallSceneWorkspaceContractTests(unittest.TestCase):
    """GET /api/small-scenes/{small_scene_id}/workspace 契约测试。"""

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
        self.material = self.manager.create_material(
            name="表情素材", material_type="expression", content="表情内容"
        )

    def test_response_fields_present(self) -> None:
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        for key in ("small_scene", "chapter", "large_scene", "pages", "resources", "mappings"):
            self.assertIn(key, body)
        self.assertEqual(body["small_scene"]["id"], self.small_scene["id"])
        self.assertEqual(body["chapter"]["id"], self.chapter["id"])
        self.assertEqual(body["large_scene"]["id"], self.large_scene["id"])

    def test_missing_small_scene_returns_404(self) -> None:
        response = self.client.get("/api/small-scenes/missing-id/workspace")
        self.assertEqual(response.status_code, 404)

    def test_empty_workspace_returns_empty_arrays(self) -> None:
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["pages"], [])
        self.assertEqual(body["resources"], [])
        self.assertEqual(body["mappings"], [])

    def test_pages_use_name_field(self) -> None:
        self.manager.create_shot_page(str(self.small_scene["id"]), "场景页1")
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        )
        pages = response.json()["pages"]
        self.assertEqual(len(pages), 1)
        self.assertIn("name", pages[0])
        self.assertNotIn("title", pages[0])
        self.assertEqual(pages[0]["name"], "场景页1")

    def test_resources_include_link_id_material_id_and_pages(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        )
        resources = response.json()["resources"]
        self.assertEqual(len(resources), 1)
        resource = resources[0]
        self.assertIn("link_id", resource)
        self.assertIn("material_id", resource)
        self.assertEqual(resource["material_id"], self.material["id"])
        self.assertIn("pages", resource)
        self.assertIsInstance(resource["pages"], list)

    def test_resource_pages_contain_auto_generated_default_page(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        )
        resource = response.json()["resources"][0]
        # create_material 自动生成默认素材页，名称与素材一致
        self.assertEqual(len(resource["pages"]), 1)
        self.assertEqual(resource["pages"][0]["name"], "表情素材")
        self.assertEqual(resource["pages"][0]["material_id"], self.material["id"])

    def test_mappings_reflect_set_mapping(self) -> None:
        page = self.manager.create_shot_page(str(self.small_scene["id"]), "场景页1")
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        default_mp = self.manager.list_material_pages(str(self.material["id"]))[0]
        self.manager.set_small_scene_page_mapping(
            str(page["id"]), "expression", str(default_mp["id"])
        )
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        )
        mappings = response.json()["mappings"]
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["scene_page_id"], page["id"])
        self.assertEqual(mappings[0]["material_page_id"], default_mp["id"])
        self.assertEqual(mappings[0]["material_type"], "expression")


if __name__ == "__main__":
    unittest.main()
