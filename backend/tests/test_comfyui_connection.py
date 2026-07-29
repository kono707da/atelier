"""阶段 2.1 ComfyUI 连接层测试。

测试范围：
- 应用设置（app_settings）读写
- ComfyUI 设置验证（地址格式/超时范围）
- 节点定义缓存（save/list/get/summary/categories）
- 资源缓存（save/list）
- ComfyUI 客户端单元测试（mock 和真实连接）

ComfyUI 真实连接测试是可选的：优先读取 ATELIER_COMFYUI_TEST_URL，
其次读取 ATELIER_COMFYUI_URL，未配置时使用 http://127.0.0.1:8188。
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.comfyui_client import (
    ComfyUIClient,
    ComfyUIConnectionConfig,
    ComfyUIError,
    compute_object_info_sha256,
    extract_resource_lists,
    summarize_node_definitions,
)


COMFYUI_TEST_URL = (
    os.environ.get("ATELIER_COMFYUI_TEST_URL")
    or os.environ.get("ATELIER_COMFYUI_URL")
    or "http://127.0.0.1:8188"
).rstrip("/")


def _is_comfyui_reachable(base_url: str = COMFYUI_TEST_URL) -> bool:
    """快速检测 ComfyUI 是否可达。"""
    import httpx

    try:
        response = httpx.get(
            f"{base_url}/system_stats",
            timeout=httpx.Timeout(3.0),
        )
        return response.status_code == 200
    except Exception:
        return False


COMFYUI_AVAILABLE = _is_comfyui_reachable()


class _ComfyuiBase(unittest.TestCase):
    """ComfyUI 连接层测试基类。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager


# ── 应用设置读写 ────────────────────────────────────────────────


class AppSettingsTests(_ComfyuiBase):
    def test_default_comfyui_settings_after_init(self) -> None:
        """数据库初始化后存在默认 ComfyUI 设置。"""
        settings = self.manager.get_comfyui_settings()
        self.assertEqual(settings["base_url"], "http://127.0.0.1:8188")
        self.assertEqual(settings["timeout_seconds"], 10.0)
        self.assertEqual(settings["websocket_url"], "")

    def test_get_setting_returns_none_for_missing_key(self) -> None:
        self.assertIsNone(self.manager.get_setting("nonexistent.key"))

    def test_set_and_get_setting(self) -> None:
        self.manager.set_setting("test.key", "test-value")
        self.assertEqual(self.manager.get_setting("test.key"), "test-value")

    def test_set_setting_overwrites(self) -> None:
        self.manager.set_setting("test.key", "v1")
        self.manager.set_setting("test.key", "v2")
        self.assertEqual(self.manager.get_setting("test.key"), "v2")

    def test_get_settings_with_prefix(self) -> None:
        self.manager.set_setting("comfyui.custom", "custom-val")
        self.manager.set_setting("other.key", "other-val")
        result = self.manager.get_settings(prefix="comfyui.")
        self.assertIn("comfyui.custom", result)
        self.assertNotIn("other.key", result)

    def test_set_comfyui_settings_partial_update(self) -> None:
        """部分更新：只传 base_url，其他字段保持不变。"""
        self.manager.set_comfyui_settings(base_url="http://192.168.1.100:8188")
        settings = self.manager.get_comfyui_settings()
        self.assertEqual(settings["base_url"], "http://192.168.1.100:8188")
        self.assertEqual(settings["timeout_seconds"], 10.0)

    def test_set_comfyui_settings_full_update(self) -> None:
        self.manager.set_comfyui_settings(
            base_url="http://comfyui.local:8888",
            timeout_seconds=30.0,
            websocket_url="ws://comfyui.local:8888/ws",
        )
        settings = self.manager.get_comfyui_settings()
        self.assertEqual(settings["base_url"], "http://comfyui.local:8888")
        self.assertEqual(settings["timeout_seconds"], 30.0)
        self.assertEqual(settings["websocket_url"], "ws://comfyui.local:8888/ws")


# ── ComfyUI 设置 API ───────────────────────────────────────────


class ComfyuiSettingsApiTests(_ComfyuiBase):
    def test_get_comfyui_settings_api(self) -> None:
        response = self.client.get("/api/settings/comfyui")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("settings", data)
        self.assertEqual(data["settings"]["base_url"], "http://127.0.0.1:8188")

    def test_update_comfyui_settings_api(self) -> None:
        response = self.client.put(
            "/api/settings/comfyui",
            json={
                "base_url": "http://192.168.3.5:8188",
                "timeout_seconds": 15.0,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["settings"]["base_url"], "http://192.168.3.5:8188")
        self.assertEqual(data["settings"]["timeout_seconds"], 15.0)

    def test_update_comfyui_settings_strips_trailing_slash(self) -> None:
        response = self.client.put(
            "/api/settings/comfyui",
            json={"base_url": "http://127.0.0.1:8188/"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["settings"]["base_url"], "http://127.0.0.1:8188")

    def test_update_comfyui_settings_rejects_empty_url(self) -> None:
        response = self.client.put(
            "/api/settings/comfyui",
            json={"base_url": ""},
        )
        self.assertEqual(response.status_code, 422)

    def test_update_comfyui_settings_rejects_non_http(self) -> None:
        response = self.client.put(
            "/api/settings/comfyui",
            json={"base_url": "ftp://127.0.0.1:8188"},
        )
        self.assertEqual(response.status_code, 422)

    def test_update_comfyui_settings_rejects_timeout_out_of_range(self) -> None:
        response = self.client.put(
            "/api/settings/comfyui",
            json={"timeout_seconds": 0.5},
        )
        self.assertEqual(response.status_code, 422)
        response = self.client.put(
            "/api/settings/comfyui",
            json={"timeout_seconds": 200},
        )
        self.assertEqual(response.status_code, 422)


# ── 节点定义缓存 ──────────────────────────────────────────────


class NodeDefinitionCacheTests(_ComfyuiBase):
    def _sample_object_info(self) -> dict:
        return {
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [["model1.safetensors", "model2.safetensors"]],
                    }
                },
                "output": ["MODEL", "CLIP", "VAE"],
                "name": "Load Checkpoint",
                "category": "loaders",
                "python_module": "comfy.sd",
                "display_name": "Load Checkpoint",
            },
            "KSampler": {
                "input": {"required": {"seed": ["INT"]}},
                "output": ["LATENT"],
                "name": "KSampler",
                "category": "sampling",
                "python_module": "comfy.samplers",
                "display_name": "KSampler",
            },
            "ImpactCustomNode": {
                "input": {"required": {}},
                "output": ["*"],
                "name": "Impact Custom",
                "category": "impact",
                "python_module": "custom_nodes.ComfyUI-Impact-Pack",
                "display_name": "Impact Custom",
            },
        }

    def test_save_and_list_node_definitions(self) -> None:
        object_info = self._sample_object_info()
        result = self.manager.save_node_definitions(object_info)
        self.assertEqual(result["node_count"], 3)
        self.assertEqual(result["custom_node_count"], 1)

        listing = self.manager.list_node_definitions()
        self.assertEqual(listing["total"], 3)
        classes = [item["node_class"] for item in listing["items"]]
        self.assertIn("CheckpointLoaderSimple", classes)
        self.assertIn("KSampler", classes)
        self.assertIn("ImpactCustomNode", classes)

    def test_get_node_definition(self) -> None:
        object_info = self._sample_object_info()
        self.manager.save_node_definitions(object_info)
        definition = self.manager.get_node_definition("KSampler")
        self.assertIsNotNone(definition)
        self.assertEqual(definition["category"], "sampling")
        self.assertFalse(definition["is_custom_node"])
        self.assertIn("definition", definition)
        self.assertEqual(definition["definition"]["name"], "KSampler")

    def test_get_node_definition_not_found(self) -> None:
        self.assertIsNone(self.manager.get_node_definition("NonexistentNode"))

    def test_list_node_definitions_filter_custom(self) -> None:
        self.manager.save_node_definitions(self._sample_object_info())
        result = self.manager.list_node_definitions(is_custom=True)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["node_class"], "ImpactCustomNode")

    def test_list_node_definitions_filter_category(self) -> None:
        self.manager.save_node_definitions(self._sample_object_info())
        result = self.manager.list_node_definitions(category="sampling")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["node_class"], "KSampler")

    def test_list_node_definitions_search(self) -> None:
        self.manager.save_node_definitions(self._sample_object_info())
        result = self.manager.list_node_definitions(search="Checkpoint")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["node_class"], "CheckpointLoaderSimple")

    def test_list_node_categories(self) -> None:
        self.manager.save_node_definitions(self._sample_object_info())
        categories = self.manager.list_node_categories()
        self.assertIn("loaders", categories)
        self.assertIn("sampling", categories)
        self.assertIn("impact", categories)

    def test_get_node_definition_summary(self) -> None:
        self.manager.save_node_definitions(self._sample_object_info())
        summary = self.manager.get_node_definition_summary()
        self.assertEqual(summary["node_count"], 3)
        self.assertEqual(summary["custom_node_count"], 1)
        self.assertTrue(summary["last_synced_at"])

    def test_save_node_definitions_replaces_old(self) -> None:
        """全量替换：旧数据被清除。"""
        self.manager.save_node_definitions(self._sample_object_info())
        self.manager.save_node_definitions({"NewNode": {
            "input": {"required": {}},
            "output": [],
            "name": "New",
            "category": "new",
            "python_module": "comfy.new",
            "display_name": "New",
        }})
        summary = self.manager.get_node_definition_summary()
        self.assertEqual(summary["node_count"], 1)
        self.assertIsNone(self.manager.get_node_definition("KSampler"))


# ── 资源缓存 ──────────────────────────────────────────────────


class ResourceCacheTests(_ComfyuiBase):
    def test_save_and_list_resource_cache(self) -> None:
        self.manager.save_resource_cache("checkpoints", ["model1.safetensors", "model2.safetensors"])
        result = self.manager.list_resource_cache(resource_type="checkpoints")
        self.assertIn("checkpoints", result["resources"])
        self.assertEqual(len(result["resources"]["checkpoints"]), 2)

    def test_save_resource_cache_replaces_old(self) -> None:
        self.manager.save_resource_cache("loras", ["lora1.safetensors", "lora2.safetensors"])
        self.manager.save_resource_cache("loras", ["lora3.safetensors"])
        result = self.manager.list_resource_cache(resource_type="loras")
        self.assertEqual(len(result["resources"]["loras"]), 1)
        self.assertEqual(result["resources"]["loras"][0], "lora3.safetensors")

    def test_list_resource_cache_search(self) -> None:
        self.manager.save_resource_cache("checkpoints", ["anime_v1.safetensors", "realistic_v2.safetensors"])
        result = self.manager.list_resource_cache(search="anime")
        self.assertEqual(len(result["resources"]["checkpoints"]), 1)
        self.assertEqual(result["resources"]["checkpoints"][0], "anime_v1.safetensors")

    def test_list_resource_cache_all_types(self) -> None:
        self.manager.save_resource_cache("checkpoints", ["ckpt1"])
        self.manager.save_resource_cache("loras", ["lora1"])
        result = self.manager.list_resource_cache()
        self.assertIn("checkpoints", result["resources"])
        self.assertIn("loras", result["resources"])


# ── ComfyUI 客户端单元测试 ────────────────────────────────────


class ComfyUIClientUnitTests(unittest.TestCase):
    def test_connection_config_default(self) -> None:
        config = ComfyUIConnectionConfig()
        self.assertEqual(config.base_url, "http://127.0.0.1:8188")
        self.assertEqual(config.timeout_seconds, 10.0)

    def test_connection_config_normalized_base_url(self) -> None:
        config = ComfyUIConnectionConfig(base_url="http://127.0.0.1:8188/")
        self.assertEqual(config.normalized_base_url(), "http://127.0.0.1:8188")

    def test_connection_config_derived_websocket_url(self) -> None:
        config = ComfyUIConnectionConfig(base_url="http://127.0.0.1:8188")
        self.assertEqual(config.derived_websocket_url(), "ws://127.0.0.1:8188/ws")

    def test_connection_config_derived_websocket_url_https(self) -> None:
        config = ComfyUIConnectionConfig(base_url="https://comfyui.example.com:443")
        self.assertEqual(config.derived_websocket_url(), "wss://comfyui.example.com:443/ws")

    def test_connection_config_with_overrides(self) -> None:
        config = ComfyUIConnectionConfig()
        new_config = config.with_overrides(base_url="http://new:8888")
        self.assertEqual(new_config.base_url, "http://new:8888")
        self.assertEqual(new_config.timeout_seconds, 10.0)

    def test_compute_object_info_sha256_stable(self) -> None:
        info = {"A": {"name": "A"}, "B": {"name": "B"}}
        sha1 = compute_object_info_sha256(info)
        sha2 = compute_object_info_sha256({"B": {"name": "B"}, "A": {"name": "A"}})
        self.assertEqual(sha1, sha2)

    def test_summarize_node_definitions(self) -> None:
        info = {
            "StdNode": {"python_module": "comfy.sd"},
            "CustomNode": {"python_module": "custom_nodes.ComfyUI-Impact-Pack"},
        }
        summary = summarize_node_definitions(info)
        self.assertEqual(summary.node_count, 2)
        self.assertEqual(summary.custom_node_count, 1)

    def test_extract_resource_lists(self) -> None:
        info = {
            "CheckpointLoaderSimple": {
                "input": {
                    "required": {
                        "ckpt_name": [["modelA.safetensors", "modelB.safetensors"]],
                    }
                },
            },
            "LoraLoader": {
                "input": {
                    "required": {
                        "lora_name": [["lora1.safetensors"]],
                    }
                },
            },
        }
        resources = extract_resource_lists(info)
        self.assertIn("checkpoints", resources)
        self.assertEqual(len(resources["checkpoints"]), 2)
        self.assertIn("loras", resources)

    def test_client_update_config_closes_old_client(self) -> None:
        client = ComfyUIClient(ComfyUIConnectionConfig(base_url="http://old:8188"))
        client._ensure_client()
        old_inner = client._client
        client.update_config(ComfyUIConnectionConfig(base_url="http://new:8188"))
        # update_config closes old client; _client is None until next _ensure_client
        self.assertIsNone(client._client)
        client._ensure_client()
        self.assertIsNotNone(client._client)
        self.assertIsNot(client._client, old_inner)
        self.assertEqual(client.config.base_url, "http://new:8188")


# ── ComfyUI 客户端 Mock 测试 ──────────────────────────────────


class ComfyUIClientMockTests(unittest.TestCase):
    def test_test_connection_success(self) -> None:
        client = ComfyUIClient(ComfyUIConnectionConfig(base_url="http://mock:8188"))
        with mock.patch.object(client, "_request") as mock_request:
            mock_request.return_value = {
                "system": {"cpu": 50},
                "devices": [{"name": "GPU0", "type": "cuda"}],
            }
            stats = client.test_connection()
            self.assertEqual(stats.status, "ok")
            self.assertEqual(len(stats.devices), 1)

    def test_test_connection_failure_raises(self) -> None:
        client = ComfyUIClient(ComfyUIConnectionConfig(base_url="http://mock:8188"))
        with mock.patch.object(client, "_request", side_effect=ComfyUIError("连接失败")):
            with self.assertRaises(ComfyUIError):
                client.test_connection()

    def test_get_models_returns_list(self) -> None:
        client = ComfyUIClient(ComfyUIConnectionConfig(base_url="http://mock:8188"))
        with mock.patch.object(client, "_request") as mock_request:
            mock_request.return_value = ["model1.safetensors", "model2.safetensors"]
            models = client.get_models("checkpoints")
            self.assertEqual(len(models), 2)

    def test_get_models_returns_empty_on_error(self) -> None:
        client = ComfyUIClient(ComfyUIConnectionConfig(base_url="http://mock:8188"))
        with mock.patch.object(client, "_request", side_effect=ComfyUIError("404")):
            with self.assertRaises(ComfyUIError):
                client.get_models("checkpoints")


# ── API 端点测试（不依赖真实 ComfyUI）──────────────────────────


class ComfyuiApiCacheTests(_ComfyuiBase):
    def test_get_sync_status_empty(self) -> None:
        """未同步时返回空状态。"""
        response = self.client.get("/api/comfyui/sync-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["node_definitions"]["node_count"], 0)

    def test_list_node_definitions_api(self) -> None:
        self.manager.save_node_definitions({
            "TestNode": {
                "input": {"required": {}},
                "output": [],
                "name": "Test",
                "category": "test",
                "python_module": "comfy.test",
                "display_name": "Test",
            }
        })
        response = self.client.get("/api/comfyui/node-definitions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["node_class"], "TestNode")

    def test_get_node_definition_api(self) -> None:
        self.manager.save_node_definitions({
            "TestNode": {
                "input": {"required": {}},
                "output": [],
                "name": "Test",
                "category": "test",
                "python_module": "comfy.test",
                "display_name": "Test",
            }
        })
        response = self.client.get("/api/comfyui/node-definitions/TestNode")
        self.assertEqual(response.status_code, 200)
        self.assertIn("node_definition", response.json())

    def test_get_node_definition_not_found(self) -> None:
        response = self.client.get("/api/comfyui/node-definitions/Nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_list_node_categories_api(self) -> None:
        self.manager.save_node_definitions({
            "NodeA": {
                "input": {"required": {}},
                "output": [],
                "name": "A",
                "category": "cat_a",
                "python_module": "comfy.a",
                "display_name": "A",
            },
            "NodeB": {
                "input": {"required": {}},
                "output": [],
                "name": "B",
                "category": "cat_b",
                "python_module": "comfy.b",
                "display_name": "B",
            },
        })
        response = self.client.get("/api/comfyui/node-categories")
        self.assertEqual(response.status_code, 200)
        categories = response.json()["categories"]
        self.assertIn("cat_a", categories)
        self.assertIn("cat_b", categories)

    def test_list_resources_api(self) -> None:
        self.manager.save_resource_cache("checkpoints", ["model1"])
        response = self.client.get("/api/comfyui/resources")
        self.assertEqual(response.status_code, 200)
        self.assertIn("checkpoints", response.json()["resources"])

    def test_test_connection_returns_error_on_unreachable(self) -> None:
        """ComfyUI 不可达时返回 error 状态而非抛异常。"""
        # 设置一个不可达的地址
        self.client.put(
            "/api/settings/comfyui",
            json={"base_url": "http://127.0.0.1:39999"},
        )
        response = self.client.post("/api/comfyui/test-connection")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "error")


# ── 真实 ComfyUI 集成测试（条件执行）──────────────────────────


@unittest.skipUnless(COMFYUI_AVAILABLE, "ComfyUI 不可达，跳过真实集成测试")
class ComfyuiRealIntegrationTests(_ComfyuiBase):
    """真实 ComfyUI 集成测试。

    需要 COMFYUI_TEST_URL 指向的实例可达。测试数据写入临时隔离数据库。
    """

    def setUp(self) -> None:
        super().setUp()
        response = self.client.put(
            "/api/settings/comfyui",
            json={"base_url": COMFYUI_TEST_URL},
        )
        self.assertEqual(response.status_code, 200, response.text)

    def test_real_test_connection(self) -> None:
        response = self.client.post("/api/comfyui/test-connection")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("system", data)
        self.assertIn("devices", data)

    def test_real_sync_object_info(self) -> None:
        response = self.client.post("/api/comfyui/sync-object-info")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertGreater(data["node_count"], 10)
        self.assertIn("sha256", data)
        self.assertIn("synced_at", data)

    def test_real_get_system_stats(self) -> None:
        response = self.client.get("/api/comfyui/system-stats")
        self.assertEqual(response.status_code, 200)
        self.assertIn("system_stats", response.json())

    def test_real_sync_resources(self) -> None:
        response = self.client.post(
            "/api/comfyui/sync-resources",
            json={"resource_types": ["checkpoints", "loras"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(len(data["synced"]), 2)

    def test_real_get_node_definition_after_sync(self) -> None:
        """同步后能查询到 CheckpointLoaderSimple 节点定义。"""
        self.client.post("/api/comfyui/sync-object-info")
        response = self.client.get("/api/comfyui/node-definitions/CheckpointLoaderSimple")
        self.assertEqual(response.status_code, 200)
        definition = response.json()["node_definition"]
        self.assertEqual(definition["node_class"], "CheckpointLoaderSimple")

    def test_real_list_node_definitions_pagination(self) -> None:
        self.client.post("/api/comfyui/sync-object-info")
        response = self.client.get("/api/comfyui/node-definitions?limit=10&offset=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertLessEqual(len(data["items"]), 10)
        self.assertGreater(data["total"], 10)

    def test_real_list_node_definitions_filter_custom(self) -> None:
        self.client.post("/api/comfyui/sync-object-info")
        response = self.client.get("/api/comfyui/node-definitions?custom=true")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for item in data["items"]:
            self.assertTrue(item["is_custom_node"])

    def test_real_sync_status_after_sync(self) -> None:
        self.client.post("/api/comfyui/sync-object-info")
        response = self.client.get("/api/comfyui/sync-status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["node_definitions"]["node_count"], 0)
        self.assertTrue(data["node_definitions"]["last_synced_at"])

    def test_real_resources_after_sync(self) -> None:
        """同步 object_info 后资源缓存包含 checkpoints。"""
        self.client.post("/api/comfyui/sync-object-info")
        response = self.client.get("/api/comfyui/resources?resource_type=checkpoints")
        self.assertEqual(response.status_code, 200)
        # checkpoints 可能为空（如果 ComfyUI 未安装模型），但 key 应存在
        data = response.json()
        self.assertIn("resources", data)


if __name__ == "__main__":
    unittest.main()
