"""阶段 3.4 ComfyUI 提交。

把已领取的任务提交到 ComfyUI 执行：

1. 从任务快照加载跑图项
2. 获取工作流版本并解析语义插槽
3. 将插槽值写入工作流副本，生成最终 API JSON
4. 保存实际 API JSON 到 attempt 记录
5. 调用 ComfyUI /prompt
6. 收到 prompt_id 后立即持久化
7. 处理提交超时但可能已进入队列的情况（标记 unknown，不重复提交）

设计原则：
- 幂等：attempt 已有 prompt_id 时直接返回，不重复提交
- 超时安全：网络超时标记 unknown，不自动重试
- 完整记录：API JSON、prompt_id 和错误都持久化到 attempt
- 可追溯：提交时保存完整输入快照，供后续图片实例关联
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .comfyui_client import ComfyUIError, ComfyUIClient
from .compiler import apply_slots_to_api_json, resolve_slots_for_item
from .task_queue import (
    get_attempt,
    mark_attempt_failed,
    mark_attempt_submitted,
    mark_attempt_unknown,
)


# 提交超时（秒）：ComfyUI 接收工作流通常很快，超时可能意味着网络问题
SUBMIT_TIMEOUT_SECONDS = 30.0


def build_api_json_for_item(
    manager: Any,
    item: dict[str, Any],
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """为跑图项构建最终 API JSON。

    流程：
    1. 获取工作流版本
    2. 解析语义插槽
    3. 应用插槽值到工作流
    4. 生成 API JSON

    如果工作流版本不存在或解析失败，抛出 ValueError。
    """
    workflow_version_id = item.get("workflow_version_id")
    if not workflow_version_id:
        raise ValueError("跑图项缺少 workflow_version_id")

    version = manager.get_workflow_version(workflow_version_id, environment=environment)
    if not version:
        raise ValueError(f"工作流版本不存在: {workflow_version_id}")

    # 解析规范化结构
    normalized_data = json.loads(version["normalized_graph"])

    # 如果有预存的 raw_api_json 且无插槽需要解析，直接使用
    workflow_id = item.get("workflow_id", "")
    slots = manager.list_semantic_slots(workflow_id, environment=environment) if workflow_id else []

    if not slots:
        # 无插槽绑定，尝试使用预存 API JSON 或从 normalized 转换
        if version.get("raw_api_json"):
            try:
                return json.loads(version["raw_api_json"])
            except (TypeError, ValueError):
                pass
        # 从 normalized 转换
        from .workflow_models import NormalizedWorkflow
        from .workflow_publish import normalized_to_api_json
        normalized = NormalizedWorkflow.from_dict(normalized_data)
        return normalized_to_api_json(normalized)

    # 有插槽绑定：解析并应用
    # 构建 RenderItem 兼容对象用于插槽解析
    from .compiler import RenderItem
    render_item = _item_dict_to_render_item(item)
    slot_resolutions = resolve_slots_for_item(manager, render_item, environment=environment)
    return apply_slots_to_api_json(normalized_data, slot_resolutions)


def submit_task_to_comfyui(
    manager: Any,
    comfyui_client: ComfyUIClient,
    task_id: str,
    attempt_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any]:
    """提交任务到 ComfyUI 执行。

    流程：
    1. 检查 attempt 是否已有 prompt_id（幂等）
    2. 获取任务快照
    3. 构建 API JSON
    4. 保存 API JSON 到 attempt
    5. 调用 ComfyUI /prompt
    6. 持久化 prompt_id，标记 attempt 为 submitted

    返回包含 prompt_id 和 attempt 信息的字典。

    异常处理：
    - 超时：标记 attempt 为 unknown（可能已进入队列，不重复提交）
    - 其他错误：标记 attempt 为 failed
    """
    # 1. 检查幂等性
    attempt = get_attempt(manager, attempt_id, environment=environment)
    if not attempt:
        raise ValueError(f"attempt 不存在: {attempt_id}")

    if attempt.get("prompt_id"):
        # 已有 prompt_id，直接返回（幂等）
        return {
            "attempt_id": attempt_id,
            "prompt_id": attempt["prompt_id"],
            "already_submitted": True,
        }

    # 2. 获取任务快照
    from .task_queue import get_task
    task = get_task(manager, task_id, environment=environment)
    if not task:
        raise ValueError(f"任务不存在: {task_id}")

    item = task.get("item", {})
    if not item:
        raise ValueError("任务快照为空")

    # 3. 构建 API JSON
    try:
        api_json = build_api_json_for_item(manager, item, environment=environment)
    except (ValueError, TypeError, KeyError) as error:
        # 构建失败：标记 attempt 失败
        mark_attempt_failed(
            manager,
            attempt_id,
            error_message=f"构建 API JSON 失败：{error}",
            error_type="build_error",
            environment=environment,
        )
        raise

    api_json_str = json.dumps(api_json, ensure_ascii=False)

    # 4. 生成 client_id（用于 WebSocket 跟踪）
    client_id = str(uuid4())

    # 5. 提交到 ComfyUI
    try:
        response = comfyui_client.submit_prompt(api_json, client_id=client_id)
    except ComfyUIError as error:
        error_msg = str(error)
        # 判断是否为超时类错误
        if "超时" in error_msg or "timeout" in error_msg.lower():
            # 超时：可能已进入队列，标记 unknown，不重复提交
            mark_attempt_unknown(
                manager,
                attempt_id,
                reason=f"提交超时，可能已进入队列：{error_msg}",
                environment=environment,
            )
            return {
                "attempt_id": attempt_id,
                "prompt_id": None,
                "timeout": True,
                "error": error_msg,
            }
        # 其他错误：标记失败
        mark_attempt_failed(
            manager,
            attempt_id,
            error_message=f"提交 ComfyUI 失败：{error_msg}",
            error_type="submit_error",
            environment=environment,
        )
        raise

    # 6. 解析响应，获取 prompt_id
    prompt_id = response.get("prompt_id") if isinstance(response, dict) else None
    if not prompt_id:
        # ComfyUI 返回了响应但没有 prompt_id
        mark_attempt_failed(
            manager,
            attempt_id,
            error_message="ComfyUI 响应缺少 prompt_id",
            error_type="invalid_response",
            environment=environment,
        )
        raise ValueError(f"ComfyUI 响应缺少 prompt_id: {response}")

    # 检查是否有节点错误
    node_errors = response.get("node_errors", {})
    if node_errors:
        # 有节点错误但 ComfyUI 仍可能接受部分提交
        # 标记为 submitted 但记录错误
        attempt = mark_attempt_submitted(
            manager,
            attempt_id,
            prompt_id=prompt_id,
            api_json=api_json_str,
            environment=environment,
        )
        return {
            "attempt_id": attempt_id,
            "prompt_id": prompt_id,
            "node_errors": node_errors,
            "submitted": True,
        }

    # 7. 持久化 prompt_id，标记 attempt 为 submitted
    attempt = mark_attempt_submitted(
        manager,
        attempt_id,
        prompt_id=prompt_id,
        api_json=api_json_str,
        environment=environment,
    )

    return {
        "attempt_id": attempt_id,
        "prompt_id": prompt_id,
        "client_id": client_id,
        "submitted": True,
    }


def check_comfyui_history(
    manager: Any,
    comfyui_client: ComfyUIClient,
    prompt_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """查询 ComfyUI 历史记录，判断任务是否已完成。

    返回 None 表示历史中不存在该 prompt_id。
    返回字典包含 outputs 信息。
    """
    try:
        history = comfyui_client.get_history(prompt_id)
    except ComfyUIError:
        return None

    if not isinstance(history, dict):
        return None

    # ComfyUI /history/{prompt_id} 返回 {prompt_id: {...}}
    prompt_history = history.get(prompt_id)
    if not prompt_history:
        return None

    return {
        "prompt_id": prompt_id,
        "status": prompt_history.get("status", {}),
        "outputs": prompt_history.get("outputs", {}),
    }


def _item_dict_to_render_item(item: dict[str, Any]) -> Any:
    """将任务快照字典转为 RenderItem 兼容对象。

    用于复用 resolve_slots_for_item 函数。
    """
    from .compiler import RenderItem
    return RenderItem(
        item_id=item.get("item_id", ""),
        sort_key=item.get("sort_key", ""),
        input_hash=item.get("input_hash", ""),
        project_id=item.get("project_id", ""),
        project_name=item.get("project_name", ""),
        chapter_id=item.get("chapter_id", ""),
        chapter_name=item.get("chapter_name", ""),
        large_scene_id=item.get("large_scene_id", ""),
        large_scene_name=item.get("large_scene_name", ""),
        small_scene_id=item.get("small_scene_id", ""),
        small_scene_name=item.get("small_scene_name", ""),
        shot_page_id=item.get("shot_page_id", ""),
        shot_page_title=item.get("shot_page_title", ""),
        branch_id=item.get("branch_id"),
        branch_name=item.get("branch_name"),
        workflow_id=item.get("workflow_id", ""),
        workflow_version_id=item.get("workflow_version_id", ""),
        workflow_label=item.get("workflow_label", ""),
        character_id=item.get("character_id"),
        character_name=item.get("character_name"),
        variant_id=item.get("variant_id"),
        variant_name=item.get("variant_name"),
        spec_values=item.get("spec_values", {}),
        material_mappings=item.get("material_mappings", {}),
        effective_config=item.get("effective_config", {}),
        field_sources=item.get("field_sources", {}),
        slot_resolutions=item.get("slot_resolutions", []),
        resolved_api_json=item.get("resolved_api_json"),
        warnings=item.get("warnings", []),
        instance_count=item.get("instance_count", 1),
        seed_strategy=item.get("seed_strategy", "fixed"),
        seed_value=item.get("seed_value"),
        seed_base=item.get("seed_base"),
    )
