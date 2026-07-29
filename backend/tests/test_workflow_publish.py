"""阶段 2.6 转换、校验和发布测试。

测试范围：
- 规范化结构转 API JSON（节点、连线、widgets_values、禁用/旁路节点跳过）
- 规范化结构转 UI JSON（节点、连线、分组、last_node_id/last_link_id）
- 导出工作流（api_json/ui_json 格式，优先原始 JSON）
- 发布前预检查（节点定义、必填输入、悬空连线、未知节点、语义插槽）
- 往返测试（导入—导出—重新导入的数据完整性）
- API 集成测试（/export、/precheck、/publish、/roundtrip-test）
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.workflow_models import NormalizedWorkflow, parse_workflow_from_raw
from backend.app.workflow_publish import (
    export_workflow,
    normalized_to_api_json,
    normalized_to_ui_json,
    precheck_publish,
    roundtrip_test,
)


# ──────────────────────────────────────────────────────────────────
# 测试辅助
# ──────────────────────────────────────────────────────────────────


def _make_simple_workflow() -> NormalizedWorkflow:
    """简单工作流：2 节点 + 1 连线。"""
    return NormalizedWorkflow(
        nodes=[
            {
                "id": "1",
                "type": "CheckpointLoaderSimple",
                "title": "Load Checkpoint",
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
            },
            {
                "id": "2",
                "type": "KSampler",
                "title": "KSampler",
                "position": [320, 0],
                "size": [300, 200],
                "mode": 0,
                "flags": {"enabled": True, "bypassed": False, "disabled": False},
                "widgets_values": [12345, "fixed", 20, 8, "euler", "normal", 1],
                "properties": {},
                "inputs": [
                    {"name": "model", "type": "MODEL", "link": 1},
                    {"name": "positive", "type": "CONDITIONING", "link": None},
                    {"name": "seed", "type": "INT", "link": None, "value": 12345},
                ],
                "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                "order": 1,
                "is_unknown": False,
            },
        ],
        links=[
            {
                "id": "1",
                "source_node": "1",
                "source_slot": 0,
                "target_node": "2",
                "target_slot": 0,
                "type": "MODEL",
            }
        ],
        groups=[],
        metadata={"source_format": "ui_json"},
    )


def _make_node_definition(node_class: str, required_inputs: dict | None = None) -> dict:
    """构造节点定义。"""
    return {
        "node_class": node_class,
        "python_module": f"nodes.{node_class}",
        "category": "sampling",
        "display_name": node_class,
        "is_custom_node": False,
        "updated_at": "2026-07-29T00:00:00Z",
        "definition": {
            "input": {
                "required": required_inputs or {},
            },
            "output": ["LATENT"],
            "name": node_class,
        },
    }


# ──────────────────────────────────────────────────────────────────
# 规范化结构 → API JSON
# ──────────────────────────────────────────────────────────────────


class NormalizedToApiJsonTests(unittest.TestCase):
    def test_basic_conversion(self) -> None:
        """基本转换：节点ID作为key，class_type 和 inputs 正确。"""
        wf = _make_simple_workflow()
        api_json = normalized_to_api_json(wf)
        self.assertIsInstance(api_json, dict)
        self.assertIn("1", api_json)
        self.assertIn("2", api_json)
        self.assertEqual(api_json["1"]["class_type"], "CheckpointLoaderSimple")
        self.assertEqual(api_json["2"]["class_type"], "KSampler")

    def test_link_reference_converted(self) -> None:
        """连线转换为 [source_node, source_slot] 格式。"""
        wf = _make_simple_workflow()
        api_json = normalized_to_api_json(wf)
        # 节点2 的 model 输入应引用节点1
        self.assertIn("model", api_json["2"]["inputs"])
        self.assertEqual(api_json["2"]["inputs"]["model"], ["1", 0])

    def test_value_input_preserved(self) -> None:
        """值参数保留原值。"""
        wf = _make_simple_workflow()
        api_json = normalized_to_api_json(wf)
        self.assertEqual(api_json["2"]["inputs"]["seed"], 12345)

    def test_disabled_node_skipped(self) -> None:
        """禁用节点不出现在 API JSON 中。"""
        wf = _make_simple_workflow()
        wf.nodes[0]["flags"]["disabled"] = True
        api_json = normalized_to_api_json(wf)
        self.assertNotIn("1", api_json)

    def test_bypassed_node_skipped(self) -> None:
        """旁路节点不出现在 API JSON 中。"""
        wf = _make_simple_workflow()
        wf.nodes[1]["flags"]["bypassed"] = True
        api_json = normalized_to_api_json(wf)
        self.assertNotIn("2", api_json)
        self.assertIn("1", api_json)


# ──────────────────────────────────────────────────────────────────
# 规范化结构 → UI JSON
# ──────────────────────────────────────────────────────────────────


class NormalizedToUiJsonTests(unittest.TestCase):
    def test_basic_structure(self) -> None:
        """UI JSON 基本结构：last_node_id、last_link_id、nodes、links。"""
        wf = _make_simple_workflow()
        ui_json = normalized_to_ui_json(wf)
        self.assertEqual(ui_json["last_node_id"], 2)
        self.assertEqual(ui_json["last_link_id"], 1)
        self.assertEqual(len(ui_json["nodes"]), 2)
        self.assertEqual(len(ui_json["links"]), 1)

    def test_node_fields_preserved(self) -> None:
        """节点字段正确转换。"""
        wf = _make_simple_workflow()
        ui_json = normalized_to_ui_json(wf)
        node1 = ui_json["nodes"][0]
        self.assertEqual(node1["type"], "CheckpointLoaderSimple")
        self.assertEqual(node1["title"], "Load Checkpoint")
        self.assertEqual(node1["pos"], [0, 0])

    def test_link_format(self) -> None:
        """连线格式为 [id, src, src_slot, tgt, tgt_slot, type]。"""
        wf = _make_simple_workflow()
        ui_json = normalized_to_ui_json(wf)
        link = ui_json["links"][0]
        self.assertEqual(link[0], 1)  # id
        self.assertEqual(link[1], 1)  # source_node
        self.assertEqual(link[2], 0)  # source_slot
        self.assertEqual(link[3], 2)  # target_node
        self.assertEqual(link[4], 0)  # target_slot
        self.assertEqual(link[5], "MODEL")  # type

    def test_disabled_node_mode(self) -> None:
        """禁用节点 mode=2。"""
        wf = _make_simple_workflow()
        wf.nodes[0]["flags"]["disabled"] = True
        ui_json = normalized_to_ui_json(wf)
        self.assertEqual(ui_json["nodes"][0]["mode"], 2)

    def test_bypassed_node_mode(self) -> None:
        """旁路节点 mode=4。"""
        wf = _make_simple_workflow()
        wf.nodes[1]["flags"]["bypassed"] = True
        ui_json = normalized_to_ui_json(wf)
        self.assertEqual(ui_json["nodes"][1]["mode"], 4)

    def test_groups_preserved(self) -> None:
        """分组正确转换。"""
        wf = _make_simple_workflow()
        wf.groups = [
            {
                "title": "测试分组",
                "bounding": [0, 0, 500, 300],
                "color": "#3f789e",
                "font_size": 24,
            }
        ]
        ui_json = normalized_to_ui_json(wf)
        self.assertEqual(len(ui_json["groups"]), 1)
        self.assertEqual(ui_json["groups"][0]["title"], "测试分组")


# ──────────────────────────────────────────────────────────────────
# 导出工作流
# ──────────────────────────────────────────────────────────────────


class ExportWorkflowTests(unittest.TestCase):
    def test_export_api_json_from_normalized(self) -> None:
        """无原始 JSON 时，从规范化结构生成 API JSON。"""
        wf = _make_simple_workflow()
        result = export_workflow(wf, format="api_json")
        self.assertEqual(result["format"], "api_json")
        self.assertIn("1", result["data"])
        self.assertEqual(result["node_count"], 2)
        self.assertTrue(result["checksum"])

    def test_export_ui_json_from_normalized(self) -> None:
        """无原始 JSON 时，从规范化结构生成 UI JSON。"""
        wf = _make_simple_workflow()
        result = export_workflow(wf, format="ui_json")
        self.assertEqual(result["format"], "ui_json")
        self.assertIn("nodes", result["data"])
        self.assertEqual(len(result["data"]["nodes"]), 2)

    def test_export_prefers_raw_api_json(self) -> None:
        """有原始 API JSON 时优先返回。"""
        wf = _make_simple_workflow()
        raw_api = {"999": {"class_type": "RawNode", "inputs": {}}}
        result = export_workflow(wf, format="api_json", raw_api_json=raw_api)
        self.assertIn("999", result["data"])
        self.assertNotIn("1", result["data"])

    def test_export_prefers_raw_ui_json(self) -> None:
        """有原始 UI JSON 时优先返回。"""
        wf = _make_simple_workflow()
        raw_ui = {"nodes": [{"id": 999, "type": "RawNode"}], "links": []}
        result = export_workflow(wf, format="ui_json", raw_ui_json=raw_ui)
        self.assertEqual(len(result["data"]["nodes"]), 1)
        self.assertEqual(result["data"]["nodes"][0]["id"], 999)

    def test_export_unsupported_format_raises(self) -> None:
        """不支持的格式抛出 ValueError。"""
        wf = _make_simple_workflow()
        with self.assertRaises(ValueError):
            export_workflow(wf, format="unknown")


# ──────────────────────────────────────────────────────────────────
# 发布前预检查
# ──────────────────────────────────────────────────────────────────


class PrecheckPublishTests(unittest.TestCase):
    def test_clean_workflow_passes(self) -> None:
        """所有节点都有定义，无错误，可以发布。"""
        wf = _make_simple_workflow()
        definitions = {
            "CheckpointLoaderSimple": _make_node_definition("CheckpointLoaderSimple"),
            "KSampler": _make_node_definition(
                "KSampler",
                required_inputs={
                    "model": ["MODEL"],  # model 已连线
                },
            ),
        }
        result = precheck_publish(wf, definitions)
        self.assertTrue(result["can_publish"])
        self.assertEqual(len(result["blocking_errors"]), 0)

    def test_missing_definition_blocks(self) -> None:
        """缺失节点定义时阻塞发布。"""
        wf = _make_simple_workflow()
        definitions = {"CheckpointLoaderSimple": _make_node_definition("CheckpointLoaderSimple")}
        result = precheck_publish(wf, definitions)
        self.assertFalse(result["can_publish"])
        # KSampler 缺失定义
        missing = [e for e in result["blocking_errors"] if e["type"] == "missing_definition"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["node_type"], "KSampler")

    def test_unknown_node_blocks(self) -> None:
        """未知节点阻塞发布。"""
        wf = _make_simple_workflow()
        wf.nodes[0]["is_unknown"] = True
        definitions = {
            "CheckpointLoaderSimple": _make_node_definition("CheckpointLoaderSimple"),
            "KSampler": _make_node_definition("KSampler"),
        }
        result = precheck_publish(wf, definitions)
        self.assertFalse(result["can_publish"])
        unknown = [e for e in result["blocking_errors"] if e["type"] == "unknown_node"]
        self.assertEqual(len(unknown), 1)

    def test_missing_required_input_blocks(self) -> None:
        """必填输入未连线时阻塞发布。"""
        wf = _make_simple_workflow()
        # 节点2 的 model 输入已连线，但 positive 未连线
        definitions = {
            "CheckpointLoaderSimple": _make_node_definition("CheckpointLoaderSimple"),
            "KSampler": _make_node_definition(
                "KSampler",
                required_inputs={
                    "model": ["MODEL"],
                    "positive": ["CONDITIONING"],  # 这个未连线
                },
            ),
        }
        result = precheck_publish(wf, definitions)
        self.assertFalse(result["can_publish"])
        missing_inputs = [
            e for e in result["blocking_errors"] if e["type"] == "missing_required_input"
        ]
        self.assertEqual(len(missing_inputs), 1)
        self.assertEqual(missing_inputs[0]["input_name"], "positive")

    def test_dangling_link_blocks(self) -> None:
        """悬空连线（源节点不存在）阻塞发布。"""
        wf = _make_simple_workflow()
        wf.links.append(
            {
                "id": "99",
                "source_node": "999",  # 不存在
                "source_slot": 0,
                "target_node": "2",
                "target_slot": 1,
                "type": "CONDITIONING",
            }
        )
        definitions = {
            "CheckpointLoaderSimple": _make_node_definition("CheckpointLoaderSimple"),
            "KSampler": _make_node_definition("KSampler"),
        }
        result = precheck_publish(wf, definitions)
        self.assertFalse(result["can_publish"])
        dangling = [e for e in result["blocking_errors"] if "dangling" in e["type"]]
        self.assertGreaterEqual(len(dangling), 1)

    def test_slot_node_not_found_blocks(self) -> None:
        """语义插槽绑定的节点不存在时阻塞发布。"""
        wf = _make_simple_workflow()
        definitions = {
            "CheckpointLoaderSimple": _make_node_definition("CheckpointLoaderSimple"),
            "KSampler": _make_node_definition("KSampler"),
        }
        slots = [{"slot_name": "正向提示词", "node_id": "999"}]
        result = precheck_publish(wf, definitions, semantic_slots=slots)
        self.assertFalse(result["can_publish"])
        slot_errors = [e for e in result["blocking_errors"] if e["type"] == "slot_node_not_found"]
        self.assertEqual(len(slot_errors), 1)

    def test_summary_counts_correct(self) -> None:
        """summary 统计正确。"""
        wf = _make_simple_workflow()
        definitions = {
            "CheckpointLoaderSimple": _make_node_definition("CheckpointLoaderSimple"),
            "KSampler": _make_node_definition("KSampler"),
        }
        result = precheck_publish(wf, definitions)
        self.assertEqual(result["summary"]["node_count"], 2)
        self.assertEqual(result["summary"]["missing_definitions"], 0)
        self.assertEqual(result["summary"]["dangling_links"], 0)


# ──────────────────────────────────────────────────────────────────
# 往返测试
# ──────────────────────────────────────────────────────────────────


class RoundtripTests(unittest.TestCase):
    def test_ui_json_roundtrip(self) -> None:
        """UI JSON 往返测试：节点数一致。"""
        raw_ui = {
            "nodes": [
                {
                    "id": 1,
                    "type": "CheckpointLoaderSimple",
                    "title": "Load",
                    "pos": [0, 0],
                    "mode": 0,
                    "inputs": [],
                    "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
                    "widgets_values": ["model.safetensors"],
                    "order": 0,
                },
                {
                    "id": 2,
                    "type": "KSampler",
                    "title": "KSampler",
                    "pos": [300, 0],
                    "mode": 0,
                    "inputs": [{"name": "model", "type": "MODEL", "link": 1}],
                    "outputs": [],
                    "widgets_values": [12345],
                    "order": 1,
                },
            ],
            "links": [[1, 1, 0, 2, 0, "MODEL"]],
        }
        result = roundtrip_test(raw_ui, "ui_json")
        self.assertTrue(result["success"], result.get("errors"))
        self.assertEqual(result["original_node_count"], result["roundtrip_node_count"])

    def test_api_json_roundtrip(self) -> None:
        """API JSON 往返测试：节点数一致。"""
        raw_api = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "model": ["1", 0],
                },
            },
        }
        result = roundtrip_test(raw_api, "api_json")
        self.assertTrue(result["success"], result.get("errors"))
        self.assertEqual(result["original_node_count"], result["roundtrip_node_count"])

    def test_invalid_input_returns_failure(self) -> None:
        """无效输入返回失败，不抛出异常。"""
        result = roundtrip_test({}, "ui_json")
        self.assertFalse(result["success"])
        self.assertGreater(len(result["errors"]), 0)

    def test_auto_format_detection(self) -> None:
        """自动格式检测。"""
        raw_api = {
            "1": {
                "class_type": "TestNode",
                "inputs": {"value": 42},
            }
        }
        result = roundtrip_test(raw_api, "auto")
        self.assertTrue(result["success"])


# ──────────────────────────────────────────────────────────────────
# API 集成测试
# ──────────────────────────────────────────────────────────────────


class _PublishApiBase(unittest.TestCase):
    """API 集成测试基类。"""

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

    def _create_workflow(self, name: str = "测试工作流") -> str:
        response = self.client.post("/api/workflows", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["workflow"]["id"]

    def _save_draft(self, workflow_id: str, normalized: NormalizedWorkflow) -> dict:
        payload = {
            "normalized_graph": json.dumps(normalized.to_dict(), ensure_ascii=False),
            "raw_ui_json": None,
            "raw_api_json": None,
            "node_count": normalized.node_count(),
        }
        response = self.client.put(f"/api/workflows/{workflow_id}/draft", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["draft"]

    def _seed_node_definitions(self, node_classes: list[str]) -> None:
        """批量写入节点定义（全量替换）。"""
        definitions = {cls: _make_node_definition(cls) for cls in node_classes}
        self.manager.save_node_definitions(definitions)


class ExportApiTests(_PublishApiBase):
    def test_export_api_json(self) -> None:
        """通过 API 导出 API JSON。"""
        workflow_id = self._create_workflow()
        wf = _make_simple_workflow()
        self._save_draft(workflow_id, wf)
        response = self.client.post(
            f"/api/workflows/{workflow_id}/export",
            json={"format": "api_json"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["format"], "api_json")
        self.assertIn("1", data["data"])
        self.assertIn("2", data["data"])

    def test_export_ui_json(self) -> None:
        """通过 API 导出 UI JSON。"""
        workflow_id = self._create_workflow()
        wf = _make_simple_workflow()
        self._save_draft(workflow_id, wf)
        response = self.client.post(
            f"/api/workflows/{workflow_id}/export",
            json={"format": "ui_json"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["format"], "ui_json")
        self.assertIn("nodes", data["data"])

    def test_export_nonexistent_draft_404(self) -> None:
        """草稿不存在时返回 404。"""
        workflow_id = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{workflow_id}/export",
            json={"format": "api_json"},
        )
        self.assertEqual(response.status_code, 404)

    def test_export_invalid_format_422(self) -> None:
        """不支持的格式返回 422。"""
        workflow_id = self._create_workflow()
        wf = _make_simple_workflow()
        self._save_draft(workflow_id, wf)
        response = self.client.post(
            f"/api/workflows/{workflow_id}/export",
            json={"format": "invalid"},
        )
        self.assertEqual(response.status_code, 422)


class PrecheckApiTests(_PublishApiBase):
    def test_precheck_passes(self) -> None:
        """预检查通过。"""
        workflow_id = self._create_workflow()
        wf = _make_simple_workflow()
        self._save_draft(workflow_id, wf)
        self._seed_node_definitions(["CheckpointLoaderSimple", "KSampler"])
        response = self.client.post(f"/api/workflows/{workflow_id}/precheck")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["can_publish"])

    def test_precheck_blocks_missing_definition(self) -> None:
        """缺失节点定义时预检查阻塞。"""
        workflow_id = self._create_workflow()
        wf = _make_simple_workflow()
        self._save_draft(workflow_id, wf)
        # 只播种一个节点定义
        self._seed_node_definitions(["CheckpointLoaderSimple"])
        response = self.client.post(f"/api/workflows/{workflow_id}/precheck")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertFalse(data["can_publish"])
        self.assertGreater(len(data["blocking_errors"]), 0)

    def test_precheck_nonexistent_draft_404(self) -> None:
        """草稿不存在时返回 404。"""
        workflow_id = self._create_workflow()
        response = self.client.post(f"/api/workflows/{workflow_id}/precheck")
        self.assertEqual(response.status_code, 404)


class PublishApiTests(_PublishApiBase):
    def test_publish_from_draft(self) -> None:
        """基于草稿发布版本。"""
        workflow_id = self._create_workflow()
        wf = _make_simple_workflow()
        self._save_draft(workflow_id, wf)
        response = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v1.0", "normalized_graph": ""},
        )
        self.assertEqual(response.status_code, 200, response.text)
        version = response.json()["version"]
        self.assertEqual(version["version_number"], 1)
        self.assertEqual(version["label"], "v1.0")

    def test_publish_creates_increasing_version_numbers(self) -> None:
        """多次发布版本号递增。"""
        workflow_id = self._create_workflow()
        wf = _make_simple_workflow()
        self._save_draft(workflow_id, wf)
        # 第一次发布
        r1 = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v1", "normalized_graph": ""},
        )
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertEqual(r1.json()["version"]["version_number"], 1)
        # 第二次发布
        r2 = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v2", "normalized_graph": ""},
        )
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r2.json()["version"]["version_number"], 2)

    def test_publish_nonexistent_draft_404(self) -> None:
        """草稿不存在时返回 404。"""
        workflow_id = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v1", "normalized_graph": ""},
        )
        self.assertEqual(response.status_code, 404)


class RoundtripApiTests(_PublishApiBase):
    def test_roundtrip_via_api(self) -> None:
        """通过 API 执行往返测试。"""
        raw_api = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "model": ["1", 0],
                },
            },
        }
        response = self.client.post(
            "/api/workflows/roundtrip-test",
            json={"workflow": raw_api, "source_format": "api_json"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["original_node_count"], data["roundtrip_node_count"])


# ──────────────────────────────────────────────────────────────────
# 编辑后导出测试（需求 §5.5）
# ──────────────────────────────────────────────────────────────────


def _make_simple_ui_json() -> dict:
    """构造简单 UI JSON 用于导入测试。"""
    return {
        "last_node_id": 2,
        "last_link_id": 1,
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "title": "Load Checkpoint",
                "pos": [0, 0],
                "size": {"0": 240, "1": 100},
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [],
                "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
                "widgets_values": ["old_model.safetensors"],
                "properties": {},
            },
            {
                "id": 2,
                "type": "KSampler",
                "title": "KSampler",
                "pos": [320, 0],
                "size": {"0": 300, "1": 200},
                "flags": {},
                "order": 1,
                "mode": 0,
                "inputs": [{"name": "model", "type": "MODEL", "link": 1}],
                "outputs": [],
                "widgets_values": [12345, "fixed", 20, 8, "euler", "normal", 1],
                "properties": {},
            },
        ],
        "links": [[1, 1, 0, 2, 0, "MODEL"]],
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }


def _make_simple_api_json() -> dict:
    """构造简单 API JSON 用于导入测试。"""
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "old_model.safetensors"},
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 12345,
                "model": ["1", 0],
            },
        },
    }


class ExportAfterEditTests(_PublishApiBase):
    """需求 §5.5：编辑后导出测试。

    覆盖：
    1. 导入 UI JSON 后不编辑，原样往返
    2. 修改节点组件值后，UI JSON 导出为新值
    3. 修改节点组件值后，API JSON 导出为新值
    4. 新增节点后，导出包含新节点
    5. 删除节点后，导出不再包含该节点
    6. 新增、替换和删除连线后，导出反映当前连线
    7. 分组和布局调整后，UI JSON 反映当前结构
    8. 未知顶层字段在编辑后仍保留
    9. 未知节点原始字段在允许的编辑范围内不丢失
    10. 发布版本保存当前草稿，而不是来源旧 JSON
    11. 编辑后导出并重新导入，节点、连线和组件值一致
    """

    def _import_ui_json(self, workflow_id: str, raw_json: dict | None = None) -> dict:
        """导入 UI JSON 到草稿，返回响应。"""
        raw_json = raw_json or _make_simple_ui_json()
        response = self.client.post(
            f"/api/workflows/{workflow_id}/import",
            json={"raw_json": raw_json, "source_format": "ui_json"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _import_api_json(self, workflow_id: str, raw_json: dict | None = None) -> dict:
        """导入 API JSON 到草稿，返回响应。"""
        raw_json = raw_json or _make_simple_api_json()
        response = self.client.post(
            f"/api/workflows/{workflow_id}/import",
            json={"raw_json": raw_json, "source_format": "api_json"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def _export(self, workflow_id: str, fmt: str = "ui_json") -> dict:
        """导出工作流，返回响应 JSON。"""
        response = self.client.post(
            f"/api/workflows/{workflow_id}/export",
            json={"format": fmt},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    # ── 1. 导入 UI JSON 后不编辑，原样往返 ──

    def test_import_without_edit_returns_raw_ui_json(self) -> None:
        """导入 UI JSON 后不编辑，导出原样返回来源快照。"""
        workflow_id = self._create_workflow("未编辑工作流")
        raw = _make_simple_ui_json()
        self._import_ui_json(workflow_id, raw)
        result = self._export(workflow_id, "ui_json")
        self.assertFalse(result["is_dirty"])
        # 未编辑时应原样返回来源 JSON（包含 last_node_id 等顶层字段）
        self.assertEqual(result["data"]["last_node_id"], 2)
        self.assertEqual(len(result["data"]["nodes"]), 2)

    # ── 2. 修改节点组件值后，UI JSON 导出为新值 ──

    def test_edit_widget_value_then_export_ui_json(self) -> None:
        """修改节点组件值后，UI JSON 导出新值，不是旧来源。"""
        workflow_id = self._create_workflow("编辑组件值")
        self._import_ui_json(workflow_id)
        # 修改节点1的 widgets_values
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["new_model.safetensors"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 导出 UI JSON
        result = self._export(workflow_id, "ui_json")
        self.assertTrue(result["is_dirty"])
        # 找到节点1，检查 widgets_values
        node1 = next(n for n in result["data"]["nodes"] if n["id"] == 1)
        self.assertIn("new_model.safetensors", node1["widgets_values"])
        self.assertNotIn("old_model.safetensors", node1["widgets_values"])

    # ── 3. 修改节点组件值后，API JSON 导出为新值 ──

    def test_edit_widget_value_then_export_api_json(self) -> None:
        """修改节点组件值后，API JSON 导出新值。"""
        workflow_id = self._create_workflow("编辑组件值API")
        self._import_api_json(workflow_id)
        # 修改节点1的 widgets_values
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["new_model.safetensors"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 导出 API JSON
        result = self._export(workflow_id, "api_json")
        self.assertTrue(result["is_dirty"])
        self.assertEqual(result["data"]["1"]["inputs"]["ckpt_name"], "new_model.safetensors")

    # ── 4. 新增节点后，导出包含新节点 ──

    def test_add_node_then_export_contains_new_node(self) -> None:
        """新增节点后，导出包含新节点。"""
        workflow_id = self._create_workflow("新增节点")
        self._import_ui_json(workflow_id)
        # 播种节点定义
        self._seed_node_definitions(["CLIPTextEncode"])
        # 新增节点
        response = self.client.post(
            f"/api/workflows/{workflow_id}/draft/nodes",
            json={"node_class": "CLIPTextEncode", "position_x": 100, "position_y": 200},
        )
        self.assertEqual(response.status_code, 200, response.text)
        new_node_id = response.json()["node"]["id"]
        # 导出
        result = self._export(workflow_id, "ui_json")
        self.assertTrue(result["is_dirty"])
        node_ids = [n["id"] for n in result["data"]["nodes"]]
        self.assertIn(int(new_node_id), [int(nid) for nid in node_ids])

    # ── 5. 删除节点后，导出不再包含该节点 ──

    def test_delete_node_then_export_excludes_node(self) -> None:
        """删除节点后，导出不再包含该节点。"""
        workflow_id = self._create_workflow("删除节点")
        self._import_ui_json(workflow_id)
        # 删除节点2
        response = self.client.delete(f"/api/workflows/{workflow_id}/draft/nodes/2")
        self.assertEqual(response.status_code, 200, response.text)
        # 导出
        result = self._export(workflow_id, "ui_json")
        self.assertTrue(result["is_dirty"])
        node_ids = [int(n["id"]) for n in result["data"]["nodes"]]
        self.assertNotIn(2, node_ids)
        self.assertIn(1, node_ids)

    # ── 6. 新增、替换和删除连线后，导出反映当前连线 ──

    def test_link_operations_reflected_in_export(self) -> None:
        """新增、替换和删除连线后，导出反映当前连线。"""
        workflow_id = self._create_workflow("连线操作")
        self._import_ui_json(workflow_id)
        # 删除现有连线 1
        response = self.client.delete(f"/api/workflows/{workflow_id}/draft/links/1")
        self.assertEqual(response.status_code, 200, response.text)
        # 导出检查连线已删除
        result = self._export(workflow_id, "ui_json")
        self.assertTrue(result["is_dirty"])
        self.assertEqual(len(result["data"]["links"]), 0)
        # 重新创建连线
        response = self.client.post(
            f"/api/workflows/{workflow_id}/draft/links",
            json={"source_node": "1", "source_slot": 0, "target_node": "2", "target_slot": 0},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 导出检查连线已重建
        result = self._export(workflow_id, "ui_json")
        self.assertEqual(len(result["data"]["links"]), 1)

    # ── 7. 分组和布局调整后，UI JSON 反映当前结构 ──

    def test_group_and_layout_reflected_in_export(self) -> None:
        """分组和布局调整后，UI JSON 反映当前结构。"""
        workflow_id = self._create_workflow("分组布局")
        self._import_ui_json(workflow_id)
        # 创建分组
        response = self.client.post(
            f"/api/workflows/{workflow_id}/draft/groups",
            json={"title": "测试分组", "color": "#3f789e", "members": ["1", "2"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 计算布局
        response = self.client.post(f"/api/workflows/{workflow_id}/draft/layout/compute")
        self.assertEqual(response.status_code, 200, response.text)
        # 导出 UI JSON
        result = self._export(workflow_id, "ui_json")
        self.assertTrue(result["is_dirty"])
        # 导出的节点位置应该有值（布局已应用）
        for node in result["data"]["nodes"]:
            self.assertIsInstance(node["pos"], list)
            self.assertEqual(len(node["pos"]), 2)

    # ── 8. 未知顶层字段在编辑后仍保留 ──

    def test_unknown_top_level_fields_preserved_after_edit(self) -> None:
        """未知顶层字段在编辑后仍保留。"""
        workflow_id = self._create_workflow("未知字段保留")
        raw = _make_simple_ui_json()
        raw["custom_top_field"] = "保留我"
        raw["another_unknown"] = {"nested": True}
        self._import_ui_json(workflow_id, raw)
        # 编辑节点
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["new_model.safetensors"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 导出
        result = self._export(workflow_id, "ui_json")
        self.assertTrue(result["is_dirty"])
        # 未知顶层字段应保留
        self.assertEqual(result["data"]["custom_top_field"], "保留我")
        self.assertEqual(result["data"]["another_unknown"]["nested"], True)

    # ── 9. 未知节点原始字段在允许的编辑范围内不丢失 ──

    def test_unknown_node_raw_fields_preserved(self) -> None:
        """未知节点的原始字段在编辑范围内不丢失。"""
        workflow_id = self._create_workflow("未知节点保留")
        raw = _make_simple_ui_json()
        # 添加一个带未知字段的节点
        raw["nodes"].append({
            "id": 99,
            "type": "UnknownCustomNode",
            "title": "未知节点",
            "pos": [500, 0],
            "size": {"0": 200, "1": 100},
            "flags": {},
            "order": 2,
            "mode": 0,
            "inputs": [],
            "outputs": [],
            "widgets_values": ["custom_value"],
            "properties": {"custom_prop": "保留"},
            "unknown_field": "should_be_preserved",
        })
        raw["last_node_id"] = 99
        self._import_ui_json(workflow_id, raw)
        # 编辑另一个节点（不编辑未知节点）
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["new_model.safetensors"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 导出
        result = self._export(workflow_id, "ui_json")
        self.assertTrue(result["is_dirty"])
        # 未知节点应保留
        node99 = next((n for n in result["data"]["nodes"] if int(n["id"]) == 99), None)
        self.assertIsNotNone(node99)
        self.assertEqual(node99["type"], "UnknownCustomNode")

    # ── 10. 发布版本保存当前草稿，而不是来源旧 JSON ──

    def test_publish_saves_current_draft_not_source_json(self) -> None:
        """发布版本保存当前草稿，而不是来源旧 JSON。"""
        workflow_id = self._create_workflow("发布版本")
        self._import_ui_json(workflow_id)
        # 编辑节点
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["published_model.safetensors"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 发布版本
        response = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v1.0", "normalized_graph": ""},
        )
        self.assertEqual(response.status_code, 200, response.text)
        version = response.json()["version"]
        # 获取版本详情
        response = self.client.get(f"/api/workflow-versions/{version['id']}")
        self.assertEqual(response.status_code, 200, response.text)
        version_detail = response.json()["version"]
        # 版本的 normalized_graph 应包含新值
        normalized_data = json.loads(version_detail["normalized_graph"])
        node1 = next(n for n in normalized_data["nodes"] if str(n["id"]) == "1")
        self.assertIn("published_model.safetensors", node1["widgets_values"])
        # 已编辑时，raw_ui_json 应为空（不发布来源旧 JSON）
        self.assertFalse(version_detail.get("raw_ui_json"))

    # ── 11. 编辑后导出并重新导入，节点、连线和组件值一致 ──

    def test_edit_then_export_and_reimport_consistent(self) -> None:
        """编辑后导出并重新导入，节点、连线和组件值一致。"""
        workflow_id = self._create_workflow("往返一致性")
        self._import_ui_json(workflow_id)
        # 编辑节点1的组件值
        self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["reimported_model.safetensors"]},
        )
        # 导出 UI JSON
        export_result = self._export(workflow_id, "ui_json")
        self.assertTrue(export_result["is_dirty"])
        exported_data = export_result["data"]
        # 创建新工作流并导入导出的 JSON
        workflow_id2 = self._create_workflow("往返目标")
        response = self.client.post(
            f"/api/workflows/{workflow_id2}/import",
            json={"raw_json": exported_data, "source_format": "ui_json"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 导出新工作流
        result2 = self._export(workflow_id2, "ui_json")
        reimported_data = result2["data"]
        # 节点数一致
        self.assertEqual(len(exported_data["nodes"]), len(reimported_data["nodes"]))
        # 连线数一致
        self.assertEqual(len(exported_data["links"]), len(reimported_data["links"]))
        # 节点1的组件值一致
        node1_exported = next(n for n in exported_data["nodes"] if int(n["id"]) == 1)
        node1_reimported = next(n for n in reimported_data["nodes"] if int(n["id"]) == 1)
        self.assertEqual(
            node1_exported["widgets_values"],
            node1_reimported["widgets_values"],
        )

    # ── 额外：并发控制测试 ──

    def test_expected_revision_mismatch_returns_409(self) -> None:
        """草稿修订号不匹配时返回 409。"""
        workflow_id = self._create_workflow("并发控制")
        self._import_ui_json(workflow_id)
        # 获取当前修订号
        draft = self.client.get(f"/api/workflows/{workflow_id}/draft").json()["draft"]
        current_revision = int(draft["draft_revision"])
        # 使用错误的 expected_revision
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft",
            json={
                "normalized_graph": draft["normalized_graph"],
                "node_count": draft["node_count"],
                "expected_revision": current_revision + 999,
            },
        )
        self.assertEqual(response.status_code, 409)

    def test_expected_revision_match_succeeds(self) -> None:
        """草稿修订号匹配时保存成功。"""
        workflow_id = self._create_workflow("并发控制成功")
        self._import_ui_json(workflow_id)
        draft = self.client.get(f"/api/workflows/{workflow_id}/draft").json()["draft"]
        current_revision = int(draft["draft_revision"])
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft",
            json={
                "normalized_graph": draft["normalized_graph"],
                "node_count": draft["node_count"],
                "expected_revision": current_revision,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_edit_increments_draft_revision(self) -> None:
        """编辑操作递增 draft_revision。"""
        workflow_id = self._create_workflow("修订号递增")
        self._import_ui_json(workflow_id)
        # 导入后修订号为 0
        draft = self.client.get(f"/api/workflows/{workflow_id}/draft").json()["draft"]
        self.assertEqual(int(draft["draft_revision"]), 0)
        self.assertFalse(draft["is_dirty"])
        # 编辑节点
        self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["new_value"]},
        )
        draft = self.client.get(f"/api/workflows/{workflow_id}/draft").json()["draft"]
        self.assertEqual(int(draft["draft_revision"]), 1)
        self.assertTrue(draft["is_dirty"])
        # 再次编辑
        self.client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/1",
            json={"widgets_values": ["newer_value"]},
        )
        draft = self.client.get(f"/api/workflows/{workflow_id}/draft").json()["draft"]
        self.assertEqual(int(draft["draft_revision"]), 2)


if __name__ == "__main__":
    unittest.main()
