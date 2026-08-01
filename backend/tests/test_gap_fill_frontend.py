from __future__ import annotations

import unittest

from backend.app.app_factory import PROJECT_ROOT


FRONTEND_ROOT = PROJECT_ROOT / "design" / "ui-preview"
GAP_UI = FRONTEND_ROOT / "gap-fill-ui.js"
RUNTIME = FRONTEND_ROOT / "runtime-api.js"
INDEX = FRONTEND_ROOT / "index.html"


class GapFillFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = GAP_UI.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.index = INDEX.read_text(encoding="utf-8")

    def test_gap_fill_bundle_is_loaded_before_runtime(self) -> None:
        self.assertIn("gap-fill-ui.js", self.index)
        self.assertLess(
            self.index.index("gap-fill-ui.js"),
            self.index.index("runtime-api.js"),
        )

    def test_runtime_dispatches_real_gap_fill_pages(self) -> None:
        self.assertIn("window.AtelierGapFillUI?.render", self.runtime)
        for page in ("review", "assembly", "export", "library", "image-detail"):
            self.assertIn(f'"{page}"', self.runtime)

    def test_mod_08_review_contract_is_present(self) -> None:
        for route in (
            "/api/image-instances",
            "/review",
            "/adopted-order",
            "/api/image-tags",
            "/tracking",
            "/copy-params",
        ):
            self.assertIn(route, self.source)
        for action in ("review-adopt", "review-reject", "review-save", "review-toggle-tag"):
            self.assertIn(action, self.source)

    def test_mod_09_assembly_and_export_contract_is_present(self) -> None:
        for route in (
            "/final-versions",
            "/items/reorder",
            "/rebuild-from-adoptions",
            "/api/export-presets",
            "/api/export-jobs",
        ):
            self.assertIn(route, self.source)
        for action in ("assembly-create-version", "assembly-move", "export-run", "export-cancel"):
            self.assertIn(action, self.source)

    def test_mod_10_gallery_uses_bounded_cursor_batches_and_lazy_images(self) -> None:
        self.assertIn("/api/gallery", self.source)
        self.assertIn('limit: "100"', self.source)
        self.assertIn('loading="lazy"', self.source)
        self.assertIn("gallery-next", self.source)
        self.assertIn("gallery-previous", self.source)
        self.assertIn("AbortController", self.source)
        self.assertIn("/api/thumbnails/rebuild-all?limit=100", self.source)

    def test_mod_11_settings_and_maintenance_contract_is_present(self) -> None:
        for route in (
            "/api/settings/directory",
            "/api/maintenance/system-info",
            "/api/maintenance/integrity-check",
            "/api/maintenance/backup",
            "/api/maintenance/restore",
            "/api/recycle-bin",
        ):
            self.assertIn(route, self.source)

    def test_mod_12_import_and_legacy_index_contract_is_present(self) -> None:
        for route in (
            "/export-package",
            "/api/projects/import-package",
            "/api/materials/export-package",
            "/api/materials/import-package",
            "/api/import/scan-legacy",
            "/api/import/legacy/index",
        ):
            self.assertIn(route, self.source)

    def test_gap_fill_2_frontend_entry_points_are_present(self) -> None:
        for action in (
            "templates-open",
            "character-completeness",
            "character-batch-paste",
            "story-tools-open",
            "workflow-validation-open",
            "blockers-open",
            "batch-rename",
        ):
            self.assertIn(action, self.source)

    def test_story_tree_pages_are_collected_from_pages_arrays(self) -> None:
        self.assertIn('parentKey === "pages"', self.source)
        self.assertIn('value.small_scene_id !== undefined', self.source)

    def test_failed_workflow_validation_refreshes_persisted_history(self) -> None:
        self.assertIn('toast(`预检失败：${error.message}`)', self.source)
        self.assertIn('await refreshWorkflowValidation(workflowId);\n      return;', self.source)

    def test_character_cards_do_not_receive_array_map_index_arguments(self) -> None:
        self.assertIn(
            'characterListState.items.map((character) => cardRenderer(character)).join("")',
            self.runtime,
        )
        self.assertNotIn(
            'characterListState.items.map(cardRenderer).join("")',
            self.runtime,
        )


if __name__ == "__main__":
    unittest.main()
