"""MOD-07 全局事件总线。

为 `/api/events` SSE 端点提供统一的进程内发布订阅能力。

设计要点：
- 单调递增 event_id，作为 SSE 的 `id:` 字段，支持 `Last-Event-ID` 重连。
- 环形缓冲最近 N 条事件，新订阅者连接时按 `Last-Event-ID` 回放错过的事件。
- 订阅时支持按事件类型前缀过滤（如 `task`、`thumbnail`、`export`、`gallery`）。
- 同时支持异步（asyncio 上下文）和同步（worker 线程）发布：
  - 异步发布直接 `queue.put_nowait`。
  - 同步发布通过 `threading.Lock` 保护订阅者列表，并安全 put_nowait。
- 不引入 Redis 等外部依赖；关键事件已由各模块写入 SQLite，SSE 仅负责实时推送。

事件命名规范：`{模块}.{动作}`，例如 `task.created`、`thumbnail.completed`、
`export.item_progress`、`gallery.index_progress`、`attempt.progress`。
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Iterable

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────


DEFAULT_REPLAY_BUFFER_SIZE = 500
DEFAULT_SSE_TIMEOUT_SECONDS = 300.0
SSE_HEARTBEAT_SECONDS = 15.0


# ──────────────────────────────────────────────────────────────────
# 事件总线
# ──────────────────────────────────────────────────────────────────


class EventBus:
    """进程内全局事件总线。

    线程安全说明：
    - 订阅者队列是 `asyncio.Queue`，必须在事件循环中使用。
    - `publish` 和 `publish_sync` 都通过 `threading.Lock` 保护订阅者列表，
      因此同步 worker 线程可以安全调用 `publish_sync`。
    - 当 `publish_sync` 在没有事件循环的线程中调用时，会安全地 put_nowait 到队列；
      若队列满则丢弃事件（SSE 客户端应通过 `Last-Event-ID` 重连补全）。
    """

    def __init__(
        self,
        *,
        replay_buffer_size: int = DEFAULT_REPLAY_BUFFER_SIZE,
    ) -> None:
        self._replay_buffer_size = max(0, replay_buffer_size)
        self._replay_buffer: deque[dict[str, Any]] = deque(maxlen=self._replay_buffer_size)
        self._subscribers: list[dict[str, Any]] = []
        self._next_event_id = 1
        self._lock = threading.Lock()
        # 主事件循环引用，由 app lifespan 设置，供同步发布者跨线程调度
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """绑定主事件循环，供同步发布者跨线程调度。"""
        self._loop = loop

    def publish(self, event_type: str, payload: dict[str, Any]) -> int:
        """异步上下文中发布事件。

        返回分配的 event_id。
        """
        event_id = self._allocate_event_id(event_type, payload)
        self._dispatch(event_id, event_type, payload)
        return event_id

    def publish_sync(self, event_type: str, payload: dict[str, Any]) -> int:
        """同步上下文中发布事件（worker 线程安全调用）。

        返回分配的 event_id。

        实现：直接 put_nowait 到订阅者队列。asyncio.Queue 的 put_nowait 是
        线程安全的（内部使用 threading.Lock），因此可以跨线程调用。
        """
        event_id = self._allocate_event_id(event_type, payload)
        self._dispatch(event_id, event_type, payload)
        return event_id

    def _allocate_event_id(
        self, event_type: str, payload: dict[str, Any]
    ) -> int:
        """分配 event_id 并写入环形缓冲。"""
        event_id: int
        with self._lock:
            event_id = self._next_event_id
            self._next_event_id += 1
        record = {
            "id": event_id,
            "event": event_type,
            "data": payload,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self._replay_buffer.append(record)
        return event_id

    def _dispatch(self, event_id: int, event_type: str, payload: dict[str, Any]) -> None:
        """分发给所有匹配的订阅者。"""
        with self._lock:
            subscribers = list(self._subscribers)
        record = {
            "id": event_id,
            "event": event_type,
            "data": payload,
            "published_at": datetime.now(timezone.utc).isoformat(),
        }
        for sub in subscribers:
            if not _matches_filter(event_type, sub.get("types")):
                continue
            queue: asyncio.Queue = sub["queue"]
            try:
                queue.put_nowait(record)
            except asyncio.QueueFull:
                logger.warning(
                    "EventBus 订阅者队列已满，丢弃事件 id=%s type=%s",
                    event_id,
                    event_type,
                )

    async def subscribe(
        self,
        *,
        last_event_id: int | None = None,
        types: Iterable[str] | None = None,
    ) -> tuple[asyncio.Queue, list[dict[str, Any]]]:
        """订阅事件流。

        返回 (queue, missed_events)：
        - queue：后续新事件通过此队列推送。
        - missed_events：根据 last_event_id 从环形缓冲回放的事件列表。
          若 last_event_id 超出缓冲区最旧 id，会在返回列表中附带
          `{"event": "bus.reconnect", "data": {"missed": true, ...}}` 提示。
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=1024)
        types_list = [t.strip() for t in types if t and t.strip()] if types else None
        sub = {"queue": queue, "types": types_list}
        with self._lock:
            self._subscribers.append(sub)
            buffer_snapshot = list(self._replay_buffer)
            oldest_id = self._replay_buffer[0]["id"] if self._replay_buffer else None
            latest_id = self._replay_buffer[-1]["id"] if self._replay_buffer else None

        missed: list[dict[str, Any]] = []
        if last_event_id is not None and buffer_snapshot:
            if oldest_id is not None and last_event_id < oldest_id:
                missed.append({
                    "id": last_event_id,
                    "event": "bus.reconnect",
                    "data": {
                        "missed": True,
                        "reason": "events_out_of_buffer",
                        "last_event_id": last_event_id,
                        "oldest_available_id": oldest_id,
                    },
                    "published_at": datetime.now(timezone.utc).isoformat(),
                })
            for record in buffer_snapshot:
                if record["id"] <= last_event_id:
                    continue
                if not _matches_filter(record["event"], types_list):
                    continue
                missed.append(record)

        return queue, missed

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """取消订阅。"""
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s["queue"] is not queue]

    def stats(self) -> dict[str, Any]:
        """返回总线状态统计。"""
        with self._lock:
            return {
                "next_event_id": self._next_event_id,
                "buffered_events": len(self._replay_buffer),
                "buffer_capacity": self._replay_buffer_size,
                "active_subscribers": len(self._subscribers),
            }


def _matches_filter(event_type: str, types: list[str] | None) -> bool:
    """判断事件类型是否匹配订阅过滤器。

    过滤规则：若 types 为 None 或空，匹配所有；否则按前缀匹配，
    例如 types=["task"] 匹配 "task.created"、"task.progress" 等。
    """
    if not types:
        return True
    for prefix in types:
        if event_type == prefix or event_type.startswith(prefix + ".") or event_type.startswith(prefix):
            return True
    return False


# ──────────────────────────────────────────────────────────────────
# SSE 生成器
# ──────────────────────────────────────────────────────────────────


def format_sse_event(
    event_id: int,
    event_type: str,
    data: dict[str, Any],
    *,
    retry: int | None = None,
) -> str:
    """格式化为标准 SSE 事件字符串。

    输出包含 `id:`、`event:`、`data:` 三段，符合 SSE 规范。
    """
    lines = [f"id: {event_id}", f"event: {event_type}"]
    if retry is not None:
        lines.append(f"retry: {retry}")
    payload = json.dumps(data, ensure_ascii=False, default=str)
    lines.append(f"data: {payload}")
    return "\n".join(lines) + "\n\n"


async def sse_events_generator(
    bus: EventBus,
    *,
    last_event_id: int | None = None,
    types: Iterable[str] | None = None,
    timeout_seconds: float = DEFAULT_SSE_TIMEOUT_SECONDS,
    max_events: int | None = None,
) -> AsyncIterator[str]:
    """全局 SSE 事件生成器。

    流程：
    1. 订阅 EventBus，回放 last_event_id 之后错过的事件。
    2. 先发送回放事件。
    3. 进入循环，从队列读取新事件并 yield。
    4. 超时或达到 max_events 时发送结束事件并退出。

    测试时必须设置 `timeout_seconds` 或 `max_events` 作为终止条件
    （满足 MOD-07 验收要求）。
    """
    queue, missed = await bus.subscribe(
        last_event_id=last_event_id, types=types
    )
    sent = 0
    try:
        # 先发送回放事件
        for record in missed:
            yield format_sse_event(
                record["id"], record["event"], record["data"]
            )
            sent += 1
            if max_events is not None and sent >= max_events:
                yield _format_end_event(bus, reason="max_events_reached")
                return

        deadline = asyncio.get_event_loop().time() + timeout_seconds
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                yield _format_end_event(bus, reason="timeout")
                return

            try:
                record = await asyncio.wait_for(
                    queue.get(), timeout=min(remaining, SSE_HEARTBEAT_SECONDS)
                )
            except asyncio.TimeoutError:
                # 发送心跳，保持连接
                yield ": heartbeat\n\n"
                continue

            yield format_sse_event(
                record["id"], record["event"], record["data"]
            )
            sent += 1
            if max_events is not None and sent >= max_events:
                yield _format_end_event(bus, reason="max_events_reached")
                return
    finally:
        bus.unsubscribe(queue)


def _format_end_event(bus: EventBus, *, reason: str) -> str:
    """格式化结束事件。"""
    stats = bus.stats()
    event_id = stats["next_event_id"]
    return format_sse_event(
        event_id,
        "bus.end",
        {"reason": reason, "stats": stats},
    )


# ──────────────────────────────────────────────────────────────────
# 模块级单例访问
# ──────────────────────────────────────────────────────────────────


_global_bus: EventBus | None = None


def get_global_bus() -> EventBus:
    """获取全局 EventBus 单例。

    若未初始化则自动创建（主要用于测试和独立模块调用）。
    生产环境应在 app 启动时调用 `set_global_bus` 绑定实例。
    """
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def set_global_bus(bus: EventBus) -> None:
    """设置全局 EventBus 单例。"""
    global _global_bus
    _global_bus = bus


def publish_event(event_type: str, payload: dict[str, Any]) -> int:
    """模块级便捷发布函数（同步安全）。

    供 worker 模块（thumbnail_worker、export_runner、maintenance_tasks 等）
    在同步上下文中调用，无需显式获取 bus 实例。
    """
    return get_global_bus().publish_sync(event_type, payload)
