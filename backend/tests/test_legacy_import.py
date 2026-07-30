"""MOD-12 历史图片原地索引测试。

测试范围：
- 作业创建与状态查询
- 完整索引流程（扫描、去重、files 记录、gallery_index 同步）
- 检查点机制（不重复处理已确认文件）
- 暂停/恢复/取消
- 重复导入幂等（content_hash 去重）
- missing 文件标记
- max_files 分批执行
- API 端点
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.legacy_import import (
    LEGACY_INDEX_JOB_TYPE,
    cancel_legacy_index,
    create_legacy_index_job,
    get_legacy_index_status,
    index_legacy_library,
    pause_legacy_index,
    resume_legacy_index,
    run_legacy_index_once,
)


def _make_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """生成纯色 PNG。"""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_png_with_pattern(width: int, height: int, seed: int) -> bytes:
    """生成带简单模式的 PNG。"""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            r = (x * 7 + seed) % 256
            g = (y * 11 + seed * 2) % 256
            b = ((x + y) * 13 + seed) % 256
            pixels[x, y] = (r, g, b)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class LegacyImportBase(unittest.TestCase):
    """公共 fixture。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.app = create_app(
            data_root=self.tmp_path,
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager
        # 历史图片目录
        self.legacy_dir = self.tmp_path / "legacy_photos"
        self.legacy_dir.mkdir(parents=True, exist_ok=True)

    def _write_image(self, name: str, data: bytes) -> Path:
        """在历史目录中写入一张图片。"""
        path = self.legacy_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class CreateJobTests(LegacyImportBase):
    """作业创建。"""

    def test_create_job_returns_pending(self) -> None:
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["job_type"], LEGACY_INDEX_JOB_TYPE)
        payload = json.loads(job["payload_json"])
        self.assertIn("directory", payload)
        self.assertEqual(payload["link_mode"], "hardlink")

    def test_create_job_invalid_link_mode(self) -> None:
        with self.assertRaises(ValueError):
            create_legacy_index_job(
                self.manager, str(self.legacy_dir), link_mode="invalid"
            )

    def test_create_job_nonexistent_directory(self) -> None:
        with self.assertRaises(ValueError):
            create_legacy_index_job(self.manager, "/nonexistent/path/xyz")

    def test_create_job_copy_mode(self) -> None:
        job = create_legacy_index_job(
            self.manager, str(self.legacy_dir), link_mode="copy"
        )
        payload = json.loads(job["payload_json"])
        self.assertEqual(payload["link_mode"], "copy")


class IndexExecutionTests(LegacyImportBase):
    """完整索引流程。"""

    def test_index_single_file_creates_files_record(self) -> None:
        """索引一张图片后，files 表应有记录。"""
        self._write_image("a.png", _make_png(64, 64, (255, 0, 0)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        result = index_legacy_library(self.manager, job["id"], max_files=10)
        self.assertEqual(result["status"], "completed")
        progress = result["progress"]
        self.assertEqual(progress["total_found"], 1)
        self.assertEqual(progress["indexed"], 1)
        # files 表应有记录
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE state = 'active'"
            ).fetchone()
            self.assertEqual(row["c"], 1)

    def test_index_syncs_gallery_index(self) -> None:
        """索引完成后 gallery_index 应有对应行。"""
        self._write_image("b.png", _make_png(64, 64, (0, 255, 0)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        index_legacy_library(self.manager, job["id"], max_files=10)
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM gallery_index"
            ).fetchone()
            self.assertEqual(row["c"], 1)

    def test_index_multiple_files(self) -> None:
        """索引多张不同图片。"""
        self._write_image("a.png", _make_png(64, 64, (255, 0, 0)))
        self._write_image("b.png", _make_png(64, 64, (0, 255, 0)))
        self._write_image("c.png", _make_png(64, 64, (0, 0, 255)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        result = index_legacy_library(self.manager, job["id"], max_files=10)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["progress"]["indexed"], 3)
        self.assertEqual(result["progress"]["total_found"], 3)

    def test_index_subdirectory(self) -> None:
        """递归扫描子目录。"""
        self._write_image("a.png", _make_png(64, 64, (255, 0, 0)))
        self._write_image("sub/dir/b.png", _make_png(64, 64, (0, 255, 0)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        result = index_legacy_library(self.manager, job["id"], max_files=10)
        self.assertEqual(result["progress"]["total_found"], 2)
        self.assertEqual(result["progress"]["indexed"], 2)

    def test_index_non_image_files_ignored(self) -> None:
        """非图片文件被忽略。"""
        self._write_image("a.png", _make_png(64, 64, (255, 0, 0)))
        (self.legacy_dir / "note.txt").write_text("hello")
        (self.legacy_dir / "data.json").write_text("{}")
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        result = index_legacy_library(self.manager, job["id"], max_files=10)
        self.assertEqual(result["progress"]["total_found"], 1)


class CheckpointTests(LegacyImportBase):
    """检查点机制。"""

    def test_checkpoint_skips_already_processed(self) -> None:
        """重复执行同一作业不重复处理已确认文件。"""
        self._write_image("a.png", _make_png(64, 64, (255, 0, 0)))
        self._write_image("b.png", _make_png(64, 64, (0, 255, 0)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        # 第一次执行
        result1 = index_legacy_library(self.manager, job["id"], max_files=10)
        self.assertEqual(result1["progress"]["indexed"], 2)
        # 第二次执行（progress 累计不变，files 表不重复）
        result2 = index_legacy_library(self.manager, job["id"], max_files=10)
        self.assertEqual(result2["progress"]["processed"], 2)
        self.assertEqual(result2["progress"]["indexed"], 2)
        # files 表不应有重复
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE state = 'active'"
            ).fetchone()
            self.assertEqual(row["c"], 2)
            # legacy_indexed_files 也只有 2 条
            row2 = conn.execute(
                "SELECT COUNT(*) AS c FROM legacy_indexed_files WHERE job_id = ?",
                (job["id"],),
            ).fetchone()
            self.assertEqual(row2["c"], 2)

    def test_batch_execution_with_max_files(self) -> None:
        """max_files 限制每轮处理数量。"""
        for i in range(5):
            self._write_image(
                f"img_{i}.png",
                _make_png_with_pattern(64, 64, seed=i),
            )
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        # 第一轮只处理 2 个
        result1 = index_legacy_library(self.manager, job["id"], max_files=2)
        self.assertEqual(result1["status"], "running")
        self.assertEqual(result1["progress"]["processed"], 2)
        # 第二轮继续
        result2 = index_legacy_library(self.manager, job["id"], max_files=2)
        self.assertEqual(result2["progress"]["processed"], 4)
        # 第三轮完成
        result3 = index_legacy_library(self.manager, job["id"], max_files=2)
        self.assertEqual(result3["status"], "completed")
        self.assertEqual(result3["progress"]["processed"], 5)
        self.assertEqual(result3["progress"]["indexed"], 5)


class DedupTests(LegacyImportBase):
    """重复导入幂等。"""

    def test_duplicate_content_hash_marked(self) -> None:
        """相同内容的图片只创建一份 files 记录，第二份标记为 duplicate。"""
        data = _make_png(64, 64, (128, 128, 128))
        self._write_image("a.png", data)
        self._write_image("b.png", data)  # 完全相同
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        result = index_legacy_library(self.manager, job["id"], max_files=10)
        self.assertEqual(result["progress"]["indexed"], 1)
        self.assertEqual(result["progress"]["duplicate"], 1)
        # files 表只有 1 条
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE state = 'active'"
            ).fetchone()
            self.assertEqual(row["c"], 1)

    def test_force_reindexes_duplicates(self) -> None:
        """force=True 时重新索引已存在的文件。"""
        data = _make_png(64, 64, (200, 100, 50))
        self._write_image("a.png", data)
        self._write_image("b.png", data)
        job = create_legacy_index_job(
            self.manager, str(self.legacy_dir), force=True
        )
        result = index_legacy_library(self.manager, job["id"], max_files=10)
        # force 模式下两份都创建 files 记录
        self.assertEqual(result["progress"]["indexed"], 2)
        self.assertEqual(result["progress"]["duplicate"], 0)


class PauseResumeCancelTests(LegacyImportBase):
    """暂停/恢复/取消。"""

    def test_pause_running_job(self) -> None:
        """暂停后状态为 paused。"""
        for i in range(3):
            self._write_image(
                f"img_{i}.png",
                _make_png_with_pattern(64, 64, seed=i),
            )
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        # 先执行一轮
        index_legacy_library(self.manager, job["id"], max_files=1)
        # 暂停（状态目前是 running）
        paused = pause_legacy_index(self.manager, job["id"])
        self.assertIsNotNone(paused)
        self.assertEqual(paused["status"], "paused")

    def test_resume_paused_job(self) -> None:
        """恢复后状态为 pending。"""
        for i in range(3):
            self._write_image(
                f"img_{i}.png",
                _make_png_with_pattern(64, 64, seed=i),
            )
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        index_legacy_library(self.manager, job["id"], max_files=1)
        pause_legacy_index(self.manager, job["id"])
        resumed = resume_legacy_index(self.manager, job["id"])
        self.assertIsNotNone(resumed)
        self.assertEqual(resumed["status"], "pending")

    def test_cancel_job(self) -> None:
        """取消后状态为 cancelled。"""
        self._write_image("a.png", _make_png(64, 64, (1, 2, 3)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        cancelled = cancel_legacy_index(self.manager, job["id"])
        self.assertIsNotNone(cancelled)
        self.assertEqual(cancelled["status"], "cancelled")

    def test_cancel_completed_returns_none(self) -> None:
        """已完成作业不能取消。"""
        self._write_image("a.png", _make_png(64, 64, (1, 2, 3)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        index_legacy_library(self.manager, job["id"], max_files=10)
        result = cancel_legacy_index(self.manager, job["id"])
        self.assertIsNone(result)

    def test_pause_non_running_returns_none(self) -> None:
        """非 running 状态不能暂停。"""
        self._write_image("a.png", _make_png(64, 64, (1, 2, 3)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        # pending 状态不能暂停
        result = pause_legacy_index(self.manager, job["id"])
        self.assertIsNone(result)


class RunOnceTests(LegacyImportBase):
    """run_legacy_index_once 领取队列。"""

    def test_run_once_no_pending_returns_none(self) -> None:
        """无 pending 作业时返回 None。"""
        result = run_legacy_index_once(self.manager, max_files=10)
        self.assertIsNone(result)

    def test_run_once_claims_and_executes(self) -> None:
        """run_once 领取并执行 pending 作业。"""
        self._write_image("a.png", _make_png(64, 64, (10, 20, 30)))
        create_legacy_index_job(self.manager, str(self.legacy_dir))
        result = run_legacy_index_once(self.manager, max_files=10)
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["progress"]["indexed"], 1)


class StatusQueryTests(LegacyImportBase):
    """状态查询。"""

    def test_get_status_nonexistent_job(self) -> None:
        """查询不存在的作业返回 None。"""
        result = get_legacy_index_status(self.manager, "nonexistent-id")
        self.assertIsNone(result)

    def test_get_status_includes_file_counts(self) -> None:
        """状态查询包含各状态文件计数。"""
        self._write_image("a.png", _make_png(64, 64, (1, 1, 1)))
        self._write_image("b.png", _make_png(64, 64, (2, 2, 2)))
        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        index_legacy_library(self.manager, job["id"], max_files=10)
        result = get_legacy_index_status(self.manager, job["id"])
        self.assertIn("file_status_counts", result)
        self.assertEqual(result["file_status_counts"].get("indexed", 0), 2)


class MissingFileTests(LegacyImportBase):
    """文件不存在标记。"""

    def test_missing_file_marked(self) -> None:
        """_process_single_file 对不存在的文件标记 missing。"""
        from backend.app.legacy_import import _process_single_file

        job = create_legacy_index_job(self.manager, str(self.legacy_dir))
        missing_path = self.legacy_dir / "ghost.png"
        with self.manager.connection() as conn:
            status = _process_single_file(
                self.manager, conn, job["id"], missing_path,
                link_mode="copy", force=False,
            )
        self.assertEqual(status, "missing")
        # legacy_indexed_files 应有 missing 记录
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT status FROM legacy_indexed_files WHERE job_id = ? AND source_path = ?",
                (job["id"], str(missing_path)),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], "missing")


class LinkModeTests(LegacyImportBase):
    """链接模式。"""

    def test_copy_mode_creates_separate_file(self) -> None:
        """copy 模式下创建独立副本。"""
        source_data = _make_png(64, 64, (100, 150, 200))
        source_path = self._write_image("a.png", source_data)
        job = create_legacy_index_job(
            self.manager, str(self.legacy_dir), link_mode="copy"
        )
        index_legacy_library(self.manager, job["id"], max_files=10)
        # 删除源文件后，副本应仍存在
        source_path.unlink()
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT storage_key FROM files WHERE state = 'active' LIMIT 1"
            ).fetchone()
            self.assertIsNotNone(row)
            dest = Path(self.manager.data_root) / "images" / row["storage_key"]
            self.assertTrue(dest.exists())


class APIEndpointTests(LegacyImportBase):
    """API 端点测试。"""

    def test_api_create_job(self) -> None:
        """POST /api/import/legacy/index 创建作业。"""
        resp = self.client.post(
            "/api/import/legacy/index",
            json={"directory": str(self.legacy_dir)},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["job"]["status"], "pending")

    def test_api_create_job_invalid_directory(self) -> None:
        """无效目录返回 422。"""
        resp = self.client.post(
            "/api/import/legacy/index",
            json={"directory": "/nonexistent/xyz"},
        )
        self.assertEqual(resp.status_code, 422)

    def test_api_get_status(self) -> None:
        """GET /api/import/legacy/index/{job_id} 查询状态。"""
        create_resp = self.client.post(
            "/api/import/legacy/index",
            json={"directory": str(self.legacy_dir)},
        )
        job_id = create_resp.json()["job"]["id"]
        resp = self.client.get(f"/api/import/legacy/index/{job_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["job"]["id"], job_id)

    def test_api_get_status_not_found(self) -> None:
        """不存在的作业返回 404。"""
        resp = self.client.get("/api/import/legacy/index/nonexistent")
        self.assertEqual(resp.status_code, 404)

    def test_api_execute_job(self) -> None:
        """POST /api/import/legacy/index/{job_id}/execute 执行作业。"""
        self._write_image("a.png", _make_png(64, 64, (7, 8, 9)))
        create_resp = self.client.post(
            "/api/import/legacy/index",
            json={"directory": str(self.legacy_dir)},
        )
        job_id = create_resp.json()["job"]["id"]
        resp = self.client.post(
            f"/api/import/legacy/index/{job_id}/execute",
            json={"directory": str(self.legacy_dir), "max_files": 10},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["job"]["status"], "completed")

    def test_api_run_worker(self) -> None:
        """POST /api/import/legacy/index/run 运行一轮。"""
        self._write_image("a.png", _make_png(64, 64, (11, 22, 33)))
        self.client.post(
            "/api/import/legacy/index",
            json={"directory": str(self.legacy_dir)},
        )
        resp = self.client.post("/api/import/legacy/index/run?max_files=10")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.json()["job"])

    def test_api_pause_and_resume(self) -> None:
        """暂停和恢复 API。"""
        for i in range(3):
            self._write_image(
                f"img_{i}.png",
                _make_png_with_pattern(64, 64, seed=i),
            )
        create_resp = self.client.post(
            "/api/import/legacy/index",
            json={"directory": str(self.legacy_dir)},
        )
        job_id = create_resp.json()["job"]["id"]
        # 先执行一轮使其变 running
        self.client.post(
            f"/api/import/legacy/index/{job_id}/execute",
            json={"directory": str(self.legacy_dir), "max_files": 1},
        )
        # 暂停
        pause_resp = self.client.post(
            f"/api/import/legacy/index/{job_id}/pause"
        )
        self.assertEqual(pause_resp.status_code, 200)
        self.assertEqual(pause_resp.json()["job"]["status"], "paused")
        # 恢复
        resume_resp = self.client.post(
            f"/api/import/legacy/index/{job_id}/resume"
        )
        self.assertEqual(resume_resp.status_code, 200)
        self.assertEqual(resume_resp.json()["job"]["status"], "pending")

    def test_api_cancel(self) -> None:
        """取消 API。"""
        self._write_image("a.png", _make_png(64, 64, (1, 2, 3)))
        create_resp = self.client.post(
            "/api/import/legacy/index",
            json={"directory": str(self.legacy_dir)},
        )
        job_id = create_resp.json()["job"]["id"]
        cancel_resp = self.client.post(
            f"/api/import/legacy/index/{job_id}/cancel"
        )
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertEqual(cancel_resp.json()["job"]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
