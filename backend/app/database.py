from __future__ import annotations

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
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
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
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (name)
                );

                CREATE INDEX IF NOT EXISTS idx_characters_sort
                    ON characters(sort_order);

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
                    is_default INTEGER NOT NULL DEFAULT 0,
                    sort_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (character_id)
                        REFERENCES characters(id) ON DELETE CASCADE,
                    UNIQUE (character_id, name)
                );

                CREATE INDEX IF NOT EXISTS idx_character_variants_character_sort
                    ON character_variants(character_id, sort_order);

                CREATE TABLE IF NOT EXISTS specs (
                    id TEXT PRIMARY KEY,
                    spec_type TEXT NOT NULL,
                    custom_label TEXT NOT NULL DEFAULT '',
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
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (material_type, name),
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
                """
            )
            # Migrate legacy tables if they exist (pre-v0.1.7 schema)
            self._migrate_legacy_character_schema(connection)
            # Add scene_type column to large_scenes for pre-v0.2.0 databases
            self._migrate_large_scenes_scene_type(connection)
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
        self, environment: DatabaseEnvironment | None = None
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, name, status, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC, name ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_project(
        self,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, name, status, created_at, updated_at
                FROM projects
                WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_project(
        self,
        name: str,
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
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self._lock, self.connection(target_environment) as connection:
                connection.execute(
                    """
                    INSERT INTO projects(id, name, status, created_at, updated_at)
                    VALUES(:id, :name, :status, :created_at, :updated_at)
                    """,
                    project,
                )
        except sqlite3.IntegrityError as error:
            raise ValueError("已经存在同名项目。") from error
        return project

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
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        """List characters. If project_id given, return characters linked to that project.
        If project_id is None, return all global characters."""
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            if project_id is None:
                rows = connection.execute(
                    """
                    SELECT id, name, sort_order, created_at, updated_at
                    FROM characters
                    ORDER BY sort_order ASC, created_at ASC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT c.id, c.name, c.sort_order, c.created_at, c.updated_at
                    FROM characters c
                    JOIN project_characters pc ON pc.character_id = c.id
                    WHERE pc.project_id = ?
                    ORDER BY c.sort_order ASC, c.created_at ASC
                    """,
                    (project_id,),
                ).fetchall()
        return [dict(row) for row in rows]

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
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            row = connection.execute(
                """
                SELECT id, name, sort_order, created_at, updated_at
                FROM characters
                WHERE id = ?
                """,
                (character_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_character(
        self,
        name: str,
        project_id: str | None = None,
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
                    INSERT INTO characters(id, name, sort_order, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (character_id, clean_name, next_sort, now, now),
                )
                if project_id is not None:
                    connection.execute(
                        "INSERT INTO project_characters(project_id, character_id, created_at) VALUES (?, ?, ?)",
                        (project_id, character_id, now),
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
            raise ValueError("已存在同名人物。") from error
        return self.get_character(character_id, target_environment)  # type: ignore[return-value]

    def link_character_to_project(
        self,
        character_id: str,
        project_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> None:
        target_environment = environment or self._active_environment
        if self.get_character(character_id, target_environment) is None:
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

    def rename_character(
        self,
        character_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("人物名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("人物名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock, self.connection(target_environment) as connection:
                cursor = connection.execute(
                    "UPDATE characters SET name = ?, updated_at = ? WHERE id = ?",
                    (clean_name, now, character_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("人物不存在。")
        except sqlite3.IntegrityError as error:
            raise ValueError("已存在同名人物。") from error
        character = self.get_character(character_id, target_environment)
        if character is None:
            raise ValueError("人物不存在。")
        return character

    def delete_character(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            character = connection.execute(
                "SELECT id, name, sort_order, created_at, updated_at FROM characters WHERE id = ?",
                (character_id,),
            ).fetchone()
            if character is None:
                raise ValueError("人物不存在。")
            connection.execute("DELETE FROM characters WHERE id = ?", (character_id,))
        return dict(character)

    # ── Character Variants ──────────────────────────────────────

    def list_character_variants(
        self,
        character_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, character_id, name, is_default, sort_order, created_at, updated_at
                FROM character_variants
                WHERE character_id = ?
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
                SELECT id, character_id, name, is_default, sort_order, created_at, updated_at
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
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("形象变体名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("形象变体名称不能超过 80 个字符。")
        character = self.get_character(character_id, target_environment)
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
                        id, character_id, name, is_default, sort_order, created_at, updated_at
                    )
                    VALUES(?, ?, ?, 0, ?, ?, ?)
                    """,
                    (variant_id, character_id, clean_name, next_sort, now, now),
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

    def rename_character_variant(
        self,
        variant_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("形象变体名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("形象变体名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock, self.connection(target_environment) as connection:
                cursor = connection.execute(
                    """
                    UPDATE character_variants
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean_name, now, variant_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("形象变体不存在。")
        except sqlite3.IntegrityError as error:
            raise ValueError("该人物下已经存在同名形象变体。") from error
        variant = self.get_character_variant(variant_id, target_environment)
        if variant is None:
            raise ValueError("形象变体不存在。")
        return variant

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

    # ── Specs (global) ──────────────────────────────────────────

    def list_specs(
        self,
        environment: DatabaseEnvironment | None = None,
    ) -> list[dict[str, object]]:
        target_environment = environment or self._active_environment
        with self.connection(target_environment) as connection:
            rows = connection.execute(
                """
                SELECT id, spec_type, custom_label, sort_order, created_at, updated_at
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
                SELECT id, spec_type, custom_label, sort_order, created_at, updated_at
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
                    INSERT INTO specs(id, spec_type, custom_label, sort_order, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (spec_id, spec_type, custom_label, next_sort, now, now),
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
        custom_label: str | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        spec = self.get_spec(spec_id, target_environment)
        if spec is None:
            raise ValueError("规格不存在。")
        if spec["spec_type"] != "custom":
            raise ValueError("只有自定义规格可以修改标签。")
        now = datetime.now(timezone.utc).isoformat()
        clean_label = " ".join((custom_label or "").split())
        if not clean_label:
            raise ValueError("自定义规格标签不能为空。")
        if len(clean_label) > 80:
            raise ValueError("自定义规格标签不能超过 80 个字符。")
        try:
            with self._lock, self.connection(target_environment) as connection:
                cursor = connection.execute(
                    "UPDATE specs SET custom_label = ?, updated_at = ? WHERE id = ?",
                    (clean_label, now, spec_id),
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
                SELECT id, spec_type, custom_label, sort_order, created_at, updated_at
                FROM specs
                WHERE id = ?
                """,
                (spec_id,),
            ).fetchone()
            if spec is None:
                raise ValueError("规格不存在。")
            connection.execute("DELETE FROM specs WHERE id = ?", (spec_id,))
        return dict(spec)

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
                       created_at, updated_at
                FROM character_spec_values
                WHERE id = ?
                """,
                (spec_value_id,),
            ).fetchone()
        return dict(row) if row else None

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
                       created_at, updated_at
                FROM materials
                WHERE id = ?
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
            "project_count": len(self.list_projects(environment)),
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
