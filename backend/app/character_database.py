"""Danbooru character database — read-only CSV lookup.

CSV source: danbooru_character.csv (from comfyui-manager project, ~244k rows).
Columns: character, copyright, trigger, core_tags, count, solo_count, url
"""

from __future__ import annotations

import csv
import os
import threading
from functools import lru_cache
from typing import TypedDict


class CharacterEntry(TypedDict):
    character: str
    copyright: str
    trigger: str
    core_tags: str
    count: int
    solo_count: int
    url: str


_CSV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "character-database",
    "danbooru_character.csv",
)

_lock = threading.Lock()
_cache: list[CharacterEntry] | None = None
_copyrights: list[str] | None = None


def _load() -> list[CharacterEntry]:
    global _cache, _copyrights
    if _cache is not None:
        return _cache
    with _lock:
        if _cache is not None:
            return _cache
        entries: list[CharacterEntry] = []
        copyrights: set[str] = set()
        if os.path.exists(_CSV_PATH):
            with open(_CSV_PATH, "r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        entry: CharacterEntry = {
                            "character": row.get("character", ""),
                            "copyright": row.get("copyright", ""),
                            "trigger": row.get("trigger", ""),
                            "core_tags": row.get("core_tags", ""),
                            "count": int(row.get("count", 0) or 0),
                            "solo_count": int(row.get("solo_count", 0) or 0),
                            "url": row.get("url", ""),
                        }
                        entries.append(entry)
                        if entry["copyright"]:
                            copyrights.add(entry["copyright"])
                    except (ValueError, KeyError):
                        continue
        _cache = entries
        _copyrights = sorted(copyrights)
        return _cache


def search(
    q: str = "",
    copyright_filter: str = "",
    sort: str = "count",
    page: int = 1,
    page_size: int = 50,
) -> dict[str, object]:
    entries = _load()
    q_lower = q.strip().lower()
    filtered: list[CharacterEntry] = []
    for entry in entries:
        if q_lower:
            if (
                q_lower not in entry["character"].lower()
                and q_lower not in entry["copyright"].lower()
                and q_lower not in entry["core_tags"].lower()
                and q_lower not in entry["trigger"].lower()
            ):
                continue
        if copyright_filter and entry["copyright"] != copyright_filter:
            continue
        filtered.append(entry)

    if sort == "az":
        filtered.sort(key=lambda e: e["character"])
    else:
        filtered.sort(key=lambda e: e["count"], reverse=True)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
    }


def list_copyrights() -> list[str]:
    _load()
    return _copyrights or []


def stats() -> dict[str, object]:
    entries = _load()
    copyrights_set = {e["copyright"] for e in entries if e["copyright"]}
    return {
        "total_characters": len(entries),
        "total_copyrights": len(copyrights_set),
    }
