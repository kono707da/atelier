"""MOD-12 导入与外部扩展的验收测试。

覆盖：
- 素材包导入导出（含 dry_run 预检、冲突处理）
- 项目包导入导出（完整项目结构）
- 旧 AI 作图笔记扫描
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.tests import IsolatedTestCase


# ────────────────────────────────────────────────────────────────────
# 1. 素材包导入导出
# ────────────────────────────────────────────────────────────────────


class MaterialsPackageTests(IsolatedTestCase):
    """素材包导入导出测试。"""

    def _create_material(
        self,
        name: str = "导出素材",
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

    def test_export_single_material(self) -> None:
        """导出单个素材，验证 manifest 结构。"""
        material = self._create_material(
            name="光照素材A",
            material_type="lighting",
            content="正面光",
            tags=["自然光"],
        )
        response = self.client.post(
            "/api/materials/export-package",
            json={"material_ids": [material["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        manifest = response.json()["manifest"]
        self.assertEqual(manifest["format"], "atelier.materials.package")
        self.assertEqual(manifest["version"], "1.0")
        self.assertEqual(manifest["material_count"], 1)
        entry = manifest["materials"][0]
        self.assertEqual(entry["name"], "光照素材A")
        self.assertEqual(entry["material_type"], "lighting")
        self.assertEqual(entry["content"], "正面光")
        self.assertIn("content_hash", entry)
        self.assertEqual(entry["tags"], ["自然光"])

    def test_export_multiple_materials(self) -> None:
        """导出多个素材。"""
        m1 = self._create_material(name="素材一", material_type="scene")
        m2 = self._create_material(name="素材二", material_type="prompt")
        response = self.client.post(
            "/api/materials/export-package",
            json={"material_ids": [m1["id"], m2["id"]]},
        )
        self.assertEqual(response.status_code, 200)
        manifest = response.json()["manifest"]
        self.assertEqual(manifest["material_count"], 2)
        names = [m["name"] for m in manifest["materials"]]
        self.assertIn("素材一", names)
        self.assertIn("素材二", names)

    def test_export_nonexistent_returns_404(self) -> None:
        """导出不存在的素材返回 404。"""
        response = self.client.post(
            "/api/materials/export-package",
            json={"material_ids": ["nonexistent-id"]},
        )
        self.assertEqual(response.status_code, 404)

    def test_import_dry_run_preview(self) -> None:
        """dry_run 预检不创建素材，返回预检报告。"""
        manifest = {
            "format": "atelier.materials.package",
            "version": "1.0",
            "materials": [
                {
                    "name": "导入素材A",
                    "material_type": "scene",
                    "content": "导入的内容",
                    "tags": ["测试"],
                },
            ],
        }
        response = self.client.post(
            "/api/materials/import-package",
            json={"manifest": manifest, "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["dry_run"])
        self.assertEqual(body["created_count"], 1)
        self.assertEqual(body["conflicts"], [])
        # dry_run 不应创建素材
        list_resp = self.client.get("/api/materials")
        self.assertEqual(list_resp.json()["total"], 0)

    def test_import_creates_materials(self) -> None:
        """实际导入创建素材及其页面。"""
        manifest = {
            "format": "atelier.materials.package",
            "version": "1.0",
            "materials": [
                {
                    "name": "实际导入素材",
                    "material_type": "expression",
                    "content": "表情内容",
                    "description": "描述",
                    "prompt_text": "提示词",
                    "tags": ["开心", "微笑"],
                    "pages": [
                        {"name": "页面一", "content": "页面内容", "sort_order": 1},
                    ],
                },
            ],
        }
        response = self.client.post(
            "/api/materials/import-package",
            json={"manifest": manifest, "dry_run": False},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["dry_run"])
        self.assertEqual(body["created_count"], 1)
        created_id = body["materials"][0]["id"]
        # 验证素材已创建
        get_resp = self.client.get(f"/api/materials/{created_id}")
        self.assertEqual(get_resp.status_code, 200)
        material = get_resp.json()["material"]
        self.assertEqual(material["name"], "实际导入素材")
        self.assertEqual(set(material["tags"]), {"开心", "微笑"})
        # 验证页面已创建
        pages_resp = self.client.get(f"/api/materials/{created_id}/pages")
        self.assertEqual(pages_resp.status_code, 200)
        pages = pages_resp.json()["pages"]
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["name"], "页面一")

    def test_import_name_conflict_with_database(self) -> None:
        """导入与数据库中已有素材同名时报告冲突。"""
        self._create_material(name="冲突素材", material_type="scene", content="已有内容")
        manifest = {
            "format": "atelier.materials.package",
            "version": "1.0",
            "materials": [
                {
                    "name": "冲突素材",
                    "material_type": "scene",
                    "content": "新内容",
                },
            ],
        }
        # dry_run
        resp = self.client.post(
            "/api/materials/import-package",
            json={"manifest": manifest, "dry_run": True},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["created_count"], 0)
        self.assertEqual(len(body["conflicts"]), 1)
        self.assertEqual(body["conflicts"][0]["type"], "name")
        self.assertEqual(body["conflicts"][0]["source"], "database")

    def test_import_duplicate_names_in_manifest(self) -> None:
        """manifest 内同名素材报告冲突。"""
        manifest = {
            "format": "atelier.materials.package",
            "version": "1.0",
            "materials": [
                {"name": "重复素材", "material_type": "scene", "content": "内容1"},
                {"name": "重复素材", "material_type": "scene", "content": "内容2"},
            ],
        }
        resp = self.client.post(
            "/api/materials/import-package",
            json={"manifest": manifest, "dry_run": True},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["created_count"], 1)
        self.assertEqual(len(body["conflicts"]), 1)
        self.assertEqual(body["conflicts"][0]["source"], "manifest")

    def test_import_invalid_entries_skipped_with_warnings(self) -> None:
        """无效条目被跳过并产生警告。"""
        manifest = {
            "format": "atelier.materials.package",
            "version": "1.0",
            "materials": [
                {"name": "", "material_type": "scene", "content": "内容"},  # 空名称
                {"name": "有效素材", "material_type": "invalid_type", "content": "内容"},  # 无效类型
                {"name": "正常素材", "material_type": "scene", "content": "正常内容"},
            ],
        }
        resp = self.client.post(
            "/api/materials/import-package",
            json={"manifest": manifest, "dry_run": True},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["created_count"], 1)
        self.assertEqual(len(body["warnings"]), 2)


# ────────────────────────────────────────────────────────────────────
# 2. 项目包导入导出
# ────────────────────────────────────────────────────────────────────


class ProjectPackageTests(IsolatedTestCase):
    """项目包导入导出测试。"""

    def _create_project_chain(self) -> dict:
        """创建 项目→章节→大场景→小场景→分镜页 链路，返回各实体。"""
        project = self.client.post(
            "/api/projects", json={"name": "导出项目", "description": "测试项目"}
        ).json()["project"]
        chapter = self.client.post(
            f"/api/projects/{project['id']}/chapters", json={"name": "第一章"}
        ).json()["chapter"]
        large_scene = self.client.post(
            f"/api/chapters/{chapter['id']}/large-scenes", json={"name": "大场景A"}
        ).json()["large_scene"]
        small_scene = self.client.post(
            f"/api/large-scenes/{large_scene['id']}/small-scenes",
            json={"name": "小场景1"},
        ).json()["small_scene"]
        shot_page = self.client.post(
            f"/api/small-scenes/{small_scene['id']}/shot-pages",
            json={"title": "分镜1"},
        ).json()["shot_page"]
        return {
            "project": project,
            "chapter": chapter,
            "large_scene": large_scene,
            "small_scene": small_scene,
            "shot_page": shot_page,
        }

    def _create_material(self, name: str = "项目素材") -> dict:
        resp = self.client.post(
            "/api/materials",
            json={"name": name, "material_type": "scene", "content": "素材内容"},
        )
        self.assertEqual(resp.status_code, 201, resp.text)
        return resp.json()["material"]

    def test_export_project_with_structure(self) -> None:
        """导出包含完整结构的项目包。"""
        chain = self._create_project_chain()
        material = self._create_material()
        # 关联素材到小场景
        self.client.put(
            f"/api/small-scenes/{chain['small_scene']['id']}/materials",
            json={"material_ids": [material["id"]]},
        )

        response = self.client.post(
            f"/api/projects/{chain['project']['id']}/export-package"
        )
        self.assertEqual(response.status_code, 200)
        manifest = response.json()["manifest"]
        self.assertEqual(manifest["format"], "atelier.project.package")
        self.assertEqual(manifest["project"]["name"], "导出项目")
        self.assertEqual(len(manifest["chapters"]), 1)
        self.assertEqual(manifest["chapters"][0]["name"], "第一章")
        self.assertEqual(len(manifest["large_scenes"]), 1)
        self.assertEqual(len(manifest["small_scenes"]), 1)
        self.assertEqual(len(manifest["shot_pages"]), 1)
        self.assertEqual(len(manifest["materials"]), 1)
        self.assertEqual(manifest["materials"][0]["name"], "项目素材")
        self.assertEqual(len(manifest["small_scene_materials"]), 1)

    def test_export_nonexistent_project_returns_404(self) -> None:
        """导出不存在的项目返回 404。"""
        response = self.client.post(
            "/api/projects/nonexistent-id/export-package"
        )
        self.assertEqual(response.status_code, 404)

    def test_import_project_dry_run(self) -> None:
        """dry_run 返回实体计数，不创建项目。"""
        chain = self._create_project_chain()
        material = self._create_material()
        self.client.put(
            f"/api/small-scenes/{chain['small_scene']['id']}/materials",
            json={"material_ids": [material["id"]]},
        )
        export_resp = self.client.post(
            f"/api/projects/{chain['project']['id']}/export-package"
        )
        manifest = export_resp.json()["manifest"]

        # 修改项目名和素材名以避免冲突
        manifest["project"]["name"] = "导入项目"
        for m in manifest["materials"]:
            m["name"] = m["name"] + "（导入副本）"

        response = self.client.post(
            "/api/projects/import-package",
            json={"manifest": manifest, "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["dry_run"])
        counts = body["entity_counts"]
        self.assertEqual(counts["chapters"], 1)
        self.assertEqual(counts["large_scenes"], 1)
        self.assertEqual(counts["small_scenes"], 1)
        self.assertEqual(counts["shot_pages"], 1)
        self.assertEqual(counts["materials_new"], 1)
        # dry_run 不应创建项目
        projects = self.client.get("/api/projects").json()["items"]
        self.assertEqual(len(projects), 1)

    def test_import_project_creates_full_structure(self) -> None:
        """实际导入创建完整项目结构。"""
        chain = self._create_project_chain()
        material = self._create_material()
        self.client.put(
            f"/api/small-scenes/{chain['small_scene']['id']}/materials",
            json={"material_ids": [material["id"]]},
        )
        export_resp = self.client.post(
            f"/api/projects/{chain['project']['id']}/export-package"
        )
        manifest = export_resp.json()["manifest"]
        manifest["project"]["name"] = "导入的完整项目"
        # 修改素材名以避免与已有素材冲突
        for m in manifest["materials"]:
            m["name"] = m["name"] + "（导入副本）"

        response = self.client.post(
            "/api/projects/import-package",
            json={"manifest": manifest, "dry_run": False},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["dry_run"])
        self.assertEqual(body["project_name"], "导入的完整项目")
        self.assertGreater(body["created_count"], 1)
        self.assertEqual(body["materials_created"], 1)

        # 验证新项目存在
        new_project_id = body["project_id"]
        get_resp = self.client.get(f"/api/projects/{new_project_id}")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["project"]["name"], "导入的完整项目")

        # 验证章节存在
        chapters_resp = self.client.get(
            f"/api/projects/{new_project_id}/chapters"
        )
        self.assertEqual(chapters_resp.status_code, 200)
        self.assertEqual(len(chapters_resp.json()["items"]), 1)

    def test_import_project_material_conflict_reuses_existing(self) -> None:
        """项目导入时素材同名冲突，复用已有素材。"""
        chain = self._create_project_chain()
        material = self._create_material(name="共享素材")
        self.client.put(
            f"/api/small-scenes/{chain['small_scene']['id']}/materials",
            json={"material_ids": [material["id"]]},
        )
        export_resp = self.client.post(
            f"/api/projects/{chain['project']['id']}/export-package"
        )
        manifest = export_resp.json()["manifest"]
        manifest["project"]["name"] = "冲突测试项目"

        response = self.client.post(
            "/api/projects/import-package",
            json={"manifest": manifest, "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["entity_counts"]["materials_reused"], 1)
        self.assertEqual(body["entity_counts"]["materials_new"], 0)
        self.assertEqual(len(body["conflicts"]), 1)
        self.assertEqual(body["conflicts"][0]["resolution"], "reuse")


# ────────────────────────────────────────────────────────────────────
# 3. 旧笔记扫描
# ────────────────────────────────────────────────────────────────────


class LegacyScanTests(IsolatedTestCase):
    """旧 AI 作图笔记扫描测试。"""

    def setUp(self) -> None:
        super().setUp()
        self._scan_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._scan_dir.cleanup)
        self.scan_path = Path(self._scan_dir.name)

    def _write_file(self, relative: str, content: bytes) -> Path:
        path = self.scan_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_scan_finds_images_and_metadata(self) -> None:
        """扫描目录找到图片和元数据文件。"""
        self._write_file("img1.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        self._write_file("img2.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 50)
        self._write_file("meta.json", b'{"prompt": "test"}')
        self._write_file("notes.txt", b"prompt text here")

        response = self.client.post(
            "/api/import/scan-legacy",
            json={"directory": str(self.scan_path), "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        scan = response.json()["scan"]
        self.assertEqual(scan["image_count"], 2)
        self.assertEqual(scan["metadata_count"], 2)
        self.assertEqual(scan["total_count"], 4)
        # 每张图片应有 content_hash
        for img in scan["images"]:
            self.assertIn("content_hash", img)
            self.assertTrue(img["content_hash"])

    def test_scan_nonexistent_directory_returns_422(self) -> None:
        """扫描不存在的目录返回 422。"""
        response = self.client.post(
            "/api/import/scan-legacy",
            json={"directory": "/nonexistent/path/xyz", "dry_run": True},
        )
        self.assertEqual(response.status_code, 422)

    def test_scan_empty_directory(self) -> None:
        """空目录返回零计数。"""
        response = self.client.post(
            "/api/import/scan-legacy",
            json={"directory": str(self.scan_path), "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        scan = response.json()["scan"]
        self.assertEqual(scan["image_count"], 0)
        self.assertEqual(scan["metadata_count"], 0)
        self.assertEqual(scan["total_count"], 0)

    def test_scan_duplicate_images_detected(self) -> None:
        """重复图片被检测到。"""
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        self._write_file("a/dup.png", content)
        self._write_file("b/dup.png", content)  # 相同内容
        self._write_file("unique.png", b"\x89PNG\r\n\x1a\n" + b"\x01" * 100)

        response = self.client.post(
            "/api/import/scan-legacy",
            json={"directory": str(self.scan_path), "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        scan = response.json()["scan"]
        self.assertEqual(scan["image_count"], 3)
        self.assertEqual(scan["duplicate_image_count"], 1)

    def test_scan_recursive_finds_nested_files(self) -> None:
        """递归扫描找到子目录中的文件。"""
        self._write_file("level1/level2/deep.json", b'{"key": "val"}')
        self._write_file("level1/level2/deep.png", b"\x89PNG" + b"\x00" * 10)

        response = self.client.post(
            "/api/import/scan-legacy",
            json={"directory": str(self.scan_path), "dry_run": True},
        )
        self.assertEqual(response.status_code, 200)
        scan = response.json()["scan"]
        self.assertEqual(scan["image_count"], 1)
        self.assertEqual(scan["metadata_count"], 1)


if __name__ == "__main__":
    unittest.main()
