"""阶段 3.1 页级编译器。

把项目结构稳定编译为页级跑图项（render items）。

编译流程：
1. 展开章节、大场景、小场景、页面和分支
2. 解析配置继承优先级（项目 → 章节 → 大场景 → 小场景 → 分支 → 页面）
3. 解析素材页映射（6 类素材 → 素材页 → 素材正文/提示词）
4. 解析人物、变体、规格、LoRA 和模型覆盖
5. 固定工作流版本（项目默认或页面覆盖）
6. 解析语义插槽（业务上下文 → 节点输入）
7. 生成稳定 sort_key 和 input_hash
8. 输出阻塞错误、警告和字段来源

设计原则：
- 确定性：相同输入产生相同 sort_key 和 input_hash
- 完整快照：每个跑图项包含完整输入快照，可供阶段 3.3 持久化
- 阻塞分离：阻塞错误和警告分开，阻塞项不生成跑图项
- 字段来源：每个有效值标记来源层级，便于调试
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class RenderItem:
    """单个页级跑图项。

    每个跑图项是一个不可变的可执行快照，包含 ComfyUI 执行所需的全部信息。
    """

    item_id: str
    sort_key: str
    input_hash: str
    project_id: str
    project_name: str
    chapter_id: str
    chapter_name: str
    large_scene_id: str
    large_scene_name: str
    small_scene_id: str
    small_scene_name: str
    shot_page_id: str
    shot_page_title: str
    branch_id: str | None
    branch_name: str | None
    workflow_id: str
    workflow_version_id: str
    workflow_label: str
    character_id: str | None
    character_name: str | None
    variant_id: str | None
    variant_name: str | None
    spec_values: dict[str, Any] = field(default_factory=dict)
    material_mappings: dict[str, dict[str, Any]] = field(default_factory=dict)
    effective_config: dict[str, Any] = field(default_factory=dict)
    field_sources: dict[str, str] = field(default_factory=dict)
    slot_resolutions: list[dict[str, Any]] = field(default_factory=list)
    resolved_api_json: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = field(default_factory=list)
    instance_count: int = 1
    seed_strategy: str = "fixed"
    seed_value: int | None = None
    seed_base: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "sort_key": self.sort_key,
            "input_hash": self.input_hash,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "chapter_id": self.chapter_id,
            "chapter_name": self.chapter_name,
            "large_scene_id": self.large_scene_id,
            "large_scene_name": self.large_scene_name,
            "small_scene_id": self.small_scene_id,
            "small_scene_name": self.small_scene_name,
            "shot_page_id": self.shot_page_id,
            "shot_page_title": self.shot_page_title,
            "branch_id": self.branch_id,
            "branch_name": self.branch_name,
            "workflow_id": self.workflow_id,
            "workflow_version_id": self.workflow_version_id,
            "workflow_label": self.workflow_label,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "variant_id": self.variant_id,
            "variant_name": self.variant_name,
            "spec_values": self.spec_values,
            "material_mappings": self.material_mappings,
            "effective_config": self.effective_config,
            "field_sources": self.field_sources,
            "slot_resolutions": self.slot_resolutions,
            "resolved_api_json": self.resolved_api_json,
            "warnings": self.warnings,
            "instance_count": self.instance_count,
            "seed_strategy": self.seed_strategy,
            "seed_value": self.seed_value,
            "seed_base": self.seed_base,
        }


@dataclass
class CompilationResult:
    """编译结果。"""

    items: list[RenderItem] = field(default_factory=list)
    blocking_errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [item.to_dict() for item in self.items],
            "blocking_errors": self.blocking_errors,
            "warnings": self.warnings,
            "summary": self.summary,
        }


# ──────────────────────────────────────────────────────────────────
# 编译器
# ──────────────────────────────────────────────────────────────────


VALID_SCOPES = ("project", "chapter", "large_scene", "small_scene", "branch", "shot_pages")

VALID_SEED_STRATEGIES = ("fixed", "random", "increment", "reuse_last")


def compile_project(
    manager: Any,
    project_id: str,
    *,
    scope: str = "project",
    scope_id: str | None = None,
    instance_count: int = 1,
    seed_strategy: str = "fixed",
    seed_base: int | None = None,
    workflow_id_override: str | None = None,
    workflow_version_id_override: str | None = None,
    skip_adopted: bool = False,
    only_failed: bool = False,
    environment: str | None = None,
) -> CompilationResult:
    """编译项目（或子范围）为页级跑图项列表。

    参数：
        manager: DatabaseManager 实例
        project_id: 项目 ID
        scope: 编译范围 (project/chapter/large_scene/small_scene/branch/shot_pages)
        scope_id: 范围 ID（shot_pages 时为逗号分隔的页面 ID 列表）
        instance_count: 每页生成实例数
        seed_strategy: 种子策略 (fixed/random/increment/reuse_last)
        seed_base: 种子基础值（increment 策略时递增起点）
        workflow_id_override: 批量覆盖工作流 ID
        workflow_version_id_override: 批量覆盖工作流版本 ID
        skip_adopted: 跳过已达到采用数量的页面
        only_failed: 只选失败项重跑
        environment: 数据库环境

    返回：
        CompilationResult
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope 无效，允许值: {', '.join(VALID_SCOPES)}")
    if seed_strategy not in VALID_SEED_STRATEGIES:
        raise ValueError(f"seed_strategy 无效，允许值: {', '.join(VALID_SEED_STRATEGIES)}")
    if instance_count < 1:
        raise ValueError("instance_count 必须 >= 1")

    result = CompilationResult()

    # 1. 收集所有 shot_page IDs
    page_ids = _collect_page_ids(manager, project_id, scope, scope_id, environment)
    if not page_ids:
        result.summary = {
            "total_pages": 0,
            "compiled_items": 0,
            "blocked_pages": 0,
        }
        return result

    # 2. 获取项目默认工作流
    project_default = manager.get_project_default_workflow(project_id, environment=environment)

    # 3. 逐页编译
    for page_id in page_ids:
        item, page_blocking, page_warnings = _compile_page(
            manager,
            project_id,
            page_id,
            instance_count=instance_count,
            seed_strategy=seed_strategy,
            seed_base=seed_base,
            workflow_id_override=workflow_id_override,
            workflow_version_id_override=workflow_version_id_override,
            project_default_workflow=project_default,
            environment=environment,
        )
        result.blocking_errors.extend(page_blocking)
        result.warnings.extend(page_warnings)
        if item is None:
            continue
        result.items.append(item)

    # 4. 生成 sort_key（稳定排序）
    for idx, item in enumerate(result.items):
        item.sort_key = f"{idx:06d}"

    # 5. 汇总
    result.summary = {
        "total_pages": len(page_ids),
        "compiled_items": len(result.items),
        "blocked_pages": len(page_ids) - len(result.items),
        "instance_count": instance_count,
        "seed_strategy": seed_strategy,
    }
    return result


def _collect_page_ids(
    manager: Any,
    project_id: str,
    scope: str,
    scope_id: str | None,
    environment: str | None,
) -> list[str]:
    """收集范围内的所有 shot_page IDs。"""
    with manager.connection(environment) as conn:
        # 验证项目存在
        proj = conn.execute(
            "SELECT id FROM projects WHERE id = ? AND deleted_at IS NULL",
            (project_id,),
        ).fetchone()
        if not proj:
            return []

        if scope == "shot_pages":
            if not scope_id:
                return []
            return [s.strip() for s in scope_id.split(",") if s.strip()]

        # 确定范围
        chapter_ids: list[str] = []
        large_scene_ids: list[str] = []
        small_scene_ids: list[str] = []
        branch_ids: list[str] = []

        if scope == "project":
            chapter_ids = [r["id"] for r in conn.execute(
                "SELECT id FROM chapters WHERE project_id = ? ORDER BY sort_order",
                (project_id,),
            ).fetchall()]
        elif scope == "chapter":
            if not scope_id:
                return []
            chapter_ids = [scope_id]
        elif scope == "large_scene":
            if not scope_id:
                return []
            large_scene_ids = [scope_id]
        elif scope == "small_scene":
            if not scope_id:
                return []
            small_scene_ids = [scope_id]
        elif scope == "branch":
            if not scope_id:
                return []
            branch_ids = [scope_id]

        # 展开层级
        if chapter_ids:
            ph = ",".join("?" * len(chapter_ids))
            large_scene_ids = [r["id"] for r in conn.execute(
                f"SELECT id FROM large_scenes WHERE chapter_id IN ({ph}) ORDER BY sort_order",
                chapter_ids,
            ).fetchall()]
        if large_scene_ids:
            ph = ",".join("?" * len(large_scene_ids))
            small_scene_ids = [r["id"] for r in conn.execute(
                f"SELECT id FROM small_scenes WHERE large_scene_id IN ({ph}) ORDER BY sort_order",
                large_scene_ids,
            ).fetchall()]

        # 如果按分支筛选
        if branch_ids:
            ph = ",".join("?" * len(branch_ids))
            page_ids = [r["id"] for r in conn.execute(
                f"""SELECT id FROM shot_pages
                    WHERE branch_id IN ({ph})
                    ORDER BY sort_order""",
                branch_ids,
            ).fetchall()]
        else:
            if small_scene_ids:
                ph = ",".join("?" * len(small_scene_ids))
                page_ids = [r["id"] for r in conn.execute(
                    f"""SELECT id FROM shot_pages
                        WHERE small_scene_id IN ({ph})
                        ORDER BY sort_order""",
                    small_scene_ids,
                ).fetchall()]
            else:
                page_ids = []

    return page_ids


def _compile_page(
    manager: Any,
    project_id: str,
    page_id: str,
    *,
    instance_count: int,
    seed_strategy: str,
    seed_base: int | None,
    workflow_id_override: str | None,
    workflow_version_id_override: str | None,
    project_default_workflow: dict[str, Any] | None,
    environment: str | None,
) -> tuple[RenderItem | None, list[dict[str, Any]], list[dict[str, Any]]]:
    """编译单个页面为跑图项。

    返回 (item, blocking_errors, warnings)。
    item 为 None 表示有阻塞错误。
    """
    blocking: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    field_sources: dict[str, str] = {}

    with manager.connection(environment) as conn:
        # 1. 获取页面及层级信息
        page = conn.execute(
            """SELECT sp.id, sp.title, sp.description, sp.prompt_text, sp.negative_prompt,
                      sp.sort_order, sp.small_scene_id, sp.branch_id
               FROM shot_pages sp
               WHERE sp.id = ?""",
            (page_id,),
        ).fetchone()
        if not page:
            blocking.append({
                "type": "page_not_found",
                "entity_type": "shot_page",
                "entity_id": page_id,
                "message": f"场景页不存在: {page_id}",
            })
            return None, blocking, warnings

        small_scene = conn.execute(
            """SELECT id, large_scene_id, name, scene_type, description
               FROM small_scenes WHERE id = ?""",
            (page["small_scene_id"],),
        ).fetchone()
        large_scene = conn.execute(
            """SELECT id, chapter_id, name, scene_type
               FROM large_scenes WHERE id = ?""",
            (small_scene["large_scene_id"],),
        ).fetchone() if small_scene else None
        chapter = conn.execute(
            """SELECT id, project_id, name FROM chapters WHERE id = ?""",
            (large_scene["chapter_id"],),
        ).fetchone() if large_scene else None
        project = conn.execute(
            """SELECT id, name, description, status FROM projects WHERE id = ?""",
            (project_id,),
        ).fetchone() if chapter else None

        if not project:
            blocking.append({
                "type": "project_not_found",
                "entity_type": "shot_page",
                "entity_id": page_id,
                "message": "页面所属项目不存在",
            })
            return None, blocking, warnings

        branch = None
        if page["branch_id"]:
            branch = conn.execute(
                """SELECT id, parent_type, parent_id, name, description, is_enabled,
                          condition_type, condition_value, return_point
                   FROM branches WHERE id = ?""",
                (page["branch_id"],),
            ).fetchone()
            if not branch:
                blocking.append({
                    "type": "invalid_branch_ref",
                    "entity_type": "shot_page",
                    "entity_id": page_id,
                    "entity_name": page["title"],
                    "message": f"场景页 '{page['title']}' 引用了不存在的分支",
                })
                return None, blocking, warnings
            if not branch["is_enabled"]:
                blocking.append({
                    "type": "disabled_branch",
                    "entity_type": "branch",
                    "entity_id": branch["id"],
                    "entity_name": branch["name"],
                    "message": f"分支 '{branch['name']}' 已禁用",
                })
                return None, blocking, warnings

        # 2. 解析人物绑定
        page_char = conn.execute(
            """SELECT spc.character_id, spc.variant_id,
                      c.name AS character_name, cv.name AS variant_name,
                      cv.default_prompt, cv.default_lora_name,
                      cv.default_lora_weight, cv.default_model_override
               FROM shot_page_characters spc
               JOIN characters c ON c.id = spc.character_id
               JOIN character_variants cv ON cv.id = spc.variant_id
               WHERE spc.shot_page_id = ?""",
            (page_id,),
        ).fetchone()
        if not page_char:
            warnings.append({
                "type": "missing_character",
                "entity_type": "shot_page",
                "entity_id": page_id,
                "entity_name": page["title"],
                "message": f"场景页 '{page['title']}' 未绑定人物",
            })
        else:
            field_sources["character"] = "shot_page"
            field_sources["variant"] = "shot_page"

        # 3. 解析规格值（变体 × 规格）
        spec_values: dict[str, Any] = {}
        if page_char:
            spec_rows = conn.execute(
                """SELECT csv.id, csv.prompt, csv.lora_name, csv.lora_weight,
                          csv.model_override, csv.notes,
                          s.spec_type, s.custom_label, s.is_required
                   FROM character_spec_values csv
                   JOIN specs s ON s.id = csv.spec_id
                   WHERE csv.variant_id = ?
                   ORDER BY s.sort_order""",
                (page_char["variant_id"],),
            ).fetchall()
            for sr in spec_rows:
                spec_key = sr["custom_label"] or sr["spec_type"]
                spec_values[spec_key] = {
                    "spec_value_id": sr["id"],
                    "prompt": sr["prompt"],
                    "lora_name": sr["lora_name"],
                    "lora_weight": sr["lora_weight"],
                    "model_override": sr["model_override"],
                    "notes": sr["notes"],
                    "is_required": bool(sr["is_required"]),
                }
                if sr["is_required"] and not sr["prompt"] and not sr["lora_name"]:
                    warnings.append({
                        "type": "missing_required_spec",
                        "entity_type": "shot_page",
                        "entity_id": page_id,
                        "entity_name": page["title"],
                        "message": f"必填规格 '{spec_key}' 的提示词和 LoRA 均为空",
                    })

        # 4. 解析素材页映射
        material_mappings: dict[str, dict[str, Any]] = {}
        mapping_rows = conn.execute(
            """SELECT sspm.id, sspm.material_type, sspm.material_page_id,
                      mp.name AS material_page_name, mp.material_id,
                      mp.content, mp.prompt_text, mp.negative_prompt
               FROM small_scene_page_mappings sspm
               JOIN material_pages mp ON mp.id = sspm.material_page_id
               WHERE sspm.scene_page_id = ?
               ORDER BY sspm.created_at""",
            (page_id,),
        ).fetchall()
        for mr in mapping_rows:
            material_mappings[mr["material_type"]] = {
                "mapping_id": mr["id"],
                "material_page_id": mr["material_page_id"],
                "material_page_name": mr["material_page_name"],
                "material_id": mr["material_id"],
                "content": mr["content"],
                "prompt_text": mr["prompt_text"],
                "negative_prompt": mr["negative_prompt"],
            }
        if not mapping_rows:
            warnings.append({
                "type": "missing_material_mapping",
                "entity_type": "shot_page",
                "entity_id": page_id,
                "entity_name": page["title"],
                "message": f"场景页 '{page['title']}' 缺失素材映射",
            })

        # 5. 解析工作流版本
        workflow_id = workflow_id_override or ""
        workflow_version_id = workflow_version_id_override or ""
        workflow_label = ""

        if workflow_id_override and workflow_version_id_override:
            # 批量覆盖
            version = manager.get_workflow_version(workflow_version_id_override, environment=environment)
            if not version:
                blocking.append({
                    "type": "workflow_version_not_found",
                    "entity_type": "shot_page",
                    "entity_id": page_id,
                    "message": f"工作流版本不存在: {workflow_version_id_override}",
                })
                return None, blocking, warnings
            workflow_id = workflow_id_override
            workflow_version_id = workflow_version_id_override
            workflow_label = str(version.get("label", ""))
            field_sources["workflow"] = "batch_override"
        elif project_default_workflow:
            workflow_id = str(project_default_workflow.get("workflow_id", ""))
            workflow_version_id = str(project_default_workflow.get("current_version_id", ""))
            workflow_label = str(project_default_workflow.get("name", ""))
            field_sources["workflow"] = "project_default"
        else:
            blocking.append({
                "type": "no_workflow",
                "entity_type": "shot_page",
                "entity_id": page_id,
                "entity_name": page["title"],
                "message": f"场景页 '{page['title']}' 无可用工作流（未设置项目默认工作流）",
            })
            return None, blocking, warnings

        # 6. 构建有效配置（继承优先级）
        effective: dict[str, Any] = {}
        # 项目级
        effective["project_name"] = project["name"]
        effective["project_description"] = project["description"] if project["description"] else ""
        # 页面级
        effective["prompt_text"] = page["prompt_text"] or ""
        effective["negative_prompt"] = page["negative_prompt"] or ""
        effective["description"] = page["description"] or ""
        if page_char:
            effective["character_prompt"] = page_char["default_prompt"] or ""
            effective["lora_name"] = page_char["default_lora_name"] or ""
            effective["lora_weight"] = page_char["default_lora_weight"]
            effective["model_override"] = page_char["default_model_override"] or ""

        # 7. 计算种子
        seed_value = _compute_seed(seed_strategy, seed_base, page_id)

    # 8. 构建 RenderItem
    item_id = str(uuid4())
    item = RenderItem(
        item_id=item_id,
        sort_key="",  # 后续填充
        input_hash="",  # 后续填充
        project_id=project["id"],
        project_name=project["name"],
        chapter_id=chapter["id"] if chapter else "",
        chapter_name=chapter["name"] if chapter else "",
        large_scene_id=large_scene["id"] if large_scene else "",
        large_scene_name=large_scene["name"] if large_scene else "",
        small_scene_id=small_scene["id"] if small_scene else "",
        small_scene_name=small_scene["name"] if small_scene else "",
        shot_page_id=page["id"],
        shot_page_title=page["title"],
        branch_id=branch["id"] if branch else None,
        branch_name=branch["name"] if branch else None,
        workflow_id=workflow_id,
        workflow_version_id=workflow_version_id,
        workflow_label=workflow_label,
        character_id=page_char["character_id"] if page_char else None,
        character_name=page_char["character_name"] if page_char else None,
        variant_id=page_char["variant_id"] if page_char else None,
        variant_name=page_char["variant_name"] if page_char else None,
        spec_values=spec_values,
        material_mappings=material_mappings,
        effective_config=effective,
        field_sources=field_sources,
        warnings=warnings,
        instance_count=instance_count,
        seed_strategy=seed_strategy,
        seed_value=seed_value,
        seed_base=seed_base,
    )

    # 9. 计算 input_hash（确定性）
    item.input_hash = _compute_input_hash(item)
    return item, blocking, warnings


def _compute_seed(strategy: str, base: int | None, page_id: str) -> int | None:
    """根据策略计算种子值。"""
    if strategy == "fixed":
        return base if base is not None else 0
    elif strategy == "random":
        # 随机种子在提交时生成，编译时返回 None
        return None
    elif strategy == "increment":
        return base if base is not None else 0
    elif strategy == "reuse_last":
        # 复用上一次的种子，编译时返回 None（需查询历史）
        return None
    return None


def _compute_input_hash(item: RenderItem) -> str:
    """计算输入快照的 SHA256 哈希（确定性）。

    相同的输入产生相同的 hash，用于去重和变更检测。
    """
    hash_data = {
        "project_id": item.project_id,
        "shot_page_id": item.shot_page_id,
        "branch_id": item.branch_id,
        "workflow_version_id": item.workflow_version_id,
        "character_id": item.character_id,
        "variant_id": item.variant_id,
        "spec_values": item.spec_values,
        "material_mappings": {
            k: {
                "material_page_id": v["material_page_id"],
                "content": v["content"],
                "prompt_text": v["prompt_text"],
                "negative_prompt": v["negative_prompt"],
            }
            for k, v in item.material_mappings.items()
        },
        "effective_config": item.effective_config,
        "instance_count": item.instance_count,
        "seed_strategy": item.seed_strategy,
        "seed_value": item.seed_value,
    }
    canonical = json.dumps(hash_data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def resolve_slots_for_item(
    manager: Any,
    item: RenderItem,
    *,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """为跑图项解析语义插槽。

    使用工作流版本的语义插槽绑定，结合跑图项的业务上下文，
    生成每个插槽的解析结果。
    """
    from .workflow_models import NormalizedWorkflow
    from .workflow_slots import resolve_slot_value

    # 获取工作流版本
    version = manager.get_workflow_version(item.workflow_version_id, environment=environment)
    if not version:
        return []

    # 解析规范化结构
    try:
        normalized_data = json.loads(version["normalized_graph"])
        normalized = NormalizedWorkflow.from_dict(normalized_data)
    except (TypeError, ValueError, KeyError):
        return []

    # 获取语义插槽绑定
    slots = manager.list_semantic_slots(item.workflow_id, environment=environment)

    # 构建业务上下文
    character_values: dict[str, Any] = {}
    if item.character_id:
        character_values["character_name"] = item.character_name or ""
        character_values["character_prompt"] = item.effective_config.get("character_prompt", "")
        character_values["lora_name"] = item.effective_config.get("lora_name", "")
        character_values["lora_weight"] = item.effective_config.get("lora_weight")
        character_values["negative_prompt"] = item.effective_config.get("negative_prompt", "")

    # 从素材映射提取提示词
    material_prompt_parts: list[str] = []
    for mat_type, mapping in item.material_mappings.items():
        if mapping.get("prompt_text"):
            material_prompt_parts.append(mapping["prompt_text"])
    material_values = {
        "material_prompt": ", ".join(material_prompt_parts) if material_prompt_parts else "",
    }

    # 从规格值提取
    for spec_key, spec_val in item.spec_values.items():
        if spec_val.get("prompt"):
            material_prompt_parts.append(spec_val["prompt"])
        if spec_val.get("lora_name") and not character_values.get("lora_name"):
            character_values["lora_name"] = spec_val["lora_name"]
            character_values["lora_weight"] = spec_val.get("lora_weight")

    project_config = {
        "default_seed": item.seed_value,
        "default_width": item.effective_config.get("width"),
        "default_height": item.effective_config.get("height"),
        "default_checkpoint": item.effective_config.get("model_override"),
    }

    context = {
        "character_values": character_values,
        "material_values": material_values,
        "project_config": project_config,
    }

    resolutions: list[dict[str, Any]] = []
    for slot in slots:
        result = resolve_slot_value(slot, normalized, context=context)
        resolutions.append(result)

    return resolutions


def apply_slots_to_api_json(
    normalized_data: dict[str, Any],
    slot_resolutions: list[dict[str, Any]],
) -> dict[str, Any]:
    """将插槽解析结果应用到工作流，生成最终 API JSON。

    返回可提交给 ComfyUI 的 API JSON。
    """
    from .workflow_models import NormalizedWorkflow
    from .workflow_publish import normalized_to_api_json

    normalized = NormalizedWorkflow.from_dict(normalized_data)

    # 应用插槽值到节点输入
    for resolution in slot_resolutions:
        if resolution.get("source") == "none":
            continue
        node_id = str(resolution.get("node_id", ""))
        input_name = str(resolution.get("input_name", ""))
        resolved_value = resolution.get("resolved_value")
        if resolved_value is None:
            continue
        # 找到节点并更新输入值
        for node in normalized.nodes:
            if str(node.get("id", "")) == node_id:
                inputs = node.get("inputs", [])
                for inp in inputs:
                    if str(inp.get("name", "")) == input_name:
                        inp["value"] = resolved_value
                        inp["link"] = None  # 断开连线，使用值
                        break
                break

    return normalized_to_api_json(normalized)
