"""MOD-10 全局图库测试。

测试范围：
- 感知哈希计算（aHash）
- 汉明距离计算
- 提示词提取
- 文件索引（单文件、增量、全量）
- FTS5 提示词全文检索
- 游标分页（多排序、多筛选）
- 相同图片搜索（按内容哈希）
- 近似图片搜索（按感知哈希汉明距离）
- 图库详情与关联实例
- API 端点
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend.app.app_factory import create_app
from backend.app.gallery import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    compute_perceptual_hash,
    extract_prompt_text,
    find_duplicate_images,
    find_similar_images,
    hamming_distance_hex,
    index_file_for_gallery,
    list_gallery_images,
    reindex_gallery,
    search_gallery_by_prompt,
    update_file_perceptual_hash,
)
from backend.app.output_receiver import (
    create_file_record,
    create_image_instance,
)


def _make_png(width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """生成纯色 PNG。"""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_png_with_pattern(
    width: int, height: int, seed: int
) -> bytes:
    """生成带简单模式的 PNG，便于 phash 区分。"""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            r = (x * 7 + seed) % 256
            g = (y * 11 + seed * 2) % 256
            b = ((x + y) * 13 + seed) % 256
            pixels[x, y] = (r, g, b)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class GalleryUnitTest(unittest.TestCase):
    """纯函数单元测试，不需要数据库。"""

    def test_compute_perceptual_hash_returns_hex(self) -> None:
        """感知哈希返回 16 位十六进制字符串。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "img.png"
            path.write_bytes(_make_png(64, 64, (128, 64, 192)))
            phash = compute_perceptual_hash(path)
            self.assertEqual(len(phash), 16)
            # 应是合法十六进制
            int(phash, 16)

    def test_compute_perceptual_hash_stable(self) -> None:
        """同一图片多次计算结果一致。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "img.png"
            path.write_bytes(_make_png_with_pattern(128, 128, seed=42))
            phash1 = compute_perceptual_hash(path)
            phash2 = compute_perceptual_hash(path)
            self.assertEqual(phash1, phash2)
            self.assertNotEqual(phash1, "")

    def test_compute_perceptual_hash_missing_file(self) -> None:
        """文件不存在返回空字符串。"""
        self.assertEqual(compute_perceptual_hash("/nonexistent/path.png"), "")

    def test_compute_perceptual_hash_similar_images(self) -> None:
        """缩放后的相似图片 phash 接近。"""
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "a.png"
            p2 = Path(tmp) / "b.png"
            p1.write_bytes(_make_png_with_pattern(128, 128, seed=42))
            # 同一模式缩放到不同尺寸
            img = Image.open(p1)
            img2 = img.resize((256, 256), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img2.save(buf, format="PNG")
            p2.write_bytes(buf.getvalue())

            phash1 = compute_perceptual_hash(p1)
            phash2 = compute_perceptual_hash(p2)
            distance = hamming_distance_hex(phash1, phash2)
            # 缩放后汉明距离应较小
            self.assertLessEqual(distance, 16)

    def test_compute_perceptual_hash_different_images(self) -> None:
        """完全不同的图片 phash 距离较大。"""
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "pattern-a.png"
            p2 = Path(tmp) / "pattern-b.png"
            p1.write_bytes(_make_png_with_pattern(128, 128, seed=1))
            p2.write_bytes(_make_png_with_pattern(128, 128, seed=200))
            phash1 = compute_perceptual_hash(p1)
            phash2 = compute_perceptual_hash(p2)
            # 不同种子产生的图案 phash 应不同
            self.assertNotEqual(phash1, phash2)

    def test_hamming_distance_identical(self) -> None:
        """相同哈希汉明距离为 0。"""
        self.assertEqual(hamming_distance_hex("ffff", "ffff"), 0)

    def test_hamming_distance_known(self) -> None:
        """已知差异的汉明距离。"""
        # 0xff (8 个 1) vs 0x00 (8 个 0) -> 距离 8
        self.assertEqual(hamming_distance_hex("ff", "00"), 8)
        # 0xf (4 个 1) vs 0x0 -> 距离 4
        self.assertEqual(hamming_distance_hex("f", "0"), 4)

    def test_hamming_distance_empty(self) -> None:
        """空哈希或长度不匹配返回大值。"""
        self.assertGreater(hamming_distance_hex("", "ff"), 0)
        self.assertGreater(hamming_distance_hex("ff", "ffff"), 0)

    def test_hamming_distance_invalid_hex(self) -> None:
        """非十六进制字符串返回默认值。"""
        self.assertEqual(hamming_distance_hex("xyz", "abc"), 64)

    def test_extract_prompt_text_from_snapshot(self) -> None:
        """从 snapshot_json 提取提示词。"""
        instance = {
            "snapshot_json": json.dumps({
                "effective_config": {"prompt": "a cute cat"},
                "api_json": {"prompt": "raw prompt text"},
            }),
        }
        text = extract_prompt_text(instance)
        self.assertIn("a cute cat", text)
        self.assertIn("raw prompt text", text)

    def test_extract_prompt_text_from_resolved(self) -> None:
        """从 resolved_json 提取提示词。"""
        instance = {
            "resolved_json": {"positive_prompt": "positive prompt"},
        }
        text = extract_prompt_text(instance)
        self.assertIn("positive prompt", text)

    def test_extract_prompt_text_empty(self) -> None:
        """空实例返回空字符串。"""
        self.assertEqual(extract_prompt_text({}), "")

    def test_extract_prompt_text_invalid_json(self) -> None:
        """JSON 解析失败时返回空字符串。"""
        instance = {"snapshot_json": "{invalid json"}
        self.assertEqual(extract_prompt_text(instance), "")


# ──────────────────────────────────────────────────────────────────
# API 集成测试
# ──────────────────────────────────────────────────────────────────


class _GalleryTestBase(unittest.TestCase):
    """图库集成测试基类。"""

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
        self.images_dir = Path(self._tmp.name) / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _create_file(
        self,
        *,
        file_id: str | None = None,
        content_hash: str | None = None,
        mime_type: str = "image/png",
        size_bytes: int = 1024,
        image_bytes: bytes | None = None,
    ) -> dict:
        """创建文件记录并写入真实图片文件。"""
        file_id = file_id or f"file-{uuid4()}"
        storage_key = f"{file_id}.png"
        if image_bytes is not None:
            (self.images_dir / storage_key).write_bytes(image_bytes)
        else:
            (self.images_dir / storage_key).write_bytes(_make_png(64, 64, (128, 64, 192)))
        file_data = {
            "file_id": file_id,
            "storage_key": storage_key,
            "original_name": f"{file_id}.png",
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "content_hash": content_hash or f"hash-{file_id}",
        }
        return create_file_record(self.manager, file_data)

    def _create_instance(
        self,
        *,
        file_id: str,
        project_id: str | None = None,
        shot_page_id: str | None = None,
        prompt_text: str | None = None,
        width: int = 64,
        height: int = 64,
        seed: int = 42,
    ) -> dict:
        """创建图片实例，可注入提示词到 snapshot_json。"""
        snapshot: dict = {}
        if prompt_text is not None:
            snapshot = {"effective_config": {"prompt": prompt_text}}
        # 简化：直接创建项目和场景页（若未提供）
        if not project_id:
            with self.manager.connection() as conn:
                row = conn.execute("SELECT id FROM projects LIMIT 1").fetchone()
                if row:
                    project_id = row["id"]
                else:
                    project_id = f"proj-{uuid4()}"
                    conn.execute(
                        "INSERT INTO projects(id, name, status, revision, created_at, updated_at) "
                        "VALUES (?, ?, 'draft', 1, ?, ?)",
                        (project_id, "测试项目", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
                    )
                    conn.commit()
        if not shot_page_id:
            with self.manager.connection() as conn:
                row = conn.execute("SELECT id FROM shot_pages LIMIT 1").fetchone()
                if row:
                    shot_page_id = row["id"]
                else:
                    shot_page_id = f"page-{uuid4()}"
                    # shot_pages 需要 small_scene_id 外键，先建一条
                    small_scene_id = f"ss-{uuid4()}"
                    chapter_id = f"ch-{uuid4()}"
                    large_scene_id = f"ls-{uuid4()}"
                    now = "2026-01-01T00:00:00Z"
                    conn.execute(
                        "INSERT INTO chapters(id, project_id, name, sort_order, revision, created_at, updated_at) "
                        "VALUES (?, ?, '章', 1, 1, ?, ?)",
                        (chapter_id, project_id, now, now),
                    )
                    conn.execute(
                        "INSERT INTO large_scenes(id, chapter_id, name, scene_type, sort_order, revision, created_at, updated_at) "
                        "VALUES (?, ?, '大场景', 'content', 1, 1, ?, ?)",
                        (large_scene_id, chapter_id, now, now),
                    )
                    conn.execute(
                        "INSERT INTO small_scenes(id, large_scene_id, name, sort_order, revision, created_at, updated_at) "
                        "VALUES (?, ?, '小场景', 1, 1, ?, ?)",
                        (small_scene_id, large_scene_id, now, now),
                    )
                    conn.execute(
                        "INSERT INTO shot_pages(id, small_scene_id, branch_id, title, sort_order, revision, created_at, updated_at) "
                        "VALUES (?, ?, NULL, '页', 1, 1, ?, ?)",
                        (shot_page_id, small_scene_id, now, now),
                    )
                    conn.commit()
        return create_image_instance(
            self.manager,
            project_id=project_id,
            shot_page_id=shot_page_id,
            task_id=None,
            attempt_id=None,
            file_id=file_id,
            node_id="node-1",
            workflow_version_id=None,
            prompt_id="prompt-1",
            width=width,
            height=height,
            img_format="PNG",
            seed=seed,
            resolved_json=None,
            snapshot_json=snapshot,
        )


class GalleryIndexTests(_GalleryTestBase):
    """图库索引测试。"""

    def test_index_single_file(self) -> None:
        """单文件索引写入 gallery_index 和 gallery_fts。"""
        file_id = "idx-file-1"
        self._create_file(file_id=file_id)
        self._create_instance(file_id=file_id, prompt_text="a beautiful sunset")
        result = index_file_for_gallery(self.manager, file_id)
        self.assertIsNotNone(result)
        self.assertEqual(result["file_id"], file_id)
        self.assertIn("sunset", result["prompt_text"])

    def test_index_idempotent(self) -> None:
        """重复索引不会产生重复行。"""
        file_id = "idx-file-2"
        self._create_file(file_id=file_id)
        self._create_instance(file_id=file_id, prompt_text="cat on sofa")
        index_file_for_gallery(self.manager, file_id)
        index_file_for_gallery(self.manager, file_id)
        with self.manager.connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM gallery_index WHERE file_id = ?",
                (file_id,),
            ).fetchone()["c"]
            fts_count = conn.execute(
                "SELECT COUNT(*) AS c FROM gallery_fts WHERE file_id = ?",
                (file_id,),
            ).fetchone()["c"]
        self.assertEqual(count, 1)
        self.assertEqual(fts_count, 1)

    def test_index_updates_prompt_text(self) -> None:
        """重新索引时 prompt_text 与 FTS 同步更新。"""
        file_id = "idx-file-3"
        self._create_file(file_id=file_id)
        self._create_instance(file_id=file_id, prompt_text="old prompt")
        index_file_for_gallery(self.manager, file_id)

        # 更新实例提示词
        with self.manager.connection() as conn:
            conn.execute(
                "UPDATE image_instances SET snapshot_json = ? WHERE file_id = ?",
                (json.dumps({"effective_config": {"prompt": "new prompt"}}), file_id),
            )
            conn.commit()
        index_file_for_gallery(self.manager, file_id)

        result = search_gallery_by_prompt(self.manager, "new")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["file_id"], file_id)

        old_result = search_gallery_by_prompt(self.manager, "old")
        self.assertEqual(len(old_result["items"]), 0)

    def test_index_missing_file_returns_none(self) -> None:
        """不存在的文件返回 None。"""
        self.assertIsNone(
            index_file_for_gallery(self.manager, "nonexistent-file")
        )

    def test_reindex_incremental(self) -> None:
        """增量索引：跳过已索引的文件，处理新增文件。"""
        # 准备 3 个文件
        for i in range(3):
            fid = f"reidx-{i}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid, prompt_text=f"prompt {i}")

        # 第一次索引：全部新增
        stats1 = reindex_gallery(self.manager)
        self.assertEqual(stats1["indexed"], 3)
        self.assertEqual(stats1["total"], 3)

        # 第二次索引：无变更，全部跳过
        stats2 = reindex_gallery(self.manager)
        self.assertEqual(stats2["indexed"], 0)
        self.assertEqual(stats2["total"], 0)

        # 新增一个文件
        fid_new = "reidx-new"
        self._create_file(file_id=fid_new)
        self._create_instance(file_id=fid_new, prompt_text="new prompt")
        stats3 = reindex_gallery(self.manager)
        self.assertEqual(stats3["indexed"], 1)
        self.assertEqual(stats3["total"], 1)

    def test_reindex_force(self) -> None:
        """强制全量重建。"""
        for i in range(2):
            fid = f"force-{i}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid, prompt_text=f"prompt {i}")
        # 先正常索引
        reindex_gallery(self.manager)
        # 强制重建
        stats = reindex_gallery(self.manager, force=True)
        self.assertEqual(stats["indexed"], 2)
        self.assertEqual(stats["total"], 2)

    def test_update_file_perceptual_hash(self) -> None:
        """计算并写回感知哈希。"""
        file_id = "phash-1"
        image_bytes = _make_png_with_pattern(128, 128, seed=7)
        self._create_file(file_id=file_id, image_bytes=image_bytes)
        # 先索引以创建 gallery_index 行
        index_file_for_gallery(self.manager, file_id)
        phash = update_file_perceptual_hash(self.manager, file_id)
        self.assertEqual(len(phash), 16)
        # 验证 files 表已更新
        with self.manager.connection() as conn:
            row = conn.execute(
                "SELECT perceptual_hash FROM files WHERE id = ?", (file_id,)
            ).fetchone()
        self.assertEqual(row["perceptual_hash"], phash)

    def test_update_phash_missing_file_raises(self) -> None:
        """不存在的文件抛出 ValueError。"""
        with self.assertRaises(ValueError):
            update_file_perceptual_hash(self.manager, "nonexistent")


class GalleryPaginationTests(_GalleryTestBase):
    """游标分页测试。"""

    def test_default_pagination(self) -> None:
        """默认分页返回空列表和 None 游标。"""
        result = list_gallery_images(self.manager)
        self.assertEqual(result["items"], [])
        self.assertIsNone(result["next_cursor"])

    def test_pagination_returns_items(self) -> None:
        """分页返回图库项。"""
        for i in range(5):
            fid = f"page-{i}"
            self._create_file(file_id=fid, size_bytes=1000 + i)
            self._create_instance(file_id=fid)
            index_file_for_gallery(self.manager, fid)

        result = list_gallery_images(self.manager, limit=3)
        self.assertEqual(len(result["items"]), 3)
        self.assertIsNotNone(result["next_cursor"])

        # 翻第二页
        result2 = list_gallery_images(self.manager, limit=3, cursor=result["next_cursor"])
        self.assertEqual(len(result2["items"]), 2)
        self.assertIsNone(result2["next_cursor"])

    def test_pagination_cursor_stable(self) -> None:
        """游标分页不会漏项或重复。"""
        # 创建 7 个文件，时间戳相同（用相同 created_at）
        now = "2026-01-01T00:00:00Z"
        for i in range(7):
            fid = f"stable-{i}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid)
            index_file_for_gallery(self.manager, fid)
            # 强制统一时间戳，验证 file_id 作为次序稳定键
            with self.manager.connection() as conn:
                conn.execute(
                    "UPDATE gallery_index SET source_created_at = ? WHERE file_id = ?",
                    (now, fid),
                )
                conn.commit()

        seen_ids: set[str] = set()
        cursor: str | None = None
        pages = 0
        while True:
            result = list_gallery_images(self.manager, limit=3, cursor=cursor)
            for item in result["items"]:
                self.assertNotIn(item["file_id"], seen_ids, "重复项")
                seen_ids.add(item["file_id"])
            cursor = result["next_cursor"]
            pages += 1
            if not cursor:
                break
            self.assertLess(pages, 10, "翻页过多")

        self.assertEqual(len(seen_ids), 7)

    def test_pagination_limit_clamped(self) -> None:
        """limit 超过上限被钳制。"""
        result = list_gallery_images(self.manager, limit=10000)
        self.assertEqual(result["limit"], MAX_PAGE_SIZE)

    def test_pagination_limit_zero_uses_default(self) -> None:
        """limit<=0 使用默认值。"""
        result = list_gallery_images(self.manager, limit=0)
        self.assertEqual(result["limit"], DEFAULT_PAGE_SIZE)

    def test_filter_by_project_id(self) -> None:
        """按 project_id 筛选。"""
        # 两个项目
        with self.manager.connection() as conn:
            proj_a = "proj-a"
            proj_b = "proj-b"
            now = "2026-01-01T00:00:00Z"
            for pid in (proj_a, proj_b):
                conn.execute(
                    "INSERT INTO projects(id, name, status, revision, created_at, updated_at) "
                    "VALUES (?, ?, 'draft', 1, ?, ?)",
                    (pid, pid, now, now),
                )
            conn.commit()

        for proj_id, suffix in [(proj_a, "a"), (proj_b, "b")]:
            fid = f"proj-file-{suffix}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid, project_id=proj_id)
            index_file_for_gallery(self.manager, fid)

        result = list_gallery_images(self.manager, project_id=proj_a)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["project_id"], proj_a)

    def test_filter_by_mime_type(self) -> None:
        """按 mime_type 筛选。"""
        self._create_file(file_id="png-1", mime_type="image/png")
        self._create_instance(file_id="png-1")
        index_file_for_gallery(self.manager, "png-1")
        self._create_file(file_id="jpg-1", mime_type="image/jpeg")
        self._create_instance(file_id="jpg-1")
        index_file_for_gallery(self.manager, "jpg-1")

        result = list_gallery_images(self.manager, mime_type="image/jpeg")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["mime_type"], "image/jpeg")

    def test_filter_has_phash(self) -> None:
        """按是否已计算 phash 筛选。"""
        # file-with-phash: 计算过 phash
        fid1 = "with-phash"
        self._create_file(file_id=fid1, image_bytes=_make_png(64, 64, (10, 20, 30)))
        self._create_instance(file_id=fid1)
        index_file_for_gallery(self.manager, fid1)
        update_file_perceptual_hash(self.manager, fid1)

        # file-without-phash: 未计算
        fid2 = "without-phash"
        self._create_file(file_id=fid2)
        self._create_instance(file_id=fid2)
        index_file_for_gallery(self.manager, fid2)

        with_phash = list_gallery_images(self.manager, has_phash=True)
        self.assertEqual(len(with_phash["items"]), 1)
        self.assertEqual(with_phash["items"][0]["file_id"], fid1)

        without_phash = list_gallery_images(self.manager, has_phash=False)
        self.assertEqual(len(without_phash["items"]), 1)
        self.assertEqual(without_phash["items"][0]["file_id"], fid2)

    def test_sort_size_desc(self) -> None:
        """按文件大小倒序排序。"""
        sizes = [100, 5000, 200, 9999]
        for i, size in enumerate(sizes):
            fid = f"size-{i}"
            self._create_file(file_id=fid, size_bytes=size)
            self._create_instance(file_id=fid)
            index_file_for_gallery(self.manager, fid)

        result = list_gallery_images(self.manager, sort="size_desc")
        sizes_returned = [item["size_bytes"] for item in result["items"]]
        self.assertEqual(sizes_returned, sorted(sizes, reverse=True))

    def test_sort_dimensions_desc(self) -> None:
        """按像素总数倒序排序。"""
        dims = [(64, 64), (128, 128), (256, 256)]
        for i, (w, h) in enumerate(dims):
            fid = f"dim-{i}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid, width=w, height=h)
            index_file_for_gallery(self.manager, fid)

        result = list_gallery_images(self.manager, sort="dimensions_desc")
        pixels = [item["width"] * item["height"] for item in result["items"]]
        self.assertEqual(pixels, sorted(pixels, reverse=True))


class GalleryFtsTests(_GalleryTestBase):
    """FTS5 全文检索测试。"""

    def test_search_basic(self) -> None:
        """基本搜索。"""
        fid = "search-1"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="a beautiful sunset over the ocean")
        index_file_for_gallery(self.manager, fid)

        result = search_gallery_by_prompt(self.manager, "sunset")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["file_id"], fid)

    def test_search_multi_token(self) -> None:
        """多 token 搜索（AND 语义）。"""
        fid = "search-2"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="a beautiful sunset")
        index_file_for_gallery(self.manager, fid)

        # 两个 token 都存在
        r1 = search_gallery_by_prompt(self.manager, "beautiful sunset")
        self.assertEqual(len(r1["items"]), 1)
        # 其中一个 token 不存在
        r2 = search_gallery_by_prompt(self.manager, "beautiful cat")
        self.assertEqual(len(r2["items"]), 0)

    def test_search_empty_query(self) -> None:
        """空查询返回空列表。"""
        self._create_file(file_id="empty-q")
        self._create_instance(file_id="empty-q", prompt_text="prompt")
        index_file_for_gallery(self.manager, "empty-q")

        result = search_gallery_by_prompt(self.manager, "")
        self.assertEqual(result["items"], [])

    def test_search_no_match(self) -> None:
        """无匹配返回空。"""
        fid = "search-3"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="a beautiful sunset")
        index_file_for_gallery(self.manager, fid)

        result = search_gallery_by_prompt(self.manager, "elephant")
        self.assertEqual(result["items"], [])

    def test_search_pagination(self) -> None:
        """搜索结果分页。"""
        for i in range(5):
            fid = f"pag-{i}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid, prompt_text=f"sunset number {i}")
            index_file_for_gallery(self.manager, fid)

        r1 = search_gallery_by_prompt(self.manager, "sunset", limit=2)
        self.assertEqual(len(r1["items"]), 2)
        self.assertIsNotNone(r1["next_cursor"])

        r2 = search_gallery_by_prompt(
            self.manager, "sunset", limit=2, cursor=r1["next_cursor"]
        )
        self.assertGreaterEqual(len(r2["items"]), 1)

    def test_search_special_chars_sanitized(self) -> None:
        """特殊字符被清理，不引发 FTS5 语法错误。"""
        fid = "special-1"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="a beautiful sunset")
        index_file_for_gallery(self.manager, fid)

        # 包含 FTS5 操作符字符
        result = search_gallery_by_prompt(self.manager, 'sunset" OR 1=1')
        # 不应抛出异常
        self.assertIsInstance(result["items"], list)


class GalleryDuplicateTests(_GalleryTestBase):
    """相同图片搜索测试。"""

    def test_find_duplicates_by_content_hash(self) -> None:
        """按内容哈希找到相同图片。"""
        shared_hash = "shared-content-hash-123"
        for i in range(3):
            fid = f"dup-{i}"
            self._create_file(file_id=fid, content_hash=shared_hash)
            self._create_instance(file_id=fid)
            index_file_for_gallery(self.manager, fid)

        # 排除自身后应找到 2 个
        items = find_duplicate_images(
            self.manager, shared_hash, exclude_file_id="dup-0"
        )
        ids = {item["file_id"] for item in items}
        self.assertEqual(ids, {"dup-1", "dup-2"})

    def test_find_duplicates_empty_hash(self) -> None:
        """空哈希返回空列表。"""
        self.assertEqual(find_duplicate_images(self.manager, ""), [])

    def test_find_duplicates_no_match(self) -> None:
        """无匹配返回空。"""
        self._create_file(file_id="nodup", content_hash="unique-hash")
        self._create_instance(file_id="nodup")
        index_file_for_gallery(self.manager, "nodup")

        items = find_duplicate_images(self.manager, "different-hash")
        self.assertEqual(items, [])


class GallerySimilarTests(_GalleryTestBase):
    """近似图片搜索测试。"""

    def test_find_similar_by_phash(self) -> None:
        """按感知哈希找到近似图片。"""
        # 创建一张基础图片
        base_bytes = _make_png_with_pattern(128, 128, seed=42)
        fid_base = "sim-base"
        self._create_file(file_id=fid_base, image_bytes=base_bytes)
        self._create_instance(file_id=fid_base)
        index_file_for_gallery(self.manager, fid_base)
        update_file_perceptual_hash(self.manager, fid_base)

        # 创建一张相同图片（不同文件 ID，相同内容）
        fid_same = "sim-same"
        self._create_file(file_id=fid_same, image_bytes=base_bytes)
        self._create_instance(file_id=fid_same)
        index_file_for_gallery(self.manager, fid_same)
        update_file_perceptual_hash(self.manager, fid_same)

        items = find_similar_images(self.manager, fid_base, max_hamming_distance=0)
        ids = {item["file_id"] for item in items}
        self.assertIn(fid_same, ids)

    def test_find_similar_no_phash_returns_empty(self) -> None:
        """目标文件没有 phash 时返回空。"""
        fid = "no-phash"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid)
        index_file_for_gallery(self.manager, fid)
        # 不调用 update_file_perceptual_hash

        items = find_similar_images(self.manager, fid)
        self.assertEqual(items, [])

    def test_find_similar_excludes_self(self) -> None:
        """相似搜索不返回自身。"""
        base_bytes = _make_png_with_pattern(128, 128, seed=99)
        fid = "self-sim"
        self._create_file(file_id=fid, image_bytes=base_bytes)
        self._create_instance(file_id=fid)
        index_file_for_gallery(self.manager, fid)
        update_file_perceptual_hash(self.manager, fid)

        items = find_similar_images(self.manager, fid)
        self.assertNotIn(fid, {item["file_id"] for item in items})

    def test_find_similar_respects_distance_threshold(self) -> None:
        """距离阈值过滤。"""
        # 用两种明显不同的图案
        pattern_a_bytes = _make_png_with_pattern(128, 128, seed=1)
        pattern_b_bytes = _make_png_with_pattern(128, 128, seed=200)

        fid_a = "sim-pattern-a"
        self._create_file(file_id=fid_a, image_bytes=pattern_a_bytes)
        self._create_instance(file_id=fid_a)
        index_file_for_gallery(self.manager, fid_a)
        update_file_perceptual_hash(self.manager, fid_a)

        fid_b = "sim-pattern-b"
        self._create_file(file_id=fid_b, image_bytes=pattern_b_bytes)
        self._create_instance(file_id=fid_b)
        index_file_for_gallery(self.manager, fid_b)
        update_file_perceptual_hash(self.manager, fid_b)

        # 计算两个 phash 的实际距离，确保距离 0 不匹配
        with self.manager.connection() as conn:
            row_a = conn.execute(
                "SELECT perceptual_hash FROM gallery_index WHERE file_id = ?",
                (fid_a,),
            ).fetchone()
            row_b = conn.execute(
                "SELECT perceptual_hash FROM gallery_index WHERE file_id = ?",
                (fid_b,),
            ).fetchone()
        actual_distance = hamming_distance_hex(
            row_a["perceptual_hash"], row_b["perceptual_hash"]
        )
        self.assertGreater(actual_distance, 0, "两种图案 phash 应不同")

        # 距离 0 应该不会匹配两个不同图案
        items_strict = find_similar_images(
            self.manager, fid_a, max_hamming_distance=0
        )
        self.assertNotIn(fid_b, {item["file_id"] for item in items_strict})

        # 距离 64（最大）应该匹配
        items_loose = find_similar_images(
            self.manager, fid_a, max_hamming_distance=64
        )
        self.assertIn(fid_b, {item["file_id"] for item in items_loose})


class GalleryDetailTests(_GalleryTestBase):
    """图库详情测试。"""

    def test_get_detail_returns_file_and_instances(self) -> None:
        """详情包含文件、索引、实例和缩略图。"""
        fid = "detail-1"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="detail prompt")
        index_file_for_gallery(self.manager, fid)
        # 直接插入 thumbnails 行（生产环境由后台任务生成）
        now = "2026-01-01T00:00:00Z"
        with self.manager.connection() as conn:
            for size_class in ("256", "640"):
                conn.execute(
                    "INSERT INTO thumbnails(id, file_id, size_class, storage_key, "
                    "width, height, state, error, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'ready', NULL, ?, ?)",
                    (
                        f"thumb-{fid}-{size_class}", fid, size_class,
                        f"{fid}-{size_class}.webp",
                        int(size_class), int(size_class), now, now,
                    ),
                )
            conn.commit()

        from backend.app.gallery import get_gallery_image_detail
        detail = get_gallery_image_detail(self.manager, fid)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["file"]["id"], fid)
        self.assertIsNotNone(detail["gallery_index"])
        self.assertEqual(len(detail["image_instances"]), 1)
        self.assertEqual(len(detail["thumbnails"]), 2)  # 256px + 640px

    def test_get_detail_missing_file_returns_none(self) -> None:
        """不存在的文件返回 None。"""
        from backend.app.gallery import get_gallery_image_detail
        self.assertIsNone(get_gallery_image_detail(self.manager, "nonexistent"))


# ──────────────────────────────────────────────────────────────────
# API 端点测试
# ──────────────────────────────────────────────────────────────────


class GalleryApiTests(_GalleryTestBase):
    """图库 API 端点测试。"""

    def test_list_gallery_api(self) -> None:
        """GET /api/gallery 返回图库列表。"""
        fid = "api-list-1"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="api prompt")
        index_file_for_gallery(self.manager, fid)

        response = self.client.get("/api/gallery")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIn("items", body)
        self.assertIn("next_cursor", body)
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["items"][0]["file_id"], fid)

    def test_list_gallery_with_filters_api(self) -> None:
        """GET /api/gallery 支持筛选参数。"""
        # 项目 A 与项目 B
        with self.manager.connection() as conn:
            now = "2026-01-01T00:00:00Z"
            for pid in ("api-proj-a", "api-proj-b"):
                conn.execute(
                    "INSERT INTO projects(id, name, status, revision, created_at, updated_at) "
                    "VALUES (?, ?, 'draft', 1, ?, ?)",
                    (pid, pid, now, now),
                )
            conn.commit()

        for pid, suffix in [("api-proj-a", "a"), ("api-proj-b", "b")]:
            fid = f"api-filter-{suffix}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid, project_id=pid)
            index_file_for_gallery(self.manager, fid)

        response = self.client.get("/api/gallery?project_id=api-proj-a")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["items"][0]["project_id"], "api-proj-a")

    def test_search_gallery_api(self) -> None:
        """GET /api/gallery/search?q=... 执行 FTS5 搜索。"""
        fid = "api-search-1"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="a happy cat")
        index_file_for_gallery(self.manager, fid)

        response = self.client.get("/api/gallery/search?q=cat")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["items"][0]["file_id"], fid)
        self.assertEqual(body["query"], "cat")

    def test_get_gallery_detail_api(self) -> None:
        """GET /api/gallery/{file_id} 返回详情。"""
        fid = "api-detail-1"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid)
        index_file_for_gallery(self.manager, fid)

        response = self.client.get(f"/api/gallery/{fid}")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["detail"]["file"]["id"], fid)

    def test_get_gallery_detail_404(self) -> None:
        """不存在的文件返回 404。"""
        response = self.client.get("/api/gallery/nonexistent")
        self.assertEqual(response.status_code, 404)

    def test_find_duplicates_api(self) -> None:
        """GET /api/gallery/{file_id}/duplicates 查找相同图片。"""
        shared_hash = "api-shared-hash"
        for i in range(2):
            fid = f"api-dup-{i}"
            self._create_file(file_id=fid, content_hash=shared_hash)
            self._create_instance(file_id=fid)
            index_file_for_gallery(self.manager, fid)

        response = self.client.get("/api/gallery/api-dup-0/duplicates")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["items"][0]["file_id"], "api-dup-1")

    def test_find_similar_api(self) -> None:
        """GET /api/gallery/{file_id}/similar 查找近似图片。"""
        base_bytes = _make_png_with_pattern(128, 128, seed=33)
        fid_base = "api-sim-base"
        self._create_file(file_id=fid_base, image_bytes=base_bytes)
        self._create_instance(file_id=fid_base)
        index_file_for_gallery(self.manager, fid_base)
        update_file_perceptual_hash(self.manager, fid_base)

        fid_same = "api-sim-same"
        self._create_file(file_id=fid_same, image_bytes=base_bytes)
        self._create_instance(file_id=fid_same)
        index_file_for_gallery(self.manager, fid_same)
        update_file_perceptual_hash(self.manager, fid_same)

        response = self.client.get(f"/api/gallery/{fid_base}/similar")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        ids = {item["file_id"] for item in body["items"]}
        self.assertIn(fid_same, ids)

    def test_compute_phash_api(self) -> None:
        """POST /api/files/{file_id}/phash 计算感知哈希。"""
        fid = "api-phash-1"
        self._create_file(file_id=fid, image_bytes=_make_png(64, 64, (50, 100, 150)))
        index_file_for_gallery(self.manager, fid)

        response = self.client.post(f"/api/files/{fid}/phash")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["file_id"], fid)
        self.assertEqual(len(body["perceptual_hash"]), 16)

    def test_index_file_api(self) -> None:
        """POST /api/gallery/index/{file_id} 索引单个文件。"""
        fid = "api-index-1"
        self._create_file(file_id=fid)
        self._create_instance(file_id=fid, prompt_text="api index prompt")
        response = self.client.post(f"/api/gallery/index/{fid}")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["gallery_index"]["file_id"], fid)
        self.assertIn("api index prompt", body["gallery_index"]["prompt_text"])

    def test_reindex_api(self) -> None:
        """POST /api/gallery/reindex 触发重建。"""
        for i in range(2):
            fid = f"api-reidx-{i}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid)
        response = self.client.post("/api/gallery/reindex")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["stats"]["indexed"], 2)

    def test_reindex_force_api(self) -> None:
        """POST /api/gallery/reindex?force=true 全量重建。"""
        for i in range(2):
            fid = f"api-reidx-force-{i}"
            self._create_file(file_id=fid)
            self._create_instance(file_id=fid)
        # 先正常索引一次
        self.client.post("/api/gallery/reindex")
        # 强制重建
        response = self.client.post("/api/gallery/reindex?force=true")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["stats"]["indexed"], 2)


if __name__ == "__main__":
    unittest.main()
