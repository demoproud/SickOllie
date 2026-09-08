from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = types.ModuleType("sickollie_recipe_component_test")
PACKAGE.__path__ = [str(ROOT)]
sys.modules.setdefault("sickollie_recipe_component_test", PACKAGE)
SPEC = importlib.util.spec_from_file_location("sickollie_recipe_component_test.solo_recipe_catalog", ROOT / "solo_recipe_catalog.py")
assert SPEC and SPEC.loader
recipe_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recipe_module
SPEC.loader.exec_module(recipe_module)
catalog_module = sys.modules["sickollie_recipe_component_test.solo_catalog"]


def payload(*placeholders: tuple[str, str, str], schema: int | None = None) -> dict:
    result = {
        "nodes": [],
        "summary": {
            "placeholders": [
                {"token": token, "value": value, "widget": widget}
                for token, value, widget in placeholders
            ]
        },
    }
    if schema is not None:
        result["schema"] = schema
    return result


class RecipeComponentLogTests(unittest.TestCase):
    def test_resolved_outfits_and_scenes_become_deduplicated_visual_assets(self) -> None:
        recipes = [
            {
                "recipe_id": "recipe:one",
                "name": "One",
                "created_at": "2026-08-19T01:00:00Z",
                "preview_ref": "one.webp",
                "payload": payload(
                    ("OUTFIT", "pink ringer tee and white shorts", "outfit_log_file_A"),
                    ("SCENE", "sunny motel pool", "scene_log_file"),
                ),
                "collections": [],
            },
            {
                "recipe_id": "recipe:two",
                "name": "Two",
                "created_at": "2026-08-19T02:00:00Z",
                "preview_ref": "two.webp",
                "payload": payload(
                    ("CLOTHES", "pink ringer tee and white shorts", "outfit_log_file_A"),
                    ("LOCATION", "neon laundromat at night", "scene_log_file"),
                ),
                "collections": [],
            },
        ]
        outfits = recipe_module._recipe_component_assets(recipes, "outfit")
        scenes = recipe_module._recipe_component_assets(recipes, "scene")
        self.assertEqual(len(outfits), 1)
        self.assertEqual(outfits[0]["value"], "pink ringer tee and white shorts")
        self.assertEqual(outfits[0]["uses"], 2)
        self.assertEqual(outfits[0]["index"], 0)
        self.assertEqual(outfits[0]["source_preview_ref"], "one.webp")
        self.assertEqual(outfits[0]["preview_ref"], "")
        self.assertEqual([item["value"] for item in scenes], ["sunny motel pool", "neon laundromat at night"])
        self.assertEqual([item["index"] for item in scenes], [0, 1])

    def test_component_master_and_collection_logs_follow_component_membership(self) -> None:
        outfit_collection = {"collection_id": "component-collection:outfit:cozy", "name": "Cozy", "color": "#ff4ab8"}
        scene_collection = {"collection_id": "component-collection:scene:night", "name": "Night", "color": "#63e6a4"}
        recipes = [
            {
                "recipe_id": "recipe:one",
                "name": "One",
                "created_at": "2026-08-19T01:00:00Z",
                "payload": payload(
                    ("OUTFIT", "silver mini dress", "outfit_log_file_A"),
                    ("SCENE", "white seamless studio", "scene_log_file"),
                ),
                "collections": [{"collection_id": "recipe-collection:faceout", "name": "Faceouts", "color": "#b89aff"}],
            },
            {
                "recipe_id": "recipe:two",
                "name": "Two",
                "created_at": "2026-08-19T02:00:00Z",
                "payload": payload(
                    ("OUTFIT", "oversized striped tee and socks", "outfit_log_file_A"),
                    ("SCENE", "bedroom window at dusk", "scene_log_file"),
                ),
                "collections": [],
            },
        ]
        components = {
            "outfit": [
                {"component_id": "outfit:one", "kind": "outfit", "value": "silver mini dress", "manual": 0, "collections": []},
                {"component_id": "outfit:two", "kind": "outfit", "value": "oversized striped tee and socks", "manual": 0, "collections": [outfit_collection]},
            ],
            "scene": [
                {"component_id": "scene:one", "kind": "scene", "value": "white seamless studio", "manual": 0, "collections": []},
                {"component_id": "scene:two", "kind": "scene", "value": "bedroom window at dusk", "manual": 0, "collections": [scene_collection]},
            ],
        }
        component_collections = {"outfit": [outfit_collection], "scene": [scene_collection]}
        with tempfile.TemporaryDirectory() as directory:
            outfit_root = Path(directory) / "outfits" / "Creative Library"
            scene_root = Path(directory) / "scenes" / "Creative Library"
            result = recipe_module._sync_recipe_component_logs(
                outfit_root, scene_root, recipes, [], components, component_collections
            )
            outfit_master = (outfit_root / recipe_module.RECIPE_OUTFIT_MASTER_FILE).read_text(encoding="utf-8")
            scene_master = (scene_root / recipe_module.RECIPE_SCENE_MASTER_FILE).read_text(encoding="utf-8")
            outfit_collection_log = (outfit_root / "Collections" / "Cozy.txt").read_text(encoding="utf-8")
            scene_collection_log_exists = (scene_root / "Collections" / "Night.txt").exists()
            scene_collection_folder_exists = (scene_root / "Collections").exists()

        self.assertTrue(result["ok"])
        self.assertEqual(outfit_master, "silver mini dress\noversized striped tee and socks\n")
        self.assertEqual(scene_master, "white seamless studio\nbedroom window at dusk\n")
        self.assertEqual(outfit_collection_log, "oversized striped tee and socks\n")
        self.assertFalse(scene_collection_log_exists)
        self.assertFalse(scene_collection_folder_exists)
        self.assertFalse((outfit_root / "Collections" / "Faceouts.txt").exists())


    def test_scene_taxonomy_classifies_from_scene_text_not_source_filename(self) -> None:
        self.assertEqual(
            recipe_module._classify_scene_taxonomy("sun-baked desert dunes beside a lonely highway"),
            ("Desert", "Dunes & Open Desert"),
        )
        self.assertEqual(
            recipe_module._classify_scene_taxonomy("downtown city street with storefronts and a crosswalk"),
            ("Urban", "Streets & Sidewalks"),
        )

    def test_scene_taxonomy_migration_preserves_component_identity_preview_and_rating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            scene = catalog.upsert_recipe_component("scene", "downtown city street with storefronts", manual=True)
            catalog.set_recipe_component_preview("scene", scene["value"], "scene-card.webp", "generated:catalog")
            catalog.set_component_rating(scene["component_id"], 5)
            legacy = catalog.create_component_collection("scene", "old-file-name.txt")
            catalog.set_component_collections(scene["component_id"], [legacy["collection_id"]])

            result = recipe_module._ensure_scene_taxonomy(catalog)
            rows = catalog.recipe_components("scene")
            groups = catalog.component_collections("scene")

        self.assertTrue(result["migrated"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["component_id"], scene["component_id"])
        self.assertEqual(rows[0]["preview_ref"], "scene-card.webp")
        self.assertEqual(rows[0]["preview_source"], "generated:catalog")
        self.assertEqual(rows[0]["rating"], 5)
        self.assertNotIn("old-file-name.txt", {group["name"] for group in groups})
        self.assertIn("Urban", {group["name"] for group in groups})
        self.assertTrue(rows[0]["collections"])

    def test_scene_classifier_keeps_working_after_migrated_biome_labels_are_renamed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            legacy_scene = catalog.upsert_recipe_component("scene", "downtown avenue with storefronts", manual=True)
            legacy = catalog.create_component_collection("scene", "legacy-scenes.txt")
            catalog.set_component_collections(legacy_scene["component_id"], [legacy["collection_id"]])
            recipe_module._ensure_scene_taxonomy(catalog)
            groups = catalog.component_collections("scene")
            urban = next(group for group in groups if group["name"] == "Urban" and not group.get("parent_id"))
            streets = next(group for group in groups if group["name"] == "Streets & Sidewalks")
            catalog.update_component_collection(urban["collection_id"], name="City Life")
            catalog.update_component_collection(streets["collection_id"], name="Street Grid")
            scene = catalog.upsert_recipe_component("scene", "downtown city street with a crosswalk", manual=False)
            assigned = recipe_module._classify_scene_component_into_existing_taxonomy(catalog, scene)
            row = next(item for item in catalog.recipe_components("scene") if item["component_id"] == scene["component_id"])

        self.assertEqual(assigned, [streets["collection_id"]])
        self.assertEqual([item["name"] for item in row["collections"]], ["Street Grid"])

    def test_fresh_scene_library_does_not_seed_builtin_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            result = recipe_module._ensure_scene_taxonomy(catalog)
            groups = catalog.component_collections("scene")

        self.assertFalse(result["migrated"])
        self.assertTrue(result["empty_library"])
        self.assertEqual(groups, [])

    def test_imported_or_user_scene_taxonomy_is_preserved_without_legacy_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            parent = catalog.create_component_collection("scene", "Tropical")
            child = catalog.create_component_collection("scene", "Beaches", parent_id=parent["collection_id"])
            scene = catalog.upsert_recipe_component("scene", "sunlit tropical beach", manual=True)
            catalog.set_component_collections(scene["component_id"], [child["collection_id"]])
            result = recipe_module._ensure_scene_taxonomy(catalog)
            groups = catalog.component_collections("scene")
            row = next(item for item in catalog.recipe_components("scene") if item["component_id"] == scene["component_id"])

        self.assertFalse(result["migrated"])
        self.assertEqual({group["name"] for group in groups}, {"Tropical", "Beaches"})
        self.assertEqual([item["name"] for item in row["collections"]], ["Beaches"])

    def test_tombstoned_scene_values_are_excluded_from_recipe_derived_assets(self) -> None:
        recipe = {
            "recipe_id": "recipe:scene",
            "created_at": "2026-08-25T01:00:00Z",
            "payload": payload(("SCENE", "white seamless studio", "scene_log_file")),
            "collections": [],
        }
        assets = recipe_module._recipe_component_assets(
            [recipe], "scene", tombstoned_values={"white seamless studio".casefold()}
        )
        self.assertEqual(assets, [])

    def test_custom_tokens_are_classified_by_their_prompt_core_widget(self) -> None:
        recipe = {
            "payload": payload(
                ("WARDROBE", "black bodysuit and slouch socks", "outfit_log_file_B"),
                ("WHERE", "rainy convenience store", "scene_log_file"),
            )
        }
        self.assertEqual(recipe_module._recipe_resolved_component_values(recipe, "outfit"), ["black bodysuit and slouch socks"])
        self.assertEqual(recipe_module._recipe_resolved_component_values(recipe, "scene"), ["rainy convenience store"])


    def test_modern_recipe_does_not_recover_selected_but_unused_scene_from_widgets(self) -> None:
        recipe = {
            "payload": {
                "schema": 4,
                "summary": {"placeholders": []},
                "nodes": [{
                    "type": recipe_module.STUDIO_PROMPT,
                    "widgets": [
                        {"name": "scene_log_file", "value": "scenes/selected.txt"},
                        {"name": "scene_index", "value": 7},
                    ],
                }],
            }
        }
        original = recipe_module._component_from_log_reference
        try:
            recipe_module._component_from_log_reference = lambda *_args, **_kwargs: "selected but unused scene"
            self.assertEqual(recipe_module._recipe_resolved_component_values(recipe, "scene"), [])
        finally:
            recipe_module._component_from_log_reference = original

    def test_legacy_recipe_can_still_recover_scene_from_fixed_log_reference(self) -> None:
        recipe = {
            "payload": {
                "schema": 3,
                "nodes": [{
                    "type": recipe_module.STUDIO_PROMPT,
                    "widgets": [
                        {"name": "scene_log_file", "value": "scenes/legacy.txt"},
                        {"name": "scene_index", "value": 2},
                    ],
                }],
            }
        }
        original = recipe_module._component_from_log_reference
        try:
            recipe_module._component_from_log_reference = lambda *_args, **_kwargs: "legacy recovered scene"
            self.assertEqual(recipe_module._recipe_resolved_component_values(recipe, "scene"), ["legacy recovered scene"])
        finally:
            recipe_module._component_from_log_reference = original

    def test_recipe_preview_never_becomes_component_card_thumbnail_without_catalog_preview(self) -> None:
        recipe = {
            "recipe_id": "recipe:preview-only",
            "name": "Preview only",
            "created_at": "2026-08-25T01:00:00Z",
            "preview_ref": "person-generation.webp",
            "payload": payload(("SCENE", "empty rooftop at dawn", "scene_log_file")),
            "collections": [],
        }
        asset = recipe_module._recipe_component_assets([recipe], "scene")[0]
        self.assertEqual(asset["source_preview_ref"], "person-generation.webp")
        self.assertEqual(asset["catalog_preview_ref"], "")
        self.assertEqual(asset["preview_ref"], "")
        self.assertEqual(asset["preview_source"], "")

    def test_fresh_release_bundles_no_scene_or_other_creative_library_logs(self) -> None:
        self.assertFalse((ROOT / "Starter Content" / "input" / "SickOllieLogs").exists())

    def test_stored_catalog_preview_replaces_person_recipe_thumbnail(self) -> None:
        recipe = {
            "recipe_id": "recipe:one",
            "name": "One",
            "created_at": "2026-08-19T01:00:00Z",
            "preview_ref": "person.webp",
            "payload": payload(("OUTFIT", "denim varsity jacket and white tee", "outfit_log_file_A")),
            "collections": [],
        }
        stored = [{
            "component_id": "recipe-component:outfit:test",
            "kind": "outfit",
            "value": "denim varsity jacket and white tee",
            "manual": 0,
            "preview_ref": "catalog.webp",
            "preview_source": "generated:catalog",
        }]
        asset = recipe_module._recipe_component_assets([recipe], "outfit", stored)[0]
        self.assertEqual(asset["source_preview_ref"], "person.webp")
        self.assertEqual(asset["catalog_preview_ref"], "catalog.webp")
        self.assertEqual(asset["preview_ref"], "catalog.webp")
        self.assertEqual(asset["preview_source"], "generated:catalog")

    def test_manual_components_join_master_log_without_a_recipe(self) -> None:
        components = {
            "outfit": [{"component_id": "manual:one", "kind": "outfit", "value": "cream cardigan and plaid skirt", "manual": 1}],
            "scene": [{"component_id": "manual:two", "kind": "scene", "value": "empty neon diner at midnight", "manual": 1}],
        }
        with tempfile.TemporaryDirectory() as directory:
            outfit_root = Path(directory) / "outfits" / "Creative Library"
            scene_root = Path(directory) / "scenes" / "Creative Library"
            recipe_module._sync_recipe_component_logs(outfit_root, scene_root, [], [], components)
            outfit_master = (outfit_root / recipe_module.RECIPE_OUTFIT_MASTER_FILE).read_text(encoding="utf-8")
            scene_master = (scene_root / recipe_module.RECIPE_SCENE_MASTER_FILE).read_text(encoding="utf-8")
        self.assertEqual(outfit_master, "cream cardigan and plaid skirt\n")
        self.assertEqual(scene_master, "empty neon diner at midnight\n")


if __name__ == "__main__":
    unittest.main()
