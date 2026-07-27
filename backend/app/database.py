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
                """
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
