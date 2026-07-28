"""Second-round rectification tests.

Covers requirements from 《Atelier 小场景画布第二轮验收整改需求》:
- 11.1 story-tree: page_count, resource_count, resources with pages, sort order
- 11.2 mapping validation: 未关联422, 跨场景422, 类型不一致422, 同类型替换, PUT null 取消
- 11.3 remove association: deleted_mapping_count, 不删素材, 不删其他小场景映射
- 11.4 reorder: 完整集合校验（缺失/重复/跨场景/分支/不存在）, 单事务回滚
- 11.5 status codes: 201/200/409 + page/resource/mapping wrappers
- 11.6 link_id: 新接口非空, 旧批量接口保留 id, 历史空 ID 修复
"""
from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class SecondRoundStoryTreeTests(unittest.TestCase):
    """11.1 story-tree 返回完整字段。"""

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
        self.project = self.manager.create_project("项目")
        self.chapter = self.manager.create_chapter(str(self.project["id"]), "章")
        self.large_scene = self.manager.create_large_scene(str(self.chapter["id"]), "大场景")
        self.small_scene = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景")
        # Create 3 scene pages
        self.pages = [
            self.manager.create_shot_page(str(self.small_scene["id"]), f"P{i+1}")
            for i in range(3)
        ]
        # Create material + associate
        self.material = self.manager.create_material(
            name="表情素材", material_type="expression", content="内容"
        )
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )

    def test_story_tree_includes_page_count_and_resource_count(self) -> None:
        body = self.client.get(f"/api/projects/{self.project['id']}/story-tree").json()
        small = body["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        self.assertEqual(small["page_count"], 3)
        self.assertEqual(small["resource_count"], 1)

    def test_story_tree_includes_resources_with_pages_and_page_count(self) -> None:
        body = self.client.get(f"/api/projects/{self.project['id']}/story-tree").json()
        small = body["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        resources = small["resources"]
        self.assertEqual(len(resources), 1)
        r = resources[0]
        self.assertIn("link_id", r)
        self.assertTrue(r["link_id"])
        self.assertEqual(r["material_id"], self.material["id"])
        self.assertEqual(r["name"], "表情素材")
        self.assertEqual(r["material_type"], "expression")
        self.assertIn("pages", r)
        # create_material auto-generates 1 default page
        self.assertEqual(r["page_count"], 1)
        self.assertEqual(len(r["pages"]), 1)

    def test_story_tree_empty_resources_when_none_associated(self) -> None:
        # New small scene with no resources
        ss2 = self.manager.create_small_scene(str(self.large_scene["id"]), "空小场景")
        body = self.client.get(f"/api/projects/{self.project['id']}/story-tree").json()
        small_scenes = body["chapters"][0]["large_scenes"][0]["small_scenes"]
        ss2_data = next(s for s in small_scenes if s["id"] == ss2["id"])
        self.assertEqual(ss2_data["resources"], [])
        self.assertEqual(ss2_data["resource_count"], 0)
        self.assertEqual(ss2_data["pages"], [])
        self.assertEqual(ss2_data["page_count"], 0)

    def test_story_tree_sort_order_ascending(self) -> None:
        body = self.client.get(f"/api/projects/{self.project['id']}/story-tree").json()
        small = body["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        page_orders = [p["sort_order"] for p in small["pages"]]
        self.assertEqual(page_orders, sorted(page_orders))
        self.assertEqual(page_orders, [1, 2, 3])


class SecondRoundMappingValidationTests(unittest.TestCase):
    """11.2 映射关联校验。"""

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
        self.project = self.manager.create_project("项目")
        self.chapter = self.manager.create_chapter(str(self.project["id"]), "章")
        self.large_scene = self.manager.create_large_scene(str(self.chapter["id"]), "大场景")
        self.small_scene = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景A")
        self.small_scene2 = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景B")
        self.scene_page = self.manager.create_shot_page(str(self.small_scene["id"]), "P1")
        self.material = self.manager.create_material(
            name="表情", material_type="expression", content="内容"
        )
        self.material_page = self.manager.list_material_pages(str(self.material["id"]))[0]

    def test_unassociated_material_page_returns_422(self) -> None:
        # Material not associated to small_scene
        response = self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        self.assertEqual(response.status_code, 422)

    def test_associated_material_can_map(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        response = self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("mapping", response.json())

    def test_material_associated_to_other_small_scene_returns_422(self) -> None:
        # Associate to small_scene2, then try to map to a page in small_scene
        self.manager.add_small_scene_resource(
            str(self.small_scene2["id"]), str(self.material["id"])
        )
        response = self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        self.assertEqual(response.status_code, 422)

    def test_material_type_mismatch_returns_422(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        response = self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/composition",
            json={"material_page_id": str(self.material_page["id"])},
        )
        self.assertEqual(response.status_code, 422)

    def test_same_type_replace_old_mapping(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        # Create a second material page
        second_page = self.manager.create_material_page(str(self.material["id"]), "第二页")
        # Set first mapping
        self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        # Replace with second page
        response = self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/expression",
            json={"material_page_id": str(second_page["id"])},
        )
        self.assertEqual(response.status_code, 200)
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        mappings = ws["mappings"]
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["material_page_id"], second_page["id"])

    def test_one_material_page_can_map_to_multiple_scene_pages(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        page2 = self.manager.create_shot_page(str(self.small_scene["id"]), "P2")
        # Map same material_page to both scene pages
        for pid in [self.scene_page["id"], page2["id"]]:
            response = self.client.put(
                f"/api/small-scene-pages/{pid}/mappings/expression",
                json={"material_page_id": str(self.material_page["id"])},
            )
            self.assertEqual(response.status_code, 200)

    def test_put_null_unsets_mapping(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        # Set mapping first
        self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        # PUT null to unset
        response = self.client.put(
            f"/api/small-scene-pages/{self.scene_page['id']}/mappings/expression",
            json={"material_page_id": None},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["mapping"])
        # Verify mapping is gone in workspace
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        self.assertEqual(len(ws["mappings"]), 0)


class SecondRoundRemoveAssociationTests(unittest.TestCase):
    """11.3 移除关联级联删除映射。"""

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
        self.project = self.manager.create_project("项目")
        self.chapter = self.manager.create_chapter(str(self.project["id"]), "章")
        self.large_scene = self.manager.create_large_scene(str(self.chapter["id"]), "大场景")
        self.small_scene = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景A")
        self.small_scene2 = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景B")
        self.scene_page1 = self.manager.create_shot_page(str(self.small_scene["id"]), "P1")
        self.scene_page2 = self.manager.create_shot_page(str(self.small_scene["id"]), "P2")
        self.material = self.manager.create_material(
            name="表情", material_type="expression", content="内容"
        )
        self.material_page = self.manager.list_material_pages(str(self.material["id"]))[0]
        # Associate to both small scenes
        self.link1 = self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        self.manager.add_small_scene_resource(
            str(self.small_scene2["id"]), str(self.material["id"])
        )
        # Map material_page to both pages in small_scene, and to a page in small_scene2
        self.client.put(
            f"/api/small-scene-pages/{self.scene_page1['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        self.client.put(
            f"/api/small-scene-pages/{self.scene_page2['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        ss2_page = self.manager.create_shot_page(str(self.small_scene2["id"]), "SS2-P1")
        self.client.put(
            f"/api/small-scene-pages/{ss2_page['id']}/mappings/expression",
            json={"material_page_id": str(self.material_page["id"])},
        )
        self.ss2_page = ss2_page

    def test_remove_link_deletes_mappings_in_same_small_scene(self) -> None:
        response = self.client.delete(
            f"/api/small-scene-resource-links/{self.link1['link_id']}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("deleted", body)
        self.assertEqual(body["deleted"]["deleted_mapping_count"], 2)
        # Workspace of small_scene should have no mappings
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        self.assertEqual(len(ws["mappings"]), 0)
        self.assertEqual(len(ws["resources"]), 0)

    def test_remove_link_does_not_delete_material_or_material_pages(self) -> None:
        self.client.delete(f"/api/small-scene-resource-links/{self.link1['link_id']}")
        mat = self.manager.get_material(str(self.material["id"]))
        self.assertIsNotNone(mat)
        pages = self.manager.list_material_pages(str(self.material["id"]))
        self.assertEqual(len(pages), 1)

    def test_remove_link_does_not_delete_other_small_scene_mappings(self) -> None:
        self.client.delete(f"/api/small-scene-resource-links/{self.link1['link_id']}")
        ws2 = self.client.get(
            f"/api/small-scenes/{self.small_scene2['id']}/workspace"
        ).json()
        self.assertEqual(len(ws2["mappings"]), 1)
        self.assertEqual(len(ws2["resources"]), 1)

    def test_remove_link_no_orphan_mappings(self) -> None:
        self.client.delete(f"/api/small-scene-resource-links/{self.link1['link_id']}")
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        # No "素材 · 未命名页" orphans - mappings array empty
        for m in ws["mappings"]:
            self.assertNotEqual(m.get("material_page_name"), "未命名页")


class SecondRoundReorderTests(unittest.TestCase):
    """11.4 排序完整集合校验 + 单事务。"""

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
        self.project = self.manager.create_project("项目")
        self.chapter = self.manager.create_chapter(str(self.project["id"]), "章")
        self.large_scene = self.manager.create_large_scene(str(self.chapter["id"]), "大场景")
        self.small_scene = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景A")
        self.small_scene2 = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景B")
        self.a = self.manager.create_shot_page(str(self.small_scene["id"]), "A")
        self.b = self.manager.create_shot_page(str(self.small_scene["id"]), "B")
        self.c = self.manager.create_shot_page(str(self.small_scene["id"]), "C")
        # Create a branch and a branch page (should be rejected in reorder)
        self.branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支1"
        )
        self.branch_page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分支页", branch_id=str(self.branch["id"])
        )
        # Page in another small scene
        self.ss2_page = self.manager.create_shot_page(str(self.small_scene2["id"]), "SS2")

    def order_endpoint(self) -> str:
        return f"/api/small-scenes/{self.small_scene['id']}/pages/order"

    def test_valid_full_set_reorder_succeeds(self) -> None:
        response = self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.c["id"], self.a["id"], self.b["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        pages = response.json()["pages"]
        self.assertEqual([p["name"] for p in pages], ["C", "A", "B"])
        self.assertEqual([p["sort_order"] for p in pages], [1, 2, 3])

    def test_missing_id_returns_422(self) -> None:
        response = self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.a["id"], self.b["id"]]},  # missing C
        )
        self.assertEqual(response.status_code, 422)

    def test_duplicate_id_returns_422(self) -> None:
        response = self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.a["id"], self.a["id"], self.b["id"], self.c["id"]]},
        )
        self.assertEqual(response.status_code, 422)

    def test_cross_small_scene_id_returns_422(self) -> None:
        response = self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.a["id"], self.b["id"], self.c["id"], self.ss2_page["id"]]},
        )
        self.assertEqual(response.status_code, 422)

    def test_branch_page_id_returns_422(self) -> None:
        response = self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.a["id"], self.b["id"], self.c["id"], self.branch_page["id"]]},
        )
        self.assertEqual(response.status_code, 422)

    def test_nonexistent_id_returns_422(self) -> None:
        response = self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.a["id"], self.b["id"], self.c["id"], "nonexistent-id"]},
        )
        self.assertEqual(response.status_code, 422)

    def test_failed_reorder_preserves_original_order(self) -> None:
        # Attempt a bad reorder
        self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.a["id"], self.b["id"]]},  # missing C
        )
        # Original order preserved
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        pages = ws["pages"]
        self.assertEqual([p["name"] for p in pages], ["A", "B", "C"])
        self.assertEqual([p["sort_order"] for p in pages], [1, 2, 3])

    def test_successful_reorder_has_continuous_sort_order(self) -> None:
        self.client.put(
            self.order_endpoint(),
            json={"page_ids": [self.c["id"], self.a["id"], self.b["id"]]},
        )
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        pages = ws["pages"]
        self.assertEqual([p["sort_order"] for p in pages], [1, 2, 3])


class SecondRoundStatusCodeContractTests(unittest.TestCase):
    """11.5 状态码与响应契约。"""

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
        self.project = self.manager.create_project("项目")
        self.chapter = self.manager.create_chapter(str(self.project["id"]), "章")
        self.large_scene = self.manager.create_large_scene(str(self.chapter["id"]), "大场景")
        self.small_scene = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景")
        self.material = self.manager.create_material(
            name="表情", material_type="expression", content="内容"
        )

    def test_create_scene_page_returns_201_with_page_wrapper(self) -> None:
        response = self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/pages",
            json={"name": "P1"},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("page", body)
        self.assertEqual(body["page"]["name"], "P1")

    def test_update_scene_page_returns_200_with_page_wrapper(self) -> None:
        created = self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/pages",
            json={"name": "P1"},
        ).json()["page"]
        response = self.client.patch(
            f"/api/small-scene-pages/{created['id']}",
            json={"name": "新名"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("page", response.json())

    def test_add_resource_returns_201_with_resource_wrapper(self) -> None:
        response = self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/resources",
            json={"material_id": str(self.material["id"])},
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn("resource", body)
        r = body["resource"]
        self.assertTrue(r["link_id"])
        self.assertEqual(r["material_id"], self.material["id"])
        self.assertEqual(r["name"], "表情")
        self.assertEqual(r["material_type"], "expression")
        self.assertIn("pages", r)

    def test_duplicate_resource_returns_409(self) -> None:
        self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/resources",
            json={"material_id": str(self.material["id"])},
        )
        response = self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/resources",
            json={"material_id": str(self.material["id"])},
        )
        self.assertEqual(response.status_code, 409)

    def test_set_mapping_returns_mapping_wrapper(self) -> None:
        # Associate material first
        self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/resources",
            json={"material_id": str(self.material["id"])},
        )
        page = self.manager.create_shot_page(str(self.small_scene["id"]), "P1")
        mp = self.manager.list_material_pages(str(self.material["id"]))[0]
        response = self.client.put(
            f"/api/small-scene-pages/{page['id']}/mappings/expression",
            json={"material_page_id": str(mp["id"])},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("mapping", body)
        self.assertIsNotNone(body["mapping"])

    def test_unset_mapping_via_put_null_returns_mapping_null(self) -> None:
        self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/resources",
            json={"material_id": str(self.material["id"])},
        )
        page = self.manager.create_shot_page(str(self.small_scene["id"]), "P1")
        mp = self.manager.list_material_pages(str(self.material["id"]))[0]
        # Set mapping
        self.client.put(
            f"/api/small-scene-pages/{page['id']}/mappings/expression",
            json={"material_page_id": str(mp["id"])},
        )
        # Unset via PUT null
        response = self.client.put(
            f"/api/small-scene-pages/{page['id']}/mappings/expression",
            json={"material_page_id": None},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["mapping"])


class SecondRoundLinkIdTests(unittest.TestCase):
    """11.6 link_id 稳定性。"""

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
        self.project = self.manager.create_project("项目")
        self.chapter = self.manager.create_chapter(str(self.project["id"]), "章")
        self.large_scene = self.manager.create_large_scene(str(self.chapter["id"]), "大场景")
        self.small_scene = self.manager.create_small_scene(str(self.large_scene["id"]), "小场景")
        self.material = self.manager.create_material(
            name="表情", material_type="expression", content="内容"
        )

    def test_new_resource_link_has_non_empty_link_id(self) -> None:
        result = self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        self.assertTrue(result["link_id"])

    def test_workspace_resource_has_non_empty_link_id(self) -> None:
        self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        for r in ws["resources"]:
            self.assertTrue(r["link_id"])

    def test_bulk_set_preserves_link_id_for_retained(self) -> None:
        # Add via new interface
        link = self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        original_link_id = link["link_id"]
        # Bulk set with same material (should preserve link_id)
        self.manager.set_small_scene_materials(
            str(self.small_scene["id"]), [str(self.material["id"])]
        )
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        self.assertEqual(len(ws["resources"]), 1)
        self.assertEqual(ws["resources"][0]["link_id"], original_link_id)

    def test_bulk_set_generates_new_link_id_for_new_material(self) -> None:
        material2 = self.manager.create_material(
            name="构图", material_type="composition", content="内容"
        )
        self.manager.set_small_scene_materials(
            str(self.small_scene["id"]), [str(self.material["id"]), str(material2["id"])]
        )
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/workspace"
        ).json()
        self.assertEqual(len(ws["resources"]), 2)
        for r in ws["resources"]:
            self.assertTrue(r["link_id"])

    def test_historical_empty_id_fixed_on_init(self) -> None:
        # Manually insert a row with empty id
        with self.manager.connection("test") as conn:
            conn.execute(
                "INSERT INTO small_scene_materials (id, small_scene_id, material_id, sort_order, created_at) "
                "VALUES ('', ?, ?, 1, '2026-07-29T00:00:00+00:00')",
                (str(self.small_scene["id"]), str(self.material["id"])),
            )
        # Re-init
        self.manager.initialize("test")
        # Verify id is now non-empty
        with self.manager.connection("test") as conn:
            row = conn.execute(
                "SELECT id FROM small_scene_materials WHERE small_scene_id = ? AND material_id = ?",
                (str(self.small_scene["id"]), str(self.material["id"])),
            ).fetchone()
        self.assertTrue(row["id"])

    def test_repeated_init_does_not_change_valid_id(self) -> None:
        link = self.manager.add_small_scene_resource(
            str(self.small_scene["id"]), str(self.material["id"])
        )
        original_id = link["link_id"]
        # Re-init
        self.manager.initialize("test")
        with self.manager.connection("test") as conn:
            row = conn.execute(
                "SELECT id FROM small_scene_materials WHERE small_scene_id = ? AND material_id = ?",
                (str(self.small_scene["id"]), str(self.material["id"])),
            ).fetchone()
        self.assertEqual(row["id"], original_id)


if __name__ == "__main__":
    unittest.main()
