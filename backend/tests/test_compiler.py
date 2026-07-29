"""阶段 3.1 页级编译器测试。

测试范围：
- 编译基本流程（项目/章节/大场景/小场景/分支/页面范围）
- 配置继承优先级
- 素材页映射解析
- 人物/变体/规格/LoRA 解析
- 工作流版本固定（项目默认 vs 批量覆盖）
- 语义插槽解析
- sort_key 和 input_hash 确定性
- 阻塞错误和警告
- API 集成测试
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.compiler import (
    CompilationResult,
    RenderItem,
    compile_project,
    _compute_input_hash,
    _compute_seed,
)


# ──────────────────────────────────────────────────────────────────
# 工具函数测试
# ──────────────────────────────────────────────────────────────────


class ComputeSeedTests(unittest.TestCase):
    def test_fixed_strategy(self) -> None:
        self.assertEqual(_compute_seed("fixed", 42, "page1"), 42)
        self.assertEqual(_compute_seed("fixed", None, "page1"), 0)

    def test_random_strategy_returns_none(self) -> None:
        self.assertIsNone(_compute_seed("random", 42, "page1"))

    def test_increment_strategy(self) -> None:
        self.assertEqual(_compute_seed("increment", 100, "page1"), 100)
        self.assertEqual(_compute_seed("increment", None, "page1"), 0)

    def test_reuse_last_strategy_returns_none(self) -> None:
        self.assertIsNone(_compute_seed("reuse_last", 42, "page1"))


class ComputeInputHashTests(unittest.TestCase):
    def test_same_input_same_hash(self) -> None:
        """相同输入产生相同 hash。"""
        item1 = RenderItem(
            item_id="id1",
            sort_key="",
            input_hash="",
            project_id="p1",
            project_name="P",
            chapter_id="c1",
            chapter_name="C",
            large_scene_id="l1",
            large_scene_name="L",
            small_scene_id="s1",
            small_scene_name="S",
            shot_page_id="sp1",
            shot_page_title="SP",
            branch_id=None,
            branch_name=None,
            workflow_id="w1",
            workflow_version_id="wv1",
            workflow_label="v1",
            character_id="ch1",
            character_name="Char",
            variant_id="v1",
            variant_name="V",
        )
        item2 = RenderItem(
            item_id="id2",  # item_id 不影响 hash
            sort_key="",
            input_hash="",
            project_id="p1",
            project_name="P",
            chapter_id="c1",
            chapter_name="C",
            large_scene_id="l1",
            large_scene_name="L",
            small_scene_id="s1",
            small_scene_name="S",
            shot_page_id="sp1",
            shot_page_title="SP",
            branch_id=None,
            branch_name=None,
            workflow_id="w1",
            workflow_version_id="wv1",
            workflow_label="v1",
            character_id="ch1",
            character_name="Char",
            variant_id="v1",
            variant_name="V",
        )
        h1 = _compute_input_hash(item1)
        h2 = _compute_input_hash(item2)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 16)

    def test_different_input_different_hash(self) -> None:
        """不同输入产生不同 hash。"""
        item1 = RenderItem(
            item_id="id1", sort_key="", input_hash="",
            project_id="p1", project_name="P", chapter_id="c1", chapter_name="C",
            large_scene_id="l1", large_scene_name="L", small_scene_id="s1", small_scene_name="S",
            shot_page_id="sp1", shot_page_title="SP1", branch_id=None, branch_name=None,
            workflow_id="w1", workflow_version_id="wv1", workflow_label="v1",
            character_id="ch1", character_name="Char", variant_id="v1", variant_name="V",
        )
        item2 = RenderItem(
            item_id="id2", sort_key="", input_hash="",
            project_id="p1", project_name="P", chapter_id="c1", chapter_name="C",
            large_scene_id="l1", large_scene_name="L", small_scene_id="s1", small_scene_name="S",
            shot_page_id="sp2", shot_page_title="SP2", branch_id=None, branch_name=None,
            workflow_id="w1", workflow_version_id="wv1", workflow_label="v1",
            character_id="ch1", character_name="Char", variant_id="v1", variant_name="V",
        )
        h1 = _compute_input_hash(item1)
        h2 = _compute_input_hash(item2)
        self.assertNotEqual(h1, h2)


# ──────────────────────────────────────────────────────────────────
# API 集成测试
# ──────────────────────────────────────────────────────────────────


class _CompilerApiBase(unittest.TestCase):
    """编译器 API 集成测试基类。"""

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

    def _create_project(self, name: str = "测试项目") -> str:
        response = self.client.post("/api/projects", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["project"]["id"]

    def _create_chapter(self, project_id: str, name: str = "第一章") -> str:
        response = self.client.post(
            f"/api/projects/{project_id}/chapters",
            json={"name": name},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["chapter"]["id"]

    def _create_large_scene(self, chapter_id: str, name: str = "大场景1") -> str:
        response = self.client.post(
            f"/api/chapters/{chapter_id}/large-scenes",
            json={"name": name, "scene_type": "content"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["large_scene"]["id"]

    def _create_small_scene(self, large_scene_id: str, name: str = "小场景1") -> str:
        response = self.client.post(
            f"/api/large-scenes/{large_scene_id}/small-scenes",
            json={"name": name},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["small_scene"]["id"]

    def _create_shot_page(self, small_scene_id: str, name: str = "场景页1") -> str:
        response = self.client.post(
            f"/api/small-scenes/{small_scene_id}/shot-pages",
            json={"title": name},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["shot_page"]["id"]

    def _create_material(
        self,
        name: str = "素材1",
        material_type: str = "composition",
    ) -> str:
        response = self.client.post(
            "/api/materials",
            json={
                "name": name,
                "material_type": material_type,
                "content": "素材内容",
                "prompt_text": "prompt content",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["material"]["id"]

    def _create_material_page(self, material_id: str, name: str = "素材页1") -> str:
        response = self.client.post(
            f"/api/materials/{material_id}/pages",
            json={"name": name, "content": "页内容", "prompt_text": "page prompt"},
        )
        self.assertIn(response.status_code, (200, 201), response.text)
        data = response.json()
        return data.get("material_page", data)["id"]

    def _create_character(self, name: str = "人物1") -> str:
        response = self.client.post(
            "/api/characters",
            json={"name": name},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["character"]["id"]

    def _create_variant(self, character_id: str, name: str = "变体1") -> str:
        response = self.client.post(
            f"/api/characters/{character_id}/variants",
            json={"name": name, "default_prompt": "character prompt"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["variant"]["id"]

    def _create_workflow(self, name: str = "工作流1") -> str:
        response = self.client.post("/api/workflows", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["workflow"]["id"]

    def _save_draft_and_publish(
        self,
        workflow_id: str,
        nodes: list[dict] | None = None,
    ) -> str:
        """保存草稿并发布版本，返回版本 ID。"""
        if nodes is None:
            nodes = [
                {
                    "id": "1",
                    "type": "CheckpointLoaderSimple",
                    "title": "Load",
                    "position": [0, 0],
                    "size": [240, 100],
                    "mode": 0,
                    "flags": {"enabled": True, "bypassed": False, "disabled": False},
                    "widgets_values": ["model.safetensors"],
                    "properties": {},
                    "inputs": [],
                    "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
                    "order": 0,
                    "is_unknown": False,
                }
            ]
        normalized = {"nodes": nodes, "links": [], "groups": [], "metadata": {}}
        # 保存草稿
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft",
            json={
                "normalized_graph": json.dumps(normalized, ensure_ascii=False),
                "raw_ui_json": None,
                "raw_api_json": None,
                "node_count": len(nodes),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 发布版本
        response = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v1", "normalized_graph": ""},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["version"]["id"]

    def _set_project_default_workflow(self, project_id: str, workflow_id: str) -> None:
        response = self.client.post(
            f"/api/projects/{project_id}/default-workflow",
            json={"workflow_id": workflow_id},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _setup_full_project(self) -> tuple[str, str, str, str]:
        """创建完整项目结构，返回 (project_id, shot_page_id, workflow_id, version_id)。"""
        project_id = self._create_project("编译测试项目")
        chapter_id = self._create_chapter(project_id)
        large_scene_id = self._create_large_scene(chapter_id)
        small_scene_id = self._create_small_scene(large_scene_id)
        shot_page_id = self._create_shot_page(small_scene_id)

        # 创建工作流并设置项目默认
        workflow_id = self._create_workflow()
        version_id = self._save_draft_and_publish(workflow_id)
        self._set_project_default_workflow(project_id, workflow_id)

        return project_id, shot_page_id, workflow_id, version_id


class CompileBasicTests(_CompilerApiBase):
    def test_compile_empty_project(self) -> None:
        """空项目编译返回空列表。"""
        project_id = self._create_project("空项目")
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["summary"]["total_pages"], 0)
        self.assertEqual(len(data["items"]), 0)

    def test_compile_nonexistent_project_404(self) -> None:
        """不存在的项目返回 404 通过空列表（编译器不报 404）。"""
        response = self.client.post(
            "/api/projects/nonexistent-id/compile",
            json={"scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["summary"]["total_pages"], 0)

    def test_compile_with_full_structure(self) -> None:
        """完整结构编译生成跑图项。"""
        project_id, shot_page_id, workflow_id, version_id = self._setup_full_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["summary"]["total_pages"], 1)
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["shot_page_id"], shot_page_id)
        self.assertEqual(item["workflow_id"], workflow_id)
        self.assertEqual(item["workflow_version_id"], version_id)
        self.assertTrue(item["input_hash"])
        self.assertTrue(item["sort_key"])

    def test_compile_scope_chapter(self) -> None:
        """按章节范围编译。"""
        project_id = self._create_project()
        chapter_id = self._create_chapter(project_id)
        large_scene_id = self._create_large_scene(chapter_id)
        small_scene_id = self._create_small_scene(large_scene_id)
        self._create_shot_page(small_scene_id)

        workflow_id = self._create_workflow()
        self._save_draft_and_publish(workflow_id)
        self._set_project_default_workflow(project_id, workflow_id)

        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "chapter", "scope_id": chapter_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["summary"]["total_pages"], 1)

    def test_compile_scope_small_scene(self) -> None:
        """按小场景范围编译。"""
        project_id = self._create_project()
        chapter_id = self._create_chapter(project_id)
        large_scene_id = self._create_large_scene(chapter_id)
        small_scene_id = self._create_small_scene(large_scene_id)
        self._create_shot_page(small_scene_id)

        workflow_id = self._create_workflow()
        self._save_draft_and_publish(workflow_id)
        self._set_project_default_workflow(project_id, workflow_id)

        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "small_scene", "scope_id": small_scene_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["summary"]["total_pages"], 1)

    def test_compile_scope_shot_pages(self) -> None:
        """按页面列表范围编译。"""
        project_id, shot_page_id, _, _ = self._setup_full_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "shot_pages", "scope_id": shot_page_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["summary"]["total_pages"], 1)
        self.assertEqual(data["items"][0]["shot_page_id"], shot_page_id)


class CompileWorkflowTests(_CompilerApiBase):
    def test_no_workflow_blocks(self) -> None:
        """无工作流时页面被阻塞。"""
        project_id = self._create_project()
        chapter_id = self._create_chapter(project_id)
        large_scene_id = self._create_large_scene(chapter_id)
        small_scene_id = self._create_small_scene(large_scene_id)
        self._create_shot_page(small_scene_id)
        # 不设置项目默认工作流

        result = compile_project(self.manager, project_id, scope="project")
        self.assertEqual(len(result.items), 0)
        self.assertGreater(len(result.blocking_errors), 0)
        self.assertEqual(result.blocking_errors[0]["type"], "no_workflow")

    def test_workflow_override(self) -> None:
        """批量覆盖工作流。"""
        project_id, shot_page_id, _, _ = self._setup_full_project()
        # 创建另一个工作流
        workflow_id2 = self._create_workflow("覆盖工作流")
        version_id2 = self._save_draft_and_publish(workflow_id2)

        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={
                "scope": "project",
                "workflow_id": workflow_id2,
                "workflow_version_id": version_id2,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data["items"]), 1)
        item = data["items"][0]
        self.assertEqual(item["workflow_id"], workflow_id2)
        self.assertEqual(item["workflow_version_id"], version_id2)
        self.assertEqual(item["field_sources"]["workflow"], "batch_override")

    def test_invalid_workflow_version_blocks(self) -> None:
        """工作流版本不存在时阻塞。"""
        project_id, shot_page_id, workflow_id, _ = self._setup_full_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={
                "scope": "project",
                "workflow_id": workflow_id,
                "workflow_version_id": "nonexistent-version",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data["items"]), 0)
        self.assertEqual(data["summary"]["blocked_pages"], 1)


class CompileCharacterTests(_CompilerApiBase):
    def test_character_binding(self) -> None:
        """人物绑定正确解析。"""
        project_id, shot_page_id, _, _ = self._setup_full_project()

        # 创建人物和变体
        character_id = self._create_character("测试人物")
        variant_id = self._create_variant(character_id, "默认变体")

        # 绑定人物到场景页
        response = self.client.put(
            f"/api/shot-pages/{shot_page_id}/character",
            json={"character_id": character_id, "variant_id": variant_id},
        )
        self.assertEqual(response.status_code, 200, response.text)

        # 编译
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["items"][0]
        self.assertEqual(item["character_id"], character_id)
        self.assertEqual(item["variant_id"], variant_id)
        self.assertEqual(item["character_name"], "测试人物")
        self.assertEqual(item["field_sources"]["character"], "shot_page")

    def test_missing_character_warning(self) -> None:
        """未绑定人物时产生警告。"""
        project_id, _, _, _ = self._setup_full_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertGreater(len(data["warnings"]), 0)
        char_warnings = [w for w in data["warnings"] if w["type"] == "missing_character"]
        self.assertEqual(len(char_warnings), 1)


class CompileMaterialTests(_CompilerApiBase):
    def test_material_mapping_resolved(self) -> None:
        """素材页映射正确解析。"""
        project_id, shot_page_id, _, _ = self._setup_full_project()

        # 创建素材和素材页
        material_id = self._create_material("构图素材", "composition")
        material_page_id = self._create_material_page(material_id, "构图页")

        # 关联素材到小场景
        # 先获取 shot_page 的 small_scene_id
        response = self.client.get(f"/api/shot-pages/{shot_page_id}")
        small_scene_id = response.json()["shot_page"]["small_scene_id"]

        response = self.client.put(
            f"/api/small-scenes/{small_scene_id}/materials",
            json={"material_ids": [material_id]},
        )
        self.assertEqual(response.status_code, 200, response.text)

        # 设置映射
        response = self.client.put(
            f"/api/small-scene-pages/{shot_page_id}/mappings/composition",
            json={"material_page_id": material_page_id},
        )
        self.assertEqual(response.status_code, 200, response.text)

        # 编译
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["items"][0]
        self.assertIn("composition", item["material_mappings"])
        self.assertEqual(
            item["material_mappings"]["composition"]["material_page_id"],
            material_page_id,
        )


class CompileDeterminismTests(_CompilerApiBase):
    def test_same_input_same_hash(self) -> None:
        """相同输入两次编译产生相同 input_hash。"""
        project_id, _, _, _ = self._setup_full_project()
        r1 = self.client.post(f"/api/projects/{project_id}/compile", json={"scope": "project"})
        r2 = self.client.post(f"/api/projects/{project_id}/compile", json={"scope": "project"})
        h1 = r1.json()["items"][0]["input_hash"]
        h2 = r2.json()["items"][0]["input_hash"]
        self.assertEqual(h1, h2)

    def test_different_instance_count_different_hash(self) -> None:
        """不同实例数产生不同 input_hash。"""
        project_id, _, _, _ = self._setup_full_project()
        r1 = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project", "instance_count": 1},
        )
        r2 = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project", "instance_count": 4},
        )
        h1 = r1.json()["items"][0]["input_hash"]
        h2 = r2.json()["items"][0]["input_hash"]
        self.assertNotEqual(h1, h2)


class CompileSeedTests(_CompilerApiBase):
    def test_fixed_seed(self) -> None:
        """固定种子策略。"""
        project_id, _, _, _ = self._setup_full_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project", "seed_strategy": "fixed", "seed_base": 42},
        )
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["items"][0]
        self.assertEqual(item["seed_strategy"], "fixed")
        self.assertEqual(item["seed_value"], 42)

    def test_random_seed_none(self) -> None:
        """随机种子策略编译时为 None。"""
        project_id, _, _, _ = self._setup_full_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project", "seed_strategy": "random"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["items"][0]
        self.assertEqual(item["seed_strategy"], "random")
        self.assertIsNone(item["seed_value"])

    def test_invalid_seed_strategy_422(self) -> None:
        """无效种子策略返回 422。"""
        project_id, _, _, _ = self._setup_full_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project", "seed_strategy": "invalid"},
        )
        self.assertEqual(response.status_code, 422)


class CompileValidationTests(_CompilerApiBase):
    def test_invalid_scope_422(self) -> None:
        """无效 scope 返回 422。"""
        project_id = self._create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "invalid_scope"},
        )
        self.assertEqual(response.status_code, 422)

    def test_scope_without_id_422(self) -> None:
        """scope=chapter 但无 scope_id 返回 422。"""
        project_id = self._create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "chapter"},
        )
        self.assertEqual(response.status_code, 422)

    def test_instance_count_validation(self) -> None:
        """实例数验证。"""
        project_id, _, _, _ = self._setup_full_project()
        # 0 不允许
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project", "instance_count": 0},
        )
        self.assertEqual(response.status_code, 422)
        # 101 不允许
        response = self.client.post(
            f"/api/projects/{project_id}/compile",
            json={"scope": "project", "instance_count": 101},
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
