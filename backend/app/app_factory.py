"""Atelier 应用工厂。

本模块仅暴露 ``create_app`` 工厂与相关常量、请求模型，
不在导入时创建任何全局应用实例，从而避免测试导入时初始化真实数据库。
ASGI 入口 ``app`` 由 ``backend.app.main`` 单独持有。
"""
from __future__ import annotations

import io
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, UploadFile, File, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator, model_validator

from .database import DatabaseManager, DatabaseSafetyError
from . import character_database


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


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


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

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("人物名称不能为空。")
        return value


class RenameCharacterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("人物名称不能为空。")
        return value


class CreateCharacterVariantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("形象变体名称不能为空。")
        return value


class RenameCharacterVariantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("形象变体名称不能为空。")
        return value


class CreateProjectSpecRequest(BaseModel):
    spec_type: str = Field(min_length=1, max_length=40)
    custom_label: str = Field(default="", max_length=80)

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
    custom_label: str = Field(min_length=1, max_length=80)

    @field_validator("custom_label")
    @classmethod
    def custom_label_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("自定义规格标签不能为空。")
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

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("分支名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.name, self.description, self.is_enabled)):
            raise ValueError("至少需要提供一个更新字段。")
        return self


class SetMaterialsRequest(BaseModel):
    material_ids: list[str]


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
    material_page_id: str = Field(min_length=1)


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


def create_app(
    *,
    data_root: Path | None = None,
    environment: Literal["production", "test"] = "production",
    locked_environment: Literal["production", "test"] | None = None,
    system_features_path: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Atelier API",
        version="0.4.2",
        docs_url="/api/docs",
        redoc_url=None,
    )
    manager = DatabaseManager(
        data_root or DEFAULT_DATA_ROOT,
        environment=environment,
        locked_environment=locked_environment,
    )
    app.state.database_manager = manager
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

    @app.get("/api/projects")
    def list_projects() -> dict[str, object]:
        projects = manager.list_projects()
        return {
            "database_environment": manager.active_environment,
            "items": projects,
            "total": len(projects),
        }

    @app.post("/api/projects", status_code=status.HTTP_201_CREATED)
    def create_project(request: CreateProjectRequest) -> dict[str, object]:
        try:
            project = manager.create_project(request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
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
    def list_characters(project_id: str | None = None) -> dict[str, object]:
        if project_id is not None and manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        characters = manager.list_characters(project_id)
        for character in characters:
            character["stats"] = manager.get_character_stats(str(character["id"]))
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "items": characters,
            "total": len(characters),
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
            character = manager.create_character(request.name, project_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "character": character,
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
    def rename_character(
        character_id: str, request: RenameCharacterRequest
    ) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        try:
            character = manager.rename_character(character_id, request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "character": character,
        }

    @app.delete("/api/characters/{character_id}")
    def delete_character(character_id: str) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        deleted = manager.delete_character(character_id)
        return {
            "database_environment": manager.active_environment,
            "deleted": deleted,
        }

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
    def list_character_variants(character_id: str) -> dict[str, object]:
        if manager.get_character(character_id) is None:
            raise HTTPException(status_code=404, detail="人物不存在。")
        variants = manager.list_character_variants(character_id)
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
            variant = manager.create_character_variant(character_id, request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
        }

    @app.patch("/api/character-variants/{variant_id}")
    def rename_character_variant(
        variant_id: str, request: RenameCharacterVariantRequest
    ) -> dict[str, object]:
        if manager.get_character_variant(variant_id) is None:
            raise HTTPException(status_code=404, detail="形象变体不存在。")
        try:
            variant = manager.rename_character_variant(variant_id, request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "variant": variant,
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
                request.spec_type, request.custom_label
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
            spec = manager.update_spec(spec_id, request.custom_label)
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

    # ── Character Spec Values ───────────────────────────────────

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

    # ── Materials ──────────────────────────────────────────────

    @app.get("/api/materials")
    def list_materials(
        q: str = "",
        material_type: str = "",
        validation_status: str = "",
        tag: str = "",
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
            limit=limit,
            offset=offset,
            sort=sort,
        )
        return {
            "database_environment": manager.active_environment,
            **result,
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
        result = manager.delete_material(material_id)
        if result is None:
            raise HTTPException(status_code=404, detail="素材不存在。")
        # Clean up material image directory
        material_dir = manager.data_root / "materials" / material_id
        if material_dir.exists():
            try:
                shutil.rmtree(material_dir)
            except OSError:
                pass
        return {
            "database_environment": manager.active_environment,
            "deleted": True,
            "material_id": material_id,
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

    @app.post("/api/small-scenes/{small_scene_id}/pages")
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
            **result,
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
            **result,
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
        """6.3 场景页排序"""
        try:
            for idx, pid in enumerate(request.page_ids, start=1):
                manager.move_shot_page(pid, idx)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        pages = manager.list_shot_pages(small_scene_id)
        # 转换 title → name
        for p in pages:
            p["name"] = p.pop("title")
        return {
            "database_environment": manager.active_environment,
            "small_scene_id": small_scene_id,
            "pages": pages,
        }

    @app.post("/api/small-scenes/{small_scene_id}/resources")
    def add_small_scene_resource(small_scene_id: str, request: AddResourceRequest) -> dict[str, object]:
        """6.4 关联素材到小场景"""
        try:
            result = manager.add_small_scene_resource(small_scene_id, request.material_id)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.delete("/api/small-scene-resource-links/{link_id}")
    def remove_small_scene_resource_link(link_id: str) -> dict[str, object]:
        """6.4 移除小场景素材关联"""
        result = manager.remove_small_scene_resource_link(link_id)
        if result is None:
            raise HTTPException(status_code=404, detail="素材关联不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.put("/api/small-scene-pages/{page_id}/mappings/{material_type}")
    def set_scene_page_mapping(page_id: str, material_type: str, request: SetMappingRequest) -> dict[str, object]:
        """6.5 设置场景页映射（同类型原子替换）"""
        valid_types = ('composition', 'expression', 'scene', 'lighting', 'prompt', 'composite_template')
        if material_type not in valid_types:
            raise HTTPException(status_code=422, detail=f"素材类型无效，允许值: {', '.join(valid_types)}")
        try:
            result = manager.set_small_scene_page_mapping(page_id, material_type, request.material_page_id)
        except ValueError as error:
            msg = str(error)
            code = 404 if "不存在" in msg else 422
            raise HTTPException(status_code=code, detail=msg) from error
        return {
            "database_environment": manager.active_environment,
            **result,
        }

    @app.delete("/api/small-scene-pages/{page_id}/mappings/{material_type}")
    def unset_scene_page_mapping(page_id: str, material_type: str) -> dict[str, object]:
        """6.5 取消场景页映射"""
        valid_types = ('composition', 'expression', 'scene', 'lighting', 'prompt', 'composite_template')
        if material_type not in valid_types:
            raise HTTPException(status_code=422, detail=f"素材类型无效，允许值: {', '.join(valid_types)}")
        result = manager.unset_small_scene_page_mapping(page_id, material_type)
        if result is None:
            raise HTTPException(status_code=404, detail="映射不存在")
        return {
            "database_environment": manager.active_environment,
            **result,
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

    # Warm the production lookup cache before the first page request. Test
    # application factories must not start a shared background import thread.
    if environment != "test":
        character_database.status()

    if not FRONTEND_ROOT.exists():
        raise RuntimeError(f"Frontend directory does not exist: {FRONTEND_ROOT}")
    app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
    return app
