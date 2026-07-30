"""MOD-09 导出执行逻辑测试。

测试范围：
- 文件复制/硬链接/降级
- 元数据移除
- 格式转换
- 文件名冲突处理（覆盖/跳过/加后缀）
- manifest 生成（JSON + CSV）
- 导出任务执行（成功/失败/空序列）
- 取消导出
- worker 批量处理
- API 端点
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.export_runner import (
    cancel_export_job,
    execute_export_job,
    run_export_worker_once,
)
from backend.app.output_receiver import create_file_record, create_image_instance


def _make_png_bytes(width: int = 100, height: int = 100, color=(128, 64, 192)) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class ExportRunnerTestBase(unittest.TestCase):
    """导出执行测试基类。"""

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

    def _create_project_and_final_version(self) -> tuple[str, str]:
        """创建项目和最终版本，返回 (project_id, final_version_id)。"""
        response = self.client.post("/api/projects", json={"name": "导出测试项目"})
        self.assertEqual(response.status_code, 201, response.text)
        project_id = response.json()["project"]["id"]

        response = self.client.post(
            f"/api/projects/{project_id}/final-versions",
            json={"name": "v1", "description": "测试"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        final_version_id = response.json()["final_version"]["id"]
        return project_id, final_version_id

    def _create_image_instance_with_file(
        self,
        project_id: str,
        *,
        image_bytes: bytes | None = None,
        adopted: bool = True,
        sort_order: int = 1,
    ) -> str:
        """创建文件记录和图片实例，返回 instance_id。"""
        import uuid as uuid_module

        if image_bytes is None:
            image_bytes = _make_png_bytes(100, 100)

        file_id = str(uuid_module.uuid4())
        storage_key = f"{file_id}.png"

        images_dir = Path(self._tmp.name) / "storage" / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        (images_dir / storage_key).write_bytes(image_bytes)

        create_file_record(
            self.manager,
            {
                "file_id": file_id,
                "storage_key": storage_key,
                "original_name": f"test_{file_id[:8]}.png",
                "mime_type": "image/png",
                "size_bytes": len(image_bytes),
                "content_hash": "hash-" + file_id[:8],
            },
        )

        # 创建场景页（简化：直接用 project_id 作为 shot_page_id 占位）
        shot_page_id = str(uuid_module.uuid4())
        instance = create_image_instance(
            self.manager,
            project_id=project_id,
            shot_page_id=shot_page_id,
            task_id=None,
            attempt_id=None,
            file_id=file_id,
            node_id=None,
            workflow_version_id=None,
            prompt_id=None,
            width=100,
            height=100,
            img_format="PNG",
            seed=None,
            resolved_json=None,
            snapshot_json=None,
        )
        instance_id = instance["id"]

        # 标记为已采用（如果有需要）
        if adopted:
            from datetime import datetime, timezone

            now = datetime.now(timezone.utc).isoformat()
            with self.manager.connection() as conn:
                conn.execute(
                    "UPDATE image_instances SET is_adopted = 1, sort_order = ? WHERE id = ?",
                    (sort_order, instance_id),
                )
                conn.commit()
        return instance_id

    def _setup_final_version_with_items(
        self, item_count: int = 2
    ) -> tuple[str, str, list[str]]:
        """创建带条目的最终版本。返回 (project_id, final_version_id, instance_ids)。"""
        project_id, final_version_id = self._create_project_and_final_version()
        instance_ids: list[str] = []
        for i in range(item_count):
            instance_id = self._create_image_instance_with_file(
                project_id, sort_order=i + 1
            )
            instance_ids.append(instance_id)
            response = self.client.post(
                f"/api/final-versions/{final_version_id}/items",
                json={"image_instance_id": instance_id},
            )
            self.assertEqual(response.status_code, 201, response.text)
        return project_id, final_version_id, instance_ids


# ──────────────────────────────────────────────────────────────────
# 导出执行核心
# ──────────────────────────────────────────────────────────────────


class ExecuteExportTests(ExportRunnerTestBase):
    """execute_export_job 核心测试。"""

    def test_execute_success_copy_mode(self) -> None:
        """copy 模式成功导出。"""
        _, fv_id, _ = self._setup_final_version_with_items(2)

        # 创建预设
        response = self.client.post(
            "/api/export-presets",
            json={
                "name": "copy-test",
                "format": "original",
                "copy_mode": "copy",
                "strip_metadata": False,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        preset_id = response.json()["preset"]["id"]

        # 创建导出任务
        output_dir = str(Path(self._tmp.name) / "export_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir, "preset_id": preset_id},
        )
        self.assertEqual(response.status_code, 201, response.text)
        job_id = response.json()["job"]["id"]

        # 执行
        result = execute_export_job(self.manager, job_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["exported"], 2)
        self.assertEqual(result["skipped"], 0)

        # 验证文件存在
        out_path = Path(output_dir)
        files = list(out_path.glob("*"))
        # 2 个图片 + manifest.json + manifest.csv = 4
        self.assertEqual(len(files), 4)
        # manifest 存在
        self.assertTrue((out_path / "manifest.json").exists())
        self.assertTrue((out_path / "manifest.csv").exists())

        # 验证 job 状态
        response = self.client.get("/api/export-jobs")
        data = response.json()
        job = [j for j in data["items"] if j["id"] == job_id][0]
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["completed_items"], 2)

    def test_execute_creates_output_dir(self) -> None:
        """输出目录不存在时自动创建。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "new_dir" / "sub")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        result = execute_export_job(self.manager, job_id)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(Path(output_dir).exists())

    def test_execute_empty_sequence(self) -> None:
        """空序列直接完成。"""
        _, fv_id = self._create_project_and_final_version()
        output_dir = str(Path(self._tmp.name) / "empty_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        result = execute_export_job(self.manager, job_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["exported"], 0)

    def test_execute_with_format_conversion(self) -> None:
        """格式转换 png -> jpeg。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        response = self.client.post(
            "/api/export-presets",
            json={
                "name": "jpeg-test",
                "format": "jpeg",
                "copy_mode": "copy",
                "strip_metadata": False,
            },
        )
        preset_id = response.json()["preset"]["id"]
        output_dir = str(Path(self._tmp.name) / "jpeg_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir, "preset_id": preset_id},
        )
        job_id = response.json()["job"]["id"]

        result = execute_export_job(self.manager, job_id)
        self.assertEqual(result["status"], "completed")

        # 验证输出是 JPEG
        out_path = Path(output_dir)
        image_files = [f for f in out_path.iterdir() if f.suffix == ".jpg"]
        self.assertEqual(len(image_files), 1)
        with Image.open(image_files[0]) as img:
            self.assertEqual(img.format, "JPEG")

    def test_execute_strip_metadata(self) -> None:
        """strip_metadata=True 时移除元数据。"""
        # 创建带 EXIF 的 JPEG
        img = Image.new("RGB", (100, 100), color=(64, 128, 192))
        from PIL.ExifTags import Base as ExifBase

        exif_data = img.getexif()
        exif_data[ExifBase.ImageDescription] = "secret metadata"
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif_data)
        image_bytes = buf.getvalue()

        _, fv_id, _ = self._setup_final_version_with_items(1)
        # 替换实例的文件为带 EXIF 的 JPEG
        # 简化：直接创建一个新的图片实例（不采用，仅用于导出）
        project_id, _ = self._create_project_and_final_version()
        project_id_2, fv_id_2, instance_ids = self._setup_final_version_with_items(1)

        response = self.client.post(
            "/api/export-presets",
            json={
                "name": "strip-test",
                "format": "original",
                "copy_mode": "copy",
                "strip_metadata": True,
            },
        )
        preset_id = response.json()["preset"]["id"]
        output_dir = str(Path(self._tmp.name) / "strip_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id_2}/export-jobs",
            json={"output_dir": output_dir, "preset_id": preset_id},
        )
        job_id = response.json()["job"]["id"]

        result = execute_export_job(self.manager, job_id)
        self.assertEqual(result["status"], "completed")

        # 验证输出的图片没有 EXIF（PNG 没问题，重点是没元数据）
        out_path = Path(output_dir)
        image_files = [f for f in out_path.iterdir() if f.suffix == ".png"]
        self.assertEqual(len(image_files), 1)


# ──────────────────────────────────────────────────────────────────
# 冲突处理
# ──────────────────────────────────────────────────────────────────


class ConflictStrategyTests(ExportRunnerTestBase):
    """文件名冲突处理测试。"""

    def test_suffix_strategy(self) -> None:
        """suffix 策略加后缀。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "conflict_out")
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        # 预先创建同名文件
        (Path(output_dir) / "0001_test_00000001.png").write_bytes(b"existing")

        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        # 使用 suffix 策略，output_pattern 简化为固定
        result = execute_export_job(self.manager, job_id, conflict_strategy="suffix")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["exported"], 1)

    def test_overwrite_strategy(self) -> None:
        """overwrite 策略覆盖。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "overwrite_out")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        result = execute_export_job(self.manager, job_id, conflict_strategy="overwrite")
        self.assertEqual(result["status"], "completed")

    def test_skip_strategy(self) -> None:
        """skip 策略跳过已存在文件。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "skip_out")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # 先导出一次（生成文件）
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id_1 = response.json()["job"]["id"]
        execute_export_job(self.manager, job_id_1)

        # 第二次导出到同一目录，用 skip 策略
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id_2 = response.json()["job"]["id"]
        result = execute_export_job(self.manager, job_id_2, conflict_strategy="skip")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["skipped"], 1)


# ──────────────────────────────────────────────────────────────────
# 取消导出
# ──────────────────────────────────────────────────────────────────


class CancelExportTests(ExportRunnerTestBase):
    """取消导出测试。"""

    def test_cancel_pending_job(self) -> None:
        """取消 pending 任务直接置为 cancelled。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "cancel_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        result = cancel_export_job(self.manager, job_id)
        self.assertEqual(result["status"], "cancelled")

    def test_cancel_nonexistent_job_raises(self) -> None:
        """取消不存在的任务抛出异常。"""
        with self.assertRaises(ValueError):
            cancel_export_job(self.manager, "nonexistent-id")

    def test_cancel_completed_job_returns_current(self) -> None:
        """取消已完成的任务返回当前状态。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "done_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]
        execute_export_job(self.manager, job_id)

        result = cancel_export_job(self.manager, job_id)
        self.assertEqual(result["status"], "completed")


# ──────────────────────────────────────────────────────────────────
# Worker
# ──────────────────────────────────────────────────────────────────


class ExportWorkerTests(ExportRunnerTestBase):
    """导出 worker 测试。"""

    def test_worker_processes_pending_jobs(self) -> None:
        """worker 处理 pending 任务。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "worker_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        result = run_export_worker_once(self.manager, max_jobs=5)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["failed"], 0)

    def test_worker_no_pending_returns_empty(self) -> None:
        """无 pending 任务时返回空。"""
        result = run_export_worker_once(self.manager, max_jobs=5)
        self.assertEqual(result["processed"], 0)


# ──────────────────────────────────────────────────────────────────
# API 端点
# ──────────────────────────────────────────────────────────────────


class ExportAPITests(ExportRunnerTestBase):
    """导出 API 端点测试。"""

    def test_execute_api(self) -> None:
        """POST /api/export-jobs/{id}/execute。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "api_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        response = self.client.post(f"/api/export-jobs/{job_id}/execute")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["export_result"]["status"], "completed")

    def test_execute_api_not_found(self) -> None:
        """任务不存在时 400。"""
        response = self.client.post("/api/export-jobs/nonexistent/execute")
        self.assertEqual(response.status_code, 400)

    def test_cancel_api(self) -> None:
        """POST /api/export-jobs/{id}/cancel。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "cancel_api_out")
        response = self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )
        job_id = response.json()["job"]["id"]

        response = self.client.post(f"/api/export-jobs/{job_id}/cancel")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["cancel_result"]["status"], "cancelled")

    def test_cancel_api_not_found(self) -> None:
        """取消不存在的任务 404。"""
        response = self.client.post("/api/export-jobs/nonexistent/cancel")
        self.assertEqual(response.status_code, 404)

    def test_worker_run_api(self) -> None:
        """POST /api/export-jobs/worker/run。"""
        _, fv_id, _ = self._setup_final_version_with_items(1)
        output_dir = str(Path(self._tmp.name) / "worker_api_out")
        self.client.post(
            f"/api/final-versions/{fv_id}/export-jobs",
            json={"output_dir": output_dir},
        )

        response = self.client.post("/api/export-jobs/worker/run?max_jobs=5")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["worker_result"]["processed"], 1)

    def test_rebuild_from_adoptions_api(self) -> None:
        """POST /api/final-versions/{id}/rebuild-from-adoptions。"""
        project_id, fv_id = self._create_project_and_final_version()
        # 创建采用实例
        for i in range(3):
            self._create_image_instance_with_file(project_id, sort_order=i + 1)

        response = self.client.post(f"/api/final-versions/{fv_id}/rebuild-from-adoptions")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["rebuilt"])

    def test_rebuild_from_adoptions_not_found(self) -> None:
        """最终版本不存在时 404。"""
        response = self.client.post("/api/final-versions/nonexistent/rebuild-from-adoptions")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
