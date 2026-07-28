from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app import character_database


class CharacterDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._original_state = {
            "csv_path": character_database._CSV_PATH,
            "sqlite_path": character_database._SQLITE_PATH,
            "state": character_database._state,
            "progress": character_database._progress,
            "total_rows": character_database._total_rows,
            "error": character_database._error,
            "import_thread": character_database._import_thread,
        }
        self.addCleanup(self._restore_module_state)

        root = Path(self._tmp.name)
        character_database._CSV_PATH = root / "characters.csv"
        character_database._SQLITE_PATH = root / "cache" / "characters.sqlite3"
        character_database._state = "loading"
        character_database._progress = 0.0
        character_database._total_rows = 0
        character_database._error = None
        character_database._import_thread = None
        character_database._CSV_PATH.write_text(
            "\n".join(
                [
                    "character,copyright,trigger,core_tags,count,solo_count,url",
                    "alpha,vocaloid,alpha,blue_hair,100,90,https://example.test/a",
                    "beta,touhou,beta,red_hair,80,70,https://example.test/b",
                    "gamma,vocaloid,gamma,green_hair,60,50,https://example.test/c",
                    "delta,original,delta,black_hair,40,30,https://example.test/d",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        character_database._import_csv_to_sqlite()
        self.assertEqual(character_database._state, "ready")

    def _restore_module_state(self) -> None:
        character_database._CSV_PATH = self._original_state["csv_path"]
        character_database._SQLITE_PATH = self._original_state["sqlite_path"]
        character_database._state = self._original_state["state"]
        character_database._progress = self._original_state["progress"]
        character_database._total_rows = self._original_state["total_rows"]
        character_database._error = self._original_state["error"]
        character_database._import_thread = self._original_state["import_thread"]

    def test_streamed_import_builds_searchable_cache(self) -> None:
        result = character_database.search(q="alp", page=1, page_size=50)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["character"], "alpha")
        self.assertEqual(character_database._count_existing_rows(), 4)
        self.assertTrue(character_database._existing_index_is_current())

    def test_copyright_suggestions_are_prefix_filtered_and_limited(self) -> None:
        self.assertEqual(
            character_database.list_copyrights(q="voc", limit=50),
            ["vocaloid"],
        )
        self.assertEqual(
            character_database.list_copyrights(q="", limit=2),
            ["original", "touhou"],
        )

    def test_read_connections_release_the_cache_file(self) -> None:
        character_database.search(page=1, page_size=2)
        character_database.list_copyrights(limit=2)
        character_database.stats()
        character_database._SQLITE_PATH.unlink()
        self.assertFalse(character_database._SQLITE_PATH.exists())


if __name__ == "__main__":
    unittest.main()
