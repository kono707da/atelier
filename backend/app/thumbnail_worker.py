"""缩略图生成 worker。

消费 ``background_jobs`` 表中 ``job_type='thumbnail'`` 的任务，读取原图，
缩放到目标尺寸（按短边对齐），输出 WebP，写入 ``storage/thumbnails/<size_class>/<file_id>.webp``，
并在 ``thumbnails`` 表中登记。

设计要点：
- 单次只领取一个任务，设置租约防止重复执行。
- 失败时记录 error 并回退到 ``pending``（最多重试 5 次后置为 ``failed``）。
- 原图缺失（``files.state='missing'`` 或文件不存在）直接置为 ``failed``，不重试。
- 支持手动调用 ``run_thumbnail_worker_once`` 执行一次循环，或通过 API 触发。
- WebP 质量 80，缩略图按短边对齐，保持原宽高比，最大尺寸受 ``size_class`` 限制。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────


THUMBNAIL_FORMAT = "WEBP"
THUMBNAIL_QUALITY = 80
THUMBNAIL_LEASE_SECONDS = 120
THUMBNAIL_MAX_RETRIES = 5

# size_class 字符串 -> 目标短边像素
SIZE_CLASS_TO_PX: dict[str, int] = {
    "256": 256,
    "640": 640,
}


# ──────────────────────────────────────────────────────────────────
# 缩略图文件路径
# ──────────────────────────────────────────────────────────────────


def thumbnail_storage_root(manager: Any) -> Path:
    """缩略图存储根目录：``<data_root>/storage/thumbnails``。"""
    return Path(manager.data_root) / "storage" / "thumbnails"


def thumbnail_path_for(
    manager: Any, file_id: str, size_class: str
) -> Path:
    """单个缩略图的存储路径：``<root>/<size_class>/<file_id>.webp``。"""
    return thumbnail_storage_root(manager) / size_class / f"{file_id}.webp"


# ──────────────────────────────────────────────────────────────────
# 任务领取与执行
# ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lease_until_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def claim_thumbnail_job(
    manager: Any,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """领取一个 pending 或租约过期的 thumbnail 任务。

    返回任务行（dict），或 None 表示无任务可领。
    同时处理重试次数：超过 ``THUMBNAIL_MAX_RETRIES`` 的任务直接置为 ``failed``。
    """
    now = _now_iso()
    with manager.connection(environment) as conn:
        # 先把超过最大重试次数的 pending 任务置为 failed
        conn.execute(
            """
            UPDATE background_jobs
            SET status = 'failed',
                error_json = json_object('reason', 'max_retries_exceeded'),
                updated_at = ?
            WHERE job_type = 'thumbnail'
              AND status = 'pending'
              AND CAST(json_extract(payload_json, '$.retry_count') AS INTEGER) >= ?
            """,
            (now, THUMBNAIL_MAX_RETRIES),
        )

        # 领取一个 pending 或租约过期的任务
        row = conn.execute(
            """
            SELECT * FROM background_jobs
            WHERE job_type = 'thumbnail'
              AND (status = 'pending'
                   OR (status = 'running' AND lease_until < ?))
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (now,),
        ).fetchone()

        if row is None:
            conn.commit()
            return None

        job = dict(row)
        conn.execute(
            """
            UPDATE background_jobs
            SET status = 'running',
                lease_until = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (_lease_until_iso(THUMBNAIL_LEASE_SECONDS), now, job["id"]),
        )
        conn.commit()
        job["status"] = "running"
        job["lease_until"] = _lease_until_iso(THUMBNAIL_LEASE_SECONDS)
        return job


def _complete_job(
    conn: Any,
    job_id: str,
    *,
    result: dict[str, Any],
) -> None:
    now = _now_iso()
    conn.execute(
        """
        UPDATE background_jobs
        SET status = 'completed',
            result_json = ?,
            lease_until = NULL,
            error_json = NULL,
            updated_at = ?
        WHERE id = ?
        """,
        (json.dumps(result, ensure_ascii=False), now, job_id),
    )


def _fail_job(
    conn: Any,
    job_id: str,
    *,
    reason: str,
    permanent: bool = False,
) -> None:
    """失败处理：permanent=True 直接 failed；否则回退 pending 并累加 retry_count。"""
    now = _now_iso()
    if permanent:
        conn.execute(
            """
            UPDATE background_jobs
            SET status = 'failed',
                error_json = json_object('reason', ?),
                lease_until = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (reason, now, job_id),
        )
        return

    # 回退到 pending 并累加重试次数
    conn.execute(
        """
        UPDATE background_jobs
        SET status = 'pending',
            lease_until = NULL,
            error_json = json_object('reason', ?),
            payload_json = json_set(
                payload_json,
                '$.retry_count',
                CAST(COALESCE(json_extract(payload_json, '$.retry_count'), 0) AS INTEGER) + 1
            ),
            updated_at = ?
        WHERE id = ?
        """,
        (reason, now, job_id),
    )


def _upsert_thumbnail_record(
    conn: Any,
    *,
    file_id: str,
    size_class: str,
    storage_key: str,
    width: int,
    height: int,
    state: str = "completed",
    error: str | None = None,
) -> str:
    """插入或更新 thumbnails 表记录，返回 thumbnail id。"""
    now = _now_iso()
    thumb_id = str(uuid4())
    # 先尝试更新
    existing = conn.execute(
        "SELECT id FROM thumbnails WHERE file_id = ? AND size_class = ?",
        (file_id, size_class),
    ).fetchone()
    if existing:
        conn.execute(
            """
            UPDATE thumbnails
            SET storage_key = ?, width = ?, height = ?, state = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (storage_key, width, height, state, error, now, existing["id"]),
        )
        return existing["id"]
    conn.execute(
        """
        INSERT INTO thumbnails(
            id, file_id, size_class, storage_key, width, height, state, error,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (thumb_id, file_id, size_class, storage_key, width, height, state, error, now, now),
    )
    return thumb_id


def generate_thumbnail_for_file(
    manager: Any,
    file_id: str,
    size_class: str,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """为指定文件生成单级缩略图。

    返回包含 storage_key、width、height 的字典。
    失败时抛出异常，由调用方决定重试策略。
    """
    if size_class not in SIZE_CLASS_TO_PX:
        raise ValueError(f"未知缩略图尺寸级别：{size_class}")

    target_short_side = SIZE_CLASS_TO_PX[size_class]

    # 读取文件记录
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT id, storage_key, mime_type, state FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
    if row is None:
        raise FileNotFoundError(f"文件记录不存在：{file_id}")
    if row["state"] == "missing":
        raise FileNotFoundError(f"文件标记为 missing：{file_id}")

    source_path = Path(manager.data_root) / "storage" / "images" / row["storage_key"]
    if not source_path.exists():
        # 标记文件为 missing
        with manager.connection(environment) as conn:
            conn.execute(
                "UPDATE files SET state = 'missing', updated_at = ? WHERE id = ?",
                (_now_iso(), file_id),
            )
            conn.commit()
        raise FileNotFoundError(f"原图文件不存在：{source_path}")

    # 生成缩略图
    dest_path = thumbnail_path_for(manager, file_id, size_class)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source_path) as img:
        img = img.convert("RGB")
        orig_w, orig_h = img.size
        # 按短边对齐缩放，保持宽高比
        if orig_w <= orig_h:
            new_w = target_short_side
            new_h = int(orig_h * (target_short_side / orig_w))
        else:
            new_h = target_short_side
            new_w = int(orig_w * (target_short_side / orig_h))
        # 确保最小 1x1
        new_w = max(1, new_w)
        new_h = max(1, new_h)
        thumb = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        thumb.save(dest_path, format=THUMBNAIL_FORMAT, quality=THUMBNAIL_QUALITY)

    storage_key = f"{size_class}/{file_id}.webp"
    return {
        "storage_key": storage_key,
        "width": new_w,
        "height": new_h,
        "size_bytes": dest_path.stat().st_size,
        "absolute_path": str(dest_path),
    }


def process_thumbnail_job(
    manager: Any,
    job: dict[str, Any],
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """处理单个缩略图任务。

    成功：写入 thumbnails 表，标记 job 为 completed。
    失败：按错误类型决定永久失败还是回退 pending 重试。
    """
    job_id = job["id"]
    try:
        payload = json.loads(job["payload_json"]) if isinstance(job["payload_json"], str) else job["payload_json"]
    except (TypeError, ValueError):
        payload = {}

    file_id = payload.get("file_id", "")
    size_class = payload.get("size_class", "")

    if not file_id or not size_class:
        with manager.connection(environment) as conn:
            _fail_job(conn, job_id, reason="invalid_payload_missing_file_id_or_size_class", permanent=True)
            conn.commit()
        return {"job_id": job_id, "status": "failed", "reason": "invalid_payload"}

    try:
        result = generate_thumbnail_for_file(manager, file_id, size_class, environment=environment)
    except FileNotFoundError as error:
        # 原图缺失，永久失败
        with manager.connection(environment) as conn:
            _upsert_thumbnail_record(
                conn,
                file_id=file_id,
                size_class=size_class,
                storage_key="",
                width=0,
                height=0,
                state="failed",
                error=str(error),
            )
            _fail_job(conn, job_id, reason=str(error), permanent=True)
            conn.commit()
        return {"job_id": job_id, "status": "failed", "reason": str(error)}
    except Exception as error:  # noqa: BLE001 - 任何处理失败都回退 pending 重试
        logger.warning("缩略图生成失败 job=%s file=%s size=%s: %s", job_id, file_id, size_class, error)
        with manager.connection(environment) as conn:
            _fail_job(conn, job_id, reason=str(error), permanent=False)
            conn.commit()
        return {"job_id": job_id, "status": "retry", "reason": str(error)}

    # 成功：写入 thumbnails 表 + 完成 job
    with manager.connection(environment) as conn:
        _upsert_thumbnail_record(
            conn,
            file_id=file_id,
            size_class=size_class,
            storage_key=result["storage_key"],
            width=result["width"],
            height=result["height"],
            state="completed",
            error=None,
        )
        _complete_job(
            conn,
            job_id,
            result={
                "file_id": file_id,
                "size_class": size_class,
                "storage_key": result["storage_key"],
                "width": result["width"],
                "height": result["height"],
                "size_bytes": result["size_bytes"],
            },
        )
        conn.commit()

    return {"job_id": job_id, "status": "completed", "result": result}


def run_thumbnail_worker_once(
    manager: Any,
    *,
    environment: str | None = None,
    max_jobs: int = 10,
) -> dict[str, Any]:
    """执行一轮缩略图 worker，最多处理 ``max_jobs`` 个任务。

    返回处理统计。
    """
    processed = 0
    completed = 0
    failed = 0
    retried = 0
    results: list[dict[str, Any]] = []

    for _ in range(max_jobs):
        job = claim_thumbnail_job(manager, environment=environment)
        if job is None:
            break
        processed += 1
        result = process_thumbnail_job(manager, job, environment=environment)
        results.append(result)
        status = result.get("status", "")
        if status == "completed":
            completed += 1
        elif status == "failed":
            failed += 1
        elif status == "retry":
            retried += 1

    return {
        "processed": processed,
        "completed": completed,
        "failed": failed,
        "retried": retried,
        "results": results,
    }


def rebuild_thumbnails_for_file(
    manager: Any,
    file_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """为指定文件重建所有级别的缩略图（绕过 background_jobs 直接生成）。

    用于维护任务"重建缩略图"。
    """
    results: list[dict[str, Any]] = []
    for size_class in SIZE_CLASS_TO_PX:
        try:
            result = generate_thumbnail_for_file(
                manager, file_id, size_class, environment=environment
            )
            with manager.connection(environment) as conn:
                _upsert_thumbnail_record(
                    conn,
                    file_id=file_id,
                    size_class=size_class,
                    storage_key=result["storage_key"],
                    width=result["width"],
                    height=result["height"],
                    state="completed",
                    error=None,
                )
                conn.commit()
            results.append({"size_class": size_class, "status": "completed", "result": result})
        except FileNotFoundError as error:
            with manager.connection(environment) as conn:
                _upsert_thumbnail_record(
                    conn,
                    file_id=file_id,
                    size_class=size_class,
                    storage_key="",
                    width=0,
                    height=0,
                    state="failed",
                    error=str(error),
                )
                conn.commit()
            results.append({"size_class": size_class, "status": "failed", "reason": str(error)})
        except Exception as error:  # noqa: BLE001
            results.append({"size_class": size_class, "status": "failed", "reason": str(error)})
    return {"file_id": file_id, "results": results}


def rebuild_all_thumbnails(
    manager: Any,
    *,
    environment: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """批量重建所有文件的缩略图（最多 ``limit`` 个文件）。

    返回处理统计。
    """
    with manager.connection(environment) as conn:
        rows = conn.execute(
            "SELECT id FROM files WHERE state = 'active' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    file_ids = [row["id"] for row in rows]
    completed = 0
    failed = 0
    for file_id in file_ids:
        result = rebuild_thumbnails_for_file(manager, file_id, environment=environment)
        for item in result["results"]:
            if item["status"] == "completed":
                completed += 1
            else:
                failed += 1

    return {
        "total_files": len(file_ids),
        "thumbnails_completed": completed,
        "thumbnails_failed": failed,
    }


def get_thumbnail_record(
    manager: Any,
    file_id: str,
    size_class: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取单个缩略图记录。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM thumbnails WHERE file_id = ? AND size_class = ?",
            (file_id, size_class),
        ).fetchone()
    return dict(row) if row else None


def list_thumbnails_for_file(
    manager: Any,
    file_id: str,
    *,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出文件的所有缩略图记录。"""
    with manager.connection(environment) as conn:
        rows = conn.execute(
            "SELECT * FROM thumbnails WHERE file_id = ? ORDER BY size_class",
            (file_id,),
        ).fetchall()
    return [dict(row) for row in rows]
