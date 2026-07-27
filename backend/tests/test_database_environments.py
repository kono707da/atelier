from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.database import DatabaseManager, DatabaseSafetyError


class DatabaseEnvironmentTests(unittest.TestCase):
    def test_production_and_test_use_different_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            production = manager.descriptor("production").path
            test = manager.descriptor("test").path

            self.assertNotEqual(production, test)
            self.assertTrue(production.exists())
            self.assertTrue(test.exists())

    def test_isolation_check_only_writes_to_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))

            result = manager.verify_isolation()

            self.assertTrue(result["isolated"])
            self.assertEqual(manager.event_count("production"), 0)
            self.assertEqual(manager.event_count("test"), 1)

    def test_locked_test_process_cannot_activate_production(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(
                Path(directory),
                environment="test",
                locked_environment="test",
            )

            with self.assertRaises(DatabaseSafetyError):
                manager.activate("production")

    def test_database_environment_marker_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            with manager.connection("test") as connection:
                connection.execute(
                    "UPDATE atelier_meta SET value = 'production' WHERE key = 'environment'"
                )

            with self.assertRaises(DatabaseSafetyError):
                manager.initialize("test")

    def test_project_is_created_only_in_active_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(
                Path(directory),
                environment="test",
                locked_environment="test",
            )

            project = manager.create_project("My Test Project")

            self.assertEqual(project["name"], "My Test Project")
            self.assertEqual(len(manager.list_projects("test")), 1)
            self.assertEqual(len(manager.list_projects("production")), 0)
            self.assertEqual(
                manager.get_project(str(project["id"]), "test")["name"],
                "My Test Project",
            )

    def test_duplicate_project_name_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            manager.create_project("Project Alpha")

            with self.assertRaises(ValueError):
                manager.create_project("project alpha")


if __name__ == "__main__":
    unittest.main()
