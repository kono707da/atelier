"""阶段 2.4 规整布局测试。

测试范围：
- 稳定拓扑分层（线性、并行、环、约束）
- 自动布局位置计算
- 节点排序操作（前移、后移、换列、置顶、置底）
- 分组泳道（创建、更新、删除、节点加入/移出）
- 连线合束和类型提示
- 聚焦上游、下游、错误节点
- 500 节点性能测试
- 布局 API 集成测试
"""
from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.workflow_layout import (
    assign_node_to_group,
    compute_focus_subgraph,
    compute_layout,
    compute_link_bundles,
    compute_topo_layers,
    create_group,
    generate_large_workflow,
    reorder_node,
    apply_layout,
    COLUMN_WIDTH,
    ROW_HEIGHT,
)
from backend.app.workflow_models import NormalizedWorkflow


def _make_linear_workflow(node_count: int = 4) -> NormalizedWorkflow:
    """生成线性链工作流：0 -> 1 -> 2 -> 3。"""
    nodes = []
    for i in range(node_count):
        nodes.append({
            "id": str(i),
            "type": "TestNode",
            "title": f"Node_{i}",
            "position": [0, 0],
            "size": [240, 0],
            "mode": 0,
            "flags": {"enabled": True, "bypassed": False, "disabled": False},
            "widgets_values": [],
            "properties": {},
            "inputs": [{"name": "in", "type": "MODEL", "link": None}] if i > 0 else [],
            "outputs": [{"name": "out", "type": "MODEL", "links": []}],
            "order": i,
            "is_unknown": False,
        })
    links = []
    for i in range(node_count - 1):
        links.append({
            "id": str(i + 1),
            "source_node": str(i),
            "source_slot": 0,
            "target_node": str(i + 1),
            "target_slot": 0,
            "type": "MODEL",
        })
    return NormalizedWorkflow(nodes=nodes, links=links, groups=[], metadata={})


def _make_parallel_workflow() -> NormalizedWorkflow:
    """生成并行工作流：
        0 -> 2
        0 -> 3
        1 -> 3
    """
    nodes = [
        {"id": "0", "type": "A", "title": "A", "position": [0, 0], "size": [240, 0], "mode": 0,
         "flags": {"enabled": True}, "widgets_values": [], "properties": {},
         "inputs": [], "outputs": [{"name": "out", "type": "MODEL", "links": []}], "order": 0, "is_unknown": False},
        {"id": "1", "type": "B", "title": "B", "position": [0, 0], "size": [240, 0], "mode": 0,
         "flags": {"enabled": True}, "widgets_values": [], "properties": {},
         "inputs": [], "outputs": [{"name": "out", "type": "MODEL", "links": []}], "order": 0, "is_unknown": False},
        {"id": "2", "type": "C", "title": "C", "position": [0, 0], "size": [240, 0], "mode": 0,
         "flags": {"enabled": True}, "widgets_values": [], "properties": {},
         "inputs": [{"name": "in", "type": "MODEL", "link": None}],
         "outputs": [{"name": "out", "type": "MODEL", "links": []}], "order": 1, "is_unknown": False},
        {"id": "3", "type": "D", "title": "D", "position": [0, 0], "size": [240, 0], "mode": 0,
         "flags": {"enabled": True}, "widgets_values": [], "properties": {},
         "inputs": [{"name": "in", "type": "MODEL", "link": None}, {"name": "in2", "type": "MODEL", "link": None}],
         "outputs": [], "order": 2, "is_unknown": False},
    ]
    links = [
        {"id": "1", "source_node": "0", "source_slot": 0, "target_node": "2", "target_slot": 0, "type": "MODEL"},
        {"id": "2", "source_node": "0", "source_slot": 0, "target_node": "3", "target_slot": 0, "type": "MODEL"},
        {"id": "3", "source_node": "1", "source_slot": 0, "target_node": "3", "target_slot": 1, "type": "MODEL"},
    ]
    return NormalizedWorkflow(nodes=nodes, links=links, groups=[], metadata={})


def _make_cycle_workflow() -> NormalizedWorkflow:
    """生成带环的工作流：0 -> 1 -> 2 -> 1（环）。"""
    nodes = [
        {"id": "0", "type": "A", "title": "A", "position": [0, 0], "size": [240, 0], "mode": 0,
         "flags": {"enabled": True}, "widgets_values": [], "properties": {},
         "inputs": [], "outputs": [{"name": "out", "type": "MODEL", "links": []}], "order": 0, "is_unknown": False},
        {"id": "1", "type": "B", "title": "B", "position": [0, 0], "size": [240, 0], "mode": 0,
         "flags": {"enabled": True}, "widgets_values": [], "properties": {},
         "inputs": [{"name": "in", "type": "MODEL", "link": None}],
         "outputs": [{"name": "out", "type": "MODEL", "links": []}], "order": 1, "is_unknown": False},
        {"id": "2", "type": "C", "title": "C", "position": [0, 0], "size": [240, 0], "mode": 0,
         "flags": {"enabled": True}, "widgets_values": [], "properties": {},
         "inputs": [{"name": "in", "type": "MODEL", "link": None}],
         "outputs": [{"name": "out", "type": "MODEL", "links": []}], "order": 2, "is_unknown": False},
    ]
    links = [
        {"id": "1", "source_node": "0", "source_slot": 0, "target_node": "1", "target_slot": 0, "type": "MODEL"},
        {"id": "2", "source_node": "1", "source_slot": 0, "target_node": "2", "target_slot": 0, "type": "MODEL"},
        {"id": "3", "source_node": "2", "source_slot": 0, "target_node": "1", "target_slot": 0, "type": "MODEL"},
    ]
    return NormalizedWorkflow(nodes=nodes, links=links, groups=[], metadata={})


# ── 拓扑分层测试 ──────────────────────────────────────────────


class TopoLayerTests(unittest.TestCase):
    def test_linear_workflow_layers(self) -> None:
        """线性工作流每个节点独占一层。"""
        wf = _make_linear_workflow(4)
        topo = compute_topo_layers(wf)
        self.assertEqual(len(topo["layers"]), 4)
        self.assertEqual(topo["layers"][0], ["0"])
        self.assertEqual(topo["layers"][1], ["1"])
        self.assertEqual(topo["layers"][3], ["3"])
        self.assertEqual(topo["node_layer"]["0"], 0)
        self.assertEqual(topo["node_layer"]["3"], 3)

    def test_parallel_workflow_layers(self) -> None:
        """并行工作流正确分层：0,1 在第0层，2和3在第1层（都依赖第0层节点）。"""
        wf = _make_parallel_workflow()
        topo = compute_topo_layers(wf)
        self.assertEqual(topo["node_layer"]["0"], 0)
        self.assertEqual(topo["node_layer"]["1"], 0)
        self.assertEqual(topo["node_layer"]["2"], 1)
        self.assertEqual(topo["node_layer"]["3"], 1)

    def test_cycle_nodes_detected(self) -> None:
        """环中节点被识别并分配到最高层。"""
        wf = _make_cycle_workflow()
        topo = compute_topo_layers(wf)
        # 节点0在第0层，1和2形成环
        self.assertEqual(topo["node_layer"]["0"], 0)
        # 环中节点1和2应在 cycle_nodes 中
        self.assertIn("1", topo["cycle_nodes"])
        self.assertIn("2", topo["cycle_nodes"])

    def test_stable_layout_repeated(self) -> None:
        """相同输入多次布局结果一致（稳定性）。"""
        wf = _make_parallel_workflow()
        layout1 = compute_layout(wf)
        layout2 = compute_layout(wf)
        self.assertEqual(layout1["positions"], layout2["positions"])
        self.assertEqual(layout1["layers"], layout2["layers"])

    def test_user_pin_layer_constraint(self) -> None:
        """用户固定层级约束生效。"""
        wf = _make_linear_workflow(4)
        constraints = {"2": {"pin_layer": 5}}
        topo = compute_topo_layers(wf, user_order_constraints=constraints)
        self.assertGreaterEqual(topo["node_layer"]["2"], 5)

    def test_user_pin_index_constraint(self) -> None:
        """用户固定同层位置约束生效。"""
        wf = _make_parallel_workflow()
        # 将节点1固定到同层首位
        constraints = {"1": {"pin_index": 0}}
        topo = compute_topo_layers(wf, user_order_constraints=constraints)
        # 第0层应为 ["1", "0"]（1在首位）
        self.assertEqual(topo["layers"][0][0], "1")


# ── 自动布局位置测试 ──────────────────────────────────────────


class LayoutPositionTests(unittest.TestCase):
    def test_linear_layout_positions(self) -> None:
        """线性工作流节点按列排列。"""
        wf = _make_linear_workflow(4)
        layout = compute_layout(wf)
        positions = layout["positions"]
        # 节点0在第0列，X=0
        self.assertEqual(positions["0"][0], 0)
        # 节点1在第1列，X=COLUMN_WIDTH
        self.assertEqual(positions["1"][0], COLUMN_WIDTH)
        # 节点3在第3列
        self.assertEqual(positions["3"][0], 3 * COLUMN_WIDTH)

    def test_parallel_layout_y_positions(self) -> None:
        """并行节点垂直排列。"""
        wf = _make_parallel_workflow()
        layout = compute_layout(wf)
        positions = layout["positions"]
        # 节点0和1在第0列，Y应不同
        self.assertNotEqual(positions["0"][1], positions["1"][1])
        # 节点0的Y应为0（同层第一个）
        self.assertEqual(positions["0"][1], 0)
        # 节点1的Y应为ROW_HEIGHT
        self.assertEqual(positions["1"][1], ROW_HEIGHT)

    def test_apply_layout_updates_positions(self) -> None:
        """apply_layout 将位置应用到节点。"""
        wf = _make_linear_workflow(3)
        layout = compute_layout(wf)
        # 重置位置
        for node in wf.nodes:
            node["position"] = [999, 999]
        apply_layout(wf, layout)
        # 验证位置已更新
        self.assertEqual(wf.nodes[0]["position"], layout["positions"]["0"])
        self.assertEqual(wf.nodes[1]["position"], layout["positions"]["1"])

    def test_groups_bounding(self) -> None:
        """分组泳道计算边界框。"""
        wf = _make_parallel_workflow()
        group = create_group("测试分组", members=["0", "1"])
        layout = compute_layout(wf, groups=[group])
        self.assertEqual(len(layout["groups"]), 1)
        group_layout = layout["groups"][0]
        self.assertEqual(group_layout["title"], "测试分组")
        self.assertIn("0", group_layout["members"])
        self.assertIn("1", group_layout["members"])
        # 边界框应有有效值
        bounding = group_layout["bounding"]
        self.assertEqual(len(bounding), 4)


# ── 节点排序操作测试 ──────────────────────────────────────────


class ReorderNodeTests(unittest.TestCase):
    def test_to_top_action(self) -> None:
        """置顶操作：节点移动到同层首位。"""
        wf = _make_parallel_workflow()
        # 默认第0层是 ["0", "1"]，将 "1" 置顶
        result = reorder_node(wf, "1", "to_top")
        layer0 = result["layout"]["layers"][0]
        self.assertEqual(layer0[0], "1")

    def test_to_bottom_action(self) -> None:
        """置底操作：节点移动到同层末位。"""
        wf = _make_parallel_workflow()
        # 默认第0层是 ["0", "1"]，将 "0" 置底
        result = reorder_node(wf, "0", "to_bottom")
        layer0 = result["layout"]["layers"][0]
        self.assertEqual(layer0[-1], "0")

    def test_forward_action(self) -> None:
        """前移操作：节点在同层前移一位。"""
        wf = _make_parallel_workflow()
        # 默认第0层是 ["0", "1"]，将 "1" 前移
        result = reorder_node(wf, "1", "forward")
        layer0 = result["layout"]["layers"][0]
        self.assertEqual(layer0[0], "1")

    def test_backward_action(self) -> None:
        """后移操作：节点在同层后移一位。"""
        wf = _make_parallel_workflow()
        # 默认第0层是 ["0", "1"]，将 "0" 后移
        result = reorder_node(wf, "0", "backward")
        layer0 = result["layout"]["layers"][0]
        self.assertEqual(layer0[-1], "0")

    def test_next_column_action(self) -> None:
        """换列操作：节点移到下一列。"""
        wf = _make_linear_workflow(4)
        result = reorder_node(wf, "0", "next_column")
        # 节点0原本在第0层，应被固定到第1层
        self.assertEqual(result["user_order_constraints"]["0"]["pin_layer"], 1)

    def test_prev_column_action(self) -> None:
        """换列操作：节点移到上一列。"""
        wf = _make_linear_workflow(4)
        # 节点1原本在第1层，移到第0层
        result = reorder_node(wf, "1", "prev_column")
        self.assertEqual(result["user_order_constraints"]["1"]["pin_layer"], 0)

    def test_prev_column_at_first_layer_no_op(self) -> None:
        """已在第0层的节点无法再上移。"""
        wf = _make_linear_workflow(4)
        result = reorder_node(wf, "0", "prev_column")
        # 不应有pin_layer约束
        self.assertNotIn("0", result["user_order_constraints"])

    def test_reorder_invalid_node_raises(self) -> None:
        """对不存在的节点排序应报错。"""
        wf = _make_parallel_workflow()
        with self.assertRaises(ValueError):
            reorder_node(wf, "nonexistent", "to_top")


# ── 分组泳道测试 ──────────────────────────────────────────────


class GroupManagementTests(unittest.TestCase):
    def test_create_group(self) -> None:
        """创建分组。"""
        group = create_group("测试", color="#ff0000", members=["1", "2"])
        self.assertEqual(group["title"], "测试")
        self.assertEqual(group["color"], "#ff0000")
        self.assertEqual(group["members"], ["1", "2"])
        self.assertIn("id", group)

    def test_assign_node_to_group(self) -> None:
        """将节点加入分组。"""
        groups = [create_group("分组A", members=["1"])]
        new_groups = assign_node_to_group(groups, "2", groups[0]["id"])
        self.assertIn("2", new_groups[0]["members"])
        self.assertIn("1", new_groups[0]["members"])

    def test_assign_node_to_another_group(self) -> None:
        """节点从原分组移到新分组。"""
        group_a = create_group("分组A", members=["1"])
        group_b = create_group("分组B", members=[])
        new_groups = assign_node_to_group([group_a, group_b], "1", group_b["id"])
        # 节点1应从分组A移除
        self.assertNotIn("1", new_groups[0]["members"])
        # 节点1应加入分组B
        self.assertIn("1", new_groups[1]["members"])

    def test_remove_node_from_group(self) -> None:
        """将节点从分组移除。"""
        groups = [create_group("分组A", members=["1", "2"])]
        new_groups = assign_node_to_group(groups, "1", None)
        self.assertNotIn("1", new_groups[0]["members"])
        self.assertIn("2", new_groups[0]["members"])


# ── 连线合束测试 ──────────────────────────────────────────────


class LinkBundleTests(unittest.TestCase):
    def test_bundle_multiple_links_from_same_source(self) -> None:
        """同源多条连线被合束。"""
        wf = _make_parallel_workflow()
        # 节点0有两条输出连线（到2和到3）
        bundles = compute_link_bundles(wf)
        self.assertEqual(len(bundles["bundles"]), 1)
        bundle = bundles["bundles"][0]
        self.assertEqual(bundle["source_node"], "0")
        self.assertEqual(len(bundle["links"]), 2)

    def test_unbundled_single_links(self) -> None:
        """单条连线的源不被合束。"""
        wf = _make_linear_workflow(3)
        bundles = compute_link_bundles(wf)
        # 每个源只有一条连线，不应合束
        self.assertEqual(len(bundles["bundles"]), 0)
        self.assertEqual(len(bundles["unbundled_links"]), 2)

    def test_type_hints_returned(self) -> None:
        """返回每条连线的类型提示。"""
        wf = _make_parallel_workflow()
        bundles = compute_link_bundles(wf)
        self.assertEqual(bundles["type_hints"]["1"], "MODEL")
        self.assertEqual(bundles["type_hints"]["2"], "MODEL")


# ── 聚焦子图测试 ──────────────────────────────────────────────


class FocusSubgraphTests(unittest.TestCase):
    def test_focus_upstream(self) -> None:
        """聚焦上游节点。"""
        wf = _make_linear_workflow(5)
        focus = compute_focus_subgraph(wf, "4", "upstream")
        self.assertEqual(focus["focus_node"], "4")
        self.assertIn("0", focus["upstream"])
        self.assertIn("3", focus["upstream"])
        self.assertNotIn("4", focus["upstream"])  # 不含自身

    def test_focus_downstream(self) -> None:
        """聚焦下游节点。"""
        wf = _make_linear_workflow(5)
        focus = compute_focus_subgraph(wf, "0", "downstream")
        self.assertIn("1", focus["downstream"])
        self.assertIn("4", focus["downstream"])
        self.assertNotIn("0", focus["downstream"])

    def test_focus_both(self) -> None:
        """聚焦上下游。"""
        wf = _make_linear_workflow(5)
        focus = compute_focus_subgraph(wf, "2", "both")
        self.assertIn("0", focus["upstream"])
        self.assertIn("1", focus["upstream"])
        self.assertIn("3", focus["downstream"])
        self.assertIn("4", focus["downstream"])
        self.assertIn("2", focus["highlighted"])

    def test_focus_errors(self) -> None:
        """聚焦错误节点及其直接邻居。"""
        wf = _make_parallel_workflow()
        focus = compute_focus_subgraph(wf, "0", "errors", error_node_ids=["2"])
        self.assertIn("2", focus["highlighted"])
        # 节点2的上游节点0也应高亮
        self.assertIn("0", focus["highlighted"])

    def test_focus_invalid_node_raises(self) -> None:
        """聚焦不存在的节点应报错。"""
        wf = _make_linear_workflow(3)
        with self.assertRaises(ValueError):
            compute_focus_subgraph(wf, "nonexistent", "both")

    def test_focus_related_links(self) -> None:
        """返回相关连线ID。"""
        wf = _make_linear_workflow(4)
        focus = compute_focus_subgraph(wf, "1", "both")
        # 上游连线（0->1）和下游连线（1->2, 2->3）应在相关连线中
        self.assertIn("1", focus["related_links"])  # 0->1
        self.assertIn("2", focus["related_links"])  # 1->2


# ── 500节点性能测试 ──────────────────────────────────────────


class PerformanceTests(unittest.TestCase):
    def test_500_nodes_layout_performance(self) -> None:
        """500节点布局在3秒内完成。"""
        wf = generate_large_workflow(500)
        self.assertEqual(len(wf.nodes), 500)
        start = time.perf_counter()
        layout = compute_layout(wf)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 3.0, f"布局耗时 {elapsed:.2f}s 超过3秒")
        # 验证布局结果
        self.assertEqual(len(layout["positions"]), 500)
        self.assertGreater(len(layout["layers"]), 0)

    def test_500_nodes_focus_performance(self) -> None:
        """500节点聚焦子图在1秒内完成。"""
        wf = generate_large_workflow(500)
        start = time.perf_counter()
        focus = compute_focus_subgraph(wf, "250", "both")
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0, f"聚焦耗时 {elapsed:.2f}s 超过1秒")
        # 验证聚焦结果
        self.assertGreater(len(focus["upstream"]), 0)
        self.assertGreater(len(focus["downstream"]), 0)

    def test_500_nodes_bundles_performance(self) -> None:
        """500节点连线合束在1秒内完成。"""
        wf = generate_large_workflow(500)
        start = time.perf_counter()
        bundles = compute_link_bundles(wf)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.0, f"合束耗时 {elapsed:.2f}s 超过1秒")
        # 验证合束结果
        self.assertGreater(len(bundles["type_hints"]), 0)


# ── API 集成测试 ──────────────────────────────────────────────


class _LayoutAPIBase(unittest.TestCase):
    """布局 API 测试基类。"""

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
        """创建一个包含3个节点的草稿。"""
        normalized = {
            "nodes": [
                {"id": "1", "type": "A", "title": "A", "position": [0, 0], "size": [240, 0],
                 "mode": 0, "flags": {"enabled": True}, "widgets_values": [], "properties": {},
                 "inputs": [], "outputs": [{"name": "out", "type": "MODEL", "links": []}],
                 "order": 0, "is_unknown": False},
                {"id": "2", "type": "B", "title": "B", "position": [0, 0], "size": [240, 0],
                 "mode": 0, "flags": {"enabled": True}, "widgets_values": [], "properties": {},
                 "inputs": [{"name": "in", "type": "MODEL", "link": None}],
                 "outputs": [{"name": "out", "type": "MODEL", "links": []}],
                 "order": 1, "is_unknown": False},
                {"id": "3", "type": "C", "title": "C", "position": [0, 0], "size": [240, 0],
                 "mode": 0, "flags": {"enabled": True}, "widgets_values": [], "properties": {},
                 "inputs": [{"name": "in", "type": "MODEL", "link": None}],
                 "outputs": [], "order": 2, "is_unknown": False},
            ],
            "links": [
                {"id": "1", "source_node": "1", "source_slot": 0, "target_node": "2", "target_slot": 0, "type": "MODEL"},
                {"id": "2", "source_node": "2", "source_slot": 0, "target_node": "3", "target_slot": 0, "type": "MODEL"},
            ],
            "groups": [],
            "metadata": {"source_format": "ui_json"},
        }
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft",
            json={
                "normalized_graph": json.dumps(normalized, ensure_ascii=False),
                "node_count": 3,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)


class LayoutAPIComputeTests(_LayoutAPIBase):
    def test_compute_layout(self) -> None:
        """计算并应用自动布局。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/layout/compute")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("layout", data)
        self.assertIn("positions", data["layout"])
        self.assertEqual(len(data["layout"]["positions"]), 3)
        # 验证节点1在第0列
        self.assertEqual(data["layout"]["positions"]["1"][0], 0)
        # 验证节点2在第1列
        self.assertEqual(data["layout"]["positions"]["2"][0], COLUMN_WIDTH)

    def test_get_layout(self) -> None:
        """获取布局状态。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.get(f"/api/workflows/{wf['id']}/draft/layout")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("layout", data)
        self.assertIn("user_order_constraints", data)
        self.assertIn("groups", data)

    def test_compute_layout_draft_not_found(self) -> None:
        """草稿不存在时返回404。"""
        wf = self._create_workflow()
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/layout/compute")
        self.assertEqual(response.status_code, 404)


class LayoutAPIReorderTests(_LayoutAPIBase):
    def test_reorder_node_to_top(self) -> None:
        """通过API对节点置顶。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/1/reorder",
            json={"action": "to_top"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("layout", data)
        self.assertIn("user_order_constraints", data)

    def test_reorder_node_next_column(self) -> None:
        """通过API换列。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/1/reorder",
            json={"action": "next_column"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["user_order_constraints"]["1"]["pin_layer"], 1)

    def test_reorder_invalid_node(self) -> None:
        """对不存在的节点排序返回404。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/nonexistent/reorder",
            json={"action": "to_top"},
        )
        self.assertEqual(response.status_code, 404)


class LayoutAPIGroupTests(_LayoutAPIBase):
    def test_create_group(self) -> None:
        """创建分组泳道。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/groups",
            json={"title": "测试分组", "color": "#ff0000", "members": ["1", "2"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["group"]["title"], "测试分组")
        self.assertIn("1", data["group"]["members"])
        self.assertIn("2", data["group"]["members"])

    def test_update_group(self) -> None:
        """更新分组标题和颜色。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        create_resp = self.client.post(
            f"/api/workflows/{wf['id']}/draft/groups",
            json={"title": "原标题", "members": []},
        )
        group_id = create_resp.json()["group"]["id"]
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft/groups/{group_id}",
            json={"title": "新标题", "color": "#00ff00"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["groups"][0]["title"], "新标题")
        self.assertEqual(data["groups"][0]["color"], "#00ff00")

    def test_delete_group(self) -> None:
        """删除分组。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        create_resp = self.client.post(
            f"/api/workflows/{wf['id']}/draft/groups",
            json={"title": "待删除", "members": []},
        )
        group_id = create_resp.json()["group"]["id"]
        response = self.client.delete(
            f"/api/workflows/{wf['id']}/draft/groups/{group_id}"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["deleted"])

    def test_assign_node_to_group(self) -> None:
        """将节点加入分组。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        create_resp = self.client.post(
            f"/api/workflows/{wf['id']}/draft/groups",
            json={"title": "分组", "members": []},
        )
        group_id = create_resp.json()["group"]["id"]
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/1/assign-group",
            json={"group_id": group_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("1", data["groups"][0]["members"])

    def test_assign_node_to_invalid_group(self) -> None:
        """加入不存在的分组返回404。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/1/assign-group",
            json={"group_id": "nonexistent"},
        )
        self.assertEqual(response.status_code, 404)

    def test_remove_node_from_group(self) -> None:
        """将节点从分组移除。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        create_resp = self.client.post(
            f"/api/workflows/{wf['id']}/draft/groups",
            json={"title": "分组", "members": ["1"]},
        )
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/nodes/1/assign-group",
            json={"group_id": None},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertNotIn("1", data["groups"][0]["members"])


class LayoutAPIBundleTests(_LayoutAPIBase):
    def test_get_link_bundles(self) -> None:
        """获取连线合束信息。"""
        wf = self._create_workflow()
        # 草稿中节点1有两条输出连线（到2和到3）
        normalized = {
            "nodes": [
                {"id": "1", "type": "A", "title": "A", "position": [0, 0], "size": [240, 0],
                 "mode": 0, "flags": {"enabled": True}, "widgets_values": [], "properties": {},
                 "inputs": [], "outputs": [{"name": "out", "type": "MODEL", "links": []}],
                 "order": 0, "is_unknown": False},
                {"id": "2", "type": "B", "title": "B", "position": [0, 0], "size": [240, 0],
                 "mode": 0, "flags": {"enabled": True}, "widgets_values": [], "properties": {},
                 "inputs": [{"name": "in", "type": "MODEL", "link": None}],
                 "outputs": [], "order": 1, "is_unknown": False},
                {"id": "3", "type": "C", "title": "C", "position": [0, 0], "size": [240, 0],
                 "mode": 0, "flags": {"enabled": True}, "widgets_values": [], "properties": {},
                 "inputs": [{"name": "in", "type": "MODEL", "link": None}],
                 "outputs": [], "order": 1, "is_unknown": False},
            ],
            "links": [
                {"id": "1", "source_node": "1", "source_slot": 0, "target_node": "2", "target_slot": 0, "type": "MODEL"},
                {"id": "2", "source_node": "1", "source_slot": 0, "target_node": "3", "target_slot": 0, "type": "MODEL"},
            ],
            "groups": [],
            "metadata": {"source_format": "ui_json"},
        }
        response = self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": json.dumps(normalized, ensure_ascii=False), "node_count": 3},
        )
        self.assertEqual(response.status_code, 200)

        bundle_resp = self.client.get(f"/api/workflows/{wf['id']}/draft/links/bundles")
        self.assertEqual(bundle_resp.status_code, 200, bundle_resp.text)
        data = bundle_resp.json()
        self.assertEqual(len(data["bundles"]), 1)
        self.assertEqual(data["bundles"][0]["source_node"], "1")
        self.assertEqual(len(data["bundles"][0]["links"]), 2)


class LayoutAPIFocusTests(_LayoutAPIBase):
    def test_focus_downstream(self) -> None:
        """通过API聚焦下游。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/focus",
            json={"node_id": "1", "direction": "downstream"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("2", data["focus"]["downstream"])
        self.assertIn("3", data["focus"]["downstream"])

    def test_focus_upstream(self) -> None:
        """通过API聚焦上游。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/focus",
            json={"node_id": "3", "direction": "upstream"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("1", data["focus"]["upstream"])
        self.assertIn("2", data["focus"]["upstream"])

    def test_focus_invalid_node(self) -> None:
        """聚焦不存在的节点返回404。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(
            f"/api/workflows/{wf['id']}/draft/focus",
            json={"node_id": "nonexistent", "direction": "both"},
        )
        self.assertEqual(response.status_code, 404)


class LayoutAPIPerfTestTests(_LayoutAPIBase):
    def test_perf_test_endpoint(self) -> None:
        """性能测试端点返回500节点布局耗时。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        response = self.client.post(f"/api/workflows/{wf['id']}/draft/layout/perf-test")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["node_count"], 500)
        self.assertGreater(data["layer_count"], 0)
        self.assertLess(data["elapsed_ms"], 3000)  # 3秒内


class LayoutStateSaveTests(_LayoutAPIBase):
    def test_layout_state_persisted(self) -> None:
        """布局状态（用户约束和分组）持久化到草稿。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        # 创建分组
        self.client.post(
            f"/api/workflows/{wf['id']}/draft/groups",
            json={"title": "持久化分组", "members": ["1"]},
        )
        # 重新获取草稿
        draft_resp = self.client.get(f"/api/workflows/{wf['id']}/draft")
        draft = draft_resp.json()["draft"]
        self.assertIsNotNone(draft.get("layout_state"))
        state = json.loads(draft["layout_state"])
        self.assertEqual(len(state["groups"]), 1)
        self.assertEqual(state["groups"][0]["title"], "持久化分组")

    def test_layout_state_survives_node_update(self) -> None:
        """更新节点时布局状态保持。"""
        wf = self._create_workflow()
        self._seed_sample_draft(wf["id"])
        # 创建分组
        self.client.post(
            f"/api/workflows/{wf['id']}/draft/groups",
            json={"title": "保持分组", "members": ["1"]},
        )
        # 更新节点
        self.client.put(
            f"/api/workflows/{wf['id']}/draft/nodes/1",
            json={"title": "新标题"},
        )
        # 验证布局状态仍存在
        draft_resp = self.client.get(f"/api/workflows/{wf['id']}/draft")
        draft = draft_resp.json()["draft"]
        state = json.loads(draft["layout_state"])
        self.assertEqual(len(state["groups"]), 1)
        self.assertEqual(state["groups"][0]["title"], "保持分组")


if __name__ == "__main__":
    unittest.main()
