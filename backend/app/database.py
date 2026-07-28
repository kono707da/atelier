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
                """
            )
            # Migrate legacy tables if they exist (pre-v0.1.7 schema)
            self._migrate_legacy_character_schema(connection)
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
                SELECT id, chapter_id, name, sort_order, created_at, updated_at
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
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        """Create a large scene at the end of a chapter's ordered scene list."""
        target_environment = environment or self._active_environment
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
                        id, chapter_id, name, sort_order, created_at, updated_at
                    )
                    VALUES(
                        :id, :chapter_id, :name, :sort_order, :created_at, :updated_at
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
                SELECT id, chapter_id, name, sort_order, created_at, updated_at
                FROM large_scenes
                WHERE id = ?
                """,
                (large_scene_id,),
            ).fetchone()
        return dict(row) if row else None

    def rename_large_scene(
        self,
        large_scene_id: str,
        name: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        clean_name = " ".join(name.split())
        if not clean_name:
            raise ValueError("大场景名称不能为空。")
        if len(clean_name) > 80:
            raise ValueError("大场景名称不能超过 80 个字符。")
        now = datetime.now(timezone.utc).isoformat()
        try:
            with self._lock, self.connection(target_environment) as connection:
                cursor = connection.execute(
                    """
                    UPDATE large_scenes
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean_name, now, large_scene_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("大场景不存在。")
        except sqlite3.IntegrityError as error:
            raise ValueError("该章节下已经存在同名大场景。") from error
        large_scene = self.get_large_scene(large_scene_id, target_environment)
        if large_scene is None:
            raise ValueError("大场景不存在。")
        return large_scene

    def delete_large_scene(
        self,
        large_scene_id: str,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object]:
        target_environment = environment or self._active_environment
        with self._lock, self.connection(target_environment) as connection:
            large_scene = connection.execute(
                """
                SELECT id, chapter_id, name, sort_order, created_at, updated_at
                FROM large_scenes
                WHERE id = ?
                """,
                (large_scene_id,),
            ).fetchone()
            if large_scene is None:
                raise ValueError("大场景不存在。")
            connection.execute(
                "DELETE FROM large_scenes WHERE id = ?", (large_scene_id,)
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
        lora_weight: float | None = None,
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
            if lora_weight is not None:
                if lora_weight < 0 or lora_weight > 2:
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
