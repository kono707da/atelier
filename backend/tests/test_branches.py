from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class BranchApiTests(unittest.TestCase):
    """分支接口测试：所有数据均写入临时测试库。"""

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
        self.project = self.manager.create_project("分支测试项目")
        self.chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )
        self.large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "大场景A"
        )
        self.small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "小场景A"
        )

    def test_list_branches_under_large_scene_returns_empty(self) -> None:
        response = self.client.get(
            f"/api/large-scenes/{self.large_scene['id']}/branches"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_list_branches_under_small_scene_returns_empty(self) -> None:
        response = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/branches"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_list_branches_is_sorted_by_sort_order(self) -> None:
        for name in ("分支C", "分支A", "分支B"):
            self.client.post(
                f"/api/large-scenes/{self.large_scene['id']}/branches",
                json={"name": name},
            )
        payload = self.client.get(
            f"/api/large-scenes/{self.large_scene['id']}/branches"
        ).json()
        self.assertEqual(
            [item["name"] for item in payload["items"]],
            ["分支C", "分支A", "分支B"],
        )
        self.assertEqual(
            [item["sort_order"] for item in payload["items"]], [1, 2, 3]
        )

    def test_list_branches_includes_shot_page_count(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "有分镜的分支"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜1",
            branch_id=str(branch["id"]),
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜2",
            branch_id=str(branch["id"]),
        )
        items = self.client.get(
            f"/api/large-scenes/{self.large_scene['id']}/branches"
        ).json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["shot_page_count"], 2)

    def test_create_branch_under_large_scene_returns_full_shape(self) -> None:
        response = self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "主线分支"},
        )
        self.assertEqual(response.status_code, 201)
        branch = response.json()["branch"]
        self.assertEqual(branch["parent_type"], "large_scene")
        self.assertEqual(branch["parent_id"], self.large_scene["id"])
        self.assertEqual(branch["name"], "主线分支")
        self.assertEqual(branch["description"], "")
        self.assertEqual(branch["is_enabled"], 1)
        self.assertEqual(branch["sort_order"], 1)
        self.assertEqual(branch["shot_page_count"], 0)
        for key in ("id", "created_at", "updated_at"):
            self.assertIn(key, branch)

    def test_create_branch_under_small_scene_returns_full_shape(self) -> None:
        response = self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/branches",
            json={"name": "支线分支", "description": "描述文本", "is_enabled": False},
        )
        self.assertEqual(response.status_code, 201)
        branch = response.json()["branch"]
        self.assertEqual(branch["parent_type"], "small_scene")
        self.assertEqual(branch["parent_id"], self.small_scene["id"])
        self.assertEqual(branch["name"], "支线分支")
        self.assertEqual(branch["description"], "描述文本")
        self.assertEqual(branch["is_enabled"], 0)
        self.assertEqual(branch["sort_order"], 1)

    def test_create_branch_with_invalid_parent_type_returns_422(self) -> None:
        response = self.client.post(
            f"/api/chapters/{self.chapter['id']}/branches",
            json={"name": "非法父级"},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_branch_under_missing_parent_returns_404(self) -> None:
        response = self.client.post(
            "/api/large-scenes/missing-id/branches",
            json={"name": "孤立分支"},
        )
        self.assertEqual(response.status_code, 404)

    def test_create_branch_name_is_cleaned(self) -> None:
        response = self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "  主线   分支  "},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["branch"]["name"], "主线 分支")

    def test_create_branch_blank_name_is_rejected(self) -> None:
        response = self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "   "},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_branch_too_long_name_is_rejected(self) -> None:
        response = self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "分" * 81},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_branch_duplicate_name_in_same_parent_is_rejected(self) -> None:
        self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "同名分支"},
        )
        response = self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "同名分支"},
        )
        self.assertEqual(response.status_code, 409)

    def test_same_branch_name_allowed_under_different_parents(self) -> None:
        other_large = self.manager.create_large_scene(
            str(self.chapter["id"]), "大场景B"
        )
        self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "通用分支"},
        )
        response = self.client.post(
            f"/api/large-scenes/{other_large['id']}/branches",
            json={"name": "通用分支"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            len(
                self.manager.list_branches(
                    "large_scene", str(other_large["id"])
                )
            ),
            1,
        )

    def test_same_branch_name_allowed_under_different_parent_types(self) -> None:
        self.client.post(
            f"/api/large-scenes/{self.large_scene['id']}/branches",
            json={"name": "跨类型同名"},
        )
        response = self.client.post(
            f"/api/small-scenes/{self.small_scene['id']}/branches",
            json={"name": "跨类型同名"},
        )
        self.assertEqual(response.status_code, 201)

    def test_get_branch_returns_shot_page_count(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "查询分支"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜X",
            branch_id=str(branch["id"]),
        )
        response = self.client.get(f"/api/branches/{branch['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["branch"]["shot_page_count"], 1)

    def test_get_missing_branch_returns_404(self) -> None:
        response = self.client.get("/api/branches/missing-id")
        self.assertEqual(response.status_code, 404)

    def test_update_branch_name(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "旧名称"
        )
        response = self.client.patch(
            f"/api/branches/{branch['id']}", json={"name": "  新   名称  "}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["branch"]["name"], "新 名称")
        self.assertEqual(
            self.manager.get_branch(str(branch["id"]))["name"], "新 名称"
        )

    def test_update_branch_description(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支A"
        )
        response = self.client.patch(
            f"/api/branches/{branch['id']}",
            json={"description": "更新后的描述"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["branch"]["description"], "更新后的描述"
        )

    def test_update_branch_is_enabled_toggle(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "开关分支"
        )
        self.assertEqual(branch["is_enabled"], 1)
        response = self.client.patch(
            f"/api/branches/{branch['id']}", json={"is_enabled": False}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["branch"]["is_enabled"], 0)
        response = self.client.patch(
            f"/api/branches/{branch['id']}", json={"is_enabled": True}
        )
        self.assertEqual(response.json()["branch"]["is_enabled"], 1)

    def test_update_branch_rejects_duplicate_name(self) -> None:
        first = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支A"
        )
        self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支B"
        )
        response = self.client.patch(
            f"/api/branches/{first['id']}", json={"name": "分支B"}
        )
        self.assertEqual(response.status_code, 409)

    def test_update_branch_rejects_blank_name(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支A"
        )
        response = self.client.patch(
            f"/api/branches/{branch['id']}", json={"name": "   "}
        )
        self.assertEqual(response.status_code, 422)

    def test_update_missing_branch_returns_404(self) -> None:
        response = self.client.patch(
            "/api/branches/missing-id", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 404)

    def test_update_branch_at_least_one_field_required(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支A"
        )
        response = self.client.patch(
            f"/api/branches/{branch['id']}", json={}
        )
        self.assertEqual(response.status_code, 422)

    def test_delete_branch_returns_deleted_info(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "待删分支"
        )
        response = self.client.delete(f"/api/branches/{branch['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"]["id"], branch["id"])
        self.assertEqual(response.json()["deleted"]["name"], "待删分支")

    def test_delete_missing_branch_returns_404(self) -> None:
        response = self.client.delete("/api/branches/missing-id")
        self.assertEqual(response.status_code, 404)

    def test_delete_branch_cascades_shot_pages(self) -> None:
        branch = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "级联分支"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜1",
            branch_id=str(branch["id"]),
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜2",
            branch_id=str(branch["id"]),
        )
        self.client.delete(f"/api/branches/{branch['id']}")
        remaining = self.manager.list_shot_pages(
            str(self.small_scene["id"]), branch_id=str(branch["id"])
        )
        self.assertEqual(len(remaining), 0)

    def test_delete_branch_reflows_sort_order(self) -> None:
        a = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支A"
        )
        b = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支B"
        )
        self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支C"
        )
        self.client.delete(f"/api/branches/{b['id']}")
        items = self.manager.list_branches(
            "large_scene", str(self.large_scene["id"])
        )
        self.assertEqual([item["name"] for item in items], ["分支A", "分支C"])
        self.assertEqual(
            [item["sort_order"] for item in items], [1, 2]
        )

    def test_shot_page_count_reflects_created_pages(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "计数分支"
        )
        self.assertEqual(branch["shot_page_count"], 0)
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜1",
            branch_id=str(branch["id"]),
        )
        refreshed = self.manager.get_branch(str(branch["id"]))
        self.assertEqual(refreshed["shot_page_count"], 1)
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜2",
            branch_id=str(branch["id"]),
        )
        refreshed = self.manager.get_branch(str(branch["id"]))
        self.assertEqual(refreshed["shot_page_count"], 2)

    def test_list_branches_under_large_scene_with_shot_page_count(self) -> None:
        branch_a = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支A"
        )
        branch_b = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支B"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜1",
            branch_id=str(branch_a["id"]),
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜2",
            branch_id=str(branch_a["id"]),
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜3",
            branch_id=str(branch_b["id"]),
        )
        items = self.client.get(
            f"/api/large-scenes/{self.large_scene['id']}/branches"
        ).json()["items"]
        counts = {item["name"]: item["shot_page_count"] for item in items}
        self.assertEqual(counts["分支A"], 2)
        self.assertEqual(counts["分支B"], 1)

    def test_list_branches_under_small_scene_with_shot_page_count(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "小场景分支"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "分镜1",
            branch_id=str(branch["id"]),
        )
        items = self.client.get(
            f"/api/small-scenes/{self.small_scene['id']}/branches"
        ).json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["shot_page_count"], 1)

    def test_branch_sort_order_independent_per_parent(self) -> None:
        other_large = self.manager.create_large_scene(
            str(self.chapter["id"]), "大场景B"
        )
        a = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支A"
        )
        b = self.manager.create_branch(
            "large_scene", str(self.large_scene["id"]), "分支B"
        )
        c = self.manager.create_branch(
            "large_scene", str(other_large["id"]), "分支C"
        )
        self.assertEqual([a["sort_order"], b["sort_order"]], [1, 2])
        self.assertEqual(c["sort_order"], 1)


if __name__ == "__main__":
    unittest.main()
