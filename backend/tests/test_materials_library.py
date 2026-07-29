"""阶段 1.3 素材库闭环的验收测试。

覆盖 v0.5.2 新增功能：
- 素材归档与恢复
- 素材软删除与回收站（含永久删除）
- 素材引用反查（小场景、场景页映射）
- 素材页预览图（上传、读取、缩略图、删除）
- 素材页复制
- 素材版本历史（快照、恢复、自动版本）
- 素材复制
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


class _MaterialsLibraryBase(IsolatedTestCase):
    """素材库测试公共辅助方法。"""

    def _create_material(
        self,
        name: str = "测试素材",
        material_type: str = "scene",
        content: str = "测试正文",
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

    def _create_project_chain(self) -> dict:
        """创建 项目→章节→大场景→小场景 链路，返回各实体 id。"""
        project = self.client.post(
            "/api/projects", json={"name": "项目"}
        ).json()["project"]
        chapter = self.client.post(
            f"/api/projects/{project['id']}/chapters", json={"name": "章"}
        ).json()["chapter"]
        large_scene = self.client.post(
            f"/api/chapters/{chapter['id']}/large-scenes", json={"name": "大场景"}
        ).json()["large_scene"]
        small_scene = self.client.post(
            f"/api/large-scenes/{large_scene['id']}/small-scenes",
            json={"name": "小场景"},
        ).json()["small_scene"]
        return {
            "project": project,
            "chapter": chapter,
            "large_scene": large_scene,
            "small_scene": small_scene,
        }

    def _create_scene_page(self, small_scene_id: str, name: str = "场景页") -> dict:
        response = self.client.post(
            f"/api/small-scenes/{small_scene_id}/pages", json={"name": name}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["page"]

    def _default_page_of(self, material_id: str) -> dict:
        pages = self.client.get(f"/api/materials/{material_id}/pages").json()["pages"]
        self.assertEqual(len(pages), 1)
        return pages[0]


# ────────────────────────────────────────────────────────────────────
# 1. 素材归档与恢复
# ────────────────────────────────────────────────────────────────────


class MaterialArchiveTests(_MaterialsLibraryBase):
    """素材归档与恢复。"""

    def test_archive_material(self) -> None:
        material = self._create_material()
        response = self.client.post(f"/api/materials/{material['id']}/archive")
        self.assertEqual(response.status_code, 200)
        archived = response.json()["material"]
        self.assertIsNotNone(archived["archived_at"])
        # 素材归档状态由 archived_at 标记，validation_status 保持不变
        self.assertEqual(archived["validation_status"], material["validation_status"])

    def test_archive_nonexistent_returns_404(self) -> None:
        response = self.client.post("/api/materials/nonexistent-id/archive")
        self.assertEqual(response.status_code, 404)

    def test_restore_archived_material(self) -> None:
        material = self._create_material()
        self.client.post(f"/api/materials/{material['id']}/archive")
        response = self.client.post(f"/api/materials/{material['id']}/restore")
        self.assertEqual(response.status_code, 200)
        restored = response.json()["material"]
        self.assertIsNone(restored["archived_at"])

    def test_archived_materials_excluded_from_default_list(self) -> None:
        self._create_material(name="活跃素材")
        to_archive = self._create_material(name="归档素材")
        self.client.post(f"/api/materials/{to_archive['id']}/archive")

        response = self.client.get("/api/materials")
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["items"]]
        self.assertIn("活跃素材", names)
        self.assertNotIn("归档素材", names)

    def test_archived_materials_included_with_param(self) -> None:
        to_archive = self._create_material(name="归档素材")
        self.client.post(f"/api/materials/{to_archive['id']}/archive")

        response = self.client.get("/api/materials?archived=true")
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()["items"]]
        self.assertIn("归档素材", names)

    def test_restore_deleted_material(self) -> None:
        """恢复回收站素材后 deleted_at 为空。"""
        material = self._create_material()
        self.client.delete(f"/api/materials/{material['id']}")
        response = self.client.post(f"/api/materials/{material['id']}/restore")
        self.assertEqual(response.status_code, 200)
        restored = response.json()["material"]
        self.assertIsNone(restored["deleted_at"])
        # 恢复后详情接口应可再次访问
        again = self.client.get(f"/api/materials/{material['id']}")
        self.assertEqual(again.status_code, 200)


# ────────────────────────────────────────────────────────────────────
# 2. 素材软删除与回收站
# ────────────────────────────────────────────────────────────────────


class MaterialSoftDeleteTests(_MaterialsLibraryBase):
    """素材软删除、回收站和永久删除。"""

    def test_soft_delete_material(self) -> None:
        material = self._create_material()
        response = self.client.delete(f"/api/materials/{material['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        # 软删除后默认 GET 详情返回 404（get_material 过滤 deleted_at IS NULL）
        again = self.client.get(f"/api/materials/{material['id']}")
        self.assertEqual(again.status_code, 404)

    def test_soft_delete_nonexistent_returns_404(self) -> None:
        response = self.client.delete("/api/materials/nonexistent-id")
        self.assertEqual(response.status_code, 404)

    def test_list_trash_materials(self) -> None:
        material = self._create_material(name="回收站素材")
        self.client.delete(f"/api/materials/{material['id']}")

        response = self.client.get("/api/materials/trash")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        ids = [item["id"] for item in body["items"]]
        self.assertIn(material["id"], ids)

    def test_restore_from_trash(self) -> None:
        material = self._create_material()
        self.client.delete(f"/api/materials/{material['id']}")
        response = self.client.post(f"/api/materials/{material['id']}/restore")
        self.assertEqual(response.status_code, 200)
        restored = response.json()["material"]
        self.assertIsNone(restored["deleted_at"])
        # 恢复后详情可访问
        again = self.client.get(f"/api/materials/{material['id']}")
        self.assertEqual(again.status_code, 200)

    def test_permanent_delete_material(self) -> None:
        material = self._create_material()
        response = self.client.delete(f"/api/materials/{material['id']}/permanent")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        # 永久删除后 GET 返回 404
        again = self.client.get(f"/api/materials/{material['id']}")
        self.assertEqual(again.status_code, 404)
        # 回收站也不应再包含该素材
        trash = self.client.get("/api/materials/trash").json()
        self.assertNotIn(material["id"], [item["id"] for item in trash["items"]])

    def test_permanent_delete_nonexistent_returns_404(self) -> None:
        response = self.client.delete("/api/materials/nonexistent-id/permanent")
        self.assertEqual(response.status_code, 404)

    def test_permanent_delete_cleans_references(self) -> None:
        """永久删除后 small_scene_materials 中的关联被清除。"""
        chain = self._create_project_chain()
        small_scene_id = chain["small_scene"]["id"]
        material = self._create_material(material_type="scene")

        # 关联素材到小场景
        associate = self.client.put(
            f"/api/small-scenes/{small_scene_id}/materials",
            json={"material_ids": [material["id"]]},
        )
        self.assertEqual(associate.status_code, 200)
        # 确认关联存在
        linked = self.client.get(
            f"/api/small-scenes/{small_scene_id}/materials"
        ).json()["materials"]
        self.assertEqual(len(linked), 1)

        # 永久删除素材
        self.client.delete(f"/api/materials/{material['id']}/permanent")

        # 小场景素材关联应已清除
        after = self.client.get(
            f"/api/small-scenes/{small_scene_id}/materials"
        ).json()["materials"]
        self.assertEqual(after, [])


# ────────────────────────────────────────────────────────────────────
# 3. 素材引用反查
# ────────────────────────────────────────────────────────────────────


class MaterialReferencesTests(_MaterialsLibraryBase):
    """素材引用反查。"""

    def test_references_empty(self) -> None:
        material = self._create_material()
        response = self.client.get(f"/api/materials/{material['id']}/references")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["small_scenes"], [])
        self.assertEqual(body["scene_pages"], [])
        self.assertEqual(body["projects"], [])
        self.assertEqual(body["total_count"], 0)

    def test_references_with_small_scene(self) -> None:
        chain = self._create_project_chain()
        small_scene_id = chain["small_scene"]["id"]
        material = self._create_material(material_type="scene")

        self.client.put(
            f"/api/small-scenes/{small_scene_id}/materials",
            json={"material_ids": [material["id"]]},
        )

        response = self.client.get(f"/api/materials/{material['id']}/references")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["small_scenes"]), 1)
        ss_ref = body["small_scenes"][0]
        self.assertEqual(ss_ref["id"], small_scene_id)
        self.assertEqual(ss_ref["project_id"], chain["project"]["id"])
        # projects 去重后应包含 1 个项目
        self.assertEqual(len(body["projects"]), 1)
        self.assertEqual(body["projects"][0]["id"], chain["project"]["id"])
        self.assertEqual(body["total_count"], 1)

    def test_references_with_scene_page_mapping(self) -> None:
        """通过素材页映射到场景页后返回引用。"""
        chain = self._create_project_chain()
        small_scene_id = chain["small_scene"]["id"]
        # 素材类型 composition，匹配默认页
        material = self._create_material(name="构图素材", material_type="composition")
        default_page = self._default_page_of(material["id"])

        # 关联素材到小场景（references 同时需要 small_scene_materials）
        self.client.put(
            f"/api/small-scenes/{small_scene_id}/materials",
            json={"material_ids": [material["id"]]},
        )
        # 创建场景页
        scene_page = self._create_scene_page(small_scene_id, "场景页1")
        # 设置场景页映射：composition 类型 -> 该素材页
        mapping = self.client.put(
            f"/api/small-scene-pages/{scene_page['id']}/mappings/composition",
            json={"material_page_id": default_page["id"]},
        )
        self.assertEqual(mapping.status_code, 200)

        response = self.client.get(f"/api/materials/{material['id']}/references")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        # 场景页引用应存在
        self.assertEqual(len(body["scene_pages"]), 1)
        sp_ref = body["scene_pages"][0]
        self.assertEqual(sp_ref["id"], scene_page["id"])
        self.assertEqual(sp_ref["small_scene_id"], small_scene_id)
        self.assertEqual(sp_ref["material_type"], "composition")
        # 总数 = 小场景引用数 + 场景页引用数
        self.assertEqual(body["total_count"], 2)

    def test_references_nonexistent_returns_404(self) -> None:
        response = self.client.get("/api/materials/nonexistent-id/references")
        self.assertEqual(response.status_code, 404)

    def test_references_count_correct(self) -> None:
        """引用数量统计正确：跨多个小场景与场景页。"""
        chain = self._create_project_chain()
        small_scene_id = chain["small_scene"]["id"]
        material = self._create_material(material_type="composition")
        default_page = self._default_page_of(material["id"])

        # 关联到小场景
        self.client.put(
            f"/api/small-scenes/{small_scene_id}/materials",
            json={"material_ids": [material["id"]]},
        )
        # 创建两个场景页并都映射到该素材页
        sp1 = self._create_scene_page(small_scene_id, "场景页A")
        sp2 = self._create_scene_page(small_scene_id, "场景页B")
        self.client.put(
            f"/api/small-scene-pages/{sp1['id']}/mappings/composition",
            json={"material_page_id": default_page["id"]},
        )
        self.client.put(
            f"/api/small-scene-pages/{sp2['id']}/mappings/composition",
            json={"material_page_id": default_page["id"]},
        )

        body = self.client.get(f"/api/materials/{material['id']}/references").json()
        # 1 个小场景 + 2 个场景页 = 3
        self.assertEqual(len(body["small_scenes"]), 1)
        self.assertEqual(len(body["scene_pages"]), 2)
        self.assertEqual(body["total_count"], 3)


# ────────────────────────────────────────────────────────────────────
# 4. 素材页预览图
# ────────────────────────────────────────────────────────────────────


class MaterialPagePreviewTests(_MaterialsLibraryBase):
    """素材页预览图上传、读取、缩略图、删除。"""

    def test_upload_page_preview_png(self) -> None:
        material = self._create_material()
        page = self._default_page_of(material["id"])
        img = _make_image_bytes("PNG")
        response = self.client.post(
            f"/api/material-pages/{page['id']}/preview",
            files={"file": ("p.png", img, "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(
            body["preview_url"], f"/api/material-pages/{page['id']}/preview"
        )
        self.assertEqual(
            body["thumbnail_url"], f"/api/material-pages/{page['id']}/thumbnail"
        )

    def test_upload_page_preview_jpeg(self) -> None:
        material = self._create_material()
        page = self._default_page_of(material["id"])
        img = _make_image_bytes("JPEG")
        response = self.client.post(
            f"/api/material-pages/{page['id']}/preview",
            files={"file": ("p.jpg", img, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("preview_url", response.json())

    def test_get_page_preview(self) -> None:
        material = self._create_material()
        page = self._default_page_of(material["id"])
        img = _make_image_bytes("PNG")
        self.client.post(
            f"/api/material-pages/{page['id']}/preview",
            files={"file": ("p.png", img, "image/png")},
        )
        response = self.client.get(f"/api/material-pages/{page['id']}/preview")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertIn("cache-control", response.headers)

    def test_get_page_thumbnail(self) -> None:
        material = self._create_material()
        page = self._default_page_of(material["id"])
        img = _make_image_bytes("PNG", size=(800, 600))
        self.client.post(
            f"/api/material-pages/{page['id']}/preview",
            files={"file": ("p.png", img, "image/png")},
        )
        response = self.client.get(f"/api/material-pages/{page['id']}/thumbnail")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/webp")

    def test_get_page_preview_when_none_returns_404(self) -> None:
        material = self._create_material()
        page = self._default_page_of(material["id"])
        response = self.client.get(f"/api/material-pages/{page['id']}/preview")
        self.assertEqual(response.status_code, 404)

    def test_delete_page_preview(self) -> None:
        material = self._create_material()
        page = self._default_page_of(material["id"])
        img = _make_image_bytes("PNG")
        self.client.post(
            f"/api/material-pages/{page['id']}/preview",
            files={"file": ("p.png", img, "image/png")},
        )
        response = self.client.delete(f"/api/material-pages/{page['id']}/preview")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        # 删除后读取返回 404
        again = self.client.get(f"/api/material-pages/{page['id']}/preview")
        self.assertEqual(again.status_code, 404)
        thumb = self.client.get(f"/api/material-pages/{page['id']}/thumbnail")
        self.assertEqual(thumb.status_code, 404)

    def test_upload_page_preview_nonexistent_page_returns_404(self) -> None:
        img = _make_image_bytes("PNG")
        response = self.client.post(
            "/api/material-pages/nonexistent-id/preview",
            files={"file": ("p.png", img, "image/png")},
        )
        self.assertEqual(response.status_code, 404)

    def test_upload_page_preview_invalid_format_returns_415(self) -> None:
        material = self._create_material()
        page = self._default_page_of(material["id"])
        response = self.client.post(
            f"/api/material-pages/{page['id']}/preview",
            files={"file": ("p.gif", b"GIF89a not really a gif", "image/gif")},
        )
        self.assertEqual(response.status_code, 415)


# ────────────────────────────────────────────────────────────────────
# 5. 素材页复制
# ────────────────────────────────────────────────────────────────────


class MaterialPageCopyTests(_MaterialsLibraryBase):
    """素材页复制。"""

    def test_copy_material_page(self) -> None:
        material = self._create_material(name="源素材")
        source_page = self._default_page_of(material["id"])
        response = self.client.post(f"/api/material-pages/{source_page['id']}/copy")
        self.assertEqual(response.status_code, 201, response.text)
        new_page = response.json()
        self.assertNotEqual(new_page["id"], source_page["id"])
        # 名称带"副本"
        self.assertIn("副本", new_page["name"])
        self.assertIn(source_page["name"], new_page["name"])
        # sort_order 递增（默认页 sort_order=1，副本应为 2）
        self.assertEqual(new_page["sort_order"], 2)
        # source_page_id 为源页 id
        self.assertEqual(new_page["source_page_id"], source_page["id"])
        self.assertEqual(new_page["material_id"], material["id"])

    def test_copy_material_page_sequential(self) -> None:
        """连续复制名称带序号。"""
        material = self._create_material(name="顺序素材")
        source_page = self._default_page_of(material["id"])

        first = self.client.post(
            f"/api/material-pages/{source_page['id']}/copy"
        ).json()
        self.assertEqual(first["name"], "顺序素材 副本")

        second = self.client.post(
            f"/api/material-pages/{source_page['id']}/copy"
        ).json()
        # 第二次复制默认页时，"顺序素材 副本" 已存在，应得到 "顺序素材 副本 2"
        self.assertEqual(second["name"], "顺序素材 副本 2")

        third = self.client.post(
            f"/api/material-pages/{source_page['id']}/copy"
        ).json()
        self.assertEqual(third["name"], "顺序素材 副本 3")

    def test_copy_nonexistent_page_returns_404(self) -> None:
        response = self.client.post("/api/material-pages/nonexistent-id/copy")
        self.assertEqual(response.status_code, 404)


# ────────────────────────────────────────────────────────────────────
# 6. 素材版本历史
# ────────────────────────────────────────────────────────────────────


class MaterialVersionTests(_MaterialsLibraryBase):
    """素材版本历史：快照、列表、详情、恢复、自动版本。"""

    def test_create_version(self) -> None:
        material = self._create_material()
        response = self.client.post(
            f"/api/materials/{material['id']}/versions",
            json={"label": "初版"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        version = response.json()["version"]
        self.assertEqual(version["version_number"], 1)
        self.assertEqual(version["label"], "初版")
        self.assertEqual(version["material_id"], material["id"])

    def test_list_versions(self) -> None:
        material = self._create_material()
        self.client.post(
            f"/api/materials/{material['id']}/versions", json={"label": "v1"}
        )
        self.client.post(
            f"/api/materials/{material['id']}/versions", json={"label": "v2"}
        )
        response = self.client.get(f"/api/materials/{material['id']}/versions")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 2)
        # 按版本号降序
        numbers = [v["version_number"] for v in body["items"]]
        self.assertEqual(numbers, [2, 1])

    def test_get_version_detail(self) -> None:
        material = self._create_material(name="详情素材")
        self.client.post(
            f"/api/materials/{material['id']}/versions", json={"label": "含快照"}
        )
        response = self.client.get(
            f"/api/materials/{material['id']}/versions/1"
        )
        self.assertEqual(response.status_code, 200)
        version = response.json()["version"]
        self.assertEqual(version["version_number"], 1)
        # snapshot 字段含完整快照
        self.assertIn("snapshot", version)
        self.assertIn("material", version["snapshot"])
        self.assertEqual(version["snapshot"]["material"]["name"], "详情素材")

    def test_restore_version(self) -> None:
        """恢复版本后素材字段还原。"""
        material = self._create_material(name="原名")
        # 第一次更新生成版本 1（快照内容为"改名A"）
        self.client.patch(
            f"/api/materials/{material['id']}", json={"name": "改名A"}
        )
        # 第二次更新生成版本 2（快照内容为"改名B"）
        self.client.patch(
            f"/api/materials/{material['id']}", json={"name": "改名B"}
        )
        # 当前应为"改名B"
        current = self.client.get(f"/api/materials/{material['id']}").json()["material"]
        self.assertEqual(current["name"], "改名B")

        # 恢复到版本 1（"改名A"）
        response = self.client.post(
            f"/api/materials/{material['id']}/versions/1/restore"
        )
        self.assertEqual(response.status_code, 200)
        restored = response.json()["material"]
        self.assertEqual(restored["name"], "改名A")

    def test_auto_version_on_update(self) -> None:
        """更新素材后自动创建版本。"""
        material = self._create_material(name="自动版本")
        # 初始无版本
        before = self.client.get(
            f"/api/materials/{material['id']}/versions"
        ).json()["total"]
        self.assertEqual(before, 0)

        self.client.patch(
            f"/api/materials/{material['id']}", json={"name": "更新后"}
        )

        after = self.client.get(
            f"/api/materials/{material['id']}/versions"
        ).json()
        self.assertEqual(after["total"], 1)
        self.assertEqual(after["items"][0]["version_number"], 1)

    def test_list_versions_nonexistent_returns_404(self) -> None:
        response = self.client.get("/api/materials/nonexistent-id/versions")
        self.assertEqual(response.status_code, 404)


# ────────────────────────────────────────────────────────────────────
# 7. 素材复制
# ────────────────────────────────────────────────────────────────────


class MaterialCopyTests(_MaterialsLibraryBase):
    """素材复制。"""

    def test_copy_material(self) -> None:
        source = self._create_material(
            name="源素材",
            material_type="scene",
            content="源正文",
            description="源描述",
            validation_status="verified",
        )
        response = self.client.post(
            f"/api/materials/{source['id']}/copy", json={"name": "副本素材"}
        )
        self.assertEqual(response.status_code, 201, response.text)
        copy = response.json()["material"]
        self.assertNotEqual(copy["id"], source["id"])
        # source_material_id 为源 id
        self.assertEqual(copy["source_material_id"], source["id"])
        # 复制后状态为 unverified
        self.assertEqual(copy["validation_status"], "unverified")
        # 内容/类型/描述被复制
        self.assertEqual(copy["content"], "源正文")
        self.assertEqual(copy["material_type"], "scene")
        self.assertEqual(copy["description"], "源描述")
        # 复制无预览图
        self.assertIsNone(copy["preview_url"])
        self.assertIsNone(copy["thumbnail_url"])

    def test_copy_material_includes_pages(self) -> None:
        source = self._create_material(name="带页素材")
        # 默认已有一个素材页，再追加一页
        extra = self.client.post(
            f"/api/materials/{source['id']}/pages", json={"name": "第二页"}
        ).json()
        source_page_ids = [
            p["id"] for p in self.client.get(
                f"/api/materials/{source['id']}/pages"
            ).json()["pages"]
        ]
        self.assertEqual(len(source_page_ids), 2)

        response = self.client.post(
            f"/api/materials/{source['id']}/copy", json={"name": "带页副本"}
        )
        self.assertEqual(response.status_code, 201)
        copy_id = response.json()["material"]["id"]

        copy_pages = self.client.get(
            f"/api/materials/{copy_id}/pages"
        ).json()["pages"]
        # 页数与源一致
        self.assertEqual(len(copy_pages), 2)
        # 新页 source_page_id 为源页 id
        copy_source_ids = {p["source_page_id"] for p in copy_pages}
        self.assertEqual(copy_source_ids, set(source_page_ids))
        # 新页 id 不与源页 id 冲突
        copy_page_ids = {p["id"] for p in copy_pages}
        self.assertEqual(copy_page_ids & set(source_page_ids), set())

    def test_copy_material_blank_name_returns_422(self) -> None:
        source = self._create_material(name="空名复制源")
        response = self.client.post(
            f"/api/materials/{source['id']}/copy", json={"name": "   "}
        )
        self.assertEqual(response.status_code, 422)

    def test_copy_nonexistent_returns_404(self) -> None:
        response = self.client.post(
            "/api/materials/nonexistent-id/copy", json={"name": "副本"}
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
