"""阶段 3.2 跑图列表和批量配置。

提供草稿 CRUD、预览缓存和不可变批次快照能力：

1. 草稿（batch_drafts）：可编辑的范围 + 配置 + 预览缓存
   - 用户选择范围（项目/章节/大场景/小场景/分支/页面）
   - 批量设置实例数量、工作流、种子策略
   - 预览编译结果（缓存，配置变更后标记为过期）
2. 批次（batches）：用户确认后固化的不可变快照
   - 保存完整编译结果（items/blocking_errors/warnings/summary）
   - 状态机：pending → running → completed/cancelled/failed
   - 供阶段 3.3 持久化任务队列消费

设计原则：
- 草稿可变：配置和预览可反复更新
- 批次不可变：固化后 snapshot_json 不再改变，仅状态可更新
- 预览缓存：避免重复编译，配置变更自动标记过期
- 软删除：deleted_at 标记，不物理删除
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .compiler import VALID_SCOPES, VALID_SEED_STRATEGIES, compile_project


# ──────────────────────────────────────────────────────────────────
# 配置数据类
# ──────────────────────────────────────────────────────────────────


@dataclass
class BatchConfig:
    """批量配置。"""

    instance_count: int = 1
    seed_strategy: str = "fixed"
    seed_base: int | None = None
    workflow_id: str | None = None
    workflow_version_id: str | None = None
    skip_adopted: bool = False
    only_failed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance_count": self.instance_count,
            "seed_strategy": self.seed_strategy,
            "seed_base": self.seed_base,
            "workflow_id": self.workflow_id,
            "workflow_version_id": self.workflow_version_id,
            "skip_adopted": self.skip_adopted,
            "only_failed": self.only_failed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BatchConfig":
        data = data or {}
        return cls(
            instance_count=int(data.get("instance_count", 1)),
            seed_strategy=data.get("seed_strategy", "fixed"),
            seed_base=data.get("seed_base"),
            workflow_id=data.get("workflow_id"),
            workflow_version_id=data.get("workflow_version_id"),
            skip_adopted=bool(data.get("skip_adopted", False)),
            only_failed=bool(data.get("only_failed", False)),
        )

    def validate(self, *, scope: str | None = None) -> None:
        """校验配置，失败抛 ValueError。"""
        if scope is not None and scope not in VALID_SCOPES:
            raise ValueError(f"scope 无效，允许值: {', '.join(VALID_SCOPES)}")
        if self.seed_strategy not in VALID_SEED_STRATEGIES:
            raise ValueError(f"seed_strategy 无效，允许值: {', '.join(VALID_SEED_STRATEGIES)}")
        if self.instance_count < 1:
            raise ValueError("instance_count 必须 >= 1")
        if self.instance_count > 100:
            raise ValueError("instance_count 必须 <= 100")
        if self.seed_base is not None and self.seed_base < 0:
            raise ValueError("seed_base 必须 >= 0")


# ──────────────────────────────────────────────────────────────────
# 草稿 CRUD
# ──────────────────────────────────────────────────────────────────


def validate_scope(scope: str, scope_id: str | None) -> None:
    """校验范围参数。"""
    if scope not in VALID_SCOPES:
        raise ValueError(f"scope 无效，允许值: {', '.join(VALID_SCOPES)}")
    if scope != "project" and not scope_id:
        raise ValueError(f"scope={scope} 需要 scope_id")


def create_draft(
    manager: Any,
    project_id: str,
    *,
    name: str = "",
    scope: str = "project",
    scope_id: str | None = None,
    config: BatchConfig | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """创建草稿。"""
    validate_scope(scope, scope_id)
    # 验证项目存在
    with manager.connection(environment) as conn:
        proj = conn.execute(
            "SELECT id FROM projects WHERE id = ? AND deleted_at IS NULL",
            (project_id,),
        ).fetchone()
        if not proj:
            raise ValueError("项目不存在")

    config = config or BatchConfig()
    config.validate(scope=scope)

    draft_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    config_json = json.dumps(config.to_dict(), ensure_ascii=False)

    with manager.connection(environment) as conn:
        conn.execute(
            """
            INSERT INTO batch_drafts(
                id, project_id, name, scope, scope_id,
                config_json, preview_json, preview_stale,
                revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, 1, 1, ?, ?)
            """,
            (draft_id, project_id, name, scope, scope_id,
             config_json, now, now),
        )

    return get_draft(manager, draft_id, environment=environment)  # type: ignore[return-value]


def get_draft(
    manager: Any,
    draft_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取草稿详情。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            """
            SELECT id, project_id, name, scope, scope_id,
                   config_json, preview_json, preview_stale,
                   revision, created_at, updated_at, deleted_at
            FROM batch_drafts
            WHERE id = ? AND deleted_at IS NULL
            """,
            (draft_id,),
        ).fetchone()
        if not row:
            return None
        return _row_to_draft(row)


def list_drafts(
    manager: Any,
    project_id: str,
    *,
    include_deleted: bool = False,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出项目的草稿。"""
    with manager.connection(environment) as conn:
        if include_deleted:
            sql = """
                SELECT id, project_id, name, scope, scope_id,
                       config_json, preview_json, preview_stale,
                       revision, created_at, updated_at, deleted_at
                FROM batch_drafts
                WHERE project_id = ?
                ORDER BY updated_at DESC
            """
            rows = conn.execute(sql, (project_id,)).fetchall()
        else:
            sql = """
                SELECT id, project_id, name, scope, scope_id,
                       config_json, preview_json, preview_stale,
                       revision, created_at, updated_at, deleted_at
                FROM batch_drafts
                WHERE project_id = ? AND deleted_at IS NULL
                ORDER BY updated_at DESC
            """
            rows = conn.execute(sql, (project_id,)).fetchall()
        return [_row_to_draft(r) for r in rows]


def update_draft(
    manager: Any,
    draft_id: str,
    *,
    name: str | None = None,
    scope: str | None = None,
    scope_id: str | None = None,
    config: BatchConfig | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """更新草稿。任一字段为 None 表示不修改。"""
    current = get_draft(manager, draft_id, environment=environment)
    if not current:
        return None

    new_name = name if name is not None else current["name"]
    new_scope = scope if scope is not None else current["scope"]
    # scope_id 单独处理：传入空字符串表示清除，传入 None 表示不修改
    if scope_id is not None:
        new_scope_id = scope_id if scope_id else None
    else:
        new_scope_id = current["scope_id"]
    new_config_dict = config.to_dict() if config is not None else current["config"]

    # 校验
    validate_scope(new_scope, new_scope_id)
    cfg = BatchConfig.from_dict(new_config_dict)
    cfg.validate(scope=new_scope)

    # 判断是否需要标记预览过期
    stale_marker = 1  # 默认标记为过期
    if (config is None and scope is None and scope_id is None and name is not None):
        # 仅修改名称，预览不需要过期
        stale_marker = current["preview_stale"]

    now = datetime.now(timezone.utc).isoformat()
    config_json = json.dumps(new_config_dict, ensure_ascii=False)

    with manager.connection(environment) as conn:
        conn.execute(
            """
            UPDATE batch_drafts
            SET name = ?, scope = ?, scope_id = ?, config_json = ?,
                preview_stale = ?, revision = revision + 1, updated_at = ?
            WHERE id = ? AND deleted_at IS NULL
            """,
            (new_name, new_scope, new_scope_id, config_json,
             stale_marker, now, draft_id),
        )

    return get_draft(manager, draft_id, environment=environment)


def delete_draft(
    manager: Any,
    draft_id: str,
    *,
    environment: str | None = None,
) -> bool:
    """软删除草稿。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            "UPDATE batch_drafts SET deleted_at = ?, updated_at = ? "
            "WHERE id = ? AND deleted_at IS NULL",
            (now, now, draft_id),
        )
        return cursor.rowcount > 0


# ──────────────────────────────────────────────────────────────────
# 预览（编译并缓存）
# ──────────────────────────────────────────────────────────────────


def preview_draft(
    manager: Any,
    draft_id: str,
    *,
    force: bool = False,
    resolve_slots: bool = False,
    environment: str | None = None,
) -> dict[str, Any]:
    """编译草稿并缓存预览。

    如果预览未过期且非强制，直接返回缓存。
    """
    draft = get_draft(manager, draft_id, environment=environment)
    if not draft:
        raise ValueError("草稿不存在")

    if not force and not draft["preview_stale"] and draft["preview"]:
        return draft["preview"]

    config = BatchConfig.from_dict(draft["config"])
    result = compile_project(
        manager,
        draft["project_id"],
        scope=draft["scope"],
        scope_id=draft["scope_id"],
        instance_count=config.instance_count,
        seed_strategy=config.seed_strategy,
        seed_base=config.seed_base,
        workflow_id_override=config.workflow_id,
        workflow_version_id_override=config.workflow_version_id,
        skip_adopted=config.skip_adopted,
        only_failed=config.only_failed,
        environment=environment,
    )

    preview = result.to_dict()
    # 附加元信息
    preview["draft_id"] = draft_id
    preview["config"] = config.to_dict()
    preview["scope"] = draft["scope"]
    preview["scope_id"] = draft["scope_id"]

    preview_json = json.dumps(preview, ensure_ascii=False)
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        conn.execute(
            """
            UPDATE batch_drafts
            SET preview_json = ?, preview_stale = 0, updated_at = ?
            WHERE id = ? AND deleted_at IS NULL
            """,
            (preview_json, now, draft_id),
        )

    return preview


def invalidate_preview(
    manager: Any,
    draft_id: str,
    *,
    environment: str | None = None,
) -> None:
    """标记草稿预览为过期。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        conn.execute(
            "UPDATE batch_drafts SET preview_stale = 1, updated_at = ? "
            "WHERE id = ? AND deleted_at IS NULL",
            (now, draft_id),
        )


# ──────────────────────────────────────────────────────────────────
# 提交批次（不可变快照）
# ──────────────────────────────────────────────────────────────────


VALID_BATCH_STATUSES = ("pending", "running", "paused", "completed", "cancelled", "failed")


def commit_draft(
    manager: Any,
    draft_id: str,
    *,
    name: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """提交草稿为不可变批次。

    流程：
    1. 加载草稿
    2. 强制重新编译（确保最新快照）
    3. 固化到 batches 表，状态为 pending
    """
    draft = get_draft(manager, draft_id, environment=environment)
    if not draft:
        raise ValueError("草稿不存在")

    # 强制重新编译，确保快照最新
    preview = preview_draft(manager, draft_id, force=True, environment=environment)

    # 如果有阻塞错误，仍允许提交（用户可查看阻塞项后决定是否取消）
    batch_id = str(uuid4())
    batch_name = name if name is not None else draft["name"] or f"批次-{batch_id[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    config_json = json.dumps(draft["config"], ensure_ascii=False)
    snapshot_json = json.dumps(preview, ensure_ascii=False)
    item_count = len(preview.get("items", []))
    blocking_count = len(preview.get("blocking_errors", []))
    warning_count = len(preview.get("warnings", []))

    with manager.connection(environment) as conn:
        conn.execute(
            """
            INSERT INTO batches(
                id, project_id, draft_id, name, scope, scope_id,
                config_json, snapshot_json,
                item_count, blocking_count, warning_count,
                status, revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, ?, ?)
            """,
            (batch_id, draft["project_id"], draft_id, batch_name,
             draft["scope"], draft["scope_id"],
             config_json, snapshot_json,
             item_count, blocking_count, warning_count,
             now, now),
        )

    return get_batch(manager, batch_id, environment=environment)  # type: ignore[return-value]


# ──────────────────────────────────────────────────────────────────
# 批次 CRUD
# ──────────────────────────────────────────────────────────────────


def get_batch(
    manager: Any,
    batch_id: str,
    *,
    include_snapshot: bool = True,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取批次详情。"""
    with manager.connection(environment) as conn:
        cols = (
            "id, project_id, draft_id, name, scope, scope_id, config_json, "
            "snapshot_json, item_count, blocking_count, warning_count, "
            "status, revision, created_at, updated_at, deleted_at"
        ) if include_snapshot else (
            "id, project_id, draft_id, name, scope, scope_id, config_json, "
            "item_count, blocking_count, warning_count, "
            "status, revision, created_at, updated_at, deleted_at"
        )
        row = conn.execute(
            f"SELECT {cols} FROM batches WHERE id = ? AND deleted_at IS NULL",
            (batch_id,),
        ).fetchone()
        if not row:
            return None
        return _row_to_batch(row, include_snapshot=include_snapshot)


def list_batches(
    manager: Any,
    *,
    project_id: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出批次。"""
    if status is not None and status not in VALID_BATCH_STATUSES:
        raise ValueError(f"status 无效，允许值: {', '.join(VALID_BATCH_STATUSES)}")

    conditions = []
    params: list[Any] = []
    if project_id is not None:
        conditions.append("project_id = ?")
        params.append(project_id)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if not include_deleted:
        conditions.append("deleted_at IS NULL")

    where = " AND ".join(conditions) if conditions else "1=1"
    sql = f"""
        SELECT id, project_id, draft_id, name, scope, scope_id, config_json,
               item_count, blocking_count, warning_count,
               status, revision, created_at, updated_at, deleted_at
        FROM batches
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with manager.connection(environment) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_batch(r, include_snapshot=False) for r in rows]


def update_batch_status(
    manager: Any,
    batch_id: str,
    status: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """更新批次状态。"""
    if status not in VALID_BATCH_STATUSES:
        raise ValueError(f"status 无效，允许值: {', '.join(VALID_BATCH_STATUSES)}")

    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            "UPDATE batches SET status = ?, revision = revision + 1, updated_at = ? "
            "WHERE id = ? AND deleted_at IS NULL",
            (status, now, batch_id),
        )
        if cursor.rowcount == 0:
            return None
    return get_batch(manager, batch_id, include_snapshot=False, environment=environment)


def delete_batch(
    manager: Any,
    batch_id: str,
    *,
    environment: str | None = None,
) -> bool:
    """软删除批次。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            "UPDATE batches SET deleted_at = ?, updated_at = ? "
            "WHERE id = ? AND deleted_at IS NULL",
            (now, now, batch_id),
        )
        return cursor.rowcount > 0


# ──────────────────────────────────────────────────────────────────
# 行转换工具
# ──────────────────────────────────────────────────────────────────


def _row_to_draft(row: Any) -> dict[str, Any]:
    """将数据库行转为草稿字典。"""
    config = json.loads(row["config_json"]) if row["config_json"] else {}
    preview = json.loads(row["preview_json"]) if row["preview_json"] else None
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "scope": row["scope"],
        "scope_id": row["scope_id"],
        "config": config,
        "preview": preview,
        "preview_stale": bool(row["preview_stale"]),
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deleted_at": row["deleted_at"],
    }


def _row_to_batch(row: Any, *, include_snapshot: bool = True) -> dict[str, Any]:
    """将数据库行转为批数字典。"""
    config = json.loads(row["config_json"]) if row["config_json"] else {}
    result = {
        "id": row["id"],
        "project_id": row["project_id"],
        "draft_id": row["draft_id"],
        "name": row["name"],
        "scope": row["scope"],
        "scope_id": row["scope_id"],
        "config": config,
        "item_count": row["item_count"],
        "blocking_count": row["blocking_count"],
        "warning_count": row["warning_count"],
        "status": row["status"],
        "revision": row["revision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "deleted_at": row["deleted_at"],
    }
    if include_snapshot:
        snapshot = json.loads(row["snapshot_json"]) if row["snapshot_json"] else {}
        result["snapshot"] = snapshot
    return result
