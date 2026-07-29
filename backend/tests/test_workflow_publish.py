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


if __name__ == "__main__":
    unittest.main()
