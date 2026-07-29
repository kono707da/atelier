"""ComfyUI HTTP 客户端。

封装与 ComfyUI 服务端的 HTTP 交互，包括：
- 连接测试与系统状态
- 节点定义同步（/object_info）
- 模型资源同步（checkpoints/loras/vaes/embeddings/controlnet 等）
- 工作流提交、历史查询和图片下载（供后续阶段使用）

设计原则：
- 同步调用，使用 httpx.Client 连接池
- 所有调用都有超时控制
- 错误统一抛出 ComfyUIError，由路由层转换为 HTTP 响应
- 不缓存数据：缓存由 database.py 负责
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx


class ComfyUIError(RuntimeError):
    """ComfyUI 调用失败的统一异常类型。"""


@dataclass(frozen=True)
class ComfyUIConnectionConfig:
    """ComfyUI 连接配置。不可变，变更时构造新实例。"""

    base_url: str = "http://127.0.0.1:8188"
    timeout_seconds: float = 10.0
    websocket_url: str = ""

    def with_overrides(
        self,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        websocket_url: str | None = None,
    ) -> ComfyUIConnectionConfig:
        return ComfyUIConnectionConfig(
            base_url=base_url if base_url is not None else self.base_url,
            timeout_seconds=(
                timeout_seconds if timeout_seconds is not None else self.timeout_seconds
            ),
            websocket_url=websocket_url if websocket_url is not None else self.websocket_url,
        )

    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")

    def derived_websocket_url(self) -> str:
        if self.websocket_url:
            return self.websocket_url
        parsed = urlparse(self.normalized_base_url())
        scheme = "wss" if parsed.scheme == "https" else "ws"
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 8188
        return f"{scheme}://{host}:{port}/ws"


@dataclass(frozen=True)
class ComfyUISystemStats:
    """/system_stats 返回的系统状态摘要。"""

    status: str
    system_cpu: str
    devices: list[dict[str, Any]]
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NodeDefinitionSummary:
    """节点定义缓存摘要。"""

    node_count: int
    sha256: str
    custom_node_count: int


class ComfyUIClient:
    """ComfyUI HTTP 客户端。

    每个 ComfyUIClient 实例内部持有 httpx.Client 连接池。
    调用方应在应用生命周期内复用同一实例。
    """

    def __init__(self, config: ComfyUIConnectionConfig | None = None) -> None:
        self._config = config or ComfyUIConnectionConfig()
        self._client: httpx.Client | None = None

    @property
    def config(self) -> ComfyUIConnectionConfig:
        return self._config

    def update_config(self, config: ComfyUIConnectionConfig) -> None:
        """更新连接配置，关闭旧连接池。"""
        self.close()
        self._config = config

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self._config.normalized_base_url(),
                timeout=httpx.Timeout(self._config.timeout_seconds),
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout_override: float | None = None,
    ) -> Any:
        client = self._ensure_client()
        timeout = (
            httpx.Timeout(timeout_override) if timeout_override else httpx.Timeout(self._config.timeout_seconds)
        )
        try:
            response = client.request(
                method,
                path,
                params=params,
                json=json_body,
                timeout=timeout,
            )
        except httpx.ConnectError as error:
            raise ComfyUIError(f"无法连接 ComfyUI：{error}") from error
        except httpx.TimeoutException as error:
            raise ComfyUIError(f"ComfyUI 请求超时：{error}") from error
        except httpx.HTTPError as error:
            raise ComfyUIError(f"ComfyUI HTTP 错误：{error}") from error

        if response.status_code >= 400:
            raise ComfyUIError(
                f"ComfyUI 返回错误状态 {response.status_code}：{response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as error:
            raise ComfyUIError("ComfyUI 响应不是合法 JSON。") from error

    def test_connection(self) -> ComfyUISystemStats:
        """连接测试，返回系统状态摘要。"""
        data = self._request("GET", "/system_stats", timeout_override=5.0)
        if not isinstance(data, dict):
            raise ComfyUIError("/system_stats 返回结构异常。")
        system = data.get("system", {})
        cpu_percent = system.get("cpu", {})
        devices = data.get("devices", [])
        return ComfyUISystemStats(
            status="ok",
            system_cpu=f"{cpu_percent}" if cpu_percent else "unknown",
            devices=devices if isinstance(devices, list) else [],
            raw=data,
        )

    def get_system_stats(self) -> dict[str, Any]:
        """获取原始 /system_stats 数据。"""
        return self._request("GET", "/system_stats")

    def get_object_info(self) -> dict[str, Any]:
        """获取所有节点定义。可能很大（数 MB）。"""
        return self._request("GET", "/object_info", timeout_override=60.0)

    def get_node_info(self, node_class: str) -> dict[str, Any]:
        """获取单个节点定义。"""
        return self._request("GET", f"/object_info/{node_class}")

    def get_models(self, model_type: str) -> list[str]:
        """获取指定类型的模型列表。

        常用类型：checkpoints, loras, vaes, embeddings, controlnet,
        upscale_models, hypernetworks, loras.
        """
        data = self._request("GET", f"/models/{model_type}")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("models"), list):
            return data["models"]
        return []

    def get_embeddings(self) -> list[str]:
        """获取 embeddings 列表。"""
        data = self._request("GET", "/embeddings")
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("embeddings"), list):
            return data["embeddings"]
        return []

    def get_queue(self) -> dict[str, Any]:
        """获取队列状态。"""
        return self._request("GET", "/prompt")

    def get_history(self, prompt_id: str | None = None) -> dict[str, Any]:
        """获取历史记录。"""
        if prompt_id:
            return self._request("GET", f"/history/{prompt_id}")
        return self._request("GET", "/history")

    def submit_prompt(self, graph: dict[str, Any], client_id: str | None = None) -> dict[str, Any]:
        """提交工作流到 ComfyUI。

        供阶段3使用，本阶段不调用。
        """
        body: dict[str, Any] = {"prompt": graph}
        if client_id:
            body["client_id"] = client_id
        return self._request("POST", "/prompt", json_body=body)

    def download_image(
        self, filename: str, subfolder: str = "", folder_type: str = "output"
    ) -> bytes:
        """下载 ComfyUI 输出的图片。

        供阶段3使用，本阶段不调用。
        """
        client = self._ensure_client()
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type,
        }
        try:
            response = client.get(
                "/view",
                params=params,
                timeout=httpx.Timeout(self._config.timeout_seconds),
            )
        except httpx.HTTPError as error:
            raise ComfyUIError(f"下载图片失败：{error}") from error
        if response.status_code >= 400:
            raise ComfyUIError(
                f"下载图片返回错误状态 {response.status_code}"
            )
        return response.content

    def interrupt(self) -> dict[str, Any]:
        """中断当前生成。"""
        return self._request("POST", "/interrupt")

    def free(self, unload_models: bool = False, free_memory: bool = False) -> dict[str, Any]:
        """释放模型或显存。"""
        return self._request(
            "POST",
            "/free",
            json_body={"unload_models": unload_models, "free_memory": free_memory},
        )


def compute_object_info_sha256(object_info: dict[str, Any]) -> str:
    """计算节点定义的 SHA256 摘要。

    用于判断节点定义是否变化，避免重复写入缓存。
    """
    canonical = json.dumps(object_info, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def summarize_node_definitions(
    object_info: dict[str, Any],
) -> NodeDefinitionSummary:
    """汇总节点定义信息。"""
    node_count = len(object_info) if isinstance(object_info, dict) else 0
    custom_count = 0
    for info in object_info.values():
        if isinstance(info, dict) and info.get("python_module", "").startswith("custom_nodes."):
            custom_count += 1
    return NodeDefinitionSummary(
        node_count=node_count,
        sha256=compute_object_info_sha256(object_info),
        custom_node_count=custom_count,
    )


def extract_resource_lists(object_info: dict[str, Any]) -> dict[str, list[str]]:
    """从 object_info 提取模型资源列表。

    ComfyUI 的节点定义中，CheckpointLoader 等节点的 input 包含模型列表。
    此函数从常见节点中提取资源列表，作为 /models/{type} 的补充。
    """
    resources: dict[str, list[str]] = {}

    def _extract_from_node(node_class: str, input_name: str, key: str) -> None:
        info = object_info.get(node_class)
        if not isinstance(info, dict):
            return
        inputs = info.get("input", {}).get("required", {})
        if not isinstance(inputs, dict):
            return
        spec = inputs.get(input_name)
        if isinstance(spec, list) and len(spec) >= 1 and isinstance(spec[0], list):
            resources[key] = list(spec[0])

    _extract_from_node("CheckpointLoaderSimple", "ckpt_name", "checkpoints")
    _extract_from_node("CheckpointLoader", "config_name", "checkpoints")
    _extract_from_node("LoraLoader", "lora_name", "loras")
    _extract_from_node("VAELoader", "vae_name", "vaes")
    _extract_from_node("ControlNetLoader", "control_net_name", "controlnet")
    _extract_from_node("UpscaleModelLoader", "model_name", "upscale_models")
    _extract_from_node("HypernetworkLoader", "hypernetwork_name", "hypernetworks")
    _extract_from_node("CLIPVisionLoader", "clip_name", "clip_vision")
    return resources
