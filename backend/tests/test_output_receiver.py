"""阶段 3.6 输出和图片实例测试。

测试范围：
- 输出解析（parse_comfyui_outputs）
- 图片下载和校验（download_and_validate_image）
- 文件记录和图片实例写入
- 缩略图后台任务创建
- 快照构建
- 输出收集主流程（collect_attempt_outputs）
- API 端点：收集输出、列表、详情、下载、后台任务

使用 mock ComfyUIClient 和真实 PIL 图片避免依赖真实 ComfyUI 服务。
"""
from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.comfyui_client import ComfyUIError
from backend.app.comfyui_submit import submit_task_to_comfyui
from backend.app.output_receiver import (
    build_snapshot,
    collect_attempt_outputs,
    create_file_record,
    create_image_instance,
    create_thumbnail_jobs,
    download_and_validate_image,
    get_file_path,
    get_file_record,
    get_image_instance,
    list_background_jobs,
    list_image_instances,
    parse_comfyui_outputs,
)


def _make_test_png(width: int = 64, height: int = 64) -> bytes:
    """生成测试用 PNG 图片字节。"""
    img = Image.new("RGB", (width, height), color=(128, 64, 192))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_test_jpeg(width: int = 32, height: int = 32) -> bytes:
    """生成测试用 JPEG 图片字节。"""
    img = Image.new("RGB", (width, height), color=(64, 192, 128))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


# ──────────────────────────────────────────────────────────────────
# 输出解析测试
# ──────────────────────────────────────────────────────────────────


class ParseOutputsTests(unittest.TestCase):
    """parse_comfyui_outputs 测试。"""

    def test_parse_single_image(self) -> None:
        """解析单个输出节点的单张图片。"""
        history_entry = {
            "outputs": {
                "node-1": {
                    "images": [
                        {"filename": "output.png", "subfolder": "", "type": "output"}
                    ]
                }
            }
        }
        images = parse_comfyui_outputs(history_entry)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["filename"], "output.png")
        self.assertEqual(images[0]["node_id"], "node-1")

    def test_parse_multiple_nodes_multiple_images(self) -> None:
        """解析多个输出节点的多张图片。"""
        history_entry = {
            "outputs": {
                "node-1": {
                    "images": [
                        {"filename": "img1.png", "subfolder": "", "type": "output"},
                        {"filename": "img2.png", "subfolder": "", "type": "output"},
                    ]
                },
                "node-2": {
                    "images": [
                        {"filename": "img3.png", "subfolder": "sub", "type": "output"}
                    ]
                },
            }
        }
        images = parse_comfyui_outputs(history_entry)
        self.assertEqual(len(images), 3)
        filenames = [img["filename"] for img in images]
        self.assertIn("img1.png", filenames)
        self.assertIn("img2.png", filenames)
        self.assertIn("img3.png", filenames)

    def test_parse_gif_output(self) -> None:
        """解析 GIF 输出。"""
        history_entry = {
            "outputs": {
                "node-1": {
                    "gifs": [
                        {"filename": "anim.gif", "subfolder": "", "type": "output"}
                    ]
                }
            }
        }
        images = parse_comfyui_outputs(history_entry)
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]["filename"], "anim.gif")

    def test_parse_empty_outputs(self) -> None:
        """空输出返回空列表。"""
        self.assertEqual(parse_comfyui_outputs({}), [])
        self.assertEqual(parse_comfyui_outputs({"outputs": {}}), [])
        self.assertEqual(parse_comfyui_outputs({"outputs": None}), [])

    def test_parse_no_images_key(self) -> None:
        """输出节点没有 images/gifs 字段时跳过。"""
        history_entry = {
            "outputs": {
                "node-1": {"text": "some text output"}
            }
        }
        images = parse_comfyui_outputs(history_entry)
        self.assertEqual(len(images), 0)


# ──────────────────────────────────────────────────────────────────
# 图片下载和校验测试
# ──────────────────────────────────────────────────────────────────


class DownloadAndValidateTests(unittest.TestCase):
    """download_and_validate_image 测试。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dest_dir = Path(self._tmp.name) / "images"

    def test_download_png_success(self) -> None:
        """成功下载 PNG 并校验。"""
        png_bytes = _make_test_png(64, 48)
        mock_client = MagicMock()
        mock_client.download_image.return_value = png_bytes

        result = download_and_validate_image(
            mock_client,
            {"filename": "test.png", "subfolder": "", "folder_type": "output"},
            self.dest_dir,
        )
        self.assertEqual(result["format"], "PNG")
        self.assertEqual(result["width"], 64)
        self.assertEqual(result["height"], 48)
        self.assertEqual(result["mime_type"], "image/png")
        self.assertTrue(result["size_bytes"] > 0)
        self.assertIsNotNone(result["content_hash"])
        # 文件应存在于目标目录
        file_path = self.dest_dir / result["storage_key"]
        self.assertTrue(file_path.exists())
        # 验证哈希
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        self.assertEqual(actual_hash, result["content_hash"])

    def test_download_jpeg_success(self) -> None:
        """成功下载 JPEG 并校验。"""
        jpeg_bytes = _make_test_jpeg(32, 32)
        mock_client = MagicMock()
        mock_client.download_image.return_value = jpeg_bytes

        result = download_and_validate_image(
            mock_client,
            {"filename": "test.jpg", "subfolder": "", "folder_type": "output"},
            self.dest_dir,
        )
        self.assertEqual(result["format"], "JPEG")
        self.assertEqual(result["width"], 32)

    def test_download_missing_filename_raises(self) -> None:
        """缺少 filename 时抛出异常。"""
        mock_client = MagicMock()
        with self.assertRaises(ValueError):
            download_and_validate_image(
                mock_client,
                {"filename": "", "subfolder": "", "folder_type": "output"},
                self.dest_dir,
            )

    def test_download_hash_mismatch_raises(self) -> None:
        """哈希不匹配时抛出异常。"""
        png_bytes = _make_test_png()
        mock_client = MagicMock()
        mock_client.download_image.return_value = png_bytes

        with self.assertRaises(ValueError) as ctx:
            download_and_validate_image(
                mock_client,
                {"filename": "test.png", "subfolder": "", "folder_type": "output"},
                self.dest_dir,
                expected_hash="wrong_hash",
            )
        self.assertIn("哈希不匹配", str(ctx.exception))

    def test_download_invalid_image_raises(self) -> None:
        """下载非图片数据时抛出异常。"""
        mock_client = MagicMock()
        mock_client.download_image.return_value = b"not an image"

        with self.assertRaises(Exception):
            download_and_validate_image(
                mock_client,
                {"filename": "test.png", "subfolder": "", "folder_type": "output"},
                self.dest_dir,
            )


# ──────────────────────────────────────────────────────────────────
# 测试基类（API 集成测试）
# ──────────────────────────────────────────────────────────────────


class _OutputTestBase(unittest.TestCase):
    """输出接收测试基类。"""

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
        self.mock_comfyui = MagicMock()
        self.app.state.comfyui_client = self.mock_comfyui

    def _setup_full_project(self, page_count: int = 1) -> tuple[str, list[str], str, str]:
        """创建完整项目结构。"""
        response = self.client.post("/api/projects", json={"name": "输出测试项目"})
        self.assertEqual(response.status_code, 201, response.text)
        project_id = response.json()["project"]["id"]
        response = self.client.post(
            f"/api/projects/{project_id}/chapters", json={"name": "第一章"}
        )
        self.assertEqual(response.status_code, 201, response.text)
        chapter_id = response.json()["chapter"]["id"]
        response = self.client.post(
            f"/api/chapters/{chapter_id}/large-scenes",
            json={"name": "大场景1", "scene_type": "content"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        large_scene_id = response.json()["large_scene"]["id"]
        response = self.client.post(
            f"/api/large-scenes/{large_scene_id}/small-scenes", json={"name": "小场景1"}
        )
        self.assertEqual(response.status_code, 201, response.text)
        small_scene_id = response.json()["small_scene"]["id"]
        shot_page_ids: list[str] = []
        for i in range(page_count):
            response = self.client.post(
                f"/api/small-scenes/{small_scene_id}/shot-pages",
                json={"title": f"场景页{i + 1}"},
            )
            self.assertEqual(response.status_code, 201, response.text)
            shot_page_ids.append(response.json()["shot_page"]["id"])
        response = self.client.post("/api/workflows", json={"name": "工作流1"})
        self.assertEqual(response.status_code, 201, response.text)
        workflow_id = response.json()["workflow"]["id"]
        nodes = [{
            "id": "1", "type": "CheckpointLoaderSimple", "title": "Load",
            "position": [0, 0], "size": [240, 100], "mode": 0,
            "flags": {"enabled": True, "bypassed": False, "disabled": False},
            "widgets_values": ["model.safetensors"], "properties": {},
            "inputs": [], "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
            "order": 0, "is_unknown": False,
        }]
        normalized = {"nodes": nodes, "links": [], "groups": [], "metadata": {}}
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft",
            json={
                "normalized_graph": json.dumps(normalized, ensure_ascii=False),
                "raw_ui_json": None, "raw_api_json": None, "node_count": 1,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v1", "normalized_graph": ""},
        )
        self.assertEqual(response.status_code, 200, response.text)
        version_id = response.json()["version"]["id"]
        response = self.client.post(
            f"/api/projects/{project_id}/default-workflow",
            json={"workflow_id": workflow_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return project_id, shot_page_ids, workflow_id, version_id

    def _setup_submitted_attempt(self) -> tuple[str, str, str]:
        """创建已提交的 attempt，返回 (task_id, attempt_id, prompt_id)。"""
        project_id, _, _, _ = self._setup_full_project(page_count=1)
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json={"name": "测试草稿", "scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        draft_id = response.json()["draft"]["id"]
        self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit", json={"name": "测试批次"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        batch_id = response.json()["batch"]["id"]
        self.client.patch(f"/api/batches/{batch_id}/status", json={"status": "running"})
        response = self.client.post(
            f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3}
        )
        self.assertEqual(response.status_code, 200, response.text)
        tasks = response.json()["tasks"]
        task_id = tasks[0]["id"]
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "test-worker"}
        ).json()["claim"]
        attempt_id = claim["attempt_id"]
        prompt_id = "comfyui-prompt-output-test"
        self.mock_comfyui.submit_prompt.return_value = {
            "prompt_id": prompt_id,
            "number": 1,
            "node_errors": {},
        }
        result = submit_task_to_comfyui(
            self.manager, self.mock_comfyui, task_id, attempt_id
        )
        self.assertTrue(result["submitted"])
        return task_id, attempt_id, prompt_id


# ──────────────────────────────────────────────────────────────────
# 数据库写入测试
# ──────────────────────────────────────────────────────────────────


class DatabaseWriteTests(_OutputTestBase):
    """文件和图片实例数据库写入测试。"""

    def test_create_file_record(self) -> None:
        """写入文件记录。"""
        file_data = {
            "file_id": "test-file-1",
            "storage_key": "test-file-1.png",
            "original_name": "output.png",
            "mime_type": "image/png",
            "size_bytes": 1024,
            "content_hash": "abc123",
        }
        record = create_file_record(self.manager, file_data)
        self.assertEqual(record["id"], "test-file-1")
        self.assertEqual(record["storage_key"], "test-file-1.png")
        self.assertEqual(record["state"], "active")

    def test_get_file_record(self) -> None:
        """获取文件记录。"""
        file_data = {
            "file_id": "test-file-2",
            "storage_key": "test-file-2.png",
            "original_name": "output.png",
            "mime_type": "image/png",
            "size_bytes": 2048,
            "content_hash": "def456",
        }
        create_file_record(self.manager, file_data)
        record = get_file_record(self.manager, "test-file-2")
        self.assertIsNotNone(record)
        self.assertEqual(record["content_hash"], "def456")

    def test_get_file_record_not_found(self) -> None:
        """文件不存在时返回 None。"""
        self.assertIsNone(get_file_record(self.manager, "nonexistent"))

    def test_create_image_instance(self) -> None:
        """写入图片实例记录。"""
        _, _, _, _ = self._setup_full_project(page_count=1)
        # 先创建文件记录
        file_data = {
            "file_id": "test-file-3",
            "storage_key": "test-file-3.png",
            "original_name": "output.png",
            "mime_type": "image/png",
            "size_bytes": 512,
            "content_hash": "ghi789",
        }
        create_file_record(self.manager, file_data)

        # 获取项目ID和页面ID
        instances_before = list_image_instances(self.manager)
        # 我们需要 project_id 和 shot_page_id
        with self.manager.connection() as conn:
            proj = conn.execute("SELECT id FROM projects LIMIT 1").fetchone()
            page = conn.execute("SELECT id FROM shot_pages LIMIT 1").fetchone()
        project_id = proj["id"]
        shot_page_id = page["id"]

        instance = create_image_instance(
            self.manager,
            project_id=project_id,
            shot_page_id=shot_page_id,
            task_id=None,
            attempt_id=None,
            file_id="test-file-3",
            node_id="node-1",
            workflow_version_id=None,
            prompt_id="test-prompt",
            width=512,
            height=512,
            img_format="PNG",
            seed=42,
            resolved_json={"test": "data"},
            snapshot_json={"snapshot": "info"},
        )
        self.assertIsNotNone(instance)
        self.assertEqual(instance["file_id"], "test-file-3")
        self.assertEqual(instance["width"], 512)
        self.assertEqual(instance["seed"], 42)
        self.assertEqual(instance["format"], "PNG")

    def test_create_thumbnail_jobs(self) -> None:
        """创建缩略图后台任务。"""
        file_data = {
            "file_id": "test-file-4",
            "storage_key": "test-file-4.png",
            "original_name": "output.png",
            "mime_type": "image/png",
            "size_bytes": 256,
            "content_hash": "jkl012",
        }
        create_file_record(self.manager, file_data)
        jobs = create_thumbnail_jobs(self.manager, "test-file-4")
        self.assertEqual(len(jobs), 2)  # 256px 和 640px
        size_classes = [json.loads(j["payload_json"])["size_class"] for j in jobs]
        self.assertIn("256", size_classes)
        self.assertIn("640", size_classes)
        self.assertTrue(all(j["status"] == "pending" for j in jobs))


# ──────────────────────────────────────────────────────────────────
# 快照构建测试
# ──────────────────────────────────────────────────────────────────


class BuildSnapshotTests(_OutputTestBase):
    """build_snapshot 测试。"""

    def test_build_snapshot_contains_key_fields(self) -> None:
        """快照包含任务、页面、工作流等关键字段。"""
        _, attempt_id, _ = self._setup_submitted_attempt()
        from backend.app.task_queue import get_attempt, get_task
        attempt = get_attempt(self.manager, attempt_id)
        task = get_task(self.manager, attempt["task_id"])
        snapshot = build_snapshot(self.manager, task, attempt)
        self.assertIn("task_id", snapshot)
        self.assertIn("attempt_id", snapshot)
        self.assertIn("prompt_id", snapshot)
        self.assertIn("project_id", snapshot)
        self.assertIn("shot_page_id", snapshot)
        self.assertIn("workflow_version_id", snapshot)
        self.assertIn("seed_strategy", snapshot)


# ──────────────────────────────────────────────────────────────────
# 输出收集主流程测试
# ──────────────────────────────────────────────────────────────────


class CollectOutputsTests(_OutputTestBase):
    """collect_attempt_outputs 测试。"""

    def test_collect_single_image(self) -> None:
        """收集单张图片输出。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png_bytes = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "output.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png_bytes

        result = collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)
        self.assertEqual(result["collected"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(result["image_instances"]), 1)
        # 验证 attempt 标记为已完成
        from backend.app.task_queue import get_attempt
        attempt = get_attempt(self.manager, attempt_id)
        self.assertEqual(attempt["status"], "completed")

    def test_collect_multiple_images(self) -> None:
        """收集多张图片输出。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png1 = _make_test_png(64, 64)
        png2 = _make_test_png(48, 48)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "img1.png", "subfolder": "", "type": "output"},
                            {"filename": "img2.png", "subfolder": "", "type": "output"},
                        ]
                    },
                    "node-2": {
                        "images": [
                            {"filename": "img3.png", "subfolder": "", "type": "output"}
                        ]
                    },
                },
            },
        }
        self.mock_comfyui.download_image.side_effect = [png1, png2, png1]

        result = collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)
        self.assertEqual(result["collected"], 3)
        self.assertEqual(result["failed"], 0)

    def test_collect_no_images_marks_completed(self) -> None:
        """没有图片输出时也标记完成。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {},
            },
        }
        result = collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)
        self.assertEqual(result["collected"], 0)
        from backend.app.task_queue import get_attempt
        attempt = get_attempt(self.manager, attempt_id)
        self.assertEqual(attempt["status"], "completed")

    def test_collect_partial_failure(self) -> None:
        """部分图片下载失败时其他图片仍成功收集。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "good.png", "subfolder": "", "type": "output"},
                            {"filename": "bad.png", "subfolder": "", "type": "output"},
                        ]
                    },
                },
            },
        }
        # 第一张成功，第二张失败
        self.mock_comfyui.download_image.side_effect = [png, ComfyUIError("下载失败")]

        result = collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)
        self.assertEqual(result["collected"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(len(result["errors"]), 1)

    def test_collect_attempt_not_found_raises(self) -> None:
        """attempt 不存在时抛出异常。"""
        with self.assertRaises(ValueError):
            collect_attempt_outputs(self.manager, self.mock_comfyui, "nonexistent")

    def test_collect_no_prompt_id_raises(self) -> None:
        """attempt 没有 prompt_id 时抛出异常。"""
        # 创建任务但未提交
        project_id, _, _, _ = self._setup_full_project(page_count=1)
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json={"name": "草稿", "scope": "project"},
        )
        draft_id = response.json()["draft"]["id"]
        self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit", json={"name": "批次"}
        )
        batch_id = response.json()["batch"]["id"]
        self.client.patch(f"/api/batches/{batch_id}/status", json={"status": "running"})
        response = self.client.post(
            f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3}
        )
        task_id = response.json()["tasks"][0]["id"]
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "worker"}
        ).json()["claim"]
        attempt_id = claim["attempt_id"]
        # 未提交，没有 prompt_id
        with self.assertRaises(ValueError):
            collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

    def test_collect_creates_thumbnail_jobs(self) -> None:
        """收集图片后创建缩略图后台任务。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)
        jobs = list_background_jobs(self.manager, job_type="thumbnail")
        self.assertEqual(len(jobs), 2)  # 256 和 640


# ──────────────────────────────────────────────────────────────────
# 查询函数测试
# ──────────────────────────────────────────────────────────────────


class QueryTests(_OutputTestBase):
    """查询函数测试。"""

    def test_list_image_instances_empty(self) -> None:
        """空数据库返回空列表。"""
        instances = list_image_instances(self.manager)
        self.assertEqual(len(instances), 0)

    def test_list_image_instances_by_project(self) -> None:
        """按项目过滤图片实例。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

        # 查询所有
        all_instances = list_image_instances(self.manager)
        self.assertEqual(len(all_instances), 1)

        # 按项目查询
        project_id = all_instances[0]["project_id"]
        project_instances = list_image_instances(self.manager, project_id=project_id)
        self.assertEqual(len(project_instances), 1)

        # 按不存在的项目查询
        empty = list_image_instances(self.manager, project_id="nonexistent")
        self.assertEqual(len(empty), 0)

    def test_get_image_instance(self) -> None:
        """获取单个图片实例。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

        instances = list_image_instances(self.manager)
        instance_id = instances[0]["id"]
        instance = get_image_instance(self.manager, instance_id)
        self.assertIsNotNone(instance)
        self.assertEqual(instance["id"], instance_id)

    def test_get_image_instance_not_found(self) -> None:
        """图片实例不存在时返回 None。"""
        self.assertIsNone(get_image_instance(self.manager, "nonexistent"))

    def test_get_file_path(self) -> None:
        """获取文件存储路径。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

        instances = list_image_instances(self.manager)
        file_id = instances[0]["file_id"]
        file_path = get_file_path(self.manager, file_id)
        self.assertIsNotNone(file_path)
        self.assertTrue(file_path.exists())


# ──────────────────────────────────────────────────────────────────
# API 端点测试
# ──────────────────────────────────────────────────────────────────


class OutputApiTests(_OutputTestBase):
    """输出相关 API 端点测试。"""

    def test_list_image_instances_api_empty(self) -> None:
        """空数据库列表返回空。"""
        response = self.client.get("/api/image-instances")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_get_image_instance_not_found_api(self) -> None:
        """获取不存在的图片实例返回 404。"""
        response = self.client.get("/api/image-instances/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_download_file_not_found_api(self) -> None:
        """下载不存在的文件返回 404。"""
        response = self.client.get("/api/files/nonexistent/download")
        self.assertEqual(response.status_code, 404)

    @patch("backend.app.app_factory.collect_attempt_outputs")
    def test_collect_outputs_api_success(self, mock_collect: MagicMock) -> None:
        """收集输出 API 端点。"""
        _, attempt_id, _ = self._setup_submitted_attempt()
        mock_collect.return_value = {
            "attempt_id": attempt_id,
            "prompt_id": "test-prompt",
            "collected": 1,
            "failed": 0,
            "image_instances": [{"id": "inst-1"}],
            "errors": [],
        }
        response = self.client.post(f"/api/attempts/{attempt_id}/collect-outputs")
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertEqual(result["collected"], 1)

    @patch("backend.app.app_factory.collect_attempt_outputs")
    def test_collect_outputs_api_attempt_not_found(self, mock_collect: MagicMock) -> None:
        """收集输出 attempt 不存在时返回 422。"""
        mock_collect.side_effect = ValueError("attempt 不存在: nonexistent")
        response = self.client.post("/api/attempts/nonexistent/collect-outputs")
        self.assertEqual(response.status_code, 422)

    def test_list_background_jobs_api_empty(self) -> None:
        """空后台任务列表。"""
        response = self.client.get("/api/background-jobs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 0)

    def test_list_background_jobs_after_collect(self) -> None:
        """收集图片后查询后台任务。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        # 直接调用函数（绕过闭包）
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

        response = self.client.get("/api/background-jobs?job_type=thumbnail")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)

    def test_download_file_api_success(self) -> None:
        """成功下载文件。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

        instances = list_image_instances(self.manager)
        file_id = instances[0]["file_id"]
        response = self.client.get(f"/api/files/{file_id}/download")
        self.assertEqual(response.status_code, 200)
        self.assertIn("image/png", response.headers.get("content-type", ""))

    def test_list_image_instances_with_filters(self) -> None:
        """使用过滤器查询图片实例。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

        # 先获取所有实例
        response = self.client.get("/api/image-instances")
        self.assertEqual(response.status_code, 200)
        instances = response.json()["image_instances"]
        self.assertEqual(len(instances), 1)

        # 按 project_id 过滤
        project_id = instances[0]["project_id"]
        response = self.client.get(f"/api/image-instances?project_id={project_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["image_instances"]), 1)

        # 按 shot_page_id 过滤
        shot_page_id = instances[0]["shot_page_id"]
        response = self.client.get(f"/api/image-instances?shot_page_id={shot_page_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["image_instances"]), 1)

    def test_get_image_instance_api_success(self) -> None:
        """获取图片实例详情。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        png = _make_test_png(64, 64)
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {
                    "node-1": {
                        "images": [
                            {"filename": "out.png", "subfolder": "", "type": "output"}
                        ]
                    }
                },
            },
        }
        self.mock_comfyui.download_image.return_value = png
        collect_attempt_outputs(self.manager, self.mock_comfyui, attempt_id)

        instances = list_image_instances(self.manager)
        instance_id = instances[0]["id"]
        response = self.client.get(f"/api/image-instances/{instance_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("image_instance", data)
        self.assertIn("file", data)
        self.assertEqual(data["image_instance"]["id"], instance_id)


if __name__ == "__main__":
    unittest.main()
