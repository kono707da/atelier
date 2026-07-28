from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class ShotPageApiTests(unittest.TestCase):
    """分镜页接口测试：所有数据均写入临时测试库。"""

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
        self.project = self.manager.create_project("分镜页测试项目")
        self.chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )
        self.large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "大场景A"
        )
        self.small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "小场景A"
        )

    def list_endpoint(self, small_scene_id: str | None = None) -> str:
        return (
            f"/api/small-scenes/{small_scene_id or self.small_scene['id']}/shot-pages"
        )

    def test_empty_small_scene_returns_empty_list(self) -> None:
        response = self.client.get(self.list_endpoint())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_list_with_branch_id_filter(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]), "主线页", branch_id=None
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]), "分支页", branch_id=str(branch["id"])
        )
        response = self.client.get(
            self.list_endpoint(), params={"branch_id": str(branch["id"])}
        )
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "分支页")

    def test_list_without_branch_id_returns_mainline_only(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]), "主线页", branch_id=None
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]), "分支页", branch_id=str(branch["id"])
        )
        response = self.client.get(self.list_endpoint())
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "主线页")

    def test_list_is_sorted_by_sort_order(self) -> None:
        for title in ("第一页", "第二页", "第三页"):
            self.client.post(self.list_endpoint(), json={"title": title})
        payload = self.client.get(self.list_endpoint()).json()
        self.assertEqual(
            [item["title"] for item in payload["items"]],
            ["第一页", "第二页", "第三页"],
        )
        self.assertEqual(
            [item["sort_order"] for item in payload["items"]], [1, 2, 3]
        )

    def test_list_items_include_material_ids(self) -> None:
        self.manager.create_shot_page(
            str(self.small_scene["id"]), "有素材页"
        )
        response = self.client.get(self.list_endpoint())
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertIn("material_ids", items[0])
        self.assertIsInstance(items[0]["material_ids"], list)

    def test_create_mainline_shot_page_returns_full_shape(self) -> None:
        response = self.client.post(
            self.list_endpoint(), json={"title": "分镜页1"}
        )
        self.assertEqual(response.status_code, 201)
        sp = response.json()["shot_page"]
        self.assertEqual(sp["small_scene_id"], self.small_scene["id"])
        self.assertIsNone(sp["branch_id"])
        self.assertEqual(sp["title"], "分镜页1")
        self.assertEqual(sp["description"], "")
        self.assertEqual(sp["prompt_text"], "")
        self.assertEqual(sp["negative_prompt"], "")
        self.assertEqual(sp["sort_order"], 1)
        for key in ("id", "created_at", "updated_at"):
            self.assertIn(key, sp)

    def test_create_branch_shot_page(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        response = self.client.post(
            self.list_endpoint(),
            json={"title": "分支页1", "branch_id": str(branch["id"])},
        )
        self.assertEqual(response.status_code, 201)
        sp = response.json()["shot_page"]
        self.assertEqual(sp["branch_id"], branch["id"])
        self.assertEqual(sp["title"], "分支页1")

    def test_create_shot_page_with_all_fields(self) -> None:
        response = self.client.post(
            self.list_endpoint(),
            json={
                "title": "完整页",
                "description": "描述文本",
                "prompt_text": "正向提示词",
                "negative_prompt": "负向提示词",
            },
        )
        self.assertEqual(response.status_code, 201)
        sp = response.json()["shot_page"]
        self.assertEqual(sp["description"], "描述文本")
        self.assertEqual(sp["prompt_text"], "正向提示词")
        self.assertEqual(sp["negative_prompt"], "负向提示词")

    def test_create_blank_title_is_rejected(self) -> None:
        response = self.client.post(self.list_endpoint(), json={"title": "   "})
        self.assertEqual(response.status_code, 422)

    def test_create_too_long_title_is_rejected(self) -> None:
        response = self.client.post(
            self.list_endpoint(), json={"title": "页" * 121}
        )
        self.assertEqual(response.status_code, 422)

    def test_create_prompt_text_at_max_length(self) -> None:
        response = self.client.post(
            self.list_endpoint(),
            json={"title": "最大提示词", "prompt_text": "a" * 50000},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["shot_page"]["prompt_text"]), 50000)

    def test_create_prompt_text_exceeds_max_length(self) -> None:
        response = self.client.post(
            self.list_endpoint(),
            json={"title": "超长提示词", "prompt_text": "a" * 50001},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_negative_prompt_at_max_length(self) -> None:
        response = self.client.post(
            self.list_endpoint(),
            json={"title": "最大负向", "negative_prompt": "b" * 20000},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["shot_page"]["negative_prompt"]), 20000)

    def test_create_negative_prompt_exceeds_max_length(self) -> None:
        response = self.client.post(
            self.list_endpoint(),
            json={"title": "超长负向", "negative_prompt": "b" * 20001},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_duplicate_title_in_same_scope_is_rejected(self) -> None:
        self.client.post(self.list_endpoint(), json={"title": "同名页"})
        response = self.client.post(self.list_endpoint(), json={"title": "同名页"})
        self.assertEqual(response.status_code, 409)

    def test_create_same_title_in_different_scopes_is_allowed(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        self.client.post(self.list_endpoint(), json={"title": "同名页"})
        response = self.client.post(
            self.list_endpoint(),
            json={"title": "同名页", "branch_id": str(branch["id"])},
        )
        self.assertEqual(response.status_code, 201)

    def test_create_shot_page_missing_small_scene_returns_404(self) -> None:
        response = self.client.post(
            "/api/small-scenes/missing-id/shot-pages",
            json={"title": "孤立页"},
        )
        self.assertEqual(response.status_code, 404)

    def test_create_shot_page_missing_branch_returns_422(self) -> None:
        response = self.client.post(
            self.list_endpoint(),
            json={"title": "幽灵分支页", "branch_id": "missing-branch-id"},
        )
        self.assertEqual(response.status_code, 422)

    def test_get_shot_page_with_materials(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "详情页"
        )
        response = self.client.get(f"/api/shot-pages/{sp['id']}")
        self.assertEqual(response.status_code, 200)
        body = response.json()["shot_page"]
        self.assertEqual(body["title"], "详情页")
        self.assertIn("materials", body)
        self.assertIsInstance(body["materials"], list)

    def test_get_missing_shot_page_returns_404(self) -> None:
        response = self.client.get("/api/shot-pages/missing-id")
        self.assertEqual(response.status_code, 404)

    def test_update_title(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "旧标题"
        )
        response = self.client.patch(
            f"/api/shot-pages/{sp['id']}", json={"title": "新标题"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shot_page"]["title"], "新标题")

    def test_update_description(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "页A"
        )
        response = self.client.patch(
            f"/api/shot-pages/{sp['id']}", json={"description": "新描述"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shot_page"]["description"], "新描述")

    def test_update_prompt_text(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "页A"
        )
        response = self.client.patch(
            f"/api/shot-pages/{sp['id']}", json={"prompt_text": "新正向"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shot_page"]["prompt_text"], "新正向")

    def test_update_negative_prompt(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "页A"
        )
        response = self.client.patch(
            f"/api/shot-pages/{sp['id']}", json={"negative_prompt": "新负向"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shot_page"]["negative_prompt"], "新负向")

    def test_update_clear_optional_fields(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]),
            "页A",
            description="有描述",
            prompt_text="有正向",
            negative_prompt="有负向",
        )
        response = self.client.patch(
            f"/api/shot-pages/{sp['id']}",
            json={"description": "", "prompt_text": "", "negative_prompt": ""},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["shot_page"]
        self.assertEqual(body["description"], "")
        self.assertEqual(body["prompt_text"], "")
        self.assertEqual(body["negative_prompt"], "")

    def test_update_missing_shot_page_returns_404(self) -> None:
        response = self.client.patch(
            "/api/shot-pages/missing-id", json={"title": "不存在"}
        )
        self.assertEqual(response.status_code, 404)

    def test_update_duplicate_title_returns_409(self) -> None:
        first = self.manager.create_shot_page(
            str(self.small_scene["id"]), "页A"
        )
        self.manager.create_shot_page(
            str(self.small_scene["id"]), "页B"
        )
        response = self.client.patch(
            f"/api/shot-pages/{first['id']}", json={"title": "页B"}
        )
        self.assertEqual(response.status_code, 409)

    def test_update_blank_title_is_rejected(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "页A"
        )
        response = self.client.patch(
            f"/api/shot-pages/{sp['id']}", json={"title": "   "}
        )
        self.assertEqual(response.status_code, 422)

    def test_update_at_least_one_field_required(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "页A"
        )
        response = self.client.patch(
            f"/api/shot-pages/{sp['id']}", json={}
        )
        self.assertEqual(response.status_code, 422)

    def test_move_forward_within_scope(self) -> None:
        a = self.manager.create_shot_page(str(self.small_scene["id"]), "A")
        b = self.manager.create_shot_page(str(self.small_scene["id"]), "B")
        c = self.manager.create_shot_page(str(self.small_scene["id"]), "C")
        response = self.client.post(
            f"/api/shot-pages/{a['id']}/move",
            json={"target_sort_order": 3},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [i["title"] for i in body["items"]], ["B", "C", "A"]
        )
        self.assertEqual(
            [i["sort_order"] for i in body["items"]], [1, 2, 3]
        )

    def test_move_backward_within_scope(self) -> None:
        a = self.manager.create_shot_page(str(self.small_scene["id"]), "A")
        b = self.manager.create_shot_page(str(self.small_scene["id"]), "B")
        c = self.manager.create_shot_page(str(self.small_scene["id"]), "C")
        response = self.client.post(
            f"/api/shot-pages/{c['id']}/move",
            json={"target_sort_order": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [i["title"] for i in response.json()["items"]],
            ["C", "A", "B"],
        )

    def test_move_target_sort_exceeds_length_appends_to_end(self) -> None:
        a = self.manager.create_shot_page(str(self.small_scene["id"]), "A")
        b = self.manager.create_shot_page(str(self.small_scene["id"]), "B")
        response = self.client.post(
            f"/api/shot-pages/{a['id']}/move",
            json={"target_sort_order": 999},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [i["title"] for i in response.json()["items"]], ["B", "A"]
        )

    def test_move_target_sort_below_one_clamped(self) -> None:
        a = self.manager.create_shot_page(str(self.small_scene["id"]), "A")
        b = self.manager.create_shot_page(str(self.small_scene["id"]), "B")
        result = self.manager.move_shot_page(str(a["id"]), 0)
        items = self.manager.list_shot_pages(str(self.small_scene["id"]))
        self.assertEqual(
            [i["title"] for i in items], ["A", "B"]
        )

    def test_move_missing_shot_page_returns_404(self) -> None:
        response = self.client.post(
            "/api/shot-pages/missing-id/move",
            json={"target_sort_order": 1},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_shot_page(self) -> None:
        sp = self.manager.create_shot_page(
            str(self.small_scene["id"]), "待删页"
        )
        response = self.client.delete(f"/api/shot-pages/{sp['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"]["id"], sp["id"])

    def test_delete_missing_shot_page_returns_404(self) -> None:
        response = self.client.delete("/api/shot-pages/missing-id")
        self.assertEqual(response.status_code, 404)

    def test_delete_renumbers_remaining_pages(self) -> None:
        a = self.manager.create_shot_page(str(self.small_scene["id"]), "A")
        b = self.manager.create_shot_page(str(self.small_scene["id"]), "B")
        c = self.manager.create_shot_page(str(self.small_scene["id"]), "C")
        self.client.delete(f"/api/shot-pages/{b['id']}")
        remaining = self.manager.list_shot_pages(str(self.small_scene["id"]))
        self.assertEqual([p["title"] for p in remaining], ["A", "C"])
        self.assertEqual([p["sort_order"] for p in remaining], [1, 2])

    def test_delete_branch_page_renumbers_within_branch(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        a = self.manager.create_shot_page(
            str(self.small_scene["id"]), "BA",
            branch_id=str(branch["id"]),
        )
        b = self.manager.create_shot_page(
            str(self.small_scene["id"]), "BB",
            branch_id=str(branch["id"]),
        )
        c = self.manager.create_shot_page(
            str(self.small_scene["id"]), "BC",
            branch_id=str(branch["id"]),
        )
        self.client.delete(f"/api/shot-pages/{b['id']}")
        remaining = self.manager.list_shot_pages(
            str(self.small_scene["id"]), branch_id=str(branch["id"])
        )
        self.assertEqual([p["title"] for p in remaining], ["BA", "BC"])
        self.assertEqual([p["sort_order"] for p in remaining], [1, 2])


if __name__ == "__main__":
    unittest.main()
