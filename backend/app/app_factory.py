"""Atelier 应用工厂。

本模块仅暴露 ``create_app`` 工厂与相关常量、请求模型，
不在导入时创建任何全局应用实例，从而避免测试导入时初始化真实数据库。
ASGI 入口 ``app`` 由 ``backend.app.main`` 单独持有。
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from .database import DatabaseManager, DatabaseSafetyError
from . import character_database
from .comfyui_client import (
    ComfyUIClient,
    ComfyUIConnectionConfig,
    ComfyUIError,
    extract_resource_lists,
    summarize_node_definitions,
)
from .workflow_models import (
    NormalizedWorkflow,
    WorkflowParseError,
    allocate_link_id,
    allocate_node_id,
    are_ports_compatible,
    build_default_node,
    detect_format,
    extract_workflow_from_image,
    parse_api_json,
    parse_ui_json,
    parse_workflow_from_raw,
    serialize_workflow,
    validate_workflow,
)
from .workflow_layout import (
    assign_node_to_group,
    compute_focus_subgraph,
    compute_layout,
    compute_link_bundles,
    create_group,
    generate_large_workflow,
    reorder_node,
    apply_layout,
)
from .workflow_slots import (
    list_builtin_slot_definitions,
    resolve_all_slots,
    validate_slot_bindings,
    apply_slots_to_workflow,
)
from .workflow_publish import (
    export_workflow,
    normalized_to_api_json,
    normalized_to_ui_json,
    precheck_publish,
    roundtrip_test,
)
from .compiler import (
    apply_slots_to_api_json,
    compile_project,
    resolve_slots_for_item,
)
from .batch_drafts import (
    BatchConfig,
    VALID_BATCH_STATUSES,
    commit_draft,
    create_draft,
    delete_batch,
    delete_draft,
    get_batch,
    get_draft,
    list_batches,
    list_drafts,
    preview_draft,
    update_batch_status,
    update_draft,
)
from .task_queue import (
    DEFAULT_LEASE_SECONDS,
    DEFAULT_MAX_ATTEMPTS,
    VALID_TASK_STATUSES,
    cancel_task,
    claim_next_task,
    create_tasks_from_batch,
    expire_stale_leases,
    get_attempt,
    get_batch_progress,
    get_task,
    get_task_center_summary,
    list_all_tasks,
    list_attempts,
    list_events,
    list_tasks,
    mark_attempt_completed,
    mark_attempt_failed,
    mark_attempt_submitted,
    mark_attempt_unknown,
    pause_task,
    recover_after_restart,
    release_lease,
    resume_task,
    retry_task,
    set_task_priority,
)
from .comfyui_submit import (
    build_api_json_for_item,
    check_comfyui_history,
    submit_task_to_comfyui,
)
from .comfyui_progress import (
    ProgressTracker,
    ComfyUIWebSocketListener,
    poll_comfyui_history_for_attempt,
    recover_submitted_attempts,
    sse_progress_generator,
)
from .output_receiver import (
    collect_attempt_outputs,
    get_file_path,
    get_file_record,
    get_image_instance,
    list_background_jobs,
    list_image_instances,
    parse_comfyui_outputs,
)


logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
FRONTEND_ROOT = PROJECT_ROOT / "design" / "ui-preview"
SYSTEM_FEATURES_PATH = PROJECT_ROOT / "系统功能清单.md"
DEVELOPMENT_TODO_PATTERN = re.compile(
    r"^\s*-\s*\[(?P<state>[ xX~\-])\]\s*(?P<body>.+?)\s*$"
)


def read_development_progress(todo_path: Path) -> dict[str, object]:
    """Read the system checklist without turning progress into hard-coded UI data."""
    content = todo_path.read_text(encoding="utf-8-sig")
    items: list[dict[str, object]] = []
    module_name = "其他"
    for line in content.splitlines():
        if line.startswith("## "):
            module_name = line[3:].strip()
            continue
        match = DEVELOPMENT_TODO_PATTERN.match(line)
        if not match:
            continue
        body = match.group("body").strip()
        title, separator, description = body.partition("：")
        if not separator:
            title, separator, description = body.partition(":")
        title = title.strip()
        description = description.strip() if separator else ""
        state = match.group("state").lower()
        item_status = (
            "completed"
            if state == "x"
            else "in_progress"
            if state in {"~", "-"}
            else "pending"
        )
        items.append(
            {
                "id": f"feature-{len(items) + 1}",
                "module": module_name,
                "title": title,
                "description": description,
                "status": item_status,
                "completed": item_status == "completed",
            }
        )

    completed_count = sum(1 for item in items if item["completed"])
    in_progress_count = sum(
        1 for item in items if item["status"] == "in_progress"
    )
    total = len(items)
    progress_percent = round((completed_count / total) * 100, 1) if total else 0.0
    modules: list[dict[str, object]] = []
    for item in items:
        module = next(
            (entry for entry in modules if entry["name"] == item["module"]),
            None,
        )
        if module is None:
            module = {
                "name": item["module"],
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "pending": 0,
                "items": [],
            }
            modules.append(module)
        module["total"] += 1
        module[item["status"]] += 1
        module["items"].append(item)

    for module in modules:
        module["progress_percent"] = round(
            (module["completed"] / module["total"]) * 100,
            1,
        )

    updated_at = datetime.fromtimestamp(
        todo_path.stat().st_mtime,
        tz=timezone.utc,
    ).isoformat()
    return {
        "source": todo_path.name,
        "updated_at": updated_at,
        "total": total,
        "completed": completed_count,
        "in_progress": in_progress_count,
        "pending": total - completed_count - in_progress_count,
        "progress_percent": progress_percent,
        "progress_rule": "只有完成前后端闭环并通过验收的功能计入完成率。",
        "modules": modules,
        "items": items,
    }


class ActivateDatabaseRequest(BaseModel):
    environment: Literal["production", "test"]
    confirmation: str | None = None


class ComfyUISettingsRequest(BaseModel):
    base_url: str | None = None
    timeout_seconds: float | None = Field(default=None, ge=1.0, le=120.0)
    websocket_url: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("ComfyUI 地址不能为空。")
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("ComfyUI 地址必须以 http:// 或 https:// 开头。")
        return stripped.rstrip("/")


class SyncResourcesRequest(BaseModel):
    resource_types: list[str] = Field(
        default_factory=lambda: [
            "checkpoints",
            "loras",
            "vaes",
            "embeddings",
            "controlnet",
            "upscale_models",
        ]
    )


class CreateComfyuiInstanceRequest(BaseModel):
    """创建 ComfyUI 实例请求（需求 §4.4）。"""

    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=1, max_length=500)
    websocket_url: str = Field(default="", max_length=500)
    timeout_seconds: float = Field(default=10.0, ge=1.0, le=120.0)
    download_timeout_seconds: float = Field(default=60.0, ge=1.0, le=600.0)
    is_active: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ComfyUI 地址不能为空。")
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("ComfyUI 地址必须以 http:// 或 https:// 开头。")
        return stripped.rstrip("/")


class UpdateComfyuiInstanceRequest(BaseModel):
    """更新 ComfyUI 实例配置请求（部分更新）。"""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = Field(default=None, max_length=500)
    websocket_url: str | None = Field(default=None, max_length=500)
    timeout_seconds: float | None = Field(default=None, ge=1.0, le=120.0)
    download_timeout_seconds: float | None = Field(default=None, ge=1.0, le=600.0)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("ComfyUI 地址不能为空。")
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("ComfyUI 地址必须以 http:// 或 https:// 开头。")
        return stripped.rstrip("/")


class CreateWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    source_type: str = Field(default="manual")
    source_identifier: str = Field(default="")
    project_id: str | None = None
    source_workflow_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("工作流名称不能为空。")
        return value.strip()

    @field_validator("source_type")
    @classmethod
    def validate_source_type(cls, value: str) -> str:
        allowed = {"manual", "ui_json", "api_json", "image_metadata", "copy"}
        if value not in allowed:
            raise ValueError(f"source_type 必须是 {allowed} 之一。")
        return value

class UpdateWorkflowRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

class CopyWorkflowRequest(BaseModel):
    new_name: str | None = Field(default=None, max_length=120)
    project_id: str | None = None

class ImportWorkflowRequest(BaseModel):
    source_format: str = Field(default="auto")
    raw_json: dict | None = None
    label: str = Field(default="")

    @field_validator("source_format")
    @classmethod
    def validate_source_format(cls, value: str) -> str:
        allowed = {"auto", "ui_json", "api_json"}
        if value not in allowed:
            raise ValueError(f"source_format 必须是 {allowed} 之一。")
        return value

class PublishVersionRequest(BaseModel):
    label: str = Field(default="", max_length=200)
    normalized_graph: str
    raw_ui_json: str | None = None
    raw_api_json: str | None = None
    node_count: int = Field(default=0, ge=0)
    checksum: str = Field(default="")
    is_validated: bool = False
    validation_result: str | None = None

class ExportWorkflowRequest(BaseModel):
    format: str = Field(default="api_json")

    @field_validator("format")
    @classmethod
    def validate_format(cls, value: str) -> str:
        allowed = {"api_json", "ui_json"}
        if value not in allowed:
            raise ValueError(f"format 必须是 {allowed} 之一。")
        return value

class RoundtripTestRequest(BaseModel):
    workflow: dict[str, Any] = Field(default_factory=dict)
    source_format: str = Field(default="auto")

    @field_validator("source_format")
    @classmethod
    def validate_source_format(cls, value: str) -> str:
        allowed = {"auto", "ui_json", "api_json"}
        if value not in allowed:
            raise ValueError(f"source_format 必须是 {allowed} 之一。")
        return value

class SaveDraftRequest(BaseModel):
    normalized_graph: str
    raw_ui_json: str | None = None
    raw_api_json: str | None = None
    node_count: int = Field(default=0, ge=0)
    semantic_slots_json: str = Field(default="[]")
    last_node_id: int | None = Field(default=None, ge=0)
    last_link_id: int | None = Field(default=None, ge=0)
    validation_state: str | None = None
    layout_state: str | None = None
    is_dirty: bool | None = None
    expected_revision: int | None = Field(default=None, ge=0)

class AddNodeRequest(BaseModel):
    node_class: str = Field(min_length=1, max_length=200)
    position_x: int = Field(default=0)
    position_y: int = Field(default=0)

class UpdateNodeRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    widgets_values: list | None = None
    flags: dict | None = None
    properties: dict | None = None

class CreateLinkRequest(BaseModel):
    source_node: str = Field(min_length=1)
    source_slot: int = Field(default=0, ge=0)
    target_node: str = Field(min_length=1)
    target_slot: int = Field(default=0, ge=0)
    link_type: str = Field(default="")

class BatchNodeDefinitionsRequest(BaseModel):
    node_classes: list[str] = Field(default_factory=list)

class SetSemanticSlotRequest(BaseModel):
    slot_name: str = Field(min_length=1, max_length=80)
    slot_type: str
    node_id: str
    input_name: str
    transform_rule: str = Field(default="")
    default_value: str | None = None
    is_required: bool = False
    conflict_strategy: str = Field(default="overwrite")

class SetProjectDefaultWorkflowRequest(BaseModel):
    workflow_id: str


class ReorderNodeRequest(BaseModel):
    action: Literal[
        "forward", "backward", "prev_column", "next_column", "to_top", "to_bottom"
    ]


class CreateGroupRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    color: str = Field(default="#3f789e", max_length=32)
    members: list[str] = Field(default_factory=list)


class UpdateGroupRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    color: str | None = Field(default=None, max_length=32)


class AssignGroupRequest(BaseModel):
    group_id: str | None = None


class SaveLayoutStateRequest(BaseModel):
    layout_state: str = Field(min_length=1)


class FocusSubgraphRequest(BaseModel):
    node_id: str = Field(min_length=1)
    direction: Literal["upstream", "downstream", "both", "errors"] = "both"
    error_node_ids: list[str] | None = None


class ResolveSlotsRequest(BaseModel):
    """插槽解析预览请求。

    context 字段传入业务上下文（人物值、素材值、项目默认配置）。
    """
    context: dict | None = None


class ValidateSlotsRequest(BaseModel):
    """插槽绑定校验请求。"""
    pass


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("项目名称不能为空。")
        return value


class UpdateProjectRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("项目名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.name is None and self.description is None:
            raise ValueError("至少需要提供一个字段。")
        return self


class CopyProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("项目名称不能为空。")
        return value


class CreateChapterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("章节名称不能为空。")
        return value


class CreateLargeSceneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scene_type: Literal["content", "transition"] = "content"

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("大场景名称不能为空。")
        return value


class UpdateLargeSceneRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    scene_type: Literal["content", "transition"] | None = None
    chapter_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("大场景名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.name is None and self.scene_type is None and self.chapter_id is None:
            raise ValueError("至少需要提供一个更新字段。")
        return self


class MoveLargeSceneRequest(BaseModel):
    target_chapter_id: str
    target_sort_order: int = Field(ge=1)


class RenameChapterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("章节名称不能为空。")
        return value


class RenameLargeSceneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("大场景名称不能为空。")
        return value


class CreateCharacterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    source: str = Field(default="", max_length=80)
    source_identifier: str | None = None
    external_url: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("人物名称不能为空。")
        return value


class UpdateCharacterRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("人物名称不能为空。")
        return value


class RenameCharacterRequest(BaseModel):
    """Legacy request model kept for backward compatibility."""
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("人物名称不能为空。")
        return value


class SetCharacterTagsRequest(BaseModel):
    tags: list[str] = Field(default_factory=list)


class CopyCharacterRequest(BaseModel):
    new_name: str = Field(min_length=1, max_length=80)

    @field_validator("new_name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("新人物名称不能为空。")
        return value


class CreateCharacterVariantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    default_prompt: str = Field(default="")
    default_lora_name: str = Field(default="")
    default_lora_weight: float | None = None
    default_model_override: str = Field(default="")

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("形象变体名称不能为空。")
        return value

    @field_validator("default_lora_weight")
    @classmethod
    def lora_weight_range(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 2):
            raise ValueError("LoRA 权重必须在 0 到 2 之间。")
        return value


class UpdateCharacterVariantRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    default_prompt: str | None = None
    default_lora_name: str | None = None
    default_lora_weight: float | None = None
    default_model_override: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("形象变体名称不能为空。")
        return value

    @field_validator("default_lora_weight")
    @classmethod
    def lora_weight_range(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 2):
            raise ValueError("LoRA 权重必须在 0 到 2 之间。")
        return value


class RenameCharacterVariantRequest(BaseModel):
    """Legacy request model kept for backward compatibility."""
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("形象变体名称不能为空。")
        return value


class CopyCharacterVariantRequest(BaseModel):
    new_name: str = Field(min_length=1, max_length=80)

    @field_validator("new_name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("新变体名称不能为空。")
        return value


class ReorderVariantsRequest(BaseModel):
    variant_ids: list[str]


class CreateProjectSpecRequest(BaseModel):
    spec_type: str = Field(min_length=1, max_length=40)
    custom_label: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=500)
    is_required: bool = False
    default_value: str = Field(default="", max_length=500)

    @field_validator("spec_type")
    @classmethod
    def spec_type_valid(cls, value: str) -> str:
        valid = ("full_body", "half_body", "close_up", "custom")
        if value not in valid:
            raise ValueError(f"规格类型必须是 {', '.join(valid)} 之一。")
        return value

    @model_validator(mode="after")
    def custom_label_required_for_custom(self) -> "CreateProjectSpecRequest":
        if self.spec_type == "custom" and not self.custom_label.strip():
            raise ValueError("自定义规格必须提供标签名称。")
        return self


class UpdateProjectSpecRequest(BaseModel):
    custom_label: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    is_required: bool | None = None
    default_value: str | None = Field(default=None, max_length=500)


class BatchUpdateSpecValuesRequest(BaseModel):
    updates: list[dict[str, object]]


class SetShotPageCharacterRequest(BaseModel):
    character_id: str
    variant_id: str


class CreateCharacterFromRoleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    source: str = Field(default="role_query", max_length=80)
    source_identifier: str | None = None
    external_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    project_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("人物名称不能为空。")
        return value


class UpdateCharacterSpecValueRequest(BaseModel):
    prompt: str | None = None
    lora_name: str | None = None
    lora_weight: float | None = None
    model_override: str | None = None
    notes: str | None = None

    @field_validator("lora_weight")
    @classmethod
    def lora_weight_range(cls, value: float | None) -> float | None:
        if value is not None and (value < 0 or value > 2):
            raise ValueError("LoRA 权重必须在 0 到 2 之间。")
        return value


class CreateMaterialRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    material_type: Literal[
        "composition",
        "expression",
        "scene",
        "lighting",
        "prompt",
        "composite_template",
    ]
    description: str = Field(default="", max_length=300)
    content: str = Field(min_length=1, max_length=50000)
    prompt_text: str = Field(default="", max_length=50000)
    negative_prompt: str = Field(default="", max_length=20000)
    validation_status: Literal["unverified", "verified"] = "unverified"
    notes: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    preview_path: str = ""

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("素材名称不能为空。")
        return value

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("素材正文不能为空。")
        return value

    @field_validator("tags")
    @classmethod
    def tags_clean(cls, value: list[str]) -> list[str]:
        if len(value) > 30:
            raise ValueError("素材标签最多 30 个。")
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            if not isinstance(raw, str):
                continue
            clean = " ".join(raw.split())
            if not clean:
                continue
            if len(clean) > 40:
                raise ValueError("单个素材标签不能超过 40 个字符。")
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(clean)
        return cleaned


class UpdateMaterialRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    material_type: Literal[
        "composition",
        "expression",
        "scene",
        "lighting",
        "prompt",
        "composite_template",
    ] | None = None
    description: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=50000)
    prompt_text: str | None = Field(default=None, max_length=50000)
    negative_prompt: str | None = Field(default=None, max_length=20000)
    validation_status: Literal["unverified", "verified"] | None = None
    notes: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=30)
    preview_path: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("素材名称不能为空。")
        return value

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("素材正文不能为空。")
        return value

    @field_validator("tags")
    @classmethod
    def tags_clean(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 30:
            raise ValueError("素材标签最多 30 个。")
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in value:
            if not isinstance(raw, str):
                continue
            clean = " ".join(raw.split())
            if not clean:
                continue
            if len(clean) > 40:
                raise ValueError("单个素材标签不能超过 40 个字符。")
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(clean)
        return cleaned

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateMaterialRequest":
        if all(
            getattr(self, field) is None
            for field in (
                "name",
                "material_type",
                "description",
                "content",
                "prompt_text",
                "negative_prompt",
                "validation_status",
                "notes",
                "preview_path",
                "tags",
            )
        ):
            raise ValueError("至少需要提供一个更新字段。")
        return self



class CreateSmallSceneRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scene_type: Literal["content", "transition"] = "content"
    description: str = ""

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("小场景名称不能为空。")
        return value


class UpdateSmallSceneRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    scene_type: Literal["content", "transition"] | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("小场景名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.name, self.scene_type, self.description)):
            raise ValueError("至少需要提供一个更新字段。")
        return self


class MoveSmallSceneRequest(BaseModel):
    target_sort_order: int = Field(ge=1)


class CreateShotPageRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    branch_id: str | None = None
    description: str = Field(default="", max_length=500)
    prompt_text: str = Field(default="", max_length=50000)
    negative_prompt: str = Field(default="", max_length=20000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("分镜页标题不能为空。")
        return value


class UpdateShotPageRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    prompt_text: str | None = Field(default=None, max_length=50000)
    negative_prompt: str | None = Field(default=None, max_length=20000)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("分镜页标题不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.title, self.description, self.prompt_text, self.negative_prompt)):
            raise ValueError("至少需要提供一个更新字段。")
        return self


class MoveShotPageRequest(BaseModel):
    target_sort_order: int = Field(ge=1)


class CreateBranchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    is_enabled: bool = True
    condition_type: str = Field(default="", max_length=50)
    condition_value: str = Field(default="", max_length=500)
    return_point: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("分支名称不能为空。")
        return value


class UpdateBranchRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    is_enabled: bool | None = None
    condition_type: str | None = Field(default=None, max_length=50)
    condition_value: str | None = Field(default=None, max_length=500)
    return_point: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("分支名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.name, self.description, self.is_enabled,
                                   self.condition_type, self.condition_value, self.return_point)):
            raise ValueError("至少需要提供一个更新字段。")
        return self


class SetMaterialsRequest(BaseModel):
    material_ids: list[str]


# ── v0.5.4 Story Structure Request Models ───────────────────────────

class CreateBranchOverrideRequest(BaseModel):
    override_type: str = Field(min_length=1, max_length=50)
    target_id: str | None = None
    character_id: str | None = None
    variant_id: str | None = None
    material_id: str | None = None
    material_page_id: str | None = None
    param_key: str | None = Field(default=None, max_length=100)
    param_value: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_override_type(self):
        if self.override_type not in ("character", "material", "parameter"):
            raise ValueError("override_type 必须为 character/material/parameter")
        return self


class UpdateBranchOverrideRequest(BaseModel):
    target_id: str | None = None
    character_id: str | None = None
    variant_id: str | None = None
    material_id: str | None = None
    material_page_id: str | None = None
    param_key: str | None = Field(default=None, max_length=100)
    param_value: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.target_id, self.character_id, self.variant_id,
                                   self.material_id, self.material_page_id,
                                   self.param_key, self.param_value)):
            raise ValueError("至少需要提供一个更新字段。")
        return self


class CreateSnapshotRequest(BaseModel):
    label: str = Field(default="", max_length=200)


class PrecheckRequest(BaseModel):
    scope: str = Field(default="project")
    scope_id: str | None = None

    @model_validator(mode="after")
    def validate_scope(self):
        valid_scopes = ("project", "chapter", "large_scene", "small_scene", "branch", "shot_pages")
        if self.scope not in valid_scopes:
            raise ValueError(f"scope 无效，允许值: {', '.join(valid_scopes)}")
        if self.scope != "project" and not self.scope_id:
            raise ValueError(f"scope={self.scope} 需要 scope_id")
        return self


class CompileRequest(BaseModel):
    scope: str = Field(default="project")
    scope_id: str | None = None
    instance_count: int = Field(default=1, ge=1, le=100)
    seed_strategy: str = Field(default="fixed")
    seed_base: int | None = Field(default=None, ge=0)
    workflow_id: str | None = None
    workflow_version_id: str | None = None
    skip_adopted: bool = False
    only_failed: bool = False
    resolve_slots: bool = Field(default=False, description="是否解析语义插槽")

    @model_validator(mode="after")
    def validate_fields(self):
        valid_scopes = ("project", "chapter", "large_scene", "small_scene", "branch", "shot_pages")
        if self.scope not in valid_scopes:
            raise ValueError(f"scope 无效，允许值: {', '.join(valid_scopes)}")
        if self.scope != "project" and not self.scope_id:
            raise ValueError(f"scope={self.scope} 需要 scope_id")
        valid_strategies = ("fixed", "random", "increment", "reuse_last")
        if self.seed_strategy not in valid_strategies:
            raise ValueError(f"seed_strategy 无效，允许值: {', '.join(valid_strategies)}")
        return self


# ── v0.7.0 阶段 3.2 批量配置请求模型 ───────────────────────────────


_BATCH_VALID_SCOPES = ("project", "chapter", "large_scene", "small_scene", "branch", "shot_pages")
_BATCH_VALID_STRATEGIES = ("fixed", "random", "increment", "reuse_last")


class BatchConfigRequest(BaseModel):
    """批量配置请求体。"""
    instance_count: int = Field(default=1, ge=1, le=100)
    seed_strategy: str = Field(default="fixed")
    seed_base: int | None = Field(default=None, ge=0)
    workflow_id: str | None = None
    workflow_version_id: str | None = None
    skip_adopted: bool = False
    only_failed: bool = False

    @model_validator(mode="after")
    def validate_fields(self):
        if self.seed_strategy not in _BATCH_VALID_STRATEGIES:
            raise ValueError(f"seed_strategy 无效，允许值: {', '.join(_BATCH_VALID_STRATEGIES)}")
        return self


class CreateBatchDraftRequest(BaseModel):
    name: str = Field(default="", max_length=120)
    scope: str = Field(default="project")
    scope_id: str | None = None
    config: BatchConfigRequest = Field(default_factory=BatchConfigRequest)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope not in _BATCH_VALID_SCOPES:
            raise ValueError(f"scope 无效，允许值: {', '.join(_BATCH_VALID_SCOPES)}")
        if self.scope != "project" and not self.scope_id:
            raise ValueError(f"scope={self.scope} 需要 scope_id")
        return self


class UpdateBatchDraftRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    scope: str | None = None
    scope_id: str | None = None
    config: BatchConfigRequest | None = None

    @model_validator(mode="after")
    def validate_scope(self):
        if self.scope is not None:
            if self.scope not in _BATCH_VALID_SCOPES:
                raise ValueError(f"scope 无效，允许值: {', '.join(_BATCH_VALID_SCOPES)}")
            if self.scope != "project" and not self.scope_id:
                raise ValueError(f"scope={self.scope} 需要 scope_id")
        return self


class PreviewBatchDraftRequest(BaseModel):
    force: bool = Field(default=False, description="强制重新编译，忽略缓存")
    resolve_slots: bool = Field(default=False, description="解析语义插槽")


class CommitBatchDraftRequest(BaseModel):
    name: str | None = Field(default=None, max_length=120)


class UpdateBatchStatusRequest(BaseModel):
    status: str

    @model_validator(mode="after")
    def validate_status(self):
        from .batch_drafts import VALID_BATCH_STATUSES
        if self.status not in VALID_BATCH_STATUSES:
            raise ValueError(f"status 无效，允许值: {', '.join(VALID_BATCH_STATUSES)}")
        return self


class CreateTasksRequest(BaseModel):
    """从批次创建任务请求。"""
    max_attempts: int = Field(default=DEFAULT_MAX_ATTEMPTS, ge=1, le=10)


class ClaimTaskRequest(BaseModel):
    """领取任务请求。"""
    lease_holder: str = Field(min_length=1, max_length=120)
    lease_seconds: int = Field(default=DEFAULT_LEASE_SECONDS, ge=10, le=3600)
    batch_id: str | None = None


class ClaimTasksBatchRequest(BaseModel):
    """批量领取任务请求。"""
    lease_holder: str = Field(min_length=1, max_length=120)
    count: int = Field(default=1, ge=1, le=20)
    lease_seconds: int = Field(default=DEFAULT_LEASE_SECONDS, ge=10, le=3600)
    batch_id: str | None = None


class AttemptSubmitRequest(BaseModel):
    """标记 attempt 已提交。"""
    prompt_id: str = Field(min_length=1)
    api_json: str | None = None


class AttemptFailRequest(BaseModel):
    """标记 attempt 失败。"""
    error_message: str = Field(default="", max_length=2000)
    error_type: str = Field(default="unknown", max_length=120)


class AttemptUnknownRequest(BaseModel):
    """标记 attempt 状态未知。"""
    reason: str = Field(default="", max_length=2000)


class TaskPriorityRequest(BaseModel):
    """设置任务优先级。"""
    priority: int = Field(ge=0, le=1000)


class TaskStatusUpdateRequest(BaseModel):
    """任务状态控制（pause/resume/cancel/retry）。"""
    action: str

    @model_validator(mode="after")
    def validate_action(self):
        valid_actions = ("pause", "resume", "cancel", "retry")
        if self.action not in valid_actions:
            raise ValueError(f"action 无效，允许值: {', '.join(valid_actions)}")
        return self


# ── v0.4.1 Request Models ───────────────────────────────────────────

class CreateScenePageRequest(BaseModel):
    """场景页创建请求（前端使用 name 字段，内部转 title）"""
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    prompt_text: str = Field(default="", max_length=50000)
    negative_prompt: str = Field(default="", max_length=20000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("场景页名称不能为空。")
        return value


class UpdateScenePageRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    prompt_text: str | None = Field(default=None, max_length=50000)
    negative_prompt: str | None = Field(default=None, max_length=20000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("场景页名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.name, self.description, self.prompt_text, self.negative_prompt)):
            raise ValueError("至少需要提供一个更新字段。")
        return self


class ReorderPagesRequest(BaseModel):
    page_ids: list[str] = Field(min_length=1)


class AddResourceRequest(BaseModel):
    material_id: str = Field(min_length=1)


class SetMappingRequest(BaseModel):
    """Per second-round contract 8.5: material_page_id may be null to unset mapping."""
    material_page_id: str | None = None

    @field_validator("material_page_id")
    @classmethod
    def non_empty_string(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("material_page_id 不能为空字符串")
        return value


class CreateMaterialPageRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    content: str = Field(default="", max_length=50000)
    prompt_text: str = Field(default="", max_length=50000)
    negative_prompt: str = Field(default="", max_length=20000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("素材页名称不能为空。")
        return value


class UpdateMaterialPageRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, max_length=50000)
    prompt_text: str | None = Field(default=None, max_length=50000)
    negative_prompt: str | None = Field(default=None, max_length=20000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("素材页名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.name, self.description, self.content, self.prompt_text, self.negative_prompt)):
            raise ValueError("至少需要提供一个更新字段。")
        return self


class ReorderMaterialPagesRequest(BaseModel):
    page_ids: list[str] = Field(min_length=1)


class CopyMaterialRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("素材名称不能为空。")
        return value


class CreateMaterialVersionRequest(BaseModel):
    label: str | None = Field(default=None, max_length=120)


# 状态码到错误码的映射，保持 API 错误响应统一可追溯。
_STATUS_CODE_TO_ERROR_CODE: dict[int, str] = {
    400: "VALIDATION_ERROR",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "BUSINESS_RULE_VIOLATION",
    500: "INTERNAL_ERROR",
    503: "SERVICE_UNAVAILABLE",
}


def _build_error_payload(
    status_code: int,
    message: str,
    *,
    details: dict | None = None,
    request_id: str | None = None,
) -> dict[str, object]:
    """构建统一错误响应 payload。

    保留 ``detail`` 字段以兼容旧测试，同时提供 ``error`` 结构以满足
    《Atelier 全功能产品与技术开发需求》10.1 节的统一错误契约。
    """
    code = _STATUS_CODE_TO_ERROR_CODE.get(status_code, "INTERNAL_ERROR")
    payload: dict[str, object] = {
        "detail": message,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": request_id or "",
        },
    }
    return payload


def _detect_project_blockers(project: dict, stats: dict) -> list[dict[str, str]]:
    """检测项目阻塞项，返回阻塞原因列表。

    阻塞项：
    - 无章节：项目无法开始组织剧本
    - 无场景页：没有可编译的跑图目标
    - 无关联素材：场景页缺少素材映射
    - 无关联人物：缺少角色规格
    """
    blockers: list[dict[str, str]] = []
    if stats.get("chapter_count", 0) == 0:
        blockers.append({"code": "NO_CHAPTER", "message": "项目还没有章节，无法组织剧本。"})
    if stats.get("shot_page_count", 0) == 0:
        blockers.append({"code": "NO_SHOT_PAGE", "message": "项目还没有场景页，没有可生成的目标。"})
    if stats.get("material_count", 0) == 0:
        blockers.append({"code": "NO_MATERIAL", "message": "项目还没有关联素材。"})
    if stats.get("character_count", 0) == 0:
        blockers.append({"code": "NO_CHARACTER", "message": "项目还没有关联人物。"})
    return blockers


def create_app(
    *,
    data_root: Path | None = None,
    environment: Literal["production", "test"] = "production",
    locked_environment: Literal["production", "test"] | None = None,
    system_features_path: Path | None = None,
) -> FastAPI:
    manager = DatabaseManager(
        data_root or DEFAULT_DATA_ROOT,
        environment=environment,
        locked_environment=locked_environment,
    )

    # ComfyUI 客户端：基于数据库设置构造，运行时可更新配置
    def _build_comfyui_client() -> ComfyUIClient:
        # 优先使用 comfyui_instances 表中的活动实例（需求 §4.2）
        active_instance = manager.get_active_comfyui_instance()
        if active_instance:
            config = ComfyUIConnectionConfig(
                base_url=str(active_instance["base_url"]),
                timeout_seconds=float(active_instance["timeout_seconds"]),
                websocket_url=str(active_instance.get("websocket_url", "")),
            )
        else:
            # 回退到 app_settings（兼容旧单实例设置）
            settings = manager.get_comfyui_settings()
            config = ComfyUIConnectionConfig(
                base_url=str(settings.get("base_url", "http://127.0.0.1:8188")),
                timeout_seconds=float(settings.get("timeout_seconds", 10.0)),
                websocket_url=str(settings.get("websocket_url", "")),
            )
        return ComfyUIClient(config)

    comfyui_client = _build_comfyui_client()

    # 阶段3.5 进度跟踪器和 WebSocket 监听器
    progress_tracker = ProgressTracker()
    ws_listener = ComfyUIWebSocketListener(
        comfyui_client.config.derived_websocket_url(),
        progress_tracker,
        client_id=str(uuid.uuid4()),
        reconnect_interval=5.0,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """应用生命周期：启动/停止 WebSocket 监听器。"""
        if environment != "test":
            await ws_listener.start()
            logger.info("ComfyUI WebSocket 监听器已启动")
        yield
        if environment != "test":
            await ws_listener.stop()
            logger.info("ComfyUI WebSocket 监听器已停止")
        comfyui_client.close()

    app = FastAPI(
        title="Atelier API",
        version="0.7.0",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.database_manager = manager
    app.state.comfyui_client = comfyui_client
    app.state.progress_tracker = progress_tracker
    app.state.ws_listener = ws_listener

    def _refresh_comfyui_client() -> ComfyUIClient:
        """根据数据库最新设置重建 ComfyUI 客户端。"""
        nonlocal comfyui_client
        comfyui_client.close()
        comfyui_client = _build_comfyui_client()
        app.state.comfyui_client = comfyui_client
        # 同步更新 WebSocket 监听器 URL
        new_ws_url = comfyui_client.config.derived_websocket_url()
        if environment != "test":
            asyncio.create_task(ws_listener.update_url(new_ws_url))
        return comfyui_client

    resolved_development_todo_path = (
        system_features_path or SYSTEM_FEATURES_PATH
    ).resolve()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        """为每个请求注入唯一 request_id，并在响应头返回。

        - 优先复用客户端传入的 X-Request-ID（截断到 64 字符）。
        - 否则生成 UUID4。
        - 将 request_id 写入 request.state，供异常处理器使用。
        """
        incoming = request.headers.get("X-Request-ID")
        if incoming and len(incoming) <= 64:
            request_id = incoming
        else:
            request_id = uuid.uuid4().hex
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            # 兜底异常由下面的 exception handler 处理；这里只确保响应头存在。
            raise
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """统一 HTTP 异常响应格式。

        兼容 FastAPI/Starlette 的 HTTPException，保留 detail 字段（可能是
        字符串或字典），同时附加 error 结构。
        """
        request_id = getattr(request.state, "request_id", "") or ""
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            # 已经是统一格式，直接返回。
            payload = exc.detail
            if request_id and payload.get("error", {}).get("request_id") in (None, ""):
                payload["error"]["request_id"] = request_id
            return JSONResponse(status_code=exc.status_code, content=payload, headers={"X-Request-ID": request_id})
        message = str(exc.detail) if exc.detail is not None else f"HTTP {exc.status_code}"
        payload = _build_error_payload(exc.status_code, message, request_id=request_id)
        return JSONResponse(status_code=exc.status_code, content=payload, headers={"X-Request-ID": request_id})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """请求体或参数校验失败统一返回 422，并附加 error 结构。

        保持 422 状态码以兼容现有测试和 FastAPI 默认行为；
        Pydantic 校验失败（空白、超长、枚举不匹配）本质属于业务规则校验。
        """
        request_id = getattr(request.state, "request_id", "") or ""
        raw_errors = exc.errors()
        # errors() 的 ctx 字段可能包含 ValueError 等不可 JSON 序列化的对象，
        # 用 jsonable_encoder 转换；失败时降级为只保留基本字段。
        try:
            safe_errors = jsonable_encoder(raw_errors)
        except (TypeError, ValueError):
            safe_errors = [
                {
                    "loc": list(err.get("loc", [])),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in raw_errors
            ]
        first_message = "请求参数校验失败。"
        if safe_errors:
            first = safe_errors[0]
            loc = first.get("loc", [])
            msg = first.get("msg", "")
            loc_str = ".".join(str(p) for p in loc if p not in ("body", "query", "path"))
            first_message = f"{loc_str} {msg}".strip() if loc_str else msg
        payload = _build_error_payload(
            422,
            first_message,
            details={"validation_errors": safe_errors},
            request_id=request_id,
        )
        return JSONResponse(status_code=422, content=payload, headers={"X-Request-ID": request_id})

    @app.exception_handler(DatabaseSafetyError)
    async def database_safety_handler(request: Request, exc: DatabaseSafetyError):
        """数据库安全错误返回 403，防止误操作生产库。"""
        request_id = getattr(request.state, "request_id", "") or ""
        payload = _build_error_payload(403, str(exc), request_id=request_id)
        return JSONResponse(status_code=403, content=payload, headers={"X-Request-ID": request_id})

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """兜底未捕获异常，返回 500 并附带 request_id 以便追踪。"""
        request_id = getattr(request.state, "request_id", "") or ""
        payload = _build_error_payload(500, "服务器内部错误。", request_id=request_id)
        return JSONResponse(status_code=500, content=payload, headers={"X-Request-ID": request_id})

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {
            "status": "ok",
            "service": "atelier",
            "database_environment": manager.active_environment,
            "database_locked": manager.locked_environment is not None,
        }

    @app.get("/api/developer/progress")
    def developer_progress() -> dict[str, object]:
        try:
            return read_development_progress(resolved_development_todo_path)
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="系统功能清单不存在，暂时无法汇总开发进度。",
            ) from error
        except OSError as error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="系统功能清单读取失败。",
            ) from error

    # ── 测试数据库路由（仅在测试模式注册，生产模式返回 404，需求 §8.3）──
    if environment == "test":
        @app.get("/api/settings/databases")
        def database_settings() -> dict[str, object]:
            return {
                "active_environment": manager.active_environment,
                "locked_environment": manager.locked_environment,
                "databases": [
                    manager.database_info("production"),
                    manager.database_info("test"),
                ],
                "safety": {
                    "default_environment": "production",
                    "tests_forced_to": "test",
                    "paths_are_separate": True,
                },
            }

        @app.post("/api/settings/databases/activate")
        def activate_database(request: ActivateDatabaseRequest) -> dict[str, object]:
            if (
                request.environment == "production"
                and request.confirmation != "USE PRODUCTION"
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Production activation requires explicit confirmation.",
                )
            try:
                manager.activate(request.environment)
            except DatabaseSafetyError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
            return {
                "active_environment": manager.active_environment,
                "message": f"Active database is now {manager.active_environment}.",
            }

        @app.post("/api/settings/databases/verify-isolation")
        def verify_database_isolation() -> dict[str, object]:
            try:
                return manager.verify_isolation()
            except DatabaseSafetyError as error:
                raise HTTPException(status_code=500, detail=str(error)) from error

    # ── ComfyUI 连接层 ──

    @app.get("/api/settings/comfyui")
    def get_comfyui_settings() -> dict[str, object]:
        return {
            "database_environment": manager.active_environment,
            "settings": manager.get_comfyui_settings(),
        }

    @app.put("/api/settings/comfyui")
    def update_comfyui_settings(request: ComfyUISettingsRequest) -> dict[str, object]:
        settings = manager.set_comfyui_settings(
            base_url=request.base_url,
            timeout_seconds=request.timeout_seconds,
            websocket_url=request.websocket_url,
        )
        # 兼容旧单实例设置：同步更新活动实例的配置（需求 §11.2 兼容期）
        active = manager.get_active_comfyui_instance()
        if active:
            manager.update_comfyui_instance(
                active["id"],
                base_url=request.base_url,
                timeout_seconds=request.timeout_seconds,
                websocket_url=request.websocket_url,
            )
        # 配置变更后重建客户端
        _refresh_comfyui_client()
        return {
            "database_environment": manager.active_environment,
            "settings": settings,
            "message": "ComfyUI 设置已保存，客户端已刷新。",
        }

    @app.post("/api/comfyui/test-connection")
    def test_comfyui_connection() -> dict[str, object]:
        try:
            stats = comfyui_client.test_connection()
        except ComfyUIError as error:
            return {
                "database_environment": manager.active_environment,
                "status": "error",
                "message": str(error),
                "base_url": comfyui_client.config.normalized_base_url(),
            }
        return {
            "database_environment": manager.active_environment,
            "status": "ok",
            "base_url": comfyui_client.config.normalized_base_url(),
            "websocket_url": comfyui_client.config.derived_websocket_url(),
            "system": stats.raw.get("system", {}),
            "devices": stats.devices,
        }

    @app.get("/api/comfyui/system-stats")
    def get_comfyui_system_stats() -> dict[str, object]:
        try:
            stats = comfyui_client.get_system_stats()
        except ComfyUIError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "system_stats": stats,
        }

    @app.get("/api/comfyui/sync-status")
    def get_comfyui_sync_status() -> dict[str, object]:
        summary = manager.get_node_definition_summary()
        resources = manager.list_resource_cache()
        return {
            "database_environment": manager.active_environment,
            "node_definitions": summary,
            "resources": {
                rtype: {
                    "count": len(names),
                    "updated_at": resources.get("updated_at", {}).get(rtype, ""),
                }
                for rtype, names in resources.get("resources", {}).items()
            },
        }

    @app.post("/api/comfyui/sync-object-info")
    def sync_comfyui_object_info() -> dict[str, object]:
        try:
            object_info = comfyui_client.get_object_info()
        except ComfyUIError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        summary = summarize_node_definitions(object_info)
        saved = manager.save_node_definitions(object_info)
        # 从 object_info 提取资源列表并缓存
        extracted = extract_resource_lists(object_info)
        synced_resources: list[dict[str, object]] = []
        for rtype, names in extracted.items():
            result = manager.save_resource_cache(rtype, names)
            synced_resources.append(result)
        return {
            "database_environment": manager.active_environment,
            "sha256": summary.sha256,
            "node_count": saved["node_count"],
            "custom_node_count": saved["custom_node_count"],
            "synced_at": saved["synced_at"],
            "resources_synced": synced_resources,
        }

    @app.get("/api/comfyui/node-definitions")
    def list_comfyui_node_definitions(
        category: str | None = None,
        custom: bool | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        result = manager.list_node_definitions(
            category=category,
            is_custom=custom,
            search=search,
            limit=limit,
            offset=offset,
        )
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.get("/api/comfyui/node-definitions/{node_class}")
    def get_comfyui_node_definition(node_class: str) -> dict[str, object]:
        definition = manager.get_node_definition(node_class)
        if not definition:
            raise HTTPException(status_code=404, detail="节点定义不存在，请先同步。")
        return {
            "database_environment": manager.active_environment,
            "node_definition": definition,
        }

    @app.get("/api/comfyui/node-categories")
    def list_comfyui_node_categories() -> dict[str, object]:
        categories = manager.list_node_categories()
        return {
            "database_environment": manager.active_environment,
            "categories": categories,
        }

    @app.post("/api/comfyui/sync-resources")
    def sync_comfyui_resources(request: SyncResourcesRequest) -> dict[str, object]:
        results: list[dict[str, object]] = []
        for rtype in request.resource_types:
            try:
                if rtype == "embeddings":
                    names = comfyui_client.get_embeddings()
                else:
                    names = comfyui_client.get_models(rtype)
                saved = manager.save_resource_cache(rtype, names)
                results.append(saved)
            except ComfyUIError as error:
                results.append({
                    "resource_type": rtype,
                    "error": str(error),
                    "count": 0,
                })
        return {
            "database_environment": manager.active_environment,
            "synced": results,
        }

    @app.get("/api/comfyui/resources")
    def list_comfyui_resources(
        resource_type: str | None = None,
        search: str | None = None,
    ) -> dict[str, object]:
        result = manager.list_resource_cache(resource_type=resource_type, search=search)
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    # ── ComfyUI 多实例管理（需求 §4.4、§6.2）──

    @app.get("/api/comfyui/instances")
    def list_comfyui_instances() -> dict[str, object]:
        """列出所有 ComfyUI 实例。"""
        instances = manager.list_comfyui_instances()
        return {
            "database_environment": manager.active_environment,
            "instances": instances,
            "total": len(instances),
        }

    @app.post("/api/comfyui/instances")
    def create_comfyui_instance(
        request: CreateComfyuiInstanceRequest,
    ) -> dict[str, object]:
        """创建 ComfyUI 实例。如果 is_active=True，同时设为活动实例。"""
        instance = manager.create_comfyui_instance(
            name=request.name,
            base_url=request.base_url,
            websocket_url=request.websocket_url,
            timeout_seconds=request.timeout_seconds,
            download_timeout_seconds=request.download_timeout_seconds,
            is_active=request.is_active,
        )
        if request.is_active:
            _refresh_comfyui_client()
        return {
            "database_environment": manager.active_environment,
            "instance": instance,
            "message": "ComfyUI 实例已创建。",
        }

    @app.patch("/api/comfyui/instances/{instance_id}")
    def update_comfyui_instance(
        instance_id: str, request: UpdateComfyuiInstanceRequest
    ) -> dict[str, object]:
        """更新 ComfyUI 实例配置。"""
        instance = manager.update_comfyui_instance(
            instance_id,
            name=request.name,
            base_url=request.base_url,
            websocket_url=request.websocket_url,
            timeout_seconds=request.timeout_seconds,
            download_timeout_seconds=request.download_timeout_seconds,
        )
        if instance is None:
            raise HTTPException(status_code=404, detail="ComfyUI 实例不存在。")
        # 如果更新的是活动实例，刷新客户端
        if instance.get("is_active"):
            _refresh_comfyui_client()
        return {
            "database_environment": manager.active_environment,
            "instance": instance,
            "message": "ComfyUI 实例已更新。",
        }

    @app.delete("/api/comfyui/instances/{instance_id}")
    def delete_comfyui_instance(instance_id: str) -> dict[str, object]:
        """删除 ComfyUI 实例。"""
        instance = manager.get_comfyui_instance(instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="ComfyUI 实例不存在。")
        was_active = bool(instance.get("is_active"))
        manager.delete_comfyui_instance(instance_id)
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "message": "ComfyUI 实例已删除。",
        }

    @app.post("/api/comfyui/instances/{instance_id}/activate")
    def activate_comfyui_instance(instance_id: str) -> dict[str, object]:
        """将指定实例设为活动实例。其他实例自动设为非活动。"""
        instance = manager.activate_comfyui_instance(instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="ComfyUI 实例不存在。")
        _refresh_comfyui_client()
        return {
            "database_environment": manager.active_environment,
            "instance": instance,
            "message": "已切换活动 ComfyUI 实例。",
        }

    @app.post("/api/comfyui/instances/{instance_id}/test")
    def test_comfyui_instance(instance_id: str) -> dict[str, object]:
        """测试指定实例的连接，更新状态字段。"""
        instance = manager.get_comfyui_instance(instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="ComfyUI 实例不存在。")
        # 构造临时客户端测试连接，不影响全局客户端
        config = ComfyUIConnectionConfig(
            base_url=str(instance["base_url"]),
            timeout_seconds=float(instance["timeout_seconds"]),
            websocket_url=str(instance.get("websocket_url", "")),
        )
        temp_client = ComfyUIClient(config)
        try:
            stats = temp_client.test_connection()
            # 提取 ComfyUI 版本和设备摘要
            system = stats.raw.get("system", {})
            version = str(system.get("comfyui_version", ""))
            devices = stats.devices if isinstance(stats.devices, list) else []
            updated = manager.update_comfyui_instance_status(
                instance_id,
                connection_status="ok",
                comfyui_version=version,
                device_summary=devices,
            )
            return {
                "database_environment": manager.active_environment,
                "instance": updated,
                "status": "ok",
                "base_url": config.normalized_base_url(),
                "websocket_url": config.derived_websocket_url(),
                "system": system,
                "devices": devices,
            }
        except ComfyUIError as error:
            manager.update_comfyui_instance_status(
                instance_id, connection_status="unreachable"
            )
            return {
                "database_environment": manager.active_environment,
                "status": "error",
                "message": str(error),
                "base_url": config.normalized_base_url(),
            }
        finally:
            temp_client.close()

    @app.post("/api/comfyui/instances/{instance_id}/sync")
    def sync_comfyui_instance(instance_id: str) -> dict[str, object]:
        """同步指定实例的节点定义和资源。如果为活动实例，同时刷新全局客户端。"""
        instance = manager.get_comfyui_instance(instance_id)
        if instance is None:
            raise HTTPException(status_code=404, detail="ComfyUI 实例不存在。")
        config = ComfyUIConnectionConfig(
            base_url=str(instance["base_url"]),
            timeout_seconds=float(instance["timeout_seconds"]),
            websocket_url=str(instance.get("websocket_url", "")),
        )
        temp_client = ComfyUIClient(config)
        try:
            object_info = temp_client.get_object_info()
        except ComfyUIError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        finally:
            temp_client.close()
        summary = summarize_node_definitions(object_info)
        saved = manager.save_node_definitions(object_info)
        extracted = extract_resource_lists(object_info)
        synced_resources: list[dict[str, object]] = []
        for rtype, names in extracted.items():
            result = manager.save_resource_cache(rtype, names)
            synced_resources.append(result)
        # 更新实例的节点定义摘要
        node_summary = {
            "node_count": saved["node_count"],
            "custom_node_count": saved["custom_node_count"],
            "sha256": summary.sha256,
            "last_synced_at": saved["synced_at"],
        }
        manager.update_comfyui_instance_status(
            instance_id,
            connection_status="ok",
            node_definition_summary=node_summary,
        )
        return {
            "database_environment": manager.active_environment,
            "instance_id": instance_id,
            "sha256": summary.sha256,
            "node_count": saved["node_count"],
            "custom_node_count": saved["custom_node_count"],
            "synced_at": saved["synced_at"],
            "resources_synced": synced_resources,
        }

    @app.post("/api/comfyui/discover")
    def discover_comfyui_instances() -> dict[str, object]:
        """探测候选 ComfyUI 实例（需求 §4.5）。

        探测范围受限：
        - 已保存的实例地址
        - 环境变量 ATELIER_COMFYUI_URL
        - 127.0.0.1:8188
        - 环境变量 ATELIER_COMFYUI_TEST_URL

        只调用只读接口 /system_stats，不自动覆盖活动实例。
        """
        import os

        candidates: list[str] = []
        # 1. 已保存的实例地址
        for inst in manager.list_comfyui_instances():
            url = str(inst["base_url"]).rstrip("/")
            if url and url not in candidates:
                candidates.append(url)
        # 2. 环境变量 ATELIER_COMFYUI_URL
        env_url = os.environ.get("ATELIER_COMFYUI_URL", "").strip()
        if env_url and env_url not in candidates:
            candidates.append(env_url)
        # 3. 环境变量 ATELIER_COMFYUI_TEST_URL
        test_url = os.environ.get("ATELIER_COMFYUI_TEST_URL", "").strip()
        if test_url and test_url not in candidates:
            candidates.append(test_url)
        # 4. 默认本机地址
        default_url = "http://127.0.0.1:8188"
        if default_url not in candidates:
            candidates.append(default_url)

        discovered: list[dict[str, object]] = []
        for url in candidates:
            config = ComfyUIConnectionConfig(base_url=url, timeout_seconds=3.0)
            temp_client = ComfyUIClient(config)
            try:
                stats = temp_client.test_connection()
                system = stats.raw.get("system", {})
                version = str(system.get("comfyui_version", ""))
                devices = stats.devices if isinstance(stats.devices, list) else []
                discovered.append({
                    "base_url": url,
                    "reachable": True,
                    "comfyui_version": version,
                    "devices": devices,
                    "status": "ok",
                })
            except ComfyUIError as error:
                discovered.append({
                    "base_url": url,
                    "reachable": False,
                    "status": "error",
                    "message": str(error),
                })
            finally:
                temp_client.close()

        return {
            "database_environment": manager.active_environment,
            "candidates": discovered,
            "total": len(discovered),
            "message": "探测完成，结果仅作为候选，未自动覆盖活动实例。",
        }

    # ── 工作流库 ──

    @app.get("/api/workflows")
    def list_workflows(
        project_id: str | None = None,
        include_global: bool = True,
        archived: bool = False,
        search: str | None = None,
        sort: str = "updated",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        # archived=true 表示只看归档的工作流；archived=false 表示只看活跃工作流
        result = manager.list_workflows(
            project_id=project_id,
            include_global=include_global,
            include_archived=False,
            archived_only=archived,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return {"database_environment": manager.active_environment, **result}

    @app.post("/api/workflows", status_code=status.HTTP_201_CREATED)
    def create_workflow(request: CreateWorkflowRequest) -> dict[str, object]:
        workflow = manager.create_workflow(
            request.name,
            description=request.description,
            source_type=request.source_type,
            source_identifier=request.source_identifier,
            project_id=request.project_id,
            source_workflow_id=request.source_workflow_id,
        )
        return {"database_environment": manager.active_environment, "workflow": workflow}

    @app.get("/api/workflows/{workflow_id}")
    def get_workflow(workflow_id: str) -> dict[str, object]:
        workflow = manager.get_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在。")
        return {"database_environment": manager.active_environment, "workflow": workflow}

    @app.patch("/api/workflows/{workflow_id}")
    def update_workflow(workflow_id: str, request: UpdateWorkflowRequest) -> dict[str, object]:
        workflow = manager.update_workflow(
            workflow_id,
            name=request.name,
            description=request.description,
        )
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在。")
        return {"database_environment": manager.active_environment, "workflow": workflow}

    @app.delete("/api/workflows/{workflow_id}")
    def delete_workflow(workflow_id: str) -> dict[str, object]:
        deleted = manager.delete_workflow(workflow_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="工作流不存在。")
        return {"database_environment": manager.active_environment, "deleted": True}

    @app.post("/api/workflows/{workflow_id}/archive")
    def archive_workflow(workflow_id: str) -> dict[str, object]:
        workflow = manager.archive_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在。")
        return {"database_environment": manager.active_environment, "workflow": workflow}

    @app.post("/api/workflows/{workflow_id}/restore")
    def restore_workflow(workflow_id: str) -> dict[str, object]:
        workflow = manager.restore_workflow(workflow_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="工作流不存在。")
        return {"database_environment": manager.active_environment, "workflow": workflow}

    @app.post("/api/workflows/{workflow_id}/copy")
    def copy_workflow(workflow_id: str, request: CopyWorkflowRequest) -> dict[str, object]:
        try:
            workflow = manager.copy_workflow(
                workflow_id,
                new_name=request.new_name,
                project_id=request.project_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"database_environment": manager.active_environment, "workflow": workflow}

    @app.post("/api/workflows/{workflow_id}/import")
    def import_workflow(workflow_id: str, request: ImportWorkflowRequest) -> dict[str, object]:
        """导入工作流 JSON 到草稿。"""
        if request.raw_json is None:
            raise HTTPException(status_code=422, detail="raw_json 不能为空。")
        try:
            normalized, actual_format = parse_workflow_from_raw(request.raw_json, request.source_format)
        except WorkflowParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        serialized = serialize_workflow(
            normalized,
            raw_ui_json=request.raw_json if actual_format == "ui_json" else None,
            raw_api_json=request.raw_json if actual_format == "api_json" else None,
        )
        # 计算来源快照校验和（用于审计，导入后不变）
        import hashlib
        source_checksum = hashlib.sha256(
            json.dumps(request.raw_json, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        draft = manager.save_workflow_draft(
            workflow_id,
            normalized_graph=serialized["normalized"] if isinstance(serialized["normalized"], str) else json.dumps(serialized["normalized"], ensure_ascii=False),
            raw_ui_json=serialized.get("raw_ui_json") and json.dumps(serialized["raw_ui_json"], ensure_ascii=False),
            raw_api_json=serialized.get("raw_api_json") and json.dumps(serialized["raw_api_json"], ensure_ascii=False),
            node_count=serialized["node_count"],
            is_dirty=False,  # 刚导入，未编辑
            source_checksum=source_checksum,
            draft_checksum=serialized["checksum"],
        )
        # 更新工作流 source_type
        manager.update_workflow(workflow_id, name=None, description=None)  # 触发 revision 递增
        return {
            "database_environment": manager.active_environment,
            "draft": draft,
            "source_format": actual_format,
            "node_count": serialized["node_count"],
            "checksum": serialized["checksum"],
        }

    @app.post("/api/workflows/import-from-image")
    def import_workflow_from_image(file: UploadFile = File(...)) -> dict[str, object]:
        """从图片提取工作流元数据。"""
        image_bytes = file.file.read()
        try:
            result = extract_workflow_from_image(image_bytes)
        except WorkflowParseError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        parsed_workflows = {}
        if result.get("ui_json"):
            try:
                normalized = parse_ui_json(result["ui_json"])
                parsed_workflows["ui_json"] = {
                    "normalized": normalized.to_dict(),
                    "node_count": normalized.node_count(),
                    "raw": result["ui_json"],
                }
            except WorkflowParseError:
                pass
        if result.get("api_json"):
            try:
                normalized = parse_api_json(result["api_json"])
                parsed_workflows["api_json"] = {
                    "normalized": normalized.to_dict(),
                    "node_count": normalized.node_count(),
                    "raw": result["api_json"],
                }
            except WorkflowParseError:
                pass
        return {
            "database_environment": manager.active_environment,
            "workflows": parsed_workflows,
        }

    @app.post("/api/workflows/{workflow_id}/versions")
    def publish_workflow_version(workflow_id: str, request: PublishVersionRequest) -> dict[str, object]:
        try:
            version = manager.publish_workflow_version(
                workflow_id,
                label=request.label,
                normalized_graph=request.normalized_graph,
                raw_ui_json=request.raw_ui_json,
                raw_api_json=request.raw_api_json,
                node_count=request.node_count,
                checksum=request.checksum,
                is_validated=request.is_validated,
                validation_result=request.validation_result,
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"database_environment": manager.active_environment, "version": version}

    @app.get("/api/workflows/{workflow_id}/versions")
    def list_workflow_versions(
        workflow_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        result = manager.list_workflow_versions(workflow_id, limit=limit, offset=offset)
        return {"database_environment": manager.active_environment, **result}

    @app.get("/api/workflow-versions/{version_id}")
    def get_workflow_version(version_id: str) -> dict[str, object]:
        version = manager.get_workflow_version(version_id)
        if not version:
            raise HTTPException(status_code=404, detail="工作流版本不存在。")
        return {"database_environment": manager.active_environment, "version": version}

    @app.get("/api/workflows/{workflow_id}/draft")
    def get_workflow_draft(workflow_id: str) -> dict[str, object]:
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        return {"database_environment": manager.active_environment, "draft": draft}

    @app.put("/api/workflows/{workflow_id}/draft")
    def save_workflow_draft(workflow_id: str, request: SaveDraftRequest) -> dict[str, object]:
        try:
            draft = manager.save_workflow_draft(
                workflow_id,
                normalized_graph=request.normalized_graph,
                raw_ui_json=request.raw_ui_json,
                raw_api_json=request.raw_api_json,
                node_count=request.node_count,
                semantic_slots_json=request.semantic_slots_json,
                last_node_id=request.last_node_id,
                last_link_id=request.last_link_id,
                validation_state=request.validation_state,
                layout_state=request.layout_state,
                is_dirty=request.is_dirty,
                expected_revision=request.expected_revision,
            )
        except ValueError as error:
            msg = str(error)
            if "草稿修订号不匹配" in msg:
                raise HTTPException(status_code=409, detail=msg) from error
            raise HTTPException(status_code=404, detail=msg) from error
        return {"database_environment": manager.active_environment, "draft": draft}

    @app.post("/api/workflows/{workflow_id}/draft/validate")
    def validate_workflow_draft(workflow_id: str) -> dict[str, object]:
        """校验工作流草稿的节点和参数。

        基于 ComfyUI 节点定义校验：
        - 未知节点（ComfyUI 未安装）
        - 节点定义未同步
        - 必填输入未连线
        - 参数缺失
        - 连线完整性（悬空节点）
        - 重复连线
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        node_classes = [str(node.get("type", "")) for node in normalized.nodes]
        definitions = manager.batch_get_node_definitions(node_classes)
        result = validate_workflow(normalized, definitions)
        # 保存校验状态到草稿
        validation_state = json.dumps(result, ensure_ascii=False)
        try:
            manager.save_workflow_draft(
                workflow_id,
                normalized_graph=draft["normalized_graph"],
                raw_ui_json=draft.get("raw_ui_json"),
                raw_api_json=draft.get("raw_api_json"),
                node_count=draft["node_count"],
                semantic_slots_json=draft.get("semantic_slots_json", "[]"),
                last_node_id=draft.get("last_node_id", 0),
                last_link_id=draft.get("last_link_id", 0),
                validation_state=validation_state,
            )
        except ValueError:
            pass
        return {"database_environment": manager.active_environment, "validation": result}

    @app.post("/api/comfyui/node-definitions/batch")
    def batch_get_node_definitions(request: BatchNodeDefinitionsRequest) -> dict[str, object]:
        """批量获取节点定义。"""
        definitions = manager.batch_get_node_definitions(request.node_classes)
        return {
            "database_environment": manager.active_environment,
            "definitions": definitions,
            "found_count": len(definitions),
            "missing_classes": [cls for cls in request.node_classes if cls and cls not in definitions],
        }

    @app.get("/api/workflows/{workflow_id}/node-definitions")
    def get_workflow_node_definitions(workflow_id: str) -> dict[str, object]:
        """获取工作流草稿所需的所有节点定义。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        node_classes = [str(node.get("type", "")) for node in normalized.nodes]
        definitions = manager.batch_get_node_definitions(node_classes)
        return {
            "database_environment": manager.active_environment,
            "definitions": definitions,
            "found_count": len(definitions),
            "missing_classes": [cls for cls in node_classes if cls and cls not in definitions],
        }

    @app.post("/api/workflows/{workflow_id}/draft/nodes")
    def add_node_to_draft(workflow_id: str, request: AddNodeRequest) -> dict[str, object]:
        """向草稿添加节点。根据节点定义生成默认节点实例。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        definition = manager.get_node_definition(request.node_class)
        if definition is None:
            raise HTTPException(
                status_code=404,
                detail=f"节点定义未同步：{request.node_class}。请先同步 ComfyUI 节点定义。",
            )
        new_id, new_last = allocate_node_id(normalized, draft.get("last_node_id", 0))
        node = build_default_node(
            request.node_class,
            definition,
            node_id=new_id,
            position=(request.position_x, request.position_y),
        )
        normalized.nodes.append(node)
        serialized = serialize_workflow(normalized)
        updated_draft = manager.save_workflow_draft(
            workflow_id,
            normalized_graph=json.dumps(serialized["normalized"], ensure_ascii=False),
            raw_ui_json=draft.get("raw_ui_json"),
            raw_api_json=draft.get("raw_api_json"),
            node_count=serialized["node_count"],
            semantic_slots_json=draft.get("semantic_slots_json", "[]"),
            last_node_id=new_last,
            last_link_id=draft.get("last_link_id", 0),
            is_dirty=True,
            draft_checksum=serialized["checksum"],
        )
        return {
            "database_environment": manager.active_environment,
            "node": node,
            "draft": updated_draft,
        }

    @app.put("/api/workflows/{workflow_id}/draft/nodes/{node_id}")
    def update_node_in_draft(
        workflow_id: str, node_id: str, request: UpdateNodeRequest
    ) -> dict[str, object]:
        """更新草稿中的节点（标题/参数/标志/属性）。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        target = None
        for node in normalized.nodes:
            if str(node.get("id", "")) == node_id:
                target = node
                break
        if target is None:
            raise HTTPException(status_code=404, detail="节点不存在。")
        if target.get("is_unknown"):
            raise HTTPException(
                status_code=422,
                detail="未知节点为只读，无法编辑。请先安装对应 ComfyUI 节点。",
            )
        if request.title is not None:
            target["title"] = request.title
        if request.widgets_values is not None:
            target["widgets_values"] = request.widgets_values
            # 同步值类型输入：按顺序将 widgets_values 写回无连线的 inputs[].value，
            # 保证 normalized 结构内部一致，导出 API JSON 时反映最新值。
            value_idx = 0
            for inp in target.get("inputs", []) if isinstance(target.get("inputs"), list) else []:
                if inp.get("link"):
                    continue  # 有连线，跳过
                if value_idx < len(request.widgets_values):
                    inp["value"] = request.widgets_values[value_idx]
                    value_idx += 1
        if request.flags is not None:
            current_flags = target.get("flags", {}) if isinstance(target.get("flags"), dict) else {}
            current_flags.update(request.flags)
            target["flags"] = current_flags
        if request.properties is not None:
            current_props = target.get("properties", {}) if isinstance(target.get("properties"), dict) else {}
            current_props.update(request.properties)
            target["properties"] = current_props
        serialized = serialize_workflow(normalized)
        updated_draft = manager.save_workflow_draft(
            workflow_id,
            normalized_graph=json.dumps(serialized["normalized"], ensure_ascii=False),
            raw_ui_json=draft.get("raw_ui_json"),
            raw_api_json=draft.get("raw_api_json"),
            node_count=serialized["node_count"],
            semantic_slots_json=draft.get("semantic_slots_json", "[]"),
            last_node_id=draft.get("last_node_id", 0),
            last_link_id=draft.get("last_link_id", 0),
            is_dirty=True,
            draft_checksum=serialized["checksum"],
        )
        return {
            "database_environment": manager.active_environment,
            "node": target,
            "draft": updated_draft,
        }

    @app.delete("/api/workflows/{workflow_id}/draft/nodes/{node_id}")
    def delete_node_from_draft(workflow_id: str, node_id: str) -> dict[str, object]:
        """删除草稿中的节点及其关联连线。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        original_count = len(normalized.nodes)
        normalized.nodes = [n for n in normalized.nodes if str(n.get("id", "")) != node_id]
        if len(normalized.nodes) == original_count:
            raise HTTPException(status_code=404, detail="节点不存在。")
        # 移除关联连线，并清理其他节点上对该连线的引用
        removed_link_ids = {
            str(link.get("id", ""))
            for link in normalized.links
            if str(link.get("source_node", "")) == node_id
            or str(link.get("target_node", "")) == node_id
        }
        normalized.links = [
            link for link in normalized.links
            if str(link.get("id", "")) not in removed_link_ids
        ]
        for node in normalized.nodes:
            for inp in node.get("inputs", []) if isinstance(node.get("inputs"), list) else []:
                if inp.get("link") and str(inp.get("link")) in removed_link_ids:
                    inp["link"] = None
            for out in node.get("outputs", []) if isinstance(node.get("outputs"), list) else []:
                if isinstance(out.get("links"), list):
                    out["links"] = [lid for lid in out["links"] if str(lid) not in removed_link_ids]
        serialized = serialize_workflow(normalized)
        updated_draft = manager.save_workflow_draft(
            workflow_id,
            normalized_graph=json.dumps(serialized["normalized"], ensure_ascii=False),
            raw_ui_json=draft.get("raw_ui_json"),
            raw_api_json=draft.get("raw_api_json"),
            node_count=serialized["node_count"],
            semantic_slots_json=draft.get("semantic_slots_json", "[]"),
            last_node_id=draft.get("last_node_id", 0),
            last_link_id=draft.get("last_link_id", 0),
            is_dirty=True,
            draft_checksum=serialized["checksum"],
        )
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "removed_links": list(removed_link_ids),
            "draft": updated_draft,
        }

    @app.post("/api/workflows/{workflow_id}/draft/nodes/{node_id}/duplicate")
    def duplicate_node_in_draft(workflow_id: str, node_id: str) -> dict[str, object]:
        """复制草稿中的节点（含参数，但不复制连线）。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        source = None
        for node in normalized.nodes:
            if str(node.get("id", "")) == node_id:
                source = node
                break
        if source is None:
            raise HTTPException(status_code=404, detail="节点不存在。")
        new_id, new_last = allocate_node_id(normalized, draft.get("last_node_id", 0))
        # 深拷贝并清空连线状态
        new_node = json.loads(json.dumps(source, ensure_ascii=False))
        new_node["id"] = new_id
        new_node["title"] = f"{source.get('title', source.get('type', '节点'))}_copy"
        old_position = source.get("position", [0, 0])
        new_node["position"] = [int(old_position[0]) + 40 if isinstance(old_position, list) and len(old_position) >= 2 else 40, int(old_position[1]) + 40 if isinstance(old_position, list) and len(old_position) >= 2 else 40]
        for inp in new_node.get("inputs", []) if isinstance(new_node.get("inputs"), list) else []:
            inp["link"] = None
        for out in new_node.get("outputs", []) if isinstance(new_node.get("outputs"), list) else []:
            if isinstance(out.get("links"), list):
                out["links"] = []
        normalized.nodes.append(new_node)
        serialized = serialize_workflow(normalized)
        updated_draft = manager.save_workflow_draft(
            workflow_id,
            normalized_graph=json.dumps(serialized["normalized"], ensure_ascii=False),
            raw_ui_json=draft.get("raw_ui_json"),
            raw_api_json=draft.get("raw_api_json"),
            node_count=serialized["node_count"],
            semantic_slots_json=draft.get("semantic_slots_json", "[]"),
            last_node_id=new_last,
            last_link_id=draft.get("last_link_id", 0),
            is_dirty=True,
            draft_checksum=serialized["checksum"],
        )
        return {
            "database_environment": manager.active_environment,
            "node": new_node,
            "draft": updated_draft,
        }

    @app.post("/api/workflows/{workflow_id}/draft/links")
    def create_link_in_draft(
        workflow_id: str, request: CreateLinkRequest
    ) -> dict[str, object]:
        """创建连线。会进行端口类型校验。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        source_node = None
        target_node = None
        for node in normalized.nodes:
            if str(node.get("id", "")) == request.source_node:
                source_node = node
            if str(node.get("id", "")) == request.target_node:
                target_node = node
        if source_node is None:
            raise HTTPException(status_code=404, detail="源节点不存在。")
        if target_node is None:
            raise HTTPException(status_code=404, detail="目标节点不存在。")
        if source_node.get("is_unknown") or target_node.get("is_unknown"):
            raise HTTPException(status_code=422, detail="未知节点不参与连线。")
        source_outputs = source_node.get("outputs", []) if isinstance(source_node.get("outputs"), list) else []
        target_inputs = target_node.get("inputs", []) if isinstance(target_node.get("inputs"), list) else []
        if request.source_slot >= len(source_outputs):
            raise HTTPException(status_code=422, detail=f"源节点输出端口 {request.source_slot} 不存在。")
        if request.target_slot >= len(target_inputs):
            raise HTTPException(status_code=422, detail=f"目标节点输入端口 {request.target_slot} 不存在。")
        source_port = source_outputs[request.source_slot]
        target_port = target_inputs[request.target_slot]
        source_type = str(source_port.get("type", ""))
        target_type = str(target_port.get("type", ""))
        compatible, reason = are_ports_compatible(source_type, target_type)
        if not compatible:
            raise HTTPException(status_code=422, detail=f"端口类型不兼容：{reason}")
        # 一个输入只能连一根线，先断开旧线
        existing_link = target_port.get("link")
        removed_link_ids: list[str] = []
        if existing_link:
            normalized.links = [
                link for link in normalized.links
                if str(link.get("id", "")) != str(existing_link)
            ]
            removed_link_ids.append(str(existing_link))
        new_id, new_last = allocate_link_id(normalized, draft.get("last_link_id", 0))
        link = {
            "id": new_id,
            "source_node": request.source_node,
            "source_slot": request.source_slot,
            "target_node": request.target_node,
            "target_slot": request.target_slot,
            "type": request.link_type or (source_type if source_type else target_type),
        }
        normalized.links.append(link)
        target_port["link"] = new_id
        if isinstance(source_port.get("links"), list):
            if new_id not in source_port["links"]:
                source_port["links"].append(new_id)
        else:
            source_port["links"] = [new_id]
        serialized = serialize_workflow(normalized)
        updated_draft = manager.save_workflow_draft(
            workflow_id,
            normalized_graph=json.dumps(serialized["normalized"], ensure_ascii=False),
            raw_ui_json=draft.get("raw_ui_json"),
            raw_api_json=draft.get("raw_api_json"),
            node_count=serialized["node_count"],
            semantic_slots_json=draft.get("semantic_slots_json", "[]"),
            last_node_id=draft.get("last_node_id", 0),
            last_link_id=new_last,
            is_dirty=True,
            draft_checksum=serialized["checksum"],
        )
        return {
            "database_environment": manager.active_environment,
            "link": link,
            "removed_links": removed_link_ids,
            "draft": updated_draft,
        }

    @app.delete("/api/workflows/{workflow_id}/draft/links/{link_id}")
    def delete_link_from_draft(workflow_id: str, link_id: str) -> dict[str, object]:
        """删除连线。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        original_count = len(normalized.links)
        target_link = None
        for link in normalized.links:
            if str(link.get("id", "")) == link_id:
                target_link = link
                break
        if target_link is None:
            raise HTTPException(status_code=404, detail="连线不存在。")
        normalized.links = [
            link for link in normalized.links
            if str(link.get("id", "")) != link_id
        ]
        # 清理端口引用
        source_node_id = str(target_link.get("source_node", ""))
        target_node_id = str(target_link.get("target_node", ""))
        source_slot = target_link.get("source_slot")
        target_slot = target_link.get("target_slot")
        for node in normalized.nodes:
            if str(node.get("id", "")) == source_node_id:
                for out in node.get("outputs", []) if isinstance(node.get("outputs"), list) else []:
                    if isinstance(out.get("links"), list):
                        out["links"] = [lid for lid in out["links"] if str(lid) != link_id]
            if str(node.get("id", "")) == target_node_id:
                for inp in node.get("inputs", []) if isinstance(node.get("inputs"), list) else []:
                    if str(inp.get("link", "")) == link_id:
                        inp["link"] = None
        serialized = serialize_workflow(normalized)
        updated_draft = manager.save_workflow_draft(
            workflow_id,
            normalized_graph=json.dumps(serialized["normalized"], ensure_ascii=False),
            raw_ui_json=draft.get("raw_ui_json"),
            raw_api_json=draft.get("raw_api_json"),
            node_count=serialized["node_count"],
            semantic_slots_json=draft.get("semantic_slots_json", "[]"),
            last_node_id=draft.get("last_node_id", 0),
            last_link_id=draft.get("last_link_id", 0),
            is_dirty=True,
            draft_checksum=serialized["checksum"],
        )
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "draft": updated_draft,
        }

    # ── 规整布局 API (v0.5.8) ──────────────────────────────────────

    def _load_draft_layout_state(draft: dict) -> dict:
        """从草稿加载布局状态。返回 {user_order_constraints, groups}。"""
        layout_state_raw = draft.get("layout_state")
        if not layout_state_raw:
            return {"user_order_constraints": {}, "groups": []}
        try:
            state = json.loads(layout_state_raw)
            if not isinstance(state, dict):
                return {"user_order_constraints": {}, "groups": []}
            return {
                "user_order_constraints": state.get("user_order_constraints", {}) if isinstance(state.get("user_order_constraints"), dict) else {},
                "groups": state.get("groups", []) if isinstance(state.get("groups"), list) else [],
            }
        except (TypeError, ValueError):
            return {"user_order_constraints": {}, "groups": []}

    def _save_draft_layout_state(
        workflow_id: str, draft: dict, layout_state: dict
    ) -> dict:
        """保存布局状态到草稿并返回更新后的草稿。

        布局操作视为编辑，标记 is_dirty=True。
        """
        # 计算当前草稿校验和
        try:
            current_normalized = NormalizedWorkflow.from_dict(
                json.loads(draft["normalized_graph"])
            )
            current_checksum = current_normalized.checksum()
        except (TypeError, ValueError, KeyError):
            current_checksum = ""
        try:
            updated = manager.save_workflow_draft(
                workflow_id,
                normalized_graph=draft["normalized_graph"],
                raw_ui_json=draft.get("raw_ui_json"),
                raw_api_json=draft.get("raw_api_json"),
                node_count=draft["node_count"],
                semantic_slots_json=draft.get("semantic_slots_json", "[]"),
                last_node_id=draft.get("last_node_id", 0),
                last_link_id=draft.get("last_link_id", 0),
                validation_state=draft.get("validation_state"),
                layout_state=json.dumps(layout_state, ensure_ascii=False),
                is_dirty=True,
                draft_checksum=current_checksum,
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return updated

    @app.post("/api/workflows/{workflow_id}/draft/layout/compute")
    def compute_workflow_layout(workflow_id: str) -> dict[str, object]:
        """计算并应用自动布局。

        基于拓扑分层算法计算节点位置，应用用户排序约束和分组泳道。
        计算结果会保存到草稿的 layout_state 中，节点位置也会更新到 normalized_graph。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        state = _load_draft_layout_state(draft)
        layout = compute_layout(
            normalized,
            user_order_constraints=state["user_order_constraints"],
            groups=state["groups"],
        )
        # 应用位置到节点
        apply_layout(normalized, layout)
        serialized = serialize_workflow(normalized)
        layout_state = {
            "user_order_constraints": state["user_order_constraints"],
            "groups": state["groups"],
            "layout": layout,
        }
        updated_draft = _save_draft_layout_state(
            workflow_id,
            {**draft, "normalized_graph": json.dumps(serialized["normalized"], ensure_ascii=False)},
            layout_state,
        )
        return {
            "database_environment": manager.active_environment,
            "layout": layout,
            "draft": updated_draft,
        }

    @app.get("/api/workflows/{workflow_id}/draft/layout")
    def get_workflow_layout(workflow_id: str) -> dict[str, object]:
        """获取当前布局状态。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        state = _load_draft_layout_state(draft)
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        # 实时计算布局（不保存），确保与当前节点状态同步
        layout = compute_layout(
            normalized,
            user_order_constraints=state["user_order_constraints"],
            groups=state["groups"],
        )
        return {
            "database_environment": manager.active_environment,
            "layout": layout,
            "user_order_constraints": state["user_order_constraints"],
            "groups": state["groups"],
        }

    @app.put("/api/workflows/{workflow_id}/draft/layout")
    def save_workflow_layout_state(
        workflow_id: str, request: SaveLayoutStateRequest
    ) -> dict[str, object]:
        """保存布局状态（用户排序约束和分组信息）。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            json.loads(request.layout_state)  # 验证是合法JSON
        except (TypeError, ValueError) as error:
            raise HTTPException(
                status_code=422, detail=f"布局状态JSON格式无效：{error}"
            ) from error
        updated_draft = _save_draft_layout_state(workflow_id, draft, {"raw": request.layout_state})
        return {
            "database_environment": manager.active_environment,
            "draft": updated_draft,
        }

    @app.post("/api/workflows/{workflow_id}/draft/nodes/{node_id}/reorder")
    def reorder_workflow_node(
        workflow_id: str, node_id: str, request: ReorderNodeRequest
    ) -> dict[str, object]:
        """对节点执行结构化排序操作。

        支持的操作：前移、后移、换列（上一列/下一列）、置顶、置底。
        操作会更新用户排序约束，并重新计算布局。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        state = _load_draft_layout_state(draft)
        try:
            result = reorder_node(
                normalized,
                node_id,
                request.action,
                user_order_constraints=state["user_order_constraints"],
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        # 应用新布局到节点
        apply_layout(normalized, result["layout"])
        serialized = serialize_workflow(normalized)
        new_state = {
            "user_order_constraints": result["user_order_constraints"],
            "groups": state["groups"],
            "layout": result["layout"],
        }
        updated_draft = _save_draft_layout_state(
            workflow_id,
            {**draft, "normalized_graph": json.dumps(serialized["normalized"], ensure_ascii=False)},
            new_state,
        )
        return {
            "database_environment": manager.active_environment,
            "layout": result["layout"],
            "user_order_constraints": result["user_order_constraints"],
            "draft": updated_draft,
        }

    @app.post("/api/workflows/{workflow_id}/draft/groups")
    def create_workflow_group(
        workflow_id: str, request: CreateGroupRequest
    ) -> dict[str, object]:
        """创建分组泳道。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        state = _load_draft_layout_state(draft)
        # 校验成员是否存在
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        existing_ids = {str(n.get("id", "")) for n in normalized.nodes}
        valid_members = [m for m in request.members if str(m) in existing_ids]
        group = create_group(
            request.title,
            color=request.color,
            members=valid_members,
        )
        new_groups = state["groups"] + [group]
        new_state = {
            "user_order_constraints": state["user_order_constraints"],
            "groups": new_groups,
        }
        updated_draft = _save_draft_layout_state(workflow_id, draft, new_state)
        return {
            "database_environment": manager.active_environment,
            "group": group,
            "draft": updated_draft,
        }

    @app.put("/api/workflows/{workflow_id}/draft/groups/{group_id}")
    def update_workflow_group(
        workflow_id: str, group_id: str, request: UpdateGroupRequest
    ) -> dict[str, object]:
        """更新分组泳道的标题或颜色。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        state = _load_draft_layout_state(draft)
        found = False
        new_groups: list[dict[str, object]] = []
        for group in state["groups"]:
            new_group = dict(group)
            if str(group.get("id", "")) == group_id:
                if request.title is not None:
                    new_group["title"] = request.title
                if request.color is not None:
                    new_group["color"] = request.color
                found = True
            new_groups.append(new_group)
        if not found:
            raise HTTPException(status_code=404, detail="分组不存在。")
        new_state = {
            "user_order_constraints": state["user_order_constraints"],
            "groups": new_groups,
        }
        updated_draft = _save_draft_layout_state(workflow_id, draft, new_state)
        return {
            "database_environment": manager.active_environment,
            "groups": new_groups,
            "draft": updated_draft,
        }

    @app.delete("/api/workflows/{workflow_id}/draft/groups/{group_id}")
    def delete_workflow_group(workflow_id: str, group_id: str) -> dict[str, object]:
        """删除分组泳道（不影响节点）。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        state = _load_draft_layout_state(draft)
        original_count = len(state["groups"])
        new_groups = [g for g in state["groups"] if str(g.get("id", "")) != group_id]
        if len(new_groups) == original_count:
            raise HTTPException(status_code=404, detail="分组不存在。")
        new_state = {
            "user_order_constraints": state["user_order_constraints"],
            "groups": new_groups,
        }
        updated_draft = _save_draft_layout_state(workflow_id, draft, new_state)
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "draft": updated_draft,
        }

    @app.post("/api/workflows/{workflow_id}/draft/nodes/{node_id}/assign-group")
    def assign_node_to_workflow_group(
        workflow_id: str, node_id: str, request: AssignGroupRequest
    ) -> dict[str, object]:
        """将节点加入或移出分组泳道。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        existing_ids = {str(n.get("id", "")) for n in normalized.nodes}
        if node_id not in existing_ids:
            raise HTTPException(status_code=404, detail="节点不存在。")
        state = _load_draft_layout_state(draft)
        if request.group_id is not None:
            valid_group_ids = {str(g.get("id", "")) for g in state["groups"]}
            if request.group_id not in valid_group_ids:
                raise HTTPException(status_code=404, detail="分组不存在。")
        new_groups = assign_node_to_group(state["groups"], node_id, request.group_id)
        new_state = {
            "user_order_constraints": state["user_order_constraints"],
            "groups": new_groups,
        }
        updated_draft = _save_draft_layout_state(workflow_id, draft, new_state)
        return {
            "database_environment": manager.active_environment,
            "groups": new_groups,
            "draft": updated_draft,
        }

    @app.get("/api/workflows/{workflow_id}/draft/links/bundles")
    def get_workflow_link_bundles(workflow_id: str) -> dict[str, object]:
        """获取连线合束信息和类型提示。"""
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        bundles = compute_link_bundles(normalized)
        return {
            "database_environment": manager.active_environment,
            **bundles,
        }

    @app.post("/api/workflows/{workflow_id}/draft/focus")
    def compute_workflow_focus(
        workflow_id: str, request: FocusSubgraphRequest
    ) -> dict[str, object]:
        """计算聚焦节点的上游/下游/错误子图。

        返回高亮节点、变暗节点和相关连线，用于前端高亮显示。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        try:
            focus = compute_focus_subgraph(
                normalized,
                request.node_id,
                request.direction,
                error_node_ids=request.error_node_ids,
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "focus": focus,
        }

    @app.post("/api/workflows/{workflow_id}/draft/layout/perf-test")
    def perf_test_workflow_layout(workflow_id: str) -> dict[str, object]:
        """500节点性能测试：生成大规模工作流并计算布局，返回耗时。

        仅供开发/测试环境使用，不会修改草稿数据。
        """
        import time
        large_wf = generate_large_workflow(500)
        start = time.perf_counter()
        layout = compute_layout(large_wf)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {
            "database_environment": manager.active_environment,
            "node_count": 500,
            "link_count": len(large_wf.links),
            "layer_count": len(layout["layers"]),
            "elapsed_ms": round(elapsed_ms, 2),
            "layout_summary": {
                "positions_count": len(layout["positions"]),
                "groups_count": len(layout["groups"]),
                "cycle_nodes_count": len(layout["cycle_nodes"]),
            },
        }

    @app.post("/api/workflows/{workflow_id}/set-global-default")
    def set_global_default_workflow(workflow_id: str) -> dict[str, object]:
        try:
            result = manager.set_global_default_workflow(workflow_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"database_environment": manager.active_environment, **result}

    @app.post("/api/projects/{project_id}/default-workflow")
    def set_project_default_workflow(
        project_id: str, request: SetProjectDefaultWorkflowRequest
    ) -> dict[str, object]:
        try:
            result = manager.set_project_default_workflow(project_id, request.workflow_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"database_environment": manager.active_environment, **result}

    @app.get("/api/projects/{project_id}/default-workflow")
    def get_project_default_workflow(project_id: str) -> dict[str, object]:
        workflow = manager.get_project_default_workflow(project_id)
        if not workflow:
            raise HTTPException(status_code=404, detail="项目未设置默认工作流。")
        return {"database_environment": manager.active_environment, "workflow": workflow}

    @app.get("/api/workflows/{workflow_id}/semantic-slots")
    def list_semantic_slots(workflow_id: str) -> dict[str, object]:
        slots = manager.list_semantic_slots(workflow_id)
        return {"database_environment": manager.active_environment, "slots": slots}

    @app.put("/api/workflows/{workflow_id}/semantic-slots")
    def set_semantic_slot(
        workflow_id: str, request: SetSemanticSlotRequest
    ) -> dict[str, object]:
        slot = manager.set_semantic_slot(
            workflow_id,
            request.slot_name,
            slot_type=request.slot_type,
            node_id=request.node_id,
            input_name=request.input_name,
            transform_rule=request.transform_rule,
            default_value=request.default_value,
            is_required=request.is_required,
            conflict_strategy=request.conflict_strategy,
        )
        return {"database_environment": manager.active_environment, "slot": slot}

    @app.delete("/api/workflows/{workflow_id}/semantic-slots/{slot_name}")
    def delete_semantic_slot(workflow_id: str, slot_name: str) -> dict[str, object]:
        deleted = manager.delete_semantic_slot(workflow_id, slot_name)
        if not deleted:
            raise HTTPException(status_code=404, detail="语义插槽不存在。")
        return {"database_environment": manager.active_environment, "deleted": True}

    # ── 语义插槽解析与校验 API (v0.5.9) ───────────────────────────

    @app.get("/api/slot-definitions")
    def list_slot_definitions() -> dict[str, object]:
        """列出所有内置插槽定义。"""
        return {
            "database_environment": manager.active_environment,
            "definitions": list_builtin_slot_definitions(),
        }

    @app.post("/api/workflows/{workflow_id}/slots/resolve")
    def resolve_workflow_slots(
        workflow_id: str, request: ResolveSlotsRequest
    ) -> dict[str, object]:
        """解析工作流的所有语义插槽（预览）。

        根据业务上下文（人物值、素材值、项目默认配置）解析每个插槽的最终值。
        不修改工作流草稿，仅返回解析结果。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        slots = manager.list_semantic_slots(workflow_id)
        result = resolve_all_slots(slots, normalized, context=request.context)
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.post("/api/workflows/{workflow_id}/slots/validate")
    def validate_workflow_slots(workflow_id: str) -> dict[str, object]:
        """校验工作流的插槽绑定是否有效。

        检查节点存在性、输入名存在性、冲突策略有效性、插槽名唯一性。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        slots = manager.list_semantic_slots(workflow_id)
        result = validate_slot_bindings(slots, normalized)
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    # ── 阶段 2.6 转换、校验和发布 ────────────────────────────────

    @app.post("/api/workflows/{workflow_id}/export")
    def export_workflow_api(workflow_id: str, request: ExportWorkflowRequest) -> dict[str, object]:
        """导出工作流为 API JSON 或 UI JSON 格式。

        - 未编辑（is_dirty=False）：优先返回来源快照，保证未知字段不丢失。
        - 已编辑（is_dirty=True）：必须从 normalized_graph 重新生成，不返回旧 JSON。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        raw_ui_json = json.loads(draft["raw_ui_json"]) if draft.get("raw_ui_json") else None
        raw_api_json = json.loads(draft["raw_api_json"]) if draft.get("raw_api_json") else None
        is_dirty = bool(draft.get("is_dirty", False))
        try:
            result = export_workflow(
                normalized,
                format=request.format,
                raw_ui_json=raw_ui_json,
                raw_api_json=raw_api_json,
                is_dirty=is_dirty,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            **result,
            "is_dirty": is_dirty,
            "draft_revision": int(draft.get("draft_revision", 0)),
            "source_checksum": draft.get("source_checksum", ""),
            "draft_checksum": draft.get("draft_checksum", ""),
        }

    @app.post("/api/workflows/{workflow_id}/precheck")
    def precheck_workflow_publish(workflow_id: str) -> dict[str, object]:
        """发布前预检查：节点定义、必填输入、模型资源、连线完整性、语义插槽。

        返回阻塞错误和警告列表，can_publish 为 True 时才允许发布。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        try:
            normalized_data = json.loads(draft["normalized_graph"])
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        node_classes = [str(node.get("type", "")) for node in normalized.nodes]
        definitions = manager.batch_get_node_definitions(node_classes)
        slots = manager.list_semantic_slots(workflow_id)
        result = precheck_publish(normalized, definitions, semantic_slots=slots)
        return {"database_environment": manager.active_environment, **result}

    @app.post("/api/workflows/{workflow_id}/publish")
    def publish_workflow_from_draft(workflow_id: str, request: PublishVersionRequest) -> dict[str, object]:
        """基于草稿发布不可变版本。

        如果 request.normalized_graph 为空，则使用当前草稿的规范化结构。
        发布前建议先调用 /precheck 检查。

        当草稿已被编辑（is_dirty=True）时：
        - raw_ui_json/raw_api_json 留空，避免发布来源旧 JSON。
        - 版本只保存当前草稿的 normalized_graph。
        """
        draft = manager.get_workflow_draft(workflow_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在。")
        normalized_graph = request.normalized_graph or draft["normalized_graph"]
        is_dirty = bool(draft.get("is_dirty", False))
        try:
            normalized_data = json.loads(normalized_graph)
            normalized = NormalizedWorkflow.from_dict(normalized_data)
        except (TypeError, ValueError, KeyError) as error:
            raise HTTPException(
                status_code=422, detail=f"草稿数据解析失败：{error}"
            ) from error
        # 已编辑时不发布来源旧 JSON；未编辑时保留来源快照用于审计
        if is_dirty:
            raw_ui_json = request.raw_ui_json
            raw_api_json = request.raw_api_json
        else:
            raw_ui_json = request.raw_ui_json or draft.get("raw_ui_json")
            raw_api_json = request.raw_api_json or draft.get("raw_api_json")
        try:
            version = manager.publish_workflow_version(
                workflow_id,
                label=request.label,
                normalized_graph=normalized_graph,
                raw_ui_json=raw_ui_json,
                raw_api_json=raw_api_json,
                node_count=normalized.node_count(),
                checksum=normalized.checksum(),
                is_validated=request.is_validated,
                validation_result=request.validation_result,
            )
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"database_environment": manager.active_environment, "version": version}

    @app.post("/api/workflows/roundtrip-test")
    def roundtrip_test_api(request: RoundtripTestRequest) -> dict[str, object]:
        """往返测试：导入—导出—重新导入，验证数据完整性。

        不写入数据库，仅用于验证工作流转换的正确性。
        """
        try:
            result = roundtrip_test(request.workflow, request.source_format)
        except Exception as error:
            raise HTTPException(
                status_code=422, detail=f"往返测试失败：{error}"
            ) from error
        return {"database_environment": manager.active_environment, **result}

    @app.get("/api/projects")
    def list_projects(
        q: str | None = None,
        status: str | None = None,
        archived: bool = False,
        trash: bool = False,
        sort: str = "updated",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        result = manager.list_projects(
            query=q,
            status=status,
            include_archived=archived,
            include_deleted=trash,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        return {
            "database_environment": manager.active_environment,
            "items": result["items"],
            "total": result["total"],
            "limit": result["limit"],
            "offset": result["offset"],
            "has_more": result["has_more"],
        }

    @app.post("/api/projects", status_code=status.HTTP_201_CREATED)
    def create_project(request: CreateProjectRequest) -> dict[str, object]:
        try:
            project = manager.create_project(request.name, request.description)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "project": project,
        }

    @app.get("/api/projects/{project_id}")
    def get_project(project_id: str) -> dict[str, object]:
        project = manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在。")
        return {
            "database_environment": manager.active_environment,
            "project": project,
        }

    @app.patch("/api/projects/{project_id}")
    def update_project(project_id: str, request: UpdateProjectRequest) -> dict[str, object]:
        try:
            project = manager.update_project(
                project_id,
                name=request.name,
                description=request.description,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在。")
        return {
            "database_environment": manager.active_environment,
            "project": project,
        }

    @app.post("/api/projects/{project_id}/archive")
    def archive_project(project_id: str) -> dict[str, object]:
        project = manager.archive_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在。")
        return {
            "database_environment": manager.active_environment,
            "project": project,
        }

    @app.post("/api/projects/{project_id}/restore")
    def restore_project(project_id: str) -> dict[str, object]:
        project = manager.restore_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在。")
        return {
            "database_environment": manager.active_environment,
            "project": project,
        }

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str) -> dict[str, object]:
        project = manager.soft_delete_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在。")
        return {
            "database_environment": manager.active_environment,
            "project": project,
        }

    @app.delete("/api/projects/{project_id}/permanent")
    def permanent_delete_project(project_id: str) -> dict[str, object]:
        cover_dir = manager.data_root / "projects" / project_id
        if cover_dir.exists():
            try:
                shutil.rmtree(cover_dir)
            except OSError:
                pass
        deleted = manager.permanent_delete_project(project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="项目不存在。")
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "project_id": project_id,
        }

    @app.post("/api/projects/{project_id}/copy", status_code=status.HTTP_201_CREATED)
    def copy_project(project_id: str, request: CopyProjectRequest) -> dict[str, object]:
        try:
            project = manager.copy_project(project_id, request.name)
        except ValueError as error:
            msg = str(error)
            if "不存在" in msg:
                raise HTTPException(status_code=404, detail=msg) from error
            raise HTTPException(status_code=422, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "project": project,
        }

    @app.get("/api/projects/{project_id}/overview")
    def get_project_overview(project_id: str) -> dict[str, object]:
        project = manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在。")
        stats = manager.get_project_stats(project_id)
        return {
            "database_environment": manager.active_environment,
            "project": project,
            "stats": stats,
            "blockers": _detect_project_blockers(project, stats),
        }

    @app.post("/api/projects/{project_id}/cover")
    async def upload_project_cover(
        project_id: str,
        file: UploadFile = File(...),
    ) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")

        MAX_SIZE = 20 * 1024 * 1024  # 20 MB
        contents = await file.read()
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="项目封面文件超过 20 MB 限制。")
        if not contents:
            raise HTTPException(status_code=422, detail="项目封面文件为空。")

        try:
            image = Image.open(io.BytesIO(contents))
            image.load()
        except (UnidentifiedImageError, OSError) as error:
            raise HTTPException(
                status_code=415,
                detail="项目封面格式不支持或文件已损坏。",
            ) from error

        if image.width > 16384 or image.height > 16384:
            raise HTTPException(
                status_code=422,
                detail="项目封面最长边不得超过 16,384 像素。",
            )

        ext_map = {
            "JPEG": "jpg",
            "PNG": "png",
            "WEBP": "webp",
        }
        fmt = image.format
        if fmt not in ext_map:
            raise HTTPException(
                status_code=415,
                detail="项目封面格式不支持，仅接受 JPG、PNG、WebP。",
            )

        cover_dir = manager.data_root / "projects" / project_id
        cover_dir.mkdir(parents=True, exist_ok=True)
        original_filename = f"cover.{ext_map[fmt]}"
        thumbnail_filename = "cover_thumb.webp"
        original_path = cover_dir / original_filename
        thumbnail_path = cover_dir / thumbnail_filename
        tmp_original = cover_dir / f"{original_filename}.tmp"
        tmp_thumbnail = cover_dir / f"{thumbnail_filename}.tmp"

        try:
            save_image = image
            if fmt == "JPEG" and save_image.mode not in ("RGB", "L"):
                save_image = save_image.convert("RGB")
            save_image.save(tmp_original, format=fmt)

            thumb = image.copy()
            thumb.thumbnail((512, 512), Image.Resampling.LANCZOS)
            if thumb.mode not in ("RGB", "RGBA"):
                thumb = thumb.convert("RGB")
            thumb.save(tmp_thumbnail, format="WEBP", quality=82)
        except OSError as error:
            for tmp in (tmp_original, tmp_thumbnail):
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
            raise HTTPException(
                status_code=422,
                detail="项目封面处理失败，请检查图片内容。",
            ) from error

        if original_path.exists():
            original_path.unlink()
        tmp_original.replace(original_path)
        if thumbnail_path.exists():
            thumbnail_path.unlink()
        tmp_thumbnail.replace(thumbnail_path)

        rel_cover = f"projects/{project_id}/{original_filename}"
        updated = manager.set_project_cover_path(project_id, cover_path=rel_cover)
        if updated is None:
            raise HTTPException(status_code=404, detail="项目不存在。")

        return {
            "database_environment": manager.active_environment,
            "project": updated,
            "cover_url": f"/api/projects/{project_id}/cover",
            "cover_thumbnail_url": f"/api/projects/{project_id}/cover/thumbnail",
        }

    @app.delete("/api/projects/{project_id}/cover")
    def delete_project_cover(project_id: str) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        cover_dir = manager.data_root / "projects" / project_id
        if cover_dir.exists():
            try:
                shutil.rmtree(cover_dir)
            except OSError:
                pass
        manager.set_project_cover_path(project_id, cover_path=None)
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "project_id": project_id,
        }

    @app.get("/api/projects/{project_id}/cover")
    def get_project_cover(project_id: str):
        project = manager.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        rel_path = project.get("cover_path")
        if not rel_path:
            raise HTTPException(status_code=404, detail="项目暂无封面。")
        abs_path = (manager.data_root / rel_path).resolve()
        projects_root = (manager.data_root / "projects").resolve()
        try:
            abs_path.relative_to(projects_root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="项目暂无封面。") from error
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="项目暂无封面。")
        ext_to_media = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        media_type = ext_to_media.get(abs_path.suffix.lower(), "application/octet-stream")
        return FileResponse(
            str(abs_path),
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @app.get("/api/projects/{project_id}/cover/thumbnail")
    def get_project_cover_thumbnail(project_id: str):
        project = manager.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        cover_dir = manager.data_root / "projects" / project_id
        thumbnail_path = (cover_dir / "cover_thumb.webp").resolve()
        projects_root = (manager.data_root / "projects").resolve()
        try:
            thumbnail_path.relative_to(projects_root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="项目暂无封面缩略图。") from error
        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="项目暂无封面缩略图。")
        return FileResponse(
            str(thumbnail_path),
            media_type="image/webp",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @app.get("/api/projects/{project_id}/chapters")
    def list_chapters(project_id: str) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        chapters = manager.list_chapters(project_id)
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "items": chapters,
            "total": len(chapters),
        }

    @app.post(
        "/api/projects/{project_id}/chapters",
        status_code=status.HTTP_201_CREATED,
    )
    def create_chapter(
        project_id: str, request: CreateChapterRequest
    ) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        try:
            chapter = manager.create_chapter(project_id, request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "chapter": chapter,
        }

    @app.patch("/api/chapters/{chapter_id}")
    def rename_chapter(
        chapter_id: str, request: RenameChapterRequest
    ) -> dict[str, object]:
        if manager.get_chapter(chapter_id) is None:
            raise HTTPException(status_code=404, detail="章节不存在。")
        try:
            chapter = manager.rename_chapter(chapter_id, request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "chapter": chapter,
        }

    @app.delete("/api/chapters/{chapter_id}")
    def delete_chapter(chapter_id: str) -> dict[str, object]:
        if manager.get_chapter(chapter_id) is None:
            raise HTTPException(status_code=404, detail="章节不存在。")
        deleted = manager.delete_chapter(chapter_id)
        return {
            "database_environment": manager.active_environment,
            "deleted": deleted,
        }

    @app.get("/api/chapters/{chapter_id}/large-scenes")
    def list_large_scenes(chapter_id: str) -> dict[str, object]:
        chapter = manager.get_chapter(chapter_id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="章节不存在。")
        large_scenes = manager.list_large_scenes(chapter_id)
        return {
            "database_environment": manager.active_environment,
            "chapter_id": chapter_id,
            "items": large_scenes,
            "total": len(large_scenes),
        }

    @app.get("/api/large-scenes/{large_scene_id}")
    def get_large_scene(large_scene_id: str) -> dict[str, object]:
        large_scene = manager.get_large_scene(large_scene_id)
        if large_scene is None:
            raise HTTPException(status_code=404, detail="大场景不存在。")
        return {
            "database_environment": manager.active_environment,
            "large_scene": large_scene,
        }

    @app.post(
        "/api/chapters/{chapter_id}/large-scenes",
        status_code=status.HTTP_201_CREATED,
    )
    def create_large_scene(
        chapter_id: str, request: CreateLargeSceneRequest
    ) -> dict[str, object]:
        if manager.get_chapter(chapter_id) is None:
            raise HTTPException(status_code=404, detail="章节不存在。")
        try:
            large_scene = manager.create_large_scene(
                chapter_id, request.name, request.scene_type
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "large_scene": large_scene,
        }

    @app.patch("/api/large-scenes/{large_scene_id}")
    def update_large_scene(
        large_scene_id: str, request: UpdateLargeSceneRequest
    ) -> dict[str, object]:
        if manager.get_large_scene(large_scene_id) is None:
            raise HTTPException(status_code=404, detail="大场景不存在。")
        try:
            large_scene = manager.update_large_scene(
                large_scene_id,
                name=request.name,
                scene_type=request.scene_type,
                chapter_id=request.chapter_id,
            )
        except ValueError as error:
            message = str(error)
            if "不存在" in message:
                raise HTTPException(status_code=404, detail=message) from error
            raise HTTPException(status_code=409, detail=message) from error
        return {
            "database_environment": manager.active_environment,
            "large_scene": large_scene,
        }

    @app.post("/api/large-scenes/{large_scene_id}/move")
    def move_large_scene(
        large_scene_id: str, request: MoveLargeSceneRequest
    ) -> dict[str, object]:
        if manager.get_large_scene(large_scene_id) is None:
            raise HTTPException(status_code=404, detail="大场景不存在。")
        try:
            result = manager.move_large_scene(
                large_scene_id,
                request.target_chapter_id,
                request.target_sort_order,
            )
        except ValueError as error:
            message = str(error)
            if "不存在" in message:
                raise HTTPException(status_code=404, detail=message) from error
            raise HTTPException(status_code=409, detail=message) from error
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.delete("/api/large-scenes/{large_scene_id}")
    def delete_large_scene(large_scene_id: str) -> dict[str, object]:
        if manager.get_large_scene(large_scene_id) is None:
            raise HTTPException(status_code=404, detail="大场景不存在。")
        deleted = manager.delete_large_scene(large_scene_id)
        return {
            "database_environment": manager.active_environment,
            "deleted": deleted,
        }

    # ── Characters (global) ────────────────────────────────────

    @app.get("/api/characters")
    def list_characters(
        project_id: str | None = None,
        q: str = "",
        tag: str = "",
        archived: bool = False,
        trash: bool = False,
        sort: str = "sort_asc",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        if project_id is not None and manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        if limit < 1 or limit > 200:
            limit = 100
        if offset < 0:
            offset = 0
        result = manager.list_characters(
            project_id,
            search=q or None,
            tag=tag or None,
            include_archived=archived,
            include_deleted=trash,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        for character in result["items"]:
            character["stats"] = manager.get_character_stats(str(character["id"]))
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            **result,
        }

    @app.post(
        "/api/characters",
        status_code=status.HTTP_201_CREATED,
    )
    def create_character(
        request: CreateCharacterRequest,
        project_id: str | None = None,
    ) -> dict[str, object]:
        if project_id is not None and manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        try:
            character = manager.create_character(
                request.name,
                project_id,
                description=request.description,
                source=request.source,
                source_identifier=request.source_identifier,
                external_url=request.external_url,
                tags=request.tags,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.post(
        "/api/characters/from-role",
        status_code=status.HTTP_201_CREATED,
    )
    def create_character_from_role(
        request: CreateCharacterFromRoleRequest,
    ) -> dict[str, object]:
        """Create a character from role query results."""
        if request.project_id is not None and manager.get_project(request.project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        # Check for duplicate names; if exists, return 409 with candidate list
        existing = manager.list_characters(search=request.name, limit=200)
        candidates = [
            {"id": c["id"], "name": c["name"]}
            for c in existing["items"]
            if str(c["name"]).lower() == request.name.lower()
        ]
        try:
            character = manager.create_character(
                request.name,
                request.project_id,
                description=request.description,
                source=request.source,
                source_identifier=request.source_identifier,
                external_url=request.external_url,
                tags=request.tags,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "character": character,
            "duplicate_candidates": candidates,
        }

    @app.get("/api/characters/{character_id}")
    def get_character(character_id: str) -> dict[str, object]:
        character = manager.get_character(character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        character["stats"] = manager.get_character_stats(character_id)
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.patch("/api/characters/{character_id}")
    def update_character(
        character_id: str, request: UpdateCharacterRequest
    ) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        try:
            updates = request.model_dump(exclude_unset=True)
            character = manager.update_character(character_id, **updates)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.post("/api/characters/{character_id}/archive")
    def archive_character(character_id: str) -> dict[str, object]:
        character = manager.archive_character(character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在或已删除。")
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.post("/api/characters/{character_id}/restore")
    def restore_character(character_id: str) -> dict[str, object]:
        character = manager.restore_character(character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.delete("/api/characters/{character_id}")
    def delete_character(character_id: str) -> dict[str, object]:
        """Soft delete (move to trash)."""
        result = manager.soft_delete_character(character_id)
        if result is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        return {
            "database_environment": manager.active_environment,
            "character": result,
            "deleted": True,
        }

    @app.delete("/api/characters/{character_id}/permanent")
    def permanent_delete_character(character_id: str) -> dict[str, object]:
        deleted = manager.permanent_delete_character(character_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="人物不存在。")
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
        }

    @app.post("/api/characters/{character_id}/copy")
    def copy_character(
        character_id: str, request: CopyCharacterRequest
    ) -> dict[str, object]:
        try:
            character = manager.copy_character(character_id, request.new_name)
        except ValueError as error:
            status_code = 404 if "不存在" in str(error) else 409
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.get("/api/characters/{character_id}/references")
    def get_character_references(character_id: str) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        references = manager.get_character_references(character_id)
        return {
            "database_environment": manager.active_environment,
            "character_id": character_id,
            **references,
        }

    @app.put("/api/characters/{character_id}/tags")
    def set_character_tags(
        character_id: str, request: SetCharacterTagsRequest
    ) -> dict[str, object]:
        character = manager.set_character_tags(character_id, request.tags)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.post("/api/characters/{character_id}/cover")
    def upload_character_cover(
        character_id: str, file: UploadFile
    ) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        allowed = {"image/png", "image/jpeg", "image/webp"}
        content_type = (file.content_type or "").lower()
        if content_type not in allowed:
            raise HTTPException(
                status_code=415,
                detail="封面格式必须为 PNG/JPEG/WebP。",
            )
        payload = file.file.read()
        if not payload:
            raise HTTPException(status_code=422, detail="封面文件为空。")
        if len(payload) > 20 * 1024 * 1024:
            raise HTTPException(status_code=422, detail="封面大小不能超过 20MB。")
        try:
            image = Image.open(io.BytesIO(payload))
            image.load()
        except Exception as error:
            raise HTTPException(
                status_code=422, detail="封面文件无法解析为图片。"
            ) from error
        cover_dir = data_root / "character-covers" / character_id
        cover_dir.mkdir(parents=True, exist_ok=True)
        original_path = cover_dir / "original"
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[content_type]
        original_path = original_path.with_suffix(ext)
        original_path.write_bytes(payload)
        # Generate 512px thumbnail
        thumb = Image.open(io.BytesIO(payload))
        thumb.thumbnail((512, 512))
        thumb_path = cover_dir / "thumbnail.webp"
        thumb.save(thumb_path, format="WEBP", quality=85)
        character = manager.set_character_cover_path(
            character_id, str(original_path.relative_to(data_root))
        )
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.delete("/api/characters/{character_id}/cover")
    def delete_character_cover(character_id: str) -> dict[str, object]:
        character = manager.get_character(character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        cover_path = character.get("cover_path")
        if cover_path:
            cover_dir = data_root / "character-covers" / character_id
            if cover_dir.exists():
                shutil.rmtree(cover_dir, ignore_errors=True)
        updated = manager.set_character_cover_path(character_id, None)
        if updated is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        return {
            "database_environment": manager.active_environment,
            "character": updated,
        }

    @app.get("/api/characters/{character_id}/cover")
    def get_character_cover(character_id: str):
        character = manager.get_character(character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        cover_path = character.get("cover_path")
        if not cover_path:
            raise HTTPException(status_code=404, detail="人物未设置封面。")
        full_path = data_root / cover_path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="封面文件不存在。")
        return FileResponse(str(full_path))

    @app.get("/api/characters/{character_id}/cover/thumbnail")
    def get_character_cover_thumbnail(character_id: str):
        character = manager.get_character(character_id)
        if character is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        cover_path = character.get("cover_path")
        if not cover_path:
            raise HTTPException(status_code=404, detail="人物未设置封面。")
        thumb_path = data_root / "character-covers" / character_id / "thumbnail.webp"
        if not thumb_path.exists():
            raise HTTPException(status_code=404, detail="封面缩略图不存在。")
        return FileResponse(str(thumb_path))

    @app.post("/api/projects/{project_id}/characters/{character_id}")
    def link_character_to_project(project_id: str, character_id: str) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        try:
            manager.link_character_to_project(character_id, project_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "character_id": character_id,
            "linked": True,
        }

    @app.delete("/api/projects/{project_id}/characters/{character_id}")
    def unlink_character_from_project(project_id: str, character_id: str) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        manager.unlink_character_from_project(character_id, project_id)
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "character_id": character_id,
            "linked": False,
        }

    # ── Character Variants ──────────────────────────────────────

    @app.get("/api/characters/{character_id}/variants")
    def list_character_variants(
        character_id: str, include_archived: bool = False
    ) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        variants = manager.list_character_variants(
            character_id, include_archived=include_archived
        )
        return {
            "database_environment": manager.active_environment,
            "character_id": character_id,
            "items": variants,
            "total": len(variants),
        }

    @app.post(
        "/api/characters/{character_id}/variants",
        status_code=status.HTTP_201_CREATED,
    )
    def create_character_variant(
        character_id: str, request: CreateCharacterVariantRequest
    ) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        try:
            variant = manager.create_character_variant(
                character_id,
                request.name,
                description=request.description,
                default_prompt=request.default_prompt,
                default_lora_name=request.default_lora_name,
                default_lora_weight=request.default_lora_weight,
                default_model_override=request.default_model_override,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
        }

    @app.patch("/api/character-variants/{variant_id}")
    def update_character_variant(
        variant_id: str, request: UpdateCharacterVariantRequest
    ) -> dict[str, object]:
        if manager.get_character_variant(variant_id) is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        try:
            updates = request.model_dump(exclude_unset=True)
            variant = manager.update_character_variant(variant_id, **updates)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
        }

    @app.post("/api/character-variants/{variant_id}/copy")
    def copy_character_variant(
        variant_id: str, request: CopyCharacterVariantRequest
    ) -> dict[str, object]:
        try:
            variant = manager.copy_character_variant(variant_id, request.new_name)
        except ValueError as error:
            status_code = 404 if "不存在" in str(error) else 409
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
        }

    @app.post("/api/character-variants/{variant_id}/archive")
    def archive_character_variant(variant_id: str) -> dict[str, object]:
        variant = manager.archive_character_variant(variant_id)
        if variant is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
        }

    @app.post("/api/character-variants/{variant_id}/restore")
    def restore_character_variant(variant_id: str) -> dict[str, object]:
        variant = manager.restore_character_variant(variant_id)
        if variant is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
        }

    @app.put("/api/characters/{character_id}/variants/reorder")
    def reorder_character_variants(
        character_id: str, request: ReorderVariantsRequest
    ) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        try:
            variants = manager.reorder_character_variants(
                character_id, request.variant_ids
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "character_id": character_id,
            "items": variants,
            "total": len(variants),
        }

    @app.post("/api/character-variants/{variant_id}/preview")
    def upload_character_variant_preview(
        variant_id: str, file: UploadFile
    ) -> dict[str, object]:
        if manager.get_character_variant(variant_id) is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        allowed = {"image/png", "image/jpeg", "image/webp"}
        content_type = (file.content_type or "").lower()
        if content_type not in allowed:
            raise HTTPException(
                status_code=415, detail="预览图格式必须为 PNG/JPEG/WebP。"
            )
        payload = file.file.read()
        if not payload:
            raise HTTPException(status_code=422, detail="预览图文件为空。")
        if len(payload) > 20 * 1024 * 1024:
            raise HTTPException(status_code=422, detail="预览图大小不能超过 20MB。")
        try:
            image = Image.open(io.BytesIO(payload))
            image.load()
        except Exception as error:
            raise HTTPException(
                status_code=422, detail="预览图文件无法解析为图片。"
            ) from error
        preview_dir = data_root / "character-variant-previews" / variant_id
        preview_dir.mkdir(parents=True, exist_ok=True)
        ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[content_type]
        original_path = preview_dir / ("original" + ext)
        original_path.write_bytes(payload)
        thumb = Image.open(io.BytesIO(payload))
        thumb.thumbnail((512, 512))
        thumb_path = preview_dir / "thumbnail.webp"
        thumb.save(thumb_path, format="WEBP", quality=85)
        variant = manager.set_character_variant_preview_paths(
            variant_id,
            str(original_path.relative_to(data_root)),
            str(thumb_path.relative_to(data_root)),
        )
        if variant is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
        }

    @app.delete("/api/character-variants/{variant_id}/preview")
    def delete_character_variant_preview(variant_id: str) -> dict[str, object]:
        variant = manager.get_character_variant(variant_id)
        if variant is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        preview_dir = data_root / "character-variant-previews" / variant_id
        if preview_dir.exists():
            shutil.rmtree(preview_dir, ignore_errors=True)
        updated = manager.set_character_variant_preview_paths(variant_id, None, None)
        if updated is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        return {
            "database_environment": manager.active_environment,
            "variant": updated,
        }

    @app.get("/api/character-variants/{variant_id}/preview")
    def get_character_variant_preview(variant_id: str):
        variant = manager.get_character_variant(variant_id)
        if variant is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        preview_path = variant.get("preview_original_path")
        if not preview_path:
            raise HTTPException(status_code=404, detail="变体未设置预览图。")
        full_path = data_root / preview_path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="预览图文件不存在。")
        return FileResponse(str(full_path))

    @app.get("/api/character-variants/{variant_id}/preview/thumbnail")
    def get_character_variant_preview_thumbnail(variant_id: str):
        variant = manager.get_character_variant(variant_id)
        if variant is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        thumb_path = data_root / "character-variant-previews" / variant_id / "thumbnail.webp"
        if not thumb_path.exists():
            raise HTTPException(status_code=404, detail="预览图缩略图不存在。")
        return FileResponse(str(thumb_path))

    @app.get("/api/character-variants/{variant_id}/references")
    def get_character_variant_references(variant_id: str) -> dict[str, object]:
        if manager.get_character_variant(variant_id) is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        references = manager.get_character_variant_references(variant_id)
        return {
            "database_environment": manager.active_environment,
            "variant_id": variant_id,
            **references,
        }

    @app.delete("/api/character-variants/{variant_id}")
    def delete_character_variant(variant_id: str) -> dict[str, object]:
        if manager.get_character_variant(variant_id) is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        deleted = manager.delete_character_variant(variant_id)
        return {
            "database_environment": manager.active_environment,
            "deleted": deleted,
        }

    # ── Specs (global) ─────────────────────────────────────────

    @app.get("/api/specs")
    def list_specs() -> dict[str, object]:
        specs = manager.list_specs()
        return {
            "database_environment": manager.active_environment,
            "items": specs,
            "total": len(specs),
        }

    @app.post(
        "/api/specs",
        status_code=status.HTTP_201_CREATED,
    )
    def create_spec(request: CreateProjectSpecRequest) -> dict[str, object]:
        try:
            spec = manager.create_spec(
                request.spec_type,
                request.custom_label,
                description=request.description,
                is_required=request.is_required,
                default_value=request.default_value,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "spec": spec,
        }

    @app.patch("/api/specs/{spec_id}")
    def update_spec(
        spec_id: str, request: UpdateProjectSpecRequest
    ) -> dict[str, object]:
        if manager.get_spec(spec_id) is None:
            raise HTTPException(status_code=404, detail="规格不存在。")
        try:
            updates = request.model_dump(exclude_unset=True)
            spec = manager.update_spec(spec_id, **updates)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "spec": spec,
        }

    @app.delete("/api/specs/{spec_id}")
    def delete_spec(spec_id: str) -> dict[str, object]:
        if manager.get_spec(spec_id) is None:
            raise HTTPException(status_code=404, detail="规格不存在。")
        deleted = manager.delete_spec(spec_id)
        return {
            "database_environment": manager.active_environment,
            "deleted": deleted,
        }

    # ── Character Spec Values & Matrix ─────────────────────────

    @app.get("/api/characters/{character_id}/matrix")
    def get_character_matrix(character_id: str) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        matrix = manager.get_character_spec_matrix(character_id)
        return {
            "database_environment": manager.active_environment,
            **matrix,
        }

    @app.post("/api/character-spec-values/batch")
    def batch_update_spec_values(
        request: BatchUpdateSpecValuesRequest,
    ) -> dict[str, object]:
        try:
            count = manager.batch_update_spec_values(request.updates)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "updated": count,
        }

    @app.get("/api/character-variants/{variant_id}/spec-values")
    def list_spec_values(variant_id: str) -> dict[str, object]:
        if manager.get_character_variant(variant_id) is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        values = manager.list_spec_values_for_variant(variant_id)
        return {
            "database_environment": manager.active_environment,
            "variant_id": variant_id,
            "items": values,
            "total": len(values),
        }

    @app.patch("/api/character-spec-values/{spec_value_id}")
    def update_character_spec_value(
        spec_value_id: str, request: UpdateCharacterSpecValueRequest
    ) -> dict[str, object]:
        if manager.get_character_spec_value(spec_value_id) is None:
            raise HTTPException(status_code=404, detail="规格值不存在。")
        try:
            updates = request.model_dump(exclude_unset=True)
            value = manager.update_character_spec_value(
                spec_value_id,
                **updates,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "spec_value": value,
        }

    # ── Shot Page Character References ─────────────────────────

    @app.get("/api/shot-pages/{shot_page_id}/character")
    def get_shot_page_character(shot_page_id: str) -> dict[str, object]:
        reference = manager.get_shot_page_character(shot_page_id)
        if reference is None:
            raise HTTPException(status_code=404, detail="场景页未绑定人物。")
        return {
            "database_environment": manager.active_environment,
            "shot_page_id": shot_page_id,
            "reference": reference,
        }

    @app.put("/api/shot-pages/{shot_page_id}/character")
    def set_shot_page_character(
        shot_page_id: str, request: SetShotPageCharacterRequest
    ) -> dict[str, object]:
        try:
            reference = manager.set_shot_page_character(
                shot_page_id, request.character_id, request.variant_id
            )
        except ValueError as error:
            status_code = 404 if "不存在" in str(error) else 400
            raise HTTPException(status_code=status_code, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "shot_page_id": shot_page_id,
            "reference": reference,
        }

    @app.delete("/api/shot-pages/{shot_page_id}/character")
    def clear_shot_page_character(shot_page_id: str) -> dict[str, object]:
        cleared = manager.clear_shot_page_character(shot_page_id)
        return {
            "database_environment": manager.active_environment,
            "shot_page_id": shot_page_id,
            "cleared": cleared,
        }

    # ── Materials ──────────────────────────────────────────────

    @app.get("/api/materials")
    def list_materials(
        q: str = "",
        material_type: str = "",
        validation_status: str = "",
        tag: str = "",
        archived: bool = False,
        trash: bool = False,
        limit: int = 60,
        offset: int = 0,
        sort: str = "updated_desc",
    ) -> dict[str, object]:
        if limit < 1 or limit > 100:
            limit = 60
        if offset < 0:
            offset = 0
        if sort not in DatabaseManager.VALID_MATERIAL_SORTS:
            sort = "updated_desc"
        result = manager.list_materials(
            query=q,
            material_type=material_type,
            validation_status=validation_status,
            tag=tag,
            include_archived=archived,
            include_deleted=trash,
            limit=limit,
            offset=offset,
            sort=sort,
        )
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.get("/api/materials/trash")
    def list_trash_materials() -> dict[str, object]:
        items = manager.list_deleted_materials()
        return {
            "database_environment": manager.active_environment,
            "items": items,
            "total": len(items),
        }

    @app.post(
        "/api/materials",
        status_code=status.HTTP_201_CREATED,
    )
    def create_material(request: CreateMaterialRequest) -> dict[str, object]:
        try:
            material = manager.create_material(
                name=request.name,
                material_type=request.material_type,
                description=request.description,
                content=request.content,
                prompt_text=request.prompt_text,
                negative_prompt=request.negative_prompt,
                validation_status=request.validation_status,
                notes=request.notes,
                tags=request.tags,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.get("/api/materials/{material_id}")
    def get_material(material_id: str) -> dict[str, object]:
        material = manager.get_material(material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.patch("/api/materials/{material_id}")
    def update_material(
        material_id: str, request: UpdateMaterialRequest
    ) -> dict[str, object]:
        if manager.get_material(material_id) is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        updates = request.model_dump(exclude_none=True)
        try:
            material = manager.update_material(material_id, **updates)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.delete("/api/materials/{material_id}")
    def delete_material(material_id: str) -> dict[str, object]:
        result = manager.soft_delete_material(material_id)
        if result is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "material_id": material_id,
        }

    @app.post("/api/materials/{material_id}/archive")
    def archive_material(material_id: str) -> dict[str, object]:
        material = manager.archive_material(material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.post("/api/materials/{material_id}/restore")
    def restore_material(material_id: str) -> dict[str, object]:
        material = manager.restore_material(material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.delete("/api/materials/{material_id}/permanent")
    def permanent_delete_material(material_id: str) -> dict[str, object]:
        # Clean up material image directory before permanent deletion
        material_dir = manager.data_root / "materials" / material_id
        if material_dir.exists():
            try:
                shutil.rmtree(material_dir)
            except OSError:
                pass
        result = manager.permanent_delete_material(material_id)
        if result is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "material_id": material_id,
        }

    @app.get("/api/materials/{material_id}/references")
    def get_material_references(material_id: str) -> dict[str, object]:
        refs = manager.get_material_references(material_id)
        if refs is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "material_id": material_id,
            **refs,
        }

    @app.post("/api/materials/{material_id}/copy", status_code=status.HTTP_201_CREATED)
    def copy_material(material_id: str, request: CopyMaterialRequest) -> dict[str, object]:
        try:
            material = manager.copy_material(material_id, new_name=request.name)
        except ValueError as error:
            msg = str(error)
            if "不存在" in msg:
                raise HTTPException(status_code=404, detail=msg) from error
            raise HTTPException(status_code=422, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    # ── Material Versions (v0.5.2) ─────────────────────────────

    @app.post(
        "/api/materials/{material_id}/versions",
        status_code=status.HTTP_201_CREATED,
    )
    def create_material_version(
        material_id: str, request: CreateMaterialVersionRequest
    ) -> dict[str, object]:
        if manager.get_material(material_id) is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        version = manager.create_material_version(
            material_id, label=request.label
        )
        if version is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        return {
            "database_environment": manager.active_environment,
            "version": version,
        }

    @app.get("/api/materials/{material_id}/versions")
    def list_material_versions(material_id: str) -> dict[str, object]:
        if manager.get_material(material_id) is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        items = manager.list_material_versions(material_id)
        return {
            "database_environment": manager.active_environment,
            "material_id": material_id,
            "items": items,
            "total": len(items),
        }

    @app.get("/api/materials/{material_id}/versions/{version_number}")
    def get_material_version(material_id: str, version_number: int) -> dict[str, object]:
        if manager.get_material(material_id) is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        version = manager.get_material_version(material_id, version_number)
        if version is None:
            raise HTTPException(status_code=404, detail="版本不存在。")
        return {
            "database_environment": manager.active_environment,
            "version": version,
        }

    @app.post("/api/materials/{material_id}/versions/{version_number}/restore")
    def restore_material_version(
        material_id: str, version_number: int
    ) -> dict[str, object]:
        material = manager.restore_material_version(material_id, version_number)
        if material is None:
            raise HTTPException(status_code=404, detail="素材或版本不存在。")
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.get("/api/material-tags")
    def list_material_tags(
        q: str = "",
        limit: int = 30,
    ) -> dict[str, object]:
        if limit < 1 or limit > 100:
            limit = 30
        items = manager.list_material_tags(query=q, limit=limit)
        return {
            "database_environment": manager.active_environment,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/materials/{material_id}/preview")
    async def upload_material_preview(
        material_id: str,
        file: UploadFile = File(...),
    ) -> dict[str, object]:
        if manager.get_material(material_id) is None:
            raise HTTPException(status_code=404, detail="素材不存在。")

        MAX_SIZE = 20 * 1024 * 1024  # 20 MB
        contents = await file.read()
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="预览图文件超过 20 MB 限制。")
        if not contents:
            raise HTTPException(status_code=422, detail="预览图文件为空。")

        try:
            image = Image.open(io.BytesIO(contents))
            image.load()
        except (UnidentifiedImageError, OSError) as error:
            raise HTTPException(
                status_code=415,
                detail="预览图格式不支持或文件已损坏。",
            ) from error

        if image.width > 16384 or image.height > 16384:
            raise HTTPException(
                status_code=422,
                detail="预览图最长边不得超过 16,384 像素。",
            )

        ext_map = {
            "JPEG": "jpg",
            "PNG": "png",
            "WEBP": "webp",
        }
        fmt = image.format
        if fmt not in ext_map:
            raise HTTPException(
                status_code=415,
                detail="预览图格式不支持，仅接受 JPG、PNG、WebP。",
            )

        material_dir = manager.data_root / "materials" / material_id
        material_dir.mkdir(parents=True, exist_ok=True)
        original_filename = f"original.{ext_map[fmt]}"
        thumbnail_filename = "thumbnail.webp"
        original_path = material_dir / original_filename
        thumbnail_path = material_dir / thumbnail_filename
        tmp_original = material_dir / f"{original_filename}.tmp"
        tmp_thumbnail = material_dir / f"{thumbnail_filename}.tmp"

        try:
            # Save original (convert to RGB if necessary for JPEG)
            save_image = image
            if fmt == "JPEG" and save_image.mode not in ("RGB", "L"):
                save_image = save_image.convert("RGB")
            save_image.save(tmp_original, format=fmt)

            # Generate thumbnail (longest edge 512, WebP quality 82)
            thumb = image.copy()
            thumb.thumbnail((512, 512), Image.Resampling.LANCZOS)
            if thumb.mode not in ("RGB", "RGBA"):
                thumb = thumb.convert("RGB")
            thumb.save(tmp_thumbnail, format="WEBP", quality=82)
        except OSError as error:
            for tmp in (tmp_original, tmp_thumbnail):
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
            raise HTTPException(
                status_code=422,
                detail="预览图处理失败，请检查图片内容。",
            ) from error

        # Atomic replacement of old files
        if original_path.exists():
            original_path.unlink()
        tmp_original.replace(original_path)
        if thumbnail_path.exists():
            thumbnail_path.unlink()
        tmp_thumbnail.replace(thumbnail_path)

        rel_original = f"materials/{material_id}/{original_filename}"
        rel_thumbnail = f"materials/{material_id}/{thumbnail_filename}"
        updated = manager.set_material_preview_paths(
            material_id,
            original_path=rel_original,
            thumbnail_path=rel_thumbnail,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="素材不存在。")

        return {
            "database_environment": manager.active_environment,
            "preview_url": f"/api/materials/{material_id}/preview",
            "thumbnail_url": f"/api/materials/{material_id}/thumbnail",
        }

    @app.delete("/api/materials/{material_id}/preview")
    def delete_material_preview(material_id: str) -> dict[str, object]:
        material = manager.get_material(material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        material_dir = manager.data_root / "materials" / material_id
        if material_dir.exists():
            try:
                shutil.rmtree(material_dir)
            except OSError:
                pass
        manager.set_material_preview_paths(
            material_id,
            original_path=None,
            thumbnail_path=None,
        )
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "material_id": material_id,
        }

    @app.get("/api/materials/{material_id}/preview")
    def get_material_preview(material_id: str):
        material = manager.get_material(material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        rel_path = material.get("preview_original_path")
        if not rel_path:
            raise HTTPException(status_code=404, detail="素材暂无预览图。")
        abs_path = (manager.data_root / rel_path).resolve()
        materials_root = (manager.data_root / "materials").resolve()
        try:
            abs_path.relative_to(materials_root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="素材暂无预览图。") from error
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="素材暂无预览图。")
        ext_to_media = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        media_type = ext_to_media.get(abs_path.suffix.lower(), "application/octet-stream")
        return FileResponse(
            str(abs_path),
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @app.get("/api/materials/{material_id}/thumbnail")
    def get_material_thumbnail(material_id: str):
        material = manager.get_material(material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        rel_path = material.get("preview_thumbnail_path")
        if not rel_path:
            raise HTTPException(status_code=404, detail="素材暂无缩略图。")
        abs_path = (manager.data_root / rel_path).resolve()
        materials_root = (manager.data_root / "materials").resolve()
        try:
            abs_path.relative_to(materials_root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="素材暂无缩略图。") from error
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="素材暂无缩略图。")
        ext_to_media = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        media_type = ext_to_media.get(abs_path.suffix.lower(), "application/octet-stream")
        return FileResponse(
            str(abs_path),
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    # ── Character Database (Danbooru CSV lookup) ───────────────

    @app.get("/api/character-database/status")
    def character_database_status() -> dict[str, object]:
        return character_database.status()

    @app.get("/api/character-database/search")
    def search_character_database(
        q: str = "",
        copyright: str = "",
        sort: str = "count_desc",
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, object]:
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 200:
            page_size = 50
        try:
            result = character_database.search(
                q=q,
                copyright_filter=copyright,
                sort=sort,
                page=page,
                page_size=page_size,
            )
        except character_database.CharacterDatabaseNotReadyError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return result

    @app.get("/api/character-database/copyrights")
    def list_character_database_copyrights(
        q: str = "",
        limit: int = 50,
    ) -> dict[str, object]:
        if limit < 1 or limit > 200:
            limit = 50
        try:
            items = character_database.list_copyrights(q=q, limit=limit)
        except character_database.CharacterDatabaseNotReadyError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        return {
            "items": items,
            "total": len(items),
            "query": q,
        }

    @app.get("/api/character-database/stats")
    def character_database_stats() -> dict[str, object]:
        return character_database.stats()

    # ── Small Scenes ──────────────────────────────────────────────────

    @app.get("/api/large-scenes/{large_scene_id}/small-scenes")
    def list_small_scenes(large_scene_id: str) -> dict[str, object]:
        items = manager.list_small_scenes(large_scene_id)
        return {
            "database_environment": manager.active_environment,
            "large_scene_id": large_scene_id,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/large-scenes/{large_scene_id}/small-scenes", status_code=status.HTTP_201_CREATED)
    def create_small_scene(large_scene_id: str, request: CreateSmallSceneRequest) -> dict[str, object]:
        try:
            small_scene = manager.create_small_scene(
                large_scene_id,
                request.name,
                scene_type=request.scene_type,
                description=request.description,
            )
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 409
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "small_scene": small_scene,
        }

    @app.get("/api/small-scenes/{small_scene_id}")
    def get_small_scene(small_scene_id: str) -> dict[str, object]:
        small_scene = manager.get_small_scene(small_scene_id)
        if small_scene is None:
            raise HTTPException(status_code=404, detail="小场景不存在")
        return {
            "database_environment": manager.active_environment,
            "small_scene": small_scene,
        }

    @app.patch("/api/small-scenes/{small_scene_id}")
    def update_small_scene(small_scene_id: str, request: UpdateSmallSceneRequest) -> dict[str, object]:
        try:
            small_scene = manager.update_small_scene(
                small_scene_id,
                name=request.name,
                scene_type=request.scene_type,
                description=request.description,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if small_scene is None:
            raise HTTPException(status_code=404, detail="小场景不存在")
        return {
            "database_environment": manager.active_environment,
            "small_scene": small_scene,
        }

    @app.post("/api/small-scenes/{small_scene_id}/move")
    def move_small_scene(small_scene_id: str, request: MoveSmallSceneRequest) -> dict[str, object]:
        try:
            small_scene = manager.move_small_scene(small_scene_id, request.target_sort_order)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        items = manager.list_small_scenes(small_scene["large_scene_id"])
        return {
            "database_environment": manager.active_environment,
            "small_scene": small_scene,
            "items": items,
        }

    @app.delete("/api/small-scenes/{small_scene_id}")
    def delete_small_scene(small_scene_id: str) -> dict[str, object]:
        result = manager.delete_small_scene(small_scene_id)
        if result is None:
            raise HTTPException(status_code=404, detail="小场景不存在")
        return {
            "database_environment": manager.active_environment,
            "deleted": result,
        }

    # ── Shot Pages ────────────────────────────────────────────────────

    @app.get("/api/small-scenes/{small_scene_id}/shot-pages")
    def list_shot_pages(small_scene_id: str, branch_id: str | None = None) -> dict[str, object]:
        items = manager.list_shot_pages(small_scene_id, branch_id=branch_id)
        return {
            "database_environment": manager.active_environment,
            "small_scene_id": small_scene_id,
            "branch_id": branch_id,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/small-scenes/{small_scene_id}/shot-pages", status_code=status.HTTP_201_CREATED)
    def create_shot_page(small_scene_id: str, request: CreateShotPageRequest) -> dict[str, object]:
        try:
            shot_page = manager.create_shot_page(
                small_scene_id,
                request.title,
                branch_id=request.branch_id,
                description=request.description,
                prompt_text=request.prompt_text,
                negative_prompt=request.negative_prompt,
            )
        except ValueError as error:
            msg = str(error)
            if "不存在" in msg:
                code = 404 if "小场景" in msg else 422
            elif "重名" in msg or "同名" in msg:
                code = 409
            else:
                code = 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "shot_page": shot_page,
        }

    @app.get("/api/shot-pages/{shot_page_id}")
    def get_shot_page(shot_page_id: str) -> dict[str, object]:
        shot_page = manager.get_shot_page(shot_page_id)
        if shot_page is None:
            raise HTTPException(status_code=404, detail="分镜页不存在")
        return {
            "database_environment": manager.active_environment,
            "shot_page": shot_page,
        }

    @app.patch("/api/shot-pages/{shot_page_id}")
    def update_shot_page(shot_page_id: str, request: UpdateShotPageRequest) -> dict[str, object]:
        try:
            shot_page = manager.update_shot_page(
                shot_page_id,
                title=request.title,
                description=request.description,
                prompt_text=request.prompt_text,
                negative_prompt=request.negative_prompt,
            )
        except ValueError as error:
            msg = str(error)
            code = 409 if "同名" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        if shot_page is None:
            raise HTTPException(status_code=404, detail="分镜页不存在")
        return {
            "database_environment": manager.active_environment,
            "shot_page": shot_page,
        }

    @app.post("/api/shot-pages/{shot_page_id}/move")
    def move_shot_page(shot_page_id: str, request: MoveShotPageRequest) -> dict[str, object]:
        try:
            shot_page = manager.move_shot_page(shot_page_id, request.target_sort_order)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if shot_page["branch_id"] is None:
            items = manager.list_shot_pages(shot_page["small_scene_id"])
        else:
            items = manager.list_shot_pages(shot_page["small_scene_id"], branch_id=shot_page["branch_id"])
        return {
            "database_environment": manager.active_environment,
            "shot_page": shot_page,
            "items": items,
        }

    @app.delete("/api/shot-pages/{shot_page_id}")
    def delete_shot_page(shot_page_id: str) -> dict[str, object]:
        result = manager.delete_shot_page(shot_page_id)
        if result is None:
            raise HTTPException(status_code=404, detail="分镜页不存在")
        return {
            "database_environment": manager.active_environment,
            "deleted": result,
        }

    # ── Branches ──────────────────────────────────────────────────────

    @app.get("/api/{parent_type}/{parent_id}/branches")
    def list_branches(parent_type: str, parent_id: str) -> dict[str, object]:
        mapped = {"large-scenes": "large_scene", "small-scenes": "small_scene"}
        pt = mapped.get(parent_type)
        if pt is None:
            raise HTTPException(status_code=422, detail="分支父级类型无效，允许值: large-scenes, small-scenes")
        try:
            items = manager.list_branches(pt, parent_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "parent_type": pt,
            "parent_id": parent_id,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/{parent_type}/{parent_id}/branches", status_code=status.HTTP_201_CREATED)
    def create_branch(parent_type: str, parent_id: str, request: CreateBranchRequest) -> dict[str, object]:
        mapped = {"large-scenes": "large_scene", "small-scenes": "small_scene"}
        pt = mapped.get(parent_type)
        if pt is None:
            raise HTTPException(status_code=422, detail="分支父级类型无效，允许值: large-scenes, small-scenes")
        try:
            branch = manager.create_branch(
                pt, parent_id, request.name,
                description=request.description,
                is_enabled=request.is_enabled,
                condition_type=request.condition_type,
                condition_value=request.condition_value,
                return_point=request.return_point,
            )
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 409
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "branch": branch,
        }

    @app.get("/api/branches/{branch_id}")
    def get_branch(branch_id: str) -> dict[str, object]:
        branch = manager.get_branch(branch_id)
        if branch is None:
            raise HTTPException(status_code=404, detail="分支不存在")
        return {
            "database_environment": manager.active_environment,
            "branch": branch,
        }

    @app.patch("/api/branches/{branch_id}")
    def update_branch(branch_id: str, request: UpdateBranchRequest) -> dict[str, object]:
        try:
            branch = manager.update_branch(
                branch_id,
                name=request.name,
                description=request.description,
                is_enabled=request.is_enabled,
                condition_type=request.condition_type,
                condition_value=request.condition_value,
                return_point=request.return_point,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if branch is None:
            raise HTTPException(status_code=404, detail="分支不存在")
        return {
            "database_environment": manager.active_environment,
            "branch": branch,
        }

    @app.delete("/api/branches/{branch_id}")
    def delete_branch(branch_id: str) -> dict[str, object]:
        result = manager.delete_branch(branch_id)
        if result is None:
            raise HTTPException(status_code=404, detail="分支不存在")
        return {
            "database_environment": manager.active_environment,
            "deleted": result,
        }

    # ── Small Scene Materials ─────────────────────────────────────────

    @app.get("/api/small-scenes/{small_scene_id}/materials")
    def list_small_scene_materials(small_scene_id: str) -> dict[str, object]:
        scene = manager.get_small_scene(small_scene_id)
        if scene is None:
            raise HTTPException(status_code=404, detail="小场景不存在")
        materials = manager.list_small_scene_materials(small_scene_id)
        return {
            "database_environment": manager.active_environment,
            "small_scene_id": small_scene_id,
            "materials": materials,
        }

    @app.put("/api/small-scenes/{small_scene_id}/materials")
    def set_small_scene_materials(small_scene_id: str, request: SetMaterialsRequest) -> dict[str, object]:
        try:
            result = manager.set_small_scene_materials(small_scene_id, request.material_ids)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    # ── Shot Page Materials ───────────────────────────────────────────

    @app.get("/api/shot-pages/{shot_page_id}/materials")
    def list_shot_page_materials(shot_page_id: str) -> dict[str, object]:
        page = manager.get_shot_page(shot_page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="分镜页不存在")
        materials = manager.list_shot_page_materials(shot_page_id)
        return {
            "database_environment": manager.active_environment,
            "shot_page_id": shot_page_id,
            "materials": materials,
        }

    @app.put("/api/shot-pages/{shot_page_id}/materials")
    def set_shot_page_materials(shot_page_id: str, request: SetMaterialsRequest) -> dict[str, object]:
        try:
            result = manager.set_shot_page_materials(shot_page_id, request.material_ids)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    # ── v0.4.1 小场景联调整改路由 ───────────────────────────────────────

    @app.get("/api/projects/{project_id}/story-tree")
    def get_story_tree(project_id: str) -> dict[str, object]:
        """6.1 项目剧本树聚合：章节 → 大场景 → 小场景 → 场景页"""
        result = manager.get_story_tree(project_id)
        if result is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.get("/api/small-scenes/{small_scene_id}/workspace")
    def get_small_scene_workspace(small_scene_id: str) -> dict[str, object]:
        """6.2 小场景工作区聚合：small_scene + pages + resources + mappings"""
        result = manager.get_small_scene_workspace(small_scene_id)
        if result is None:
            raise HTTPException(status_code=404, detail="小场景不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.post("/api/small-scenes/{small_scene_id}/pages", status_code=status.HTTP_201_CREATED)
    def create_scene_page(small_scene_id: str, request: CreateScenePageRequest) -> dict[str, object]:
        """6.3 创建场景页（前端 name → 内部 title）"""
        try:
            page = manager.create_shot_page(
                small_scene_id,
                request.name.strip(),
                description=request.description,
                prompt_text=request.prompt_text,
                negative_prompt=request.negative_prompt,
            )
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        # 返回时把 title 转回 name
        result = dict(page)
        result["name"] = result.pop("title")
        return {
            "database_environment": manager.active_environment,
            "page": result,
        }

    @app.patch("/api/small-scene-pages/{page_id}")
    def update_scene_page(page_id: str, request: UpdateScenePageRequest) -> dict[str, object]:
        """6.3 更新场景页（前端 name → 内部 title）"""
        try:
            page = manager.update_shot_page(
                page_id,
                title=request.name,
                description=request.description,
                prompt_text=request.prompt_text,
                negative_prompt=request.negative_prompt,
            )
        except ValueError as error:
            msg = str(error)
            code = 422
            raise HTTPException(status_code=code, detail=msg) from error
        if page is None:
            raise HTTPException(status_code=404, detail="场景页不存在")
        result = dict(page)
        if "title" in result:
            result["name"] = result.pop("title")
        return {
            "database_environment": manager.active_environment,
            "page": result,
        }

    @app.delete("/api/small-scene-pages/{page_id}")
    def delete_scene_page(page_id: str) -> dict[str, object]:
        """6.3 删除场景页"""
        result = manager.delete_shot_page(page_id)
        if result is None:
            raise HTTPException(status_code=404, detail="场景页不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.put("/api/small-scenes/{small_scene_id}/pages/order")
    def reorder_scene_pages(small_scene_id: str, request: ReorderPagesRequest) -> dict[str, object]:
        """6.3 场景页排序（单事务 + 完整集合校验）"""
        try:
            pages = manager.reorder_scene_pages(small_scene_id, request.page_ids)
        except ValueError as error:
            msg = str(error)
            # Per second-round contract 7.1: all invalid page_ids return 422.
            # Only the small_scene itself missing returns 404.
            code = 404 if msg == "小场景不存在" else 422
            raise HTTPException(status_code=code, detail=msg) from error
        # 转换 title → name
        for p in pages:
            if "title" in p:
                p["name"] = p.pop("title")
        return {
            "database_environment": manager.active_environment,
            "small_scene_id": small_scene_id,
            "pages": pages,
        }

    @app.post("/api/small-scenes/{small_scene_id}/resources", status_code=status.HTTP_201_CREATED)
    def add_small_scene_resource(small_scene_id: str, request: AddResourceRequest) -> dict[str, object]:
        """6.4 关联素材到小场景"""
        try:
            link_info = manager.add_small_scene_resource(small_scene_id, request.material_id)
        except ValueError as error:
            msg = str(error)
            if "已关联" in msg:
                code = 409
            elif "不存在" in msg:
                code = 404
            else:
                code = 422
            raise HTTPException(status_code=code, detail=msg) from error
        # Build resource payload with material info + material_pages (per contract 8.3)
        material = manager.get_material(request.material_id)
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在") from None
        material_pages = manager.list_material_pages(request.material_id)
        resource = {
            "link_id": link_info["link_id"],
            "material_id": request.material_id,
            "name": material.get("name"),
            "material_type": material.get("material_type"),
            "pages": material_pages,
        }
        return {
            "database_environment": manager.active_environment,
            "resource": resource,
        }

    @app.delete("/api/small-scene-resource-links/{link_id}")
    def remove_small_scene_resource_link(link_id: str) -> dict[str, object]:
        """6.4 移除小场景素材关联（级联删除该小场景内映射）"""
        result = manager.remove_small_scene_resource_link(link_id)
        if result is None:
            raise HTTPException(status_code=404, detail="素材关联不存在")
        return {
            "database_environment": manager.active_environment,
            "deleted": result,
        }

    @app.put("/api/small-scene-pages/{page_id}/mappings/{material_type}")
    def set_scene_page_mapping(page_id: str, material_type: str, request: SetMappingRequest) -> dict[str, object]:
        """6.5 设置场景页映射（同类型原子替换，支持 PUT null 取消）"""
        valid_types = ('composition', 'expression', 'scene', 'lighting', 'prompt', 'composite_template')
        if material_type not in valid_types:
            raise HTTPException(status_code=422, detail=f"素材类型无效，允许值: {', '.join(valid_types)}")
        try:
            result = manager.set_small_scene_page_mapping(page_id, material_type, request.material_page_id)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        # result is None when material_page_id was None and no existing mapping to remove
        # Per contract 8.5: cancel returns mapping: null
        if result is None:
            return {
                "database_environment": manager.active_environment,
                "mapping": None,
            }
        return {
            "database_environment": manager.active_environment,
            "mapping": result,
        }

    @app.delete("/api/small-scene-pages/{page_id}/mappings/{material_type}")
    def unset_scene_page_mapping(page_id: str, material_type: str) -> dict[str, object]:
        """6.5 取消场景页映射（DELETE 兼容接口；前端应使用 PUT + null）"""
        valid_types = ('composition', 'expression', 'scene', 'lighting', 'prompt', 'composite_template')
        if material_type not in valid_types:
            raise HTTPException(status_code=422, detail=f"素材类型无效，允许值: {', '.join(valid_types)}")
        result = manager.unset_small_scene_page_mapping(page_id, material_type)
        if result is None:
            raise HTTPException(status_code=404, detail="映射不存在")
        return {
            "database_environment": manager.active_environment,
            "mapping": result,
        }

    @app.get("/api/materials/{material_id}/pages")
    def list_material_pages(material_id: str) -> dict[str, object]:
        """6.6 获取素材页列表"""
        mat = manager.get_material(material_id)
        if mat is None:
            raise HTTPException(status_code=404, detail="素材不存在")
        pages = manager.list_material_pages(material_id)
        return {
            "database_environment": manager.active_environment,
            "material_id": material_id,
            "pages": pages,
        }

    @app.post("/api/materials/{material_id}/pages")
    def create_material_page(material_id: str, request: CreateMaterialPageRequest) -> dict[str, object]:
        """6.6 创建素材页"""
        try:
            page = manager.create_material_page(
                material_id,
                request.name.strip(),
                description=request.description,
                content=request.content,
                prompt_text=request.prompt_text,
                negative_prompt=request.negative_prompt,
            )
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            **page,
        }

    @app.get("/api/material-pages/{page_id}")
    def get_material_page(page_id: str) -> dict[str, object]:
        """6.6 获取单个素材页"""
        page = manager.get_material_page(page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="素材页不存在")
        return {
            "database_environment": manager.active_environment,
            **page,
        }

    @app.patch("/api/material-pages/{page_id}")
    def update_material_page(page_id: str, request: UpdateMaterialPageRequest) -> dict[str, object]:
        """6.6 更新素材页"""
        try:
            page = manager.update_material_page(
                page_id,
                name=request.name,
                description=request.description,
                content=request.content,
                prompt_text=request.prompt_text,
                negative_prompt=request.negative_prompt,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if page is None:
            raise HTTPException(status_code=404, detail="素材页不存在")
        return {
            "database_environment": manager.active_environment,
            **page,
        }

    @app.delete("/api/material-pages/{page_id}")
    def delete_material_page(page_id: str) -> dict[str, object]:
        """6.6 删除素材页"""
        result = manager.delete_material_page(page_id)
        if result is None:
            raise HTTPException(status_code=404, detail="素材页不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.put("/api/materials/{material_id}/pages/order")
    def reorder_material_pages(material_id: str, request: ReorderMaterialPagesRequest) -> dict[str, object]:
        """6.6 素材页排序"""
        pages = manager.reorder_material_pages(material_id, request.page_ids)
        return {
            "database_environment": manager.active_environment,
            "material_id": material_id,
            "pages": pages,
        }

    # ── Material Page Preview & Copy (v0.5.2) ──────────────────

    @app.post("/api/material-pages/{page_id}/copy", status_code=status.HTTP_201_CREATED)
    def copy_material_page(page_id: str) -> dict[str, object]:
        page = manager.copy_material_page(page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="素材页不存在")
        return {
            "database_environment": manager.active_environment,
            **page,
        }

    @app.post("/api/material-pages/{page_id}/preview")
    async def upload_material_page_preview(
        page_id: str,
        file: UploadFile = File(...),
    ) -> dict[str, object]:
        if manager.get_material_page(page_id) is None:
            raise HTTPException(status_code=404, detail="素材页不存在")

        MAX_SIZE = 20 * 1024 * 1024  # 20 MB
        contents = await file.read()
        if len(contents) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="预览图文件超过 20 MB 限制。")
        if not contents:
            raise HTTPException(status_code=422, detail="预览图文件为空。")

        try:
            image = Image.open(io.BytesIO(contents))
            image.load()
        except (UnidentifiedImageError, OSError) as error:
            raise HTTPException(
                status_code=415,
                detail="预览图格式不支持或文件已损坏。",
            ) from error

        if image.width > 16384 or image.height > 16384:
            raise HTTPException(
                status_code=422,
                detail="预览图最长边不得超过 16,384 像素。",
            )

        ext_map = {
            "JPEG": "jpg",
            "PNG": "png",
            "WEBP": "webp",
        }
        fmt = image.format
        if fmt not in ext_map:
            raise HTTPException(
                status_code=415,
                detail="预览图格式不支持，仅接受 JPG、PNG、WebP。",
            )

        page_dir = manager.data_root / "material_pages" / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        original_filename = f"original.{ext_map[fmt]}"
        thumbnail_filename = "thumbnail.webp"
        original_path = page_dir / original_filename
        thumbnail_path = page_dir / thumbnail_filename
        tmp_original = page_dir / f"{original_filename}.tmp"
        tmp_thumbnail = page_dir / f"{thumbnail_filename}.tmp"

        try:
            save_image = image
            if fmt == "JPEG" and save_image.mode not in ("RGB", "L"):
                save_image = save_image.convert("RGB")
            save_image.save(tmp_original, format=fmt)

            thumb = image.copy()
            thumb.thumbnail((512, 512), Image.Resampling.LANCZOS)
            if thumb.mode not in ("RGB", "RGBA"):
                thumb = thumb.convert("RGB")
            thumb.save(tmp_thumbnail, format="WEBP", quality=82)
        except OSError as error:
            for tmp in (tmp_original, tmp_thumbnail):
                if tmp.exists():
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
            raise HTTPException(
                status_code=422,
                detail="预览图处理失败，请检查图片内容。",
            ) from error

        if original_path.exists():
            original_path.unlink()
        tmp_original.replace(original_path)
        if thumbnail_path.exists():
            thumbnail_path.unlink()
        tmp_thumbnail.replace(thumbnail_path)

        rel_original = f"material_pages/{page_id}/{original_filename}"
        rel_thumbnail = f"material_pages/{page_id}/{thumbnail_filename}"
        updated = manager.set_material_page_preview_paths(
            page_id,
            original_path=rel_original,
            thumbnail_path=rel_thumbnail,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="素材页不存在。")

        return {
            "database_environment": manager.active_environment,
            "preview_url": f"/api/material-pages/{page_id}/preview",
            "thumbnail_url": f"/api/material-pages/{page_id}/thumbnail",
        }

    @app.delete("/api/material-pages/{page_id}/preview")
    def delete_material_page_preview(page_id: str) -> dict[str, object]:
        page = manager.get_material_page(page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="素材页不存在")
        page_dir = manager.data_root / "material_pages" / page_id
        if page_dir.exists():
            try:
                shutil.rmtree(page_dir)
            except OSError:
                pass
        manager.set_material_page_preview_paths(
            page_id,
            original_path=None,
            thumbnail_path=None,
        )
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "page_id": page_id,
        }

    @app.get("/api/material-pages/{page_id}/preview")
    def get_material_page_preview(page_id: str):
        page = manager.get_material_page(page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="素材页不存在")
        rel_path = page.get("preview_original_path")
        if not rel_path:
            raise HTTPException(status_code=404, detail="素材页暂无预览图。")
        abs_path = (manager.data_root / rel_path).resolve()
        pages_root = (manager.data_root / "material_pages").resolve()
        try:
            abs_path.relative_to(pages_root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="素材页暂无预览图。") from error
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="素材页暂无预览图。")
        ext_to_media = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        media_type = ext_to_media.get(abs_path.suffix.lower(), "application/octet-stream")
        return FileResponse(
            str(abs_path),
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    @app.get("/api/material-pages/{page_id}/thumbnail")
    def get_material_page_thumbnail(page_id: str):
        page = manager.get_material_page(page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="素材页不存在")
        rel_path = page.get("preview_thumbnail_path")
        if not rel_path:
            raise HTTPException(status_code=404, detail="素材页暂无缩略图。")
        abs_path = (manager.data_root / rel_path).resolve()
        pages_root = (manager.data_root / "material_pages").resolve()
        try:
            abs_path.relative_to(pages_root)
        except ValueError as error:
            raise HTTPException(status_code=404, detail="素材页暂无缩略图。") from error
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="素材页暂无缩略图。")
        ext_to_media = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        media_type = ext_to_media.get(abs_path.suffix.lower(), "application/octet-stream")
        return FileResponse(
            str(abs_path),
            media_type=media_type,
            headers={"Cache-Control": "private, max-age=3600"},
        )

    # ── v0.5.4 Story Structure Routes ─────────────────────────────────

    @app.get("/api/branches/{branch_id}/overrides")
    def list_branch_overrides(branch_id: str) -> dict[str, object]:
        if manager.get_branch(branch_id) is None:
            raise HTTPException(status_code=404, detail="分支不存在")
        items = manager.list_branch_overrides(branch_id)
        return {
            "database_environment": manager.active_environment,
            "branch_id": branch_id,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/branches/{branch_id}/overrides", status_code=status.HTTP_201_CREATED)
    def create_branch_override(branch_id: str, request: CreateBranchOverrideRequest) -> dict[str, object]:
        try:
            override = manager.create_branch_override(
                branch_id, request.override_type,
                target_id=request.target_id,
                character_id=request.character_id,
                variant_id=request.variant_id,
                material_id=request.material_id,
                material_page_id=request.material_page_id,
                param_key=request.param_key,
                param_value=request.param_value,
            )
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 409
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "override": override,
        }

    @app.patch("/api/branch-overrides/{override_id}")
    def update_branch_override(override_id: str, request: UpdateBranchOverrideRequest) -> dict[str, object]:
        try:
            override = manager.update_branch_override(
                override_id,
                target_id=request.target_id,
                character_id=request.character_id,
                variant_id=request.variant_id,
                material_id=request.material_id,
                material_page_id=request.material_page_id,
                param_key=request.param_key,
                param_value=request.param_value,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if override is None:
            raise HTTPException(status_code=404, detail="覆盖配置不存在")
        return {
            "database_environment": manager.active_environment,
            "override": override,
        }

    @app.delete("/api/branch-overrides/{override_id}")
    def delete_branch_override(override_id: str) -> dict[str, object]:
        result = manager.delete_branch_override(override_id)
        if result is None:
            raise HTTPException(status_code=404, detail="覆盖配置不存在")
        return {
            "database_environment": manager.active_environment,
            "deleted": result,
        }

    @app.get("/api/shot-pages/{shot_page_id}/effective-overrides")
    def get_effective_overrides(shot_page_id: str, branch_id: str) -> dict[str, object]:
        try:
            result = manager.get_effective_overrides(shot_page_id, branch_id)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.get("/api/projects/{project_id}/snapshots")
    def list_story_snapshots(project_id: str) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        items = manager.list_story_snapshots(project_id)
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/projects/{project_id}/snapshots", status_code=status.HTTP_201_CREATED)
    def create_story_snapshot(project_id: str, request: CreateSnapshotRequest) -> dict[str, object]:
        try:
            snapshot = manager.create_story_snapshot(project_id, request.label)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if snapshot is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {
            "database_environment": manager.active_environment,
            "snapshot": snapshot,
        }

    @app.get("/api/story-snapshots/{snapshot_id}")
    def get_story_snapshot(snapshot_id: str) -> dict[str, object]:
        snapshot = manager.get_story_snapshot(snapshot_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="快照不存在")
        return {
            "database_environment": manager.active_environment,
            "snapshot": snapshot,
        }

    @app.post("/api/story-snapshots/{snapshot_id}/restore")
    def restore_story_snapshot(snapshot_id: str) -> dict[str, object]:
        try:
            result = manager.restore_story_snapshot(snapshot_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="快照不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.get("/api/projects/{project_id}/operations")
    def list_operations(project_id: str, limit: int = 50) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        items = manager.list_operations(project_id, limit=limit)
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/operations/{operation_id}/undo")
    def undo_operation(operation_id: str) -> dict[str, object]:
        try:
            result = manager.undo_operation(operation_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="操作记录不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.post("/api/operations/{operation_id}/redo")
    def redo_operation(operation_id: str) -> dict[str, object]:
        try:
            result = manager.redo_operation(operation_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="操作记录不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.get("/api/shot-pages/{shot_page_id}/inheritance")
    def get_shot_page_inheritance(shot_page_id: str) -> dict[str, object]:
        result = manager.get_shot_page_inheritance(shot_page_id)
        if result is None:
            raise HTTPException(status_code=404, detail="场景页不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.post("/api/projects/{project_id}/precheck")
    def precheck_compilation(project_id: str, request: PrecheckRequest) -> dict[str, object]:
        try:
            result = manager.precheck_compilation(
                project_id, request.scope, request.scope_id
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="项目不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.post("/api/projects/{project_id}/compile")
    def compile_project_api(project_id: str, request: CompileRequest) -> dict[str, object]:
        """编译项目为页级跑图项列表。

        返回每个页面的完整输入快照、阻塞错误和警告。
        """
        try:
            result = compile_project(
                manager,
                project_id,
                scope=request.scope,
                scope_id=request.scope_id,
                instance_count=request.instance_count,
                seed_strategy=request.seed_strategy,
                seed_base=request.seed_base,
                workflow_id_override=request.workflow_id,
                workflow_version_id_override=request.workflow_version_id,
                skip_adopted=request.skip_adopted,
                only_failed=request.only_failed,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

        # 可选：解析语义插槽
        if request.resolve_slots:
            for item in result.items:
                try:
                    item.slot_resolutions = resolve_slots_for_item(manager, item)
                except Exception:
                    pass

        return {
            "database_environment": manager.active_environment,
            **result.to_dict(),
        }

    # ── 阶段 3.2 跑图列表与批量配置 API ───────────────────────────────

    @app.post("/api/projects/{project_id}/batch-drafts")
    def create_batch_draft_api(project_id: str, request: CreateBatchDraftRequest) -> dict[str, object]:
        """创建批量配置草稿。"""
        config = BatchConfig(
            instance_count=request.config.instance_count,
            seed_strategy=request.config.seed_strategy,
            seed_base=request.config.seed_base,
            workflow_id=request.config.workflow_id,
            workflow_version_id=request.config.workflow_version_id,
            skip_adopted=request.config.skip_adopted,
            only_failed=request.config.only_failed,
        )
        try:
            draft = create_draft(
                manager,
                project_id,
                name=request.name,
                scope=request.scope,
                scope_id=request.scope_id,
                config=config,
            )
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "draft": draft,
        }

    @app.get("/api/projects/{project_id}/batch-drafts")
    def list_batch_drafts_api(project_id: str, include_deleted: bool = False) -> dict[str, object]:
        """列出项目的批量配置草稿。"""
        drafts = list_drafts(manager, project_id, include_deleted=include_deleted)
        return {
            "database_environment": manager.active_environment,
            "drafts": drafts,
        }

    @app.get("/api/batch-drafts/{draft_id}")
    def get_batch_draft_api(draft_id: str) -> dict[str, object]:
        """获取草稿详情。"""
        draft = get_draft(manager, draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在")
        return {
            "database_environment": manager.active_environment,
            "draft": draft,
        }

    @app.patch("/api/batch-drafts/{draft_id}")
    def update_batch_draft_api(draft_id: str, request: UpdateBatchDraftRequest) -> dict[str, object]:
        """更新草稿。"""
        config = None
        if request.config is not None:
            config = BatchConfig(
                instance_count=request.config.instance_count,
                seed_strategy=request.config.seed_strategy,
                seed_base=request.config.seed_base,
                workflow_id=request.config.workflow_id,
                workflow_version_id=request.config.workflow_version_id,
                skip_adopted=request.config.skip_adopted,
                only_failed=request.config.only_failed,
            )
        try:
            draft = update_draft(
                manager,
                draft_id,
                name=request.name,
                scope=request.scope,
                scope_id=request.scope_id,
                config=config,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not draft:
            raise HTTPException(status_code=404, detail="草稿不存在")
        return {
            "database_environment": manager.active_environment,
            "draft": draft,
        }

    @app.delete("/api/batch-drafts/{draft_id}")
    def delete_batch_draft_api(draft_id: str) -> dict[str, object]:
        """软删除草稿。"""
        deleted = delete_draft(manager, draft_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="草稿不存在或已删除")
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
        }

    @app.post("/api/batch-drafts/{draft_id}/preview")
    def preview_batch_draft_api(draft_id: str, request: PreviewBatchDraftRequest) -> dict[str, object]:
        """编译草稿并缓存预览。"""
        try:
            preview = preview_draft(manager, draft_id, force=request.force)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "preview": preview,
        }

    @app.post("/api/batch-drafts/{draft_id}/commit")
    def commit_batch_draft_api(draft_id: str, request: CommitBatchDraftRequest) -> dict[str, object]:
        """提交草稿为不可变批次快照。"""
        try:
            batch = commit_draft(manager, draft_id, name=request.name)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            "batch": batch,
        }

    @app.get("/api/batches")
    def list_batches_api(
        project_id: str | None = None,
        status: str | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        """列出批次。"""
        try:
            batches = list_batches(
                manager,
                project_id=project_id,
                status=status,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "batches": batches,
        }

    @app.get("/api/projects/{project_id}/batches")
    def list_project_batches_api(
        project_id: str,
        status: str | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, object]:
        """列出项目的批次。"""
        try:
            batches = list_batches(
                manager,
                project_id=project_id,
                status=status,
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "batches": batches,
        }

    @app.get("/api/batches/{batch_id}")
    def get_batch_api(batch_id: str, include_snapshot: bool = True) -> dict[str, object]:
        """获取批次详情。"""
        batch = get_batch(manager, batch_id, include_snapshot=include_snapshot)
        if not batch:
            raise HTTPException(status_code=404, detail="批次不存在")
        return {
            "database_environment": manager.active_environment,
            "batch": batch,
        }

    @app.patch("/api/batches/{batch_id}/status")
    def update_batch_status_api(batch_id: str, request: UpdateBatchStatusRequest) -> dict[str, object]:
        """更新批次状态。"""
        try:
            batch = update_batch_status(manager, batch_id, request.status)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if not batch:
            raise HTTPException(status_code=404, detail="批次不存在")
        return {
            "database_environment": manager.active_environment,
            "batch": batch,
        }

    @app.delete("/api/batches/{batch_id}")
    def delete_batch_api(batch_id: str) -> dict[str, object]:
        """软删除批次。"""
        deleted = delete_batch(manager, batch_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="批次不存在或已删除")
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
        }

    # ── 阶段3.3 持久化任务队列 ──────────────────────────────────────

    @app.post("/api/batches/{batch_id}/tasks")
    def create_tasks_api(batch_id: str, request: CreateTasksRequest) -> dict[str, object]:
        """从批次的不可变快照展开为页级任务。

        幂等：若任务已存在则直接返回已有任务列表。
        """
        try:
            tasks = create_tasks_from_batch(
                manager,
                batch_id,
                max_attempts=request.max_attempts,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "batch_id": batch_id,
            "tasks": tasks,
            "count": len(tasks),
        }

    @app.get("/api/batches/{batch_id}/tasks")
    def list_tasks_api(
        batch_id: str,
        task_status: str | None = None,
        include_deleted: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, object]:
        """列出批次内的任务。"""
        if task_status is not None and task_status not in VALID_TASK_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"task_status 无效，允许值: {', '.join(VALID_TASK_STATUSES)}",
            )
        tasks = list_tasks(
            manager,
            batch_id,
            status=task_status,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )
        return {
            "database_environment": manager.active_environment,
            "batch_id": batch_id,
            "tasks": tasks,
            "count": len(tasks),
        }

    @app.get("/api/batches/{batch_id}/progress")
    def get_batch_progress_api(batch_id: str) -> dict[str, object]:
        """获取批次的任务进度统计。"""
        try:
            progress = get_batch_progress(manager, batch_id)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "progress": progress,
        }

    @app.get("/api/tasks/{task_id}")
    def get_task_api(task_id: str, include_item: bool = True) -> dict[str, object]:
        """获取任务详情。"""
        task = get_task(manager, task_id, include_item=include_item)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {
            "database_environment": manager.active_environment,
            "task": task,
        }

    @app.patch("/api/tasks/{task_id}")
    def update_task_api(task_id: str, request: TaskStatusUpdateRequest) -> dict[str, object]:
        """任务状态控制：pause / resume / cancel / retry。"""
        action_map = {
            "pause": pause_task,
            "resume": resume_task,
            "cancel": cancel_task,
            "retry": retry_task,
        }
        handler = action_map[request.action]
        task = handler(manager, task_id)
        if not task:
            raise HTTPException(
                status_code=422,
                detail=f"任务当前状态不允许执行 {request.action} 操作",
            )
        return {
            "database_environment": manager.active_environment,
            "task": task,
        }

    @app.patch("/api/tasks/{task_id}/priority")
    def set_task_priority_api(task_id: str, request: TaskPriorityRequest) -> dict[str, object]:
        """设置任务优先级。"""
        task = set_task_priority(manager, task_id, request.priority)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {
            "database_environment": manager.active_environment,
            "task": task,
        }

    @app.post("/api/tasks/claim")
    def claim_task_api(request: ClaimTaskRequest) -> dict[str, object]:
        """原子领取下一个可执行任务。

        返回 task + attempt + lease 信息；无可领取任务时返回 null。
        """
        claim = claim_next_task(
            manager,
            lease_holder=request.lease_holder,
            lease_seconds=request.lease_seconds,
            batch_id=request.batch_id,
        )
        return {
            "database_environment": manager.active_environment,
            "claim": claim,
        }

    @app.post("/api/tasks/claim-batch")
    def claim_tasks_batch_api(request: ClaimTasksBatchRequest) -> dict[str, object]:
        """批量领取多个任务。"""
        claims: list[dict[str, object]] = []
        for _ in range(request.count):
            claim = claim_next_task(
                manager,
                lease_holder=request.lease_holder,
                lease_seconds=request.lease_seconds,
                batch_id=request.batch_id,
            )
            if claim is None:
                break
            claims.append(claim)
        return {
            "database_environment": manager.active_environment,
            "claims": claims,
            "count": len(claims),
        }

    @app.post("/api/attempts/{attempt_id}/submit")
    def mark_attempt_submitted_api(
        attempt_id: str,
        request: AttemptSubmitRequest,
    ) -> dict[str, object]:
        """标记 attempt 已提交到 ComfyUI。"""
        attempt = mark_attempt_submitted(
            manager,
            attempt_id,
            prompt_id=request.prompt_id,
            api_json=request.api_json,
        )
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        return {
            "database_environment": manager.active_environment,
            "attempt": attempt,
        }

    @app.post("/api/attempts/{attempt_id}/complete")
    def mark_attempt_completed_api(attempt_id: str) -> dict[str, object]:
        """标记 attempt 成功完成，同时更新任务状态为 completed。"""
        attempt = mark_attempt_completed(manager, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        return {
            "database_environment": manager.active_environment,
            "attempt": attempt,
        }

    @app.post("/api/attempts/{attempt_id}/fail")
    def mark_attempt_failed_api(
        attempt_id: str,
        request: AttemptFailRequest,
    ) -> dict[str, object]:
        """标记 attempt 失败，根据重试次数决定任务状态。"""
        attempt = mark_attempt_failed(
            manager,
            attempt_id,
            error_message=request.error_message,
            error_type=request.error_type,
        )
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        return {
            "database_environment": manager.active_environment,
            "attempt": attempt,
        }

    @app.post("/api/attempts/{attempt_id}/unknown")
    def mark_attempt_unknown_api(
        attempt_id: str,
        request: AttemptUnknownRequest,
    ) -> dict[str, object]:
        """标记 attempt 状态为 unknown（重启后无法判断）。"""
        attempt = mark_attempt_unknown(manager, attempt_id, reason=request.reason)
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        return {
            "database_environment": manager.active_environment,
            "attempt": attempt,
        }

    @app.get("/api/attempts/{attempt_id}")
    def get_attempt_api(attempt_id: str) -> dict[str, object]:
        """获取 attempt 详情。"""
        attempt = get_attempt(manager, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        return {
            "database_environment": manager.active_environment,
            "attempt": attempt,
        }

    @app.get("/api/tasks/{task_id}/attempts")
    def list_attempts_api(task_id: str) -> dict[str, object]:
        """列出任务的所有 attempt（按尝试序号倒序）。"""
        attempts = list_attempts(manager, task_id)
        return {
            "database_environment": manager.active_environment,
            "task_id": task_id,
            "attempts": attempts,
            "count": len(attempts),
        }

    @app.get("/api/tasks/{task_id}/events")
    def list_events_api(
        task_id: str,
        event_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        """列出任务的事件。"""
        events = list_events(
            manager,
            task_id,
            event_type=event_type,
            limit=limit,
        )
        return {
            "database_environment": manager.active_environment,
            "task_id": task_id,
            "events": events,
            "count": len(events),
        }

    @app.post("/api/leases/{lease_id}/release")
    def release_lease_api(lease_id: str) -> dict[str, object]:
        """手动释放租约。"""
        released = release_lease(manager, lease_id)
        if not released:
            raise HTTPException(status_code=404, detail="租约不存在或已释放")
        return {
            "database_environment": manager.active_environment,
            "released": True,
        }

    @app.post("/api/tasks/expire-stale-leases")
    def expire_stale_leases_api() -> dict[str, object]:
        """过期所有超时租约，将对应任务重置为 pending。"""
        expired = expire_stale_leases(manager)
        return {
            "database_environment": manager.active_environment,
            "expired_count": expired,
        }

    @app.post("/api/tasks/recover")
    def recover_after_restart_api() -> dict[str, object]:
        """应用重启后的任务恢复。

        过期超时租约、重置 running 任务、标记 submitted attempt 为 unknown。
        """
        result = recover_after_restart(manager)
        return {
            "database_environment": manager.active_environment,
            "recovery": result,
        }

    # ── 阶段3.4 ComfyUI 提交 ────────────────────────────────────────

    @app.post("/api/tasks/{task_id}/attempts/{attempt_id}/submit-to-comfyui")
    def submit_to_comfyui_api(task_id: str, attempt_id: str) -> dict[str, object]:
        """提交任务到 ComfyUI 执行。

        流程：构建 API JSON → 提交 /prompt → 持久化 prompt_id。
        幂等：attempt 已有 prompt_id 时直接返回。
        """
        try:
            result = submit_task_to_comfyui(
                manager,
                comfyui_client,
                task_id,
                attempt_id,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ComfyUIError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "result": result,
        }

    @app.post("/api/attempts/{attempt_id}/check-history")
    def check_history_api(attempt_id: str) -> dict[str, object]:
        """查询 ComfyUI 历史记录，判断任务是否已完成。"""
        attempt = get_attempt(manager, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        prompt_id = attempt.get("prompt_id")
        if not prompt_id:
            raise HTTPException(status_code=422, detail="尝试记录缺少 prompt_id")
        history = check_comfyui_history(manager, comfyui_client, prompt_id)
        return {
            "database_environment": manager.active_environment,
            "attempt_id": attempt_id,
            "prompt_id": prompt_id,
            "history": history,
        }

    @app.post("/api/tasks/{task_id}/preview-api-json")
    def preview_api_json_api(task_id: str) -> dict[str, object]:
        """预览任务的最终 API JSON（不提交到 ComfyUI）。"""
        task = get_task(manager, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        item = task.get("item", {})
        if not item:
            raise HTTPException(status_code=422, detail="任务快照为空")
        try:
            api_json = build_api_json_for_item(manager, item)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "task_id": task_id,
            "api_json": api_json,
        }

    # ── 阶段3.5 实时进度与故障恢复 ──────────────────────────────────

    @app.get("/api/attempts/{attempt_id}/progress/sse")
    async def attempt_progress_sse(attempt_id: str):
        """SSE 推送任务进度。

        前端通过 EventSource 连接此端点，实时接收 ComfyUI 执行事件。
        连接超时或任务完成时自动关闭。
        """
        attempt = get_attempt(manager, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        prompt_id = attempt.get("prompt_id")
        if not prompt_id:
            raise HTTPException(status_code=422, detail="尝试记录缺少 prompt_id")
        return StreamingResponse(
            sse_progress_generator(progress_tracker, prompt_id, timeout_seconds=300.0),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/api/attempts/{attempt_id}/progress/poll")
    def poll_attempt_progress(attempt_id: str) -> dict[str, object]:
        """轮询任务进度（SSE 不可用时兜底）。

        直接查询 ComfyUI 历史，返回当前进度快照。
        """
        attempt = get_attempt(manager, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        result = poll_comfyui_history_for_attempt(
            manager, comfyui_client, attempt_id
        )
        if result is None:
            raise HTTPException(
                status_code=404,
                detail="尝试记录缺少 prompt_id 或 ComfyUI 历史中未找到",
            )
        return {
            "database_environment": manager.active_environment,
            "attempt_id": attempt_id,
            "result": result,
        }

    @app.post("/api/tasks/recover-submitted")
    def recover_submitted_tasks_api() -> dict[str, object]:
        """重启后恢复所有 submitted 状态的 attempt。

        核对 ComfyUI 历史，将已完成/失败的 attempt 更新状态，
        无法判断的标记为 unknown。
        """
        result = recover_submitted_attempts(manager, comfyui_client)
        return {
            "database_environment": manager.active_environment,
            "recovery": result,
        }

    @app.get("/api/attempts/{attempt_id}/progress")
    def get_attempt_progress(attempt_id: str) -> dict[str, object]:
        """获取 attempt 当前进度（从内存读取，不查询 ComfyUI）。"""
        attempt = get_attempt(manager, attempt_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="尝试记录不存在")
        prompt_id = attempt.get("prompt_id")
        if not prompt_id:
            raise HTTPException(status_code=422, detail="尝试记录缺少 prompt_id")
        progress = progress_tracker.get(prompt_id)
        return {
            "database_environment": manager.active_environment,
            "attempt_id": attempt_id,
            "prompt_id": prompt_id,
            "progress": progress,
        }

    # ── 阶段3.6 输出和图片实例 ──────────────────────────────────────

    @app.post("/api/attempts/{attempt_id}/collect-outputs")
    def collect_outputs_api(attempt_id: str) -> dict[str, object]:
        """收集 attempt 的所有输出图片。

        从 ComfyUI 历史解析输出，下载图片，写入文件和图片实例记录。
        """
        try:
            result = collect_attempt_outputs(
                manager, comfyui_client, attempt_id
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except ComfyUIError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "result": result,
        }

    @app.get("/api/image-instances")
    def list_image_instances_api(
        project_id: str | None = None,
        shot_page_id: str | None = None,
        task_id: str | None = None,
        attempt_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        """列出图片实例。"""
        instances = list_image_instances(
            manager,
            project_id=project_id,
            shot_page_id=shot_page_id,
            task_id=task_id,
            attempt_id=attempt_id,
            limit=limit,
            offset=offset,
        )
        return {
            "database_environment": manager.active_environment,
            "image_instances": instances,
            "count": len(instances),
        }

    @app.get("/api/image-instances/{instance_id}")
    def get_image_instance_api(instance_id: str) -> dict[str, object]:
        """获取单个图片实例详情。"""
        instance = get_image_instance(manager, instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="图片实例不存在")
        file_record = get_file_record(manager, instance.get("file_id", ""))
        return {
            "database_environment": manager.active_environment,
            "image_instance": instance,
            "file": file_record,
        }

    @app.get("/api/files/{file_id}/download")
    def download_file_api(file_id: str):
        """下载原始图片文件。"""
        file_record = get_file_record(manager, file_id)
        if not file_record:
            raise HTTPException(status_code=404, detail="文件不存在")
        file_path = get_file_path(manager, file_id)
        if not file_path or not file_path.exists():
            raise HTTPException(status_code=404, detail="文件存储不存在")
        return FileResponse(
            path=str(file_path),
            filename=file_record.get("original_name", file_path.name),
            media_type=file_record.get("mime_type", "application/octet-stream"),
        )

    @app.get("/api/background-jobs")
    def list_background_jobs_api(
        job_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        """列出后台任务。"""
        jobs = list_background_jobs(
            manager,
            job_type=job_type,
            status=status,
            limit=limit,
        )
        return {
            "database_environment": manager.active_environment,
            "background_jobs": jobs,
            "count": len(jobs),
        }

    # ── 阶段3.7 任务中心 API ────────────────────────────────────────

    @app.get("/api/tasks")
    def list_all_tasks_api(
        status: str | None = None,
        project_id: str | None = None,
        batch_id: str | None = None,
        has_error: bool | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        """任务中心：跨批次列出所有任务，支持多维度筛选。"""
        tasks = list_all_tasks(
            manager,
            status=status,
            project_id=project_id,
            batch_id=batch_id,
            has_error=has_error,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
        )
        return {
            "database_environment": manager.active_environment,
            "tasks": tasks,
            "count": len(tasks),
        }

    @app.get("/api/task-center/summary")
    def task_center_summary_api(project_id: str | None = None) -> dict[str, object]:
        """任务中心汇总统计：各状态任务数、错误任务数、批次统计。"""
        summary = get_task_center_summary(manager, project_id=project_id)
        return {
            "database_environment": manager.active_environment,
            "summary": summary,
        }

    @app.get("/api/tasks/{task_id}/error-detail")
    def get_task_error_detail_api(task_id: str) -> dict[str, object]:
        """获取任务错误详情和关联对象信息。"""
        task = get_task(manager, task_id, include_item=True)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        # 获取 attempt 列表
        attempts = list_attempts(manager, task_id)
        # 获取事件列表
        events = list_events(manager, task_id, limit=20)
        # 获取批次信息
        batch = get_batch(manager, task.get("batch_id", ""), include_snapshot=False)
        # 从 item 中提取关联对象
        item = task.get("item", {})
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except (TypeError, ValueError):
                item = {}
        return {
            "database_environment": manager.active_environment,
            "task": task,
            "attempts": attempts,
            "events": events,
            "batch": batch,
            "related": {
                "project_id": item.get("project_id"),
                "project_name": item.get("project_name"),
                "chapter_id": item.get("chapter_id"),
                "chapter_name": item.get("chapter_name"),
                "large_scene_id": item.get("large_scene_id"),
                "large_scene_name": item.get("large_scene_name"),
                "small_scene_id": item.get("small_scene_id"),
                "small_scene_name": item.get("small_scene_name"),
                "shot_page_id": item.get("shot_page_id"),
                "shot_page_title": item.get("shot_page_title"),
                "workflow_id": item.get("workflow_id"),
                "workflow_version_id": item.get("workflow_version_id"),
                "workflow_label": item.get("workflow_label"),
                "character_id": item.get("character_id"),
                "character_name": item.get("character_name"),
            },
        }

    # Warm the production lookup cache before the first page request. Test
    # application factories must not start a shared background import thread.
    if environment != "test":
        character_database.status()

    if not FRONTEND_ROOT.exists():
        raise RuntimeError(f"Frontend directory does not exist: {FRONTEND_ROOT}")
    app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
    return app
