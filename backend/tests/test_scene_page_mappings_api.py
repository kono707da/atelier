from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class ScenePageMappingsApiTests(unittest.TestCase):
    """场景页素材页映射接口测试
    （/api/small-scene-pages/{id}/mappings/{material_type}）。
    """

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
            name="构图素材", material_type="composition", content="构图内容"
        )
        # 关联素材到小场景
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        # 创建场景页
        self.scene_page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "场景页1"
        )
        # create_material 自动生成默认素材页
        self.default_page = self.manager.list_material_pages(
            str(self.material["id"])
        )[0]

    def mapping_url(self, material_type: str = "composition", page_id: str | None = None) -> str:
        pid = page_id or str(self.scene_page["id"])
        return f"/api/small-scene-pages/{pid}/mappings/{material_type}"

    def test_set_mapping(self) -> None:
        response = self.client.put(
            self.mapping_url(),
            json={"material_page_id": str(self.default_page["id"])},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # Per second-round contract 8.4: mapping wrapped in `mapping` key
        mapping = body["mapping"]
        self.assertEqual(mapping["scene_page_id"], self.scene_page["id"])
        self.assertEqual(mapping["material_page_id"], self.default_page["id"])
        self.assertEqual(mapping["material_type"], "composition")

    def test_unset_mapping(self) -> None:
        self.client.put(
            self.mapping_url(),
            json={"material_page_id": str(self.default_page["id"])},
        )
        response = self.client.delete(self.mapping_url())
        self.assertEqual(response.status_code, 200)

    def test_unset_missing_mapping_returns_404(self) -> None:
        response = self.client.delete(self.mapping_url())
        self.assertEqual(response.status_code, 404)

    def test_atomic_replace_same_type(self) -> None:
        # 创建第二个素材页（同素材、同 composition 类型）
        second_page = self.manager.create_material_page(
            str(self.material["id"]), "第二页", content="内容2"
        )
        # 先设置第一个映射
        self.client.put(
            self.mapping_url(),
            json={"material_page_id": str(self.default_page["id"])},
        )
        # 同类型原子替换为第二个
        response = self.client.put(
            self.mapping_url(),
            json={"material_page_id": str(second_page["id"])},
        )
        self.assertEqual(response.status_code, 200)
        # 验证工作区只有 1 个映射，且指向第二个素材页
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        mappings = ws["mappings"]
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["material_page_id"], second_page["id"])

    def test_invalid_material_type_returns_422(self) -> None:
        response = self.client.put(
            self.mapping_url("invalid_type"),
            json={"material_page_id": str(self.default_page["id"])},
        )
        self.assertEqual(response.status_code, 422)

    def test_material_type_mismatch_returns_422(self) -> None:
        # 素材是 composition，用 expression 类型设置映射应被拒绝
        response = self.client.put(
            self.mapping_url("expression"),
            json={"material_page_id": str(self.default_page["id"])},
        )
        self.assertEqual(response.status_code, 422)

    def test_missing_scene_page_returns_404(self) -> None:
        response = self.client.put(
            "/api/small-scene-pages/missing-id/mappings/composition",
            json={"material_page_id": str(self.default_page["id"])},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_invalid_material_type_returns_422(self) -> None:
        response = self.client.delete(self.mapping_url("invalid_type"))
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
