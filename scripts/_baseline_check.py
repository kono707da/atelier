"""One-off baseline snapshot for production database before characters development."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "databases" / "atelier.production.sqlite3"


def main() -> int:
    if not DB_PATH.exists():
        print(f"ERROR: production database not found: {DB_PATH}", file=sys.stderr)
        return 1

    data = DB_PATH.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    size = os.path.getsize(DB_PATH)
    mtime = os.path.getmtime(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        projects = conn.execute("SELECT id, name FROM projects ORDER BY name").fetchall()
        chapters = conn.execute("SELECT id, name FROM chapters ORDER BY name").fetchall()
        scenes = conn.execute("SELECT id, name FROM large_scenes ORDER BY name").fetchall()
    finally:
        conn.close()

    print(f"SHA256: {sha}")
    print(f"Size: {size} bytes")
    print(f"MTime: {mtime}")
    print(f"Projects: {len(projects)}")
    for p in projects:
        print(f"  - {p['id']} | {p['name']}")
    print(f"Chapters: {len(chapters)}")
    for c in chapters:
        print(f"  - {c['id']} | {c['name']}")
    print(f"LargeScenes: {len(scenes)}")
    for s in scenes:
        print(f"  - {s['id']} | {s['name']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
