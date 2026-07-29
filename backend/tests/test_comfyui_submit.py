"""阶段 3.4 ComfyUI 提交测试。

测试范围：
- API JSON 构建（无插槽、有插槽、工作流版本不存在）
- 提交流程（正常提交、幂等性、超时处理、构建失败）
- 历史查询

使用 mock ComfyUIClient 避免依赖真实 ComfyUI 服务。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.comfyui_client import ComfyUIError
from backend.app.comfyui_submit import (
    build_api_json_for_item,
    check_comfyui_history,
    submit_task_to_comfyui,
)


# ──────────────────────────────────────────────────────────────────
# 测试基类
# ──────────────────────────────────────────────────────────────────


class _ComfyUISubmitBase(unittest.TestCase):
    """ComfyUI 提交测试基类。"""

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
        # 替换 ComfyUI 客户端为 mock
        self.mock_comfyui = MagicMock()
        self.app.state.comfyui_client = self.mock_comfyui

    def _setup_full_project(self, page_count: int = 1) -> tuple[str, list[str], str, str]:
        """创建完整项目结构。"""
        response = self.client.post("/api/projects", json={"name": "提交测试项目"})
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

    def _setup_running_batch_with_tasks(self, page_count: int = 1) -> tuple[str, str, list[dict]]:
        """创建项目 → 草稿 → 批次 → running → 任务，返回 (project_id, batch_id, tasks)。"""
        project_id, _, _, _ = self._setup_full_project(page_count=page_count)
        # 创建草稿
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json={"name": "测试草稿", "scope": "project"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        draft_id = response.json()["draft"]["id"]
        # 预览
        self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        # 提交批次
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit", json={"name": "测试批次"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        batch_id = response.json()["batch"]["id"]
        # 推进到 running
        self.client.patch(f"/api/batches/{batch_id}/status", json={"status": "running"})
        # 创建任务
        response = self.client.post(
            f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3}
        )
        self.assertEqual(response.status_code, 200, response.text)
        tasks = response.json()["tasks"]
        return project_id, batch_id, tasks

    def _claim_task(self) -> dict:
        """领取一个任务，返回 claim 信息。"""
        response = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "test-worker"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        claim = response.json()["claim"]
        self.assertIsNotNone(claim)
        return claim


# ──────────────────────────────────────────────────────────────────
# API JSON 构建测试
# ──────────────────────────────────────────────────────────────────


class BuildApiJsonTests(_ComfyUISubmitBase):
    def test_build_api_json_no_slots(self) -> None:
        """无插槽绑定时构建 API JSON。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task = tasks[0]
        api_json = build_api_json_for_item(self.manager, task["item"])
        self.assertIsInstance(api_json, dict)
        # API JSON 应该有节点结构
        self.assertTrue(len(api_json) > 0)

    def test_build_api_json_version_not_found(self) -> None:
        """工作流版本不存在时抛出 ValueError。"""
        item = {"workflow_version_id": "nonexistent", "workflow_id": "w1"}
        with self.assertRaises(ValueError) as ctx:
            build_api_json_for_item(self.manager, item)
        self.assertIn("工作流版本不存在", str(ctx.exception))

    def test_build_api_json_missing_version_id(self) -> None:
        """缺少 workflow_version_id 时抛出 ValueError。"""
        item = {"workflow_id": "w1"}
        with self.assertRaises(ValueError) as ctx:
            build_api_json_for_item(self.manager, item)
        self.assertIn("缺少 workflow_version_id", str(ctx.exception))


# ──────────────────────────────────────────────────────────────────
# 提交流程测试
# ──────────────────────────────────────────────────────────────────


class SubmitTaskTests(_ComfyUISubmitBase):
    def test_submit_success(self) -> None:
        """正常提交：ComfyUI 返回 prompt_id，attempt 标记为 submitted。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        # 领取任务
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        # Mock ComfyUI 返回
        self.mock_comfyui.submit_prompt.return_value = {
            "prompt_id": "comfyui-prompt-123",
            "number": 1,
            "node_errors": {},
        }

        result = submit_task_to_comfyui(
            self.manager, self.mock_comfyui, task_id, attempt_id
        )
        self.assertTrue(result["submitted"])
        self.assertEqual(result["prompt_id"], "comfyui-prompt-123")
        self.assertEqual(result["attempt_id"], attempt_id)

        # 验证 attempt 已标记为 submitted
        response = self.client.get(f"/api/attempts/{attempt_id}")
        attempt = response.json()["attempt"]
        self.assertEqual(attempt["status"], "submitted")
        self.assertEqual(attempt["prompt_id"], "comfyui-prompt-123")
        self.assertIsNotNone(attempt["api_json"])

    def test_submit_idempotent(self) -> None:
        """幂等：attempt 已有 prompt_id 时直接返回，不重复提交。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        # 第一次提交
        self.mock_comfyui.submit_prompt.return_value = {
            "prompt_id": "prompt-1", "node_errors": {},
        }
        submit_task_to_comfyui(self.manager, self.mock_comfyui, task_id, attempt_id)

        # 第二次提交（幂等）
        self.mock_comfyui.submit_prompt.reset_mock()
        result = submit_task_to_comfyui(
            self.manager, self.mock_comfyui, task_id, attempt_id
        )
        self.assertTrue(result["already_submitted"])
        self.assertEqual(result["prompt_id"], "prompt-1")
        # ComfyUI 不应被再次调用
        self.mock_comfyui.submit_prompt.assert_not_called()

    def test_submit_timeout_marks_unknown(self) -> None:
        """超时：标记 attempt 为 unknown，不重复提交。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        # Mock 超时错误
        self.mock_comfyui.submit_prompt.side_effect = ComfyUIError("ComfyUI 请求超时")

        result = submit_task_to_comfyui(
            self.manager, self.mock_comfyui, task_id, attempt_id
        )
        self.assertTrue(result["timeout"])
        self.assertIsNone(result["prompt_id"])

        # attempt 标记为 unknown
        response = self.client.get(f"/api/attempts/{attempt_id}")
        attempt = response.json()["attempt"]
        self.assertEqual(attempt["status"], "unknown")

    def test_submit_error_marks_failed(self) -> None:
        """非超时错误：标记 attempt 为 failed。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        # Mock 连接错误
        self.mock_comfyui.submit_prompt.side_effect = ComfyUIError("无法连接 ComfyUI")

        with self.assertRaises(ComfyUIError):
            submit_task_to_comfyui(
                self.manager, self.mock_comfyui, task_id, attempt_id
            )

        # attempt 标记为 failed
        response = self.client.get(f"/api/attempts/{attempt_id}")
        attempt = response.json()["attempt"]
        self.assertEqual(attempt["status"], "failed")
        self.assertIn("无法连接", attempt["error_message"])

    def test_submit_missing_prompt_id(self) -> None:
        """ComfyUI 响应缺少 prompt_id 时标记失败。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        self.mock_comfyui.submit_prompt.return_value = {"number": 1}

        with self.assertRaises(ValueError):
            submit_task_to_comfyui(
                self.manager, self.mock_comfyui, task_id, attempt_id
            )

        response = self.client.get(f"/api/attempts/{attempt_id}")
        self.assertEqual(response.json()["attempt"]["status"], "failed")

    def test_submit_with_node_errors(self) -> None:
        """ComfyUI 返回节点错误时仍标记为 submitted。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        self.mock_comfyui.submit_prompt.return_value = {
            "prompt_id": "prompt-with-errors",
            "node_errors": {"node_1": {"errors": ["invalid value"]}},
        }

        result = submit_task_to_comfyui(
            self.manager, self.mock_comfyui, task_id, attempt_id
        )
        self.assertTrue(result["submitted"])
        self.assertEqual(result["prompt_id"], "prompt-with-errors")
        self.assertIn("node_errors", result)

    def test_submit_attempt_not_found(self) -> None:
        """attempt 不存在时抛出 ValueError。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        with self.assertRaises(ValueError):
            submit_task_to_comfyui(
                self.manager, self.mock_comfyui, task_id, "nonexistent-attempt"
            )


# ──────────────────────────────────────────────────────────────────
# 历史查询测试
# ──────────────────────────────────────────────────────────────────


class CheckHistoryTests(_ComfyUISubmitBase):
    def test_check_history_found(self) -> None:
        """查询历史找到结果。"""
        self.mock_comfyui.get_history.return_value = {
            "prompt-123": {
                "status": {"status_str": "success"},
                "outputs": {"node_1": {"images": [{"filename": "output.png"}]}},
            }
        }
        result = check_comfyui_history(
            self.manager, self.mock_comfyui, "prompt-123"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["prompt_id"], "prompt-123")
        self.assertIn("outputs", result)

    def test_check_history_not_found(self) -> None:
        """查询历史未找到。"""
        self.mock_comfyui.get_history.return_value = {}
        result = check_comfyui_history(
            self.manager, self.mock_comfyui, "prompt-123"
        )
        self.assertIsNone(result)

    def test_check_history_error(self) -> None:
        """查询历史出错返回 None。"""
        self.mock_comfyui.get_history.side_effect = ComfyUIError("连接失败")
        result = check_comfyui_history(
            self.manager, self.mock_comfyui, "prompt-123"
        )
        self.assertIsNone(result)


# ──────────────────────────────────────────────────────────────────
# API 端点测试
# ──────────────────────────────────────────────────────────────────


class SubmitApiTests(_ComfyUISubmitBase):
    @patch("backend.app.app_factory.submit_task_to_comfyui")
    def test_submit_to_comfyui_api(self, mock_submit: MagicMock) -> None:
        """通过 API 端点提交任务。"""
        mock_submit.return_value = {
            "attempt_id": "att-1",
            "prompt_id": "api-prompt-1",
            "submitted": True,
        }
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        response = self.client.post(
            f"/api/tasks/{task_id}/attempts/{attempt_id}/submit-to-comfyui"
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["result"]
        self.assertTrue(result["submitted"])
        self.assertEqual(result["prompt_id"], "api-prompt-1")

    def test_preview_api_json(self) -> None:
        """预览任务的 API JSON。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        response = self.client.post(f"/api/tasks/{task_id}/preview-api-json")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("api_json", data)
        self.assertIsInstance(data["api_json"], dict)

    def test_preview_api_json_task_not_found(self) -> None:
        """预览不存在的任务返回 404。"""
        response = self.client.post("/api/tasks/nonexistent/preview-api-json")
        self.assertEqual(response.status_code, 404)

    def test_submit_to_comfyui_task_not_found(self) -> None:
        """提交不存在的任务返回 422。"""
        response = self.client.post(
            "/api/tasks/nonexistent/attempts/nonexistent/submit-to-comfyui"
        )
        self.assertEqual(response.status_code, 422)

    @patch("backend.app.app_factory.check_comfyui_history")
    def test_check_history_api(self, mock_history: MagicMock) -> None:
        """通过 API 查询历史。"""
        mock_history.return_value = {
            "prompt_id": "history-prompt",
            "status": {},
            "outputs": {},
        }
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        # 先通过函数直接提交（设置 prompt_id）
        self.mock_comfyui.submit_prompt.return_value = {
            "prompt_id": "history-prompt", "node_errors": {},
        }
        submit_task_to_comfyui(
            self.manager, self.mock_comfyui, task_id, attempt_id
        )

        # 查询历史
        response = self.client.post(f"/api/attempts/{attempt_id}/check-history")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["history"])

    def test_check_history_no_prompt_id(self) -> None:
        """查询历史但 attempt 无 prompt_id 返回 422。"""
        _, _, tasks = self._setup_running_batch_with_tasks(page_count=1)
        claim = self._claim_task()
        attempt_id = claim["attempt_id"]

        response = self.client.post(f"/api/attempts/{attempt_id}/check-history")
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
