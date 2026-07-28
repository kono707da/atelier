from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class MaterialPagesApiTests(unittest.TestCase):
    """素材页 CRUD 接口测试（/api/materials/{id}/pages、/api/material-pages/{id}）。"""

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
        self.material = self.manager.create_material(
            name="测试素材", material_type="composition", content="构图内容"
        )

    def pages_endpoint(self, material_id: str | None = None) -> str:
        return f"/api/materials/{material_id or self.material['id']}/pages"

    def test_create_material_auto_generates_default_page(self) -> None:
        # 需求 3.3/5.4：新建素材时必须自动生成一个默认素材页
        response = self.client.get(self.pages_endpoint())
        self.assertEqual(response.status_code, 200)
        pages = response.json()["pages"]
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["name"], "测试素材")
        self.assertEqual(pages[0]["sort_order"], 1)
        self.assertEqual(pages[0]["content"], "构图内容")
        self.assertEqual(pages[0]["material_id"], self.material["id"])

    def test_list_material_pages(self) -> None:
        response = self.client.get(self.pages_endpoint())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["material_id"], self.material["id"])
        self.assertIsInstance(body["pages"], list)

    def test_create_material_page(self) -> None:
        response = self.client.post(
            self.pages_endpoint(),
            json={"name": "第二页", "description": "说明", "content": "内容"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["name"], "第二页")
        self.assertEqual(body["description"], "说明")
        self.assertEqual(body["content"], "内容")
        self.assertEqual(body["material_id"], self.material["id"])
        self.assertEqual(body["sort_order"], 2)

    def test_create_duplicate_name_case_insensitive_returns_422(self) -> None:
        # 默认页名称为 "测试素材"，同素材下同名（忽略大小写）应拒绝
        response = self.client.post(self.pages_endpoint(), json={"name": "测试素材"})
        self.assertEqual(response.status_code, 422)

    def test_create_blank_name_returns_422(self) -> None:
        response = self.client.post(self.pages_endpoint(), json={"name": ""})
        self.assertEqual(response.status_code, 422)

    def test_get_material_page(self) -> None:
        created = self.client.post(
            self.pages_endpoint(), json={"name": "查询页"}
        ).json()
        response = self.client.get(f"/api/material-pages/{created['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], created["id"])
        self.assertEqual(response.json()["name"], "查询页")

    def test_update_material_page(self) -> None:
        created = self.client.post(
            self.pages_endpoint(), json={"name": "旧名"}
        ).json()
        response = self.client.patch(
            f"/api/material-pages/{created['id']}", json={"name": "新名"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "新名")

    def test_delete_material_page(self) -> None:
        created = self.client.post(
            self.pages_endpoint(), json={"name": "待删页"}
        ).json()
        response = self.client.delete(f"/api/material-pages/{created['id']}")
        self.assertEqual(response.status_code, 200)
        again = self.client.get(f"/api/material-pages/{created['id']}")
        self.assertEqual(again.status_code, 404)

    def test_reorder_material_pages(self) -> None:
        default_page = self.client.get(self.pages_endpoint()).json()["pages"][0]
        b = self.client.post(self.pages_endpoint(), json={"name": "B"}).json()
        c = self.client.post(self.pages_endpoint(), json={"name": "C"}).json()
        response = self.client.put(
            self.pages_endpoint() + "/order",
            json={"page_ids": [c["id"], default_page["id"], b["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        pages = response.json()["pages"]
        self.assertEqual([p["name"] for p in pages], ["C", "测试素材", "B"])
        self.assertEqual([p["sort_order"] for p in pages], [1, 2, 3])

    def test_missing_material_returns_404(self) -> None:
        response = self.client.get("/api/materials/missing-id/pages")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
