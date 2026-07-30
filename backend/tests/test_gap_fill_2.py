"""Gap-Fill 2: 剩余后端缺口补全测试。

测试范围：
- MOD-11: 可配置目录 + 回收站
- MOD-05: 工作流验证运行持久化
- MOD-04: 转场结构块 + 自动保存
- MOD-06: 阻塞项持久化 + 批次改名
- MOD-02: 素材模板 + 素材页引用模式
- MOD-03: 规格完整性检查 + 批量粘贴
- MOD-12: 从查询结果创建/关联人物
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.gap_fill_2 import (
    VALID_RECYCLE_ENTITY_TYPES,
    VALID_TRANSITION_TYPES,
    add_to_recycle_bin,
    batch_paste_spec_values,
    check_directory_access,
    check_spec_completeness,
    create_autosave_snapshot,
    create_blocking_issue,
    create_material_template,
    create_transition_block,
    create_validation_run,
    delete_material_template,
    delete_transition_block,
    get_directory_settings,
    get_latest_autosave,
    get_material_template,
    get_transition_block,
    get_validation_run,
    link_query_record_to_character,
    list_autosave_snapshots,
    list_blocking_issues,
    list_material_templates,
    list_recycle_bin,
    list_transition_blocks,
    list_validation_runs,
    purge_recycle_bin,
    restore_from_recycle_bin,
    set_directory_settings,
    set_material_page_reference_mode,
    update_blocking_issue,
    update_material_template,
    update_transition_block,
    update_validation_run,
)


class _GapFill2Base(unittest.TestCase):
    """Gap-Fill 2 测试基类。"""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)
        self.app = create_app(
            data_root=self.tmp_path,
            environment="test",
            locked_environment="test",
        )
        self.client = TestClient(self.app)
        self.manager = self.app.state.database_manager

    def _create_project(self) -> str:
        """创建测试项目，返回 project_id。"""
        project_id = f"proj-{uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT INTO projects(id, name, status, revision, created_at, updated_at) "
                "VALUES (?, ?, 'draft', 1, ?, ?)",
                (project_id, "测试项目", now, now),
            )
            conn.commit()
        return project_id

    def _create_character(self, name: str = "测试角色") -> str:
        """创建测试人物，返回 character_id。"""
        char_id = f"char-{uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT INTO characters(id, name, description, archived_at, sort_order, revision, created_at, updated_at, deleted_at) "
                "VALUES (?, ?, '', NULL, 0, 1, ?, ?, NULL)",
                (char_id, name, now, now),
            )
            conn.commit()
        return char_id

    def _create_character_variant(self, character_id: str, name: str = "变体1") -> str:
        """创建测试人物变体，返回 variant_id。"""
        variant_id = f"var-{uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT INTO character_variants(id, character_id, name, archived_at, sort_order, revision, created_at, updated_at) "
                "VALUES (?, ?, ?, NULL, 0, 1, ?, ?)",
                (variant_id, character_id, name, now, now),
            )
            conn.commit()
        return variant_id

    def _create_spec_value(
        self,
        character_id: str,
        variant_id: str,
        name: str = "规格1",
        prompt_text: str = "",
        lora_name: str = "",
        preview_path: str | None = None,
    ) -> str:
        """创建测试规格值，返回 spec_value_id。

        先在 specs 表创建一条规格定义（spec_type=default, custom_label=name），
        再在 character_spec_values 表创建对应值。

        preview_path 用于控制 preview_original_path 字段；check_spec_completeness
        会将缺失 preview 视为 incomplete，因此 "完整规格" 测试需要传入非空 preview_path。
        """
        # character_id 在当前 schema 下不直接写入 character_spec_values，
        # 但保留参数以兼容调用方；variant 已经挂在 character 下。
        del character_id
        spec_id = f"spec-{uuid4()}"
        csv_id = f"csv-{uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            # 创建 specs 记录
            conn.execute(
                """INSERT INTO specs(
                    id, spec_type, custom_label, description,
                    is_required, default_value, sort_order, created_at, updated_at
                ) VALUES (?, 'default', ?, '', 0, '', 1, ?, ?)
                """,
                (spec_id, name, now, now),
            )
            # 创建 character_spec_values 记录
            conn.execute(
                """INSERT INTO character_spec_values(
                    id, variant_id, spec_id,
                    prompt, lora_name, lora_weight, model_override, notes,
                    preview_original_path, preview_thumbnail_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0.0, '', '', ?, ?, ?, ?)
                """,
                (csv_id, variant_id, spec_id, prompt_text, lora_name,
                 preview_path, preview_path, now, now),
            )
            conn.commit()
        return csv_id

    def _create_batch(self, project_id: str, name: str = "测试批次") -> str:
        """创建测试批次，返回 batch_id。"""
        batch_id = f"batch-{uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT INTO batches(id, project_id, name, status, revision, created_at, updated_at) "
                "VALUES (?, ?, ?, 'pending', 1, ?, ?)",
                (batch_id, project_id, name, now, now),
            )
            conn.commit()
        return batch_id

    def _create_material_page(self, material_id: str | None = None) -> str:
        """创建测试素材页，返回 page_id。

        如果未提供 material_id，会先创建一个 materials 记录以满足外键约束。
        """
        page_id = f"mpage-{uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            if material_id is None:
                material_id = f"mat-{uuid4()}"
                conn.execute(
                    "INSERT INTO materials(id, name, material_type, content, revision, created_at, updated_at) "
                    "VALUES (?, '测试素材', 'composition', '', 1, ?, ?)",
                    (material_id, now, now),
                )
            conn.execute(
                "INSERT INTO material_pages(id, material_id, name, sort_order, revision, created_at, updated_at) "
                "VALUES (?, ?, '页', 1, 1, ?, ?)",
                (page_id, material_id, now, now),
            )
            conn.commit()
        return page_id

    def _create_workflow(self, name: str = "测试工作流") -> str:
        """创建测试工作流，返回 workflow_id。

        workflow_validation_runs.workflow_id 有 FK 约束指向 workflows(id)，
        因此调用 create_validation_run(workflow_id=...) 前需要先创建 workflow。
        """
        wf_id = f"wf-{uuid4()}"
        now = datetime.now(timezone.utc).isoformat()
        with self.manager.connection() as conn:
            conn.execute(
                "INSERT INTO workflows(id, name, description, source_type, is_archived, is_global_default, node_count, revision, created_at, updated_at) "
                "VALUES (?, ?, '', 'manual', 0, 0, 0, 1, ?, ?)",
                (wf_id, name, now, now),
            )
            conn.commit()
        return wf_id


# ──────────────────────────────────────────────────────────────────
# MOD-11: 可配置目录
# ──────────────────────────────────────────────────────────────────


class DirectorySettingsTests(_GapFill2Base):
    """目录配置测试。"""

    def test_get_default_directory_settings(self) -> None:
        """默认目录配置为空，resolved 从 data_root 派生。"""
        result = get_directory_settings(self.manager)
        self.assertEqual(result["data_dir"], "")
        self.assertEqual(result["images_dir"], "")
        self.assertIn("resolved", result)
        self.assertEqual(result["resolved"]["data_dir"], str(self.manager.data_root))

    def test_set_directory_settings(self) -> None:
        """更新目录配置后能正确读取。"""
        custom_dir = str(self.tmp_path / "custom_images")
        result = set_directory_settings(self.manager, images_dir=custom_dir)
        self.assertEqual(result["images_dir"], custom_dir)
        self.assertEqual(result["resolved"]["images_dir"], str(Path(custom_dir).resolve()))

    def test_reset_directory_settings(self) -> None:
        """传入空字符串恢复默认。"""
        set_directory_settings(self.manager, images_dir="/tmp/custom")
        result = set_directory_settings(self.manager, images_dir="")
        self.assertEqual(result["images_dir"], "")

    def test_check_directory_access_writable(self) -> None:
        """可写目录返回 writable=True。"""
        result = check_directory_access(self.tmp_path)
        self.assertTrue(result["writable"])
        self.assertIsNone(result["error"])

    def test_check_directory_access_nonexistent_parent(self) -> None:
        """父目录不存在返回错误。"""
        result = check_directory_access("/nonexistent_root/sub/dir")
        self.assertFalse(result["writable"])
        self.assertIsNotNone(result["error"])

    def test_get_directory_settings_api(self) -> None:
        """API GET /api/settings/directory 返回目录配置。"""
        response = self.client.get("/api/settings/directory")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("directory", data)
        self.assertIn("resolved", data["directory"])

    def test_update_directory_settings_api(self) -> None:
        """API PUT /api/settings/directory 更新目录配置。"""
        response = self.client.put(
            "/api/settings/directory",
            json={"images_dir": str(self.tmp_path / "new_images")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["directory"]["images_dir"], str(self.tmp_path / "new_images"))

    def test_check_directory_api(self) -> None:
        """API POST /api/settings/directory/check 检查目录。"""
        response = self.client.post(
            "/api/settings/directory/check",
            json={"path": str(self.tmp_path)},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["check"]["writable"])


# ──────────────────────────────────────────────────────────────────
# MOD-11: 回收站
# ──────────────────────────────────────────────────────────────────


class RecycleBinTests(_GapFill2Base):
    """回收站测试。"""

    def test_add_and_list_recycle_bin(self) -> None:
        """添加回收站条目后能列出。"""
        entry = add_to_recycle_bin(
            self.manager,
            entity_type="project",
            entity_id="proj-1",
            entity_name="测试项目",
            source_table="projects",
            payload_json={"name": "测试项目"},
        )
        self.assertIn("id", entry)
        result = list_recycle_bin(self.manager)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["entity_id"], "proj-1")

    def test_add_recycle_bin_idempotent(self) -> None:
        """同一 entity_type+entity_id 重复添加只保留一条。"""
        add_to_recycle_bin(
            self.manager, entity_type="project", entity_id="p1",
            source_table="projects",
        )
        add_to_recycle_bin(
            self.manager, entity_type="project", entity_id="p1",
            entity_name="改名后",
            source_table="projects",
        )
        result = list_recycle_bin(self.manager, entity_type="project")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["entity_name"], "改名后")

    def test_restore_from_recycle_bin(self) -> None:
        """恢复条目后回收站中不再包含该条目。"""
        entry = add_to_recycle_bin(
            self.manager, entity_type="material", entity_id="m1",
            source_table="materials", payload_json={"name": "素材"},
        )
        restored = restore_from_recycle_bin(self.manager, entry["id"])
        self.assertIsNotNone(restored)
        self.assertEqual(restored["entity_id"], "m1")
        result = list_recycle_bin(self.manager)
        self.assertEqual(result["total"], 0)

    def test_restore_nonexistent_returns_none(self) -> None:
        """恢复不存在的条目返回 None。"""
        self.assertIsNone(restore_from_recycle_bin(self.manager, "nonexistent"))

    def test_purge_recycle_bin_by_id(self) -> None:
        """按 ID 清除回收站条目。"""
        entry = add_to_recycle_bin(
            self.manager, entity_type="project", entity_id="p1",
            source_table="projects",
        )
        result = purge_recycle_bin(self.manager, entry_id=entry["id"])
        self.assertEqual(result["purged"], 1)
        self.assertEqual(list_recycle_bin(self.manager)["total"], 0)

    def test_purge_recycle_bin_by_type(self) -> None:
        """按类型清除回收站条目。"""
        add_to_recycle_bin(self.manager, entity_type="project", entity_id="p1", source_table="projects")
        add_to_recycle_bin(self.manager, entity_type="material", entity_id="m1", source_table="materials")
        result = purge_recycle_bin(self.manager, entity_type="project")
        self.assertEqual(result["purged"], 1)
        self.assertEqual(list_recycle_bin(self.manager)["total"], 1)

    def test_purge_all(self) -> None:
        """清除全部回收站条目。"""
        add_to_recycle_bin(self.manager, entity_type="project", entity_id="p1", source_table="projects")
        add_to_recycle_bin(self.manager, entity_type="material", entity_id="m1", source_table="materials")
        result = purge_recycle_bin(self.manager)
        self.assertEqual(result["purged"], 2)
        self.assertEqual(list_recycle_bin(self.manager)["total"], 0)

    def test_invalid_entity_type_raises(self) -> None:
        """无效 entity_type 抛出 ValueError。"""
        with self.assertRaises(ValueError):
            add_to_recycle_bin(
                self.manager, entity_type="invalid", entity_id="x",
                source_table="x",
            )

    def test_list_recycle_bin_api(self) -> None:
        """API GET /api/recycle-bin 列出回收站。"""
        add_to_recycle_bin(
            self.manager, entity_type="project", entity_id="p1",
            entity_name="项目", source_table="projects",
        )
        response = self.client.get("/api/recycle-bin")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["recycle_bin"]["total"], 1)

    def test_add_recycle_bin_api(self) -> None:
        """API POST /api/recycle-bin 添加回收站条目。"""
        response = self.client.post(
            "/api/recycle-bin",
            json={
                "entity_type": "material",
                "entity_id": "m1",
                "entity_name": "素材",
                "source_table": "materials",
                "payload": {"key": "value"},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("entry", response.json())

    def test_restore_recycle_bin_api(self) -> None:
        """API POST /api/recycle-bin/{id}/restore 恢复条目。"""
        entry = add_to_recycle_bin(
            self.manager, entity_type="project", entity_id="p1",
            source_table="projects",
        )
        response = self.client.post(f"/api/recycle-bin/{entry['id']}/restore")
        self.assertEqual(response.status_code, 200)

    def test_restore_nonexistent_api_returns_404(self) -> None:
        """API 恢复不存在的条目返回 404。"""
        response = self.client.post("/api/recycle-bin/nonexistent/restore")
        self.assertEqual(response.status_code, 404)

    def test_purge_recycle_bin_api(self) -> None:
        """API POST /api/recycle-bin/purge 清除条目。"""
        add_to_recycle_bin(self.manager, entity_type="project", entity_id="p1", source_table="projects")
        response = self.client.post(
            "/api/recycle-bin/purge",
            json={"entity_type": "project"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["purge"]["purged"], 1)


# ──────────────────────────────────────────────────────────────────
# MOD-05: 工作流验证运行
# ──────────────────────────────────────────────────────────────────


class ValidationRunTests(_GapFill2Base):
    """工作流验证运行测试。"""

    def test_create_validation_run(self) -> None:
        """创建验证运行记录。"""
        result = create_validation_run(self.manager, run_type="precheck")
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["run_type"], "precheck")
        self.assertEqual(result["errors_json"], "[]")

    def test_create_validation_run_invalid_type(self) -> None:
        """无效 run_type 抛出 ValueError。"""
        with self.assertRaises(ValueError):
            create_validation_run(self.manager, run_type="invalid")

    def test_update_validation_run(self) -> None:
        """更新验证运行记录。"""
        run = create_validation_run(self.manager)
        updated = update_validation_run(
            self.manager, run["id"],
            status="failed",
            errors=[{"node": "1", "msg": "error"}],
            node_count=10,
        )
        self.assertEqual(updated["status"], "failed")
        self.assertIn("error", updated["errors_json"])
        self.assertEqual(updated["node_count"], 10)
        self.assertIsNotNone(updated["completed_at"])

    def test_update_validation_run_invalid_status(self) -> None:
        """无效 status 抛出 ValueError。"""
        run = create_validation_run(self.manager)
        with self.assertRaises(ValueError):
            update_validation_run(self.manager, run["id"], status="invalid")

    def test_list_validation_runs(self) -> None:
        """列出验证运行记录。"""
        create_validation_run(self.manager)
        create_validation_run(self.manager, run_type="validate")
        result = list_validation_runs(self.manager)
        self.assertEqual(result["total"], 2)

    def test_list_validation_runs_filter(self) -> None:
        """按 workflow_id 筛选验证运行记录。"""
        wf1 = self._create_workflow("工作流1")
        wf2 = self._create_workflow("工作流2")
        create_validation_run(self.manager, workflow_id=wf1)
        create_validation_run(self.manager, workflow_id=wf2)
        result = list_validation_runs(self.manager, workflow_id=wf1)
        self.assertEqual(result["total"], 1)

    def test_get_validation_run(self) -> None:
        """获取单条验证运行记录。"""
        run = create_validation_run(self.manager)
        result = get_validation_run(self.manager, run["id"])
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], run["id"])

    def test_get_nonexistent_validation_run(self) -> None:
        """获取不存在的记录返回 None。"""
        self.assertIsNone(get_validation_run(self.manager, "nonexistent"))

    def test_create_validation_run_api(self) -> None:
        """API POST /api/workflow-validation-runs 创建记录。"""
        response = self.client.post(
            "/api/workflow-validation-runs",
            json={"run_type": "precheck"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("run", response.json())

    def test_list_validation_runs_api(self) -> None:
        """API GET /api/workflow-validation-runs 列出记录。"""
        create_validation_run(self.manager)
        response = self.client.get("/api/workflow-validation-runs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["runs"]["total"], 1)

    def test_update_validation_run_api(self) -> None:
        """API PATCH 更新验证运行记录。"""
        run = create_validation_run(self.manager)
        response = self.client.patch(
            f"/api/workflow-validation-runs/{run['id']}",
            json={"status": "passed", "node_count": 5},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run"]["status"], "passed")


# ──────────────────────────────────────────────────────────────────
# MOD-04: 转场结构块
# ──────────────────────────────────────────────────────────────────


class TransitionBlockTests(_GapFill2Base):
    """转场结构块测试。"""

    def test_create_transition_block(self) -> None:
        """创建转场结构块。"""
        project_id = self._create_project()
        result = create_transition_block(
            self.manager, project_id=project_id, transition_type="fade",
            duration_frames=10,
        )
        self.assertEqual(result["transition_type"], "fade")
        self.assertEqual(result["duration_frames"], 10)

    def test_create_invalid_transition_type(self) -> None:
        """无效 transition_type 抛出 ValueError。"""
        project_id = self._create_project()
        with self.assertRaises(ValueError):
            create_transition_block(
                self.manager, project_id=project_id, transition_type="invalid",
            )

    def test_list_transition_blocks(self) -> None:
        """列出项目的转场结构块。"""
        project_id = self._create_project()
        create_transition_block(self.manager, project_id=project_id, sort_order=2)
        create_transition_block(self.manager, project_id=project_id, sort_order=1)
        result = list_transition_blocks(self.manager, project_id)
        self.assertEqual(len(result), 2)
        # 按 sort_order 排序
        self.assertEqual(result[0]["sort_order"], 1)

    def test_get_transition_block(self) -> None:
        """获取单个转场结构块。"""
        project_id = self._create_project()
        block = create_transition_block(self.manager, project_id=project_id)
        result = get_transition_block(self.manager, block["id"])
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], block["id"])

    def test_update_transition_block(self) -> None:
        """更新转场结构块。"""
        project_id = self._create_project()
        block = create_transition_block(self.manager, project_id=project_id)
        result = update_transition_block(
            self.manager, block["id"],
            transition_type="dissolve", duration_frames=20,
        )
        self.assertEqual(result["transition_type"], "dissolve")
        self.assertEqual(result["duration_frames"], 20)

    def test_delete_transition_block(self) -> None:
        """删除转场结构块。"""
        project_id = self._create_project()
        block = create_transition_block(self.manager, project_id=project_id)
        self.assertTrue(delete_transition_block(self.manager, block["id"]))
        self.assertIsNone(get_transition_block(self.manager, block["id"]))

    def test_create_transition_block_api(self) -> None:
        """API POST /api/transition-blocks 创建转场块。"""
        project_id = self._create_project()
        response = self.client.post(
            "/api/transition-blocks",
            json={"project_id": project_id, "transition_type": "wipe"},
        )
        self.assertEqual(response.status_code, 200)

    def test_list_transition_blocks_api(self) -> None:
        """API GET /api/projects/{id}/transition-blocks 列出转场块。"""
        project_id = self._create_project()
        create_transition_block(self.manager, project_id=project_id)
        response = self.client.get(f"/api/projects/{project_id}/transition-blocks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["blocks"]), 1)

    def test_delete_transition_block_api(self) -> None:
        """API DELETE /api/transition-blocks/{id} 删除转场块。"""
        project_id = self._create_project()
        block = create_transition_block(self.manager, project_id=project_id)
        response = self.client.delete(f"/api/transition-blocks/{block['id']}")
        self.assertEqual(response.status_code, 200)


# ──────────────────────────────────────────────────────────────────
# MOD-04: 自动保存
# ──────────────────────────────────────────────────────────────────


class AutosaveTests(_GapFill2Base):
    """自动保存测试。"""

    def test_create_autosave_snapshot(self) -> None:
        """创建自动保存快照。"""
        project_id = self._create_project()
        result = create_autosave_snapshot(
            self.manager,
            project_id=project_id,
            entity_type="shot_page",
            entity_id="page-1",
            payload={"title": "测试页"},
        )
        self.assertEqual(result["entity_type"], "shot_page")
        self.assertEqual(result["is_recovered"], 0)

    def test_create_autosave_invalid_entity_type(self) -> None:
        """无效 entity_type 抛出 ValueError。"""
        project_id = self._create_project()
        with self.assertRaises(ValueError):
            create_autosave_snapshot(
                self.manager, project_id=project_id,
                entity_type="invalid", entity_id="x",
            )

    def test_list_autosave_snapshots(self) -> None:
        """列出自动保存快照。"""
        project_id = self._create_project()
        create_autosave_snapshot(self.manager, project_id=project_id, entity_type="shot_page", entity_id="p1")
        create_autosave_snapshot(self.manager, project_id=project_id, entity_type="small_scene", entity_id="s1")
        result = list_autosave_snapshots(self.manager, project_id)
        self.assertEqual(result["total"], 2)

    def test_list_autosave_filter_by_entity(self) -> None:
        """按 entity_type 筛选自动保存快照。"""
        project_id = self._create_project()
        create_autosave_snapshot(self.manager, project_id=project_id, entity_type="shot_page", entity_id="p1")
        create_autosave_snapshot(self.manager, project_id=project_id, entity_type="small_scene", entity_id="s1")
        result = list_autosave_snapshots(self.manager, project_id, entity_type="shot_page")
        self.assertEqual(result["total"], 1)

    def test_get_latest_autosave(self) -> None:
        """获取最新自动保存快照。"""
        project_id = self._create_project()
        create_autosave_snapshot(self.manager, project_id=project_id, entity_type="shot_page", entity_id="p1", payload={"v": 1})
        create_autosave_snapshot(self.manager, project_id=project_id, entity_type="shot_page", entity_id="p1", payload={"v": 2})
        result = get_latest_autosave(self.manager, project_id, "shot_page", "p1")
        self.assertIsNotNone(result)
        self.assertIn('"v": 2', result["payload_json"])

    def test_get_latest_autosave_nonexistent(self) -> None:
        """获取不存在的自动保存快照返回 None。"""
        project_id = self._create_project()
        self.assertIsNone(get_latest_autosave(self.manager, project_id, "shot_page", "nonexistent"))

    def test_create_autosave_api(self) -> None:
        """API POST /api/autosave/snapshots 创建快照。"""
        project_id = self._create_project()
        response = self.client.post(
            "/api/autosave/snapshots",
            json={
                "project_id": project_id,
                "entity_type": "shot_page",
                "entity_id": "p1",
                "payload": {"title": "测试"},
            },
        )
        self.assertEqual(response.status_code, 200)

    def test_list_autosave_api(self) -> None:
        """API GET /api/projects/{id}/autosave 列出快照。"""
        project_id = self._create_project()
        create_autosave_snapshot(self.manager, project_id=project_id, entity_type="shot_page", entity_id="p1")
        response = self.client.get(f"/api/projects/{project_id}/autosave")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["autosave"]["total"], 1)


# ──────────────────────────────────────────────────────────────────
# MOD-06: 阻塞项
# ──────────────────────────────────────────────────────────────────


class BlockingIssueTests(_GapFill2Base):
    """阻塞项测试。"""

    def test_create_blocking_issue(self) -> None:
        """创建阻塞项。"""
        project_id = self._create_project()
        result = create_blocking_issue(
            self.manager, project_id=project_id, message="缺少工作流",
        )
        self.assertEqual(result["status"], "open")
        self.assertEqual(result["message"], "缺少工作流")

    def test_create_blocking_issue_invalid_severity(self) -> None:
        """无效 severity 抛出 ValueError。"""
        project_id = self._create_project()
        with self.assertRaises(ValueError):
            create_blocking_issue(
                self.manager, project_id=project_id,
                severity="invalid", message="msg",
            )

    def test_list_blocking_issues(self) -> None:
        """列出阻塞项。"""
        project_id = self._create_project()
        create_blocking_issue(self.manager, project_id=project_id, message="error1")
        create_blocking_issue(self.manager, project_id=project_id, severity="warning", message="warn1")
        result = list_blocking_issues(self.manager, project_id=project_id)
        self.assertEqual(result["total"], 2)

    def test_list_blocking_issues_filter_severity(self) -> None:
        """按 severity 筛选阻塞项。"""
        project_id = self._create_project()
        create_blocking_issue(self.manager, project_id=project_id, message="e1")
        create_blocking_issue(self.manager, project_id=project_id, severity="warning", message="w1")
        result = list_blocking_issues(self.manager, severity="warning")
        self.assertEqual(result["total"], 1)

    def test_update_blocking_issue(self) -> None:
        """更新阻塞项状态。"""
        project_id = self._create_project()
        issue = create_blocking_issue(self.manager, project_id=project_id, message="msg")
        result = update_blocking_issue(self.manager, issue["id"], status="resolved")
        self.assertEqual(result["status"], "resolved")
        self.assertIsNotNone(result["resolved_at"])

    def test_update_blocking_issue_invalid_status(self) -> None:
        """无效 status 抛出 ValueError。"""
        project_id = self._create_project()
        issue = create_blocking_issue(self.manager, project_id=project_id, message="msg")
        with self.assertRaises(ValueError):
            update_blocking_issue(self.manager, issue["id"], status="invalid")

    def test_create_blocking_issue_api(self) -> None:
        """API POST /api/blocking-issues 创建阻塞项。"""
        project_id = self._create_project()
        response = self.client.post(
            "/api/blocking-issues",
            json={"project_id": project_id, "message": "测试阻塞"},
        )
        self.assertEqual(response.status_code, 200)

    def test_list_blocking_issues_api(self) -> None:
        """API GET /api/blocking-issues 列出阻塞项。"""
        project_id = self._create_project()
        create_blocking_issue(self.manager, project_id=project_id, message="msg")
        response = self.client.get("/api/blocking-issues", params={"project_id": project_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["issues"]["total"], 1)

    def test_update_blocking_issue_api(self) -> None:
        """API PATCH /api/blocking-issues/{id} 更新阻塞项。"""
        project_id = self._create_project()
        issue = create_blocking_issue(self.manager, project_id=project_id, message="msg")
        response = self.client.patch(
            f"/api/blocking-issues/{issue['id']}",
            json={"status": "ignored"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["issue"]["status"], "ignored")


# ──────────────────────────────────────────────────────────────────
# MOD-02: 素材模板
# ──────────────────────────────────────────────────────────────────


class MaterialTemplateTests(_GapFill2Base):
    """素材模板测试。"""

    def test_create_material_template(self) -> None:
        """创建素材模板。"""
        result = create_material_template(
            self.manager, name="镜头模板1", template_type="shot_template",
        )
        self.assertEqual(result["name"], "镜头模板1")
        self.assertEqual(result["template_type"], "shot_template")

    def test_create_invalid_template_type(self) -> None:
        """无效 template_type 抛出 ValueError。"""
        with self.assertRaises(ValueError):
            create_material_template(self.manager, name="x", template_type="invalid")

    def test_list_material_templates(self) -> None:
        """列出素材模板。"""
        create_material_template(self.manager, name="t1", template_type="shot_template")
        create_material_template(self.manager, name="t2", template_type="scene_pack")
        result = list_material_templates(self.manager)
        self.assertEqual(result["total"], 2)

    def test_list_material_templates_filter_type(self) -> None:
        """按 template_type 筛选。"""
        create_material_template(self.manager, name="t1", template_type="shot_template")
        create_material_template(self.manager, name="t2", template_type="scene_pack")
        result = list_material_templates(self.manager, template_type="shot_template")
        self.assertEqual(result["total"], 1)

    def test_get_material_template(self) -> None:
        """获取单个素材模板。"""
        tpl = create_material_template(self.manager, name="t1")
        result = get_material_template(self.manager, tpl["id"])
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], tpl["id"])

    def test_update_material_template(self) -> None:
        """更新素材模板。"""
        tpl = create_material_template(self.manager, name="t1")
        result = update_material_template(self.manager, tpl["id"], name="改名", is_archived=1)
        self.assertEqual(result["name"], "改名")
        self.assertEqual(result["is_archived"], 1)

    def test_delete_material_template(self) -> None:
        """删除素材模板。"""
        tpl = create_material_template(self.manager, name="t1")
        self.assertTrue(delete_material_template(self.manager, tpl["id"]))
        self.assertIsNone(get_material_template(self.manager, tpl["id"]))

    def test_list_excludes_archived_by_default(self) -> None:
        """默认列表不包含已归档模板。"""
        create_material_template(self.manager, name="t1")
        tpl = create_material_template(self.manager, name="t2")
        update_material_template(self.manager, tpl["id"], is_archived=1)
        result = list_material_templates(self.manager)
        self.assertEqual(result["total"], 1)
        result_all = list_material_templates(self.manager, include_archived=True)
        self.assertEqual(result_all["total"], 2)

    def test_create_material_template_api(self) -> None:
        """API POST /api/material-templates 创建模板。"""
        response = self.client.post(
            "/api/material-templates",
            json={"name": "测试模板", "template_type": "transition_pack"},
        )
        self.assertEqual(response.status_code, 200)

    def test_list_material_templates_api(self) -> None:
        """API GET /api/material-templates 列出模板。"""
        create_material_template(self.manager, name="t1")
        response = self.client.get("/api/material-templates")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["templates"]["total"], 1)

    def test_delete_material_template_api(self) -> None:
        """API DELETE /api/material-templates/{id} 删除模板。"""
        tpl = create_material_template(self.manager, name="t1")
        response = self.client.delete(f"/api/material-templates/{tpl['id']}")
        self.assertEqual(response.status_code, 200)


# ──────────────────────────────────────────────────────────────────
# MOD-02: 素材页引用模式
# ──────────────────────────────────────────────────────────────────


class MaterialPageReferenceModeTests(_GapFill2Base):
    """素材页引用模式测试。"""

    def test_set_reference_mode_link(self) -> None:
        """设置素材页引用模式为 link。"""
        page_id = self._create_material_page()
        result = set_material_page_reference_mode(self.manager, page_id, "link")
        self.assertEqual(result["reference_mode"], "link")

    def test_set_reference_mode_independent(self) -> None:
        """设置素材页引用模式为 independent。"""
        page_id = self._create_material_page()
        set_material_page_reference_mode(self.manager, page_id, "link")
        result = set_material_page_reference_mode(self.manager, page_id, "independent")
        self.assertEqual(result["reference_mode"], "independent")

    def test_set_invalid_mode_raises(self) -> None:
        """无效 mode 抛出 ValueError。"""
        page_id = self._create_material_page()
        with self.assertRaises(ValueError):
            set_material_page_reference_mode(self.manager, page_id, "invalid")

    def test_set_reference_mode_api(self) -> None:
        """API PATCH /api/material-pages/{id}/reference-mode 设置引用模式。"""
        page_id = self._create_material_page()
        response = self.client.patch(
            f"/api/material-pages/{page_id}/reference-mode",
            json={"mode": "link"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page"]["reference_mode"], "link")


# ──────────────────────────────────────────────────────────────────
# MOD-03: 规格完整性检查
# ──────────────────────────────────────────────────────────────────


class SpecCompletenessTests(_GapFill2Base):
    """规格完整性检查测试。"""

    def test_check_empty_character(self) -> None:
        """空人物的完整性检查返回零矩阵。"""
        char_id = self._create_character()
        result = check_spec_completeness(self.manager, char_id)
        self.assertEqual(result["summary"]["total_variants"], 0)
        self.assertEqual(result["summary"]["total_specs"], 0)
        self.assertEqual(result["summary"]["total_cells"], 0)

    def test_check_complete_spec(self) -> None:
        """完整规格不报缺失。

        check_spec_completeness 检查 prompt、lora_name 和 preview 三项，
        因此 "完整" 需要三者都非空。
        """
        char_id = self._create_character()
        var_id = self._create_character_variant(char_id)
        self._create_spec_value(
            char_id, var_id, "规格1",
            prompt_text="prompt", lora_name="lora1",
            preview_path="/preview/1.png",
        )
        result = check_spec_completeness(self.manager, char_id)
        self.assertEqual(result["summary"]["filled_cells"], 1)
        self.assertEqual(result["summary"]["incomplete_cells"], 0)

    def test_check_incomplete_spec(self) -> None:
        """缺失 prompt_text 和 lora_name 的规格被标记缺失。"""
        char_id = self._create_character()
        var_id = self._create_character_variant(char_id)
        self._create_spec_value(char_id, var_id, "规格1", prompt_text="", lora_name="")
        result = check_spec_completeness(self.manager, char_id)
        self.assertEqual(result["summary"]["filled_cells"], 1)
        self.assertEqual(result["summary"]["incomplete_cells"], 1)

    def test_check_spec_completeness_api(self) -> None:
        """API GET /api/characters/{id}/spec-completeness 检查完整性。"""
        char_id = self._create_character()
        response = self.client.get(f"/api/characters/{char_id}/spec-completeness")
        self.assertEqual(response.status_code, 200)
        self.assertIn("completeness", response.json())


# ──────────────────────────────────────────────────────────────────
# MOD-03: 批量粘贴
# ──────────────────────────────────────────────────────────────────


class BatchPasteSpecValuesTests(_GapFill2Base):
    """批量粘贴 spec_value 测试。"""

    def test_batch_paste_create(self) -> None:
        """批量创建 spec_value。"""
        char_id = self._create_character()
        var_id = self._create_character_variant(char_id)
        result = batch_paste_spec_values(
            self.manager,
            character_id=char_id,
            variant_id=var_id,
            spec_values=[
                {"spec_type": "default", "custom_label": "规格1", "prompt": "p1", "lora_name": "l1"},
                {"spec_type": "default", "custom_label": "规格2", "prompt": "p2", "lora_name": "l2"},
            ],
        )
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["updated"], 0)

    def test_batch_paste_update_existing(self) -> None:
        """批量更新已有 spec_value。

        _create_spec_value 使用 spec_type='default', custom_label=name 创建 specs 记录，
        因此批量粘贴时使用相同的 spec_type + custom_label 会命中已有记录并更新。
        """
        char_id = self._create_character()
        var_id = self._create_character_variant(char_id)
        self._create_spec_value(char_id, var_id, "规格1", prompt_text="old")
        result = batch_paste_spec_values(
            self.manager,
            character_id=char_id,
            variant_id=var_id,
            spec_values=[
                {"spec_type": "default", "custom_label": "规格1", "prompt": "new"},
            ],
        )
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["updated"], 1)

    def test_batch_paste_mixed(self) -> None:
        """批量混合创建和更新。"""
        char_id = self._create_character()
        var_id = self._create_character_variant(char_id)
        self._create_spec_value(char_id, var_id, "规格1", prompt_text="old")
        result = batch_paste_spec_values(
            self.manager,
            character_id=char_id,
            variant_id=var_id,
            spec_values=[
                {"spec_type": "default", "custom_label": "规格1", "prompt": "new"},
                {"spec_type": "default", "custom_label": "规格2", "prompt": "new2"},
            ],
        )
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["updated"], 1)

    def test_batch_paste_missing_spec_name(self) -> None:
        """缺少 spec_type 的项被跳过并记录错误。"""
        char_id = self._create_character()
        var_id = self._create_character_variant(char_id)
        result = batch_paste_spec_values(
            self.manager,
            character_id=char_id,
            variant_id=var_id,
            spec_values=[
                {"spec_type": "", "custom_label": "x", "prompt": "p"},
                {"custom_label": "y", "prompt": "p2"},
            ],
        )
        self.assertEqual(result["created"], 0)
        self.assertEqual(len(result["errors"]), 2)

    def test_batch_paste_api(self) -> None:
        """API POST /api/character-spec-values/batch-paste 批量粘贴。"""
        char_id = self._create_character()
        var_id = self._create_character_variant(char_id)
        response = self.client.post(
            "/api/character-spec-values/batch-paste",
            json={
                "character_id": char_id,
                "variant_id": var_id,
                "spec_values": [
                    {"spec_type": "default", "custom_label": "规格1", "prompt": "p1"},
                ],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["created"], 1)


# ──────────────────────────────────────────────────────────────────
# MOD-12: 从查询结果创建/关联人物
# ──────────────────────────────────────────────────────────────────


class CharacterLinkTests(_GapFill2Base):
    """角色关联测试。"""

    def test_link_create_new_character(self) -> None:
        """从查询记录创建新人物并关联。"""
        record_id = f"rec-{uuid4()}"
        result = link_query_record_to_character(
            self.manager,
            record_id=record_id,
            character_name="角色A",
            record_name="角色A",
        )
        self.assertTrue(result["linked"])
        self.assertIn("character_id", result)

    def test_link_to_existing_character(self) -> None:
        """关联到已有人物。"""
        record_id = f"rec-{uuid4()}"
        char_id = self._create_character("已有角色")
        result = link_query_record_to_character(
            self.manager,
            record_id=record_id,
            character_id=char_id,
        )
        self.assertEqual(result["character_id"], char_id)

    def test_link_requires_character_id_or_name(self) -> None:
        """缺少 character_id 和 character_name 抛出 ValueError。"""
        record_id = f"rec-{uuid4()}"
        with self.assertRaises(ValueError):
            link_query_record_to_character(self.manager, record_id=record_id)

    def test_get_linked_character(self) -> None:
        """查询已关联的人物。"""
        record_id = f"rec-{uuid4()}"
        link_query_record_to_character(
            self.manager, record_id=record_id, character_name="角色B",
        )
        result = self.manager.get_setting(f"character_link.{record_id}")
        self.assertIsNotNone(result)

    def test_get_linked_character_nonexistent(self) -> None:
        """查询未关联的人物返回 None。"""
        from backend.app.gap_fill_2 import get_linked_character_for_record
        result = get_linked_character_for_record(self.manager, "nonexistent")
        self.assertIsNone(result)

    def test_link_query_record_api(self) -> None:
        """API POST /api/character-database/link 关联角色。"""
        record_id = f"rec-{uuid4()}"
        response = self.client.post(
            "/api/character-database/link",
            json={"record_id": record_id, "character_name": "角色C"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["link"]["linked"])

    def test_get_linked_character_api(self) -> None:
        """API GET /api/character-database/{id}/link 查询关联。"""
        record_id = f"rec-{uuid4()}"
        self.client.post(
            "/api/character-database/link",
            json={"record_id": record_id, "character_name": "角色D"},
        )
        response = self.client.get(f"/api/character-database/{record_id}/link")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.json()["link"])


# ──────────────────────────────────────────────────────────────────
# MOD-06: 批次改名
# ──────────────────────────────────────────────────────────────────


class BatchRenameTests(_GapFill2Base):
    """批次改名测试。"""

    def test_rename_batch_api(self) -> None:
        """API PATCH /api/batches/{id} 重命名批次。"""
        project_id = self._create_project()
        batch_id = self._create_batch(project_id, "原名")
        response = self.client.patch(
            f"/api/batches/{batch_id}",
            json={"name": "新名"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["batch"]["name"], "新名")

    def test_rename_nonexistent_batch_404(self) -> None:
        """API 重命名不存在的批次返回 404。"""
        response = self.client.patch(
            "/api/batches/nonexistent",
            json={"name": "x"},
        )
        self.assertEqual(response.status_code, 404)

    def test_rename_batch_revision_conflict(self) -> None:
        """API revision 冲突返回 409。"""
        project_id = self._create_project()
        batch_id = self._create_batch(project_id, "批次")
        response = self.client.patch(
            f"/api/batches/{batch_id}",
            json={"name": "新名", "revision": 999},
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
