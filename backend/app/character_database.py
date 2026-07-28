"""Danbooru character database — SQLite + FTS5 read-only lookup.

CSV source: danbooru_character.csv (from comfyui-manager project, ~244k rows).
On first start the CSV is imported into a sidecar SQLite file with a FTS5
full-text index. Subsequent starts reuse the SQLite file as long as the CSV
has not changed (compared by mtime).

Import runs in a background daemon thread with batched INSERTs and short
sleeps between batches to release the GIL, so the FastAPI request loop can
keep serving other endpoints while the index is being built.
"""

from __future__ import annotations

import csv
import sqlite3
import threading
import time
from pathlib import Path
from typing import Literal


_CSV_DIR = Path(__file__).resolve().parents[2] / "data" / "character-database"
_CSV_PATH = _CSV_DIR / "danbooru_character.csv"
_SQLITE_PATH = _CSV_DIR / "danbooru_character.sqlite3"

ImportState = Literal["pending", "loading", "ready", "error"]


class CharacterDatabaseNotReadyError(RuntimeError):
    """Raised when a query is issued before the SQLite index is ready."""


_lock = threading.RLock()
_state: ImportState = "pending"
_progress: float = 0.0
_total_rows: int = 0
_error: str | None = None
_import_thread: threading.Thread | None = None


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_SQLITE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _build_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TABLE IF EXISTS characters_fts;
        DROP TABLE IF EXISTS characters;
        DROP TABLE IF EXISTS db_meta;

        CREATE TABLE characters (
            id INTEGER PRIMARY KEY,
            character TEXT NOT NULL DEFAULT '',
            copyright TEXT NOT NULL DEFAULT '',
            trigger TEXT NOT NULL DEFAULT '',
            core_tags TEXT NOT NULL DEFAULT '',
            count INTEGER NOT NULL DEFAULT 0,
            solo_count INTEGER NOT NULL DEFAULT 0,
            url TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX idx_characters_count ON characters(count);
        CREATE INDEX idx_characters_character ON characters(character);
        CREATE INDEX idx_characters_copyright ON characters(copyright);

        CREATE VIRTUAL TABLE characters_fts USING fts5(
            character,
            copyright,
            trigger,
            core_tags,
            content='characters',
            content_rowid='id',
            tokenize="unicode61 separators '_-.'"
        );

        CREATE TABLE db_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )


def _existing_index_is_current() -> bool:
    """Return True if the sidecar SQLite exists and matches the CSV mtime."""
    if not _SQLITE_PATH.exists():
        return False
    try:
        conn = sqlite3.connect(_SQLITE_PATH, timeout=5)
        try:
            row = conn.execute(
                "SELECT value FROM db_meta WHERE key = 'csv_mtime'"
            ).fetchone()
            row_count = conn.execute("SELECT COUNT(*) FROM characters").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        return False
    if not row or row_count == 0:
        return False
    try:
        csv_mtime = str(_CSV_PATH.stat().st_mtime)
    except OSError:
        return False
    return row[0] == csv_mtime


def _count_existing_rows() -> int:
    """Return the row count of the existing sidecar SQLite, or 0 on error."""
    if not _SQLITE_PATH.exists():
        return 0
    try:
        conn = sqlite3.connect(_SQLITE_PATH, timeout=5)
        try:
            row = conn.execute("SELECT COUNT(*) FROM characters").fetchone()
        finally:
            conn.close()
        return int(row[0]) if row else 0
    except sqlite3.DatabaseError:
        return 0


def _import_csv_to_sqlite() -> None:
    """Read the CSV and populate the SQLite index in batched inserts.

    Writes to a temporary file and atomically renames on success so an
    interrupted import never leaves a corrupt half-built index behind.
    Releases the GIL between batches so the FastAPI request loop can keep
    serving other endpoints during the import.
    """
    global _state, _progress, _total_rows, _error
    tmp_path = _SQLITE_PATH.with_suffix(".sqlite3.tmp")
    try:
        if not _CSV_PATH.exists():
            _state = "error"
            _error = f"CSV not found: {_CSV_PATH}"
            return

        # Write to a temp file so an interrupted import doesn't corrupt the
        # last good index.
        if tmp_path.exists():
            tmp_path.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = tmp_path.with_suffix(tmp_path.suffix + suffix)
            if sidecar.exists():
                sidecar.unlink()

        conn = sqlite3.connect(tmp_path, timeout=30)
        try:
            # Import-time pragmas for speed; we switch to WAL after.
            conn.execute("PRAGMA journal_mode = OFF")
            conn.execute("PRAGMA synchronous = OFF")
            _build_schema(conn)

            with open(_CSV_PATH, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                # First pass: count rows for progress reporting.
                rows = list(reader)
                _total_rows = len(rows)

                batch: list[tuple] = []
                batch_size = 2000
                inserted = 0
                for idx, row in enumerate(rows, start=1):
                    try:
                        batch.append((
                            idx,
                            row.get("character", ""),
                            row.get("copyright", ""),
                            row.get("trigger", ""),
                            row.get("core_tags", ""),
                            int(row.get("count", 0) or 0),
                            int(row.get("solo_count", 0) or 0),
                            row.get("url", ""),
                        ))
                    except (ValueError, TypeError):
                        continue
                    if len(batch) >= batch_size:
                        conn.executemany(
                            "INSERT INTO characters(id, character, copyright, trigger, core_tags, count, solo_count, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            batch,
                        )
                        conn.commit()
                        inserted += len(batch)
                        batch.clear()
                        _progress = inserted / _total_rows if _total_rows else 1.0
                        # Yield to other threads so request loop stays responsive.
                        time.sleep(0.005)
                if batch:
                    conn.executemany(
                        "INSERT INTO characters(id, character, copyright, trigger, core_tags, count, solo_count, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        batch,
                    )
                    conn.commit()
                    inserted += len(batch)
                _progress = 1.0

                # Rebuild FTS index from the characters table.
                conn.execute("INSERT INTO characters_fts(rowid, character, copyright, trigger, core_tags) SELECT id, character, copyright, trigger, core_tags FROM characters")
                # Record CSV mtime so subsequent starts can skip re-import.
                try:
                    csv_mtime = str(_CSV_PATH.stat().st_mtime)
                except OSError:
                    csv_mtime = ""
                conn.execute(
                    "INSERT INTO db_meta(key, value) VALUES('csv_mtime', ?)",
                    (csv_mtime,),
                )
                conn.commit()
        finally:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except Exception:
                pass
            conn.close()

        # Atomically replace the old index with the freshly built one.
        if _SQLITE_PATH.exists():
            _SQLITE_PATH.unlink()
        for suffix in ("-wal", "-shm"):
            sidecar = _SQLITE_PATH.with_suffix(_SQLITE_PATH.suffix + suffix)
            if sidecar.exists():
                sidecar.unlink()
        tmp_path.rename(_SQLITE_PATH)

        _state = "ready"
    except Exception as exc:
        _state = "error"
        _error = str(exc)
    finally:
        # Clean up the temp file if something went wrong.
        if _state != "ready" and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _ensure_import_started() -> None:
    """Start the background import thread if needed (idempotent)."""
    global _import_thread, _state, _error, _total_rows, _progress
    if _state == "ready" or _import_thread is not None:
        return
    if not _CSV_PATH.exists():
        _state = "error"
        _error = f"CSV not found: {_CSV_PATH}"
        return
    with _lock:
        if _state == "ready" or _import_thread is not None:
            return
        # If the sidecar SQLite is already in sync with the CSV, skip import.
        if _existing_index_is_current():
            _state = "ready"
            _progress = 1.0
            _total_rows = _count_existing_rows()
            return
        _state = "loading"
        _progress = 0.0
        _error = None
        _import_thread = threading.Thread(
            target=_import_csv_to_sqlite,
            name="character-database-import",
            daemon=True,
        )
        _import_thread.start()


def _is_ready() -> bool:
    return _state == "ready" and _SQLITE_PATH.exists()


def _build_fts_query(q: str) -> str:
    """Convert a user query into a FTS5 prefix query.

    "hatsune miku" -> "hatsune* AND miku*"
    "hatsune_miku" -> "hatsune* AND miku*" (separators already split by tokenizer)
    """
    tokens = [t for t in q.replace("_", " ").replace("-", " ").split() if t]
    if not tokens:
        return ""
    # Escape FTS5 special characters by quoting each token, then add prefix *.
    safe = []
    for tok in tokens:
        # Strip double quotes; FTS5 treats "..." as a phrase.
        cleaned = tok.replace('"', "")
        if cleaned:
            safe.append(f'"{cleaned}"*')
    return " AND ".join(safe) if safe else ""


def status() -> dict[str, object]:
    """Return the current import status for the frontend to poll."""
    _ensure_import_started()
    return {
        "state": _state,
        "progress": round(_progress, 4),
        "total_rows": _total_rows,
        "error": _error,
        "csv_path": str(_CSV_PATH),
        "sqlite_path": str(_SQLITE_PATH),
    }


def search(
    q: str = "",
    copyright_filter: str = "",
    sort: str = "count_desc",
    page: int = 1,
    page_size: int = 50,
) -> dict[str, object]:
    if not _is_ready():
        raise CharacterDatabaseNotReadyError(
            f"Character database is {_state}; please retry shortly."
        )

    order_map = {
        "count_desc": "count DESC",
        "count_asc": "count ASC",
        "character_asc": "character ASC",
        "character_desc": "character DESC",
    }
    order_sql = order_map.get(sort, "count DESC")

    where_clauses: list[str] = []
    params: list[object] = []
    q_clean = q.strip()
    if q_clean:
        fts_query = _build_fts_query(q_clean)
        if fts_query:
            where_clauses.append(
                "id IN (SELECT rowid FROM characters_fts WHERE characters_fts MATCH ?)"
            )
            params.append(fts_query)
    if copyright_filter:
        where_clauses.append("copyright = ?")
        params.append(copyright_filter)

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with _connect() as conn:
        total_row = conn.execute(
            f"SELECT COUNT(*) AS c FROM characters{where_sql}", params
        ).fetchone()
        total = int(total_row["c"]) if total_row else 0

        offset = max(0, (page - 1) * page_size)
        rows = conn.execute(
            f"SELECT character, copyright, trigger, core_tags, count, solo_count, url "
            f"FROM characters{where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    items = [dict(row) for row in rows]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def list_copyrights() -> list[str]:
    if not _is_ready():
        raise CharacterDatabaseNotReadyError(
            f"Character database is {_state}; please retry shortly."
        )
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT copyright FROM characters WHERE copyright != '' ORDER BY copyright"
        ).fetchall()
    return [row["copyright"] for row in rows]


def stats() -> dict[str, object]:
    if not _is_ready():
        return {
            "state": _state,
            "total_characters": 0,
            "total_copyrights": 0,
        }
    with _connect() as conn:
        total_row = conn.execute("SELECT COUNT(*) AS c FROM characters").fetchone()
        copyright_row = conn.execute(
            "SELECT COUNT(DISTINCT copyright) AS c FROM characters WHERE copyright != ''"
        ).fetchone()
    return {
        "state": _state,
        "total_characters": int(total_row["c"]) if total_row else 0,
        "total_copyrights": int(copyright_row["c"]) if copyright_row else 0,
    }
