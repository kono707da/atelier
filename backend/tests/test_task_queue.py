"""阶段 3.3 持久化任务队列测试。

测试范围：
- 任务创建（从批次展开、幂等性）
- 任务领取（原子性、批次必须 running、无任务时返回 null）
- Attempt 生命周期（submit → complete、submit → fail 重试、达上限失败）
- 任务状态控制（pause / resume / cancel / retry）
- 任务优先级
- 租约管理（手动释放、过期清理）
- 应用重启恢复（running → pending、submitted → unknown）
- 批次进度统计
- 事件查询
- 查询 API（任务详情、attempt 详情、事件列表）
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app


# ──────────────────────────────────────────────────────────────────
# API 集成测试基类
# ──────────────────────────────────────────────────────────────────


class _TaskQueueApiBase(unittest.TestCase):
    """任务队列 API 集成测试基类。"""

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

    def _create_project(self, name: str = "测试项目") -> str:
        response = self.client.post("/api/projects", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["project"]["id"]

    def _setup_full_project(self, page_count: int = 1) -> tuple[str, list[str], str, str]:
        """创建完整项目结构，返回 (project_id, shot_page_ids, workflow_id, version_id)。"""
        project_id = self._create_project("任务队列测试项目")
        # 章节
        response = self.client.post(
            f"/api/projects/{project_id}/chapters",
            json={"name": "第一章"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        chapter_id = response.json()["chapter"]["id"]
        # 大场景
        response = self.client.post(
            f"/api/chapters/{chapter_id}/large-scenes",
            json={"name": "大场景1", "scene_type": "content"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        large_scene_id = response.json()["large_scene"]["id"]
        # 小场景
        response = self.client.post(
            f"/api/large-scenes/{large_scene_id}/small-scenes",
            json={"name": "小场景1"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        small_scene_id = response.json()["small_scene"]["id"]
        # 场景页（可创建多个）
        shot_page_ids: list[str] = []
        for i in range(page_count):
            response = self.client.post(
                f"/api/small-scenes/{small_scene_id}/shot-pages",
                json={"title": f"场景页{i + 1}"},
            )
            self.assertEqual(response.status_code, 201, response.text)
            shot_page_ids.append(response.json()["shot_page"]["id"])
        # 工作流
        response = self.client.post("/api/workflows", json={"name": "工作流1"})
        self.assertEqual(response.status_code, 201, response.text)
        workflow_id = response.json()["workflow"]["id"]
        # 保存草稿并发布
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
        # 设置项目默认工作流
        response = self.client.post(
            f"/api/projects/{project_id}/default-workflow",
            json={"workflow_id": workflow_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return project_id, shot_page_ids, workflow_id, version_id

    def _create_draft_and_commit(
        self,
        project_id: str,
        *,
        name: str = "测试草稿",
        config: dict | None = None,
    ) -> str:
        """创建草稿、预览、提交批次，返回 batch_id。"""
        body: dict = {"name": name, "scope": "project"}
        if config is not None:
            body["config"] = config
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json=body,
        )
        self.assertEqual(response.status_code, 200, response.text)
        draft_id = response.json()["draft"]["id"]
        # 预览
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/preview",
            json={},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 提交
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit",
            json={"name": "测试批次"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["batch"]["id"]

    def _start_batch(self, batch_id: str) -> None:
        """将批次状态推进到 running。"""
        response = self.client.patch(
            f"/api/batches/{batch_id}/status",
            json={"status": "running"},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _setup_running_batch(self, page_count: int = 1) -> tuple[str, str]:
        """完整流程：创建项目 → 草稿 → 批次 → running，返回 (project_id, batch_id)。"""
        project_id, _, _, _ = self._setup_full_project(page_count=page_count)
        batch_id = self._create_draft_and_commit(project_id)
        self._start_batch(batch_id)
        return project_id, batch_id


# ──────────────────────────────────────────────────────────────────
# 任务创建测试
# ──────────────────────────────────────────────────────────────────


class TaskCreationTests(_TaskQueueApiBase):
    def test_create_tasks_from_batch(self) -> None:
        """从批次创建任务，数量等于跑图项数量。"""
        _, batch_id = self._setup_running_batch(page_count=3)
        response = self.client.post(
            f"/api/batches/{batch_id}/tasks",
            json={"max_attempts": 3},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["count"], 3)
        self.assertEqual(len(data["tasks"]), 3)
        for task in data["tasks"]:
            self.assertEqual(task["status"], "pending")
            self.assertEqual(task["max_attempts"], 3)
            self.assertEqual(task["attempt_count"], 0)
            self.assertIn("item", task)

    def test_create_tasks_idempotent(self) -> None:
        """重复创建任务返回相同列表（幂等）。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        r1 = self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        self.assertEqual(r1.status_code, 200)
        r2 = self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        self.assertEqual(r2.status_code, 200)
        ids1 = [t["id"] for t in r1.json()["tasks"]]
        ids2 = [t["id"] for t in r2.json()["tasks"]]
        self.assertEqual(ids1, ids2)

    def test_create_tasks_batch_not_found(self) -> None:
        """批次不存在时返回 422。"""
        response = self.client.post(
            "/api/batches/nonexistent/tasks",
            json={"max_attempts": 3},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_tasks_invalid_max_attempts(self) -> None:
        """max_attempts 超范围返回 422。"""
        _, batch_id = self._setup_running_batch()
        response = self.client.post(
            f"/api/batches/{batch_id}/tasks",
            json={"max_attempts": 0},
        )
        self.assertEqual(response.status_code, 422)


# ──────────────────────────────────────────────────────────────────
# 任务领取测试
# ──────────────────────────────────────────────────────────────────


class TaskClaimTests(_TaskQueueApiBase):
    def test_claim_returns_task_and_attempt(self) -> None:
        """领取任务返回 task + attempt + lease。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        # 先创建任务
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 领取
        response = self.client.post(
            "/api/tasks/claim",
            json={"lease_holder": "worker-1", "lease_seconds": 60},
        )
        self.assertEqual(response.status_code, 200, response.text)
        claim = response.json()["claim"]
        self.assertIsNotNone(claim)
        self.assertEqual(claim["batch_id"], batch_id)
        self.assertTrue(claim["task_id"])
        self.assertTrue(claim["attempt_id"])
        self.assertEqual(claim["attempt_number"], 1)
        self.assertTrue(claim["lease_id"])
        self.assertTrue(claim["lease_expires_at"])
        self.assertEqual(claim["max_attempts"], 3)
        self.assertIn("item", claim)

    def test_claim_no_tasks_when_batch_not_running(self) -> None:
        """批次未 running 时无可领取任务。"""
        project_id, _, _, _ = self._setup_full_project()
        batch_id = self._create_draft_and_commit(project_id)
        # 批次状态为 pending，未推进到 running
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        response = self.client.post(
            "/api/tasks/claim",
            json={"lease_holder": "worker-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["claim"])

    def test_claim_no_tasks_when_all_claimed(self) -> None:
        """所有任务领取完后返回 null。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 领取唯一任务
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "worker-1"})
        self.assertIsNotNone(r.json()["claim"])
        # 再次领取返回 null
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "worker-1"})
        self.assertIsNone(r.json()["claim"])

    def test_claim_batch_scoped(self) -> None:
        """指定 batch_id 只领取该批次的任务。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 用其他 batch_id 领取，应返回 null
        response = self.client.post(
            "/api/tasks/claim",
            json={"lease_holder": "worker-1", "batch_id": "nonexistent"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["claim"])

    def test_claim_batch_multiple(self) -> None:
        """批量领取多个任务。"""
        _, batch_id = self._setup_running_batch(page_count=3)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        response = self.client.post(
            "/api/tasks/claim-batch",
            json={"lease_holder": "worker-1", "count": 2},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(len(data["claims"]), 2)
        # 第三次领取只剩 1 个
        response = self.client.post(
            "/api/tasks/claim-batch",
            json={"lease_holder": "worker-1", "count": 5},
        )
        self.assertEqual(response.json()["count"], 1)

    def test_claim_order_by_sort_key(self) -> None:
        """任务按 sort_key 顺序领取。"""
        _, batch_id = self._setup_running_batch(page_count=3)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        sort_keys: list[str] = []
        for _ in range(3):
            r = self.client.post("/api/tasks/claim", json={"lease_holder": "w"})
            sort_keys.append(r.json()["claim"]["sort_key"])
        self.assertEqual(sort_keys, sorted(sort_keys))


# ──────────────────────────────────────────────────────────────────
# Attempt 生命周期测试
# ──────────────────────────────────────────────────────────────────


class AttemptLifecycleTests(_TaskQueueApiBase):
    def test_submit_and_complete(self) -> None:
        """提交 → 完成：任务状态变为 completed。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "worker-1"}
        ).json()["claim"]
        attempt_id = claim["attempt_id"]
        task_id = claim["task_id"]

        # 标记已提交
        r = self.client.post(
            f"/api/attempts/{attempt_id}/submit",
            json={"prompt_id": "prompt-123", "api_json": "{}"},
        )
        self.assertEqual(r.status_code, 200)
        attempt = r.json()["attempt"]
        self.assertEqual(attempt["status"], "submitted")
        self.assertEqual(attempt["prompt_id"], "prompt-123")

        # 标记完成
        r = self.client.post(f"/api/attempts/{attempt_id}/complete")
        self.assertEqual(r.status_code, 200)
        attempt = r.json()["attempt"]
        self.assertEqual(attempt["status"], "completed")

        # 任务状态变为 completed
        r = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(r.json()["task"]["status"], "completed")

    def test_submit_and_fail_retry(self) -> None:
        """提交 → 失败：未达上限时任务变为 retrying。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "worker-1"}
        ).json()["claim"]
        attempt_id = claim["attempt_id"]
        task_id = claim["task_id"]

        # 标记已提交
        self.client.post(
            f"/api/attempts/{attempt_id}/submit",
            json={"prompt_id": "prompt-1"},
        )
        # 标记失败
        r = self.client.post(
            f"/api/attempts/{attempt_id}/fail",
            json={"error_message": "ComfyUI 超时", "error_type": "timeout"},
        )
        self.assertEqual(r.status_code, 200)
        attempt = r.json()["attempt"]
        self.assertEqual(attempt["status"], "failed")
        self.assertIn("超时", attempt["error_message"])

        # 任务状态变为 retrying
        r = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(r.json()["task"]["status"], "retrying")
        self.assertEqual(r.json()["task"]["attempt_count"], 1)

    def test_fail_reaches_max_attempts(self) -> None:
        """达到最大重试次数后任务变为 failed。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        # 设置 max_attempts=1，一次失败即终止
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 1})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "worker-1"}
        ).json()["claim"]
        attempt_id = claim["attempt_id"]
        task_id = claim["task_id"]

        self.client.post(
            f"/api/attempts/{attempt_id}/submit",
            json={"prompt_id": "prompt-1"},
        )
        r = self.client.post(
            f"/api/attempts/{attempt_id}/fail",
            json={"error_message": "致命错误", "error_type": "fatal"},
        )
        self.assertEqual(r.status_code, 200)

        # 任务状态变为 failed
        r = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(r.json()["task"]["status"], "failed")

    def test_retry_creates_new_attempt(self) -> None:
        """重试后创建新 attempt，旧 attempt 保留。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 第一次领取并失败
        claim1 = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.client.post(
            f"/api/attempts/{claim1['attempt_id']}/submit",
            json={"prompt_id": "p1"},
        )
        self.client.post(
            f"/api/attempts/{claim1['attempt_id']}/fail",
            json={"error_message": "失败1"},
        )
        # 第二次领取（retrying → running）
        claim2 = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.assertEqual(claim2["attempt_number"], 2)
        self.assertNotEqual(claim1["attempt_id"], claim2["attempt_id"])
        self.assertEqual(claim2["task_id"], claim1["task_id"])

        # 旧 attempt 仍在列表中
        r = self.client.get(f"/api/tasks/{claim1['task_id']}/attempts")
        attempts = r.json()["attempts"]
        self.assertEqual(len(attempts), 2)
        # 按 attempt_number 倒序
        self.assertEqual(attempts[0]["attempt_number"], 2)
        self.assertEqual(attempts[1]["attempt_number"], 1)

    def test_mark_attempt_unknown(self) -> None:
        """标记 attempt 为 unknown 状态。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        r = self.client.post(
            f"/api/attempts/{claim['attempt_id']}/unknown",
            json={"reason": "重启后状态未知"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["attempt"]["status"], "unknown")

    def test_attempt_not_found(self) -> None:
        """attempt 不存在返回 404。"""
        r = self.client.post(
            "/api/attempts/nonexistent/submit",
            json={"prompt_id": "p1"},
        )
        self.assertEqual(r.status_code, 404)


# ──────────────────────────────────────────────────────────────────
# 任务状态控制测试
# ──────────────────────────────────────────────────────────────────


class TaskControlTests(_TaskQueueApiBase):
    def test_pause_and_resume(self) -> None:
        """暂停后恢复任务。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 获取任务 ID
        task_id = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"][0]["id"]

        # 暂停
        r = self.client.patch(f"/api/tasks/{task_id}", json={"action": "pause"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["task"]["status"], "paused")

        # 暂停状态不可领取
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "w"})
        self.assertIsNone(r.json()["claim"])

        # 恢复
        r = self.client.patch(f"/api/tasks/{task_id}", json={"action": "resume"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["task"]["status"], "pending")

        # 恢复后可领取
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "w"})
        self.assertIsNotNone(r.json()["claim"])

    def test_cancel(self) -> None:
        """取消任务。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        task_id = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"][0]["id"]

        r = self.client.patch(f"/api/tasks/{task_id}", json={"action": "cancel"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["task"]["status"], "cancelled")

        # 取消后不可领取
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "w"})
        self.assertIsNone(r.json()["claim"])

    def test_retry_failed_task(self) -> None:
        """手动重试 failed 任务。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 1})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.client.post(
            f"/api/attempts/{claim['attempt_id']}/fail",
            json={"error_message": "失败"},
        )
        # 任务状态为 failed
        task_id = claim["task_id"]
        self.assertEqual(
            self.client.get(f"/api/tasks/{task_id}").json()["task"]["status"],
            "failed",
        )
        # 手动重试
        r = self.client.patch(f"/api/tasks/{task_id}", json={"action": "retry"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["task"]["status"], "pending")

    def test_pause_running_task_not_allowed(self) -> None:
        """running 状态的任务不能暂停（只允许 pending/retrying）。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        r = self.client.patch(
            f"/api/tasks/{claim['task_id']}", json={"action": "pause"}
        )
        self.assertEqual(r.status_code, 422)

    def test_invalid_action(self) -> None:
        """无效 action 返回 422。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        task_id = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"][0]["id"]
        r = self.client.patch(f"/api/tasks/{task_id}", json={"action": "invalid"})
        self.assertEqual(r.status_code, 422)


# ──────────────────────────────────────────────────────────────────
# 任务优先级测试
# ──────────────────────────────────────────────────────────────────


class TaskPriorityTests(_TaskQueueApiBase):
    def test_set_priority(self) -> None:
        """设置任务优先级。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        tasks = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"]
        # 给第二个任务设置高优先级
        r = self.client.patch(
            f"/api/tasks/{tasks[1]['id']}/priority",
            json={"priority": 100},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["task"]["priority"], 100)

    def test_high_priority_claimed_first(self) -> None:
        """高优先级任务先被领取。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        tasks = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"]
        # 第二个任务设置高优先级
        self.client.patch(
            f"/api/tasks/{tasks[1]['id']}/priority",
            json={"priority": 100},
        )
        # 领取应返回高优先级任务
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.assertEqual(claim["task_id"], tasks[1]["id"])

    def test_priority_not_found(self) -> None:
        """任务不存在返回 404。"""
        r = self.client.patch(
            "/api/tasks/nonexistent/priority",
            json={"priority": 10},
        )
        self.assertEqual(r.status_code, 404)


# ──────────────────────────────────────────────────────────────────
# 租约管理测试
# ──────────────────────────────────────────────────────────────────


class LeaseTests(_TaskQueueApiBase):
    def test_release_lease(self) -> None:
        """手动释放租约。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        r = self.client.post(f"/api/leases/{claim['lease_id']}/release")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["released"])

    def test_release_already_released(self) -> None:
        """重复释放返回 404。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.client.post(f"/api/leases/{claim['lease_id']}/release")
        r = self.client.post(f"/api/leases/{claim['lease_id']}/release")
        self.assertEqual(r.status_code, 404)

    def test_expire_stale_leases(self) -> None:
        """过期超时租约将任务重置为 pending。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 用很短的租约时间领取
        claim = self.client.post(
            "/api/tasks/claim",
            json={"lease_holder": "w", "lease_seconds": 10},
        ).json()["claim"]
        task_id = claim["task_id"]

        # 手动将租约过期时间设为过去
        from datetime import datetime, timezone
        past = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                "UPDATE task_leases SET expires_at = ? WHERE id = ?",
                (past, claim["lease_id"]),
            )

        # 过期清理
        r = self.client.post("/api/tasks/expire-stale-leases")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["expired_count"], 1)

        # 任务被重置为 pending
        r = self.client.get(f"/api/tasks/{task_id}")
        self.assertEqual(r.json()["task"]["status"], "pending")

        # 可重新领取
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "w"})
        self.assertIsNotNone(r.json()["claim"])


# ──────────────────────────────────────────────────────────────────
# 应用重启恢复测试
# ──────────────────────────────────────────────────────────────────


class RecoveryTests(_TaskQueueApiBase):
    def test_recover_running_tasks(self) -> None:
        """重启恢复：running 任务重置为 pending。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 领取两个任务使其变为 running
        c1 = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        c2 = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]

        # 模拟重启恢复
        r = self.client.post("/api/tasks/recover")
        self.assertEqual(r.status_code, 200)
        recovery = r.json()["recovery"]
        self.assertEqual(recovery["recovered_tasks"], 2)

        # 任务被重置为 pending
        for tid in (c1["task_id"], c2["task_id"]):
            r = self.client.get(f"/api/tasks/{tid}")
            self.assertEqual(r.json()["task"]["status"], "pending")

    def test_recover_submitted_attempts_marked_unknown(self) -> None:
        """重启恢复：submitted attempt 标记为 unknown。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        # 标记为已提交
        self.client.post(
            f"/api/attempts/{claim['attempt_id']}/submit",
            json={"prompt_id": "p1"},
        )

        # 模拟重启恢复
        r = self.client.post("/api/tasks/recover")
        recovery = r.json()["recovery"]
        self.assertGreaterEqual(recovery["unknown_attempts"], 1)

        # attempt 标记为 unknown
        r = self.client.get(f"/api/attempts/{claim['attempt_id']}")
        self.assertEqual(r.json()["attempt"]["status"], "unknown")


# ──────────────────────────────────────────────────────────────────
# 批次进度测试
# ──────────────────────────────────────────────────────────────────


class BatchProgressTests(_TaskQueueApiBase):
    def test_progress_empty_batch(self) -> None:
        """无任务的批次进度为 0。"""
        project_id, _, _, _ = self._setup_full_project()
        batch_id = self._create_draft_and_commit(project_id)
        r = self.client.get(f"/api/batches/{batch_id}/progress")
        self.assertEqual(r.status_code, 200)
        progress = r.json()["progress"]
        self.assertEqual(progress["total"], 0)
        self.assertEqual(progress["progress_percent"], 0)

    def test_progress_with_tasks(self) -> None:
        """有任务的批次进度统计正确。"""
        _, batch_id = self._setup_running_batch(page_count=3)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        r = self.client.get(f"/api/batches/{batch_id}/progress")
        progress = r.json()["progress"]
        self.assertEqual(progress["total"], 3)
        self.assertEqual(progress["pending"], 3)
        self.assertEqual(progress["completed"], 0)
        self.assertEqual(progress["progress_percent"], 0)

    def test_progress_after_completion(self) -> None:
        """完成任务后进度更新。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 领取并完成一个
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.client.post(
            f"/api/attempts/{claim['attempt_id']}/submit",
            json={"prompt_id": "p1"},
        )
        self.client.post(f"/api/attempts/{claim['attempt_id']}/complete")

        r = self.client.get(f"/api/batches/{batch_id}/progress")
        progress = r.json()["progress"]
        self.assertEqual(progress["total"], 2)
        self.assertEqual(progress["completed"], 1)
        self.assertEqual(progress["pending"], 1)
        self.assertEqual(progress["progress_percent"], 50.0)

    def test_progress_batch_not_found(self) -> None:
        """批次不存在返回 404。"""
        r = self.client.get("/api/batches/nonexistent/progress")
        self.assertEqual(r.status_code, 404)


# ──────────────────────────────────────────────────────────────────
# 事件查询测试
# ──────────────────────────────────────────────────────────────────


class EventTests(_TaskQueueApiBase):
    def test_events_created_on_lifecycle(self) -> None:
        """任务生命周期产生事件。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        task_id = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"][0]["id"]

        # 初始应有 created 事件
        r = self.client.get(f"/api/tasks/{task_id}/events")
        events = r.json()["events"]
        event_types = [e["event_type"] for e in events]
        self.assertIn("created", event_types)

    def test_events_leased_and_completed(self) -> None:
        """领取和完成产生事件。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.client.post(
            f"/api/attempts/{claim['attempt_id']}/submit",
            json={"prompt_id": "p1"},
        )
        self.client.post(f"/api/attempts/{claim['attempt_id']}/complete")

        r = self.client.get(f"/api/tasks/{claim['task_id']}/events")
        event_types = [e["event_type"] for e in r.json()["events"]]
        self.assertIn("leased", event_types)
        self.assertIn("submitted", event_types)
        self.assertIn("completed", event_types)

    def test_events_filter_by_type(self) -> None:
        """按事件类型筛选。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]

        r = self.client.get(
            f"/api/tasks/{claim['task_id']}/events",
            params={"event_type": "leased"},
        )
        events = r.json()["events"]
        self.assertTrue(all(e["event_type"] == "leased" for e in events))
        self.assertGreaterEqual(len(events), 1)


# ──────────────────────────────────────────────────────────────────
# 查询 API 测试
# ──────────────────────────────────────────────────────────────────


class QueryTests(_TaskQueueApiBase):
    def test_list_tasks_with_status_filter(self) -> None:
        """按状态筛选任务列表。"""
        _, batch_id = self._setup_running_batch(page_count=3)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        # 领取一个变为 running
        self.client.post("/api/tasks/claim", json={"lease_holder": "w"})

        # 筛选 pending
        r = self.client.get(
            f"/api/batches/{batch_id}/tasks",
            params={"task_status": "pending"},
        )
        self.assertEqual(r.status_code, 200)
        tasks = r.json()["tasks"]
        self.assertEqual(len(tasks), 2)
        self.assertTrue(all(t["status"] == "pending" for t in tasks))

    def test_list_tasks_invalid_status(self) -> None:
        """无效状态返回 422。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        r = self.client.get(
            f"/api/batches/{batch_id}/tasks",
            params={"task_status": "invalid"},
        )
        self.assertEqual(r.status_code, 422)

    def test_get_task_not_found(self) -> None:
        """任务不存在返回 404。"""
        r = self.client.get("/api/tasks/nonexistent")
        self.assertEqual(r.status_code, 404)

    def test_get_task_without_item(self) -> None:
        """获取任务不包含 item 快照。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        task_id = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"][0]["id"]
        r = self.client.get(f"/api/tasks/{task_id}", params={"include_item": False})
        task = r.json()["task"]
        self.assertNotIn("item", task)

    def test_get_attempt_detail(self) -> None:
        """获取 attempt 详情。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        claim = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        r = self.client.get(f"/api/attempts/{claim['attempt_id']}")
        self.assertEqual(r.status_code, 200)
        attempt = r.json()["attempt"]
        self.assertEqual(attempt["id"], claim["attempt_id"])
        self.assertEqual(attempt["status"], "running")
        self.assertEqual(attempt["attempt_number"], 1)

    def test_get_attempt_not_found(self) -> None:
        """attempt 不存在返回 404。"""
        r = self.client.get("/api/attempts/nonexistent")
        self.assertEqual(r.status_code, 404)


# ──────────────────────────────────────────────────────────────────
# 完整端到端流程测试
# ──────────────────────────────────────────────────────────────────


class FullFlowTests(_TaskQueueApiBase):
    def test_full_flow_create_claim_complete(self) -> None:
        """完整流程：创建项目 → 草稿 → 批次 → running → 创建任务 → 领取 → 提交 → 完成。"""
        project_id, shot_page_ids, workflow_id, version_id = self._setup_full_project(page_count=2)
        batch_id = self._create_draft_and_commit(project_id)
        self._start_batch(batch_id)

        # 创建任务
        r = self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        self.assertEqual(r.json()["count"], 2)

        # 领取并完成所有任务
        for _ in range(2):
            claim = self.client.post(
                "/api/tasks/claim", json={"lease_holder": "worker-1"}
            ).json()["claim"]
            self.assertIsNotNone(claim)
            self.client.post(
                f"/api/attempts/{claim['attempt_id']}/submit",
                json={"prompt_id": f"prompt-{claim['task_id']}"},
            )
            self.client.post(f"/api/attempts/{claim['attempt_id']}/complete")

        # 进度应为 100%
        r = self.client.get(f"/api/batches/{batch_id}/progress")
        progress = r.json()["progress"]
        self.assertEqual(progress["completed"], 2)
        self.assertEqual(progress["progress_percent"], 100.0)

    def test_full_flow_with_retry_and_failure(self) -> None:
        """完整流程：创建 → 领取 → 失败 → 重试 → 失败 → 达上限失败。"""
        _, batch_id = self._setup_running_batch(page_count=1)
        # max_attempts=2
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 2})

        # 第一次领取并失败
        c1 = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.client.post(
            f"/api/attempts/{c1['attempt_id']}/fail",
            json={"error_message": "第一次失败", "error_type": "test"},
        )
        task_id = c1["task_id"]
        self.assertEqual(
            self.client.get(f"/api/tasks/{task_id}").json()["task"]["status"],
            "retrying",
        )

        # 第二次领取并失败（达到上限）
        c2 = self.client.post(
            "/api/tasks/claim", json={"lease_holder": "w"}
        ).json()["claim"]
        self.assertEqual(c2["attempt_number"], 2)
        self.client.post(
            f"/api/attempts/{c2['attempt_id']}/fail",
            json={"error_message": "第二次失败", "error_type": "test"},
        )
        self.assertEqual(
            self.client.get(f"/api/tasks/{task_id}").json()["task"]["status"],
            "failed",
        )

        # 两个 attempt 都在列表中
        r = self.client.get(f"/api/tasks/{task_id}/attempts")
        self.assertEqual(len(r.json()["attempts"]), 2)

    def test_full_flow_pause_cancel_resume(self) -> None:
        """完整流程：创建 → 暂停 → 取消 → 重试 → 完成。"""
        _, batch_id = self._setup_running_batch(page_count=2)
        self.client.post(f"/api/batches/{batch_id}/tasks", json={"max_attempts": 3})
        tasks = self.client.get(
            f"/api/batches/{batch_id}/tasks"
        ).json()["tasks"]

        # 暂停第一个
        self.client.patch(f"/api/tasks/{tasks[0]['id']}", json={"action": "pause"})
        # 取消第二个
        self.client.patch(f"/api/tasks/{tasks[1]['id']}", json={"action": "cancel"})

        # 此时无可领取任务
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "w"})
        self.assertIsNone(r.json()["claim"])

        # 恢复第一个
        self.client.patch(f"/api/tasks/{tasks[0]['id']}", json={"action": "resume"})
        # 重试第二个
        self.client.patch(f"/api/tasks/{tasks[1]['id']}", json={"action": "retry"})

        # 现在可领取
        r = self.client.post("/api/tasks/claim", json={"lease_holder": "w"})
        self.assertIsNotNone(r.json()["claim"])


if __name__ == "__main__":
    unittest.main()
