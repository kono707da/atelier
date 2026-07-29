"""阶段 2.3 通用节点编辑器测试。

测试范围：
- 节点定义批量查询
- 草稿节点 CRUD（添加/更新/删除/复制）
- 草稿连线管理（创建/删除/端口类型校验）
- 草稿校验（未知节点/缺失定义/必填输入/悬空连线/重复连线）
- 未知节点只读保留
- 节点标志（禁用/旁路/折叠）
- ID 分配工具
- 端口兼容性判断
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.workflow_models import (
    NormalizedWorkflow,
    allocate_link_id,
    allocate_node_id,
    are_ports_compatible,
    build_default_node,
    validate_workflow,
)


def _make_node_definition(
    node_class: str,
    *,
    is_custom: bool = False,
    output_type: str = "LATENT",
    output_name: str = "LATENT",
) -> dict:
    """构造 ComfyUI 节点定义（用于测试缓存）。"""
    return {
        "node_class": node_class,
        "python_module": "nodes" if not is_custom else "custom_nodes.test",
        "category": "sampling" if not is_custom else "custom",
        "display_name": node_class,
        "is_custom_node": is_custom,
        "definition": {
            "input": {
                "required": {
                    "model": ["MODEL"],
                    "positive": ["CONDITIONING"],
                    "seed": ["INT", {"default": 0}],
                },
                "optional": {
                    "negative": ["CONDITIONING"],
                },
            },
            "output": [output_type],
            "output_name": [output_name],
        },
    }


class _EditorBase(unittest.TestCase):
    """节点编辑器测试基类。"""

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

    def _create_workflow(self, name: str = "编辑器测试工作流") -> dict:
        response = self.client.post("/api/workflows", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["workflow"]

    def _seed_node_definition(
        self,
        node_class: str,
        *,
        is_custom: bool = False,
        output_type: str = "LATENT",
        output_name: str = "LATENT",
    ) -> dict:
        """单节点便捷播种，注意会清空现有节点定义。"""
        return self._seed_node_definitions([(node_class, {
            "is_custom": is_custom, "output_type": output_type, "output_name": output_name,
        })])

    def _seed_node_definitions(self, specs: list[tuple[str, dict]]) -> dict:
        """一次保存多个节点定义，避免全量替换语义清空之前的节点。

        specs: [(node_class, {is_custom, output_type, output_name})]
        """
        definitions: dict[str, dict] = {}
        result: dict[str, dict] = {}
        for node_class, opts in specs:
            definition = _make_node_definition(
                node_class,
                is_custom=opts.get("is_custom", False),
                output_type=opts.get("output_type", "LATENT"),
                output_name=opts.get("output_name", "LATENT"),
            )
            result[node_class] = definition
            definitions[node_class] = {
                "python_module": definition["python_module"],
                "category": definition["category"],
                "display_name": definition["display_name"],
                "input": definition["definition"]["input"],
                "output": definition["definition"]["output"],
                "output_name": definition["definition"]["output_name"],
            }
        self.manager.save_node_definitions(definitions)
        return result

    def _import_sample_draft(self, workflow_id: str) -> dict:
        """导入一个最小工作流到草稿，便于后续编辑。"""
        ui_json = {
            "nodes": [
                {
                    "id": 1,
                    "type": "CheckpointLoaderSimple",
                    "title": "Load Checkpoint",
                    "pos": [100, 200],
                    "size": [300, 100],
                    "mode": 0,
                    "inputs": [],
                    "outputs": [
                        {"name": "MODEL", "type": "MODEL", "links": [1]},
                    ],
                    "widgets_values": ["model.safetensors"],
                    "properties": {},
                    "order": 0,
                },
                {
                    "id": 2,
                    "type": "KSampler",
                    "title": "KSampler",
                    "pos": [500, 200],
                    "size": [300, 200],
                    "mode": 0,
                    "inputs": [
                        {"name": "model", "type": "MODEL", "link": 1},
                    ],
                    "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                    "widgets_values": [12345, "fixed", 20, 8, "euler", "normal", 1],
                    "properties": {},
                    "order": 1,
                },
            ],
            "links": [
                [1, 1, 0, 2, 0, "MODEL"],
            ],
        }
        response = self.client.post(
            f"/api/workflows/{workflow_id}/import",
            json={"source_format": "ui_json", "raw_json": ui_json},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["draft"]


# ── 1. 节点定义批量查询 ─────────────────────────────────────────


class NodeDefinitionBatchTests(_EditorBase):
    def test_batch_get_node_definitions_api(self) -> None:
        self._seed_node_definitions([
            ("KSampler", {}),
            ("CheckpointLoaderSimple", {"is_custom": True}),
        ])
        response = self.client.post(
            "/api/comfyui/node-definitions/batch",
            json={"node_classes": ["KSampler", "CheckpointLoaderSimple", "NotExist"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["found_count"], 2)
        self.assertIn("KSampler", data["definitions"])
        self.assertIn("CheckpointLoaderSimple", data["definitions"])
        self.assertIn("NotExist", data["missing_classes"])

    def test_batch_get_workflow_node_definitions(self) -> None:
        self._seed_node_definitions([
            ("KSampler", {}),
            ("CheckpointLoaderSimple", {}),
        ])
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.get(f"/api/workflows/{wf['id']}/node-definitions")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["found_count"], 2)
        self.assertEqual(data["missing_classes"], [])

    def test_batch_get_empty_classes(self) -> None:
        response = self.client.post(
            "/api/comfyui/node-definitions/batch",
            json={"node_classes": []},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["found_count"], 0)


# ── 2. 节点 CRUD ────────────────────────────────────────────────


class NodeCrudTests(_EditorBase):
    def test_add_node_to_draft(self) -> None:
        self._seed_node_definition("KSampler")
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes",
            json={"node_class": "KSampler", "position_x": 800, "position_y": 200},
        )
        self.assertEqual(response.status_code, 200, response.text)
        node = response.json()["node"]
        self.assertEqual(node["type"], "KSampler")
        self.assertEqual(node["id"], "3")  # 已有 1,2，新节点 ID=3
        self.assertEqual(node["position"], [800, 200])
        # 节点应有默认输入和输出
        self.assertTrue(any(i["name"] == "model" for i in node["inputs"]))

    def test_add_node_missing_definition_returns_404(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes",
            json={"node_class": "MissingNode"},
        )
        self.assertEqual(response.status_code, 404)

    def test_update_node_widgets(self) -> None:
        self._seed_node_definition("KSampler")
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/2",
            json={"widgets_values": [99999, "karras", 30, 7.5, "dpmpp_2m", "normal", 1]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        node = response.json()["node"]
        self.assertEqual(node["widgets_values"][0], 99999)
        self.assertEqual(node["widgets_values"][2], 30)

    def test_update_node_flags(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/2",
            json={"flags": {"disabled": True, "collapsed": True}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        node = response.json()["node"]
        self.assertTrue(node["flags"]["disabled"])
        self.assertTrue(node["flags"]["collapsed"])

    def test_update_node_title(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/2",
            json={"title": "采样器（重命名）"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["node"]["title"], "采样器（重命名）")

    def test_update_unknown_node_rejected(self) -> None:
        """未知节点为只读，不能编辑。"""
        wf = self._create_workflow()
        # 先写入一个空草稿
        empty = {"nodes": [], "links": []}
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(empty, ensure_ascii=False), "node_count": 0},
        )
        draft = self.client.get(f"/api/workflows/{wf['id']}/draft").json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        normalized["nodes"].append({
            "id": "99",
            "type": "MissingNode",
            "title": "未知节点",
            "position": [0, 0],
            "size": [200, 100],
            "mode": 0,
            "flags": {},
            "widgets_values": [],
            "properties": {},
            "inputs": [],
            "outputs": [],
            "order": -1,
            "is_unknown": True,
            "raw": {"class_type": "MissingNode", "inputs": {}},
        })
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": len(normalized["nodes"])},
        )
        # 尝试更新应被拒绝
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/99",
            json={"title": "新标题"},
        )
        self.assertEqual(response.status_code, 422)

    def test_update_nonexistent_node_returns_404(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/999",
            json={"title": "新标题"},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_node_cascades_links(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        # 删除节点 2（KSampler，是 link 1 的目标）
        response = self.client.delete(f"/api/workflows/{wf['id']}/draft/nodes/2")
        self.assertEqual(response.status_code, 200, response.text)
        removed = response.json()["removed_links"]
        self.assertIn("1", removed)
        # 草稿应只剩节点 1
        draft = self.client.get(f"/api/workflows/{wf['id']}/draft").json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        self.assertEqual(len(normalized["nodes"]), 1)
        self.assertEqual(len(normalized["links"]), 0)
        # 节点 1 上的 link 引用应被清理
        self.assertEqual(normalized["nodes"][0]["outputs"][0]["links"], [])

    def test_delete_nonexistent_node_returns_404(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.delete(f"/api/workflows/{wf['id']}/draft/nodes/999")
        self.assertEqual(response.status_code, 404)

    def test_duplicate_node(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/2/duplicate",
        )
        self.assertEqual(response.status_code, 200, response.text)
        node = response.json()["node"]
        self.assertEqual(node["id"], "3")
        self.assertIn("copy", node["title"])
        # 新节点不应携带连线
        for inp in node["inputs"]:
            self.assertIsNone(inp["link"])

    def test_duplicate_nonexistent_returns_404(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/999/duplicate",
        )
        self.assertEqual(response.status_code, 404)


# ── 3. 连线管理 ─────────────────────────────────────────────────


class LinkManagementTests(_EditorBase):
    def test_create_link(self) -> None:
        self._seed_node_definition("KSampler")
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        # 先添加第三个节点（KSampler），然后从节点 1 的输出端口 0 连到新节点的输入端口 0
        add_resp = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes",
            json={"node_class": "KSampler", "position_x": 800, "position_y": 400},
        )
        new_node_id = add_resp.json()["node"]["id"]
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/links",
            json={
                "source_node": "1",
                "source_slot": 0,
                "target_node": new_node_id,
                "target_slot": 0,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        link = response.json()["link"]
        self.assertEqual(link["source_node"], "1")
        self.assertEqual(link["target_node"], new_node_id)

    def test_create_link_replaces_existing(self) -> None:
        """一个输入端口只能连一根线，新连线应替换旧连线。"""
        self._seed_node_definitions([
            ("KSampler", {}),
            ("CheckpointLoaderSimple", {"output_type": "MODEL", "output_name": "MODEL"}),
        ])
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        # 添加两个 CheckpointLoaderSimple 节点（都输出 MODEL）
        add1 = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes",
            json={"node_class": "CheckpointLoaderSimple", "position_x": 800, "position_y": 100},
        )
        add2 = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes",
            json={"node_class": "CheckpointLoaderSimple", "position_x": 800, "position_y": 300},
        )
        node_a = add1.json()["node"]["id"]
        node_b = add2.json()["node"]["id"]
        # 先断开节点 2 现有的 model 输入连线（link 1）
        self.client.delete(f"/api/workflows/{wf['id']}/draft/links/1")
        # 第一次连接 node_a:0 → 节点2:0
        r1 = self.client.post(
            f"/api/workflows/{wf['id']}/draft/links",
            json={"source_node": node_a, "source_slot": 0, "target_node": "2", "target_slot": 0},
        )
        self.assertEqual(r1.status_code, 200)
        old_link_id = r1.json()["link"]["id"]
        # 第二次连接 node_b:0 → 节点2:0，应替换 old_link
        r2 = self.client.post(
            f"/api/workflows/{wf['id']}/draft/links",
            json={"source_node": node_b, "source_slot": 0, "target_node": "2", "target_slot": 0},
        )
        self.assertEqual(r2.status_code, 200)
        self.assertIn(old_link_id, r2.json()["removed_links"])
        # 草稿中应只剩一条连接到节点 2 输入端口 0 的线
        draft = self.client.get(f"/api/workflows/{wf['id']}/draft").json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        target_links = [
            link for link in normalized["links"]
            if str(link.get("target_node", "")) == "2" and int(link.get("target_slot", -1)) == 0
        ]
        self.assertEqual(len(target_links), 1)
        self.assertEqual(target_links[0]["source_node"], node_b)

    def test_create_link_type_mismatch_returns_422(self) -> None:
        """端口类型不兼容应返回 422。"""
        # 用一个 LATENT 输出节点连到 MODEL 输入节点
        # 在 _sample_ui_json 中节点 1 输出 MODEL，节点 2 输入 MODEL
        # 改造：让节点 1 的输出 0 类型变成 LATENT，然后连 1:0 → 2:0(MODEL)
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        # 直接通过 PUT 草稿改节点 1 的输出类型为 LATENT
        draft = self.client.get(f"/api/workflows/{wf['id']}/draft").json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        # 节点 2 的输入端口 0 是 MODEL 类型
        # 节点 1 的输出端口 0 是 MODEL 类型
        # 改节点 1 输出为 LATENT
        for node in normalized["nodes"]:
            if node["id"] == "1":
                node["outputs"][0]["type"] = "LATENT"
        # 先删除现有连线
        normalized["links"] = []
        for node in normalized["nodes"]:
            for inp in node.get("inputs", []):
                inp["link"] = None
            for out in node.get("outputs", []):
                out["links"] = []
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 2},
        )
        # 现在连 1:0(LATENT) → 2:0(MODEL) 应失败
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/links",
            json={"source_node": "1", "source_slot": 0, "target_node": "2", "target_slot": 0},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("端口类型不兼容", response.json()["detail"])

    def test_create_link_invalid_source_port_returns_422(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/links",
            json={"source_node": "1", "source_slot": 99, "target_node": "2", "target_slot": 0},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_link_unknown_node_rejected(self) -> None:
        wf = self._create_workflow()
        # 先写入一个空草稿
        empty = {"nodes": [], "links": []}
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(empty, ensure_ascii=False), "node_count": 0},
        )
        draft = self.client.get(f"/api/workflows/{wf['id']}/draft").json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        normalized["nodes"] = [
            {"id": "1", "type": "A", "title": "A", "position": [0, 0], "size": [100, 100], "mode": 0,
             "flags": {}, "widgets_values": [], "properties": {}, "inputs": [],
             "outputs": [{"name": "out", "type": "MODEL", "links": []}], "order": 0, "is_unknown": False},
            {"id": "2", "type": "UnknownNode", "title": "未知", "position": [200, 0], "size": [100, 100], "mode": 0,
             "flags": {}, "widgets_values": [], "properties": {},
             "inputs": [{"name": "in", "type": "MODEL", "link": None}],
             "outputs": [], "order": 1, "is_unknown": True, "raw": {}},
        ]
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 2},
        )
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/links",
            json={"source_node": "1", "source_slot": 0, "target_node": "2", "target_slot": 0},
        )
        self.assertEqual(response.status_code, 422)

    def test_delete_link(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        # 草稿中已有 link 1
        response = self.client.delete(f"/api/workflows/{wf['id']}/draft/links/1")
        self.assertEqual(response.status_code, 200, response.text)
        # 验证连线已删除
        draft = self.client.get(f"/api/workflows/{wf['id']}/draft").json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        self.assertEqual(len(normalized["links"]), 0)
        # 节点 2 的输入端口 link 应被清理
        for node in normalized["nodes"]:
            if node["id"] == "2":
                self.assertIsNone(node["inputs"][0]["link"])
            if node["id"] == "1":
                self.assertEqual(node["outputs"][0]["links"], [])

    def test_delete_nonexistent_link_returns_404(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.delete(f"/api/workflows/{wf['id']}/draft/links/999")
        self.assertEqual(response.status_code, 404)


# ── 4. 草稿校验 ─────────────────────────────────────────────────


class DraftValidationTests(_EditorBase):
    def test_validate_clean_draft(self) -> None:
        """节点定义齐全、必填输入已连线的草稿应通过校验。"""
        self._seed_node_definitions([
            ("CheckpointLoaderSimple", {}),
            ("KSampler", {}),
        ])
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/validate")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["validation"]
        # 至少不应有 unknown_node 或 missing_definition 错误
        error_types = [e["error_type"] for e in result["errors"]]
        self.assertNotIn("unknown_node", error_types)
        self.assertNotIn("missing_definition", error_types)
        self.assertEqual(result["stats"]["node_count"], 2)
        self.assertEqual(result["stats"]["link_count"], 1)

    def test_validate_unknown_node(self) -> None:
        """草稿中有未知节点应报错。"""
        wf = self._create_workflow()
        # 直接写一个未知节点到草稿
        normalized = {
            "nodes": [{
                "id": "1", "type": "MissingNode", "title": "未知",
                "position": [0, 0], "size": [100, 100], "mode": 0,
                "flags": {}, "widgets_values": [], "properties": {},
                "inputs": [], "outputs": [], "order": 0,
                "is_unknown": True, "raw": {},
            }],
            "links": [],
        }
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 1},
        )
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/validate")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["validation"]
        self.assertFalse(result["is_valid"])
        error_types = [e["error_type"] for e in result["errors"]]
        self.assertIn("unknown_node", error_types)
        self.assertEqual(result["stats"]["unknown_count"], 1)

    def test_validate_missing_definition(self) -> None:
        """节点定义未同步应报错。"""
        wf = self._create_workflow()
        normalized = {
            "nodes": [{
                "id": "1", "type": "UnsyncedNode", "title": "未同步",
                "position": [0, 0], "size": [100, 100], "mode": 0,
                "flags": {}, "widgets_values": [], "properties": {},
                "inputs": [], "outputs": [], "order": 0,
                "is_unknown": False,
            }],
            "links": [],
        }
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 1},
        )
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/validate")
        result = response.json()["validation"]
        self.assertFalse(result["is_valid"])
        error_types = [e["error_type"] for e in result["errors"]]
        self.assertIn("missing_definition", error_types)
        self.assertIn("UnsyncedNode", result["missing_definitions"])

    def test_validate_dangling_link(self) -> None:
        """悬空连线（源/目标节点不存在）应报错。"""
        wf = self._create_workflow()
        normalized = {
            "nodes": [{
                "id": "1", "type": "KSampler", "title": "K",
                "position": [0, 0], "size": [100, 100], "mode": 0,
                "flags": {}, "widgets_values": [], "properties": {},
                "inputs": [], "outputs": [], "order": 0, "is_unknown": False,
            }],
            "links": [{
                "id": "1", "source_node": "1", "source_slot": 0,
                "target_node": "999", "target_slot": 0, "type": "MODEL",
            }],
        }
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 1},
        )
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/validate")
        result = response.json()["validation"]
        error_types = [e["error_type"] for e in result["errors"]]
        self.assertIn("dangling_target", error_types)

    def test_validate_saves_state_to_draft(self) -> None:
        """校验后应将结果保存到草稿的 validation_state 字段。"""
        self._seed_node_definition("KSampler")
        wf = self._create_workflow()
        normalized = {
            "nodes": [{
                "id": "1", "type": "KSampler", "title": "K",
                "position": [0, 0], "size": [100, 100], "mode": 0,
                "flags": {}, "widgets_values": [], "properties": {},
                "inputs": [], "outputs": [], "order": 0, "is_unknown": False,
            }],
            "links": [],
        }
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 1},
        )
        self.client.post(f"/api/workflows/{wf['id']}/draft/validate")
        draft = self.client.get(f"/api/workflows/{wf['id']}/draft").json()["draft"]
        self.assertIsNotNone(draft.get("validation_state"))

    def test_validate_custom_node_counted(self) -> None:
        """自定义节点应被统计。"""
        self._seed_node_definition("CustomNode", is_custom=True)
        wf = self._create_workflow()
        normalized = {
            "nodes": [{
                "id": "1", "type": "CustomNode", "title": "自定义",
                "position": [0, 0], "size": [100, 100], "mode": 0,
                "flags": {}, "widgets_values": [], "properties": {},
                "inputs": [], "outputs": [], "order": 0, "is_unknown": False,
            }],
            "links": [],
        }
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 1},
        )
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/validate")
        result = response.json()["validation"]
        self.assertEqual(result["stats"]["custom_count"], 1)


# ── 5. 单元测试：ID 分配、端口兼容性、默认节点构建 ──────────────


class UtilityUnitTests(unittest.TestCase):
    def test_allocate_node_id_increments(self) -> None:
        normalized = NormalizedWorkflow(
            nodes=[{"id": "1"}, {"id": "5"}, {"id": "3"}],
        )
        new_id, last = allocate_node_id(normalized, last_node_id=2)
        self.assertEqual(new_id, "6")
        self.assertEqual(last, 6)

    def test_allocate_node_id_uses_last_node_id_when_higher(self) -> None:
        normalized = NormalizedWorkflow(nodes=[{"id": "1"}])
        new_id, last = allocate_node_id(normalized, last_node_id=10)
        self.assertEqual(new_id, "11")
        self.assertEqual(last, 11)

    def test_allocate_link_id_increments(self) -> None:
        normalized = NormalizedWorkflow(links=[{"id": "1"}, {"id": "7"}])
        new_id, last = allocate_link_id(normalized, last_link_id=3)
        self.assertEqual(new_id, "8")
        self.assertEqual(last, 8)

    def test_are_ports_compatible_same_type(self) -> None:
        ok, _ = are_ports_compatible("MODEL", "MODEL")
        self.assertTrue(ok)

    def test_are_ports_compatible_wildcard(self) -> None:
        ok, _ = are_ports_compatible("*", "MODEL")
        self.assertTrue(ok)
        ok, _ = are_ports_compatible("MODEL", "*")
        self.assertTrue(ok)

    def test_are_ports_compatible_mismatch(self) -> None:
        ok, reason = are_ports_compatible("LATENT", "MODEL")
        self.assertFalse(ok)
        self.assertIn("不匹配", reason)

    def test_build_default_node_generates_inputs_outputs(self) -> None:
        definition = _make_node_definition("TestNode")
        node = build_default_node("TestNode", definition, node_id="1")
        self.assertEqual(node["id"], "1")
        self.assertEqual(node["type"], "TestNode")
        # 必填 MODEL 输入应在 inputs 中
        self.assertTrue(any(i["name"] == "model" for i in node["inputs"]))
        # 必填 seed 应作为 widget_value
        self.assertEqual(len(node["widgets_values"]), 1)
        # 输出 LATENT 应在 outputs 中
        self.assertEqual(node["outputs"][0]["name"], "LATENT")

    def test_build_default_node_no_definition(self) -> None:
        node = build_default_node("Unknown", None, node_id="1")
        self.assertEqual(node["id"], "1")
        self.assertEqual(node["type"], "Unknown")
        self.assertEqual(node["inputs"], [])
        self.assertEqual(node["outputs"], [])

    def test_validate_workflow_empty(self) -> None:
        normalized = NormalizedWorkflow()
        result = validate_workflow(normalized, {})
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["stats"]["node_count"], 0)


# ── 6. 节点标志：禁用/旁路/折叠 ─────────────────────────────────


class NodeFlagsTests(_EditorBase):
    def test_disable_node_via_flags(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/2",
            json={"flags": {"disabled": True}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["node"]["flags"]["disabled"])

    def test_bypass_node_via_flags(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/2",
            json={"flags": {"bypassed": True}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["node"]["flags"]["bypassed"])

    def test_collapse_node_via_flags(self) -> None:
        wf = self._create_workflow()
        self._import_sample_draft(wf["id"])
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/2",
            json={"flags": {"collapsed": True}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["node"]["flags"]["collapsed"])

    def test_validation_counts_disabled_and_bypassed(self) -> None:
        self._seed_node_definition("KSampler")
        wf = self._create_workflow()
        normalized = {
            "nodes": [
                {"id": "1", "type": "KSampler", "title": "K1",
                 "position": [0, 0], "size": [100, 100], "mode": 0,
                 "flags": {"disabled": True}, "widgets_values": [], "properties": {},
                 "inputs": [], "outputs": [], "order": 0, "is_unknown": False},
                {"id": "2", "type": "KSampler", "title": "K2",
                 "position": [200, 0], "size": [100, 100], "mode": 0,
                 "flags": {"bypassed": True}, "widgets_values": [], "properties": {},
                 "inputs": [], "outputs": [], "order": 1, "is_unknown": False},
            ],
            "links": [],
        }
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 2},
        )
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/validate")
        result = response.json()["validation"]
        self.assertEqual(result["stats"]["disabled_count"], 1)
        self.assertEqual(result["stats"]["bypassed_count"], 1)


if __name__ == "__main__":
    unittest.main()
