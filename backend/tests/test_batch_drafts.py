"""阶段 3.2 跑图列表与批量配置测试。

测试范围：
- 草稿 CRUD（创建/读取/更新/删除）
- 草稿配置校验（scope/scope_id/seed_strategy/instance_count）
- 预览缓存（首次编译/缓存命中/配置变更后过期/强制重编译）
- 提交批次（不可变快照/状态初始为 pending）
- 批次 CRUD（列表/筛选/状态更新/软删除）
- 完整流程：创建草稿 → 预览 → 提交 → 查询批次
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.batch_drafts import (
    BatchConfig,
    VALID_BATCH_STATUSES,
)


# ──────────────────────────────────────────────────────────────────
# 工具函数测试
# ──────────────────────────────────────────────────────────────────


class BatchConfigTests(unittest.TestCase):
    def test_default_config(self) -> None:
        cfg = BatchConfig()
        self.assertEqual(cfg.instance_count, 1)
        self.assertEqual(cfg.seed_strategy, "fixed")
        self.assertIsNone(cfg.seed_base)
        self.assertIsNone(cfg.workflow_id)
        self.assertFalse(cfg.skip_adopted)
        self.assertFalse(cfg.only_failed)

    def test_from_dict(self) -> None:
        cfg = BatchConfig.from_dict({
            "instance_count": 4,
            "seed_strategy": "increment",
            "seed_base": 100,
            "workflow_id": "w1",
            "skip_adopted": True,
        })
        self.assertEqual(cfg.instance_count, 4)
        self.assertEqual(cfg.seed_strategy, "increment")
        self.assertEqual(cfg.seed_base, 100)
        self.assertEqual(cfg.workflow_id, "w1")
        self.assertTrue(cfg.skip_adopted)
        self.assertFalse(cfg.only_failed)

    def test_to_dict_roundtrip(self) -> None:
        cfg = BatchConfig(instance_count=3, seed_strategy="random", seed_base=42)
        d = cfg.to_dict()
        cfg2 = BatchConfig.from_dict(d)
        self.assertEqual(cfg, cfg2)

    def test_validate_invalid_seed_strategy(self) -> None:
        cfg = BatchConfig(seed_strategy="invalid")
        with self.assertRaises(ValueError):
            cfg.validate()

    def test_validate_invalid_instance_count(self) -> None:
        cfg = BatchConfig(instance_count=0)
        with self.assertRaises(ValueError):
            cfg.validate()

        cfg2 = BatchConfig(instance_count=101)
        with self.assertRaises(ValueError):
            cfg2.validate()

    def test_validate_negative_seed_base(self) -> None:
        cfg = BatchConfig(seed_base=-1)
        with self.assertRaises(ValueError):
            cfg.validate()


# ──────────────────────────────────────────────────────────────────
# API 集成测试基类
# ──────────────────────────────────────────────────────────────────


class _BatchApiBase(unittest.TestCase):
    """批量配置 API 集成测试基类。"""

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

    def _create_project(self, name: str = "测试项目") -> str:
        response = self.client.post("/api/projects", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["project"]["id"]

    def _setup_full_project(self) -> tuple[str, str, str, str]:
        """创建完整项目结构，返回 (project_id, shot_page_id, workflow_id, version_id)。"""
        project_id = self._create_project("批量配置测试项目")
        # 章节
        response = self.client.post(
            f"/api/projects/{project_id}/chapters",
            json={"name": "第一章"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        chapter_id = response.json()["chapter"]["id"]
        # 大场景
        response = self.client.post(
            f"/api/chapters/{chapter_id}/large-scenes",
            json={"name": "大场景1", "scene_type": "content"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        large_scene_id = response.json()["large_scene"]["id"]
        # 小场景
        response = self.client.post(
            f"/api/large-scenes/{large_scene_id}/small-scenes",
            json={"name": "小场景1"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        small_scene_id = response.json()["small_scene"]["id"]
        # 场景页
        response = self.client.post(
            f"/api/small-scenes/{small_scene_id}/shot-pages",
            json={"title": "场景页1"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        shot_page_id = response.json()["shot_page"]["id"]
        # 工作流
        response = self.client.post("/api/workflows", json={"name": "工作流1"})
        self.assertEqual(response.status_code, 201, response.text)
        workflow_id = response.json()["workflow"]["id"]
        # 保存草稿并发布
        nodes = [{
            "id": "1", "type": "CheckpointLoaderSimple", "title": "Load",
            "position": [0, 0], "size": [240, 100], "mode": 0,
            "flags": {"enabled": True, "bypassed": False, "disabled": False},
            "widgets_values": ["model.safetensors"], "properties": {},
            "inputs": [], "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
            "order": 0, "is_unknown": False,
        }]
        normalized = {"nodes": nodes, "links": [], "groups": [], "metadata": {}}
        response = self.client.put(
            f"/api/workflows/{workflow_id}/draft",
            json={
                "normalized_graph": json.dumps(normalized, ensure_ascii=False),
                "raw_ui_json": None, "raw_api_json": None, "node_count": 1,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post(
            f"/api/workflows/{workflow_id}/publish",
            json={"label": "v1", "normalized_graph": ""},
        )
        self.assertEqual(response.status_code, 200, response.text)
        version_id = response.json()["version"]["id"]
        # 设置项目默认工作流
        response = self.client.post(
            f"/api/projects/{project_id}/default-workflow",
            json={"workflow_id": workflow_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return project_id, shot_page_id, workflow_id, version_id

    def _create_draft(
        self,
        project_id: str,
        *,
        name: str = "测试草稿",
        scope: str = "project",
        scope_id: str | None = None,
        config: dict | None = None,
    ) -> str:
        body: dict = {"name": name, "scope": scope}
        if scope_id is not None:
            body["scope_id"] = scope_id
        if config is not None:
            body["config"] = config
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json=body,
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["draft"]["id"]


# ──────────────────────────────────────────────────────────────────
# 草稿 CRUD 测试
# ──────────────────────────────────────────────────────────────────


class DraftCrudTests(_BatchApiBase):
    def test_create_draft_default(self) -> None:
        """默认配置创建草稿。"""
        project_id = self._create_project()
        draft_id = self._create_draft(project_id)
        self.assertTrue(draft_id)

        response = self.client.get(f"/api/batch-drafts/{draft_id}")
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()["draft"]
        self.assertEqual(draft["project_id"], project_id)
        self.assertEqual(draft["scope"], "project")
        self.assertIsNone(draft["scope_id"])
        self.assertTrue(draft["preview_stale"])
        self.assertIsNone(draft["preview"])
        self.assertEqual(draft["config"]["instance_count"], 1)
        self.assertEqual(draft["config"]["seed_strategy"], "fixed")

    def test_create_draft_with_config(self) -> None:
        """带配置创建草稿。"""
        project_id = self._create_project()
        draft_id = self._create_draft(
            project_id,
            config={
                "instance_count": 4,
                "seed_strategy": "increment",
                "seed_base": 100,
            },
        )
        response = self.client.get(f"/api/batch-drafts/{draft_id}")
        draft = response.json()["draft"]
        self.assertEqual(draft["config"]["instance_count"], 4)
        self.assertEqual(draft["config"]["seed_strategy"], "increment")
        self.assertEqual(draft["config"]["seed_base"], 100)

    def test_create_draft_invalid_scope(self) -> None:
        """无效 scope 返回 422。"""
        project_id = self._create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json={"scope": "invalid_scope"},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_create_draft_chapter_without_scope_id(self) -> None:
        """chapter scope 缺少 scope_id 返回 422。"""
        project_id = self._create_project()
        response = self.client.post(
            f"/api/projects/{project_id}/batch-drafts",
            json={"scope": "chapter"},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_create_draft_nonexistent_project(self) -> None:
        """项目不存在返回 404。"""
        response = self.client.post(
            "/api/projects/nonexistent-id/batch-drafts",
            json={"scope": "project"},
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_list_drafts(self) -> None:
        """列出项目草稿。"""
        project_id = self._create_project()
        self._create_draft(project_id, name="草稿1")
        self._create_draft(project_id, name="草稿2")

        response = self.client.get(f"/api/projects/{project_id}/batch-drafts")
        self.assertEqual(response.status_code, 200, response.text)
        drafts = response.json()["drafts"]
        self.assertEqual(len(drafts), 2)

    def test_list_drafts_empty(self) -> None:
        """空项目草稿列表。"""
        project_id = self._create_project()
        response = self.client.get(f"/api/projects/{project_id}/batch-drafts")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["drafts"]), 0)

    def test_update_draft_name(self) -> None:
        """仅修改名称不标记预览过期。"""
        project_id = self._create_project()
        draft_id = self._create_draft(project_id, name="旧名称")
        # 先预览
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/preview",
            json={"force": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        # 修改名称
        response = self.client.patch(
            f"/api/batch-drafts/{draft_id}",
            json={"name": "新名称"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()["draft"]
        self.assertEqual(draft["name"], "新名称")
        # 预览应未过期
        self.assertFalse(draft["preview_stale"])

    def test_update_draft_config_marks_stale(self) -> None:
        """修改配置后预览标记为过期。"""
        project_id = self._create_project()
        draft_id = self._create_draft(project_id)
        # 先预览
        self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        # 修改配置
        response = self.client.patch(
            f"/api/batch-drafts/{draft_id}",
            json={"config": {"instance_count": 4}},
        )
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()["draft"]
        self.assertTrue(draft["preview_stale"])
        self.assertEqual(draft["config"]["instance_count"], 4)

    def test_update_draft_invalid_config(self) -> None:
        """无效配置返回 422。"""
        project_id = self._create_project()
        draft_id = self._create_draft(project_id)
        response = self.client.patch(
            f"/api/batch-drafts/{draft_id}",
            json={"config": {"instance_count": 0}},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_update_nonexistent_draft(self) -> None:
        """更新不存在的草稿返回 404。"""
        response = self.client.patch(
            "/api/batch-drafts/nonexistent-id",
            json={"name": "新名称"},
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_delete_draft(self) -> None:
        """软删除草稿。"""
        project_id = self._create_project()
        draft_id = self._create_draft(project_id)
        # 删除
        response = self.client.delete(f"/api/batch-drafts/{draft_id}")
        self.assertEqual(response.status_code, 200, response.text)
        # 再次获取应 404
        response = self.client.get(f"/api/batch-drafts/{draft_id}")
        self.assertEqual(response.status_code, 404, response.text)
        # 列表不含已删除
        response = self.client.get(f"/api/projects/{project_id}/batch-drafts")
        self.assertEqual(len(response.json()["drafts"]), 0)
        # include_deleted 可看到
        response = self.client.get(
            f"/api/projects/{project_id}/batch-drafts?include_deleted=true"
        )
        self.assertEqual(len(response.json()["drafts"]), 1)

    def test_delete_nonexistent_draft(self) -> None:
        """删除不存在的草稿返回 404。"""
        response = self.client.delete("/api/batch-drafts/nonexistent-id")
        self.assertEqual(response.status_code, 404, response.text)


# ──────────────────────────────────────────────────────────────────
# 预览测试
# ──────────────────────────────────────────────────────────────────


class DraftPreviewTests(_BatchApiBase):
    def test_preview_first_compile(self) -> None:
        """首次预览编译。"""
        project_id, _, _, _ = self._setup_full_project()
        draft_id = self._create_draft(project_id)
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/preview",
            json={"force": False},
        )
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()["preview"]
        self.assertEqual(preview["summary"]["total_pages"], 1)
        self.assertEqual(len(preview["items"]), 1)
        self.assertEqual(preview["draft_id"], draft_id)

        # 预览应已缓存且未过期
        response = self.client.get(f"/api/batch-drafts/{draft_id}")
        draft = response.json()["draft"]
        self.assertFalse(draft["preview_stale"])
        self.assertIsNotNone(draft["preview"])

    def test_preview_cache_hit(self) -> None:
        """缓存命中：未过期且非强制时直接返回缓存。"""
        project_id, _, _, _ = self._setup_full_project()
        draft_id = self._create_draft(project_id)
        # 首次预览
        r1 = self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        self.assertEqual(r1.status_code, 200)
        # 二次预览（应命中缓存）
        r2 = self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        self.assertEqual(r2.status_code, 200)
        # 两次返回的 items 应一致
        self.assertEqual(
            r1.json()["preview"]["items"][0]["item_id"],
            r2.json()["preview"]["items"][0]["item_id"],
        )

    def test_preview_force_recompile(self) -> None:
        """强制重编译。"""
        project_id, _, _, _ = self._setup_full_project()
        draft_id = self._create_draft(project_id)
        # 首次预览
        r1 = self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        # 强制重编译
        r2 = self.client.post(
            f"/api/batch-drafts/{draft_id}/preview",
            json={"force": True},
        )
        self.assertEqual(r2.status_code, 200)
        # 编译结果相同（同一项目同一配置）
        self.assertEqual(
            r1.json()["preview"]["items"][0]["input_hash"],
            r2.json()["preview"]["items"][0]["input_hash"],
        )

    def test_preview_after_config_change(self) -> None:
        """配置变更后预览应反映新配置。"""
        project_id, _, _, _ = self._setup_full_project()
        draft_id = self._create_draft(project_id)
        # 首次预览（instance_count=1）
        r1 = self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        h1 = r1.json()["preview"]["items"][0]["input_hash"]
        # 修改配置
        self.client.patch(
            f"/api/batch-drafts/{draft_id}",
            json={"config": {"instance_count": 4}},
        )
        # 再次预览
        r2 = self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        h2 = r2.json()["preview"]["items"][0]["input_hash"]
        # 不同实例数应产生不同 hash
        self.assertNotEqual(h1, h2)
        self.assertEqual(
            r2.json()["preview"]["summary"]["instance_count"], 4
        )

    def test_preview_nonexistent_draft(self) -> None:
        """预览不存在的草稿返回 404。"""
        response = self.client.post(
            "/api/batch-drafts/nonexistent-id/preview",
            json={},
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_preview_with_scope_chapter(self) -> None:
        """按章节范围预览。"""
        project_id, shot_page_id, _, _ = self._setup_full_project()
        # 获取 chapter_id
        response = self.client.get(f"/api/projects/{project_id}/chapters")
        chapter_id = response.json()["items"][0]["id"]

        draft_id = self._create_draft(
            project_id, scope="chapter", scope_id=chapter_id
        )
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/preview",
            json={},
        )
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()["preview"]
        self.assertEqual(preview["summary"]["total_pages"], 1)

    def test_preview_with_scope_shot_pages(self) -> None:
        """按指定页面范围预览。"""
        project_id, shot_page_id, _, _ = self._setup_full_project()
        draft_id = self._create_draft(
            project_id,
            scope="shot_pages",
            scope_id=shot_page_id,
        )
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/preview",
            json={},
        )
        self.assertEqual(response.status_code, 200, response.text)
        preview = response.json()["preview"]
        self.assertEqual(preview["summary"]["total_pages"], 1)
        self.assertEqual(preview["items"][0]["shot_page_id"], shot_page_id)


# ──────────────────────────────────────────────────────────────────
# 批次提交测试
# ──────────────────────────────────────────────────────────────────


class BatchCommitTests(_BatchApiBase):
    def test_commit_draft_to_batch(self) -> None:
        """提交草稿为不可变批次。"""
        project_id, _, _, _ = self._setup_full_project()
        draft_id = self._create_draft(project_id, name="提交测试")
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit",
            json={"name": "正式批次"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        batch = response.json()["batch"]
        self.assertEqual(batch["project_id"], project_id)
        self.assertEqual(batch["draft_id"], draft_id)
        self.assertEqual(batch["name"], "正式批次")
        self.assertEqual(batch["status"], "pending")
        self.assertEqual(batch["item_count"], 1)
        self.assertEqual(batch["blocking_count"], 0)
        self.assertIn("snapshot", batch)
        self.assertEqual(len(batch["snapshot"]["items"]), 1)

    def test_commit_without_name_uses_default(self) -> None:
        """未指定名称时使用草稿名称。"""
        project_id, _, _, _ = self._setup_full_project()
        draft_id = self._create_draft(project_id, name="草稿A")
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit",
            json={},
        )
        self.assertEqual(response.status_code, 200, response.text)
        batch = response.json()["batch"]
        self.assertEqual(batch["name"], "草稿A")

    def test_commit_nonexistent_draft(self) -> None:
        """提交不存在的草稿返回 404。"""
        response = self.client.post(
            "/api/batch-drafts/nonexistent-id/commit",
            json={},
        )
        self.assertEqual(response.status_code, 404, response.text)

    def test_commit_captures_blocking_errors(self) -> None:
        """提交时若有阻塞错误仍允许提交。"""
        project_id = self._create_project()
        # 不设置工作流，编译会有阻塞错误
        draft_id = self._create_draft(project_id)
        response = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit",
            json={"name": "阻塞批次"},
        )
        # 应该能提交（用户可查看后取消）
        self.assertEqual(response.status_code, 200, response.text)
        batch = response.json()["batch"]
        # 没有页面，total_pages=0
        self.assertEqual(batch["item_count"], 0)

    def test_commit_snapshot_is_immutable(self) -> None:
        """提交后修改草稿不影响批次快照。"""
        project_id, _, _, _ = self._setup_full_project()
        draft_id = self._create_draft(project_id)
        # 提交
        r1 = self.client.post(f"/api/batch-drafts/{draft_id}/commit", json={})
        batch_id = r1.json()["batch"]["id"]
        original_hash = r1.json()["batch"]["snapshot"]["items"][0]["input_hash"]
        # 修改草稿配置
        self.client.patch(
            f"/api/batch-drafts/{draft_id}",
            json={"config": {"instance_count": 4}},
        )
        # 再次查看批次：快照应未变
        r2 = self.client.get(f"/api/batches/{batch_id}")
        self.assertEqual(r2.status_code, 200)
        batch = r2.json()["batch"]
        self.assertEqual(batch["snapshot"]["items"][0]["input_hash"], original_hash)


# ──────────────────────────────────────────────────────────────────
# 批次 CRUD 测试
# ──────────────────────────────────────────────────────────────────


class BatchCrudTests(_BatchApiBase):
    def test_list_batches_empty(self) -> None:
        """空批次列表。"""
        response = self.client.get("/api/batches")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["batches"]), 0)

    def test_list_batches_by_project(self) -> None:
        """按项目列出批次。"""
        project_id1, _, _, _ = self._setup_full_project()
        project_id2, _, _, _ = self._setup_full_project()
        # 各创建一个批次
        draft1 = self._create_draft(project_id1)
        self.client.post(f"/api/batch-drafts/{draft1}/commit", json={})
        draft2 = self._create_draft(project_id2)
        self.client.post(f"/api/batch-drafts/{draft2}/commit", json={})
        # 查询项目1的批次
        response = self.client.get(f"/api/projects/{project_id1}/batches")
        self.assertEqual(response.status_code, 200, response.text)
        batches = response.json()["batches"]
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["project_id"], project_id1)

    def test_list_batches_all(self) -> None:
        """列出全部批次。"""
        project_id, _, _, _ = self._setup_full_project()
        draft = self._create_draft(project_id)
        self.client.post(f"/api/batch-drafts/{draft}/commit", json={})
        response = self.client.get("/api/batches")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["batches"]), 1)

    def test_get_batch_without_snapshot(self) -> None:
        """获取批次详情不带快照。"""
        project_id, _, _, _ = self._setup_full_project()
        draft = self._create_draft(project_id)
        r = self.client.post(f"/api/batch-drafts/{draft}/commit", json={})
        batch_id = r.json()["batch"]["id"]
        response = self.client.get(
            f"/api/batches/{batch_id}?include_snapshot=false"
        )
        self.assertEqual(response.status_code, 200, response.text)
        batch = response.json()["batch"]
        self.assertNotIn("snapshot", batch)
        self.assertIn("item_count", batch)

    def test_get_nonexistent_batch(self) -> None:
        """获取不存在的批次返回 404。"""
        response = self.client.get("/api/batches/nonexistent-id")
        self.assertEqual(response.status_code, 404, response.text)

    def test_update_batch_status(self) -> None:
        """更新批次状态。"""
        project_id, _, _, _ = self._setup_full_project()
        draft = self._create_draft(project_id)
        r = self.client.post(f"/api/batch-drafts/{draft}/commit", json={})
        batch_id = r.json()["batch"]["id"]
        # 更新为 running
        response = self.client.patch(
            f"/api/batches/{batch_id}/status",
            json={"status": "running"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["batch"]["status"], "running")
        # 更新为 completed
        response = self.client.patch(
            f"/api/batches/{batch_id}/status",
            json={"status": "completed"},
        )
        self.assertEqual(response.json()["batch"]["status"], "completed")

    def test_update_batch_invalid_status(self) -> None:
        """无效状态返回 422。"""
        project_id, _, _, _ = self._setup_full_project()
        draft = self._create_draft(project_id)
        r = self.client.post(f"/api/batch-drafts/{draft}/commit", json={})
        batch_id = r.json()["batch"]["id"]
        response = self.client.patch(
            f"/api/batches/{batch_id}/status",
            json={"status": "invalid_status"},
        )
        self.assertEqual(response.status_code, 422, response.text)

    def test_filter_batches_by_status(self) -> None:
        """按状态筛选批次。"""
        project_id, _, _, _ = self._setup_full_project()
        draft1 = self._create_draft(project_id, name="草稿1")
        r1 = self.client.post(f"/api/batch-drafts/{draft1}/commit", json={})
        draft2 = self._create_draft(project_id, name="草稿2")
        r2 = self.client.post(f"/api/batch-drafts/{draft2}/commit", json={})
        # 第一个改为 running
        self.client.patch(
            f"/api/batches/{r1.json()['batch']['id']}/status",
            json={"status": "running"},
        )
        # 查询 pending 的批次（应该只有第二个）
        response = self.client.get(
            f"/api/projects/{project_id}/batches?status=pending"
        )
        self.assertEqual(response.status_code, 200, response.text)
        batches = response.json()["batches"]
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["status"], "pending")

    def test_delete_batch(self) -> None:
        """软删除批次。"""
        project_id, _, _, _ = self._setup_full_project()
        draft = self._create_draft(project_id)
        r = self.client.post(f"/api/batch-drafts/{draft}/commit", json={})
        batch_id = r.json()["batch"]["id"]
        # 删除
        response = self.client.delete(f"/api/batches/{batch_id}")
        self.assertEqual(response.status_code, 200, response.text)
        # 再次获取应 404
        response = self.client.get(f"/api/batches/{batch_id}")
        self.assertEqual(response.status_code, 404, response.text)

    def test_delete_nonexistent_batch(self) -> None:
        """删除不存在的批次返回 404。"""
        response = self.client.delete("/api/batches/nonexistent-id")
        self.assertEqual(response.status_code, 404, response.text)


# ──────────────────────────────────────────────────────────────────
# 完整流程测试
# ──────────────────────────────────────────────────────────────────


class FullFlowTests(_BatchApiBase):
    def test_full_flow_create_preview_commit(self) -> None:
        """完整流程：创建 → 预览 → 修改 → 重新预览 → 提交。"""
        project_id, shot_page_id, workflow_id, version_id = self._setup_full_project()

        # 1. 创建草稿
        draft_id = self._create_draft(
            project_id,
            name="完整流程测试",
            config={"instance_count": 2, "seed_strategy": "fixed", "seed_base": 42},
        )

        # 2. 首次预览
        r = self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["preview"]["summary"]["instance_count"], 2)

        # 3. 修改配置
        r = self.client.patch(
            f"/api/batch-drafts/{draft_id}",
            json={"config": {"instance_count": 3, "seed_strategy": "increment", "seed_base": 100}},
        )
        self.assertEqual(r.status_code, 200)

        # 4. 重新预览
        r = self.client.post(f"/api/batch-drafts/{draft_id}/preview", json={})
        self.assertEqual(r.json()["preview"]["summary"]["instance_count"], 3)

        # 5. 提交批次
        r = self.client.post(
            f"/api/batch-drafts/{draft_id}/commit",
            json={"name": "正式批次"},
        )
        self.assertEqual(r.status_code, 200)
        batch = r.json()["batch"]
        self.assertEqual(batch["status"], "pending")
        self.assertEqual(batch["item_count"], 1)
        self.assertEqual(batch["name"], "正式批次")
        # 快照中的配置应是最新配置
        self.assertEqual(batch["snapshot"]["summary"]["instance_count"], 3)

        # 6. 推进状态
        batch_id = batch["id"]
        r = self.client.patch(
            f"/api/batches/{batch_id}/status",
            json={"status": "running"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["batch"]["status"], "running")

    def test_multiple_drafts_independent(self) -> None:
        """同一项目多个草稿互不影响。"""
        project_id, _, _, _ = self._setup_full_project()
        draft1 = self._create_draft(project_id, name="草稿1")
        draft2 = self._create_draft(project_id, name="草稿2")

        # 配置不同
        self.client.patch(
            f"/api/batch-drafts/{draft1}",
            json={"config": {"instance_count": 2}},
        )
        self.client.patch(
            f"/api/batch-drafts/{draft2}",
            json={"config": {"instance_count": 4}},
        )

        # 各自预览
        r1 = self.client.post(f"/api/batch-drafts/{draft1}/preview", json={})
        r2 = self.client.post(f"/api/batch-drafts/{draft2}/preview", json={})
        self.assertNotEqual(
            r1.json()["preview"]["items"][0]["input_hash"],
            r2.json()["preview"]["items"][0]["input_hash"],
        )

    def test_valid_batch_statuses_constant(self) -> None:
        """批次状态常量完整。"""
        expected = {"pending", "running", "paused", "completed", "cancelled", "failed"}
        self.assertEqual(set(VALID_BATCH_STATUSES), expected)


if __name__ == "__main__":
    unittest.main()
