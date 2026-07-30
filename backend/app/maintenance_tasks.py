"""MOD-11 补齐维护任务。

包含：
- restore_database: 从备份文件恢复数据库（恢复前自动备份当前库）
- rebuild_fts_index: 重建 gallery_fts 全文索引
- recompute_all_phash: 批量重算感知哈希
- clean_temp_files: 清理过期临时文件
- clean_trash: 清理过期回收站项（软删除记录的物理删除）
- rebuild_all_thumbnails_wrapper: 调用 thumbnail_worker 批量重建缩略图
"""
from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PIL import Image

from .gallery import compute_perceptual_hash, index_file_for_gallery
from .thumbnail_worker import rebuild_all_thumbnails

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────


DEFAULT_TEMP_RETENTION_DAYS = 7
DEFAULT_TRASH_RETENTION_DAYS = 30


# ──────────────────────────────────────────────────────────────────
# 工具
# ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────
# 数据库恢复
# ──────────────────────────────────────────────────────────────────


def restore_database(
    manager: Any,
    backup_path: str,
    *,
    pre_restore_backup: bool = True,
    pre_restore_backup_dir: str | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """从备份文件恢复数据库。

    流程（需求 §17.2）：
    1. 校验备份文件存在且是有效 SQLite 文件
    2. 恢复前自动备份当前数据库（pre_restore_backup=True）
    3. 关闭当前连接（或使用新连接覆盖）
    4. 用备份文件替换当前数据库文件
    5. 重新打开连接并运行迁移
    6. 运行完整性检查和文件引用检查
    7. 返回恢复结果

    注意：恢复操作需要独占访问数据库，调用方应确保无其他写入。
    """
    backup_file = Path(backup_path).resolve()
    if not backup_file.exists():
        raise FileNotFoundError(f"备份文件不存在：{backup_file}")
    if not backup_file.is_file():
        raise ValueError(f"备份路径不是文件：{backup_file}")

    # 校验是有效 SQLite 文件（前 16 字节）
    # SQLite 3.x 数据库文件头部为 "SQLite format 3\x00"
    with open(backup_file, "rb") as f:
        header = f.read(16)
    if not header.startswith(b"SQLite format 3"):
        raise ValueError(f"备份文件不是有效的 SQLite 数据库：{backup_file}")

    target = environment or manager._active_environment
    descriptor = manager.descriptor(target)
    current_path = Path(descriptor.path).resolve()

    # 恢复前自动备份
    pre_backup_info: dict[str, Any] | None = None
    if pre_restore_backup:
        if pre_restore_backup_dir:
            pre_backup_dir = Path(pre_restore_backup_dir)
        else:
            pre_backup_dir = current_path.parent / "backups"
        pre_backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        pre_backup_path = pre_backup_dir / f"pre_restore_{target}_{timestamp}.db"
        pre_backup_info = manager.backup_database(
            str(pre_backup_path), environment=target
        )

    # 关闭 WAL 和连接（通过 manager 的连接池）
    # 先 checkpoint 把 WAL 写入主库
    try:
        with manager.connection(target) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception as error:  # noqa: BLE001
        logger.warning("恢复前 wal_checkpoint 失败: %s", error)

    # 替换数据库文件
    # 先删除 WAL 和 SHM 文件（避免恢复后冲突）
    wal_path = current_path.with_suffix(current_path.suffix + "-wal")
    shm_path = current_path.with_suffix(current_path.suffix + "-shm")
    for sidecar in (wal_path, shm_path):
        if sidecar.exists():
            try:
                sidecar.unlink()
            except OSError as error:
                logger.warning("删除 %s 失败: %s", sidecar, error)

    # 复制备份到当前路径
    shutil.copy2(str(backup_file), str(current_path))

    # 重新初始化（运行迁移）
    # 通过 manager 的初始化方法重新打开连接并运行迁移
    # 这里假设 manager 有 _ensure_environment 或类似方法
    # 实际上 manager 在下次 connection() 时会重新打开
    # 我们显式触发一次迁移
    try:
        with manager.connection(target) as conn:
            # 运行迁移（如果 manager 有 migrate 方法）
            if hasattr(manager, "_run_all_migrations"):
                manager._run_all_migrations(conn, target)
    except Exception as error:  # noqa: BLE001
        logger.warning("恢复后迁移失败: %s", error)

    # 完整性检查
    integrity_result = manager.integrity_check(environment=target)

    # 文件引用检查
    orphan_result = manager.check_orphaned_files(environment=target)

    return {
        "environment": target,
        "backup_path": str(backup_file),
        "restored_to": str(current_path),
        "pre_restore_backup": pre_backup_info,
        "integrity_check": integrity_result,
        "orphan_check": orphan_result,
        "restored_at": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────
# 重建 FTS 索引
# ──────────────────────────────────────────────────────────────────


def rebuild_fts_index(
    manager: Any,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """重建 gallery_fts 全文索引。

    删除 FTS 表所有内容，从 gallery_index 重新插入。
    """
    with manager.connection(environment) as conn:
        # 清空 FTS 表
        conn.execute("DELETE FROM gallery_fts")
        # 从 gallery_index 重新插入
        rows = conn.execute(
            "SELECT file_id, prompt_text FROM gallery_index WHERE prompt_text != ''"
        ).fetchall()
        for row in rows:
            conn.execute(
                "INSERT INTO gallery_fts(file_id, prompt_text) VALUES (?, ?)",
                (row["file_id"], row["prompt_text"]),
            )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM gallery_fts").fetchone()[0]

    return {
        "environment": manager._active_environment if environment is None else environment,
        "rebuilt": True,
        "indexed_count": count,
        "rebuilt_at": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────
# 批量重算感知哈希
# ──────────────────────────────────────────────────────────────────


def recompute_all_phash(
    manager: Any,
    *,
    limit: int = 100,
    environment: str | None = None,
) -> dict[str, Any]:
    """批量重算所有文件的感知哈希。

    只处理 state='active' 且文件实际存在的记录。
    """
    images_root = Path(manager.data_root) / "storage" / "images"
    with manager.connection(environment) as conn:
        rows = conn.execute(
            "SELECT id, storage_key FROM files WHERE state = 'active' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    total = len(rows)
    computed = 0
    failed = 0
    skipped = 0
    now = _now_iso()

    for row in rows:
        file_id = row["id"]
        storage_key = row["storage_key"]
        source_path = images_root / storage_key
        if not source_path.exists():
            skipped += 1
            continue
        try:
            phash = compute_perceptual_hash(source_path)
            if not phash:
                failed += 1
                continue
            with manager.connection(environment) as conn:
                conn.execute(
                    "UPDATE files SET perceptual_hash = ?, updated_at = ? WHERE id = ?",
                    (phash, now, file_id),
                )
                # 同步更新 gallery_index
                conn.execute(
                    "UPDATE gallery_index SET perceptual_hash = ? WHERE file_id = ?",
                    (phash, file_id),
                )
                conn.commit()
            computed += 1
        except Exception as error:  # noqa: BLE001
            logger.warning("重算 phash 失败 file=%s: %s", file_id, error)
            failed += 1

    return {
        "environment": manager._active_environment if environment is None else environment,
        "total_files": total,
        "computed": computed,
        "failed": failed,
        "skipped_missing": skipped,
        "completed_at": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────
# 清理临时文件
# ──────────────────────────────────────────────────────────────────


def clean_temp_files(
    manager: Any,
    *,
    retention_days: int = DEFAULT_TEMP_RETENTION_DAYS,
    environment: str | None = None,
) -> dict[str, Any]:
    """清理过期的临时文件。

    扫描 <data_root>/tmp 和 <data_root>/cache 目录，删除修改时间超过
    retention_days 天的文件。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_timestamp = cutoff.timestamp()

    temp_root = Path(manager.data_root) / "tmp"
    cache_root = Path(manager.data_root) / "cache"

    removed_temp: list[dict[str, Any]] = []
    removed_cache: list[dict[str, Any]] = []
    kept_temp = 0
    kept_cache = 0

    for root, removed_list, kept_counter in [
        (temp_root, removed_temp, "kept_temp"),
        (cache_root, removed_cache, "kept_cache"),
    ]:
        if not root.exists():
            continue
        for entry in sorted(root.iterdir()):
            if entry.is_file():
                try:
                    mtime = entry.stat().st_mtime
                    if mtime < cutoff_timestamp:
                        size = entry.stat().st_size
                        entry.unlink()
                        removed_list.append({
                            "name": entry.name,
                            "path": str(entry),
                            "size_bytes": size,
                            "mtime": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                        })
                    else:
                        if kept_counter == "kept_temp":
                            kept_temp += 1
                        else:
                            kept_cache += 1
                except OSError as error:
                    logger.warning("删除临时文件失败 %s: %s", entry, error)

    return {
        "environment": manager._active_environment if environment is None else environment,
        "temp_root": str(temp_root),
        "cache_root": str(cache_root),
        "retention_days": retention_days,
        "removed_temp_count": len(removed_temp),
        "removed_cache_count": len(removed_cache),
        "removed_temp_files": removed_temp,
        "removed_cache_files": removed_cache,
        "kept_temp": kept_temp,
        "kept_cache": kept_cache,
        "cleaned_at": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────
# 清理回收站
# ──────────────────────────────────────────────────────────────────


def clean_trash(
    manager: Any,
    *,
    retention_days: int = DEFAULT_TRASH_RETENTION_DAYS,
    environment: str | None = None,
) -> dict[str, Any]:
    """清理过期回收站项。

    扫描所有带 deleted_at 字段的表，物理删除超过 retention_days 天的软删除记录。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    # 带软删除的表
    tables_with_deletion = [
        "projects",
        "chapters",
        "large_scenes",
        "small_scenes",
        "shot_pages",
        "materials",
        "characters",
        "character_variants",
        "workflows",
        "workflow_versions",
    ]

    results: dict[str, int] = {}
    total_removed = 0

    for table in tables_with_deletion:
        try:
            with manager.connection(environment) as conn:
                # 检查表是否有 deleted_at 列
                columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
                if "deleted_at" not in columns:
                    results[table] = 0
                    continue
                # 删除过期的软删除记录
                cursor = conn.execute(
                    f"DELETE FROM {table} WHERE deleted_at IS NOT NULL AND deleted_at < ?",
                    (cutoff_iso,),
                )
                results[table] = cursor.rowcount
                total_removed += cursor.rowcount
            if results[table] > 0:
                with manager.connection(environment) as conn:
                    conn.commit()
        except Exception as error:  # noqa: BLE001
            logger.warning("清理表 %s 回收站失败: %s", table, error)
            results[table] = -1

    return {
        "environment": manager._active_environment if environment is None else environment,
        "retention_days": retention_days,
        "cutoff": cutoff_iso,
        "removed_per_table": results,
        "total_removed": total_removed,
        "cleaned_at": _now_iso(),
    }


# ──────────────────────────────────────────────────────────────────
# 综合维护任务
# ──────────────────────────────────────────────────────────────────


def rebuild_all_thumbnails_wrapper(
    manager: Any,
    *,
    limit: int = 100,
    environment: str | None = None,
) -> dict[str, Any]:
    """重建缩略图的包装函数，调用 thumbnail_worker.rebuild_all_thumbnails。"""
    return rebuild_all_thumbnails(manager, limit=limit, environment=environment)


def run_full_maintenance(
    manager: Any,
    *,
    environment: str | None = None,
    thumbnail_limit: int = 100,
    phash_limit: int = 100,
    temp_retention_days: int = DEFAULT_TEMP_RETENTION_DAYS,
    trash_retention_days: int = DEFAULT_TRASH_RETENTION_DAYS,
) -> dict[str, Any]:
    """运行全套维护任务。

    包含：
    - 数据库优化
    - 重建缩略图
    - 重建 FTS 索引
    - 重算感知哈希
    - 清理临时文件
    - 清理回收站
    - 完整性检查
    """
    results: dict[str, Any] = {}

    try:
        results["optimize"] = manager.optimize_database(environment=environment)
    except Exception as error:  # noqa: BLE001
        results["optimize"] = {"error": str(error)}

    try:
        results["rebuild_thumbnails"] = rebuild_all_thumbnails(
            manager, limit=thumbnail_limit, environment=environment
        )
    except Exception as error:  # noqa: BLE001
        results["rebuild_thumbnails"] = {"error": str(error)}

    try:
        results["rebuild_fts"] = rebuild_fts_index(manager, environment=environment)
    except Exception as error:  # noqa: BLE001
        results["rebuild_fts"] = {"error": str(error)}

    try:
        results["recompute_phash"] = recompute_all_phash(
            manager, limit=phash_limit, environment=environment
        )
    except Exception as error:  # noqa: BLE001
        results["recompute_phash"] = {"error": str(error)}

    try:
        results["clean_temp"] = clean_temp_files(
            manager, retention_days=temp_retention_days, environment=environment
        )
    except Exception as error:  # noqa: BLE001
        results["clean_temp"] = {"error": str(error)}

    try:
        results["clean_trash"] = clean_trash(
            manager, retention_days=trash_retention_days, environment=environment
        )
    except Exception as error:  # noqa: BLE001
        results["clean_trash"] = {"error": str(error)}

    try:
        results["integrity_check"] = manager.integrity_check(environment=environment)
    except Exception as error:  # noqa: BLE001
        results["integrity_check"] = {"error": str(error)}

    results["completed_at"] = _now_iso()
    return results
