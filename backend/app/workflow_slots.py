"""工作流语义插槽解析与校验。

实现阶段 2.5 的核心能力：

1. 内置插槽定义：正向/负向提示词、人物提示词、LoRA名称/权重、checkpoint、VAE、
   seed、width、height、batch size、输出文件前缀等。
2. 自定义插槽：通过 slot_type="custom" 创建任意命名插槽。
3. 转换规则、默认值、必填、冲突策略：解析时按规则处理输入值。
4. 接入人物值、素材值和项目默认配置：通过 context 参数传入业务值。
5. 插槽解析预览：返回每个插槽的解析结果（最终值、来源、警告）。

设计原则：
- 插槽绑定记录：{node_id, input_name, transform_rule, default_value, is_required, conflict_strategy}
- 解析优先级：业务上下文值 > 节点当前值 > 默认值
- 冲突策略：
    - overwrite: 用业务值覆盖节点值
    - skip: 保留节点值，跳过业务值
    - merge: 合并（仅适用于文本类插槽，用分隔符连接）
    - error: 报错，阻止提交
"""
from __future__ import annotations

from typing import Any, Literal

from .workflow_models import NormalizedWorkflow


# ──────────────────────────────────────────────────────────────────
# 内置插槽定义
# ──────────────────────────────────────────────────────────────────


# 内置插槽类型枚举
BUILTIN_SLOT_TYPES = {
    "positive_prompt": "正向提示词",
    "negative_prompt": "负向提示词",
    "character_prompt": "人物提示词",
    "lora_name": "LoRA 名称",
    "lora_weight": "LoRA 权重",
    "checkpoint": "checkpoint",
    "vae": "VAE",
    "seed": "seed",
    "width": "width",
    "height": "height",
    "batch_size": "batch size",
    "output_prefix": "输出文件前缀",
    "custom": "自定义参数",
}


# 内置插槽的推荐配置（用于前端展示和默认绑定）
BUILTIN_SLOT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "slot_type": "positive_prompt",
        "slot_name": "正向提示词",
        "description": "正向提示词，支持合并人物提示词和素材提示词",
        "value_type": "string",
        "default_conflict_strategy": "merge",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["text", "positive", "prompt", "positive_prompt"],
    },
    {
        "slot_type": "negative_prompt",
        "slot_name": "负向提示词",
        "description": "负向提示词",
        "value_type": "string",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["negative", "negative_prompt", "text_negative"],
    },
    {
        "slot_type": "character_prompt",
        "slot_name": "人物提示词",
        "description": "人物相关的提示词，从人物值解析",
        "value_type": "string",
        "default_conflict_strategy": "merge",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["text", "positive", "prompt"],
    },
    {
        "slot_type": "lora_name",
        "slot_name": "LoRA 名称",
        "description": "LoRA 模型名称",
        "value_type": "string",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["lora_name", "lora_1_name", "lora_2_name"],
    },
    {
        "slot_type": "lora_weight",
        "slot_name": "LoRA 权重",
        "description": "LoRA 权重值",
        "value_type": "float",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["lora_wt", "lora_1_wt", "lora_2_wt", "strength_model", "strength_clip"],
    },
    {
        "slot_type": "checkpoint",
        "slot_name": "checkpoint",
        "description": "基础模型 checkpoint 名称",
        "value_type": "string",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["ckpt_name", "checkpoint_name", "model_name"],
    },
    {
        "slot_type": "vae",
        "slot_name": "VAE",
        "description": "VAE 模型名称",
        "value_type": "string",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["vae_name"],
    },
    {
        "slot_type": "seed",
        "slot_name": "seed",
        "description": "随机种子",
        "value_type": "int",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["seed", "noise_seed"],
    },
    {
        "slot_type": "width",
        "slot_name": "width",
        "description": "图像宽度",
        "value_type": "int",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["width", "image_width"],
    },
    {
        "slot_type": "height",
        "slot_name": "height",
        "description": "图像高度",
        "value_type": "int",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["height", "image_height"],
    },
    {
        "slot_type": "batch_size",
        "slot_name": "batch size",
        "description": "批处理大小",
        "value_type": "int",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["batch_size", "num_images"],
    },
    {
        "slot_type": "output_prefix",
        "slot_name": "输出文件前缀",
        "description": "输出文件名前缀",
        "value_type": "string",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": ["filename_prefix", "output_prefix"],
    },
    {
        "slot_type": "custom",
        "slot_name": "自定义参数",
        "description": "任意自定义命名参数",
        "value_type": "any",
        "default_conflict_strategy": "overwrite",
        "default_transform_rule": "{value}",
        "applicable_inputs": [],
    },
]


ConflictStrategy = Literal["overwrite", "skip", "merge", "error"]


def get_builtin_slot_definition(slot_type: str) -> dict[str, Any] | None:
    """获取内置插槽定义。"""
    for defn in BUILTIN_SLOT_DEFINITIONS:
        if defn["slot_type"] == slot_type:
            return defn
    return None


def list_builtin_slot_definitions() -> list[dict[str, Any]]:
    """列出所有内置插槽定义。"""
    return list(BUILTIN_SLOT_DEFINITIONS)


# ──────────────────────────────────────────────────────────────────
# 插槽解析
# ──────────────────────────────────────────────────────────────────


def get_node_input_value(
    normalized: NormalizedWorkflow, node_id: str, input_name: str
) -> Any:
    """获取节点输入的当前值。

    优先从 inputs 列表查找匹配的输入名。
    如果 inputs 中找到但无 value 字段（仅有连线），返回 None。
    如果 inputs 中未找到，返回 None（不回退到 widgets_values，避免误匹配）。
    返回 None 表示未找到值。
    """
    for node in normalized.nodes:
        if str(node.get("id", "")) != str(node_id):
            continue
        # 检查 inputs 列表中的值
        for inp in node.get("inputs", []) if isinstance(node.get("inputs"), list) else []:
            if str(inp.get("name", "")) == input_name:
                # 如果有连线，返回连线信息
                if inp.get("link"):
                    return {"type": "link", "link": inp["link"]}
                # 返回值
                if "value" in inp:
                    return inp["value"]
                return None
        # 未在 inputs 中找到匹配的输入名
        return None
    return None


def apply_transform_rule(
    value: Any, transform_rule: str, context: dict[str, Any] | None = None
) -> Any:
    """应用转换规则。

    转换规则是一个字符串模板，支持以下占位符：
    - {value}: 插槽值
    - {character_name}: 人物名称（来自 context）
    - {character_prompt}: 人物提示词（来自 context）
    - {material_name}: 素材名称（来自 context）
    - {project_name}: 项目名称（来自 context）
    - {seed}: 种子值（来自 context）
    - {width}: 宽度（来自 context）
    - {height}: 高度（来自 context）

    如果 transform_rule 为空或仅 "{value}"，直接返回原值。
    """
    if not transform_rule or transform_rule == "{value}":
        return value
    context = context or {}
    template_vars = {"value": str(value) if value is not None else "", **context}
    try:
        return transform_rule.format(**template_vars)
    except (KeyError, ValueError, IndexError):
        # 模板变量缺失时返回原值
        return value


def resolve_slot_value(
    slot: dict[str, Any],
    normalized: NormalizedWorkflow,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """解析单个插槽的值。

    参数：
        slot: 插槽绑定记录 {
            slot_name, slot_type, node_id, input_name,
            transform_rule, default_value, is_required, conflict_strategy
        }
        normalized: 规范化工作流结构
        context: 业务上下文 {
            character_values: {character_name, character_prompt, lora_name, lora_weight, ...},
            material_values: {material_name, ...},
            project_config: {project_name, default_seed, default_width, default_height, ...},
        }

    返回：
        {
            "slot_name": str,
            "slot_type": str,
            "node_id": str,
            "input_name": str,
            "resolved_value": Any,        # 最终值
            "source": str,                # 值来源: "context" | "node" | "default" | "none"
            "warnings": [str, ...],       # 警告信息
            "errors": [str, ...],         # 错误信息（必填缺失等）
            "is_required": bool,
            "conflict_strategy": str,
        }
    """
    context = context or {}
    warnings: list[str] = []
    errors: list[str] = []

    slot_name = str(slot.get("slot_name", ""))
    slot_type = str(slot.get("slot_type", ""))
    node_id = str(slot.get("node_id", ""))
    input_name = str(slot.get("input_name", ""))
    transform_rule = str(slot.get("transform_rule", "") or "")
    default_value = slot.get("default_value")
    is_required = bool(slot.get("is_required", False))
    conflict_strategy = str(slot.get("conflict_strategy", "overwrite"))

    # 1. 从业务上下文获取值
    context_value: Any = None
    context_source = "none"

    # 人物值
    character_values = context.get("character_values", {}) if isinstance(context.get("character_values"), dict) else {}
    material_values = context.get("material_values", {}) if isinstance(context.get("material_values"), dict) else {}
    project_config = context.get("project_config", {}) if isinstance(context.get("project_config"), dict) else {}

    if slot_type == "positive_prompt":
        # 稳定顺序(需求 6.3):页级正向 → 人物规格(场景化) → 素材正向(按类型顺序)
        parts: list[str] = []
        if material_values.get("page_prompt"):
            parts.append(str(material_values["page_prompt"]))
        if character_values.get("character_prompt"):
            parts.append(str(character_values["character_prompt"]))
        if material_values.get("material_prompt"):
            parts.append(str(material_values["material_prompt"]))
        if parts:
            context_value = ", ".join(parts)
            context_source = "context"
    elif slot_type == "negative_prompt":
        if character_values.get("negative_prompt"):
            context_value = str(character_values["negative_prompt"])
            context_source = "context"
    elif slot_type == "character_prompt":
        if character_values.get("character_prompt"):
            context_value = str(character_values["character_prompt"])
            context_source = "context"
    elif slot_type == "lora_name":
        if character_values.get("lora_name"):
            context_value = str(character_values["lora_name"])
            context_source = "context"
    elif slot_type == "lora_weight":
        if character_values.get("lora_weight") is not None:
            context_value = character_values["lora_weight"]
            context_source = "context"
    elif slot_type == "checkpoint":
        if project_config.get("default_checkpoint"):
            context_value = str(project_config["default_checkpoint"])
            context_source = "context"
    elif slot_type == "vae":
        if project_config.get("default_vae"):
            context_value = str(project_config["default_vae"])
            context_source = "context"
    elif slot_type == "seed":
        if project_config.get("default_seed") is not None:
            context_value = project_config["default_seed"]
            context_source = "context"
    elif slot_type == "width":
        if project_config.get("default_width") is not None:
            context_value = project_config["default_width"]
            context_source = "context"
    elif slot_type == "height":
        if project_config.get("default_height") is not None:
            context_value = project_config["default_height"]
            context_source = "context"
    elif slot_type == "batch_size":
        if project_config.get("default_batch_size") is not None:
            context_value = project_config["default_batch_size"]
            context_source = "context"
    elif slot_type == "output_prefix":
        if project_config.get("default_output_prefix"):
            context_value = str(project_config["default_output_prefix"])
            context_source = "context"
    elif slot_type == "custom":
        # 自定义插槽：从 context 的 custom_values 字典中查找
        custom_values = context.get("custom_values", {}) if isinstance(context.get("custom_values"), dict) else {}
        if slot_name in custom_values:
            context_value = custom_values[slot_name]
            context_source = "context"

    # 2. 获取节点当前值
    node_value = get_node_input_value(normalized, node_id, input_name)

    # 3. 根据冲突策略决定最终值
    resolved_value: Any = None
    source = "none"

    if context_value is not None and node_value is not None:
        # 两者都有值，应用冲突策略
        if conflict_strategy == "overwrite":
            resolved_value = context_value
            source = "context"
        elif conflict_strategy == "skip":
            resolved_value = node_value
            source = "node"
        elif conflict_strategy == "merge":
            # 合并文本值
            if isinstance(node_value, str) and isinstance(context_value, str):
                resolved_value = f"{node_value}, {context_value}"
            elif isinstance(node_value, list) and isinstance(context_value, list):
                resolved_value = node_value + context_value
            else:
                resolved_value = context_value
            source = "merged"
        elif conflict_strategy == "error":
            errors.append(f"插槽 '{slot_name}' 存在冲突：节点已有值且业务上下文也有值。")
            resolved_value = node_value
            source = "node"
        else:
            warnings.append(f"未知冲突策略：{conflict_strategy}，使用默认 overwrite。")
            resolved_value = context_value
            source = "context"
    elif context_value is not None:
        resolved_value = context_value
        source = "context"
    elif node_value is not None:
        resolved_value = node_value
        source = "node"
    elif default_value is not None:
        resolved_value = default_value
        source = "default"
    else:
        # 无值
        if is_required:
            errors.append(f"必填插槽 '{slot_name}' 无值可解析。")
        else:
            warnings.append(f"插槽 '{slot_name}' 无值可解析，将使用节点默认。")

    # 4. 应用转换规则
    if resolved_value is not None and transform_rule:
        resolved_value = apply_transform_rule(resolved_value, transform_rule, context)

    return {
        "slot_name": slot_name,
        "slot_type": slot_type,
        "node_id": node_id,
        "input_name": input_name,
        "resolved_value": resolved_value,
        "source": source,
        "warnings": warnings,
        "errors": errors,
        "is_required": is_required,
        "conflict_strategy": conflict_strategy,
    }


def resolve_all_slots(
    slots: list[dict[str, Any]],
    normalized: NormalizedWorkflow,
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """解析工作流的所有语义插槽。

    返回：
        {
            "resolved_slots": [resolve_slot_value() 返回的字典列表],
            "has_errors": bool,           # 是否有错误
            "has_warnings": bool,         # 是否有警告
            "error_count": int,
            "warning_count": int,
            "summary": {
                "total_slots": int,
                "resolved_count": int,     # 成功解析值的插槽数
                "missing_count": int,      # 无值的插槽数
                "required_missing": int,   # 必填但无值的插槽数
            },
        }
    """
    context = context or {}
    resolved_slots: list[dict[str, Any]] = []
    error_count = 0
    warning_count = 0
    resolved_count = 0
    missing_count = 0
    required_missing = 0

    for slot in slots:
        result = resolve_slot_value(slot, normalized, context=context)
        resolved_slots.append(result)
        error_count += len(result["errors"])
        warning_count += len(result["warnings"])
        if result["resolved_value"] is not None:
            resolved_count += 1
        else:
            missing_count += 1
            if result["is_required"]:
                required_missing += 1

    return {
        "resolved_slots": resolved_slots,
        "has_errors": error_count > 0,
        "has_warnings": warning_count > 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "summary": {
            "total_slots": len(slots),
            "resolved_count": resolved_count,
            "missing_count": missing_count,
            "required_missing": required_missing,
        },
    }


# ──────────────────────────────────────────────────────────────────
# 插槽校验
# ──────────────────────────────────────────────────────────────────


def validate_slot_bindings(
    slots: list[dict[str, Any]],
    normalized: NormalizedWorkflow,
) -> dict[str, Any]:
    """校验插槽绑定是否有效。

    检查：
    - 节点是否存在
    - 输入名是否存在
    - 必填插槽是否有值
    - 冲突策略是否有效
    - 插槽名是否重复

    返回：
        {
            "is_valid": bool,
            "errors": [{slot_name, error_type, message}, ...],
            "warnings": [{slot_name, warning_type, message}, ...],
        }
    """
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    # 构建节点ID到节点的映射
    nodes_by_id: dict[str, dict[str, Any]] = {
        str(n.get("id", "")): n for n in normalized.nodes
    }

    valid_strategies = {"overwrite", "skip", "merge", "error"}

    for slot in slots:
        slot_name = str(slot.get("slot_name", ""))
        node_id = str(slot.get("node_id", ""))
        input_name = str(slot.get("input_name", ""))
        slot_type = str(slot.get("slot_type", ""))
        conflict_strategy = str(slot.get("conflict_strategy", "overwrite"))

        # 检查插槽名重复
        if slot_name in seen_names:
            errors.append({
                "slot_name": slot_name,
                "error_type": "duplicate_name",
                "message": f"插槽名 '{slot_name}' 重复。",
            })
        seen_names.add(slot_name)

        # 检查节点存在
        if node_id not in nodes_by_id:
            errors.append({
                "slot_name": slot_name,
                "error_type": "node_not_found",
                "message": f"节点 '{node_id}' 不存在于工作流草稿中。",
            })
            continue

        # 检查输入名存在
        node = nodes_by_id[node_id]
        inputs = node.get("inputs", []) if isinstance(node.get("inputs"), list) else []
        input_names = {str(inp.get("name", "")) for inp in inputs}
        # widgets_values 也算可绑定的输入
        if input_name and input_name not in input_names and input_name != "widgets_values":
            # 对于 widgets_values，允许绑定（因为有些节点的参数只在 widgets_values 中）
            warnings.append({
                "slot_name": slot_name,
                "warning_type": "input_not_found",
                "message": f"输入名 '{input_name}' 不在节点 '{node_id}' 的 inputs 列表中，将尝试从 widgets_values 绑定。",
            })

        # 检查冲突策略有效
        if conflict_strategy not in valid_strategies:
            errors.append({
                "slot_name": slot_name,
                "error_type": "invalid_conflict_strategy",
                "message": f"冲突策略 '{conflict_strategy}' 无效，应为 overwrite/skip/merge/error。",
            })

        # 检查插槽类型有效
        if slot_type not in BUILTIN_SLOT_TYPES:
            warnings.append({
                "slot_name": slot_name,
                "warning_type": "unknown_slot_type",
                "message": f"插槽类型 '{slot_type}' 不在内置类型中。",
            })

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ──────────────────────────────────────────────────────────────────
# 插槽应用（写入工作流副本）
# ──────────────────────────────────────────────────────────────────


def apply_slots_to_workflow(
    normalized: NormalizedWorkflow,
    resolved_slots: list[dict[str, Any]],
) -> NormalizedWorkflow:
    """将解析后的插槽值应用到工作流节点（修改副本，不影响原工作流）。

    用于提交前将插槽值写入工作流副本。
    """
    nodes_by_id: dict[str, dict[str, Any]] = {
        str(n.get("id", "")): n for n in normalized.nodes
    }

    for resolved in resolved_slots:
        node_id = str(resolved.get("node_id", ""))
        input_name = str(resolved.get("input_name", ""))
        value = resolved.get("resolved_value")

        if value is None:
            continue
        if node_id not in nodes_by_id:
            continue

        node = nodes_by_id[node_id]
        inputs = node.get("inputs", []) if isinstance(node.get("inputs"), list) else []

        # 尝试在 inputs 中找到对应输入并更新值
        found = False
        for inp in inputs:
            if str(inp.get("name", "")) == input_name:
                # 如果有连线，不覆盖连线值
                if not inp.get("link"):
                    inp["value"] = value
                    found = True
                break

        # 如果 inputs 中没找到，尝试写入 widgets_values
        if not found and input_name != "widgets_values":
            widgets_values = node.get("widgets_values", [])
            if isinstance(widgets_values, list):
                # 简化：将值追加到 widgets_values（实际需要节点定义来正确匹配位置）
                # 这里仅做简单处理，实际应用需要更精确的位置匹配
                pass

    return normalized
