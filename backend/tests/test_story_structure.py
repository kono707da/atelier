from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class _StoryStructureTestBase(unittest.TestCase):
    """Common setUp: creates project → chapter → large_scene → small_scene."""

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
        self.project = self.manager.create_project("剧本结构测试项目")
        self.chapter = self.manager.create_chapter(
            str(self.project["id"]), "第一章"
        )
        self.large_scene = self.manager.create_large_scene(
            str(self.chapter["id"]), "大场景A"
        )
        self.small_scene = self.manager.create_small_scene(
            str(self.large_scene["id"]), "小场景A"
        )


class BranchConditionTests(_StoryStructureTestBase):
    """1. 分支条件字段 CRUD。"""

    def test_create_branch_with_condition_fields(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "选项A",
            condition_type="choice", condition_value="opt_a",
            return_point="merge_point_1",
        )
        self.assertEqual(branch["condition_type"], "choice")
        self.assertEqual(branch["condition_value"], "opt_a")
        self.assertEqual(branch["return_point"], "merge_point_1")

    def test_create_branch_defaults_condition_fields(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "默认分支"
        )
        self.assertEqual(branch["condition_type"], "")
        self.assertEqual(branch["condition_value"], "")
        self.assertIsNone(branch["return_point"])

    def test_update_branch_condition_fields(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支X"
        )
        updated = self.manager.update_branch(
            str(branch["id"]),
            condition_type="auto",
            condition_value="hp<30",
            return_point="checkpoint_2",
        )
        self.assertEqual(updated["condition_type"], "auto")
        self.assertEqual(updated["condition_value"], "hp<30")
        self.assertEqual(updated["return_point"], "checkpoint_2")

    def test_get_branch_includes_condition_fields(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支Y",
            condition_type="manual", condition_value="player_choice",
        )
        fetched = self.manager.get_branch(str(branch["id"]))
        self.assertIsNotNone(fetched)
        self.assertIn("condition_type", fetched)
        self.assertIn("condition_value", fetched)
        self.assertIn("return_point", fetched)
        self.assertEqual(fetched["condition_type"], "manual")

    def test_list_branches_includes_condition_fields(self) -> None:
        self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支1",
            condition_type="choice", condition_value="a",
        )
        items = self.manager.list_branches(
            "small_scene", str(self.small_scene["id"])
        )
        self.assertEqual(len(items), 1)
        self.assertIn("condition_type", items[0])
        self.assertIn("condition_value", items[0])
        self.assertIn("return_point", items[0])
        self.assertEqual(items[0]["condition_type"], "choice")


class BranchOverrideTests(_StoryStructureTestBase):
    """2. 分支覆盖 CRUD + 有效覆盖查询。"""

    def setUp(self) -> None:
        super().setUp()
        self.branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A"
        )
        self.shot_page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页1"
        )

    def test_list_branch_overrides_empty(self) -> None:
        items = self.manager.list_branch_overrides(str(self.branch["id"]))
        self.assertEqual(items, [])

    def test_create_branch_override_parameter(self) -> None:
        override = self.manager.create_branch_override(
            str(self.branch["id"]), "parameter",
            param_key="seed", param_value="42",
        )
        self.assertEqual(override["override_type"], "parameter")
        self.assertEqual(override["param_key"], "seed")
        self.assertEqual(override["param_value"], "42")
        self.assertIsNone(override["target_id"])

    def test_create_branch_override_with_target_id(self) -> None:
        override = self.manager.create_branch_override(
            str(self.branch["id"]), "parameter",
            target_id=str(self.shot_page["id"]),
            param_key="width", param_value="1024",
        )
        self.assertEqual(override["target_id"], str(self.shot_page["id"]))

    def test_create_branch_override_invalid_type(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.create_branch_override(
                str(self.branch["id"]), "invalid_type",
            )

    def test_update_branch_override(self) -> None:
        override = self.manager.create_branch_override(
            str(self.branch["id"]), "parameter",
            param_key="seed", param_value="42",
        )
        updated = self.manager.update_branch_override(
            str(override["id"]), param_value="100",
        )
        self.assertEqual(updated["param_value"], "100")
        self.assertEqual(updated["param_key"], "seed")

    def test_delete_branch_override(self) -> None:
        override = self.manager.create_branch_override(
            str(self.branch["id"]), "parameter",
            param_key="seed", param_value="42",
        )
        result = self.manager.delete_branch_override(str(override["id"]))
        self.assertTrue(result["deleted"])
        self.assertIsNone(self.manager.delete_branch_override(str(override["id"])))

    def test_get_effective_overrides_page_overrides_branch(self) -> None:
        # Branch-wide override
        self.manager.create_branch_override(
            str(self.branch["id"]), "parameter",
            param_key="seed", param_value="42",
        )
        # Page-specific override (higher priority)
        self.manager.create_branch_override(
            str(self.branch["id"]), "parameter",
            target_id=str(self.shot_page["id"]),
            param_key="seed", param_value="999",
        )
        result = self.manager.get_effective_overrides(
            str(self.shot_page["id"]), str(self.branch["id"])
        )
        # Only one effective override for "seed" - page-specific wins
        seeds = [o for o in result["parameter"] if o["param_key"] == "seed"]
        self.assertEqual(len(seeds), 1)
        self.assertEqual(seeds[0]["param_value"], "999")

    def test_get_effective_overrides_returns_branch_wide_when_no_page_specific(self) -> None:
        self.manager.create_branch_override(
            str(self.branch["id"]), "parameter",
            param_key="seed", param_value="42",
        )
        result = self.manager.get_effective_overrides(
            str(self.shot_page["id"]), str(self.branch["id"])
        )
        self.assertEqual(len(result["parameter"]), 1)
        self.assertEqual(result["parameter"][0]["param_value"], "42")


class StorySnapshotTests(_StoryStructureTestBase):
    """3. 快照创建/列表/详情/恢复。"""

    def setUp(self) -> None:
        super().setUp()
        self.shot_page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页1"
        )

    def test_create_snapshot_returns_metadata(self) -> None:
        snapshot = self.manager.create_story_snapshot(
            str(self.project["id"]), label="v1"
        )
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["label"], "v1")
        self.assertIn("id", snapshot)
        self.assertIn("created_at", snapshot)

    def test_create_snapshot_for_missing_project_returns_none(self) -> None:
        result = self.manager.create_story_snapshot("missing-id", label="x")
        self.assertIsNone(result)

    def test_list_snapshots_excludes_snapshot_data(self) -> None:
        self.manager.create_story_snapshot(str(self.project["id"]), label="v1")
        self.manager.create_story_snapshot(str(self.project["id"]), label="v2")
        items = self.manager.list_story_snapshots(str(self.project["id"]))
        self.assertEqual(len(items), 2)
        for item in items:
            self.assertNotIn("snapshot_data", item)

    def test_get_snapshot_includes_parsed_data(self) -> None:
        snapshot = self.manager.create_story_snapshot(
            str(self.project["id"]), label="v1"
        )
        fetched = self.manager.get_story_snapshot(str(snapshot["id"]))
        self.assertIsNotNone(fetched)
        self.assertIn("snapshot_data", fetched)
        data = fetched["snapshot_data"]
        self.assertIn("chapters", data)
        self.assertIn("shot_pages", data)
        self.assertEqual(len(data["chapters"]), 1)
        self.assertEqual(len(data["shot_pages"]), 1)

    def test_restore_snapshot_rebuilds_structure(self) -> None:
        # Take initial snapshot with 1 page
        snapshot = self.manager.create_story_snapshot(
            str(self.project["id"]), label="baseline"
        )
        # Add another page after snapshot
        extra_page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页2"
        )
        # Verify 2 pages now
        tree = self.manager.get_story_tree(str(self.project["id"]))
        ss = tree["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        self.assertEqual(len(ss["pages"]), 2)

        # Restore from snapshot (should have 1 page)
        result = self.manager.restore_story_snapshot(str(snapshot["id"]))
        self.assertIsNotNone(result)
        self.assertIn("backup_snapshot_id", result)

        # Verify restored state has 1 page
        tree = self.manager.get_story_tree(str(self.project["id"]))
        ss = tree["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        self.assertEqual(len(ss["pages"]), 1)
        self.assertEqual(ss["pages"][0]["name"], "分镜页1")

    def test_restore_missing_snapshot_returns_none(self) -> None:
        result = self.manager.restore_story_snapshot("missing-id")
        self.assertIsNone(result)


class OperationHistoryTests(_StoryStructureTestBase):
    """4. 操作记录/列表/撤销。"""

    def test_record_operation_returns_metadata(self) -> None:
        op = self.manager.record_operation(
            str(self.project["id"]), "create", "chapter",
            entity_id=str(self.chapter["id"]),
            before_state=None,
            after_state={"id": str(self.chapter["id"]), "name": "第一章"},
        )
        self.assertEqual(op["operation_type"], "create")
        self.assertEqual(op["entity_type"], "chapter")
        self.assertEqual(op["entity_id"], str(self.chapter["id"]))

    def test_record_operation_invalid_type(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.record_operation(
                str(self.project["id"]), "invalid_op", "chapter",
            )

    def test_list_operations_returns_recent_first(self) -> None:
        self.manager.record_operation(
            str(self.project["id"]), "create", "chapter",
            entity_id=str(self.chapter["id"]),
            after_state={"name": "第一章"},
        )
        self.manager.record_operation(
            str(self.project["id"]), "rename", "chapter",
            entity_id=str(self.chapter["id"]),
            before_state={"name": "第一章"},
            after_state={"name": "第二章"},
        )
        items = self.manager.list_operations(str(self.project["id"]))
        self.assertEqual(len(items), 2)
        # Most recent first
        self.assertEqual(items[0]["operation_type"], "rename")
        self.assertEqual(items[1]["operation_type"], "create")

    def test_undo_operation_restores_before_state(self) -> None:
        # Record rename operation with before_state
        before = {"id": str(self.chapter["id"]),
                  "project_id": str(self.project["id"]),
                  "name": "原章节名", "sort_order": 1}
        after = {"id": str(self.chapter["id"]),
                 "project_id": str(self.project["id"]),
                 "name": "新章节名", "sort_order": 1}
        op = self.manager.record_operation(
            str(self.project["id"]), "rename", "chapter",
            entity_id=str(self.chapter["id"]),
            before_state=before, after_state=after,
        )
        # Apply the rename (simulate)
        self.manager.rename_chapter(str(self.chapter["id"]), "新章节名")
        # Undo
        result = self.manager.undo_operation(str(op["id"]))
        self.assertIsNotNone(result)
        self.assertEqual(result["entity_type"], "chapter")
        # Verify the chapter name was restored
        chapter = self.manager.get_chapter(str(self.chapter["id"]))
        self.assertEqual(chapter["name"], "原章节名")

    def test_undo_missing_operation_returns_none(self) -> None:
        result = self.manager.undo_operation("missing-id")
        self.assertIsNone(result)


class InheritanceTests(_StoryStructureTestBase):
    """5. 继承链查询。"""

    def test_inheritance_chain_includes_all_levels(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A",
            condition_type="choice", condition_value="x",
        )
        page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页1",
            branch_id=str(branch["id"]),
            prompt_text="a beautiful scene",
        )
        result = self.manager.get_shot_page_inheritance(str(page["id"]))
        self.assertIsNotNone(result)
        levels = [link["level"] for link in result["chain"]]
        self.assertEqual(levels, ["project", "chapter", "large_scene",
                                   "small_scene", "branch", "shot_page"])

    def test_inheritance_chain_excludes_branch_when_unbranched(self) -> None:
        page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页1"
        )
        result = self.manager.get_shot_page_inheritance(str(page["id"]))
        self.assertIsNotNone(result)
        levels = [link["level"] for link in result["chain"]]
        self.assertEqual(levels, ["project", "chapter", "large_scene",
                                   "small_scene", "shot_page"])

    def test_inheritance_effective_sources_tracked(self) -> None:
        page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页1",
            prompt_text="test prompt",
        )
        result = self.manager.get_shot_page_inheritance(str(page["id"]))
        self.assertIsNotNone(result)
        # prompt_text should come from shot_page level
        self.assertIn("prompt_text", result["effective"])
        self.assertEqual(result["sources"]["prompt_text"], "shot_page")

    def test_inheritance_missing_page_returns_none(self) -> None:
        result = self.manager.get_shot_page_inheritance("missing-id")
        self.assertIsNone(result)


class PrecheckTests(_StoryStructureTestBase):
    """6. 编译预检查（阻塞项/警告项/空项目/完整项目）。"""

    def test_precheck_empty_project_no_blocking(self) -> None:
        # Empty project (no chapters yet)
        empty_project = self.manager.create_project("空项目")
        result = self.manager.precheck_compilation(
            str(empty_project["id"]), scope="project"
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["blocking"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["summary"]["total_pages"], 0)

    def test_precheck_missing_project_returns_none(self) -> None:
        result = self.manager.precheck_compilation("missing-id", scope="project")
        self.assertIsNone(result)

    def test_precheck_invalid_scope_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.manager.precheck_compilation(
                str(self.project["id"]), scope="invalid_scope"
            )

    def test_precheck_detects_empty_small_scene(self) -> None:
        # small_scene exists but has no pages
        result = self.manager.precheck_compilation(
            str(self.project["id"]), scope="project"
        )
        self.assertIsNotNone(result)
        blocking_types = [b["type"] for b in result["blocking"]]
        self.assertIn("empty_small_scene", blocking_types)

    def test_precheck_complete_project_no_issues(self) -> None:
        # Create material, associate to scene, create page, set mapping
        material = self.manager.create_material(
            name="素材A", material_type="composition", content="构图"
        )
        self.manager.set_small_scene_materials(
            str(self.small_scene["id"]), [str(material["id"])]
        )
        page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分镜页1",
            prompt_text="a scene",
        )
        # Get the material page (auto-created with material)
        material_pages = self.manager.list_material_pages(str(material["id"]))
        self.manager.set_small_scene_page_mapping(
            str(page["id"]), "composition", str(material_pages[0]["id"])
        )
        result = self.manager.precheck_compilation(
            str(self.project["id"]), scope="project"
        )
        self.assertIsNotNone(result)
        # No blocking for empty small_scene (it now has a page)
        blocking_types = [b["type"] for b in result["blocking"]]
        self.assertNotIn("empty_small_scene", blocking_types)
        # Warnings may include missing_character (we didn't bind one)
        warning_types = [w["type"] for w in result["warnings"]]
        self.assertIn("missing_character", warning_types)


class StoryTreeBranchTests(_StoryStructureTestBase):
    """7. story-tree 包含分支信息。"""

    def test_story_tree_includes_branches_array(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支A",
            condition_type="choice", condition_value="opt1",
        )
        tree = self.manager.get_story_tree(str(self.project["id"]))
        self.assertIsNotNone(tree)
        ss = tree["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        self.assertIn("branches", ss)
        self.assertEqual(len(ss["branches"]), 1)
        self.assertEqual(ss["branches"][0]["name"], "分支A")
        self.assertEqual(ss["branches"][0]["condition_type"], "choice")
        self.assertEqual(ss["branches"][0]["condition_value"], "opt1")

    def test_story_tree_branch_includes_pages(self) -> None:
        branch = self.manager.create_branch(
            "small_scene", str(self.small_scene["id"]), "分支B"
        )
        page = self.manager.create_shot_page(
            str(self.small_scene["id"]), "分支页1",
            branch_id=str(branch["id"]),
        )
        tree = self.manager.get_story_tree(str(self.project["id"]))
        ss = tree["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        self.assertEqual(len(ss["branches"]), 1)
        branch_data = ss["branches"][0]
        self.assertEqual(len(branch_data["pages"]), 1)
        self.assertEqual(branch_data["pages"][0]["name"], "分支页1")

    def test_story_tree_no_branches_returns_empty_array(self) -> None:
        tree = self.manager.get_story_tree(str(self.project["id"]))
        ss = tree["chapters"][0]["large_scenes"][0]["small_scenes"][0]
        self.assertIn("branches", ss)
        self.assertEqual(ss["branches"], [])


if __name__ == "__main__":
    unittest.main()
