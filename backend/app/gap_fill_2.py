"""Gap-Fill 2: 补全剩余后端缺口的业务逻辑。

覆盖模块：
- MOD-11: 可配置目录 + 回收站
- MOD-05: 工作流验证运行持久化
- MOD-04: 转场结构块 + 自动保存
- MOD-06: 阻塞项持久化 + 批次改名
- MOD-02: 素材模板 + 素材页引用模式
- MOD-03: 规格完整性检查 + 批量粘贴 + spec 预览图
- MOD-12: 从查询结果创建/关联人物

所有函数使用 ``manager.connection()`` 上下文管理器操作数据库，
与现有模块（output_receiver、gallery、maintenance 等）风格一致。
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────
# MOD-11: 可配置目录
# ──────────────────────────────────────────────────────────────────

DIRECTORY_SETTING_KEYS = (
    "directory.data_dir",
    "directory.images_dir",
    "directory.cache_dir",
    "directory.tmp_dir",
)

DIRECTORY_KEY_TO_LABEL = {
    "directory.data_dir": "data_dir",
    "directory.images_dir": "images_dir",
    "directory.cache_dir": "cache_dir",
    "directory.tmp_dir": "tmp_dir",
}


def get_directory_settings(manager: Any, *, environment: str | None = None) -> dict[str, Any]:
    """读取目录配置。空字符串表示使用默认（data_root 派生）路径。"""
    raw = manager.get_settings("directory.", environment=environment)
    result: dict[str, str] = {}
    for key, label in DIRECTORY_KEY_TO_LABEL.items():
        result[label] = raw.get(key, "")
    result["data_root"] = str(manager.data_root)
    # 计算实际生效路径
    result["resolved"] = _resolve_all_directories(manager)
    return result


def _resolve_all_directories(manager: Any) -> dict[str, str]:
    """返回实际生效的目录路径（配置优先，否则从 data_root 派生）。"""
    raw = manager.get_settings("directory.")
    data_root = manager.data_root
    resolved: dict[str, str] = {
        "data_dir": str(data_root),
        "images_dir": str(data_root / "storage" / "images"),
        "cache_dir": str(data_root / "cache"),
        "tmp_dir": str(data_root / "tmp"),
    }
    for key, label in DIRECTORY_KEY_TO_LABEL.items():
        value = raw.get(key, "")
        if value and value.strip():
            resolved[label] = str(Path(value).resolve())
    return resolved


def set_directory_settings(
    manager: Any,
    *,
    data_dir: str | None = None,
    images_dir: str | None = None,
    cache_dir: str | None = None,
    tmp_dir: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """更新目录配置。传入 None 表示不修改，传入空字符串表示恢复默认。"""
    updates = {
        "directory.data_dir": data_dir,
        "directory.images_dir": images_dir,
        "directory.cache_dir": cache_dir,
        "directory.tmp_dir": tmp_dir,
    }
    for key, value in updates.items():
        if value is not None:
            manager.set_setting(key, value.strip(), environment=environment)
    return get_directory_settings(manager, environment=environment)


def check_directory_access(path: str | Path) -> dict[str, Any]:
    """检查目录路径的权限、空间和可写性。

    返回 {"writable": bool, "exists": bool, "error": str|None, "free_bytes": int|None}。
    """
    p = Path(path)
    result: dict[str, Any] = {
        "path": str(p),
        "exists": p.exists(),
        "writable": False,
        "free_bytes": None,
        "error": None,
    }
    try:
        # 确保目录存在（或其父目录存在以便后续创建）
        if not p.exists():
            # 检查父目录是否可写
            parent = p.parent if p.parent != p else p
            if not parent.exists():
                result["error"] = f"父目录不存在: {parent}"
                return result
            test_file = parent / ".atelier_dir_check"
            test_file.touch()
            test_file.unlink()
            result["writable"] = True
        else:
            test_file = p / ".atelier_dir_check"
            test_file.touch()
            test_file.unlink()
            result["writable"] = True
        # 尝试获取剩余空间
        try:
            usage = shutil.disk_usage(p if p.exists() else p.parent)
            result["free_bytes"] = usage.free
        except (OSError, RuntimeError):
            pass
    except PermissionError:
        result["error"] = "权限不足"
    except OSError as exc:
        result["error"] = str(exc)
    return result


# ──────────────────────────────────────────────────────────────────
# MOD-11: 回收站
# ──────────────────────────────────────────────────────────────────

VALID_RECYCLE_ENTITY_TYPES = (
    "project",
    "chapter",
    "large_scene",
    "small_scene",
    "shot_page",
    "material",
    "material_page",
    "character",
    "character_variant",
    "workflow",
    "workflow_version",
    "batch",
)


def add_to_recycle_bin(
    manager: Any,
    *,
    entity_type: str,
    entity_id: str,
    entity_name: str = "",
    source_table: str,
    payload_json: str | dict | None = None,
    expires_at: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """将一个被软删的实体登记到回收站。"""
    if entity_type not in VALID_RECYCLE_ENTITY_TYPES:
        raise ValueError(f"entity_type 必须是 {VALID_RECYCLE_ENTITY_TYPES} 之一")
    if isinstance(payload_json, dict):
        payload_json = json.dumps(payload_json, ensure_ascii=False)
    entry_id = str(uuid4())
    now = _now_iso()
    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO recycle_bin(
                id, entity_type, entity_id, entity_name, source_table,
                payload_json, deleted_at, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                entity_name = excluded.entity_name,
                source_table = excluded.source_table,
                payload_json = excluded.payload_json,
                deleted_at = excluded.deleted_at,
                expires_at = excluded.expires_at
            """,
            (entry_id, entity_type, entity_id, entity_name, source_table,
             payload_json, now, expires_at, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM recycle_bin WHERE entity_type = ? AND entity_id = ?",
            (entity_type, entity_id),
        ).fetchone()
    return dict(row) if row else {}


def list_recycle_bin(
    manager: Any,
    *,
    entity_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    environment: str | None = None,
) -> dict[str, Any]:
    """列出回收站条目，支持按类型筛选和分页。"""
    query = "SELECT * FROM recycle_bin"
    params: list[Any] = []
    if entity_type:
        query += " WHERE entity_type = ?"
        params.append(entity_type)
    query += " ORDER BY deleted_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM recycle_bin"
            + (" WHERE entity_type = ?" if entity_type else ""),
            (entity_type,) if entity_type else (),
        ).fetchone()["c"]
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def restore_from_recycle_bin(
    manager: Any,
    entry_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """从回收站恢复条目（仅移除回收站记录，实际恢复由业务模块处理）。

    返回回收站条目的 payload，供业务模块恢复数据使用。
    """
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM recycle_bin WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM recycle_bin WHERE id = ?", (entry_id,))
        conn.commit()
    return dict(row)


def purge_recycle_bin(
    manager: Any,
    *,
    entry_id: str | None = None,
    entity_type: str | None = None,
    older_than_days: int | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """彻底清除回收站条目。支持按 ID、类型或保留天数清除。"""
    query = "DELETE FROM recycle_bin"
    conditions: list[str] = []
    params: list[Any] = []
    if entry_id:
        conditions.append("id = ?")
        params.append(entry_id)
    if entity_type:
        conditions.append("entity_type = ?")
        params.append(entity_type)
    if older_than_days is not None:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        conditions.append("deleted_at < ?")
        params.append(cutoff)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    with manager.connection(environment) as conn:
        cursor = conn.execute(query, params)
        deleted = cursor.rowcount
        conn.commit()
    return {"purged": deleted}


# ──────────────────────────────────────────────────────────────────
# MOD-05: 工作流验证运行持久化
# ──────────────────────────────────────────────────────────────────

VALID_RUN_TYPES = ("precheck", "validate", "dry_run")
VALID_RUN_STATUSES = ("pending", "running", "passed", "failed", "error")


def create_validation_run(
    manager: Any,
    *,
    workflow_id: str | None = None,
    workflow_version_id: str | None = None,
    draft_id: str | None = None,
    run_type: str = "precheck",
    environment: str | None = None,
) -> dict[str, Any]:
    """创建一条工作流验证运行记录。"""
    if run_type not in VALID_RUN_TYPES:
        raise ValueError(f"run_type 必须是 {VALID_RUN_TYPES} 之一")
    run_id = str(uuid4())
    now = _now_iso()
    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO workflow_validation_runs(
                id, workflow_id, workflow_version_id, draft_id, run_type,
                status, errors_json, warnings_json, node_count, connection_count,
                duration_ms, comfyui_response_json, started_at, completed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', '[]', '[]', 0, 0, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (run_id, workflow_id, workflow_version_id, draft_id, run_type, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM workflow_validation_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return dict(row) if row else {}


def update_validation_run(
    manager: Any,
    run_id: str,
    *,
    status: str | None = None,
    errors: list | None = None,
    warnings: list | None = None,
    node_count: int | None = None,
    connection_count: int | None = None,
    duration_ms: int | None = None,
    comfyui_response: dict | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """更新验证运行记录。"""
    if status is not None and status not in VALID_RUN_STATUSES:
        raise ValueError(f"status 必须是 {VALID_RUN_STATUSES} 之一")
    updates: list[str] = []
    params: list[Any] = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status in ("passed", "failed", "error"):
            updates.append("completed_at = ?")
            params.append(_now_iso())
    if errors is not None:
        updates.append("errors_json = ?")
        params.append(json.dumps(errors, ensure_ascii=False))
    if warnings is not None:
        updates.append("warnings_json = ?")
        params.append(json.dumps(warnings, ensure_ascii=False))
    if node_count is not None:
        updates.append("node_count = ?")
        params.append(node_count)
    if connection_count is not None:
        updates.append("connection_count = ?")
        params.append(connection_count)
    if duration_ms is not None:
        updates.append("duration_ms = ?")
        params.append(duration_ms)
    if comfyui_response is not None:
        updates.append("comfyui_response_json = ?")
        params.append(json.dumps(comfyui_response, ensure_ascii=False))
    if not updates:
        return get_validation_run(manager, run_id, environment=environment)
    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(run_id)
    with manager.connection(environment) as conn:
        conn.execute(
            f"UPDATE workflow_validation_runs SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM workflow_validation_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def get_validation_run(
    manager: Any,
    run_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取单条验证运行记录。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM workflow_validation_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def list_validation_runs(
    manager: Any,
    *,
    workflow_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    environment: str | None = None,
) -> dict[str, Any]:
    """列出验证运行记录。"""
    query = "SELECT * FROM workflow_validation_runs"
    conditions: list[str] = []
    params: list[Any] = []
    if workflow_id:
        conditions.append("workflow_id = ?")
        params.append(workflow_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
        count_query = "SELECT COUNT(*) AS c FROM workflow_validation_runs"
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions)
        total = conn.execute(count_query, params[:-2] if len(params) >= 2 else params).fetchone()["c"]
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ──────────────────────────────────────────────────────────────────
# MOD-04: 转场结构块
# ──────────────────────────────────────────────────────────────────

VALID_TRANSITION_TYPES = (
    "cut", "fade", "dissolve", "wipe", "slide", "zoom", "custom",
)


def create_transition_block(
    manager: Any,
    *,
    project_id: str,
    source_page_id: str | None = None,
    target_page_id: str | None = None,
    transition_type: str = "cut",
    duration_frames: int = 0,
    in_frame: int | None = None,
    out_frame: int | None = None,
    params: dict | None = None,
    sort_order: int = 0,
    environment: str | None = None,
) -> dict[str, Any]:
    """创建转场结构块。"""
    if transition_type not in VALID_TRANSITION_TYPES:
        raise ValueError(f"transition_type 必须是 {VALID_TRANSITION_TYPES} 之一")
    block_id = str(uuid4())
    now = _now_iso()
    params_json = json.dumps(params or {}, ensure_ascii=False)
    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO transition_blocks(
                id, project_id, source_page_id, target_page_id, transition_type,
                duration_frames, in_frame, out_frame, params_json, sort_order,
                revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (block_id, project_id, source_page_id, target_page_id, transition_type,
             duration_frames, in_frame, out_frame, params_json, sort_order, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM transition_blocks WHERE id = ?", (block_id,)
        ).fetchone()
    return dict(row) if row else {}


def list_transition_blocks(
    manager: Any,
    project_id: str,
    *,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出项目的所有转场结构块。"""
    with manager.connection(environment) as conn:
        rows = conn.execute(
            "SELECT * FROM transition_blocks WHERE project_id = ? ORDER BY sort_order, created_at",
            (project_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_transition_block(
    manager: Any,
    block_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取单个转场结构块。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM transition_blocks WHERE id = ?", (block_id,)
        ).fetchone()
    return dict(row) if row else None


def update_transition_block(
    manager: Any,
    block_id: str,
    *,
    transition_type: str | None = None,
    duration_frames: int | None = None,
    in_frame: int | None = None,
    out_frame: int | None = None,
    params: dict | None = None,
    sort_order: int | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """更新转场结构块。"""
    if transition_type is not None and transition_type not in VALID_TRANSITION_TYPES:
        raise ValueError(f"transition_type 必须是 {VALID_TRANSITION_TYPES} 之一")
    updates: list[str] = []
    params_list: list[Any] = []
    if transition_type is not None:
        updates.append("transition_type = ?")
        params_list.append(transition_type)
    if duration_frames is not None:
        updates.append("duration_frames = ?")
        params_list.append(duration_frames)
    if in_frame is not None:
        updates.append("in_frame = ?")
        params_list.append(in_frame)
    if out_frame is not None:
        updates.append("out_frame = ?")
        params_list.append(out_frame)
    if params is not None:
        updates.append("params_json = ?")
        params_list.append(json.dumps(params, ensure_ascii=False))
    if sort_order is not None:
        updates.append("sort_order = ?")
        params_list.append(sort_order)
    if not updates:
        return get_transition_block(manager, block_id, environment=environment)
    updates.append("updated_at = ?")
    params_list.append(_now_iso())
    params_list.append(block_id)
    with manager.connection(environment) as conn:
        conn.execute(
            f"UPDATE transition_blocks SET {', '.join(updates)} WHERE id = ?",
            params_list,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM transition_blocks WHERE id = ?", (block_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_transition_block(
    manager: Any,
    block_id: str,
    *,
    environment: str | None = None,
) -> bool:
    """删除转场结构块。"""
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            "DELETE FROM transition_blocks WHERE id = ?", (block_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


# ──────────────────────────────────────────────────────────────────
# MOD-04: 自动保存
# ──────────────────────────────────────────────────────────────────

VALID_AUTOSAVE_ENTITY_TYPES = (
    "shot_page", "small_scene", "large_scene", "chapter",
    "branch", "material_page", "project",
)


def create_autosave_snapshot(
    manager: Any,
    *,
    project_id: str,
    entity_type: str,
    entity_id: str,
    operation_type: str = "update",
    payload: dict | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """创建自动保存快照。"""
    if entity_type not in VALID_AUTOSAVE_ENTITY_TYPES:
        raise ValueError(f"entity_type 必须是 {VALID_AUTOSAVE_ENTITY_TYPES} 之一")
    snap_id = str(uuid4())
    now = _now_iso()
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO autosave_snapshots(
                id, project_id, entity_type, entity_id, operation_type,
                payload_json, is_recovered, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (snap_id, project_id, entity_type, entity_id, operation_type, payload_json, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM autosave_snapshots WHERE id = ?", (snap_id,)
        ).fetchone()
    return dict(row) if row else {}


def list_autosave_snapshots(
    manager: Any,
    project_id: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    environment: str | None = None,
) -> dict[str, Any]:
    """列出自动保存快照。"""
    query = "SELECT * FROM autosave_snapshots WHERE project_id = ?"
    params: list[Any] = [project_id]
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    if entity_id:
        query += " AND entity_id = ?"
        params.append(entity_id)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    # 计数查询必须应用同样的过滤条件，否则 total 与 items 数量不一致
    count_query = "SELECT COUNT(*) AS c FROM autosave_snapshots WHERE project_id = ?"
    count_params: list[Any] = [project_id]
    if entity_type:
        count_query += " AND entity_type = ?"
        count_params.append(entity_type)
    if entity_id:
        count_query += " AND entity_id = ?"
        count_params.append(entity_id)
    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
        total = conn.execute(count_query, count_params).fetchone()["c"]
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_latest_autosave(
    manager: Any,
    project_id: str,
    entity_type: str,
    entity_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取指定实体的最新自动保存快照。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            """SELECT * FROM autosave_snapshots
               WHERE project_id = ? AND entity_type = ? AND entity_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (project_id, entity_type, entity_id),
        ).fetchone()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────────
# MOD-06: 阻塞项持久化
# ──────────────────────────────────────────────────────────────────

VALID_ISSUE_SEVERITIES = ("error", "warning", "info")
VALID_ISSUE_STATUSES = ("open", "resolved", "ignored")


def create_blocking_issue(
    manager: Any,
    *,
    project_id: str,
    batch_id: str | None = None,
    severity: str = "error",
    category: str = "general",
    page_id: str | None = None,
    field_path: str | None = None,
    message: str,
    detail: dict | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """创建阻塞项记录。"""
    if severity not in VALID_ISSUE_SEVERITIES:
        raise ValueError(f"severity 必须是 {VALID_ISSUE_SEVERITIES} 之一")
    issue_id = str(uuid4())
    now = _now_iso()
    detail_json = json.dumps(detail or {}, ensure_ascii=False)
    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO blocking_issues(
                id, project_id, batch_id, severity, category, page_id,
                field_path, message, detail_json, status, resolved_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL, ?, ?)
            """,
            (issue_id, project_id, batch_id, severity, category, page_id,
             field_path, message, detail_json, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM blocking_issues WHERE id = ?", (issue_id,)
        ).fetchone()
    return dict(row) if row else {}


def list_blocking_issues(
    manager: Any,
    *,
    project_id: str | None = None,
    batch_id: str | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
    environment: str | None = None,
) -> dict[str, Any]:
    """列出阻塞项。"""
    query = "SELECT * FROM blocking_issues"
    conditions: list[str] = []
    params: list[Any] = []
    if project_id:
        conditions.append("project_id = ?")
        params.append(project_id)
    if batch_id:
        conditions.append("batch_id = ?")
        params.append(batch_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
        count_query = "SELECT COUNT(*) AS c FROM blocking_issues"
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions)
        total = conn.execute(count_query, params[:-2] if len(params) >= 2 else params).fetchone()["c"]
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def update_blocking_issue(
    manager: Any,
    issue_id: str,
    *,
    status: str | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """更新阻塞项状态。"""
    if status is not None and status not in VALID_ISSUE_STATUSES:
        raise ValueError(f"status 必须是 {VALID_ISSUE_STATUSES} 之一")
    updates: list[str] = ["updated_at = ?"]
    params: list[Any] = [_now_iso()]
    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status in ("resolved", "ignored"):
            updates.append("resolved_at = ?")
            params.append(_now_iso())
    params.append(issue_id)
    with manager.connection(environment) as conn:
        conn.execute(
            f"UPDATE blocking_issues SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM blocking_issues WHERE id = ?", (issue_id,)
        ).fetchone()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────────
# MOD-02: 素材模板（镜头模板/场景包/转场包）
# ──────────────────────────────────────────────────────────────────

VALID_TEMPLATE_TYPES = ("shot_template", "scene_pack", "transition_pack")


def create_material_template(
    manager: Any,
    *,
    name: str,
    template_type: str = "shot_template",
    description: str = "",
    pages: list | None = None,
    tags: list | None = None,
    preview_file_id: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """创建素材模板。"""
    if template_type not in VALID_TEMPLATE_TYPES:
        raise ValueError(f"template_type 必须是 {VALID_TEMPLATE_TYPES} 之一")
    tpl_id = str(uuid4())
    now = _now_iso()
    pages_json = json.dumps(pages or [], ensure_ascii=False)
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO material_templates(
                id, name, template_type, description, pages_json, tags_json,
                preview_file_id, is_archived, revision, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
            """,
            (tpl_id, name, template_type, description, pages_json, tags_json,
             preview_file_id, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM material_templates WHERE id = ?", (tpl_id,)
        ).fetchone()
    return dict(row) if row else {}


def list_material_templates(
    manager: Any,
    *,
    template_type: str | None = None,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
    environment: str | None = None,
) -> dict[str, Any]:
    """列出素材模板。"""
    query = "SELECT * FROM material_templates"
    conditions: list[str] = []
    params: list[Any] = []
    if template_type:
        conditions.append("template_type = ?")
        params.append(template_type)
    if not include_archived:
        conditions.append("is_archived = 0")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
        count_query = "SELECT COUNT(*) AS c FROM material_templates"
        if conditions:
            count_query += " WHERE " + " AND ".join(conditions)
        total = conn.execute(count_query, params[:-2] if len(params) >= 2 else params).fetchone()["c"]
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_material_template(
    manager: Any,
    template_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取单个素材模板。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM material_templates WHERE id = ?", (template_id,)
        ).fetchone()
    return dict(row) if row else None


def update_material_template(
    manager: Any,
    template_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    pages: list | None = None,
    tags: list | None = None,
    preview_file_id: str | None = None,
    is_archived: int | None = None,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """更新素材模板。"""
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if pages is not None:
        updates.append("pages_json = ?")
        params.append(json.dumps(pages, ensure_ascii=False))
    if tags is not None:
        updates.append("tags_json = ?")
        params.append(json.dumps(tags, ensure_ascii=False))
    if preview_file_id is not None:
        updates.append("preview_file_id = ?")
        params.append(preview_file_id)
    if is_archived is not None:
        updates.append("is_archived = ?")
        params.append(is_archived)
    if not updates:
        return get_material_template(manager, template_id, environment=environment)
    updates.append("updated_at = ?")
    params.append(_now_iso())
    params.append(template_id)
    with manager.connection(environment) as conn:
        conn.execute(
            f"UPDATE material_templates SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM material_templates WHERE id = ?", (template_id,)
        ).fetchone()
    return dict(row) if row else None


def delete_material_template(
    manager: Any,
    template_id: str,
    *,
    environment: str | None = None,
) -> bool:
    """删除素材模板。"""
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            "DELETE FROM material_templates WHERE id = ?", (template_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


# ──────────────────────────────────────────────────────────────────
# MOD-02: 素材页引用模式
# ──────────────────────────────────────────────────────────────────

VALID_REFERENCE_MODES = ("independent", "link")


def set_material_page_reference_mode(
    manager: Any,
    page_id: str,
    mode: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """设置素材页的引用模式。"""
    if mode not in VALID_REFERENCE_MODES:
        raise ValueError(f"mode 必须是 {VALID_REFERENCE_MODES} 之一")
    now = _now_iso()
    with manager.connection(environment) as conn:
        conn.execute(
            "UPDATE material_pages SET reference_mode = ?, updated_at = ? WHERE id = ?",
            (mode, now, page_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM material_pages WHERE id = ?", (page_id,)
        ).fetchone()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────────
# MOD-03: 规格完整性检查
# ──────────────────────────────────────────────────────────────────

def check_spec_completeness(
    manager: Any,
    character_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """检查人物规格完整性，返回每个变体×规格的缺失项。

    检查项：
    - prompt 是否为空
    - lora_name 是否为空
    - preview 是否已上传
    """
    with manager.connection(environment) as conn:
        variants = conn.execute(
            "SELECT id, name FROM character_variants WHERE character_id = ?",
            (character_id,),
        ).fetchall()
        specs = conn.execute(
            "SELECT id, spec_type, custom_label FROM specs ORDER BY sort_order"
        ).fetchall()
        # 查询已有的 spec_values
        values = conn.execute(
            """SELECT csv.variant_id, csv.spec_id, csv.prompt, csv.lora_name,
                      csv.preview_original_path
               FROM character_spec_values csv
               JOIN character_variants cv ON cv.id = csv.variant_id
               WHERE cv.character_id = ?""",
            (character_id,),
        ).fetchall()

    # 构建矩阵
    matrix: dict[str, dict[str, dict]] = {}
    for v in variants:
        matrix[v["id"]] = {"name": v["name"], "specs": {}}
    for s in specs:
        spec_label = s["custom_label"] or s["spec_type"]
        for v_id in matrix:
            matrix[v_id]["specs"][s["id"]] = {
                "name": spec_label, "missing": [], "has_value": False
            }

    for row in values:
        v_id = row["variant_id"]
        s_id = row["spec_id"]
        if v_id not in matrix or s_id not in matrix[v_id]["specs"]:
            continue
        entry = matrix[v_id]["specs"][s_id]
        entry["has_value"] = True
        missing: list[str] = []
        if not row["prompt"]:
            missing.append("prompt")
        if not row["lora_name"]:
            missing.append("lora_name")
        if not row["preview_original_path"]:
            missing.append("preview")
        entry["missing"] = missing

    # 统计
    total_cells = sum(len(v["specs"]) for v in matrix.values())
    filled_cells = sum(
        1 for v in matrix.values() for s in v["specs"].values() if s["has_value"]
    )
    incomplete_cells = sum(
        1 for v in matrix.values() for s in v["specs"].values()
        if s["has_value"] and s["missing"]
    )
    empty_cells = total_cells - filled_cells

    return {
        "character_id": character_id,
        "matrix": matrix,
        "summary": {
            "total_variants": len(variants),
            "total_specs": len(specs),
            "total_cells": total_cells,
            "filled_cells": filled_cells,
            "empty_cells": empty_cells,
            "incomplete_cells": incomplete_cells,
        },
    }


# ──────────────────────────────────────────────────────────────────
# MOD-03: 批量粘贴 spec_value
# ──────────────────────────────────────────────────────────────────

def batch_paste_spec_values(
    manager: Any,
    *,
    character_id: str,
    variant_id: str,
    spec_values: list[dict[str, Any]],
    environment: str | None = None,
) -> dict[str, Any]:
    """批量创建或更新 spec_value。

    每项格式: {"spec_type": "age", "custom_label": "成年", "prompt": "...", "lora_name": "...", ...}

    按 spec_type + custom_label 查找或创建 specs 记录，
    然后 upsert character_spec_values（variant_id + spec_id）。
    """
    now = _now_iso()
    created = 0
    updated = 0
    errors: list[str] = []
    with manager.connection(environment) as conn:
        for item in spec_values:
            spec_type = item.get("spec_type", "").strip()
            custom_label = item.get("custom_label", "").strip()
            if not spec_type:
                errors.append("缺少 spec_type")
                continue
            # 查找或创建 specs 记录
            spec_row = conn.execute(
                "SELECT id FROM specs WHERE spec_type = ? AND custom_label = ?",
                (spec_type, custom_label),
            ).fetchone()
            if spec_row:
                spec_id = spec_row["id"]
            else:
                spec_id = str(uuid4())
                max_order = conn.execute(
                    "SELECT MAX(sort_order) as m FROM specs"
                ).fetchone()
                sort_order = (max_order["m"] or 0) + 1 if max_order and max_order["m"] is not None else 1
                conn.execute(
                    """INSERT INTO specs(
                        id, spec_type, custom_label, description,
                        is_required, default_value, sort_order, created_at, updated_at
                    ) VALUES (?, ?, ?, '', 0, '', ?, ?, ?)
                    """,
                    (spec_id, spec_type, custom_label, sort_order, now, now),
                )
            # 查找或创建 character_spec_values
            csv_row = conn.execute(
                "SELECT id FROM character_spec_values WHERE variant_id = ? AND spec_id = ?",
                (variant_id, spec_id),
            ).fetchone()
            if csv_row:
                # 更新
                csv_id = csv_row["id"]
                updates: list[str] = []
                params: list[Any] = []
                for field in ("prompt", "lora_name", "lora_weight", "model_override", "notes"):
                    if field in item:
                        updates.append(f"{field} = ?")
                        params.append(item[field])
                updates.append("updated_at = ?")
                params.append(now)
                params.append(csv_id)
                conn.execute(
                    f"UPDATE character_spec_values SET {', '.join(updates)} WHERE id = ?",
                    params,
                )
                updated += 1
            else:
                # 创建
                csv_id = str(uuid4())
                conn.execute(
                    """INSERT INTO character_spec_values(
                        id, variant_id, spec_id,
                        prompt, lora_name, lora_weight, model_override, notes,
                        preview_original_path, preview_thumbnail_path,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                    """,
                    (csv_id, variant_id, spec_id,
                     item.get("prompt", ""), item.get("lora_name", ""),
                     item.get("lora_weight"), item.get("model_override", ""),
                     item.get("notes", ""), now, now),
                )
                created += 1
        conn.commit()
    return {
        "character_id": character_id,
        "variant_id": variant_id,
        "created": created,
        "updated": updated,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────────
# MOD-03: spec_value 预览图上传
# ──────────────────────────────────────────────────────────────────

def upload_spec_value_preview(
    manager: Any,
    spec_value_id: str,
    *,
    file_data: bytes,
    filename: str,
    storage_dir: Path,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """上传 spec_value 的预览图。

    保存原图和缩略图到 storage_dir，更新 spec_value 记录。
    """
    from PIL import Image
    now = _now_iso()
    # 生成存储键
    ext = Path(filename).suffix or ".png"
    original_key = f"spec_{spec_value_id}_preview{ext}"
    thumb_key = f"spec_{spec_value_id}_preview_thumb.webp"
    original_path = storage_dir / original_key
    thumb_path = storage_dir / thumb_key

    # 保存原图
    storage_dir.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(file_data)

    # 生成缩略图
    try:
        with Image.open(original_path) as img:
            img.thumbnail((256, 256))
            img.save(thumb_path, format="WEBP", quality=80)
    except Exception:
        thumb_path = original_path  # 降级使用原图

    with manager.connection(environment) as conn:
        conn.execute(
            """UPDATE character_spec_values
               SET preview_original_path = ?, preview_thumbnail_path = ?, updated_at = ?
               WHERE id = ?""",
            (str(original_path), str(thumb_path), now, spec_value_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM character_spec_values WHERE id = ?", (spec_value_id,)
        ).fetchone()
    return dict(row) if row else None


# ──────────────────────────────────────────────────────────────────
# MOD-12: 从查询结果创建/关联人物
# ──────────────────────────────────────────────────────────────────

def link_query_record_to_character(
    manager: Any,
    *,
    record_id: str,
    character_id: str | None = None,
    character_name: str | None = None,
    project_id: str | None = None,
    record_name: str = "",
    environment: str | None = None,
) -> dict[str, Any]:
    """将角色查询库中的记录关联到人物库。

    角色查询库使用独立的 SQLite 数据库（character_database 模块），
    本函数只在主数据库中保存关联映射，不直接查询角色查询库。

    如果 character_id 不提供但 character_name 提供，则创建新人物。
    """
    now = _now_iso()

    # 创建新人物或使用已有
    if not character_id and character_name:
        character_id = str(uuid4())
        with manager.connection(environment) as conn:
            conn.execute(
                """INSERT INTO characters(
                    id, name, description, cover_path, archived_at,
                    source, source_identifier, external_url,
                    sort_order, revision, created_at, updated_at, deleted_at
                ) VALUES (?, ?, '', NULL, NULL, '', NULL, NULL, 0, 1, ?, ?, NULL)
                """,
                (character_id, character_name, now, now),
            )
            if project_id:
                conn.execute(
                    """INSERT INTO project_characters(
                        character_id, project_id, created_at
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(character_id, project_id) DO NOTHING
                    """,
                    (character_id, project_id, now),
                )
            conn.commit()
    elif not character_id:
        raise ValueError("必须提供 character_id 或 character_name")

    # 保存关联映射
    mapping_key = f"character_link.{record_id}"
    mapping_value = json.dumps({
        "record_id": record_id,
        "character_id": character_id,
        "record_name": record_name,
        "linked_at": now,
    }, ensure_ascii=False)
    manager.set_setting(mapping_key, mapping_value, environment=environment)

    return {
        "record_id": record_id,
        "character_id": character_id,
        "record_name": record_name,
        "linked": True,
    }


def get_linked_character_for_record(
    manager: Any,
    record_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """查询记录是否已关联人物。"""
    mapping_key = f"character_link.{record_id}"
    value = manager.get_setting(mapping_key, environment=environment)
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None
