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

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("大场景名称不能为空。")
        return value


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


def create_app(
    *,
    data_root: Path | None = None,
    environment: Literal["production", "test"] = "production",
    locked_environment: Literal["production", "test"] | None = None,
) -> FastAPI:
    app = FastAPI(
        title="Atelier API",
        version="0.1.0",
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
            large_scene = manager.create_large_scene(chapter_id, request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "large_scene": large_scene,
        }

    @app.patch("/api/large-scenes/{large_scene_id}")
    def rename_large_scene(
        large_scene_id: str, request: RenameLargeSceneRequest
    ) -> dict[str, object]:
        if manager.get_large_scene(large_scene_id) is None:
            raise HTTPException(status_code=404, detail="大场景不存在。")
        try:
            large_scene = manager.rename_large_scene(
                large_scene_id, request.name
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "large_scene": large_scene,
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

    # ── Characters ──────────────────────────────────────────────

    @app.get("/api/projects/{project_id}/characters")
    def list_characters(project_id: str) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        characters = manager.list_characters(project_id)
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "items": characters,
            "total": len(characters),
        }

    @app.post(
        "/api/projects/{project_id}/characters",
        status_code=status.HTTP_201_CREATED,
    )
    def create_character(
        project_id: str, request: CreateCharacterRequest
    ) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        try:
            character = manager.create_character(project_id, request.name)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
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

    # ── Project Specs ───────────────────────────────────────────

    @app.get("/api/projects/{project_id}/specs")
    def list_project_specs(project_id: str) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        specs = manager.list_project_specs(project_id)
        return {
            "database_environment": manager.active_environment,
            "project_id": project_id,
            "items": specs,
            "total": len(specs),
        }

    @app.post(
        "/api/projects/{project_id}/specs",
        status_code=status.HTTP_201_CREATED,
    )
    def create_project_spec(
        project_id: str, request: CreateProjectSpecRequest
    ) -> dict[str, object]:
        if manager.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="项目不存在。")
        try:
            spec = manager.create_project_spec(
                project_id, request.spec_type, request.custom_label
            )
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "spec": spec,
        }

    @app.patch("/api/project-specs/{spec_id}")
    def update_project_spec(
        spec_id: str, request: UpdateProjectSpecRequest
    ) -> dict[str, object]:
        if manager.get_project_spec(spec_id) is None:
            raise HTTPException(status_code=404, detail="规格不存在。")
        try:
            spec = manager.update_project_spec(spec_id, request.custom_label)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "spec": spec,
        }

    @app.delete("/api/project-specs/{spec_id}")
    def delete_project_spec(spec_id: str) -> dict[str, object]:
        if manager.get_project_spec(spec_id) is None:
            raise HTTPException(status_code=404, detail="规格不存在。")
        deleted = manager.delete_project_spec(spec_id)
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
            value = manager.update_character_spec_value(
                spec_value_id,
                prompt=request.prompt,
                lora_name=request.lora_name,
                lora_weight=request.lora_weight,
                model_override=request.model_override,
                notes=request.notes,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return {
            "database_environment": manager.active_environment,
            "spec_value": value,
        }

    if not FRONTEND_ROOT.exists():
        raise RuntimeError(f"Frontend directory does not exist: {FRONTEND_ROOT}")
    app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")
    return app
