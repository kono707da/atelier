"""MOD-11 补齐维护任务测试。

测试范围：
- restore_database: 备份不存在/无效文件/成功恢复/恢复前自动备份
- rebuild_fts_index
- recompute_all_phash
- clean_temp_files
- clean_trash
- run_full_maintenance
- API 端点
"""
from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.maintenance_tasks import (
    DEFAULT_TEMP_RETENTION_DAYS,
    DEFAULT_TRASH_RETENTION_DAYS,
    clean_temp_files,
    clean_trash,
    rebuild_fts_index,
    recompute_all_phash,
    restore_database,
    run_full_maintenance,
)
from backend.app.output_receiver import create_file_record


def _make_png_bytes(width: int = 64, height: int = 64) -> bytes:
    img = Image.new("RGB", (width, height), color=(128, 64, 192))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class MaintenanceTestBase(unittest.TestCase):
    """维护任务测试基类。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager

    def _write_file(self, *, image_bytes: bytes | None = None) -> str:
        """创建文件记录并写入实际文件。"""
        import uuid as uuid_module

        file_id = str(uuid_module.uuid4())
        storage_key = f"{file_id}.png"
        if image_bytes is None:
            image_bytes = _make_png_bytes()
        images_dir = Path(self._tmp.name) / "storage" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / storage_key).write_bytes(image_bytes)
        create_file_record(
            self.manager,
            {
                "file_id": file_id,
                "storage_key": storage_key,
                "original_name": f"{file_id}.png",
                "mime_type": "image/png",
                "size_bytes": len(image_bytes),
                "content_hash": "hash-" + file_id[:8],
            },
        )
        return file_id


# ──────────────────────────────────────────────────────────────────
# 数据库恢复
# ──────────────────────────────────────────────────────────────────


class RestoreDatabaseTests(MaintenanceTestBase):
    """restore_database 测试。"""

    def test_restore_from_valid_backup(self) -> None:
        """从有效备份恢复。"""
        # 先创建一些数据
        self._write_file()
        # 创建备份
        backup_path = str(Path(self._tmp.name) / "backup.db")
        manager_backup = self.manager.backup_database(backup_path)

        # 再添加数据（使恢复前后不同）
        self._write_file()

        # 恢复
        result = restore_database(
            self.manager,
            backup_path,
            pre_restore_backup=False,  # 测试不创建恢复前备份
        )
        self.assertEqual(result["environment"], "test")
        self.assertIn("integrity_check", result)
        self.assertIn("orphan_check", result)

        # 验证恢复后只有 1 个文件（备份时的状态）
        with self.manager.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        self.assertEqual(count, 1)

    def test_restore_with_pre_backup(self) -> None:
        """恢复前自动备份。"""
        self._write_file()
        backup_path = str(Path(self._tmp.name) / "backup.db")
        self.manager.backup_database(backup_path)

        result = restore_database(
            self.manager,
            backup_path,
            pre_restore_backup=True,
            pre_restore_backup_dir=str(Path(self._tmp.name) / "pre_backups"),
        )
        self.assertIsNotNone(result["pre_restore_backup"])
        self.assertTrue(Path(result["pre_restore_backup"]["target_path"]).exists())

    def test_restore_nonexistent_backup_raises(self) -> None:
        """备份文件不存在时抛出 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            restore_database(self.manager, "/nonexistent/backup.db")

    def test_restore_invalid_backup_raises(self) -> None:
        """无效 SQLite 文件抛出 ValueError。"""
        invalid_path = str(Path(self._tmp.name) / "invalid.db")
        Path(invalid_path).write_text("not a sqlite file")
        with self.assertRaises(ValueError):
            restore_database(self.manager, invalid_path)


# ──────────────────────────────────────────────────────────────────
# 重建 FTS 索引
# ──────────────────────────────────────────────────────────────────


class RebuildFTSTests(MaintenanceTestBase):
    """rebuild_fts_index 测试。"""

    def test_rebuild_fts_empty(self) -> None:
        """空库重建 FTS。"""
        result = rebuild_fts_index(self.manager)
        self.assertTrue(result["rebuilt"])
        self.assertEqual(result["indexed_count"], 0)

    def test_rebuild_fts_with_data(self) -> None:
        """有数据时重建 FTS。"""
        from backend.app.gallery import index_file_for_gallery

        file_id = self._write_file()
        # 手动插入 gallery_index 记录（带 prompt_text）
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO gallery_index(file_id, prompt_text, indexed_at) "
                "VALUES (?, ?, ?)",
                (file_id, "test prompt for fts", datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        # 插入 FTS
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT INTO gallery_fts(file_id, prompt_text) VALUES (?, ?)",
                (file_id, "test prompt for fts"),
            )
            conn.commit()

        # 重建
        result = rebuild_fts_index(self.manager)
        self.assertTrue(result["rebuilt"])
        self.assertEqual(result["indexed_count"], 1)


# ──────────────────────────────────────────────────────────────────
# 重算 phash
# ──────────────────────────────────────────────────────────────────


class RecomputePHashTests(MaintenanceTestBase):
    """recompute_all_phash 测试。"""

    def test_recompute_phash_success(self) -> None:
        """成功重算 phash。"""
        file_id = self._write_file()
        result = recompute_all_phash(self.manager, limit=10)
        self.assertEqual(result["total_files"], 1)
        self.assertEqual(result["computed"], 1)
        self.assertEqual(result["failed"], 0)

        # 验证 phash 已写入
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT perceptual_hash FROM files WHERE id = ?", (file_id,)
            ).fetchone()
        self.assertTrue(row["perceptual_hash"])

    def test_recompute_phash_missing_file(self) -> None:
        """文件不存在时跳过。"""
        file_id = self._write_file()
        # 删除实际文件
        (Path(self._tmp.name) / "storage" / "images" / f"{file_id}.png").unlink()
        result = recompute_all_phash(self.manager, limit=10)
        self.assertEqual(result["total_files"], 1)
        self.assertEqual(result["skipped_missing"], 1)


# ──────────────────────────────────────────────────────────────────
# 清理临时文件
# ──────────────────────────────────────────────────────────────────


class CleanTempTests(MaintenanceTestBase):
    """clean_temp_files 测试。"""

    def test_clean_temp_removes_old_files(self) -> None:
        """删除过期临时文件。"""
        temp_root = Path(self._tmp.name) / "tmp"
        temp_root.mkdir(parents=True, exist_ok=True)
        # 创建过期文件
        old_file = temp_root / "old.txt"
        old_file.write_text("old")
        # 设置修改时间为 30 天前
        old_time = (datetime.now(timezone.utc) - timedelta(days=30)).timestamp()
        import os

        os.utime(old_file, (old_time, old_time))
        # 创建新文件
        new_file = temp_root / "new.txt"
        new_file.write_text("new")

        result = clean_temp_files(self.manager, retention_days=7)
        self.assertEqual(result["removed_temp_count"], 1)
        self.assertFalse(old_file.exists())
        self.assertTrue(new_file.exists())

    def test_clean_temp_empty_dir(self) -> None:
        """空目录返回 0。"""
        result = clean_temp_files(self.manager, retention_days=7)
        self.assertEqual(result["removed_temp_count"], 0)


# ──────────────────────────────────────────────────────────────────
# 清理回收站
# ──────────────────────────────────────────────────────────────────


class CleanTrashTests(MaintenanceTestBase):
    """clean_trash 测试。"""

    def test_clean_trash_empty(self) -> None:
        """空库清理回收站。"""
        result = clean_trash(self.manager, retention_days=30)
        self.assertEqual(result["total_removed"], 0)

    def test_clean_trash_with_old_records(self) -> None:
        """清理过期软删除记录。"""
        # 创建一个项目并软删除
        response = self.client.post("/api/projects", json={"name": "回收站测试"})
        project_id = response.json()["project"]["id"]
        self.client.delete(f"/api/projects/{project_id}")

        # 设置 deleted_at 为 60 天前
        old_time = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                "UPDATE projects SET deleted_at = ? WHERE id = ?",
                (old_time, project_id),
            )
            conn.commit()

        result = clean_trash(self.manager, retention_days=30)
        self.assertGreaterEqual(result["total_removed"], 1)

        # 验证记录已物理删除
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        self.assertEqual(row[0], 0)


# ──────────────────────────────────────────────────────────────────
# 综合维护
# ──────────────────────────────────────────────────────────────────


class FullMaintenanceTests(MaintenanceTestBase):
    """run_full_maintenance 测试。"""

    def test_run_full_maintenance_empty_db(self) -> None:
        """空库运行全套维护。"""
        result = run_full_maintenance(self.manager)
        self.assertIn("optimize", result)
        self.assertIn("rebuild_thumbnails", result)
        self.assertIn("rebuild_fts", result)
        self.assertIn("recompute_phash", result)
        self.assertIn("clean_temp", result)
        self.assertIn("clean_trash", result)
        self.assertIn("integrity_check", result)
        self.assertIn("completed_at", result)

    def test_run_full_maintenance_with_data(self) -> None:
        """有数据时运行全套维护。"""
        self._write_file()
        result = run_full_maintenance(self.manager, thumbnail_limit=5, phash_limit=5)
        self.assertIn("optimize", result)
        # 缩略图应该已生成
        self.assertEqual(result["rebuild_thumbnails"]["total_files"], 1)
        # phash 应该已计算
        self.assertEqual(result["recompute_phash"]["computed"], 1)


# ──────────────────────────────────────────────────────────────────
# API 端点
# ──────────────────────────────────────────────────────────────────


class MaintenanceAPITests(MaintenanceTestBase):
    """维护任务 API 测试。"""

    def test_restore_api(self) -> None:
        """POST /api/maintenance/restore。"""
        # 创建备份
        backup_path = str(Path(self._tmp.name) / "backup.db")
        self.manager.backup_database(backup_path)

        response = self.client.post(
            "/api/maintenance/restore",
            json={"backup_path": backup_path, "pre_restore_backup": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("restore", data)
        self.assertIn("integrity_check", data["restore"])

    def test_restore_api_not_found(self) -> None:
        """备份不存在时 404。"""
        response = self.client.post(
            "/api/maintenance/restore",
            json={"backup_path": "/nonexistent/backup.db"},
        )
        self.assertEqual(response.status_code, 404)

    def test_restore_api_invalid_file(self) -> None:
        """无效备份文件 400。"""
        invalid_path = str(Path(self._tmp.name) / "invalid.db")
        Path(invalid_path).write_text("not sqlite")
        response = self.client.post(
            "/api/maintenance/restore",
            json={"backup_path": invalid_path, "pre_restore_backup": False},
        )
        self.assertEqual(response.status_code, 400)

    def test_rebuild_fts_api(self) -> None:
        """POST /api/maintenance/rebuild-fts。"""
        response = self.client.post("/api/maintenance/rebuild-fts")
        self.assertEqual(response.status_code, 200, response.text)

    def test_recompute_phash_api(self) -> None:
        """POST /api/maintenance/recompute-phash。"""
        self._write_file()
        response = self.client.post("/api/maintenance/recompute-phash?limit=5")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["recompute_phash"]["computed"], 1)

    def test_clean_temp_api(self) -> None:
        """POST /api/maintenance/clean-temp。"""
        response = self.client.post("/api/maintenance/clean-temp?retention_days=7")
        self.assertEqual(response.status_code, 200, response.text)

    def test_clean_trash_api(self) -> None:
        """POST /api/maintenance/clean-trash。"""
        response = self.client.post("/api/maintenance/clean-trash?retention_days=30")
        self.assertEqual(response.status_code, 200, response.text)

    def test_run_full_maintenance_api(self) -> None:
        """POST /api/maintenance/run-full。"""
        response = self.client.post(
            "/api/maintenance/run-full?thumbnail_limit=5&phash_limit=5"
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("maintenance", data)


if __name__ == "__main__":
    unittest.main()
