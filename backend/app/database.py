from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4


DatabaseEnvironment = Literal["production", "test"]
VALID_ENVIRONMENTS: tuple[DatabaseEnvironment, ...] = ("production", "test")
_UNSET = object()


class DatabaseSafetyError(RuntimeError):
    """Raised when an operation could cross the production/test boundary."""


@dataclass(frozen=True)
class DatabaseDescriptor:
    environment: DatabaseEnvironment
    path: Path
    purpose: str


class DatabaseManager:
    """Owns two physically separate SQLite databases and the active environment."""

    def __init__(
        self,
        data_root: Path,
        environment: DatabaseEnvironment = "production",
        *,
        locked_environment: DatabaseEnvironment | None = None,
    ) -> None:
        self.data_root = data_root.resolve()
        self.database_root = (self.data_root / "databases").resolve()
        self.database_root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._locked_environment = locked_environment
        self._active_environment = self._validate_environment(environment)

        if locked_environment and environment != locked_environment:
            raise DatabaseSafetyError(
                f"Locked database environment is {locked_environment}, not {environment}."
            )

        self._descriptors = {
            "production": DatabaseDescriptor(
                environment="production",
                path=self.database_root / "atelier.production.sqlite3",
                purpose="Your real projects and production output metadata.",
            ),
            "test": DatabaseDescriptor(
                environment="test",
                path=self.database_root / "atelier.test.sqlite3",
                purpose="Development checks, automated tests, and disposable demo data.",
            ),
        }
        self._assert_paths_are_isolated()
        for target_environment in VALID_ENVIRONMENTS:
            self.initialize(target_environment)

    @property
    def active_environment(self) -> DatabaseEnvironment:
        return self._active_environment

    @property
    def locked_environment(self) -> DatabaseEnvironment | None:
        return self._locked_environment

    def descriptor(self, environment: DatabaseEnvironment) -> DatabaseDescriptor:
        return self._descriptors[self._validate_environment(environment)]

    def _validate_environment(self, environment: str) -> DatabaseEnvironment:
        if environment not in VALID_ENVIRONMENTS:
            raise ValueError(f"Unknown database environment: {environment}")
        return environment  # type: ignore[return-value]

    def _assert_paths_are_isolated(self) -> None:
        production = self._descriptors["production"].path.resolve()
        test = self._descriptors["test"].path.resolve()
        if production == test:
            raise DatabaseSafetyError("Production and test database paths must differ.")
        if production.parent != self.database_root or test.parent != self.database_root:
            raise DatabaseSafetyError("Database path escaped the Atelier data directory.")

    @contextmanager
    def connection(
        self, environment: DatabaseEnvironment | None = None
    ) -> Iterator[sqlite3.Connection]:
        target_environment = environment or self._active_environment
        descriptor = self.descriptor(target_environment)
        connection = sqlite3.connect(descriptor.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self, environment: DatabaseEnvironment) -> None:
        descriptor = self.descriptor(environment)
        with self._lock, self.connection(environment) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            # Disable foreign keys during schema migration to allow table rebuilds
            # (ALTER TABLE RENAME + CREATE + INSERT + DROP sequence would otherwise
            # fail when other tables hold FK references to the table being rebuilt).
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS atelier_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS database_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    event_value TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    cover_path TEXT,
                    archived_at TEXT,
                    deleted_at TEXT,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_projects_status
                    ON projects(status, updated_at DESC);

                -- Note: idx_projects_deleted is created by _migrate_projects_extend
                -- to handle legacy tables missing the deleted_at column.

                CREATE TABLE IF NOT EXISTS chapters (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (project_id)
                        REFERENCES projects(id) ON DELETE CASCADE,
                    UNIQUE (project_id, name)
                );

                CREATE INDEX IF NOT EXISTS idx_chapters_project_sort
                    ON chapters(project_id, sort_order);

                CREATE TABLE IF NOT EXISTS large_scenes (
                    id TEXT PRIMARY KEY,
                    chapter_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    scene_type TEXT NOT NULL DEFAULT 'content',
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (chapter_id)
                        REFERENCES chapters(id) ON DELETE CASCADE,
                    UNIQUE (chapter_id, name)
                );

                CREATE INDEX IF NOT EXISTS idx_large_scenes_chapter_sort
                    ON large_scenes(chapter_id, sort_order);

                CREATE TABLE IF NOT EXISTS characters (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE,
                    description TEXT NOT NULL DEFAULT '',
                    cover_path TEXT,
                    archived_at TEXT,
                    deleted_at TEXT,
                    source TEXT NOT NULL DEFAULT '',
                    source_identifier TEXT,
                    external_url TEXT,
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_characters_sort
                    ON characters(sort_order);

                -- Note: idx_characters_deleted and idx_characters_archived are created
                -- by _migrate_characters_extend to handle legacy tables missing columns.

                CREATE TABLE IF NOT EXISTS character_tags (
                    id TEXT PRIMARY KEY,
                    character_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id) ON DELETE CASCADE,
                    UNIQUE (character_id, tag)
                );

                CREATE INDEX IF NOT EXISTS idx_character_tags_character
                    ON character_tags(character_id);

                CREATE INDEX IF NOT EXISTS idx_character_tags_tag
                    ON character_tags(tag);

                CREATE TABLE IF NOT EXISTS project_characters (
                    project_id TEXT NOT NULL,
                    character_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (project_id, character_id),
                    FOREIGN KEY (project_id)
                        REFERENCES projects(id) ON DELETE CASCADE,
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_project_characters_project
                    ON project_characters(project_id);

                CREATE TABLE IF NOT EXISTS character_variants (
                    id TEXT PRIMARY KEY,
                    character_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    default_prompt TEXT NOT NULL DEFAULT '',
                    default_lora_name TEXT NOT NULL DEFAULT '',
                    default_lora_weight REAL,
                    default_model_override TEXT NOT NULL DEFAULT '',
                    preview_original_path TEXT,
                    preview_thumbnail_path TEXT,
                    archived_at TEXT,
                    source_variant_id TEXT,
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_character_variants_character_sort
                    ON character_variants(character_id, sort_order);

                CREATE TABLE IF NOT EXISTS specs (
                    id TEXT PRIMARY KEY,
                    spec_type TEXT NOT NULL,
                    custom_label TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    is_required INTEGER NOT NULL DEFAULT 0,
                    default_value TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (spec_type, custom_label)
                );

                CREATE INDEX IF NOT EXISTS idx_specs_sort
                    ON specs(sort_order);

                CREATE TABLE IF NOT EXISTS character_spec_values (
                    id TEXT PRIMARY KEY,
                    variant_id TEXT NOT NULL,
                    spec_id TEXT NOT NULL,
                    prompt TEXT NOT NULL DEFAULT '',
                    lora_name TEXT NOT NULL DEFAULT '',
                    lora_weight REAL,
                    model_override TEXT NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    preview_original_path TEXT,
                    preview_thumbnail_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (variant_id)
                        REFERENCES character_variants(id) ON DELETE CASCADE,
                    FOREIGN KEY (spec_id)
                        REFERENCES specs(id) ON DELETE CASCADE,
                    UNIQUE (variant_id, spec_id)
                );

                CREATE INDEX IF NOT EXISTS idx_character_spec_values_variant
                    ON character_spec_values(variant_id);

                CREATE TABLE IF NOT EXISTS shot_page_characters (
                    shot_page_id TEXT NOT NULL,
                    character_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (shot_page_id),
                    FOREIGN KEY (shot_page_id)
                        REFERENCES shot_pages(id) ON DELETE CASCADE,
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id) ON DELETE CASCADE,
                    FOREIGN KEY (variant_id)
                        REFERENCES character_variants(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_shot_page_characters_character
                    ON shot_page_characters(character_id);

                CREATE INDEX IF NOT EXISTS idx_shot_page_characters_variant
                    ON shot_page_characters(variant_id);

                CREATE TABLE IF NOT EXISTS materials (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE,
                    material_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    prompt_text TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    validation_status TEXT NOT NULL DEFAULT 'unverified',
                    notes TEXT NOT NULL DEFAULT '',
                    preview_original_path TEXT,
                    preview_thumbnail_path TEXT,
                    archived_at TEXT,
                    deleted_at TEXT,
                    source_material_id TEXT,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (
                        material_type IN (
                            'composition',
                            'expression',
                            'scene',
                            'lighting',
                            'prompt',
                            'composite_template'
                        )
                    ),
                    CHECK (validation_status IN ('unverified', 'verified'))
                );

                CREATE INDEX IF NOT EXISTS idx_materials_type_updated
                    ON materials(material_type, updated_at DESC);

                CREATE INDEX IF NOT EXISTS idx_materials_status_updated
                    ON materials(validation_status, updated_at DESC);

                -- Note: idx_materials_deleted and idx_materials_archived are created
                -- by _migrate_materials_extend to handle legacy tables missing columns.

                CREATE INDEX IF NOT EXISTS idx_materials_name
                    ON materials(name);

                CREATE TABLE IF NOT EXISTS material_tags (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS material_tag_links (
                    material_id TEXT NOT NULL,
                    tag_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (material_id, tag_id),
                    FOREIGN KEY (material_id)
                        REFERENCES materials(id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id)
                        REFERENCES material_tags(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_material_tag_links_tag
                    ON material_tag_links(tag_id, material_id);

                CREATE TABLE IF NOT EXISTS small_scenes (
                    id TEXT PRIMARY KEY,
                    large_scene_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    scene_type TEXT NOT NULL DEFAULT 'content',
                    description TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (large_scene_id)
                        REFERENCES large_scenes(id) ON DELETE CASCADE,
                    UNIQUE (large_scene_id, name)
                );

                CREATE INDEX IF NOT EXISTS idx_small_scenes_large_scene_sort
                    ON small_scenes(large_scene_id, sort_order);

                CREATE TABLE IF NOT EXISTS branches (
                    id TEXT PRIMARY KEY,
                    parent_type TEXT NOT NULL,
                    parent_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (
                        parent_type IN ('large_scene', 'small_scene')
                    )
                );

                CREATE INDEX IF NOT EXISTS idx_branches_parent
                    ON branches(parent_type, parent_id, sort_order);

                CREATE TABLE IF NOT EXISTS shot_pages (
                    id TEXT PRIMARY KEY,
                    small_scene_id TEXT NOT NULL,
                    branch_id TEXT,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    prompt_text TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (small_scene_id)
                        REFERENCES small_scenes(id) ON DELETE CASCADE,
                    FOREIGN KEY (branch_id)
                        REFERENCES branches(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_shot_pages_small_scene_sort
                    ON shot_pages(small_scene_id, sort_order);

                CREATE INDEX IF NOT EXISTS idx_shot_pages_branch_sort
                    ON shot_pages(branch_id, sort_order);

                CREATE TABLE IF NOT EXISTS small_scene_materials (
                    small_scene_id TEXT NOT NULL,
                    material_id TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (small_scene_id, material_id),
                    FOREIGN KEY (small_scene_id)
                        REFERENCES small_scenes(id) ON DELETE CASCADE,
                    FOREIGN KEY (material_id)
                        REFERENCES materials(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_small_scene_materials_material
                    ON small_scene_materials(material_id, small_scene_id);

                CREATE TABLE IF NOT EXISTS shot_page_materials (
                    shot_page_id TEXT NOT NULL,
                    material_id TEXT NOT NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (shot_page_id, material_id),
                    FOREIGN KEY (shot_page_id)
                        REFERENCES shot_pages(id) ON DELETE CASCADE,
                    FOREIGN KEY (material_id)
                        REFERENCES materials(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_shot_page_materials_material
                    ON shot_page_materials(material_id, shot_page_id);

                CREATE TABLE IF NOT EXISTS material_pages (
                    id TEXT PRIMARY KEY,
                    material_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    prompt_text TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    preview_original_path TEXT,
                    preview_thumbnail_path TEXT,
                    source_page_id TEXT,
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (material_id)
                        REFERENCES materials(id) ON DELETE CASCADE,
                    UNIQUE (material_id, name)
                );

                CREATE INDEX IF NOT EXISTS idx_material_pages_material_sort
                    ON material_pages(material_id, sort_order);

                CREATE TABLE IF NOT EXISTS material_versions (
                    id TEXT PRIMARY KEY,
                    material_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    snapshot TEXT NOT NULL,
                    label TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (material_id)
                        REFERENCES materials(id) ON DELETE CASCADE,
                    UNIQUE (material_id, version_number)
                );

                CREATE INDEX IF NOT EXISTS idx_material_versions_material
                    ON material_versions(material_id, version_number DESC);

                CREATE TABLE IF NOT EXISTS small_scene_page_mappings (
                    id TEXT PRIMARY KEY,
                    scene_page_id TEXT NOT NULL,
                    material_page_id TEXT NOT NULL,
                    material_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (scene_page_id)
                        REFERENCES shot_pages(id) ON DELETE CASCADE,
                    FOREIGN KEY (material_page_id)
                        REFERENCES material_pages(id) ON DELETE CASCADE,
                    UNIQUE (scene_page_id, material_type)
                );

                CREATE INDEX IF NOT EXISTS idx_small_scene_page_mappings_material_page
                    ON small_scene_page_mappings(material_page_id, scene_page_id);
                """
            )
            # schema_migrations table for versioned migration tracking
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                )
                """
            )
            # Versioned migrations: each is idempotent and registered with a version.
            # For databases that predate schema_migrations, all existing migrations
            # run once (they are idempotent) and get marked as applied.
            self._run_migration(
                connection, "v0.1.7", "Migrate legacy character schema",
                self._migrate_legacy_character_schema,
            )
            self._run_migration(
                connection, "v0.2.0", "Add scene_type to large_scenes",
                self._migrate_large_scenes_scene_type,
            )
            self._run_migration(
                connection, "v0.4.0", "Create materials/small_scenes/branches/shot_pages tables",
                self._migrate_v040_tables,
            )
            self._run_migration(
                connection, "v0.4.1", "Create material_pages and small_scene_page_mappings tables",
                self._migrate_v041_tables,
            )
            self._run_migration(
                connection, "v0.4.1.1", "Create default material pages for existing materials",
                self._migrate_default_material_pages,
            )
            self._run_migration(
                connection, "v0.4.1.2", "Fix empty link IDs in small_scene_materials",
                self._migrate_fix_empty_link_ids,
            )
            self._run_migration(
                connection, "v0.5.0", "Add revision column to core editing tables",
                self._migrate_add_revision_columns,
            )
            self._run_migration(
                connection, "v0.5.1", "Extend projects table: add description/cover/archived_at/deleted_at, drop UNIQUE on name",
                self._migrate_projects_extend,
            )
            self._run_migration(
                connection, "v0.5.2", "Extend materials/material_pages: add archived_at/deleted_at/source_material_id, page preview/source_page_id, material_versions table",
                self._migrate_materials_extend,
            )
            self._run_migration(
                connection, "v0.5.3", "Extend characters/character_variants/specs/character_spec_values: archive/delete/source/preview/cover/tags",
                self._migrate_characters_extend,
            )
            self._run_migration(
                connection, "v0.5.4", "Extend branches with condition fields; add branch_overrides/story_snapshots/operation_history tables",
                self._migrate_branches_extend,
            )
            self._run_migration(
                connection, "v0.5.5", "Add app_settings/comfyui_node_definitions/comfyui_resource_cache tables for ComfyUI connection layer",
                self._migrate_comfyui_connect,
            )
            self._run_migration(
                connection, "v0.5.6", "Add workflows/workflow_versions/workflow_drafts/semantic_slots/project_default_workflows tables",
                self._migrate_workflows,
            )
            self._run_migration(
                connection, "v0.5.7", "Extend workflow_drafts with last_node_id/last_link_id/validation_state for node editor",
                self._migrate_workflow_draft_extend,
            )
            self._run_migration(
                connection, "v0.5.8", "Extend workflow_drafts with layout_state for regular layout",
                self._migrate_workflow_draft_layout_extend,
            )
            marker = connection.execute(
                "SELECT value FROM atelier_meta WHERE key = 'environment'"
            ).fetchone()
            if marker and marker["value"] != environment:
                raise DatabaseSafetyError(
                    f"Database marker is {marker['value']}, expected {environment}."
                )
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                INSERT INTO atelier_meta(key, value)
                VALUES('environment', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (environment,),
            )
            connection.execute(
                """
                INSERT INTO atelier_meta(key, value)
                VALUES('initialized_at', ?)
                ON CONFLICT(key) DO NOTHING
                """,
                (now,),
            )
            # Re-enable foreign keys after migration is complete.
            connection.execute("PRAGMA foreign_keys = ON")

    def _migrate_legacy_character_schema(self, connection) -> None:
        """Migrate pre-v0.1.7 schema: characters had project_id, project_specs was project-scoped."""
        # Check if old characters table has project_id column
        cols = [row["name"] for row in connection.execute("PRAGMA table_info(characters)").fetchall()]
        if "project_id" not in cols:
            return  # Already new schema or empty

        # Backup old data
        old_chars = connection.execute(
            "SELECT id, project_id, name, sort_order, created_at, updated_at FROM characters"
        ).fetchall()
        old_variants = connection.execute(
            "SELECT id, character_id, name, is_default, sort_order, created_at, updated_at FROM character_variants"
        ).fetchall()
        old_specs = connection.execute(
            "SELECT id, project_id, spec_type, custom_label, sort_order, created_at, updated_at FROM project_specs"
        ).fetchall()
        old_csv = connection.execute(
            "SELECT id, variant_id, project_spec_id, prompt, lora_name, lora_weight, model_override, notes, created_at, updated_at FROM character_spec_values"
        ).fetchall()

        # Drop old tables and recreate with new schema
        connection.execute("DROP TABLE IF EXISTS character_spec_values")
        connection.execute("DROP TABLE IF EXISTS character_variants")
        connection.execute("DROP TABLE IF EXISTS project_specs")
        connection.execute("DROP TABLE IF EXISTS project_characters")
        connection.execute("DROP TABLE IF EXISTS specs")
        connection.execute("DROP TABLE IF EXISTS characters")

        connection.execute(
            """
            CREATE TABLE characters (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (name)
            )
            """
        )
        connection.execute("CREATE INDEX idx_characters_sort ON characters(sort_order)")
        connection.execute(
            """
            CREATE TABLE project_characters (
                project_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (project_id, character_id),
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute("CREATE INDEX idx_project_characters_project ON project_characters(project_id)")
        connection.execute(
            """
            CREATE TABLE character_variants (
                id TEXT PRIMARY KEY,
                character_id TEXT NOT NULL,
                name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE,
                UNIQUE (character_id, name)
            )
            """
        )
        connection.execute("CREATE INDEX idx_character_variants_character_sort ON character_variants(character_id, sort_order)")
        connection.execute(
            """
            CREATE TABLE specs (
                id TEXT PRIMARY KEY,
                spec_type TEXT NOT NULL,
                custom_label TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (spec_type, custom_label)
            )
            """
        )
        connection.execute("CREATE INDEX idx_specs_sort ON specs(sort_order)")
        connection.execute(
            """
            CREATE TABLE character_spec_values (
                id TEXT PRIMARY KEY,
                variant_id TEXT NOT NULL,
                spec_id TEXT NOT NULL,
                prompt TEXT NOT NULL DEFAULT '',
                lora_name TEXT NOT NULL DEFAULT '',
                lora_weight REAL,
                model_override TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (variant_id) REFERENCES character_variants(id) ON DELETE CASCADE,
                FOREIGN KEY (spec_id) REFERENCES specs(id) ON DELETE CASCADE,
                UNIQUE (variant_id, spec_id)
            )
            """
        )
        connection.execute("CREATE INDEX idx_character_spec_values_variant ON character_spec_values(variant_id)")

        # Migrate characters (deduplicate by name, prefer earliest created_at)
        seen_names = {}
        for row in old_chars:
            name = row["name"]
            if name not in seen_names or row["created_at"] < seen_names[name]["created_at"]:
                seen_names[name] = row
        for name, row in seen_names.items():
            connection.execute(
                "INSERT INTO characters(id, name, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (row["id"], name, row["sort_order"], row["created_at"], row["updated_at"]),
            )
            # Re-create project_characters association from original project_id
            connection.execute(
                "INSERT OR IGNORE INTO project_characters(project_id, character_id, created_at) VALUES (?, ?, ?)",
                (row["project_id"], row["id"], row["created_at"]),
            )

        # Re-insert character_variants (schema unchanged)
        for row in old_variants:
            connection.execute(
                "INSERT OR IGNORE INTO character_variants(id, character_id, name, is_default, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row["id"], row["character_id"], row["name"], row["is_default"], row["sort_order"], row["created_at"], row["updated_at"]),
            )

        # Migrate specs (deduplicate by spec_type + custom_label)
        seen_specs = {}
        for row in old_specs:
            key = (row["spec_type"], row["custom_label"])
            if key not in seen_specs or row["created_at"] < seen_specs[key]["created_at"]:
                seen_specs[key] = row
        for key, row in seen_specs.items():
            connection.execute(
                "INSERT INTO specs(id, spec_type, custom_label, sort_order, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (row["id"], row["spec_type"], row["custom_label"], row["sort_order"], row["created_at"], row["updated_at"]),
            )

        # Migrate character_spec_values (project_spec_id → spec_id, mapping already preserved since spec ids unchanged)
        for row in old_csv:
            connection.execute(
                """INSERT INTO character_spec_values(
                    id, variant_id, spec_id, prompt, lora_name, lora_weight, model_override, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["id"], row["variant_id"], row["project_spec_id"], row["prompt"], row["lora_name"],
                 row["lora_weight"], row["model_override"], row["notes"], row["created_at"], row["updated_at"]),
            )

    def _migrate_large_scenes_scene_type(self, connection) -> None:
        """Add scene_type column to large_scenes for pre-v0.2.0 databases.

        Uses PRAGMA table_info to check existence. Existing rows get 'content'.
        Does not touch data beyond setting the default.
        """
        cols = [row["name"] for row in connection.execute("PRAGMA table_info(large_scenes)").fetchall()]
        if "scene_type" in cols:
            return
        connection.execute(
            "ALTER TABLE large_scenes ADD COLUMN scene_type TEXT NOT NULL DEFAULT 'content'"
        )

    def _migrate_v040_tables(self, connection) -> None:
        v040_tables = [
            "materials", "material_tags", "small_scenes", "branches",
            "shot_pages", "small_scene_materials", "shot_page_materials",
        ]
        for table_name in v040_tables:
            exists = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
            if exists:
                continue
            if table_name == "materials":
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS materials (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        material_type TEXT NOT NULL DEFAULT 'composition',
                        description TEXT NOT NULL DEFAULT '',
                        validation_status TEXT NOT NULL DEFAULT 'unverified',
                        preview_path TEXT NOT NULL DEFAULT '',
                        sort_order INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        CHECK (material_type IN ('composition','expression','scene','lighting','prompt','composite_template')),
                        CHECK (validation_status IN ('verified','unverified'))
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_materials_sort ON materials(sort_order)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_materials_type ON materials(material_type)")
            elif table_name == "material_tags":
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS material_tags (
                        id TEXT PRIMARY KEY,
                        material_id TEXT NOT NULL,
                        tag TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_material_tags_material ON material_tags(material_id)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_material_tags_tag ON material_tags(tag)")
            elif table_name == "small_scenes":
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS small_scenes (
                        id TEXT PRIMARY KEY,
                        large_scene_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        scene_type TEXT NOT NULL DEFAULT 'content',
                        description TEXT NOT NULL DEFAULT '',
                        sort_order INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (large_scene_id) REFERENCES large_scenes(id) ON DELETE CASCADE,
                        UNIQUE (large_scene_id, name)
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_small_scenes_large_scene_sort ON small_scenes(large_scene_id, sort_order)")
            elif table_name == "branches":
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS branches (
                        id TEXT PRIMARY KEY,
                        parent_type TEXT NOT NULL,
                        parent_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        is_enabled INTEGER NOT NULL DEFAULT 1,
                        sort_order INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        CHECK (parent_type IN ('large_scene','small_scene'))
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_branches_parent ON branches(parent_type, parent_id, sort_order)")
            elif table_name == "shot_pages":
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS shot_pages (
                        id TEXT PRIMARY KEY,
                        small_scene_id TEXT NOT NULL,
                        branch_id TEXT,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        prompt_text TEXT NOT NULL DEFAULT '',
                        negative_prompt TEXT NOT NULL DEFAULT '',
                        sort_order INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (small_scene_id) REFERENCES small_scenes(id) ON DELETE CASCADE,
                        FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE CASCADE
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_shot_pages_small_scene_sort ON shot_pages(small_scene_id, sort_order)")
                connection.execute("CREATE INDEX IF NOT EXISTS idx_shot_pages_branch_sort ON shot_pages(branch_id, sort_order)")
            elif table_name == "small_scene_materials":
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS small_scene_materials (
                        small_scene_id TEXT NOT NULL,
                        material_id TEXT NOT NULL,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (small_scene_id, material_id),
                        FOREIGN KEY (small_scene_id) REFERENCES small_scenes(id) ON DELETE CASCADE,
                        FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_small_scene_materials_material ON small_scene_materials(material_id, small_scene_id)")
            elif table_name == "shot_page_materials":
                connection.execute("""
                    CREATE TABLE IF NOT EXISTS shot_page_materials (
                        shot_page_id TEXT NOT NULL,
                        material_id TEXT NOT NULL,
                        sort_order INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        PRIMARY KEY (shot_page_id, material_id),
                        FOREIGN KEY (shot_page_id) REFERENCES shot_pages(id) ON DELETE CASCADE,
                        FOREIGN KEY (material_id) REFERENCES materials(id) ON DELETE CASCADE
                    )
                """)
                connection.execute("CREATE INDEX IF NOT EXISTS idx_shot_page_materials_material ON shot_page_materials(material_id, shot_page_id)")

    def _migrate_v041_tables(self, connection) -> None:
        """v0.4.1 migration: add material_pages, small_scene_page_mappings, and id column to small_scene_materials."""
        # material_pages table
        exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='material_pages'"
        ).fetchone()
        if not exists:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS material_pages (
                    id TEXT PRIMARY KEY,
                    material_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    prompt_text TEXT NOT NULL DEFAULT '',
                    negative_prompt TEXT NOT NULL DEFAULT '',
                    sort_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (material_id)
                        REFERENCES materials(id) ON DELETE CASCADE,
                    UNIQUE (material_id, name)
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_material_pages_material_sort ON material_pages(material_id, sort_order)")

        # small_scene_page_mappings table
        exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='small_scene_page_mappings'"
        ).fetchone()
        if not exists:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS small_scene_page_mappings (
                    id TEXT PRIMARY KEY,
                    scene_page_id TEXT NOT NULL,
                    material_page_id TEXT NOT NULL,
                    material_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (scene_page_id)
                        REFERENCES shot_pages(id) ON DELETE CASCADE,
                    FOREIGN KEY (material_page_id)
                        REFERENCES material_pages(id) ON DELETE CASCADE,
                    UNIQUE (scene_page_id, material_type)
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS idx_small_scene_page_mappings_material_page ON small_scene_page_mappings(material_page_id, scene_page_id)")

        # Add id column to small_scene_materials (for stable link_id)
        cols = [row["name"] for row in connection.execute("PRAGMA table_info(small_scene_materials)").fetchall()]
        if "id" not in cols:
            connection.execute("ALTER TABLE small_scene_materials ADD COLUMN id TEXT")
            # Backfill UUIDs for existing rows
            rows = connection.execute("SELECT small_scene_id, material_id FROM small_scene_materials").fetchall()
            from uuid import uuid4
            for row in rows:
                connection.execute(
                    "UPDATE small_scene_materials SET id = ? WHERE small_scene_id = ? AND material_id = ?",
                    (str(uuid4()), row["small_scene_id"], row["material_id"]),
                )
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_small_scene_materials_id ON small_scene_materials(id)")

    def _migrate_default_material_pages(self, connection) -> None:
        """Create default material_pages for materials that have none. Idempotent."""
        # Check if material_pages table exists
        exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='material_pages'"
        ).fetchone()
        if not exists:
            return
        from uuid import uuid4
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        # Find materials without any pages
        materials = connection.execute("""
            SELECT m.id, m.name, m.description, m.content, m.prompt_text, m.negative_prompt
            FROM materials m
            WHERE NOT EXISTS (
                SELECT 1 FROM material_pages mp WHERE mp.material_id = m.id
            )
        """).fetchall()
        for mat in materials:
            connection.execute(
                """INSERT INTO material_pages
                   (id, material_id, name, description, content, prompt_text, negative_prompt, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (str(uuid4()), mat["id"], mat["name"], mat["description"], mat["content"],
                 mat["prompt_text"], mat["negative_prompt"], now, now),
            )

    def _migrate_fix_empty_link_ids(self, connection) -> None:
        """Idempotent fix for small_scene_materials.id being NULL or empty string.

        Per second-round requirement 9.2: backfill UUIDs for any rows where id is
        NULL or empty. Re-running this migration must not modify rows that already
        have a valid non-empty id.
        """
        # Check table exists
        exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='small_scene_materials'"
        ).fetchone()
        if not exists:
            return
        cols = [row["name"] for row in connection.execute("PRAGMA table_info(small_scene_materials)").fetchall()]
        if "id" not in cols:
            return
        from uuid import uuid4
        rows = connection.execute(
            "SELECT small_scene_id, material_id FROM small_scene_materials WHERE id IS NULL OR id = ''"
        ).fetchall()
        for row in rows:
            connection.execute(
                "UPDATE small_scene_materials SET id = ? WHERE small_scene_id = ? AND material_id = ?",
                (str(uuid4()), row["small_scene_id"], row["material_id"]),
            )

    def _run_migration(
        self, connection, version: str, description: str, migration_func
    ) -> None:
        """Run a versioned migration.

        迁移函数必须幂等。每次 initialize 都会执行迁移函数（幂等检查），
        以便修复手动破坏或历史遗留的数据不一致；版本记录只插入一次，
        用于追踪迁移历史。这保证了：
        - 新数据库：所有迁移执行并记录
        - 已有数据库：迁移函数仍执行（幂等），版本不重复插入
        - 手动破坏后的修复：迁移函数检测并修复不一致
        """
        migration_func(connection)
        already = connection.execute(
            "SELECT version FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if not already:
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "INSERT INTO schema_migrations(version, description, applied_at) VALUES (?, ?, ?)",
                (version, description, now),
            )

    def _migrate_add_revision_columns(self, connection) -> None:
        """Add revision INTEGER NOT NULL DEFAULT 1 to core editing tables.

        Idempotent: uses PRAGMA table_info to check column existence before
        adding. Existing rows get revision=1 automatically via DEFAULT.
        """
        revision_tables = [
            "projects",
            "chapters",
            "large_scenes",
            "small_scenes",
            "shot_pages",
            "materials",
            "material_pages",
            "characters",
            "character_variants",
        ]
        for table in revision_tables:
            exists = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not exists:
                continue
            cols = [row["name"] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]
            if "revision" not in cols:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")

    def _migrate_projects_extend(self, connection) -> None:
        """v0.5.1: 扩展 projects 表，添加 description/cover_path/archived_at/deleted_at 字段，
        并去掉 name 的 UNIQUE 约束以支持同名项目。

        幂等：通过 PRAGMA 检查列是否存在。UNIQUE 约束去除通过重建表实现。
        重建表时保留原 revision 字段（v0.5.0 已添加）。
        """
        exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='projects'",
        ).fetchone()
        if not exists:
            return

        cols = [row["name"] for row in connection.execute("PRAGMA table_info(projects)").fetchall()]
        needed = ["description", "cover_path", "archived_at", "deleted_at"]
        missing = [c for c in needed if c not in cols]

        # 检查 name 列是否仍有 UNIQUE 约束（通过查看 CREATE TABLE SQL）
        create_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='projects'",
        ).fetchone()["sql"]
        has_unique = "UNIQUE" in create_sql.upper()

        if missing or has_unique:
            # 重建表：去掉 UNIQUE 约束，添加缺失字段
            connection.execute("ALTER TABLE projects RENAME TO projects_old_v051")
            connection.execute(
                """
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    cover_path TEXT,
                    archived_at TEXT,
                    deleted_at TEXT,
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # 确定 SELECT 列：旧表可能没有 revision/description 等列
            old_cols = [row["name"] for row in connection.execute("PRAGMA table_info(projects_old_v051)").fetchall()]
            select_parts = ["id", "name"]
            for col in ["description", "status", "cover_path", "archived_at", "deleted_at", "revision", "created_at", "updated_at"]:
                if col in old_cols:
                    select_parts.append(col)
                else:
                    # 旧表没有该列，用默认值
                    if col == "description":
                        select_parts.append("'' AS description")
                    elif col == "status":
                        select_parts.append("'draft' AS status")
                    elif col == "revision":
                        select_parts.append("1 AS revision")
                    else:
                        select_parts.append("NULL AS " + col)
            select_clause = ", ".join(select_parts)
            connection.execute(
                f"INSERT INTO projects(id, name, description, status, cover_path, archived_at, deleted_at, revision, created_at, updated_at) "
                f"SELECT {select_clause} FROM projects_old_v051"
            )
            connection.execute("DROP TABLE projects_old_v051")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status, updated_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_deleted ON projects(deleted_at)"
            )
        else:
            # 表已经是新结构，确保索引存在（全新数据库或已迁移数据库）
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status, updated_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_projects_deleted ON projects(deleted_at)"
            )

    def _migrate_materials_extend(self, connection) -> None:
        """v0.5.2: 扩展 materials 和 material_pages 表。

        materials: 添加 archived_at/deleted_at/source_material_id 字段，
                   去掉 UNIQUE(material_type, name) 约束以支持同名素材（复制场景）。
        material_pages: 添加 preview_original_path/preview_thumbnail_path/source_page_id 字段。
        新增 material_versions 表（版本历史）。

        幂等：通过 PRAGMA 检查列是否存在。UNIQUE 约束去除通过重建表实现。
        """
        # ── materials 表 ──
        mat_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='materials'",
        ).fetchone()
        if mat_exists:
            cols = [row["name"] for row in connection.execute("PRAGMA table_info(materials)").fetchall()]
            needed = ["archived_at", "deleted_at", "source_material_id"]
            missing = [c for c in needed if c not in cols]
            create_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='materials'",
            ).fetchone()["sql"]
            # 检测 UNIQUE(material_type, name) 约束
            has_unique = "UNIQUE" in create_sql.upper() and "MATERIAL_TYPE" in create_sql.upper()

            if missing or has_unique:
                connection.execute("ALTER TABLE materials RENAME TO materials_old_v052")
                connection.execute(
                    """
                    CREATE TABLE materials (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL COLLATE NOCASE,
                        material_type TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        content TEXT NOT NULL,
                        prompt_text TEXT NOT NULL DEFAULT '',
                        negative_prompt TEXT NOT NULL DEFAULT '',
                        validation_status TEXT NOT NULL DEFAULT 'unverified',
                        notes TEXT NOT NULL DEFAULT '',
                        preview_original_path TEXT,
                        preview_thumbnail_path TEXT,
                        archived_at TEXT,
                        deleted_at TEXT,
                        source_material_id TEXT,
                        revision INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        CHECK (
                            material_type IN (
                                'composition', 'expression', 'scene',
                                'lighting', 'prompt', 'composite_template'
                            )
                        ),
                        CHECK (validation_status IN ('unverified', 'verified'))
                    )
                    """
                )
                old_cols = [row["name"] for row in connection.execute("PRAGMA table_info(materials_old_v052)").fetchall()]
                select_parts = ["id", "name", "material_type"]
                for col in ["description", "content", "prompt_text", "negative_prompt",
                            "validation_status", "notes", "preview_original_path",
                            "preview_thumbnail_path", "archived_at", "deleted_at",
                            "source_material_id", "revision", "created_at", "updated_at"]:
                    if col in old_cols:
                        select_parts.append(col)
                    elif col == "description":
                        select_parts.append("'' AS description")
                    elif col == "content":
                        select_parts.append("'' AS content")
                    elif col == "prompt_text":
                        select_parts.append("'' AS prompt_text")
                    elif col == "negative_prompt":
                        select_parts.append("'' AS negative_prompt")
                    elif col == "validation_status":
                        select_parts.append("'unverified' AS validation_status")
                    elif col == "notes":
                        select_parts.append("'' AS notes")
                    elif col == "revision":
                        select_parts.append("1 AS revision")
                    else:
                        select_parts.append("NULL AS " + col)
                select_clause = ", ".join(select_parts)
                connection.execute(
                    f"INSERT INTO materials(id, name, material_type, description, content, "
                    f"prompt_text, negative_prompt, validation_status, notes, "
                    f"preview_original_path, preview_thumbnail_path, archived_at, deleted_at, "
                    f"source_material_id, revision, created_at, updated_at) "
                    f"SELECT {select_clause} FROM materials_old_v052"
                )
                connection.execute("DROP TABLE materials_old_v052")
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_type_updated "
                    "ON materials(material_type, updated_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_status_updated "
                    "ON materials(validation_status, updated_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_deleted ON materials(deleted_at)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_archived ON materials(archived_at)"
                )
            else:
                # 表已经是新结构，确保索引存在（全新数据库或已迁移数据库）
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_type_updated "
                    "ON materials(material_type, updated_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_status_updated "
                    "ON materials(validation_status, updated_at DESC)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_deleted ON materials(deleted_at)"
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_materials_archived ON materials(archived_at)"
                )

        # ── material_pages 表：添加预览图和来源字段 ──
        mp_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='material_pages'",
        ).fetchone()
        if mp_exists:
            mp_cols = [row["name"] for row in connection.execute("PRAGMA table_info(material_pages)").fetchall()]
            for col in ["preview_original_path", "preview_thumbnail_path", "source_page_id"]:
                if col not in mp_cols:
                    connection.execute(
                        f"ALTER TABLE material_pages ADD COLUMN {col} TEXT"
                    )

        # ── material_versions 表（版本历史）──
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS material_versions (
                id TEXT PRIMARY KEY,
                material_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                snapshot TEXT NOT NULL,
                label TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (material_id)
                    REFERENCES materials(id) ON DELETE CASCADE,
                UNIQUE (material_id, version_number)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_material_versions_material "
            "ON material_versions(material_id, version_number DESC)"
        )

    def _migrate_characters_extend(self, connection) -> None:
        """v0.5.3: 扩展人物库相关表。

        - characters: 添加 description/cover_path/archived_at/deleted_at/source/
          source_identifier/external_url 字段，去除 UNIQUE(name) 约束（支持同名/复制），
          name 列添加 COLLATE NOCASE。
        - character_variants: 添加 description/default_prompt/default_lora_name/
          default_lora_weight/default_model_override/preview_original_path/
          preview_thumbnail_path/archived_at/source_variant_id 字段。
        - specs: 添加 description/is_required/default_value 字段。
        - character_spec_values: 添加 preview_original_path/preview_thumbnail_path 字段。
        - 新增 character_tags 表。

        幂等：通过 PRAGMA 检查列是否存在；UNIQUE 约束去除通过重建表实现。
        """
        # ── characters 表 ──
        char_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='characters'",
        ).fetchone()
        if char_exists:
            cols = [row["name"] for row in connection.execute("PRAGMA table_info(characters)").fetchall()]
            needed = [
                "description", "cover_path", "archived_at", "deleted_at",
                "source", "source_identifier", "external_url",
            ]
            missing = [c for c in needed if c not in cols]
            create_sql = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='characters'",
            ).fetchone()["sql"]
            has_unique = "UNIQUE" in create_sql.upper() and "NAME" in create_sql.upper()
            # 旧表 name 列没有 COLLATE NOCASE 时也需要重建
            has_collate = "COLLATE NOCASE" in create_sql.upper()

            if missing or has_unique or not has_collate:
                connection.execute("ALTER TABLE characters RENAME TO characters_old_v053")
                connection.execute(
                    """
                    CREATE TABLE characters (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL COLLATE NOCASE,
                        description TEXT NOT NULL DEFAULT '',
                        cover_path TEXT,
                        archived_at TEXT,
                        deleted_at TEXT,
                        source TEXT NOT NULL DEFAULT '',
                        source_identifier TEXT,
                        external_url TEXT,
                        sort_order INTEGER NOT NULL,
                        revision INTEGER NOT NULL DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                old_cols = [row["name"] for row in connection.execute("PRAGMA table_info(characters_old_v053)").fetchall()]
                select_parts = ["id", "name"]
                for col in [
                    "description", "cover_path", "archived_at", "deleted_at",
                    "source", "source_identifier", "external_url",
                    "sort_order", "revision", "created_at", "updated_at",
                ]:
                    if col in old_cols:
                        select_parts.append(col)
                    elif col == "description":
                        select_parts.append("'' AS description")
                    elif col == "source":
                        select_parts.append("'' AS source")
                    elif col == "revision":
                        select_parts.append("1 AS revision")
                    else:
                        select_parts.append(f"NULL AS {col}")
                select_clause = ", ".join(select_parts)
                connection.execute(
                    f"INSERT INTO characters(id, name, description, cover_path, archived_at, "
                    f"deleted_at, source, source_identifier, external_url, sort_order, "
                    f"revision, created_at, updated_at) "
                    f"SELECT {select_clause} FROM characters_old_v053"
                )
                connection.execute("DROP TABLE characters_old_v053")

            # Ensure indexes exist (idempotent). Handles both rebuilt and pre-existing tables.
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_characters_sort ON characters(sort_order)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_characters_deleted ON characters(deleted_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_characters_archived ON characters(archived_at)"
            )

        # ── character_variants 表：添加新字段 ──
        cv_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='character_variants'",
        ).fetchone()
        if cv_exists:
            cv_cols = [row["name"] for row in connection.execute("PRAGMA table_info(character_variants)").fetchall()]
            cv_additions = {
                "description": "TEXT NOT NULL DEFAULT ''",
                "default_prompt": "TEXT NOT NULL DEFAULT ''",
                "default_lora_name": "TEXT NOT NULL DEFAULT ''",
                "default_lora_weight": "REAL",
                "default_model_override": "TEXT NOT NULL DEFAULT ''",
                "preview_original_path": "TEXT",
                "preview_thumbnail_path": "TEXT",
                "archived_at": "TEXT",
                "source_variant_id": "TEXT",
            }
            for col, col_type in cv_additions.items():
                if col not in cv_cols:
                    connection.execute(
                        f"ALTER TABLE character_variants ADD COLUMN {col} {col_type}"
                    )

        # ── specs 表：添加 description/is_required/default_value ──
        specs_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='specs'",
        ).fetchone()
        if specs_exists:
            specs_cols = [row["name"] for row in connection.execute("PRAGMA table_info(specs)").fetchall()]
            specs_additions = {
                "description": "TEXT NOT NULL DEFAULT ''",
                "is_required": "INTEGER NOT NULL DEFAULT 0",
                "default_value": "TEXT NOT NULL DEFAULT ''",
            }
            for col, col_type in specs_additions.items():
                if col not in specs_cols:
                    connection.execute(
                        f"ALTER TABLE specs ADD COLUMN {col} {col_type}"
                    )

        # ── character_spec_values 表：添加预览图字段 ──
        csv_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='character_spec_values'",
        ).fetchone()
        if csv_exists:
            csv_cols = [row["name"] for row in connection.execute("PRAGMA table_info(character_spec_values)").fetchall()]
            for col in ["preview_original_path", "preview_thumbnail_path"]:
                if col not in csv_cols:
                    connection.execute(
                        f"ALTER TABLE character_spec_values ADD COLUMN {col} TEXT"
                    )

        # ── character_tags 表（新表）──
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS character_tags (
                id TEXT PRIMARY KEY,
                character_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (character_id)
                    REFERENCES characters(id) ON DELETE CASCADE,
                UNIQUE (character_id, tag)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_character_tags_character ON character_tags(character_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_character_tags_tag ON character_tags(tag)"
        )

        # ── shot_page_characters 表（场景页人物引用，新表）──
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS shot_page_characters (
                shot_page_id TEXT NOT NULL,
                character_id TEXT NOT NULL,
                variant_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (shot_page_id),
                FOREIGN KEY (shot_page_id)
                    REFERENCES shot_pages(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id)
                    REFERENCES characters(id) ON DELETE CASCADE,
                FOREIGN KEY (variant_id)
                    REFERENCES character_variants(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_shot_page_characters_character "
            "ON shot_page_characters(character_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_shot_page_characters_variant "
            "ON shot_page_characters(variant_id)"
        )

    def _migrate_branches_extend(self, connection) -> None:
        """v0.5.4: 扩展 branches 表（分支条件字段）并新增 3 张表。

        - branches: 添加 condition_type/condition_value/return_point 字段
        - branch_overrides: 分支覆盖数据（人物/素材/参数）
        - story_snapshots: 剧本结构快照
        - operation_history: 操作历史（撤销/重做基础）

        幂等：通过 PRAGMA 检查列是否存在；CREATE TABLE IF NOT EXISTS。
        """
        # ── branches 表：添加条件字段 ──
        branches_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='branches'",
        ).fetchone()
        if branches_exists:
            cols = [row["name"] for row in connection.execute("PRAGMA table_info(branches)").fetchall()]
            additions = {
                "condition_type": "TEXT NOT NULL DEFAULT ''",
                "condition_value": "TEXT NOT NULL DEFAULT ''",
                "return_point": "TEXT",
            }
            for col, col_type in additions.items():
                if col not in cols:
                    connection.execute(
                        f"ALTER TABLE branches ADD COLUMN {col} {col_type}"
                    )

        # ── branch_overrides 表 ──
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS branch_overrides (
                id TEXT PRIMARY KEY,
                branch_id TEXT NOT NULL,
                override_type TEXT NOT NULL,
                target_id TEXT,
                character_id TEXT,
                variant_id TEXT,
                material_id TEXT,
                material_page_id TEXT,
                param_key TEXT,
                param_value TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (branch_id)
                    REFERENCES branches(id) ON DELETE CASCADE,
                UNIQUE (branch_id, override_type, target_id, param_key)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_branch_overrides_branch "
            "ON branch_overrides(branch_id, override_type)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_branch_overrides_target "
            "ON branch_overrides(target_id)"
        )

        # ── story_snapshots 表 ──
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS story_snapshots (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                snapshot_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id)
                    REFERENCES projects(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_story_snapshots_project "
            "ON story_snapshots(project_id, created_at DESC)"
        )

        # ── operation_history 表 ──
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS operation_history (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT,
                before_state TEXT,
                after_state TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id)
                    REFERENCES projects(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_operation_history_project "
            "ON operation_history(project_id, created_at DESC)"
        )

    def _migrate_comfyui_connect(self, connection) -> None:
        """v0.5.5: 新增 ComfyUI 连接层相关表。

        - app_settings: 应用级键值配置（ComfyUI 地址/超时/WebSocket 等）
        - comfyui_node_definitions: 缓存 /object_info 节点定义
        - comfyui_resource_cache: 缓存模型/LoRA/VAE 等资源列表

        幂等：CREATE TABLE IF NOT EXISTS。
        """
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # 插入默认 ComfyUI 连接配置（仅一次）
        existing = connection.execute(
            "SELECT key FROM app_settings WHERE key = 'comfyui.base_url'"
        ).fetchone()
        if not existing:
            now = datetime.now(timezone.utc).isoformat()
            defaults = [
                ("comfyui.base_url", "http://127.0.0.1:8188"),
                ("comfyui.timeout_seconds", "10"),
                ("comfyui.websocket_url", ""),
            ]
            for key, value in defaults:
                connection.execute(
                    "INSERT OR IGNORE INTO app_settings(key, value, updated_at) VALUES (?, ?, ?)",
                    (key, value, now),
                )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS comfyui_node_definitions (
                node_class TEXT PRIMARY KEY,
                python_module TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                definition_json TEXT NOT NULL,
                is_custom_node INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_comfyui_node_definitions_category "
            "ON comfyui_node_definitions(category)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_comfyui_node_definitions_custom "
            "ON comfyui_node_definitions(is_custom_node)"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS comfyui_resource_cache (
                resource_type TEXT NOT NULL,
                resource_name TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (resource_type, resource_name)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS comfyui_sync_meta (
                sync_key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    def _migrate_workflows(self, connection) -> None:
        """v0.5.6: 新增工作流库相关表。

        - workflows: 工作流主表（全局模板或项目副本）
        - workflow_versions: 不可变版本（发布后不可修改）
        - workflow_drafts: 可编辑草稿（每个工作流最多一个）
        - semantic_slots: 语义插槽绑定（节点输入→业务语义）
        - project_default_workflows: 项目默认工作流关联

        幂等：CREATE TABLE IF NOT EXISTS。
        """
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                source_type TEXT NOT NULL DEFAULT 'manual',
                source_identifier TEXT NOT NULL DEFAULT '',
                project_id TEXT,
                source_workflow_id TEXT,
                current_version_id TEXT,
                draft_id TEXT,
                is_archived INTEGER NOT NULL DEFAULT 0,
                archived_at TEXT,
                is_global_default INTEGER NOT NULL DEFAULT 0,
                node_count INTEGER NOT NULL DEFAULT 0,
                revision INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflows_project "
            "ON workflows(project_id, is_archived)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflows_archived "
            "ON workflows(is_archived, updated_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflows_global_default "
            "ON workflows(is_global_default) WHERE is_global_default = 1"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_versions (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                label TEXT NOT NULL DEFAULT '',
                normalized_graph TEXT NOT NULL,
                raw_ui_json TEXT,
                raw_api_json TEXT,
                node_count INTEGER NOT NULL DEFAULT 0,
                checksum TEXT NOT NULL DEFAULT '',
                is_validated INTEGER NOT NULL DEFAULT 0,
                validation_result TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id)
                    REFERENCES workflows(id) ON DELETE CASCADE,
                UNIQUE (workflow_id, version_number)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_workflow_versions_workflow "
            "ON workflow_versions(workflow_id, version_number DESC)"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workflow_drafts (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL UNIQUE,
                normalized_graph TEXT NOT NULL,
                raw_ui_json TEXT,
                raw_api_json TEXT,
                node_count INTEGER NOT NULL DEFAULT 0,
                semantic_slots_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id)
                    REFERENCES workflows(id) ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_slots (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                slot_name TEXT NOT NULL,
                slot_type TEXT NOT NULL,
                node_id TEXT NOT NULL,
                input_name TEXT NOT NULL,
                transform_rule TEXT NOT NULL DEFAULT '',
                default_value TEXT,
                is_required INTEGER NOT NULL DEFAULT 0,
                conflict_strategy TEXT NOT NULL DEFAULT 'overwrite',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id)
                    REFERENCES workflows(id) ON DELETE CASCADE,
                UNIQUE (workflow_id, slot_name)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_slots_workflow "
            "ON semantic_slots(workflow_id, slot_type)"
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_default_workflows (
                project_id TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                set_at TEXT NOT NULL,
                PRIMARY KEY (project_id),
                FOREIGN KEY (workflow_id)
                    REFERENCES workflows(id) ON DELETE CASCADE
            )
            """
        )

    def _migrate_workflow_draft_extend(self, connection) -> None:
        """v0.5.7: 扩展 workflow_drafts 表，支持节点编辑器。

        - last_node_id: 草稿中已分配的最大节点 ID（用于新增节点分配 ID）
        - last_link_id: 草稿中已分配的最大连线 ID
        - validation_state: 上次校验结果（JSON 字符串，含 errors/warnings/validated_at）

        幂等：使用 PRAGMA table_info 检查列是否存在。
        """
        cols = [row["name"] for row in connection.execute("PRAGMA table_info(workflow_drafts)").fetchall()]
        if "last_node_id" not in cols:
            connection.execute(
                "ALTER TABLE workflow_drafts ADD COLUMN last_node_id INTEGER NOT NULL DEFAULT 0"
            )
        if "last_link_id" not in cols:
            connection.execute(
                "ALTER TABLE workflow_drafts ADD COLUMN last_link_id INTEGER NOT NULL DEFAULT 0"
            )
        if "validation_state" not in cols:
            connection.execute(
                "ALTER TABLE workflow_drafts ADD COLUMN validation_state TEXT"
            )

    def _migrate_workflow_draft_layout_extend(self, connection) -> None:
        """v0.5.8: 扩展 workflow_drafts 表，支持规整布局。

        - layout_state: 布局状态（JSON 字符串，含 user_order_constraints/groups/layout）

        幂等：使用 PRAGMA table_info 检查列是否存在。
        """
        cols = [row["name"] for row in connection.execute("PRAGMA table_info(workflow_drafts)").fetchall()]
        if "layout_state" not in cols:
            connection.execute(
                "ALTER TABLE workflow_drafts ADD COLUMN layout_state TEXT"
            )

    def activate(self, environment: DatabaseEnvironment) -> None:
        target_environment = self._validate_environment(environment)
        with self._lock:
            if self._locked_environment and target_environment != self._locked_environment:
                raise DatabaseSafetyError(
                    f"This process is locked to the {self._locked_environment} database."
                )
            self.initialize(target_environment)
            self._active_environment = target_environment

    def record_event(
        self,
        event_type: str,
        event_value: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> int:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                INSERT INTO database_events(event_type, event_value, created_at)
                VALUES (?, ?, ?)
                """,
                (event_type, event_value, datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def event_count(self, environment: DatabaseEnvironment) -> int:
        with self.connection(environment) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM database_events"
            ).fetchone()
            return int(row["count"])

    def list_projects(
        self,
        query: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        include_deleted: bool = False,
        sort: str = "updated",
        limit: int = 50,
        offset: int = 0,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """List projects with search, filter, sort and pagination.

        Returns a dict: {"items": [...], "total": N, "limit": L, "offset": O, "has_more": bool}.
        Each item contains: id, name, description, status, cover_path, archived_at,
        deleted_at, revision, created_at, updated_at.
        """
        target_environment = environment or self._active_environment
        conditions: list[str] = []
        params: list[object] = []

        if not include_archived:
            conditions.append("archived_at IS NULL")
        if not include_deleted:
            conditions.append("deleted_at IS NULL")
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if query:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sort_mapping = {
            "updated": "updated_at DESC, name ASC",
            "name": "name ASC",
            "created": "created_at DESC",
        }
        order_clause = sort_mapping.get(sort, sort_mapping["updated"])

        select_cols = (
            "id, name, description, status, cover_path, archived_at, "
            "deleted_at, revision, created_at, updated_at"
        )

        with self.connection(target_environment) as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) AS total FROM projects {where_clause}",
                params,
            ).fetchone()
            total = int(count_row["total"])

            rows = connection.execute(
                f"SELECT {select_cols} FROM projects {where_clause} "
                f"ORDER BY {order_clause} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()

        items = [dict(row) for row in rows]
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    def get_project(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, name, description, status, cover_path, archived_at,
                       deleted_at, revision, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_project(
        self,
        name: str,
        description: str = "",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("项目名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("项目名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        project = {
            "id": str(uuid4()),
            "name": clean_name,
            "description": description,
            "status": "draft",
            "cover_path": None,
            "archived_at": None,
            "deleted_at": None,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock, self.connection(target_environment) as connection:
            connection.execute(
                """
                INSERT INTO projects(
                    id, name, description, status, cover_path, archived_at,
                    deleted_at, revision, created_at, updated_at
                )
                VALUES(
                    :id, :name, :description, :status, :cover_path, :archived_at,
                    :deleted_at, :revision, :created_at, :updated_at
                )
                """,
                project,
            )
        return project

    def update_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Update a project's name and/or description.

        Only provided fields are updated. Updates updated_at and increments revision.
        Returns the updated project dict, or None if the project does not exist.
        Runs in a single transaction.
        """
        target_environment = environment or self._active_environment
        if name is None and description is None:
            raise ValueError("至少需要提供一个更新字段。")
        clean_name: str | None = None
        if name is not None:
            clean_name = " ".join(name.split())
            if not clean_name:
                raise ValueError("项目名称不能为空。")
            if len(clean_name) > 80:
                raise ValueError("项目名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if existing is None:
                return None
            sets: list[str] = []
            params: list[object] = []
            if clean_name is not None:
                sets.append("name = ?")
                params.append(clean_name)
            if description is not None:
                sets.append("description = ?")
                params.append(description)
            sets.append("updated_at = ?")
            params.append(now)
            sets.append("revision = revision + 1")
            params.append(project_id)
            connection.execute(
                f"UPDATE projects SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            row = connection.execute(
                """
                SELECT id, name, description, status, cover_path, archived_at,
                       deleted_at, revision, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def archive_project(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Archive a project: set archived_at and status='archived'.

        Returns the updated project dict, or None if the project does not exist.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE projects SET archived_at = ?, status = ?, updated_at = ? WHERE id = ?",
                (now, "archived", now, project_id),
            )
            row = connection.execute(
                """
                SELECT id, name, description, status, cover_path, archived_at,
                       deleted_at, revision, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def restore_project(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Restore an archived or soft-deleted project.

        Clears both archived_at and deleted_at, sets status='draft'.
        Returns the updated project dict, or None if the project does not exist.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE projects SET archived_at = NULL, deleted_at = NULL, status = ?, updated_at = ? WHERE id = ?",
                ("draft", now, project_id),
            )
            row = connection.execute(
                """
                SELECT id, name, description, status, cover_path, archived_at,
                       deleted_at, revision, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def soft_delete_project(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Soft-delete a project: set deleted_at to current UTC time.

        Does not actually remove data. Returns the updated project dict,
        or None if the project does not exist.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE projects SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, project_id),
            )
            row = connection.execute(
                """
                SELECT id, name, description, status, cover_path, archived_at,
                       deleted_at, revision, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def permanent_delete_project(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> bool:
        """Permanently delete a project record.

        Cascade-deletes chapters etc. via FK ON DELETE CASCADE.
        Returns True if a row was deleted, False otherwise.
        """
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                "DELETE FROM projects WHERE id = ?",
                (project_id,),
            )
            return cursor.rowcount > 0

    def get_project_stats(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Gather statistics for a project in a single query.

        Returns a dict with: chapter_count, large_scene_count, small_scene_count,
        shot_page_count, material_count, character_count.
        Returns None if the project does not exist.
        Only counts non-deleted data (records that exist in the database).
        """
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            project = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project is None:
                return None
            row = connection.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM chapters c
                     WHERE c.project_id = p.id) AS chapter_count,
                    (SELECT COUNT(*) FROM large_scenes ls
                     JOIN chapters c ON c.id = ls.chapter_id
                     WHERE c.project_id = p.id) AS large_scene_count,
                    (SELECT COUNT(*) FROM small_scenes ss
                     JOIN large_scenes ls ON ls.id = ss.large_scene_id
                     JOIN chapters c ON c.id = ls.chapter_id
                     WHERE c.project_id = p.id) AS small_scene_count,
                    (SELECT COUNT(*) FROM shot_pages sp
                     JOIN small_scenes ss ON ss.id = sp.small_scene_id
                     JOIN large_scenes ls ON ls.id = ss.large_scene_id
                     JOIN chapters c ON c.id = ls.chapter_id
                     WHERE c.project_id = p.id) AS shot_page_count,
                    (SELECT COUNT(DISTINCT ssm.material_id)
                     FROM small_scene_materials ssm
                     JOIN small_scenes ss ON ss.id = ssm.small_scene_id
                     JOIN large_scenes ls ON ls.id = ss.large_scene_id
                     JOIN chapters c ON c.id = ls.chapter_id
                     WHERE c.project_id = p.id) AS material_count,
                    (SELECT COUNT(*) FROM project_characters pc
                     WHERE pc.project_id = p.id) AS character_count
                FROM projects p
                WHERE p.id = ?
                """,
                (project_id,),
            ).fetchone()
        return {
            "chapter_count": int(row["chapter_count"]),
            "large_scene_count": int(row["large_scene_count"]),
            "small_scene_count": int(row["small_scene_count"]),
            "shot_page_count": int(row["shot_page_count"]),
            "material_count": int(row["material_count"]),
            "character_count": int(row["character_count"]),
        }

    def copy_project(
        self,
        project_id: str,
        new_name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Copy a project and its story tree structure.

        Copies: project (name=new_name, description, status='draft'), chapters,
        large_scenes, small_scenes, shot_pages, branches, material associations
        (small_scene_materials, shot_page_materials), and page mappings
        (small_scene_page_mappings).

        Does NOT copy: images, task history, materials themselves, material_pages,
        or character associations.

        All new records get new UUIDs. sort_order is preserved. Runs in a single
        transaction. Returns the new project dict.
        """
        target_environment = environment or self._active_environment
        clean_name = " ".join(new_name.split())
        if not clean_name:
            raise ValueError("项目名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("项目名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        new_project_id = str(uuid4())

        with self._lock, self.connection(target_environment) as connection:
            source = connection.execute(
                """
                SELECT id, name, description FROM projects WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
            if source is None:
                raise ValueError("项目不存在。")

            connection.execute(
                """
                INSERT INTO projects(
                    id, name, description, status, cover_path, archived_at,
                    deleted_at, revision, created_at, updated_at
                )
                VALUES(?, ?, ?, 'draft', NULL, NULL, NULL, 1, ?, ?)
                """,
                (new_project_id, clean_name, source["description"], now, now),
            )

            # ID mapping tables
            chapter_map: dict[str, str] = {}
            large_scene_map: dict[str, str] = {}
            small_scene_map: dict[str, str] = {}
            branch_map: dict[str, str] = {}
            shot_page_map: dict[str, str] = {}

            # Copy chapters
            chapters = connection.execute(
                """
                SELECT id, name, sort_order, revision
                FROM chapters
                WHERE project_id = ?
                ORDER BY sort_order ASC
                """,
                (project_id,),
            ).fetchall()
            for ch in chapters:
                new_ch_id = str(uuid4())
                chapter_map[ch["id"]] = new_ch_id
                connection.execute(
                    """
                    INSERT INTO chapters(
                        id, project_id, name, sort_order, revision, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (new_ch_id, new_project_id, ch["name"], ch["sort_order"],
                     ch["revision"], now, now),
                )

            # Copy large_scenes
            if chapter_map:
                ch_placeholders = ",".join("?" * len(chapter_map))
                large_scenes = connection.execute(
                    f"""
                    SELECT id, chapter_id, name, scene_type, sort_order, revision
                    FROM large_scenes
                    WHERE chapter_id IN ({ch_placeholders})
                    ORDER BY sort_order ASC
                    """,
                    list(chapter_map.keys()),
                ).fetchall()
                for ls in large_scenes:
                    new_ls_id = str(uuid4())
                    large_scene_map[ls["id"]] = new_ls_id
                    connection.execute(
                        """
                        INSERT INTO large_scenes(
                            id, chapter_id, name, scene_type, sort_order,
                            revision, created_at, updated_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (new_ls_id, chapter_map[ls["chapter_id"]], ls["name"],
                         ls["scene_type"], ls["sort_order"], ls["revision"], now, now),
                    )

            # Copy small_scenes
            if large_scene_map:
                ls_placeholders = ",".join("?" * len(large_scene_map))
                small_scenes = connection.execute(
                    f"""
                    SELECT id, large_scene_id, name, scene_type, description,
                           sort_order, revision
                    FROM small_scenes
                    WHERE large_scene_id IN ({ls_placeholders})
                    ORDER BY sort_order ASC
                    """,
                    list(large_scene_map.keys()),
                ).fetchall()
                for ss in small_scenes:
                    new_ss_id = str(uuid4())
                    small_scene_map[ss["id"]] = new_ss_id
                    connection.execute(
                        """
                        INSERT INTO small_scenes(
                            id, large_scene_id, name, scene_type, description,
                            sort_order, revision, created_at, updated_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (new_ss_id, large_scene_map[ss["large_scene_id"]],
                         ss["name"], ss["scene_type"], ss["description"],
                         ss["sort_order"], ss["revision"], now, now),
                    )

            # Copy branches (parent_type in ('large_scene', 'small_scene'))
            parent_ids = list(large_scene_map.keys()) + list(small_scene_map.keys())
            if parent_ids:
                parent_placeholders = ",".join("?" * len(parent_ids))
                branches = connection.execute(
                    f"""
                    SELECT id, parent_type, parent_id, name, description,
                           is_enabled, sort_order
                    FROM branches
                    WHERE parent_type IN ('large_scene', 'small_scene')
                      AND parent_id IN ({parent_placeholders})
                    ORDER BY sort_order ASC
                    """,
                    parent_ids,
                ).fetchall()
                for br in branches:
                    new_br_id = str(uuid4())
                    branch_map[br["id"]] = new_br_id
                    if br["parent_type"] == "large_scene":
                        new_parent_id = large_scene_map[br["parent_id"]]
                    else:
                        new_parent_id = small_scene_map[br["parent_id"]]
                    connection.execute(
                        """
                        INSERT INTO branches(
                            id, parent_type, parent_id, name, description,
                            is_enabled, sort_order, created_at, updated_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (new_br_id, br["parent_type"], new_parent_id, br["name"],
                         br["description"], br["is_enabled"], br["sort_order"],
                         now, now),
                    )

            # Copy shot_pages (both branch_id IS NULL and branch_id IS NOT NULL)
            if small_scene_map:
                ss_placeholders = ",".join("?" * len(small_scene_map))
                shot_pages = connection.execute(
                    f"""
                    SELECT id, small_scene_id, branch_id, title, description,
                           prompt_text, negative_prompt, sort_order, revision
                    FROM shot_pages
                    WHERE small_scene_id IN ({ss_placeholders})
                    ORDER BY sort_order ASC
                    """,
                    list(small_scene_map.keys()),
                ).fetchall()
                for sp in shot_pages:
                    new_sp_id = str(uuid4())
                    shot_page_map[sp["id"]] = new_sp_id
                    new_branch_id = (
                        branch_map[sp["branch_id"]]
                        if sp["branch_id"] is not None
                        else None
                    )
                    connection.execute(
                        """
                        INSERT INTO shot_pages(
                            id, small_scene_id, branch_id, title, description,
                            prompt_text, negative_prompt, sort_order, revision,
                            created_at, updated_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (new_sp_id, small_scene_map[sp["small_scene_id"]],
                         new_branch_id, sp["title"], sp["description"],
                         sp["prompt_text"], sp["negative_prompt"], sp["sort_order"],
                         sp["revision"], now, now),
                    )

            # Copy small_scene_materials (material associations)
            if small_scene_map:
                ss_placeholders = ",".join("?" * len(small_scene_map))
                ssm_rows = connection.execute(
                    f"""
                    SELECT small_scene_id, material_id, sort_order
                    FROM small_scene_materials
                    WHERE small_scene_id IN ({ss_placeholders})
                    """,
                    list(small_scene_map.keys()),
                ).fetchall()
                for ssm in ssm_rows:
                    connection.execute(
                        """
                        INSERT INTO small_scene_materials(
                            id, small_scene_id, material_id, sort_order, created_at
                        )
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (str(uuid4()), small_scene_map[ssm["small_scene_id"]],
                         ssm["material_id"], ssm["sort_order"], now),
                    )

            # Copy shot_page_materials (material associations)
            if shot_page_map:
                sp_placeholders = ",".join("?" * len(shot_page_map))
                spm_rows = connection.execute(
                    f"""
                    SELECT shot_page_id, material_id, sort_order
                    FROM shot_page_materials
                    WHERE shot_page_id IN ({sp_placeholders})
                    """,
                    list(shot_page_map.keys()),
                ).fetchall()
                for spm in spm_rows:
                    connection.execute(
                        """
                        INSERT INTO shot_page_materials(
                            shot_page_id, material_id, sort_order, created_at
                        )
                        VALUES(?, ?, ?, ?)
                        """,
                        (shot_page_map[spm["shot_page_id"]], spm["material_id"],
                         spm["sort_order"], now),
                    )

            # Copy small_scene_page_mappings (page mappings)
            if shot_page_map:
                sp_placeholders = ",".join("?" * len(shot_page_map))
                mapping_rows = connection.execute(
                    f"""
                    SELECT scene_page_id, material_page_id, material_type
                    FROM small_scene_page_mappings
                    WHERE scene_page_id IN ({sp_placeholders})
                    """,
                    list(shot_page_map.keys()),
                ).fetchall()
                for m in mapping_rows:
                    connection.execute(
                        """
                        INSERT INTO small_scene_page_mappings(
                            id, scene_page_id, material_page_id, material_type,
                            created_at, updated_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?)
                        """,
                        (str(uuid4()), shot_page_map[m["scene_page_id"]],
                         m["material_page_id"], m["material_type"], now, now),
                    )

            new_project = connection.execute(
                """
                SELECT id, name, description, status, cover_path, archived_at,
                       deleted_at, revision, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (new_project_id,),
            ).fetchone()
        return dict(new_project)

    def list_chapters(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """Return chapters for a project ordered by sort_order ascending."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, name, sort_order, created_at, updated_at
                FROM chapters
                WHERE project_id = ?
                ORDER BY sort_order ASC, created_at ASC
                """,
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_chapter(
        self,
        project_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Create a chapter in the given project.

        Validates name length, project existence, and per-project uniqueness.
        sort_order is assigned as max(existing) + 1, starting at 1.
        """
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("章节名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("章节名称不能超过 80 个字符。")
        if self.get_project(project_id, target_environment) is None:
            raise ValueError("项目不存在。")
        now = datetime.now(timezone.utc).isoformat()
        chapter = {
            "id": str(uuid4()),
            "project_id": project_id,
            "name": clean_name,
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._lock, self.connection(target_environment) as connection:
                row = connection.execute(
                    """
                    SELECT COALESCE(MAX(sort_order), 0) AS max_sort
                    FROM chapters
                    WHERE project_id = ?
                    """,
                    (project_id,),
                ).fetchone()
                next_sort = int(row["max_sort"]) + 1
                chapter["sort_order"] = next_sort
                connection.execute(
                    """
                    INSERT INTO chapters(
                        id, project_id, name, sort_order, created_at, updated_at
                    )
                    VALUES(:id, :project_id, :name, :sort_order, :created_at, :updated_at)
                    """,
                    chapter,
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("该项目下已经存在同名章节。") from error
        return chapter

    def get_chapter(
        self,
        chapter_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, project_id, name, sort_order, created_at, updated_at
                FROM chapters
                WHERE id = ?
                """,
                (chapter_id,),
            ).fetchone()
        return dict(row) if row else None

    def rename_chapter(
        self,
        chapter_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("章节名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("章节名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock, self.connection(target_environment) as connection:
                cursor = connection.execute(
                    """
                    UPDATE chapters
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean_name, now, chapter_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("章节不存在。")
        except sqlite3.IntegrityError as error:
            raise ValueError("该项目下已经存在同名章节。") from error
        chapter = self.get_chapter(chapter_id, target_environment)
        if chapter is None:
            raise ValueError("章节不存在。")
        return chapter

    def delete_chapter(
        self,
        chapter_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            chapter = connection.execute(
                """
                SELECT id, project_id, name, sort_order, created_at, updated_at
                FROM chapters
                WHERE id = ?
                """,
                (chapter_id,),
            ).fetchone()
            if chapter is None:
                raise ValueError("章节不存在。")
            connection.execute("DELETE FROM chapters WHERE id = ?", (chapter_id,))
        return dict(chapter)

    def list_large_scenes(
        self,
        chapter_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """Return a chapter's large scenes in their fixed linear order."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                FROM large_scenes
                WHERE chapter_id = ?
                ORDER BY sort_order ASC, created_at ASC
                """,
                (chapter_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_large_scene(
        self,
        chapter_id: str,
        name: str,
        scene_type: str = "content",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Create a large scene at the end of a chapter's ordered scene list."""
        target_environment = environment or self._active_environment
        if scene_type not in ("content", "transition"):
            raise ValueError("大场景类型必须是 content 或 transition。")
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("大场景名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("大场景名称不能超过 80 个字符。")
        if self.get_chapter(chapter_id, target_environment) is None:
            raise ValueError("章节不存在。")
        now = datetime.now(timezone.utc).isoformat()
        large_scene = {
            "id": str(uuid4()),
            "chapter_id": chapter_id,
            "name": clean_name,
            "scene_type": scene_type,
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._lock, self.connection(target_environment) as connection:
                row = connection.execute(
                    """
                    SELECT COALESCE(MAX(sort_order), 0) AS max_sort
                    FROM large_scenes
                    WHERE chapter_id = ?
                    """,
                    (chapter_id,),
                ).fetchone()
                large_scene["sort_order"] = int(row["max_sort"]) + 1
                connection.execute(
                    """
                    INSERT INTO large_scenes(
                        id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                    )
                    VALUES(
                        :id, :chapter_id, :name, :scene_type, :sort_order, :created_at, :updated_at
                    )
                    """,
                    large_scene,
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("该章节下已经存在同名大场景。") from error
        return large_scene

    def get_large_scene(
        self,
        large_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                FROM large_scenes
                WHERE id = ?
                """,
                (large_scene_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_large_scene(
        self,
        large_scene_id: str,
        *,
        name: str | None = None,
        scene_type: str | None = None,
        chapter_id: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Update name, scene_type, and/or chapter_id of a large scene.

        - At least one of name/scene_type/chapter_id must be provided.
        - When chapter_id changes, scene is moved to end of target chapter and
          both source and target chapters are renumbered within this transaction.
        - Same-project constraint and same-name conflict are enforced.
        """
        target_environment = environment or self._active_environment
        if name is None and scene_type is None and chapter_id is None:
            raise ValueError("至少需要提供一个更新字段。")
        if scene_type is not None and scene_type not in ("content", "transition"):
            raise ValueError("大场景类型必须是 content 或 transition。")
        clean_name = " ".join(name.split()) if name is not None else None
        if clean_name is not None:
            if not clean_name:
                raise ValueError("大场景名称不能为空。")
            if len(clean_name) > 80:
                raise ValueError("大场景名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock, self.connection(target_environment) as connection:
                existing = connection.execute(
                    """
                    SELECT id, chapter_id, name, scene_type, sort_order
                    FROM large_scenes WHERE id = ?
                    """,
                    (large_scene_id,),
                ).fetchone()
                if existing is None:
                    raise ValueError("大场景不存在。")
                source_chapter_id = existing["chapter_id"]
                target_chapter_id = chapter_id if chapter_id is not None else source_chapter_id

                # Validate target chapter existence and same-project constraint
                if chapter_id is not None:
                    src_ch = connection.execute(
                        "SELECT project_id FROM chapters WHERE id = ?",
                        (source_chapter_id,),
                    ).fetchone()
                    tgt_ch = connection.execute(
                        "SELECT project_id FROM chapters WHERE id = ?",
                        (target_chapter_id,),
                    ).fetchone()
                    if tgt_ch is None:
                        raise ValueError("目标章节不存在。")
                    if src_ch["project_id"] != tgt_ch["project_id"]:
                        raise ValueError("目标章节与原章节不属于同一项目。")

                # Validate name uniqueness in target chapter
                effective_name = clean_name if clean_name is not None else existing["name"]
                dup = connection.execute(
                    """
                    SELECT id FROM large_scenes
                    WHERE chapter_id = ? AND name = ? AND id != ?
                    """,
                    (target_chapter_id, effective_name, large_scene_id),
                ).fetchone()
                if dup is not None:
                    raise ValueError("目标章节下已经存在同名大场景。")

                # Update scalar fields
                sets = []
                params: list[object] = []
                if clean_name is not None:
                    sets.append("name = ?")
                    params.append(clean_name)
                if scene_type is not None:
                    sets.append("scene_type = ?")
                    params.append(scene_type)
                if chapter_id is not None and chapter_id != source_chapter_id:
                    # Append to end of target chapter
                    max_row = connection.execute(
                        "SELECT COALESCE(MAX(sort_order), 0) AS m FROM large_scenes WHERE chapter_id = ?",
                        (target_chapter_id,),
                    ).fetchone()
                    sets.append("chapter_id = ?")
                    params.append(target_chapter_id)
                    sets.append("sort_order = ?")
                    params.append(int(max_row["m"]) + 1)
                sets.append("updated_at = ?")
                params.append(now)
                params.append(large_scene_id)
                connection.execute(
                    f"UPDATE large_scenes SET {', '.join(sets)} WHERE id = ?",
                    params,
                )

                # Renumber affected chapters
                chapters_to_renumber = {source_chapter_id}
                if chapter_id is not None and chapter_id != source_chapter_id:
                    chapters_to_renumber.add(target_chapter_id)
                for ch_id in chapters_to_renumber:
                    rows = connection.execute(
                        "SELECT id FROM large_scenes WHERE chapter_id = ? ORDER BY sort_order ASC, created_at ASC",
                        (ch_id,),
                    ).fetchall()
                    for idx, r in enumerate(rows, start=1):
                        connection.execute(
                            "UPDATE large_scenes SET sort_order = ? WHERE id = ?",
                            (idx, r["id"]),
                        )
        except sqlite3.IntegrityError as error:
            raise ValueError("该章节下已经存在同名大场景。") from error
        result = self.get_large_scene(large_scene_id, target_environment)
        if result is None:
            raise ValueError("大场景不存在。")
        return result

    def rename_large_scene(
        self,
        large_scene_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Legacy rename-only method. Kept for backward compatibility with tests."""
        return self.update_large_scene(
            large_scene_id, name=name, environment=environment
        )

    def move_large_scene(
        self,
        large_scene_id: str,
        target_chapter_id: str,
        target_sort_order: int,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Move a large scene to a specific position in a chapter.

        - Validates same-project constraint and name conflict.
        - target_sort_order < 1 is treated as 1; > target length is appended to end.
        - Renumbers source and target chapters in the same transaction.
        - Returns dict with source/target chapter ids and their final items.
        """
        target_environment = environment or self._active_environment
        if target_sort_order < 1:
            target_sort_order = 1
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, chapter_id, name, scene_type, sort_order FROM large_scenes WHERE id = ?",
                (large_scene_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("大场景不存在。")
            source_chapter_id = existing["chapter_id"]

            src_ch = connection.execute(
                "SELECT project_id FROM chapters WHERE id = ?",
                (source_chapter_id,),
            ).fetchone()
            tgt_ch = connection.execute(
                "SELECT project_id FROM chapters WHERE id = ?",
                (target_chapter_id,),
            ).fetchone()
            if tgt_ch is None:
                raise ValueError("目标章节不存在。")
            if src_ch is None:
                raise ValueError("原章节不存在。")
            if src_ch["project_id"] != tgt_ch["project_id"]:
                raise ValueError("目标章节与原章节不属于同一项目。")

            # Name conflict check (excluding self)
            dup = connection.execute(
                "SELECT id FROM large_scenes WHERE chapter_id = ? AND name = ? AND id != ?",
                (target_chapter_id, existing["name"], large_scene_id),
            ).fetchone()
            if dup is not None:
                raise ValueError("目标章节下已经存在同名大场景。")

            # If cross-chapter, remove from source ordering first
            if source_chapter_id != target_chapter_id:
                connection.execute(
                    "UPDATE large_scenes SET chapter_id = ?, updated_at = ? WHERE id = ?",
                    (target_chapter_id, now, large_scene_id),
                )

            # Build target ordering
            target_rows = connection.execute(
                """
                SELECT id FROM large_scenes
                WHERE chapter_id = ? AND id != ?
                ORDER BY sort_order ASC, created_at ASC
                """,
                (target_chapter_id, large_scene_id),
            ).fetchall()
            target_ids = [r["id"] for r in target_rows]
            if target_sort_order > len(target_ids) + 1:
                target_sort_order = len(target_ids) + 1
            target_ids.insert(target_sort_order - 1, large_scene_id)
            for idx, sid in enumerate(target_ids, start=1):
                connection.execute(
                    "UPDATE large_scenes SET sort_order = ?, updated_at = ? WHERE id = ?",
                    (idx, now, sid),
                )

            # Renumber source chapter if cross-chapter
            if source_chapter_id != target_chapter_id:
                src_rows = connection.execute(
                    "SELECT id FROM large_scenes WHERE chapter_id = ? ORDER BY sort_order ASC, created_at ASC",
                    (source_chapter_id,),
                ).fetchall()
                for idx, r in enumerate(src_rows, start=1):
                    connection.execute(
                        "UPDATE large_scenes SET sort_order = ? WHERE id = ?",
                        (idx, r["id"]),
                    )

            # Fetch final state
            moved = connection.execute(
                """
                SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                FROM large_scenes WHERE id = ?
                """,
                (large_scene_id,),
            ).fetchone()
            source_items = [
                dict(r) for r in connection.execute(
                    """
                    SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                    FROM large_scenes WHERE chapter_id = ?
                    ORDER BY sort_order ASC, created_at ASC
                    """,
                    (source_chapter_id,),
                ).fetchall()
            ]
            target_items = [
                dict(r) for r in connection.execute(
                    """
                    SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                    FROM large_scenes WHERE chapter_id = ?
                    ORDER BY sort_order ASC, created_at ASC
                    """,
                    (target_chapter_id,),
                ).fetchall()
            ]
        return {
            "large_scene": dict(moved),
            "source_chapter_id": source_chapter_id,
            "target_chapter_id": target_chapter_id,
            "source_items": source_items,
            "target_items": target_items,
        }

    def delete_large_scene(
        self,
        large_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            large_scene = connection.execute(
                """
                SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                FROM large_scenes
                WHERE id = ?
                """,
                (large_scene_id,),
            ).fetchone()
            if large_scene is None:
                raise ValueError("大场景不存在。")
            chapter_id = large_scene["chapter_id"]
            connection.execute(
                "DELETE FROM large_scenes WHERE id = ?", (large_scene_id,)
            )
            # Renumber remaining scenes in the chapter to be contiguous 1..N
            rows = connection.execute(
                "SELECT id FROM large_scenes WHERE chapter_id = ? ORDER BY sort_order ASC, created_at ASC",
                (chapter_id,),
            ).fetchall()
            for idx, r in enumerate(rows, start=1):
                connection.execute(
                    "UPDATE large_scenes SET sort_order = ? WHERE id = ?",
                    (idx, r["id"]),
                )
        return dict(large_scene)

    # ── Characters ──────────────────────────────────────────────

    def list_characters(
        self,
        project_id: str | None = None,
        *,
        search: str | None = None,
        tag: str | None = None,
        include_archived: bool = False,
        include_deleted: bool = False,
        sort: str = "sort_asc",
        limit: int = 100,
        offset: int = 0,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """List characters with search, filter, sort and pagination.

        If project_id given, return characters linked to that project.
        If project_id is None, return all global characters.

        Returns {"items": [...], "total": N, "limit": L, "offset": O, "has_more": bool}.
        Each item contains id/name/description/cover_path/source/archived_at/deleted_at/
        sort_order/revision/created_at/updated_at/tags/variant_count.
        """
        target_environment = environment or self._active_environment
        conditions: list[str] = []
        params: list[object] = []
        base_select = """
            SELECT c.id, c.name, c.description, c.cover_path,
                   c.archived_at, c.deleted_at, c.source, c.source_identifier,
                   c.external_url, c.sort_order, c.revision,
                   c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM character_variants cv
                    WHERE cv.character_id = c.id AND cv.archived_at IS NULL) AS variant_count
        """
        if project_id is not None:
            conditions.append(
                "c.id IN (SELECT character_id FROM project_characters WHERE project_id = ?)"
            )
            params.append(project_id)
        if not include_archived:
            conditions.append("c.archived_at IS NULL")
        if not include_deleted:
            conditions.append("c.deleted_at IS NULL")
        if search:
            conditions.append("(c.name LIKE ? OR c.description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if tag:
            conditions.append(
                "c.id IN (SELECT character_id FROM character_tags WHERE tag = ?)"
            )
            params.append(tag)

        where_clause = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        order_clause = {
            "sort_asc": " ORDER BY c.sort_order ASC, c.created_at ASC",
            "sort_desc": " ORDER BY c.sort_order DESC, c.created_at DESC",
            "name_asc": " ORDER BY c.name ASC, c.created_at ASC",
            "name_desc": " ORDER BY c.name DESC, c.created_at DESC",
            "updated_desc": " ORDER BY c.updated_at DESC, c.created_at DESC",
        }.get(sort, " ORDER BY c.sort_order ASC, c.created_at ASC")

        with self.connection(target_environment) as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM characters c{where_clause}",
                params,
            ).fetchone()
            total = int(count_row["count"])
            rows = connection.execute(
                f"{base_select} FROM characters c{where_clause}{order_clause} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            tag_rows = connection.execute(
                f"""
                SELECT ct.character_id, ct.tag
                FROM character_tags ct
                WHERE ct.character_id IN (
                    SELECT c.id FROM characters c{where_clause}
                )
                ORDER BY ct.tag ASC
                """,
                params,
            ).fetchall()
            tags_by_char: dict[str, list[str]] = {}
            for tr in tag_rows:
                tags_by_char.setdefault(tr["character_id"], []).append(tr["tag"])

        items = []
        for row in rows:
            item = dict(row)
            item["tags"] = tags_by_char.get(item["id"], [])
            item["variant_count"] = int(item.get("variant_count") or 0)
            items.append(item)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        }

    def get_character_stats(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, int]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(DISTINCT cv.id) AS variant_count,
                    COUNT(csv.id) AS spec_total,
                    COUNT(CASE WHEN csv.prompt != '' THEN 1 END) AS spec_filled
                FROM characters c
                LEFT JOIN character_variants cv ON cv.character_id = c.id
                LEFT JOIN character_spec_values csv ON csv.variant_id = cv.id
                WHERE c.id = ?
                """,
                (character_id,),
            ).fetchone()
        return {
            "variant_count": int(row["variant_count"] or 0),
            "spec_total": int(row["spec_total"] or 0),
            "spec_filled": int(row["spec_filled"] or 0),
        }

    def get_character(
        self,
        character_id: str,
        *,
        include_tags: bool = True,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, name, description, cover_path,
                       archived_at, deleted_at, source, source_identifier,
                       external_url, sort_order, revision,
                       created_at, updated_at
                FROM characters
                WHERE id = ?
                """,
                (character_id,),
            ).fetchone()
            tags: list[str] = []
            if row and include_tags:
                tag_rows = connection.execute(
                    "SELECT tag FROM character_tags WHERE character_id = ? ORDER BY tag ASC",
                    (character_id,),
                ).fetchall()
                tags = [tr["tag"] for tr in tag_rows]
        if row is None:
            return None
        result = dict(row)
        result["tags"] = tags
        return result

    def create_character(
        self,
        name: str,
        project_id: str | None = None,
        *,
        description: str = "",
        source: str = "",
        source_identifier: str | None = None,
        external_url: str | None = None,
        tags: list[str] | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Create a global character. If project_id given, also link to that project."""
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("人物名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("人物名称不能超过 80 个字符。")
        if project_id is not None and self.get_project(project_id, target_environment) is None:
            raise ValueError("项目不存在。")
        clean_description = " ".join(description.split())
        if len(clean_description) > 500:
            raise ValueError("人物说明不能超过 500 个字符。")
        clean_source = " ".join(source.split())
        clean_tags = sorted({
            " ".join(t.split()) for t in (tags or []) if " ".join(t.split())
        })
        now = datetime.now(timezone.utc).isoformat()
        character_id = str(uuid4())
        try:
            with self._lock, self.connection(target_environment) as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) AS max_sort FROM characters"
                ).fetchone()
                next_sort = int(row["max_sort"]) + 1
                connection.execute(
                    """
                    INSERT INTO characters(
                        id, name, description, source, source_identifier,
                        external_url, sort_order, revision, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        character_id, clean_name, clean_description, clean_source,
                        source_identifier, external_url, next_sort, now, now,
                    ),
                )
                if project_id is not None:
                    connection.execute(
                        "INSERT INTO project_characters(project_id, character_id, created_at) VALUES (?, ?, ?)",
                        (project_id, character_id, now),
                    )
                for tag in clean_tags:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO character_tags(id, character_id, tag, created_at)
                        VALUES(?, ?, ?, ?)
                        """,
                        (str(uuid4()), character_id, tag, now),
                    )
                variant_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO character_variants(
                        id, character_id, name, is_default, sort_order, created_at, updated_at
                    )
                    VALUES(?, ?, '默认', 1, 1, ?, ?)
                    """,
                    (variant_id, character_id, now, now),
                )
                spec_rows = connection.execute(
                    "SELECT id FROM specs ORDER BY sort_order ASC"
                ).fetchall()
                for spec in spec_rows:
                    connection.execute(
                        """
                        INSERT INTO character_spec_values(
                            id, variant_id, spec_id,
                            prompt, lora_name, lora_weight, model_override, notes,
                            created_at, updated_at
                        )
                        VALUES(?, ?, ?, '', '', NULL, '', '', ?, ?)
                        """,
                        (str(uuid4()), variant_id, spec["id"], now, now),
                    )
        except sqlite3.IntegrityError as error:
            raise ValueError("人物创建失败，可能是数据冲突。") from error
        return self.get_character(character_id, environment=target_environment)  # type: ignore[return-value]

    def link_character_to_project(
        self,
        character_id: str,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> None:
        target_environment = environment or self._active_environment
        if self.get_character(character_id, environment=target_environment) is None:
            raise ValueError("人物不存在。")
        if self.get_project(project_id, target_environment) is None:
            raise ValueError("项目不存在。")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            connection.execute(
                "INSERT OR IGNORE INTO project_characters(project_id, character_id, created_at) VALUES (?, ?, ?)",
                (project_id, character_id, now),
            )

    def unlink_character_from_project(
        self,
        character_id: str,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            connection.execute(
                "DELETE FROM project_characters WHERE project_id = ? AND character_id = ?",
                (project_id, character_id),
            )

    def update_character(
        self,
        character_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Update character name and/or description. revision auto-incremented."""
        target_environment = environment or self._active_environment
        sets: list[str] = []
        params: list[object] = []
        if name is not None:
            clean_name = " ".join(name.split())
            if not clean_name:
                raise ValueError("人物名称不能为空。")
            if len(clean_name) > 80:
                raise ValueError("人物名称不能超过 80 个字符。")
            sets.append("name = ?")
            params.append(clean_name)
        if description is not None:
            clean_description = " ".join(description.split())
            if len(clean_description) > 500:
                raise ValueError("人物说明不能超过 500 个字符。")
            sets.append("description = ?")
            params.append(clean_description)
        if not sets:
            raise ValueError("至少需要提供一个更新字段。")
        now = datetime.now(timezone.utc).isoformat()
        sets.extend(["revision = revision + 1", "updated_at = ?"])
        params.extend([now, character_id])
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                f"UPDATE characters SET {', '.join(sets)} WHERE id = ?",
                params,
            )
            if cursor.rowcount == 0:
                raise ValueError("人物不存在。")
        character = self.get_character(character_id, environment=target_environment)
        if character is None:
            raise ValueError("人物不存在。")
        return character

    def rename_character(
        self,
        character_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Legacy rename wrapper, kept for backward compatibility."""
        return self.update_character(
            character_id, name=name, environment=environment
        )

    def set_character_cover_path(
        self,
        character_id: str,
        cover_path: str | None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Set or clear character cover_path. revision auto-incremented."""
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE characters
                SET cover_path = ?, revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (cover_path, now, character_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character(character_id, environment=target_environment)

    def set_character_tags(
        self,
        character_id: str,
        tags: list[str],
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Replace all tags of a character."""
        target_environment = environment or self._active_environment
        clean_tags = sorted({
            " ".join(t.split()) for t in tags if " ".join(t.split())
        })
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM characters WHERE id = ?", (character_id,)
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "DELETE FROM character_tags WHERE character_id = ?", (character_id,)
            )
            for tag in clean_tags:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO character_tags(id, character_id, tag, created_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (str(uuid4()), character_id, tag, now),
                )
        return self.get_character(character_id, environment=target_environment)

    def archive_character(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE characters
                SET archived_at = ?, revision = revision + 1, updated_at = ?
                WHERE id = ? AND deleted_at IS NULL
                """,
                (now, now, character_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character(character_id, environment=target_environment)

    def restore_character(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Clear both archived_at and deleted_at."""
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE characters
                SET archived_at = NULL, deleted_at = NULL,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, character_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character(character_id, environment=target_environment)

    def soft_delete_character(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE characters
                SET deleted_at = ?, revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, now, character_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character(character_id, environment=target_environment)

    def list_deleted_characters(
        self,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, name, description, cover_path,
                       archived_at, deleted_at, source, source_identifier,
                       external_url, sort_order, revision,
                       created_at, updated_at
                FROM characters
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def permanent_delete_character(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> bool:
        """Permanently delete a character and all related data (cascade)."""
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM characters WHERE id = ?", (character_id,)
            ).fetchone()
            if existing is None:
                return False
            # Cascade delete covers character_variants/character_spec_values/character_tags/project_characters
            connection.execute(
                "DELETE FROM characters WHERE id = ?", (character_id,)
            )
        return True

    def get_character_references(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Return project/scene-page references of a character."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            project_rows = connection.execute(
                """
                SELECT p.id AS project_id, p.name AS project_name
                FROM project_characters pc
                JOIN projects p ON p.id = pc.project_id
                WHERE pc.character_id = ?
                ORDER BY p.name ASC
                """,
                (character_id,),
            ).fetchall()
            page_rows = connection.execute(
                """
                SELECT sp.id AS shot_page_id, sp.title AS shot_page_title,
                       ss.id AS small_scene_id, ss.name AS small_scene_name
                FROM shot_page_characters spc
                JOIN shot_pages sp ON sp.id = spc.shot_page_id
                JOIN small_scenes ss ON ss.id = sp.small_scene_id
                WHERE spc.character_id = ?
                ORDER BY sp.title ASC
                """,
                (character_id,),
            ).fetchall()
        return {
            "projects": [dict(r) for r in project_rows],
            "shot_pages": [dict(r) for r in page_rows],
            "project_count": len(project_rows),
            "shot_page_count": len(page_rows),
        }

    def copy_character(
        self,
        character_id: str,
        new_name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Copy a character (with variants, spec values, tags) as an independent copy."""
        target_environment = environment or self._active_environment
        source = self.get_character(character_id, environment=target_environment)
        if source is None:
            raise ValueError("人物不存在。")
        clean_name = " ".join(new_name.split())
        if not clean_name:
            raise ValueError("新人物名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("人物名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        new_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) AS max_sort FROM characters"
            ).fetchone()
            next_sort = int(row["max_sort"]) + 1
            connection.execute(
                """
                INSERT INTO characters(
                    id, name, description, cover_path, source, source_identifier,
                    external_url, sort_order, revision, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, 'copy', ?, NULL, ?, 1, ?, ?)
                """,
                (
                    new_id, clean_name, source.get("description", ""), None,
                    character_id, next_sort, now, now,
                ),
            )
            # Copy tags
            tag_rows = connection.execute(
                "SELECT tag FROM character_tags WHERE character_id = ?",
                (character_id,),
            ).fetchall()
            for tr in tag_rows:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO character_tags(id, character_id, tag, created_at)
                    VALUES(?, ?, ?, ?)
                    """,
                    (str(uuid4()), new_id, tr["tag"], now),
                )
            # Copy variants and their spec values
            variant_rows = connection.execute(
                """
                SELECT id, name, description, is_default, default_prompt,
                       default_lora_name, default_lora_weight, default_model_override,
                       preview_original_path, preview_thumbnail_path,
                       archived_at, sort_order
                FROM character_variants
                WHERE character_id = ?
                ORDER BY sort_order ASC
                """,
                (character_id,),
            ).fetchall()
            for vr in variant_rows:
                new_variant_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO character_variants(
                        id, character_id, name, description, is_default,
                        default_prompt, default_lora_name, default_lora_weight,
                        default_model_override, preview_original_path, preview_thumbnail_path,
                        archived_at, source_variant_id, sort_order, revision,
                        created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, 1, ?, ?)
                    """,
                    (
                        new_variant_id, new_id, vr["name"], vr["description"],
                        vr["is_default"], vr["default_prompt"], vr["default_lora_name"],
                        vr["default_lora_weight"], vr["default_model_override"],
                        vr["id"], vr["sort_order"], now, now,
                    ),
                )
                csv_rows = connection.execute(
                    """
                    SELECT spec_id, prompt, lora_name, lora_weight,
                           model_override, notes
                    FROM character_spec_values
                    WHERE variant_id = ?
                    """,
                    (vr["id"],),
                ).fetchall()
                for csv in csv_rows:
                    connection.execute(
                        """
                        INSERT INTO character_spec_values(
                            id, variant_id, spec_id, prompt, lora_name,
                            lora_weight, model_override, notes,
                            preview_original_path, preview_thumbnail_path,
                            created_at, updated_at
                        )
                        VALUES(?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                        """,
                        (
                            str(uuid4()), new_variant_id, csv["spec_id"], csv["prompt"],
                            csv["lora_name"], csv["lora_weight"], csv["model_override"],
                            csv["notes"], now, now,
                        ),
                    )
        result = self.get_character(new_id, environment=target_environment)
        if result is None:
            raise ValueError("人物复制失败。")
        return result

    def delete_character(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Soft delete a character (alias for soft_delete_character for backward compat)."""
        result = self.soft_delete_character(character_id, environment)
        if result is None:
            raise ValueError("人物不存在。")
        return result

    # ── Character Variants ──────────────────────────────────────

    def list_character_variants(
        self,
        character_id: str,
        *,
        include_archived: bool = False,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, character_id, name, description, is_default,
                       default_prompt, default_lora_name, default_lora_weight,
                       default_model_override, preview_original_path, preview_thumbnail_path,
                       archived_at, source_variant_id, sort_order, revision,
                       created_at, updated_at
                FROM character_variants
                WHERE character_id = ? AND archived_at IS NULL
                ORDER BY sort_order ASC, created_at ASC
                """,
                (character_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_character_variant(
        self,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, character_id, name, description, is_default,
                       default_prompt, default_lora_name, default_lora_weight,
                       default_model_override, preview_original_path, preview_thumbnail_path,
                       archived_at, source_variant_id, sort_order, revision,
                       created_at, updated_at
                FROM character_variants
                WHERE id = ?
                """,
                (variant_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_character_variant(
        self,
        character_id: str,
        name: str,
        *,
        description: str = "",
        default_prompt: str = "",
        default_lora_name: str = "",
        default_lora_weight: float | None = None,
        default_model_override: str = "",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("形象变体名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("形象变体名称不能超过 80 个字符。")
        clean_description = " ".join(description.split())
        if len(clean_description) > 500:
            raise ValueError("变体说明不能超过 500 个字符。")
        if default_lora_weight is not None and (default_lora_weight < 0 or default_lora_weight > 2):
            raise ValueError("LoRA 权重必须在 0 到 2 之间。")
        character = self.get_character(character_id, environment=target_environment)
        if character is None:
            raise ValueError("人物不存在。")
        now = datetime.now(timezone.utc).isoformat()
        variant_id = str(uuid4())
        try:
            with self._lock, self.connection(target_environment) as connection:
                row = connection.execute(
                    """
                    SELECT COALESCE(MAX(sort_order), 0) AS max_sort
                    FROM character_variants
                    WHERE character_id = ?
                    """,
                    (character_id,),
                ).fetchone()
                next_sort = int(row["max_sort"]) + 1
                connection.execute(
                    """
                    INSERT INTO character_variants(
                        id, character_id, name, description, is_default,
                        default_prompt, default_lora_name, default_lora_weight,
                        default_model_override, sort_order, revision, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        variant_id, character_id, clean_name, clean_description,
                        default_prompt, default_lora_name, default_lora_weight,
                        default_model_override, next_sort, now, now,
                    ),
                )
                spec_rows = connection.execute(
                    "SELECT id FROM specs ORDER BY sort_order ASC"
                ).fetchall()
                for spec in spec_rows:
                    connection.execute(
                        """
                        INSERT INTO character_spec_values(
                            id, variant_id, spec_id,
                            prompt, lora_name, lora_weight, model_override, notes,
                            created_at, updated_at
                        )
                        VALUES(?, ?, ?, '', '', NULL, '', '', ?, ?)
                        """,
                        (str(uuid4()), variant_id, spec["id"], now, now),
                    )
        except sqlite3.IntegrityError as error:
            raise ValueError("该人物下已经存在同名形象变体。") from error
        return self.get_character_variant(variant_id, target_environment)  # type: ignore[return-value]

    def update_character_variant(
        self,
        variant_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        default_prompt: str | None = None,
        default_lora_name: str | None = None,
        default_lora_weight: float | None | object = _UNSET,
        default_model_override: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        sets: list[str] = []
        params: list[object] = []
        if name is not None:
            clean_name = " ".join(name.split())
            if not clean_name:
                raise ValueError("形象变体名称不能为空。")
            if len(clean_name) > 80:
                raise ValueError("形象变体名称不能超过 80 个字符。")
            sets.append("name = ?")
            params.append(clean_name)
        if description is not None:
            clean_description = " ".join(description.split())
            if len(clean_description) > 500:
                raise ValueError("变体说明不能超过 500 个字符。")
            sets.append("description = ?")
            params.append(clean_description)
        if default_prompt is not None:
            sets.append("default_prompt = ?")
            params.append(default_prompt)
        if default_lora_name is not None:
            sets.append("default_lora_name = ?")
            params.append(default_lora_name)
        if default_lora_weight is not _UNSET:
            if default_lora_weight is not None and (
                default_lora_weight < 0 or default_lora_weight > 2
            ):
                raise ValueError("LoRA 权重必须在 0 到 2 之间。")
            sets.append("default_lora_weight = ?")
            params.append(default_lora_weight)
        if default_model_override is not None:
            sets.append("default_model_override = ?")
            params.append(default_model_override)
        if not sets:
            raise ValueError("至少需要提供一个更新字段。")
        now = datetime.now(timezone.utc).isoformat()
        sets.extend(["revision = revision + 1", "updated_at = ?"])
        params.extend([now, variant_id])
        try:
            with self._lock, self.connection(target_environment) as connection:
                cursor = connection.execute(
                    f"UPDATE character_variants SET {', '.join(sets)} WHERE id = ?",
                    params,
                )
                if cursor.rowcount == 0:
                    raise ValueError("形象变体不存在。")
        except sqlite3.IntegrityError as error:
            raise ValueError("该人物下已经存在同名形象变体。") from error
        variant = self.get_character_variant(variant_id, target_environment)
        if variant is None:
            raise ValueError("形象变体不存在。")
        return variant

    def rename_character_variant(
        self,
        variant_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Legacy rename wrapper."""
        return self.update_character_variant(
            variant_id, name=name, environment=environment
        )

    def set_character_variant_preview_paths(
        self,
        variant_id: str,
        preview_original_path: str | None,
        preview_thumbnail_path: str | None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE character_variants
                SET preview_original_path = ?, preview_thumbnail_path = ?,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (preview_original_path, preview_thumbnail_path, now, variant_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character_variant(variant_id, target_environment)

    def reorder_character_variants(
        self,
        character_id: str,
        variant_ids: list[str],
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """Reorder variants of a character. variant_ids must include all non-archived variants."""
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing_rows = connection.execute(
                """
                SELECT id FROM character_variants
                WHERE character_id = ? AND archived_at IS NULL
                """,
                (character_id,),
            ).fetchall()
            existing_ids = {r["id"] for r in existing_rows}
            if set(variant_ids) != existing_ids:
                raise ValueError("变体 ID 列表必须包含全部未归档变体。")
            for index, vid in enumerate(variant_ids, start=1):
                connection.execute(
                    """
                    UPDATE character_variants
                    SET sort_order = ?, revision = revision + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (index, now, vid),
                )
        return self.list_character_variants(character_id, environment=target_environment)

    def copy_character_variant(
        self,
        variant_id: str,
        new_name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Copy a variant as an independent variant under the same character."""
        target_environment = environment or self._active_environment
        source = self.get_character_variant(variant_id, target_environment)
        if source is None:
            raise ValueError("形象变体不存在。")
        clean_name = " ".join(new_name.split())
        if not clean_name:
            raise ValueError("新变体名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("形象变体名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        new_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sort_order), 0) AS max_sort
                FROM character_variants
                WHERE character_id = ?
                """,
                (source["character_id"],),
            ).fetchone()
            next_sort = int(row["max_sort"]) + 1
            connection.execute(
                """
                INSERT INTO character_variants(
                    id, character_id, name, description, is_default,
                    default_prompt, default_lora_name, default_lora_weight,
                    default_model_override, preview_original_path, preview_thumbnail_path,
                    archived_at, source_variant_id, sort_order, revision,
                    created_at, updated_at
                )
                VALUES(?, ?, ?, ?, 0, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, 1, ?, ?)
                """,
                (
                    new_id, source["character_id"], clean_name, source.get("description", ""),
                    source.get("default_prompt", ""), source.get("default_lora_name", ""),
                    source.get("default_lora_weight"), source.get("default_model_override", ""),
                    variant_id, next_sort, now, now,
                ),
            )
            csv_rows = connection.execute(
                """
                SELECT spec_id, prompt, lora_name, lora_weight,
                       model_override, notes
                FROM character_spec_values
                WHERE variant_id = ?
                """,
                (variant_id,),
            ).fetchall()
            for csv in csv_rows:
                connection.execute(
                    """
                    INSERT INTO character_spec_values(
                        id, variant_id, spec_id, prompt, lora_name,
                        lora_weight, model_override, notes,
                        preview_original_path, preview_thumbnail_path,
                        created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                    """,
                    (
                        str(uuid4()), new_id, csv["spec_id"], csv["prompt"],
                        csv["lora_name"], csv["lora_weight"], csv["model_override"],
                        csv["notes"], now, now,
                    ),
                )
        result = self.get_character_variant(new_id, target_environment)
        if result is None:
            raise ValueError("变体复制失败。")
        return result

    def archive_character_variant(
        self,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE character_variants
                SET archived_at = ?, revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, now, variant_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character_variant(variant_id, target_environment)

    def restore_character_variant(
        self,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE character_variants
                SET archived_at = NULL, revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, variant_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character_variant(variant_id, target_environment)

    def delete_character_variant(
        self,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            variant = connection.execute(
                """
                SELECT id, character_id, name, is_default, sort_order, created_at, updated_at
                FROM character_variants
                WHERE id = ?
                """,
                (variant_id,),
            ).fetchone()
            if variant is None:
                raise ValueError("形象变体不存在。")
            connection.execute(
                "DELETE FROM character_variants WHERE id = ?", (variant_id,)
            )
        return dict(variant)

    def get_character_variant_references(
        self,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Return shot_pages that reference this variant."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            page_rows = connection.execute(
                """
                SELECT sp.id AS shot_page_id, sp.title AS shot_page_title,
                       ss.id AS small_scene_id, ss.name AS small_scene_name,
                       ls.id AS large_scene_id, ls.name AS large_scene_name
                FROM shot_page_characters spc
                JOIN shot_pages sp ON sp.id = spc.shot_page_id
                JOIN small_scenes ss ON ss.id = sp.small_scene_id
                JOIN large_scenes ls ON ls.id = ss.large_scene_id
                WHERE spc.variant_id = ?
                ORDER BY sp.title ASC
                """,
                (variant_id,),
            ).fetchall()
        return {
            "shot_pages": [dict(r) for r in page_rows],
            "shot_page_count": len(page_rows),
        }

    # ── Specs (global) ──────────────────────────────────────────

    def list_specs(
        self,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, spec_type, custom_label, description,
                       is_required, default_value, sort_order,
                       created_at, updated_at
                FROM specs
                ORDER BY sort_order ASC, created_at ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_spec(
        self,
        spec_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, spec_type, custom_label, description,
                       is_required, default_value, sort_order,
                       created_at, updated_at
                FROM specs
                WHERE id = ?
                """,
                (spec_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_spec(
        self,
        spec_type: str,
        custom_label: str = "",
        *,
        description: str = "",
        is_required: bool = False,
        default_value: str = "",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        valid_types = ("full_body", "half_body", "close_up", "custom")
        if spec_type not in valid_types:
            raise ValueError(f"规格类型必须是 {', '.join(valid_types)} 之一。")
        if spec_type == "custom" and not custom_label.strip():
            raise ValueError("自定义规格必须提供标签名称。")
        if spec_type != "custom":
            custom_label = ""
        clean_description = " ".join(description.split())
        if len(clean_description) > 500:
            raise ValueError("规格说明不能超过 500 个字符。")
        clean_default = " ".join(default_value.split())
        if len(clean_default) > 500:
            raise ValueError("默认值不能超过 500 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        spec_id = str(uuid4())
        try:
            with self._lock, self.connection(target_environment) as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) AS max_sort FROM specs"
                ).fetchone()
                next_sort = int(row["max_sort"]) + 1
                connection.execute(
                    """
                    INSERT INTO specs(
                        id, spec_type, custom_label, description,
                        is_required, default_value, sort_order, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        spec_id, spec_type, custom_label, clean_description,
                        1 if is_required else 0, clean_default, next_sort, now, now,
                    ),
                )
                # Create empty spec values for all existing variants
                variant_rows = connection.execute(
                    "SELECT id FROM character_variants"
                ).fetchall()
                for variant in variant_rows:
                    connection.execute(
                        """
                        INSERT INTO character_spec_values(
                            id, variant_id, spec_id,
                            prompt, lora_name, lora_weight, model_override, notes,
                            created_at, updated_at
                        )
                        VALUES(?, ?, ?, '', '', NULL, '', '', ?, ?)
                        """,
                        (str(uuid4()), variant["id"], spec_id, now, now),
                    )
        except sqlite3.IntegrityError as error:
            raise ValueError("已存在相同类型和标签的规格。") from error
        return self.get_spec(spec_id, target_environment)  # type: ignore[return-value]

    def update_spec(
        self,
        spec_id: str,
        *,
        custom_label: str | None = None,
        description: str | None = None,
        is_required: bool | None = None,
        default_value: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        spec = self.get_spec(spec_id, target_environment)
        if spec is None:
            raise ValueError("规格不存在。")
        sets: list[str] = []
        params: list[object] = []
        if custom_label is not None:
            if spec["spec_type"] != "custom":
                raise ValueError("只有自定义规格可以修改标签。")
            clean_label = " ".join(custom_label.split())
            if not clean_label:
                raise ValueError("自定义规格标签不能为空。")
            if len(clean_label) > 80:
                raise ValueError("自定义规格标签不能超过 80 个字符。")
            sets.append("custom_label = ?")
            params.append(clean_label)
        if description is not None:
            clean_description = " ".join(description.split())
            if len(clean_description) > 500:
                raise ValueError("规格说明不能超过 500 个字符。")
            sets.append("description = ?")
            params.append(clean_description)
        if is_required is not None:
            sets.append("is_required = ?")
            params.append(1 if is_required else 0)
        if default_value is not None:
            clean_default = " ".join(default_value.split())
            if len(clean_default) > 500:
                raise ValueError("默认值不能超过 500 个字符。")
            sets.append("default_value = ?")
            params.append(clean_default)
        if not sets:
            raise ValueError("至少需要提供一个更新字段。")
        now = datetime.now(timezone.utc).isoformat()
        sets.append("updated_at = ?")
        params.extend([now, spec_id])
        try:
            with self._lock, self.connection(target_environment) as connection:
                cursor = connection.execute(
                    f"UPDATE specs SET {', '.join(sets)} WHERE id = ?",
                    params,
                )
                if cursor.rowcount == 0:
                    raise ValueError("规格不存在。")
        except sqlite3.IntegrityError as error:
            raise ValueError("已存在相同标签的规格。") from error
        return self.get_spec(spec_id, target_environment)  # type: ignore[return-value]

    def delete_spec(
        self,
        spec_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            spec = connection.execute(
                """
                SELECT id, spec_type, custom_label, description,
                       is_required, default_value, sort_order,
                       created_at, updated_at
                FROM specs
                WHERE id = ?
                """,
                (spec_id,),
            ).fetchone()
            if spec is None:
                raise ValueError("规格不存在。")
            connection.execute("DELETE FROM specs WHERE id = ?", (spec_id,))
        return dict(spec)

    def get_character_spec_matrix(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Return the variant × spec matrix of a character.

        Returns:
        {
            "character": {...},
            "specs": [{id, spec_type, custom_label, is_required, default_value, sort_order}],
            "variants": [{id, name, is_default, sort_order}],
            "values": {variant_id: {spec_id: {id, prompt, lora_name, lora_weight, model_override, notes}}},
            "missing_required": [{variant_id, variant_name, spec_id, spec_label}]
        }
        """
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            character = connection.execute(
                """
                SELECT id, name FROM characters WHERE id = ?
                """,
                (character_id,),
            ).fetchone()
            if character is None:
                raise ValueError("人物不存在。")
            spec_rows = connection.execute(
                """
                SELECT id, spec_type, custom_label, description,
                       is_required, default_value, sort_order
                FROM specs
                ORDER BY sort_order ASC, created_at ASC
                """
            ).fetchall()
            variant_rows = connection.execute(
                """
                SELECT id, name, is_default, sort_order
                FROM character_variants
                WHERE character_id = ? AND archived_at IS NULL
                ORDER BY sort_order ASC
                """,
                (character_id,),
            ).fetchall()
            csv_rows = connection.execute(
                """
                SELECT csv.id, csv.variant_id, csv.spec_id,
                       csv.prompt, csv.lora_name, csv.lora_weight,
                       csv.model_override, csv.notes,
                       csv.preview_original_path, csv.preview_thumbnail_path
                FROM character_spec_values csv
                JOIN character_variants cv ON cv.id = csv.variant_id
                WHERE cv.character_id = ? AND cv.archived_at IS NULL
                """,
                (character_id,),
            ).fetchall()
        values: dict[str, dict[str, dict[str, object]]] = {
            vr["id"]: {} for vr in variant_rows
        }
        for csv in csv_rows:
            values.setdefault(csv["variant_id"], {})[csv["spec_id"]] = {
                "id": csv["id"],
                "prompt": csv["prompt"],
                "lora_name": csv["lora_name"],
                "lora_weight": csv["lora_weight"],
                "model_override": csv["model_override"],
                "notes": csv["notes"],
                "preview_original_path": csv["preview_original_path"],
                "preview_thumbnail_path": csv["preview_thumbnail_path"],
            }
        missing_required: list[dict[str, object]] = []
        required_specs = [s for s in spec_rows if s["is_required"]]
        for vr in variant_rows:
            for sp in required_specs:
                v = values.get(vr["id"], {}).get(sp["id"])
                if v is None or (not v.get("prompt") and not v.get("lora_name")):
                    missing_required.append({
                        "variant_id": vr["id"],
                        "variant_name": vr["name"],
                        "spec_id": sp["id"],
                        "spec_label": sp["custom_label"] or sp["spec_type"],
                    })
        return {
            "character": dict(character),
            "specs": [dict(s) for s in spec_rows],
            "variants": [dict(v) for v in variant_rows],
            "values": values,
            "missing_required": missing_required,
        }

    def batch_update_spec_values(
        self,
        updates: list[dict[str, object]],
        environment: DatabaseEnvironment | None = None,
    ) -> int:
        """Batch update spec values. Each update must contain spec_value_id and fields to update.

        Returns count of updated rows.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        with self._lock, self.connection(target_environment) as connection:
            for update in updates:
                spec_value_id = update.get("spec_value_id")
                if not spec_value_id:
                    continue
                sets: list[str] = []
                params: list[object] = []
                for field in ("prompt", "lora_name", "model_override", "notes"):
                    if field in update:
                        sets.append(f"{field} = ?")
                        params.append(update[field])
                if "lora_weight" in update:
                    lw = update["lora_weight"]
                    if lw is not None and (lw < 0 or lw > 2):
                        raise ValueError("LoRA 权重必须在 0 到 2 之间。")
                    sets.append("lora_weight = ?")
                    params.append(lw)
                if not sets:
                    continue
                sets.append("updated_at = ?")
                params.extend([now, spec_value_id])
                cursor = connection.execute(
                    f"UPDATE character_spec_values SET {', '.join(sets)} WHERE id = ?",
                    params,
                )
                if cursor.rowcount:
                    count += 1
        return count

    # ── Character Spec Values ───────────────────────────────────

    def get_character_spec_value(
        self,
        spec_value_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, variant_id, spec_id,
                       prompt, lora_name, lora_weight, model_override, notes,
                       preview_original_path, preview_thumbnail_path,
                       created_at, updated_at
                FROM character_spec_values
                WHERE id = ?
                """,
                (spec_value_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_character_spec_value_preview_paths(
        self,
        spec_value_id: str,
        preview_original_path: str | None,
        preview_thumbnail_path: str | None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                """
                UPDATE character_spec_values
                SET preview_original_path = ?, preview_thumbnail_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (preview_original_path, preview_thumbnail_path, now, spec_value_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_character_spec_value(spec_value_id, target_environment)

    def update_character_spec_value(
        self,
        spec_value_id: str,
        *,
        prompt: str | None = None,
        lora_name: str | None = None,
        lora_weight: float | None | object = _UNSET,
        model_override: str | None = None,
        notes: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM character_spec_values WHERE id = ?",
                (spec_value_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("规格值不存在。")
            sets: list[str] = []
            params: list[object] = []
            if prompt is not None:
                sets.append("prompt = ?")
                params.append(prompt)
            if lora_name is not None:
                sets.append("lora_name = ?")
                params.append(lora_name)
            if lora_weight is not _UNSET:
                if lora_weight is not None and (lora_weight < 0 or lora_weight > 2):
                    raise ValueError("LoRA 权重必须在 0 到 2 之间。")
                sets.append("lora_weight = ?")
                params.append(lora_weight)
            if model_override is not None:
                sets.append("model_override = ?")
                params.append(model_override)
            if notes is not None:
                sets.append("notes = ?")
                params.append(notes)
            if not sets:
                raise ValueError("至少需要提供一个更新字段。")
            sets.append("updated_at = ?")
            params.append(now)
            params.append(spec_value_id)
            connection.execute(
                f"UPDATE character_spec_values SET {', '.join(sets)} WHERE id = ?",
                params,
            )
        result = self.get_character_spec_value(spec_value_id, target_environment)
        if result is None:
            raise ValueError("规格值不存在。")
        return result

    # ── Shot Page Character References ──────────────────────────

    def get_shot_page_character(
        self,
        shot_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Return the character/variant bound to a shot page, or None."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT spc.shot_page_id, spc.character_id, spc.variant_id,
                       c.name AS character_name,
                       cv.name AS variant_name,
                       cv.default_prompt, cv.default_lora_name,
                       cv.default_lora_weight, cv.default_model_override
                FROM shot_page_characters spc
                JOIN characters c ON c.id = spc.character_id
                JOIN character_variants cv ON cv.id = spc.variant_id
                WHERE spc.shot_page_id = ?
                """,
                (shot_page_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_shot_page_character(
        self,
        shot_page_id: str,
        character_id: str,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Bind a character variant to a shot page (upsert)."""
        target_environment = environment or self._active_environment
        # Validate variant belongs to character
        variant = self.get_character_variant(variant_id, target_environment)
        if variant is None:
            raise ValueError("形象变体不存在。")
        if variant["character_id"] != character_id:
            raise ValueError("形象变体不属于该人物。")
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            page = connection.execute(
                "SELECT id FROM shot_pages WHERE id = ?", (shot_page_id,)
            ).fetchone()
            if page is None:
                raise ValueError("场景页不存在。")
            connection.execute(
                """
                INSERT INTO shot_page_characters(
                    shot_page_id, character_id, variant_id, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(shot_page_id) DO UPDATE SET
                    character_id = excluded.character_id,
                    variant_id = excluded.variant_id,
                    updated_at = excluded.updated_at
                """,
                (shot_page_id, character_id, variant_id, now, now),
            )
        result = self.get_shot_page_character(shot_page_id, target_environment)
        if result is None:
            raise ValueError("场景页人物绑定失败。")
        return result

    def clear_shot_page_character(
        self,
        shot_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> bool:
        """Remove the character binding from a shot page. Returns True if a row was deleted."""
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            cursor = connection.execute(
                "DELETE FROM shot_page_characters WHERE shot_page_id = ?",
                (shot_page_id,),
            )
            return cursor.rowcount > 0

    def list_shot_pages_by_variant(
        self,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT sp.id AS shot_page_id, sp.title AS shot_page_title,
                       ss.id AS small_scene_id, ss.name AS small_scene_name,
                       ls.id AS large_scene_id, ls.name AS large_scene_name,
                       c.id AS chapter_id, c.name AS chapter_name
                FROM shot_page_characters spc
                JOIN shot_pages sp ON sp.id = spc.shot_page_id
                JOIN small_scenes ss ON ss.id = sp.small_scene_id
                JOIN large_scenes ls ON ls.id = ss.large_scene_id
                JOIN chapters c ON c.id = ls.chapter_id
                WHERE spc.variant_id = ?
                ORDER BY c.sort_order ASC, ls.sort_order ASC, ss.sort_order ASC, sp.sort_order ASC
                """,
                (variant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_spec_values_for_variant(
        self,
        variant_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT csv.id, csv.variant_id, csv.spec_id,
                       csv.prompt, csv.lora_name, csv.lora_weight,
                       csv.model_override, csv.notes,
                       csv.created_at, csv.updated_at,
                       s.spec_type, s.custom_label
                FROM character_spec_values csv
                JOIN specs s ON s.id = csv.spec_id
                WHERE csv.variant_id = ?
                ORDER BY s.sort_order ASC
                """,
                (variant_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ── Materials ──────────────────────────────────────────────

    VALID_MATERIAL_TYPES: tuple[str, ...] = (
        "composition",
        "expression",
        "scene",
        "lighting",
        "prompt",
        "composite_template",
    )
    VALID_MATERIAL_SORTS: tuple[str, ...] = (
        "updated_desc",
        "created_desc",
        "name_asc",
        "name_desc",
    )
    VALID_MATERIAL_STATUSES: tuple[str, ...] = ("unverified", "verified")

    def _normalize_material_name(self, name: str) -> str:
        clean = " ".join(name.split())
        if not clean:
            raise ValueError("素材名称不能为空。")
        if len(clean) > 80:
            raise ValueError("素材名称不能超过 80 个字符。")
        return clean

    def _normalize_material_tags(self, tags: list[str] | None) -> list[str]:
        if not tags:
            return []
        if len(tags) > 30:
            raise ValueError("素材标签最多 30 个。")
        seen: set[str] = set()
        result: list[str] = []
        for raw in tags:
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
            result.append(clean)
        return result

    def _validate_material_type(self, material_type: str) -> str:
        if material_type not in self.VALID_MATERIAL_TYPES:
            raise ValueError("素材类型不合法。")
        return material_type

    def _validate_material_status(self, validation_status: str) -> str:
        if validation_status not in self.VALID_MATERIAL_STATUSES:
            raise ValueError("素材验证状态不合法。")
        return validation_status

    def _validate_material_text(
        self,
        *,
        content: str,
        description: str = "",
        prompt_text: str = "",
        negative_prompt: str = "",
        notes: str = "",
    ) -> None:
        if not content.strip():
            raise ValueError("素材正文不能为空。")
        if len(content) > 50000:
            raise ValueError("素材正文不能超过 50,000 字。")
        if len(description) > 300:
            raise ValueError("素材简介不能超过 300 字。")
        if len(prompt_text) > 50000:
            raise ValueError("提示词内容不能超过 50,000 字。")
        if len(negative_prompt) > 20000:
            raise ValueError("负面提示词不能超过 20,000 字。")
        if len(notes) > 5000:
            raise ValueError("备注不能超过 5,000 字。")

    def _material_row_to_dict(self, row: sqlite3.Row) -> dict[str, object]:
        return dict(row)

    def _get_material_tags(
        self, connection: sqlite3.Connection, material_id: str
    ) -> list[str]:
        rows = connection.execute(
            """
            SELECT t.name
            FROM material_tag_links l
            JOIN material_tags t ON t.id = l.tag_id
            WHERE l.material_id = ?
            ORDER BY t.name ASC
            """,
            (material_id,),
        ).fetchall()
        return [row["name"] for row in rows]

    def _sync_material_tags(
        self,
        connection: sqlite3.Connection,
        material_id: str,
        tags: list[str],
        now: str,
    ) -> None:
        connection.execute(
            "DELETE FROM material_tag_links WHERE material_id = ?",
            (material_id,),
        )
        for tag_name in tags:
            row = connection.execute(
                "SELECT id FROM material_tags WHERE name = ?",
                (tag_name,),
            ).fetchone()
            if row is None:
                tag_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO material_tags(id, name, created_at)
                    VALUES(?, ?, ?)
                    """,
                    (tag_id, tag_name, now),
                )
            else:
                tag_id = row["id"]
            connection.execute(
                """
                INSERT OR IGNORE INTO material_tag_links(material_id, tag_id, created_at)
                VALUES(?, ?, ?)
                """,
                (material_id, tag_id, now),
            )

    def list_materials(
        self,
        *,
        query: str = "",
        material_type: str = "",
        validation_status: str = "",
        tag: str = "",
        include_archived: bool = False,
        include_deleted: bool = False,
        limit: int = 60,
        offset: int = 0,
        sort: str = "updated_desc",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100
        if offset < 0:
            offset = 0
        if sort not in self.VALID_MATERIAL_SORTS:
            sort = "updated_desc"

        order_clause = {
            "updated_desc": "m.updated_at DESC, m.name ASC",
            "created_desc": "m.created_at DESC, m.name ASC",
            "name_asc": "m.name ASC, m.updated_at DESC",
            "name_desc": "m.name DESC, m.updated_at DESC",
        }[sort]

        where_parts: list[str] = []
        params: list[object] = []
        if not include_archived:
            where_parts.append("m.archived_at IS NULL")
        if not include_deleted:
            where_parts.append("m.deleted_at IS NULL")
        if query:
            q = query.strip()
            if q:
                if len(q) > 100:
                    q = q[:100]
                escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                like = f"%{escaped}%"
                where_parts.append(
                    "(m.name LIKE ? ESCAPE '\\' OR m.description LIKE ? ESCAPE '\\' "
                    "OR m.content LIKE ? ESCAPE '\\' OR EXISTS ("
                    "SELECT 1 FROM material_tag_links l "
                    "JOIN material_tags t ON t.id = l.tag_id "
                    "WHERE l.material_id = m.id AND t.name LIKE ? ESCAPE '\\'"
                    "))"
                )
                params.extend([like, like, like, like])
        if material_type:
            if material_type not in self.VALID_MATERIAL_TYPES:
                material_type = ""
            else:
                where_parts.append("m.material_type = ?")
                params.append(material_type)
        if validation_status:
            if validation_status in self.VALID_MATERIAL_STATUSES:
                where_parts.append("m.validation_status = ?")
                params.append(validation_status)
        if tag:
            clean_tag = " ".join(tag.split())
            if clean_tag:
                where_parts.append(
                    "EXISTS (SELECT 1 FROM material_tag_links l "
                    "JOIN material_tags t ON t.id = l.tag_id "
                    "WHERE l.material_id = m.id AND t.name = ?)"
                )
                params.append(clean_tag)

        where_sql = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

        with self.connection(target_environment) as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) AS total FROM materials m{where_sql}",
                params,
            ).fetchone()
            total = int(count_row["total"])
            rows = connection.execute(
                f"""
                SELECT m.id, m.name, m.material_type, m.description,
                       m.validation_status, m.preview_thumbnail_path,
                       m.archived_at, m.deleted_at, m.source_material_id,
                       m.created_at, m.updated_at
                FROM materials m
                {where_sql}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()
            items: list[dict[str, object]] = []
            for row in rows:
                item = dict(row)
                tags = self._get_material_tags(connection, row["id"])
                item["tags"] = tags
                thumbnail_path = item.get("preview_thumbnail_path")
                item["thumbnail_url"] = (
                    f"/api/materials/{item['id']}/thumbnail" if thumbnail_path else None
                )
                items.append(item)

        has_more = (offset + limit) < total
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": has_more,
        }

    def get_material(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, name, material_type, description, content,
                       prompt_text, negative_prompt, validation_status, notes,
                       preview_original_path, preview_thumbnail_path,
                       archived_at, deleted_at, source_material_id,
                       created_at, updated_at
                FROM materials
                WHERE id = ? AND deleted_at IS NULL
                """,
                (material_id,),
            ).fetchone()
            if row is None:
                return None
            material = dict(row)
            material["tags"] = self._get_material_tags(connection, material_id)
        material["preview_url"] = (
            f"/api/materials/{material_id}/preview"
            if material.get("preview_original_path")
            else None
        )
        material["thumbnail_url"] = (
            f"/api/materials/{material_id}/thumbnail"
            if material.get("preview_thumbnail_path")
            else None
        )
        return material

    def create_material(
        self,
        *,
        name: str,
        material_type: str,
        content: str,
        description: str = "",
        prompt_text: str = "",
        negative_prompt: str = "",
        validation_status: str = "unverified",
        notes: str = "",
        tags: list[str] | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = self._normalize_material_name(name)
        self._validate_material_type(material_type)
        self._validate_material_status(validation_status)
        self._validate_material_text(
            content=content,
            description=description,
            prompt_text=prompt_text,
            negative_prompt=negative_prompt,
            notes=notes,
        )
        clean_tags = self._normalize_material_tags(tags)
        now = datetime.now(timezone.utc).isoformat()
        material = {
            "id": str(uuid4()),
            "name": clean_name,
            "material_type": material_type,
            "description": description,
            "content": content,
            "prompt_text": prompt_text,
            "negative_prompt": negative_prompt,
            "validation_status": validation_status,
            "notes": notes,
            "preview_original_path": None,
            "preview_thumbnail_path": None,
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._lock, self.connection(target_environment) as connection:
                connection.execute(
                    """
                    INSERT INTO materials(
                        id, name, material_type, description, content,
                        prompt_text, negative_prompt, validation_status, notes,
                        preview_original_path, preview_thumbnail_path,
                        created_at, updated_at
                    )
                    VALUES(
                        :id, :name, :material_type, :description, :content,
                        :prompt_text, :negative_prompt, :validation_status, :notes,
                        :preview_original_path, :preview_thumbnail_path,
                        :created_at, :updated_at
                    )
                    """,
                    material,
                )
                self._sync_material_tags(connection, material["id"], clean_tags, now)
                # v0.4.1: auto-generate a default material page so the material
                # is immediately usable after being associated with a scene.
                connection.execute(
                    """INSERT INTO material_pages
                       (id, material_id, name, description, content, prompt_text,
                        negative_prompt, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                    (str(uuid4()), material["id"], clean_name, description, content,
                     prompt_text, negative_prompt, now, now),
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("该类型下已存在同名素材。") from error
        material["tags"] = clean_tags
        material["preview_url"] = None
        material["thumbnail_url"] = None
        return material

    def update_material(
        self,
        material_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
        **updates,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        allowed = {
            "name",
            "material_type",
            "description",
            "content",
            "prompt_text",
            "negative_prompt",
            "validation_status",
            "notes",
            "tags",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"不允许更新的字段: {', '.join(sorted(unknown))}")
        if not updates:
            raise ValueError("至少需要提供一个更新字段。")

        if "name" in updates and updates["name"] is not None:
            updates["name"] = self._normalize_material_name(updates["name"])
        if "material_type" in updates and updates["material_type"] is not None:
            self._validate_material_type(updates["material_type"])
        if "validation_status" in updates and updates["validation_status"] is not None:
            self._validate_material_status(updates["validation_status"])
        if "description" in updates and updates["description"] is not None:
            if len(updates["description"]) > 300:
                raise ValueError("素材简介不能超过 300 字。")
        if "content" in updates and updates["content"] is not None:
            if not updates["content"].strip():
                raise ValueError("素材正文不能为空。")
            if len(updates["content"]) > 50000:
                raise ValueError("素材正文不能超过 50,000 字。")
        if "prompt_text" in updates and updates["prompt_text"] is not None:
            if len(updates["prompt_text"]) > 50000:
                raise ValueError("提示词内容不能超过 50,000 字。")
        if "negative_prompt" in updates and updates["negative_prompt"] is not None:
            if len(updates["negative_prompt"]) > 20000:
                raise ValueError("负面提示词不能超过 20,000 字。")
        if "notes" in updates and updates["notes"] is not None:
            if len(updates["notes"]) > 5000:
                raise ValueError("备注不能超过 5,000 字。")
        if "tags" in updates and updates["tags"] is not None:
            updates["tags"] = self._normalize_material_tags(updates["tags"])

        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if row is None:
                return None
            now = datetime.now(timezone.utc).isoformat()
            set_parts: list[str] = []
            params: list[object] = []
            tag_list: list[str] | None = None
            for key, value in updates.items():
                if key == "tags":
                    tag_list = value if value is not None else []
                    continue
                set_parts.append(f"{key} = ?")
                params.append(value)
            set_parts.append("updated_at = ?")
            params.append(now)
            params.append(material_id)
            try:
                connection.execute(
                    f"""
                    UPDATE materials
                    SET {', '.join(set_parts)}
                    WHERE id = ?
                    """,
                    params,
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("该类型下已存在同名素材。") from error
            if tag_list is not None:
                self._sync_material_tags(connection, material_id, tag_list, now)
        self.create_material_version(material_id, environment=target_environment)
        return self.get_material(material_id, target_environment)

    def delete_material(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id, preview_original_path, preview_thumbnail_path FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "DELETE FROM materials WHERE id = ?",
                (material_id,),
            )
        return {
            "deleted": True,
            "material_id": material_id,
            "preview_original_path": row["preview_original_path"],
            "preview_thumbnail_path": row["preview_thumbnail_path"],
        }

    def list_material_tags(
        self,
        query: str = "",
        limit: int = 30,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        if limit < 1:
            limit = 1
        if limit > 100:
            limit = 100
        q = query.strip()
        params: list[object] = []
        where_sql = ""
        if q:
            if len(q) > 100:
                q = q[:100]
            escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            where_sql = "WHERE t.name LIKE ? ESCAPE '\\'"
            params.append(f"{escaped}%")
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                f"""
                SELECT t.name AS name, COUNT(l.material_id) AS material_count
                FROM material_tags t
                LEFT JOIN material_tag_links l ON l.tag_id = t.id
                LEFT JOIN materials m ON m.id = l.material_id
                {where_sql}
                GROUP BY t.id, t.name
                HAVING material_count > 0
                ORDER BY material_count DESC, t.name ASC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()
        return [dict(row) for row in rows]

    def set_material_preview_paths(
        self,
        material_id: str,
        *,
        original_path: str | None,
        thumbnail_path: str | None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if row is None:
                return None
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                UPDATE materials
                SET preview_original_path = ?, preview_thumbnail_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (original_path, thumbnail_path, now, material_id),
            )
        return self.get_material(material_id, target_environment)

    def set_project_cover_path(
        self,
        project_id: str,
        *,
        cover_path: str | None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Set or clear a project's cover_path.

        Passing cover_path=None clears the cover. Updates updated_at and
        increments revision. Returns the updated project dict, or None if
        the project does not exist.
        """
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if row is None:
                return None
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                UPDATE projects
                SET cover_path = ?, updated_at = ?, revision = revision + 1
                WHERE id = ?
                """,
                (cover_path, now, project_id),
            )
        return self.get_project(project_id, target_environment)

    # ── Small Scenes ───────────────────────────────────────────────────

    def list_small_scenes(
        self,
        large_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT ss.id, ss.large_scene_id, ss.name, ss.scene_type,
                       ss.description, ss.sort_order,
                       ss.created_at, ss.updated_at,
                       (SELECT COUNT(*) FROM shot_pages sp
                        WHERE sp.small_scene_id = ss.id AND sp.branch_id IS NULL) AS shot_page_count,
                       (SELECT COUNT(*) FROM branches b
                        WHERE b.parent_type = 'small_scene' AND b.parent_id = ss.id) AS branch_count
                FROM small_scenes ss
                WHERE ss.large_scene_id = ?
                ORDER BY ss.sort_order ASC
                """,
                (large_scene_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_small_scene(
        self,
        small_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT ss.id, ss.large_scene_id, ss.name, ss.scene_type,
                       ss.description, ss.sort_order,
                       ss.created_at, ss.updated_at
                FROM small_scenes ss
                WHERE ss.id = ?
                """,
                (small_scene_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            mat_rows = connection.execute(
                """
                SELECT m.id AS material_id, m.name, m.material_type, ssm.sort_order
                FROM small_scene_materials ssm
                JOIN materials m ON m.id = ssm.material_id
                WHERE ssm.small_scene_id = ?
                ORDER BY ssm.sort_order ASC
                """,
                (small_scene_id,),
            ).fetchall()
            result["materials"] = [dict(r) for r in mat_rows]
        return result

    def create_small_scene(
        self,
        large_scene_id: str,
        name: str,
        scene_type: str = "content",
        description: str = "",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        if not name or not name.strip():
            raise ValueError("小场景名称不能为空")
        name = name.strip()
        if len(name) > 80:
            raise ValueError("小场景名称不能超过80字")
        if scene_type not in ("content", "transition"):
            raise ValueError("小场景类型无效，允许值: content, transition")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        small_scene_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            parent = connection.execute(
                "SELECT id FROM large_scenes WHERE id = ?", (large_scene_id,)
            ).fetchone()
            if not parent:
                raise ValueError("大场景不存在")
            duplicate = connection.execute(
                "SELECT id FROM small_scenes WHERE large_scene_id = ? AND name = ? COLLATE NOCASE",
                (large_scene_id, name),
            ).fetchone()
            if duplicate:
                raise ValueError("同一大场景下已存在同名小场景")
            max_order = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM small_scenes WHERE large_scene_id = ?",
                (large_scene_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO small_scenes (id, large_scene_id, name, scene_type,
                    description, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (small_scene_id, large_scene_id, name, scene_type,
                 description, max_order + 1, now, now),
            )
        return self.get_small_scene(small_scene_id, environment=target_environment)  # type: ignore[return-value]

    def update_small_scene(
        self,
        small_scene_id: str,
        *,
        name: str | None = None,
        scene_type: str | None = None,
        description: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        if all(v is None for v in (name, scene_type, description)):
            raise ValueError("至少提供一个更新字段")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, large_scene_id FROM small_scenes WHERE id = ?",
                (small_scene_id,),
            ).fetchone()
            if not existing:
                return None
            sets: list[str] = []
            params: list[object] = []
            if name is not None:
                if not name.strip():
                    raise ValueError("小场景名称不能为空")
                name = name.strip()
                if len(name) > 80:
                    raise ValueError("小场景名称不能超过80字")
                duplicate = connection.execute(
                    "SELECT id FROM small_scenes WHERE large_scene_id = ? AND name = ? COLLATE NOCASE AND id != ?",
                    (existing["large_scene_id"], name, small_scene_id),
                ).fetchone()
                if duplicate:
                    raise ValueError("同一大场景下已存在同名小场景")
                sets.append("name = ?")
                params.append(name)
            if scene_type is not None:
                if scene_type not in ("content", "transition"):
                    raise ValueError("小场景类型无效，允许值: content, transition")
                sets.append("scene_type = ?")
                params.append(scene_type)
            if description is not None:
                sets.append("description = ?")
                params.append(description)
            sets.append("updated_at = ?")
            params.append(now)
            params.append(small_scene_id)
            connection.execute(
                f"UPDATE small_scenes SET {', '.join(sets)} WHERE id = ?", params
            )
        return self.get_small_scene(small_scene_id, environment=target_environment)

    def move_small_scene(
        self,
        small_scene_id: str,
        target_sort_order: int,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id, large_scene_id, sort_order FROM small_scenes WHERE id = ?",
                (small_scene_id,),
            ).fetchone()
            if not row:
                raise ValueError("小场景不存在")
            large_scene_id = row["large_scene_id"]
            current_order = row["sort_order"]
            siblings = connection.execute(
                "SELECT id FROM small_scenes WHERE large_scene_id = ? ORDER BY sort_order ASC",
                (large_scene_id,),
            ).fetchall()
            total = len(siblings)
            target = max(1, min(target_sort_order, total))
            if current_order == target:
                pass
            else:
                connection.execute(
                    "UPDATE small_scenes SET sort_order = -1 WHERE id = ?",
                    (small_scene_id,),
                )
                if target < current_order:
                    connection.execute(
                        "UPDATE small_scenes SET sort_order = sort_order + 1 WHERE large_scene_id = ? AND sort_order >= ? AND sort_order < ? AND id != ?",
                        (large_scene_id, target, current_order, small_scene_id),
                    )
                else:
                    connection.execute(
                        "UPDATE small_scenes SET sort_order = sort_order - 1 WHERE large_scene_id = ? AND sort_order > ? AND sort_order <= ? AND id != ?",
                        (large_scene_id, current_order, target, small_scene_id),
                    )
                connection.execute(
                    "UPDATE small_scenes SET sort_order = ? WHERE id = ?",
                    (target, small_scene_id),
                )
        return self.get_small_scene(small_scene_id, environment=target_environment)  # type: ignore[return-value]

    def delete_small_scene(
        self,
        small_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if row is None:
                return None
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                UPDATE materials
                SET preview_original_path = ?, preview_thumbnail_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (original_path, thumbnail_path, now, material_id),
            )
        return self.get_material(material_id, target_environment)

    # ── Small Scenes ───────────────────────────────────────────────────

    def delete_small_scene(
        self,
        small_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, large_scene_id, name FROM small_scenes WHERE id = ?",
                (small_scene_id,),
            ).fetchone()
            if not existing:
                return None
            large_scene_id = existing["large_scene_id"]
            branch_ids = [r["id"] for r in connection.execute(
                "SELECT id FROM branches WHERE parent_type = 'small_scene' AND parent_id = ?",
                (small_scene_id,),
            ).fetchall()]
            for bid in branch_ids:
                connection.execute("DELETE FROM shot_page_materials WHERE shot_page_id IN (SELECT id FROM shot_pages WHERE branch_id = ?)", (bid,))
                connection.execute("DELETE FROM shot_pages WHERE branch_id = ?", (bid,))
            connection.execute("DELETE FROM branches WHERE parent_type = 'small_scene' AND parent_id = ?", (small_scene_id,))
            connection.execute("DELETE FROM small_scenes WHERE id = ?", (small_scene_id,))
            remaining = connection.execute(
                "SELECT id FROM small_scenes WHERE large_scene_id = ? ORDER BY sort_order ASC",
                (large_scene_id,),
            ).fetchall()
            for idx, r in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE small_scenes SET sort_order = ? WHERE id = ?",
                    (idx, r["id"]),
                )
        return {"id": small_scene_id, "name": existing["name"]}

    # ── Shot Pages ─────────────────────────────────────────────────────

    def list_shot_pages(
        self,
        small_scene_id: str,
        branch_id: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            if branch_id is None:
                rows = connection.execute(
                    """
                    SELECT sp.id, sp.small_scene_id, sp.branch_id, sp.title,
                           sp.description, sp.prompt_text, sp.negative_prompt,
                           sp.sort_order, sp.created_at, sp.updated_at
                    FROM shot_pages sp
                    WHERE sp.small_scene_id = ? AND sp.branch_id IS NULL
                    ORDER BY sp.sort_order ASC
                    """,
                    (small_scene_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT sp.id, sp.small_scene_id, sp.branch_id, sp.title,
                           sp.description, sp.prompt_text, sp.negative_prompt,
                           sp.sort_order, sp.created_at, sp.updated_at
                    FROM shot_pages sp
                    WHERE sp.small_scene_id = ? AND sp.branch_id = ?
                    ORDER BY sp.sort_order ASC
                    """,
                    (small_scene_id, branch_id),
                ).fetchall()
            result = []
            for row in rows:
                page = dict(row)
                mat_rows = connection.execute(
                    """
                    SELECT spm.material_id
                    FROM shot_page_materials spm
                    WHERE spm.shot_page_id = ?
                    ORDER BY spm.sort_order ASC
                    """,
                    (row["id"],),
                ).fetchall()
                page["material_ids"] = [r["material_id"] for r in mat_rows]
                result.append(page)
        return result

    def get_shot_page(
        self,
        shot_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, small_scene_id, branch_id, title,
                       description, prompt_text, negative_prompt,
                       sort_order, created_at, updated_at
                FROM shot_pages WHERE id = ?
                """,
                (shot_page_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            mat_rows = connection.execute(
                """
                SELECT m.id AS material_id, m.name, m.material_type, spm.sort_order
                FROM shot_page_materials spm
                JOIN materials m ON m.id = spm.material_id
                WHERE spm.shot_page_id = ?
                ORDER BY spm.sort_order ASC
                """,
                (shot_page_id,),
            ).fetchall()
            result["materials"] = [dict(r) for r in mat_rows]
        return result

    def create_shot_page(
        self,
        small_scene_id: str,
        title: str,
        *,
        branch_id: str | None = None,
        description: str = "",
        prompt_text: str = "",
        negative_prompt: str = "",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        if not title or not title.strip():
            raise ValueError("分镜页标题不能为空")
        title = title.strip()
        if len(title) > 120:
            raise ValueError("分镜页标题不能超过120字")
        if len(description) > 500:
            raise ValueError("分镜页描述不能超过500字")
        if len(prompt_text) > 50000:
            raise ValueError("正向提示词不能超过50000字")
        if len(negative_prompt) > 20000:
            raise ValueError("负向提示词不能超过20000字")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        shot_page_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            scene = connection.execute(
                "SELECT id FROM small_scenes WHERE id = ?", (small_scene_id,)
            ).fetchone()
            if not scene:
                raise ValueError("小场景不存在")
            if branch_id is not None:
                branch = connection.execute(
                    "SELECT id, parent_id FROM branches WHERE id = ?",
                    (branch_id,),
                ).fetchone()
                if not branch:
                    raise ValueError("分支不存在")
            if branch_id is None:
                duplicate = connection.execute(
                    "SELECT id FROM shot_pages WHERE small_scene_id = ? AND branch_id IS NULL AND title = ? COLLATE NOCASE",
                    (small_scene_id, title),
                ).fetchone()
            else:
                duplicate = connection.execute(
                    "SELECT id FROM shot_pages WHERE branch_id = ? AND title = ? COLLATE NOCASE",
                    (branch_id, title),
                ).fetchone()
            if duplicate:
                raise ValueError("同范围内已存在同名分镜页")
            if branch_id is None:
                max_order = connection.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) FROM shot_pages WHERE small_scene_id = ? AND branch_id IS NULL",
                    (small_scene_id,),
                ).fetchone()[0]
            else:
                max_order = connection.execute(
                    "SELECT COALESCE(MAX(sort_order), 0) FROM shot_pages WHERE branch_id = ?",
                    (branch_id,),
                ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO shot_pages (id, small_scene_id, branch_id, title,
                    description, prompt_text, negative_prompt,
                    sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (shot_page_id, small_scene_id, branch_id, title,
                 description, prompt_text, negative_prompt,
                 max_order + 1, now, now),
            )
        return self.get_shot_page(shot_page_id, environment=target_environment)  # type: ignore[return-value]

    def update_shot_page(
        self,
        shot_page_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        prompt_text: str | None = None,
        negative_prompt: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        if all(v is None for v in (title, description, prompt_text, negative_prompt)):
            raise ValueError("至少提供一个更新字段")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, small_scene_id, branch_id FROM shot_pages WHERE id = ?",
                (shot_page_id,),
            ).fetchone()
            if not existing:
                return None
            sets: list[str] = []
            params: list[object] = []
            if title is not None:
                if not title.strip():
                    raise ValueError("分镜页标题不能为空")
                title = title.strip()
                if len(title) > 120:
                    raise ValueError("分镜页标题不能超过120字")
                if existing["branch_id"] is None:
                    duplicate = connection.execute(
                        "SELECT id FROM shot_pages WHERE small_scene_id = ? AND branch_id IS NULL AND title = ? COLLATE NOCASE AND id != ?",
                        (existing["small_scene_id"], title, shot_page_id),
                    ).fetchone()
                else:
                    duplicate = connection.execute(
                        "SELECT id FROM shot_pages WHERE branch_id = ? AND title = ? COLLATE NOCASE AND id != ?",
                        (existing["branch_id"], title, shot_page_id),
                    ).fetchone()
                if duplicate:
                    raise ValueError("同范围内已存在同名分镜页")
                sets.append("title = ?")
                params.append(title)
            if description is not None:
                if len(description) > 500:
                    raise ValueError("分镜页描述不能超过500字")
                sets.append("description = ?")
                params.append(description)
            if prompt_text is not None:
                if len(prompt_text) > 50000:
                    raise ValueError("正向提示词不能超过50000字")
                sets.append("prompt_text = ?")
                params.append(prompt_text)
            if negative_prompt is not None:
                if len(negative_prompt) > 20000:
                    raise ValueError("负向提示词不能超过20000字")
                sets.append("negative_prompt = ?")
                params.append(negative_prompt)
            sets.append("updated_at = ?")
            params.append(now)
            params.append(shot_page_id)
            connection.execute(
                f"UPDATE shot_pages SET {', '.join(sets)} WHERE id = ?", params
            )
        return self.get_shot_page(shot_page_id, environment=target_environment)

    def reorder_scene_pages(
        self,
        small_scene_id: str,
        page_ids: list[str],
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """Reorder scene pages of a small scene in a single transaction.

        Validates that page_ids exactly match the set of直属 scene pages
        (small_scene_id matches, branch_id IS NULL). Rejects:
        - missing IDs, duplicate IDs, IDs from other small_scenes
        - branch page IDs, non-existent IDs, empty list

        On success, sort_order is rewritten starting from 1.
        """
        if not page_ids:
            raise ValueError("排序页面列表不能为空")
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("排序页面列表包含重复 ID")
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            scene = connection.execute(
                "SELECT id FROM small_scenes WHERE id = ?", (small_scene_id,)
            ).fetchone()
            if not scene:
                raise ValueError("小场景不存在")
            # Fetch直属 scene pages (branch_id IS NULL)
            existing_rows = connection.execute(
                "SELECT id FROM shot_pages WHERE small_scene_id = ? AND branch_id IS NULL",
                (small_scene_id,),
            ).fetchall()
            existing_ids = {r["id"] for r in existing_rows}
            requested_set = set(page_ids)
            if requested_set != existing_ids:
                missing = existing_ids - requested_set
                extra = requested_set - existing_ids
                if missing:
                    raise ValueError("排序页面列表缺失页面")
                if extra:
                    # Check if any extra IDs are branch pages or belong to other small_scenes
                    for extra_id in extra:
                        row = connection.execute(
                            "SELECT small_scene_id, branch_id FROM shot_pages WHERE id = ?",
                            (extra_id,),
                        ).fetchone()
                        if not row:
                            raise ValueError(f"页面不存在: {extra_id}")
                        if row["branch_id"] is not None:
                            raise ValueError("排序页面列表包含分支页面")
                        if row["small_scene_id"] != small_scene_id:
                            raise ValueError("排序页面列表包含其他小场景的页面")
                    raise ValueError("排序页面列表包含非法页面")
            # All validation passed, perform the reorder in this single transaction
            for idx, pid in enumerate(page_ids, start=1):
                connection.execute(
                    "UPDATE shot_pages SET sort_order = ? WHERE id = ? AND small_scene_id = ? AND branch_id IS NULL",
                    (idx, pid, small_scene_id),
                )
        return self.list_shot_pages(small_scene_id, environment=target_environment)

    def move_shot_page(
        self,
        shot_page_id: str,
        target_sort_order: int,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id, small_scene_id, branch_id, sort_order FROM shot_pages WHERE id = ?",
                (shot_page_id,),
            ).fetchone()
            if not row:
                raise ValueError("分镜页不存在")
            current_order = row["sort_order"]
            if row["branch_id"] is None:
                scope_filter = "small_scene_id = ? AND branch_id IS NULL"
                scope_params: list[object] = [row["small_scene_id"]]
            else:
                scope_filter = "branch_id = ?"
                scope_params = [row["branch_id"]]
            siblings = connection.execute(
                f"SELECT id FROM shot_pages WHERE {scope_filter} ORDER BY sort_order ASC",
                scope_params,
            ).fetchall()
            total = len(siblings)
            target = max(1, min(target_sort_order, total))
            if current_order != target:
                connection.execute(
                    "UPDATE shot_pages SET sort_order = -1 WHERE id = ?",
                    (shot_page_id,),
                )
                if target < current_order:
                    connection.execute(
                        f"UPDATE shot_pages SET sort_order = sort_order + 1 WHERE {scope_filter} AND sort_order >= ? AND sort_order < ? AND id != ?",
                        scope_params + [target, current_order, shot_page_id],
                    )
                else:
                    connection.execute(
                        f"UPDATE shot_pages SET sort_order = sort_order - 1 WHERE {scope_filter} AND sort_order > ? AND sort_order <= ? AND id != ?",
                        scope_params + [current_order, target, shot_page_id],
                    )
                connection.execute(
                    "UPDATE shot_pages SET sort_order = ? WHERE id = ?",
                    (target, shot_page_id),
                )
        return self.get_shot_page(shot_page_id, environment=target_environment)  # type: ignore[return-value]

    def delete_shot_page(
        self,
        shot_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, small_scene_id, branch_id, title FROM shot_pages WHERE id = ?",
                (shot_page_id,),
            ).fetchone()
            if not existing:
                return None
            if existing["branch_id"] is None:
                scope_filter = "small_scene_id = ? AND branch_id IS NULL"
                scope_params: list[object] = [existing["small_scene_id"]]
            else:
                scope_filter = "branch_id = ?"
                scope_params = [existing["branch_id"]]
            connection.execute("DELETE FROM shot_pages WHERE id = ?", (shot_page_id,))
            remaining = connection.execute(
                f"SELECT id FROM shot_pages WHERE {scope_filter} ORDER BY sort_order ASC",
                scope_params,
            ).fetchall()
            for idx, r in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE shot_pages SET sort_order = ? WHERE id = ?",
                    (idx, r["id"]),
                )
        return {"id": shot_page_id, "title": existing["title"]}

    # ── Branches ───────────────────────────────────────────────────────

    def list_branches(
        self,
        parent_type: str,
        parent_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        if parent_type not in ("large_scene", "small_scene"):
            raise ValueError("分支父级类型无效，允许值: large_scene, small_scene")
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT b.id, b.parent_type, b.parent_id, b.name,
                       b.description, b.is_enabled, b.sort_order,
                       b.condition_type, b.condition_value, b.return_point,
                       b.created_at, b.updated_at,
                       (SELECT COUNT(*) FROM shot_pages sp
                        WHERE sp.branch_id = b.id) AS shot_page_count
                FROM branches b
                WHERE b.parent_type = ? AND b.parent_id = ?
                ORDER BY b.sort_order ASC
                """,
                (parent_type, parent_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_branch(
        self,
        branch_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, parent_type, parent_id, name,
                       description, is_enabled, sort_order,
                       condition_type, condition_value, return_point,
                       created_at, updated_at
                FROM branches WHERE id = ?
                """,
                (branch_id,),
            ).fetchone()
            if not row:
                return None
            result = dict(row)
            count = connection.execute(
                "SELECT COUNT(*) AS cnt FROM shot_pages WHERE branch_id = ?",
                (branch_id,),
            ).fetchone()
            result["shot_page_count"] = count["cnt"] if count else 0
        return result

    def create_branch(
        self,
        parent_type: str,
        parent_id: str,
        name: str,
        *,
        description: str = "",
        is_enabled: bool = True,
        condition_type: str = "",
        condition_value: str = "",
        return_point: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        if parent_type not in ("large_scene", "small_scene"):
            raise ValueError("分支父级类型无效，允许值: large_scene, small_scene")
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("分支名称不能为空")
        name = clean_name
        if len(name) > 80:
            raise ValueError("分支名称不能超过80字")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        branch_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            if parent_type == "large_scene":
                parent = connection.execute(
                    "SELECT id FROM large_scenes WHERE id = ?", (parent_id,)
                ).fetchone()
            else:
                parent = connection.execute(
                    "SELECT id FROM small_scenes WHERE id = ?", (parent_id,)
                ).fetchone()
            if not parent:
                raise ValueError("父级不存在")
            duplicate = connection.execute(
                "SELECT id FROM branches WHERE parent_type = ? AND parent_id = ? AND name = ? COLLATE NOCASE",
                (parent_type, parent_id, name),
            ).fetchone()
            if duplicate:
                raise ValueError("同一父级下已存在同名分支")
            max_order = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM branches WHERE parent_type = ? AND parent_id = ?",
                (parent_type, parent_id),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO branches (id, parent_type, parent_id, name,
                    description, is_enabled, sort_order,
                    condition_type, condition_value, return_point,
                    created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (branch_id, parent_type, parent_id, name,
                 description, 1 if is_enabled else 0,
                 max_order + 1,
                 condition_type, condition_value, return_point,
                 now, now),
            )
        return self.get_branch(branch_id, environment=target_environment)  # type: ignore[return-value]

    def update_branch(
        self,
        branch_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_enabled: bool | None = None,
        condition_type: str | None = None,
        condition_value: str | None = None,
        return_point: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        if all(v is None for v in (name, description, is_enabled,
                                   condition_type, condition_value, return_point)):
            raise ValueError("至少提供一个更新字段")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, parent_type, parent_id FROM branches WHERE id = ?",
                (branch_id,),
            ).fetchone()
            if not existing:
                return None
            sets: list[str] = []
            params: list[object] = []
            if name is not None:
                clean_name = " ".join(name.split())
                if not clean_name:
                    raise ValueError("分支名称不能为空")
                name = clean_name
                if len(name) > 80:
                    raise ValueError("分支名称不能超过80字")
                duplicate = connection.execute(
                    "SELECT id FROM branches WHERE parent_type = ? AND parent_id = ? AND name = ? COLLATE NOCASE AND id != ?",
                    (existing["parent_type"], existing["parent_id"], name, branch_id),
                ).fetchone()
                if duplicate:
                    raise ValueError("同一父级下已存在同名分支")
                sets.append("name = ?")
                params.append(name)
            if description is not None:
                sets.append("description = ?")
                params.append(description)
            if is_enabled is not None:
                sets.append("is_enabled = ?")
                params.append(1 if is_enabled else 0)
            if condition_type is not None:
                sets.append("condition_type = ?")
                params.append(condition_type)
            if condition_value is not None:
                sets.append("condition_value = ?")
                params.append(condition_value)
            if return_point is not None:
                sets.append("return_point = ?")
                params.append(return_point)
            sets.append("updated_at = ?")
            params.append(now)
            params.append(branch_id)
            connection.execute(
                f"UPDATE branches SET {', '.join(sets)} WHERE id = ?", params
            )
        return self.get_branch(branch_id, environment=target_environment)

    def delete_branch(
        self,
        branch_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, parent_type, parent_id, name FROM branches WHERE id = ?",
                (branch_id,),
            ).fetchone()
            if not existing:
                return None
            parent_type = existing["parent_type"]
            parent_id = existing["parent_id"]
            connection.execute("DELETE FROM shot_page_materials WHERE shot_page_id IN (SELECT id FROM shot_pages WHERE branch_id = ?)", (branch_id,))
            connection.execute("DELETE FROM shot_pages WHERE branch_id = ?", (branch_id,))
            connection.execute("DELETE FROM branches WHERE id = ?", (branch_id,))
            remaining = connection.execute(
                "SELECT id FROM branches WHERE parent_type = ? AND parent_id = ? ORDER BY sort_order ASC",
                (parent_type, parent_id),
            ).fetchall()
            for idx, r in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE branches SET sort_order = ? WHERE id = ?",
                    (idx, r["id"]),
                )
        return {"id": branch_id, "name": existing["name"]}

    # ── Small Scene Materials ──────────────────────────────────────────

    def list_small_scene_materials(
        self,
        small_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT m.id AS material_id, m.name, m.material_type, ssm.sort_order
                FROM small_scene_materials ssm
                JOIN materials m ON m.id = ssm.material_id
                WHERE ssm.small_scene_id = ?
                ORDER BY ssm.sort_order ASC
                """,
                (small_scene_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_small_scene_materials(
        self,
        small_scene_id: str,
        material_ids: list[str],
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Differential update preserving existing link_id for retained associations.

        - Retained materials keep their original `id` (link_id) and sort_order is updated.
        - Newly added materials get a new UUID as `id`.
        - Removed materials: their related small_scene_page_mappings (within this
          small_scene) are cascade-deleted, then the link row is deleted.
        - All operations run in a single transaction.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        seen: set[str] = set()
        unique_ids: list[str] = []
        for mid in material_ids:
            if mid not in seen:
                seen.add(mid)
                unique_ids.append(mid)
        with self._lock, self.connection(target_environment) as connection:
            scene = connection.execute(
                "SELECT id FROM small_scenes WHERE id = ?", (small_scene_id,)
            ).fetchone()
            if not scene:
                raise ValueError("小场景不存在")
            for mid in unique_ids:
                mat = connection.execute(
                    "SELECT id FROM materials WHERE id = ?", (mid,)
                ).fetchone()
                if not mat:
                    raise ValueError(f"素材不存在: {mid}")
            # Snapshot existing links: {material_id: link_id}
            existing_rows = connection.execute(
                "SELECT id, material_id FROM small_scene_materials WHERE small_scene_id = ?",
                (small_scene_id,),
            ).fetchall()
            existing_map: dict[str, str] = {r["material_id"]: r["id"] for r in existing_rows}
            existing_set = set(existing_map.keys())
            new_set = set(unique_ids)
            to_remove = existing_set - new_set
            to_add = [mid for mid in unique_ids if mid not in existing_set]
            # Order retained + new materials by user-supplied order
            ordered_materials = unique_ids
            # Cascade delete mappings for removed materials (only within this small_scene)
            if to_remove:
                removed_material_ids = list(to_remove)
                placeholders_rm = ",".join("?" * len(removed_material_ids))
                material_page_ids = [r["id"] for r in connection.execute(
                    f"SELECT id FROM material_pages WHERE material_id IN ({placeholders_rm})",
                    removed_material_ids,
                ).fetchall()]
                if material_page_ids:
                    placeholders_mp = ",".join("?" * len(material_page_ids))
                    connection.execute(
                        f"""DELETE FROM small_scene_page_mappings
                            WHERE material_page_id IN ({placeholders_mp})
                            AND scene_page_id IN (
                                SELECT id FROM shot_pages WHERE small_scene_id = ?
                            )""",
                        (*material_page_ids, small_scene_id),
                    )
                placeholders_rm_ids = ",".join("?" * len(removed_material_ids))
                connection.execute(
                    f"DELETE FROM small_scene_materials WHERE small_scene_id = ? AND material_id IN ({placeholders_rm_ids})",
                    (small_scene_id, *removed_material_ids),
                )
            # Insert new associations with generated id
            for mid in to_add:
                link_id = str(uuid4())
                connection.execute(
                    """INSERT INTO small_scene_materials (id, small_scene_id, material_id, sort_order, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (link_id, small_scene_id, mid, 0, now),
                )
            # Rewrite continuous sort_order for all retained + new associations
            for idx, mid in enumerate(ordered_materials, start=1):
                connection.execute(
                    "UPDATE small_scene_materials SET sort_order = ? WHERE small_scene_id = ? AND material_id = ?",
                    (idx, small_scene_id, mid),
                )
        materials = self.list_small_scene_materials(small_scene_id, environment=target_environment)
        return {"small_scene_id": small_scene_id, "materials": materials}

    # ── Shot Page Materials ────────────────────────────────────────────

    def list_shot_page_materials(
        self,
        shot_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT m.id AS material_id, m.name, m.material_type, spm.sort_order
                FROM shot_page_materials spm
                JOIN materials m ON m.id = spm.material_id
                WHERE spm.shot_page_id = ?
                ORDER BY spm.sort_order ASC
                """,
                (shot_page_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_shot_page_materials(
        self,
        shot_page_id: str,
        material_ids: list[str],
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        seen: set[str] = set()
        unique_ids: list[str] = []
        for mid in material_ids:
            if mid not in seen:
                seen.add(mid)
                unique_ids.append(mid)
        with self._lock, self.connection(target_environment) as connection:
            page = connection.execute(
                "SELECT id FROM shot_pages WHERE id = ?", (shot_page_id,)
            ).fetchone()
            if not page:
                raise ValueError("分镜页不存在")
            for mid in unique_ids:
                mat = connection.execute(
                    "SELECT id FROM materials WHERE id = ?", (mid,)
                ).fetchone()
                if not mat:
                    raise ValueError(f"素材不存在: {mid}")
            connection.execute(
                "DELETE FROM shot_page_materials WHERE shot_page_id = ?",
                (shot_page_id,),
            )
            for idx, mid in enumerate(unique_ids, start=1):
                connection.execute(
                    """
                    INSERT INTO shot_page_materials (shot_page_id, material_id, sort_order, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (shot_page_id, mid, idx, now),
                )
        materials = self.list_shot_page_materials(shot_page_id, environment=target_environment)
        return {"shot_page_id": shot_page_id, "materials": materials}

    def database_info(self, environment: DatabaseEnvironment) -> dict[str, object]:
        descriptor = self.descriptor(environment)
        with self.connection(environment) as connection:
            initialized = connection.execute(
                "SELECT value FROM atelier_meta WHERE key = 'initialized_at'"
            ).fetchone()
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        return {
            "environment": environment,
            "active": environment == self._active_environment,
            "locked": environment == self._locked_environment,
            "path": str(descriptor.path),
            "purpose": descriptor.purpose,
            "exists": descriptor.path.exists(),
            "size_bytes": descriptor.path.stat().st_size if descriptor.path.exists() else 0,
            "initialized_at": initialized["value"] if initialized else None,
            "journal_mode": str(journal_mode).upper(),
            "event_count": self.event_count(environment),
            "project_count": self.list_projects(environment=environment)["total"],
        }

    def verify_isolation(self) -> dict[str, object]:
        """Write only to test and prove that the production row count is unchanged."""
        with self._lock:
            production_before = self.event_count("production")
            test_before = self.event_count("test")
            marker = f"isolation-check-{datetime.now(timezone.utc).timestamp()}"
            self.record_event("isolation_check", marker, environment="test")
            production_after = self.event_count("production")
            test_after = self.event_count("test")
        isolated = (
            production_before == production_after and test_after == test_before + 1
        )
        if not isolated:
            raise DatabaseSafetyError("Database isolation verification failed.")
        return {
            "isolated": True,
            "production_rows_before": production_before,
            "production_rows_after": production_after,
            "test_rows_before": test_before,
            "test_rows_after": test_after,
        }

    def clear_environment_data(
        self, environment: DatabaseEnvironment
    ) -> dict[str, object]:
        """Delete application rows while preserving the database identity metadata."""
        target_environment = self._validate_environment(environment)
        with self._lock, self.connection(target_environment) as connection:
            table_rows = connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                  AND name <> 'atelier_meta'
                ORDER BY name
                """
            ).fetchall()
            deleted: dict[str, int] = {}
            for row in table_rows:
                table_name = str(row["name"])
                quoted_name = table_name.replace('"', '""')
                before = connection.execute(
                    f'SELECT COUNT(*) AS count FROM "{quoted_name}"'
                ).fetchone()
                connection.execute(f'DELETE FROM "{quoted_name}"')
                deleted[table_name] = int(before["count"])
            connection.execute(
                "DELETE FROM sqlite_sequence WHERE name <> 'atelier_meta'"
            )
        return {
            "environment": target_environment,
            "deleted": deleted,
            "preserved_tables": ["atelier_meta"],
        }

    # ── Story Tree (v0.4.1) ────────────────────────────────────────────

    def get_story_tree(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Aggregate 4-level tree: chapters → large_scenes → small_scenes → shot_pages.

        Uses batch queries to avoid N+1.
        Each small_scene includes:
        - pages: shot_pages (with `name` field)
        - resources: associated materials (with link_id, material_id, name, material_type, pages)
        - page_count, resource_count: counts
        """
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            proj = connection.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not proj:
                return None

            chapters = connection.execute(
                """SELECT id, project_id, name, sort_order, created_at, updated_at
                   FROM chapters WHERE project_id = ? ORDER BY sort_order ASC""",
                (project_id,),
            ).fetchall()
            chapter_ids = [c["id"] for c in chapters]

            large_scenes: list[dict[str, object]] = []
            small_scenes: list[dict[str, object]] = []
            shot_pages: list[dict[str, object]] = []
            scene_resources: list[dict[str, object]] = []
            material_page_rows: list[dict[str, object]] = []
            branches_rows: list[sqlite3.Row] = []
            branch_pages_map: dict[str, list[dict[str, object]]] = {}

            if chapter_ids:
                placeholders = ",".join("?" * len(chapter_ids))
                large_scenes_rows = connection.execute(
                    f"""SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                        FROM large_scenes WHERE chapter_id IN ({placeholders}) ORDER BY sort_order ASC""",
                    chapter_ids,
                ).fetchall()
                large_scenes = [dict(r) for r in large_scenes_rows]
                large_scene_ids = [ls["id"] for ls in large_scenes]

                if large_scene_ids:
                    placeholders_ls = ",".join("?" * len(large_scene_ids))
                    small_scenes_rows = connection.execute(
                        f"""SELECT id, large_scene_id, name, scene_type, description, sort_order, created_at, updated_at
                            FROM small_scenes WHERE large_scene_id IN ({placeholders_ls}) ORDER BY sort_order ASC""",
                        large_scene_ids,
                    ).fetchall()
                    small_scenes = [dict(r) for r in small_scenes_rows]
                    small_scene_ids = [ss["id"] for ss in small_scenes]

                    if small_scene_ids:
                        placeholders_ss = ",".join("?" * len(small_scene_ids))
                        shot_pages_rows = connection.execute(
                            f"""SELECT id, small_scene_id, branch_id, title, description, prompt_text, negative_prompt,
                                       sort_order, created_at, updated_at
                                FROM shot_pages
                                WHERE small_scene_id IN ({placeholders_ss}) AND branch_id IS NULL
                                ORDER BY sort_order ASC""",
                            small_scene_ids,
                        ).fetchall()
                        # Rename title → name for frontend contract
                        shot_pages = []
                        for r in shot_pages_rows:
                            p = dict(r)
                            p["name"] = p.pop("title")
                            shot_pages.append(p)

                        # Fetch branches under these small_scenes (v0.5.4 story-tree enhancement)
                        branches_rows = connection.execute(
                            f"""SELECT id, parent_type, parent_id, name,
                                       condition_type, condition_value, is_enabled,
                                       sort_order, created_at, updated_at
                                FROM branches
                                WHERE parent_type = 'small_scene'
                                  AND parent_id IN ({placeholders_ss})
                                ORDER BY sort_order ASC""",
                            small_scene_ids,
                        ).fetchall()
                        all_branch_ids = [b["id"] for b in branches_rows]
                        if all_branch_ids:
                            placeholders_b = ",".join("?" * len(all_branch_ids))
                            bp_rows = connection.execute(
                                f"""SELECT id, small_scene_id, branch_id, title, description, prompt_text, negative_prompt,
                                           sort_order, created_at, updated_at
                                    FROM shot_pages
                                    WHERE branch_id IN ({placeholders_b})
                                    ORDER BY sort_order ASC""",
                                    all_branch_ids,
                            ).fetchall()
                            for r in bp_rows:
                                p = dict(r)
                                p["name"] = p.pop("title")
                                branch_pages_map.setdefault(p["branch_id"], []).append(p)

                        # Batch query resources (small_scene_materials + materials)
                        resources_rows = connection.execute(
                            f"""SELECT ssm.id AS link_id, ssm.small_scene_id, ssm.material_id, ssm.sort_order,
                                       m.name, m.material_type, m.description, m.prompt_text, m.negative_prompt
                                FROM small_scene_materials ssm
                                JOIN materials m ON m.id = ssm.material_id
                                WHERE ssm.small_scene_id IN ({placeholders_ss})
                                ORDER BY ssm.sort_order ASC""",
                            small_scene_ids,
                        ).fetchall()
                        scene_resources = [dict(r) for r in resources_rows]

                        # Batch query material_pages for all referenced materials
                        material_ids = list({r["material_id"] for r in scene_resources})
                        if material_ids:
                            placeholders_m = ",".join("?" * len(material_ids))
                            material_page_rows = [
                                dict(r) for r in connection.execute(
                                    f"""SELECT id, material_id, name, description, content, prompt_text, negative_prompt,
                                               sort_order, created_at, updated_at
                                        FROM material_pages
                                        WHERE material_id IN ({placeholders_m})
                                        ORDER BY sort_order ASC""",
                                    material_ids,
                                ).fetchall()
                            ]

            # Group pages by scene
            pages_by_scene: dict[str, list[dict[str, object]]] = {}
            for p in shot_pages:
                pages_by_scene.setdefault(p["small_scene_id"], []).append(p)

            # Group branches by parent small_scene (v0.5.4 story-tree enhancement)
            branches_by_scene: dict[str, list[dict[str, object]]] = {}
            for b in branches_rows:
                b_dict = dict(b)
                b_dict["is_enabled"] = bool(b_dict["is_enabled"])
                b_dict["pages"] = branch_pages_map.get(b_dict["id"], [])
                branches_by_scene.setdefault(b_dict["parent_id"], []).append(b_dict)

            # Group material_pages by material_id
            mp_by_material: dict[str, list[dict[str, object]]] = {}
            for mp in material_page_rows:
                mp_by_material.setdefault(mp["material_id"], []).append(mp)

            # Group resources by scene, attach pages to each resource
            resources_by_scene: dict[str, list[dict[str, object]]] = {}
            for r in scene_resources:
                r_pages = mp_by_material.get(r["material_id"], [])
                r["pages"] = r_pages
                r["page_count"] = len(r_pages)
                resources_by_scene.setdefault(r["small_scene_id"], []).append(r)

            scenes_by_large: dict[str, list[dict[str, object]]] = {}
            for s in small_scenes:
                s_pages = pages_by_scene.get(s["id"], [])
                s_resources = resources_by_scene.get(s["id"], [])
                s_branches = branches_by_scene.get(s["id"], [])
                s["pages"] = s_pages
                s["resources"] = s_resources
                s["branches"] = s_branches
                s["page_count"] = len(s_pages)
                s["resource_count"] = len(s_resources)
                scenes_by_large.setdefault(s["large_scene_id"], []).append(s)

            large_by_chapter: dict[str, list[dict[str, object]]] = {}
            for ls in large_scenes:
                ls["small_scenes"] = scenes_by_large.get(ls["id"], [])
                large_by_chapter.setdefault(ls["chapter_id"], []).append(ls)

            chapters_list: list[dict[str, object]] = []
            for c in chapters:
                c_dict = dict(c)
                c_dict["large_scenes"] = large_by_chapter.get(c["id"], [])
                chapters_list.append(c_dict)

            return {
                "project_id": project_id,
                "chapters": chapters_list,
                "backendAvailable": True,
            }

    # ── Small Scene Workspace (v0.4.1) ─────────────────────────────────

    def get_small_scene_workspace(
        self,
        small_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Aggregate workspace data: small_scene + pages + resources + mappings.

        Field contract for frontend:
        - pages: shot_pages with `name` (renamed from title)
        - resources: each resource includes `link_id`, `pages` (material_pages of that material)
        - mappings: includes material_page_name, material_id
        - chapter, large_scene: parent info for breadcrumb
        """
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            scene_row = connection.execute(
                """SELECT id, large_scene_id, name, scene_type, description, sort_order, created_at, updated_at
                   FROM small_scenes WHERE id = ?""",
                (small_scene_id,),
            ).fetchone()
            if not scene_row:
                return None
            small_scene = dict(scene_row)

            # Fetch parent chapter & large_scene for breadcrumb
            large_scene_row = connection.execute(
                """SELECT id, chapter_id, name, scene_type
                   FROM large_scenes WHERE id = ?""",
                (small_scene["large_scene_id"],),
            ).fetchone()
            chapter = None
            large_scene = None
            if large_scene_row:
                large_scene = dict(large_scene_row)
                chapter_row = connection.execute(
                    """SELECT id, project_id, name
                       FROM chapters WHERE id = ?""",
                    (large_scene["chapter_id"],),
                ).fetchone()
                if chapter_row:
                    chapter = dict(chapter_row)

            pages_rows = connection.execute(
                """SELECT id, small_scene_id, title, description, prompt_text, negative_prompt,
                          sort_order, created_at, updated_at
                   FROM shot_pages
                   WHERE small_scene_id = ? AND branch_id IS NULL
                   ORDER BY sort_order ASC""",
                (small_scene_id,),
            ).fetchall()
            # Rename title → name for frontend contract
            pages: list[dict[str, object]] = []
            for r in pages_rows:
                p = dict(r)
                p["name"] = p.pop("title")
                pages.append(p)
            page_ids = [p["id"] for p in pages]

            resources_rows = connection.execute(
                """SELECT ssm.id AS link_id, ssm.material_id, ssm.sort_order,
                          m.name, m.material_type, m.description, m.prompt_text, m.negative_prompt
                   FROM small_scene_materials ssm
                   JOIN materials m ON m.id = ssm.material_id
                   WHERE ssm.small_scene_id = ?
                   ORDER BY ssm.sort_order ASC""",
                (small_scene_id,),
            ).fetchall()
            resources = [dict(r) for r in resources_rows]

            # Fetch material_pages for each resource (batch query)
            material_ids = [r["material_id"] for r in resources]
            resource_pages_map: dict[str, list[dict[str, object]]] = {}
            if material_ids:
                placeholders_m = ",".join("?" * len(material_ids))
                mp_rows = connection.execute(
                    f"""SELECT id, material_id, name, description, content, prompt_text, negative_prompt,
                               sort_order, created_at, updated_at
                        FROM material_pages
                        WHERE material_id IN ({placeholders_m})
                        ORDER BY sort_order ASC""",
                    material_ids,
                ).fetchall()
                for mp in mp_rows:
                    resource_pages_map.setdefault(mp["material_id"], []).append(dict(mp))
            for r in resources:
                r["pages"] = resource_pages_map.get(r["material_id"], [])

            mappings: list[dict[str, object]] = []
            if page_ids:
                placeholders = ",".join("?" * len(page_ids))
                mapping_rows = connection.execute(
                    f"""SELECT sspm.id, sspm.scene_page_id, sspm.material_page_id, sspm.material_type,
                               mp.name AS material_page_name, mp.material_id,
                               sspm.created_at, sspm.updated_at
                        FROM small_scene_page_mappings sspm
                        JOIN material_pages mp ON mp.id = sspm.material_page_id
                        WHERE sspm.scene_page_id IN ({placeholders})
                        ORDER BY sspm.created_at ASC""",
                    page_ids,
                ).fetchall()
                mappings = [dict(r) for r in mapping_rows]

            return {
                "small_scene": small_scene,
                "chapter": chapter,
                "large_scene": large_scene,
                "pages": pages,
                "resources": resources,
                "mappings": mappings,
            }

    # ── Material Pages (v0.4.1) ────────────────────────────────────────

    def list_material_pages(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """SELECT id, material_id, name, description, content, prompt_text, negative_prompt,
                          preview_original_path, preview_thumbnail_path, source_page_id,
                          sort_order, created_at, updated_at
                   FROM material_pages
                   WHERE material_id = ?
                   ORDER BY sort_order ASC""",
                (material_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_material_page(
        self,
        material_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """SELECT id, material_id, name, description, content, prompt_text, negative_prompt,
                          preview_original_path, preview_thumbnail_path, source_page_id,
                          sort_order, created_at, updated_at
                   FROM material_pages WHERE id = ?""",
                (material_page_id,),
            ).fetchone()
            if not row:
                return None
            return dict(row)

    def create_material_page(
        self,
        material_id: str,
        name: str,
        *,
        description: str = "",
        content: str = "",
        prompt_text: str = "",
        negative_prompt: str = "",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        if not name or not name.strip():
            raise ValueError("素材页名称不能为空")
        name = name.strip()
        if len(name) > 120:
            raise ValueError("素材页名称不能超过120字")
        if len(description) > 500:
            raise ValueError("素材页描述不能超过500字")
        if len(content) > 50000:
            raise ValueError("素材页内容不能超过50000字")
        if len(prompt_text) > 50000:
            raise ValueError("正向提示词不能超过50000字")
        if len(negative_prompt) > 20000:
            raise ValueError("负向提示词不能超过20000字")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        page_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            mat = connection.execute(
                "SELECT id FROM materials WHERE id = ?", (material_id,)
            ).fetchone()
            if not mat:
                raise ValueError("素材不存在")
            duplicate = connection.execute(
                "SELECT id FROM material_pages WHERE material_id = ? AND name = ? COLLATE NOCASE",
                (material_id, name),
            ).fetchone()
            if duplicate:
                raise ValueError("同素材下已存在同名素材页")
            max_order = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM material_pages WHERE material_id = ?",
                (material_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO material_pages
                   (id, material_id, name, description, content, prompt_text, negative_prompt, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (page_id, material_id, name, description, content, prompt_text, negative_prompt,
                 max_order + 1, now, now),
            )
        return self.get_material_page(page_id, environment=target_environment)  # type: ignore[return-value]

    def update_material_page(
        self,
        material_page_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        content: str | None = None,
        prompt_text: str | None = None,
        negative_prompt: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        if all(v is None for v in (name, description, content, prompt_text, negative_prompt)):
            raise ValueError("至少提供一个更新字段")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, material_id FROM material_pages WHERE id = ?",
                (material_page_id,),
            ).fetchone()
            if not existing:
                return None
            sets: list[str] = []
            params: list[object] = []
            if name is not None:
                if not name.strip():
                    raise ValueError("素材页名称不能为空")
                name = name.strip()
                if len(name) > 120:
                    raise ValueError("素材页名称不能超过120字")
                duplicate = connection.execute(
                    "SELECT id FROM material_pages WHERE material_id = ? AND name = ? COLLATE NOCASE AND id != ?",
                    (existing["material_id"], name, material_page_id),
                ).fetchone()
                if duplicate:
                    raise ValueError("同素材下已存在同名素材页")
                sets.append("name = ?")
                params.append(name)
            if description is not None:
                if len(description) > 500:
                    raise ValueError("素材页描述不能超过500字")
                sets.append("description = ?")
                params.append(description)
            if content is not None:
                if len(content) > 50000:
                    raise ValueError("素材页内容不能超过50000字")
                sets.append("content = ?")
                params.append(content)
            if prompt_text is not None:
                if len(prompt_text) > 50000:
                    raise ValueError("正向提示词不能超过50000字")
                sets.append("prompt_text = ?")
                params.append(prompt_text)
            if negative_prompt is not None:
                if len(negative_prompt) > 20000:
                    raise ValueError("负向提示词不能超过20000字")
                sets.append("negative_prompt = ?")
                params.append(negative_prompt)
            sets.append("updated_at = ?")
            params.append(now)
            params.append(material_page_id)
            connection.execute(
                f"UPDATE material_pages SET {', '.join(sets)} WHERE id = ?", params
            )
        return self.get_material_page(material_page_id, environment=target_environment)

    def delete_material_page(
        self,
        material_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, material_id, name FROM material_pages WHERE id = ?",
                (material_page_id,),
            ).fetchone()
            if not existing:
                return None
            material_id = existing["material_id"]
            connection.execute("DELETE FROM material_pages WHERE id = ?", (material_page_id,))
            remaining = connection.execute(
                "SELECT id FROM material_pages WHERE material_id = ? ORDER BY sort_order ASC",
                (material_id,),
            ).fetchall()
            for idx, r in enumerate(remaining, start=1):
                connection.execute(
                    "UPDATE material_pages SET sort_order = ? WHERE id = ?",
                    (idx, r["id"]),
                )
        return {"id": material_page_id, "name": existing["name"]}

    def reorder_material_pages(
        self,
        material_id: str,
        page_ids: list[str],
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            for idx, pid in enumerate(page_ids, start=1):
                connection.execute(
                    "UPDATE material_pages SET sort_order = ? WHERE id = ? AND material_id = ?",
                    (idx, pid, material_id),
                )
        return self.list_material_pages(material_id, environment=target_environment)

    # ── Small Scene Resources (v0.4.1) ─────────────────────────────────

    def add_small_scene_resource(
        self,
        small_scene_id: str,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Associate a material with a small scene. Returns the link record with link_id."""
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        link_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            scene = connection.execute(
                "SELECT id FROM small_scenes WHERE id = ?", (small_scene_id,)
            ).fetchone()
            if not scene:
                raise ValueError("小场景不存在")
            mat = connection.execute(
                "SELECT id FROM materials WHERE id = ?", (material_id,)
            ).fetchone()
            if not mat:
                raise ValueError("素材不存在")
            existing = connection.execute(
                "SELECT id FROM small_scene_materials WHERE small_scene_id = ? AND material_id = ?",
                (small_scene_id, material_id),
            ).fetchone()
            if existing:
                raise ValueError("该素材已关联到此小场景")
            max_order = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM small_scene_materials WHERE small_scene_id = ?",
                (small_scene_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO small_scene_materials (id, small_scene_id, material_id, sort_order, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (link_id, small_scene_id, material_id, max_order + 1, now),
            )
        return {"link_id": link_id, "small_scene_id": small_scene_id, "material_id": material_id}

    def remove_small_scene_resource_link(
        self,
        link_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Remove a material association by link_id (the stable id of small_scene_materials).

        Also cascade-deletes all small_scene_page_mappings that reference material_pages
        belonging to this material, for any scene_page within the same small_scene.
        Returns deleted_mapping_count for the API contract.
        """
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, small_scene_id, material_id FROM small_scene_materials WHERE id = ?",
                (link_id,),
            ).fetchone()
            if not existing:
                return None
            small_scene_id = existing["small_scene_id"]
            material_id = existing["material_id"]
            # Cascade delete mappings: find all material_pages of this material,
            # then delete mappings that reference those pages AND belong to scene_pages
            # within this same small_scene.
            material_page_ids = [r["id"] for r in connection.execute(
                "SELECT id FROM material_pages WHERE material_id = ?", (material_id,)
            ).fetchall()]
            deleted_mapping_count = 0
            if material_page_ids:
                placeholders = ",".join("?" * len(material_page_ids))
                cursor = connection.execute(
                    f"""DELETE FROM small_scene_page_mappings
                        WHERE material_page_id IN ({placeholders})
                        AND scene_page_id IN (
                            SELECT id FROM shot_pages WHERE small_scene_id = ?
                        )""",
                    (*material_page_ids, small_scene_id),
                )
                deleted_mapping_count = cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
            connection.execute(
                "DELETE FROM small_scene_materials WHERE id = ?", (link_id,)
            )
        return {
            "link_id": link_id,
            "small_scene_id": small_scene_id,
            "material_id": material_id,
            "deleted_mapping_count": deleted_mapping_count,
        }

    # ── Small Scene Page Mappings (v0.4.1) ─────────────────────────────

    def list_small_scene_page_mappings(
        self,
        scene_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """SELECT sspm.id, sspm.scene_page_id, sspm.material_page_id, sspm.material_type,
                          mp.name AS material_page_name, mp.material_id,
                          sspm.created_at, sspm.updated_at
                   FROM small_scene_page_mappings sspm
                   JOIN material_pages mp ON mp.id = sspm.material_page_id
                   WHERE sspm.scene_page_id = ?
                   ORDER BY sspm.created_at ASC""",
                (scene_page_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def set_small_scene_page_mapping(
        self,
        scene_page_id: str,
        material_type: str,
        material_page_id: str | None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Set or replace the mapping for (scene_page_id, material_type).

        Third-round contract (2026-07-29):
        - Validation order: material_type -> scene_page existence -> branch_id check -> material_page handling.
        - Branch pages (branch_id IS NOT NULL) are rejected with 422 for both set and cancel.
        - Non-existent pages are rejected with 404 for both set and cancel.
        - If material_page_id is None, removes the mapping (PUT + null contract).
          Returns None to signal the API layer that the response should be `mapping: null`.
        - Validates that the material is already associated to the same small_scene.
        - Atomic replace: deletes existing mapping with same (scene_page_id, material_type),
          then inserts new one.
        """
        valid_types = ('composition', 'expression', 'scene', 'lighting', 'prompt', 'composite_template')
        if material_type not in valid_types:
            raise ValueError(f"素材类型无效，允许值: {', '.join(valid_types)}")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        mapping_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            page = connection.execute(
                "SELECT id, small_scene_id, branch_id FROM shot_pages WHERE id = ?",
                (scene_page_id,),
            ).fetchone()
            if not page:
                raise ValueError("场景页不存在")
            if page["branch_id"] is not None:
                raise ValueError("分支页面不能设置素材页映射")
            small_scene_id = page["small_scene_id"]
            if material_page_id is None:
                connection.execute(
                    "DELETE FROM small_scene_page_mappings WHERE scene_page_id = ? AND material_type = ?",
                    (scene_page_id, material_type),
                )
                return None
            mp = connection.execute(
                "SELECT id, material_id FROM material_pages WHERE id = ?",
                (material_page_id,),
            ).fetchone()
            if not mp:
                raise ValueError("素材页不存在")
            mat = connection.execute(
                "SELECT material_type FROM materials WHERE id = ?",
                (mp["material_id"],),
            ).fetchone()
            if not mat:
                raise ValueError("素材不存在")
            if mat["material_type"] != material_type:
                raise ValueError(f"素材页所属素材类型({mat['material_type']})与指定类型({material_type})不匹配")
            link = connection.execute(
                "SELECT id FROM small_scene_materials WHERE small_scene_id = ? AND material_id = ?",
                (small_scene_id, mp["material_id"]),
            ).fetchone()
            if not link:
                raise ValueError("该素材尚未关联到此小场景，不能设置映射")
            connection.execute(
                "DELETE FROM small_scene_page_mappings WHERE scene_page_id = ? AND material_type = ?",
                (scene_page_id, material_type),
            )
            connection.execute(
                """INSERT INTO small_scene_page_mappings
                   (id, scene_page_id, material_page_id, material_type, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (mapping_id, scene_page_id, material_page_id, material_type, now, now),
            )
        return {
            "id": mapping_id,
            "scene_page_id": scene_page_id,
            "material_page_id": material_page_id,
            "material_type": material_type,
        }

    def unset_small_scene_page_mapping(
        self,
        scene_page_id: str,
        material_type: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Remove the mapping for (scene_page_id, material_type). Returns None if no mapping existed."""
        valid_types = ('composition', 'expression', 'scene', 'lighting', 'prompt', 'composite_template')
        if material_type not in valid_types:
            raise ValueError(f"素材类型无效，允许值: {', '.join(valid_types)}")
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id, scene_page_id, material_page_id, material_type FROM small_scene_page_mappings "
                "WHERE scene_page_id = ? AND material_type = ?",
                (scene_page_id, material_type),
            ).fetchone()
            if not existing:
                return None
            connection.execute(
                "DELETE FROM small_scene_page_mappings WHERE scene_page_id = ? AND material_type = ?",
                (scene_page_id, material_type),
            )
        return dict(existing)

    # ── Material Lifecycle (v0.5.2) ───────────────────────────────────

    _MATERIAL_SELECT_COLUMNS = (
        "id, name, material_type, description, content, "
        "prompt_text, negative_prompt, validation_status, notes, "
        "preview_original_path, preview_thumbnail_path, "
        "archived_at, deleted_at, source_material_id, "
        "revision, created_at, updated_at"
    )

    def archive_material(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Archive a material: set archived_at.

        Returns the updated material dict, or None if the material does not exist.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM materials WHERE id = ? AND deleted_at IS NULL",
                (material_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE materials SET archived_at = ?, updated_at = ? WHERE id = ?",
                (now, now, material_id),
            )
            row = connection.execute(
                f"SELECT {self._MATERIAL_SELECT_COLUMNS} FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
        return dict(row) if row else None

    def restore_material(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Restore an archived or soft-deleted material.

        Clears both archived_at and deleted_at.
        Returns the updated material dict, or None if the material does not exist.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE materials SET archived_at = NULL, deleted_at = NULL, updated_at = ? WHERE id = ?",
                (now, material_id),
            )
            row = connection.execute(
                f"SELECT {self._MATERIAL_SELECT_COLUMNS} FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
        return dict(row) if row else None

    def soft_delete_material(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Soft-delete a material: set deleted_at to current UTC time.

        Does not actually remove data. Returns the updated material dict,
        or None if the material does not exist.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM materials WHERE id = ? AND deleted_at IS NULL",
                (material_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE materials SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, material_id),
            )
            row = connection.execute(
                f"SELECT {self._MATERIAL_SELECT_COLUMNS} FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_deleted_materials(
        self,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """List all soft-deleted materials (deleted_at IS NOT NULL)."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                f"""
                SELECT {self._MATERIAL_SELECT_COLUMNS}
                FROM materials
                WHERE deleted_at IS NOT NULL
                ORDER BY deleted_at DESC
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    def permanent_delete_material(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Permanently delete a material and all its dependencies.

        Explicitly deletes: small_scene_page_mappings (via material_page_id),
        material_pages, material_versions, small_scene_materials,
        shot_page_materials, material_tag_links, and the material itself.
        Returns a dict with deleted info and preview paths, or None if not found.
        """
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id, preview_original_path, preview_thumbnail_path FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if row is None:
                return None
            # Collect material_page ids for mapping cleanup
            page_ids = [r["id"] for r in connection.execute(
                "SELECT id FROM material_pages WHERE material_id = ?",
                (material_id,),
            ).fetchall()]
            if page_ids:
                placeholders = ",".join("?" * len(page_ids))
                connection.execute(
                    f"DELETE FROM small_scene_page_mappings WHERE material_page_id IN ({placeholders})",
                    page_ids,
                )
            connection.execute(
                "DELETE FROM material_pages WHERE material_id = ?",
                (material_id,),
            )
            connection.execute(
                "DELETE FROM material_versions WHERE material_id = ?",
                (material_id,),
            )
            connection.execute(
                "DELETE FROM small_scene_materials WHERE material_id = ?",
                (material_id,),
            )
            connection.execute(
                "DELETE FROM shot_page_materials WHERE material_id = ?",
                (material_id,),
            )
            connection.execute(
                "DELETE FROM material_tag_links WHERE material_id = ?",
                (material_id,),
            )
            connection.execute(
                "DELETE FROM materials WHERE id = ?",
                (material_id,),
            )
        return {
            "deleted": True,
            "material_id": material_id,
            "preview_original_path": row["preview_original_path"],
            "preview_thumbnail_path": row["preview_thumbnail_path"],
        }

    def get_material_references(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Return all references to a material from projects, small scenes, and scene pages.

        Returns None if the material does not exist.
        """
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if existing is None:
                return None
            small_scenes = [dict(r) for r in connection.execute(
                """
                SELECT DISTINCT ss.id, ss.name,
                       ls.id AS large_scene_id, ls.name AS large_scene_name,
                       c.id AS chapter_id, c.name AS chapter_name,
                       p.id AS project_id, p.name AS project_name
                FROM small_scene_materials ssm
                JOIN small_scenes ss ON ss.id = ssm.small_scene_id
                JOIN large_scenes ls ON ls.id = ss.large_scene_id
                JOIN chapters c ON c.id = ls.chapter_id
                JOIN projects p ON p.id = c.project_id
                WHERE ssm.material_id = ?
                ORDER BY p.name, ss.name
                """,
                (material_id,),
            ).fetchall()]
            scene_pages = [dict(r) for r in connection.execute(
                """
                SELECT DISTINCT sp.id, sp.title AS name,
                       ss.id AS small_scene_id, ss.name AS small_scene_name,
                       sspm.material_type
                FROM small_scene_page_mappings sspm
                JOIN material_pages mp ON mp.id = sspm.material_page_id
                JOIN shot_pages sp ON sp.id = sspm.scene_page_id
                JOIN small_scenes ss ON ss.id = sp.small_scene_id
                WHERE mp.material_id = ?
                ORDER BY ss.name, sp.title
                """,
                (material_id,),
            ).fetchall()]
        # Deduplicate projects
        seen_projects: set[str] = set()
        projects: list[dict[str, object]] = []
        for ss in small_scenes:
            pid = ss["project_id"]
            if pid not in seen_projects:
                seen_projects.add(pid)
                projects.append({"id": pid, "name": ss["project_name"]})
        total_count = len(small_scenes) + len(scene_pages)
        return {
            "small_scenes": small_scenes,
            "scene_pages": scene_pages,
            "projects": projects,
            "total_count": total_count,
        }

    # ── Material Page Preview (v0.5.2) ─────────────────────────────────

    def set_material_page_preview_paths(
        self,
        material_page_id: str,
        *,
        original_path: str | None,
        thumbnail_path: str | None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Set preview paths for a material page. Returns the updated page, or None."""
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            row = connection.execute(
                "SELECT id FROM material_pages WHERE id = ?",
                (material_page_id,),
            ).fetchone()
            if row is None:
                return None
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """
                UPDATE material_pages
                SET preview_original_path = ?, preview_thumbnail_path = ?, updated_at = ?
                WHERE id = ?
                """,
                (original_path, thumbnail_path, now, material_page_id),
            )
        return self.get_material_page(material_page_id, environment=target_environment)

    def copy_material_page(
        self,
        material_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Copy a material page. Returns the new page, or None if source not found.

        Name gets " 副本" suffix; if that exists, a sequence number is appended.
        sort_order is set to max+1. source_page_id is set to the source page id.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        new_page_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            source = connection.execute(
                """SELECT id, material_id, name, description, content, prompt_text,
                          negative_prompt, sort_order
                   FROM material_pages WHERE id = ?""",
                (material_page_id,),
            ).fetchone()
            if source is None:
                return None
            material_id = source["material_id"]
            base_name = source["name"]
            candidate = f"{base_name} 副本"
            suffix = 2
            while connection.execute(
                "SELECT id FROM material_pages WHERE material_id = ? AND name = ? COLLATE NOCASE",
                (material_id, candidate),
            ).fetchone():
                candidate = f"{base_name} 副本 {suffix}"
                suffix += 1
            max_order = connection.execute(
                "SELECT COALESCE(MAX(sort_order), 0) FROM material_pages WHERE material_id = ?",
                (material_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO material_pages
                   (id, material_id, name, description, content, prompt_text,
                    negative_prompt, preview_original_path, preview_thumbnail_path,
                    source_page_id, sort_order, revision, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, 1, ?, ?)""",
                (new_page_id, material_id, candidate, source["description"],
                 source["content"], source["prompt_text"], source["negative_prompt"],
                 source["id"], max_order + 1, now, now),
            )
        return self.get_material_page(new_page_id, environment=target_environment)

    # ── Material Versions (v0.5.2) ─────────────────────────────────────

    def create_material_version(
        self,
        material_id: str,
        *,
        label: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Create a version snapshot of the material and its pages.

        snapshot is a JSON string containing all material fields and pages list.
        version_number auto-increments. Returns the version record, or None if not found.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        version_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if existing is None:
                return None
            material_row = connection.execute(
                f"SELECT {self._MATERIAL_SELECT_COLUMNS} FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if material_row is None:
                return None
            material_data = dict(material_row)
            pages = [dict(r) for r in connection.execute(
                """SELECT id, name, description, content, prompt_text, negative_prompt,
                          preview_original_path, preview_thumbnail_path, source_page_id,
                          sort_order, created_at, updated_at
                   FROM material_pages WHERE material_id = ?
                   ORDER BY sort_order ASC""",
                (material_id,),
            ).fetchall()]
            snapshot = json.dumps(
                {"material": material_data, "pages": pages},
                ensure_ascii=False,
            )
            max_version = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) FROM material_versions WHERE material_id = ?",
                (material_id,),
            ).fetchone()[0]
            version_number = max_version + 1
            connection.execute(
                """INSERT INTO material_versions (id, material_id, version_number, snapshot, label, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (version_id, material_id, version_number, snapshot, label, now),
            )
        return {
            "id": version_id,
            "material_id": material_id,
            "version_number": version_number,
            "label": label,
            "created_at": now,
        }

    def list_material_versions(
        self,
        material_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """List all versions of a material (without snapshot)."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """SELECT id, material_id, version_number, label, created_at
                   FROM material_versions
                   WHERE material_id = ?
                   ORDER BY version_number DESC""",
                (material_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_material_version(
        self,
        material_id: str,
        version_number: int,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Get a specific version with full snapshot. Returns None if not found."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """SELECT id, material_id, version_number, snapshot, label, created_at
                   FROM material_versions
                   WHERE material_id = ? AND version_number = ?""",
                (material_id, version_number),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["snapshot"] = json.loads(row["snapshot"])
        return result

    def restore_material_version(
        self,
        material_id: str,
        version_number: int,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Restore a material from a version snapshot.

        Updates material fields, deletes all current pages, and rebuilds pages from snapshot.
        Returns the restored material, or None if material or version not found.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if existing is None:
                return None
            version_row = connection.execute(
                "SELECT snapshot FROM material_versions WHERE material_id = ? AND version_number = ?",
                (material_id, version_number),
            ).fetchone()
            if version_row is None:
                return None
            snapshot = json.loads(version_row["snapshot"])
            mat = snapshot["material"]
            connection.execute(
                """UPDATE materials
                   SET name = ?, material_type = ?, description = ?, content = ?,
                       prompt_text = ?, negative_prompt = ?, validation_status = ?,
                       notes = ?, updated_at = ?
                   WHERE id = ?""",
                (mat["name"], mat["material_type"], mat["description"],
                 mat["content"], mat["prompt_text"], mat["negative_prompt"],
                 mat["validation_status"], mat["notes"], now, material_id),
            )
            # Delete all current pages
            connection.execute(
                "DELETE FROM material_pages WHERE material_id = ?",
                (material_id,),
            )
            # Rebuild pages from snapshot
            for page in snapshot.get("pages", []):
                new_page_id = str(uuid4())
                connection.execute(
                    """INSERT INTO material_pages
                       (id, material_id, name, description, content, prompt_text,
                        negative_prompt, preview_original_path, preview_thumbnail_path,
                        source_page_id, sort_order, revision, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                    (new_page_id, material_id, page["name"], page["description"],
                     page["content"], page["prompt_text"], page["negative_prompt"],
                     page.get("preview_original_path"), page.get("preview_thumbnail_path"),
                     page.get("source_page_id"), page["sort_order"], now, now),
                )
        return self.get_material(material_id, environment=target_environment)

    # ── Material Copy (v0.5.2) ─────────────────────────────────────────

    def copy_material(
        self,
        material_id: str,
        *,
        new_name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Copy a material and its pages. Returns the new material.

        The new material has: name=new_name, source_material_id=source_id,
        status='unverified', no preview images. Pages are copied with
        source_page_id set to the source page id.
        """
        target_environment = environment or self._active_environment
        clean_name = self._normalize_material_name(new_name)
        now = datetime.now(timezone.utc).isoformat()
        new_material_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            source = connection.execute(
                f"SELECT {self._MATERIAL_SELECT_COLUMNS} FROM materials WHERE id = ?",
                (material_id,),
            ).fetchone()
            if source is None:
                raise ValueError("素材不存在。")
            connection.execute(
                """INSERT INTO materials(
                    id, name, material_type, description, content,
                    prompt_text, negative_prompt, validation_status, notes,
                    preview_original_path, preview_thumbnail_path,
                    archived_at, deleted_at, source_material_id,
                    revision, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, 'unverified', ?, NULL, NULL, NULL, NULL, ?, 1, ?, ?)""",
                (new_material_id, clean_name, source["material_type"],
                 source["description"], source["content"],
                 source["prompt_text"], source["negative_prompt"],
                 source["notes"], material_id, now, now),
            )
            # Copy tags
            tags = self._get_material_tags(connection, material_id)
            if tags:
                self._sync_material_tags(connection, new_material_id, tags, now)
            # Copy pages
            pages = connection.execute(
                """SELECT id, name, description, content, prompt_text, negative_prompt,
                          sort_order
                   FROM material_pages WHERE material_id = ?
                   ORDER BY sort_order ASC""",
                (material_id,),
            ).fetchall()
            for page in pages:
                new_page_id = str(uuid4())
                connection.execute(
                    """INSERT INTO material_pages
                       (id, material_id, name, description, content, prompt_text,
                        negative_prompt, preview_original_path, preview_thumbnail_path,
                        source_page_id, sort_order, revision, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, 1, ?, ?)""",
                    (new_page_id, new_material_id, page["name"], page["description"],
                     page["content"], page["prompt_text"], page["negative_prompt"],
                     page["id"], page["sort_order"], now, now),
                )
        return self.get_material(new_material_id, environment=target_environment)

    # ── Branch Overrides (v0.5.4) ──────────────────────────────────────

    _BRANCH_OVERRIDE_SELECT_COLUMNS = (
        "id, branch_id, override_type, target_id, character_id, variant_id, "
        "material_id, material_page_id, param_key, param_value, created_at, updated_at"
    )

    def list_branch_overrides(
        self,
        branch_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                f"""SELECT {self._BRANCH_OVERRIDE_SELECT_COLUMNS}
                    FROM branch_overrides
                    WHERE branch_id = ?
                    ORDER BY override_type ASC, created_at ASC""",
                (branch_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_branch_override(
        self,
        branch_id: str,
        override_type: str,
        *,
        target_id: str | None = None,
        character_id: str | None = None,
        variant_id: str | None = None,
        material_id: str | None = None,
        material_page_id: str | None = None,
        param_key: str | None = None,
        param_value: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        if override_type not in ("character", "material", "parameter"):
            raise ValueError("override_type 必须为 character/material/parameter")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        override_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            branch = connection.execute(
                "SELECT id FROM branches WHERE id = ?", (branch_id,)
            ).fetchone()
            if not branch:
                raise ValueError("分支不存在")
            try:
                connection.execute(
                    f"""INSERT INTO branch_overrides (
                        id, branch_id, override_type, target_id,
                        character_id, variant_id, material_id, material_page_id,
                        param_key, param_value, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (override_id, branch_id, override_type, target_id,
                     character_id, variant_id, material_id, material_page_id,
                     param_key, param_value, now, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("同一分支下已存在相同的覆盖配置") from error
        return self._get_branch_override(override_id, environment=target_environment)  # type: ignore[return-value]

    def _get_branch_override(
        self,
        override_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                f"""SELECT {self._BRANCH_OVERRIDE_SELECT_COLUMNS}
                    FROM branch_overrides WHERE id = ?""",
                (override_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_branch_override(
        self,
        override_id: str,
        *,
        target_id: str | None = None,
        character_id: str | None = None,
        variant_id: str | None = None,
        material_id: str | None = None,
        material_page_id: str | None = None,
        param_key: str | None = None,
        param_value: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM branch_overrides WHERE id = ?",
                (override_id,),
            ).fetchone()
            if not existing:
                return None
            sets: list[str] = []
            params: list[object] = []
            field_map = {
                "target_id": target_id,
                "character_id": character_id,
                "variant_id": variant_id,
                "material_id": material_id,
                "material_page_id": material_page_id,
                "param_key": param_key,
                "param_value": param_value,
            }
            for col, val in field_map.items():
                if val is not None:
                    sets.append(f"{col} = ?")
                    params.append(val)
            if not sets:
                raise ValueError("至少提供一个更新字段")
            sets.append("updated_at = ?")
            params.append(now)
            params.append(override_id)
            try:
                connection.execute(
                    f"UPDATE branch_overrides SET {', '.join(sets)} WHERE id = ?",
                    params,
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("同一分支下已存在相同的覆盖配置") from error
        return self._get_branch_override(override_id, environment=target_environment)

    def delete_branch_override(
        self,
        override_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            existing = connection.execute(
                "SELECT id FROM branch_overrides WHERE id = ?",
                (override_id,),
            ).fetchone()
            if not existing:
                return None
            connection.execute(
                "DELETE FROM branch_overrides WHERE id = ?",
                (override_id,),
            )
        return {"id": override_id, "deleted": True}

    def get_effective_overrides(
        self,
        shot_page_id: str,
        branch_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Return overrides that apply to a shot_page under a given branch.

        Page-specific overrides (target_id = shot_page_id) take precedence over
        branch-wide overrides (target_id IS NULL). Returns a dict with keys
        'character', 'material', 'parameter' containing the effective override rows.
        """
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            page = connection.execute(
                "SELECT id FROM shot_pages WHERE id = ?", (shot_page_id,)
            ).fetchone()
            if not page:
                raise ValueError("场景页不存在")
            branch = connection.execute(
                "SELECT id FROM branches WHERE id = ?", (branch_id,)
            ).fetchone()
            if not branch:
                raise ValueError("分支不存在")
            # Page-specific overrides (target_id = shot_page_id)
            page_rows = connection.execute(
                f"""SELECT {self._BRANCH_OVERRIDE_SELECT_COLUMNS}
                    FROM branch_overrides
                    WHERE branch_id = ? AND target_id = ?
                    ORDER BY override_type ASC, created_at ASC""",
                (branch_id, shot_page_id),
            ).fetchall()
            # Branch-wide overrides (target_id IS NULL)
            branch_rows = connection.execute(
                f"""SELECT {self._BRANCH_OVERRIDE_SELECT_COLUMNS}
                    FROM branch_overrides
                    WHERE branch_id = ? AND target_id IS NULL
                    ORDER BY override_type ASC, created_at ASC""",
                (branch_id,),
            ).fetchall()

        # Build effective map: key = (override_type, param_key or material_id or character_id)
        effective: dict[str, dict[str, dict[str, object]]] = {
            "character": {},
            "material": {},
            "parameter": {},
        }
        # Branch-wide first (lower priority)
        for row in branch_rows:
            r = dict(row)
            key = self._override_key(r)
            effective[r["override_type"]][key] = r
        # Page-specific overrides (higher priority, replace branch-wide)
        for row in page_rows:
            r = dict(row)
            key = self._override_key(r)
            effective[r["override_type"]][key] = r

        return {
            "shot_page_id": shot_page_id,
            "branch_id": branch_id,
            "character": list(effective["character"].values()),
            "material": list(effective["material"].values()),
            "parameter": list(effective["parameter"].values()),
        }

    @staticmethod
    def _override_key(row: dict[str, object]) -> str:
        """Build a dedup key for an override row."""
        if row["override_type"] == "character":
            return str(row.get("character_id") or "")
        if row["override_type"] == "material":
            return str(row.get("material_id") or "") + ":" + str(row.get("material_page_id") or "")
        # parameter
        return str(row.get("param_key") or "")

    # ── Story Snapshots (v0.5.4) ───────────────────────────────────────

    def create_story_snapshot(
        self,
        project_id: str,
        label: str = "",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Serialize the full story structure (chapters/scenes/pages/branches/mappings/overrides)
        into a JSON snapshot. Returns the snapshot record, or None if project not found.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        snapshot_id = str(uuid4())
        with self._lock, self.connection(target_environment) as connection:
            proj = connection.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not proj:
                return None
            chapters = [dict(r) for r in connection.execute(
                """SELECT id, project_id, name, sort_order, created_at, updated_at
                   FROM chapters WHERE project_id = ? ORDER BY sort_order ASC""",
                (project_id,),
            ).fetchall()]
            chapter_ids = [c["id"] for c in chapters]
            large_scenes: list[dict[str, object]] = []
            small_scenes: list[dict[str, object]] = []
            shot_pages: list[dict[str, object]] = []
            branches: list[dict[str, object]] = []
            mappings: list[dict[str, object]] = []
            overrides: list[dict[str, object]] = []

            if chapter_ids:
                ph_c = ",".join("?" * len(chapter_ids))
                large_scenes = [dict(r) for r in connection.execute(
                    f"""SELECT id, chapter_id, name, scene_type, sort_order, created_at, updated_at
                        FROM large_scenes WHERE chapter_id IN ({ph_c}) ORDER BY sort_order ASC""",
                    chapter_ids,
                ).fetchall()]
                large_scene_ids = [ls["id"] for ls in large_scenes]
                if large_scene_ids:
                    ph_ls = ",".join("?" * len(large_scene_ids))
                    small_scenes = [dict(r) for r in connection.execute(
                        f"""SELECT id, large_scene_id, name, scene_type, description, sort_order, created_at, updated_at
                            FROM small_scenes WHERE large_scene_id IN ({ph_ls}) ORDER BY sort_order ASC""",
                        large_scene_ids,
                    ).fetchall()]
                    small_scene_ids = [ss["id"] for ss in small_scenes]
                    if small_scene_ids:
                        ph_ss = ",".join("?" * len(small_scene_ids))
                        shot_pages = [dict(r) for r in connection.execute(
                            f"""SELECT id, small_scene_id, branch_id, title, description, prompt_text, negative_prompt,
                                       sort_order, revision, created_at, updated_at
                                FROM shot_pages WHERE small_scene_id IN ({ph_ss}) ORDER BY sort_order ASC""",
                            small_scene_ids,
                        ).fetchall()]
                        branches = [dict(r) for r in connection.execute(
                            f"""SELECT id, parent_type, parent_id, name, description, is_enabled,
                                       sort_order, condition_type, condition_value, return_point,
                                       created_at, updated_at
                                FROM branches
                                WHERE parent_type = 'small_scene' AND parent_id IN ({ph_ss})
                                ORDER BY sort_order ASC""",
                            small_scene_ids,
                        ).fetchall()]
                        page_ids = [p["id"] for p in shot_pages]
                        if page_ids:
                            ph_p = ",".join("?" * len(page_ids))
                            mappings = [dict(r) for r in connection.execute(
                                f"""SELECT id, scene_page_id, material_page_id, material_type, created_at, updated_at
                                    FROM small_scene_page_mappings
                                    WHERE scene_page_id IN ({ph_p}) ORDER BY created_at ASC""",
                                page_ids,
                            ).fetchall()]
                        branch_ids = [b["id"] for b in branches]
                        if branch_ids:
                            ph_b = ",".join("?" * len(branch_ids))
                            overrides = [dict(r) for r in connection.execute(
                                f"""SELECT {self._BRANCH_OVERRIDE_SELECT_COLUMNS}
                                    FROM branch_overrides
                                    WHERE branch_id IN ({ph_b})
                                    ORDER BY override_type ASC, created_at ASC""",
                                branch_ids,
                            ).fetchall()]

            snapshot_data = json.dumps(
                {
                    "project_id": project_id,
                    "chapters": chapters,
                    "large_scenes": large_scenes,
                    "small_scenes": small_scenes,
                    "shot_pages": shot_pages,
                    "branches": branches,
                    "mappings": mappings,
                    "branch_overrides": overrides,
                },
                ensure_ascii=False,
            )
            connection.execute(
                """INSERT INTO story_snapshots (id, project_id, label, snapshot_data, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (snapshot_id, project_id, label, snapshot_data, now),
            )
        return {
            "id": snapshot_id,
            "project_id": project_id,
            "label": label,
            "created_at": now,
        }

    def list_story_snapshots(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """List all snapshots for a project (without snapshot_data)."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """SELECT id, project_id, label, created_at
                   FROM story_snapshots
                   WHERE project_id = ?
                   ORDER BY created_at DESC""",
                (project_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_story_snapshot(
        self,
        snapshot_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Get a snapshot with full snapshot_data parsed as JSON."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """SELECT id, project_id, label, snapshot_data, created_at
                   FROM story_snapshots WHERE id = ?""",
                (snapshot_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["snapshot_data"] = json.loads(row["snapshot_data"])
        return result

    def restore_story_snapshot(
        self,
        snapshot_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Restore story structure from a snapshot.

        Strategy: first create a snapshot of the current state (for redo), then
        delete all current story-related rows for the project and rebuild from
        the snapshot. Returns the restore record with the new backup snapshot id.
        """
        target_environment = environment or self._active_environment
        snapshot = self.get_story_snapshot(snapshot_id, environment=target_environment)
        if snapshot is None:
            return None
        project_id = str(snapshot["project_id"])
        data = snapshot["snapshot_data"]
        # Create a backup snapshot of the current state before restore
        backup = self.create_story_snapshot(
            project_id, label=f"恢复前自动备份 (源: {snapshot_id[:8]})",
            environment=target_environment,
        )
        backup_id = str(backup["id"]) if backup else None
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            # Delete current story structure (cascade handles child rows)
            # Order: mappings → shot_pages → branches → small_scenes → large_scenes → chapters
            connection.execute(
                """DELETE FROM small_scene_page_mappings
                   WHERE scene_page_id IN (
                       SELECT sp.id FROM shot_pages sp
                       JOIN small_scenes ss ON ss.id = sp.small_scene_id
                       JOIN large_scenes ls ON ls.id = ss.large_scene_id
                       JOIN chapters c ON c.id = ls.chapter_id
                       WHERE c.project_id = ?
                   )""",
                (project_id,),
            )
            connection.execute(
                """DELETE FROM shot_pages WHERE small_scene_id IN (
                       SELECT ss.id FROM small_scenes ss
                       JOIN large_scenes ls ON ls.id = ss.large_scene_id
                       JOIN chapters c ON c.id = ls.chapter_id
                       WHERE c.project_id = ?
                   )""",
                (project_id,),
            )
            connection.execute(
                """DELETE FROM branches WHERE parent_type = 'small_scene' AND parent_id IN (
                       SELECT ss.id FROM small_scenes ss
                       JOIN large_scenes ls ON ls.id = ss.large_scene_id
                       JOIN chapters c ON c.id = ls.chapter_id
                       WHERE c.project_id = ?
                   )""",
                (project_id,),
            )
            connection.execute(
                """DELETE FROM small_scenes WHERE large_scene_id IN (
                       SELECT ls.id FROM large_scenes ls
                       JOIN chapters c ON c.id = ls.chapter_id
                       WHERE c.project_id = ?
                   )""",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM large_scenes WHERE chapter_id IN (SELECT id FROM chapters WHERE project_id = ?)",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM chapters WHERE project_id = ?",
                (project_id,),
            )

            # Rebuild from snapshot
            for c in data.get("chapters", []):
                connection.execute(
                    """INSERT INTO chapters (id, project_id, name, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (c["id"], project_id, c["name"], c["sort_order"],
                     c["created_at"], c["updated_at"]),
                )
            for ls in data.get("large_scenes", []):
                connection.execute(
                    """INSERT INTO large_scenes (id, chapter_id, name, scene_type, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ls["id"], ls["chapter_id"], ls["name"], ls["scene_type"],
                     ls["sort_order"], ls["created_at"], ls["updated_at"]),
                )
            for ss in data.get("small_scenes", []):
                connection.execute(
                    """INSERT INTO small_scenes (id, large_scene_id, name, scene_type, description, sort_order, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (ss["id"], ss["large_scene_id"], ss["name"], ss["scene_type"],
                     ss["description"], ss["sort_order"], ss["created_at"], ss["updated_at"]),
                )
            for b in data.get("branches", []):
                connection.execute(
                    """INSERT INTO branches (id, parent_type, parent_id, name, description, is_enabled,
                                              sort_order, condition_type, condition_value, return_point,
                                              created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (b["id"], b["parent_type"], b["parent_id"], b["name"], b["description"],
                     b["is_enabled"], b["sort_order"],
                     b.get("condition_type", ""), b.get("condition_value", ""),
                     b.get("return_point"), b["created_at"], b["updated_at"]),
                )
            for p in data.get("shot_pages", []):
                connection.execute(
                    """INSERT INTO shot_pages (id, small_scene_id, branch_id, title, description,
                                                prompt_text, negative_prompt, sort_order, revision,
                                                created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (p["id"], p["small_scene_id"], p["branch_id"], p["title"], p["description"],
                     p["prompt_text"], p["negative_prompt"], p["sort_order"], p.get("revision", 1),
                     p["created_at"], p["updated_at"]),
                )
            for m in data.get("mappings", []):
                connection.execute(
                    """INSERT INTO small_scene_page_mappings
                       (id, scene_page_id, material_page_id, material_type, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (m["id"], m["scene_page_id"], m["material_page_id"], m["material_type"],
                     m["created_at"], m["updated_at"]),
                )
            for o in data.get("branch_overrides", []):
                connection.execute(
                    """INSERT INTO branch_overrides
                       (id, branch_id, override_type, target_id, character_id, variant_id,
                        material_id, material_page_id, param_key, param_value, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (o["id"], o["branch_id"], o["override_type"], o["target_id"],
                     o["character_id"], o["variant_id"], o["material_id"], o["material_page_id"],
                     o["param_key"], o["param_value"], o["created_at"], o["updated_at"]),
                )
        return {
            "restored_snapshot_id": snapshot_id,
            "project_id": project_id,
            "backup_snapshot_id": backup_id,
            "restored_at": now,
        }

    # ── Operation History (v0.5.4) ─────────────────────────────────────

    def record_operation(
        self,
        project_id: str,
        operation_type: str,
        entity_type: str,
        entity_id: str | None = None,
        *,
        before_state: dict | None = None,
        after_state: dict | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        if operation_type not in ("move", "create", "delete", "rename", "reorder", "map", "unmap"):
            raise ValueError("operation_type 无效")
        if entity_type not in ("chapter", "large_scene", "small_scene", "shot_page", "branch", "mapping"):
            raise ValueError("entity_type 无效")
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        op_id = str(uuid4())
        before_json = json.dumps(before_state, ensure_ascii=False) if before_state is not None else None
        after_json = json.dumps(after_state, ensure_ascii=False) if after_state is not None else None
        with self._lock, self.connection(target_environment) as connection:
            proj = connection.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not proj:
                raise ValueError("项目不存在")
            connection.execute(
                """INSERT INTO operation_history
                   (id, project_id, operation_type, entity_type, entity_id,
                    before_state, after_state, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (op_id, project_id, operation_type, entity_type, entity_id,
                 before_json, after_json, now),
            )
        return {
            "id": op_id,
            "project_id": project_id,
            "operation_type": operation_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before_state": before_state,
            "after_state": after_state,
            "created_at": now,
        }

    def list_operations(
        self,
        project_id: str,
        limit: int = 50,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """SELECT id, project_id, operation_type, entity_type, entity_id,
                          before_state, after_state, created_at
                   FROM operation_history
                   WHERE project_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (project_id, limit),
            ).fetchall()
        results: list[dict[str, object]] = []
        for row in rows:
            r = dict(row)
            if r["before_state"]:
                r["before_state"] = json.loads(r["before_state"])
            if r["after_state"]:
                r["after_state"] = json.loads(r["after_state"])
            results.append(r)
        return results

    def undo_operation(
        self,
        operation_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Undo a single operation by restoring before_state.

        Records a new operation capturing the current state as after_state for redo.
        Returns the undo record, or None if operation not found.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            op = connection.execute(
                """SELECT id, project_id, operation_type, entity_type, entity_id,
                          before_state, after_state, created_at
                   FROM operation_history WHERE id = ?""",
                (operation_id,),
            ).fetchone()
            if op is None:
                return None
            before = json.loads(op["before_state"]) if op["before_state"] else None
            if not before:
                raise ValueError("无法撤销：缺少 before_state")
            entity_type = op["entity_type"]
            entity_id = op["entity_id"]
            # Capture current state for redo
            current_state = self._capture_entity_state(
                connection, entity_type, entity_id
            )
            # Apply before_state to revert the entity
            self._apply_entity_state(
                connection, entity_type, entity_id, before, op["operation_type"]
            )
            # Record redo entry
            redo_id = str(uuid4())
            connection.execute(
                """INSERT INTO operation_history
                   (id, project_id, operation_type, entity_type, entity_id,
                    before_state, after_state, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (redo_id, op["project_id"], op["operation_type"], entity_type, entity_id,
                 json.dumps(current_state, ensure_ascii=False) if current_state else None,
                 json.dumps(before, ensure_ascii=False), now),
            )
        return {
            "undone_operation_id": operation_id,
            "redo_operation_id": redo_id,
            "project_id": op["project_id"],
            "entity_type": entity_type,
            "entity_id": entity_id,
            "restored_at": now,
        }

    def redo_operation(
        self,
        operation_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Redo an operation by applying after_state.

        Records a new operation capturing the current state as before_state for undo.
        Returns the redo record, or None if operation not found.
        """
        target_environment = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target_environment) as connection:
            op = connection.execute(
                """SELECT id, project_id, operation_type, entity_type, entity_id,
                          before_state, after_state, created_at
                   FROM operation_history WHERE id = ?""",
                (operation_id,),
            ).fetchone()
            if op is None:
                return None
            after = json.loads(op["after_state"]) if op["after_state"] else None
            if not after:
                raise ValueError("无法重做：缺少 after_state")
            entity_type = op["entity_type"]
            entity_id = op["entity_id"]
            # Capture current state for undo
            current_state = self._capture_entity_state(
                connection, entity_type, entity_id
            )
            # Apply after_state to redo the entity
            self._apply_entity_state(
                connection, entity_type, entity_id, after, op["operation_type"]
            )
            # Record undo entry
            undo_id = str(uuid4())
            connection.execute(
                """INSERT INTO operation_history
                   (id, project_id, operation_type, entity_type, entity_id,
                    before_state, after_state, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (undo_id, op["project_id"], op["operation_type"], entity_type, entity_id,
                 json.dumps(current_state, ensure_ascii=False) if current_state else None,
                 json.dumps(after, ensure_ascii=False), now),
            )
        return {
            "redone_operation_id": operation_id,
            "undo_operation_id": undo_id,
            "project_id": op["project_id"],
            "entity_type": entity_type,
            "entity_id": entity_id,
            "restored_at": now,
        }

    def _capture_entity_state(
        self, connection, entity_type: str, entity_id: str | None
    ) -> dict | None:
        """Capture the current state of an entity as a dict (for undo/redo)."""
        if not entity_id:
            return None
        if entity_type == "chapter":
            row = connection.execute(
                "SELECT id, project_id, name, sort_order FROM chapters WHERE id = ?",
                (entity_id,),
            ).fetchone()
        elif entity_type == "large_scene":
            row = connection.execute(
                "SELECT id, chapter_id, name, scene_type, sort_order FROM large_scenes WHERE id = ?",
                (entity_id,),
            ).fetchone()
        elif entity_type == "small_scene":
            row = connection.execute(
                "SELECT id, large_scene_id, name, scene_type, sort_order FROM small_scenes WHERE id = ?",
                (entity_id,),
            ).fetchone()
        elif entity_type == "shot_page":
            row = connection.execute(
                """SELECT id, small_scene_id, branch_id, title, description,
                          prompt_text, negative_prompt, sort_order
                   FROM shot_pages WHERE id = ?""",
                (entity_id,),
            ).fetchone()
        elif entity_type == "branch":
            row = connection.execute(
                """SELECT id, parent_type, parent_id, name, description, is_enabled,
                          sort_order, condition_type, condition_value, return_point
                   FROM branches WHERE id = ?""",
                (entity_id,),
            ).fetchone()
        elif entity_type == "mapping":
            row = connection.execute(
                """SELECT id, scene_page_id, material_page_id, material_type
                   FROM small_scene_page_mappings WHERE id = ?""",
                (entity_id,),
            ).fetchone()
        else:
            return None
        return dict(row) if row else None

    def _apply_entity_state(
        self, connection, entity_type: str, entity_id: str | None,
        state: dict, operation_type: str,
    ) -> None:
        """Apply a captured state to revert or redo an entity.

        For 'delete' operations: re-insert the row using the captured state.
        For 'create' operations: delete the row.
        For other operations (rename/move/reorder/map): upsert the captured state.
        """
        if not entity_id:
            return
        if operation_type == "delete":
            # Re-insert the row from state
            self._insert_entity_from_state(connection, entity_type, state)
            return
        if operation_type == "create":
            # Delete the row
            table_map = {
                "chapter": "chapters",
                "large_scene": "large_scenes",
                "small_scene": "small_scenes",
                "shot_page": "shot_pages",
                "branch": "branches",
                "mapping": "small_scene_page_mappings",
            }
            table = table_map.get(entity_type)
            if table:
                connection.execute(
                    f"DELETE FROM {table} WHERE id = ?", (entity_id,)
                )
            return
        # rename/move/reorder/map/unmap: upsert
        self._upsert_entity_from_state(connection, entity_type, state)

    def _insert_entity_from_state(
        self, connection, entity_type: str, state: dict
    ) -> None:
        if entity_type == "chapter":
            connection.execute(
                """INSERT OR IGNORE INTO chapters (id, project_id, name, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (state["id"], state["project_id"], state["name"], state["sort_order"],
                 datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )
        elif entity_type == "large_scene":
            connection.execute(
                """INSERT OR IGNORE INTO large_scenes (id, chapter_id, name, scene_type, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (state["id"], state["chapter_id"], state["name"], state["scene_type"],
                 state["sort_order"], datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )
        elif entity_type == "small_scene":
            connection.execute(
                """INSERT OR IGNORE INTO small_scenes (id, large_scene_id, name, scene_type, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (state["id"], state["large_scene_id"], state["name"], state["scene_type"],
                 state["sort_order"], datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )
        elif entity_type == "shot_page":
            connection.execute(
                """INSERT OR IGNORE INTO shot_pages (id, small_scene_id, branch_id, title, description,
                                                      prompt_text, negative_prompt, sort_order, revision,
                                                      created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (state["id"], state["small_scene_id"], state.get("branch_id"),
                 state["title"], state.get("description", ""), state.get("prompt_text", ""),
                 state.get("negative_prompt", ""), state["sort_order"], 1,
                 datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )
        elif entity_type == "branch":
            connection.execute(
                """INSERT OR IGNORE INTO branches (id, parent_type, parent_id, name, description, is_enabled,
                                                    sort_order, condition_type, condition_value, return_point,
                                                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (state["id"], state["parent_type"], state["parent_id"], state["name"],
                 state.get("description", ""), state.get("is_enabled", 1), state["sort_order"],
                 state.get("condition_type", ""), state.get("condition_value", ""),
                 state.get("return_point"), datetime.now(timezone.utc).isoformat(),
                 datetime.now(timezone.utc).isoformat()),
            )
        elif entity_type == "mapping":
            now_ts = datetime.now(timezone.utc).isoformat()
            connection.execute(
                """INSERT OR IGNORE INTO small_scene_page_mappings
                   (id, scene_page_id, material_page_id, material_type, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (state["id"], state["scene_page_id"], state["material_page_id"],
                 state["material_type"], now_ts, now_ts),
            )

    def _upsert_entity_from_state(
        self, connection, entity_type: str, state: dict
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if entity_type == "chapter":
            connection.execute(
                """INSERT INTO chapters (id, project_id, name, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name, sort_order = excluded.sort_order, updated_at = excluded.updated_at""",
                (state["id"], state["project_id"], state["name"], state["sort_order"], now, now),
            )
        elif entity_type == "large_scene":
            connection.execute(
                """INSERT INTO large_scenes (id, chapter_id, name, scene_type, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name, scene_type = excluded.scene_type,
                                                    sort_order = excluded.sort_order, updated_at = excluded.updated_at""",
                (state["id"], state["chapter_id"], state["name"], state["scene_type"],
                 state["sort_order"], now, now),
            )
        elif entity_type == "small_scene":
            connection.execute(
                """INSERT INTO small_scenes (id, large_scene_id, name, scene_type, sort_order, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name, scene_type = excluded.scene_type,
                                                   sort_order = excluded.sort_order, updated_at = excluded.updated_at""",
                (state["id"], state["large_scene_id"], state["name"], state["scene_type"],
                 state["sort_order"], now, now),
            )
        elif entity_type == "shot_page":
            connection.execute(
                """INSERT INTO shot_pages (id, small_scene_id, branch_id, title, description,
                                            prompt_text, negative_prompt, sort_order, revision,
                                            created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET title = excluded.title, description = excluded.description,
                                                   prompt_text = excluded.prompt_text, negative_prompt = excluded.negative_prompt,
                                                   sort_order = excluded.sort_order, updated_at = excluded.updated_at""",
                (state["id"], state["small_scene_id"], state.get("branch_id"),
                 state["title"], state.get("description", ""), state.get("prompt_text", ""),
                 state.get("negative_prompt", ""), state["sort_order"], 1, now, now),
            )
        elif entity_type == "branch":
            connection.execute(
                """INSERT INTO branches (id, parent_type, parent_id, name, description, is_enabled,
                                          sort_order, condition_type, condition_value, return_point,
                                          created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name, description = excluded.description,
                                                   is_enabled = excluded.is_enabled, sort_order = excluded.sort_order,
                                                   condition_type = excluded.condition_type,
                                                   condition_value = excluded.condition_value,
                                                   return_point = excluded.return_point,
                                                   updated_at = excluded.updated_at""",
                (state["id"], state["parent_type"], state["parent_id"], state["name"],
                 state.get("description", ""), state.get("is_enabled", 1), state["sort_order"],
                 state.get("condition_type", ""), state.get("condition_value", ""),
                 state.get("return_point"), now, now),
            )
        elif entity_type == "mapping":
            connection.execute(
                """INSERT INTO small_scene_page_mappings
                   (id, scene_page_id, material_page_id, material_type, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET scene_page_id = excluded.scene_page_id,
                                                   material_page_id = excluded.material_page_id,
                                                   material_type = excluded.material_type,
                                                   updated_at = excluded.updated_at""",
                (state["id"], state["scene_page_id"], state["material_page_id"],
                 state["material_type"], now, now),
            )

    # ── Shot Page Inheritance (v0.5.4) ─────────────────────────────────

    def get_shot_page_inheritance(
        self,
        shot_page_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Return the inheritance chain for a shot page.

        Chain: project → chapter → large_scene → small_scene → branch → shot_page.
        Each level includes id/name and inheritable attributes. The final
        effective values are computed with closer levels taking precedence.
        """
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            page = connection.execute(
                """SELECT id, small_scene_id, branch_id, title, description, prompt_text, negative_prompt,
                          sort_order, created_at, updated_at
                   FROM shot_pages WHERE id = ?""",
                (shot_page_id,),
            ).fetchone()
            if not page:
                return None
            small_scene = None
            large_scene = None
            chapter = None
            project = None
            branch = None

            ss_row = connection.execute(
                """SELECT id, large_scene_id, name, scene_type, description
                   FROM small_scenes WHERE id = ?""",
                (page["small_scene_id"],),
            ).fetchone()
            if ss_row:
                small_scene = dict(ss_row)
                ls_row = connection.execute(
                    """SELECT id, chapter_id, name, scene_type
                       FROM large_scenes WHERE id = ?""",
                    (small_scene["large_scene_id"],),
                ).fetchone()
                if ls_row:
                    large_scene = dict(ls_row)
                    c_row = connection.execute(
                        """SELECT id, project_id, name
                           FROM chapters WHERE id = ?""",
                        (large_scene["chapter_id"],),
                    ).fetchone()
                    if c_row:
                        chapter = dict(c_row)
                        p_row = connection.execute(
                            """SELECT id, name, description, status
                               FROM projects WHERE id = ?""",
                            (chapter["project_id"],),
                        ).fetchone()
                        if p_row:
                            project = dict(p_row)
            if page["branch_id"]:
                b_row = connection.execute(
                    """SELECT id, parent_type, parent_id, name, description, is_enabled,
                              condition_type, condition_value, return_point
                       FROM branches WHERE id = ?""",
                    (page["branch_id"],),
                ).fetchone()
                if b_row:
                    branch = dict(b_row)

            # Fetch character binding at the page level (only level that has it directly)
            page_character = connection.execute(
                """SELECT spc.character_id, spc.variant_id,
                          c.name AS character_name, cv.name AS variant_name,
                          cv.default_prompt, cv.default_lora_name,
                          cv.default_lora_weight, cv.default_model_override
                   FROM shot_page_characters spc
                   JOIN characters c ON c.id = spc.character_id
                   JOIN character_variants cv ON cv.id = spc.variant_id
                   WHERE spc.shot_page_id = ?""",
                (shot_page_id,),
            ).fetchone()

        # Build chain
        chain: list[dict[str, object]] = []
        if project:
            chain.append({
                "level": "project",
                "id": project["id"],
                "name": project["name"],
                "attributes": {
                    "description": project.get("description", ""),
                    "status": project.get("status", ""),
                },
            })
        if chapter:
            chain.append({
                "level": "chapter",
                "id": chapter["id"],
                "name": chapter["name"],
                "attributes": {},
            })
        if large_scene:
            chain.append({
                "level": "large_scene",
                "id": large_scene["id"],
                "name": large_scene["name"],
                "attributes": {"scene_type": large_scene.get("scene_type", "")},
            })
        if small_scene:
            chain.append({
                "level": "small_scene",
                "id": small_scene["id"],
                "name": small_scene["name"],
                "attributes": {
                    "scene_type": small_scene.get("scene_type", ""),
                    "description": small_scene.get("description", ""),
                },
            })
        if branch:
            chain.append({
                "level": "branch",
                "id": branch["id"],
                "name": branch["name"],
                "attributes": {
                    "condition_type": branch.get("condition_type", ""),
                    "condition_value": branch.get("condition_value", ""),
                    "return_point": branch.get("return_point"),
                    "is_enabled": bool(branch.get("is_enabled", 1)),
                },
            })
        page_dict = dict(page)
        page_dict["name"] = page_dict.pop("title")
        page_attributes = {
            "description": page_dict.get("description", ""),
            "prompt_text": page_dict.get("prompt_text", ""),
            "negative_prompt": page_dict.get("negative_prompt", ""),
        }
        if page_character:
            page_attributes["character"] = dict(page_character)
        chain.append({
            "level": "shot_page",
            "id": page_dict["id"],
            "name": page_dict["name"],
            "attributes": page_attributes,
        })

        # Compute effective values (closer level wins)
        effective: dict[str, object] = {}
        source_map: dict[str, str] = {}
        for level in chain:
            for key, val in level["attributes"].items():
                if val in (None, "", []):
                    continue
                effective[key] = val
                source_map[key] = level["level"]

        return {
            "shot_page_id": shot_page_id,
            "chain": chain,
            "effective": effective,
            "sources": source_map,
        }

    # ── Compilation Precheck (v0.5.4) ──────────────────────────────────

    def precheck_compilation(
        self,
        project_id: str,
        scope: str = "project",
        scope_id: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """Pre-check a project (or sub-scope) for compilation readiness.

        Returns blocking/warnings/summary, or None if project not found.
        scope: 'project' / 'chapter' / 'large_scene' / 'small_scene' / 'branch' / 'shot_pages'
        """
        valid_scopes = ("project", "chapter", "large_scene", "small_scene", "branch", "shot_pages")
        if scope not in valid_scopes:
            raise ValueError(f"scope 无效，允许值: {', '.join(valid_scopes)}")
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            proj = connection.execute(
                "SELECT id FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not proj:
                return None

            # Determine the set of chapters/large_scenes/small_scenes to inspect
            chapter_ids: list[str] = []
            large_scene_ids: list[str] = []
            small_scene_ids: list[str] = []
            branch_ids: list[str] = []

            if scope == "project":
                chapter_ids = [r["id"] for r in connection.execute(
                    "SELECT id FROM chapters WHERE project_id = ?", (project_id,)
                ).fetchall()]
            elif scope == "chapter":
                if not scope_id:
                    raise ValueError("scope=chapter 需要 scope_id")
                chapter_ids = [scope_id]
            elif scope == "large_scene":
                if not scope_id:
                    raise ValueError("scope=large_scene 需要 scope_id")
                large_scene_ids = [scope_id]
            elif scope == "small_scene":
                if not scope_id:
                    raise ValueError("scope=small_scene 需要 scope_id")
                small_scene_ids = [scope_id]
            elif scope == "branch":
                if not scope_id:
                    raise ValueError("scope=branch 需要 scope_id")
                branch_ids = [scope_id]
            elif scope == "shot_pages":
                if not scope_id:
                    raise ValueError("scope=shot_pages 需要 scope_id")
                # scope_id is a comma-separated list of shot_page ids
                pass

            if chapter_ids:
                ph = ",".join("?" * len(chapter_ids))
                large_scene_ids = [r["id"] for r in connection.execute(
                    f"SELECT id FROM large_scenes WHERE chapter_id IN ({ph})", chapter_ids
                ).fetchall()]
            if large_scene_ids:
                ph = ",".join("?" * len(large_scene_ids))
                small_scene_ids = [r["id"] for r in connection.execute(
                    f"SELECT id FROM small_scenes WHERE large_scene_id IN ({ph})", large_scene_ids
                ).fetchall()]
            if small_scene_ids and not branch_ids:
                ph = ",".join("?" * len(small_scene_ids))
                branch_ids = [r["id"] for r in connection.execute(
                    f"""SELECT id FROM branches
                        WHERE parent_type = 'small_scene' AND parent_id IN ({ph})""",
                    small_scene_ids,
                ).fetchall()]

            # Gather all shot_pages to inspect
            if scope == "shot_pages":
                page_ids = [s.strip() for s in scope_id.split(",") if s.strip()]
            else:
                page_ids = []
                if small_scene_ids:
                    ph = ",".join("?" * len(small_scene_ids))
                    page_ids = [r["id"] for r in connection.execute(
                        f"SELECT id FROM shot_pages WHERE small_scene_id IN ({ph})",
                        small_scene_ids,
                    ).fetchall()]

            blocking: list[dict[str, object]] = []
            warnings: list[dict[str, object]] = []

            # Check 1: chapters/large_scenes/small_scenes with no pages
            if small_scene_ids:
                ph = ",".join("?" * len(small_scene_ids))
                empty_scenes = connection.execute(
                    f"""SELECT ss.id, ss.name, ss.large_scene_id
                        FROM small_scenes ss
                        WHERE ss.id IN ({ph})
                          AND NOT EXISTS (SELECT 1 FROM shot_pages sp WHERE sp.small_scene_id = ss.id)
                        ORDER BY ss.name""",
                    small_scene_ids,
                ).fetchall()
                for r in empty_scenes:
                    blocking.append({
                        "type": "empty_small_scene",
                        "entity_type": "small_scene",
                        "entity_id": r["id"],
                        "entity_name": r["name"],
                        "message": f"小场景 '{r['name']}' 没有场景页",
                    })
            if large_scene_ids:
                ph = ",".join("?" * len(large_scene_ids))
                empty_large = connection.execute(
                    f"""SELECT ls.id, ls.name
                        FROM large_scenes ls
                        WHERE ls.id IN ({ph})
                          AND NOT EXISTS (SELECT 1 FROM small_scenes ss WHERE ss.large_scene_id = ls.id)
                        ORDER BY ls.name""",
                    large_scene_ids,
                ).fetchall()
                for r in empty_large:
                    blocking.append({
                        "type": "empty_large_scene",
                        "entity_type": "large_scene",
                        "entity_id": r["id"],
                        "entity_name": r["name"],
                        "message": f"大场景 '{r['name']}' 没有小场景",
                    })
            if chapter_ids:
                ph = ",".join("?" * len(chapter_ids))
                empty_chapters = connection.execute(
                    f"""SELECT c.id, c.name
                        FROM chapters c
                        WHERE c.id IN ({ph})
                          AND NOT EXISTS (SELECT 1 FROM large_scenes ls WHERE ls.chapter_id = c.id)
                        ORDER BY c.name""",
                    chapter_ids,
                ).fetchall()
                for r in empty_chapters:
                    blocking.append({
                        "type": "empty_chapter",
                        "entity_type": "chapter",
                        "entity_id": r["id"],
                        "entity_name": r["name"],
                        "message": f"章节 '{r['name']}' 没有大场景",
                    })

            # Check 2: shot_pages without character binding
            if page_ids:
                ph = ",".join("?" * len(page_ids))
                pages_no_char = connection.execute(
                    f"""SELECT sp.id, sp.title, sp.small_scene_id
                        FROM shot_pages sp
                        WHERE sp.id IN ({ph})
                          AND NOT EXISTS (SELECT 1 FROM shot_page_characters spc WHERE spc.shot_page_id = sp.id)
                        ORDER BY sp.title""",
                    page_ids,
                ).fetchall()
                for r in pages_no_char:
                    warnings.append({
                        "type": "missing_character",
                        "entity_type": "shot_page",
                        "entity_id": r["id"],
                        "entity_name": r["title"],
                        "message": f"场景页 '{r['title']}' 未绑定人物",
                    })

                # Check 3: shot_pages without material mappings
                pages_no_mapping = connection.execute(
                    f"""SELECT sp.id, sp.title
                        FROM shot_pages sp
                        WHERE sp.id IN ({ph})
                          AND NOT EXISTS (SELECT 1 FROM small_scene_page_mappings m WHERE m.scene_page_id = sp.id)
                        ORDER BY sp.title""",
                    page_ids,
                ).fetchall()
                for r in pages_no_mapping:
                    warnings.append({
                        "type": "missing_material_mapping",
                        "entity_type": "shot_page",
                        "entity_id": r["id"],
                        "entity_name": r["title"],
                        "message": f"场景页 '{r['title']}' 缺失素材映射",
                    })

                # Check 4: shot_pages with empty prompt_text
                pages_no_prompt = connection.execute(
                    f"""SELECT sp.id, sp.title
                        FROM shot_pages sp
                        WHERE sp.id IN ({ph}) AND (sp.prompt_text IS NULL OR sp.prompt_text = '')
                        ORDER BY sp.title""",
                    page_ids,
                ).fetchall()
                for r in pages_no_prompt:
                    warnings.append({
                        "type": "missing_prompt",
                        "entity_type": "shot_page",
                        "entity_id": r["id"],
                        "entity_name": r["title"],
                        "message": f"场景页 '{r['title']}' 正向提示词为空",
                    })

            # Check 5: invalid branch references (branch_id pointing to non-existent branches)
            if page_ids:
                ph = ",".join("?" * len(page_ids))
                invalid_branch_refs = connection.execute(
                    f"""SELECT sp.id, sp.title, sp.branch_id
                        FROM shot_pages sp
                        WHERE sp.id IN ({ph}) AND sp.branch_id IS NOT NULL
                          AND NOT EXISTS (SELECT 1 FROM branches b WHERE b.id = sp.branch_id)
                        ORDER BY sp.title""",
                    page_ids,
                ).fetchall()
                for r in invalid_branch_refs:
                    blocking.append({
                        "type": "invalid_branch_ref",
                        "entity_type": "shot_page",
                        "entity_id": r["id"],
                        "entity_name": r["title"],
                        "message": f"场景页 '{r['title']}' 引用了不存在的分支",
                    })

            total_pages = len(page_ids)
            blocked_pages = len({b["entity_id"] for b in blocking if b["entity_type"] == "shot_page"})
            ready_pages = total_pages - blocked_pages

            return {
                "project_id": project_id,
                "scope": scope,
                "scope_id": scope_id,
                "blocking": blocking,
                "warnings": warnings,
                "summary": {
                    "total_pages": total_pages,
                    "ready_pages": ready_pages,
                    "blocked_pages": blocked_pages,
                },
            }

    # ──────────────────────────────────────────────────────────────────
    # 应用设置（app_settings 表）
    # ──────────────────────────────────────────────────────────────────

    def get_setting(
        self,
        key: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> str | None:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
            return row["value"] if row else None

    def set_setting(
        self,
        key: str,
        value: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> None:
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            connection.execute(
                "INSERT INTO app_settings(key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, value, now),
            )

    def get_settings(
        self,
        prefix: str = "",
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, str]:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            if prefix:
                rows = connection.execute(
                    "SELECT key, value FROM app_settings WHERE key LIKE ? ORDER BY key",
                    (f"{prefix}%",),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT key, value FROM app_settings ORDER BY key",
                ).fetchall()
            return {row["key"]: row["value"] for row in rows}

    def get_comfyui_settings(
        self,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            rows = connection.execute(
                "SELECT key, value FROM app_settings WHERE key LIKE 'comfyui.%' ORDER BY key",
            ).fetchall()
        settings: dict[str, str] = {row["key"]: row["value"] for row in rows}
        base_url = settings.get("comfyui.base_url", "http://127.0.0.1:8188")
        timeout_raw = settings.get("comfyui.timeout_seconds", "10")
        try:
            timeout = float(timeout_raw)
        except (TypeError, ValueError):
            timeout = 10.0
        websocket_url = settings.get("comfyui.websocket_url", "")
        return {
            "base_url": base_url,
            "timeout_seconds": timeout,
            "websocket_url": websocket_url,
        }

    def set_comfyui_settings(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        websocket_url: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target = environment or self._active_environment
        if base_url is not None:
            self.set_setting("comfyui.base_url", str(base_url), environment=target)
        if timeout_seconds is not None:
            self.set_setting("comfyui.timeout_seconds", str(timeout_seconds), environment=target)
        if websocket_url is not None:
            self.set_setting("comfyui.websocket_url", str(websocket_url), environment=target)
        return self.get_comfyui_settings(environment=target)

    # ──────────────────────────────────────────────────────────────────
    # ComfyUI 节点定义缓存（comfyui_node_definitions 表）
    # ──────────────────────────────────────────────────────────────────

    def save_node_definitions(
        self,
        object_info: dict[str, object],
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """全量替换节点定义缓存。

        删除旧缓存并写入新数据。返回摘要信息。
        """
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            connection.execute("DELETE FROM comfyui_node_definitions")
            rows_to_insert: list[tuple] = []
            custom_count = 0
            for node_class, definition in object_info.items():
                if not isinstance(definition, dict):
                    continue
                python_module = str(definition.get("python_module", ""))
                category = str(definition.get("category", ""))
                display_name = str(definition.get("display_name", node_class))
                is_custom = 1 if python_module.startswith("custom_nodes.") else 0
                if is_custom:
                    custom_count += 1
                rows_to_insert.append(
                    (
                        node_class,
                        python_module,
                        category,
                        display_name,
                        json.dumps(definition, ensure_ascii=False),
                        is_custom,
                        now,
                    )
                )
            connection.executemany(
                """
                INSERT INTO comfyui_node_definitions
                    (node_class, python_module, category, display_name, definition_json, is_custom_node, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                rows_to_insert,
            )
            total = len(rows_to_insert)
            connection.execute(
                "INSERT INTO comfyui_sync_meta(sync_key, value, updated_at) VALUES ('node_definitions.count', ?, ?) "
                "ON CONFLICT(sync_key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (str(total), now),
            )
            connection.execute(
                "INSERT INTO comfyui_sync_meta(sync_key, value, updated_at) VALUES ('node_definitions.custom_count', ?, ?) "
                "ON CONFLICT(sync_key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (str(custom_count), now),
            )
            connection.execute(
                "INSERT INTO comfyui_sync_meta(sync_key, value, updated_at) VALUES ('node_definitions.last_sync', ?, ?) "
                "ON CONFLICT(sync_key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (now, now),
            )
        return {
            "node_count": total,
            "custom_node_count": custom_count,
            "synced_at": now,
        }

    def list_node_definitions(
        self,
        *,
        category: str | None = None,
        is_custom: bool | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            where_parts: list[str] = []
            params: list[object] = []
            if category:
                where_parts.append("category = ?")
                params.append(category)
            if is_custom is not None:
                where_parts.append("is_custom_node = ?")
                params.append(1 if is_custom else 0)
            if search:
                where_parts.append("(node_class LIKE ? OR display_name LIKE ?)")
                params.extend([f"%{search}%", f"%{search}%"])
            where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
            total_row = connection.execute(
                f"SELECT COUNT(*) AS cnt FROM comfyui_node_definitions{where_clause}",
                params,
            ).fetchone()
            total = total_row["cnt"] if total_row else 0
            rows = connection.execute(
                f"""
                SELECT node_class, python_module, category, display_name, is_custom_node, updated_at
                FROM comfyui_node_definitions{where_clause}
                ORDER BY category, node_class
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()
            items = [
                {
                    "node_class": row["node_class"],
                    "python_module": row["python_module"],
                    "category": row["category"],
                    "display_name": row["display_name"],
                    "is_custom_node": bool(row["is_custom_node"]),
                    "updated_at": row["updated_at"],
                }
                for row in rows
            ]
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        }

    def get_node_definition(
        self,
        node_class: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            row = connection.execute(
                "SELECT * FROM comfyui_node_definitions WHERE node_class = ?",
                (node_class,),
            ).fetchone()
            if not row:
                return None
            try:
                definition = json.loads(row["definition_json"])
            except (TypeError, ValueError):
                definition = {}
        return {
            "node_class": row["node_class"],
            "python_module": row["python_module"],
            "category": row["category"],
            "display_name": row["display_name"],
            "is_custom_node": bool(row["is_custom_node"]),
            "updated_at": row["updated_at"],
            "definition": definition,
        }

    def get_node_definition_summary(
        self,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            count_row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM comfyui_node_definitions"
            ).fetchone()
            custom_row = connection.execute(
                "SELECT COUNT(*) AS cnt FROM comfyui_node_definitions WHERE is_custom_node = 1"
            ).fetchone()
            meta_rows = connection.execute(
                "SELECT sync_key, value, updated_at FROM comfyui_sync_meta "
                "WHERE sync_key LIKE 'node_definitions.%'"
            ).fetchall()
        meta = {row["sync_key"]: row["value"] for row in meta_rows}
        last_sync = meta.get("node_definitions.last_sync", "")
        return {
            "node_count": count_row["cnt"] if count_row else 0,
            "custom_node_count": custom_row["cnt"] if custom_row else 0,
            "last_synced_at": last_sync,
        }

    def list_node_categories(
        self,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> list[str]:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            rows = connection.execute(
                "SELECT DISTINCT category FROM comfyui_node_definitions "
                "WHERE category != '' ORDER BY category"
            ).fetchall()
        return [row["category"] for row in rows]

    # ──────────────────────────────────────────────────────────────────
    # ComfyUI 资源缓存（comfyui_resource_cache 表）
    # ──────────────────────────────────────────────────────────────────

    def save_resource_cache(
        self,
        resource_type: str,
        resource_names: list[str],
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """全量替换某一资源类型的缓存。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            connection.execute(
                "DELETE FROM comfyui_resource_cache WHERE resource_type = ?",
                (resource_type,),
            )
            if resource_names:
                connection.executemany(
                    "INSERT INTO comfyui_resource_cache(resource_type, resource_name, updated_at) VALUES (?, ?, ?)",
                    [(resource_type, name, now) for name in resource_names],
                )
            connection.execute(
                "INSERT INTO comfyui_sync_meta(sync_key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(sync_key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (f"resources.{resource_type}.count", str(len(resource_names)), now),
            )
            connection.execute(
                "INSERT INTO comfyui_sync_meta(sync_key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(sync_key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (f"resources.{resource_type}.last_sync", now, now),
            )
        return {
            "resource_type": resource_type,
            "count": len(resource_names),
            "synced_at": now,
        }

    def list_resource_cache(
        self,
        resource_type: str | None = None,
        *,
        search: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            where_parts: list[str] = []
            params: list[object] = []
            if resource_type:
                where_parts.append("resource_type = ?")
                params.append(resource_type)
            if search:
                where_parts.append("resource_name LIKE ?")
                params.append(f"%{search}%")
            where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
            rows = connection.execute(
                f"""
                SELECT resource_type, resource_name, updated_at
                FROM comfyui_resource_cache{where_clause}
                ORDER BY resource_type, resource_name
                """
                + (" LIMIT 2000" if not where_clause else " LIMIT 2000"),
                params,
            ).fetchall()
            grouped: dict[str, list[str]] = {}
            updated_map: dict[str, str] = {}
            for row in rows:
                grouped.setdefault(row["resource_type"], []).append(row["resource_name"])
                updated_map[row["resource_type"]] = row["updated_at"]
        return {
            "resources": grouped,
            "updated_at": updated_map,
        }

    # ──────────────────────────────────────────────────────────────────
    # 工作流库（workflows/workflow_versions/workflow_drafts/semantic_slots 表）
    # ──────────────────────────────────────────────────────────────────

    def create_workflow(
        self,
        name: str,
        *,
        description: str = "",
        source_type: str = "manual",
        source_identifier: str = "",
        project_id: str | None = None,
        source_workflow_id: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """创建工作流。project_id 为 None 时是全局模板。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        workflow_id = uuid4().hex
        workflow = {
            "id": workflow_id,
            "name": name,
            "description": description,
            "source_type": source_type,
            "source_identifier": source_identifier,
            "project_id": project_id,
            "source_workflow_id": source_workflow_id,
            "current_version_id": None,
            "draft_id": None,
            "is_archived": False,
            "archived_at": None,
            "is_global_default": False,
            "node_count": 0,
            "revision": 1,
            "created_at": now,
            "updated_at": now,
        }
        with self._lock, self.connection(target) as connection:
            connection.execute(
                """
                INSERT INTO workflows(
                    id, name, description, source_type, source_identifier,
                    project_id, source_workflow_id, current_version_id, draft_id,
                    is_archived, archived_at, is_global_default, node_count, revision,
                    created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id, name, description, source_type, source_identifier,
                    project_id, source_workflow_id, None, None,
                    0, None, 0, 0, 1, now, now,
                ),
            )
        return workflow

    def get_workflow(
        self,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """获取工作流详情，包括 current_version 和 draft 摘要。"""
        target = environment or self._active_environment
        with self.connection(target) as connection:
            row = connection.execute(
                """
                SELECT w.id, w.name, w.description, w.source_type, w.source_identifier,
                       w.project_id, w.source_workflow_id, w.current_version_id, w.draft_id,
                       w.is_archived, w.archived_at, w.is_global_default, w.node_count,
                       w.revision, w.created_at, w.updated_at
                FROM workflows w
                WHERE w.id = ?
                """,
                (workflow_id,),
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["is_archived"] = bool(result["is_archived"])
            result["is_global_default"] = bool(result["is_global_default"])
            current_version = None
            if row["current_version_id"]:
                cv = connection.execute(
                    """
                    SELECT id, version_number, label, node_count, checksum,
                           is_validated, created_at
                    FROM workflow_versions
                    WHERE id = ?
                    """,
                    (row["current_version_id"],),
                ).fetchone()
                if cv:
                    current_version = dict(cv)
                    current_version["is_validated"] = bool(current_version["is_validated"])
            result["current_version"] = current_version
            draft = None
            if row["draft_id"]:
                dr = connection.execute(
                    """
                    SELECT id, workflow_id, node_count, updated_at
                    FROM workflow_drafts
                    WHERE id = ?
                    """,
                    (row["draft_id"],),
                ).fetchone()
                if dr:
                    draft = dict(dr)
            result["draft"] = draft
        return result

    def list_workflows(
        self,
        *,
        project_id: str | None = None,
        include_global: bool = True,
        include_archived: bool = False,
        archived_only: bool = False,
        search: str | None = None,
        sort: str = "updated",
        limit: int = 50,
        offset: int = 0,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """列出工作流。project_id=None 列全局模板，project_id 非空列项目副本+全局模板。

        - include_archived=True: 返回所有工作流（含归档）
        - archived_only=True: 只返回归档的工作流（优先级高于 include_archived）
        - 两者都为 False: 只返回未归档的工作流
        """
        target = environment or self._active_environment
        conditions: list[str] = []
        params: list[object] = []
        if project_id is None:
            conditions.append("project_id IS NULL")
        else:
            if include_global:
                conditions.append("(project_id = ? OR project_id IS NULL)")
                params.append(project_id)
            else:
                conditions.append("project_id = ?")
                params.append(project_id)
        if archived_only:
            conditions.append("is_archived = 1")
        elif not include_archived:
            conditions.append("is_archived = 0")
        if search:
            conditions.append("(name LIKE ? OR description LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        where_clause = " WHERE " + " AND ".join(conditions)
        order_clause = {
            "updated": " ORDER BY updated_at DESC, created_at DESC",
            "created": " ORDER BY created_at DESC, updated_at DESC",
            "name": " ORDER BY name ASC, created_at ASC",
            "node_count": " ORDER BY node_count DESC, updated_at DESC",
        }.get(sort, " ORDER BY updated_at DESC, created_at DESC")
        with self.connection(target) as connection:
            count_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM workflows{where_clause}",
                params,
            ).fetchone()
            total = int(count_row["count"])
            rows = connection.execute(
                f"""
                SELECT id, name, description, source_type, source_identifier,
                       project_id, source_workflow_id, current_version_id, draft_id,
                       is_archived, archived_at, is_global_default, node_count,
                       revision, created_at, updated_at
                FROM workflows{where_clause}{order_clause}
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["is_archived"] = bool(item["is_archived"])
            item["is_global_default"] = bool(item["is_global_default"])
            items.append(item)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        }

    def update_workflow(
        self,
        workflow_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """更新工作流基本信息。同时递增 revision。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if existing is None:
                return None
            set_parts: list[str] = []
            params: list[object] = []
            if name is not None:
                set_parts.append("name = ?")
                params.append(name)
            if description is not None:
                set_parts.append("description = ?")
                params.append(description)
            set_parts.append("revision = revision + 1")
            set_parts.append("updated_at = ?")
            params.append(now)
            params.append(workflow_id)
            connection.execute(
                f"UPDATE workflows SET {', '.join(set_parts)} WHERE id = ?",
                params,
            )
            row = connection.execute(
                """
                SELECT id, name, description, source_type, source_identifier,
                       project_id, source_workflow_id, current_version_id, draft_id,
                       is_archived, archived_at, is_global_default, node_count,
                       revision, created_at, updated_at
                FROM workflows
                WHERE id = ?
                """,
                (workflow_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_archived"] = bool(result["is_archived"])
        result["is_global_default"] = bool(result["is_global_default"])
        return result

    def delete_workflow(
        self,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> bool:
        """删除工作流（级联删除版本、草稿、插槽）。"""
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            cursor = connection.execute(
                "DELETE FROM workflows WHERE id = ?",
                (workflow_id,),
            )
            return cursor.rowcount > 0

    def archive_workflow(
        self,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """归档工作流。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE workflows SET is_archived = 1, archived_at = ?, updated_at = ? WHERE id = ?",
                (now, now, workflow_id),
            )
            row = connection.execute(
                """
                SELECT id, name, description, source_type, source_identifier,
                       project_id, source_workflow_id, current_version_id, draft_id,
                       is_archived, archived_at, is_global_default, node_count,
                       revision, created_at, updated_at
                FROM workflows
                WHERE id = ?
                """,
                (workflow_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_archived"] = bool(result["is_archived"])
        result["is_global_default"] = bool(result["is_global_default"])
        return result

    def restore_workflow(
        self,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """恢复归档工作流。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if existing is None:
                return None
            connection.execute(
                "UPDATE workflows SET is_archived = 0, archived_at = NULL, updated_at = ? WHERE id = ?",
                (now, workflow_id),
            )
            row = connection.execute(
                """
                SELECT id, name, description, source_type, source_identifier,
                       project_id, source_workflow_id, current_version_id, draft_id,
                       is_archived, archived_at, is_global_default, node_count,
                       revision, created_at, updated_at
                FROM workflows
                WHERE id = ?
                """,
                (workflow_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_archived"] = bool(result["is_archived"])
        result["is_global_default"] = bool(result["is_global_default"])
        return result

    def copy_workflow(
        self,
        workflow_id: str,
        *,
        new_name: str | None = None,
        project_id: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """复制工作流。project_id 为 None 时复制为全局模板，非 None 时创建项目副本。
        source_workflow_id 指向源工作流。复制草稿但不复制版本。"""
        target = environment or self._active_environment
        source = self.get_workflow(workflow_id, environment=target)
        if source is None:
            raise ValueError("工作流不存在。")
        now = datetime.now(timezone.utc).isoformat()
        new_id = uuid4().hex
        name = new_name or f"{source['name']} (副本)"
        with self._lock, self.connection(target) as connection:
            connection.execute(
                """
                INSERT INTO workflows(
                    id, name, description, source_type, source_identifier,
                    project_id, source_workflow_id, current_version_id, draft_id,
                    is_archived, archived_at, is_global_default, node_count, revision,
                    created_at, updated_at
                )
                VALUES(?, ?, ?, 'copy', '', ?, ?, NULL, NULL, 0, NULL, 0, ?, 1, ?, ?)
                """,
                (
                    new_id, name, source.get("description", ""),
                    project_id, workflow_id,
                    int(source.get("node_count") or 0), now, now,
                ),
            )
            draft_row = connection.execute(
                """
                SELECT normalized_graph, raw_ui_json, raw_api_json, node_count, semantic_slots_json
                FROM workflow_drafts
                WHERE workflow_id = ?
                """,
                (workflow_id,),
            ).fetchone()
            if draft_row:
                new_draft_id = uuid4().hex
                connection.execute(
                    """
                    INSERT INTO workflow_drafts(
                        id, workflow_id, normalized_graph, raw_ui_json, raw_api_json,
                        node_count, semantic_slots_json, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_draft_id, new_id,
                        draft_row["normalized_graph"], draft_row["raw_ui_json"],
                        draft_row["raw_api_json"], draft_row["node_count"],
                        draft_row["semantic_slots_json"], now, now,
                    ),
                )
                connection.execute(
                    "UPDATE workflows SET draft_id = ? WHERE id = ?",
                    (new_draft_id, new_id),
                )
            slot_rows = connection.execute(
                """
                SELECT slot_name, slot_type, node_id, input_name, transform_rule,
                       default_value, is_required, conflict_strategy
                FROM semantic_slots
                WHERE workflow_id = ?
                """,
                (workflow_id,),
            ).fetchall()
            for sr in slot_rows:
                connection.execute(
                    """
                    INSERT INTO semantic_slots(
                        id, workflow_id, slot_name, slot_type, node_id, input_name,
                        transform_rule, default_value, is_required, conflict_strategy,
                        created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid4().hex, new_id,
                        sr["slot_name"], sr["slot_type"], sr["node_id"], sr["input_name"],
                        sr["transform_rule"], sr["default_value"], sr["is_required"],
                        sr["conflict_strategy"], now, now,
                    ),
                )
        copied = self.get_workflow(new_id, environment=target)
        assert copied is not None
        return copied

    def publish_workflow_version(
        self,
        workflow_id: str,
        *,
        label: str = "",
        normalized_graph: str,
        raw_ui_json: str | None = None,
        raw_api_json: str | None = None,
        node_count: int = 0,
        checksum: str = "",
        is_validated: bool = False,
        validation_result: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """发布不可变版本。version_number 自增。更新 workflow.current_version_id。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        version_id = uuid4().hex
        with self._lock, self.connection(target) as connection:
            existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("工作流不存在。")
            max_row = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) AS max_num FROM workflow_versions WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
            next_number = int(max_row["max_num"]) + 1
            connection.execute(
                """
                INSERT INTO workflow_versions(
                    id, workflow_id, version_number, label, normalized_graph,
                    raw_ui_json, raw_api_json, node_count, checksum,
                    is_validated, validation_result, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id, workflow_id, next_number, label, normalized_graph,
                    raw_ui_json, raw_api_json, node_count, checksum,
                    1 if is_validated else 0, validation_result, now,
                ),
            )
            connection.execute(
                "UPDATE workflows SET current_version_id = ?, node_count = ?, revision = revision + 1, updated_at = ? WHERE id = ?",
                (version_id, node_count, now, workflow_id),
            )
            row = connection.execute(
                """
                SELECT id, workflow_id, version_number, label, normalized_graph,
                       raw_ui_json, raw_api_json, node_count, checksum,
                       is_validated, validation_result, created_at
                FROM workflow_versions
                WHERE id = ?
                """,
                (version_id,),
            ).fetchone()
        result = dict(row)
        result["is_validated"] = bool(result["is_validated"])
        return result

    def list_workflow_versions(
        self,
        workflow_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """列出工作流的版本（按 version_number 降序）。"""
        target = environment or self._active_environment
        with self.connection(target) as connection:
            count_row = connection.execute(
                "SELECT COUNT(*) AS count FROM workflow_versions WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
            total = int(count_row["count"])
            rows = connection.execute(
                """
                SELECT id, workflow_id, version_number, label, node_count, checksum,
                       is_validated, validation_result, created_at
                FROM workflow_versions
                WHERE workflow_id = ?
                ORDER BY version_number DESC
                LIMIT ? OFFSET ?
                """,
                (workflow_id, limit, offset),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["is_validated"] = bool(item["is_validated"])
            items.append(item)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + len(items)) < total,
        }

    def get_workflow_version(
        self,
        version_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """获取版本详情，包含 normalized_graph/raw_ui_json/raw_api_json。"""
        target = environment or self._active_environment
        with self.connection(target) as connection:
            row = connection.execute(
                """
                SELECT id, workflow_id, version_number, label, normalized_graph,
                       raw_ui_json, raw_api_json, node_count, checksum,
                       is_validated, validation_result, created_at
                FROM workflow_versions
                WHERE id = ?
                """,
                (version_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_validated"] = bool(result["is_validated"])
        return result

    def get_workflow_draft(
        self,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """获取工作流草稿。"""
        target = environment or self._active_environment
        with self.connection(target) as connection:
            row = connection.execute(
                """
                SELECT id, workflow_id, normalized_graph, raw_ui_json, raw_api_json,
                       node_count, semantic_slots_json, last_node_id, last_link_id,
                       validation_state, layout_state, created_at, updated_at
                FROM workflow_drafts
                WHERE workflow_id = ?
                """,
                (workflow_id,),
            ).fetchone()
        return dict(row) if row else None

    def save_workflow_draft(
        self,
        workflow_id: str,
        *,
        normalized_graph: str,
        raw_ui_json: str | None = None,
        raw_api_json: str | None = None,
        node_count: int = 0,
        semantic_slots_json: str = "[]",
        last_node_id: int | None = None,
        last_link_id: int | None = None,
        validation_state: str | None = None,
        layout_state: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """保存草稿（upsert）。如果没有草稿则创建，有则更新。同时更新 workflow.draft_id 和 node_count。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("工作流不存在。")
            existing_draft = connection.execute(
                "SELECT id, last_node_id, last_link_id, validation_state, layout_state FROM workflow_drafts WHERE workflow_id = ?",
                (workflow_id,),
            ).fetchone()
            if existing_draft:
                draft_id = existing_draft["id"]
                # 保留未传入字段的现有值（草稿增量更新）
                resolved_last_node = last_node_id if last_node_id is not None else int(existing_draft["last_node_id"] or 0)
                resolved_last_link = last_link_id if last_link_id is not None else int(existing_draft["last_link_id"] or 0)
                resolved_validation = validation_state if validation_state is not None else existing_draft["validation_state"]
                resolved_layout = layout_state if layout_state is not None else existing_draft["layout_state"]
                connection.execute(
                    """
                    UPDATE workflow_drafts
                    SET normalized_graph = ?, raw_ui_json = ?, raw_api_json = ?,
                        node_count = ?, semantic_slots_json = ?,
                        last_node_id = ?, last_link_id = ?, validation_state = ?,
                        layout_state = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (normalized_graph, raw_ui_json, raw_api_json,
                     node_count, semantic_slots_json,
                     resolved_last_node, resolved_last_link, resolved_validation,
                     resolved_layout,
                     now, draft_id),
                )
            else:
                draft_id = uuid4().hex
                connection.execute(
                    """
                    INSERT INTO workflow_drafts(
                        id, workflow_id, normalized_graph, raw_ui_json, raw_api_json,
                        node_count, semantic_slots_json, last_node_id, last_link_id,
                        validation_state, layout_state, created_at, updated_at
                    )
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft_id, workflow_id, normalized_graph, raw_ui_json, raw_api_json,
                        node_count, semantic_slots_json,
                        last_node_id or 0, last_link_id or 0, validation_state,
                        layout_state,
                        now, now,
                    ),
                )
            connection.execute(
                "UPDATE workflows SET draft_id = ?, node_count = ?, updated_at = ? WHERE id = ?",
                (draft_id, node_count, now, workflow_id),
            )
            row = connection.execute(
                """
                SELECT id, workflow_id, normalized_graph, raw_ui_json, raw_api_json,
                       node_count, semantic_slots_json, last_node_id, last_link_id,
                       validation_state, layout_state, created_at, updated_at
                FROM workflow_drafts
                WHERE id = ?
                """,
                (draft_id,),
            ).fetchone()
        return dict(row)

    def batch_get_node_definitions(
        self,
        node_classes: list[str],
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, dict[str, object]]:
        """批量获取节点定义。返回 {node_class: definition_dict}。

        用于节点编辑器加载工作流所需的所有节点定义。
        """
        if not node_classes:
            return {}
        target = environment or self._active_environment
        # 去重并保持顺序
        unique_classes: list[str] = []
        seen: set[str] = set()
        for cls in node_classes:
            if cls and cls not in seen:
                seen.add(cls)
                unique_classes.append(cls)
        placeholders = ",".join("?" for _ in unique_classes)
        with self.connection(target) as connection:
            rows = connection.execute(
                f"""
                SELECT node_class, python_module, category, display_name,
                       is_custom_node, definition_json, updated_at
                FROM comfyui_node_definitions
                WHERE node_class IN ({placeholders})
                """,
                unique_classes,
            ).fetchall()
        result: dict[str, dict[str, object]] = {}
        for row in rows:
            try:
                definition = json.loads(row["definition_json"])
            except (TypeError, ValueError):
                definition = {}
            result[row["node_class"]] = {
                "node_class": row["node_class"],
                "python_module": row["python_module"],
                "category": row["category"],
                "display_name": row["display_name"],
                "is_custom_node": bool(row["is_custom_node"]),
                "updated_at": row["updated_at"],
                "definition": definition,
            }
        return result

    def set_global_default_workflow(
        self,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """设置全局默认工作流。清除其他工作流的 is_global_default。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("工作流不存在。")
            connection.execute(
                "UPDATE workflows SET is_global_default = 0 WHERE is_global_default = 1"
            )
            connection.execute(
                "UPDATE workflows SET is_global_default = 1, updated_at = ? WHERE id = ?",
                (now, workflow_id),
            )
            row = connection.execute(
                """
                SELECT id, name, description, source_type, source_identifier,
                       project_id, source_workflow_id, current_version_id, draft_id,
                       is_archived, archived_at, is_global_default, node_count,
                       revision, created_at, updated_at
                FROM workflows
                WHERE id = ?
                """,
                (workflow_id,),
            ).fetchone()
        result = dict(row)
        result["is_archived"] = bool(result["is_archived"])
        result["is_global_default"] = bool(result["is_global_default"])
        return result

    def set_project_default_workflow(
        self,
        project_id: str,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """设置项目默认工作流（upsert project_default_workflows）。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self.connection(target) as connection:
            workflow_existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if workflow_existing is None:
                raise ValueError("工作流不存在。")
            connection.execute(
                """
                INSERT INTO project_default_workflows(project_id, workflow_id, set_at)
                VALUES(?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    workflow_id = excluded.workflow_id,
                    set_at = excluded.set_at
                """,
                (project_id, workflow_id, now),
            )
        return {
            "project_id": project_id,
            "workflow_id": workflow_id,
            "set_at": now,
        }

    def get_project_default_workflow(
        self,
        project_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        """获取项目默认工作流。"""
        target = environment or self._active_environment
        with self.connection(target) as connection:
            row = connection.execute(
                """
                SELECT pdw.project_id, pdw.workflow_id, pdw.set_at,
                       w.id, w.name, w.description, w.node_count, w.revision,
                       w.source_type, w.source_identifier, w.project_id AS workflow_project_id,
                       w.source_workflow_id, w.current_version_id, w.draft_id,
                       w.is_archived, w.archived_at, w.is_global_default,
                       w.created_at, w.updated_at
                FROM project_default_workflows pdw
                JOIN workflows w ON w.id = pdw.workflow_id
                WHERE pdw.project_id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["is_archived"] = bool(result.get("is_archived"))
        result["is_global_default"] = bool(result.get("is_global_default"))
        return result

    def list_semantic_slots(
        self,
        workflow_id: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """列出工作流的语义插槽。"""
        target = environment or self._active_environment
        with self.connection(target) as connection:
            rows = connection.execute(
                """
                SELECT id, workflow_id, slot_name, slot_type, node_id, input_name,
                       transform_rule, default_value, is_required, conflict_strategy,
                       created_at, updated_at
                FROM semantic_slots
                WHERE workflow_id = ?
                ORDER BY slot_name ASC
                """,
                (workflow_id,),
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["is_required"] = bool(item["is_required"])
            items.append(item)
        return items

    def set_semantic_slot(
        self,
        workflow_id: str,
        slot_name: str,
        *,
        slot_type: str,
        node_id: str,
        input_name: str,
        transform_rule: str = "",
        default_value: str | None = None,
        is_required: bool = False,
        conflict_strategy: str = "overwrite",
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """设置语义插槽（upsert by workflow_id + slot_name）。"""
        target = environment or self._active_environment
        now = datetime.now(timezone.utc).isoformat()
        slot_id = uuid4().hex
        with self._lock, self.connection(target) as connection:
            existing = connection.execute(
                "SELECT id FROM workflows WHERE id = ?",
                (workflow_id,),
            ).fetchone()
            if existing is None:
                raise ValueError("工作流不存在。")
            connection.execute(
                """
                INSERT INTO semantic_slots(
                    id, workflow_id, slot_name, slot_type, node_id, input_name,
                    transform_rule, default_value, is_required, conflict_strategy,
                    created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id, slot_name) DO UPDATE SET
                    slot_type = excluded.slot_type,
                    node_id = excluded.node_id,
                    input_name = excluded.input_name,
                    transform_rule = excluded.transform_rule,
                    default_value = excluded.default_value,
                    is_required = excluded.is_required,
                    conflict_strategy = excluded.conflict_strategy,
                    updated_at = excluded.updated_at
                """,
                (
                    slot_id, workflow_id, slot_name, slot_type, node_id, input_name,
                    transform_rule, default_value, 1 if is_required else 0,
                    conflict_strategy, now, now,
                ),
            )
            row = connection.execute(
                """
                SELECT id, workflow_id, slot_name, slot_type, node_id, input_name,
                       transform_rule, default_value, is_required, conflict_strategy,
                       created_at, updated_at
                FROM semantic_slots
                WHERE workflow_id = ? AND slot_name = ?
                """,
                (workflow_id, slot_name),
            ).fetchone()
        result = dict(row)
        result["is_required"] = bool(result["is_required"])
        return result

    def delete_semantic_slot(
        self,
        workflow_id: str,
        slot_name: str,
        *,
        environment: DatabaseEnvironment | None = None,
    ) -> bool:
        """删除语义插槽。"""
        target = environment or self._active_environment
        with self._lock, self.connection(target) as connection:
            cursor = connection.execute(
                "DELETE FROM semantic_slots WHERE workflow_id = ? AND slot_name = ?",
                (workflow_id, slot_name),
            )
            return cursor.rowcount > 0


