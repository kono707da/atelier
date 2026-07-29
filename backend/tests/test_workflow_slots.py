"""阶段 2.5 语义插槽测试。

测试范围：
- 内置插槽定义
- 插槽解析（业务上下文值、节点值、默认值）
- 冲突策略（overwrite/skip/merge/error）
- 转换规则
- 必填校验
- 插槽绑定校验
- 接入人物值、素材值、项目默认配置
- 插槽应用到工作流
- API 集成测试
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.workflow_models import NormalizedWorkflow
from backend.app.workflow_slots import (
    BUILTIN_SLOT_DEFINITIONS,
    BUILTIN_SLOT_TYPES,
    apply_slots_to_workflow,
    apply_transform_rule,
    get_builtin_slot_definition,
    list_builtin_slot_definitions,
    resolve_all_slots,
    resolve_slot_value,
    validate_slot_bindings,
)


def _make_workflow_with_slots() -> NormalizedWorkflow:
    """生成带可绑定输入的工作流。"""
    return NormalizedWorkflow(
        nodes=[
            {
                "id": "1",
                "type": "CheckpointLoaderSimple",
                "title": "Load Checkpoint",
                "position": [0, 0],
                "size": [240, 0],
                "mode": 0,
                "flags": {"enabled": True},
                "widgets_values": ["model.safetensors"],
                "properties": {},
                "inputs": [],
                "outputs": [{"name": "MODEL", "type": "MODEL", "links": []}],
                "order": 0,
                "is_unknown": False,
            },
            {
                "id": "2",
                "type": "CLIPTextEncode",
                "title": "Positive Prompt",
                "position": [320, 0],
                "size": [240, 0],
                "mode": 0,
                "flags": {"enabled": True},
                "widgets_values": ["beautiful scenery"],
                "properties": {},
                "inputs": [{"name": "text", "type": "STRING", "link": None, "value": "beautiful scenery"}],
                "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": []}],
                "order": 1,
                "is_unknown": False,
            },
            {
                "id": "3",
                "type": "EmptyLatentImage",
                "title": "Empty Latent",
                "position": [320, 200],
                "size": [240, 0],
                "mode": 0,
                "flags": {"enabled": True},
                "widgets_values": [512, 512, 1],
                "properties": {},
                "inputs": [
                    {"name": "width", "type": "INT", "link": None, "value": 512},
                    {"name": "height", "type": "INT", "link": None, "value": 512},
                    {"name": "batch_size", "type": "INT", "link": None, "value": 1},
                ],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                "order": 2,
                "is_unknown": False,
            },
        ],
        links=[],
        groups=[],
        metadata={"source_format": "ui_json"},
    )


# ── 内置插槽定义测试 ──────────────────────────────────────────


class BuiltinSlotDefinitionsTests(unittest.TestCase):
    def test_list_builtin_slots(self) -> None:
        """列出所有内置插槽定义。"""
        defs = list_builtin_slot_definitions()
        self.assertGreater(len(defs), 10)
        slot_types = {d["slot_type"] for d in defs}
        self.assertIn("positive_prompt", slot_types)
        self.assertIn("negative_prompt", slot_types)
        self.assertIn("character_prompt", slot_types)
        self.assertIn("lora_name", slot_types)
        self.assertIn("lora_weight", slot_types)
        self.assertIn("checkpoint", slot_types)
        self.assertIn("vae", slot_types)
        self.assertIn("seed", slot_types)
        self.assertIn("width", slot_types)
        self.assertIn("height", slot_types)
        self.assertIn("batch_size", slot_types)
        self.assertIn("output_prefix", slot_types)
        self.assertIn("custom", slot_types)

    def test_get_builtin_slot_definition(self) -> None:
        """获取单个内置插槽定义。"""
        defn = get_builtin_slot_definition("positive_prompt")
        self.assertIsNotNone(defn)
        self.assertEqual(defn["slot_type"], "positive_prompt")
        self.assertEqual(defn["value_type"], "string")
        self.assertEqual(defn["default_conflict_strategy"], "merge")

    def test_get_nonexistent_slot_definition(self) -> None:
        """获取不存在的插槽定义返回 None。"""
        result = get_builtin_slot_definition("nonexistent")
        self.assertIsNone(result)

    def test_builtin_slot_types_complete(self) -> None:
        """内置插槽类型与定义列表一致。"""
        def_types = {d["slot_type"] for d in BUILTIN_SLOT_DEFINITIONS}
        self.assertEqual(def_types, set(BUILTIN_SLOT_TYPES.keys()))


# ── 转换规则测试 ──────────────────────────────────────────────


class TransformRuleTests(unittest.TestCase):
    def test_empty_rule_returns_value(self) -> None:
        """空规则直接返回原值。"""
        result = apply_transform_rule("hello", "")
        self.assertEqual(result, "hello")

    def test_simple_value_rule(self) -> None:
        """{value} 规则返回原值。"""
        result = apply_transform_rule("hello", "{value}")
        self.assertEqual(result, "hello")

    def test_template_with_context(self) -> None:
        """模板支持上下文变量。"""
        result = apply_transform_rule(
            "girl",
            "{character_name}, {value}",
            context={"character_name": "Alice"},
        )
        self.assertEqual(result, "Alice, girl")

    def test_missing_context_var_returns_value(self) -> None:
        """模板变量缺失时返回原值。"""
        result = apply_transform_rule("hello", "{missing_var}_{value}")
        self.assertEqual(result, "hello")


# ── 插槽解析测试 ──────────────────────────────────────────────


class SlotResolveTests(unittest.TestCase):
    def test_resolve_positive_prompt_from_context(self) -> None:
        """从人物上下文解析正向提示词。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "正向提示词",
            "slot_type": "positive_prompt",
            "node_id": "2",
            "input_name": "text",
            "transform_rule": "",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "overwrite",
        }
        context = {
            "character_values": {"character_prompt": "1girl, red hair"},
            "material_values": {"material_prompt": "forest background"},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertIsNotNone(result["resolved_value"])
        self.assertEqual(result["source"], "context")
        self.assertIn("1girl, red hair", result["resolved_value"])
        self.assertIn("forest background", result["resolved_value"])

    def test_resolve_with_overwrite_strategy(self) -> None:
        """overwrite 策略：用业务值覆盖节点值。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "正向提示词",
            "slot_type": "positive_prompt",
            "node_id": "2",
            "input_name": "text",
            "transform_rule": "",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "overwrite",
        }
        context = {
            "character_values": {"character_prompt": "1girl"},
            "material_values": {},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertEqual(result["source"], "context")
        self.assertEqual(result["resolved_value"], "1girl")

    def test_resolve_with_skip_strategy(self) -> None:
        """skip 策略：保留节点值。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "正向提示词",
            "slot_type": "positive_prompt",
            "node_id": "2",
            "input_name": "text",
            "transform_rule": "",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "skip",
        }
        context = {
            "character_values": {"character_prompt": "1girl"},
            "material_values": {},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertEqual(result["source"], "node")

    def test_resolve_with_merge_strategy(self) -> None:
        """merge 策略：合并节点值和业务值。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "正向提示词",
            "slot_type": "positive_prompt",
            "node_id": "2",
            "input_name": "text",
            "transform_rule": "",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "merge",
        }
        context = {
            "character_values": {"character_prompt": "1girl"},
            "material_values": {},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertEqual(result["source"], "merged")
        self.assertIn("beautiful scenery", result["resolved_value"])
        self.assertIn("1girl", result["resolved_value"])

    def test_resolve_with_error_strategy(self) -> None:
        """error 策略：冲突时报错。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "正向提示词",
            "slot_type": "positive_prompt",
            "node_id": "2",
            "input_name": "text",
            "transform_rule": "",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "error",
        }
        context = {
            "character_values": {"character_prompt": "1girl"},
            "material_values": {},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertGreater(len(result["errors"]), 0)
        self.assertIn("冲突", result["errors"][0])

    def test_resolve_with_default_value(self) -> None:
        """无上下文值和节点值时使用默认值。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "checkpoint",
            "slot_type": "checkpoint",
            "node_id": "1",
            "input_name": "ckpt_name",
            "transform_rule": "",
            "default_value": "default_model.safetensors",
            "is_required": False,
            "conflict_strategy": "overwrite",
        }
        result = resolve_slot_value(slot, wf, context={})
        self.assertEqual(result["source"], "default")
        self.assertEqual(result["resolved_value"], "default_model.safetensors")

    def test_resolve_required_missing(self) -> None:
        """必填插槽无值时报错。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "vae",
            "slot_type": "vae",
            "node_id": "999",  # 不存在的节点
            "input_name": "vae_name",
            "transform_rule": "",
            "default_value": None,
            "is_required": True,
            "conflict_strategy": "overwrite",
        }
        result = resolve_slot_value(slot, wf, context={})
        self.assertGreater(len(result["errors"]), 0)
        self.assertIn("必填", result["errors"][0])

    def test_resolve_from_project_config(self) -> None:
        """从项目配置解析值。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "width",
            "slot_type": "width",
            "node_id": "3",
            "input_name": "width",
            "transform_rule": "",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "overwrite",
        }
        context = {
            "project_config": {"default_width": 768},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertEqual(result["source"], "context")
        self.assertEqual(result["resolved_value"], 768)

    def test_resolve_custom_slot(self) -> None:
        """自定义插槽从 custom_values 解析。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "自定义参数1",
            "slot_type": "custom",
            "node_id": "2",
            "input_name": "text",
            "transform_rule": "",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "overwrite",
        }
        context = {
            "custom_values": {"自定义参数1": "custom_value_123"},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertEqual(result["source"], "context")
        self.assertEqual(result["resolved_value"], "custom_value_123")

    def test_resolve_with_transform_rule(self) -> None:
        """转换规则应用到解析值。"""
        wf = _make_workflow_with_slots()
        slot = {
            "slot_name": "正向提示词",
            "slot_type": "positive_prompt",
            "node_id": "2",
            "input_name": "text",
            "transform_rule": "masterpiece, {value}",
            "default_value": None,
            "is_required": False,
            "conflict_strategy": "overwrite",
        }
        context = {
            "character_values": {"character_prompt": "1girl"},
            "material_values": {},
        }
        result = resolve_slot_value(slot, wf, context=context)
        self.assertEqual(result["resolved_value"], "masterpiece, 1girl")


# ── 批量解析测试 ──────────────────────────────────────────────


class ResolveAllSlotsTests(unittest.TestCase):
    def test_resolve_multiple_slots(self) -> None:
        """批量解析多个插槽。"""
        wf = _make_workflow_with_slots()
        slots = [
            {
                "slot_name": "正向提示词",
                "slot_type": "positive_prompt",
                "node_id": "2",
                "input_name": "text",
                "transform_rule": "",
                "default_value": None,
                "is_required": False,
                "conflict_strategy": "overwrite",
            },
            {
                "slot_name": "width",
                "slot_type": "width",
                "node_id": "3",
                "input_name": "width",
                "transform_rule": "",
                "default_value": None,
                "is_required": True,
                "conflict_strategy": "overwrite",
            },
        ]
        context = {
            "character_values": {"character_prompt": "1girl"},
            "material_values": {},
            "project_config": {"default_width": 768},
        }
        result = resolve_all_slots(slots, wf, context=context)
        self.assertEqual(result["summary"]["total_slots"], 2)
        self.assertEqual(result["summary"]["resolved_count"], 2)
        self.assertFalse(result["has_errors"])

    def test_resolve_with_required_missing(self) -> None:
        """必填插槽缺失时计入 required_missing。"""
        wf = _make_workflow_with_slots()
        slots = [
            {
                "slot_name": "vae",
                "slot_type": "vae",
                "node_id": "999",
                "input_name": "vae_name",
                "transform_rule": "",
                "default_value": None,
                "is_required": True,
                "conflict_strategy": "overwrite",
            },
        ]
        result = resolve_all_slots(slots, wf, context={})
        self.assertTrue(result["has_errors"])
        self.assertEqual(result["summary"]["required_missing"], 1)


# ── 插槽绑定校验测试 ──────────────────────────────────────────


class ValidateSlotBindingsTests(unittest.TestCase):
    def test_valid_bindings(self) -> None:
        """有效的插槽绑定通过校验。"""
        wf = _make_workflow_with_slots()
        slots = [
            {
                "slot_name": "正向提示词",
                "slot_type": "positive_prompt",
                "node_id": "2",
                "input_name": "text",
                "transform_rule": "",
                "default_value": None,
                "is_required": False,
                "conflict_strategy": "overwrite",
            },
        ]
        result = validate_slot_bindings(slots, wf)
        self.assertTrue(result["is_valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_node_not_found(self) -> None:
        """绑定的节点不存在时报错。"""
        wf = _make_workflow_with_slots()
        slots = [
            {
                "slot_name": "test",
                "slot_type": "positive_prompt",
                "node_id": "nonexistent",
                "input_name": "text",
                "transform_rule": "",
                "default_value": None,
                "is_required": False,
                "conflict_strategy": "overwrite",
            },
        ]
        result = validate_slot_bindings(slots, wf)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["errors"][0]["error_type"], "node_not_found")

    def test_duplicate_slot_name(self) -> None:
        """插槽名重复时报错。"""
        wf = _make_workflow_with_slots()
        slots = [
            {
                "slot_name": "重复名",
                "slot_type": "positive_prompt",
                "node_id": "2",
                "input_name": "text",
                "transform_rule": "",
                "default_value": None,
                "is_required": False,
                "conflict_strategy": "overwrite",
            },
            {
                "slot_name": "重复名",
                "slot_type": "negative_prompt",
                "node_id": "2",
                "input_name": "text",
                "transform_rule": "",
                "default_value": None,
                "is_required": False,
                "conflict_strategy": "overwrite",
            },
        ]
        result = validate_slot_bindings(slots, wf)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["errors"][0]["error_type"], "duplicate_name")

    def test_invalid_conflict_strategy(self) -> None:
        """无效的冲突策略报错。"""
        wf = _make_workflow_with_slots()
        slots = [
            {
                "slot_name": "test",
                "slot_type": "positive_prompt",
                "node_id": "2",
                "input_name": "text",
                "transform_rule": "",
                "default_value": None,
                "is_required": False,
                "conflict_strategy": "invalid_strategy",
            },
        ]
        result = validate_slot_bindings(slots, wf)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["errors"][0]["error_type"], "invalid_conflict_strategy")


# ── 插槽应用测试 ──────────────────────────────────────────────


class ApplySlotsTests(unittest.TestCase):
    def test_apply_slots_to_workflow(self) -> None:
        """将解析后的插槽值应用到工作流。"""
        wf = _make_workflow_with_slots()
        resolved_slots = [
            {
                "slot_name": "正向提示词",
                "slot_type": "positive_prompt",
                "node_id": "2",
                "input_name": "text",
                "resolved_value": "1girl, red hair",
                "source": "context",
                "warnings": [],
                "errors": [],
                "is_required": False,
                "conflict_strategy": "overwrite",
            },
        ]
        apply_slots_to_workflow(wf, resolved_slots)
        # 验证节点2的text输入值已更新
        for node in wf.nodes:
            if node["id"] == "2":
                for inp in node["inputs"]:
                    if inp["name"] == "text":
                        self.assertEqual(inp["value"], "1girl, red hair")
                        return
        self.fail("未找到节点2的text输入")


# ── API 集成测试 ──────────────────────────────────────────────


class _SlotAPIBase(unittest.TestCase):
    """插槽 API 测试基类。"""

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

    def _create_workflow(self, name: str = "测试工作流") -> dict:
        response = self.client.post("/api/workflows", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["workflow"]

    def _seed_sample_draft(self, workflow_id: str) -> None:
        """创建包含可绑定输入的草稿。"""
        normalized = {
            "nodes": [
                {"id": "1", "type": "CheckpointLoaderSimple", "title": "Load Checkpoint",
                 "position": [0, 0], "size": [240, 0], "mode": 0,
                 "flags": {"enabled": True}, "widgets_values": ["model.safetensors"], "properties": {},
                 "inputs": [], "outputs": [{"name": "MODEL", "type": "MODEL", "links": []}],
                 "order": 0, "is_unknown": False},
                {"id": "2", "type": "CLIPTextEncode", "title": "Positive Prompt",
                 "position": [320, 0], "size": [240, 0], "mode": 0,
                 "flags": {"enabled": True}, "widgets_values": ["beautiful scenery"], "properties": {},
                 "inputs": [{"name": "text", "type": "STRING", "link": None, "value": "beautiful scenery"}],
                 "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING", "links": []}],
                 "order": 1, "is_unknown": False},
            ],
            "links": [],
            "groups": [],
            "metadata": {"source_format": "ui_json"},
        }
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft",
            json={
                "normalized_graph": json.dumps(normalized, ensure_ascii=False),
                "node_count": 2,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _set_slot(self, workflow_id: str, slot_name: str, slot_type: str,
                  node_id: str, input_name: str, **kwargs) -> dict:
        payload = {
            "slot_name": slot_name,
            "slot_type": slot_type,
            "node_id": node_id,
            "input_name": input_name,
            **kwargs,
        }
        response = self.client.put(
            f"/api/workflows/{workflow_id}/semantic-slots",
            json=payload,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["slot"]


class SlotDefinitionAPITests(_SlotAPIBase):
    def test_list_slot_definitions(self) -> None:
        """通过API获取内置插槽定义。"""
        response = self.client.get("/api/slot-definitions")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertGreater(len(data["definitions"]), 10)


class SlotResolveAPITests(_SlotAPIBase):
    def test_resolve_slots(self) -> None:
        """通过API解析插槽。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        self._set_slot(
            wf["id"], "正向提示词", "positive_prompt",
            node_id="2", input_name="text",
            conflict_strategy="overwrite",
        )
        response = self.client.post(
            f"/api/workflows/{wf['id']}/slots/resolve",
            json={"context": {
                "character_values": {"character_prompt": "1girl, red hair"},
                "material_values": {},
            }},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["summary"]["total_slots"], 1)
        self.assertEqual(data["summary"]["resolved_count"], 1)
        self.assertIn("1girl", data["resolved_slots"][0]["resolved_value"])

    def test_resolve_slots_no_draft(self) -> None:
        """草稿不存在时返回404。"""
        wf = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{wf['id']}/slots/resolve",
            json={"context": {}},
        )
        self.assertEqual(response.status_code, 404)

    def test_resolve_slots_with_project_config(self) -> None:
        """从项目配置解析值。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        self._set_slot(
            wf["id"], "checkpoint", "checkpoint",
            node_id="1", input_name="ckpt_name",
            default_value="fallback.safetensors",
        )
        response = self.client.post(
            f"/api/workflows/{wf['id']}/slots/resolve",
            json={"context": {
                "project_config": {"default_checkpoint": "configured_model.safetensors"},
            }},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        slot_result = data["resolved_slots"][0]
        self.assertEqual(slot_result["source"], "context")
        self.assertEqual(slot_result["resolved_value"], "configured_model.safetensors")


class SlotValidateAPITests(_SlotAPIBase):
    def test_validate_slots_valid(self) -> None:
        """校验有效的插槽绑定。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        self._set_slot(
            wf["id"], "正向提示词", "positive_prompt",
            node_id="2", input_name="text",
        )
        response = self.client.post(f"/api/workflows/{wf['id']}/slots/validate")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["is_valid"])

    def test_validate_slots_invalid_node(self) -> None:
        """校验无效的节点绑定。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        self._set_slot(
            wf["id"], "test", "positive_prompt",
            node_id="nonexistent", input_name="text",
        )
        response = self.client.post(f"/api/workflows/{wf['id']}/slots/validate")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertFalse(data["is_valid"])
        self.assertGreater(len(data["errors"]), 0)

    def test_validate_slots_no_draft(self) -> None:
        """草稿不存在时返回404。"""
        wf = self._create_workflow()
        response = self.client.post(f"/api/workflows/{wf['id']}/slots/validate")
        self.assertEqual(response.status_code, 404)


class SlotCRUDPersistenceTests(_SlotAPIBase):
    def test_slot_persisted_after_set(self) -> None:
        """设置插槽后持久化。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        self._set_slot(
            wf["id"], "正向提示词", "positive_prompt",
            node_id="2", input_name="text",
            is_required=True,
        )
        # 重新获取
        response = self.client.get(f"/api/workflows/{wf['id']}/semantic-slots")
        self.assertEqual(response.status_code, 200)
        slots = response.json()["slots"]
        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0]["slot_name"], "正向提示词")
        self.assertTrue(slots[0]["is_required"])

    def test_delete_slot(self) -> None:
        """删除插槽。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        self._set_slot(
            wf["id"], "test", "positive_prompt",
            node_id="2", input_name="text",
        )
        response = self.client.delete(f"/api/workflows/{wf['id']}/semantic-slots/test")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

    def test_delete_nonexistent_slot(self) -> None:
        """删除不存在的插槽返回404。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.delete(f"/api/workflows/{wf['id']}/semantic-slots/nonexistent")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
