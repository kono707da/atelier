"""阶段 3.7 任务中心 API 测试。

测试范围：
- 跨批次任务列表（list_all_tasks）及多维度筛选
- 任务中心汇总统计（get_task_center_summary）
- 任务错误详情和关联对象跳转
- API 端点：/api/tasks、/api/task-center/summary、/api/tasks/{id}/error-detail
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.comfyui_submit import submit_task_to_comfyui
from backend.app.task_queue import (
    get_task_center_summary,
    list_all_tasks,
)


# ──────────────────────────────────────────────────────────────────
# 测试基类
# ──────────────────────────────────────────────────────────────────


class _TaskCenterTestBase(unittest.TestCase):
    """任务中心测试基类。"""

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

    def _setup_project_with_tasks(
        self, project_name: str = "任务中心测试项目", page_count: int = 2
    ) -> tuple[str, str, list[dict]]:
        """创建项目并生成任务，返回 (project_id, batch_id, tasks)。"""
        response = self.client.post("/api/projects", json={"name": project_name})
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
        for i in range(page_count):
            response = self.client.post(
                f"/api/small-scenes/{small_scene_id}/shot-pages",
                json={"title": f"场景页{i + 1}"},
            )
            self.assertEqual(response.status_code, 201, response.text)
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
        response = self.client.post(
            f"/api/projects/{project_id}/default-workflow",
            json={"workflow_id": workflow_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 创建草稿和批次
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json={"name": "测试草稿", "scope": "project"},
        )
        draft_id = response.json()["draft"]["id"]
        self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit", json={"name": "测试批次"}
        )
        batch_id = response.json()["batch"]["id"]
        self.client.patch(f"/api/batches/{batch_id}/status", json={"status": "running"})
        response = self.client.post(
            f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3}
        )
        tasks = response.json()["tasks"]
        return project_id, batch_id, tasks

    def _fail_task(self, task_id: str) -> None:
        """将任务标记为失败。"""
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "test-worker"}
        ).json()["claim"]
        if claim and claim.get("task_id") == task_id:
            attempt_id = claim["attempt_id"]
            self.client.post(f"/api/attempts/{attempt_id}/fail", json={
                "error_message": "测试错误信息",
                "error_type": "test_error",
            })


# ──────────────────────────────────────────────────────────────────
# list_all_tests 测试
# ──────────────────────────────────────────────────────────────────


class ListAllTasksTests(_TaskCenterTestBase):
    """list_all_tasks 函数测试。"""

    def test_list_all_empty(self) -> None:
        """空数据库返回空列表。"""
        tasks = list_all_tasks(self.manager)
        self.assertEqual(len(tasks), 0)

    def test_list_all_returns_tasks(self) -> None:
        """返回所有任务。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=2)
        all_tasks = list_all_tasks(self.manager)
        self.assertEqual(len(all_tasks), 2)

    def test_list_all_includes_project_id(self) -> None:
        """结果包含 project_id 字段。"""
        project_id, _, _ = self._setup_project_with_tasks(page_count=1)
        all_tasks = list_all_tasks(self.manager)
        self.assertEqual(len(all_tasks), 1)
        self.assertEqual(all_tasks[0]["project_id"], project_id)

    def test_filter_by_status(self) -> None:
        """按状态筛选。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=2)
        # 将第一个任务设为 paused
        self.client.patch(f"/api/tasks/{tasks[0]['id']}", json={"action": "pause"})
        pending = list_all_tasks(self.manager, status="pending")
        paused = list_all_tasks(self.manager, status="paused")
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(paused), 1)

    def test_filter_by_project(self) -> None:
        """按项目筛选。"""
        project_id1, _, _ = self._setup_project_with_tasks(
            project_name="项目A", page_count=1
        )
        project_id2, _, _ = self._setup_project_with_tasks(
            project_name="项目B", page_count=1
        )
        project1_tasks = list_all_tasks(self.manager, project_id=project_id1)
        project2_tasks = list_all_tasks(self.manager, project_id=project_id2)
        self.assertEqual(len(project1_tasks), 1)
        self.assertEqual(len(project2_tasks), 1)
        self.assertNotEqual(
            project1_tasks[0]["id"], project2_tasks[0]["id"]
        )

    def test_filter_by_batch(self) -> None:
        """按批次筛选。"""
        _, batch_id, _ = self._setup_project_with_tasks(page_count=2)
        tasks = list_all_tasks(self.manager, batch_id=batch_id)
        self.assertEqual(len(tasks), 2)
        for task in tasks:
            self.assertEqual(task["batch_id"], batch_id)

    def test_filter_has_error(self) -> None:
        """筛选有错误的任务。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=2)
        self._fail_task(tasks[0]["id"])
        with_errors = list_all_tasks(self.manager, has_error=True)
        without_errors = list_all_tasks(self.manager, has_error=False)
        self.assertEqual(len(with_errors), 1)
        self.assertEqual(len(without_errors), 1)

    def test_pagination(self) -> None:
        """分页测试。"""
        _, _, _ = self._setup_project_with_tasks(page_count=5)
        page1 = list_all_tasks(self.manager, limit=2, offset=0)
        page2 = list_all_tasks(self.manager, limit=2, offset=2)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)
        page1_ids = {t["id"] for t in page1}
        page2_ids = {t["id"] for t in page2}
        self.assertEqual(len(page1_ids & page2_ids), 0)


# ──────────────────────────────────────────────────────────────────
# get_task_center_summary 测试
# ──────────────────────────────────────────────────────────────────


class TaskCenterSummaryTests(_TaskCenterTestBase):
    """get_task_center_summary 函数测试。"""

    def test_summary_empty(self) -> None:
        """空数据库汇总。"""
        summary = get_task_center_summary(self.manager)
        self.assertEqual(summary["total_tasks"], 0)
        self.assertEqual(summary["error_tasks"], 0)

    def test_summary_with_tasks(self) -> None:
        """有任务时的汇总。"""
        _, _, _ = self._setup_project_with_tasks(page_count=3)
        summary = get_task_center_summary(self.manager)
        self.assertEqual(summary["total_tasks"], 3)
        self.assertEqual(summary["pending"], 3)
        self.assertEqual(summary["completed"], 0)

    def test_summary_with_failed_tasks(self) -> None:
        """有失败任务时的汇总。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=3)
        self._fail_task(tasks[0]["id"])
        summary = get_task_center_summary(self.manager)
        self.assertEqual(summary["total_tasks"], 3)
        self.assertGreater(summary["error_tasks"], 0)

    def test_summary_by_project(self) -> None:
        """按项目汇总。"""
        project_id1, _, _ = self._setup_project_with_tasks(
            project_name="项目A", page_count=2
        )
        project_id2, _, _ = self._setup_project_with_tasks(
            project_name="项目B", page_count=3
        )
        summary1 = get_task_center_summary(self.manager, project_id=project_id1)
        summary2 = get_task_center_summary(self.manager, project_id=project_id2)
        self.assertEqual(summary1["total_tasks"], 2)
        self.assertEqual(summary2["total_tasks"], 3)


# ──────────────────────────────────────────────────────────────────
# API 端点测试
# ──────────────────────────────────────────────────────────────────


class TaskCenterApiTests(_TaskCenterTestBase):
    """任务中心 API 端点测试。"""

    def test_list_all_tasks_api(self) -> None:
        """GET /api/tasks 列出所有任务。"""
        _, _, _ = self._setup_project_with_tasks(page_count=2)
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertIn("tasks", data)

    def test_list_all_tasks_api_with_status_filter(self) -> None:
        """GET /api/tasks?status=pending 按状态筛选。"""
        _, _, _ = self._setup_project_with_tasks(page_count=2)
        response = self.client.get("/api/tasks?status=pending")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

        response = self.client.get("/api/tasks?status=completed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_list_all_tasks_api_with_project_filter(self) -> None:
        """GET /api/tasks?project_id=xxx 按项目筛选。"""
        project_id, _, _ = self._setup_project_with_tasks(page_count=1)
        response = self.client.get(f"/api/tasks?project_id={project_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_list_all_tasks_api_with_error_filter(self) -> None:
        """GET /api/tasks?has_error=true 按错误筛选。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=2)
        self._fail_task(tasks[0]["id"])
        response = self.client.get("/api/tasks?has_error=true")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_list_all_tasks_api_empty(self) -> None:
        """空数据库列表。"""
        response = self.client.get("/api/tasks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)

    def test_task_center_summary_api(self) -> None:
        """GET /api/task-center/summary 汇总统计。"""
        _, _, _ = self._setup_project_with_tasks(page_count=3)
        response = self.client.get("/api/task-center/summary")
        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["total_tasks"], 3)
        self.assertEqual(summary["pending"], 3)

    def test_task_center_summary_api_with_project(self) -> None:
        """GET /api/task-center/summary?project_id=xxx 按项目汇总。"""
        project_id, _, _ = self._setup_project_with_tasks(page_count=2)
        response = self.client.get(f"/api/task-center/summary?project_id={project_id}")
        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["total_tasks"], 2)

    def test_task_error_detail_api(self) -> None:
        """GET /api/tasks/{task_id}/error-detail 错误详情。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        response = self.client.get(f"/api/tasks/{task_id}/error-detail")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("task", data)
        self.assertIn("attempts", data)
        self.assertIn("events", data)
        self.assertIn("batch", data)
        self.assertIn("related", data)
        # 关联对象应包含项目信息
        related = data["related"]
        self.assertIsNotNone(related["project_id"])
        self.assertIsNotNone(related["shot_page_id"])

    def test_task_error_detail_not_found(self) -> None:
        """获取不存在的任务错误详情返回 404。"""
        response = self.client.get("/api/tasks/nonexistent/error-detail")
        self.assertEqual(response.status_code, 404)

    def test_task_error_detail_with_failed_task(self) -> None:
        """失败任务的错误详情包含错误信息。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        self._fail_task(task_id)
        response = self.client.get(f"/api/tasks/{task_id}/error-detail")
        self.assertEqual(response.status_code, 200)
        task = response.json()["task"]
        self.assertIsNotNone(task.get("error_message"))
        attempts = response.json()["attempts"]
        self.assertGreater(len(attempts), 0)
        # 应该有失败的 attempt
        failed_attempts = [a for a in attempts if a.get("status") == "failed"]
        self.assertGreater(len(failed_attempts), 0)

    def test_task_center_has_existing_pause_resume(self) -> None:
        """任务中心支持暂停和恢复操作。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        # 暂停
        response = self.client.patch(f"/api/tasks/{task_id}", json={"action": "pause"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["status"], "paused")
        # 恢复
        response = self.client.patch(f"/api/tasks/{task_id}", json={"action": "resume"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["status"], "pending")

    def test_task_center_priority(self) -> None:
        """任务中心支持优先级设置。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        response = self.client.patch(
            f"/api/tasks/{task_id}/priority", json={"priority": 10}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["priority"], 10)

    def test_task_center_cancel(self) -> None:
        """任务中心支持取消操作。"""
        _, _, tasks = self._setup_project_with_tasks(page_count=1)
        task_id = tasks[0]["id"]
        response = self.client.patch(f"/api/tasks/{task_id}", json={"action": "cancel"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["status"], "cancelled")

    def test_task_center_recover(self) -> None:
        """任务中心支持状态恢复。"""
        response = self.client.post("/api/tasks/recover")
        self.assertEqual(response.status_code, 200)
        self.assertIn("recovery", response.json())

    def test_task_center_recover_submitted(self) -> None:
        """任务中心支持 submitted 状态恢复。"""
        response = self.client.post("/api/tasks/recover-submitted")
        self.assertEqual(response.status_code, 200)
        self.assertIn("recovery", response.json())


if __name__ == "__main__":
    unittest.main()
