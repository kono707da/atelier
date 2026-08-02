"""阶段 1.6「阶段集成验收」端到端集成测试。

覆盖验收清单：
1. 新建完整项目（多章节、多场景、多分支结构）
2. 创建多页素材并完成映射
3. 创建人物、变体、规格和矩阵值
4. 刷新、重启应用后全部恢复
5. 验证删除、恢复、撤销和版本快照
6. 验证任何列表都不依赖展示数据
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app


class Stage1IntegrationTests(unittest.TestCase):
    """阶段 1.6 集成验收：完整端到端流程测试。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.data_root = Path(self._tmp.name)
        self.app = create_app(
            data_root=self.data_root,
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager

    # ── 辅助方法 ──────────────────────────────────────────────

    def _create_project(self, name: str = "集成验收项目", description: str = "") -> dict:
        resp = self.client.post(
            "/api/projects", json={"name": name, "description": description}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["project"]

    def _create_chapter(self, project_id: str, name: str) -> dict:
        resp = self.client.post(
            f"/api/projects/{project_id}/chapters", json={"name": name}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["chapter"]

    def _create_large_scene(
        self, chapter_id: str, name: str, scene_type: str = "content"
    ) -> dict:
        resp = self.client.post(
            f"/api/chapters/{chapter_id}/large-scenes",
            json={"name": name, "scene_type": scene_type},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["large_scene"]

    def _create_small_scene(
        self, large_scene_id: str, name: str, scene_type: str = "content"
    ) -> dict:
        resp = self.client.post(
            f"/api/large-scenes/{large_scene_id}/small-scenes",
            json={"name": name, "scene_type": scene_type},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["small_scene"]

    def _create_shot_page(
        self,
        small_scene_id: str,
        title: str,
        branch_id: str | None = None,
        prompt_text: str = "",
    ) -> dict:
        payload: dict = {"title": title, "prompt_text": prompt_text}
        if branch_id:
            payload["branch_id"] = branch_id
        resp = self.client.post(
            f"/api/small-scenes/{small_scene_id}/shot-pages", json=payload
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["shot_page"]

    def _create_branch(
        self,
        parent_type: str,
        parent_id: str,
        name: str,
        condition_type: str = "",
        condition_value: str = "",
        return_point: str | None = None,
    ) -> dict:
        payload: dict = {"name": name, "condition_type": condition_type,
                         "condition_value": condition_value}
        if return_point:
            payload["return_point"] = return_point
        resp = self.client.post(
            f"/api/{parent_type}/{parent_id}/branches", json=payload
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["branch"]

    def _create_material(
        self, name: str, material_type: str = "scene", content: str = "素材正文"
    ) -> dict:
        resp = self.client.post(
            "/api/materials",
            json={"name": name, "material_type": material_type, "content": content},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["material"]

    def _create_material_page(self, material_id: str, name: str) -> dict:
        resp = self.client.post(
            f"/api/materials/{material_id}/pages", json={"name": name}
        )
        self.assertIn(resp.status_code, (200, 201), resp.text)
        return resp.json()

    def _create_character(self, name: str, project_id: str | None = None) -> dict:
        url = "/api/characters"
        if project_id:
            url += f"?project_id={project_id}"
        resp = self.client.post(url, json={"name": name})
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["character"]

    def _create_variant(self, character_id: str, name: str) -> dict:
        resp = self.client.post(
            f"/api/characters/{character_id}/variants", json={"name": name}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["variant"]

    def _create_spec(
        self, spec_type: str = "custom", custom_label: str = "服装"
    ) -> dict:
        resp = self.client.post(
            "/api/specs",
            json={"spec_type": spec_type, "custom_label": custom_label},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["spec"]

    def _build_full_structure(self) -> dict:
        """构建完整的项目结构，返回各实体引用的字典。"""
        refs: dict[str, object] = {}

        # 1. 创建项目
        project = self._create_project("集成验收项目", "阶段1.6端到端测试")
        refs["project"] = project

        # 2. 创建多章节
        ch1 = self._create_chapter(project["id"], "第一章 开端")
        ch2 = self._create_chapter(project["id"], "第二章 发展")
        refs["chapters"] = [ch1, ch2]

        # 3. 创建多场景
        # 第一章下 2 个大场景（大场景不再支持 transition 类型，统一为 content）
        ls_a = self._create_large_scene(ch1["id"], "场景A", scene_type="content")
        ls_b = self._create_large_scene(ch1["id"], "场景B", scene_type="content")
        # 第二章下 1 个大场景
        ls_c = self._create_large_scene(ch2["id"], "场景C", scene_type="content")
        refs["large_scenes"] = [ls_a, ls_b, ls_c]

        # 每个大场景下 2 个小场景
        small_scenes = []
        for ls in [ls_a, ls_b, ls_c]:
            ss1 = self._create_small_scene(ls["id"], f"{ls['name']}-小场景1")
            ss2 = self._create_small_scene(ls["id"], f"{ls['name']}-小场景2")
            small_scenes.extend([ss1, ss2])
        refs["small_scenes"] = small_scenes

        # 4. 创建场景页（每个小场景 2-3 个）
        shot_pages = []
        for idx, ss in enumerate(small_scenes):
            count = 3 if idx == 0 else 2
            for i in range(count):
                page = self._create_shot_page(
                    ss["id"], f"场景页-{i+1}", prompt_text=f"prompt-{i+1}"
                )
                shot_pages.append(page)
        refs["shot_pages"] = shot_pages

        # 5. 创建分支
        target_ss = small_scenes[0]
        branch = self._create_branch(
            "small-scenes", target_ss["id"], "分支甲",
            condition_type="choice", condition_value="选择A",
        )
        refs["branch"] = branch
        # 分支下创建 1 个场景页
        branch_page = self._create_shot_page(
            target_ss["id"], "分支场景页-1", branch_id=branch["id"]
        )
        refs["branch_page"] = branch_page

        # 6. 创建素材并映射
        mat_scene = self._create_material("场景素材", material_type="scene")
        mat_expr = self._create_material("表情素材", material_type="expression")
        refs["materials"] = [mat_scene, mat_expr]

        # 每个素材再添加 1 个素材页（create_material 自动生成 1 个默认页）
        mat_scene_page2 = self._create_material_page(mat_scene["id"], "场景素材页2")
        mat_expr_page2 = self._create_material_page(mat_expr["id"], "表情素材页2")
        refs["material_pages_extra"] = [mat_scene_page2, mat_expr_page2]

        # 关联素材到小场景
        resp = self.client.put(
            f"/api/small-scenes/{target_ss['id']}/materials",
            json={"material_ids": [mat_scene["id"], mat_expr["id"]]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        # 获取素材页列表
        scene_pages_resp = self.client.get(f"/api/materials/{mat_scene['id']}/pages")
        scene_mp_ids = [p["id"] for p in scene_pages_resp.json()["pages"]]
        expr_pages_resp = self.client.get(f"/api/materials/{mat_expr['id']}/pages")
        expr_mp_ids = [p["id"] for p in expr_pages_resp.json()["pages"]]

        # 将素材页映射到场景页（不同类型）
        page1 = shot_pages[0]
        page2 = shot_pages[1]
        resp = self.client.put(
            f"/api/small-scene-pages/{page1['id']}/mappings/scene",
            json={"material_page_id": scene_mp_ids[0]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self.client.put(
            f"/api/small-scene-pages/{page2['id']}/mappings/expression",
            json={"material_page_id": expr_mp_ids[0]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        # 7. 创建人物和变体
        char1 = self._create_character("主角", project_id=project["id"])
        char2 = self._create_character("配角", project_id=project["id"])
        refs["characters"] = [char1, char2]

        # 每个人物创建 2 个变体（除默认外）
        v1a = self._create_variant(char1["id"], "主角-变体A")
        v1b = self._create_variant(char1["id"], "主角-变体B")
        v2a = self._create_variant(char2["id"], "配角-变体A")
        v2b = self._create_variant(char2["id"], "配角-变体B")
        refs["variants"] = [v1a, v1b, v2a, v2b]

        # 创建 2 个规格
        spec1 = self._create_spec("custom", "服装")
        spec2 = self._create_spec("full_body")
        refs["specs"] = [spec1, spec2]

        # 填写规格矩阵值（通过 batch_update）
        matrix = self.client.get(f"/api/characters/{char1['id']}/matrix").json()
        updates = []
        for variant_id, spec_vals in matrix["values"].items():
            for spec_id, val in spec_vals.items():
                updates.append({
                    "spec_value_id": val["id"],
                    "prompt": f"prompt-{variant_id[:8]}-{spec_id[:8]}",
                    "lora_name": f"lora-{variant_id[:8]}",
                    "lora_weight": 0.8,
                })
        if updates:
            resp = self.client.post(
                "/api/character-spec-values/batch", json={"updates": updates}
            )
            self.assertEqual(resp.status_code, 200, resp.text)

        # 8. 场景页人物绑定
        resp = self.client.put(
            f"/api/shot-pages/{page1['id']}/character",
            json={"character_id": char1["id"], "variant_id": v1a["id"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        resp = self.client.put(
            f"/api/shot-pages/{page2['id']}/character",
            json={"character_id": char2["id"], "variant_id": v2a["id"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)

        # 9. 创建分支覆盖
        # 人物覆盖
        resp = self.client.post(
            f"/api/branches/{branch['id']}/overrides",
            json={
                "override_type": "character",
                "target_id": branch_page["id"],
                "character_id": char1["id"],
                "variant_id": v1b["id"],
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        # 参数覆盖
        resp = self.client.post(
            f"/api/branches/{branch['id']}/overrides",
            json={
                "override_type": "parameter",
                "param_key": "seed",
                "param_value": "42",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)

        return refs

    # ── 测试用例 ──────────────────────────────────────────────

    def test_full_project_lifecycle(self):
        """验收清单 1-4, 10-11：完整项目生命周期。"""
        refs = self._build_full_structure()
        project = refs["project"]

        # 10. 创建剧本快照
        resp = self.client.post(
            f"/api/projects/{project['id']}/snapshots", json={"label": "验收前快照"}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        snapshot = resp.json()["snapshot"]
        self.assertEqual(snapshot["label"], "验收前快照")

        # 11. 编译预检查
        resp = self.client.post(
            f"/api/projects/{project['id']}/precheck", json={"scope": "project"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        precheck = resp.json()
        self.assertIn("blocking", precheck)
        self.assertIn("warnings", precheck)
        self.assertIn("summary", precheck)
        self.assertIn("total_pages", precheck["summary"])

        # 验证结构完整性
        # 2 章节
        resp = self.client.get(f"/api/projects/{project['id']}/chapters")
        self.assertEqual(resp.json()["total"], 2)

        # 3 大场景
        chapters = resp.json()["items"]
        ls_count = 0
        for ch in chapters:
            ls_resp = self.client.get(f"/api/chapters/{ch['id']}/large-scenes")
            ls_count += ls_resp.json()["total"]
        self.assertEqual(ls_count, 3)

        # 6 小场景
        ss_count = 0
        for ch in chapters:
            ls_resp = self.client.get(f"/api/chapters/{ch['id']}/large-scenes")
            for ls in ls_resp.json()["items"]:
                ss_resp = self.client.get(f"/api/large-scenes/{ls['id']}/small-scenes")
                ss_count += ss_resp.json()["total"]
        self.assertEqual(ss_count, 6)

        # story-tree 包含 branches 信息
        tree_resp = self.client.get(f"/api/projects/{project['id']}/story-tree")
        self.assertEqual(tree_resp.status_code, 200, tree_resp.text)
        tree = tree_resp.json()
        self.assertTrue(tree["backendAvailable"])
        # 验证小场景下有 branches 数组
        target_ss = tree["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        self.assertIn("branches", target_ss)
        self.assertGreaterEqual(len(target_ss["branches"]), 1)

        # 验证人物
        resp = self.client.get(f"/api/characters?project_id={project['id']}")
        self.assertEqual(resp.json()["total"], 2)

        # 验证素材
        resp = self.client.get("/api/materials")
        self.assertEqual(resp.json()["total"], 2)

        # 验证规格
        resp = self.client.get("/api/specs")
        self.assertEqual(resp.json()["total"], 2)

    def test_persistence_across_restart(self):
        """验收清单 5：刷新、重启应用后全部恢复。"""
        refs = self._build_full_structure()
        project = refs["project"]

        # 记录关键数据
        original_project_id = project["id"]
        original_chapter_count = len(refs["chapters"])
        original_shot_page_count = len(refs["shot_pages"])
        original_character_count = len(refs["characters"])
        original_material_count = len(refs["materials"])

        # 销毁第一个 app 实例（模拟关闭应用）
        del self.app
        del self.client

        # 用同一个 data_root 创建新 app 实例（模拟重启）
        new_app = create_app(
            data_root=self.data_root,
            environment="test",
            locked_environment="test",
        )
        new_client = TestClient(new_app)

        # 验证项目恢复
        resp = new_client.get("/api/projects")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], original_project_id)
        self.assertEqual(items[0]["name"], "集成验收项目")

        # 验证 story-tree 完整
        resp = new_client.get(f"/api/projects/{original_project_id}/story-tree")
        self.assertEqual(resp.status_code, 200)
        tree = resp.json()
        self.assertEqual(len(tree["chapters"]), original_chapter_count)
        # 统计场景页数
        page_count = 0
        for ch in tree["chapters"]:
            for ls in ch["large_scenes"]:
                for ss in ls["small_scenes"]:
                    page_count += len(ss["pages"])
                    # 分支页也要计入
                    for br in ss.get("branches", []):
                        page_count += len(br.get("pages", []))
        self.assertEqual(page_count, original_shot_page_count + 1)  # +1 分支页

        # 验证人物恢复
        resp = new_client.get(f"/api/characters?project_id={original_project_id}")
        self.assertEqual(resp.json()["total"], original_character_count)

        # 验证素材恢复
        resp = new_client.get("/api/materials")
        self.assertEqual(resp.json()["total"], original_material_count)

        # 验证规格恢复
        resp = new_client.get("/api/specs")
        self.assertEqual(resp.json()["total"], 2)

    def test_soft_delete_and_restore(self):
        """验收清单 6：验证删除、恢复。"""
        project = self._create_project("软删除测试项目")
        ch = self._create_chapter(project["id"], "章节1")
        ls = self._create_large_scene(ch["id"], "大场景1")
        ss = self._create_small_scene(ls["id"], "小场景1")
        page = self._create_shot_page(ss["id"], "场景页1")

        # 场景页硬删除 + 通过快照恢复
        # 创建快照
        resp = self.client.post(
            f"/api/projects/{project['id']}/snapshots", json={"label": "删除前"}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        snapshot_id = resp.json()["snapshot"]["id"]

        # 删除场景页
        resp = self.client.delete(f"/api/shot-pages/{page['id']}")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 默认列表不可见
        resp = self.client.get(f"/api/small-scenes/{ss['id']}/shot-pages")
        self.assertEqual(resp.json()["total"], 0)

        # 通过快照恢复场景页
        resp = self.client.post(f"/api/story-snapshots/{snapshot_id}/restore")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 场景页重新可见
        resp = self.client.get(f"/api/small-scenes/{ss['id']}/shot-pages")
        self.assertEqual(resp.json()["total"], 1)

        # 人物软删除和恢复
        char = self._create_character("待删人物", project_id=project["id"])
        resp = self.client.delete(f"/api/characters/{char['id']}")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 默认列表不可见
        resp = self.client.get("/api/characters")
        char_ids = [c["id"] for c in resp.json()["items"]]
        self.assertNotIn(char["id"], char_ids)

        # 恢复人物
        resp = self.client.post(f"/api/characters/{char['id']}/restore")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 重新可见
        resp = self.client.get("/api/characters")
        char_ids = [c["id"] for c in resp.json()["items"]]
        self.assertIn(char["id"], char_ids)

        # 素材软删除，验证引用关系仍存在
        material = self._create_material("待删素材", material_type="scene")
        # 关联到小场景
        self.client.put(
            f"/api/small-scenes/{ss['id']}/materials",
            json={"material_ids": [material["id"]]},
        )
        # 软删除素材
        resp = self.client.delete(f"/api/materials/{material['id']}")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 软删除后默认列表不可见
        resp = self.client.get("/api/materials")
        mat_ids = [m["id"] for m in resp.json()["items"]]
        self.assertNotIn(material["id"], mat_ids)

        # 回收站可见
        resp = self.client.get("/api/materials/trash")
        trash_ids = [m["id"] for m in resp.json()["items"]]
        self.assertIn(material["id"], trash_ids)

        # 永久删除一个素材，验证级联清理
        material2 = self._create_material("永久删除素材", material_type="expression")
        self.client.put(
            f"/api/small-scenes/{ss['id']}/materials",
            json={"material_ids": [material2["id"]]},
        )
        # 确认关联存在
        resp = self.client.get(f"/api/small-scenes/{ss['id']}/materials")
        linked_ids = [m["material_id"] for m in resp.json()["materials"]]
        self.assertIn(material2["id"], linked_ids)

        # 永久删除
        resp = self.client.delete(f"/api/materials/{material2['id']}/permanent")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 级联清理：小场景素材关联已清除
        resp = self.client.get(f"/api/small-scenes/{ss['id']}/materials")
        linked_ids = [m["material_id"] for m in resp.json()["materials"]]
        self.assertNotIn(material2["id"], linked_ids)

        # 永久删除后 GET 返回 404
        resp = self.client.get(f"/api/materials/{material2['id']}")
        self.assertEqual(resp.status_code, 404)

    def test_story_snapshot_restore(self):
        """验收清单 6：剧本快照恢复。"""
        project = self._create_project("快照恢复测试项目")
        ch = self._create_chapter(project["id"], "章节1")
        ls = self._create_large_scene(ch["id"], "大场景1")
        ss = self._create_small_scene(ls["id"], "小场景1")
        page1 = self._create_shot_page(ss["id"], "场景页1")
        page2 = self._create_shot_page(ss["id"], "场景页2")

        # 创建快照
        resp = self.client.post(
            f"/api/projects/{project['id']}/snapshots", json={"label": "初始结构"}
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        snapshot_id = resp.json()["snapshot"]["id"]

        # 修改结构：添加 1 个场景页，删除 1 个场景页
        page3 = self._create_shot_page(ss["id"], "场景页3")
        self.client.delete(f"/api/shot-pages/{page1['id']}")

        # 验证当前结构与快照不同
        resp = self.client.get(f"/api/small-scenes/{ss['id']}/shot-pages")
        current_titles = [p["title"] for p in resp.json()["items"]]
        self.assertNotIn("场景页1", current_titles)
        self.assertIn("场景页3", current_titles)
        self.assertEqual(len(current_titles), 2)

        # 恢复快照
        resp = self.client.post(f"/api/story-snapshots/{snapshot_id}/restore")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 验证结构恢复到快照时的状态
        resp = self.client.get(f"/api/small-scenes/{ss['id']}/shot-pages")
        restored_titles = [p["title"] for p in resp.json()["items"]]
        self.assertIn("场景页1", restored_titles)
        self.assertIn("场景页2", restored_titles)
        self.assertNotIn("场景页3", restored_titles)
        self.assertEqual(len(restored_titles), 2)

    def test_operation_undo_redo(self):
        """验收清单 6：操作撤销重做。

        通过 record_operation 手动记录 rename 操作，验证 undo 恢复原始名称、
        redo 重新应用新名称。
        """
        project = self._create_project("撤销重做测试项目")
        ch = self._create_chapter(project["id"], "章节1")
        ls = self._create_large_scene(ch["id"], "大场景1")
        ss = self._create_small_scene(ls["id"], "小场景1")
        page = self._create_shot_page(ss["id"], "原始场景页")

        # 手动记录 rename 操作（record_operation 不自动触发）
        before_state = {
            "id": page["id"],
            "small_scene_id": ss["id"],
            "branch_id": None,
            "title": "原始场景页",
            "description": "",
            "prompt_text": "",
            "negative_prompt": "",
            "sort_order": 1,
        }
        after_state = {
            "id": page["id"],
            "small_scene_id": ss["id"],
            "branch_id": None,
            "title": "新场景页名",
            "description": "",
            "prompt_text": "",
            "negative_prompt": "",
            "sort_order": 1,
        }
        op = self.manager.record_operation(
            project["id"], "rename", "shot_page",
            entity_id=page["id"],
            before_state=before_state,
            after_state=after_state,
        )
        original_op_id = op["id"]

        # 执行重命名（模拟操作效果）
        self.client.patch(
            f"/api/shot-pages/{page['id']}", json={"title": "新场景页名"}
        )

        # 验证当前名称为新名称
        resp = self.client.get(f"/api/shot-pages/{page['id']}")
        self.assertEqual(resp.json()["shot_page"]["title"], "新场景页名")

        # GET 操作列表
        resp = self.client.get(f"/api/projects/{project['id']}/operations")
        self.assertEqual(resp.status_code, 200, resp.text)
        ops = resp.json()["items"]
        self.assertGreaterEqual(len(ops), 1)

        # 撤销操作
        resp = self.client.post(f"/api/operations/{original_op_id}/undo")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 验证名称恢复为原始
        resp = self.client.get(f"/api/shot-pages/{page['id']}")
        self.assertEqual(resp.json()["shot_page"]["title"], "原始场景页")

        # 重做：对原始操作调用 redo，重新应用 after_state
        resp = self.client.post(f"/api/operations/{original_op_id}/redo")
        self.assertEqual(resp.status_code, 200, resp.text)

        # 验证名称恢复为新名称
        resp = self.client.get(f"/api/shot-pages/{page['id']}")
        self.assertEqual(resp.json()["shot_page"]["title"], "新场景页名")

    def test_inheritance_chain(self):
        """验收清单：继承链。"""
        project = self._create_project("继承链测试项目")
        ch = self._create_chapter(project["id"], "章节1")
        ls = self._create_large_scene(ch["id"], "大场景1")
        ss = self._create_small_scene(ls["id"], "小场景1")
        branch = self._create_branch(
            "small-scenes", ss["id"], "分支A",
            condition_type="choice", condition_value="opt1",
        )
        page = self._create_shot_page(
            ss["id"], "分镜页1", branch_id=branch["id"],
            prompt_text="a beautiful scene",
        )

        resp = self.client.get(f"/api/shot-pages/{page['id']}/inheritance")
        self.assertEqual(resp.status_code, 200, resp.text)
        result = resp.json()

        self.assertIn("chain", result)
        chain = result["chain"]
        levels = [link["level"] for link in chain]
        self.assertEqual(
            levels,
            ["project", "chapter", "large_scene", "small_scene", "branch", "shot_page"],
        )

        # 验证每层有 id 和 name
        for link in chain:
            self.assertIn("id", link)
            self.assertIn("name", link)

        # 验证有效值
        self.assertIn("effective", result)
        self.assertIn("prompt_text", result["effective"])

    def test_no_demo_data_fallback(self):
        """验收清单 7：无展示数据回退。"""
        # 全新空 app 实例（setUp 已创建）
        # GET /api/projects 返回空列表
        resp = self.client.get("/api/projects")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["items"], [])
        self.assertEqual(resp.json()["total"], 0)

        # GET /api/characters 返回空列表
        resp = self.client.get("/api/characters")
        self.assertEqual(resp.json()["items"], [])
        self.assertEqual(resp.json()["total"], 0)

        # GET /api/materials 返回空列表
        resp = self.client.get("/api/materials")
        self.assertEqual(resp.json()["items"], [])
        self.assertEqual(resp.json()["total"], 0)

        # GET /api/specs 返回空列表
        resp = self.client.get("/api/specs")
        self.assertEqual(resp.json()["items"], [])
        self.assertEqual(resp.json()["total"], 0)

        # 创建一个项目后，story-tree 返回空树
        project = self._create_project("空树项目")
        resp = self.client.get(f"/api/projects/{project['id']}/story-tree")
        self.assertEqual(resp.status_code, 200, resp.text)
        tree = resp.json()
        self.assertEqual(tree["chapters"], [])
        self.assertTrue(tree["backendAvailable"])

    def test_branch_with_conditions_and_overrides(self):
        """验收清单：分支条件和覆盖。"""
        project = self._create_project("分支覆盖测试项目")
        ch = self._create_chapter(project["id"], "章节1")
        ls = self._create_large_scene(ch["id"], "大场景1")
        ss = self._create_small_scene(ls["id"], "小场景1")

        # 创建分支，带条件
        branch = self._create_branch(
            "small-scenes", ss["id"], "条件分支",
            condition_type="choice", condition_value="选项A",
            return_point="回到主线",
        )

        # GET 验证条件字段
        resp = self.client.get(f"/api/branches/{branch['id']}")
        self.assertEqual(resp.status_code, 200, resp.text)
        branch_data = resp.json()["branch"]
        self.assertEqual(branch_data["condition_type"], "choice")
        self.assertEqual(branch_data["condition_value"], "选项A")
        self.assertEqual(branch_data["return_point"], "回到主线")

        # 创建人物和变体用于覆盖
        char = self._create_character("覆盖测试人物", project_id=project["id"])
        variants = self.client.get(f"/api/characters/{char['id']}/variants").json()["items"]
        default_variant = next(v for v in variants if v["is_default"])
        other_variant_id = None
        if len(variants) > 1:
            other_variant_id = next(v for v in variants if not v["is_default"])["id"]

        # 创建分支页（用于覆盖目标）
        branch_page = self._create_shot_page(
            ss["id"], "分支页1", branch_id=branch["id"]
        )

        # 创建分支覆盖：人物覆盖
        override_payload: dict = {
            "override_type": "character",
            "target_id": branch_page["id"],
            "character_id": char["id"],
            "variant_id": other_variant_id or default_variant["id"],
        }
        resp = self.client.post(
            f"/api/branches/{branch['id']}/overrides", json=override_payload
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        char_override = resp.json()["override"]
        self.assertEqual(char_override["override_type"], "character")
        self.assertEqual(char_override["character_id"], char["id"])

        # 创建分支覆盖：参数覆盖
        resp = self.client.post(
            f"/api/branches/{branch['id']}/overrides",
            json={
                "override_type": "parameter",
                "param_key": "seed",
                "param_value": "42",
            },
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        param_override = resp.json()["override"]
        self.assertEqual(param_override["param_key"], "seed")
        self.assertEqual(param_override["param_value"], "42")

        # GET 验证覆盖列表
        resp = self.client.get(f"/api/branches/{branch['id']}/overrides")
        self.assertEqual(resp.status_code, 200, resp.text)
        overrides = resp.json()["items"]
        self.assertEqual(len(overrides), 2)
        override_types = [o["override_type"] for o in overrides]
        self.assertIn("character", override_types)
        self.assertIn("parameter", override_types)

        # GET 有效覆盖
        resp = self.client.get(
            f"/api/shot-pages/{branch_page['id']}/effective-overrides",
            params={"branch_id": branch["id"]},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        effective = resp.json()
        # 参数覆盖应出现在有效覆盖中
        self.assertIn("parameter", effective)
        param_eff = [o for o in effective["parameter"] if o["param_key"] == "seed"]
        self.assertEqual(len(param_eff), 1)
        self.assertEqual(param_eff[0]["param_value"], "42")


if __name__ == "__main__":
    unittest.main()
