from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app, PROJECT_ROOT


RUNTIME_API_PATH = PROJECT_ROOT / "design" / "ui-preview" / "runtime-api.js"
STYLES_PATH = PROJECT_ROOT / "design" / "ui-preview" / "styles.css"


def _extract_frontend_paths(source: str) -> set[str]:
    """从 runtime-api.js 提取所有 /api/... 路径，归一化为 {param} 占位符。"""
    raw: set[str] = set()
    for match in re.finditer(r"/api/[^\s`'\"<>]+", source):
        path = match.group(0)
        # 去掉查询字符串
        path = path.split("?", 1)[0]
        # 去掉可能的尾随括号
        path = path.rstrip(")")
        # 将 ${...} 模板占位符统一替换为 {param}
        path = re.sub(r"\$\{[^}]+\}", "{param}", path)
        path = path.strip()
        if path:
            raw.add(path)
    return raw


def _shape(path: str) -> tuple[str, ...]:
    """将路径转为分段形状，{...} 视为参数占位 {}。"""
    segments: list[str] = []
    for seg in path.strip("/").split("/"):
        if seg.startswith("{") and seg.endswith("}"):
            segments.append("{}")
        else:
            segments.append(seg)
    return tuple(segments)


class FrontendRouteContractTests(unittest.TestCase):
    """验证 runtime-api.js 调用的所有 API 路由在 OpenAPI 中已注册。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.app = create_app(
            data_root=Path(self._tmp.name),
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.source = RUNTIME_API_PATH.read_text(encoding="utf-8")

    def openapi_shapes(self) -> set[tuple[str, ...]]:
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json().get("paths", {})
        return {_shape(p) for p in paths}

    def test_runtime_api_file_exists(self) -> None:
        self.assertTrue(RUNTIME_API_PATH.exists())
        self.assertIn("/api/", self.source)

    def test_all_frontend_routes_registered(self) -> None:
        frontend_paths = _extract_frontend_paths(self.source)
        self.assertTrue(frontend_paths, "未从 runtime-api.js 提取到任何 /api/ 路径")
        shapes = self.openapi_shapes()
        missing = [p for p in sorted(frontend_paths) if _shape(p) not in shapes]
        self.assertFalse(
            missing, f"前端调用了但后端未注册的路由: {missing}"
        )

    def test_story_tree_route_registered(self) -> None:
        shapes = self.openapi_shapes()
        self.assertIn(_shape("/api/projects/{param}/story-tree"), shapes)

    def test_workspace_route_registered(self) -> None:
        shapes = self.openapi_shapes()
        self.assertIn(_shape("/api/small-scenes/{param}/workspace"), shapes)

    def test_small_scene_pages_routes_registered(self) -> None:
        shapes = self.openapi_shapes()
        self.assertIn(_shape("/api/small-scenes/{param}/pages"), shapes)
        self.assertIn(_shape("/api/small-scene-pages/{param}"), shapes)
        self.assertIn(_shape("/api/small-scenes/{param}/pages/order"), shapes)

    def test_resources_routes_registered(self) -> None:
        shapes = self.openapi_shapes()
        self.assertIn(_shape("/api/small-scenes/{param}/resources"), shapes)

    def test_resource_links_route_registered(self) -> None:
        shapes = self.openapi_shapes()
        self.assertIn(_shape("/api/small-scene-resource-links/{param}"), shapes)

    def test_mappings_route_registered(self) -> None:
        shapes = self.openapi_shapes()
        self.assertIn(_shape("/api/small-scene-pages/{param}/mappings/{param}"), shapes)

    def test_material_pages_routes_registered(self) -> None:
        shapes = self.openapi_shapes()
        self.assertIn(_shape("/api/materials/{param}/pages"), shapes)
        self.assertIn(_shape("/api/material-pages/{param}"), shapes)
        self.assertIn(_shape("/api/materials/{param}/pages/order"), shapes)

    def test_overview_dashboard_has_scoped_layout_and_scroll_styles(self) -> None:
        styles = STYLES_PATH.read_text(encoding="utf-8")
        self.assertIn('page.classList.add("overview-dashboard-page")', self.source)
        self.assertIn(".page-scroll.overview-dashboard-page", styles)
        self.assertIn(".overview-summary-body", styles)
        self.assertIn(".overview-stats-grid", styles)
        self.assertIn(".overview-jump-grid", styles)

    def test_batch_page_uses_user_facing_run_batch_flow(self) -> None:
        styles = STYLES_PATH.read_text(encoding="utf-8")
        self.assertIn("创建第一个跑图批次", self.source)
        self.assertIn("检查跑图列表", self.source)
        self.assertIn("创建任务并前往开始", self.source)
        self.assertIn("当前范围没有可创建的任务", self.source)
        self.assertNotIn("建立第一个批量草稿", self.source)
        self.assertIn(".stage3-flow-steps", styles)
        self.assertIn(".stage3-advanced-grid", styles)

    def test_character_library_defaults_to_simple_editor(self) -> None:
        self.assertNotIn('id="character-tag-filter"', self.source)
        self.assertIn("管理人物形象、规格名称和提示词", self.source)
        self.assertIn("添加规格", self.source)
        self.assertIn("规格名称", self.source)
        self.assertIn("输入这个规格使用的提示词", self.source)
        self.assertNotIn("character-advanced-management", self.source)
        self.assertNotIn('name="lora_name"', self.source)
        self.assertNotIn('data-gap-action="spec-preview-upload"', self.source)
        self.assertNotIn('placeholder="例如：近景特写"', self.source)
        self.assertIn('draggable="true"', self.source)
        self.assertIn('data-menu-action="copy"', self.source)
        self.assertIn('data-menu-action="move-up"', self.source)
        self.assertNotIn('data-api-action="archive-character-variant"', self.source)
        self.assertNotIn("function characterVariantList(", self.source)


if __name__ == "__main__":
    unittest.main()
