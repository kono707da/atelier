"""阶段 1.2 项目管理闭环的验收测试。

覆盖：
- 项目创建（含描述）
- 项目编辑（改名、改描述）
- 项目搜索、筛选和排序
- 项目归档与恢复
- 项目软删除、回收站和永久删除
- 项目复制
- 项目概览统计和阻塞项
- 同名项目允许存在
- 项目封面上传、删除和读取
"""
from __future__ import annotations

import io
import unittest

from PIL import Image

from backend.tests import IsolatedTestCase


def _make_image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(128, 64, 32)).save(buffer, format=fmt)
    return buffer.getvalue()


class ProjectCrudTests(IsolatedTestCase):
    """项目 CRUD 基础测试。"""

    def test_create_project_with_description(self) -> None:
        response = self.client.post(
            "/api/projects", json={"name": "测试项目", "description": "这是一个描述"}
        )
        self.assertEqual(response.status_code, 201)
        project = response.json()["project"]
        self.assertEqual(project["name"], "测试项目")
        self.assertEqual(project["description"], "这是一个描述")
        self.assertEqual(project["status"], "draft")
        self.assertIsNone(project["archived_at"])
        self.assertIsNone(project["deleted_at"])
        self.assertEqual(project["revision"], 1)

    def test_create_project_without_description(self) -> None:
        response = self.client.post("/api/projects", json={"name": "无描述项目"})
        self.assertEqual(response.status_code, 201)
        project = response.json()["project"]
        self.assertEqual(project["description"], "")

    def test_create_project_blank_name_rejected(self) -> None:
        response = self.client.post("/api/projects", json={"name": "  "})
        self.assertEqual(response.status_code, 422)

    def test_get_project_returns_full_fields(self) -> None:
        create = self.client.post(
            "/api/projects", json={"name": "完整项目", "description": "描述"}
        )
        project_id = create.json()["project"]["id"]
        response = self.client.get(f"/api/projects/{project_id}")
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        for field in ["id", "name", "description", "status", "cover_path",
                       "archived_at", "deleted_at", "revision", "created_at", "updated_at"]:
            self.assertIn(field, project)

    def test_get_nonexistent_project_returns_404(self) -> None:
        response = self.client.get("/api/projects/nonexistent-id")
        self.assertEqual(response.status_code, 404)

    def test_update_project_name(self) -> None:
        create = self.client.post("/api/projects", json={"name": "原名称"})
        project_id = create.json()["project"]["id"]
        response = self.client.patch(
            f"/api/projects/{project_id}", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertEqual(project["name"], "新名称")
        self.assertEqual(project["revision"], 2)

    def test_update_project_description(self) -> None:
        create = self.client.post("/api/projects", json={"name": "项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.patch(
            f"/api/projects/{project_id}", json={"description": "新描述"}
        )
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertEqual(project["description"], "新描述")

    def test_update_project_both_fields(self) -> None:
        create = self.client.post("/api/projects", json={"name": "原名称"})
        project_id = create.json()["project"]["id"]
        response = self.client.patch(
            f"/api/projects/{project_id}",
            json={"name": "新名称", "description": "新描述"},
        )
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertEqual(project["name"], "新名称")
        self.assertEqual(project["description"], "新描述")

    def test_update_project_no_fields_rejected(self) -> None:
        create = self.client.post("/api/projects", json={"name": "项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.patch(
            f"/api/projects/{project_id}", json={}
        )
        self.assertEqual(response.status_code, 422)

    def test_update_nonexistent_project_returns_404(self) -> None:
        response = self.client.patch(
            "/api/projects/nonexistent", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 404)


class ProjectSearchFilterSortTests(IsolatedTestCase):
    """项目搜索、筛选和排序。"""

    def setUp(self) -> None:
        super().setUp()
        self.p1 = self.client.post(
            "/api/projects", json={"name": "Alpha项目", "description": "第一个"}
        ).json()["project"]
        self.p2 = self.client.post(
            "/api/projects", json={"name": "Beta项目", "description": "第二个"}
        ).json()["project"]
        self.p3 = self.client.post(
            "/api/projects", json={"name": "Gamma素材", "description": "Alpha相关"}
        ).json()["project"]

    def test_list_all_projects(self) -> None:
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertEqual(len(body["items"]), 3)

    def test_search_by_name(self) -> None:
        response = self.client.get("/api/projects?q=Alpha")
        body = response.json()
        self.assertEqual(body["total"], 2)
        names = [p["name"] for p in body["items"]]
        self.assertIn("Alpha项目", names)
        self.assertIn("Gamma素材", names)

    def test_search_by_description(self) -> None:
        response = self.client.get("/api/projects?q=第一个")
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["name"], "Alpha项目")

    def test_sort_by_name(self) -> None:
        response = self.client.get("/api/projects?sort=name")
        body = response.json()
        names = [p["name"] for p in body["items"]]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_sort_by_created(self) -> None:
        response = self.client.get("/api/projects?sort=created")
        body = response.json()
        # 按创建时间降序，最后创建的在前
        self.assertEqual(body["items"][0]["id"], self.p3["id"])

    def test_pagination(self) -> None:
        response = self.client.get("/api/projects?limit=2&offset=0")
        body = response.json()
        self.assertEqual(len(body["items"]), 2)
        self.assertTrue(body["has_more"])
        self.assertEqual(body["total"], 3)

        response2 = self.client.get("/api/projects?limit=2&offset=2")
        body2 = response2.json()
        self.assertEqual(len(body2["items"]), 1)
        self.assertFalse(body2["has_more"])


class ProjectArchiveTests(IsolatedTestCase):
    """项目归档与恢复。"""

    def test_archive_project(self) -> None:
        create = self.client.post("/api/projects", json={"name": "待归档"})
        project_id = create.json()["project"]["id"]
        response = self.client.post(f"/api/projects/{project_id}/archive")
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertIsNotNone(project["archived_at"])
        self.assertEqual(project["status"], "archived")

    def test_restore_archived_project(self) -> None:
        create = self.client.post("/api/projects", json={"name": "已归档"})
        project_id = create.json()["project"]["id"]
        self.client.post(f"/api/projects/{project_id}/archive")
        response = self.client.post(f"/api/projects/{project_id}/restore")
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertIsNone(project["archived_at"])
        self.assertEqual(project["status"], "draft")

    def test_archived_projects_excluded_by_default(self) -> None:
        self.client.post("/api/projects", json={"name": "活跃项目"})
        create_archived = self.client.post("/api/projects", json={"name": "归档项目"})
        archive_id = create_archived.json()["project"]["id"]
        self.client.post(f"/api/projects/{archive_id}/archive")

        response = self.client.get("/api/projects")
        body = response.json()
        # 默认不返回已归档项目
        names = [p["name"] for p in body["items"]]
        self.assertNotIn("归档项目", names)
        self.assertIn("活跃项目", names)

    def test_archived_projects_included_with_flag(self) -> None:
        create = self.client.post("/api/projects", json={"name": "归档项目"})
        project_id = create.json()["project"]["id"]
        self.client.post(f"/api/projects/{project_id}/archive")

        response = self.client.get("/api/projects?archived=true")
        body = response.json()
        names = [p["name"] for p in body["items"]]
        self.assertIn("归档项目", names)

    def test_archive_nonexistent_returns_404(self) -> None:
        response = self.client.post("/api/projects/nonexistent/archive")
        self.assertEqual(response.status_code, 404)


class ProjectSoftDeleteTests(IsolatedTestCase):
    """项目软删除、回收站和永久删除。"""

    def test_soft_delete_project(self) -> None:
        create = self.client.post("/api/projects", json={"name": "待删除"})
        project_id = create.json()["project"]["id"]
        response = self.client.delete(f"/api/projects/{project_id}")
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertIsNotNone(project["deleted_at"])

    def test_deleted_projects_excluded_by_default(self) -> None:
        create = self.client.post("/api/projects", json={"name": "已删除"})
        project_id = create.json()["project"]["id"]
        self.client.delete(f"/api/projects/{project_id}")

        response = self.client.get("/api/projects")
        body = response.json()
        names = [p["name"] for p in body["items"]]
        self.assertNotIn("已删除", names)

    def test_trash_list_shows_deleted_projects(self) -> None:
        create = self.client.post("/api/projects", json={"name": "回收站项目"})
        project_id = create.json()["project"]["id"]
        self.client.delete(f"/api/projects/{project_id}")

        response = self.client.get("/api/projects?trash=true")
        body = response.json()
        names = [p["name"] for p in body["items"]]
        self.assertIn("回收站项目", names)

    def test_restore_deleted_project_via_restore_endpoint(self) -> None:
        create = self.client.post("/api/projects", json={"name": "可恢复"})
        project_id = create.json()["project"]["id"]
        self.client.delete(f"/api/projects/{project_id}")
        response = self.client.post(f"/api/projects/{project_id}/restore")
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertIsNone(project["deleted_at"])

    def test_permanent_delete_project(self) -> None:
        create = self.client.post("/api/projects", json={"name": "永久删除"})
        project_id = create.json()["project"]["id"]
        response = self.client.delete(f"/api/projects/{project_id}/permanent")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

        # 确认彻底删除
        get_response = self.client.get(f"/api/projects/{project_id}")
        self.assertEqual(get_response.status_code, 404)

    def test_permanent_delete_nonexistent_returns_404(self) -> None:
        response = self.client.delete("/api/projects/nonexistent/permanent")
        self.assertEqual(response.status_code, 404)


class ProjectCopyTests(IsolatedTestCase):
    """项目复制。"""

    def test_copy_project_basic(self) -> None:
        create = self.client.post(
            "/api/projects", json={"name": "原项目", "description": "原描述"}
        )
        original_id = create.json()["project"]["id"]
        response = self.client.post(
            f"/api/projects/{original_id}/copy", json={"name": "副本项目"}
        )
        self.assertEqual(response.status_code, 201)
        copy = response.json()["project"]
        self.assertNotEqual(copy["id"], original_id)
        self.assertEqual(copy["name"], "副本项目")
        self.assertEqual(copy["description"], "原描述")
        self.assertEqual(copy["status"], "draft")

    def test_copy_project_with_chapters(self) -> None:
        create = self.client.post("/api/projects", json={"name": "原项目"})
        original_id = create.json()["project"]["id"]
        self.client.post(
            f"/api/projects/{original_id}/chapters", json={"name": "第一章"}
        )

        response = self.client.post(
            f"/api/projects/{original_id}/copy", json={"name": "副本"}
        )
        copy_id = response.json()["project"]["id"]

        chapters = self.client.get(f"/api/projects/{copy_id}/chapters").json()
        self.assertEqual(chapters["total"], 1)
        self.assertEqual(chapters["items"][0]["name"], "第一章")

    def test_copy_nonexistent_returns_404(self) -> None:
        response = self.client.post(
            "/api/projects/nonexistent/copy", json={"name": "副本"}
        )
        self.assertEqual(response.status_code, 404)


class ProjectOverviewTests(IsolatedTestCase):
    """项目概览统计和阻塞项。"""

    def test_overview_empty_project(self) -> None:
        create = self.client.post("/api/projects", json={"name": "空项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.get(f"/api/projects/{project_id}/overview")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        stats = body["stats"]
        self.assertEqual(stats["chapter_count"], 0)
        self.assertEqual(stats["large_scene_count"], 0)
        self.assertEqual(stats["small_scene_count"], 0)
        self.assertEqual(stats["shot_page_count"], 0)
        self.assertEqual(stats["material_count"], 0)
        self.assertEqual(stats["character_count"], 0)

    def test_overview_blockers_for_empty_project(self) -> None:
        create = self.client.post("/api/projects", json={"name": "空项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.get(f"/api/projects/{project_id}/overview")
        blockers = response.json()["blockers"]
        codes = [b["code"] for b in blockers]
        self.assertIn("NO_CHAPTER", codes)
        self.assertIn("NO_SHOT_PAGE", codes)
        self.assertIn("NO_MATERIAL", codes)
        self.assertIn("NO_CHARACTER", codes)

    def test_overview_with_chapter_removes_blocker(self) -> None:
        create = self.client.post("/api/projects", json={"name": "项目"})
        project_id = create.json()["project"]["id"]
        self.client.post(
            f"/api/projects/{project_id}/chapters", json={"name": "第一章"}
        )
        response = self.client.get(f"/api/projects/{project_id}/overview")
        blockers = response.json()["blockers"]
        codes = [b["code"] for b in blockers]
        self.assertNotIn("NO_CHAPTER", codes)

    def test_overview_nonexistent_returns_404(self) -> None:
        response = self.client.get("/api/projects/nonexistent/overview")
        self.assertEqual(response.status_code, 404)


class DuplicateProjectNameTests(IsolatedTestCase):
    """同名项目允许存在（需求 7.1 验收项）。"""

    def test_duplicate_name_allowed(self) -> None:
        response1 = self.client.post("/api/projects", json={"name": "同名项目"})
        self.assertEqual(response1.status_code, 201)
        response2 = self.client.post("/api/projects", json={"name": "同名项目"})
        self.assertEqual(response2.status_code, 201)

        # 两个项目有不同 ID
        id1 = response1.json()["project"]["id"]
        id2 = response2.json()["project"]["id"]
        self.assertNotEqual(id1, id2)

    def test_duplicate_name_appears_in_list(self) -> None:
        self.client.post("/api/projects", json={"name": "同名"})
        self.client.post("/api/projects", json={"name": "同名"})
        response = self.client.get("/api/projects")
        body = response.json()
        names = [p["name"] for p in body["items"]]
        self.assertEqual(names.count("同名"), 2)


class ProjectCoverTests(IsolatedTestCase):
    """项目封面上传、删除和读取。"""

    def test_upload_png_cover_sets_cover_path(self) -> None:
        create = self.client.post("/api/projects", json={"name": "封面项目"})
        project_id = create.json()["project"]["id"]
        img_bytes = _make_image_bytes("PNG")
        response = self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.png", img_bytes, "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        project = response.json()["project"]
        self.assertIsNotNone(project["cover_path"])
        self.assertTrue(project["cover_path"].startswith(f"projects/{project_id}/"))
        self.assertEqual(response.json()["cover_url"], f"/api/projects/{project_id}/cover")
        self.assertEqual(project["revision"], 2)

    def test_upload_jpeg_cover(self) -> None:
        create = self.client.post("/api/projects", json={"name": "JPEG 项目"})
        project_id = create.json()["project"]["id"]
        img_bytes = _make_image_bytes("JPEG")
        response = self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["project"]["cover_path"].endswith(".jpg"))

    def test_upload_webp_cover(self) -> None:
        create = self.client.post("/api/projects", json={"name": "WEBP 项目"})
        project_id = create.json()["project"]["id"]
        img_bytes = _make_image_bytes("WEBP")
        response = self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.webp", img_bytes, "image/webp")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["project"]["cover_path"].endswith(".webp"))

    def test_get_cover_returns_image(self) -> None:
        create = self.client.post("/api/projects", json={"name": "读取封面项目"})
        project_id = create.json()["project"]["id"]
        img_bytes = _make_image_bytes("PNG")
        self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.png", img_bytes, "image/png")},
        )
        response = self.client.get(f"/api/projects/{project_id}/cover")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertIn("cache-control", response.headers)

    def test_get_cover_thumbnail_returns_webp(self) -> None:
        create = self.client.post("/api/projects", json={"name": "缩略图项目"})
        project_id = create.json()["project"]["id"]
        img_bytes = _make_image_bytes("PNG", size=(800, 600))
        self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.png", img_bytes, "image/png")},
        )
        response = self.client.get(f"/api/projects/{project_id}/cover/thumbnail")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")

    def test_get_cover_when_none_returns_404(self) -> None:
        create = self.client.post("/api/projects", json={"name": "无封面项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.get(f"/api/projects/{project_id}/cover")
        self.assertEqual(response.status_code, 404)

    def test_delete_cover_clears_cover_path(self) -> None:
        create = self.client.post("/api/projects", json={"name": "删除封面项目"})
        project_id = create.json()["project"]["id"]
        img_bytes = _make_image_bytes("PNG")
        self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.png", img_bytes, "image/png")},
        )
        response = self.client.delete(f"/api/projects/{project_id}/cover")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        # 校验数据库 cover_path 已清空
        project = self.client.get(f"/api/projects/{project_id}").json()["project"]
        self.assertIsNone(project["cover_path"])
        # 读取接口返回 404
        get_response = self.client.get(f"/api/projects/{project_id}/cover")
        self.assertEqual(get_response.status_code, 404)

    def test_upload_cover_replaces_previous(self) -> None:
        create = self.client.post("/api/projects", json={"name": "替换封面项目"})
        project_id = create.json()["project"]["id"]
        img1 = _make_image_bytes("PNG", size=(100, 100))
        first = self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("a.png", img1, "image/png")},
        )
        first_path = first.json()["project"]["cover_path"]
        img2 = _make_image_bytes("JPEG", size=(200, 200))
        second = self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("b.jpg", img2, "image/jpeg")},
        )
        second_path = second.json()["project"]["cover_path"]
        self.assertNotEqual(first_path, second_path)
        self.assertTrue(second_path.endswith(".jpg"))
        # revision 只增 2（两次上传各 +1）
        self.assertEqual(second.json()["project"]["revision"], 3)

    def test_upload_cover_nonexistent_project_returns_404(self) -> None:
        img_bytes = _make_image_bytes("PNG")
        response = self.client.post(
            "/api/projects/nonexistent/cover",
            files={"file": ("cover.png", img_bytes, "image/png")},
        )
        self.assertEqual(response.status_code, 404)

    def test_upload_cover_empty_file_returns_422(self) -> None:
        create = self.client.post("/api/projects", json={"name": "空文件项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("empty.png", b"", "image/png")},
        )
        self.assertEqual(response.status_code, 422)

    def test_upload_cover_invalid_format_returns_415(self) -> None:
        create = self.client.post("/api/projects", json={"name": "错误格式项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.gif", b"GIF89a not really", "image/gif")},
        )
        self.assertEqual(response.status_code, 415)

    def test_delete_cover_nonexistent_project_returns_404(self) -> None:
        response = self.client.delete("/api/projects/nonexistent/cover")
        self.assertEqual(response.status_code, 404)

    def test_permanent_delete_removes_cover_files(self) -> None:
        create = self.client.post("/api/projects", json={"name": "永久删除封面项目"})
        project_id = create.json()["project"]["id"]
        img_bytes = _make_image_bytes("PNG")
        self.client.post(
            f"/api/projects/{project_id}/cover",
            files={"file": ("cover.png", img_bytes, "image/png")},
        )
        # 软删除
        self.client.delete(f"/api/projects/{project_id}")
        # 永久删除
        response = self.client.delete(f"/api/projects/{project_id}/permanent")
        self.assertEqual(response.status_code, 200)
        # 封面文件目录已不存在
        cover_dir = self.manager.data_root / "projects" / project_id
        self.assertFalse(cover_dir.exists())


class ProjectDeletionImpactTests(IsolatedTestCase):
    """项目删除影响预览 API(MOD-01 补齐)的验收测试。"""

    def test_impact_returns_404_for_missing_project(self) -> None:
        response = self.client.get("/api/projects/does-not-exist/deletion-impact")
        self.assertEqual(response.status_code, 404)

    def test_impact_for_empty_project(self) -> None:
        create = self.client.post("/api/projects", json={"name": "空项目"})
        project_id = create.json()["project"]["id"]
        response = self.client.get(f"/api/projects/{project_id}/deletion-impact")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["database_environment"], "test")
        impact = body["impact"]
        self.assertEqual(impact["project"]["id"], project_id)
        self.assertEqual(impact["project"]["name"], "空项目")
        # 空项目所有计数为 0
        counts = impact["counts"]
        for field in (
            "chapters",
            "large_scenes",
            "small_scenes",
            "shot_pages",
            "linked_materials",
            "characters",
            "large_scene_branches",
            "small_scene_branches",
            "snapshots",
            "operations",
            "batches",
            "tasks",
            "image_instances",
            "files",
        ):
            self.assertEqual(counts[field], 0, f"{field} 应为 0")
        # 总计受影响为 0
        self.assertEqual(impact["totals"]["affected"], 0)
        # 空项目应给出"可安全删除"告警
        self.assertTrue(
            any("可安全删除" in w for w in impact["warnings"]),
            f"应包含可安全删除告警,实际: {impact['warnings']}",
        )

    def test_impact_includes_structure_counts(self) -> None:
        """包含章节/大场景/小场景/分镜页的项目,影响计数应反映这些结构。"""
        create = self.client.post("/api/projects", json={"name": "结构项目"})
        project_id = create.json()["project"]["id"]
        chapter = self.client.post(
            f"/api/projects/{project_id}/chapters", json={"name": "第一章"}
        ).json()["chapter"]
        large_scene = self.client.post(
            f"/api/chapters/{chapter['id']}/large-scenes", json={"name": "大场景 A"}
        ).json()["large_scene"]
        small_scene = self.client.post(
            f"/api/large-scenes/{large_scene['id']}/small-scenes",
            json={"name": "小场景 1"},
        ).json()["small_scene"]
        self.client.post(
            f"/api/small-scenes/{small_scene['id']}/shot-pages",
            json={"name": "分镜页 1"},
        )

        response = self.client.get(f"/api/projects/{project_id}/deletion-impact")
        self.assertEqual(response.status_code, 200)
        counts = response.json()["impact"]["counts"]
        self.assertEqual(counts["chapters"], 1)
        self.assertEqual(counts["large_scenes"], 1)
        self.assertEqual(counts["small_scenes"], 1)
        self.assertEqual(counts["shot_pages"], 1)
        self.assertEqual(response.json()["impact"]["totals"]["structural"], 4)

    def test_impact_includes_asset_links(self) -> None:
        """项目关联人物后,影响计数应反映关联的资产。"""
        create = self.client.post("/api/projects", json={"name": "资产项目"})
        project_id = create.json()["project"]["id"]
        character = self.client.post(
            "/api/characters", json={"name": "主角", "source": "original"}
        ).json()["character"]
        self.client.post(f"/api/projects/{project_id}/characters/{character['id']}")

        response = self.client.get(f"/api/projects/{project_id}/deletion-impact")
        counts = response.json()["impact"]["counts"]
        self.assertEqual(counts["characters"], 1)
        self.assertEqual(response.json()["impact"]["totals"]["assets"], 1)

    def test_impact_includes_history(self) -> None:
        """创建剧本快照后,影响计数应包含快照与操作历史。"""
        create = self.client.post("/api/projects", json={"name": "快照项目"})
        project_id = create.json()["project"]["id"]
        self.client.post(
            f"/api/projects/{project_id}/snapshots", json={"label": "v1"}
        )

        response = self.client.get(f"/api/projects/{project_id}/deletion-impact")
        counts = response.json()["impact"]["counts"]
        self.assertGreaterEqual(counts["snapshots"], 1)
        self.assertGreaterEqual(response.json()["impact"]["totals"]["history"], 1)

    def test_impact_warnings_for_soft_deleted_project(self) -> None:
        """已软删除项目再次查询影响时,应提示本次为永久删除。"""
        create = self.client.post("/api/projects", json={"name": "回收站项目"})
        project_id = create.json()["project"]["id"]
        self.client.delete(f"/api/projects/{project_id}")  # 软删除

        response = self.client.get(f"/api/projects/{project_id}/deletion-impact")
        self.assertEqual(response.status_code, 200)
        impact = response.json()["impact"]
        self.assertIsNotNone(impact["project"]["deleted_at"])
        self.assertTrue(
            any("永久删除" in w for w in impact["warnings"]),
            f"应包含永久删除告警,实际: {impact['warnings']}",
        )

    def test_impact_warnings_when_files_exist(self) -> None:
        """项目存在文件记录时,应给出文件清理告警。"""
        create = self.client.post("/api/projects", json={"name": "文件项目"})
        project_id = create.json()["project"]["id"]
        # 当前 files 是全局文件记录，项目归属由 image_instances 建立。
        from uuid import uuid4
        from backend.app.output_receiver import create_file_record, create_image_instance

        chapter = self.manager.create_chapter(project_id, "第一章")
        large_scene = self.manager.create_large_scene(chapter["id"], "大场景")
        small_scene = self.manager.create_small_scene(large_scene["id"], "小场景")
        shot_page = self.manager.create_shot_page(small_scene["id"], "分镜页")
        file_id = str(uuid4())
        create_file_record(
            self.manager,
            {
                "file_id": file_id,
                "storage_key": f"{file_id}.png",
                "original_name": "test.png",
                "content_hash": "abc",
                "size_bytes": 100,
                "mime_type": "image/png",
            },
        )
        create_image_instance(
            self.manager,
            project_id=project_id,
            shot_page_id=shot_page["id"],
            task_id=None,
            attempt_id=None,
            file_id=file_id,
            node_id=None,
            workflow_version_id=None,
            prompt_id=None,
            width=64,
            height=64,
            img_format="PNG",
            seed=1,
            resolved_json=None,
            snapshot_json=None,
        )

        response = self.client.get(f"/api/projects/{project_id}/deletion-impact")
        impact = response.json()["impact"]
        self.assertEqual(impact["counts"]["files"], 1)
        self.assertTrue(
            any("文件" in w for w in impact["warnings"]),
            f"应包含文件清理告警,实际: {impact['warnings']}",
        )


if __name__ == "__main__":
    unittest.main()
