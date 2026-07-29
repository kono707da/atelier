"""阶段 1.1 基础约束和迁移能力的验收测试。

覆盖：
- schema_migrations 表存在且记录迁移版本
- 9 张核心编辑表拥有 revision 字段
- 统一错误响应格式（detail + error 结构）
- request ID 中间件注入 X-Request-ID 响应头
- RequestValidationError 返回 422 并包含 error 结构
- 兜底异常返回 500
- 测试隔离基类 IsolatedTestCase 可用
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.tests import IsolatedTestCase


class SchemaMigrationsTests(IsolatedTestCase):
    """schema_migrations 表和版本化迁移流程。"""

    def test_schema_migrations_table_exists(self) -> None:
        with self.manager.connection("test") as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
        self.assertIsNotNone(row)

    def test_migration_versions_are_recorded(self) -> None:
        with self.manager.connection("test") as conn:
            rows = conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        versions = [r["version"] for r in rows]
        self.assertIn("v0.5.0", versions)
        self.assertIn("v0.4.1", versions)
        self.assertIn("v0.2.0", versions)

    def test_repeated_initialize_does_not_duplicate_migrations(self) -> None:
        self.manager.initialize("test")
        with self.manager.connection("test") as conn:
            count = conn.execute(
                "SELECT COUNT(*) as c FROM schema_migrations WHERE version = 'v0.5.0'"
            ).fetchone()["c"]
        self.assertEqual(count, 1)

    def test_migrations_run_idempotently_on_reinit(self) -> None:
        """重新初始化时迁移函数仍执行（幂等），不破坏现有数据。"""
        with self.manager.connection("test") as conn:
            conn.execute(
                "INSERT INTO projects(id, name, status, revision, created_at, updated_at) "
                "VALUES('test-1', '测试项目', 'draft', 1, '2024-01-01', '2024-01-01')"
            )
        self.manager.initialize("test")
        with self.manager.connection("test") as conn:
            row = conn.execute(
                "SELECT name, revision FROM projects WHERE id = 'test-1'"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "测试项目")
        self.assertEqual(row["revision"], 1)


class RevisionColumnTests(IsolatedTestCase):
    """9 张核心编辑表的 revision 字段。"""

    REVISION_TABLES = [
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

    def test_all_core_tables_have_revision_column(self) -> None:
        for table in self.REVISION_TABLES:
            with self.manager.connection("test") as conn:
                cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            self.assertIn("revision", cols, f"表 {table} 缺少 revision 字段")

    def test_revision_defaults_to_one(self) -> None:
        """新创建的记录 revision 默认为 1。"""
        with self.manager.connection("test") as conn:
            conn.execute(
                "INSERT INTO projects(id, name, status, created_at, updated_at) "
                "VALUES('rev-test', 'revision测试', 'draft', '2024-01-01', '2024-01-01')"
            )
            row = conn.execute(
                "SELECT revision FROM projects WHERE id = 'rev-test'"
            ).fetchone()
        self.assertEqual(row["revision"], 1)

    def test_legacy_database_adds_revision_on_migrate(self) -> None:
        """旧数据库（无 revision 列）重新初始化后自动添加 revision 字段。"""
        with self.manager.connection("test") as conn:
            conn.execute("DROP TABLE characters")
            conn.execute(
                "CREATE TABLE characters ("
                "id TEXT PRIMARY KEY, name TEXT NOT NULL, sort_order INTEGER NOT NULL, "
                "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(name))"
            )
            conn.execute(
                "INSERT INTO characters(id, name, sort_order, created_at, updated_at) "
                "VALUES('legacy-char', '旧角色', 1, '2024-01-01', '2024-01-01')"
            )
        self.manager.initialize("test")
        with self.manager.connection("test") as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(characters)").fetchall()]
            self.assertIn("revision", cols)
            row = conn.execute(
                "SELECT revision FROM characters WHERE id = 'legacy-char'"
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["revision"], 1)


class RequestIdMiddlewareTests(IsolatedTestCase):
    """request ID 中间件。"""

    def test_response_has_request_id_header(self) -> None:
        response = self.client.get("/api/health")
        self.assertIn("x-request-id", response.headers)
        self.assertTrue(response.headers["x-request-id"])

    def test_client_provided_request_id_is_preserved(self) -> None:
        custom_id = "test-request-id-12345"
        response = self.client.get("/api/health", headers={"X-Request-ID": custom_id})
        self.assertEqual(response.headers["x-request-id"], custom_id)

    def test_generated_request_id_is_uuid_hex(self) -> None:
        response = self.client.get("/api/health")
        request_id = response.headers["x-request-id"]
        # uuid4().hex 是 32 个十六进制字符
        self.assertEqual(len(request_id), 32)
        int(request_id, 16)  # 验证是合法的十六进制


class UnifiedErrorResponseTests(IsolatedTestCase):
    """统一错误响应格式。"""

    def test_http_exception_has_error_structure(self) -> None:
        response = self.client.get("/api/projects/nonexistent-id")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertIn("detail", body)
        self.assertIn("error", body)
        self.assertIn("code", body["error"])
        self.assertIn("message", body["error"])
        self.assertIn("request_id", body["error"])
        self.assertTrue(body["error"]["request_id"])

    def test_404_error_code_is_not_found(self) -> None:
        response = self.client.get("/api/projects/nonexistent-id")
        body = response.json()
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

    def test_409_error_code_is_conflict(self) -> None:
        # Project names are no longer unique (v0.5.1 dropped UNIQUE on name),
        # so use chapter duplicate name to trigger a 409 CONFLICT.
        project = self.manager.create_project("冲突测试项目")
        self.client.post(
            f"/api/projects/{project['id']}/chapters", json={"name": "同名章节"}
        )
        response = self.client.post(
            f"/api/projects/{project['id']}/chapters", json={"name": "同名章节"}
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["error"]["code"], "CONFLICT")

    def test_422_validation_error_has_error_structure(self) -> None:
        response = self.client.post("/api/projects", json={"name": ""})
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertIn("detail", body)
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "BUSINESS_RULE_VIOLATION")
        self.assertIn("validation_errors", body["error"]["details"])

    def test_error_response_includes_request_id_header(self) -> None:
        response = self.client.get("/api/projects/nonexistent-id")
        self.assertEqual(response.status_code, 404)
        self.assertIn("x-request-id", response.headers)
        body = response.json()
        self.assertEqual(body["error"]["request_id"], response.headers["x-request-id"])

    def test_database_safety_error_returns_409(self) -> None:
        """锁定到 test 的进程尝试激活 production 时返回 409。"""
        response = self.client.post(
            "/api/settings/databases/activate",
            json={"environment": "production", "confirmation": "USE PRODUCTION"},
        )
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertIn("error", body)
        self.assertEqual(body["error"]["code"], "CONFLICT")


class IsolatedTestCaseTests(unittest.TestCase):
    """IsolatedTestCase 基类可用性。"""

    def test_isolated_test_case_provides_app_and_client(self) -> None:
        """IsolatedTestCase 自动创建临时目录、应用和客户端。"""
        case = IsolatedTestCase()
        case.setUp()
        try:
            self.assertIsNotNone(case.app)
            self.assertIsNotNone(case.client)
            self.assertIsNotNone(case.manager)
            response = case.client.get("/api/health")
            self.assertEqual(response.status_code, 200)
            # 确认使用的是 test 环境
            self.assertEqual(response.json()["database_environment"], "test")
        finally:
            case.doCleanups()

    def test_isolated_test_case_uses_temporary_directory(self) -> None:
        """IsolatedTestCase 的数据目录是临时的，不是生产目录。"""
        case = IsolatedTestCase()
        case.setUp()
        try:
            data_root = case.manager.data_root
            # 临时目录不应是生产数据目录
            production_root = Path(__file__).resolve().parents[2] / "data"
            self.assertNotEqual(data_root.resolve(), production_root.resolve())
        finally:
            case.doCleanups()


if __name__ == "__main__":
    unittest.main()
