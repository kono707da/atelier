from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app, PROJECT_ROOT


RUNTIME_API_PATH = PROJECT_ROOT / "design" / "ui-preview" / "runtime-api.js"


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


if __name__ == "__main__":
    unittest.main()
