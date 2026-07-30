"""阶段 3.6 输出和图片实例。

从 ComfyUI 历史中解析输出，下载图片，写入文件和图片实例记录。

流程：
1. 从 ComfyUI /history 解析所有输出节点和所有图片
2. 通过 /view 流式下载到临时文件
3. 校验图片完整性和格式后原子移动到存储目录
4. 写入 files 和 image_instances 记录
5. 保存任务、页面、分支、工作流、提示词、种子和参数快照
6. 创建缩略图后台任务
7. 文件失败时执行补偿或标记可修复状态

设计原则：
- 一个任务可产生多个图片实例
- 不假设只有一个输出节点
- 原图保存和数据库写入具备补偿机制
- 原图永远不因缩略图失败而丢失
- 流式下载，不一次把大文件读入内存
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from .comfyui_client import ComfyUIError, ComfyUIClient
from .task_queue import get_attempt, get_task, mark_attempt_completed

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# 常量
# ──────────────────────────────────────────────────────────────────


VALID_IMAGE_FORMATS = ("PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF")

THUMBNAIL_SIZE_CLASSES = ("256", "640")


# ──────────────────────────────────────────────────────────────────
# 输出解析
# ──────────────────────────────────────────────────────────────────


def parse_comfyui_outputs(history_entry: dict[str, Any]) -> list[dict[str, Any]]:
    """从 ComfyUI 历史条目解析所有输出图片。

    ComfyUI 的 /history/{prompt_id} 返回结构：
    {
        "outputs": {
            "node_id": {
                "images": [
                    {"filename": "xxx.png", "subfolder": "", "type": "output"}
                ]
            }
        }
    }

    返回图片信息列表，每项包含 node_id、filename、subfolder、type。
    """
    outputs = history_entry.get("outputs", {})
    if not isinstance(outputs, dict):
        return []

    images: list[dict[str, Any]] = []
    for node_id, node_output in outputs.items():
        if not isinstance(node_output, dict):
            continue
        # 图片输出
        for img_info in node_output.get("images", []) or []:
            if not isinstance(img_info, dict):
                continue
            images.append({
                "node_id": node_id,
                "filename": img_info.get("filename", ""),
                "subfolder": img_info.get("subfolder", ""),
                "folder_type": img_info.get("type", "output"),
            })
        # GIF 输出（部分节点使用 animated 字段）
        for gif_info in node_output.get("gifs", []) or []:
            if not isinstance(gif_info, dict):
                continue
            images.append({
                "node_id": node_id,
                "filename": gif_info.get("filename", ""),
                "subfolder": gif_info.get("subfolder", ""),
                "folder_type": gif_info.get("type", "output"),
            })

    return images


# ──────────────────────────────────────────────────────────────────
# 文件下载和校验
# ──────────────────────────────────────────────────────────────────


def download_and_validate_image(
    comfyui_client: ComfyUIClient,
    image_info: dict[str, Any],
    dest_dir: Path,
    *,
    expected_hash: str | None = None,
) -> dict[str, Any]:
    """下载图片到临时文件，校验后原子移动到目标目录。

    返回包含 file_id、storage_key、size_bytes、content_hash、width、height、format 的字典。
    失败时抛出异常。

    流程：
    1. 流式下载到临时文件
    2. 计算 SHA256 内容哈希
    3. 用 PIL 校验图片格式和尺寸
    4. 原子移动到目标目录
    """
    filename = image_info.get("filename", "")
    subfolder = image_info.get("subfolder", "")
    folder_type = image_info.get("folder_type", "output")

    if not filename:
        raise ValueError("图片信息缺少 filename")

    # 流式下载到临时文件
    image_bytes = comfyui_client.download_image(
        filename=filename,
        subfolder=subfolder,
        folder_type=folder_type,
    )

    # 计算内容哈希
    content_hash = hashlib.sha256(image_bytes).hexdigest()
    if expected_hash and content_hash != expected_hash:
        raise ValueError(
            f"图片内容哈希不匹配：期望 {expected_hash}，实际 {content_hash}"
        )

    # 校验图片格式和尺寸
    temp_fd, temp_path = tempfile.mkstemp(
        suffix=Path(filename).suffix or ".png",
        prefix="atelier_download_",
    )
    try:
        with os.fdopen(temp_fd, "wb") as f:
            f.write(image_bytes)

        with Image.open(temp_path) as img:
            img.verify()  # 验证图片完整性
            width, height = img.size
            img_format = img.format or "UNKNOWN"

        if img_format not in VALID_IMAGE_FORMATS:
            raise ValueError(f"不支持的图片格式：{img_format}")

        # 生成存储键
        file_id = str(uuid4())
        ext = Path(filename).suffix or ".png"
        storage_key = f"{file_id}{ext}"
        dest_path = dest_dir / storage_key

        # 确保目标目录存在
        dest_dir.mkdir(parents=True, exist_ok=True)

        # 原子移动
        shutil.move(str(temp_path), str(dest_path))

        return {
            "file_id": file_id,
            "storage_key": storage_key,
            "original_name": filename,
            "mime_type": _format_to_mime(img_format),
            "size_bytes": os.path.getsize(dest_path),
            "content_hash": content_hash,
            "width": width,
            "height": height,
            "format": img_format,
        }
    except Exception:
        # 清理临时文件
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
        raise


def _format_to_mime(img_format: str) -> str:
    """图片格式转 MIME 类型。"""
    mapping = {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "WEBP": "image/webp",
        "GIF": "image/gif",
        "BMP": "image/bmp",
        "TIFF": "image/tiff",
    }
    return mapping.get(img_format, "application/octet-stream")


# ──────────────────────────────────────────────────────────────────
# 数据库写入
# ──────────────────────────────────────────────────────────────────


def create_file_record(
    manager: Any,
    file_data: dict[str, Any],
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """写入 files 表记录。"""
    file_id = file_data["file_id"]
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        conn.execute(
            """INSERT INTO files(
                id, storage_key, original_name, mime_type, size_bytes,
                content_hash, perceptual_hash, state, error_message,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, NULL, 'active', NULL, ?, ?)""",
            (
                file_id,
                file_data["storage_key"],
                file_data["original_name"],
                file_data["mime_type"],
                file_data["size_bytes"],
                file_data["content_hash"],
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM files WHERE id = ?", (file_id,)
        ).fetchone()
    return dict(row) if row else {}


def create_image_instance(
    manager: Any,
    *,
    project_id: str,
    shot_page_id: str,
    task_id: str | None,
    attempt_id: str | None,
    file_id: str,
    node_id: str | None,
    workflow_version_id: str | None,
    prompt_id: str | None,
    width: int,
    height: int,
    img_format: str,
    seed: int | None,
    resolved_json: dict[str, Any] | None,
    snapshot_json: dict[str, Any] | None,
    environment: str | None = None,
) -> dict[str, Any]:
    """写入 image_instances 表记录。"""
    instance_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    resolved_str = json.dumps(resolved_json, ensure_ascii=False) if resolved_json else None
    snapshot_str = json.dumps(snapshot_json, ensure_ascii=False) if snapshot_json else None

    with manager.connection(environment) as conn:
        # 确定 sort_order
        max_order = conn.execute(
            "SELECT MAX(sort_order) as max_order FROM image_instances WHERE shot_page_id = ?",
            (shot_page_id,),
        ).fetchone()
        sort_order = (max_order["max_order"] or 0) + 1 if max_order and max_order["max_order"] is not None else 1

        conn.execute(
            """INSERT INTO image_instances(
                id, project_id, shot_page_id, task_id, attempt_id, file_id,
                node_id, workflow_version_id, prompt_id,
                width, height, format, seed,
                resolved_json, snapshot_json,
                is_adopted, sort_order, revision,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 1, ?, ?)""",
            (
                instance_id, project_id, shot_page_id, task_id, attempt_id, file_id,
                node_id, workflow_version_id, prompt_id,
                width, height, img_format, seed,
                resolved_str, snapshot_str,
                sort_order,
                now, now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM image_instances WHERE id = ?", (instance_id,)
        ).fetchone()
    return dict(row) if row else {}


def create_thumbnail_jobs(
    manager: Any,
    file_id: str,
    *,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """为文件创建缩略图后台任务（256px 和 640px 两级）。"""
    jobs: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        for size_class in THUMBNAIL_SIZE_CLASSES:
            job_id = str(uuid4())
            payload = json.dumps(
                {"file_id": file_id, "size_class": size_class},
                ensure_ascii=False,
            )
            conn.execute(
                """INSERT INTO background_jobs(
                    id, job_type, status, payload_json,
                    progress_json, result_json, lease_until, error_json,
                    created_at, updated_at
                ) VALUES (?, 'thumbnail', 'pending', ?, NULL, NULL, NULL, NULL, ?, ?)""",
                (job_id, payload, now, now),
            )
            row = conn.execute(
                "SELECT * FROM background_jobs WHERE id = ?", (job_id,)
            ).fetchone()
            if row:
                jobs.append(dict(row))
        conn.commit()
    return jobs


# ──────────────────────────────────────────────────────────────────
# 快照构建
# ──────────────────────────────────────────────────────────────────


def build_snapshot(
    manager: Any,
    task: dict[str, Any],
    attempt: dict[str, Any],
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """构建图片实例的快照数据。

    保存任务、页面、分支、工作流、提示词、种子和参数快照。
    """
    item = task.get("item", {})
    if isinstance(item, str):
        try:
            item = json.loads(item)
        except (TypeError, ValueError):
            item = {}
    elif item is None:
        item = {}

    snapshot: dict[str, Any] = {
        "task_id": task.get("id"),
        "task_status": task.get("status"),
        "attempt_id": attempt.get("id"),
        "attempt_number": attempt.get("attempt_number"),
        "prompt_id": attempt.get("prompt_id"),
        "sort_key": item.get("sort_key"),
        "project_id": item.get("project_id"),
        "project_name": item.get("project_name"),
        "chapter_id": item.get("chapter_id"),
        "chapter_name": item.get("chapter_name"),
        "large_scene_id": item.get("large_scene_id"),
        "large_scene_name": item.get("large_scene_name"),
        "small_scene_id": item.get("small_scene_id"),
        "small_scene_name": item.get("small_scene_name"),
        "shot_page_id": item.get("shot_page_id"),
        "shot_page_title": item.get("shot_page_title"),
        "branch_id": item.get("branch_id"),
        "branch_name": item.get("branch_name"),
        "workflow_id": item.get("workflow_id"),
        "workflow_version_id": item.get("workflow_version_id"),
        "workflow_label": item.get("workflow_label"),
        "character_id": item.get("character_id"),
        "character_name": item.get("character_name"),
        "variant_id": item.get("variant_id"),
        "variant_name": item.get("variant_name"),
        "effective_config": item.get("effective_config", {}),
        "field_sources": item.get("field_sources", {}),
        "material_mappings": item.get("material_mappings", {}),
        "spec_values": item.get("spec_values", {}),
        "instance_count": item.get("instance_count", 1),
        "seed_strategy": item.get("seed_strategy", "fixed"),
        "seed_value": item.get("seed_value"),
        "seed_base": item.get("seed_base"),
        "api_json": attempt.get("api_json"),
    }
    return snapshot


# ──────────────────────────────────────────────────────────────────
# 输出收集主流程
# ──────────────────────────────────────────────────────────────────


def collect_attempt_outputs(
    manager: Any,
    comfyui_client: ComfyUIClient,
    attempt_id: str,
    *,
    storage_dir: Path | None = None,
    environment: str | None = None,
) -> dict[str, Any]:
    """收集 attempt 的所有输出图片。

    流程：
    1. 获取 attempt 和 task 信息
    2. 查询 ComfyUI 历史
    3. 解析所有输出图片
    4. 逐个下载、校验、写入记录
    5. 创建缩略图后台任务
    6. 标记 attempt 为已完成

    返回收集结果统计。
    """
    attempt = get_attempt(manager, attempt_id, environment=environment)
    if not attempt:
        raise ValueError(f"attempt 不存在: {attempt_id}")

    prompt_id = attempt.get("prompt_id")
    if not prompt_id:
        raise ValueError(f"attempt 缺少 prompt_id: {attempt_id}")

    task_id = attempt.get("task_id")
    task = get_task(manager, task_id, environment=environment) if task_id else None
    if not task:
        raise ValueError(f"任务不存在: {task_id}")

    item = task.get("item", {})
    if isinstance(item, str):
        try:
            item = json.loads(item)
        except (TypeError, ValueError):
            item = {}
    elif item is None:
        item = {}

    project_id = item.get("project_id", "")
    shot_page_id = item.get("shot_page_id", "")
    workflow_version_id = item.get("workflow_version_id")
    seed = item.get("seed_value")

    if not project_id or not shot_page_id:
        raise ValueError("跑图项缺少 project_id 或 shot_page_id")

    # 确定 storage 目录
    if storage_dir is None:
        storage_dir = manager.data_root / "storage" / "images"
    storage_dir = Path(storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    # 查询 ComfyUI 历史
    try:
        history = comfyui_client.get_history(prompt_id)
    except ComfyUIError as error:
        raise ValueError(f"查询 ComfyUI 历史失败: {error}") from error

    if not isinstance(history, dict):
        raise ValueError("ComfyUI 历史响应格式异常")

    history_entry = history.get(prompt_id)
    if not history_entry:
        raise ValueError(f"ComfyUI 历史中未找到 prompt_id: {prompt_id}")

    # 解析输出图片
    images = parse_comfyui_outputs(history_entry)
    if not images:
        # 没有图片输出，但任务已完成
        mark_attempt_completed(manager, attempt_id, environment=environment)
        return {
            "attempt_id": attempt_id,
            "prompt_id": prompt_id,
            "collected": 0,
            "failed": 0,
            "image_instances": [],
            "errors": [],
        }

    # 构建快照
    snapshot = build_snapshot(manager, task, attempt, environment=environment)

    # 逐个下载和写入
    collected_instances: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    failed_count = 0

    for img_info in images:
        try:
            file_data = download_and_validate_image(
                comfyui_client, img_info, storage_dir
            )
            # 写入 file 记录
            create_file_record(manager, file_data, environment=environment)
            # 写入 image_instance 记录
            instance = create_image_instance(
                manager,
                project_id=project_id,
                shot_page_id=shot_page_id,
                task_id=task_id,
                attempt_id=attempt_id,
                file_id=file_data["file_id"],
                node_id=img_info.get("node_id"),
                workflow_version_id=workflow_version_id,
                prompt_id=prompt_id,
                width=file_data["width"],
                height=file_data["height"],
                img_format=file_data["format"],
                seed=seed,
                resolved_json=item.get("resolved_api_json"),
                snapshot_json=snapshot,
                environment=environment,
            )
            # 创建缩略图后台任务
            create_thumbnail_jobs(
                manager, file_data["file_id"], environment=environment
            )
            collected_instances.append(instance)
        except Exception as error:
            failed_count += 1
            error_detail: dict[str, Any] = {
                "filename": img_info.get("filename", ""),
                "node_id": img_info.get("node_id", ""),
                "error": str(error),
            }
            errors.append(error_detail)
            logger.error(
                "下载图片失败: filename=%s node_id=%s error=%s",
                img_info.get("filename", ""),
                img_info.get("node_id", ""),
                error,
            )

    # 标记 attempt 为已完成（即使部分图片失败）
    if collected_instances:
        mark_attempt_completed(manager, attempt_id, environment=environment)

    return {
        "attempt_id": attempt_id,
        "prompt_id": prompt_id,
        "collected": len(collected_instances),
        "failed": failed_count,
        "image_instances": collected_instances,
        "errors": errors,
    }


# ──────────────────────────────────────────────────────────────────
# 查询函数
# ──────────────────────────────────────────────────────────────────


def list_image_instances(
    manager: Any,
    *,
    project_id: str | None = None,
    shot_page_id: str | None = None,
    task_id: str | None = None,
    attempt_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出图片实例。"""
    query = "SELECT * FROM image_instances WHERE 1=1"
    params: list[Any] = []
    if project_id:
        query += " AND project_id = ?"
        params.append(project_id)
    if shot_page_id:
        query += " AND shot_page_id = ?"
        params.append(shot_page_id)
    if task_id:
        query += " AND task_id = ?"
        params.append(task_id)
    if attempt_id:
        query += " AND attempt_id = ?"
        params.append(attempt_id)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_image_instance(
    manager: Any,
    instance_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取单个图片实例。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM image_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
    return dict(row) if row else None


def get_file_record(
    manager: Any,
    file_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取文件记录。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM files WHERE id = ?",
            (file_id,),
        ).fetchone()
    return dict(row) if row else None


# ── MOD-08: 审片操作 ─────────────────────────────────────────────


def adopt_image_instance(
    manager: Any,
    instance_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """采用图片实例。已淘汰的实例不能采用。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT id, is_rejected FROM image_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return None
        if row["is_rejected"]:
            raise ValueError("已淘汰的图片实例不能采用。")
        conn.execute(
            "UPDATE image_instances SET is_adopted = 1, adopted_at = ?, updated_at = ? WHERE id = ?",
            (now, now, instance_id),
        )
        conn.commit()
        result = conn.execute(
            "SELECT * FROM image_instances WHERE id = ?", (instance_id,)
        ).fetchone()
    return dict(result) if result else None


def reject_image_instance(
    manager: Any,
    instance_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """淘汰图片实例。已采用的实例不能淘汰。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT id, is_adopted FROM image_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return None
        if row["is_adopted"]:
            raise ValueError("已采用的图片实例不能淘汰。")
        conn.execute(
            "UPDATE image_instances SET is_rejected = 1, rejected_at = ?, updated_at = ? WHERE id = ?",
            (now, now, instance_id),
        )
        conn.commit()
        result = conn.execute(
            "SELECT * FROM image_instances WHERE id = ?", (instance_id,)
        ).fetchone()
    return dict(result) if result else None


def unadopt_image_instance(
    manager: Any,
    instance_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """取消采用图片实例。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT id FROM image_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE image_instances SET is_adopted = 0, adopted_at = NULL, "
            "is_representative = 0, representative_at = NULL, updated_at = ? WHERE id = ?",
            (now, instance_id),
        )
        conn.commit()
        result = conn.execute(
            "SELECT * FROM image_instances WHERE id = ?", (instance_id,)
        ).fetchone()
    return dict(result) if result else None


def set_representative_image_instance(
    manager: Any,
    instance_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """标记图片实例为代表图。必须是已采用状态。同时取消同页其他代表图。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT id, shot_page_id, is_adopted FROM image_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return None
        if not row["is_adopted"]:
            raise ValueError("只有已采用的图片实例才能标记为代表图。")
        # 取消同页其他代表图
        conn.execute(
            "UPDATE image_instances SET is_representative = 0, representative_at = NULL, updated_at = ? "
            "WHERE shot_page_id = ? AND id != ? AND is_representative = 1",
            (now, row["shot_page_id"], instance_id),
        )
        conn.execute(
            "UPDATE image_instances SET is_representative = 1, representative_at = ?, updated_at = ? WHERE id = ?",
            (now, now, instance_id),
        )
        conn.commit()
        result = conn.execute(
            "SELECT * FROM image_instances WHERE id = ?", (instance_id,)
        ).fetchone()
    return dict(result) if result else None


def reorder_adopted_image_instances(
    manager: Any,
    shot_page_id: str,
    instance_ids: list[str],
    *,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """重新排序已采用的图片实例。"""
    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        for idx, iid in enumerate(instance_ids, start=1):
            conn.execute(
                "UPDATE image_instances SET sort_order = ?, updated_at = ? "
                "WHERE id = ? AND shot_page_id = ? AND is_adopted = 1",
                (idx, now, iid, shot_page_id),
            )
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM image_instances WHERE shot_page_id = ? AND is_adopted = 1 "
            "ORDER BY sort_order ASC",
            (shot_page_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_image_instance_tracking(
    manager: Any,
    instance_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """获取图片实例的完整生成追踪信息。"""
    with manager.connection(environment) as conn:
        row = conn.execute(
            "SELECT * FROM image_instances WHERE id = ?",
            (instance_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        # 解析 snapshot_json
        if result.get("snapshot_json"):
            try:
                result["snapshot"] = json.loads(result["snapshot_json"])
            except (json.JSONDecodeError, TypeError):
                result["snapshot"] = None
        else:
            result["snapshot"] = None
        # 解析 resolved_json
        if result.get("resolved_json"):
            try:
                result["resolved"] = json.loads(result["resolved_json"])
            except (json.JSONDecodeError, TypeError):
                result["resolved"] = None
        else:
            result["resolved"] = None
        # 关联文件记录
        file_row = conn.execute(
            "SELECT * FROM files WHERE id = ?",
            (result.get("file_id"),),
        ).fetchone()
        result["file"] = dict(file_row) if file_row else None
    return result


def copy_params_from_instance(
    manager: Any,
    instance_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """从图片实例复制参数，返回可用于再次生成的参数快照。"""
    tracking = get_image_instance_tracking(manager, instance_id, environment=environment)
    if not tracking:
        return None
    snapshot = tracking.get("snapshot") or {}
    return {
        "source_instance_id": instance_id,
        "project_id": tracking.get("project_id"),
        "shot_page_id": tracking.get("shot_page_id"),
        "workflow_version_id": tracking.get("workflow_version_id"),
        "seed": tracking.get("seed"),
        "effective_config": snapshot.get("effective_config"),
        "api_json": snapshot.get("api_json"),
        "character_id": snapshot.get("character_id"),
        "variant_id": snapshot.get("variant_id"),
        "field_sources": snapshot.get("field_sources"),
        "material_mappings": snapshot.get("material_mappings"),
        "spec_values": snapshot.get("spec_values"),
    }


def list_background_jobs(
    manager: Any,
    *,
    job_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """列出后台任务。"""
    query = "SELECT * FROM background_jobs WHERE 1=1"
    params: list[Any] = []
    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def get_file_path(manager: Any, file_id: str, *, environment: str | None = None) -> Path | None:
    """获取文件的本地存储路径。"""
    file_record = get_file_record(manager, file_id, environment=environment)
    if not file_record:
        return None
    storage_key = file_record.get("storage_key", "")
    if not storage_key:
        return None
    return Path(manager.data_root) / "storage" / "images" / storage_key
