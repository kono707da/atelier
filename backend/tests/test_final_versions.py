"""MOD-09 最终版本与导出测试。"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.output_receiver import create_file_record, create_image_instance


class FinalVersionsApiTests(unittest.TestCase):
    """最终版本 CRUD 和导出接口测试。"""

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
        # 创建基础项目结构
        self.project_id = self.manager.create_project("测试项目")["id"]
        self.chapter_id = self.manager.create_chapter(
            str(self.project_id), "第一章"
        )["id"]
        self.large_scene_id = self.manager.create_large_scene(
            str(self.chapter_id), "大场景"
        )["id"]
        self.small_scene_id = self.manager.create_small_scene(
            str(self.large_scene_id), "小场景"
        )["id"]
        self.shot_page_id = self.manager.create_shot_page(
            str(self.small_scene_id), "场景页"
        )["id"]

    def _create_image_instance(self, adopted: bool = False, seed: int = 42) -> str:
        """创建测试图片实例并返回 ID。"""
        file_id = f"file-{seed}"
        create_file_record(self.manager, {
            "file_id": file_id,
            "storage_key": f"{file_id}.png",
            "original_name": "output.png",
            "mime_type": "image/png",
            "size_bytes": 512,
            "content_hash": f"hash-{seed}",
        })
        instance = create_image_instance(
            self.manager,
            project_id=str(self.project_id),
            shot_page_id=str(self.shot_page_id),
            task_id=None,
            attempt_id=None,
            file_id=file_id,
            node_id=None,
            workflow_version_id=None,
            prompt_id=None,
            width=64,
            height=64,
            img_format="PNG",
            seed=seed,
            resolved_json=None,
            snapshot_json=None,
        )
        if adopted:
            with self.manager.connection("test") as conn:
                conn.execute(
                    "UPDATE image_instances SET is_adopted = 1 WHERE id = ?",
                    (instance["id"],),
                )
                conn.commit()
        return instance["id"]

    # ── 最终版本 CRUD ──────────────────────────────────────────────

    def test_list_empty(self) -> None:
        response = self.client.get(
            f"/api/projects/{self.project_id}/final-versions"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])

    def test_create_final_version(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本一", "description": "第一版"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        fv = response.json()["final_version"]
        self.assertEqual(fv["name"], "版本一")
        self.assertEqual(fv["description"], "第一版")
        self.assertEqual(fv["sort_order"], 1)
        self.assertFalse(fv["is_archived"])

    def test_create_multiple_versions_sort_order(self) -> None:
        for i in range(3):
            self.client.post(
                f"/api/projects/{self.project_id}/final-versions",
                json={"name": f"版本{i+1}"},
            )
        response = self.client.get(
            f"/api/projects/{self.project_id}/final-versions"
        )
        items = response.json()["items"]
        self.assertEqual([i["sort_order"] for i in items], [1, 2, 3])

    def test_update_final_version(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "原名"},
        )
        fv_id = response.json()["final_version"]["id"]
        response = self.client.patch(
            f"/api/final-versions/{fv_id}",
            json={"name": "新名", "is_archived": True},
        )
        self.assertEqual(response.status_code, 200, response.text)
        fv = response.json()["final_version"]
        self.assertEqual(fv["name"], "新名")
        self.assertTrue(fv["is_archived"])

    def test_delete_final_version(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "删除我"},
        )
        fv_id = response.json()["final_version"]["id"]
        response = self.client.delete(f"/api/final-versions/{fv_id}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

    def test_delete_missing_returns_404(self) -> None:
        response = self.client.delete("/api/final-versions/missing-id")
        self.assertEqual(response.status_code, 404)

    def test_empty_name_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": ""},
        )
        self.assertEqual(response.status_code, 422)

    # ── 最终版本条目 ───────────────────────────────────────────────

    def test_add_item_to_final_version(self) -> None:
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        instance_id = self._create_image_instance()
        response = self.client.post(
            f"/api/final-versions/{fv['id']}/items",
            json={"image_instance_id": instance_id},
        )
        self.assertEqual(response.status_code, 201, response.text)
        item = response.json()["item"]
        self.assertEqual(item["image_instance_id"], instance_id)
        self.assertEqual(item["sort_order"], 1)

    def test_same_image_reused_in_multiple_versions(self) -> None:
        """同一图片被多个最终版本复用。"""
        fv1 = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本1"},
        ).json()["final_version"]
        fv2 = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本2"},
        ).json()["final_version"]
        instance_id = self._create_image_instance()
        # 添加到两个版本
        self.client.post(
            f"/api/final-versions/{fv1['id']}/items",
            json={"image_instance_id": instance_id},
        )
        self.client.post(
            f"/api/final-versions/{fv2['id']}/items",
            json={"image_instance_id": instance_id},
        )
        # 两个版本都有该条目
        items1 = self.client.get(
            f"/api/final-versions/{fv1['id']}/items"
        ).json()["items"]
        items2 = self.client.get(
            f"/api/final-versions/{fv2['id']}/items"
        ).json()["items"]
        self.assertEqual(len(items1), 1)
        self.assertEqual(len(items2), 1)
        self.assertEqual(items1[0]["image_instance_id"], instance_id)
        self.assertEqual(items2[0]["image_instance_id"], instance_id)

    def test_reorder_items(self) -> None:
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        ids = []
        for i in range(3):
            iid = self._create_image_instance(seed=i + 1)
            r = self.client.post(
                f"/api/final-versions/{fv['id']}/items",
                json={"image_instance_id": iid},
            )
            ids.append(r.json()["item"]["id"])
        # 反转排序
        reversed_ids = list(reversed(ids))
        response = self.client.put(
            f"/api/final-versions/{fv['id']}/items/reorder",
            json={"item_ids": reversed_ids},
        )
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual([i["id"] for i in items], reversed_ids)
        self.assertEqual([i["sort_order"] for i in items], [1, 2, 3])

    def test_remove_item(self) -> None:
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        iid = self._create_image_instance()
        item = self.client.post(
            f"/api/final-versions/{fv['id']}/items",
            json={"image_instance_id": iid},
        ).json()["item"]
        response = self.client.delete(
            f"/api/final-version-items/{item['id']}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

    def test_generate_default_sequence(self) -> None:
        """按场景页和页内采用顺序生成默认成片序列。"""
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        # 创建 3 个已采用的图片实例
        for i in range(3):
            self._create_image_instance(adopted=True, seed=i + 10)
        response = self.client.post(
            f"/api/final-versions/{fv['id']}/generate-default-sequence"
        )
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual(len(items), 3)
        self.assertEqual([i["sort_order"] for i in items], [1, 2, 3])
        # 每个条目都有 source_shot_page_id
        for item in items:
            self.assertEqual(item["source_shot_page_id"], str(self.shot_page_id))

    def test_generate_default_sequence_ignores_unadopted(self) -> None:
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        self._create_image_instance(adopted=True, seed=1)
        self._create_image_instance(adopted=False, seed=2)
        response = self.client.post(
            f"/api/final-versions/{fv['id']}/generate-default-sequence"
        )
        items = response.json()["items"]
        self.assertEqual(len(items), 1)  # 只有已采用的

    def test_add_item_to_missing_fv_returns_404(self) -> None:
        response = self.client.post(
            "/api/final-versions/missing-id/items",
            json={"image_instance_id": "x"},
        )
        self.assertEqual(response.status_code, 404)

    # ── 导出预设 ───────────────────────────────────────────────────

    def test_create_export_preset(self) -> None:
        response = self.client.post(
            "/api/export-presets",
            json={
                "name": "PNG导出",
                "format": "png",
                "copy_mode": "copy",
                "strip_metadata": True,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        preset = response.json()["preset"]
        self.assertEqual(preset["name"], "PNG导出")
        self.assertEqual(preset["format"], "png")
        self.assertTrue(preset["strip_metadata"])

    def test_list_export_presets(self) -> None:
        self.client.post("/api/export-presets", json={"name": "预设1"})
        self.client.post("/api/export-presets", json={"name": "预设2"})
        response = self.client.get("/api/export-presets")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 2)

    def test_delete_export_preset(self) -> None:
        preset = self.client.post(
            "/api/export-presets", json={"name": "删除我"}
        ).json()["preset"]
        response = self.client.delete(f"/api/export-presets/{preset['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])

    def test_invalid_format_rejected(self) -> None:
        response = self.client.post(
            "/api/export-presets",
            json={"name": "测试", "format": "invalid"},
        )
        self.assertEqual(response.status_code, 422)

    # ── 导出任务 ───────────────────────────────────────────────────

    def test_create_export_job(self) -> None:
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        # 添加一个条目
        iid = self._create_image_instance(adopted=True)
        self.client.post(
            f"/api/final-versions/{fv['id']}/items",
            json={"image_instance_id": iid},
        )
        response = self.client.post(
            f"/api/final-versions/{fv['id']}/export-jobs",
            json={"output_dir": "/tmp/export"},
        )
        self.assertEqual(response.status_code, 201, response.text)
        job = response.json()["job"]
        self.assertEqual(job["status"], "pending")
        self.assertEqual(job["total_items"], 1)
        self.assertEqual(job["completed_items"], 0)

    def test_update_export_job_status(self) -> None:
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        job = self.client.post(
            f"/api/final-versions/{fv['id']}/export-jobs",
            json={"output_dir": "/tmp/export"},
        ).json()["job"]
        response = self.client.patch(
            f"/api/export-jobs/{job['id']}",
            params={"status": "running", "completed_items": 1},
        )
        self.assertEqual(response.status_code, 200, response.text)
        updated = response.json()["job"]
        self.assertEqual(updated["status"], "running")
        self.assertEqual(updated["completed_items"], 1)

    def test_list_export_jobs(self) -> None:
        fv = self.client.post(
            f"/api/projects/{self.project_id}/final-versions",
            json={"name": "版本"},
        ).json()["final_version"]
        self.client.post(
            f"/api/final-versions/{fv['id']}/export-jobs",
            json={"output_dir": "/tmp/export1"},
        )
        self.client.post(
            f"/api/final-versions/{fv['id']}/export-jobs",
            json={"output_dir": "/tmp/export2"},
        )
        response = self.client.get(
            "/api/export-jobs",
            params={"final_version_id": fv["id"]},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["items"]), 2)

    def test_create_export_job_missing_fv_returns_404(self) -> None:
        response = self.client.post(
            "/api/final-versions/missing-id/export-jobs",
            json={"output_dir": "/tmp/export"},
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
