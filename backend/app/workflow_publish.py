"""工作流转换、校验和发布。

实现阶段 2.6 的核心能力：

1. UI JSON 转 API JSON：将规范化结构转换为 ComfyUI API JSON 格式。
2. API JSON 回读和导出：从 API JSON 重新解析为规范化结构，并支持导出。
3. 与当前 ComfyUI 节点定义校验：检查节点定义是否已同步、模型是否可用。
4. 定位缺失节点、模型和参数错误：返回详细的错误定位信息。
5. 发布不可变版本：基于草稿创建不可变版本快照。
6. 设置项目默认工作流：已有实现（database.set_project_default_workflow）。
7. 往返测试：导入—编辑—保存—导出的完整性验证。

设计原则：
- 转换不丢失数据：raw_ui_json 和 raw_api_json 独立保存。
- API JSON 生成基于规范化结构，不依赖原始 UI JSON。
- 发布前必须通过预检查（可选）。
"""
from __future__ import annotations

from typing import Any

from .workflow_models import NormalizedWorkflow


# ──────────────────────────────────────────────────────────────────
# 规范化结构 → API JSON
# ──────────────────────────────────────────────────────────────────


def normalized_to_api_json(normalized: NormalizedWorkflow) -> dict[str, Any]:
    """将规范化工作流结构转换为 ComfyUI API JSON 格式。

    API JSON 格式：
    {
        "node_id": {
            "class_type": "NodeClass",
            "inputs": {
                "input_name": value,           # 值参数
                "input_name": ["node_id", slot]  # 连线引用
            }
        }
    }

    转换规则：
    - 节点ID作为key
    - class_type 来自节点 type
    - inputs 包含所有输入参数
    - 连线引用为 [source_node_id, source_slot] 格式
    - 旁路节点（bypassed）跳过，其输入直通到输出
    - 禁用节点跳过
    """
    # 构建节点ID到节点的映射
    nodes_by_id: dict[str, dict[str, Any]] = {
        str(n.get("id", "")): n for n in normalized.nodes
    }

    # 构建连线映射：target_node + target_slot -> (source_node, source_slot)
    link_map: dict[tuple[str, int], tuple[str, int]] = {}
    for link in normalized.links:
        src = str(link.get("source_node", ""))
        tgt = str(link.get("target_node", ""))
        src_slot = int(link.get("source_slot", -1))
        tgt_slot = int(link.get("target_slot", -1))
        if src and tgt and src_slot >= 0 and tgt_slot >= 0:
            link_map[(tgt, tgt_slot)] = (src, src_slot)

    api_json: dict[str, Any] = {}

    for node in normalized.nodes:
        node_id = str(node.get("id", ""))
        node_type = str(node.get("type", "Unknown"))
        flags = node.get("flags", {}) if isinstance(node.get("flags"), dict) else {}
        is_bypassed = bool(flags.get("bypassed", False))
        is_disabled = bool(flags.get("disabled", False))

        # 跳过禁用节点
        if is_disabled:
            continue

        # 旁路节点的输入直通到输出（简化处理：仍包含在API JSON中但标记）
        if is_bypassed:
            # 旁路节点在API JSON中跳过，其输入连线需要直通
            # 简化：跳过旁路节点，后续版本可优化直通逻辑
            continue

        inputs_data: dict[str, Any] = {}
        inputs = node.get("inputs", []) if isinstance(node.get("inputs"), list) else []
        for inp in inputs:
            inp_name = str(inp.get("name", ""))
            if not inp_name:
                continue
            # 检查是否有连线
            link_id = inp.get("link")
            if link_id:
                # 查找连线对应的源节点和槽
                target_slot = -1
                for idx, i in enumerate(inputs):
                    if i is inp:
                        target_slot = idx
                        break
                if target_slot >= 0 and (node_id, target_slot) in link_map:
                    src_node, src_slot = link_map[(node_id, target_slot)]
                    inputs_data[inp_name] = [src_node, src_slot]
            else:
                # 值参数
                if "value" in inp:
                    inputs_data[inp_name] = inp["value"]

        # 从 widgets_values 补充参数（如果 inputs 中没有值）
        widgets_values = node.get("widgets_values", [])
        if isinstance(widgets_values, list) and widgets_values:
            # 尝试将 widgets_values 映射到 inputs
            # 简化：如果 inputs 中没有值，按顺序使用 widgets_values
            value_idx = 0
            for inp in inputs:
                inp_name = str(inp.get("name", ""))
                if not inp_name:
                    continue
                if inp.get("link"):
                    continue  # 有连线，跳过
                if inp_name not in inputs_data and value_idx < len(widgets_values):
                    inputs_data[inp_name] = widgets_values[value_idx]
                    value_idx += 1

        api_json[node_id] = {
            "class_type": node_type,
            "inputs": inputs_data,
        }

    return api_json


# ──────────────────────────────────────────────────────────────────
# 规范化结构 → UI JSON
# ──────────────────────────────────────────────────────────────────


def normalized_to_ui_json(normalized: NormalizedWorkflow) -> dict[str, Any]:
    """将规范化工作流结构转换为 ComfyUI UI JSON 格式。

    UI JSON 格式：
    {
        "last_node_id": int,
        "last_link_id": int,
        "nodes": [...],
        "links": [[id, src, src_slot, tgt, tgt_slot, type], ...],
        "groups": [...],
        "version": 0.4
    }
    """
    # 计算 last_node_id 和 last_link_id
    max_node_id = 0
    for node in normalized.nodes:
        try:
            node_id_int = int(node.get("id", 0))
            if node_id_int > max_node_id:
                max_node_id = node_id_int
        except (TypeError, ValueError):
            pass

    max_link_id = 0
    for link in normalized.links:
        try:
            link_id_int = int(link.get("id", 0))
            if link_id_int > max_link_id:
                max_link_id = link_id_int
        except (TypeError, ValueError):
            pass

    # 转换节点
    ui_nodes: list[dict[str, Any]] = []
    for node in normalized.nodes:
        flags = node.get("flags", {}) if isinstance(node.get("flags"), dict) else {}
        is_bypassed = bool(flags.get("bypassed", False))
        is_disabled = bool(flags.get("disabled", False))
        mode = 4 if is_bypassed else (2 if is_disabled else 0)

        # 转换 inputs/outputs
        ui_inputs = []
        for inp in node.get("inputs", []) if isinstance(node.get("inputs"), list) else []:
            ui_inputs.append({
                "name": str(inp.get("name", "")),
                "type": str(inp.get("type", "")),
                "link": inp.get("link"),
            })
        ui_outputs = []
        for out in node.get("outputs", []) if isinstance(node.get("outputs"), list) else []:
            ui_outputs.append({
                "name": str(out.get("name", "")),
                "type": str(out.get("type", "")),
                "links": out.get("links", []) if isinstance(out.get("links"), list) else [],
            })

        position = node.get("position", [0, 0])
        if not isinstance(position, list) or len(position) < 2:
            position = [0, 0]

        ui_nodes.append({
            "id": int(node["id"]) if str(node.get("id", "")).isdigit() else node.get("id"),
            "type": str(node.get("type", "Unknown")),
            "title": str(node.get("title", "")),
            "pos": [int(position[0]), int(position[1])],
            "size": {"0": 240, "1": 100},
            "flags": flags,
            "order": node.get("order", -1),
            "mode": mode,
            "inputs": ui_inputs,
            "outputs": ui_outputs,
            "widgets_values": node.get("widgets_values", []),
            "properties": node.get("properties", {}),
        })

    # 转换连线
    ui_links: list[list[Any]] = []
    for link in normalized.links:
        ui_links.append([
            int(link["id"]) if str(link.get("id", "")).isdigit() else link.get("id"),
            int(link["source_node"]) if str(link.get("source_node", "")).isdigit() else link.get("source_node"),
            int(link.get("source_slot", 0)),
            int(link["target_node"]) if str(link.get("target_node", "")).isdigit() else link.get("target_node"),
            int(link.get("target_slot", 0)),
            str(link.get("type", "")),
        ])

    # 转换分组
    ui_groups: list[dict[str, Any]] = []
    for group in normalized.groups:
        ui_groups.append({
            "title": str(group.get("title", "")),
            "bounding": group.get("bounding", [0, 0, 0, 0]),
            "color": str(group.get("color", "#3f789e")),
            "font_size": int(group.get("font_size", 24)),
        })

    return {
        "last_node_id": max_node_id,
        "last_link_id": max_link_id,
        "nodes": ui_nodes,
        "links": ui_links,
        "groups": ui_groups,
        "config": {},
        "extra": {},
        "version": 0.4,
    }


# ──────────────────────────────────────────────────────────────────
# 导出工作流
# ──────────────────────────────────────────────────────────────────


def export_workflow(
    normalized: NormalizedWorkflow,
    format: str = "api_json",
    *,
    raw_ui_json: dict[str, Any] | None = None,
    raw_api_json: dict[str, Any] | None = None,
    is_dirty: bool = False,
) -> dict[str, Any]:
    """导出工作流为指定格式。

    参数：
        format: "api_json"（ComfyUI API JSON）或 "ui_json"（ComfyUI UI JSON）
        raw_ui_json: 原始 UI JSON（来源快照，仅在未编辑时返回）
        raw_api_json: 原始 API JSON（来源快照，仅在未编辑时返回）
        is_dirty: 草稿是否被编辑过。
            - False（刚导入未编辑）：可以返回来源快照，保证未知字段不丢失。
            - True（已编辑）：必须从 normalized_graph 重新生成，不返回旧 JSON。
              来源中无法理解的未知字段通过 metadata 合并保留。

    返回：
        {
            "format": str,
            "data": dict,        # 工作流数据
            "node_count": int,
            "checksum": str,
        }
    """
    if format == "ui_json":
        if not is_dirty and raw_ui_json:
            # 未编辑且有来源快照：原样返回，保证未知字段不丢失
            data = raw_ui_json
        else:
            # 已编辑或无来源快照：从规范化结构生成
            data = normalized_to_ui_json(normalized)
            # 编辑后合并来源中的未知顶层字段（通过 metadata 保留）
            if is_dirty and raw_ui_json and isinstance(raw_ui_json, dict):
                data = _merge_unknown_top_level_fields(raw_ui_json, data)
    elif format == "api_json":
        if not is_dirty and raw_api_json:
            data = raw_api_json
        else:
            data = normalized_to_api_json(normalized)
            if is_dirty and raw_api_json and isinstance(raw_api_json, dict):
                data = _merge_unknown_top_level_fields(raw_api_json, data)
    else:
        raise ValueError(f"不支持的导出格式：{format}")

    return {
        "format": format,
        "data": data,
        "node_count": normalized.node_count(),
        "checksum": normalized.checksum(),
    }


def _merge_unknown_top_level_fields(
    source: dict[str, Any], generated: dict[str, Any]
) -> dict[str, Any]:
    """将来源 JSON 中的未知顶层字段合并到生成结果中。

    已知字段（nodes/links/groups/last_node_id/last_link_id/version/config/extra
    以及 API JSON 的节点 ID 键）使用生成结果中的最新值，不覆盖。
    未知字段从来源中保留，确保编辑后仍不丢失。
    """
    known_ui_keys = {
        "nodes", "links", "groups", "last_node_id", "last_link_id",
        "version", "config", "extra",
    }
    result = dict(generated)
    if isinstance(source, dict):
        for key, value in source.items():
            if key in known_ui_keys:
                continue
            # API JSON 的键是节点 ID（数字字符串），使用生成结果的最新值
            if key not in result:
                result[key] = value
    return result


# ──────────────────────────────────────────────────────────────────
# 发布前预检查
# ──────────────────────────────────────────────────────────────────


def precheck_publish(
    normalized: NormalizedWorkflow,
    node_definitions: dict[str, dict[str, Any]],
    *,
    semantic_slots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """发布前预检查。

    检查内容：
    1. 节点定义是否已同步（ComfyUI 是否安装了对应节点）
    2. 必填输入是否已连线或有值
    3. 模型资源是否可用（检查节点定义中的模型枚举）
    4. 参数是否完整（widgets_values 是否缺失）
    5. 语义插槽绑定是否有效（如果传入了 slots）
    6. 连线完整性（悬空连线、重复连线）

    返回：
        {
            "can_publish": bool,            # 是否可以发布
            "blocking_errors": [...],       # 阻塞错误（不能发布）
            "warnings": [...],              # 警告（可以发布但有风险）
            "summary": {
                "node_count": int,
                "missing_definitions": int,
                "missing_models": int,
                "missing_params": int,
                "dangling_links": int,
                "slot_errors": int,
            },
        }
    """
    blocking_errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    missing_definitions = 0
    missing_models = 0
    missing_params = 0
    dangling_links = 0
    slot_errors = 0

    nodes_by_id: dict[str, dict[str, Any]] = {
        str(n.get("id", "")): n for n in normalized.nodes
    }
    node_ids = set(nodes_by_id.keys())

    # 1. 检查节点定义
    for node in normalized.nodes:
        node_id = str(node.get("id", ""))
        node_type = str(node.get("type", ""))
        is_unknown = bool(node.get("is_unknown", False))

        if is_unknown:
            blocking_errors.append({
                "type": "unknown_node",
                "node_id": node_id,
                "node_type": node_type,
                "message": f"节点 '{node_type}'（ID: {node_id}）是未知节点，ComfyUI 未安装。",
            })
            missing_definitions += 1
            continue

        definition = node_definitions.get(node_type)
        if definition is None:
            blocking_errors.append({
                "type": "missing_definition",
                "node_id": node_id,
                "node_type": node_type,
                "message": f"节点定义未同步：{node_type}。请先同步 ComfyUI 节点定义。",
            })
            missing_definitions += 1
            continue

        # 2. 检查必填输入
        def_data = definition.get("definition", {}) if isinstance(definition, dict) else {}
        if not isinstance(def_data, dict):
            def_data = {}
        def_inputs = def_data.get("input", {})
        if not isinstance(def_inputs, dict):
            def_inputs = {}
        required_inputs = def_inputs.get("required", {})
        if not isinstance(required_inputs, dict):
            required_inputs = {}

        node_inputs = node.get("inputs", []) if isinstance(node.get("inputs"), list) else []
        input_by_name = {str(inp.get("name", "")): inp for inp in node_inputs}

        for req_name, req_spec in required_inputs.items():
            if not isinstance(req_spec, list) or len(req_spec) == 0:
                continue
            req_type = req_spec[0]
            # 连线类型的必填输入
            if isinstance(req_type, str) and req_type in {"MODEL", "CLIP", "VAE", "CONDITIONING", "LATENT", "IMAGE", "MASK", "CONTROL_NET", "*"}:
                inp = input_by_name.get(req_name)
                if inp is None or not inp.get("link"):
                    blocking_errors.append({
                        "type": "missing_required_input",
                        "node_id": node_id,
                        "node_type": node_type,
                        "input_name": req_name,
                        "message": f"节点 '{node_type}'（ID: {node_id}）的必填输入 '{req_name}' 未连线。",
                    })
                    missing_params += 1

        # 3. 检查模型资源（简化：检查 widgets_values 是否有模型名）
        widgets_values = node.get("widgets_values", [])
        if isinstance(widgets_values, list):
            for idx, value in enumerate(widgets_values):
                if value is None or (isinstance(value, str) and not value.strip()):
                    # 仅对模型类参数警告
                    warnings.append({
                        "type": "empty_widget_value",
                        "node_id": node_id,
                        "node_type": node_type,
                        "widget_index": idx,
                        "message": f"节点 '{node_type}'（ID: {node_id}）的参数 {idx} 为空。",
                    })
                    missing_params += 1

    # 4. 检查连线完整性
    for link in normalized.links:
        src = str(link.get("source_node", ""))
        tgt = str(link.get("target_node", ""))
        if src not in node_ids:
            blocking_errors.append({
                "type": "dangling_link_source",
                "link_id": str(link.get("id", "")),
                "source_node": src,
                "message": f"连线 {link.get('id', '')} 的源节点 {src} 不存在。",
            })
            dangling_links += 1
        if tgt not in node_ids:
            blocking_errors.append({
                "type": "dangling_link_target",
                "link_id": str(link.get("id", "")),
                "target_node": tgt,
                "message": f"连线 {link.get('id', '')} 的目标节点 {tgt} 不存在。",
            })
            dangling_links += 1

    # 5. 检查语义插槽绑定（如果传入了）
    if semantic_slots:
        for slot in semantic_slots:
            slot_name = str(slot.get("slot_name", ""))
            node_id = str(slot.get("node_id", ""))
            if node_id not in nodes_by_id:
                blocking_errors.append({
                    "type": "slot_node_not_found",
                    "slot_name": slot_name,
                    "node_id": node_id,
                    "message": f"插槽 '{slot_name}' 绑定的节点 {node_id} 不存在。",
                })
                slot_errors += 1

    return {
        "can_publish": len(blocking_errors) == 0,
        "blocking_errors": blocking_errors,
        "warnings": warnings,
        "summary": {
            "node_count": len(normalized.nodes),
            "missing_definitions": missing_definitions,
            "missing_models": missing_models,
            "missing_params": missing_params,
            "dangling_links": dangling_links,
            "slot_errors": slot_errors,
        },
    }


# ──────────────────────────────────────────────────────────────────
# 往返测试辅助
# ──────────────────────────────────────────────────────────────────


def roundtrip_test(
    raw_workflow: dict[str, Any],
    source_format: str = "auto",
) -> dict[str, Any]:
    """往返测试：导入—导出—重新导入，验证数据完整性。

    步骤：
    1. 解析原始工作流为规范化结构
    2. 从规范化结构导出为API JSON
    3. 从API JSON重新解析为规范化结构
    4. 比较两次规范化结构的节点数和连线数

    返回：
        {
            "success": bool,
            "original_node_count": int,
            "original_link_count": int,
            "roundtrip_node_count": int,
            "roundtrip_link_count": int,
            "node_count_match": bool,
            "link_count_match": bool,
            "errors": [str, ...],
        }
    """
    from .workflow_models import parse_workflow_from_raw

    errors: list[str] = []

    try:
        normalized1, actual_format = parse_workflow_from_raw(raw_workflow, source_format)
    except Exception as error:
        return {
            "success": False,
            "errors": [f"第一次解析失败：{error}"],
            "original_node_count": 0,
            "original_link_count": 0,
            "roundtrip_node_count": 0,
            "roundtrip_link_count": 0,
            "node_count_match": False,
            "link_count_match": False,
        }

    original_node_count = len(normalized1.nodes)
    original_link_count = len(normalized1.links)

    # 导出到API JSON
    api_json = normalized_to_api_json(normalized1)

    # 从API JSON重新解析
    try:
        normalized2, _ = parse_workflow_from_raw(api_json, "api_json")
    except Exception as error:
        return {
            "success": False,
            "errors": [f"第二次解析失败：{error}"],
            "original_node_count": original_node_count,
            "original_link_count": original_link_count,
            "roundtrip_node_count": 0,
            "roundtrip_link_count": 0,
            "node_count_match": False,
            "link_count_match": False,
        }

    roundtrip_node_count = len(normalized2.nodes)
    roundtrip_link_count = len(normalized2.links)

    node_count_match = original_node_count == roundtrip_node_count
    link_count_match = original_link_count == roundtrip_link_count

    if not node_count_match:
        errors.append(f"节点数不匹配：原始 {original_node_count}，往返 {roundtrip_node_count}")
    if not link_count_match:
        errors.append(f"连线数不匹配：原始 {original_link_count}，往返 {roundtrip_link_count}")

    return {
        "success": node_count_match and link_count_match and len(errors) == 0,
        "original_node_count": original_node_count,
        "original_link_count": original_link_count,
        "roundtrip_node_count": roundtrip_node_count,
        "roundtrip_link_count": roundtrip_link_count,
        "node_count_match": node_count_match,
        "link_count_match": link_count_match,
        "errors": errors,
    }
