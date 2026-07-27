from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.app_factory import create_app
from backend.app.database import DatabaseManager


class CharacterApiTests(unittest.TestCase):
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
        self.project = self.manager.create_project("人物测试项目")

    def test_empty_project_returns_empty_character_list(self) -> None:
        response = self.client.get(f"/api/projects/{self.project['id']}/characters")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"], [])
        self.assertEqual(body["total"], 0)

    def test_list_characters_includes_stats_aggregate(self) -> None:
        self.manager.create_project_spec(str(self.project["id"]), "full_body")
        self.manager.create_project_spec(str(self.project["id"]), "half_body")
        char = self.manager.create_character(str(self.project["id"]), "角色A")
        self.manager.create_character_variant(str(char["id"]), "裙装")
        response = self.client.get(
            f"/api/projects/{self.project['id']}/characters"
        )
        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        stats = item["stats"]
        self.assertEqual(stats["variant_count"], 2)
        self.assertEqual(stats["spec_total"], 4)
        self.assertEqual(stats["spec_filled"], 0)

    def test_create_character_returns_full_shape(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/characters",
            json={"name": "角色A"},
        )
        self.assertEqual(response.status_code, 201)
        char = response.json()["character"]
        self.assertEqual(char["project_id"], self.project["id"])
        self.assertEqual(char["name"], "角色A")
        self.assertEqual(char["sort_order"], 1)
        for key in ("id", "created_at", "updated_at"):
            self.assertIn(key, char)

    def test_create_character_auto_creates_default_variant(self) -> None:
        char = self.manager.create_character(str(self.project["id"]), "角色A")
        variants = self.manager.list_character_variants(str(char["id"]))
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["name"], "默认")
        self.assertEqual(variants[0]["is_default"], 1)

    def test_create_character_with_existing_specs_creates_spec_values(self) -> None:
        self.manager.create_project_spec(str(self.project["id"]), "full_body")
        self.manager.create_project_spec(str(self.project["id"]), "half_body")
        char = self.manager.create_character(str(self.project["id"]), "角色A")
        variants = self.manager.list_character_variants(str(char["id"]))
        values = self.manager.list_spec_values_for_variant(str(variants[0]["id"]))
        self.assertEqual(len(values), 2)

    def test_character_name_is_cleaned(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/characters",
            json={"name": "  角色  A  "},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["character"]["name"], "角色 A")

    def test_blank_character_name_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/characters",
            json={"name": "   "},
        )
        self.assertEqual(response.status_code, 422)

    def test_too_long_character_name_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/characters",
            json={"name": "名" * 81},
        )
        self.assertEqual(response.status_code, 422)

    def test_duplicate_character_name_in_same_project_rejected(self) -> None:
        self.client.post(
            f"/api/projects/{self.project['id']}/characters",
            json={"name": "同名角色"},
        )
        response = self.client.post(
            f"/api/projects/{self.project['id']}/characters",
            json={"name": "同名角色"},
        )
        self.assertEqual(response.status_code, 409)

    def test_same_character_name_allowed_in_different_projects(self) -> None:
        other = self.manager.create_project("另一个项目")
        self.client.post(
            f"/api/projects/{self.project['id']}/characters",
            json={"name": "共享名"},
        )
        response = self.client.post(
            f"/api/projects/{other['id']}/characters",
            json={"name": "共享名"},
        )
        self.assertEqual(response.status_code, 201)

    def test_nonexistent_project_returns_404(self) -> None:
        self.assertEqual(
            self.client.get("/api/projects/missing-id/characters").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                "/api/projects/missing-id/characters", json={"name": "孤儿"}
            ).status_code,
            404,
        )

    def test_rename_character(self) -> None:
        char = self.manager.create_character(str(self.project["id"]), "旧名称")
        response = self.client.patch(
            f"/api/characters/{char['id']}", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["character"]["name"], "新名称")

    def test_rename_character_rejects_duplicate(self) -> None:
        first = self.manager.create_character(str(self.project["id"]), "角色A")
        self.manager.create_character(str(self.project["id"]), "角色B")
        response = self.client.patch(
            f"/api/characters/{first['id']}", json={"name": "角色B"}
        )
        self.assertEqual(response.status_code, 409)

    def test_rename_missing_character_returns_404(self) -> None:
        response = self.client.patch(
            "/api/characters/missing-id", json={"name": "新名称"}
        )
        self.assertEqual(response.status_code, 404)

    def test_delete_character(self) -> None:
        char = self.manager.create_character(str(self.project["id"]), "待删除")
        response = self.client.delete(f"/api/characters/{char['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted"]["id"], char["id"])
        self.assertIsNone(self.manager.get_character(str(char["id"])))

    def test_delete_character_cascades_to_variants(self) -> None:
        char = self.manager.create_character(str(self.project["id"]), "级联角色")
        variants = self.manager.list_character_variants(str(char["id"]))
        self.assertEqual(len(variants), 1)
        self.client.delete(f"/api/characters/{char['id']}")
        self.assertEqual(
            self.manager.list_character_variants(str(char["id"])), []
        )

    def test_delete_missing_character_returns_404(self) -> None:
        self.assertEqual(
            self.client.delete("/api/characters/missing-id").status_code, 404
        )

    def test_characters_sorted_by_sort_order(self) -> None:
        for name in ("角色C", "角色A", "角色B"):
            self.client.post(
                f"/api/projects/{self.project['id']}/characters",
                json={"name": name},
            )
        body = self.client.get(
            f"/api/projects/{self.project['id']}/characters"
        ).json()
        self.assertEqual(
            [c["name"] for c in body["items"]], ["角色C", "角色A", "角色B"]
        )
        self.assertEqual(
            [c["sort_order"] for c in body["items"]], [1, 2, 3]
        )


class CharacterVariantApiTests(unittest.TestCase):
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
        self.project = self.manager.create_project("变体测试项目")
        self.character = self.manager.create_character(
            str(self.project["id"]), "测试角色"
        )

    def test_default_variant_exists(self) -> None:
        response = self.client.get(
            f"/api/characters/{self.character['id']}/variants"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["name"], "默认")
        self.assertEqual(body["items"][0]["is_default"], 1)

    def test_create_variant(self) -> None:
        response = self.client.post(
            f"/api/characters/{self.character['id']}/variants",
            json={"name": "裙装"},
        )
        self.assertEqual(response.status_code, 201)
        variant = response.json()["variant"]
        self.assertEqual(variant["name"], "裙装")
        self.assertEqual(variant["is_default"], 0)
        self.assertEqual(variant["sort_order"], 2)

    def test_create_variant_with_existing_specs_creates_values(self) -> None:
        self.manager.create_project_spec(str(self.project["id"]), "full_body")
        self.manager.create_project_spec(str(self.project["id"]), "close_up")
        response = self.client.post(
            f"/api/characters/{self.character['id']}/variants",
            json={"name": "裙装"},
        )
        variant = response.json()["variant"]
        values = self.manager.list_spec_values_for_variant(str(variant["id"]))
        self.assertEqual(len(values), 2)

    def test_duplicate_variant_name_rejected(self) -> None:
        self.client.post(
            f"/api/characters/{self.character['id']}/variants",
            json={"name": "裙装"},
        )
        response = self.client.post(
            f"/api/characters/{self.character['id']}/variants",
            json={"name": "裙装"},
        )
        self.assertEqual(response.status_code, 409)

    def test_rename_variant(self) -> None:
        variants = self.manager.list_character_variants(str(self.character["id"]))
        response = self.client.patch(
            f"/api/character-variants/{variants[0]['id']}",
            json={"name": "默认形象"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["variant"]["name"], "默认形象")

    def test_delete_variant(self) -> None:
        self.manager.create_character_variant(str(self.character["id"]), "裙装")
        variants = self.manager.list_character_variants(str(self.character["id"]))
        skirt_variant = [v for v in variants if v["name"] == "裙装"][0]
        response = self.client.delete(
            f"/api/character-variants/{skirt_variant['id']}"
        )
        self.assertEqual(response.status_code, 200)
        remaining = self.manager.list_character_variants(str(self.character["id"]))
        self.assertEqual(len(remaining), 1)

    def test_nonexistent_character_returns_404_for_variants(self) -> None:
        self.assertEqual(
            self.client.get("/api/characters/missing-id/variants").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                "/api/characters/missing-id/variants", json={"name": "裙装"}
            ).status_code,
            404,
        )


class ProjectSpecApiTests(unittest.TestCase):
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
        self.project = self.manager.create_project("规格测试项目")

    def test_empty_project_returns_empty_spec_list(self) -> None:
        response = self.client.get(f"/api/projects/{self.project['id']}/specs")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["items"], [])
        self.assertEqual(body["total"], 0)

    def test_create_standard_spec(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/specs",
            json={"spec_type": "full_body"},
        )
        self.assertEqual(response.status_code, 201)
        spec = response.json()["spec"]
        self.assertEqual(spec["spec_type"], "full_body")
        self.assertEqual(spec["custom_label"], "")
        self.assertEqual(spec["sort_order"], 1)

    def test_create_custom_spec(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/specs",
            json={"spec_type": "custom", "custom_label": "近景"},
        )
        self.assertEqual(response.status_code, 201)
        spec = response.json()["spec"]
        self.assertEqual(spec["spec_type"], "custom")
        self.assertEqual(spec["custom_label"], "近景")

    def test_custom_spec_without_label_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/specs",
            json={"spec_type": "custom"},
        )
        self.assertEqual(response.status_code, 422)

    def test_invalid_spec_type_rejected(self) -> None:
        response = self.client.post(
            f"/api/projects/{self.project['id']}/specs",
            json={"spec_type": "invalid_type"},
        )
        self.assertEqual(response.status_code, 422)

    def test_duplicate_spec_rejected(self) -> None:
        self.client.post(
            f"/api/projects/{self.project['id']}/specs",
            json={"spec_type": "full_body"},
        )
        response = self.client.post(
            f"/api/projects/{self.project['id']}/specs",
            json={"spec_type": "full_body"},
        )
        self.assertEqual(response.status_code, 409)

    def test_create_spec_auto_creates_values_for_existing_variants(self) -> None:
        char = self.manager.create_character(str(self.project["id"]), "角色A")
        variants = self.manager.list_character_variants(str(char["id"]))
        self.client.post(
            f"/api/projects/{self.project['id']}/specs",
            json={"spec_type": "full_body"},
        )
        values = self.manager.list_spec_values_for_variant(str(variants[0]["id"]))
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["prompt"], "")
        self.assertIsNone(values[0]["lora_weight"])

    def test_delete_spec_removes_spec_values(self) -> None:
        self.manager.create_project_spec(str(self.project["id"]), "full_body")
        self.manager.create_character(str(self.project["id"]), "角色A")
        specs = self.manager.list_project_specs(str(self.project["id"]))
        response = self.client.delete(
            f"/api/project-specs/{specs[0]['id']}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.manager.list_project_specs(str(self.project["id"])), []
        )

    def test_update_character_spec_value(self) -> None:
        self.manager.create_project_spec(str(self.project["id"]), "full_body")
        char = self.manager.create_character(str(self.project["id"]), "角色A")
        variants = self.manager.list_character_variants(str(char["id"]))
        values = self.manager.list_spec_values_for_variant(str(variants[0]["id"]))
        response = self.client.patch(
            f"/api/character-spec-values/{values[0]['id']}",
            json={
                "prompt": "1girl, solo",
                "lora_name": "char_a.safetensors",
                "lora_weight": 0.82,
                "model_override": "sd_xl",
                "notes": "主线默认",
            },
        )
        self.assertEqual(response.status_code, 200)
        updated = response.json()["spec_value"]
        self.assertEqual(updated["prompt"], "1girl, solo")
        self.assertEqual(updated["lora_name"], "char_a.safetensors")
        self.assertAlmostEqual(updated["lora_weight"], 0.82)
        self.assertEqual(updated["model_override"], "sd_xl")
        self.assertEqual(updated["notes"], "主线默认")

    def test_lora_weight_out_of_range_rejected(self) -> None:
        self.manager.create_project_spec(str(self.project["id"]), "full_body")
        char = self.manager.create_character(str(self.project["id"]), "角色A")
        variants = self.manager.list_character_variants(str(char["id"]))
        values = self.manager.list_spec_values_for_variant(str(variants[0]["id"]))
        response = self.client.patch(
            f"/api/character-spec-values/{values[0]['id']}",
            json={"lora_weight": 2.5},
        )
        self.assertEqual(response.status_code, 422)


class CharacterSpecValueIsolationTests(unittest.TestCase):
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
        self.project = self.manager.create_project("隔离测试项目")

    def test_character_data_stays_in_test_database(self) -> None:
        char = self.manager.create_character(str(self.project["id"]), "角色A")
        self.assertEqual(
            self.manager.list_characters(str(self.project["id"])),
            [char],
        )
        production_chars = self.manager.list_characters(
            str(self.project["id"]), environment="production"
        )
        self.assertEqual(production_chars, [])