"""MOD-12 历史图片原地索引。

将外部目录中的历史图片增量索引到全局图库（``gallery_index``），支持检查点、
暂停与恢复（需求 §15）。

设计要点：
- 使用 ``background_jobs`` 表（``job_type='legacy_index'``）作为作业载体，
  ``status`` 流转控制暂停/恢复/取消。
- ``payload_json`` 存储扫描目录与选项；``progress_json`` 存储检查点
  （``last_processed_path`` 与统计计数）。
- ``legacy_indexed_files`` 表记录每个已处理文件的最终状态，作为检查点，
  避免重复处理已确认文件。
- 文件不存在时标记 ``missing``，不直接删除数据库记录。
- 默认 ``link_mode='hardlink'``：把原文件硬链接到 ``<data_root>/images/`` 下，
  使 ``files`` / ``gallery_index`` 能复用现有存储路径解析；硬链接失败时降级为 copy。
- 每处理 ``checkpoint_interval`` 个文件就提交一次检查点，并发布进度事件。
- ``run_legacy_index_once`` 单次处理有限数量文件后返回，便于 API 轮询驱动
  或在循环中检测暂停/取消。
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────


LEGACY_INDEX_JOB_TYPE = "legacy_index"

LEGACY_IMAGE_EXTENSIONS: tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".tif",
)

# 作业状态机
VALID_JOB_STATUSES = (
    "pending", "running", "paused", "completed", "failed", "cancelled",
)

# 默认每批处理的文件数
DEFAULT_MAX_FILES = 200

# 每处理多少个文件提交一次检查点
DEFAULT_CHECKPOINT_INTERVAL = 20

# 链接模式
LINK_MODES = ("hardlink", "copy")

# MIME 类型映射
EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}


# ──────────────────────────────────────────────────────────────────
# 事件发布
# ──────────────────────────────────────────────────────────────────


def _publish_event(event_type: str, payload: dict[str, Any]) -> None:
    """MOD-07: 发布事件到全局事件总线（失败不影响主流程）。"""
    try:
        from .event_bus import publish_event
        publish_event(event_type, payload)
    except Exception:  # noqa: BLE001
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────
# 作业创建
# ──────────────────────────────────────────────────────────────────


def create_legacy_index_job(
    manager: Any,
    directory: str,
    *,
    link_mode: str = "hardlink",
    force: bool = False,
    environment: str | None = None,
) -> dict[str, Any]:
    """创建一个历史图片原地索引作业。

    作业初始状态为 ``pending``，需要调用 ``run_legacy_index_once`` 执行。

    参数：
    - directory: 要扫描的目录
    - link_mode: 文件注册方式（hardlink/copy）
    - force: 是否强制重新索引已存在的文件

    返回创建的作业记录。
    """
    if link_mode not in LINK_MODES:
        raise ValueError(f"未知 link_mode：{link_mode}，可选 {LINK_MODES}")

    scan_path = Path(directory).resolve()
    if not scan_path.exists():
        raise ValueError(f"目录不存在：{directory}")
    if not scan_path.is_dir():
        raise ValueError(f"路径不是目录：{directory}")

    job_id = str(uuid4())
    now = _now_iso()
    payload = {
        "directory": str(scan_path),
        "link_mode": link_mode,
        "force": force,
    }
    progress = {
        "last_processed_path": None,
        "total_found": 0,
        "processed": 0,
        "indexed": 0,
        "skipped": 0,
        "missing": 0,
        "duplicate": 0,
        "errors": 0,
    }

    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO background_jobs(
                id, job_type, status, payload_json, progress_json,
                result_json, lease_until, error_json, created_at, updated_at
            ) VALUES (?, ?, 'pending', ?, ?, NULL, NULL, NULL, ?, ?)""",
            (
                job_id, LEGACY_INDEX_JOB_TYPE,
                json.dumps(payload, ensure_ascii=False),
                json.dumps(progress, ensure_ascii=False),
                now, now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM background_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else {}


# ──────────────────────────────────────────────────────────────────
# 作业状态控制
# ──────────────────────────────────────────────────────────────────


def _update_job_status(
    conn: Any,
    job_id: str,
    status: str,
    *,
    now: str | None = None,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> int:
    """更新作业状态，返回 rowcount。"""
    now = now or _now_iso()
    sets = ["status = ?", "updated_at = ?"]
    params: list[Any] = [status, now]
    if result is not None:
        sets.append("result_json = ?")
        params.append(json.dumps(result, ensure_ascii=False))
    if error is not None:
        sets.append("error_json = ?")
        params.append(json.dumps(error, ensure_ascii=False))
    params.append(job_id)
    cursor = conn.execute(
        f"UPDATE background_jobs SET {', '.join(sets)} WHERE id = ?",
        params,
    )
    return cursor.rowcount


def _update_job_progress(
    conn: Any,
    job_id: str,
    progress: dict[str, Any],
) -> None:
    """更新作业检查点。"""
    conn.execute(
        "UPDATE background_jobs SET progress_json = ?, updated_at = ? WHERE id = ?",
        (json.dumps(progress, ensure_ascii=False), _now_iso(), job_id),
    )


def pause_legacy_index(
    manager: Any,
    job_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """暂停作业（仅 running 可暂停）。"""
    now = _now_iso()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            """UPDATE background_jobs
               SET status = 'paused', updated_at = ?
               WHERE id = ? AND job_type = ? AND status = 'running'""",
            (now, job_id, LEGACY_INDEX_JOB_TYPE),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM background_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else None


def resume_legacy_index(
    manager: Any,
    job_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """恢复暂停的作业。"""
    now = _now_iso()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            """UPDATE background_jobs
               SET status = 'pending', updated_at = ?
               WHERE id = ? AND job_type = ? AND status = 'paused'""",
            (now, job_id, LEGACY_INDEX_JOB_TYPE),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM background_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else None


def cancel_legacy_index(
    manager: Any,
    job_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """取消作业（非终态均可取消）。"""
    now = _now_iso()
    with manager.connection(environment) as conn:
        cursor = conn.execute(
            """UPDATE background_jobs
               SET status = 'cancelled', updated_at = ?
               WHERE id = ? AND job_type = ?
                 AND status NOT IN ('completed', 'cancelled')""",
            (now, job_id, LEGACY_INDEX_JOB_TYPE),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT * FROM background_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else None


def get_legacy_index_status(
    manager: Any,
    job_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """查询作业状态，合并 payload/progress/result 便于前端展示。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM background_jobs WHERE id = ? AND job_type = ?",
            (job_id, LEGACY_INDEX_JOB_TYPE),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    result["payload"] = json.loads(row["payload_json"]) if row["payload_json"] else {}
    result["progress"] = json.loads(row["progress_json"]) if row["progress_json"] else {}
    result["result"] = json.loads(row["result_json"]) if row["result_json"] else None
    result["error"] = json.loads(row["error_json"]) if row["error_json"] else None
    # 汇总 legacy_indexed_files 各状态计数
    with manager.connection(environment) as conn:
        counts = conn.execute(
            """SELECT status, COUNT(*) AS count
               FROM legacy_indexed_files WHERE job_id = ?
               GROUP BY status""",
            (job_id,),
        ).fetchall()
    result["file_status_counts"] = {r["status"]: r["count"] for r in counts}
    return result


# ──────────────────────────────────────────────────────────────────
# 文件扫描与索引
# ──────────────────────────────────────────────────────────────────


def _scan_image_files(directory: Path) -> list[Path]:
    """递归扫描目录中的图片文件，按路径排序保证顺序稳定。"""
    files: list[Path] = []
    for entry in sorted(directory.rglob("*")):
        if entry.is_file() and entry.suffix.lower() in LEGACY_IMAGE_EXTENSIONS:
            files.append(entry)
    return files


def _compute_content_hash(path: Path) -> str:
    """计算文件 SHA-256 内容哈希。"""
    sha = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def _find_existing_file_by_hash(
    conn: Any, content_hash: str
) -> str | None:
    """按 content_hash 查找已存在的 files.id。"""
    row = conn.execute(
        "SELECT id FROM files WHERE content_hash = ? AND state = 'active' LIMIT 1",
        (content_hash,),
    ).fetchone()
    return row["id"] if row else None


def _is_file_indexed_for_job(
    conn: Any, job_id: str, source_path: str
) -> bool:
    """检查某文件是否已在当前作业中处理过（检查点）。"""
    row = conn.execute(
        "SELECT 1 FROM legacy_indexed_files WHERE job_id = ? AND source_path = ? LIMIT 1",
        (job_id, source_path),
    ).fetchone()
    return row is not None


def _link_file_to_images(
    manager: Any,
    source: Path,
    storage_key: str,
    *,
    link_mode: str,
) -> str:
    """把源文件链接/复制到 <data_root>/images/<storage_key>。

    返回实际使用的模式（'hardlink' / 'copy'）。
    """
    dest = Path(manager.data_root) / "images" / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        # 目标已存在，若内容相同则跳过，否则加后缀
        if dest.stat().st_size == source.stat().st_size:
            return "exists"
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        for i in range(1, 10000):
            candidate = parent / f"{stem}_{i}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
        else:
            raise RuntimeError(f"无法解决存储路径冲突：{dest}")

    if link_mode == "hardlink":
        try:
            import os
            os.link(source, dest)
            return "hardlink"
        except OSError:
            shutil.copy2(source, dest)
            return "copy_fallback"
    # copy
    shutil.copy2(source, dest)
    return "copy"


def _record_indexed_file(
    conn: Any,
    job_id: str,
    source_path: str,
    *,
    content_hash: str | None,
    file_id: str | None,
    status: str,
    error_message: str | None = None,
) -> None:
    """记录一个已处理文件到 legacy_indexed_files（检查点）。"""
    now = _now_iso()
    conn.execute(
        """INSERT INTO legacy_indexed_files(
            id, job_id, source_path, content_hash, file_id,
            status, error_message, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, source_path) DO UPDATE SET
            content_hash = excluded.content_hash,
            file_id = excluded.file_id,
            status = excluded.status,
            error_message = excluded.error_message,
            updated_at = excluded.updated_at""",
        (
            str(uuid4()), job_id, source_path, content_hash, file_id,
            status, error_message, now, now,
        ),
    )


def _process_single_file(
    manager: Any,
    conn: Any,
    job_id: str,
    source: Path,
    *,
    link_mode: str,
    force: bool,
) -> str:
    """处理单个历史图片文件，返回状态字符串。

    状态：indexed / skipped / missing / duplicate / error
    """
    if not source.exists():
        _record_indexed_file(
            conn, job_id, str(source),
            content_hash=None, file_id=None,
            status="missing", error_message="文件不存在",
        )
        return "missing"

    try:
        content_hash = _compute_content_hash(source)
    except OSError as exc:
        _record_indexed_file(
            conn, job_id, str(source),
            content_hash=None, file_id=None,
            status="error", error_message=f"读取失败：{exc}",
        )
        return "error"

    # 去重：按 content_hash 查找已有 files 记录
    existing_file_id = _find_existing_file_by_hash(conn, content_hash)
    if existing_file_id and not force:
        # 已存在，只记录关联，不重复创建
        _record_indexed_file(
            conn, job_id, str(source),
            content_hash=content_hash, file_id=existing_file_id,
            status="duplicate",
        )
        return "duplicate"

    # 创建 files 记录
    file_id = str(uuid4())
    ext = source.suffix.lower()
    mime_type = EXT_TO_MIME.get(ext, "application/octet-stream")
    size_bytes = source.stat().st_size
    # storage_key: <job_id前8位>/<file_id><ext>
    storage_key = f"{job_id[:8]}/{file_id}{ext}"

    try:
        _link_file_to_images(
            manager, source, storage_key, link_mode=link_mode,
        )
    except Exception as exc:  # noqa: BLE001
        _record_indexed_file(
            conn, job_id, str(source),
            content_hash=content_hash, file_id=None,
            status="error", error_message=f"链接失败：{exc}",
        )
        return "error"

    now = _now_iso()
    conn.execute(
        """INSERT INTO files(
            id, storage_key, original_name, mime_type, size_bytes,
            content_hash, perceptual_hash, state, error_message,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, NULL, 'active', NULL, ?, ?)""",
        (
            file_id, storage_key, source.name, mime_type, size_bytes,
            content_hash, now, now,
        ),
    )

    _record_indexed_file(
        conn, job_id, str(source),
        content_hash=content_hash, file_id=file_id,
        status="indexed",
    )
    return "indexed"


def _claim_job(
    manager: Any,
    *,
    environment: str | None,
) -> dict[str, Any] | None:
    """领取一个 pending 的 legacy_index 作业，置为 running。"""
    now = _now_iso()
    lease_until = datetime.now(timezone.utc).timestamp() + 600
    lease_iso = datetime.fromtimestamp(lease_until, tz=timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        row = conn.execute(
            """SELECT * FROM background_jobs
               WHERE job_type = ? AND status = 'pending'
               ORDER BY created_at ASC LIMIT 1""",
            (LEGACY_INDEX_JOB_TYPE,),
        ).fetchone()
        if not row:
            return None
        cursor = conn.execute(
            """UPDATE background_jobs
               SET status = 'running', lease_until = ?, updated_at = ?
               WHERE id = ? AND status = 'pending'""",
            (lease_iso, now, row["id"]),
        )
        if cursor.rowcount == 0:
            return None
        return dict(row)


# ──────────────────────────────────────────────────────────────────
# 核心执行
# ──────────────────────────────────────────────────────────────────


def run_legacy_index_once(
    manager: Any,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """执行一轮历史图片索引。

    1. 领取一个 pending 作业
    2. 扫描目录（首次）或从检查点继续
    3. 处理最多 ``max_files`` 个未处理文件
    4. 更新检查点
    5. 若全部处理完则标记 completed，否则保持 running（等待下一轮）

    返回作业状态快照，无 pending 作业时返回 None。
    """
    job = _claim_job(manager, environment=environment)
    if job is None:
        return None

    result = _execute_job(manager, job, max_files=max_files, environment=environment)
    return result


def index_legacy_library(
    manager: Any,
    job_id: str,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    environment: str | None = None,
) -> dict[str, Any]:
    """直接执行指定作业的一轮索引（不经过 claim，用于测试或显式驱动）。

    作业状态会被置为 running，处理完后根据是否全部完成置为 completed 或 running。
    """
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM background_jobs WHERE id = ? AND job_type = ?",
            (job_id, LEGACY_INDEX_JOB_TYPE),
        ).fetchone()
        if not row:
            raise ValueError(f"作业不存在：{job_id}")
        now = _now_iso()
        conn.execute(
            """UPDATE background_jobs
               SET status = 'running', updated_at = ?
               WHERE id = ? AND status IN ('pending', 'running', 'paused')""",
            (now, job_id),
        )
        job = dict(row)

    return _execute_job(manager, job, max_files=max_files, environment=environment)


def _execute_job(
    manager: Any,
    job: dict[str, Any],
    *,
    max_files: int,
    environment: str | None,
) -> dict[str, Any]:
    """核心执行逻辑。"""
    job_id = job["id"]
    payload = json.loads(job["payload_json"]) if job["payload_json"] else {}
    progress = json.loads(job["progress_json"]) if job["progress_json"] else {}
    directory = Path(payload["directory"])
    link_mode = payload.get("link_mode", "hardlink")
    force = bool(payload.get("force", False))

    # 初始化进度
    if not progress:
        progress = {
            "last_processed_path": None,
            "total_found": 0,
            "processed": 0,
            "indexed": 0,
            "skipped": 0,
            "missing": 0,
            "duplicate": 0,
            "errors": 0,
        }

    # 扫描目录
    if directory.exists():
        all_files = _scan_image_files(directory)
    else:
        all_files = []
    progress["total_found"] = len(all_files)

    _publish_event("legacy_index.started", {
        "job_id": job_id,
        "directory": str(directory),
        "total_found": len(all_files),
    })

    processed_this_round = 0
    last_processed_path = progress.get("last_processed_path")

    with manager.connection(environment) as conn:
        for source in all_files:
            # 检查是否已被取消
            status_row = conn.execute(
                "SELECT status FROM background_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if status_row and status_row["status"] == "cancelled":
                _update_job_progress(conn, job_id, progress)
                _publish_event("legacy_index.cancelled", {
                    "job_id": job_id, "progress": progress,
                })
                return get_legacy_index_status(manager, job_id, environment=environment) or {}

            # 检查点跳过：已处理过的文件
            source_str = str(source)
            if _is_file_indexed_for_job(conn, job_id, source_str):
                continue

            # 跳过 last_processed_path 之前的文件（恢复时）
            if last_processed_path and source_str <= last_processed_path:
                continue

            status = _process_single_file(
                manager, conn, job_id, source,
                link_mode=link_mode, force=force,
            )

            progress["processed"] += 1
            progress[status] = progress.get(status, 0) + 1
            progress["last_processed_path"] = source_str
            last_processed_path = source_str
            processed_this_round += 1

            # 对已创建的 file_id 同步到 gallery_index
            if status == "indexed":
                try:
                    from .gallery import index_file_for_gallery
                    # 查找刚创建的 file_id
                    rec = conn.execute(
                        "SELECT file_id FROM legacy_indexed_files WHERE job_id = ? AND source_path = ?",
                        (job_id, source_str),
                    ).fetchone()
                    if rec and rec["file_id"]:
                        # 在 conn 之外调用（index_file_for_gallery 会自己开连接）
                        pass
                except Exception:  # noqa: BLE001
                    pass

            # 定期检查点
            if processed_this_round % DEFAULT_CHECKPOINT_INTERVAL == 0:
                _update_job_progress(conn, job_id, progress)
                _publish_event("legacy_index.progress", {
                    "job_id": job_id,
                    "processed": progress["processed"],
                    "total_found": progress["total_found"],
                    "indexed": progress["indexed"],
                    "skipped": progress["skipped"],
                    "missing": progress["missing"],
                    "duplicate": progress["duplicate"],
                    "errors": progress["errors"],
                })

            if processed_this_round >= max_files:
                break

        # 更新最终进度
        _update_job_progress(conn, job_id, progress)

        # 判断是否全部完成
        all_done = progress["processed"] >= progress["total_found"]
        if all_done:
            _update_job_status(
                conn, job_id, "completed",
                result={
                    "indexed": progress["indexed"],
                    "skipped": progress["skipped"],
                    "missing": progress["missing"],
                    "duplicate": progress["duplicate"],
                    "errors": progress["errors"],
                    "total_found": progress["total_found"],
                },
            )
        # 否则保持 running，等待下一轮

    # 全部完成后，批量同步 gallery_index
    if all_done:
        _sync_gallery_for_job(manager, job_id, environment=environment)
        _publish_event("legacy_index.completed", {
            "job_id": job_id,
            "progress": progress,
        })

    return get_legacy_index_status(manager, job_id, environment=environment) or {}


def _sync_gallery_for_job(
    manager: Any,
    job_id: str,
    *,
    environment: str | None,
) -> None:
    """作业完成后，把所有新创建的 file_id 同步到 gallery_index。"""
    from .gallery import index_file_for_gallery

    with manager.connection(environment) as conn:
        rows = conn.execute(
            """SELECT file_id FROM legacy_indexed_files
               WHERE job_id = ? AND status = 'indexed' AND file_id IS NOT NULL""",
            (job_id,),
        ).fetchall()

    for row in rows:
        try:
            index_file_for_gallery(manager, row["file_id"], environment=environment)
        except Exception as exc:  # noqa: BLE001
            logger.warning("gallery index failed for %s: %s", row["file_id"], exc)
