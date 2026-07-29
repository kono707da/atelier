"""阶段 3.3 持久化任务队列。

实现批次内任务的持久化、领取、重试和状态机：

1. 任务创建：从批次的不可变快照展开为页级任务
2. 任务领取：原子获取 pending 任务，创建 attempt 和租约
3. 并发限制：通过租约机制防止重复领取
4. 状态机：pending → running → completed/failed/cancelled
5. 失败重试：失败后创建新 attempt，不覆盖旧记录
6. 暂停/继续/取消：批次级别的调度控制
7. 应用重启恢复：通过任务和租约状态恢复调度

设计原则：
- 任务不可变快照：每个任务保存完整的 RenderItem 快照
- Attempt 不可变：每次尝试都是一个独立记录，永不覆盖
- 租约防重：通过 expires_at 和 released_at 实现超时释放
- 事件溯源：所有状态变更记录到 task_events
- 幂等性：重复领取同一任务返回已有 attempt
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


# ──────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────


# 任务状态机
VALID_TASK_STATUSES = (
    "pending",      # 等待调度
    "running",      # 正在执行（有活跃 attempt）
    "paused",       # 暂停（不参与调度）
    "completed",    # 成功完成
    "cancelled",    # 用户取消
    "failed",       # 达到最大重试次数后失败
    "retrying",     # 等待重试（短暂状态，会被立即领取）
)

# Attempt 状态
VALID_ATTEMPT_STATUSES = (
    "running",      # 已创建但未提交
    "submitted",    # 已提交到 ComfyUI
    "completed",    # 成功完成
    "failed",       # 失败
    "timeout",      # 超时
    "unknown",      # 状态未知（重启后无法判断）
)

# 事件类型
VALID_EVENT_TYPES = (
    "created",          # 任务创建
    "leased",           # 任务被领取
    "submitted",        # attempt 已提交
    "progress",         # 进度更新
    "completed",        # 任务完成
    "failed",           # attempt 失败
    "retried",          # 触发重试
    "cancelled",        # 任务被取消
    "paused",           # 任务被暂停
    "resumed",          # 任务被恢复
    "lease_expired",    # 租约过期
    "recovered",        # 重启恢复
)

# 默认租约时长（秒）
DEFAULT_LEASE_SECONDS = 300  # 5 分钟

# 默认最大重试次数
DEFAULT_MAX_ATTEMPTS = 3


# ──────────────────────────────────────────────────────────────────
# 任务创建
# ──────────────────────────────────────────────────────────────────


def create_tasks_from_batch(
    manager: Any,
    batch_id: str,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """从批次的不可变快照展开为页级任务。

    如果任务已存在（幂等），返回已有任务列表。
    """
    # 获取批次
    with manager.connection(environment) as conn:
        batch = conn.execute(
            "SELECT id, project_id, snapshot_json FROM batches WHERE id = ? AND deleted_at IS NULL",
            (batch_id,),
        ).fetchone()
        if not batch:
            raise ValueError("批次不存在")

        # 检查是否已有任务（幂等）
        existing = conn.execute(
            "SELECT COUNT(*) AS count FROM tasks WHERE batch_id = ? AND deleted_at IS NULL",
            (batch_id,),
        ).fetchone()
        if existing["count"] > 0:
            return list_tasks(manager, batch_id, environment=environment)

        # 从快照展开任务
        snapshot = json.loads(batch["snapshot_json"]) if batch["snapshot_json"] else {}
        items = snapshot.get("items", [])
        if not items:
            return []

        now = datetime.now(timezone.utc).isoformat()
        tasks_data: list[tuple] = []
        events_data: list[tuple] = []
        for item in items:
            task_id = str(uuid4())
            sort_key = item.get("sort_key", "0")
            item_snapshot = json.dumps(item, ensure_ascii=False)
            tasks_data.append((
                task_id, batch_id, sort_key, item_snapshot,
                "pending", 0, 0, max_attempts,
                now, now,
            ))
            # 收集事件（在任务插入后再写入，避免外键约束失败）
            event_id = str(uuid4())
            events_data.append((
                event_id, task_id,
                json.dumps({"sort_key": sort_key}, ensure_ascii=False), now,
            ))

        # 先插入任务（满足 task_events 的外键约束）
        conn.executemany(
            """INSERT INTO tasks(
                id, batch_id, sort_key, item_snapshot_json,
                status, priority, attempt_count, max_attempts,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tasks_data,
        )

        # 再插入事件
        conn.executemany(
            """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
               VALUES (?, ?, NULL, 'created', ?, ?)""",
            events_data,
        )

    return list_tasks(manager, batch_id, environment=environment)


# ──────────────────────────────────────────────────────────────────
# 任务领取（原子操作）
# ──────────────────────────────────────────────────────────────────


def claim_next_task(
    manager: Any,
    *,
    lease_holder: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    batch_id: str | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """原子领取下一个可执行任务。

    流程：
    1. 查找 pending 或 retrying 状态的任务（按优先级和创建时间排序）
    2. 检查所属批次是否为 running 状态
    3. 原子更新任务状态为 running
    4. 创建新 attempt
    5. 创建租约
    6. 记录事件

    返回 None 表示没有可领取的任务。
    """
    now = datetime.now(timezone.utc)
    lease_expires = now.timestamp() + lease_seconds
    expires_at = datetime.fromtimestamp(lease_expires, tz=timezone.utc).isoformat()
    now = now.isoformat()

    with manager.connection(environment) as conn:
        # 查找可领取的任务
        if batch_id:
            row = conn.execute(
                """
                SELECT t.id, t.batch_id, t.sort_key, t.item_snapshot_json,
                       t.attempt_count, t.max_attempts, t.priority
                FROM tasks t
                JOIN batches b ON b.id = t.batch_id
                WHERE t.status IN ('pending', 'retrying')
                  AND t.deleted_at IS NULL
                  AND b.status = 'running'
                  AND b.deleted_at IS NULL
                  AND t.batch_id = ?
                ORDER BY t.priority DESC, t.created_at ASC
                LIMIT 1
                """,
                (batch_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT t.id, t.batch_id, t.sort_key, t.item_snapshot_json,
                       t.attempt_count, t.max_attempts, t.priority
                FROM tasks t
                JOIN batches b ON b.id = t.batch_id
                WHERE t.status IN ('pending', 'retrying')
                  AND t.deleted_at IS NULL
                  AND b.status = 'running'
                  AND b.deleted_at IS NULL
                ORDER BY t.priority DESC, t.created_at ASC
                LIMIT 1
                """,
            ).fetchone()

        if not row:
            return None

        task_id = row["id"]
        # 原子更新任务状态（防止并发领取）
        cursor = conn.execute(
            """UPDATE tasks
               SET status = 'running', attempt_count = attempt_count + 1,
                   updated_at = ?
               WHERE id = ? AND status IN ('pending', 'retrying')""",
            (now, task_id),
        )
        if cursor.rowcount == 0:
            # 已被其他 worker 领取
            return None

        # 创建新 attempt
        attempt_id = str(uuid4())
        attempt_number = row["attempt_count"] + 1
        conn.execute(
            """INSERT INTO task_attempts(
                id, task_id, attempt_number, status,
                started_at, created_at
            ) VALUES (?, ?, ?, 'running', ?, ?)""",
            (attempt_id, task_id, attempt_number, now, now),
        )

        # 更新任务的 last_attempt_id
        conn.execute(
            "UPDATE tasks SET last_attempt_id = ?, updated_at = ? WHERE id = ?",
            (attempt_id, now, task_id),
        )

        # 创建租约
        lease_id = str(uuid4())
        conn.execute(
            """INSERT INTO task_leases(
                id, task_id, attempt_id, lease_holder,
                acquired_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (lease_id, task_id, attempt_id, lease_holder, now, expires_at),
        )

        # 记录事件
        event_id = str(uuid4())
        conn.execute(
            """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
               VALUES (?, ?, ?, 'leased', ?, ?)""",
            (event_id, task_id, attempt_id,
             json.dumps({"lease_holder": lease_holder, "attempt_number": attempt_number}, ensure_ascii=False),
             now),
        )

        return {
            "task_id": task_id,
            "batch_id": row["batch_id"],
            "sort_key": row["sort_key"],
            "item": json.loads(row["item_snapshot_json"]) if row["item_snapshot_json"] else {},
            "attempt_id": attempt_id,
            "attempt_number": attempt_number,
            "lease_id": lease_id,
            "lease_expires_at": expires_at,
            "max_attempts": row["max_attempts"],
        }


def claim_tasks_batch(
    manager: Any,
    count: int,
    *,
    lease_holder: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    batch_id: str | None = None,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """批量领取多个任务。"""
    results: list[dict[str, Any]] = []
    for _ in range(count):
        claim = claim_next_task(
            manager,
            lease_holder=lease_holder,
            lease_seconds=lease_seconds,
            batch_id=batch_id,
            environment=environment,
        )
        if claim is None:
            break
        results.append(claim)
    return results


# ──────────────────────────────────────────────────────────────────
# Attempt 状态更新
# ──────────────────────────────────────────────────────────────────


def mark_attempt_submitted(
    manager: Any,
    attempt_id: str,
    *,
    prompt_id: str,
    api_json: str | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """标记 attempt 已提交到 ComfyUI。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        # 获取 attempt
        attempt = conn.execute(
            "SELECT id, task_id, attempt_number, status FROM task_attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        if not attempt:
            return None

        conn.execute(
            """UPDATE task_attempts
               SET status = 'submitted', prompt_id = ?, api_json = ?, submitted_at = ?,
                   revision = revision + 1
               WHERE id = ?""",
            (prompt_id, api_json, now, attempt_id),
        )

        # 记录事件
        event_id = str(uuid4())
        conn.execute(
            """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
               VALUES (?, ?, ?, 'submitted', ?, ?)""",
            (event_id, attempt["task_id"], attempt_id,
             json.dumps({"prompt_id": prompt_id}, ensure_ascii=False), now),
        )

    return get_attempt(manager, attempt_id, environment=environment)


def mark_attempt_completed(
    manager: Any,
    attempt_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """标记 attempt 成功完成，同时更新任务状态为 completed。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        attempt = conn.execute(
            "SELECT id, task_id, attempt_number FROM task_attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        if not attempt:
            return None

        # 更新 attempt
        conn.execute(
            """UPDATE task_attempts
               SET status = 'completed', completed_at = ?, revision = revision + 1
               WHERE id = ?""",
            (now, attempt_id),
        )

        # 更新任务状态
        conn.execute(
            """UPDATE tasks
               SET status = 'completed', updated_at = ?, revision = revision + 1
               WHERE id = ?""",
            (now, attempt["task_id"]),
        )

        # 释放租约
        conn.execute(
            "UPDATE task_leases SET released_at = ? WHERE attempt_id = ? AND released_at IS NULL",
            (now, attempt_id),
        )

        # 记录事件
        event_id = str(uuid4())
        conn.execute(
            """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
               VALUES (?, ?, ?, 'completed', '{}', ?)""",
            (event_id, attempt["task_id"], attempt_id, now),
        )

    return get_attempt(manager, attempt_id, environment=environment)


def mark_attempt_failed(
    manager: Any,
    attempt_id: str,
    *,
    error_message: str = "",
    error_type: str = "unknown",
    environment: str | None = None,
) -> dict[str, Any] | None:
    """标记 attempt 失败，根据重试次数决定任务状态。

    - 如果未达到最大重试次数：任务状态变为 retrying
    - 如果已达到最大重试次数：任务状态变为 failed
    """
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        attempt = conn.execute(
            "SELECT id, task_id, attempt_number FROM task_attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        if not attempt:
            return None

        # 更新 attempt
        conn.execute(
            """UPDATE task_attempts
               SET status = 'failed', error_message = ?, error_type = ?,
                   completed_at = ?, revision = revision + 1
               WHERE id = ?""",
            (error_message, error_type, now, attempt_id),
        )

        # 释放租约
        conn.execute(
            "UPDATE task_leases SET released_at = ? WHERE attempt_id = ? AND released_at IS NULL",
            (now, attempt_id),
        )

        # 获取任务信息
        task = conn.execute(
            "SELECT id, attempt_count, max_attempts FROM tasks WHERE id = ?",
            (attempt["task_id"],),
        ).fetchone()

        # 决定任务状态
        if task and task["attempt_count"] >= task["max_attempts"]:
            new_status = "failed"
            event_type = "failed"
            task_update = "error_message = ?, error_type = ?"
            task_params: list[Any] = [error_message, error_type, now, task["id"]]
        else:
            new_status = "retrying"
            event_type = "retried"
            task_update = "error_message = ?, error_type = ?"
            task_params = [error_message, error_type, now, task["id"]]

        conn.execute(
            f"""UPDATE tasks
                SET status = ?, {task_update}, updated_at = ?, revision = revision + 1
                WHERE id = ?""",
            [new_status] + task_params,
        )

        # 记录事件
        event_id = str(uuid4())
        conn.execute(
            """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_id, attempt["task_id"], attempt_id, event_type,
             json.dumps({"error_message": error_message, "error_type": error_type,
                         "new_status": new_status}, ensure_ascii=False),
             now),
        )

    return get_attempt(manager, attempt_id, environment=environment)


def mark_attempt_unknown(
    manager: Any,
    attempt_id: str,
    *,
    reason: str = "",
    environment: str | None = None,
) -> dict[str, Any] | None:
    """标记 attempt 状态为 unknown（重启后无法判断）。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        attempt = conn.execute(
            "SELECT id, task_id FROM task_attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        if not attempt:
            return None

        conn.execute(
            """UPDATE task_attempts
               SET status = 'unknown', error_message = ?, completed_at = ?,
                   revision = revision + 1
               WHERE id = ?""",
            (reason, now, attempt_id),
        )

        # 任务状态也标记为 unknown（用 failed 替代，因为没有 unknown 任务状态）
        # 实际上任务保持原状态，让用户手动决定
        event_id = str(uuid4())
        conn.execute(
            """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
               VALUES (?, ?, ?, 'recovered', ?, ?)""",
            (event_id, attempt["task_id"], attempt_id,
             json.dumps({"reason": reason}, ensure_ascii=False), now),
        )

    return get_attempt(manager, attempt_id, environment=environment)


# ──────────────────────────────────────────────────────────────────
# 任务控制（暂停/继续/取消/优先级）
# ──────────────────────────────────────────────────────────────────


def pause_task(
    manager: Any,
    task_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """暂停任务（不参与调度）。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            """UPDATE tasks
               SET status = 'paused', updated_at = ?, revision = revision + 1
               WHERE id = ? AND status IN ('pending', 'retrying')""",
            (now, task_id),
        )
        if cursor.rowcount == 0:
            return None
        _record_event(conn, task_id, "paused", {})
    return get_task(manager, task_id, environment=environment)


def resume_task(
    manager: Any,
    task_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """恢复暂停的任务。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            """UPDATE tasks
               SET status = 'pending', updated_at = ?, revision = revision + 1
               WHERE id = ? AND status = 'paused'""",
            (now, task_id),
        )
        if cursor.rowcount == 0:
            return None
        _record_event(conn, task_id, "resumed", {})
    return get_task(manager, task_id, environment=environment)


def cancel_task(
    manager: Any,
    task_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """取消任务。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            """UPDATE tasks
               SET status = 'cancelled', updated_at = ?, revision = revision + 1
               WHERE id = ? AND status NOT IN ('completed', 'cancelled')""",
            (now, task_id),
        )
        if cursor.rowcount == 0:
            return None
        _record_event(conn, task_id, "cancelled", {})
    return get_task(manager, task_id, environment=environment)


def set_task_priority(
    manager: Any,
    task_id: str,
    priority: int,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """设置任务优先级。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            "UPDATE tasks SET priority = ?, updated_at = ?, revision = revision + 1 WHERE id = ?",
            (priority, now, task_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_task(manager, task_id, environment=environment)


def retry_task(
    manager: Any,
    task_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """手动重试任务（重置为 pending）。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            """UPDATE tasks
               SET status = 'pending', error_message = NULL, error_type = NULL,
                   updated_at = ?, revision = revision + 1
               WHERE id = ? AND status IN ('failed', 'cancelled')""",
            (now, task_id),
        )
        if cursor.rowcount == 0:
            return None
        _record_event(conn, task_id, "retried", {"manual": True})
    return get_task(manager, task_id, environment=environment)


# ──────────────────────────────────────────────────────────────────
# 查询接口
# ──────────────────────────────────────────────────────────────────


def list_tasks(
    manager: Any,
    batch_id: str,
    *,
    status: str | None = None,
    include_deleted: bool = False,
    limit: int = 200,
    offset: int = 0,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出批次内的任务。"""
    conditions = ["batch_id = ?"]
    params: list[Any] = [batch_id]
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if not include_deleted:
        conditions.append("deleted_at IS NULL")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id, batch_id, sort_key, item_snapshot_json, status, priority,
               attempt_count, max_attempts, last_attempt_id,
               error_message, error_type, revision,
               created_at, updated_at, deleted_at
        FROM tasks
        WHERE {where}
        ORDER BY sort_key ASC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with manager.connection(environment) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_task(r) for r in rows]


def get_task(
    manager: Any,
    task_id: str,
    *,
    include_item: bool = True,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取任务详情。"""
    cols = (
        "id, batch_id, sort_key, item_snapshot_json, status, priority, "
        "attempt_count, max_attempts, last_attempt_id, "
        "error_message, error_type, revision, "
        "created_at, updated_at, deleted_at"
    ) if include_item else (
        "id, batch_id, sort_key, status, priority, "
        "attempt_count, max_attempts, last_attempt_id, "
        "error_message, error_type, revision, "
        "created_at, updated_at, deleted_at"
    )
    with manager.connection(environment) as conn:
        row = conn.execute(
            f"SELECT {cols} FROM tasks WHERE id = ? AND deleted_at IS NULL",
            (task_id,),
        ).fetchone()
        if not row:
            return None
        return _row_to_task(row, include_item=include_item)


def get_attempt(
    manager: Any,
    attempt_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取 attempt 详情。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            """SELECT id, task_id, attempt_number, status, prompt_id, api_json,
                      error_message, error_type,
                      started_at, submitted_at, completed_at,
                      revision, created_at
               FROM task_attempts WHERE id = ?""",
            (attempt_id,),
        ).fetchone()
        if not row:
            return None
        return _row_to_attempt(row)


def list_attempts(
    manager: Any,
    task_id: str,
    *,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出任务的所有 attempt（按尝试序号倒序）。"""
    with manager.connection(environment) as conn:
        rows = conn.execute(
            """SELECT id, task_id, attempt_number, status, prompt_id, api_json,
                      error_message, error_type,
                      started_at, submitted_at, completed_at,
                      revision, created_at
               FROM task_attempts
               WHERE task_id = ?
               ORDER BY attempt_number DESC""",
            (task_id,),
        ).fetchall()
        return [_row_to_attempt(r) for r in rows]


def list_events(
    manager: Any,
    task_id: str,
    *,
    event_type: str | None = None,
    limit: int = 100,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出任务的事件。"""
    conditions = ["task_id = ?"]
    params: list[Any] = [task_id]
    if event_type is not None:
        conditions.append("event_type = ?")
        params.append(event_type)

    where = " AND ".join(conditions)
    sql = f"""
        SELECT id, task_id, attempt_id, event_type, event_data_json, created_at
        FROM task_events
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT ?
    """
    params.append(limit)

    with manager.connection(environment) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [{
            "id": r["id"],
            "task_id": r["task_id"],
            "attempt_id": r["attempt_id"],
            "event_type": r["event_type"],
            "event_data": json.loads(r["event_data_json"]) if r["event_data_json"] else {},
            "created_at": r["created_at"],
        } for r in rows]


def get_batch_progress(
    manager: Any,
    batch_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """获取批次的任务进度统计。"""
    with manager.connection(environment) as conn:
        # 验证批次存在
        batch = conn.execute(
            "SELECT id FROM batches WHERE id = ? AND deleted_at IS NULL",
            (batch_id,),
        ).fetchone()
        if not batch:
            raise ValueError("批次不存在")

        total = conn.execute(
            "SELECT COUNT(*) AS count FROM tasks WHERE batch_id = ? AND deleted_at IS NULL",
            (batch_id,),
        ).fetchone()["count"]

        if total == 0:
            return {
                "batch_id": batch_id,
                "total": 0,
                "pending": 0,
                "running": 0,
                "retrying": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0,
                "paused": 0,
                "progress_percent": 0,
            }

        rows = conn.execute(
            """SELECT status, COUNT(*) AS count
               FROM tasks
               WHERE batch_id = ? AND deleted_at IS NULL
               GROUP BY status""",
            (batch_id,),
        ).fetchall()

        status_counts = {r["status"]: r["count"] for r in rows}
        completed = status_counts.get("completed", 0)
        return {
            "batch_id": batch_id,
            "total": total,
            "pending": status_counts.get("pending", 0),
            "running": status_counts.get("running", 0),
            "retrying": status_counts.get("retrying", 0),
            "completed": completed,
            "failed": status_counts.get("failed", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "paused": status_counts.get("paused", 0),
            "progress_percent": round(completed / total * 100, 1) if total > 0 else 0,
        }


def list_all_tasks(
    manager: Any,
    *,
    status: str | None = None,
    project_id: str | None = None,
    batch_id: str | None = None,
    has_error: bool | None = None,
    created_after: str | None = None,
    created_before: str | None = None,
    include_deleted: bool = False,
    limit: int = 100,
    offset: int = 0,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """跨批次列出所有任务，支持多维度筛选。

    筛选维度：
    - status: 任务状态
    - project_id: 项目 ID（关联 batches 表）
    - batch_id: 批次 ID
    - has_error: 是否有错误
    - created_after/created_before: 创建时间范围
    """
    conditions: list[str] = []
    params: list[Any] = []

    if status is not None:
        conditions.append("t.status = ?")
        params.append(status)
    if batch_id is not None:
        conditions.append("t.batch_id = ?")
        params.append(batch_id)
    if project_id is not None:
        conditions.append("b.project_id = ?")
        params.append(project_id)
    if has_error is True:
        conditions.append("t.error_message IS NOT NULL AND t.error_message != ''")
    elif has_error is False:
        conditions.append("(t.error_message IS NULL OR t.error_message = '')")
    if created_after is not None:
        conditions.append("t.created_at >= ?")
        params.append(created_after)
    if created_before is not None:
        conditions.append("t.created_at <= ?")
        params.append(created_before)
    if not include_deleted:
        conditions.append("t.deleted_at IS NULL")

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"""
        SELECT t.id, t.batch_id, t.sort_key, t.item_snapshot_json, t.status,
               t.priority, t.attempt_count, t.max_attempts, t.last_attempt_id,
               t.error_message, t.error_type, t.revision,
               t.created_at, t.updated_at, t.deleted_at,
               b.project_id, b.name AS batch_name
        FROM tasks t
        LEFT JOIN batches b ON t.batch_id = b.id
        WHERE {where}
        ORDER BY t.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with manager.connection(environment) as conn:
        rows = conn.execute(sql, params).fetchall()
        tasks = [_row_to_task(r) for r in rows]
        # 添加 JOIN 查询的额外字段
        for task, row in zip(tasks, rows):
            try:
                task["project_id"] = row["project_id"]
            except (IndexError, KeyError):
                task["project_id"] = None
            try:
                task["batch_name"] = row["batch_name"]
            except (IndexError, KeyError):
                task["batch_name"] = None
        return tasks


def get_task_center_summary(
    manager: Any,
    *,
    project_id: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """获取任务中心汇总统计。

    返回各状态的任务数量、错误任务数和最近失败任务。
    """
    conditions = ["t.deleted_at IS NULL"]
    params: list[Any] = []
    if project_id is not None:
        conditions.append("b.project_id = ?")
        params.append(project_id)
    where = " AND ".join(conditions)

    with manager.connection(environment) as conn:
        # 状态统计
        rows = conn.execute(
            f"""SELECT t.status, COUNT(*) AS count
               FROM tasks t
               LEFT JOIN batches b ON t.batch_id = b.id
               WHERE {where}
               GROUP BY t.status""",
            params,
        ).fetchall()
        status_counts = {r["status"]: r["count"] for r in rows}
        total = sum(status_counts.values())

        # 错误任务数
        error_count = conn.execute(
            f"""SELECT COUNT(*) AS count
               FROM tasks t
               LEFT JOIN batches b ON t.batch_id = b.id
               WHERE {where}
               AND t.error_message IS NOT NULL AND t.error_message != ''""",
            params,
        ).fetchone()["count"]

        # 批次统计
        batch_conditions = ["deleted_at IS NULL"]
        batch_params: list[Any] = []
        if project_id is not None:
            batch_conditions.append("project_id = ?")
            batch_params.append(project_id)
        batch_where = " AND ".join(batch_conditions)
        batch_rows = conn.execute(
            f"""SELECT status, COUNT(*) AS count
               FROM batches
               WHERE {batch_where}
               GROUP BY status""",
            batch_params,
        ).fetchall()
        batch_status_counts = {r["status"]: r["count"] for r in batch_rows}

        return {
            "total_tasks": total,
            "pending": status_counts.get("pending", 0),
            "running": status_counts.get("running", 0),
            "retrying": status_counts.get("retrying", 0),
            "completed": status_counts.get("completed", 0),
            "failed": status_counts.get("failed", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "paused": status_counts.get("paused", 0),
            "error_tasks": error_count,
            "total_batches": sum(batch_status_counts.values()),
            "running_batches": batch_status_counts.get("running", 0),
        }


# ──────────────────────────────────────────────────────────────────
# 租约管理
# ──────────────────────────────────────────────────────────────────


def release_lease(
    manager: Any,
    lease_id: str,
    *,
    environment: str | None = None,
) -> bool:
    """手动释放租约。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            "UPDATE task_leases SET released_at = ? WHERE id = ? AND released_at IS NULL",
            (now, lease_id),
        )
        return cursor.rowcount > 0


def expire_stale_leases(
    manager: Any,
    *,
    environment: str | None = None,
) -> int:
    """过期所有超时租约，将对应任务重置为 pending。

    返回过期的租约数量。
    """
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        # 查找过期且未释放的租约
        stale = conn.execute(
            """SELECT id, task_id, attempt_id
               FROM task_leases
               WHERE expires_at < ? AND released_at IS NULL""",
            (now,),
        ).fetchall()

        if not stale:
            return 0

        for row in stale:
            # 释放租约
            conn.execute(
                "UPDATE task_leases SET released_at = ? WHERE id = ?",
                (now, row["id"]),
            )
            # 将任务重置为 pending（如果是 running 状态）
            conn.execute(
                """UPDATE tasks
                   SET status = 'pending', updated_at = ?, revision = revision + 1
                   WHERE id = ? AND status = 'running'""",
                (now, row["task_id"]),
            )
            # 标记 attempt 为 unknown
            conn.execute(
                """UPDATE task_attempts
                   SET status = 'unknown', error_message = '租约超时',
                       completed_at = ?, revision = revision + 1
                   WHERE id = ?""",
                (now, row["attempt_id"]),
            )
            # 记录事件
            event_id = str(uuid4())
            conn.execute(
                """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
                   VALUES (?, ?, ?, 'lease_expired', '{}', ?)""",
                (event_id, row["task_id"], row["attempt_id"], now),
            )

        return len(stale)


# ──────────────────────────────────────────────────────────────────
# 应用重启恢复
# ──────────────────────────────────────────────────────────────────


def recover_after_restart(
    manager: Any,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """应用重启后的任务恢复。

    流程：
    1. 过期所有超时租约
    2. 将所有 running 状态的任务重置为 pending
    3. 将所有 submitted 状态的 attempt 标记为 unknown
    4. 返回恢复统计
    """
    now = datetime.now(timezone.utc).isoformat()

    # 1. 过期超时租约
    expired_leases = expire_stale_leases(manager, environment=environment)

    with manager.connection(environment) as conn:
        # 2. 将所有 running 状态的任务重置为 pending
        running_tasks = conn.execute(
            "SELECT id FROM tasks WHERE status = 'running' AND deleted_at IS NULL"
        ).fetchall()
        for row in running_tasks:
            conn.execute(
                """UPDATE tasks
                   SET status = 'pending', updated_at = ?, revision = revision + 1
                   WHERE id = ?""",
                (now, row["id"]),
            )
            _record_event(conn, row["id"], "recovered", {"reason": "running_to_pending"})

        # 3. 将所有 submitted 状态的 attempt 标记为 unknown
        submitted_attempts = conn.execute(
            "SELECT id, task_id FROM task_attempts WHERE status = 'submitted'"
        ).fetchall()
        for row in submitted_attempts:
            conn.execute(
                """UPDATE task_attempts
                   SET status = 'unknown', error_message = '应用重启后状态未知',
                       completed_at = ?, revision = revision + 1
                   WHERE id = ?""",
                (now, row["id"]),
            )
            _record_event(conn, row["task_id"], "recovered",
                          {"attempt_id": row["id"], "reason": "submitted_to_unknown"})

        return {
            "expired_leases": expired_leases,
            "recovered_tasks": len(running_tasks),
            "unknown_attempts": len(submitted_attempts),
        }


# ──────────────────────────────────────────────────────────────────
# 内部工具
# ──────────────────────────────────────────────────────────────────


def _record_event(
    conn: Any,
    task_id: str,
    event_type: str,
    event_data: dict[str, Any],
) -> None:
    """记录任务事件（内部使用，不单独开连接）。"""
    now = datetime.now(timezone.utc).isoformat()
    event_id = str(uuid4())
    conn.execute(
        """INSERT INTO task_events(id, task_id, attempt_id, event_type, event_data_json, created_at)
           VALUES (?, ?, NULL, ?, ?, ?)""",
        (event_id, task_id, event_type,
         json.dumps(event_data, ensure_ascii=False), now),
    )


def _row_to_task(row: Any, *, include_item: bool = True) -> dict[str, Any]:
    """将数据库行转为任务字典。"""
    result: dict[str, Any] = {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "sort_key": row["sort_key"],
        "status": row["status"],
        "priority": row["priority"],
        "attempt_count": row["attempt_count"],
        "max_attempts": row["max_attempts"],
        "last_attempt_id": row["last_attempt_id"],
        "error_message": row["error_message"],
        "error_type": row["error_type"],
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deleted_at": row["deleted_at"],
    }
    if include_item:
        result["item"] = json.loads(row["item_snapshot_json"]) if row["item_snapshot_json"] else {}
    return result


def _row_to_attempt(row: Any) -> dict[str, Any]:
    """将数据库行转为 attempt 字典。"""
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "attempt_number": row["attempt_number"],
        "status": row["status"],
        "prompt_id": row["prompt_id"],
        "api_json": row["api_json"],
        "error_message": row["error_message"],
        "error_type": row["error_type"],
        "started_at": row["started_at"],
        "submitted_at": row["submitted_at"],
        "completed_at": row["completed_at"],
        "revision": row["revision"],
        "created_at": row["created_at"],
    }
