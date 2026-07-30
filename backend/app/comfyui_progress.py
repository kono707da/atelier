"""阶段 3.5 实时进度与故障恢复。

连接 ComfyUI WebSocket，实时跟踪任务执行进度：

1. 后端连接 ComfyUI WebSocket，接收执行事件
2. 保存当前节点、采样进度和事件
3. FastAPI 通过 SSE 推送前端
4. WebSocket 断开后自动重连
5. history 轮询兜底（WS 断开时）
6. Atelier 重启后核对 ComfyUI 队列和历史
7. 无法判断的任务标为 unknown，不自动重复

设计原则：
- 进度数据内存存储，按 prompt_id 索引
- WebSocket 监听器为后台异步任务，可启停
- SSE 端点从内存读取进度，推送给前端
- 历史轮询作为 WS 不可用时的兜底
- 重启恢复核对所有 submitted 状态的 attempt
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from .comfyui_client import ComfyUIError, ComfyUIClient
from .task_queue import (
    get_attempt,
    mark_attempt_completed,
    mark_attempt_failed,
    mark_attempt_unknown,
)


logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 进度跟踪器
# ──────────────────────────────────────────────────────────────────


class ProgressTracker:
    """内存进度跟踪器，按 prompt_id 索引。

    线程安全：使用 asyncio.Lock 保护（在异步上下文中使用）。
    如果在同步上下文中使用，操作足够原子（dict 读写）不需要锁。
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def update(self, prompt_id: str, event: dict[str, Any]) -> None:
        """更新某个 prompt_id 的进度数据。"""
        if prompt_id not in self._data:
            self._data[prompt_id] = {
                "prompt_id": prompt_id,
                "status": "running",
                "current_node": None,
                "progress_value": 0,
                "progress_max": 0,
                "events": [],
                "started_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        entry = self._data[prompt_id]
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        entry["events"].append(event)

        # 解析事件类型
        msg_type = event.get("type", "")
        data = event.get("data", {})

        if msg_type == "execution_start":
            entry["status"] = "running"
        elif msg_type == "executing":
            node_id = data.get("node")
            if node_id:
                entry["current_node"] = node_id
            elif data.get("node") is None and prompt_id:
                # node 为 None 表示执行完成
                entry["status"] = "completed"
        elif msg_type == "progress":
            entry["progress_value"] = data.get("value", 0)
            entry["progress_max"] = data.get("max", 0)
        elif msg_type == "executed":
            entry["current_node"] = data.get("node")
            # 记录输出
            outputs = entry.setdefault("outputs", {})
            node_id = data.get("node", "")
            if node_id and data.get("output"):
                outputs[node_id] = data["output"]
        elif msg_type == "execution_error":
            entry["status"] = "error"
            entry["error"] = data.get("exception_message", "执行错误")
        elif msg_type == "execution_interrupt":
            entry["status"] = "interrupted"
        elif msg_type == "execution_success":
            entry["status"] = "completed"

        # 通知订阅者
        self._notify(prompt_id, entry)

    def get(self, prompt_id: str) -> dict[str, Any] | None:
        """获取某个 prompt_id 的进度数据。"""
        return self._data.get(prompt_id)

    def get_all(self) -> dict[str, dict[str, Any]]:
        """获取所有进度数据。"""
        return dict(self._data)

    def remove(self, prompt_id: str) -> None:
        """删除某个 prompt_id 的进度数据。"""
        self._data.pop(prompt_id, None)
        self._subscribers.pop(prompt_id, None)

    def clear(self) -> None:
        """清空所有进度数据。"""
        self._data.clear()
        self._subscribers.clear()

    async def subscribe(self, prompt_id: str) -> asyncio.Queue:
        """订阅某个 prompt_id 的进度更新。"""
        queue: asyncio.Queue = asyncio.Queue()
        if prompt_id not in self._subscribers:
            self._subscribers[prompt_id] = []
        self._subscribers[prompt_id].append(queue)
        return queue

    def unsubscribe(self, prompt_id: str, queue: asyncio.Queue) -> None:
        """取消订阅。"""
        if prompt_id in self._subscribers:
            try:
                self._subscribers[prompt_id].remove(queue)
            except ValueError:
                pass
            if not self._subscribers[prompt_id]:
                self._subscribers.pop(prompt_id, None)

    def _notify(self, prompt_id: str, data: dict[str, Any]) -> None:
        """通知所有订阅者。"""
        subscribers = self._subscribers.get(prompt_id, [])
        for queue in subscribers:
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                pass

        # MOD-07: 转发到全局事件总线（供 /api/events SSE 推送）
        try:
            from .event_bus import publish_event
            status = data.get("status", "running")
            event_type = f"attempt.{status}" if status in (
                "completed", "error", "interrupted"
            ) else "attempt.progress"
            publish_event(event_type, {
                "prompt_id": prompt_id,
                "status": status,
                "current_node": data.get("current_node"),
                "progress_value": data.get("progress_value"),
                "progress_max": data.get("progress_max"),
                "updated_at": data.get("updated_at"),
            })
        except Exception:  # noqa: BLE001
            pass


# ──────────────────────────────────────────────────────────────────
# WebSocket 监听器
# ──────────────────────────────────────────────────────────────────


class ComfyUIWebSocketListener:
    """ComfyUI WebSocket 监听器。

    连接 ComfyUI WebSocket，接收执行事件并更新 ProgressTracker。
    支持自动重连。
    """

    def __init__(
        self,
        ws_url: str,
        tracker: ProgressTracker,
        *,
        client_id: str = "",
        reconnect_interval: float = 5.0,
        max_reconnect_attempts: int = 0,  # 0 = 无限重连
    ) -> None:
        self._ws_url = ws_url
        self._tracker = tracker
        self._client_id = client_id
        self._reconnect_interval = reconnect_interval
        self._max_reconnect_attempts = max_reconnect_attempts
        self._running = False
        self._task: asyncio.Task | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """启动 WebSocket 监听器（后台任务）。"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """停止 WebSocket 监听器。"""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._connected = False

    async def update_url(self, ws_url: str) -> None:
        """更新 WebSocket URL，如果正在运行则重启。"""
        was_running = self._running
        if was_running:
            await self.stop()
        self._ws_url = ws_url
        if was_running:
            await self.start()

    async def _run_loop(self) -> None:
        """主循环：连接 → 监听 → 断开 → 重连。"""
        import websockets

        attempts = 0
        while self._running:
            try:
                url = self._ws_url
                if self._client_id:
                    sep = "&" if "?" in url else "?"
                    url = f"{url}{sep}clientId={self._client_id}"

                async with websockets.connect(url, ping_interval=20) as ws:
                    self._connected = True
                    attempts = 0
                    logger.info("ComfyUI WebSocket 已连接: %s", url)

                    while self._running:
                        try:
                            message = await ws.recv()
                        except websockets.ConnectionClosed:
                            break

                        try:
                            data = json.loads(message)
                        except (TypeError, ValueError):
                            continue

                        prompt_id = data.get("data", {}).get("prompt_id", "")
                        if prompt_id:
                            self._tracker.update(prompt_id, data)

            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.warning("ComfyUI WebSocket 连接失败: %s", error)

            self._connected = False

            if not self._running:
                break

            attempts += 1
            if self._max_reconnect_attempts > 0 and attempts > self._max_reconnect_attempts:
                logger.error("ComfyUI WebSocket 重连次数超限，停止重连")
                break

            logger.info("等待 %.1f 秒后重连 WebSocket...", self._reconnect_interval)
            await asyncio.sleep(self._reconnect_interval)


# ──────────────────────────────────────────────────────────────────
# 历史轮询兜底
# ──────────────────────────────────────────────────────────────────


def _history_error_message(status_info: dict[str, Any]) -> str:
    """Extract an error from both legacy and current ComfyUI history shapes."""
    completed = status_info.get("completed")
    if isinstance(completed, dict):
        legacy_error = completed.get("error")
        if legacy_error:
            return str(legacy_error)
    messages = status_info.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, (list, tuple)) or len(message) < 2:
                continue
            if message[0] != "execution_error" or not isinstance(message[1], dict):
                continue
            detail = message[1]
            return str(
                detail.get("exception_message")
                or detail.get("exception_type")
                or detail.get("message")
                or "执行错误"
            )
    return str(status_info.get("error") or status_info.get("message") or "执行错误")


def poll_comfyui_history_for_attempt(
    manager: Any,
    comfyui_client: ComfyUIClient,
    attempt_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """轮询 ComfyUI 历史，检查指定 attempt 的执行结果。

    流程：
    1. 获取 attempt 的 prompt_id
    2. 查询 ComfyUI /history/{prompt_id}
    3. 如果找到结果，根据状态更新 attempt
    4. 返回查询结果

    返回 None 表示历史中不存在或查询失败。
    """
    attempt = get_attempt(manager, attempt_id, environment=environment)
    if not attempt:
        return None

    prompt_id = attempt.get("prompt_id")
    if not prompt_id:
        return None

    try:
        history = comfyui_client.get_history(prompt_id)
    except ComfyUIError:
        return None

    if not isinstance(history, dict):
        return None

    prompt_history = history.get(prompt_id)
    if not prompt_history:
        return None

    # 解析状态
    status_info = prompt_history.get("status", {})
    status_str = status_info.get("status_str", "")
    outputs = prompt_history.get("outputs", {})

    result = {
        "prompt_id": prompt_id,
        "status": status_str,
        "outputs": outputs,
        "completed": bool(status_str == "success"),
    }

    # 根据 ComfyUI 历史状态更新 attempt
    current_status = attempt.get("status")
    if current_status in ("submitted", "unknown", "running"):
        if status_str == "success":
            mark_attempt_completed(manager, attempt_id, environment=environment)
        elif status_str == "error":
            error_msg = _history_error_message(status_info)
            from .task_queue import mark_attempt_failed
            mark_attempt_failed(
                manager,
                attempt_id,
                error_message=f"ComfyUI 执行错误：{error_msg}",
                error_type="execution_error",
                environment=environment,
            )

    return result


def recover_submitted_attempts(
    manager: Any,
    comfyui_client: ComfyUIClient,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """重启后核对所有 submitted 状态的 attempt。

    流程：
    1. 查询所有 submitted 状态的 attempt
    2. 对每个 attempt 查询 ComfyUI 历史
    3. 历史中有结果：更新 attempt 状态（completed/failed）
    4. 历史中无结果：标记为 unknown（可能仍在队列或已丢失）

    返回恢复统计。
    """
    from .task_queue import list_attempts

    # 获取所有 submitted 状态的 attempt
    # 由于 list_attempts 需要 task_id，我们直接查数据库
    with manager.connection(environment) as conn:
        rows = conn.execute(
            """SELECT id, task_id, prompt_id FROM task_attempts
               WHERE status = 'submitted' AND prompt_id IS NOT NULL""",
        ).fetchall()

    recovered_completed = 0
    recovered_failed = 0
    marked_unknown = 0

    for row in rows:
        attempt_id = row["id"]
        prompt_id = row["prompt_id"]

        try:
            history = comfyui_client.get_history(prompt_id)
        except ComfyUIError:
            # 查询失败：标记为 unknown
            mark_attempt_unknown(
                manager,
                attempt_id,
                reason="重启后无法查询 ComfyUI 历史",
                environment=environment,
            )
            marked_unknown += 1
            continue

        if not isinstance(history, dict):
            mark_attempt_unknown(
                manager,
                attempt_id,
                reason="ComfyUI 历史响应格式异常",
                environment=environment,
            )
            marked_unknown += 1
            continue

        prompt_history = history.get(prompt_id)
        if not prompt_history:
            # 历史中不存在：标记为 unknown（可能仍在队列中）
            mark_attempt_unknown(
                manager,
                attempt_id,
                reason="重启后 ComfyUI 历史中未找到该任务",
                environment=environment,
            )
            marked_unknown += 1
            continue

        status_info = prompt_history.get("status", {})
        status_str = status_info.get("status_str", "")

        if status_str == "success":
            mark_attempt_completed(manager, attempt_id, environment=environment)
            recovered_completed += 1
        elif status_str == "error":
            error_msg = _history_error_message(status_info)
            from .task_queue import mark_attempt_failed
            mark_attempt_failed(
                manager,
                attempt_id,
                error_message=f"ComfyUI 执行错误：{error_msg}",
                error_type="execution_error",
                environment=environment,
            )
            recovered_failed += 1
        else:
            mark_attempt_unknown(
                manager,
                attempt_id,
                reason=f"ComfyUI 历史状态未知：{status_str}",
                environment=environment,
            )
            marked_unknown += 1

    return {
        "checked": len(rows),
        "recovered_completed": recovered_completed,
        "recovered_failed": recovered_failed,
        "marked_unknown": marked_unknown,
    }


# ──────────────────────────────────────────────────────────────────
# SSE 进度推送
# ──────────────────────────────────────────────────────────────────


async def sse_progress_generator(
    tracker: ProgressTracker,
    prompt_id: str,
    *,
    timeout_seconds: float = 300.0,
) -> Any:
    """SSE 事件生成器，推送指定 prompt_id 的进度更新。

    当任务完成或超时后停止。
    """
    import asyncio

    queue = await tracker.subscribe(prompt_id)

    try:
        # 先发送当前状态（如果有）。已经处于终态时必须立即结束，
        # 否则 TestClient 和真实 EventSource 都会继续等待到 300 秒超时。
        current = tracker.get(prompt_id)
        if current:
            is_terminal = current.get("status") in ("completed", "error", "interrupted")
            yield _format_sse_event(current)
            # current 是跟踪器中的可变字典；必须使用 yield 之前捕获的状态，
            # 避免消费者在两次迭代之间更新它后跳过队列里的终态事件。
            if is_terminal:
                return

        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                yield _format_sse_event({
                    "prompt_id": prompt_id,
                    "status": "timeout",
                    "message": "SSE 超时",
                })
                break

            try:
                data = await asyncio.wait_for(queue.get(), timeout=remaining)
            except asyncio.TimeoutError:
                yield _format_sse_event({
                    "prompt_id": prompt_id,
                    "status": "timeout",
                    "message": "SSE 超时",
                })
                break

            yield _format_sse_event(data)

            # 完成或错误时停止
            if data.get("status") in ("completed", "error", "interrupted"):
                break
    finally:
        tracker.unsubscribe(prompt_id, queue)


def _format_sse_event(data: dict[str, Any]) -> str:
    """格式化为 SSE 事件字符串。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
