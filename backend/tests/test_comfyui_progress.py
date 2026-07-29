"""阶段 3.5 实时进度与故障恢复测试。

测试范围：
- ProgressTracker 进度跟踪（事件解析、订阅通知）
- ComfyUIWebSocketListener 启停和 URL 更新
- 历史轮询兜底（poll_comfyui_history_for_attempt）
- 重启恢复（recover_submitted_attempts）
- SSE 进度推送生成器
- API 端点：SSE、轮询、恢复、内存进度查询

使用 mock ComfyUIClient 避免依赖真实 ComfyUI 服务。
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.comfyui_client import ComfyUIError
from backend.app.comfyui_progress import (
    ComfyUIWebSocketListener,
    ProgressTracker,
    poll_comfyui_history_for_attempt,
    recover_submitted_attempts,
    sse_progress_generator,
)
from backend.app.comfyui_submit import submit_task_to_comfyui


# ──────────────────────────────────────────────────────────────────
# ProgressTracker 单元测试
# ──────────────────────────────────────────────────────────────────


class ProgressTrackerTests(unittest.TestCase):
    """ProgressTracker 进度跟踪器测试。"""

    def test_update_creates_entry(self) -> None:
        """update 首次调用创建进度条目。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {"type": "execution_start", "data": {}})
        entry = tracker.get("prompt-1")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["prompt_id"], "prompt-1")
        self.assertEqual(entry["status"], "running")

    def test_update_progress_event(self) -> None:
        """progress 事件更新进度值。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {
            "type": "progress",
            "data": {"value": 5, "max": 10},
        })
        entry = tracker.get("prompt-1")
        self.assertEqual(entry["progress_value"], 5)
        self.assertEqual(entry["progress_max"], 10)

    def test_update_executing_event_sets_current_node(self) -> None:
        """executing 事件设置当前节点。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {
            "type": "executing",
            "data": {"node": "node-5"},
        })
        entry = tracker.get("prompt-1")
        self.assertEqual(entry["current_node"], "node-5")
        self.assertEqual(entry["status"], "running")

    def test_update_executing_node_none_marks_completed(self) -> None:
        """executing 事件 node 为 None 表示完成。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {
            "type": "executing",
            "data": {"node": None},
        })
        entry = tracker.get("prompt-1")
        self.assertEqual(entry["status"], "completed")

    def test_update_execution_success_marks_completed(self) -> None:
        """execution_success 事件标记完成。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {
            "type": "execution_success",
            "data": {},
        })
        entry = tracker.get("prompt-1")
        self.assertEqual(entry["status"], "completed")

    def test_update_execution_error_marks_error(self) -> None:
        """execution_error 事件标记错误。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {
            "type": "execution_error",
            "data": {"exception_message": "CUDA out of memory"},
        })
        entry = tracker.get("prompt-1")
        self.assertEqual(entry["status"], "error")
        self.assertIn("CUDA out of memory", entry["error"])

    def test_update_execution_interrupt_marks_interrupted(self) -> None:
        """execution_interrupt 事件标记中断。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {
            "type": "execution_interrupt",
            "data": {},
        })
        entry = tracker.get("prompt-1")
        self.assertEqual(entry["status"], "interrupted")

    def test_update_executed_event_records_output(self) -> None:
        """executed 事件记录节点输出。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {
            "type": "executed",
            "data": {
                "node": "node-9",
                "output": {"images": [{"filename": "test.png"}]},
            },
        })
        entry = tracker.get("prompt-1")
        self.assertIn("node-9", entry["outputs"])
        self.assertEqual(entry["outputs"]["node-9"]["images"][0]["filename"], "test.png")

    def test_update_appends_events(self) -> None:
        """多次 update 追加事件到 events 列表。"""
        tracker = ProgressTracker()
        for i in range(3):
            tracker.update("prompt-1", {"type": "progress", "data": {"value": i}})
        entry = tracker.get("prompt-1")
        self.assertEqual(len(entry["events"]), 3)

    def test_get_returns_none_for_unknown(self) -> None:
        """get 对未知 prompt_id 返回 None。"""
        tracker = ProgressTracker()
        self.assertIsNone(tracker.get("unknown"))

    def test_remove_deletes_entry(self) -> None:
        """remove 删除进度条目。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {"type": "execution_start", "data": {}})
        tracker.remove("prompt-1")
        self.assertIsNone(tracker.get("prompt-1"))

    def test_clear_removes_all(self) -> None:
        """clear 清空所有进度数据。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {"type": "execution_start", "data": {}})
        tracker.update("prompt-2", {"type": "execution_start", "data": {}})
        tracker.clear()
        self.assertIsNone(tracker.get("prompt-1"))
        self.assertIsNone(tracker.get("prompt-2"))

    def test_get_all_returns_copy(self) -> None:
        """get_all 返回外层字典的副本。"""
        tracker = ProgressTracker()
        tracker.update("prompt-1", {"type": "execution_start", "data": {}})
        all_data = tracker.get_all()
        self.assertIn("prompt-1", all_data)
        # 修改返回的字典不影响原数据的外层结构
        all_data["prompt-2"] = {"status": "fake"}
        self.assertNotIn("prompt-2", tracker.get_all())

    def test_subscribe_unsubscribe(self) -> None:
        """subscribe 和 unsubscribe 正确管理订阅者列表。"""
        tracker = ProgressTracker()

        async def _test():
            queue = await tracker.subscribe("prompt-1")
            # update 后订阅者应收到通知
            tracker.update("prompt-1", {"type": "execution_start", "data": {}})
            data = await asyncio.wait_for(queue.get(), timeout=1.0)
            self.assertEqual(data["prompt_id"], "prompt-1")
            tracker.unsubscribe("prompt-1", queue)
            # 取消订阅后不再收到通知
            tracker.update("prompt-1", {"type": "progress", "data": {"value": 1}})
            self.assertTrue(queue.empty())

        asyncio.run(_test())


# ──────────────────────────────────────────────────────────────────
# ComfyUIWebSocketListener 单元测试
# ──────────────────────────────────────────────────────────────────


class WebSocketListenerTests(unittest.TestCase):
    """ComfyUIWebSocketListener 测试。"""

    def test_start_stop(self) -> None:
        """start 和 stop 正确管理运行状态。"""

        async def _test():
            tracker = ProgressTracker()
            listener = ComfyUIWebSocketListener(
                "ws://127.0.0.1:8188/ws",
                tracker,
                client_id="test-client",
            )
            self.assertFalse(listener.running)
            await listener.start()
            self.assertTrue(listener.running)
            await listener.stop()
            self.assertFalse(listener.running)

        asyncio.run(_test())

    def test_start_idempotent(self) -> None:
        """重复 start 不会创建多个任务。"""

        async def _test():
            tracker = ProgressTracker()
            listener = ComfyUIWebSocketListener(
                "ws://127.0.0.1:8188/ws",
                tracker,
            )
            await listener.start()
            task1 = listener._task
            await listener.start()
            task2 = listener._task
            self.assertIs(task1, task2)
            await listener.stop()

        asyncio.run(_test())

    def test_update_url(self) -> None:
        """update_url 更新 WebSocket URL。"""

        async def _test():
            tracker = ProgressTracker()
            listener = ComfyUIWebSocketListener(
                "ws://127.0.0.1:8188/ws",
                tracker,
            )
            self.assertEqual(listener._ws_url, "ws://127.0.0.1:8188/ws")
            await listener.update_url("ws://192.168.1.100:8188/ws")
            self.assertEqual(listener._ws_url, "ws://192.168.1.100:8188/ws")

        asyncio.run(_test())


# ──────────────────────────────────────────────────────────────────
# SSE 生成器测试
# ──────────────────────────────────────────────────────────────────


class SSEGeneratorTests(unittest.TestCase):
    """SSE 进度推送生成器测试。"""

    def test_yields_current_state_first(self) -> None:
        """SSE 首先推送当前状态。"""

        async def _test():
            tracker = ProgressTracker()
            tracker.update("prompt-1", {"type": "execution_start", "data": {}})
            gen = sse_progress_generator(tracker, "prompt-1", timeout_seconds=0.5)
            events = []
            async for event in gen:
                events.append(event)
                break  # 只取第一个事件
            self.assertTrue(events[0].startswith("data: "))
            data = json.loads(events[0][6:].strip())
            self.assertEqual(data["prompt_id"], "prompt-1")

        asyncio.run(_test())

    def test_stops_on_completion(self) -> None:
        """任务完成时 SSE 停止推送。"""

        async def _test():
            tracker = ProgressTracker()
            # 先设置为 running
            tracker.update("prompt-1", {"type": "execution_start", "data": {}})
            gen = sse_progress_generator(tracker, "prompt-1", timeout_seconds=2.0)
            events = []
            async for event in gen:
                events.append(event)
                data = json.loads(event[6:].strip())
                if data.get("status") == "completed":
                    break
                # 模拟收到完成事件
                tracker.update("prompt-1", {
                    "type": "execution_success",
                    "data": {},
                })
            # 最后一个事件应该是完成状态
            last_data = json.loads(events[-1][6:].strip())
            self.assertEqual(last_data["status"], "completed")

        asyncio.run(_test())

    def test_timeout_yields_timeout_event(self) -> None:
        """超时后推送 timeout 事件。"""

        async def _test():
            tracker = ProgressTracker()
            gen = sse_progress_generator(tracker, "prompt-1", timeout_seconds=0.1)
            events = []
            async for event in gen:
                events.append(event)
            last_data = json.loads(events[-1][6:].strip())
            self.assertEqual(last_data["status"], "timeout")

        asyncio.run(_test())


# ──────────────────────────────────────────────────────────────────
# 测试基类（API 集成测试）
# ──────────────────────────────────────────────────────────────────


class _ProgressTestBase(unittest.TestCase):
    """进度 API 测试基类。"""

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
        response = self.client.post("/api/projects", json={"name": "进度测试项目"})
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
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]
        prompt_id = "comfyui-prompt-test"
        self.mock_comfyui.submit_prompt.return_value = {
            "prompt_id": prompt_id,
            "number": 1,
            "node_errors": {},
        }
        # 直接调用函数（绕过 API 端点的闭包引用）
        result = submit_task_to_comfyui(
            self.manager, self.mock_comfyui, task_id, attempt_id
        )
        self.assertTrue(result["submitted"])
        return task_id, attempt_id, prompt_id

    def _setup_running_batch_with_tasks(self, page_count: int = 1) -> tuple[str, str, list[dict]]:
        """创建项目 → 草稿 → 批次 → running → 任务。"""
        project_id, _, _, _ = self._setup_full_project(page_count=page_count)
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
        return project_id, batch_id, tasks

    def _claim_task(self) -> dict:
        """领取一个任务。"""
        response = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "test-worker"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["claim"]


# ──────────────────────────────────────────────────────────────────
# 历史轮询测试
# ──────────────────────────────────────────────────────────────────


class PollHistoryTests(_ProgressTestBase):
    """poll_comfyui_history_for_attempt 测试。"""

    def test_poll_success_marks_completed(self) -> None:
        """历史中状态为 success 时标记 attempt 完成。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {"node-1": {"images": [{"filename": "out.png"}]}},
            },
        }
        result = poll_comfyui_history_for_attempt(
            self.manager, self.mock_comfyui, attempt_id
        )
        self.assertIsNotNone(result)
        self.assertTrue(result["completed"])
        # 验证 attempt 状态已更新
        response = self.client.get(f"/api/attempts/{attempt_id}")
        self.assertEqual(response.json()["attempt"]["status"], "completed")

    def test_poll_error_marks_failed(self) -> None:
        """历史中状态为 error 时标记 attempt 失败。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {
                    "status_str": "error",
                    "completed": {"error": "Execution error"},
                },
                "outputs": {},
            },
        }
        result = poll_comfyui_history_for_attempt(
            self.manager, self.mock_comfyui, attempt_id
        )
        self.assertIsNotNone(result)
        self.assertFalse(result["completed"])
        response = self.client.get(f"/api/attempts/{attempt_id}")
        self.assertEqual(response.json()["attempt"]["status"], "failed")

    def test_poll_not_found_returns_none(self) -> None:
        """历史中不存在 prompt_id 时返回 None。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.return_value = {}
        result = poll_comfyui_history_for_attempt(
            self.manager, self.mock_comfyui, attempt_id
        )
        self.assertIsNone(result)

    def test_poll_comfyui_error_returns_none(self) -> None:
        """ComfyUI 查询失败时返回 None。"""
        _, attempt_id, _ = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.side_effect = ComfyUIError("连接失败")
        result = poll_comfyui_history_for_attempt(
            self.manager, self.mock_comfyui, attempt_id
        )
        self.assertIsNone(result)

    def test_poll_no_prompt_id_returns_none(self) -> None:
        """attempt 没有 prompt_id 时返回 None。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]
        # 未提交，没有 prompt_id
        result = poll_comfyui_history_for_attempt(
            self.manager, self.mock_comfyui, attempt_id
        )
        self.assertIsNone(result)


# ──────────────────────────────────────────────────────────────────
# 重启恢复测试
# ──────────────────────────────────────────────────────────────────


class RecoverSubmittedTests(_ProgressTestBase):
    """recover_submitted_attempts 测试。"""

    def test_recover_completed(self) -> None:
        """重启后 ComfyUI 历史显示成功，标记完成。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {"status_str": "success"},
                "outputs": {},
            },
        }
        result = recover_submitted_attempts(self.manager, self.mock_comfyui)
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["recovered_completed"], 1)
        response = self.client.get(f"/api/attempts/{attempt_id}")
        self.assertEqual(response.json()["attempt"]["status"], "completed")

    def test_recover_failed(self) -> None:
        """重启后 ComfyUI 历史显示错误，标记失败。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.return_value = {
            prompt_id: {
                "status": {
                    "status_str": "error",
                    "completed": {"error": "OOM"},
                },
                "outputs": {},
            },
        }
        result = recover_submitted_attempts(self.manager, self.mock_comfyui)
        self.assertEqual(result["recovered_failed"], 1)
        response = self.client.get(f"/api/attempts/{attempt_id}")
        self.assertEqual(response.json()["attempt"]["status"], "failed")

    def test_recover_not_found_marks_unknown(self) -> None:
        """重启后 ComfyUI 历史中不存在，标记 unknown。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.return_value = {}
        result = recover_submitted_attempts(self.manager, self.mock_comfyui)
        self.assertEqual(result["marked_unknown"], 1)
        response = self.client.get(f"/api/attempts/{attempt_id}")
        self.assertEqual(response.json()["attempt"]["status"], "unknown")

    def test_recover_comfyui_error_marks_unknown(self) -> None:
        """重启后 ComfyUI 查询失败，标记 unknown。"""
        _, attempt_id, _ = self._setup_submitted_attempt()
        self.mock_comfyui.get_history.side_effect = ComfyUIError("连接失败")
        result = recover_submitted_attempts(self.manager, self.mock_comfyui)
        self.assertEqual(result["marked_unknown"], 1)
        response = self.client.get(f"/api/attempts/{attempt_id}")
        self.assertEqual(response.json()["attempt"]["status"], "unknown")

    def test_recover_no_submitted_attempts(self) -> None:
        """没有 submitted 状态的 attempt 时返回空。"""
        result = recover_submitted_attempts(self.manager, self.mock_comfyui)
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["recovered_completed"], 0)


# ──────────────────────────────────────────────────────────────────
# API 端点测试
# ──────────────────────────────────────────────────────────────────


class ProgressApiTests(_ProgressTestBase):
    """进度相关 API 端点测试。"""

    def test_get_progress_no_prompt_id(self) -> None:
        """attempt 没有 prompt_id 时返回 422。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]
        response = self.client.get(f"/api/attempts/{attempt_id}/progress")
        self.assertEqual(response.status_code, 422)

    def test_get_progress_returns_current(self) -> None:
        """获取 attempt 当前进度。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        # 手动更新进度跟踪器
        tracker: ProgressTracker = self.app.state.progress_tracker
        tracker.update(prompt_id, {"type": "execution_start", "data": {}})
        tracker.update(prompt_id, {
            "type": "progress",
            "data": {"value": 3, "max": 10},
        })
        response = self.client.get(f"/api/attempts/{attempt_id}/progress")
        self.assertEqual(response.status_code, 200)
        progress = response.json()["progress"]
        self.assertIsNotNone(progress)
        self.assertEqual(progress["progress_value"], 3)
        self.assertEqual(progress["progress_max"], 10)

    def test_get_progress_attempt_not_found(self) -> None:
        """attempt 不存在时返回 404。"""
        response = self.client.get("/api/attempts/nonexistent/progress")
        self.assertEqual(response.status_code, 404)

    @patch("backend.app.app_factory.poll_comfyui_history_for_attempt")
    def test_poll_progress_success(self, mock_poll: MagicMock) -> None:
        """轮询进度端点正常返回。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        mock_poll.return_value = {
            "prompt_id": prompt_id,
            "status": "success",
            "outputs": {},
            "completed": True,
        }
        response = self.client.post(f"/api/attempts/{attempt_id}/progress/poll")
        self.assertEqual(response.status_code, 200)
        result = response.json()["result"]
        self.assertTrue(result["completed"])

    @patch("backend.app.app_factory.poll_comfyui_history_for_attempt")
    def test_poll_progress_not_found(self, mock_poll: MagicMock) -> None:
        """轮询进度端点历史不存在时返回 404。"""
        _, attempt_id, _ = self._setup_submitted_attempt()
        mock_poll.return_value = None
        response = self.client.post(f"/api/attempts/{attempt_id}/progress/poll")
        self.assertEqual(response.status_code, 404)

    def test_poll_progress_attempt_not_found(self) -> None:
        """轮询进度端点 attempt 不存在时返回 404。"""
        response = self.client.post("/api/attempts/nonexistent/progress/poll")
        self.assertEqual(response.status_code, 404)

    @patch("backend.app.app_factory.recover_submitted_attempts")
    def test_recover_submitted_api(self, mock_recover: MagicMock) -> None:
        """恢复 submitted attempt API 端点。"""
        self._setup_submitted_attempt()
        mock_recover.return_value = {
            "checked": 1,
            "recovered_completed": 1,
            "recovered_failed": 0,
            "marked_unknown": 0,
        }
        response = self.client.post("/api/tasks/recover-submitted")
        self.assertEqual(response.status_code, 200)
        recovery = response.json()["recovery"]
        self.assertEqual(recovery["checked"], 1)
        self.assertEqual(recovery["recovered_completed"], 1)

    def test_sse_endpoint_returns_stream(self) -> None:
        """SSE 端点返回 text/event-stream。"""
        _, attempt_id, prompt_id = self._setup_submitted_attempt()
        # 手动更新进度跟踪器，使其有数据
        tracker: ProgressTracker = self.app.state.progress_tracker
        tracker.update(prompt_id, {"type": "execution_start", "data": {}})
        tracker.update(prompt_id, {
            "type": "execution_success",
            "data": {},
        })
        response = self.client.get(f"/api/attempts/{attempt_id}/progress/sse")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("content-type", ""),
            "text/event-stream; charset=utf-8",
        )
        # 应该能解析到至少一个 SSE 事件
        body = response.text
        self.assertIn("data: ", body)

    def test_sse_attempt_not_found(self) -> None:
        """SSE 端点 attempt 不存在时返回 404。"""
        response = self.client.get("/api/attempts/nonexistent/progress/sse")
        self.assertEqual(response.status_code, 404)

    def test_sse_no_prompt_id(self) -> None:
        """SSE 端点 attempt 没有 prompt_id 时返回 422。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]
        response = self.client.get(f"/api/attempts/{attempt_id}/progress/sse")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
