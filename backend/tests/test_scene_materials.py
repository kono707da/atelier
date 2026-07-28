from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class SceneMaterialApiTests(unittest.TestCase):
    """场景素材关联接口测试：小场景素材、分镜页素材、级联删除。"""

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
        self.project = self.manager.create_project("素材关联测试项目")
        self.chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )
        self.large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "大场景A"
        )
        self.small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "小场景A"
        )
        self.material_a = self.manager.create_material(name="素材A", material_type="composition", content="构图内容A")
        self.material_b = self.manager.create_material(name="素材B", material_type="expression", content="表情内容B")
        self.shot_page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页1"
        )

    def test_list_small_scene_materials_empty(self) -> None:
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/materials"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["materials"], [])

    def test_list_small_scene_materials_404_for_missing_scene(self) -> None:
        response = self.client.get("/api/small-scenes/missing-id/materials")
        self.assertEqual(response.status_code, 404)

    def test_set_small_scene_materials_full_replace(self) -> None:
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        response = self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_b["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["materials"]
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["material_id"], self.material_b["id"])

    def test_set_small_scene_materials_order_preserved(self) -> None:
        response = self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_b["id"], self.material_a["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["materials"]
        self.assertEqual(materials[0]["material_id"], self.material_b["id"])
        self.assertEqual(materials[1]["material_id"], self.material_a["id"])
        self.assertEqual(materials[0]["sort_order"], 1)
        self.assertEqual(materials[1]["sort_order"], 2)

    def test_set_small_scene_materials_dedup_ids(self) -> None:
        response = self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={
                "material_ids": [
                    self.material_a["id"],
                    self.material_a["id"],
                    self.material_b["id"],
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["materials"]
        self.assertEqual(len(materials), 2)
        self.assertEqual(materials[0]["material_id"], self.material_a["id"])
        self.assertEqual(materials[1]["material_id"], self.material_b["id"])

    def test_set_small_scene_materials_404_for_missing_material(self) -> None:
        response = self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"], "missing-material-id"]},
        )
        self.assertEqual(response.status_code, 404)

    def test_set_small_scene_materials_404_for_missing_scene(self) -> None:
        response = self.client.put(
            "/api/small-scenes/missing-id/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        self.assertEqual(response.status_code, 404)

    def test_small_scene_materials_appear_in_get_small_scene(self) -> None:
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}"
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["small_scene"]["materials"]
        self.assertEqual(len(materials), 2)
        self.assertEqual(materials[0]["material_id"], self.material_a["id"])
        self.assertEqual(materials[1]["material_id"], self.material_b["id"])

    def test_list_shot_page_materials_empty(self) -> None:
        response = self.client.get(
            f"/api/shot-pages/{self.shot_page['id']}/materials"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["materials"], [])

    def test_list_shot_page_materials_404_for_missing_page(self) -> None:
        response = self.client.get("/api/shot-pages/missing-id/materials")
        self.assertEqual(response.status_code, 404)

    def test_set_shot_page_materials_full_replace(self) -> None:
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        response = self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["materials"]
        self.assertEqual(len(materials), 1)
        self.assertEqual(materials[0]["material_id"], self.material_a["id"])

    def test_set_shot_page_materials_order_preserved(self) -> None:
        response = self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_b["id"], self.material_a["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["materials"]
        self.assertEqual(materials[0]["material_id"], self.material_b["id"])
        self.assertEqual(materials[1]["material_id"], self.material_a["id"])
        self.assertEqual(materials[0]["sort_order"], 1)
        self.assertEqual(materials[1]["sort_order"], 2)

    def test_set_shot_page_materials_dedup_ids(self) -> None:
        response = self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={
                "material_ids": [
                    self.material_b["id"],
                    self.material_b["id"],
                    self.material_a["id"],
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["materials"]
        self.assertEqual(len(materials), 2)
        self.assertEqual(materials[0]["material_id"], self.material_b["id"])
        self.assertEqual(materials[1]["material_id"], self.material_a["id"])

    def test_set_shot_page_materials_404_for_missing_material(self) -> None:
        response = self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": ["missing-material-id"]},
        )
        self.assertEqual(response.status_code, 404)

    def test_set_shot_page_materials_404_for_missing_page(self) -> None:
        response = self.client.put(
            "/api/shot-pages/missing-id/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        self.assertEqual(response.status_code, 404)

    def test_shot_page_materials_appear_in_get_shot_page(self) -> None:
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        response = self.client.get(
            f"/api/shot-pages/{self.shot_page['id']}"
        )
        self.assertEqual(response.status_code, 200)
        materials = response.json()["shot_page"]["materials"]
        self.assertEqual(len(materials), 2)
        self.assertEqual(materials[0]["material_id"], self.material_a["id"])
        self.assertEqual(materials[1]["material_id"], self.material_b["id"])

    def test_cascade_delete_small_scene_removes_materials(self) -> None:
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        with self.manager.connection() as conn:
            count_before = conn.execute(
                "SELECT COUNT(*) FROM small_scene_materials WHERE small_scene_id = ?",
                (str(self.small_scene["id"]),),
            ).fetchone()[0]
            self.assertEqual(count_before, 1)
        self.client.delete(f"/api/small-scenes/{self.small_scene['id']}")
        with self.manager.connection() as conn:
            count_after = conn.execute(
                "SELECT COUNT(*) FROM small_scene_materials WHERE small_scene_id = ?",
                (str(self.small_scene["id"]),),
            ).fetchone()[0]
            self.assertEqual(count_after, 0)

    def test_cascade_delete_shot_page_removes_materials(self) -> None:
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        with self.manager.connection() as conn:
            count_before = conn.execute(
                "SELECT COUNT(*) FROM shot_page_materials WHERE shot_page_id = ?",
                (str(self.shot_page["id"]),),
            ).fetchone()[0]
            self.assertEqual(count_before, 1)
        self.client.delete(f"/api/shot-pages/{self.shot_page['id']}")
        with self.manager.connection() as conn:
            count_after = conn.execute(
                "SELECT COUNT(*) FROM shot_page_materials WHERE shot_page_id = ?",
                (str(self.shot_page["id"]),),
            ).fetchone()[0]
            self.assertEqual(count_after, 0)

    def test_cascade_delete_material_removes_all_references(self) -> None:
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        self.client.delete(f"/api/materials/{self.material_a['id']}")
        ss_materials = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/materials"
        ).json()["materials"]
        self.assertEqual(len(ss_materials), 1)
        self.assertEqual(ss_materials[0]["material_id"], self.material_b["id"])
        sp_materials = self.client.get(
            f"/api/shot-pages/{self.shot_page['id']}/materials"
        ).json()["materials"]
        self.assertEqual(len(sp_materials), 0)

    def test_cascade_delete_branch_removes_shot_page_materials(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        branch_page = self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分支分镜页",
            branch_id=str(branch["id"]),
        )
        self.client.put(
            f"/api/shot-pages/{branch_page['id']}/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        with self.manager.connection() as conn:
            count_before = conn.execute(
                "SELECT COUNT(*) FROM shot_page_materials WHERE shot_page_id = ?",
                (str(branch_page["id"]),),
            ).fetchone()[0]
            self.assertEqual(count_before, 1)
        self.client.delete(f"/api/branches/{branch['id']}")
        with self.manager.connection() as conn:
            count_after = conn.execute(
                "SELECT COUNT(*) FROM shot_page_materials WHERE shot_page_id = ?",
                (str(branch_page["id"]),),
            ).fetchone()[0]
            self.assertEqual(count_after, 0)

    def test_cascade_delete_large_scene_removes_all_material_associations(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支B"
        )
        branch_page = self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分支分镜页B",
            branch_id=str(branch["id"]),
        )
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"]]},
        )
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_b["id"]]},
        )
        self.client.put(
            f"/api/shot-pages/{branch_page['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        self.client.delete(f"/api/large-scenes/{self.large_scene['id']}")
        with self.manager.connection() as conn:
            ss_count = conn.execute("SELECT COUNT(*) FROM small_scene_materials").fetchone()[0]
            sp_count = conn.execute("SELECT COUNT(*) FROM shot_page_materials").fetchone()[0]
            self.assertEqual(ss_count, 0)
            self.assertEqual(sp_count, 0)

    def test_small_scene_materials_sort_order_after_replace(self) -> None:
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_b["id"], self.material_a["id"]]},
        )
        materials = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/materials"
        ).json()["materials"]
        self.assertEqual(materials[0]["material_id"], self.material_b["id"])
        self.assertEqual(materials[0]["sort_order"], 1)
        self.assertEqual(materials[1]["material_id"], self.material_a["id"])
        self.assertEqual(materials[1]["sort_order"], 2)

    def test_shot_page_materials_sort_order_after_replace(self) -> None:
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_b["id"], self.material_a["id"]]},
        )
        materials = self.client.get(
            f"/api/shot-pages/{self.shot_page['id']}/materials"
        ).json()["materials"]
        self.assertEqual(materials[0]["material_id"], self.material_b["id"])
        self.assertEqual(materials[0]["sort_order"], 1)
        self.assertEqual(materials[1]["material_id"], self.material_a["id"])
        self.assertEqual(materials[1]["sort_order"], 2)

    def test_set_small_scene_materials_empty_clears_all(self) -> None:
        self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        response = self.client.put(
            f"/api/small-scenes/{self.small_scene['id']}/materials",
            json={"material_ids": []},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["materials"], [])

    def test_set_shot_page_materials_empty_clears_all(self) -> None:
        self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": [self.material_a["id"], self.material_b["id"]]},
        )
        response = self.client.put(
            f"/api/shot-pages/{self.shot_page['id']}/materials",
            json={"material_ids": []},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["materials"], [])


if __name__ == "__main__":
    unittest.main()
