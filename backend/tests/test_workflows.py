"""阶段 2.2 工作流数据与工作流库测试。

测试范围：
- 规范化结构解析（UI JSON / API JSON / 图片提取）
- 工作流 CRUD（创建/获取/列表/更新/删除）
- 归档/恢复
- 复制（全局模板复制/项目副本）
- 版本发布和查询
- 草稿读写
- 默认工作流（全局/项目）
- 语义插槽管理
- 工作流导入 API
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.workflow_models import (
    NormalizedWorkflow,
    WorkflowParseError,
    detect_format,
    extract_workflow_from_image,
    parse_api_json,
    parse_ui_json,
    parse_workflow_from_raw,
    serialize_workflow,
)


class _WorkflowBase(unittest.TestCase):
    """工作流库测试基类。"""

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

    def _create_workflow(self, name: str = "测试工作流", **kwargs) -> dict:
        payload = {"name": name, **kwargs}
        response = self.client.post("/api/workflows", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["workflow"]

    def _create_project(self, name: str = "测试项目") -> dict:
        response = self.client.post("/api/projects", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["project"]

    def _sample_ui_json(self) -> dict:
        return {
            "last_node_id": 3,
            "last_link_id": 2,
            "nodes": [
                {
                    "id": 1,
                    "type": "CheckpointLoaderSimple",
                    "title": "Load Checkpoint",
                    "pos": [100, 200],
                    "size": {"0": 300, "1": 100},
                    "mode": 0,
                    "inputs": [{"name": "ckpt_name", "type": "COMBO", "link": None}],
                    "outputs": [
                        {"name": "MODEL", "type": "MODEL", "links": [1]},
                        {"name": "CLIP", "type": "CLIP", "links": [2]},
                        {"name": "VAE", "type": "VAE", "links": None},
                    ],
                    "widgets_values": ["model.safetensors"],
                    "properties": {},
                    "order": 0,
                },
                {
                    "id": 2,
                    "type": "KSampler",
                    "title": "KSampler",
                    "pos": [500, 200],
                    "size": [300, 200],
                    "mode": 0,
                    "inputs": [
                        {"name": "model", "type": "MODEL", "link": 1},
                        {"name": "positive", "type": "CONDITIONING", "link": 2},
                    ],
                    "outputs": [{"name": "LATENT", "type": "LATENT", "links": []}],
                    "widgets_values": [12345, "fixed", 20, 8, "euler", "normal", 1],
                    "properties": {},
                    "order": 1,
                },
            ],
            "links": [
                [1, 1, 0, 2, 0, "MODEL"],
                [2, 1, 1, 2, 1, "CLIP"],
            ],
            "groups": [],
            "config": {},
            "extra": {},
            "version": 0.4,
        }

    def _sample_api_json(self) -> dict:
        return {
            "3": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "steps": 20,
                    "cfg": 8,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["4", 1],
                    "negative": ["4", 2],
                    "latent_image": ["5", 0],
                },
            },
            "4": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "5": {
                "class_type": "EmptyLatentImage",
                "inputs": {"width": 512, "height": 512, "batch_size": 1},
            },
        }


# ── 规范化结构解析 ────────────────────────────────────────────


class WorkflowParseTests(unittest.TestCase):
    def test_parse_ui_json_basic(self) -> None:
        ui_json = {
            "nodes": [
                {
                    "id": 1,
                    "type": "CheckpointLoaderSimple",
                    "title": "Load Checkpoint",
                    "pos": [100, 200],
                    "size": {"0": 300, "1": 100},
                    "mode": 0,
                    "inputs": [],
                    "outputs": [{"name": "MODEL", "type": "MODEL", "links": [1]}],
                    "widgets_values": ["model.safetensors"],
                    "properties": {},
                    "order": 0,
                }
            ],
            "links": [[1, 1, 0, 2, 0, "MODEL"]],
            "groups": [],
            "version": 0.4,
        }
        normalized = parse_ui_json(ui_json)
        self.assertEqual(len(normalized.nodes), 1)
        self.assertEqual(normalized.nodes[0]["type"], "CheckpointLoaderSimple")
        self.assertEqual(normalized.nodes[0]["position"], [100, 200])
        self.assertEqual(len(normalized.links), 1)
        self.assertEqual(normalized.links[0]["source_node"], "1")
        self.assertEqual(normalized.metadata["source_format"], "ui_json")

    def test_parse_ui_json_bypassed_mode(self) -> None:
        ui_json = {
            "nodes": [{"id": 1, "type": "Test", "mode": 4, "inputs": [], "outputs": []}],
            "links": [],
        }
        normalized = parse_ui_json(ui_json)
        self.assertTrue(normalized.nodes[0]["flags"]["bypassed"])
        self.assertFalse(normalized.nodes[0]["flags"]["enabled"])

    def test_parse_ui_json_missing_nodes_raises(self) -> None:
        with self.assertRaises(WorkflowParseError):
            parse_ui_json({})

    def test_parse_api_json_basic(self) -> None:
        api_json = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {"ckpt_name": "model.safetensors"},
            },
            "2": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": 12345,
                    "model": ["1", 0],
                },
            },
        }
        normalized = parse_api_json(api_json)
        self.assertEqual(len(normalized.nodes), 2)
        self.assertEqual(normalized.nodes[0]["type"], "CheckpointLoaderSimple")
        # 连线从 API JSON 的引用关系提取
        self.assertEqual(len(normalized.links), 1)
        self.assertEqual(normalized.links[0]["source_node"], "1")
        self.assertEqual(normalized.links[0]["target_node"], "2")

    def test_detect_format_ui_json(self) -> None:
        self.assertEqual(detect_format({"nodes": []}), "ui_json")

    def test_detect_format_api_json(self) -> None:
        self.assertEqual(detect_format({"1": {"class_type": "Test"}}), "api_json")

    def test_detect_format_unknown_raises(self) -> None:
        with self.assertRaises(WorkflowParseError):
            detect_format({"foo": "bar"})

    def test_parse_workflow_from_raw_auto_detect(self) -> None:
        normalized, fmt = parse_workflow_from_raw({"nodes": []}, "auto")
        self.assertEqual(fmt, "ui_json")

    def test_normalized_workflow_checksum_stable(self) -> None:
        nw1 = NormalizedWorkflow(nodes=[{"id": "1"}], links=[], groups=[], metadata={})
        nw2 = NormalizedWorkflow(nodes=[{"id": "1"}], links=[], groups=[], metadata={})
        self.assertEqual(nw1.checksum(), nw2.checksum())

    def test_serialize_and_store_workflow(self) -> None:
        normalized = NormalizedWorkflow(
            nodes=[{"id": "1", "type": "Test"}],
            links=[],
            groups=[],
            metadata={"source_format": "ui_json"},
        )
        serialized = serialize_workflow(normalized, raw_ui_json={"nodes": []})
        self.assertEqual(serialized["node_count"], 1)
        self.assertIn("checksum", serialized)
        self.assertIsNotNone(serialized["raw_ui_json"])


# ── 图片元数据提取 ────────────────────────────────────────────


class ImageMetadataExtractionTests(unittest.TestCase):
    def _make_png_with_workflow(self, workflow: dict, prompt: dict | None = None) -> bytes:
        from PIL.PngImagePlugin import PngInfo
        buffer = io.BytesIO()
        img = Image.new("RGB", (64, 64), color=(128, 128, 128))
        info = PngInfo()
        info.add_text("workflow", json.dumps(workflow))
        if prompt:
            info.add_text("prompt", json.dumps(prompt))
        img.save(buffer, format="PNG", pnginfo=info)
        return buffer.getvalue()

    def test_extract_ui_json_from_png(self) -> None:
        workflow = {"nodes": [{"id": 1, "type": "Test"}], "links": []}
        png_bytes = self._make_png_with_workflow(workflow)
        result = extract_workflow_from_image(png_bytes)
        self.assertIsNotNone(result["ui_json"])
        self.assertEqual(result["ui_json"]["nodes"][0]["type"], "Test")

    def test_extract_api_json_from_png(self) -> None:
        prompt = {"1": {"class_type": "Test", "inputs": {}}}
        png_bytes = self._make_png_with_workflow(workflow={"nodes": []}, prompt=prompt)
        result = extract_workflow_from_image(png_bytes)
        self.assertIsNotNone(result["api_json"])

    def test_extract_no_metadata_raises(self) -> None:
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64)).save(buffer, format="PNG")
        with self.assertRaises(WorkflowParseError):
            extract_workflow_from_image(buffer.getvalue())


# ── 工作流 CRUD ──────────────────────────────────────────────


class WorkflowCrudTests(_WorkflowBase):
    def test_create_workflow(self) -> None:
        wf = self._create_workflow("基础工作流", description="测试描述")
        self.assertEqual(wf["name"], "基础工作流")
        self.assertEqual(wf["description"], "测试描述")
        self.assertFalse(wf["is_archived"])
        self.assertFalse(wf["is_global_default"])
        self.assertEqual(wf["node_count"], 0)
        self.assertEqual(wf["revision"], 1)
        self.assertIsNone(wf["project_id"])

    def test_create_workflow_rejects_empty_name(self) -> None:
        response = self.client.post("/api/workflows", json={"name": ""})
        self.assertEqual(response.status_code, 422)

    def test_create_workflow_rejects_invalid_source_type(self) -> None:
        response = self.client.post(
            "/api/workflows",
            json={"name": "Test", "source_type": "invalid"},
        )
        self.assertEqual(response.status_code, 422)

    def test_get_workflow(self) -> None:
        wf = self._create_workflow()
        response = self.client.get(f"/api/workflows/{wf['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"]["id"], wf["id"])

    def test_get_workflow_not_found(self) -> None:
        response = self.client.get("/api/workflows/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_list_workflows(self) -> None:
        self._create_workflow("工作流A")
        self._create_workflow("工作流B")
        response = self.client.get("/api/workflows")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

    def test_list_workflows_search(self) -> None:
        self._create_workflow("Anime工作流")
        self._create_workflow("Realistic工作流")
        response = self.client.get("/api/workflows?search=Anime")
        self.assertEqual(response.json()["total"], 1)

    def test_list_workflows_exclude_archived(self) -> None:
        wf = self._create_workflow("活跃工作流")
        archived = self._create_workflow("归档工作流")
        self.client.post(f"/api/workflows/{archived['id']}/archive")
        response = self.client.get("/api/workflows")
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["id"], wf["id"])

    def test_list_workflows_include_archived(self) -> None:
        self._create_workflow("活跃工作流")
        archived = self._create_workflow("归档工作流")
        self.client.post(f"/api/workflows/{archived['id']}/archive")
        response = self.client.get("/api/workflows?archived=true")
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["id"], archived["id"])

    def test_update_workflow(self) -> None:
        wf = self._create_workflow("原名")
        response = self.client.patch(
            f"/api/workflows/{wf['id']}",
            json={"name": "新名", "description": "新描述"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"]["name"], "新名")
        self.assertEqual(response.json()["workflow"]["description"], "新描述")
        self.assertEqual(response.json()["workflow"]["revision"], 2)

    def test_delete_workflow(self) -> None:
        wf = self._create_workflow()
        response = self.client.delete(f"/api/workflows/{wf['id']}")
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f"/api/workflows/{wf['id']}")
        self.assertEqual(response.status_code, 404)

    def test_delete_workflow_not_found(self) -> None:
        response = self.client.delete("/api/workflows/nonexistent")
        self.assertEqual(response.status_code, 404)


# ── 归档/恢复 ────────────────────────────────────────────────


class WorkflowArchiveTests(_WorkflowBase):
    def test_archive_workflow(self) -> None:
        wf = self._create_workflow()
        response = self.client.post(f"/api/workflows/{wf['id']}/archive")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["workflow"]["is_archived"])

    def test_restore_workflow(self) -> None:
        wf = self._create_workflow()
        self.client.post(f"/api/workflows/{wf['id']}/archive")
        response = self.client.post(f"/api/workflows/{wf['id']}/restore")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["workflow"]["is_archived"])


# ── 复制 ─────────────────────────────────────────────────────


class WorkflowCopyTests(_WorkflowBase):
    def test_copy_workflow_global(self) -> None:
        wf = self._create_workflow("源工作流")
        response = self.client.post(
            f"/api/workflows/{wf['id']}/copy",
            json={"new_name": "复制工作流"},
        )
        self.assertEqual(response.status_code, 200)
        copy = response.json()["workflow"]
        self.assertEqual(copy["name"], "复制工作流")
        self.assertEqual(copy["source_workflow_id"], wf["id"])
        self.assertIsNone(copy["project_id"])

    def test_copy_workflow_to_project(self) -> None:
        wf = self._create_workflow("全局模板")
        project = self._create_project()
        response = self.client.post(
            f"/api/workflows/{wf['id']}/copy",
            json={"project_id": project["id"]},
        )
        self.assertEqual(response.status_code, 200)
        copy = response.json()["workflow"]
        self.assertEqual(copy["project_id"], project["id"])
        self.assertEqual(copy["source_workflow_id"], wf["id"])

    def test_copy_nonexistent_raises_404(self) -> None:
        response = self.client.post(
            "/api/workflows/nonexistent/copy",
            json={"new_name": "Copy"},
        )
        self.assertEqual(response.status_code, 404)


# ── 版本发布 ─────────────────────────────────────────────────


class WorkflowVersionTests(_WorkflowBase):
    def test_publish_version(self) -> None:
        wf = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{wf['id']}/versions",
            json={
                "label": "v1.0",
                "normalized_graph": '{"nodes":[],"links":[]}',
                "node_count": 5,
                "checksum": "abc123",
            },
        )
        self.assertEqual(response.status_code, 200)
        version = response.json()["version"]
        self.assertEqual(version["version_number"], 1)
        self.assertEqual(version["label"], "v1.0")

    def test_publish_multiple_versions(self) -> None:
        wf = self._create_workflow()
        for i in range(3):
            self.client.post(
                f"/api/workflows/{wf['id']}/versions",
                json={
                    "label": f"v{i+1}",
                    "normalized_graph": f'{{"v":{i+1}}}',
                    "node_count": i + 1,
                },
            )
        response = self.client.get(f"/api/workflows/{wf['id']}/versions")
        self.assertEqual(response.json()["total"], 3)
        # 最新版本号最大
        self.assertEqual(response.json()["items"][0]["version_number"], 3)

    def test_get_workflow_includes_current_version(self) -> None:
        wf = self._create_workflow()
        self.client.post(
            f"/api/workflows/{wf['id']}/versions",
            json={"normalized_graph": "{}", "node_count": 1},
        )
        response = self.client.get(f"/api/workflows/{wf['id']}")
        self.assertIn("current_version", response.json()["workflow"])

    def test_get_version_detail(self) -> None:
        wf = self._create_workflow()
        pub = self.client.post(
            f"/api/workflows/{wf['id']}/versions",
            json={"normalized_graph": '{"nodes":[]}', "node_count": 0},
        )
        version_id = pub.json()["version"]["id"]
        response = self.client.get(f"/api/workflow-versions/{version_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("normalized_graph", response.json()["version"])

    def test_get_version_not_found(self) -> None:
        response = self.client.get("/api/workflow-versions/nonexistent")
        self.assertEqual(response.status_code, 404)


# ── 草稿 ─────────────────────────────────────────────────────


class WorkflowDraftTests(_WorkflowBase):
    def test_save_and_get_draft(self) -> None:
        wf = self._create_workflow()
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={
                "normalized_graph": '{"nodes":[{"id":"1"}]}',
                "node_count": 1,
            },
        )
        response = self.client.get(f"/api/workflows/{wf['id']}/draft")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["draft"]["node_count"], 1)

    def test_save_draft_updates_workflow_node_count(self) -> None:
        wf = self._create_workflow()
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": "{}", "node_count": 10},
        )
        response = self.client.get(f"/api/workflows/{wf['id']}")
        self.assertEqual(response.json()["workflow"]["node_count"], 10)

    def test_get_draft_not_found(self) -> None:
        wf = self._create_workflow()
        response = self.client.get(f"/api/workflows/{wf['id']}/draft")
        self.assertEqual(response.status_code, 404)

    def test_save_draft_overwrites(self) -> None:
        wf = self._create_workflow()
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": '{"v":1}', "node_count": 1},
        )
        self.client.put(
            f"/api/workflows/{wf['id']}/draft",
            json={"normalized_graph": '{"v":2}', "node_count": 2},
        )
        response = self.client.get(f"/api/workflows/{wf['id']}/draft")
        self.assertEqual(response.json()["draft"]["node_count"], 2)


# ── 默认工作流 ───────────────────────────────────────────────


class DefaultWorkflowTests(_WorkflowBase):
    def test_set_global_default(self) -> None:
        wf = self._create_workflow("默认工作流")
        response = self.client.post(f"/api/workflows/{wf['id']}/set-global-default")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_global_default"])

    def test_set_global_default_replaces_previous(self) -> None:
        wf1 = self._create_workflow("工作流1")
        wf2 = self._create_workflow("工作流2")
        self.client.post(f"/api/workflows/{wf1['id']}/set-global-default")
        self.client.post(f"/api/workflows/{wf2['id']}/set-global-default")
        response = self.client.get(f"/api/workflows/{wf1['id']}")
        self.assertFalse(response.json()["workflow"]["is_global_default"])
        response = self.client.get(f"/api/workflows/{wf2['id']}")
        self.assertTrue(response.json()["workflow"]["is_global_default"])

    def test_set_project_default(self) -> None:
        project = self._create_project()
        wf = self._create_workflow()
        response = self.client.post(
            f"/api/projects/{project['id']}/default-workflow",
            json={"workflow_id": wf["id"]},
        )
        self.assertEqual(response.status_code, 200)

    def test_get_project_default(self) -> None:
        project = self._create_project()
        wf = self._create_workflow()
        self.client.post(
            f"/api/projects/{project['id']}/default-workflow",
            json={"workflow_id": wf["id"]},
        )
        response = self.client.get(f"/api/projects/{project['id']}/default-workflow")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["workflow"]["id"], wf["id"])

    def test_get_project_default_not_set(self) -> None:
        project = self._create_project()
        response = self.client.get(f"/api/projects/{project['id']}/default-workflow")
        self.assertEqual(response.status_code, 404)


# ── 语义插槽 ─────────────────────────────────────────────────


class SemanticSlotTests(_WorkflowBase):
    def test_set_and_list_semantic_slot(self) -> None:
        wf = self._create_workflow()
        self.client.put(
            f"/api/workflows/{wf['id']}/semantic-slots",
            json={
                "slot_name": "positive_prompt",
                "slot_type": "positive_prompt",
                "node_id": "6",
                "input_name": "text",
            },
        )
        response = self.client.get(f"/api/workflows/{wf['id']}/semantic-slots")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["slots"]), 1)
        self.assertEqual(response.json()["slots"][0]["slot_name"], "positive_prompt")

    def test_set_semantic_slot_upsert(self) -> None:
        wf = self._create_workflow()
        for node_id in ["6", "7"]:
            self.client.put(
                f"/api/workflows/{wf['id']}/semantic-slots",
                json={
                    "slot_name": "positive_prompt",
                    "slot_type": "positive_prompt",
                    "node_id": node_id,
                    "input_name": "text",
                },
            )
        response = self.client.get(f"/api/workflows/{wf['id']}/semantic-slots")
        self.assertEqual(len(response.json()["slots"]), 1)
        self.assertEqual(response.json()["slots"][0]["node_id"], "7")

    def test_delete_semantic_slot(self) -> None:
        wf = self._create_workflow()
        self.client.put(
            f"/api/workflows/{wf['id']}/semantic-slots",
            json={
                "slot_name": "seed",
                "slot_type": "seed",
                "node_id": "3",
                "input_name": "seed",
            },
        )
        response = self.client.delete(
            f"/api/workflows/{wf['id']}/semantic-slots/seed"
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f"/api/workflows/{wf['id']}/semantic-slots")
        self.assertEqual(len(response.json()["slots"]), 0)

    def test_delete_semantic_slot_not_found(self) -> None:
        wf = self._create_workflow()
        response = self.client.delete(
            f"/api/workflows/{wf['id']}/semantic-slots/nonexistent"
        )
        self.assertEqual(response.status_code, 404)


# ── 工作流导入 API ──────────────────────────────────────────


class WorkflowImportApiTests(_WorkflowBase):
    def test_import_ui_json(self) -> None:
        wf = self._create_workflow("导入工作流")
        response = self.client.post(
            f"/api/workflows/{wf['id']}/import",
            json={
                "source_format": "ui_json",
                "raw_json": self._sample_ui_json(),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["source_format"], "ui_json")
        self.assertEqual(data["node_count"], 2)

    def test_import_api_json(self) -> None:
        wf = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{wf['id']}/import",
            json={
                "source_format": "api_json",
                "raw_json": self._sample_api_json(),
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["source_format"], "api_json")
        self.assertEqual(response.json()["node_count"], 3)

    def test_import_auto_detect_ui_json(self) -> None:
        wf = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{wf['id']}/import",
            json={
                "source_format": "auto",
                "raw_json": self._sample_ui_json(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_format"], "ui_json")

    def test_import_auto_detect_api_json(self) -> None:
        wf = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{wf['id']}/import",
            json={
                "source_format": "auto",
                "raw_json": self._sample_api_json(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_format"], "api_json")

    def test_import_invalid_json_raises_422(self) -> None:
        wf = self._create_workflow()
        response = self.client.post(
            f"/api/workflows/{wf['id']}/import",
            json={"source_format": "auto", "raw_json": {"foo": "bar"}},
        )
        self.assertEqual(response.status_code, 422)

    def test_import_creates_draft(self) -> None:
        wf = self._create_workflow()
        self.client.post(
            f"/api/workflows/{wf['id']}/import",
            json={"source_format": "ui_json", "raw_json": self._sample_ui_json()},
        )
        response = self.client.get(f"/api/workflows/{wf['id']}/draft")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["draft"]["node_count"], 2)

    def test_import_from_image(self) -> None:
        # 创建带工作流元数据的 PNG
        from PIL.PngImagePlugin import PngInfo
        buffer = io.BytesIO()
        img = Image.new("RGB", (64, 64), color=(128, 128, 128))
        pnginfo = PngInfo()
        pnginfo.add_text("workflow", json.dumps(self._sample_ui_json()))
        pnginfo.add_text("prompt", json.dumps(self._sample_api_json()))
        img.save(buffer, format="PNG", pnginfo=pnginfo)

        response = self.client.post(
            "/api/workflows/import-from-image",
            files={"file": ("test.png", buffer.getvalue(), "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertIn("workflows", data)
        # 至少提取到一种格式
        self.assertTrue(len(data["workflows"]) > 0)


# ── 工作流与项目关联 ─────────────────────────────────────────


class WorkflowProjectTests(_WorkflowBase):
    def test_list_workflows_for_project(self) -> None:
        project = self._create_project()
        # 创建全局模板
        global_wf = self._create_workflow("全局模板")
        # 创建项目副本
        response = self.client.post(
            f"/api/workflows/{global_wf['id']}/copy",
            json={"project_id": project["id"], "new_name": "项目副本"},
        )
        self.assertEqual(response.status_code, 200)
        # 查询项目可见的工作流（项目副本 + 全局模板）
        response = self.client.get(f"/api/workflows?project_id={project['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

    def test_list_workflows_global_only(self) -> None:
        project = self._create_project()
        global_wf = self._create_workflow("全局模板")
        self.client.post(
            f"/api/workflows/{global_wf['id']}/copy",
            json={"project_id": project["id"]},
        )
        # 不带 project_id 时只列出全局模板
        response = self.client.get("/api/workflows")
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["items"][0]["id"], global_wf["id"])

    def test_create_workflow_with_project(self) -> None:
        project = self._create_project()
        wf = self._create_workflow("项目工作流", project_id=project["id"])
        self.assertEqual(wf["project_id"], project["id"])


if __name__ == "__main__":
    unittest.main()
