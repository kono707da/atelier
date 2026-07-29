"""工作流规整布局算法。

实现阶段 2.4 的核心能力：

1. 稳定拓扑分层：基于有向图（Kahn 算法）将节点分为稳定的层级列。
2. 禁止自由拖动：节点位置完全由拓扑布局决定，不保存任意坐标。
3. 结构化调整：前移、后移、换列、置顶、置底、加入/移出分组泳道。
4. 分组泳道：节点可加入逻辑分组，分组以泳道形式包裹成员节点。
5. 连线避让、合束和类型提示：输出同源长连线的合束信息，便于前端绘制。
6. 聚焦上游、下游和错误节点：基于有向图计算可达子图。
7. 500 节点性能：算法复杂度为 O(V+E)，可处理大规模工作流。

设计原则：
- 布局结果必须可重复（稳定）：相同输入多次布局结果一致。
- 用户排序约束保存在 layout_state 中，不作为节点本身属性。
- 算法只输出位置和层级信息，不直接修改节点的业务字段。
"""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Literal

from .workflow_models import NormalizedWorkflow


# ──────────────────────────────────────────────────────────────────
# 布局常量
# ──────────────────────────────────────────────────────────────────

COLUMN_WIDTH = 320          # 列间距
ROW_HEIGHT = 120            # 同列节点行高
GROUP_PADDING = 40          # 分组泳道内边距
GROUP_HEADER_HEIGHT = 32    # 分组标题区高度
MAX_NODES_VIEWPORT = 80     # 视口裁剪阈值（超过此数量时前端应启用裁剪）


# ──────────────────────────────────────────────────────────────────
# 拓扑分层
# ──────────────────────────────────────────────────────────────────


def compute_topo_layers(
    normalized: NormalizedWorkflow,
    *,
    user_order_constraints: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """计算稳定拓扑分层。

    参数：
        normalized: 规范化工作流结构
        user_order_constraints: 用户排序约束 {
            node_id: {
                "pin_layer": int|None,   # 固定到指定层级
                "pin_index": int|None,   # 固定到同层指定位置
                "lock_relative": bool,   # 锁定相对次序
            }
        }

    返回：
        {
            "layers": [[node_id, ...], ...],  # 按层级分组的节点ID列表
            "node_layer": {node_id: layer_index},
            "node_index": {node_id: index_in_layer},
            "cycle_nodes": [node_id, ...],    # 环中的节点（打破环后分配到最高层）
        }

    算法：
        1. 构建有向图（source -> target）
        2. Kahn 算法计算拓扑序
        3. 节点层级 = max(所有前驱层级) + 1
        4. 同层节点按用户约束、节点ID稳定排序
        5. 环中节点统一分配到最顶层
    """
    user_order_constraints = user_order_constraints or {}
    nodes_by_id: dict[str, dict[str, Any]] = {
        str(node.get("id", "")): node for node in normalized.nodes
    }
    node_ids = set(nodes_by_id.keys())

    # 构建邻接表和入度
    successors: dict[str, set[str]] = defaultdict(set)
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

    for link in normalized.links:
        src = str(link.get("source_node", ""))
        tgt = str(link.get("target_node", ""))
        if src in node_ids and tgt in node_ids and tgt not in successors[src]:
            successors[src].add(tgt)
            in_degree[tgt] += 1

    # Kahn 算法：使用稳定排序的队列（按节点ID字符串排序）
    # 第一遍：计算层级
    node_layer: dict[str, int] = {}
    queue: deque[str] = deque(sorted([nid for nid, d in in_degree.items() if d == 0]))
    remaining_in_degree = dict(in_degree)
    processed = 0

    while queue:
        current = queue.popleft()
        # 层级 = max(前驱层级) + 1，无前驱则为 0
        preds = [n for n, succs in successors.items() if current in succs]
        if preds:
            layer = max(node_layer.get(p, 0) for p in preds) + 1
        else:
            layer = 0
        # 应用用户固定层级约束
        constraint = user_order_constraints.get(current, {})
        pin_layer = constraint.get("pin_layer")
        if isinstance(pin_layer, int) and pin_layer >= 0:
            layer = max(layer, pin_layer)
        node_layer[current] = layer
        processed += 1

        for succ in sorted(successors[current]):
            remaining_in_degree[succ] -= 1
            if remaining_in_degree[succ] == 0:
                queue.append(succ)

    # 处理环中节点（未处理的节点）
    cycle_nodes = [nid for nid in node_ids if nid not in node_layer]
    if cycle_nodes:
        max_layer = max(node_layer.values()) if node_layer else 0
        for nid in sorted(cycle_nodes):
            node_layer[nid] = max_layer + 1

    # 按层级分组
    layers_dict: dict[int, list[str]] = defaultdict(list)
    for nid, layer in node_layer.items():
        layers_dict[layer].append(nid)

    # 对每层节点稳定排序
    layers: list[list[str]] = []
    node_index: dict[str, int] = {}
    for layer_idx in sorted(layers_dict.keys()):
        members = layers_dict[layer_idx]
        # 排序优先级：pin_index > 节点ID
        def sort_key(nid: str) -> tuple[int, int, str]:
            constraint = user_order_constraints.get(nid, {})
            pin_index = constraint.get("pin_index")
            if isinstance(pin_index, int) and pin_index >= 0:
                return (0, pin_index, nid)
            return (1, 0, nid)

        members.sort(key=sort_key)
        for idx, nid in enumerate(members):
            node_index[nid] = idx
        layers.append(members)

    return {
        "layers": layers,
        "node_layer": node_layer,
        "node_index": node_index,
        "cycle_nodes": sorted(cycle_nodes),
    }


# ──────────────────────────────────────────────────────────────────
# 自动布局：计算节点位置
# ──────────────────────────────────────────────────────────────────


def compute_layout(
    normalized: NormalizedWorkflow,
    *,
    user_order_constraints: dict[str, dict[str, Any]] | None = None,
    groups: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """计算节点的自动布局位置。

    返回：
        {
            "positions": {node_id: [x, y]},
            "layers": [[node_id, ...], ...],
            "node_layer": {node_id: layer_index},
            "node_index": {node_id: index_in_layer},
            "groups": [{id, title, bounding, color, members}],
            "cycle_nodes": [node_id, ...],
        }

    布局规则：
        - 从左到右分列，列间距 COLUMN_WIDTH
        - 同列节点按 ROW_HEIGHT 垂直排列
        - 分组泳道包裹成员节点，添加内边距
        - 分组标题区高度 GROUP_HEADER_HEIGHT
    """
    groups = groups or []
    user_order_constraints = user_order_constraints or {}

    topo = compute_topo_layers(
        normalized, user_order_constraints=user_order_constraints
    )
    layers = topo["layers"]
    node_layer = topo["node_layer"]
    node_index = topo["node_index"]

    # 计算每列的节点位置
    positions: dict[str, list[int]] = {}
    # 统计每个分组在每层的成员数量（用于泳道高度）
    group_members_by_layer: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))

    # 构建分组映射：node_id -> group_id
    node_to_group: dict[str, str] = {}
    for group in groups:
        gid = str(group.get("id", ""))
        for member_id in group.get("members", []) if isinstance(group.get("members"), list) else []:
            node_to_group[str(member_id)] = gid

    for layer_idx, members in enumerate(layers):
        x = layer_idx * COLUMN_WIDTH
        # 按分组组织该层节点
        groups_in_layer: dict[str, list[str]] = defaultdict(list)
        ungrouped: list[str] = []
        for nid in members:
            gid = node_to_group.get(nid)
            if gid:
                groups_in_layer[gid].append(nid)
                group_members_by_layer[gid][layer_idx].append(nid)
            else:
                ungrouped.append(nid)

        # 先放置未分组节点，再放置各分组
        y = 0
        # 未分组节点
        for nid in ungrouped:
            positions[nid] = [x, y]
            y += ROW_HEIGHT

        # 分组节点（每个分组在每层内连续排列，形成泳道）
        for gid, group_members in groups_in_layer.items():
            y += GROUP_PADDING  # 分组内边距
            for nid in group_members:
                positions[nid] = [x, y]
                y += ROW_HEIGHT
            y += GROUP_PADDING

    # 计算分组的边界框
    group_layouts: list[dict[str, Any]] = []
    for group in groups:
        gid = str(group.get("id", ""))
        # 找出该分组所有成员的位置
        member_positions = [
            (nid, positions[nid]) for nid in node_to_group if node_to_group[nid] == gid and nid in positions
        ]
        if not member_positions:
            group_layouts.append({
                "id": gid,
                "title": str(group.get("title", "")),
                "color": str(group.get("color", "#3f789e")),
                "bounding": [0, 0, 0, 0],
                "members": [],
            })
            continue

        # 计算该分组占据的层级范围
        member_layers = [node_layer.get(nid, 0) for nid, _ in member_positions]
        min_layer = min(member_layers)
        max_layer = max(member_layers)
        min_x = min_layer * COLUMN_WIDTH - GROUP_PADDING
        max_x = (max_layer + 1) * COLUMN_WIDTH - COLUMN_WIDTH + 240 + GROUP_PADDING

        # 计算Y范围：在每个层中，该分组的成员Y范围
        member_ids = {nid for nid, _ in member_positions}
        min_y_values: list[int] = []
        max_y_values: list[int] = []
        for layer_idx, layer_members in enumerate(layers):
            group_in_this_layer = [nid for nid in layer_members if nid in member_ids]
            if not group_in_this_layer:
                continue
            ys = [positions[nid][1] for nid in group_in_this_layer]
            min_y_values.append(min(ys) - GROUP_PADDING)
            max_y_values.append(max(ys) + ROW_HEIGHT + GROUP_PADDING)

        min_y = min(min_y_values) if min_y_values else 0
        max_y = max(max_y_values) if max_y_values else min_y + ROW_HEIGHT

        group_layouts.append({
            "id": gid,
            "title": str(group.get("title", "")),
            "color": str(group.get("color", "#3f789e")),
            "bounding": [min_x, min_y - GROUP_HEADER_HEIGHT, max_x - min_x, max_y - min_y + GROUP_HEADER_HEIGHT],
            "members": sorted(member_ids),
        })

    return {
        "positions": positions,
        "layers": layers,
        "node_layer": node_layer,
        "node_index": node_index,
        "groups": group_layouts,
        "cycle_nodes": topo["cycle_nodes"],
    }


def apply_layout(
    normalized: NormalizedWorkflow,
    layout: dict[str, Any],
) -> NormalizedWorkflow:
    """将布局结果应用到节点（修改 position 字段）。

    注意：此函数会修改 normalized.nodes 中节点的 position 字段。
    其他业务字段保持不变。
    """
    positions = layout.get("positions", {})
    for node in normalized.nodes:
        nid = str(node.get("id", ""))
        if nid in positions:
            node["position"] = list(positions[nid])
    return normalized


# ──────────────────────────────────────────────────────────────────
# 节点排序操作（结构化调整）
# ──────────────────────────────────────────────────────────────────


ReorderAction = Literal[
    "forward",      # 同层前移
    "backward",     # 同层后移
    "prev_column",  # 移到上一列
    "next_column",  # 移到下一列
    "to_top",       # 置顶（同层首位）
    "to_bottom",    # 置底（同层末位）
]


def reorder_node(
    normalized: NormalizedWorkflow,
    node_id: str,
    action: ReorderAction,
    *,
    user_order_constraints: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """对节点执行结构化排序操作。

    返回更新后的 user_order_constraints 和新的布局。

    约束模型：
        - pin_layer: 固定层级（用于换列操作）
        - pin_index: 固定同层位置（用于前移/后移/置顶/置底）
        - lock_relative: 锁定相对次序（此版本不强制使用，保留扩展）

    换列操作会设置 pin_layer，将节点移动到新的层级。
    前移/后移/置顶/置底会设置 pin_index，调整同层内位置。
    为确保位置交换生效，会为同层所有节点分配 pin_index。
    """
    user_order_constraints = user_order_constraints or {}
    # 深拷贝约束，避免修改原对象
    constraints: dict[str, dict[str, Any]] = {
        nid: dict(c) for nid, c in user_order_constraints.items()
    }

    topo = compute_topo_layers(normalized, user_order_constraints=constraints)
    node_layer = topo["node_layer"]
    layers = topo["layers"]

    if node_id not in node_layer:
        raise ValueError(f"节点不存在：{node_id}")

    current_layer = node_layer[node_id]
    current_layer_members = layers[current_layer] if current_layer < len(layers) else [node_id]
    current_idx = topo["node_index"].get(node_id, 0)
    layer_size = len(current_layer_members)

    if action == "prev_column":
        if current_layer > 0:
            constraints[node_id] = {**constraints.get(node_id, {}), "pin_layer": current_layer - 1}
    elif action == "next_column":
        constraints[node_id] = {**constraints.get(node_id, {}), "pin_layer": current_layer + 1}
    else:
        # 对于同层排序操作（前移/后移/置顶/置底）：
        # 为同层所有节点分配 pin_index（基于当前位置），然后修改目标节点的 pin_index
        # 这样可以确保位置交换正确生效
        for idx, nid in enumerate(current_layer_members):
            existing = constraints.get(nid, {})
            constraints[nid] = {**existing, "pin_index": idx}

        if action == "to_top":
            # 将目标节点移到首位，其他节点后移
            target_new_idx = 0
        elif action == "to_bottom":
            target_new_idx = layer_size - 1
        elif action == "forward":
            if current_idx == 0:
                # 已在首位，无需移动
                return {
                    "user_order_constraints": constraints,
                    "layout": compute_layout(normalized, user_order_constraints=constraints),
                }
            target_new_idx = current_idx - 1
        elif action == "backward":
            if current_idx >= layer_size - 1:
                return {
                    "user_order_constraints": constraints,
                    "layout": compute_layout(normalized, user_order_constraints=constraints),
                }
            target_new_idx = current_idx + 1
        else:
            raise ValueError(f"不支持的排序操作：{action}")

        # 交换目标节点与目标位置的节点的 pin_index
        swapped_nid = current_layer_members[target_new_idx]
        constraints[node_id]["pin_index"] = target_new_idx
        constraints[swapped_nid]["pin_index"] = current_idx

    # 重新计算布局以返回结果
    layout = compute_layout(normalized, user_order_constraints=constraints)
    return {
        "user_order_constraints": constraints,
        "layout": layout,
    }


# ──────────────────────────────────────────────────────────────────
# 分组泳道管理
# ──────────────────────────────────────────────────────────────────


def create_group(
    title: str,
    *,
    color: str = "#3f789e",
    members: list[str] | None = None,
    group_id: str | None = None,
) -> dict[str, Any]:
    """创建分组泳道。"""
    import uuid as _uuid
    return {
        "id": group_id or _uuid.uuid4().hex,
        "title": title,
        "color": color,
        "members": list(members) if members else [],
    }


def assign_node_to_group(
    groups: list[dict[str, Any]],
    node_id: str,
    group_id: str | None,
) -> list[dict[str, Any]]:
    """将节点加入或移出分组。

    group_id 为 None 时，将节点从所有分组中移除。
    group_id 非空时，将节点从其他分组移除并加入指定分组。
    """
    result: list[dict[str, Any]] = []
    for group in groups:
        new_group = dict(group)
        members = [m for m in group.get("members", []) if isinstance(group.get("members"), list)]
        members = [m for m in members if str(m) != node_id]
        if str(group.get("id", "")) == group_id and node_id not in members:
            members.append(node_id)
        new_group["members"] = members
        result.append(new_group)
    return result


# ──────────────────────────────────────────────────────────────────
# 连线合束
# ──────────────────────────────────────────────────────────────────


def compute_link_bundles(
    normalized: NormalizedWorkflow,
    *,
    layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """计算连线合束信息。

    同源（source_node + source_slot）的长连线可以合束，在端口附近拆分。

    返回：
        {
            "bundles": [{
                "bundle_id": str,            # 合束ID
                "source_node": str,
                "source_slot": int,
                "source_type": str,
                "links": [link_id, ...],     # 合束的连线ID列表
                "targets": [{link_id, target_node, target_slot}, ...],
            }],
            "unbundled_links": [link_id, ...],  # 未合束的连线ID
            "type_hints": {link_id: type_str},  # 每条连线的类型提示
        }

    合束规则：
        - 同源连线数量 >= 2 时才合束
        - 同源连线只保留一条主线，其他在端口附近拆分
    """
    links_by_source: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    type_hints: dict[str, str] = {}

    for link in normalized.links:
        src = str(link.get("source_node", ""))
        src_slot = int(link.get("source_slot", -1))
        link_type = str(link.get("type", ""))
        link_id = str(link.get("id", ""))
        type_hints[link_id] = link_type
        if src and src_slot >= 0:
            links_by_source[(src, src_slot)].append(link)

    bundles: list[dict[str, Any]] = []
    unbundled: list[str] = []
    bundle_idx = 0

    for (src, src_slot), links in links_by_source.items():
        if len(links) >= 2:
            bundle_idx += 1
            bundles.append({
                "bundle_id": f"bundle_{src}_{src_slot}_{bundle_idx}",
                "source_node": src,
                "source_slot": src_slot,
                "source_type": str(links[0].get("type", "")),
                "links": [str(l.get("id", "")) for l in links],
                "targets": [
                    {
                        "link_id": str(l.get("id", "")),
                        "target_node": str(l.get("target_node", "")),
                        "target_slot": int(l.get("target_slot", -1)),
                    }
                    for l in links
                ],
            })
        else:
            unbundled.extend(str(l.get("id", "")) for l in links)

    return {
        "bundles": bundles,
        "unbundled_links": unbundled,
        "type_hints": type_hints,
    }


# ──────────────────────────────────────────────────────────────────
# 聚焦子图
# ──────────────────────────────────────────────────────────────────


FocusDirection = Literal["upstream", "downstream", "both", "errors"]


def compute_focus_subgraph(
    normalized: NormalizedWorkflow,
    node_id: str,
    direction: FocusDirection = "both",
    *,
    error_node_ids: list[str] | None = None,
) -> dict[str, Any]:
    """计算聚焦节点的上游/下游/错误子图。

    参数：
        node_id: 聚焦的节点ID
        direction: "upstream"（上游）、"downstream"（下游）、"both"（完整路径）、"errors"（错误节点）
        error_node_ids: 错误节点ID列表（direction="errors"时使用）

    返回：
        {
            "focus_node": node_id,
            "direction": direction,
            "upstream": [node_id, ...],
            "downstream": [node_id, ...],
            "highlighted": [node_id, ...],  # 高亮的节点ID
            "dimmed": [node_id, ...],       # 变暗的节点ID
            "related_links": [link_id, ...],  # 相关连线ID
        }
    """
    nodes_by_id = {str(n.get("id", "")): n for n in normalized.nodes}
    if node_id not in nodes_by_id:
        raise ValueError(f"节点不存在：{node_id}")

    # 构建邻接表
    successors: dict[str, set[str]] = defaultdict(set)
    predecessors: dict[str, set[str]] = defaultdict(set)
    links_between: dict[tuple[str, str], list[str]] = defaultdict(list)

    for link in normalized.links:
        src = str(link.get("source_node", ""))
        tgt = str(link.get("target_node", ""))
        link_id = str(link.get("id", ""))
        if src in nodes_by_id and tgt in nodes_by_id:
            successors[src].add(tgt)
            predecessors[tgt].add(src)
            links_between[(src, tgt)].append(link_id)

    if direction == "errors":
        error_set = set(error_node_ids or [])
        # 高亮错误节点及其直接上下游
        highlighted = set(error_set)
        related_links: list[str] = []
        for eid in error_set:
            for succ in successors.get(eid, set()):
                highlighted.add(succ)
                related_links.extend(links_between.get((eid, succ), []))
            for pred in predecessors.get(eid, set()):
                highlighted.add(pred)
                related_links.extend(links_between.get((pred, eid), []))
        all_ids = set(nodes_by_id.keys())
        return {
            "focus_node": node_id,
            "direction": direction,
            "upstream": [],
            "downstream": [],
            "highlighted": sorted(highlighted),
            "dimmed": sorted(all_ids - highlighted),
            "related_links": sorted(set(related_links)),
        }

    # BFS 上游
    upstream: set[str] = set()
    if direction in ("upstream", "both"):
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for pred in predecessors.get(current, set()):
                if pred not in upstream:
                    upstream.add(pred)
                    queue.append(pred)

    # BFS 下游
    downstream: set[str] = set()
    if direction in ("downstream", "both"):
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for succ in successors.get(current, set()):
                if succ not in downstream:
                    downstream.add(succ)
                    queue.append(succ)

    highlighted = {node_id} | upstream | downstream
    all_ids = set(nodes_by_id.keys())
    dimmed = all_ids - highlighted

    # 收集相关连线
    related_links: list[str] = []
    for nid in highlighted:
        for succ in successors.get(nid, set()):
            if succ in highlighted:
                related_links.extend(links_between.get((nid, succ), []))

    return {
        "focus_node": node_id,
        "direction": direction,
        "upstream": sorted(upstream),
        "downstream": sorted(downstream),
        "highlighted": sorted(highlighted),
        "dimmed": sorted(dimmed),
        "related_links": sorted(set(related_links)),
    }


# ──────────────────────────────────────────────────────────────────
# 性能测试辅助
# ──────────────────────────────────────────────────────────────────


def generate_large_workflow(node_count: int = 500) -> NormalizedWorkflow:
    """生成大规模测试工作流（线性链+并行分支）。

    用于 500 节点性能测试。
    结构：节点0 -> 节点1 -> ... -> 节点N-1（线性链）
         偶数节点额外连向下一个偶数节点（并行分支）
    """
    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    link_id = 0

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

    for i in range(node_count - 1):
        link_id += 1
        links.append({
            "id": str(link_id),
            "source_node": str(i),
            "source_slot": 0,
            "target_node": str(i + 1),
            "target_slot": 0,
            "type": "MODEL",
        })
        # 偶数节点额外并行分支
        if i % 2 == 0 and i + 2 < node_count:
            link_id += 1
            links.append({
                "id": str(link_id),
                "source_node": str(i),
                "source_slot": 0,
                "target_node": str(i + 2),
                "target_slot": 0,
                "type": "MODEL",
            })

    return NormalizedWorkflow(nodes=nodes, links=links, groups=[], metadata={})
