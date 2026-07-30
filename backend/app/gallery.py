"""阶段 MOD-10 百万级全局图库。

本模块实现全局图库的索引、查询、检索与去重能力：

- ``compute_perceptual_hash``: 基于平均哈希（aHash）的感知哈希，返回 16 位十六进制字符串。
  使用 PIL 直接计算，避免引入 ``imagehash`` 依赖；对缩放、轻微裁剪和颜色调整具备鲁棒性。
- ``index_file_for_gallery`` / ``reindex_gallery``: 增量索引。从 ``files`` 表读取文件元数据，
  从 ``image_instances`` 提取来源页/任务/提示词，写入 ``gallery_index`` 与 ``gallery_fts``。
- ``list_gallery_images``: 游标分页。游标格式为 ``<source_created_at>|<file_id>``，
  按 ``source_created_at DESC, file_id DESC`` 稳定排序，避免 OFFSET 在百万行下的性能退化。
- ``search_gallery_by_prompt``: FTS5 全文检索，使用 BM25 排序并支持游标分页。
- ``find_duplicate_images``: 按内容哈希精确查找相同图片。
- ``find_similar_images``: 按感知哈希汉明距离查找近似图片。
- ``get_gallery_image_detail``: 文件详情 + 关联图片实例。

设计原则：
- 列表查询绝不读取原图文件，只读取数据库索引行；
- 索引同步是幂等的，重复执行不会产生重复行；
- FTS5 同步使用“先删除后插入”策略，保证 prompt_text 更新生效；
- 感知哈希存储为十六进制字符串，汉明距离按位异或后 popcount 计算。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


# 游标分页单页最大条数上限，防止前端传入过大值拖慢查询。
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50

# 感知哈希默认比特数（8x8 = 64 位）。
PHASH_HASH_SIZE = 8


# ──────────────────────────────────────────────────────────────────
# 感知哈希计算
# ──────────────────────────────────────────────────────────────────


def compute_perceptual_hash(image_path: Path | str, *, hash_size: int = PHASH_HASH_SIZE) -> str:
    """计算图片的平均哈希（aHash），返回十六进制字符串。

    算法：
    1. 转灰度；
    2. 缩放到 (hash_size*1+1, hash_size*1+1) 即 9x8，取每行相邻像素差；
       —— 这里采用更常见的“缩放到 hash_size x hash_size + 比较均值”方案。
    3. 计算像素均值；
    4. 每个像素大于均值记 1，否则记 0；
    5. 拼成 hash_size*hash_size 位比特串，转十六进制。

    失败时返回空字符串，调用方按“未计算”处理。
    """
    try:
        with Image.open(image_path) as img:
            img = img.convert("L").resize(
                (hash_size, hash_size), Image.Resampling.LANCZOS
            )
            pixels = list(img.getdata())
    except Exception as error:  # noqa: BLE001 - 任何图片读取失败都降级为空哈希
        logger.warning("compute_perceptual_hash failed for %s: %s", image_path, error)
        return ""

    if not pixels:
        return ""

    avg = sum(pixels) / len(pixels)
    bits = 0
    for pixel in pixels:
        bits = (bits << 1) | (1 if pixel > avg else 0)

    # 64 位 -> 16 位十六进制
    hex_length = (hash_size * hash_size + 3) // 4
    return format(bits, f"0{hex_length}x")


def hamming_distance_hex(hash_a: str, hash_b: str) -> int:
    """计算两个十六进制感知哈希的汉明距离。

    长度不一致时返回较大值（视为完全不相似），避免误判。
    """
    if not hash_a or not hash_b or len(hash_a) != len(hash_b):
        return len(hash_a) * 4 if hash_a else 64
    try:
        a = int(hash_a, 16)
        b = int(hash_b, 16)
    except ValueError:
        return 64
    return bin(a ^ b).count("1")


# ──────────────────────────────────────────────────────────────────
# 提示词提取
# ──────────────────────────────────────────────────────────────────


def extract_prompt_text(instance: dict[str, Any]) -> str:
    """从图片实例的快照/解析 JSON 中提取提示词文本。

    优先级：
    1. snapshot_json.effective_config.prompt（编译期最终提示词）；
    2. snapshot_json.api_json.prompt（提交给 ComfyUI 的原始 prompt）；
    3. resolved_json.prompt（解析后的提示词）；
    4. 其余常见字段：positive_prompt、prompt_text、caption。

    返回纯文本字符串，多段以换行拼接。失败返回空字符串。
    """
    pieces: list[str] = []

    def _push(value: Any) -> None:
        if not value:
            return
        if isinstance(value, str):
            text = value.strip()
            if text:
                pieces.append(text)
        elif isinstance(value, list):
            for item in value:
                _push(item)
        elif isinstance(value, dict):
            for key in ("prompt", "positive_prompt", "prompt_text", "caption", "text"):
                if key in value:
                    _push(value[key])

    snapshot_raw = instance.get("snapshot_json")
    if isinstance(snapshot_raw, str):
        try:
            snapshot = json.loads(snapshot_raw)
        except (TypeError, ValueError):
            snapshot = {}
    elif isinstance(snapshot_raw, dict):
        snapshot = snapshot_raw
    else:
        snapshot = {}

    effective_config = snapshot.get("effective_config") if isinstance(snapshot, dict) else None
    if isinstance(effective_config, dict):
        _push(effective_config.get("prompt"))
        _push(effective_config.get("positive_prompt"))

    api_json = snapshot.get("api_json") if isinstance(snapshot, dict) else None
    if isinstance(api_json, dict):
        _push(api_json.get("prompt"))

    resolved_raw = instance.get("resolved_json")
    if isinstance(resolved_raw, str):
        try:
            resolved = json.loads(resolved_raw)
        except (TypeError, ValueError):
            resolved = {}
    elif isinstance(resolved_raw, dict):
        resolved = resolved_raw
    else:
        resolved = {}

    if isinstance(resolved, dict):
        _push(resolved.get("prompt"))
        _push(resolved.get("positive_prompt"))
        _push(resolved.get("prompt_text"))

    return "\n".join(pieces)


# ──────────────────────────────────────────────────────────────────
# 索引同步
# ──────────────────────────────────────────────────────────────────


def _get_storage_path(manager: Any, storage_key: str) -> Path:
    """返回文件在本地图库中的物理路径。"""
    return Path(manager.data_root) / "images" / storage_key


def update_file_perceptual_hash(
    manager: Any,
    file_id: str,
    *,
    environment: str | None = None,
) -> str:
    """读取原图计算感知哈希并写回 files 表与 gallery_index。

    返回计算出的哈希字符串。如果文件不存在或无法解码，返回空字符串
    并清除已有哈希（置为 NULL），以便后续重试。
    """
    with manager.connection(environment) as conn:
        file_row = conn.execute(
            "SELECT id, storage_key FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if not file_row:
            raise ValueError(f"文件不存在: {file_id}")
        storage_key = file_row["storage_key"]

    image_path = _get_storage_path(manager, storage_key)
    phash = ""
    if image_path.exists():
        phash = compute_perceptual_hash(image_path)

    now = datetime.now(timezone.utc).isoformat()
    with manager.connection(environment) as conn:
        conn.execute(
            "UPDATE files SET perceptual_hash = ?, updated_at = ? WHERE id = ?",
            (phash or None, now, file_id),
        )
        conn.execute(
            "UPDATE gallery_index SET perceptual_hash = ?, indexed_at = ? WHERE file_id = ?",
            (phash or None, now, file_id),
        )
    return phash


def index_file_for_gallery(
    manager: Any,
    file_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """为单个 file_id 构建/刷新 gallery_index 与 gallery_fts 行。

    幂等：若 gallery_index 已存在该 file_id，则先删除 FTS 旧行再重新插入。
    缺失文件记录或文件不存在时返回 None。
    """
    with manager.connection(environment) as conn:
        file_row = conn.execute(
            "SELECT * FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if not file_row:
            return None
        file_dict = dict(file_row)

        # 取该文件关联的第一条图片实例（用于来源与提示词）
        instance_row = conn.execute(
            "SELECT * FROM image_instances WHERE file_id = ? ORDER BY created_at ASC LIMIT 1",
            (file_id,),
        ).fetchone()
        instance_dict = dict(instance_row) if instance_row else {}

    prompt_text = extract_prompt_text(instance_dict) if instance_dict else ""
    now = datetime.now(timezone.utc).isoformat()

    project_id = instance_dict.get("project_id") if instance_dict else None
    shot_page_id = instance_dict.get("shot_page_id") if instance_dict else None
    task_id = instance_dict.get("task_id") if instance_dict else None
    attempt_id = instance_dict.get("attempt_id") if instance_dict else None
    width = instance_dict.get("width") or 0
    height = instance_dict.get("height") or 0
    img_format = instance_dict.get("format") or file_dict.get("mime_type", "") or ""
    seed = instance_dict.get("seed")
    source_created_at = instance_dict.get("created_at") or file_dict.get("created_at", now)

    with manager.connection(environment) as conn:
        # 幂等：先清除可能的旧 FTS 行（按 file_id 过滤）
        conn.execute(
            "DELETE FROM gallery_fts WHERE file_id = ?", (file_id,)
        )
        # upsert gallery_index
        conn.execute(
            """
            INSERT INTO gallery_index(
                file_id, project_id, shot_page_id, task_id, attempt_id,
                prompt_text, width, height, format, seed,
                mime_type, size_bytes, content_hash, perceptual_hash,
                state, source_created_at, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_id) DO UPDATE SET
                project_id = excluded.project_id,
                shot_page_id = excluded.shot_page_id,
                task_id = excluded.task_id,
                attempt_id = excluded.attempt_id,
                prompt_text = excluded.prompt_text,
                width = excluded.width,
                height = excluded.height,
                format = excluded.format,
                seed = excluded.seed,
                mime_type = excluded.mime_type,
                size_bytes = excluded.size_bytes,
                content_hash = excluded.content_hash,
                perceptual_hash = excluded.perceptual_hash,
                state = excluded.state,
                source_created_at = excluded.source_created_at,
                indexed_at = excluded.indexed_at
            """,
            (
                file_id, project_id, shot_page_id, task_id, attempt_id,
                prompt_text, width, height, img_format, seed,
                file_dict.get("mime_type", ""), file_dict.get("size_bytes", 0),
                file_dict.get("content_hash"), file_dict.get("perceptual_hash"),
                file_dict.get("state", "active"), source_created_at, now,
            ),
        )
        # 写入 FTS5 行（即使 prompt_text 为空也写入，便于按 file_id 删除）
        conn.execute(
            "INSERT INTO gallery_fts(file_id, prompt_text) VALUES (?, ?)",
            (file_id, prompt_text),
        )
        row = conn.execute(
            "SELECT * FROM gallery_index WHERE file_id = ?", (file_id,)
        ).fetchone()
    return dict(row) if row else None


def reindex_gallery(
    manager: Any,
    *,
    batch_size: int = 500,
    force: bool = False,
    environment: str | None = None,
) -> dict[str, int]:
    """增量重建全局图库索引。

    - ``force=False``（默认）：只索引 gallery_index 中不存在或 files.updated_at
      晚于 gallery_index.indexed_at 的文件。
    - ``force=True``：全量重建，先清空 gallery_index 与 gallery_fts 再重新索引。

    返回 ``{"indexed": N, "skipped": M, "total": T}`` 统计。
    """
    if force:
        with manager.connection(environment) as conn:
            conn.execute("DELETE FROM gallery_index")
            conn.execute("DELETE FROM gallery_fts")

    with manager.connection(environment) as conn:
        if force:
            rows = conn.execute(
                "SELECT id FROM files WHERE state = 'active' ORDER BY created_at ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT f.id AS file_id
                FROM files f
                LEFT JOIN gallery_index g ON g.file_id = f.id
                WHERE f.state = 'active'
                  AND (g.file_id IS NULL OR g.indexed_at < f.updated_at)
                ORDER BY f.created_at ASC
                """
            ).fetchall()

    total = len(rows)
    indexed = 0
    skipped = 0
    for row in rows:
        file_id = row["file_id"] if "file_id" in row.keys() else row["id"]
        result = index_file_for_gallery(manager, file_id, environment=environment)
        if result is None:
            skipped += 1
        else:
            indexed += 1
    return {"indexed": indexed, "skipped": skipped, "total": total}


# ──────────────────────────────────────────────────────────────────
# 游标分页
# ──────────────────────────────────────────────────────────────────


def _encode_cursor(source_created_at: str, file_id: str) -> str:
    """生成不透明游标字符串。"""
    return f"{source_created_at}|{file_id}"


def _decode_cursor(cursor: str) -> tuple[str, str] | None:
    """解析游标，返回 (created_at, file_id)。无效返回 None。"""
    if not cursor:
        return None
    parts = cursor.split("|", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1]


def list_gallery_images(
    manager: Any,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    project_id: str | None = None,
    mime_type: str | None = None,
    has_phash: bool | None = None,
    state: str | None = None,
    sort: str = "created_desc",
    environment: str | None = None,
) -> dict[str, Any]:
    """游标分页查询全局图库。

    返回结构::

        {
            "items": [...],
            "next_cursor": "..." | None,
            "limit": N,
        }

    ``sort`` 支持：
    - ``created_desc``: 创建时间倒序（默认，最新在前）；
    - ``created_asc``: 创建时间正序（最旧在前）；
    - ``size_desc`` / ``size_asc``: 按文件大小排序；
    - ``dimensions_desc``: 按像素总数（width*height）倒序。

    游标仅在 ``created_desc`` / ``created_asc`` 模式下返回。
    其他排序模式返回 ``next_cursor=None``，前端应使用 offset 兜底。
    """
    if limit <= 0:
        limit = DEFAULT_PAGE_SIZE
    if limit > MAX_PAGE_SIZE:
        limit = MAX_PAGE_SIZE

    where_parts: list[str] = []
    params: list[Any] = []
    if project_id:
        where_parts.append("project_id = ?")
        params.append(project_id)
    if mime_type:
        where_parts.append("mime_type = ?")
        params.append(mime_type)
    if has_phash is True:
        where_parts.append("perceptual_hash IS NOT NULL")
    elif has_phash is False:
        where_parts.append("perceptual_hash IS NULL")
    if state:
        where_parts.append("state = ?")
        params.append(state)

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""

    order_clause: str
    next_sort_field: str | None = None
    if sort == "created_asc":
        order_clause = "source_created_at ASC, file_id ASC"
        next_sort_field = "source_created_at"
    elif sort == "size_desc":
        order_clause = "size_bytes DESC, file_id DESC"
    elif sort == "size_asc":
        order_clause = "size_bytes ASC, file_id ASC"
    elif sort == "dimensions_desc":
        order_clause = "(width * height) DESC, file_id DESC"
    else:  # created_desc 默认
        order_clause = "source_created_at DESC, file_id DESC"
        next_sort_field = "source_created_at"

    cursor_clause = ""
    if next_sort_field and cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            cur_created, cur_file = decoded
            if sort == "created_desc":
                cursor_clause = (
                    " AND (source_created_at < ? OR "
                    "(source_created_at = ? AND file_id < ?))"
                )
                params.extend([cur_created, cur_created, cur_file])
            else:  # created_asc
                cursor_clause = (
                    " AND (source_created_at > ? OR "
                    "(source_created_at = ? AND file_id > ?))"
                )
                params.extend([cur_created, cur_created, cur_file])

    effective_where = where_clause
    if cursor_clause:
        if not effective_where:
            effective_where = " WHERE 1=1"
        effective_where += cursor_clause

    query = (
        f"SELECT * FROM gallery_index{effective_where} "
        f"ORDER BY {order_clause} LIMIT ?"
    )
    params.append(limit + 1)  # 多取一条判断是否有下一页

    with manager.connection(environment) as conn:
        rows = conn.execute(query, params).fetchall()
        items = [dict(row) for row in rows]

    next_cursor: str | None = None
    if next_sort_field and len(items) > limit:
        items = items[:limit]
        last = items[-1]
        next_cursor = _encode_cursor(
            last.get("source_created_at", ""), last.get("file_id", "")
        )

    return {"items": items, "next_cursor": next_cursor, "limit": limit}


# ──────────────────────────────────────────────────────────────────
# FTS5 提示词搜索
# ──────────────────────────────────────────────────────────────────


def _sanitize_fts_query(raw: str) -> str:
    """将用户输入转为安全的 FTS5 查询。

    - 拆分为 token；
    - 每个 token 加引号变成前缀匹配（"token"*），避免操作符注入；
    - 多个 token 用空格连接（默认 AND）。
    """
    tokens = [t for t in raw.split() if t]
    if not tokens:
        return ""
    quoted = []
    for token in tokens:
        safe = token.replace('"', "").strip()
        if safe:
            quoted.append(f'"{safe}"*')
    return " ".join(quoted)


def search_gallery_by_prompt(
    manager: Any,
    query: str,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    environment: str | None = None,
) -> dict[str, Any]:
    """使用 FTS5 全文检索提示词。

    使用 BM25 排序。游标格式与 ``list_gallery_images`` 的 ``created_desc`` 一致，
    但游标基于 BM25 排序后的最后一行 (rank, file_id)。
    """
    if limit <= 0:
        limit = DEFAULT_PAGE_SIZE
    if limit > MAX_PAGE_SIZE:
        limit = MAX_PAGE_SIZE

    fts_query = _sanitize_fts_query(query)
    if not fts_query:
        return {"items": [], "next_cursor": None, "limit": limit, "query": query}

    params: list[Any] = [fts_query]
    cursor_clause = ""
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded:
            cur_rank_str, cur_file = decoded
            try:
                cur_rank = float(cur_rank_str)
            except ValueError:
                cur_rank = None
            if cur_rank is not None:
                cursor_clause = (
                    " AND (rank > ? OR (rank = ? AND g.file_id > ?))"
                )
                params.extend([cur_rank, cur_rank, cur_file])

    sql = (
        "SELECT g.*, bm25(gallery_fts) AS rank "
        "FROM gallery_fts JOIN gallery_index g ON g.file_id = gallery_fts.file_id "
        "WHERE gallery_fts MATCH ?"
        + cursor_clause +
        " ORDER BY rank ASC, g.file_id ASC LIMIT ?"
    )
    params.append(limit + 1)

    with manager.connection(environment) as conn:
        rows = conn.execute(sql, params).fetchall()
        items = [dict(row) for row in rows]

    next_cursor: str | None = None
    if len(items) > limit:
        items = items[:limit]
        last = items[-1]
        next_cursor = _encode_cursor(
            f"{last.get('rank', 0):.6f}", last.get("file_id", "")
        )

    return {"items": items, "next_cursor": next_cursor, "limit": limit, "query": query}


# ──────────────────────────────────────────────────────────────────
# 相同 / 近似搜索
# ──────────────────────────────────────────────────────────────────


def find_duplicate_images(
    manager: Any,
    content_hash: str,
    *,
    exclude_file_id: str | None = None,
    limit: int = DEFAULT_PAGE_SIZE,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """按内容哈希查找相同图片（精确去重）。"""
    if not content_hash:
        return []
    params: list[Any] = [content_hash]
    where_extra = ""
    if exclude_file_id:
        where_extra = " AND file_id != ?"
        params.append(exclude_file_id)
    params.append(limit)
    sql = (
        "SELECT * FROM gallery_index WHERE content_hash = ?"
        + where_extra +
        " ORDER BY source_created_at DESC LIMIT ?"
    )
    with manager.connection(environment) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def find_similar_images(
    manager: Any,
    file_id: str,
    *,
    max_hamming_distance: int = 8,
    limit: int = DEFAULT_PAGE_SIZE,
    environment: str | None = None,
) -> list[dict[str, Any]]:
    """按感知哈希汉明距离查找近似图片。

    由于 SQLite 没有内置 popcount，这里先取出所有非空 phash 行在 Python 中比较。
    百万行级别下，phash 非空行通常远小于总量（只有已计算过 phash 的文件），
    且每次比较只需一次 int XOR + popcount，性能可接受。
    生产环境若需要进一步优化，可在 gallery_index 上引入 LSH 或 vp-tree。
    """
    with manager.connection(environment) as conn:
        target_row = conn.execute(
            "SELECT perceptual_hash FROM gallery_index WHERE file_id = ?",
            (file_id,),
        ).fetchone()
        if not target_row or not target_row["perceptual_hash"]:
            return []
        target_phash = target_row["perceptual_hash"]

        rows = conn.execute(
            "SELECT * FROM gallery_index WHERE perceptual_hash IS NOT NULL "
            "AND file_id != ? ORDER BY source_created_at DESC",
            (file_id,),
        ).fetchall()

    candidates: list[tuple[int, dict[str, Any]]] = []
    for row in rows:
        row_dict = dict(row)
        distance = hamming_distance_hex(target_phash, row_dict["perceptual_hash"])
        if distance <= max_hamming_distance:
            candidates.append((distance, row_dict))

    candidates.sort(key=lambda item: (item[0], item[1].get("source_created_at", "")))
    return [item[1] for item in candidates[:limit]]


# ──────────────────────────────────────────────────────────────────
# 详情与关联实例
# ──────────────────────────────────────────────────────────────────


def get_gallery_image_detail(
    manager: Any,
    file_id: str,
    *,
    environment: str | None = None,
) -> dict[str, Any] | None:
    """返回文件详情、索引行和所有关联图片实例。

    用于图库详情页：展示文件元数据、来源项目/页面、提示词和生成参数。
    """
    with manager.connection(environment) as conn:
        file_row = conn.execute(
            "SELECT * FROM files WHERE id = ?", (file_id,)
        ).fetchone()
        if not file_row:
            return None
        index_row = conn.execute(
            "SELECT * FROM gallery_index WHERE file_id = ?", (file_id,)
        ).fetchone()
        instance_rows = conn.execute(
            "SELECT * FROM image_instances WHERE file_id = ? ORDER BY created_at ASC",
            (file_id,),
        ).fetchall()
        thumb_rows = conn.execute(
            "SELECT * FROM thumbnails WHERE file_id = ? ORDER BY size_class ASC",
            (file_id,),
        ).fetchall()

    return {
        "file": dict(file_row),
        "gallery_index": dict(index_row) if index_row else None,
        "image_instances": [dict(row) for row in instance_rows],
        "thumbnails": [dict(row) for row in thumb_rows],
    }
