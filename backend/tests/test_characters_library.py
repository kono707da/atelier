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


class _CharacterLibraryBase(unittest.TestCase):
    """Shared setup and helpers for character library 1.4 tests."""

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
        self.project = self.manager.create_project("人物库测试项目")

    # ── Helpers ────────────────────────────────────────────────

    def _create_character(self, name: str = "测试人物", **kwargs) -> dict:
        payload = {"name": name, **kwargs}
        response = self.client.post("/api/characters", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["character"]

    def _create_character_in_project(
        self, project_id: str, name: str = "测试人物"
    ) -> dict:
        response = self.client.post(
            f"/api/characters?project_id={project_id}", json={"name": name}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["character"]

    def _create_project(self, name: str = "测试项目") -> dict:
        response = self.client.post("/api/projects", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["project"]

    def _create_variant(self, character_id: str, name: str = "测试变体") -> dict:
        response = self.client.post(
            f"/api/characters/{character_id}/variants",
            json={"name": name},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["variant"]

    def _create_spec(
        self, spec_type: str = "full_body", **kwargs
    ) -> dict:
        payload = {"spec_type": spec_type, **kwargs}
        response = self.client.post("/api/specs", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["spec"]

    def _create_shot_page(self, title: str = "测试场景页") -> dict:
        """Create a shot page via manager (chapter → large_scene → small_scene chain)."""
        chapter = self.manager.create_chapter(str(self.project["id"]), "测试章节")
        large_scene = self.manager.create_large_scene(str(chapter["id"]), "测试大场景")
        small_scene = self.manager.create_small_scene(
            str(large_scene["id"]), "测试小场景"
        )
        return self.manager.create_shot_page(str(small_scene["id"]), title)

    def _list_variant_spec_values(self, variant_id: str) -> list[dict]:
        response = self.client.get(
            f"/api/character-variants/{variant_id}/spec-values"
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["items"]


# ── 1. Archive / Restore / Soft delete / Permanent delete ──────


class CharacterArchiveTests(_CharacterLibraryBase):
    def test_archive_character(self) -> None:
        char = self._create_character()
        response = self.client.post(f"/api/characters/{char['id']}/archive")
        self.assertEqual(response.status_code, 200, response.text)
        archived = response.json()["character"]
        self.assertIsNotNone(archived["archived_at"])

    def test_restore_archived_character(self) -> None:
        char = self._create_character()
        self.client.post(f"/api/characters/{char['id']}/archive")
        response = self.client.post(f"/api/characters/{char['id']}/restore")
        self.assertEqual(response.status_code, 200, response.text)
        restored = response.json()["character"]
        self.assertIsNone(restored["archived_at"])

    def test_archived_characters_excluded_by_default(self) -> None:
        char = self._create_character(name="将被归档")
        self.client.post(f"/api/characters/{char['id']}/archive")
        response = self.client.get("/api/characters")
        self.assertEqual(response.status_code, 200)
        names = [c["name"] for c in response.json()["items"]]
        self.assertNotIn("将被归档", names)

    def test_archived_characters_included_with_param(self) -> None:
        char = self._create_character(name="归档可见")
        self.client.post(f"/api/characters/{char['id']}/archive")
        response = self.client.get("/api/characters?archived=true")
        self.assertEqual(response.status_code, 200)
        names = [c["name"] for c in response.json()["items"]]
        self.assertIn("归档可见", names)

    def test_soft_delete_character(self) -> None:
        char = self._create_character(name="将被删除")
        response = self.client.delete(f"/api/characters/{char['id']}")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["deleted"])
        self.assertIsNotNone(response.json()["character"]["deleted_at"])
        listed = self.client.get("/api/characters").json()
        self.assertNotIn(char["id"], [c["id"] for c in listed["items"]])

    def test_list_trash_characters(self) -> None:
        char = self._create_character(name="回收站人物")
        self.client.delete(f"/api/characters/{char['id']}")
        response = self.client.get("/api/characters?trash=true")
        self.assertEqual(response.status_code, 200)
        ids = [c["id"] for c in response.json()["items"]]
        self.assertIn(char["id"], ids)

    def test_restore_deleted_character(self) -> None:
        char = self._create_character(name="待恢复")
        self.client.delete(f"/api/characters/{char['id']}")
        response = self.client.post(f"/api/characters/{char['id']}/restore")
        self.assertEqual(response.status_code, 200, response.text)
        restored = response.json()["character"]
        self.assertIsNone(restored["deleted_at"])
        listed = self.client.get("/api/characters").json()
        self.assertIn(char["id"], [c["id"] for c in listed["items"]])

    def test_permanent_delete_character(self) -> None:
        char = self._create_character(name="永久删除")
        response = self.client.delete(f"/api/characters/{char['id']}/permanent")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["deleted"])
        self.assertIsNone(self.manager.get_character(char["id"]))

    def test_permanent_delete_cleans_variants(self) -> None:
        char = self._create_character(name="带变体删除")
        self._create_variant(char["id"], "裙装")
        variants = self.manager.list_character_variants(str(char["id"]))
        self.assertEqual(len(variants), 2)
        self.client.delete(f"/api/characters/{char['id']}/permanent")
        remaining = self.manager.list_character_variants(str(char["id"]))
        self.assertEqual(remaining, [])

    def test_permanent_delete_missing_returns_404(self) -> None:
        response = self.client.delete("/api/characters/missing-id/permanent")
        self.assertEqual(response.status_code, 404)


# ── 2. Copy ────────────────────────────────────────────────────


class CharacterCopyTests(_CharacterLibraryBase):
    def test_copy_character(self) -> None:
        char = self._create_character(name="源人物", description="说明")
        response = self.client.post(
            f"/api/characters/{char['id']}/copy",
            json={"new_name": "复制人物"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        copy = response.json()["character"]
        self.assertEqual(copy["name"], "复制人物")
        self.assertEqual(copy["source"], "copy")
        self.assertEqual(copy["source_identifier"], char["id"])
        self.assertNotEqual(copy["id"], char["id"])
        # The new character should be retrievable via GET
        self.assertIsNotNone(self.manager.get_character(copy["id"]))

    def test_copy_character_includes_variants(self) -> None:
        char = self._create_character(name="带变体源")
        self._create_variant(char["id"], "裙装")
        response = self.client.post(
            f"/api/characters/{char['id']}/copy",
            json={"new_name": "带变体副本"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        copy = response.json()["character"]
        source_variants = self.manager.list_character_variants(str(char["id"]))
        copy_variants = self.manager.list_character_variants(str(copy["id"]))
        self.assertEqual(len(copy_variants), len(source_variants))
        self.assertEqual(
            sorted(v["name"] for v in copy_variants),
            sorted(v["name"] for v in source_variants),
        )

    def test_copy_character_includes_spec_values(self) -> None:
        self._create_spec("full_body")
        self._create_spec("close_up")
        char = self._create_character(name="带规格源")
        response = self.client.post(
            f"/api/characters/{char['id']}/copy",
            json={"new_name": "带规格副本"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        copy = response.json()["character"]
        source_variants = self.manager.list_character_variants(str(char["id"]))
        copy_variants = self.manager.list_character_variants(str(copy["id"]))
        # Default variant exists; spec_values count should match spec count
        for cv in copy_variants:
            values = self._list_variant_spec_values(cv["id"])
            self.assertEqual(len(values), 2)
        # Cross-check: same number of spec_values between source and copy
        source_values = self._list_variant_spec_values(source_variants[0]["id"])
        copy_values = self._list_variant_spec_values(copy_variants[0]["id"])
        self.assertEqual(len(source_values), len(copy_values))

    def test_copy_nonexistent_returns_404(self) -> None:
        response = self.client.post(
            "/api/characters/missing-id/copy",
            json={"new_name": "新人物"},
        )
        self.assertEqual(response.status_code, 404)

    def test_copy_with_empty_name_returns_422(self) -> None:
        char = self._create_character(name="源人物")
        response = self.client.post(
            f"/api/characters/{char['id']}/copy",
            json={"new_name": "   "},
        )
        self.assertEqual(response.status_code, 422)


# ── 3. Tags ────────────────────────────────────────────────────


class CharacterTagsTests(_CharacterLibraryBase):
    def test_set_character_tags(self) -> None:
        char = self._create_character()
        response = self.client.put(
            f"/api/characters/{char['id']}/tags",
            json={"tags": ["主角", "奇幻"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        tags = response.json()["character"]["tags"]
        # Backend stores tags sorted by Python's sorted() (Unicode codepoint order)
        self.assertEqual(set(tags), {"主角", "奇幻"})
        self.assertEqual(len(tags), 2)

    def test_set_character_tags_replaces(self) -> None:
        char = self._create_character()
        self.client.put(
            f"/api/characters/{char['id']}/tags",
            json={"tags": ["主角", "配角"]},
        )
        response = self.client.put(
            f"/api/characters/{char['id']}/tags",
            json={"tags": ["反派"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        tags = response.json()["character"]["tags"]
        self.assertEqual(tags, ["反派"])

    def test_set_character_tags_dedup(self) -> None:
        char = self._create_character()
        response = self.client.put(
            f"/api/characters/{char['id']}/tags",
            json={"tags": ["主角", "主角", "配角", "配角"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        tags = response.json()["character"]["tags"]
        self.assertEqual(sorted(tags), ["主角", "配角"])

    def test_set_character_tags_empty_clears(self) -> None:
        char = self._create_character()
        self.client.put(
            f"/api/characters/{char['id']}/tags",
            json={"tags": ["主角"]},
        )
        response = self.client.put(
            f"/api/characters/{char['id']}/tags",
            json={"tags": []},
        )
        self.assertEqual(response.status_code, 200, response.text)
        tags = response.json()["character"]["tags"]
        self.assertEqual(tags, [])

    def test_filter_by_tag(self) -> None:
        self._create_character(name="主角人物")
        tagged = self._create_character(name="配角人物")
        self.client.put(
            f"/api/characters/{tagged['id']}/tags",
            json={"tags": ["配角"]},
        )
        response = self.client.get("/api/characters?tag=配角")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "配角人物")

    def test_set_tags_missing_character_returns_404(self) -> None:
        response = self.client.put(
            "/api/characters/missing-id/tags",
            json={"tags": ["主角"]},
        )
        self.assertEqual(response.status_code, 404)


# ── 4. Cover ───────────────────────────────────────────────────


class CharacterCoverTests(_CharacterLibraryBase):
    def test_upload_png_cover(self) -> None:
        char = self._create_character()
        response = self.client.post(
            f"/api/characters/{char['id']}/cover",
            files={"file": ("cover.png", _make_image_bytes("PNG"), "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["character"]["cover_path"])

    def test_upload_jpeg_cover(self) -> None:
        char = self._create_character()
        response = self.client.post(
            f"/api/characters/{char['id']}/cover",
            files={"file": ("cover.jpg", _make_image_bytes("JPEG"), "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["character"]["cover_path"])

    def test_upload_webp_cover(self) -> None:
        char = self._create_character()
        response = self.client.post(
            f"/api/characters/{char['id']}/cover",
            files={"file": ("cover.webp", _make_image_bytes("WEBP"), "image/webp")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["character"]["cover_path"])

    def test_get_cover(self) -> None:
        char = self._create_character()
        payload = _make_image_bytes("PNG")
        self.client.post(
            f"/api/characters/{char['id']}/cover",
            files={"file": ("cover.png", payload, "image/png")},
        )
        response = self.client.get(f"/api/characters/{char['id']}/cover")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.content, payload)

    def test_get_cover_thumbnail(self) -> None:
        char = self._create_character()
        self.client.post(
            f"/api/characters/{char['id']}/cover",
            files={"file": ("cover.png", _make_image_bytes("PNG", (1024, 768)), "image/png")},
        )
        response = self.client.get(f"/api/characters/{char['id']}/cover/thumbnail")
        self.assertEqual(response.status_code, 200)
        # Note: Starlette FileResponse relies on the OS mimetype registry for the
        # .webp extension. On Windows the .webp MIME type may not be registered,
        # causing content-type to fall back to text/plain. We therefore only
        # verify the payload is a decodable image and within 512px.
        thumb = Image.open(io.BytesIO(response.content))
        self.assertLessEqual(max(thumb.size), 512)

    def test_delete_cover(self) -> None:
        char = self._create_character()
        self.client.post(
            f"/api/characters/{char['id']}/cover",
            files={"file": ("cover.png", _make_image_bytes("PNG"), "image/png")},
        )
        response = self.client.delete(f"/api/characters/{char['id']}/cover")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["character"]["cover_path"])
        follow = self.client.get(f"/api/characters/{char['id']}/cover")
        self.assertEqual(follow.status_code, 404)

    def test_get_cover_missing_returns_404(self) -> None:
        char = self._create_character()
        response = self.client.get(f"/api/characters/{char['id']}/cover")
        self.assertEqual(response.status_code, 404)

    def test_upload_invalid_format_returns_415(self) -> None:
        char = self._create_character()
        response = self.client.post(
            f"/api/characters/{char['id']}/cover",
            files={"file": ("cover.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(response.status_code, 415)

    def test_upload_cover_missing_character_returns_404(self) -> None:
        response = self.client.post(
            "/api/characters/missing-id/cover",
            files={"file": ("cover.png", _make_image_bytes("PNG"), "image/png")},
        )
        self.assertEqual(response.status_code, 404)


# ── 5. References (reverse lookup) ────────────────────────────


class CharacterReferencesTests(_CharacterLibraryBase):
    def test_no_references(self) -> None:
        char = self._create_character()
        response = self.client.get(f"/api/characters/{char['id']}/references")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["projects"], [])
        self.assertEqual(body["shot_pages"], [])
        self.assertEqual(body["project_count"], 0)
        self.assertEqual(body["shot_page_count"], 0)

    def test_referenced_by_project(self) -> None:
        project = self._create_project("引用项目")
        char = self._create_character()
        self.client.post(
            f"/api/projects/{project['id']}/characters/{char['id']}"
        )
        response = self.client.get(f"/api/characters/{char['id']}/references")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["project_count"], 1)
        self.assertEqual(body["projects"][0]["project_id"], project["id"])
        self.assertEqual(body["projects"][0]["project_name"], "引用项目")

    def test_referenced_by_shot_page(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        shot_page = self._create_shot_page("场景页A")
        self.client.put(
            f"/api/shot-pages/{shot_page['id']}/character",
            json={"character_id": char["id"], "variant_id": variant["id"]},
        )
        response = self.client.get(f"/api/characters/{char['id']}/references")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["shot_page_count"], 1)
        self.assertEqual(body["shot_pages"][0]["shot_page_id"], shot_page["id"])


# ── 6. Variant extended (archive / restore / copy / reorder / preview) ──


class CharacterVariantExtendedTests(_CharacterLibraryBase):
    def test_archive_variant(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        response = self.client.post(
            f"/api/character-variants/{variant['id']}/archive"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["variant"]["archived_at"])

    def test_restore_variant(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        self.client.post(f"/api/character-variants/{variant['id']}/archive")
        response = self.client.post(
            f"/api/character-variants/{variant['id']}/restore"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["variant"]["archived_at"])

    def test_archived_variants_excluded_by_default(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        self.client.post(f"/api/character-variants/{variant['id']}/archive")
        response = self.client.get(
            f"/api/characters/{char['id']}/variants"
        )
        self.assertEqual(response.status_code, 200, response.text)
        ids = [v["id"] for v in response.json()["items"]]
        self.assertNotIn(variant["id"], ids)

    def test_copy_variant(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        response = self.client.post(
            f"/api/character-variants/{variant['id']}/copy",
            json={"new_name": "裙装备份"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        copy = response.json()["variant"]
        self.assertEqual(copy["name"], "裙装备份")
        self.assertEqual(copy["source_variant_id"], variant["id"])
        self.assertNotEqual(copy["id"], variant["id"])
        variants = self.manager.list_character_variants(str(char["id"]))
        self.assertEqual(len(variants), 3)  # default + original + copy

    def test_copy_variant_missing_returns_404(self) -> None:
        response = self.client.post(
            "/api/character-variants/missing-id/copy",
            json={"new_name": "新变体"},
        )
        self.assertEqual(response.status_code, 404)

    def test_reorder_variants(self) -> None:
        char = self._create_character()
        v1 = self._create_variant(char["id"], "变体一")
        v2 = self._create_variant(char["id"], "变体二")
        v3 = self._create_variant(char["id"], "变体三")
        default_variant = self.manager.list_character_variants(str(char["id"]))
        # Sort orders before reorder: default=1, v1=2, v2=3, v3=4
        all_variants = [v["id"] for v in default_variant]
        # Reverse the order of non-default variants
        new_order = [all_variants[0], v3["id"], v2["id"], v1["id"]]
        response = self.client.put(
            f"/api/characters/{char['id']}/variants/reorder",
            json={"variant_ids": new_order},
        )
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual([v["id"] for v in items], new_order)
        self.assertEqual([v["sort_order"] for v in items], [1, 2, 3, 4])

    def test_upload_variant_preview(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        response = self.client.post(
            f"/api/character-variants/{variant['id']}/preview",
            files={"file": ("preview.png", _make_image_bytes("PNG"), "image/png")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["variant"]["preview_original_path"])
        self.assertIsNotNone(response.json()["variant"]["preview_thumbnail_path"])

    def test_get_variant_preview(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        payload = _make_image_bytes("PNG")
        self.client.post(
            f"/api/character-variants/{variant['id']}/preview",
            files={"file": ("preview.png", payload, "image/png")},
        )
        response = self.client.get(
            f"/api/character-variants/{variant['id']}/preview"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.content, payload)

    def test_delete_variant_preview(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        self.client.post(
            f"/api/character-variants/{variant['id']}/preview",
            files={"file": ("preview.png", _make_image_bytes("PNG"), "image/png")},
        )
        response = self.client.delete(
            f"/api/character-variants/{variant['id']}/preview"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json()["variant"]["preview_original_path"])
        self.assertIsNone(response.json()["variant"]["preview_thumbnail_path"])
        follow = self.client.get(
            f"/api/character-variants/{variant['id']}/preview"
        )
        self.assertEqual(follow.status_code, 404)

    def test_upload_variant_preview_invalid_format_returns_415(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        response = self.client.post(
            f"/api/character-variants/{variant['id']}/preview",
            files={"file": ("preview.txt", b"not an image", "text/plain")},
        )
        self.assertEqual(response.status_code, 415)


# ── 7. Spec matrix ────────────────────────────────────────────


class CharacterMatrixTests(_CharacterLibraryBase):
    def test_get_matrix(self) -> None:
        char = self._create_character()
        response = self.client.get(f"/api/characters/{char['id']}/matrix")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["character"]["id"], char["id"])
        for key in ("specs", "variants", "values", "missing_required"):
            self.assertIn(key, body)

    def test_matrix_empty_character(self) -> None:
        char = self._create_character()
        body = self.client.get(f"/api/characters/{char['id']}/matrix").json()
        # No specs configured, but default variant exists
        self.assertEqual(body["specs"], [])
        self.assertEqual(len(body["variants"]), 1)
        self.assertEqual(body["variants"][0]["name"], "默认")
        self.assertEqual(body["values"], {body["variants"][0]["id"]: {}})
        self.assertEqual(body["missing_required"], [])

    def test_matrix_with_specs_and_variants(self) -> None:
        spec_a = self._create_spec("full_body")
        spec_b = self._create_spec("close_up")
        char = self._create_character()
        self._create_variant(char["id"], "裙装")
        body = self.client.get(f"/api/characters/{char['id']}/matrix").json()
        self.assertEqual(len(body["specs"]), 2)
        self.assertEqual(len(body["variants"]), 2)  # default + 裙装
        spec_ids = [s["id"] for s in body["specs"]]
        self.assertEqual(set(spec_ids), {spec_a["id"], spec_b["id"]})
        for variant in body["variants"]:
            self.assertEqual(
                set(body["values"][variant["id"]].keys()), set(spec_ids)
            )

    def test_matrix_missing_required(self) -> None:
        self._create_spec("full_body", is_required=True)
        char = self._create_character()
        body = self.client.get(f"/api/characters/{char['id']}/matrix").json()
        self.assertEqual(len(body["missing_required"]), 1)
        missing = body["missing_required"][0]
        self.assertEqual(missing["variant_name"], "默认")
        self.assertEqual(missing["spec_label"], "full_body")

    def test_get_matrix_missing_character_returns_404(self) -> None:
        response = self.client.get("/api/characters/missing-id/matrix")
        self.assertEqual(response.status_code, 404)


# ── 8. Batch spec values ──────────────────────────────────────


class BatchSpecValueTests(_CharacterLibraryBase):
    def test_batch_update_spec_values(self) -> None:
        self._create_spec("full_body")
        self._create_spec("close_up")
        char = self._create_character()
        variants = self.manager.list_character_variants(str(char["id"]))
        values = self.manager.list_spec_values_for_variant(str(variants[0]["id"]))
        self.assertEqual(len(values), 2)
        updates = [
            {
                "spec_value_id": values[0]["id"],
                "prompt": "1girl",
                "lora_name": "a.safetensors",
                "lora_weight": 0.5,
            },
            {
                "spec_value_id": values[1]["id"],
                "prompt": "close-up",
                "notes": "近景说明",
            },
        ]
        response = self.client.post(
            "/api/character-spec-values/batch",
            json={"updates": updates},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["updated"], 2)
        # Verify each value
        v0 = self.manager.get_character_spec_value(values[0]["id"])
        self.assertEqual(v0["prompt"], "1girl")
        self.assertEqual(v0["lora_name"], "a.safetensors")
        self.assertAlmostEqual(v0["lora_weight"], 0.5)
        v1 = self.manager.get_character_spec_value(values[1]["id"])
        self.assertEqual(v1["prompt"], "close-up")
        self.assertEqual(v1["notes"], "近景说明")

    def test_batch_update_partial_failure(self) -> None:
        """When one update raises ValueError, the whole transaction is rolled back
        (single connection context manager). Already-applied updates do NOT persist."""
        self._create_spec("full_body")
        self._create_spec("close_up")
        char = self._create_character()
        variants = self.manager.list_character_variants(str(char["id"]))
        values = self.manager.list_spec_values_for_variant(str(variants[0]["id"]))
        original_prompt = values[0]["prompt"]
        updates = [
            {
                "spec_value_id": values[0]["id"],
                "prompt": "should be rolled back",
            },
            {
                "spec_value_id": values[1]["id"],
                "lora_weight": 3.5,  # out of range, triggers ValueError
            },
        ]
        response = self.client.post(
            "/api/character-spec-values/batch",
            json={"updates": updates},
        )
        self.assertEqual(response.status_code, 400, response.text)
        # First update should NOT persist due to transaction rollback
        v0 = self.manager.get_character_spec_value(values[0]["id"])
        self.assertEqual(v0["prompt"], original_prompt)


# ── 9. Shot page character binding ────────────────────────────


class ShotPageCharacterTests(_CharacterLibraryBase):
    def test_set_shot_page_character(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        shot_page = self._create_shot_page("场景页A")
        response = self.client.put(
            f"/api/shot-pages/{shot_page['id']}/character",
            json={"character_id": char["id"], "variant_id": variant["id"]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        ref = response.json()["reference"]
        self.assertEqual(ref["character_id"], char["id"])
        self.assertEqual(ref["variant_id"], variant["id"])
        self.assertEqual(ref["character_name"], "测试人物")
        self.assertEqual(ref["variant_name"], "裙装")

    def test_get_shot_page_character(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        shot_page = self._create_shot_page("场景页B")
        self.client.put(
            f"/api/shot-pages/{shot_page['id']}/character",
            json={"character_id": char["id"], "variant_id": variant["id"]},
        )
        response = self.client.get(
            f"/api/shot-pages/{shot_page['id']}/character"
        )
        self.assertEqual(response.status_code, 200, response.text)
        ref = response.json()["reference"]
        self.assertEqual(ref["character_id"], char["id"])
        self.assertEqual(ref["variant_id"], variant["id"])

    def test_clear_shot_page_character(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        shot_page = self._create_shot_page("场景页C")
        self.client.put(
            f"/api/shot-pages/{shot_page['id']}/character",
            json={"character_id": char["id"], "variant_id": variant["id"]},
        )
        response = self.client.delete(
            f"/api/shot-pages/{shot_page['id']}/character"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["cleared"])
        follow = self.client.get(
            f"/api/shot-pages/{shot_page['id']}/character"
        )
        self.assertEqual(follow.status_code, 404)

    def test_set_shot_page_character_missing_page_returns_404(self) -> None:
        char = self._create_character()
        variant = self._create_variant(char["id"], "裙装")
        response = self.client.put(
            "/api/shot-pages/missing-page-id/character",
            json={"character_id": char["id"], "variant_id": variant["id"]},
        )
        self.assertEqual(response.status_code, 404)

    def test_set_shot_page_character_missing_character_returns_404(self) -> None:
        """Both character_id and variant_id are unknown → router raises 404
        ("形象变体不存在。") since variant is checked first."""
        shot_page = self._create_shot_page("场景页D")
        response = self.client.put(
            f"/api/shot-pages/{shot_page['id']}/character",
            json={
                "character_id": "missing-character-id",
                "variant_id": "missing-variant-id",
            },
        )
        self.assertEqual(response.status_code, 404)


# ── 10. Project character link ────────────────────────────────


class ProjectCharacterLinkTests(_CharacterLibraryBase):
    def test_link_character_to_project(self) -> None:
        project = self._create_project("链接项目")
        char = self._create_character()
        response = self.client.post(
            f"/api/projects/{project['id']}/characters/{char['id']}"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["linked"])

    def test_unlink_character_from_project(self) -> None:
        project = self._create_project("解绑项目")
        char = self._create_character()
        self.client.post(
            f"/api/projects/{project['id']}/characters/{char['id']}"
        )
        response = self.client.delete(
            f"/api/projects/{project['id']}/characters/{char['id']}"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["linked"])
        listed = self.client.get(
            f"/api/characters?project_id={project['id']}"
        ).json()
        self.assertEqual(listed["total"], 0)

    def test_list_project_characters(self) -> None:
        project = self._create_project("列表项目")
        char = self._create_character(name="项目人物A")
        self.client.post(
            f"/api/projects/{project['id']}/characters/{char['id']}"
        )
        response = self.client.get(
            f"/api/characters?project_id={project['id']}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["name"], "项目人物A")

    def test_link_missing_character_returns_404(self) -> None:
        project = self._create_project("项目")
        response = self.client.post(
            f"/api/projects/{project['id']}/characters/missing-character-id"
        )
        self.assertEqual(response.status_code, 404)

    def test_link_missing_project_returns_404(self) -> None:
        char = self._create_character()
        response = self.client.post(
            f"/api/projects/missing-project-id/characters/{char['id']}"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
