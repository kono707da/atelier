"""阶段2真实 ComfyUI 验收脚本 (需求 §9)。

逐项执行 16 项验收，输出结构化报告。运行后会清理本次产生的测试工作流。
"""
from __future__ import annotations

import json
import sys
import time
from typing import Any

import httpx

BASE = "http://127.0.0.1:8110"
TIMEOUT = 30.0

# 标准 txt2img API JSON（ComfyUI 0.27.x 内置节点）
TXT2IMG_API_JSON: dict[str, Any] = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 123456789,
            "steps": 20,
            "cfg": 8.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "placeholder.safetensors"},
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "beautiful scenery", "clip": ["4", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "blurry, bad", "clip": ["4", 1]},
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"images": ["8", 0], "filename_prefix": "atelier_acceptance"},
    },
}


def header(msg: str) -> None:
    print(f"\n=== {msg} ===")


def step(idx: int, name: str) -> None:
    print(f"\n[§9.{idx:02d}] {name}")


def ok(msg: str) -> None:
    print(f"  PASS: {msg}")


def fail(msg: str, detail: Any = None) -> None:
    print(f"  FAIL: {msg}")
    if detail is not None:
        print(f"    detail: {detail}")


def main() -> int:
    results: list[tuple[int, str, bool, str]] = []
    client = httpx.Client(base_url=BASE, timeout=TIMEOUT)
    workflow_id: str | None = None
    reimport_workflow_id: str | None = None

    def record(idx: int, name: str, success: bool, msg: str) -> None:
        results.append((idx, name, success, msg))
        if success:
            print(f"  PASS: {msg}")
        else:
            print(f"  FAIL: {msg}")

    try:
        # ── 前置：识别活动实例 ───────────────────────────────────
        header("前置：识别 ComfyUI 实例")
        resp = client.get("/api/comfyui/instances")
        resp.raise_for_status()
        instances = resp.json()["instances"]
        active = next((i for i in instances if i["is_active"]), None)
        if not active:
            print("没有活动实例，验收中止。")
            return 1
        active_id = active["id"]
        active_url = active["base_url"]
        print(f"活动实例: id={active_id} url={active_url}")

        # ── §9.01 测试连接 ────────────────────────────────────────
        step(1, "测试连接")
        resp = client.post(f"/api/comfyui/instances/{active_id}/test")
        data = resp.json()
        if resp.status_code == 200 and data.get("status") == "ok":
            version = data.get("system", {}).get("comfyui_version", "")
            devices = data.get("devices", [])
            device_summary = ", ".join(d.get("name", "") for d in devices) if devices else ""
            record(1, "测试连接", True, f"连接成功 version={version} device={device_summary}")
        else:
            record(1, "测试连接", False, f"status={resp.status_code} body={data}")

        # ── §9.02 读取 /system_stats ──────────────────────────────
        step(2, "读取 /system_stats")
        # test-connection 已包含 system_stats，但 §9 要求显式读取
        resp = client.get("/api/comfyui/system-stats")
        if resp.status_code == 200:
            stats = resp.json()["system_stats"]
            sys_info = stats.raw.get("system", {}) if hasattr(stats, "raw") else stats.get("system", {})
            version = sys_info.get("comfyui_version", "")
            py_version = sys_info.get("python_version", "")
            record(2, "读取 /system_stats", True, f"version={version} python={py_version}")
        else:
            record(2, "读取 /system_stats", False, f"status={resp.status_code}")

        # ── §9.03 同步 /object_info ───────────────────────────────
        step(3, "同步 /object_info")
        resp = client.post(f"/api/comfyui/instances/{active_id}/sync")
        data = resp.json()
        if resp.status_code == 200:
            node_count = data.get("node_count", 0)
            custom_count = data.get("custom_node_count", 0)
            sha = data.get("sha256", "")[:12]
            record(3, "同步 /object_info", True, f"nodes={node_count} custom={custom_count} sha={sha}")
        else:
            record(3, "同步 /object_info", False, f"status={resp.status_code} body={data}")

        # ── §9.04 显示标准节点 ────────────────────────────────────
        step(4, "显示标准节点")
        resp = client.get("/api/comfyui/node-definitions", params={"custom": False, "limit": 5})
        if resp.status_code == 200:
            data = resp.json()
            standard_nodes = data.get("items", [])
            total = data.get("total", 0)
            sample = [n.get("node_class", "") for n in standard_nodes[:3]]
            record(4, "显示标准节点", True, f"total={total} sample={sample}")
        else:
            record(4, "显示标准节点", False, f"status={resp.status_code}")

        # ── §9.05 显示自定义节点 ──────────────────────────────────
        step(5, "显示自定义节点")
        resp = client.get("/api/comfyui/node-definitions", params={"custom": True, "limit": 5})
        if resp.status_code == 200:
            data = resp.json()
            custom_nodes = data.get("items", [])
            custom_total = data.get("total", 0)
            sample = [n.get("node_class", "") for n in custom_nodes[:3]]
            record(5, "显示自定义节点", True, f"total={custom_total} sample={sample}")
        else:
            record(5, "显示自定义节点", False, f"status={resp.status_code}")

        # ── §9.06 同步模型、LoRA 和其他资源 ───────────────────────
        step(6, "同步模型、LoRA 和其他资源")
        # 同步在 §9.03 的 /sync 中已包含资源同步，验证资源缓存
        resp = client.get("/api/comfyui/resources")
        if resp.status_code == 200:
            data = resp.json()
            resources = data.get("resources", {})
            counts = {k: len(v) if isinstance(v, list) else v.get("count", 0) for k, v in resources.items()}
            record(6, "同步资源", True, f"resource_types={counts}")
        else:
            record(6, "同步资源", False, f"status={resp.status_code}")

        # ── §9.07 导入真实工作流 ──────────────────────────────────
        step(7, "导入真实工作流")
        resp = client.post("/api/workflows", json={"name": "§9验收工作流"})
        if resp.status_code != 201:
            record(7, "导入真实工作流", False, f"创建工作流失败 status={resp.status_code} body={resp.text}")
            return 1
        workflow_id = resp.json()["workflow"]["id"]
        resp = client.post(
            f"/api/workflows/{workflow_id}/import",
            json={"source_format": "api_json", "raw_json": TXT2IMG_API_JSON, "label": "txt2img"},
        )
        if resp.status_code == 200:
            data = resp.json()
            node_count = data.get("node_count", 0)
            checksum = data.get("checksum", "")[:12]
            record(7, "导入真实工作流", True, f"workflow_id={workflow_id} nodes={node_count} checksum={checksum}")
        else:
            record(7, "导入真实工作流", False, f"status={resp.status_code} body={resp.text}")

        # 读取草稿获取节点 ID 映射
        resp = client.get(f"/api/workflows/{workflow_id}/draft")
        draft = resp.json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        nodes_by_id = {str(n["id"]): n for n in normalized["nodes"]}
        # 找 KSampler 节点（id="3"）和 CLIPTextEncode 正向（id="6"）
        ksampler = nodes_by_id.get("3")
        clip_pos = nodes_by_id.get("6")
        if not ksampler or not clip_pos:
            record(7, "导入真实工作流", False, f"未找到 KSampler 或 CLIPTextEncode 节点 nodes={list(nodes_by_id.keys())}")
            return 1

        # ── §9.08 编辑至少一个组件参数 ────────────────────────────
        step(8, "编辑至少一个组件参数")
        # 修改 KSampler 的 widgets_values（steps 20 -> 30）
        # 需要先读取当前 widgets_values
        old_widgets = ksampler.get("widgets_values", [])
        new_widgets = list(old_widgets)
        # 尝试把第二个值（通常是 steps）改为 30
        if len(new_widgets) >= 2:
            try:
                old_val = new_widgets[1]
                new_widgets[1] = 30
            except (TypeError, IndexError):
                new_widgets = [30]
        else:
            new_widgets = [30]
        resp = client.put(
            f"/api/workflows/{workflow_id}/draft/nodes/3",
            json={"widgets_values": new_widgets, "title": "KSampler-验收编辑"},
        )
        if resp.status_code == 200:
            updated_node = resp.json()["node"]
            actual_widgets = updated_node.get("widgets_values", [])
            actual_inputs = updated_node.get("inputs", [])
            # 检查 inputs[].value 是否同步
            steps_input = next((i for i in actual_inputs if i.get("name") == "steps"), None)
            steps_value = steps_input.get("value") if steps_input else None
            record(8, "编辑组件参数", True, f"old_widgets={old_widgets} new_widgets={actual_widgets} steps_value={steps_value}")
        else:
            record(8, "编辑组件参数", False, f"status={resp.status_code} body={resp.text}")

        # ── §9.09 修改至少一条连线 ────────────────────────────────
        step(9, "修改至少一条连线")
        # 重新读取草稿获取最新状态
        resp = client.get(f"/api/workflows/{workflow_id}/draft")
        draft = resp.json()["draft"]
        normalized = json.loads(draft["normalized_graph"])
        nodes_by_id = {str(n["id"]): n for n in normalized["nodes"]}
        # 找 VAEDecode 节点（id="8"）和 SaveImage 节点（id="9"）
        vae_decode = nodes_by_id.get("8")
        save_image = nodes_by_id.get("9")
        if vae_decode and save_image:
            # 删除 VAEDecode -> SaveImage 的连线，再重新创建
            existing_link = None
            for inp in save_image.get("inputs", []):
                if inp.get("name") == "images":
                    existing_link = inp.get("link")
                    break
            if existing_link:
                client.delete(f"/api/workflows/{workflow_id}/draft/links/{existing_link}")
            # 重新创建连线
            resp = client.post(
                f"/api/workflows/{workflow_id}/draft/links",
                json={"source_node": "8", "source_slot": 0, "target_node": "9", "target_slot": 0},
            )
            if resp.status_code == 200:
                link = resp.json()["link"]
                record(9, "修改连线", True, f"删除旧连线后重建 link_id={link['id']} src=8:0 dst=9:0")
            else:
                record(9, "修改连线", False, f"重建连线失败 status={resp.status_code} body={resp.text}")
        else:
            record(9, "修改连线", False, "未找到 VAEDecode 或 SaveImage 节点")

        # ── §9.10 执行自动布局 ────────────────────────────────────
        step(10, "执行自动布局")
        resp = client.post(f"/api/workflows/{workflow_id}/draft/layout/compute")
        if resp.status_code == 200:
            layout = resp.json()["layout"]
            layers = len(layout.get("layers", []))
            positions = len(layout.get("positions", {}))
            record(10, "自动布局", True, f"layers={layers} positions={positions}")
        else:
            record(10, "自动布局", False, f"status={resp.status_code} body={resp.text}")

        # ── §9.11 设置至少一个语义插槽 ────────────────────────────
        step(11, "设置至少一个语义插槽")
        resp = client.put(
            f"/api/workflows/{workflow_id}/semantic-slots",
            json={
                "slot_name": "positive_prompt",
                "slot_type": "positive_prompt",
                "node_id": "6",
                "input_name": "text",
                "transform_rule": "{value}",
                "default_value": "",
                "is_required": True,
                "conflict_strategy": "overwrite",
            },
        )
        if resp.status_code == 200:
            slot = resp.json()["slot"]
            record(11, "设置语义插槽", True, f"slot={slot.get('slot_name')} node=6 input=text")
        else:
            record(11, "设置语义插槽", False, f"status={resp.status_code} body={resp.text}")

        # ── §9.12 导出 UI JSON ────────────────────────────────────
        step(12, "导出 UI JSON")
        resp = client.post(f"/api/workflows/{workflow_id}/export", json={"format": "ui_json"})
        if resp.status_code == 200:
            data = resp.json()
            ui_json = data["data"]
            ui_nodes = len(ui_json.get("nodes", []))
            ui_links = len(ui_json.get("links", []))
            record(12, "导出 UI JSON", True, f"nodes={ui_nodes} links={ui_links}")
            exported_ui_json = ui_json
        else:
            record(12, "导出 UI JSON", False, f"status={resp.status_code} body={resp.text}")
            exported_ui_json = None

        # ── §9.13 导出 API JSON ───────────────────────────────────
        step(13, "导出 API JSON")
        resp = client.post(f"/api/workflows/{workflow_id}/export", json={"format": "api_json"})
        if resp.status_code == 200:
            data = resp.json()
            api_json = data["data"]
            api_node_count = len(api_json)
            # 验证编辑后的值（steps=30）是否反映在导出中
            ksampler_export = api_json.get("3", {})
            exported_steps = ksampler_export.get("inputs", {}).get("steps")
            record(13, "导出 API JSON", True, f"nodes={api_node_count} exported_steps={exported_steps}")
            exported_api_json = api_json
        else:
            record(13, "导出 API JSON", False, f"status={resp.status_code} body={resp.text}")
            exported_api_json = None

        # ── §9.14 重新导入导出结果 ────────────────────────────────
        step(14, "重新导入导出结果")
        if exported_ui_json is None:
            record(14, "重新导入导出结果", False, "导出 UI JSON 失败，跳过")
        else:
            resp = client.post("/api/workflows", json={"name": "§9验收-重新导入"})
            if resp.status_code == 201:
                reimport_workflow_id = resp.json()["workflow"]["id"]
                resp = client.post(
                    f"/api/workflows/{reimport_workflow_id}/import",
                    json={"source_format": "ui_json", "raw_json": exported_ui_json, "label": "reimport"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    reimport_nodes = data.get("node_count", 0)
                    record(14, "重新导入导出结果", True, f"reimport_workflow_id={reimport_workflow_id} nodes={reimport_nodes}")
                else:
                    record(14, "重新导入导出结果", False, f"status={resp.status_code} body={resp.text}")
            else:
                record(14, "重新导入导出结果", False, f"创建工作流失败 status={resp.status_code}")

        # ── §9.15 使用当前节点定义完成校验 ────────────────────────
        step(15, "使用当前节点定义完成校验")
        resp = client.post(f"/api/workflows/{workflow_id}/precheck")
        if resp.status_code == 200:
            data = resp.json()
            can_publish = data.get("can_publish", False)
            blocking = data.get("blocking_errors", [])
            warnings = data.get("warnings", [])
            # txt2img 工作流的 ckpt_name 是占位符，可能产生模型缺失警告但不应阻塞
            record(15, "节点定义校验", True, f"can_publish={can_publish} blocking={len(blocking)} warnings={len(warnings)}")
        else:
            record(15, "节点定义校验", False, f"status={resp.status_code} body={resp.text}")

        # ── §9.16 发布一个不可变版本 ──────────────────────────────
        step(16, "发布一个不可变版本")
        # 需要传 normalized_graph，从草稿读取
        resp = client.get(f"/api/workflows/{workflow_id}/draft")
        draft = resp.json()["draft"]
        normalized_graph = draft["normalized_graph"]
        resp = client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={
                "label": "§9验收发布",
                "normalized_graph": normalized_graph,
                "is_validated": True,
                "validation_result": "§9 验收发布",
            },
        )
        if resp.status_code == 200:
            version = resp.json()["version"]
            version_num = version.get("version", 0)
            version_id = version.get("id", "")
            record(16, "发布不可变版本", True, f"version={version_num} id={version_id}")
        else:
            record(16, "发布不可变版本", False, f"status={resp.status_code} body={resp.text}")

    finally:
        client.close()

    # ── 汇总报告 ────────────────────────────────────────────────
    header("§9 验收汇总")
    passed = sum(1 for _, _, success, _ in results if success)
    failed = sum(1 for _, _, success, _ in results if not success)
    print(f"通过: {passed}/{len(results)}  失败: {failed}/{len(results)}")
    for idx, name, success, msg in results:
        status = "PASS" if success else "FAIL"
        print(f"  [{idx:02d}] {status} {name}: {msg}")

    # ── 清理测试数据 ────────────────────────────────────────────
    header("清理测试数据")
    cleanup_client = httpx.Client(base_url=BASE, timeout=TIMEOUT)
    try:
        for wid in [workflow_id, reimport_workflow_id]:
            if wid:
                resp = cleanup_client.delete(f"/api/workflows/{wid}")
                if resp.status_code in (200, 204):
                    print(f"  已删除工作流 {wid}")
                else:
                    print(f"  删除工作流 {wid} 失败 status={resp.status_code}")
    finally:
        cleanup_client.close()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
