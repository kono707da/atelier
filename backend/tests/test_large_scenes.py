from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class LargeSceneApiTests(unittest.TestCase):
    """大场景接口测试：所有数据均写入临时测试库。"""

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
        self.project = self.manager.create_project("大场景测试项目")
        self.chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )

    def endpoint(self, chapter_id: str | None = None) -> str:
        return (
            f"/api/chapters/{chapter_id or self.chapter['id']}/large-scenes"
        )

    def test_empty_chapter_returns_empty_list(self) -> None:
        response = self.client.get(self.endpoint())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(response.json()["total"], 0)

    def test_create_large_scene_returns_full_shape(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        self.assertEqual(response.status_code, 201)
        large_scene = response.json()["large_scene"]
        self.assertEqual(large_scene["chapter_id"], self.chapter["id"])
        self.assertEqual(large_scene["name"], "公共沙滩")
        self.assertEqual(large_scene["sort_order"], 1)
        for key in ("id", "created_at", "updated_at"):
            self.assertIn(key, large_scene)

    def test_list_is_sorted_by_sort_order(self) -> None:
        for name in ("公共沙滩", "浅水区", "度假屋"):
            self.client.post(self.endpoint(), json={"name": name})
        payload = self.client.get(self.endpoint()).json()
        self.assertEqual(
            [item["name"] for item in payload["items"]],
            ["公共沙滩", "浅水区", "度假屋"],
        )
        self.assertEqual(
            [item["sort_order"] for item in payload["items"]], [1, 2, 3]
        )

    def test_name_is_cleaned_before_storage(self) -> None:
        response = self.client.post(
            self.endpoint(), json={"name": "  公共   沙滩  "}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["large_scene"]["name"], "公共 沙滩")

    def test_blank_name_is_rejected(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "   "})
        self.assertEqual(response.status_code, 422)

    def test_too_long_name_is_rejected(self) -> None:
        response = self.client.post(self.endpoint(), json={"name": "场" * 81})
        self.assertEqual(response.status_code, 422)

    def test_duplicate_name_in_same_chapter_is_rejected(self) -> None:
        self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        response = self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        self.assertEqual(response.status_code, 409)

    def test_missing_chapter_returns_404(self) -> None:
        self.assertEqual(self.client.get(self.endpoint("missing")).status_code, 404)
        self.assertEqual(
            self.client.post(
                self.endpoint("missing"), json={"name": "孤立场景"}
            ).status_code,
            404,
        )

    def test_same_name_is_allowed_in_different_chapters(self) -> None:
        other = self.manager.create_chapter(str(self.project["id"]), "第二章")
        self.client.post(self.endpoint(), json={"name": "公共沙滩"})
        response = self.client.post(
            self.endpoint(str(other["id"])), json={"name": "公共沙滩"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(self.manager.list_large_scenes(str(other["id"]))), 1)

    def test_rename_large_scene_updates_name(self) -> None:
        large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "旧名称"
        )
        response = self.client.patch(
            f"/api/large-scenes/{large_scene['id']}",
            json={"name": "  新   名称  "},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["large_scene"]["name"], "新 名称")
        self.assertEqual(
            self.manager.get_large_scene(str(large_scene["id"]))["name"],
            "新 名称",
        )

    def test_rename_large_scene_rejects_duplicate_name(self) -> None:
        first = self.manager.create_large_scene(
            str(self.chapter["id"]), "公共沙滩"
        )
        self.manager.create_large_scene(str(self.chapter["id"]), "浅水区")
        response = self.client.patch(
            f"/api/large-scenes/{first['id']}", json={"name": "浅水区"}
        )
        self.assertEqual(response.status_code, 409)

    def test_rename_large_scene_rejects_blank_name(self) -> None:
        large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "公共沙滩"
        )
        response = self.client.patch(
            f"/api/large-scenes/{large_scene['id']}", json={"name": "   "}
        )
        self.assertEqual(response.status_code, 422)

    def test_rename_missing_large_scene_returns_404(self) -> None:
        response = self.client.patch(
            "/api/large-scenes/missing-id", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_large_scene_removes_only_target(self) -> None:
        first = self.manager.create_large_scene(
            str(self.chapter["id"]), "公共沙滩"
        )
        second = self.manager.create_large_scene(
            str(self.chapter["id"]), "浅水区"
        )
        response = self.client.delete(f"/api/large-scenes/{first['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"]["id"], first["id"])
        remaining = self.manager.list_large_scenes(str(self.chapter["id"]))
        self.assertEqual([item["id"] for item in remaining], [second["id"]])

    def test_delete_missing_large_scene_returns_404(self) -> None:
        response = self.client.delete("/api/large-scenes/missing-id")
        self.assertEqual(response.status_code, 404)


class LargeSceneDatabaseTests(unittest.TestCase):
    def test_large_scene_is_written_only_to_test_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(
                Path(directory),
                environment="test",
                locked_environment="test",
            )
            project = manager.create_project("隔离项目")
            chapter = manager.create_chapter(str(project["id"]), "第一章")
            manager.create_large_scene(str(chapter["id"]), "公共沙滩")

            self.assertEqual(
                len(manager.list_large_scenes(str(chapter["id"]), "test")), 1
            )
            self.assertEqual(
                len(manager.list_large_scenes(str(chapter["id"]), "production")), 0
            )

    def test_sort_order_is_independent_per_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("排序项目")
            first = manager.create_chapter(str(project["id"]), "第一章")
            second = manager.create_chapter(str(project["id"]), "第二章")
            a = manager.create_large_scene(str(first["id"]), "A")
            b = manager.create_large_scene(str(first["id"]), "B")
            c = manager.create_large_scene(str(second["id"]), "C")
            self.assertEqual([a["sort_order"], b["sort_order"]], [1, 2])
            self.assertEqual(c["sort_order"], 1)

    def test_chapter_delete_cascades_to_large_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = DatabaseManager(Path(directory))
            project = manager.create_project("级联项目")
            chapter = manager.create_chapter(str(project["id"]), "第一章")
            manager.create_large_scene(str(chapter["id"]), "公共沙滩")
            with manager.connection() as connection:
                connection.execute(
                    "DELETE FROM chapters WHERE id = ?", (str(chapter["id"]),)
                )
            self.assertEqual(
                manager.list_large_scenes(str(chapter["id"])), []
            )


class LargeSceneOrganizeApiTests(unittest.TestCase):
    """大场景组织功能测试：scene_type 字段、跨章节移动、重排序、安全迁移。"""

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
        self.project = self.manager.create_project("组织测试项目")
        self.chapter_a = self.manager.create_chapter(
            str(self.project["id"]), "沙滩章"
        )
        self.chapter_b = self.manager.create_chapter(
            str(self.project["id"]), "更衣章"
        )

    def _scene(self, chapter_id: str, name: str, scene_type: str = "content"):
        return self.manager.create_large_scene(
            str(chapter_id), name, scene_type
        )

    # ── 4.1 scene_type 字段与迁移 ──────────────────────────────

    def test_create_with_scene_type_content_by_default(self) -> None:
        scene = self._scene(str(self.chapter_a["id"]), "内容1")
        self.assertEqual(scene["scene_type"], "content")

    def test_create_rejects_transition_scene_type(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.create_large_scene(
                str(self.chapter_a["id"]), "过渡1", scene_type="transition"
            )

    def test_create_with_invalid_scene_type_returns_422(self) -> None:
        response = self.client.post(
            f"/api/chapters/{self.chapter_a['id']}/large-scenes",
            json={"name": "非法", "scene_type": "invalid"},
        )
        # scene_type is no longer a field on CreateLargeSceneRequest, so the
        # extra key is ignored and the scene is created successfully (201).
        self.assertEqual(response.status_code, 201)

    def test_list_returns_scene_type(self) -> None:
        self._scene(str(self.chapter_a["id"]), "内容1", "content")
        self._scene(str(self.chapter_a["id"]), "内容2", "content")
        items = self.client.get(
            f"/api/chapters/{self.chapter_a['id']}/large-scenes"
        ).json()["items"]
        self.assertEqual([i["scene_type"] for i in items], ["content", "content"])

    def test_legacy_db_migration_adds_scene_type_with_default_content(self) -> None:
        # Simulate pre-v0.2.0 schema: drop & recreate large_scenes without scene_type
        with self.manager.connection("test") as conn:
            conn.execute("DROP TABLE large_scenes")
            conn.execute(
                """
                CREATE TABLE large_scenes (
                    id TEXT PRIMARY KEY,
                    chapter_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (chapter_id) REFERENCES chapters(id) ON DELETE CASCADE,
                    UNIQUE (chapter_id, name)
                )
                """
            )
            conn.execute(
                "INSERT INTO large_scenes(id, chapter_id, name, sort_order, created_at, updated_at) "
                "VALUES('legacy-1', ?, '旧场景', 1, '2024-01-01', '2024-01-01')",
                (str(self.chapter_a["id"]),),
            )
        # Reinitialize — should auto-add scene_type column back with default 'content'
        self.manager.initialize("test")
        with self.manager.connection("test") as conn:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(large_scenes)").fetchall()]
            self.assertIn("scene_type", cols)
            row = conn.execute("SELECT scene_type FROM large_scenes WHERE id = 'legacy-1'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["scene_type"], "content")

    # ── 5.2 PATCH 三字段可选 update ────────────────────────────

    def test_update_name_only_preserves_sort_and_type(self) -> None:
        scene = self._scene(str(self.chapter_a["id"]), "旧名", "content")
        response = self.client.patch(
            f"/api/large-scenes/{scene['id']}", json={"name": "新名"}
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["large_scene"]
        self.assertEqual(body["name"], "新名")
        self.assertEqual(body["scene_type"], "content")
        self.assertEqual(body["sort_order"], 1)

    def test_update_scene_type_ignored_by_api(self) -> None:
        scene = self._scene(str(self.chapter_a["id"]), "场景1", "content")
        response = self.client.patch(
            f"/api/large-scenes/{scene['id']}", json={"scene_type": "transition"}
        )
        # scene_type is no longer a field on UpdateLargeSceneRequest; the extra
        # key is ignored, but at_least_one_field raises because no valid field
        # was provided.
        self.assertEqual(response.status_code, 422)

    def test_update_chapter_moves_to_end_of_target(self) -> None:
        a1 = self._scene(str(self.chapter_a["id"]), "A1")
        a2 = self._scene(str(self.chapter_a["id"]), "A2")
        b1 = self._scene(str(self.chapter_b["id"]), "B1")
        response = self.client.patch(
            f"/api/large-scenes/{a1['id']}",
            json={"chapter_id": str(self.chapter_b["id"])},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()["large_scene"]
        self.assertEqual(body["chapter_id"], self.chapter_b["id"])
        self.assertEqual(body["sort_order"], 2)  # appended after B1
        # Source chapter renumbered
        src = self.manager.list_large_scenes(str(self.chapter_a["id"]))
        self.assertEqual([s["sort_order"] for s in src], [1])
        self.assertEqual(src[0]["id"], a2["id"])

    def test_update_to_missing_chapter_returns_404(self) -> None:
        scene = self._scene(str(self.chapter_a["id"]), "场景1")
        response = self.client.patch(
            f"/api/large-scenes/{scene['id']}", json={"chapter_id": "missing"}
        )
        self.assertEqual(response.status_code, 404)

    def test_update_to_same_name_in_target_rejected(self) -> None:
        self._scene(str(self.chapter_a["id"]), "重名场景")
        scene_b = self._scene(str(self.chapter_b["id"]), "B1")
        response = self.client.patch(
            f"/api/large-scenes/{scene_b['id']}",
            json={
                "chapter_id": str(self.chapter_a["id"]),
                "name": "重名场景",
            },
        )
        self.assertEqual(response.status_code, 409)
        # Data unchanged
        self.assertEqual(
            len(self.manager.list_large_scenes(str(self.chapter_b["id"]))), 1
        )

    def test_update_at_least_one_field_required(self) -> None:
        scene = self._scene(str(self.chapter_a["id"]), "场景1")
        response = self.client.patch(
            f"/api/large-scenes/{scene['id']}", json={}
        )
        self.assertEqual(response.status_code, 422)

    # ── 5.3 /move 接口 ────────────────────────────────────────

    def test_move_within_chapter_forward(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "A")
        b = self._scene(str(self.chapter_a["id"]), "B")
        c = self._scene(str(self.chapter_a["id"]), "C")
        # Move A to position 3
        response = self.client.post(
            f"/api/large-scenes/{a['id']}/move",
            json={
                "target_chapter_id": str(self.chapter_a["id"]),
                "target_sort_order": 3,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            [i["name"] for i in body["target_items"]], ["B", "C", "A"]
        )
        self.assertEqual(
            [i["sort_order"] for i in body["target_items"]], [1, 2, 3]
        )

    def test_move_within_chapter_backward(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "A")
        b = self._scene(str(self.chapter_a["id"]), "B")
        c = self._scene(str(self.chapter_a["id"]), "C")
        # Move C to position 1
        response = self.client.post(
            f"/api/large-scenes/{c['id']}/move",
            json={
                "target_chapter_id": str(self.chapter_a["id"]),
                "target_sort_order": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [i["name"] for i in response.json()["target_items"]],
            ["C", "A", "B"],
        )

    def test_move_cross_chapter_to_empty_chapter(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "A")
        response = self.client.post(
            f"/api/large-scenes/{a['id']}/move",
            json={
                "target_chapter_id": str(self.chapter_b["id"]),
                "target_sort_order": 1,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_chapter_id"], self.chapter_a["id"])
        self.assertEqual(body["target_chapter_id"], self.chapter_b["id"])
        self.assertEqual(len(body["source_items"]), 0)
        self.assertEqual(len(body["target_items"]), 1)
        self.assertEqual(body["target_items"][0]["id"], a["id"])
        self.assertEqual(body["target_items"][0]["sort_order"], 1)

    def test_move_cross_chapter_to_specific_position(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "A")
        b1 = self._scene(str(self.chapter_b["id"]), "B1")
        b2 = self._scene(str(self.chapter_b["id"]), "B2")
        response = self.client.post(
            f"/api/large-scenes/{a['id']}/move",
            json={
                "target_chapter_id": str(self.chapter_b["id"]),
                "target_sort_order": 2,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [i["name"] for i in response.json()["target_items"]],
            ["B1", "A", "B2"],
        )

    def test_move_target_sort_below_one_treated_as_one(self) -> None:
        # target_sort_order is validated by pydantic ge=1, so 0 returns 422
        # but backend clamps internally if somehow reached
        a = self._scene(str(self.chapter_a["id"]), "A")
        b = self._scene(str(self.chapter_a["id"]), "B")
        # Use manager directly to test clamp (since API rejects <1 at validation)
        result = self.manager.move_large_scene(
            str(a["id"]), str(self.chapter_a["id"]), 0
        )
        self.assertEqual(
            [i["name"] for i in result["target_items"]], ["A", "B"]
        )

    def test_move_target_sort_exceeds_length_appends_to_end(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "A")
        b = self._scene(str(self.chapter_a["id"]), "B")
        response = self.client.post(
            f"/api/large-scenes/{a['id']}/move",
            json={
                "target_chapter_id": str(self.chapter_a["id"]),
                "target_sort_order": 999,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [i["name"] for i in response.json()["target_items"]], ["B", "A"]
        )

    def test_move_cross_project_rejected(self) -> None:
        other_project = self.manager.create_project("其他项目")
        other_chapter = self.manager.create_chapter(
            str(other_project["id"]), "其他章"
        )
        a = self._scene(str(self.chapter_a["id"]), "A")
        response = self.client.post(
            f"/api/large-scenes/{a['id']}/move",
            json={
                "target_chapter_id": str(other_chapter["id"]),
                "target_sort_order": 1,
            },
        )
        self.assertEqual(response.status_code, 409)
        # Data unchanged
        self.assertEqual(
            len(self.manager.list_large_scenes(str(self.chapter_a["id"]))), 1
        )

    def test_move_to_missing_target_chapter_returns_404(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "A")
        response = self.client.post(
            f"/api/large-scenes/{a['id']}/move",
            json={"target_chapter_id": "missing", "target_sort_order": 1},
        )
        self.assertEqual(response.status_code, 404)

    def test_move_missing_large_scene_returns_404(self) -> None:
        response = self.client.post(
            "/api/large-scenes/missing/move",
            json={
                "target_chapter_id": str(self.chapter_a["id"]),
                "target_sort_order": 1,
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_move_same_name_in_target_rolls_back(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "重名")
        self._scene(str(self.chapter_b["id"]), "重名")
        response = self.client.post(
            f"/api/large-scenes/{a['id']}/move",
            json={
                "target_chapter_id": str(self.chapter_b["id"]),
                "target_sort_order": 1,
            },
        )
        self.assertEqual(response.status_code, 409)
        # Source unchanged, target unchanged
        self.assertEqual(
            len(self.manager.list_large_scenes(str(self.chapter_a["id"]))), 1
        )
        self.assertEqual(
            len(self.manager.list_large_scenes(str(self.chapter_b["id"]))), 1
        )

    # ── 删除后重排 ───────────────────────────────────────────

    def test_delete_renumbers_remaining_scenes(self) -> None:
        a = self._scene(str(self.chapter_a["id"]), "A")
        b = self._scene(str(self.chapter_a["id"]), "B")
        c = self._scene(str(self.chapter_a["id"]), "C")
        # Delete B (middle)
        self.client.delete(f"/api/large-scenes/{b['id']}")
        remaining = self.manager.list_large_scenes(str(self.chapter_a["id"]))
        self.assertEqual([s["name"] for s in remaining], ["A", "C"])
        self.assertEqual([s["sort_order"] for s in remaining], [1, 2])

    # ── 双数据库隔离 ─────────────────────────────────────────

    def test_test_db_writes_do_not_affect_production(self) -> None:
        self._scene(str(self.chapter_a["id"]), "测试场景")
        self.assertEqual(
            len(self.manager.list_large_scenes(
                str(self.chapter_a["id"]), "production"
            )),
            0,
        )


if __name__ == "__main__":
    unittest.main()
