"""Third-round rectification tests for scene page mapping.

Validates:
- Branch pages reject both set and cancel (422).
- Non-existent pages reject both set and cancel (404).
- Normal direct pages support idempotent cancel (200, mapping: null).
- Normal flow regression: associated material can map, unassociated cannot,
  same-type atomic replace, one material page to multiple scene pages.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app


class ThirdRoundMappingTests(unittest.TestCase):
    """Tests for third-round mapping target page validation."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        # Build a project tree: project -> chapter -> large_scene -> small_scene
        proj = self.client.post("/api/projects", json={"name": "P"}).json()
        self.project_id = proj["project"]["id"]
        ch = self.client.post(
            f"/api/projects/{self.project_id}/chapters",
            json={"name": "Ch"},
        ).json()
        self.chapter_id = ch["chapter"]["id"]
        ls = self.client.post(
            f"/api/chapters/{self.chapter_id}/large-scenes",
            json={"name": "LS", "scene_type": "content"},
        ).json()
        self.large_scene_id = ls["large_scene"]["id"]
        ss = self.client.post(
            f"/api/large-scenes/{self.large_scene_id}/small-scenes",
            json={"name": "SS", "scene_type": "content", "description": ""},
        ).json()
        self.small_scene_id = ss["small_scene"]["id"]
        # Create a branch under the small scene
        br = self.client.post(
            f"/api/small-scenes/{self.small_scene_id}/branches",
            json={"name": "Br", "description": ""},
        ).json()
        self.branch_id = br["branch"]["id"]
        # Create a direct scene page and a branch page
        p1 = self.client.post(
            f"/api/small-scenes/{self.small_scene_id}/pages",
            json={"name": "P1", "description": ""},
        ).json()
        self.direct_page_id = p1["page"]["id"]
        p2 = self.client.post(
            f"/api/small-scenes/{self.small_scene_id}/pages",
            json={"name": "P2", "description": ""},
        ).json()
        self.direct_page_id_2 = p2["page"]["id"]
        bp = self.client.post(
            f"/api/small-scenes/{self.small_scene_id}/shot-pages",
            json={"title": "BP", "description": "", "branch_id": self.branch_id},
        ).json()
        self.branch_page_id = bp["shot_page"]["id"]
        # Create an expression material with a material page
        mat = self.client.post(
            "/api/materials",
            json={
                "name": "ExprMat",
                "material_type": "expression",
                "content": "c",
                "description": "",
            },
        ).json()
        self.material_id = mat["material"]["id"]
        pages = self.client.get(f"/api/materials/{self.material_id}/pages").json()
        self.material_page_id = pages["pages"][0]["id"]
        # Associate the material to the small scene
        link = self.client.post(
            f"/api/small-scenes/{self.small_scene_id}/resources",
            json={"material_id": self.material_id},
        ).json()
        self.link_id = link["resource"]["link_id"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # 9.1 Branch page set mapping -> 422
    def test_branch_page_set_mapping_returns_422(self) -> None:
        resp = self.client.put(
            f"/api/small-scene-pages/{self.branch_page_id}/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("分支页面", resp.json()["detail"])
        # Verify no mapping was created
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene_id}/workspace"
        ).json()
        for m in ws["mappings"]:
            self.assertNotEqual(m["scene_page_id"], self.branch_page_id)

    # 9.2 Branch page cancel mapping -> 422
    def test_branch_page_cancel_mapping_returns_422(self) -> None:
        resp = self.client.put(
            f"/api/small-scene-pages/{self.branch_page_id}/mappings/expression",
            json={"material_page_id": None},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("分支页面", resp.json()["detail"])

    # 9.3 Non-existent page set mapping -> 404
    def test_missing_page_set_mapping_returns_404(self) -> None:
        resp = self.client.put(
            "/api/small-scene-pages/nonexistent-page-id/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("场景页不存在", resp.json()["detail"])

    # 9.4 Non-existent page cancel mapping -> 404
    def test_missing_page_cancel_mapping_returns_404(self) -> None:
        resp = self.client.put(
            "/api/small-scene-pages/nonexistent-page-id/mappings/expression",
            json={"material_page_id": None},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertIn("场景页不存在", resp.json()["detail"])
        # Response must not be a success with mapping: null
        body = resp.json()
        self.assertNotIn("mapping", body)

    # 9.5 Normal page idempotent cancel -> 200, mapping: null
    def test_normal_page_idempotent_cancel(self) -> None:
        # Cancel on a page with no existing mapping
        resp = self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id_2}/mappings/expression",
            json={"material_page_id": None},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["mapping"])

    # 9.6 Normal flow regression
    def test_associated_material_can_map(self) -> None:
        resp = self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id}/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["mapping"]["material_page_id"], self.material_page_id)

    def test_unassociated_material_cannot_map(self) -> None:
        # Create a second material not associated to the small scene
        mat2 = self.client.post(
            "/api/materials",
            json={
                "name": "ExprMat2",
                "material_type": "expression",
                "content": "c",
                "description": "",
            },
        ).json()
        mat2_id = mat2["material"]["id"]
        pages2 = self.client.get(f"/api/materials/{mat2_id}/pages").json()
        mp2_id = pages2["pages"][0]["id"]
        resp = self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id}/mappings/expression",
            json={"material_page_id": mp2_id},
        )
        self.assertEqual(resp.status_code, 422)

    def test_same_type_atomic_replace(self) -> None:
        # Create a second material page for the same material
        mp2 = self.client.post(
            f"/api/materials/{self.material_id}/pages",
            json={"name": "Page2", "description": "", "content": ""},
        ).json()
        mp2_id = mp2["id"]
        # Set initial mapping
        self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id}/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        # Replace with second page
        resp = self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id}/mappings/expression",
            json={"material_page_id": mp2_id},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["mapping"]["material_page_id"], mp2_id)
        # Verify only one mapping exists for this page+type
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene_id}/workspace"
        ).json()
        count = sum(
            1
            for m in ws["mappings"]
            if m["scene_page_id"] == self.direct_page_id
            and m["material_type"] == "expression"
        )
        self.assertEqual(count, 1)

    def test_one_material_page_to_multiple_scene_pages(self) -> None:
        # Map the same material page to two different direct scene pages
        for page_id in (self.direct_page_id, self.direct_page_id_2):
            resp = self.client.put(
                f"/api/small-scene-pages/{page_id}/mappings/expression",
                json={"material_page_id": self.material_page_id},
            )
            self.assertEqual(resp.status_code, 200)
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene_id}/workspace"
        ).json()
        mapped_pages = {
            m["scene_page_id"]
            for m in ws["mappings"]
            if m["material_page_id"] == self.material_page_id
        }
        self.assertEqual(
            mapped_pages, {self.direct_page_id, self.direct_page_id_2}
        )

    def test_normal_page_cancel_after_set(self) -> None:
        # Set then cancel
        self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id}/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        resp = self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id}/mappings/expression",
            json={"material_page_id": None},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["mapping"])
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene_id}/workspace"
        ).json()
        for m in ws["mappings"]:
            self.assertFalse(
                m["scene_page_id"] == self.direct_page_id
                and m["material_type"] == "expression"
            )

    def test_failed_requests_do_not_modify_existing_mappings(self) -> None:
        # Set a mapping on direct_page_id
        self.client.put(
            f"/api/small-scene-pages/{self.direct_page_id}/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        # Attempt 4 failing requests
        self.client.put(
            f"/api/small-scene-pages/{self.branch_page_id}/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        self.client.put(
            f"/api/small-scene-pages/{self.branch_page_id}/mappings/expression",
            json={"material_page_id": None},
        )
        self.client.put(
            "/api/small-scene-pages/nonexistent/mappings/expression",
            json={"material_page_id": self.material_page_id},
        )
        self.client.put(
            "/api/small-scene-pages/nonexistent/mappings/expression",
            json={"material_page_id": None},
        )
        # Verify original mapping is intact
        ws = self.client.get(
            f"/api/small-scenes/{self.small_scene_id}/workspace"
        ).json()
        found = False
        for m in ws["mappings"]:
            if (
                m["scene_page_id"] == self.direct_page_id
                and m["material_type"] == "expression"
                and m["material_page_id"] == self.material_page_id
            ):
                found = True
                break
        self.assertTrue(found, "Original mapping should still exist after failed requests")


if __name__ == "__main__":
    unittest.main()
