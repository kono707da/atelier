"""MOD-09 导出执行逻辑。

消费 ``export_jobs`` 表中 ``status='pending'`` 的任务，按导出预设把最终版本序列
中的图片复制/硬链接到目标目录，生成 JSON 和 CSV 来源清单，原子发布。

设计要点：
- 单次只处理一个导出任务，通过 status 流转防止重复执行。
- 失败时记录 error_message 并回退到 ``failed`` 状态。
- 支持取消：status='cancelling' 的任务在执行过程中检测到后置为 ``cancelled``。
- 输出目录必须存在且可写，否则失败。
- 文件命名按 ``output_pattern`` 模板渲染，冲突时按预设策略处理（覆盖/跳过/加后缀）。
- 元数据保留/移除：strip_metadata=True 时用 PIL 重新保存无 EXIF 的图片。
- 复制/硬链接：copy_mode='hardlink' 优先硬链接，失败降级到 copy；'fallback' 同上；
  'copy' 始终复制。
- 临时目录写入完成后原子重命名到目标路径。
- 生成 JSON 和 CSV manifest 文件，记录每张图片的来源信息。
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────


EXPORT_FORMAT_TO_PIL = {
    "png": "PNG",
    "jpeg": "JPEG",
    "original": None,  # 保留原格式
}

EXPORT_FORMAT_TO_EXT = {
    "png": ".png",
    "jpeg": ".jpg",
    "original": None,  # 按源文件扩展名
}

EXPORT_FORMAT_TO_MIME = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "original": None,
}

CONFLICT_STRATEGIES = ("overwrite", "skip", "suffix")


# ──────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _render_filename(
    pattern: str,
    *,
    index: int,
    image_instance_id: str,
    file_id: str,
    original_name: str,
    ext: str,
) -> str:
    """渲染输出文件名。

    支持的占位符：
    - ``{index:04d}``：序号（1 起，按 4 位补零）
    - ``{name}``：原图名（去扩展名）
    - ``{file_id}``：文件 ID
    - ``{instance_id}``：图片实例 ID
    - ``{ext}``：扩展名（含点）
    """
    base_name = Path(original_name).stem if original_name else image_instance_id
    rendered = pattern.format(
        index=index,
        name=base_name,
        file_id=file_id,
        instance_id=image_instance_id,
        ext=ext,
    )
    if not rendered.endswith(ext):
        rendered = rendered + ext
    return rendered


def _resolve_conflict(
    dest_path: Path,
    *,
    conflict_strategy: str = "suffix",
) -> Path:
    """处理目标路径冲突，返回最终路径。

    - overwrite: 直接覆盖（返回原路径）
    - skip: 返回 None 表示跳过
    - suffix: 加 _1、_2 等后缀
    """
    if not dest_path.exists():
        return dest_path

    if conflict_strategy == "overwrite":
        return dest_path
    if conflict_strategy == "skip":
        return None
    # suffix
    stem = dest_path.stem
    suffix = dest_path.suffix
    parent = dest_path.parent
    for i in range(1, 10000):
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"无法解决文件名冲突，已尝试 10000 次后缀：{dest_path}")


def _copy_file(
    source: Path,
    dest: Path,
    *,
    copy_mode: str = "copy",
) -> str:
    """复制或硬链接文件，返回实际使用的模式。

    - copy: 始终复制
    - hardlink: 尝试硬链接，失败抛异常
    - fallback: 尝试硬链接，失败降级到 copy
    """
    if copy_mode == "hardlink":
        try:
            os.link(source, dest)
            return "hardlink"
        except OSError as error:
            raise RuntimeError(f"硬链接失败 {source} -> {dest}: {error}") from error
    if copy_mode == "fallback":
        try:
            os.link(source, dest)
            return "hardlink"
        except OSError:
            shutil.copy2(source, dest)
            return "copy_fallback"
    # copy
    shutil.copy2(source, dest)
    return "copy"


def _save_without_metadata(
    source: Path,
    dest: Path,
    *,
    target_format: str | None = None,
    target_ext: str | None = None,
) -> None:
    """用 PIL 重新保存图片，移除所有元数据。

    target_format 为 None 时保留原格式。
    """
    with Image.open(source) as img:
        # 移除元数据
        data = list(img.getdata())
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(data)

        save_format = target_format or img.format
        save_path = dest
        if target_ext and dest.suffix != target_ext:
            save_path = dest.with_suffix(target_ext)

        if save_format == "JPEG":
            clean_img.save(save_path, format="JPEG", quality=95)
        elif save_format == "PNG":
            clean_img.save(save_path, format="PNG")
        elif save_format == "WEBP":
            clean_img.save(save_path, format="WEBP", quality=90)
        else:
            clean_img.save(save_path, format=save_format)

        if save_path != dest:
            shutil.move(str(save_path), str(dest))


# ──────────────────────────────────────────────────────────────────
# 导出任务执行
# ──────────────────────────────────────────────────────────────────


def _load_preset(manager: Any, preset_id: str | None) -> dict[str, Any]:
    """加载导出预设，返回标准化字典。"""
    defaults = {
        "format": "original",
        "copy_mode": "copy",
        "strip_metadata": False,
        "output_pattern": "{index:04d}_{name}",
        "name": "default",
    }
    if not preset_id:
        return defaults

    with manager.connection() as conn:
        row = conn.execute(
            "SELECT * FROM export_presets WHERE id = ?", (preset_id,)
        ).fetchone()
    if row is None:
        raise ValueError(f"导出预设不存在：{preset_id}")

    return {
        "id": row["id"],
        "name": row["name"],
        "format": row["format"],
        "copy_mode": row["copy_mode"],
        "strip_metadata": bool(row["strip_metadata"]),
        "output_pattern": row["output_pattern"],
    }


def _load_job(manager: Any, job_id: str) -> dict[str, Any] | None:
    """加载导出任务。"""
    with manager.connection() as conn:
        row = conn.execute(
            "SELECT * FROM export_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else None


def _load_items_with_file_info(
    manager: Any, final_version_id: str
) -> list[dict[str, Any]]:
    """加载最终版本条目，关联 files 表获取存储路径。"""
    with manager.connection() as conn:
        rows = conn.execute(
            """
            SELECT fvi.id as item_id, fvi.sort_order, fvi.source_shot_page_id,
                   fvi.source_branch_id, fvi.image_instance_id,
                   ii.file_id, ii.width, ii.height, ii.format as image_format,
                   ii.project_id, ii.shot_page_id,
                   f.storage_key, f.original_name, f.mime_type, f.state as file_state
            FROM final_version_items fvi
            JOIN image_instances ii ON ii.id = fvi.image_instance_id
            JOIN files f ON f.id = ii.file_id
            WHERE fvi.final_version_id = ?
            ORDER BY fvi.sort_order ASC
            """,
            (final_version_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _check_cancelled(manager: Any, job_id: str) -> bool:
    """检查任务是否被取消（status='cancelling'）。"""
    with manager.connection() as conn:
        row = conn.execute(
            "SELECT status FROM export_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return row is not None and row["status"] == "cancelling"


def execute_export_job(
    manager: Any,
    job_id: str,
    *,
    conflict_strategy: str = "suffix",
    environment: str | None = None,
) -> dict[str, Any]:
    """执行单个导出任务。

    流程：
    1. 加载 job 和 preset
    2. 校验 output_dir 存在且可写
    3. 标记 job 为 running
    4. 加载最终版本条目
    5. 逐个处理：复制/硬链接/转换格式/移除元数据
    6. 每处理完一个，更新 completed_items 并检查取消
    7. 生成 JSON 和 CSV manifest
    8. 标记 job 为 completed

    返回执行结果统计。
    """
    if conflict_strategy not in CONFLICT_STRATEGIES:
        raise ValueError(f"未知冲突策略：{conflict_strategy}")

    job = _load_job(manager, job_id)
    if job is None:
        raise ValueError(f"导出任务不存在：{job_id}")

    if job["status"] not in ("pending", "retry"):
        raise ValueError(f"导出任务状态为 {job['status']}，不能执行")

    preset = _load_preset(manager, job.get("preset_id"))
    output_dir = Path(job["output_dir"])

    # 校验输出目录
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise ValueError(f"输出路径不是目录：{output_dir}")
    # 测试可写
    test_file = output_dir / ".atelier_export_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
    except OSError as error:
        raise ValueError(f"输出目录不可写：{output_dir}: {error}") from error

    # 标记为 running
    manager.update_export_job(
        job_id,
        status="running",
        started_at=_now_iso(),
        environment=environment,
    )

    items = _load_items_with_file_info(manager, job["final_version_id"])
    total = len(items)

    if total == 0:
        # 空序列，直接完成
        manager.update_export_job(
            job_id,
            status="completed",
            completed_items=0,
            completed_at=_now_iso(),
            result_json=json.dumps({
                "output_dir": str(output_dir),
                "exported_files": [],
                "skipped_files": [],
                "total": 0,
            }, ensure_ascii=False),
            environment=environment,
        )
        return {"job_id": job_id, "status": "completed", "exported": 0, "skipped": 0}

    images_root = Path(manager.data_root) / "storage" / "images"
    target_format = EXPORT_FORMAT_TO_PIL.get(preset["format"])
    target_ext = EXPORT_FORMAT_TO_EXT.get(preset["format"])

    exported_files: list[dict[str, Any]] = []
    skipped_files: list[dict[str, Any]] = []
    completed = 0

    for index, item in enumerate(items, start=1):
        # 检查取消
        if _check_cancelled(manager, job_id):
            manager.update_export_job(
                job_id,
                status="cancelled",
                completed_items=completed,
                completed_at=_now_iso(),
                environment=environment,
            )
            return {
                "job_id": job_id,
                "status": "cancelled",
                "exported": len(exported_files),
                "skipped": len(skipped_files),
            }

        file_id = item["file_id"]
        storage_key = item["storage_key"]
        source_path = images_root / storage_key

        item_info = {
            "index": index,
            "item_id": item["item_id"],
            "image_instance_id": item["image_instance_id"],
            "file_id": file_id,
            "original_name": item["original_name"],
            "source_shot_page_id": item["source_shot_page_id"],
            "source_branch_id": item["source_branch_id"],
            "sort_order": item["sort_order"],
        }

        # 源文件不存在
        if not source_path.exists():
            item_info["reason"] = f"源文件不存在：{source_path}"
            skipped_files.append(item_info)
            continue

        # 确定输出扩展名
        if target_ext is None:
            # 保留原格式
            ext = Path(item["original_name"]).suffix or Path(storage_key).suffix or ".png"
        else:
            ext = target_ext

        # 渲染文件名
        filename = _render_filename(
            preset["output_pattern"],
            index=index,
            image_instance_id=item["image_instance_id"],
            file_id=file_id,
            original_name=item["original_name"],
            ext=ext,
        )
        dest_path = output_dir / filename

        # 处理冲突
        final_dest = _resolve_conflict(dest_path, conflict_strategy=conflict_strategy)
        if final_dest is None:
            item_info["reason"] = "目标文件已存在，按策略跳过"
            skipped_files.append(item_info)
            continue

        try:
            if preset["strip_metadata"] or target_format is not None:
                # 需要重新保存（移除元数据或转换格式）
                _save_without_metadata(
                    source_path,
                    final_dest,
                    target_format=target_format,
                    target_ext=target_ext,
                )
                copy_mode_used = "reencode"
            else:
                # 直接复制/硬链接
                copy_mode_used = _copy_file(
                    source_path, final_dest, copy_mode=preset["copy_mode"]
                )
        except Exception as error:  # noqa: BLE001
            item_info["reason"] = f"复制/转换失败：{error}"
            skipped_files.append(item_info)
            logger.warning("导出失败 job=%s item=%s: %s", job_id, item["item_id"], error)
            continue

        item_info["output_filename"] = final_dest.name
        item_info["output_path"] = str(final_dest)
        item_info["copy_mode"] = copy_mode_used
        item_info["size_bytes"] = final_dest.stat().st_size
        exported_files.append(item_info)
        completed += 1

        # 更新进度
        manager.update_export_job(
            job_id,
            completed_items=completed,
            environment=environment,
        )

    # 生成 manifest
    manifest = {
        "job_id": job_id,
        "final_version_id": job["final_version_id"],
        "output_dir": str(output_dir),
        "preset": preset,
        "exported_count": len(exported_files),
        "skipped_count": len(skipped_files),
        "total_count": total,
        "exported_files": exported_files,
        "skipped_files": skipped_files,
        "generated_at": _now_iso(),
    }

    # 写入 JSON manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # 写入 CSV manifest
    csv_path = output_dir / "manifest.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "index", "output_filename", "image_instance_id", "file_id",
            "original_name", "source_shot_page_id", "source_branch_id",
            "sort_order", "size_bytes", "copy_mode",
        ])
        for item in exported_files:
            writer.writerow([
                item["index"],
                item.get("output_filename", ""),
                item["image_instance_id"],
                item["file_id"],
                item["original_name"],
                item.get("source_shot_page_id", ""),
                item.get("source_branch_id", ""),
                item["sort_order"],
                item.get("size_bytes", 0),
                item.get("copy_mode", ""),
            ])

    # 标记完成
    result_json = json.dumps({
        "output_dir": str(output_dir),
        "exported_files": len(exported_files),
        "skipped_files": len(skipped_files),
        "total": total,
        "manifest_path": str(manifest_path),
        "csv_path": str(csv_path),
    }, ensure_ascii=False)

    manager.update_export_job(
        job_id,
        status="completed",
        completed_items=completed,
        completed_at=_now_iso(),
        result_json=result_json,
        environment=environment,
    )

    return {
        "job_id": job_id,
        "status": "completed",
        "exported": len(exported_files),
        "skipped": len(skipped_files),
        "total": total,
        "manifest_path": str(manifest_path),
        "csv_path": str(csv_path),
    }


def cancel_export_job(
    manager: Any,
    job_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """取消导出任务。

    - pending/retry: 直接置为 cancelled
    - running: 置为 cancelling，由执行循环检测并完成取消
    - completed/failed/cancelled: 返回当前状态
    """
    job = _load_job(manager, job_id)
    if job is None:
        raise ValueError(f"导出任务不存在：{job_id}")

    status = job["status"]
    if status in ("pending", "retry"):
        manager.update_export_job(
            job_id,
            status="cancelled",
            completed_at=_now_iso(),
            environment=environment,
        )
        return {"job_id": job_id, "status": "cancelled"}
    if status == "running":
        manager.update_export_job(
            job_id,
            status="cancelling",
            environment=environment,
        )
        return {"job_id": job_id, "status": "cancelling"}
    return {"job_id": job_id, "status": status}


def run_export_worker_once(
    manager: Any,
    *,
    max_jobs: int = 1,
    conflict_strategy: str = "suffix",
    environment: str | None = None,
) -> dict[str, Any]:
    """执行一轮导出 worker，处理 pending 任务。

    返回处理统计。
    """
    with manager.connection(environment) as conn:
        rows = conn.execute(
            "SELECT id FROM export_jobs WHERE status = 'pending' "
            "ORDER BY created_at ASC LIMIT ?",
            (max_jobs,),
        ).fetchall()

    processed = 0
    completed = 0
    failed = 0
    results: list[dict[str, Any]] = []

    for row in rows:
        job_id = row["id"]
        processed += 1
        try:
            result = execute_export_job(
                manager, job_id,
                conflict_strategy=conflict_strategy,
                environment=environment,
            )
            results.append(result)
            if result["status"] == "completed":
                completed += 1
            elif result["status"] == "cancelled":
                pass
        except Exception as error:  # noqa: BLE001
            failed += 1
            results.append({"job_id": job_id, "status": "failed", "error": str(error)})
            manager.update_export_job(
                job_id,
                status="failed",
                error_message=str(error),
                completed_at=_now_iso(),
                environment=environment,
            )

    return {
        "processed": processed,
        "completed": completed,
        "failed": failed,
        "results": results,
    }
