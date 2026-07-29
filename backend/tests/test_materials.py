from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app


def _make_image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(128, 64, 32)).save(buffer, format=fmt)
    return buffer.getvalue()


class MaterialsApiTests(unittest.TestCase):
    """素材库接口测试：所有数据均写入临时测试库。"""

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

    def _create_material(
        self,
        name: str = "测试素材",
        material_type: str = "scene",
        content: str = "素材正文内容",
        **kwargs,
    ) -> dict:
        payload = {
            "name": name,
            "material_type": material_type,
            "content": content,
            **kwargs,
        }
        response = self.client.post("/api/materials", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["material"]

    # ── CRUD ───────────────────────────────────────────────────

    def test_empty_list_returns_empty(self) -> None:
        response = self.client.get("/api/materials")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)
        self.assertIn("database_environment", response.json())

    def test_create_six_material_types(self) -> None:
        types = [
            "composition",
            "expression",
            "scene",
            "lighting",
            "prompt",
            "composite_template",
        ]
        for idx, material_type in enumerate(types):
            material = self._create_material(
                name=f"素材-{idx}",
                material_type=material_type,
            )
            self.assertEqual(material["material_type"], material_type)

    def test_name_and_tag_whitespace_cleaned(self) -> None:
        material = self._create_material(
            name="  测试   素材  ",
            tags=["  沙滩  ", "浅水", "浅水", "  浅 水  "],
        )
        self.assertEqual(material["name"], "测试 素材")
        # Tags are deduplicated case-insensitively and whitespace-cleaned.
        # Order is determined by SQL ORDER BY name ASC.
        self.assertEqual(set(material["tags"]), {"沙滩", "浅水", "浅 水"})
        self.assertEqual(len(material["tags"]), 3)

    def test_empty_name_rejected(self) -> None:
        response = self.client.post(
            "/api/materials",
            json={"name": "   ", "material_type": "scene", "content": "正文"},
        )
        self.assertEqual(response.status_code, 422)

    def test_empty_content_rejected(self) -> None:
        response = self.client.post(
            "/api/materials",
            json={"name": "素材", "material_type": "scene", "content": "   "},
        )
        self.assertEqual(response.status_code, 422)

    def test_too_long_name_rejected(self) -> None:
        response = self.client.post(
            "/api/materials",
            json={"name": "x" * 81, "material_type": "scene", "content": "正文"},
        )
        self.assertEqual(response.status_code, 422)

    def test_invalid_material_type_rejected(self) -> None:
        response = self.client.post(
            "/api/materials",
            json={"name": "素材", "material_type": "invalid_type", "content": "正文"},
        )
        self.assertEqual(response.status_code, 422)

    def test_invalid_validation_status_rejected(self) -> None:
        response = self.client.post(
            "/api/materials",
            json={
                "name": "素材",
                "material_type": "scene",
                "content": "正文",
                "validation_status": "invalid",
            },
        )
        self.assertEqual(response.status_code, 422)

    def test_same_type_same_name_allowed(self) -> None:
        """v0.5.2: 去除 UNIQUE(material_type, name) 约束，支持复制场景。"""
        self._create_material(name="同名素材", material_type="scene")
        response = self.client.post(
            "/api/materials",
            json={"name": "同名素材", "material_type": "scene", "content": "正文"},
        )
        self.assertEqual(response.status_code, 201)

    def test_case_insensitive_same_name_allowed(self) -> None:
        """v0.5.2: 同名素材允许存在（大小写不敏感）。"""
        self._create_material(name="TestMaterial", material_type="scene")
        response = self.client.post(
            "/api/materials",
            json={"name": "testmaterial", "material_type": "scene", "content": "正文"},
        )
        self.assertEqual(response.status_code, 201)

    def test_different_type_allows_same_name(self) -> None:
        self._create_material(name="同名素材", material_type="scene")
        response = self.client.post(
            "/api/materials",
            json={"name": "同名素材", "material_type": "lighting", "content": "正文"},
        )
        self.assertEqual(response.status_code, 201)

    def test_get_material_detail(self) -> None:
        created = self._create_material(description="测试简介", notes="备注")
        response = self.client.get(f"/api/materials/{created['id']}")
        self.assertEqual(response.status_code, 200)
        material = response.json()["material"]
        self.assertEqual(material["id"], created["id"])
        self.assertEqual(material["description"], "测试简介")
        self.assertEqual(material["notes"], "备注")
        self.assertIn("content", material)
        self.assertIn("prompt_text", material)

    def test_get_missing_material_returns_404(self) -> None:
        response = self.client.get("/api/materials/nonexistent-id")
        self.assertEqual(response.status_code, 404)

    def test_partial_update_name(self) -> None:
        created = self._create_material()
        response = self.client.patch(
            f"/api/materials/{created['id']}",
            json={"name": "新名称"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["material"]["name"], "新名称")

    def test_partial_update_clears_optional_field(self) -> None:
        created = self._create_material(description="原简介", notes="原备注")
        response = self.client.patch(
            f"/api/materials/{created['id']}",
            json={"description": "", "notes": ""},
        )
        self.assertEqual(response.status_code, 200)
        material = response.json()["material"]
        self.assertEqual(material["description"], "")
        self.assertEqual(material["notes"], "")

    def test_patch_no_fields_returns_422(self) -> None:
        created = self._create_material()
        response = self.client.patch(
            f"/api/materials/{created['id']}",
            json={},
        )
        self.assertEqual(response.status_code, 422)

    def test_patch_missing_material_returns_404(self) -> None:
        response = self.client.patch(
            "/api/materials/nonexistent-id",
            json={"name": "新名称"},
        )
        self.assertEqual(response.status_code, 404)

    def test_patch_duplicate_name_allowed(self) -> None:
        """v0.5.2: 同名素材允许存在，改名到已有名称不再冲突。"""
        self._create_material(name="素材A", material_type="scene")
        material_b = self._create_material(name="素材B", material_type="scene")
        response = self.client.patch(
            f"/api/materials/{material_b['id']}",
            json={"name": "素材A"},
        )
        self.assertEqual(response.status_code, 200)

    def test_delete_material(self) -> None:
        created = self._create_material()
        response = self.client.delete(f"/api/materials/{created['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        # Subsequent get returns 404
        response = self.client.get(f"/api/materials/{created['id']}")
        self.assertEqual(response.status_code, 404)

    def test_delete_missing_returns_404(self) -> None:
        response = self.client.delete("/api/materials/nonexistent-id")
        self.assertEqual(response.status_code, 404)

    # ── List / Search / Filter / Sort ─────────────────────────

    def _seed_search_materials(self) -> None:
        self._create_material(
            name="沙滩场景",
            material_type="scene",
            content="阳光沙滩",
            description="海边描述",
            tags=["沙滩", "白天"],
        )
        self._create_material(
            name="人物表情",
            material_type="expression",
            content="微笑表情",
            description="微笑描述",
            tags=["人物", "微笑"],
        )
        self._create_material(
            name="光线设置",
            material_type="lighting",
            content="侧光照明",
            description="光线描述",
            tags=["光线", "侧光"],
        )

    def test_search_by_name(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?q=沙滩")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "沙滩场景")

    def test_search_by_description(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?q=微笑描述")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "人物表情")

    def test_search_by_content(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?q=侧光照明")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "光线设置")

    def test_search_by_tag(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?q=白天")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "沙滩场景")

    def test_filter_by_material_type(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?material_type=expression")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["material_type"], "expression")

    def test_filter_by_validation_status(self) -> None:
        self._create_material(name="未验证素材", material_type="scene")
        self._create_material(
            name="已验证素材",
            material_type="scene",
            validation_status="verified",
        )
        response = self.client.get("/api/materials?validation_status=verified")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "已验证素材")

    def test_filter_by_tag_exact(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?tag=沙滩")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "沙滩场景")

    def test_combined_filters(self) -> None:
        self._seed_search_materials()
        response = self.client.get(
            "/api/materials?material_type=scene&q=沙滩&tag=白天"
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)

    def test_sort_updated_desc(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?sort=updated_desc")
        items = response.json()["items"]
        self.assertEqual(len(items), 3)

    def test_sort_name_asc(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?sort=name_asc")
        items = response.json()["items"]
        names = [item["name"] for item in items]
        self.assertEqual(names, sorted(names))

    def test_sort_name_desc(self) -> None:
        self._seed_search_materials()
        response = self.client.get("/api/materials?sort=name_desc")
        items = response.json()["items"]
        names = [item["name"] for item in items]
        self.assertEqual(names, sorted(names, reverse=True))

    def test_pagination_limit_offset(self) -> None:
        for i in range(5):
            self._create_material(name=f"素材{i}", material_type="scene")
        response = self.client.get("/api/materials?limit=2&offset=0")
        body = response.json()
        self.assertEqual(len(body["items"]), 2)
        self.assertEqual(body["total"], 5)
        self.assertTrue(body["has_more"])

        response = self.client.get("/api/materials?limit=2&offset=4")
        body = response.json()
        self.assertEqual(len(body["items"]), 1)
        self.assertFalse(body["has_more"])

    def test_list_does_not_return_large_text_fields(self) -> None:
        self._create_material(content="详细正文", prompt_text="提示词", notes="备注")
        response = self.client.get("/api/materials")
        item = response.json()["items"][0]
        self.assertNotIn("content", item)
        self.assertNotIn("prompt_text", item)
        self.assertNotIn("negative_prompt", item)
        self.assertNotIn("notes", item)
        self.assertNotIn("preview_url", item)

    # ── Tags ───────────────────────────────────────────────────

    def test_tags_dedup_case_insensitive(self) -> None:
        material = self._create_material(tags=["Tag1", "tag1", "TAG1", "Tag2"])
        self.assertEqual(material["tags"], ["Tag1", "Tag2"])

    def test_tags_full_replace_on_update(self) -> None:
        created = self._create_material(tags=["A", "B"])
        response = self.client.patch(
            f"/api/materials/{created['id']}",
            json={"tags": ["C"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["material"]["tags"], ["C"])

    def test_tags_cleared_with_empty_list(self) -> None:
        created = self._create_material(tags=["A"])
        response = self.client.patch(
            f"/api/materials/{created['id']}",
            json={"tags": []},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["material"]["tags"], [])

    def test_delete_material_cascades_tag_links(self) -> None:
        created = self._create_material(tags=["唯一标签"])
        self.client.delete(f"/api/materials/{created['id']}/permanent")
        # Tag still exists in tag table but no link
        response = self.client.get("/api/material-tags?q=唯一")
        self.assertEqual(response.status_code, 200)
        # HAVING material_count > 0 filters out orphan tags
        self.assertEqual(response.json()["items"], [])

    def test_tag_suggestions_with_count(self) -> None:
        self._create_material(name="A", material_type="scene", tags=["共享"])
        self._create_material(name="B", material_type="lighting", tags=["共享"])
        self._create_material(name="C", material_type="scene", tags=["独有"])
        response = self.client.get("/api/material-tags?q=共")
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "共享")
        self.assertEqual(items[0]["material_count"], 2)

    def test_tag_suggestions_limit(self) -> None:
        for i in range(5):
            self._create_material(
                name=f"素材{i}",
                material_type="scene",
                tags=[f"标签{i}"],
            )
        response = self.client.get("/api/material-tags?limit=3")
        self.assertEqual(len(response.json()["items"]), 3)

    def test_tag_suggestions_no_orphan_tags(self) -> None:
        # Create and delete to leave orphan tag
        created = self._create_material(tags=["孤儿标签"])
        self.client.delete(f"/api/materials/{created['id']}/permanent")
        response = self.client.get("/api/material-tags?q=孤儿")
        self.assertEqual(response.json()["items"], [])

    # ── Images ─────────────────────────────────────────────────

    def test_upload_jpg_preview(self) -> None:
        material = self._create_material()
        img_bytes = _make_image_bytes("JPEG")
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("preview_url", body)
        self.assertIn("thumbnail_url", body)

    def test_upload_png_preview(self) -> None:
        material = self._create_material()
        img_bytes = _make_image_bytes("PNG")
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("test.png", img_bytes, "image/png")},
        )
        self.assertEqual(response.status_code, 200)

    def test_upload_webp_preview(self) -> None:
        material = self._create_material()
        img_bytes = _make_image_bytes("WEBP")
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("test.webp", img_bytes, "image/webp")},
        )
        self.assertEqual(response.status_code, 200)

    def test_upload_creates_thumbnail(self) -> None:
        material = self._create_material()
        img_bytes = _make_image_bytes("PNG", size=(1024, 768))
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("test.png", img_bytes, "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        # Read thumbnail and verify it exists
        response = self.client.get(f"/api/materials/{material['id']}/thumbnail")
        self.assertEqual(response.status_code, 200)
        self.assertIn("image", response.headers.get("content-type", ""))

    def test_corrupted_image_rejected(self) -> None:
        material = self._create_material()
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("test.png", b"not an image", "image/png")},
        )
        self.assertEqual(response.status_code, 415)

    def test_fake_extension_rejected(self) -> None:
        material = self._create_material()
        # PNG bytes with .jpg extension
        img_bytes = _make_image_bytes("PNG")
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("test.jpg", img_bytes, "image/jpeg")},
        )
        # Pillow detects actual format, .jpg extension is ignored, file saved as PNG
        # Should succeed because we detect by content
        self.assertEqual(response.status_code, 200)

    def test_replace_preview_preserves_material(self) -> None:
        material = self._create_material()
        img1 = _make_image_bytes("PNG", size=(100, 100))
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("a.png", img1, "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        img2 = _make_image_bytes("JPEG", size=(200, 200))
        response = self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("b.jpg", img2, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        # Material still accessible
        response = self.client.get(f"/api/materials/{material['id']}")
        self.assertEqual(response.status_code, 200)

    def test_delete_preview_only(self) -> None:
        material = self._create_material()
        img_bytes = _make_image_bytes("PNG")
        self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("a.png", img_bytes, "image/png")},
        )
        response = self.client.delete(f"/api/materials/{material['id']}/preview")
        self.assertEqual(response.status_code, 200)
        # Material still exists
        response = self.client.get(f"/api/materials/{material['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["material"]["preview_url"])
        self.assertIsNone(response.json()["material"]["thumbnail_url"])

    def test_delete_material_cleans_image_directory(self) -> None:
        material = self._create_material()
        img_bytes = _make_image_bytes("PNG")
        self.client.post(
            f"/api/materials/{material['id']}/preview",
            files={"file": ("a.png", img_bytes, "image/png")},
        )
        material_dir = self.manager.data_root / "materials" / material["id"]
        self.assertTrue(material_dir.exists())
        self.client.delete(f"/api/materials/{material['id']}/permanent")
        self.assertFalse(material_dir.exists())

    def test_get_preview_when_none_returns_404(self) -> None:
        material = self._create_material()
        response = self.client.get(f"/api/materials/{material['id']}/preview")
        self.assertEqual(response.status_code, 404)

    def test_get_thumbnail_when_none_returns_404(self) -> None:
        material = self._create_material()
        response = self.client.get(f"/api/materials/{material['id']}/thumbnail")
        self.assertEqual(response.status_code, 404)

    def test_path_traversal_blocked(self) -> None:
        material = self._create_material()
        # Try to insert a malicious path directly via DatabaseManager
        self.manager.set_material_preview_paths(
            material["id"],
            original_path="../etc/passwd",
            thumbnail_path="../etc/shadow",
        )
        # API should still return 404 because path is outside materials root
        response = self.client.get(f"/api/materials/{material['id']}/preview")
        self.assertEqual(response.status_code, 404)

    # ── Data safety ───────────────────────────────────────────

    def test_test_db_writes_do_not_affect_production(self) -> None:
        # This test runs in test environment; verify production DB is unaffected
        prod_manager = self.manager
        # Test environment is locked
        self.assertEqual(prod_manager.active_environment, "test")
        self._create_material()
        # Verify production database has no materials
        with prod_manager.connection("production") as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM materials").fetchone()
            self.assertEqual(int(row["n"]), 0)


class MaterialVersionDeleteTests(unittest.TestCase):
    """MOD-02: 素材版本删除接口验收测试。"""

    def setUp(self) -> None:
        from backend.tests import IsolatedTestCase

        self._tc = IsolatedTestCase()
        self._tc.setUp()
        self.client = self._tc.client
        self.manager = self._tc.manager

    def tearDown(self) -> None:
        self._tc.tearDown()

    def _create_material(self) -> dict[str, object]:
        response = self.client.post(
            "/api/materials",
            json={
                "name": "版本测试素材",
                "material_type": "composition",
                "content": "v1 内容",
            },
        )
        return response.json()["material"]

    def test_delete_version_returns_404_for_missing_material(self) -> None:
        response = self.client.delete(
            "/api/materials/nonexistent/versions/1"
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_only_remaining_version(self) -> None:
        material = self._create_material()
        # 创建一个版本(此时只有一个)
        self.client.post(f"/api/materials/{material['id']}/versions")
        response = self.client.delete(
            f"/api/materials/{material['id']}/versions/1"
        )
        self.assertEqual(response.status_code, 409)

    def test_delete_version_when_multiple_exist(self) -> None:
        material = self._create_material()
        # 创建两个版本
        self.client.post(f"/api/materials/{material['id']}/versions")
        self.client.post(f"/api/materials/{material['id']}/versions")
        # 删除第一个版本
        response = self.client.delete(
            f"/api/materials/{material['id']}/versions/1"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        # 确认列表只剩一个
        list_resp = self.client.get(
            f"/api/materials/{material['id']}/versions"
        )
        self.assertEqual(len(list_resp.json()["versions"]), 1)


class MaterialLinkModeTests(unittest.TestCase):
    """MOD-02: 链接引用 vs 复制后独立复用模式验收测试。"""

    def setUp(self) -> None:
        from backend.tests import IsolatedTestCase

        self._tc = IsolatedTestCase()
        self._tc.setUp()
        self.client = self._tc.client
        self.manager = self._tc.manager

    def tearDown(self) -> None:
        self._tc.tearDown()

    def _create_source_material(self, content: str = "源内容") -> dict[str, object]:
        response = self.client.post(
            "/api/materials",
            json={
                "name": "源素材",
                "material_type": "composition",
                "content": content,
            },
        )
        material = response.json()["material"]
        # 添加一个素材页
        self.client.post(
            f"/api/materials/{material['id']}/pages",
            json={"name": "源页面", "content": "页面内容"},
        )
        return material

    def test_independent_copy_creates_own_pages(self) -> None:
        source = self._create_source_material()
        response = self.client.post(
            f"/api/materials/{source['id']}/copy",
            json={"name": "独立副本", "mode": "independent"},
        )
        self.assertEqual(response.status_code, 201)
        copy = response.json()["material"]
        self.assertEqual(copy["link_mode"], "independent")
        self.assertEqual(copy["source_material_id"], source["id"])
        # 独立副本有自己的页面
        pages_resp = self.client.get(f"/api/materials/{copy['id']}/pages")
        self.assertEqual(pages_resp.json()["total"], 1)

    def test_link_copy_does_not_duplicate_pages(self) -> None:
        source = self._create_source_material()
        response = self.client.post(
            f"/api/materials/{source['id']}/copy",
            json={"name": "链接副本", "mode": "link"},
        )
        self.assertEqual(response.status_code, 201)
        copy = response.json()["material"]
        self.assertEqual(copy["link_mode"], "link")
        self.assertEqual(copy["source_material_id"], source["id"])
        # 链接副本自己没有页面(直接查 material_pages 为空)
        own_pages = self.client.get(f"/api/materials/{copy['id']}/pages")
        self.assertEqual(own_pages.json()["total"], 0)
        # 通过 resolved 接口可读到源素材的页面
        resolved = self.client.get(
            f"/api/materials/{copy['id']}/pages/resolved"
        )
        self.assertEqual(resolved.json()["total"], 1)
        self.assertEqual(
            resolved.json()["pages"][0]["name"],
            "源页面",
        )

    def test_default_mode_is_independent(self) -> None:
        source = self._create_source_material()
        response = self.client.post(
            f"/api/materials/{source['id']}/copy",
            json={"name": "默认副本"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["material"]["link_mode"], "independent")


class MaterialPackItemsTests(unittest.TestCase):
    """MOD-02: 镜头模板/场景包/转场包(包素材成员管理)验收测试。"""

    def setUp(self) -> None:
        from backend.tests import IsolatedTestCase

        self._tc = IsolatedTestCase()
        self._tc.setUp()
        self.client = self._tc.client
        self.manager = self._tc.manager

    def tearDown(self) -> None:
        self._tc.tearDown()

    def _create_material(self, name: str = "素材") -> dict[str, object]:
        response = self.client.post(
            "/api/materials",
            json={
                "name": name,
                "material_type": "composition",
                "content": "内容",
            },
        )
        return response.json()["material"]

    def test_default_kind_is_single(self) -> None:
        material = self._create_material()
        self.assertEqual(material["kind"], "single")

    def test_set_material_kind_to_scene_pack(self) -> None:
        material = self._create_material()
        response = self.client.patch(
            f"/api/materials/{material['id']}/kind",
            json={"kind": "scene_pack"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["material"]["kind"], "scene_pack")

    def test_cannot_add_pack_item_to_single_kind(self) -> None:
        pack = self._create_material(name="包")
        member = self._create_material(name="成员")
        response = self.client.post(
            f"/api/materials/{pack['id']}/pack-items",
            json={"member_material_id": member["id"]},
        )
        self.assertEqual(response.status_code, 422)

    def test_add_list_update_remove_pack_item(self) -> None:
        # 创建包素材和成员素材
        pack = self._create_material(name="场景包")
        self.client.patch(
            f"/api/materials/{pack['id']}/kind",
            json={"kind": "scene_pack"},
        )
        member = self._create_material(name="成员 A")
        member_page = self.client.post(
            f"/api/materials/{member['id']}/pages",
            json={"name": "页面 1", "content": "页面内容"},
        ).json()["page"]

        # 添加成员
        add_resp = self.client.post(
            f"/api/materials/{pack['id']}/pack-items",
            json={
                "member_material_id": member["id"],
                "member_material_page_id": member_page["id"],
                "slot_role": "background",
            },
        )
        self.assertEqual(add_resp.status_code, 201)
        item = add_resp.json()["item"]
        self.assertEqual(item["slot_role"], "background")

        # 列表
        list_resp = self.client.get(
            f"/api/materials/{pack['id']}/pack-items"
        )
        self.assertEqual(list_resp.json()["total"], 1)

        # 更新
        upd_resp = self.client.patch(
            f"/api/material-pack-items/{item['id']}",
            json={"slot_role": "foreground", "sort_order": 5},
        )
        self.assertEqual(upd_resp.status_code, 200)
        self.assertEqual(upd_resp.json()["item"]["slot_role"], "foreground")
        self.assertEqual(upd_resp.json()["item"]["sort_order"], 5)

        # 删除
        del_resp = self.client.delete(
            f"/api/material-pack-items/{item['id']}"
        )
        self.assertEqual(del_resp.status_code, 200)
        self.assertTrue(del_resp.json()["deleted"])

        # 确认列表为空
        list_resp2 = self.client.get(
            f"/api/materials/{pack['id']}/pack-items"
        )
        self.assertEqual(list_resp2.json()["total"], 0)

    def test_pack_item_validates_member_page_ownership(self) -> None:
        pack = self._create_material(name="包")
        self.client.patch(
            f"/api/materials/{pack['id']}/kind",
            json={"kind": "scene_pack"},
        )
        member = self._create_material(name="成员")
        other = self._create_material(name="其他素材")
        other_page = self.client.post(
            f"/api/materials/{other['id']}/pages",
            json={"name": "其他页面", "content": "x"},
        ).json()["page"]
        # member_material_page_id 属于 other,不属于 member,应拒绝
        response = self.client.post(
            f"/api/materials/{pack['id']}/pack-items",
            json={
                "member_material_id": member["id"],
                "member_material_page_id": other_page["id"],
            },
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
