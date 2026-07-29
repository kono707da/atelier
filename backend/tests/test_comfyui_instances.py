"""ComfyUI 多实例管理测试（需求 §4、§12.3）。

测试范围：
- 多实例保存和活动实例唯一约束
- 实例 CRUD（创建/读取/更新/删除）
- 切换活动实例不删除其他实例设置
- 同时发现两台实例时不自动切换
- 环境变量测试地址
- 旧单实例设置迁移为一条实例记录
- 节点定义摘要记录
- 探测范围受限，不自动覆盖活动实例

不依赖真实 ComfyUI 服务。
"""
from __future__ import annotations

import unittest
from unittest import mock

from backend.app.app_factory import create_app
from backend.app.comfyui_client import ComfyUIError, ComfyUISystemStats
from backend.tests import IsolatedTestCase


# ──────────────────────────────────────────────────────────────────
# 数据库层：多实例 CRUD 和活动实例唯一约束
# ──────────────────────────────────────────────────────────────────


class ComfyuiInstancesDatabaseTests(IsolatedTestCase):
    """数据库层：comfyui_instances 表 CRUD 和约束。"""

    def test_migrated_default_instance_exists_after_init(self) -> None:
        """初始化后存在迁移的默认实例，且为活动实例。"""
        instances = self.manager.list_comfyui_instances()
        self.assertEqual(len(instances), 1)
        default = instances[0]
        self.assertEqual(default["base_url"], "http://127.0.0.1:8188")
        self.assertTrue(default["is_active"])
        self.assertEqual(default["last_connection_status"], "unknown")

    def test_create_instance(self) -> None:
        """创建实例成功。"""
        instance = self.manager.create_comfyui_instance(
            name="局域网实例",
            base_url="http://192.168.3.5:8188",
            timeout_seconds=15.0,
        )
        self.assertTrue(instance["id"])
        self.assertEqual(instance["name"], "局域网实例")
        self.assertEqual(instance["base_url"], "http://192.168.3.5:8188")
        self.assertEqual(instance["timeout_seconds"], 15.0)
        self.assertFalse(instance["is_active"])

    def test_create_active_instance_deactivates_others(self) -> None:
        """创建新的活动实例时，其他实例自动设为非活动。"""
        # 初始有一个迁移的默认活动实例
        old_active = self.manager.get_active_comfyui_instance()
        self.assertIsNotNone(old_active)
        # 创建新的活动实例
        new_active = self.manager.create_comfyui_instance(
            name="新活动实例",
            base_url="http://192.168.3.5:8188",
            is_active=True,
        )
        self.assertTrue(new_active["is_active"])
        # 旧的活动实例应变为非活动
        old_instance = self.manager.get_comfyui_instance(old_active["id"])
        self.assertIsNotNone(old_instance)
        self.assertFalse(old_instance["is_active"])
        # 当前活动实例是新创建的
        current_active = self.manager.get_active_comfyui_instance()
        self.assertEqual(current_active["id"], new_active["id"])

    def test_activate_instance(self) -> None:
        """切换活动实例。"""
        inst1 = self.manager.create_comfyui_instance(
            name="实例1",
            base_url="http://192.168.1.1:8188",
        )
        # 切换活动实例为 inst1
        activated = self.manager.activate_comfyui_instance(inst1["id"])
        self.assertTrue(activated["is_active"])
        # 迁移的默认实例应变为非活动
        current_active = self.manager.get_active_comfyui_instance()
        self.assertEqual(current_active["id"], inst1["id"])

    def test_activate_nonexistent_returns_none(self) -> None:
        """激活不存在的实例返回 None。"""
        result = self.manager.activate_comfyui_instance("nonexistent-id")
        self.assertIsNone(result)

    def test_update_instance(self) -> None:
        """更新实例配置。"""
        instance = self.manager.create_comfyui_instance(
            name="原名",
            base_url="http://127.0.0.1:8188",
        )
        updated = self.manager.update_comfyui_instance(
            instance["id"],
            name="新名",
            base_url="http://192.168.3.5:8188",
            timeout_seconds=30.0,
        )
        self.assertEqual(updated["name"], "新名")
        self.assertEqual(updated["base_url"], "http://192.168.3.5:8188")
        self.assertEqual(updated["timeout_seconds"], 30.0)

    def test_update_nonexistent_returns_none(self) -> None:
        """更新不存在的实例返回 None。"""
        result = self.manager.update_comfyui_instance("nonexistent-id", name="新名")
        self.assertIsNone(result)

    def test_delete_instance(self) -> None:
        """删除实例成功。"""
        instance = self.manager.create_comfyui_instance(
            name="待删除",
            base_url="http://127.0.0.1:8188",
        )
        self.assertTrue(self.manager.delete_comfyui_instance(instance["id"]))
        self.assertIsNone(self.manager.get_comfyui_instance(instance["id"]))

    def test_delete_nonexistent_returns_false(self) -> None:
        """删除不存在的实例返回 False。"""
        self.assertFalse(self.manager.delete_comfyui_instance("nonexistent-id"))

    def test_switching_active_does_not_delete_other_settings(self) -> None:
        """切换活动实例不删除其他实例的设置（需求 §4.4）。"""
        inst1 = self.manager.create_comfyui_instance(
            name="实例1",
            base_url="http://192.168.1.1:8188",
            websocket_url="ws://192.168.1.1:8188/ws",
            is_active=True,
        )
        inst2 = self.manager.create_comfyui_instance(
            name="实例2",
            base_url="http://192.168.3.5:8188",
            is_active=True,  # 切换活动实例
        )
        # inst1 仍然存在，只是变为非活动
        inst1_after = self.manager.get_comfyui_instance(inst1["id"])
        self.assertIsNotNone(inst1_after)
        self.assertFalse(inst1_after["is_active"])
        self.assertEqual(inst1_after["websocket_url"], "ws://192.168.1.1:8188/ws")
        # inst2 是活动实例
        self.assertTrue(inst2["is_active"])

    def test_update_instance_status(self) -> None:
        """更新实例连接状态和检测结果。"""
        instance = self.manager.create_comfyui_instance(
            name="测试实例",
            base_url="http://127.0.0.1:8188",
        )
        updated = self.manager.update_comfyui_instance_status(
            instance["id"],
            connection_status="ok",
            comfyui_version="0.27.1",
            device_summary=[{"name": "cuda:0", "type": "gpu"}],
            node_definition_summary={"node_count": 2065, "custom_node_count": 1275},
        )
        self.assertEqual(updated["last_connection_status"], "ok")
        self.assertEqual(updated["comfyui_version"], "0.27.1")
        self.assertEqual(len(updated["device_summary"]), 1)
        self.assertEqual(updated["device_summary"][0]["name"], "cuda:0")
        self.assertEqual(updated["node_definition_summary"]["node_count"], 2065)
        self.assertTrue(updated["last_checked_at"])

    def test_multiple_instances_only_one_active(self) -> None:
        """多个实例同时只有一个活动（需求 §4.4）。"""
        # 创建 3 个实例，都标记为活动
        inst1 = self.manager.create_comfyui_instance(
            name="实例1", base_url="http://1.1.1.1:8188", is_active=True
        )
        inst2 = self.manager.create_comfyui_instance(
            name="实例2", base_url="http://2.2.2.2:8188", is_active=True
        )
        inst3 = self.manager.create_comfyui_instance(
            name="实例3", base_url="http://3.3.3.3:8188", is_active=True
        )
        # 只有最后创建的活动实例是活动的
        active = self.manager.get_active_comfyui_instance()
        self.assertEqual(active["id"], inst3["id"])
        # 其他实例都是非活动
        for inst in [inst1, inst2]:
            instance = self.manager.get_comfyui_instance(inst["id"])
            self.assertFalse(instance["is_active"])

    def test_migration_is_idempotent(self) -> None:
        """重新初始化不会重复迁移默认实例。"""
        self.manager.initialize("test")
        instances = self.manager.list_comfyui_instances()
        # 仍然只有迁移的默认实例（测试中未添加其他实例）
        default_count = [i for i in instances if i["id"] == "migrated-default"]
        self.assertEqual(len(default_count), 1)


# ──────────────────────────────────────────────────────────────────
# API 层：实例管理路由
# ──────────────────────────────────────────────────────────────────


class ComfyuiInstancesApiTests(IsolatedTestCase):
    """API 层：/api/comfyui/instances 路由。"""

    def test_list_instances_api(self) -> None:
        """GET /api/comfyui/instances 返回实例列表。"""
        response = self.client.get("/api/comfyui/instances")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("instances", data)
        self.assertGreaterEqual(data["total"], 1)  # 至少有迁移的默认实例

    def test_create_instance_api(self) -> None:
        """POST /api/comfyui/instances 创建实例。"""
        response = self.client.post(
            "/api/comfyui/instances",
            json={
                "name": "局域网实例",
                "base_url": "http://192.168.3.5:8188",
                "timeout_seconds": 15.0,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["instance"]["name"], "局域网实例")
        self.assertEqual(data["instance"]["base_url"], "http://192.168.3.5:8188")

    def test_create_instance_invalid_url_returns_422(self) -> None:
        """无效地址返回 422。"""
        response = self.client.post(
            "/api/comfyui/instances",
            json={"name": "测试", "base_url": "ftp://invalid"},
        )
        self.assertEqual(response.status_code, 422)

    def test_create_instance_empty_name_returns_422(self) -> None:
        """空名称返回 422。"""
        response = self.client.post(
            "/api/comfyui/instances",
            json={"name": "", "base_url": "http://127.0.0.1:8188"},
        )
        self.assertEqual(response.status_code, 422)

    def test_update_instance_api(self) -> None:
        """PATCH /api/comfyui/instances/{id} 更新实例。"""
        create_resp = self.client.post(
            "/api/comfyui/instances",
            json={"name": "原名", "base_url": "http://127.0.0.1:8188"},
        )
        instance_id = create_resp.json()["instance"]["id"]
        response = self.client.patch(
            f"/api/comfyui/instances/{instance_id}",
            json={"name": "新名", "base_url": "http://192.168.3.5:8188"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["instance"]["name"], "新名")
        self.assertEqual(data["instance"]["base_url"], "http://192.168.3.5:8188")

    def test_update_nonexistent_instance_returns_404(self) -> None:
        """更新不存在的实例返回 404。"""
        response = self.client.patch(
            "/api/comfyui/instances/nonexistent-id",
            json={"name": "新名"},
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_instance_api(self) -> None:
        """DELETE /api/comfyui/instances/{id} 删除实例。"""
        create_resp = self.client.post(
            "/api/comfyui/instances",
            json={"name": "待删除", "base_url": "http://127.0.0.1:8188"},
        )
        instance_id = create_resp.json()["instance"]["id"]
        response = self.client.delete(f"/api/comfyui/instances/{instance_id}")
        self.assertEqual(response.status_code, 200, response.text)
        # 确认已删除
        list_resp = self.client.get("/api/comfyui/instances")
        ids = [i["id"] for i in list_resp.json()["instances"]]
        self.assertNotIn(instance_id, ids)

    def test_delete_nonexistent_instance_returns_404(self) -> None:
        """删除不存在的实例返回 404。"""
        response = self.client.delete("/api/comfyui/instances/nonexistent-id")
        self.assertEqual(response.status_code, 404)

    def test_activate_instance_api(self) -> None:
        """POST /api/comfyui/instances/{id}/activate 切换活动实例。"""
        # 创建新实例
        create_resp = self.client.post(
            "/api/comfyui/instances",
            json={
                "name": "新活动实例",
                "base_url": "http://192.168.3.5:8188",
            },
        )
        instance_id = create_resp.json()["instance"]["id"]
        # 激活
        response = self.client.post(f"/api/comfyui/instances/{instance_id}/activate")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data["instance"]["is_active"])
        # 验证只有一个活动实例
        list_resp = self.client.get("/api/comfyui/instances")
        active_count = sum(1 for i in list_resp.json()["instances"] if i["is_active"])
        self.assertEqual(active_count, 1)

    def test_activate_nonexistent_returns_404(self) -> None:
        """激活不存在的实例返回 404。"""
        response = self.client.post("/api/comfyui/instances/nonexistent-id/activate")
        self.assertEqual(response.status_code, 404)

    def test_create_active_instance_via_api(self) -> None:
        """通过 API 创建活动实例，其他实例自动变为非活动。"""
        # 创建第一个活动实例
        resp1 = self.client.post(
            "/api/comfyui/instances",
            json={
                "name": "实例1",
                "base_url": "http://192.168.1.1:8188",
                "is_active": True,
            },
        )
        self.assertEqual(resp1.status_code, 200)
        # 创建第二个活动实例
        resp2 = self.client.post(
            "/api/comfyui/instances",
            json={
                "name": "实例2",
                "base_url": "http://192.168.3.5:8188",
                "is_active": True,
            },
        )
        self.assertEqual(resp2.status_code, 200)
        # 验证只有一个活动实例
        list_resp = self.client.get("/api/comfyui/instances")
        active_instances = [i for i in list_resp.json()["instances"] if i["is_active"]]
        self.assertEqual(len(active_instances), 1)
        self.assertEqual(active_instances[0]["name"], "实例2")


# ──────────────────────────────────────────────────────────────────
# 探测逻辑：不自动覆盖活动实例
# ──────────────────────────────────────────────────────────────────


class ComfyuiDiscoveryTests(IsolatedTestCase):
    """探测逻辑测试（需求 §4.5）。"""

    def test_discover_does_not_auto_activate(self) -> None:
        """探测结果不自动覆盖活动实例（需求 §4.5）。"""
        # 记录当前活动实例
        original_active = self.manager.get_active_comfyui_instance()
        self.assertIsNotNone(original_active)
        # 调用探测（所有地址都不可达，因为端口不存在）
        with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
            mock_test.side_effect = ComfyUIError("unreachable")
            response = self.client.post("/api/comfyui/discover")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("candidates", data)
        # 活动实例未改变
        current_active = self.manager.get_active_comfyui_instance()
        self.assertEqual(current_active["id"], original_active["id"])

    def test_discover_returns_candidates_list(self) -> None:
        """探测返回候选列表，包含探测过的地址。"""
        with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
            mock_test.side_effect = ComfyUIError("connection refused")
            response = self.client.post("/api/comfyui/discover")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreater(data["total"], 0)
        # 应包含默认地址
        urls = [c["base_url"] for c in data["candidates"]]
        self.assertIn("http://127.0.0.1:8188", urls)

    def test_discover_includes_env_var_url(self) -> None:
        """探测包含环境变量 ATELIER_COMFYUI_URL 指定的地址。"""
        with mock.patch.dict(
            "os.environ",
            {"ATELIER_COMFYUI_URL": "http://192.168.99.99:8188"},
        ):
            with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
                mock_test.side_effect = ComfyUIError("connection refused")
                response = self.client.post("/api/comfyui/discover")
        data = response.json()
        urls = [c["base_url"] for c in data["candidates"]]
        self.assertIn("http://192.168.99.99:8188", urls)

    def test_discover_includes_test_env_var_url(self) -> None:
        """探测包含环境变量 ATELIER_COMFYUI_TEST_URL 指定的地址。"""
        with mock.patch.dict(
            "os.environ",
            {"ATELIER_COMFYUI_TEST_URL": "http://192.168.88.88:8188"},
        ):
            with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
                mock_test.side_effect = ComfyUIError("connection refused")
                response = self.client.post("/api/comfyui/discover")
        data = response.json()
        urls = [c["base_url"] for c in data["candidates"]]
        self.assertIn("http://192.168.88.88:8188", urls)

    def test_discover_reachable_candidate_shows_version(self) -> None:
        """可达的候选显示 ComfyUI 版本。"""
        fake_stats = ComfyUISystemStats(
            status="ok",
            system_cpu="unknown",
            devices=[{"name": "cuda:0", "type": "gpu"}],
            raw={
                "system": {"comfyui_version": "0.27.1"},
                "devices": [{"name": "cuda:0", "type": "gpu"}],
            },
        )
        with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
            mock_test.return_value = fake_stats
            response = self.client.post("/api/comfyui/discover")
        data = response.json()
        reachable = [c for c in data["candidates"] if c["reachable"]]
        self.assertGreater(len(reachable), 0)
        self.assertEqual(reachable[0]["comfyui_version"], "0.27.1")

    def test_discover_two_reachable_does_not_auto_switch(self) -> None:
        """同时发现两台实例时不自动切换（需求 §12.3）。"""
        original_active = self.manager.get_active_comfyui_instance()
        self.assertIsNotNone(original_active)
        # 模拟所有候选都可达
        fake_stats = ComfyUISystemStats(
            status="ok",
            system_cpu="unknown",
            devices=[],
            raw={"system": {"comfyui_version": "0.27.1"}, "devices": []},
        )
        with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
            mock_test.return_value = fake_stats
            response = self.client.post("/api/comfyui/discover")
        self.assertEqual(response.status_code, 200)
        # 活动实例未改变
        current_active = self.manager.get_active_comfyui_instance()
        self.assertEqual(current_active["id"], original_active["id"])


# ──────────────────────────────────────────────────────────────────
# 旧单实例设置迁移
# ──────────────────────────────────────────────────────────────────


class ComfyuiMigrationTests(IsolatedTestCase):
    """旧单实例设置迁移测试（需求 §11.1）。"""

    def test_old_settings_migrated_to_instance(self) -> None:
        """旧 app_settings 中的 comfyui.* 迁移为一条实例记录。"""
        instances = self.manager.list_comfyui_instances()
        # 应该有一条迁移的默认实例
        migrated = [i for i in instances if i["id"] == "migrated-default"]
        self.assertEqual(len(migrated), 1)
        self.assertTrue(migrated[0]["is_active"])
        self.assertEqual(migrated[0]["base_url"], "http://127.0.0.1:8188")

    def test_old_custom_settings_migrated(self) -> None:
        """旧自定义地址迁移后保留原值，不自动更改。"""
        # 先写入旧设置
        self.manager.set_comfyui_settings(
            base_url="http://192.168.3.5:8188",
            timeout_seconds=30.0,
            websocket_url="ws://192.168.3.5:8188/ws",
        )
        # 删除迁移的默认实例，重新初始化触发迁移
        with self.manager.connection("test") as conn:
            conn.execute("DELETE FROM comfyui_instances")
        self.manager.initialize("test")
        instances = self.manager.list_comfyui_instances()
        self.assertEqual(len(instances), 1)
        migrated = instances[0]
        self.assertEqual(migrated["base_url"], "http://192.168.3.5:8188")
        self.assertEqual(migrated["timeout_seconds"], 30.0)
        self.assertEqual(migrated["websocket_url"], "ws://192.168.3.5:8188/ws")
        self.assertTrue(migrated["is_active"])

    def test_migration_preserves_invalid_address(self) -> None:
        """无法判断旧地址是否有效时仍保留，不自动改成另一个地址。"""
        # 写入一个看起来无效的地址
        self.manager.set_comfyui_settings(base_url="http://10.0.0.99:9999")
        with self.manager.connection("test") as conn:
            conn.execute("DELETE FROM comfyui_instances")
        self.manager.initialize("test")
        instances = self.manager.list_comfyui_instances()
        self.assertEqual(len(instances), 1)
        # 地址保留原值
        self.assertEqual(instances[0]["base_url"], "http://10.0.0.99:9999")


# ──────────────────────────────────────────────────────────────────
# 测试连接和同步（mock ComfyUI）
# ──────────────────────────────────────────────────────────────────


class ComfyuiInstanceTestSyncTests(IsolatedTestCase):
    """实例测试连接和同步（mock ComfyUI，不依赖真实服务）。"""

    def test_test_instance_updates_status(self) -> None:
        """POST /api/comfyui/instances/{id}/test 更新实例状态。"""
        create_resp = self.client.post(
            "/api/comfyui/instances",
            json={"name": "测试实例", "base_url": "http://127.0.0.1:8188"},
        )
        instance_id = create_resp.json()["instance"]["id"]
        fake_stats = ComfyUISystemStats(
            status="ok",
            system_cpu="unknown",
            devices=[{"name": "cuda:0", "type": "gpu"}],
            raw={
                "system": {"comfyui_version": "0.27.1"},
                "devices": [{"name": "cuda:0", "type": "gpu"}],
            },
        )
        with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
            mock_test.return_value = fake_stats
            response = self.client.post(f"/api/comfyui/instances/{instance_id}/test")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["instance"]["last_connection_status"], "ok")
        self.assertEqual(data["instance"]["comfyui_version"], "0.27.1")

    def test_test_instance_unreachable_updates_status(self) -> None:
        """不可达实例更新状态为 unreachable。"""
        create_resp = self.client.post(
            "/api/comfyui/instances",
            json={"name": "不可达实例", "base_url": "http://127.0.0.1:39999"},
        )
        instance_id = create_resp.json()["instance"]["id"]
        with mock.patch("backend.app.comfyui_client.ComfyUIClient.test_connection") as mock_test:
            mock_test.side_effect = ComfyUIError("connection refused")
            response = self.client.post(f"/api/comfyui/instances/{instance_id}/test")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["status"], "error")
        # 验证状态已更新
        list_resp = self.client.get("/api/comfyui/instances")
        instance = next(i for i in list_resp.json()["instances"] if i["id"] == instance_id)
        self.assertEqual(instance["last_connection_status"], "unreachable")

    def test_test_nonexistent_instance_returns_404(self) -> None:
        """测试不存在的实例返回 404。"""
        response = self.client.post("/api/comfyui/instances/nonexistent-id/test")
        self.assertEqual(response.status_code, 404)

    def test_sync_instance_updates_node_summary(self) -> None:
        """POST /api/comfyui/instances/{id}/sync 更新节点定义摘要。"""
        create_resp = self.client.post(
            "/api/comfyui/instances",
            json={"name": "同步实例", "base_url": "http://127.0.0.1:8188"},
        )
        instance_id = create_resp.json()["instance"]["id"]
        fake_object_info = {
            "CheckpointLoaderSimple": {
                "input": {"required": {}},
                "output": ["MODEL"],
                "name": "CheckpointLoaderSimple",
                "category": "loaders",
                "python_module": "comfy_extras.nodes",
                "display_name": "Load Checkpoint",
            },
            "KSampler": {
                "input": {"required": {}},
                "output": ["LATENT"],
                "name": "KSampler",
                "category": "sampling",
                "python_module": "custom_nodes.custom_sampler",
                "display_name": "KSampler",
            },
        }
        with mock.patch("backend.app.comfyui_client.ComfyUIClient.get_object_info") as mock_get:
            mock_get.return_value = fake_object_info
            response = self.client.post(f"/api/comfyui/instances/{instance_id}/sync")
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["node_count"], 2)
        self.assertEqual(data["custom_node_count"], 1)
        # 验证实例的节点定义摘要已更新
        list_resp = self.client.get("/api/comfyui/instances")
        instance = next(i for i in list_resp.json()["instances"] if i["id"] == instance_id)
        self.assertEqual(instance["node_definition_summary"]["node_count"], 2)
        self.assertEqual(instance["last_connection_status"], "ok")

    def test_sync_nonexistent_instance_returns_404(self) -> None:
        """同步不存在的实例返回 404。"""
        response = self.client.post("/api/comfyui/instances/nonexistent-id/sync")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
