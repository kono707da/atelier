"""工作流规范化结构与导入解析器。

ComfyUI 工作流有两种原生格式：
- UI JSON：前端画布格式（节点位置、大小、连线、分组等可视化信息）
- API JSON：后端执行格式（节点ID、类型、输入值和连线）

本模块负责：
1. 解析 UI JSON 和 API JSON 为内部规范化结构
2. 保留原始 JSON 和未知字段
3. 从 PNG/WebP 图片元数据提取工作流
4. 规范化结构的序列化与反序列化

规范化结构设计原则：
- 不丢失原始数据：raw_ui_json 和 raw_api_json 独立保存
- 统一访问：normalized_graph 提供节点/连线的统一视图
- 未知节点保留：以 is_unknown 标记，保留原始 JSON
- 幂等：同一输入重复解析结果一致
"""
from __future__ import annotations

import hashlib
import io
import json
import struct
import zipfile
from dataclasses import dataclass, field
from typing import Any

from PIL import Image


class WorkflowParseError(ValueError):
    """工作流解析失败的统一异常。"""


@dataclass
class NormalizedWorkflow:
    """规范化工作流结构。

    统一 UI JSON 和 API JSON 的差异，提供一致的节点/连线视图。
    """

    nodes: list[dict[str, Any]] = field(default_factory=list)
    links: list[dict[str, Any]] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "links": self.links,
            "groups": self.groups,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedWorkflow:
        return cls(
            nodes=data.get("nodes", []),
            links=data.get("links", []),
            groups=data.get("groups", []),
            metadata=data.get("metadata", {}),
        )

    def node_count(self) -> int:
        return len(self.nodes)

    def checksum(self) -> str:
        """计算规范化结构的校验和，用于版本比对。"""
        canonical = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_ui_json(raw: dict[str, Any]) -> NormalizedWorkflow:
    """解析 ComfyUI UI JSON（前端画布格式）。

    UI JSON 结构：
    {
        "last_node_id": 10,
        "last_link_id": 15,
        "nodes": [
            {
                "id": 1,
                "type": "CheckpointLoaderSimple",
                "title": "Load Checkpoint",
                "pos": [100, 200],
                "size": {"0": 300, "1": 100},
                "flags": {},
                "order": 0,
                "mode": 0,
                "inputs": [{"name": "...", "type": "...", "link": null}],
                "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
                "properties": {},
                "widgets_values": ["model.safetensors"],
            }
        ],
        "links": [
            [1, 1, 0, 2, 0, "MODEL"]
        ],
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4
    }
    """
    if not isinstance(raw, dict):
        raise WorkflowParseError("UI JSON 必须是对象。")
    if "nodes" not in raw:
        raise WorkflowParseError("UI JSON 缺少 nodes 字段。")

    nodes: list[dict[str, Any]] = []
    raw_nodes = raw.get("nodes", [])
    if not isinstance(raw_nodes, list):
        raise WorkflowParseError("UI JSON nodes 字段必须是数组。")

    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            continue
        node_id = str(raw_node.get("id", ""))
        node_type = str(raw_node.get("type", "Unknown"))
        title = raw_node.get("title") or node_type
        pos = raw_node.get("pos", [0, 0])
        if isinstance(pos, dict):
            pos = [pos.get("0", 0), pos.get("1", 0)]
        size = raw_node.get("size", [0, 0])
        if isinstance(size, dict):
            size = [size.get("0", 0), size.get("1", 0)]
        mode = raw_node.get("mode", 0)
        flags = raw_node.get("flags", {})
        is_bypassed = mode == 4 or bool(flags.get("bypass", False))
        is_disabled = mode == 2 or bool(flags.get("disabled", False))
        widgets_values = raw_node.get("widgets_values", [])
        properties = raw_node.get("properties", {})

        inputs = _normalize_ui_ports(raw_node.get("inputs", []))
        outputs = _normalize_ui_ports(raw_node.get("outputs", []))

        nodes.append({
            "id": node_id,
            "type": node_type,
            "title": str(title),
            "position": [int(pos[0]) if pos and len(pos) > 0 else 0,
                         int(pos[1]) if pos and len(pos) > 1 else 0],
            "size": [int(size[0]) if size and len(size) > 0 else 0,
                     int(size[1]) if size and len(size) > 1 else 0],
            "mode": int(mode),
            "flags": {
                "enabled": not is_disabled and not is_bypassed,
                "bypassed": is_bypassed,
                "disabled": is_disabled,
            },
            "widgets_values": widgets_values if isinstance(widgets_values, list) else [],
            "properties": properties if isinstance(properties, dict) else {},
            "inputs": inputs,
            "outputs": outputs,
            "order": raw_node.get("order", -1),
            "is_unknown": False,
            "raw": raw_node,
        })

    links: list[dict[str, Any]] = []
    raw_links = raw.get("links", [])
    if isinstance(raw_links, list):
        for raw_link in raw_links:
            if not isinstance(raw_link, (list, tuple)) or len(raw_link) < 6:
                continue
            links.append({
                "id": str(raw_link[0]),
                "source_node": str(raw_link[1]),
                "source_slot": int(raw_link[2]),
                "target_node": str(raw_link[3]),
                "target_slot": int(raw_link[4]),
                "type": str(raw_link[5]),
            })

    groups: list[dict[str, Any]] = []
    raw_groups = raw.get("groups", [])
    if isinstance(raw_groups, list):
        for raw_group in raw_groups:
            if isinstance(raw_group, dict):
                groups.append({
                    "title": str(raw_group.get("title", "")),
                    "bounding": raw_group.get("bounding", [0, 0, 0, 0]),
                    "color": str(raw_group.get("color", "#3f789e")),
                    "font_size": int(raw_group.get("font_size", 24)),
                })

    return NormalizedWorkflow(
        nodes=nodes,
        links=links,
        groups=groups,
        metadata={
            "source_format": "ui_json",
            "last_node_id": raw.get("last_node_id"),
            "last_link_id": raw.get("last_link_id"),
            "version": raw.get("version"),
            "extra": raw.get("extra", {}),
            "config": raw.get("config", {}),
        },
    )


def _normalize_ui_ports(ports: Any) -> list[dict[str, Any]]:
    if not isinstance(ports, list):
        return []
    result: list[dict[str, Any]] = []
    for port in ports:
        if isinstance(port, dict):
            result.append({
                "name": str(port.get("name", "")),
                "type": str(port.get("type", "")),
                "link": port.get("link"),
                "links": port.get("links", []) if isinstance(port.get("links"), list) else [],
                "slot_index": port.get("slot_index"),
            })
    return result


def parse_api_json(raw: dict[str, Any]) -> NormalizedWorkflow:
    """解析 ComfyUI API JSON（后端执行格式）。

    API JSON 结构：
    {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "model.safetensors"
            }
        },
        "2": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "seed": 12345,
                ...
            }
        }
    }
    """
    if not isinstance(raw, dict):
        raise WorkflowParseError("API JSON 必须是对象。")

    nodes: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    link_id = 0

    for node_id, node_data in raw.items():
        if not isinstance(node_data, dict):
            continue
        class_type = str(node_data.get("class_type", "Unknown"))
        inputs_data = node_data.get("inputs", {})
        if not isinstance(inputs_data, dict):
            inputs_data = {}

        inputs: list[dict[str, Any]] = []
        widgets_values: list[Any] = []
        for input_name, input_value in inputs_data.items():
            if isinstance(input_value, list) and len(input_value) == 2:
                source_node = str(input_value[0])
                source_slot = int(input_value[1])
                link_id += 1
                links.append({
                    "id": str(link_id),
                    "source_node": source_node,
                    "source_slot": source_slot,
                    "target_node": str(node_id),
                    "target_slot": len(inputs),
                    "type": "",
                })
                inputs.append({
                    "name": input_name,
                    "type": "",
                    "link": link_id,
                })
            else:
                widgets_values.append(input_value)
                inputs.append({
                    "name": input_name,
                    "type": _infer_value_type(input_value),
                    "value": input_value,
                })

        nodes.append({
            "id": str(node_id),
            "type": class_type,
            "title": class_type,
            "position": [0, 0],
            "size": [0, 0],
            "mode": 0,
            "flags": {"enabled": True, "bypassed": False, "disabled": False},
            "widgets_values": widgets_values,
            "properties": {},
            "inputs": inputs,
            "outputs": [],
            "order": -1,
            "is_unknown": False,
            "raw": node_data,
        })

    # API JSON 不包含输出端口定义，根据已建立的连线推导输出端口。
    # 否则导入后无法新增连线（create_link 校验源节点输出端口存在性）。
    node_outputs: dict[str, list[dict[str, Any]]] = {}
    for link in links:
        src_node = str(link.get("source_node", ""))
        src_slot = int(link.get("source_slot", 0))
        if src_node not in node_outputs:
            node_outputs[src_node] = []
        while len(node_outputs[src_node]) <= src_slot:
            node_outputs[src_node].append({"name": "", "type": "*", "links": []})
        if link.get("id") not in node_outputs[src_node][src_slot]["links"]:
            node_outputs[src_node][src_slot]["links"].append(link["id"])
    for node in nodes:
        nid = str(node.get("id", ""))
        if nid in node_outputs:
            node["outputs"] = node_outputs[nid]

    return NormalizedWorkflow(
        nodes=nodes,
        links=links,
        groups=[],
        metadata={
            "source_format": "api_json",
        },
    )


def _infer_value_type(value: Any) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INT"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, str):
        return "STRING"
    return "*"


def extract_workflow_from_image(image_bytes: bytes) -> dict[str, Any]:
    """从 PNG/WebP 图片元数据提取 ComfyUI 工作流。

    ComfyUI 在生成的图片中嵌入工作流信息：
    - PNG：嵌入到 tEXt/iTXt chunk，key 为 "workflow"（UI JSON）或 "prompt"（API JSON）
    - WebP：嵌入到 EXIF 数据中

    返回 {"ui_json": ..., "api_json": ...}，其中可能有 None。
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as error:
        raise WorkflowParseError(f"无法读取图片：{error}") from error

    result: dict[str, Any] = {"ui_json": None, "api_json": None}

    # PNG text chunks
    if image.format == "PNG":
        info = image.info or {}
        if isinstance(info.get("workflow"), str):
            try:
                result["ui_json"] = json.loads(info["workflow"])
            except (TypeError, ValueError):
                pass
        if isinstance(info.get("prompt"), str):
            try:
                result["api_json"] = json.loads(info["prompt"])
            except (TypeError, ValueError):
                pass
        if isinstance(info.get("parameters"), str) and not result["ui_json"]:
            try:
                result["api_json"] = json.loads(info["parameters"])
            except (TypeError, ValueError):
                pass

    # WebP EXIF
    if image.format == "WEBP":
        exif_data = image.info.get("exif")
        if exif_data:
            try:
                extracted = _extract_from_exif(exif_data)
                if extracted.get("ui_json"):
                    result["ui_json"] = extracted["ui_json"]
                if extracted.get("api_json"):
                    result["api_json"] = extracted["api_json"]
            except Exception:
                pass

    if not result["ui_json"] and not result["api_json"]:
        raise WorkflowParseError("图片中未找到 ComfyUI 工作流元数据。")

    return result


def _extract_from_exif(exif_data: bytes) -> dict[str, Any]:
    """从 EXIF 数据中提取 ComfyUI 工作流。

    ComfyUI WebP 图片将工作流嵌入 EXIF UserComment 字段。
    """
    result: dict[str, Any] = {"ui_json": None, "api_json": None}
    try:
        if exif_data[:4] == b"Exif":
            exif_data = exif_data[6:]
        with io.BytesIO(exif_data) as buf:
            segments = _parse_exif_segments(buf)
            for key, value in segments.items():
                if key in ("workflow", "Workflow"):
                    try:
                        result["ui_json"] = json.loads(value)
                    except (TypeError, ValueError):
                        pass
                elif key in ("prompt", "Prompt", "parameters"):
                    try:
                        result["api_json"] = json.loads(value)
                    except (TypeError, ValueError):
                        pass
    except Exception:
        pass
    return result


def _parse_exif_segments(buf: io.BytesIO) -> dict[str, str]:
    """简单解析 EXIF 数据段，提取文本字段。"""
    result: dict[str, str] = {}
    try:
        data = buf.read()
        # 尝试在 EXIF 数据中查找 JSON 字符串
        text = data.decode("utf-8", errors="ignore")
        # 查找 "workflow" 和 "prompt" 标记
        for marker in ('"workflow"', '"prompt"', '"parameters"'):
            idx = text.find(marker)
            if idx >= 0:
                # 查找 JSON 值的开始
                colon_idx = text.find(":", idx)
                if colon_idx < 0:
                    continue
                start = colon_idx + 1
                while start < len(text) and text[start] in ' \t\n\r':
                    start += 1
                if start < len(text) and text[start] == "{":
                    # 查找匹配的右花括号
                    depth = 0
                    end = start
                    for i in range(start, len(text)):
                        if text[i] == "{":
                            depth += 1
                        elif text[i] == "}":
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                break
                    key = marker.strip('"')
                    result[key] = text[start:end]
    except Exception:
        pass
    return result


def parse_workflow_from_raw(
    raw: dict[str, Any],
    source_format: str = "ui_json",
) -> tuple[NormalizedWorkflow, str]:
    """根据格式解析工作流，返回规范化结构和实际格式。

    自动检测：如果 source_format 为 "auto"，根据结构特征判断。
    """
    if source_format == "auto":
        source_format = detect_format(raw)

    if source_format == "ui_json":
        return parse_ui_json(raw), "ui_json"
    if source_format == "api_json":
        return parse_api_json(raw), "api_json"
    raise WorkflowParseError(f"不支持的工作流格式：{source_format}")


def detect_format(raw: dict[str, Any]) -> str:
    """自动检测工作流格式。"""
    if not isinstance(raw, dict):
        raise WorkflowParseError("工作流数据必须是对象。")
    if "nodes" in raw and isinstance(raw.get("nodes"), list):
        return "ui_json"
    # API JSON 的特征：键是节点ID，值包含 class_type
    for key, value in raw.items():
        if isinstance(value, dict) and "class_type" in value:
            return "api_json"
    raise WorkflowParseError("无法识别工作流格式。")


def serialize_workflow(
    normalized: NormalizedWorkflow,
    raw_ui_json: dict[str, Any] | None = None,
    raw_api_json: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """序列化工作流为存储格式。"""
    return {
        "normalized": normalized.to_dict(),
        "raw_ui_json": raw_ui_json,
        "raw_api_json": raw_api_json,
        "node_count": normalized.node_count(),
        "checksum": normalized.checksum(),
    }


def deserialize_workflow(data: dict[str, Any]) -> tuple[NormalizedWorkflow, dict[str, Any] | None, dict[str, Any] | None]:
    """反序列化存储的工作流数据。"""
    normalized = NormalizedWorkflow.from_dict(data.get("normalized", {}))
    raw_ui_json = data.get("raw_ui_json")
    raw_api_json = data.get("raw_api_json")
    return normalized, raw_ui_json, raw_api_json


# ──────────────────────────────────────────────────────────────────
# 节点编辑器：校验、ID 分配、节点操作工具
# ──────────────────────────────────────────────────────────────────


def allocate_node_id(normalized: NormalizedWorkflow, last_node_id: int = 0) -> tuple[str, int]:
    """分配新的节点 ID。返回 (new_id, new_last_node_id)。

    规则：取 max(existing_ids, last_node_id) + 1。
    """
    max_id = int(last_node_id or 0)
    for node in normalized.nodes:
        try:
            node_id_int = int(node.get("id", 0))
        except (TypeError, ValueError):
            continue
        if node_id_int > max_id:
            max_id = node_id_int
    new_id = max_id + 1
    return str(new_id), new_id


def allocate_link_id(normalized: NormalizedWorkflow, last_link_id: int = 0) -> tuple[str, int]:
    """分配新的连线 ID。返回 (new_id, new_last_link_id)。"""
    max_id = int(last_link_id or 0)
    for link in normalized.links:
        try:
            link_id_int = int(link.get("id", 0))
        except (TypeError, ValueError):
            continue
        if link_id_int > max_id:
            max_id = link_id_int
    new_id = max_id + 1
    return str(new_id), new_id


def validate_workflow(
    normalized: NormalizedWorkflow,
    node_definitions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """校验工作流草稿。

    参数：
        normalized: 规范化工作流结构
        node_definitions: {node_class: definition_dict} 字典，来自 batch_get_node_definitions

    返回：
        {
            "is_valid": bool,
            "errors": [{"node_id", "node_class", "input_name", "error_type", "message"}],
            "warnings": [{"node_id", "node_class", "input_name", "warning_type", "message"}],
            "stats": {"node_count", "link_count", "unknown_count", "custom_count", "disabled_count", "bypassed_count"},
            "missing_definitions": [node_class, ...],
        }
    """
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    nodes_by_id: dict[str, dict[str, Any]] = {}
    missing_definitions: list[str] = []
    unknown_count = 0
    custom_count = 0
    disabled_count = 0
    bypassed_count = 0

    for node in normalized.nodes:
        node_id = str(node.get("id", ""))
        nodes_by_id[node_id] = node
        node_class = str(node.get("type", ""))
        flags = node.get("flags", {}) if isinstance(node.get("flags"), dict) else {}
        is_disabled = bool(flags.get("disabled", False))
        is_bypassed = bool(flags.get("bypassed", False))
        if is_disabled:
            disabled_count += 1
        if is_bypassed:
            bypassed_count += 1

        if node.get("is_unknown"):
            unknown_count += 1
            errors.append({
                "node_id": node_id,
                "node_class": node_class,
                "input_name": "",
                "error_type": "unknown_node",
                "message": f"未知节点类型 {node_class}，ComfyUI 未安装该节点。将以只读模式保留原始数据。",
            })
            continue

        definition = node_definitions.get(node_class)
        if definition is None:
            if node_class not in missing_definitions:
                missing_definitions.append(node_class)
            errors.append({
                "node_id": node_id,
                "node_class": node_class,
                "input_name": "",
                "error_type": "missing_definition",
                "message": f"节点定义未同步：{node_class}。请先同步 ComfyUI 节点定义。",
            })
            continue

        if definition.get("is_custom_node"):
            custom_count += 1

        # 校验必填输入是否已连线
        def_inputs = definition.get("definition", {}).get("input", {})
        if not isinstance(def_inputs, dict):
            def_inputs = {}
        required_inputs = def_inputs.get("required", {})
        if not isinstance(required_inputs, dict):
            required_inputs = {}
        optional_inputs = def_inputs.get("optional", {})
        if not isinstance(optional_inputs, dict):
            optional_inputs = {}

        # 收集节点的实际输入（连线状态）
        actual_inputs = node.get("inputs", []) if isinstance(node.get("inputs"), list) else []
        actual_input_by_name: dict[str, dict[str, Any]] = {}
        for inp in actual_inputs:
            if isinstance(inp, dict):
                name = str(inp.get("name", ""))
                if name:
                    actual_input_by_name[name] = inp

        widgets = node.get("widgets_values", []) if isinstance(node.get("widgets_values"), list) else []

        # 校验必填输入
        widget_index = 0
        for input_name, input_spec in required_inputs.items():
            if not isinstance(input_spec, list) or len(input_spec) == 0:
                continue
            input_type = input_spec[0]
            actual = actual_input_by_name.get(input_name)
            # 连线类型输入：检查是否已连线
            if isinstance(input_type, list) or input_type in {"MODEL", "CLIP", "VAE", "CONDITIONING", "LATENT", "IMAGE", "MASK", "CONTROL_NET", "*"}:
                if actual is None or not actual.get("link"):
                    warnings.append({
                        "node_id": node_id,
                        "node_class": node_class,
                        "input_name": input_name,
                        "warning_type": "unconnected_required_input",
                        "message": f"必填输入 {input_name}（{input_type}）未连线。",
                    })
            else:
                # 值类型输入：检查 widgets_values 是否有值
                if widget_index >= len(widgets):
                    warnings.append({
                        "node_id": node_id,
                        "node_class": node_class,
                        "input_name": input_name,
                        "warning_type": "missing_widget_value",
                        "message": f"参数 {input_name} 缺少值。",
                    })
                widget_index += 1

    # 校验连线完整性
    for link in normalized.links:
        link_id = str(link.get("id", ""))
        source_node = str(link.get("source_node", ""))
        target_node = str(link.get("target_node", ""))
        if source_node not in nodes_by_id:
            errors.append({
                "node_id": target_node,
                "node_class": nodes_by_id.get(target_node, {}).get("type", ""),
                "input_name": "",
                "error_type": "dangling_source",
                "message": f"连线 {link_id} 的源节点 {source_node} 不存在。",
            })
            continue
        if target_node not in nodes_by_id:
            errors.append({
                "node_id": source_node,
                "node_class": nodes_by_id.get(source_node, {}).get("type", ""),
                "input_name": "",
                "error_type": "dangling_target",
                "message": f"连线 {link_id} 的目标节点 {target_node} 不存在。",
            })

    # 检查重复连线
    seen_links: set[tuple[str, int, str, int]] = set()
    for link in normalized.links:
        try:
            key = (
                str(link.get("source_node", "")),
                int(link.get("source_slot", 0)),
                str(link.get("target_node", "")),
                int(link.get("target_slot", 0)),
            )
        except (TypeError, ValueError):
            continue
        if key in seen_links:
            warnings.append({
                "node_id": key[2],
                "node_class": nodes_by_id.get(key[2], {}).get("type", ""),
                "input_name": "",
                "warning_type": "duplicate_link",
                "message": f"重复连线：{key[0]}:{key[1]} → {key[2]}:{key[3]}。",
            })
        seen_links.add(key)

    stats = {
        "node_count": len(normalized.nodes),
        "link_count": len(normalized.links),
        "unknown_count": unknown_count,
        "custom_count": custom_count,
        "disabled_count": disabled_count,
        "bypassed_count": bypassed_count,
    }
    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
        "missing_definitions": missing_definitions,
    }


def build_default_node(
    node_class: str,
    definition: dict[str, Any] | None,
    *,
    node_id: str,
    position: tuple[int, int] = (0, 0),
) -> dict[str, Any]:
    """根据节点定义构建默认节点实例。

    用于节点编辑器从节点库添加新节点。
    """
    definition = definition or {}
    def_data = definition.get("definition", {}) if isinstance(definition, dict) else {}
    if not isinstance(def_data, dict):
        def_data = {}
    category = definition.get("category", "") if isinstance(definition, dict) else ""
    display_name = definition.get("display_name", node_class) if isinstance(definition, dict) else node_class
    is_custom = bool(definition.get("is_custom_node", False)) if isinstance(definition, dict) else False

    def_inputs = def_data.get("input", {})
    if not isinstance(def_inputs, dict):
        def_inputs = {}
    required_inputs = def_inputs.get("required", {})
    if not isinstance(required_inputs, dict):
        required_inputs = {}
    optional_inputs = def_inputs.get("optional", {})
    if not isinstance(optional_inputs, dict):
        optional_inputs = {}

    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
    widgets_values: list[Any] = []

    for name, spec in required_inputs.items():
        if not isinstance(spec, list) or len(spec) == 0:
            continue
        input_type = spec[0]
        if isinstance(input_type, list) or input_type in {"MODEL", "CLIP", "VAE", "CONDITIONING", "LATENT", "IMAGE", "MASK", "CONTROL_NET", "*"}:
            inputs.append({"name": name, "type": input_type if isinstance(input_type, str) else "*", "link": None})
        else:
            # 值类型：取默认值
            default_value = None
            if len(spec) > 1 and isinstance(spec[1], dict):
                default_value = spec[1].get("default", "")
            widgets_values.append(default_value if default_value is not None else "")

    for name, spec in optional_inputs.items():
        if not isinstance(spec, list) or len(spec) == 0:
            continue
        input_type = spec[0]
        if isinstance(input_type, list) or input_type in {"MODEL", "CLIP", "VAE", "CONDITIONING", "LATENT", "IMAGE", "MASK", "CONTROL_NET", "*"}:
            inputs.append({"name": name, "type": input_type if isinstance(input_type, str) else "*", "link": None})

    def_outputs = def_data.get("output", [])
    if isinstance(def_outputs, list):
        output_names = def_data.get("output_name", [])
        if not isinstance(output_names, list):
            output_names = ["" for _ in def_outputs]
        for idx, output_type in enumerate(def_outputs):
            name = output_names[idx] if idx < len(output_names) else f"output_{idx}"
            outputs.append({"name": str(name), "type": str(output_type) if isinstance(output_type, str) else "*", "links": []})

    return {
        "id": node_id,
        "type": node_class,
        "title": display_name,
        "position": list(position),
        "size": [240, 0],
        "mode": 0,
        "flags": {"enabled": True, "bypassed": False, "disabled": False, "collapsed": False},
        "widgets_values": widgets_values,
        "properties": {},
        "inputs": inputs,
        "outputs": outputs,
        "order": -1,
        "is_unknown": False,
        "is_custom": is_custom,
        "category": category,
        "raw": None,
    }


def are_ports_compatible(source_type: str, target_type: str) -> tuple[bool, str]:
    """判断两个端口类型是否可连接。返回 (compatible, reason)。"""
    if not source_type or not target_type:
        return True, ""
    # 通配类型
    if source_type == "*" or target_type == "*":
        return True, ""
    if source_type == target_type:
        return True, ""
    # 兼容的子类型关系（参考 ComfyUI 实践）
    compatible_pairs = {
        ("CLIP", "CLIP"),
        ("MODEL", "MODEL"),
        ("VAE", "VAE"),
        ("CONDITIONING", "CONDITIONING"),
        ("LATENT", "LATENT"),
        ("IMAGE", "IMAGE"),
        ("MASK", "MASK"),
    }
    if (source_type, target_type) in compatible_pairs:
        return True, ""
    return False, f"端口类型不匹配：{source_type} → {target_type}"
