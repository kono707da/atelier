"""缩略图生成 worker 测试。

测试范围：
- 单文件缩略图生成（256/640）
- 多级缩略图记录写入与查询
- worker 任务领取、执行、完成
- 失败处理（文件缺失、payload 无效、最大重试）
- 重建单文件和批量重建
- API 端点
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.output_receiver import create_file_record
from backend.app.thumbnail_worker import (
    SIZE_CLASS_TO_PX,
    THUMBNAIL_MAX_RETRIES,
    claim_thumbnail_job,
    generate_thumbnail_for_file,
    get_thumbnail_record,
    list_thumbnails_for_file,
    process_thumbnail_job,
    rebuild_all_thumbnails,
    rebuild_thumbnails_for_file,
    run_thumbnail_worker_once,
    thumbnail_path_for,
)


def _make_png_bytes(width: int = 400, height: int = 600, color=(128, 64, 192)) -> bytes:
    """生成测试 PNG 字节。"""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_bytes(width: int = 800, height: int = 200) -> bytes:
    img = Image.new("RGB", (width, height), color=(64, 192, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class ThumbnailWorkerTestBase(unittest.TestCase):
    """缩略图 worker 测试基类。"""

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

    def _write_file(
        self,
        *,
        storage_key: str | None = None,
        image_bytes: bytes | None = None,
        mime_type: str = "image/png",
        state: str = "active",
    ) -> str:
        """写入一个文件记录和实际文件，返回 file_id。"""
        import uuid as uuid_module

        file_id = str(uuid_module.uuid4())
        if storage_key is None:
            ext = ".png" if "png" in mime_type else ".jpg"
            storage_key = f"{file_id}{ext}"
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
                "original_name": storage_key,
                "mime_type": mime_type,
                "size_bytes": len(image_bytes),
                "content_hash": "fake-hash-" + file_id[:8],
            },
        )
        if state != "active":
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            with self.manager.connection() as conn:
                conn.execute(
                    "UPDATE files SET state = ?, updated_at = ? WHERE id = ?",
                    (state, now, file_id),
                )
                conn.commit()
        return file_id


# ──────────────────────────────────────────────────────────────────
# 单文件缩略图生成
# ──────────────────────────────────────────────────────────────────


class GenerateThumbnailTests(ThumbnailWorkerTestBase):
    """generate_thumbnail_for_file 测试。"""

    def test_generate_256_thumbnail(self) -> None:
        """生成 256 缩略图。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        result = generate_thumbnail_for_file(self.manager, file_id, "256")
        self.assertEqual(result["storage_key"], f"256/{file_id}.webp")
        # 短边 400 -> 256，长边按比例 600 * (256/400) = 384
        self.assertEqual(result["width"], 256)
        self.assertEqual(result["height"], 384)
        # 文件实际存在
        path = thumbnail_path_for(self.manager, file_id, "256")
        self.assertTrue(path.exists())
        with Image.open(path) as img:
            self.assertEqual(img.format, "WEBP")
            self.assertEqual(img.size, (256, 384))

    def test_generate_640_thumbnail(self) -> None:
        """生成 640 缩略图。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(800, 200))
        result = generate_thumbnail_for_file(self.manager, file_id, "640")
        # 短边 200 -> 640 不可能放大，按短边对齐：长边 800, 短边 200 -> 640/200 * 800 = 2560
        # 但短边 200 < 640，所以短边对齐后短边变成 640，长边变成 800*(640/200)=2560
        self.assertEqual(result["width"], 2560)
        self.assertEqual(result["height"], 640)

    def test_generate_unknown_size_class_raises(self) -> None:
        """未知 size_class 抛出异常。"""
        file_id = self._write_file()
        with self.assertRaises(ValueError):
            generate_thumbnail_for_file(self.manager, file_id, "999")

    def test_generate_missing_file_raises(self) -> None:
        """文件不存在时抛出 FileNotFoundError 并标记 missing。"""
        file_id = self._write_file()
        # 删除实际文件
        path = Path(self._tmp.name) / "storage" / "images" / f"{file_id}.png"
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            generate_thumbnail_for_file(self.manager, file_id, "256")
        # 验证 files 表被标记为 missing
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT state FROM files WHERE id = ?", (file_id,)
            ).fetchone()
        self.assertEqual(row["state"], "missing")

    def test_generate_missing_record_raises(self) -> None:
        """文件记录不存在时抛出 FileNotFoundError。"""
        with self.assertRaises(FileNotFoundError):
            generate_thumbnail_for_file(self.manager, "nonexistent-id", "256")

    def test_generate_already_missing_state_raises(self) -> None:
        """文件 state=missing 时直接抛出。"""
        file_id = self._write_file(state="missing")
        with self.assertRaises(FileNotFoundError):
            generate_thumbnail_for_file(self.manager, file_id, "256")


# ──────────────────────────────────────────────────────────────────
# 缩略图记录查询
# ──────────────────────────────────────────────────────────────────


class ThumbnailRecordTests(ThumbnailWorkerTestBase):
    """thumbnails 表记录测试。"""

    def test_get_thumbnail_record_none(self) -> None:
        """不存在的缩略图记录返回 None。"""
        record = get_thumbnail_record(self.manager, "no-such-file", "256")
        self.assertIsNone(record)

    def test_list_thumbnails_empty(self) -> None:
        """无缩略图时返回空列表。"""
        file_id = self._write_file()
        items = list_thumbnails_for_file(self.manager, file_id)
        self.assertEqual(items, [])

    def test_rebuild_writes_thumbnail_records(self) -> None:
        """rebuild 后 thumbnails 表有记录。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        rebuild_thumbnails_for_file(self.manager, file_id)
        items = list_thumbnails_for_file(self.manager, file_id)
        self.assertEqual(len(items), 2)
        size_classes = {item["size_class"] for item in items}
        self.assertEqual(size_classes, {"256", "640"})
        for item in items:
            self.assertEqual(item["state"], "completed")
            self.assertTrue(item["storage_key"])
            self.assertGreater(item["width"], 0)
            self.assertGreater(item["height"], 0)

    def test_rebuild_upserts_existing_record(self) -> None:
        """重建时更新已有记录而不是插入新记录。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        rebuild_thumbnails_for_file(self.manager, file_id)
        # 再次重建
        rebuild_thumbnails_for_file(self.manager, file_id)
        items = list_thumbnails_for_file(self.manager, file_id)
        # 仍然只有 2 条，不重复
        self.assertEqual(len(items), 2)


# ──────────────────────────────────────────────────────────────────
# Worker 任务流程
# ──────────────────────────────────────────────────────────────────


class WorkerJobTests(ThumbnailWorkerTestBase):
    """worker 任务领取、执行、完成测试。"""

    def _create_thumbnail_job(
        self, file_id: str, size_class: str = "256"
    ) -> str:
        """直接插入一个 thumbnail background_job，返回 job_id。"""
        import uuid as uuid_module
        from datetime import datetime, timezone

        job_id = str(uuid_module.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({"file_id": file_id, "size_class": size_class})
        with self.manager.connection() as conn:
            conn.execute(
                """INSERT INTO background_jobs(
                    id, job_type, status, payload_json,
                    progress_json, result_json, lease_until, error_json,
                    created_at, updated_at
                ) VALUES (?, 'thumbnail', 'pending', ?, NULL, NULL, NULL, NULL, ?, ?)""",
                (job_id, payload, now, now),
            )
            conn.commit()
        return job_id

    def test_claim_returns_pending_job(self) -> None:
        """claim 领取 pending 任务。"""
        file_id = self._write_file()
        job_id = self._create_thumbnail_job(file_id)
        claimed = claim_thumbnail_job(self.manager)
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], job_id)
        self.assertEqual(claimed["status"], "running")

    def test_claim_none_when_no_jobs(self) -> None:
        """无任务时返回 None。"""
        self.assertIsNone(claim_thumbnail_job(self.manager))

    def test_process_job_success(self) -> None:
        """成功处理任务：写入 thumbnails 记录，job 标记 completed。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        job_id = self._create_thumbnail_job(file_id, "256")
        job = claim_thumbnail_job(self.manager)
        self.assertEqual(job["id"], job_id)

        result = process_thumbnail_job(self.manager, job)
        self.assertEqual(result["status"], "completed")

        # 验证 job 状态
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT status, result_json FROM background_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        self.assertEqual(row["status"], "completed")
        result_data = json.loads(row["result_json"])
        self.assertEqual(result_data["file_id"], file_id)
        self.assertEqual(result_data["size_class"], "256")

        # 验证 thumbnails 表
        record = get_thumbnail_record(self.manager, file_id, "256")
        self.assertIsNotNone(record)
        self.assertEqual(record["state"], "completed")

    def test_process_job_missing_file_permanent_fail(self) -> None:
        """文件不存在时永久失败。"""
        file_id = self._write_file()
        (Path(self._tmp.name) / "storage" / "images" / f"{file_id}.png").unlink()

        job_id = self._create_thumbnail_job(file_id)
        job = claim_thumbnail_job(self.manager)
        result = process_thumbnail_job(self.manager, job)
        self.assertEqual(result["status"], "failed")

        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT status FROM background_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        self.assertEqual(row["status"], "failed")

    def test_process_job_invalid_payload_permanent_fail(self) -> None:
        """payload 缺字段时永久失败。"""
        import uuid as uuid_module
        from datetime import datetime, timezone

        job_id = str(uuid_module.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                """INSERT INTO background_jobs(
                    id, job_type, status, payload_json,
                    progress_json, result_json, lease_until, error_json,
                    created_at, updated_at
                ) VALUES (?, 'thumbnail', 'pending', ?, NULL, NULL, NULL, NULL, ?, ?)""",
                (job_id, json.dumps({"file_id": ""}), now, now),
            )
            conn.commit()

        job = claim_thumbnail_job(self.manager)
        result = process_thumbnail_job(self.manager, job)
        self.assertEqual(result["status"], "failed")

    def test_run_worker_once_processes_multiple(self) -> None:
        """一次运行处理多个任务。"""
        file_id_1 = self._write_file(image_bytes=_make_png_bytes(400, 600))
        file_id_2 = self._write_file(image_bytes=_make_png_bytes(500, 500))
        # 每个文件创建 2 个任务（256 + 640）
        self._create_thumbnail_job(file_id_1, "256")
        self._create_thumbnail_job(file_id_1, "640")
        self._create_thumbnail_job(file_id_2, "256")
        self._create_thumbnail_job(file_id_2, "640")

        result = run_thumbnail_worker_once(self.manager, max_jobs=10)
        self.assertEqual(result["processed"], 4)
        self.assertEqual(result["completed"], 4)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["retried"], 0)

    def test_max_retries_exceeded(self) -> None:
        """超过最大重试次数后任务标记 failed。"""
        file_id = self._write_file()
        # 创建一个 retry_count 已达上限的 pending 任务
        import uuid as uuid_module
        from datetime import datetime, timezone

        job_id = str(uuid_module.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({
            "file_id": file_id,
            "size_class": "256",
            "retry_count": THUMBNAIL_MAX_RETRIES,
        })
        with self.manager.connection() as conn:
            conn.execute(
                """INSERT INTO background_jobs(
                    id, job_type, status, payload_json,
                    progress_json, result_json, lease_until, error_json,
                    created_at, updated_at
                ) VALUES (?, 'thumbnail', 'pending', ?, NULL, NULL, NULL, NULL, ?, ?)""",
                (job_id, payload, now, now),
            )
            conn.commit()

        # claim 时会先处理超限任务
        claimed = claim_thumbnail_job(self.manager)
        self.assertIsNone(claimed)

        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT status FROM background_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        self.assertEqual(row["status"], "failed")


# ──────────────────────────────────────────────────────────────────
# 批量重建
# ──────────────────────────────────────────────────────────────────


class RebuildTests(ThumbnailWorkerTestBase):
    """批量重建测试。"""

    def test_rebuild_all_thumbnails(self) -> None:
        """批量重建多个文件的缩略图。"""
        file_id_1 = self._write_file(image_bytes=_make_png_bytes(400, 600))
        file_id_2 = self._write_file(image_bytes=_make_png_bytes(300, 300))

        result = rebuild_all_thumbnails(self.manager, limit=10)
        self.assertEqual(result["total_files"], 2)
        self.assertEqual(result["thumbnails_completed"], 4)
        self.assertEqual(result["thumbnails_failed"], 0)

    def test_rebuild_all_respects_limit(self) -> None:
        """limit 限制处理文件数。"""
        for _ in range(5):
            self._write_file()
        result = rebuild_all_thumbnails(self.manager, limit=2)
        self.assertEqual(result["total_files"], 2)


# ──────────────────────────────────────────────────────────────────
# API 端点
# ──────────────────────────────────────────────────────────────────


class ThumbnailAPITests(ThumbnailWorkerTestBase):
    """缩略图 API 端点测试。"""

    def test_run_worker_api(self) -> None:
        """POST /api/thumbnails/worker/run。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        # 创建任务
        from backend.app.output_receiver import create_thumbnail_jobs

        create_thumbnail_jobs(self.manager, file_id)

        response = self.client.post("/api/thumbnails/worker/run?max_jobs=5")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["worker_result"]["processed"], 2)
        self.assertEqual(data["worker_result"]["completed"], 2)

    def test_list_file_thumbnails_api(self) -> None:
        """GET /api/files/{id}/thumbnails。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        rebuild_thumbnails_for_file(self.manager, file_id)

        response = self.client.get(f"/api/files/{file_id}/thumbnails")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["count"], 2)

    def test_list_file_thumbnails_not_found(self) -> None:
        """文件不存在时 404。"""
        response = self.client.get("/api/files/no-such-file/thumbnails")
        self.assertEqual(response.status_code, 404)

    def test_get_thumbnail_api(self) -> None:
        """GET /api/files/{id}/thumbnails/{size}。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        rebuild_thumbnails_for_file(self.manager, file_id)

        response = self.client.get(f"/api/files/{file_id}/thumbnails/256")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["thumbnail"]["size_class"], "256")

    def test_get_thumbnail_not_found(self) -> None:
        """缩略图不存在时 404。"""
        file_id = self._write_file()
        response = self.client.get(f"/api/files/{file_id}/thumbnails/256")
        self.assertEqual(response.status_code, 404)

    def test_serve_thumbnail_image_api(self) -> None:
        """GET /api/files/{id}/thumbnails/{size}/image 返回 WebP。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        rebuild_thumbnails_for_file(self.manager, file_id)

        response = self.client.get(f"/api/files/{file_id}/thumbnails/256/image")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")
        self.assertGreater(len(response.content), 0)

    def test_serve_thumbnail_not_ready(self) -> None:
        """缩略图未完成时 409。"""
        file_id = self._write_file()
        # 不生成缩略图，直接查询 image 端点
        response = self.client.get(f"/api/files/{file_id}/thumbnails/256/image")
        self.assertEqual(response.status_code, 404)

    def test_rebuild_file_thumbnails_api(self) -> None:
        """POST /api/files/{id}/thumbnails/rebuild。"""
        file_id = self._write_file(image_bytes=_make_png_bytes(400, 600))
        response = self.client.post(f"/api/files/{file_id}/thumbnails/rebuild")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data["rebuild_result"]["results"]), 2)

    def test_rebuild_file_thumbnails_not_found(self) -> None:
        """文件不存在时 404。"""
        response = self.client.post("/api/files/no-such-file/thumbnails/rebuild")
        self.assertEqual(response.status_code, 404)

    def test_rebuild_all_api(self) -> None:
        """POST /api/thumbnails/rebuild-all。"""
        self._write_file(image_bytes=_make_png_bytes(400, 600))
        self._write_file(image_bytes=_make_png_bytes(300, 300))

        response = self.client.post("/api/thumbnails/rebuild-all?limit=5")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["rebuild_result"]["total_files"], 2)


if __name__ == "__main__":
    unittest.main()
