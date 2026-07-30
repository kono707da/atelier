"""MOD-07 全局 /api/events SSE 测试。

测试范围：
- EventBus 基础：发布/订阅、事件 ID 递增、环形缓冲回放
- 类型过滤（按前缀匹配）
- Last-Event-ID 重连
- SSE 事件格式（id/event/data 三段）
- sse_events_generator 终止条件（max_events、timeout）
- 模块级 publish_event 便捷函数
- /api/events SSE 端点
- /api/events/stats 端点
- 跨模块事件发布（task、thumbnail、export、gallery 钩子）

验收要求：所有 SSE 测试必须设置终止条件（max_events 或 timeout）。
"""
from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.event_bus import (
    DEFAULT_REPLAY_BUFFER_SIZE,
    DEFAULT_SSE_TIMEOUT_SECONDS,
    EventBus,
    format_sse_event,
    get_global_bus,
    publish_event,
    set_global_bus,
    sse_events_generator,
)


# ──────────────────────────────────────────────────────────────────
# EventBus 单元测试
# ──────────────────────────────────────────────────────────────────


class EventBusBasicTests(unittest.IsolatedAsyncioTestCase):
    """EventBus 基础功能测试。"""

    async def asyncSetUp(self) -> None:
        self.bus = EventBus(replay_buffer_size=10)
        set_global_bus(self.bus)

    async def asyncTearDown(self) -> None:
        # 重置全局 bus，避免影响其他测试
        set_global_bus(EventBus())

    async def test_publish_assigns_incrementing_event_id(self) -> None:
        """发布事件后 event_id 单调递增。"""
        id1 = self.bus.publish("task.created", {"task_id": "t1"})
        id2 = self.bus.publish("task.completed", {"task_id": "t1"})
        id3 = self.bus.publish("thumbnail.completed", {"file_id": "f1"})
        self.assertEqual(id2, id1 + 1)
        self.assertEqual(id3, id2 + 1)

    async def test_subscribe_receives_published_events(self) -> None:
        """订阅后能收到新发布的事件。"""
        queue, missed = await self.bus.subscribe()
        self.assertEqual(missed, [])
        self.bus.publish("task.created", {"task_id": "t1"})
        record = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(record["event"], "task.created")
        self.assertEqual(record["data"]["task_id"], "t1")
        self.bus.unsubscribe(queue)

    async def test_publish_sync_from_sync_context(self) -> None:
        """publish_sync 可在同步上下文中调用。"""
        queue, _ = await self.bus.subscribe()
        # 在异步上下文中调用 publish_sync 也应正常工作
        event_id = self.bus.publish_sync("task.failed", {"task_id": "t1"})
        self.assertGreater(event_id, 0)
        record = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(record["event"], "task.failed")
        self.bus.unsubscribe(queue)

    async def test_replay_buffer_replays_missed_events(self) -> None:
        """订阅时根据 last_event_id 回放错过的事件。"""
        id1 = self.bus.publish("task.created", {"n": 1})
        id2 = self.bus.publish("task.created", {"n": 2})
        id3 = self.bus.publish("task.created", {"n": 3})

        # 用 last_event_id=id1 订阅，应收到 id2 和 id3
        queue, missed = await self.bus.subscribe(last_event_id=id1)
        missed_ids = [r["id"] for r in missed]
        self.assertIn(id2, missed_ids)
        self.assertIn(id3, missed_ids)
        self.assertNotIn(id1, missed_ids)
        self.bus.unsubscribe(queue)

    async def test_replay_buffer_reports_out_of_buffer(self) -> None:
        """last_event_id 超出缓冲区时返回 reconnect 提示。"""
        # 发布少量事件（使缓冲区非空）
        self.bus.publish("task.created", {"n": 1})
        # 用一个非常旧的 last_event_id 订阅（0 < 最旧 id 1）
        queue, missed = await self.bus.subscribe(last_event_id=0)
        # 应该有一个 reconnect 提示事件
        reconnect_events = [r for r in missed if r["event"] == "bus.reconnect"]
        self.assertEqual(len(reconnect_events), 1)
        self.assertTrue(reconnect_events[0]["data"]["missed"])
        self.bus.unsubscribe(queue)

    async def test_type_filter(self) -> None:
        """按类型前缀过滤事件。"""
        queue, _ = await self.bus.subscribe(types=["thumbnail"])
        self.bus.publish("task.created", {"task_id": "t1"})
        self.bus.publish("thumbnail.completed", {"file_id": "f1"})
        self.bus.publish("thumbnail.failed", {"file_id": "f2"})
        self.bus.publish("export.job_completed", {"job_id": "j1"})

        received: list[str] = []
        try:
            for _ in range(2):
                record = await asyncio.wait_for(queue.get(), timeout=1.0)
                received.append(record["event"])
        except asyncio.TimeoutError:
            pass
        self.assertEqual(set(received), {"thumbnail.completed", "thumbnail.failed"})
        self.bus.unsubscribe(queue)

    async def test_unsubscribe_stops_delivery(self) -> None:
        """取消订阅后不再收到事件。"""
        queue, _ = await self.bus.subscribe()
        self.bus.publish("task.created", {"n": 1})
        record = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(record["event"], "task.created")
        self.bus.unsubscribe(queue)
        self.bus.publish("task.created", {"n": 2})
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.5)

    async def test_stats(self) -> None:
        """stats 返回正确的统计信息。"""
        self.bus.publish("task.created", {"n": 1})
        self.bus.publish("task.created", {"n": 2})
        queue, _ = await self.bus.subscribe()
        stats = self.bus.stats()
        self.assertEqual(stats["buffered_events"], 2)
        self.assertEqual(stats["active_subscribers"], 1)
        self.assertEqual(stats["next_event_id"], 3)
        self.bus.unsubscribe(queue)

    async def test_replay_buffer_evicts_old_events(self) -> None:
        """环形缓冲满后丢弃最旧的事件。"""
        bus = EventBus(replay_buffer_size=3)
        set_global_bus(bus)
        # 发布 5 个事件，缓冲区只保留最后 3 个
        ids = [bus.publish("task.created", {"n": i}) for i in range(5)]
        queue, missed = await bus.subscribe(last_event_id=0)
        # 缓冲区最旧的是 ids[2]
        missed_ids = [r["id"] for r in missed if r["event"] != "bus.reconnect"]
        self.assertEqual(min(missed_ids), ids[2])
        self.assertEqual(max(missed_ids), ids[4])
        bus.unsubscribe(queue)
        # 恢复全局 bus
        set_global_bus(self.bus)


# ──────────────────────────────────────────────────────────────────
# SSE 格式测试
# ──────────────────────────────────────────────────────────────────


class SSEFormatTests(unittest.TestCase):
    """SSE 事件格式测试。"""

    def test_format_includes_id_event_data(self) -> None:
        """格式化的 SSE 事件包含 id、event、data 三段。"""
        result = format_sse_event(42, "task.created", {"task_id": "t1"})
        self.assertIn("id: 42", result)
        self.assertIn("event: task.created", result)
        self.assertIn('data: {"task_id": "t1"}', result)
        self.assertTrue(result.endswith("\n\n"))

    def test_format_includes_retry_when_provided(self) -> None:
        """提供 retry 时包含 retry 字段。"""
        result = format_sse_event(1, "task.created", {"x": 1}, retry=5000)
        self.assertIn("retry: 5000", result)

    def test_format_handles_non_serializable(self) -> None:
        """非 JSON 可序列化对象通过 default=str 处理。"""
        from datetime import datetime, timezone
        ts = datetime(2026, 7, 30, tzinfo=timezone.utc)
        result = format_sse_event(1, "test", {"ts": ts})
        self.assertIn("data:", result)


# ──────────────────────────────────────────────────────────────────
# SSE 生成器测试
# ──────────────────────────────────────────────────────────────────


class SSEGeneratorTests(unittest.IsolatedAsyncioTestCase):
    """sse_events_generator 测试。所有测试必须设置终止条件。"""

    async def asyncSetUp(self) -> None:
        self.bus = EventBus(replay_buffer_size=50)
        set_global_bus(self.bus)

    async def asyncTearDown(self) -> None:
        set_global_bus(EventBus())

    async def test_max_events_terminates_generator(self) -> None:
        """max_events 达到后生成器终止。"""
        # 先发布 3 个事件
        for i in range(3):
            self.bus.publish("task.created", {"n": i})

        # 用 last_event_id=0 触发回放，max_events=3 终止
        events: list[str] = []
        async for chunk in sse_events_generator(
            self.bus, last_event_id=0, max_events=3, timeout_seconds=2.0
        ):
            events.append(chunk)
            if len(events) > 10:
                break

        # 应该收到 3 个事件 + 1 个结束事件
        self.assertGreaterEqual(len(events), 3)
        # 最后一个应该是结束事件
        self.assertIn("bus.end", events[-1])

    async def test_timeout_terminates_generator(self) -> None:
        """超时后生成器发送结束事件并终止。"""
        events: list[str] = []
        async for chunk in sse_events_generator(
            self.bus, timeout_seconds=0.5, max_events=None
        ):
            events.append(chunk)
            if len(events) > 5:
                break

        # 应该至少有一个心跳或结束事件
        self.assertTrue(any("bus.end" in e for e in events) or any("heartbeat" in e for e in events))

    async def test_replay_via_generator(self) -> None:
        """通过生成器回放错过的事件。"""
        id1 = self.bus.publish("task.created", {"n": 1})
        id2 = self.bus.publish("task.created", {"n": 2})

        events: list[str] = []
        async for chunk in sse_events_generator(
            self.bus, last_event_id=id1, max_events=1, timeout_seconds=2.0
        ):
            events.append(chunk)
            if len(events) > 5:
                break

        # 应该回放 id2 的事件
        replayed = [e for e in events if f"id: {id2}" in e]
        self.assertEqual(len(replayed), 1)
        self.assertIn("task.created", replayed[0])


# ──────────────────────────────────────────────────────────────────
# 模块级 publish_event 测试
# ──────────────────────────────────────────────────────────────────


class PublishEventFunctionTests(unittest.IsolatedAsyncioTestCase):
    """模块级 publish_event 函数测试。"""

    async def asyncSetUp(self) -> None:
        self.bus = EventBus()
        set_global_bus(self.bus)

    async def asyncTearDown(self) -> None:
        set_global_bus(EventBus())

    async def test_publish_event_uses_global_bus(self) -> None:
        """publish_event 使用全局 bus。"""
        queue, _ = await self.bus.subscribe()
        event_id = publish_event("task.created", {"task_id": "t1"})
        self.assertGreater(event_id, 0)
        record = await asyncio.wait_for(queue.get(), timeout=1.0)
        self.assertEqual(record["event"], "task.created")
        self.bus.unsubscribe(queue)

    async def test_get_global_bus_auto_creates(self) -> None:
        """get_global_bus 在未设置时自动创建。"""
        # 重置全局 bus
        import backend.app.event_bus as eb
        eb._global_bus = None
        bus = get_global_bus()
        self.assertIsNotNone(bus)
        # 清理
        set_global_bus(EventBus())


# ──────────────────────────────────────────────────────────────────
# 跨模块事件钩子测试
# ──────────────────────────────────────────────────────────────────


class CrossModuleHookTests(unittest.TestCase):
    """验证各 worker 模块的事件发布钩子。

    这些测试通过直接检查 bus 的环形缓冲区验证事件已发布，
    避免复杂的异步订阅器设置。
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.bus = self.app.state.event_bus
        set_global_bus(self.bus)
        self.addCleanup(lambda: set_global_bus(EventBus()))
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager

    def _get_buffered_event_types(self) -> list[str]:
        """从 bus 的环形缓冲区获取已发布的事件类型列表。"""
        with self.bus._lock:
            return [r["event"] for r in self.bus._replay_buffer]

    def test_thumbnail_worker_publishes_events(self) -> None:
        """缩略图 worker 完成时发布 thumbnail.completed 事件。"""
        import io
        from PIL import Image
        from backend.app.output_receiver import create_file_record
        from backend.app.thumbnail_worker import run_thumbnail_worker_once

        # 创建图片文件
        img = Image.new("RGB", (100, 100), color=(128, 64, 192))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        import uuid as uuid_module
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
                "original_name": f"{file_id}.png",
                "mime_type": "image/png",
                "size_bytes": len(image_bytes),
                "content_hash": "hash-" + file_id[:8],
            },
        )
        # 创建缩略图任务
        from backend.app.output_receiver import create_thumbnail_jobs
        create_thumbnail_jobs(self.manager, file_id)

        # 执行 worker
        result = run_thumbnail_worker_once(self.manager, max_jobs=5)
        self.assertEqual(result["completed"], 2)  # 256 和 640 两级

        # 验证事件已发布到 bus 的缓冲区
        event_types = self._get_buffered_event_types()
        self.assertIn("thumbnail.completed", event_types)
        self.assertIn("thumbnail.batch_progress", event_types)

    def test_export_runner_publishes_events(self) -> None:
        """导出 runner 发布 export.job_started/item_progress/job_completed 事件。"""
        import io
        from PIL import Image
        from backend.app.output_receiver import create_file_record, create_image_instance
        from backend.app.export_runner import execute_export_job

        # 先创建项目（外键约束）
        project = self.manager.create_project(name="测试项目")
        project_id = project["id"]

        # 创建图片
        img = Image.new("RGB", (50, 50), color=(100, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        import uuid as uuid_module
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
                "original_name": f"{file_id}.png",
                "mime_type": "image/png",
                "size_bytes": len(image_bytes),
                "content_hash": "hash-" + file_id[:8],
            },
        )

        # 创建最终版本
        fv = self.manager.create_final_version(project_id=project_id, name="测试版本")
        fv_id = fv["id"]

        # 创建图片实例
        instance = create_image_instance(
            self.manager,
            project_id=project_id,
            shot_page_id="s1",
            task_id=None,
            attempt_id=None,
            file_id=file_id,
            node_id=None,
            workflow_version_id=None,
            prompt_id=None,
            width=50,
            height=50,
            img_format="PNG",
            seed=None,
            resolved_json=None,
            snapshot_json=None,
        )

        # 添加到最终版本
        self.manager.add_final_version_item(
            final_version_id=fv_id,
            image_instance_id=instance["id"],
            sort_order=1,
        )

        # 创建预设
        preset = self.manager.create_export_preset(
            name="测试预设",
            output_pattern="img_{index:03d}.png",
            format="original",
            copy_mode="copy",
            strip_metadata=False,
        )

        # 创建导出任务
        output_dir = str(Path(self._tmp.name) / "export_output")
        job = self.manager.create_export_job(
            final_version_id=fv_id,
            preset_id=preset["id"],
            output_dir=output_dir,
        )

        # 执行导出
        result = execute_export_job(self.manager, job["id"])
        self.assertEqual(result["status"], "completed")

        # 验证事件已发布
        event_types = self._get_buffered_event_types()
        self.assertIn("export.job_started", event_types)
        self.assertIn("export.item_progress", event_types)
        self.assertIn("export.job_completed", event_types)

    def test_task_queue_publishes_events(self) -> None:
        """任务队列 _record_event 发布 task.{event_type} 事件。"""
        # 先创建项目（外键约束）
        project = self.manager.create_project(name="测试项目")
        # 创建 batch 和 task（满足外键约束）
        from datetime import datetime, timezone
        import uuid as uuid_module
        batch_id = str(uuid_module.uuid4())
        task_id = str(uuid_module.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                """INSERT INTO batches(id, project_id, name, scope, config_json,
                   snapshot_json, item_count, blocking_count, warning_count,
                   status, revision, created_at, updated_at)
                   VALUES (?, ?, '测试批次', 'project', '{}', '{}', 0, 0, 0,
                   'pending', 1, ?, ?)""",
                (batch_id, project["id"], now, now),
            )
            conn.execute(
                """INSERT INTO tasks(id, batch_id, sort_key, item_snapshot_json,
                   status, priority, max_attempts, attempt_count, created_at, updated_at)
                   VALUES (?, ?, '1', '{}', 'pending', 0, 3, 0, ?, ?)""",
                (task_id, batch_id, now, now),
            )
            conn.commit()

        # 调用 _record_event 验证事件发布
        from backend.app.task_queue import _record_event
        with self.manager.connection() as conn:
            _record_event(
                conn,
                task_id=task_id,
                event_type="created",
                event_data={"task_id": task_id, "batch_id": batch_id},
            )
            conn.commit()

        # 验证事件已发布到 bus 的缓冲区
        event_types = self._get_buffered_event_types()
        self.assertIn("task.created", event_types)


# ──────────────────────────────────────────────────────────────────
# /api/events SSE 端点测试
# ──────────────────────────────────────────────────────────────────


class APIEventsSSETests(unittest.TestCase):
    """/api/events SSE 端点测试。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.bus = self.app.state.event_bus
        set_global_bus(self.bus)
        self.addCleanup(lambda: set_global_bus(EventBus()))
        self.client = TestClient(self.app)

    def test_events_stats_endpoint(self) -> None:
        """/api/events/stats 返回总线统计。"""
        self.bus.publish("task.created", {"n": 1})
        response = self.client.get("/api/events/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("bus", data)
        self.assertGreaterEqual(data["bus"]["next_event_id"], 2)

    def test_events_sse_with_max_events(self) -> None:
        """/api/events SSE 端点支持 max_events 终止条件。"""
        # 先发布一些事件
        for i in range(3):
            self.bus.publish("task.created", {"n": i})

        # 使用 max_events=2 终止，并用 Last-Event-ID=0 触发回放
        with self.client.stream(
            "GET",
            "/api/events",
            params={"max_events": 2, "timeout": 5},
            headers={"Last-Event-ID": "0"},
        ) as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/event-stream", response.headers.get("content-type", ""))
            chunks: list[str] = []
            for chunk in response.iter_text():
                chunks.append(chunk)
                if len(chunks) > 20:
                    break
            content = "".join(chunks)
            # 应该收到事件
            self.assertIn("event: task.created", content)
            self.assertIn("id:", content)

    def test_events_sse_with_type_filter(self) -> None:
        """/api/events SSE 端点支持 types 过滤。"""
        # 发布不同类型的事件
        self.bus.publish("task.created", {"n": 1})
        self.bus.publish("thumbnail.completed", {"n": 1})

        # 只订阅 thumbnail 类型，max_events=2（reconnect + thumbnail.completed），
        # 用 Last-Event-ID=0 触发回放
        with self.client.stream(
            "GET",
            "/api/events",
            params={"types": "thumbnail", "max_events": 2, "timeout": 5},
            headers={"Last-Event-ID": "0"},
        ) as response:
            self.assertEqual(response.status_code, 200)
            chunks: list[str] = []
            for chunk in response.iter_text():
                chunks.append(chunk)
                if len(chunks) > 20:
                    break
            content = "".join(chunks)
            # 应该收到 thumbnail 事件（reconnect 事件因类型过滤不会发送）
            self.assertIn("thumbnail.completed", content)
            # 不应该有 task 事件（除了可能的 bus.end）
            task_events = [
                line for line in content.split("\n")
                if line.startswith("event: task.")
            ]
            self.assertEqual(len(task_events), 0)

    def test_events_sse_last_event_id_header(self) -> None:
        """/api/events SSE 支持 Last-Event-ID 重连。"""
        # 发布 3 个事件
        id1 = self.bus.publish("task.created", {"n": 1})
        id2 = self.bus.publish("task.created", {"n": 2})
        id3 = self.bus.publish("task.created", {"n": 3})

        # 用 Last-Event-ID=id1 重连，应回放 id2 和 id3
        with self.client.stream(
            "GET",
            "/api/events",
            params={"max_events": 3, "timeout": 5},
            headers={"Last-Event-ID": str(id1)},
        ) as response:
            self.assertEqual(response.status_code, 200)
            chunks: list[str] = []
            for chunk in response.iter_text():
                chunks.append(chunk)
                if len(chunks) > 20:
                    break
            content = "".join(chunks)
            # 应该包含 id2 和 id3
            self.assertIn(f"id: {id2}", content)
            self.assertIn(f"id: {id3}", content)
            # 不应该回放 id1
            # （注意：id: 1 可能匹配 id: 10 等，因此用更严格的匹配）
            lines = content.split("\n")
            id_lines = [l for l in lines if l.startswith("id: ")]
            id_values = [int(l[4:]) for l in id_lines if l[4:].isdigit()]
            self.assertNotIn(id1, id_values)


if __name__ == "__main__":
    unittest.main()
