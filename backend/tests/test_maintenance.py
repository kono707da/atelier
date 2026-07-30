"""MOD-11 存储备份与维护测试。

测试范围：
- SQLite 在线备份（sqlite3 backup API）
- 数据库优化和 wal checkpoint
- 完整性检查
- 系统信息和迁移版本清单
- 孤立文件检查（DB 记录 vs 实际文件）
- 缓存清理

全部使用临时数据目录，不触碰生产数据库。
"""
from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from backend.tests import IsolatedTestCase


def _insert_file_record(
    manager,
    *,
    storage_key: str,
    original_name: str = "test.png",
    state: str = "active",
) -> str:
    """向 files 表插入一条记录，返回 file_id。"""
    file_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection("test") as connection:
        connection.execute(
            """
            INSERT INTO files(id, storage_key, original_name, mime_type,
                              size_bytes, state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (file_id, storage_key, original_name, "image/png", 1024, state, now, now),
        )
    return file_id


class MaintenanceApiTests(IsolatedTestCase):
    """MOD-11 维护 API 测试：备份、优化、完整性检查、系统信息、孤立检查、缓存清理。"""

    # ── 在线备份 ──────────────────────────────────────────────────────

    def test_backup_creates_snapshot_file(self) -> None:
        """POST /api/maintenance/backup 生成快照文件。"""
        target = self.manager.data_root / "backups" / "snapshot.sqlite3"
        response = self.client.post(
            "/api/maintenance/backup", json={"target_path": str(target)}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["database_environment"], "test")
        backup = body["backup"]
        self.assertTrue(target.exists())
        self.assertGreater(backup["size_bytes"], 0)
        self.assertEqual(backup["target_path"], str(target.resolve()))

    def test_backup_preserves_data(self) -> None:
        """备份文件包含与源数据库相同的数据。"""
        self.manager.create_project("Backup Source Project")
        target = self.manager.data_root / "backup_copy.sqlite3"
        self.manager.backup_database(str(target))
        # 读取备份文件验证数据一致
        backup_conn = sqlite3.connect(str(target))
        try:
            row = backup_conn.execute(
                "SELECT COUNT(*) FROM projects WHERE name = 'Backup Source Project'"
            ).fetchone()
        finally:
            backup_conn.close()
        self.assertEqual(row[0], 1)

    # ── 数据库优化 ────────────────────────────────────────────────────

    def test_optimize_returns_checkpoint_info(self) -> None:
        """POST /api/maintenance/optimize 返回 wal_checkpoint 信息。"""
        response = self.client.post("/api/maintenance/optimize")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["database_environment"], "test")
        optimize = body["optimize"]
        self.assertIn("optimize", optimize)
        self.assertIn("wal_checkpoint", optimize)
        checkpoint = optimize["wal_checkpoint"]
        # wal_checkpoint(TRUNCATE) 返回 (busy, log, checkpointed) 三个整数
        self.assertIn("busy", checkpoint)
        self.assertIn("log", checkpoint)
        self.assertIn("checkpointed", checkpoint)

    # ── 完整性检查 ────────────────────────────────────────────────────

    def test_integrity_check_passes(self) -> None:
        """GET /api/maintenance/integrity-check 对健康数据库返回 ok。"""
        response = self.client.get("/api/maintenance/integrity-check")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["database_environment"], "test")
        integrity = body["integrity"]
        self.assertTrue(integrity["ok"])
        self.assertEqual(integrity["results"], ["ok"])

    # ── 系统信息 ──────────────────────────────────────────────────────

    def test_system_info_returns_database_metadata(self) -> None:
        """GET /api/maintenance/system-info 返回数据库路径和大小。"""
        response = self.client.get("/api/maintenance/system-info")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        info = body["system_info"]
        self.assertEqual(info["environment"], "test")
        self.assertTrue(info["database_exists"])
        self.assertGreater(info["database_size_bytes"], 0)
        self.assertIn("journal_mode", info)
        self.assertGreater(info["table_count"], 0)
        self.assertGreater(info["page_size"], 0)

    def test_system_info_includes_migration_versions(self) -> None:
        """GET /api/maintenance/system-info 返回迁移版本清单。"""
        response = self.client.get("/api/maintenance/system-info")
        body = response.json()
        info = body["system_info"]
        self.assertGreater(info["migration_count"], 0)
        versions = [m["version"] for m in info["migrations"]]
        # 初始化后会注册多个版本化迁移
        self.assertIn("v0.1.7", versions)
        self.assertEqual(len(versions), info["migration_count"])

    # ── 孤立文件检查 ──────────────────────────────────────────────────

    def test_orphan_check_reports_missing_files(self) -> None:
        """GET /api/maintenance/orphan-check 报告 storage_key 对应文件缺失。"""
        # 插入两条记录：一条对应实际文件，一条不对应
        storage_root = self.manager.data_root / "storage" / "images"
        storage_root.mkdir(parents=True, exist_ok=True)
        existing_key = "existing_file.png"
        (storage_root / existing_key).write_bytes(b"\x89PNG fake content")

        _insert_file_record(self.manager, storage_key=existing_key)
        _insert_file_record(self.manager, storage_key="missing_file.png")

        result = self.manager.check_orphaned_files()
        self.assertEqual(result["total_files_in_db"], 2)
        self.assertEqual(result["existing_files"], 1)
        self.assertEqual(len(result["orphaned_db_records"]), 1)
        self.assertEqual(
            result["orphaned_db_records"][0]["storage_key"], "missing_file.png"
        )

    def test_orphan_check_reports_unreferenced_storage_files(self) -> None:
        """orphan-check 报告存储目录中未被 DB 引用的孤立文件。"""
        storage_root = self.manager.data_root / "storage" / "images"
        storage_root.mkdir(parents=True, exist_ok=True)
        # 创建一个未被任何 DB 记录引用的文件
        (storage_root / "orphan_in_storage.png").write_bytes(b"orphan")

        result = self.manager.check_orphaned_files()
        unreferenced = result["unreferenced_storage_files"]
        names = [u["name"] for u in unreferenced]
        self.assertIn("orphan_in_storage.png", names)

    def test_orphan_check_empty_when_no_files(self) -> None:
        """orphan-check 对空 files 表返回零计数。"""
        response = self.client.get("/api/maintenance/orphan-check")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        orphan = body["orphan_check"]
        self.assertEqual(orphan["total_files_in_db"], 0)
        self.assertEqual(orphan["existing_files"], 0)
        self.assertEqual(orphan["orphaned_db_records"], [])

    # ── 缓存清理 ──────────────────────────────────────────────────────

    def test_clear_cache_removes_temp_files(self) -> None:
        """POST /api/maintenance/clear-cache 清空 cache 和 tmp 目录。"""
        cache_root = self.manager.data_root / "cache"
        temp_root = self.manager.data_root / "tmp"
        cache_root.mkdir(parents=True, exist_ok=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        (cache_root / "stale.json").write_text("{}")
        (cache_root / "subdir").mkdir()
        (temp_root / "scratch.tmp").write_text("scratch")

        response = self.client.post("/api/maintenance/clear-cache")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        cleared = body["clear_cache"]["cleared"]
        # cache 目录有 2 个条目（文件 + 子目录），tmp 有 1 个
        self.assertEqual(cleared["cache"], 2)
        self.assertEqual(cleared["tmp"], 1)
        # 目录本身保留
        self.assertTrue(cache_root.exists())
        self.assertTrue(temp_root.exists())
        # 内容已清空
        self.assertEqual(list(cache_root.iterdir()), [])
        self.assertEqual(list(temp_root.iterdir()), [])

    def test_clear_cache_safe_when_directories_absent(self) -> None:
        """clear-cache 在目录不存在时不报错。"""
        result = self.manager.clear_cache()
        self.assertEqual(result["cleared"]["cache"], 0)
        self.assertEqual(result["cleared"]["tmp"], 0)


if __name__ == "__main__":
    unittest.main()
