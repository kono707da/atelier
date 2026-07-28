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
                    revision INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

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
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1,
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
                    revision INTEGER NOT NULL DEFAULT 1,
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
                    revision INTEGER NOT NULL DEFAULT 1,
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
                    description, is_enabled, sort_order, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (branch_id, parent_type, parent_id, name,
                 description, 1 if is_enabled else 0,
                 max_order + 1, now, now),
            )
        return self.get_branch(branch_id, environment=target_environment)  # type: ignore[return-value]

    def update_branch(
        self,
        branch_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        is_enabled: bool | None = None,
        environment: DatabaseEnvironment | None = None,
    ) -> dict[str, object] | None:
        if all(v is None for v in (name, description, is_enabled)):
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
                s["pages"] = s_pages
                s["resources"] = s_resources
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

