"""Atelier 应用工厂。

本模块仅暴露 ``create_app`` 工厂与相关常量、请求模型，
不在导入时创建任何全局应用实例，从而避免测试导入时初始化真实数据库。
ASGI 入口 ``app`` 由 ``backend.app.main`` 单独持有。
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator

from .database import DatabaseManager, DatabaseSafetyError
from . import character_database


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"
FRONTEND_ROOT = PROJECT_ROOT / "design" / "ui-preview"


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
    material_type: Literal["composition", "expression", "scene", "lighting", "prompt", "composite_template"] = "composition"
    description: str = ""
    validation_status: Literal["verified", "unverified"] = "unverified"
    preview_path: str = ""
    tags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("素材名称不能为空。")
        return value


class UpdateMaterialRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    material_type: Literal["composition", "expression", "scene", "lighting", "prompt", "composite_template"] | None = None
    description: str | None = None
    validation_status: Literal["verified", "unverified"] | None = None
    preview_path: str | None = None
    tags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("素材名称不能为空。")
        return value

    @model_validator(mode="after")
    def at_least_one_field(self):
        if all(v is None for v in (self.name, self.material_type, self.description, self.validation_status, self.preview_path, self.tags)):
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


def create_app(
    *,
    data_root: Path | None = None,
    environment: Literal["production", "test"] = "production",
    locked_environment: Literal["production", "test"] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Atelier API",
        version="0.4.0",
        docs_url="/api/docs",
        redoc_url=None,
    )
    manager = DatabaseManager(
        data_root or DEFAULT_DATA_ROOT,
        environment=environment,
        locked_environment=locked_environment,
    )
    app.state.database_manager = manager

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

    # ── Materials ─────────────────────────────────────────────────────

    @app.get("/api/materials")
    def list_materials(
        material_type: str | None = None,
        validation_status: str | None = None,
        tag: str | None = None,
        q: str | None = None,
        sort: str = "updated_desc",
    ) -> dict[str, object]:
        items = manager.list_materials(
            material_type=material_type,
            validation_status=validation_status,
            tag=tag,
            q=q,
            sort=sort,
        )
        return {
            "database_environment": manager.active_environment,
            "items": items,
            "total": len(items),
        }

    @app.post("/api/materials", status_code=status.HTTP_201_CREATED)
    def create_material(request: CreateMaterialRequest) -> dict[str, object]:
        try:
            material = manager.create_material(
                request.name,
                request.material_type,
                description=request.description,
                validation_status=request.validation_status,
                preview_path=request.preview_path,
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
            raise HTTPException(status_code=404, detail="素材不存在")
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.patch("/api/materials/{material_id}")
    def update_material(material_id: str, request: UpdateMaterialRequest) -> dict[str, object]:
        try:
            material = manager.update_material(
                material_id,
                name=request.name,
                material_type=request.material_type,
                description=request.description,
                validation_status=request.validation_status,
                preview_path=request.preview_path,
                tags=request.tags,
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if material is None:
            raise HTTPException(status_code=404, detail="素材不存在")
        return {
            "database_environment": manager.active_environment,
            "material": material,
        }

    @app.delete("/api/materials/{material_id}")
    def delete_material(material_id: str) -> dict[str, object]:
        result = manager.delete_material(material_id)
        if result is None:
            raise HTTPException(status_code=404, detail="素材不存在")
        return {
            "database_environment": manager.active_environment,
            "deleted": result,
        }

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

    # Warm the production lookup cache before the first page request. Test
    # application factories must not start a shared background import thread.
    if environment != "test":
        character_database.status()

    if not FRONTEND_ROOT.exists():
        raise RuntimeError(f"Frontend directory does not exist: {FRONTEND_ROOT}")
    app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
    return app
