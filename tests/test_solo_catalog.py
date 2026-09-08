from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "solo_catalog.py"
SPEC = importlib.util.spec_from_file_location("sickollie_solo_catalog", MODULE)
assert SPEC and SPEC.loader
catalog_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalog_module)


class SoloCatalogTests(unittest.TestCase):
    def test_legacy_shared_prompt_folders_split_into_prompt_and_template_copies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.sqlite3"
            catalog_module.SoloCatalog(path)
            with sqlite3.connect(path) as db:
                db.execute(
                    "INSERT INTO recipe_collections(collection_id,name,color,created_at,updated_at) VALUES(?,?,?,?,?)",
                    ("legacy:folder", "Showcase", "#ff4ab8", "2026-01-01", "2026-01-01"),
                )
                db.execute(
                    "INSERT INTO prompt_collection_memberships(prompt_id,collection_id,created_at) VALUES(?,?,?)",
                    ("legacy:prompt", "legacy:folder", "2026-01-01"),
                )
                db.execute("DELETE FROM schema_meta WHERE key='prompt_showcase_split_v1'")

            upgraded = catalog_module.SoloCatalog(path)
            prompt_folders = upgraded.prompt_showcase_collections("prompt")
            template_folders = upgraded.prompt_showcase_collections("template")
            memberships = upgraded.prompt_collection_map(["legacy:prompt"])["legacy:prompt"]

        self.assertEqual([row["name"] for row in prompt_folders], ["Showcase"])
        self.assertEqual([row["name"] for row in template_folders], ["Showcase"])
        self.assertEqual({row["kind"] for row in memberships}, {"prompt"})

    def test_upgrade_from_legacy_component_collections_adds_parent_before_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.sqlite3"
            with sqlite3.connect(path) as db:
                db.execute(
                    """CREATE TABLE component_collections (
                        collection_id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        name TEXT NOT NULL COLLATE NOCASE,
                        color TEXT NOT NULL DEFAULT '#ff4ab8',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(kind, name)
                    )"""
                )
                db.execute(
                    "INSERT INTO component_collections(collection_id, kind, name, color, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    ("legacy-scenes", "scene", "Legacy Scenes", "#63e6a4", "2026-08-25T00:00:00Z", "2026-08-25T00:00:00Z"),
                )
            catalog = catalog_module.SoloCatalog(path)
            with sqlite3.connect(path) as db:
                columns = {row[1] for row in db.execute("PRAGMA table_info(component_collections)")}
                indexes = {row[1] for row in db.execute("PRAGMA index_list(component_collections)")}
                preserved = db.execute("SELECT name, parent_id FROM component_collections WHERE collection_id='legacy-scenes'").fetchone()

        self.assertIn("parent_id", columns)
        self.assertIn("component_collections_kind_parent", indexes)
        self.assertEqual(preserved, ("Legacy Scenes", ""))

    def test_asset_history_trigger_pin_and_review_are_durable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.upsert_asset(asset_id="sha256:abc", path="/models/Old.safetensors", sha256="abc", size=12)
            catalog.replace_trigger_candidates("sha256:abc", [{"raw": "shyla", "clean": "shyla", "source": "civitai.trainedWords", "confidence": .88, "flags": []}])
            catalog.pin_trigger("sha256:abc", "shyla")
            catalog.set_review("sha256:abc", "favorite", 5, "Reliable")
            catalog.record_relocation("sha256:abc", "/models/Old.safetensors", "/models/New.safetensors", "move.json")
            asset = catalog.asset("sha256:abc")
            repaired = catalog.exact_repair_target(sha256="abc")
            catalog.save_filter("Favorites", {"state": "favorite"})
            filtered = catalog.list_assets(state="favorite")
            saved_filters = catalog.filters()
            catalog.save_recipe("recipe:one", "Poster test", {"nodes": []})
            recipes = catalog.recipes()

        self.assertEqual(asset["current_path"], "/models/New.safetensors")
        self.assertEqual(asset["review"]["state"], "favorite")
        self.assertTrue(asset["triggers"][0]["pinned"])
        self.assertIn("/models/Old.safetensors", asset["paths"])
        self.assertIn("/models/New.safetensors", asset["paths"])
        self.assertEqual(repaired, "/models/New.safetensors")
        self.assertEqual(filtered[0]["asset_id"], "sha256:abc")
        self.assertEqual(saved_filters[0]["name"], "Favorites")
        self.assertEqual(recipes[0]["name"], "Poster test")

    def test_prompt_collection_remove_is_surgical_for_theater_reject_undo(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            prompt, _ = catalog.import_prompt_asset({"value": "A cinematic portrait of a young woman.", "kind": "prompt", "primary_parent": "Portrait", "primary_subcategory": "General"})
            keep = catalog.create_prompt_showcase_collection("prompt", "Keep Folder")
            rejected = catalog.create_prompt_showcase_collection("prompt", "Rejected")
            catalog.set_prompt_collections(prompt["prompt_id"], [keep["collection_id"], rejected["collection_id"]])
            result = catalog.remove_prompts_from_collections([prompt["prompt_id"]], [rejected["collection_id"]])
            memberships = catalog.prompt_collection_map([prompt["prompt_id"]])[prompt["prompt_id"]]

        self.assertEqual(result["memberships_removed"], 1)
        self.assertEqual([item["name"] for item in memberships], ["Keep Folder"])

    def test_lora_reviews_support_exact_theater_ratings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.upsert_asset(asset_id="sha256:rated", path="/models/Rated.safetensors", sha256="rated", size=12)
            catalog.set_review("sha256:rated", "rated", 2)
            two_star = catalog.list_assets()[0]
            catalog.set_review("sha256:rated", "rated", 5)
            five_star = catalog.list_assets()[0]

        self.assertEqual(two_star["review_state"], "rated")
        self.assertEqual(two_star["rating"], 2)
        self.assertEqual(five_star["review_state"], "rated")
        self.assertEqual(five_star["rating"], 5)

    def test_lora_collections_are_virtual_many_to_many_groups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.upsert_asset(asset_id="path:one", path="/models/creator-a/One.safetensors", size=12, model_name="One")
            catalog.upsert_asset(asset_id="path:two", path="/models/creator-b/Two.safetensors", size=12, model_name="Two")
            cast = catalog.create_lora_collection("Favorite cast")
            catalog.update_lora_collection_members(cast["collection_id"], ["path:one", "path:two"])
            populated = catalog.lora_collections()[0]
            catalog.update_lora_collection_members(cast["collection_id"], ["path:one"], remove=True)
            reduced = catalog.lora_collections()[0]
            catalog.delete_lora_collection(cast["collection_id"])
            deleted = catalog.lora_collections()

        self.assertEqual(populated["asset_count"], 2)
        self.assertEqual(set(populated["asset_ids"]), {"path:one", "path:two"})
        self.assertEqual(reduced["asset_ids"], ["path:two"])
        self.assertEqual(deleted, [])

    def test_lora_memberships_update_many_assets_and_collections_in_one_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.upsert_asset(asset_id="path:one", path="/models/One.safetensors", size=12)
            catalog.upsert_asset(asset_id="path:two", path="/models/Two.safetensors", size=12)
            favorites = catalog.create_lora_collection("Favorites")
            campaign = catalog.create_lora_collection("Campaign")
            result = catalog.update_lora_collections_members(
                [favorites["collection_id"], campaign["collection_id"]],
                ["path:one", "path:two"],
            )
            populated = {item["name"]: item for item in catalog.lora_collections()}
            removed = catalog.update_lora_collections_members(
                [favorites["collection_id"], campaign["collection_id"]],
                ["path:one"],
                remove=True,
            )
            reduced = {item["name"]: item for item in catalog.lora_collections()}

        self.assertEqual(result, {"assets": 2, "collections": 2, "memberships_changed": 4})
        self.assertEqual(set(populated["Favorites"]["asset_ids"]), {"path:one", "path:two"})
        self.assertEqual(set(populated["Campaign"]["asset_ids"]), {"path:one", "path:two"})
        self.assertEqual(removed["memberships_changed"], 2)
        self.assertEqual(reduced["Favorites"]["asset_ids"], ["path:two"])
        self.assertEqual(reduced["Campaign"]["asset_ids"], ["path:two"])

    def test_recipe_collections_are_many_to_many_and_delete_without_recipes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.save_recipe("recipe:faceout", "Faceout poster", {"nodes": []})
            catalog.save_recipe("recipe:yearbook", "Yearbook portrait", {"nodes": []})
            faceout = catalog.create_recipe_collection("Faceout Posters")
            favorites = catalog.create_recipe_collection("Favorites")
            catalog.set_recipe_collections("recipe:faceout", [faceout["collection_id"], favorites["collection_id"]])
            catalog.set_recipe_collections("recipe:yearbook", [favorites["collection_id"]])
            before = {item["recipe_id"]: item for item in catalog.recipes()}
            catalog.delete_recipe_collection(favorites["collection_id"])
            after = {item["recipe_id"]: item for item in catalog.recipes()}
            remaining_collections = catalog.recipe_collections()

        self.assertEqual({item["name"] for item in before["recipe:faceout"]["collections"]}, {"Faceout Posters", "Favorites"})
        self.assertEqual({item["name"] for item in before["recipe:yearbook"]["collections"]}, {"Favorites"})
        self.assertEqual([item["name"] for item in after["recipe:faceout"]["collections"]], ["Faceout Posters"])
        self.assertEqual(after["recipe:yearbook"]["collections"], [])
        self.assertEqual({item["name"] for item in remaining_collections}, {"Faceout Posters"})

    def test_recipe_revision_invalidates_prompt_cache_for_collection_changes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.save_recipe("recipe:one", "One", {"nodes": []})
            before_collection = catalog.recipe_revision()
            collection = catalog.create_recipe_collection("Night")
            after_collection = catalog.recipe_revision()
            catalog.set_recipe_collections("recipe:one", [collection["collection_id"]])
            after_membership = catalog.recipe_revision()

        self.assertNotEqual(before_collection, after_collection)
        self.assertNotEqual(after_collection, after_membership)

    def test_recipe_bulk_collection_add_preserves_existing_memberships_and_bulk_delete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.save_recipe("recipe:one", "One", {"nodes": []})
            catalog.save_recipe("recipe:two", "Two", {"nodes": []})
            catalog.save_recipe("recipe:three", "Three", {"nodes": []})
            existing = catalog.create_recipe_collection("Existing")
            batch = catalog.create_recipe_collection("Batch")
            catalog.set_recipe_collections("recipe:one", [existing["collection_id"]])

            result = catalog.add_recipes_to_collections(
                ["recipe:one", "recipe:two"],
                [batch["collection_id"]],
            )
            after_add = {item["recipe_id"]: item for item in catalog.recipes()}
            deleted = catalog.delete_recipes(["recipe:one", "recipe:three"])
            remaining = {item["recipe_id"]: item for item in catalog.recipes()}

        self.assertEqual(result["recipes"], 2)
        self.assertEqual(result["collections"], 1)
        self.assertEqual(result["memberships_added"], 2)
        self.assertEqual(
            {item["name"] for item in after_add["recipe:one"]["collections"]},
            {"Existing", "Batch"},
        )
        self.assertEqual(
            {item["name"] for item in after_add["recipe:two"]["collections"]},
            {"Batch"},
        )
        self.assertEqual(deleted, 2)
        self.assertEqual(set(remaining), {"recipe:two"})

    def test_prompt_showcase_folder_memberships_are_many_to_many_and_revisioned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            favorites = catalog.create_prompt_showcase_collection("prompt", "Showcase Favorites")
            campaign = catalog.create_prompt_showcase_collection("prompt", "Campaign Set")
            before = catalog.prompt_revision()
            result = catalog.add_prompts_to_collections(
                ["corpus-prompt:one", "creative-prompt:two"],
                [favorites["collection_id"]],
            )
            catalog.set_prompt_collections(
                "corpus-prompt:one", [favorites["collection_id"], campaign["collection_id"]],
            )
            memberships = catalog.prompt_collection_map()
            collections = {item["name"]: item for item in catalog.prompt_showcase_collections("prompt")}
            after = catalog.prompt_revision()

        self.assertEqual(result["prompts"], 2)
        self.assertEqual(result["memberships_added"], 2)
        self.assertEqual({item["name"] for item in memberships["corpus-prompt:one"]}, {"Showcase Favorites", "Campaign Set"})
        self.assertEqual([item["name"] for item in memberships["creative-prompt:two"]], ["Showcase Favorites"])
        self.assertEqual(collections["Showcase Favorites"]["prompt_count"], 2)
        self.assertNotEqual(before, after)

    def test_prompt_showcase_folder_survives_canonical_index_rebuild(self) -> None:
        asset = {
            "prompt_id": "corpus-prompt:stable", "kind": "prompt", "value": "young woman in a neon studio",
            "primary_parent": "Studio", "primary_subcategory": "Neon", "facets": {}, "sources": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.replace_prompt_index([asset], [], signature="one")
            folder = catalog.create_prompt_showcase_collection("prompt", "Showcase")
            catalog.add_prompts_to_collections([asset["prompt_id"]], [folder["collection_id"]])
            catalog.replace_prompt_index([asset], [], signature="two")
            after = catalog.prompt_collection_map([asset["prompt_id"]])

        self.assertEqual([item["name"] for item in after[asset["prompt_id"]]], ["Showcase"])

    def test_prompt_and_template_showcase_folders_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            prompt_folder = catalog.create_prompt_showcase_collection("prompt", "Campaign")
            template_folder = catalog.create_prompt_showcase_collection("template", "Campaign")
            catalog.add_prompts_to_collections(["prompt:one"], [prompt_folder["collection_id"]], "prompt")
            catalog.add_prompts_to_collections(["template:one"], [template_folder["collection_id"]], "template")
            catalog.delete_prompt_showcase_collection(prompt_folder["collection_id"])

            prompt_folders = catalog.prompt_showcase_collections("prompt")
            template_folders = catalog.prompt_showcase_collections("template")
            template_memberships = catalog.prompt_collection_map(["template:one"])

        self.assertEqual(prompt_folders, [])
        self.assertEqual([row["name"] for row in template_folders], ["Campaign"])
        self.assertEqual([row["collection_id"] for row in template_memberships["template:one"]], [template_folder["collection_id"]])

    def test_prompt_preview_preserves_source_and_resolved_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.replace_prompt_index([{
                "prompt_id": "template:variant", "kind": "template",
                "value": "NAME wearing OUTFIT beside BRAND",
                "primary_parent": "Portrait", "primary_subcategory": "Editorial",
            }], [], signature="variant")
            result = catalog.set_prompt_preview(
                "template:variant", "variant.webp",
                source_prompt_snapshot="NAME wearing OUTFIT beside BRAND",
                resolved_prompt_snapshot="NAME wearing a pink slip dress beside BRAND",
                preview_metadata={"outfit_a": "a pink slip dress", "scene": "beside a mirrored wall"},
            )
            indexed = catalog.indexed_prompt_assets()[0]

        self.assertEqual(result["source_prompt_snapshot"], "NAME wearing OUTFIT beside BRAND")
        self.assertEqual(result["resolved_prompt_snapshot"], "NAME wearing a pink slip dress beside BRAND")
        self.assertEqual(result["preview_metadata"]["outfit_a"], "a pink slip dress")
        self.assertEqual(result["preview_metadata"]["scene"], "beside a mirrored wall")
        self.assertEqual(indexed["resolved_prompt_snapshot"], "NAME wearing a pink slip dress beside BRAND")
        self.assertEqual(indexed["preview_metadata"], result["preview_metadata"])

    def test_library_pack_round_trip_keeps_prompt_variants_and_separate_showcases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = catalog_module.SoloCatalog(root / "source.sqlite3")
            source.replace_prompt_index([
                {
                    "prompt_id": "prompt:pack", "kind": "prompt", "value": "A silver dress in a neon studio",
                    "primary_parent": "Editorial", "primary_subcategory": "Sets",
                },
                {
                    "prompt_id": "template:pack", "kind": "template", "value": "NAME in OUTFIT",
                    "primary_parent": "Identity", "primary_subcategory": "Sets",
                },
            ], [], signature="pack")
            prompt_folder = source.create_prompt_showcase_collection("prompt", "Best Looks")
            template_folder = source.create_prompt_showcase_collection("template", "Best Looks")
            source.add_prompts_to_collections(["prompt:pack"], [prompt_folder["collection_id"]], "prompt")
            source.add_prompts_to_collections(["template:pack"], [template_folder["collection_id"]], "template")
            source.set_prompt_preview(
                "template:pack", "template.webp",
                source_prompt_snapshot="NAME in OUTFIT",
                resolved_prompt_snapshot="NAME in a red satin dress",
                preview_metadata={"outfit_a": "a red satin dress"},
            )
            source.set_creative_structure_order("prompt", {"showcase_collections": [prompt_folder["collection_id"]]})
            source.set_creative_structure_order("template", {"showcase_collections": [template_folder["collection_id"]]})
            snapshot = source.creative_library_pack_snapshot("starter")

            target = catalog_module.SoloCatalog(root / "target.sqlite3")
            target.merge_creative_library_pack_records(
                {"pack_id": "pack:variants", "name": "Variants", "export_mode": "starter"}, snapshot,
            )
            target_assets = {row["value"]: row for row in target.indexed_prompt_assets()}
            prompt_folders = target.prompt_showcase_collections("prompt")
            template_folders = target.prompt_showcase_collections("template")

        self.assertEqual([row["name"] for row in prompt_folders], ["Best Looks"])
        self.assertEqual([row["name"] for row in template_folders], ["Best Looks"])
        self.assertEqual(target_assets["NAME in OUTFIT"]["resolved_prompt_snapshot"], "NAME in a red satin dress")
        self.assertEqual(target_assets["NAME in OUTFIT"]["preview_metadata"], {"outfit_a": "a red satin dress"})
        self.assertEqual([row["name"] for row in target_assets["A silver dress in a neon studio"]["collections"]], ["Best Looks"])
        self.assertEqual([row["name"] for row in target_assets["NAME in OUTFIT"]["collections"]], ["Best Looks"])

    def test_creative_boards_are_durable_editable_and_independent_of_recipes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.save_recipe("recipe:base", "Base blueprint", {"nodes": []})
            first = catalog.save_creative_board("", "Flash portrait", {
                "recipe_id": "recipe:base",
                "outfit_value": "white ringer tee and denim shorts",
                "scene_value": "a neon laundromat at night",
            })
            updated = catalog.save_creative_board(first["board_id"], "Flash portrait v2", {
                "recipe_id": "recipe:base",
                "outfit_value": "pink camisole and white shorts",
                "scene_value": "a neon laundromat at night",
            })
            rows = catalog.creative_boards()
            deleted = catalog.delete_creative_board(first["board_id"])
            recipes = catalog.recipes()

        self.assertEqual(first["board_id"], updated["board_id"])
        self.assertEqual(rows[0]["name"], "Flash portrait v2")
        self.assertEqual(rows[0]["payload"]["outfit_value"], "pink camisole and white shorts")
        self.assertTrue(deleted)
        self.assertEqual(recipes[0]["recipe_id"], "recipe:base")

    def test_default_registry_covers_dynamic_studio_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            with catalog._connection() as db:
                tokens = {row[0] for row in db.execute("SELECT token FROM token_registry")}
        self.assertTrue({"NAME", "OUTFIT_A", "OUTFIT_B", "OUTFIT_C", "SCENE", "ITEM", "TRIGGER"}.issubset(tokens))

    def test_completed_generation_records_testing_without_changing_rating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "rory.safetensors"
            model.write_bytes(b"lora")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset_id = catalog.ensure_path_asset(model)
            catalog.set_review(asset_id, "retest")
            catalog.record_usage(model, "/outputs/one.png")
            tested_retest = catalog.list_assets()[0]
            catalog.set_review(asset_id, "favorite")
            catalog.record_usage(model, "/outputs/two.png")
            favorite = catalog.list_assets()[0]

        self.assertEqual(tested_retest["review_state"], "retest")
        self.assertEqual(tested_retest["tested"], 1)
        self.assertEqual(tested_retest["use_count"], 1)
        self.assertEqual(favorite["review_state"], "favorite")
        self.assertEqual(favorite["rating"], 4)
        self.assertEqual(favorite["use_count"], 2)

    def test_clear_rating_preserves_testing_and_reset_all_removes_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "shyla.safetensors"
            model.write_bytes(b"lora")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset_id = catalog.ensure_path_asset(model)
            catalog.record_usage(model, "/outputs/one.png")
            catalog.set_review(asset_id, "keep")
            catalog.reset_status(asset_id, include_testing=False)
            cleared = catalog.list_assets()[0]
            catalog.reset_status(asset_id, include_testing=True)
            nuked = catalog.list_assets()[0]

        self.assertEqual(cleared["review_state"], "none")
        self.assertEqual(cleared["use_count"], 1)
        self.assertEqual(nuked["review_state"], "none")
        self.assertEqual(nuked["use_count"], 0)

    def test_most_used_sort_and_test_filters_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            low = Path(directory) / "low.safetensors"; low.write_bytes(b"low")
            high = Path(directory) / "high.safetensors"; high.write_bytes(b"high")
            fresh = Path(directory) / "fresh.safetensors"; fresh.write_bytes(b"fresh")
            catalog.ensure_path_asset(fresh)
            catalog.record_usage(low)
            catalog.record_usage(high); catalog.record_usage(high)
            catalog.set_review(catalog.path_asset_id(fresh), "favorite")
            ordered = catalog.list_assets(sort="most_used")
            tested = catalog.list_assets(state="tested")
            untested = catalog.list_assets(state="untested")

        self.assertEqual([item["model_name"] for item in ordered], ["high", "low", "fresh"])
        self.assertEqual({item["model_name"] for item in tested}, {"high", "low"})
        self.assertEqual({item["model_name"] for item in untested}, {"fresh"})

    def test_civitai_preview_skips_showcase_video_and_uses_first_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "helena.safetensors"
            model.write_bytes(b"lora")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset_id = catalog.ensure_path_asset(model)
            catalog.set_remote_metadata(asset_id, {
                "images": [
                    "https://image.civitai.com/demo/original=true/first.mp4",
                    "https://image.civitai.com/demo/original=true/second.jpeg",
                    "https://image.civitai.com/demo/original=true/third.webp",
                ]
            }, "civitai:sha256")
            listed = catalog.list_assets()[0]

        self.assertEqual(listed["civitai_preview"], "https://image.civitai.com/demo/original=true/second.jpeg")
        self.assertEqual(listed["civitai_image_count"], 2)


    def test_list_assets_exposes_thumbnail_updated_at_for_cache_busting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "cache_bust.safetensors"
            model.write_bytes(b"lora")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset_id = catalog.ensure_path_asset(model)
            catalog.set_thumbnail(asset_id, "stable.webp", "generated:yearbook")
            first = catalog.list_assets()[0]
            catalog.set_thumbnail(asset_id, "stable.webp", "civitai-showcase")
            second = catalog.list_assets()[0]

        self.assertTrue(first["thumbnail_updated_at"])
        self.assertTrue(second["thumbnail_updated_at"])
        self.assertEqual(second["thumbnail_source"], "civitai-showcase")

    def test_purge_assets_resets_lora_records_but_preserves_shared_catalog_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "reset_me.safetensors"
            model.write_bytes(b"lora")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset_id = catalog.ensure_path_asset(model)
            catalog.replace_trigger_candidates(asset_id, [{"raw": "reset", "clean": "reset", "source": "test", "confidence": .8, "flags": []}])
            catalog.set_review(asset_id, "favorite")
            catalog.record_usage(model, "/outputs/one.png")
            catalog.set_thumbnail(asset_id, "thumb.webp", "generated:yearbook")
            catalog.set_remote_metadata(asset_id, {"creator": "demo", "images": ["https://image.civitai.com/example.webp"]}, "test")
            catalog.save_filter("Keep me", {"state": "favorite"})
            catalog.save_recipe("recipe:keep", "Keep recipe", {"nodes": []})

            result = catalog.purge_assets([asset_id])

            self.assertEqual(result["purged"], 1)
            self.assertEqual(result["thumbnails"][0]["filename"], "thumb.webp")
            self.assertIsNone(catalog.asset(asset_id))
            self.assertEqual(catalog.filters()[0]["name"], "Keep me")
            self.assertEqual(catalog.recipes()[0]["name"], "Keep recipe")
            with catalog._connection() as db:
                token_count = db.execute("SELECT COUNT(*) FROM token_registry").fetchone()[0]
            self.assertGreater(token_count, 0)

    def test_clear_thumbnails_only_preserves_other_asset_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "thumb_only.safetensors"
            model.write_bytes(b"lora")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset_id = catalog.ensure_path_asset(model)
            catalog.set_review(asset_id, "keep")
            catalog.record_usage(model, "/outputs/one.png")
            catalog.set_thumbnail(asset_id, "thumb.webp", "civitai-showcase")

            removed = catalog.clear_thumbnails([asset_id])
            asset = catalog.asset(asset_id)

            self.assertEqual(removed[0]["filename"], "thumb.webp")
            self.assertIsNone(asset["thumbnail"])
            self.assertEqual(asset["review"]["state"], "keep")
            self.assertEqual(asset["usage"]["use_count"], 1)

    def test_thumbnail_remote_metadata_and_usage_events_are_cataloged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "lumi_epoch_12.safetensors"
            model.write_bytes(b"lora")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset_id = catalog.ensure_path_asset(model)
            catalog.set_thumbnail(asset_id, "abc.webp", "generated:yearbook", width=384, height=512, byte_size=42000)
            catalog.set_remote_metadata(asset_id, {
                "model_id": "123", "version_id": "456", "creator": "ollie",
                "base_model": "Krea2", "images": ["https://image.civitai.com/example.webp"],
            }, "civitai:sha256")
            catalog.record_usage(model, "/outputs/one.png")
            detail = catalog.asset(asset_id)
            listed = catalog.list_assets()[0]

        self.assertEqual(detail["thumbnail"]["source"], "generated:yearbook")
        self.assertEqual(detail["remote_metadata"]["creator"], "ollie")
        self.assertEqual(detail["usage_events"][0]["output_path"], "/outputs/one.png")
        self.assertEqual(listed["thumbnail_ref"], "abc.webp")
        self.assertEqual(listed["civitai_preview"], "https://image.civitai.com/example.webp")
        self.assertEqual(listed["base_model"], "Krea2")

    def test_recipe_components_support_manual_assets_and_catalog_previews(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            first = catalog.upsert_recipe_component("outfit", "red ringer tee and denim shorts", manual=True)
            catalog.set_recipe_component_preview("outfit", "red ringer tee and denim shorts", "outfit.webp", "generated:catalog")
            second = catalog.upsert_recipe_component("outfit", "RED RINGER TEE AND DENIM SHORTS", manual=False)
            rows = catalog.recipe_components("outfit")

        self.assertEqual(first["component_id"], second["component_id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["manual"], 1)
        self.assertEqual(rows[0]["preview_ref"], "outfit.webp")
        self.assertEqual(rows[0]["preview_source"], "generated:catalog")

    def test_component_collections_are_scoped_by_asset_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            outfit = catalog.upsert_recipe_component("outfit", "cream cardigan and plaid skirt", manual=True)
            scene = catalog.upsert_recipe_component("scene", "warm motel bedroom", manual=True)
            outfit_collection = catalog.create_component_collection("outfit", "Cozy")
            scene_collection = catalog.create_component_collection("scene", "Cozy")
            catalog.set_component_collections(outfit["component_id"], [outfit_collection["collection_id"]])
            catalog.set_component_collections(scene["component_id"], [scene_collection["collection_id"]])
            outfit_rows = catalog.recipe_components("outfit")
            scene_rows = catalog.recipe_components("scene")
            outfit_groups = catalog.component_collections("outfit")
            scene_groups = catalog.component_collections("scene")

        self.assertNotEqual(outfit_collection["collection_id"], scene_collection["collection_id"])
        self.assertEqual([item["name"] for item in outfit_rows[0]["collections"]], ["Cozy"])
        self.assertEqual([item["name"] for item in scene_rows[0]["collections"]], ["Cozy"])
        self.assertEqual(outfit_groups[0]["asset_count"], 1)
        self.assertEqual(scene_groups[0]["asset_count"], 1)

    def test_scene_component_collections_support_category_subcategory_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            street = catalog.upsert_recipe_component("scene", "downtown street", manual=True)
            general = catalog.upsert_recipe_component("scene", "city skyline", manual=True)
            urban = catalog.create_component_collection("scene", "Urban")
            streets = catalog.create_component_collection("scene", "Streets", parent_id=urban["collection_id"])
            catalog.set_component_collections(street["component_id"], [streets["collection_id"]])
            catalog.set_component_collections(general["component_id"], [urban["collection_id"]])
            groups = {row["name"]: row for row in catalog.component_collections("scene")}
            scoped = catalog.component_collection_member_ids(urban["collection_id"], include_children=True)

        self.assertEqual(groups["Urban"]["asset_count"], 2)
        self.assertEqual(groups["Urban"]["direct_asset_count"], 1)
        self.assertEqual(groups["Streets"]["asset_count"], 1)
        self.assertEqual(set(scoped), {street["component_id"], general["component_id"]})

    def test_delete_everywhere_tombstones_recipe_scene_until_manual_readd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            scene = catalog.upsert_recipe_component("scene", "rainy downtown alley", manual=False)
            catalog.set_recipe_component_preview("scene", scene["value"], "alley.webp", "generated:catalog")
            deleted = catalog.delete_recipe_components([scene["component_id"]], everywhere=True)
            blocked = catalog.upsert_recipe_component("scene", "RAINY DOWNTOWN ALLEY", manual=False)
            after_block = catalog.recipe_components("scene")
            restored = catalog.upsert_recipe_component("scene", "rainy downtown alley", manual=True)
            after_restore = catalog.recipe_components("scene")
            tombstoned_after_restore = catalog.is_component_tombstoned("scene", "rainy downtown alley")

        self.assertEqual(deleted["deleted"], 1)
        self.assertEqual(deleted["tombstoned"], 1)
        self.assertTrue(blocked.get("tombstoned"))
        self.assertEqual(after_block, [])
        self.assertFalse(tombstoned_after_restore)
        self.assertEqual(len(after_restore), 1)
        self.assertEqual(after_restore[0]["component_id"], restored["component_id"])
        self.assertEqual(after_restore[0]["manual"], 1)

    def test_delete_everywhere_tombstones_recipe_outfit_until_manual_readd(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            outfit = catalog.upsert_recipe_component("outfit", "white butterfly graphic tee and denim shorts", manual=False)
            catalog.set_recipe_component_preview("outfit", outfit["value"], "look.webp", "generated:catalog")
            deleted = catalog.delete_recipe_components([outfit["component_id"]], everywhere=True)
            blocked = catalog.upsert_recipe_component("outfit", "WHITE BUTTERFLY GRAPHIC TEE AND DENIM SHORTS", manual=False)
            after_block = catalog.recipe_components("outfit")
            restored = catalog.upsert_recipe_component("outfit", "white butterfly graphic tee and denim shorts", manual=True)
            after_restore = catalog.recipe_components("outfit")
            tombstoned_after_restore = catalog.is_component_tombstoned("outfit", "white butterfly graphic tee and denim shorts")

        self.assertEqual(deleted["deleted"], 1)
        self.assertEqual(deleted["tombstoned"], 1)
        self.assertTrue(blocked.get("tombstoned"))
        self.assertEqual(after_block, [])
        self.assertFalse(tombstoned_after_restore)
        self.assertEqual(len(after_restore), 1)
        self.assertEqual(after_restore[0]["component_id"], restored["component_id"])
        self.assertEqual(after_restore[0]["manual"], 1)

    def test_component_collection_delete_keeps_library_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset = catalog.upsert_recipe_component("outfit", "oversized striped tee and socks", manual=True)
            group = catalog.create_component_collection("outfit", "Casual")
            catalog.set_component_collections(asset["component_id"], [group["collection_id"]])
            removed = catalog.delete_component_collection(group["collection_id"])
            rows = catalog.recipe_components("outfit")

        self.assertTrue(removed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["value"], "oversized striped tee and socks")
        self.assertEqual(rows[0]["collections"], [])

    def test_wardrobe_items_preserve_piece_taxonomy_rating_and_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            first = catalog.upsert_wardrobe_item("piece", "lavender oversized hoodie", category="Layers", subtype="Hoodies & Sweatshirts")
            second = catalog.upsert_wardrobe_item("piece", "LAVENDER OVERSIZED HOODIE", category="Layers", subtype="Hoodies & Sweatshirts")
            catalog.set_wardrobe_rating(first["wardrobe_id"], 5)
            catalog.set_wardrobe_preview("piece", "lavender oversized hoodie", "piece.webp", "generated:catalog", category="Layers", subtype="Hoodies & Sweatshirts")
            rows = catalog.wardrobe_items("piece")

        self.assertEqual(first["wardrobe_id"], second["wardrobe_id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "Layers")
        self.assertEqual(rows[0]["subtype"], "Hoodies & Sweatshirts")
        self.assertEqual(rows[0]["rating"], 5)
        self.assertEqual(rows[0]["preview_ref"], "piece.webp")

    def test_clear_wardrobe_preview_preserves_item_and_returns_removed_ref(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            item = catalog.upsert_wardrobe_item("piece", "ribbed loungewear set", category="Matching Sets", subtype="Loungewear")
            catalog.set_wardrobe_rating(item["wardrobe_id"], 4)
            catalog.set_wardrobe_preview("piece", item["value"], "couch.webp", "generated:catalog", category="Matching Sets", subtype="Loungewear")
            cleared = catalog.clear_wardrobe_preview(item["wardrobe_id"])
            row = catalog.wardrobe_item_by_value("piece", item["value"])

        self.assertIsNotNone(cleared)
        self.assertEqual(cleared["removed_preview_ref"], "couch.webp")
        self.assertEqual(row["preview_ref"], "")
        self.assertEqual(row["preview_source"], "")
        self.assertEqual(row["rating"], 4)
        self.assertEqual(row["value"], "ribbed loungewear set")

    def test_wardrobe_item_edit_preserves_metadata_relationships_and_merges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            look = catalog.upsert_recipe_component("outfit", "striped sweater with denim overalls", manual=True)
            source = catalog.upsert_wardrobe_source("look", look["component_id"], label="Original Look")
            old = catalog.upsert_wardrobe_item("piece", "striped sweater with denim overalls", category="Tops", subtype="Sweaters")
            catalog.set_wardrobe_rating(old["wardrobe_id"], 4)
            catalog.set_wardrobe_preview("piece", old["value"], "old.webp", "generated:catalog", category="Tops", subtype="Sweaters")
            catalog.link_wardrobe_source(old["wardrobe_id"], source["source_id"])
            catalog.set_wardrobe_look_parts(look["component_id"], [{"wardrobe_id": old["wardrobe_id"], "relation": "with", "source_text": old["value"]}])

            edited = catalog.update_wardrobe_item(old["wardrobe_id"], "piece", "striped sweater", category="Tops", subtype="Sweaters")
            edited_id = edited["wardrobe_id"]
            edited_row = catalog.wardrobe_item_by_value("piece", "striped sweater")
            parts = catalog.wardrobe_look_parts(look["component_id"])
            sources = catalog.wardrobe_item_sources(edited_id)

            existing = catalog.upsert_wardrobe_item("piece", "denim overalls", category="Dresses & One-Pieces", subtype="Jumpsuits")
            catalog.set_wardrobe_rating(existing["wardrobe_id"], 5)
            duplicate = catalog.upsert_wardrobe_item("piece", "blue denim overalls", category="Dresses & One-Pieces", subtype="Jumpsuits")
            merged = catalog.update_wardrobe_item(duplicate["wardrobe_id"], "piece", "denim overalls", category="Dresses & One-Pieces", subtype="Jumpsuits")
            merged_row = catalog.wardrobe_item_by_value("piece", "denim overalls")

        self.assertIsNotNone(edited_row)
        self.assertEqual(edited_row["rating"], 4)
        self.assertEqual(edited_row["preview_ref"], "old.webp")
        self.assertEqual(parts[0]["wardrobe_id"], edited_id)
        self.assertEqual(len(sources), 1)
        self.assertTrue(merged["merged"])
        self.assertEqual(merged["wardrobe_id"], existing["wardrobe_id"])
        self.assertEqual(merged_row["rating"], 5)

    def test_wardrobe_sets_and_finishers_are_independent_from_outfit_looks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            look = catalog.upsert_recipe_component("outfit", "pink camisole, lace shorts, fluffy slippers", manual=True)
            set_item = catalog.upsert_wardrobe_item("set", "pink camisole and lace shorts", category="Matching Sets", subtype="Sleepwear Sets")
            finisher = catalog.upsert_wardrobe_item("finisher", "completely naked everywhere else", category="Finishers")
            catalog.delete_wardrobe_item(set_item["wardrobe_id"])
            looks = catalog.recipe_components("outfit")
            finishers = catalog.wardrobe_items("finisher")

        self.assertEqual(looks[0]["component_id"], look["component_id"])
        self.assertEqual(looks[0]["value"], "pink camisole, lace shorts, fluffy slippers")
        self.assertEqual(finishers[0]["wardrobe_id"], finisher["wardrobe_id"])

    def test_recipe_component_ids_are_stable_by_kind_and_casefolded_value(self) -> None:
        outfit = catalog_module.SoloCatalog.recipe_component_id("outfit", "White Tank + Socks")
        same = catalog_module.SoloCatalog.recipe_component_id("OUTFIT", "white tank + socks")
        scene = catalog_module.SoloCatalog.recipe_component_id("scene", "white tank + socks")
        self.assertEqual(outfit, same)
        self.assertNotEqual(outfit, scene)

    def test_bulk_prompt_import_reuses_existing_and_preserves_manual_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            existing_text = "A candid analog portrait beside a neon motel sign."
            new_text = "A quiet editorial portrait beside a rain-streaked diner window."
            catalog.replace_prompt_index([{
                "prompt_id": "corpus:existing",
                "kind": "prompt",
                "value": existing_text,
                "primary_parent": "Other",
                "primary_subcategory": "General",
                "facets": {"style": ["Analog"]},
            }], [], signature="initial")
            folder = catalog.create_prompt_showcase_collection("prompt", "Showcase Picks")
            before_revision = catalog.prompt_revision()

            result = catalog.import_prompt_assets([
                {"value": existing_text, "facets": {"style": ["Analog"]}},
                {"value": new_text, "facets": {"style": ["Editorial"]}},
                {"value": new_text, "facets": {"style": ["Editorial"]}},
            ], parent="Travel & Adventure", subcategory="Roadside", collection_ids=[folder["collection_id"]])
            imported = {row["value"]: row for row in catalog.indexed_prompt_assets()}
            after_revision = catalog.prompt_revision()

            # A later canonical rebuild may suggest another home, but the
            # curator's explicit import destination must continue to win.
            catalog.replace_prompt_index([{
                "prompt_id": "corpus:existing",
                "kind": "prompt",
                "value": existing_text,
                "primary_parent": "Suburban & Domestic",
                "primary_subcategory": "Kitchen",
                "facets": {"style": ["Analog"]},
            }], [], signature="rebuilt")
            rebuilt = {row["value"]: row for row in catalog.indexed_prompt_assets()}

        self.assertEqual(result["created"], 1)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(result["input_duplicates"], 1)
        self.assertEqual(result["homes_updated"], 2)
        self.assertNotEqual(before_revision, after_revision)
        for value in (existing_text, new_text):
            self.assertEqual(imported[value]["primary_parent"], "Travel & Adventure")
            self.assertEqual(imported[value]["primary_subcategory"], "Roadside")
            self.assertEqual([row["name"] for row in imported[value]["collections"]], ["Showcase Picks"])
        self.assertEqual(rebuilt[existing_text]["primary_parent"], "Travel & Adventure")
        self.assertEqual(rebuilt[existing_text]["primary_subcategory"], "Roadside")
        self.assertIn(new_text, rebuilt)

    def test_creative_structure_order_roundtrips_and_preserves_collection_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            first = catalog.create_component_collection("outfit", "First")
            second = catalog.create_component_collection("outfit", "Second")
            saved = catalog.set_creative_structure_order("outfit", {"collections": [second["collection_id"], first["collection_id"], second["collection_id"], ""]})
            rows = catalog.component_collections("outfit")
            roundtrip = catalog.creative_structure_order("outfit")

        self.assertEqual(saved["collections"], [second["collection_id"], first["collection_id"]])
        self.assertEqual(roundtrip, saved)
        self.assertEqual([row["name"] for row in rows], ["Second", "First"])

    def test_prompt_import_accepts_category_only_and_strict_template_kind(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            prompt = catalog.import_prompt_assets(
                [{"value": "A fully resolved portrait.", "source_line": 1}],
                parent="Editorial",
                subcategory="",
                kind="prompt",
            )
            template = catalog.import_prompt_assets(
                [{"value": "NAME wears OUTFIT in SCENE.", "source_line": 2}],
                parent="Editorial",
                subcategory="",
                kind="template",
            )
            rows = {row["value"]: row for row in catalog.indexed_prompt_assets()}

            catalog.set_prompt_home([prompt["prompt_ids"][0]], "Resolved", "")
            moved = {row["value"]: row for row in catalog.indexed_prompt_assets()}

        self.assertEqual(prompt["kind"], "prompt")
        self.assertEqual(template["kind"], "template")
        self.assertEqual(rows["A fully resolved portrait."]["primary_subcategory"], "")
        self.assertEqual(rows["NAME wears OUTFIT in SCENE."]["primary_subcategory"], "")
        self.assertEqual(rows["NAME wears OUTFIT in SCENE."]["placeholder_signature"], "NAME+OUTFIT+SCENE")
        self.assertEqual(moved["A fully resolved portrait."]["primary_parent"], "Resolved")
        self.assertEqual(moved["A fully resolved portrait."]["primary_subcategory"], "")

    def test_placeholder_tab_migration_moves_legacy_showcase_membership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.sqlite3"
            legacy = catalog_module.SoloCatalog(path)
            folder = legacy.create_prompt_showcase_collection("prompt", "Favorite Openers")
            with legacy._connection() as db:
                now = catalog_module._now()
                db.execute(
                    """INSERT INTO prompt_assets(
                    prompt_id, kind, value, placeholder_signature, primary_parent, primary_subcategory,
                    facets_json, is_custom, created_at, updated_at
                    ) VALUES ('legacy:outfit-scene', 'prompt', 'A young woman wearing OUTFIT in SCENE.', '', 'Narratives', 'Openers', '{}', 1, ?, ?)""",
                    (now, now),
                )
                db.execute(
                    "INSERT INTO prompt_showcase_memberships(prompt_id, collection_id, created_at) VALUES ('legacy:outfit-scene', ?, ?)",
                    (folder["collection_id"], now),
                )
                db.execute("DELETE FROM schema_meta WHERE key='prompt_placeholder_tabs_v2'")

            migrated = catalog_module.SoloCatalog(path)
            asset = migrated.indexed_prompt_assets()[0]
            template_folders = migrated.prompt_showcase_collections("template")

        self.assertEqual(asset["kind"], "template")
        self.assertEqual(asset["placeholder_signature"], "OUTFIT+SCENE")
        self.assertEqual([row["name"] for row in template_folders], ["Favorite Openers"])
        self.assertEqual([row["name"] for row in asset["collections"]], ["Favorite Openers"])

    def test_recipe_collection_can_be_renamed_without_touching_memberships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.save_recipe("recipe:one", "One", {"prompt": "A portrait"})
            collection = catalog.create_recipe_collection("Old Folder")
            catalog.set_recipe_collections("recipe:one", [collection["collection_id"]])
            renamed = catalog.update_recipe_collection(collection["collection_id"], name="New Folder")
            recipes = catalog.recipes()

        self.assertEqual(renamed["name"], "New Folder")
        self.assertEqual(renamed["recipe_count"], 1)
        self.assertEqual(recipes[0]["collections"][0]["name"], "New Folder")

    def test_prompt_source_log_label_can_be_renamed_without_changing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            source_path = "Imported Logs/Candid/Party/Nest Roll Journey.txt"
            catalog.import_prompt_assets(
                [{"value": "Opening beat", "source_line": 1, "facets": {}}],
                parent="Candid", subcategory="Party", source_path=source_path, source_label="Nest Roll Journey",
            )
            changed = catalog.rename_prompt_source_log(source_path, "Nest Roll Journey Redux")
            row = catalog.indexed_prompt_assets()[0]

        self.assertEqual(changed, 1)
        self.assertEqual(row["sources"][0]["source_path"], source_path)
        self.assertEqual(row["sources"][0]["source_label"], "Nest Roll Journey Redux")

    def test_prompt_source_log_move_updates_path_and_saved_manual_order_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            old_path = "Imported Logs/Dataset Creators/Woman.txt"
            next_path = "Imported Logs/Dataset Creators/Women.txt"
            catalog.import_prompt_assets(
                [{"value": "A portrait of a woman wearing OUTFIT.", "source_line": 1, "facets": {}}],
                parent="Dataset Creators", subcategory="Women", source_path=old_path, source_label="Woman",
            )
            catalog.set_creative_structure_order("template", {
                "parents": ["Dataset Creators"],
                "subcategories": {"Dataset Creators": ["Women"]},
                "logs": {"Dataset Creators": {"Women": [old_path]}},
            })
            changed = catalog.move_prompt_source_log(old_path, next_path, "Women")
            row = catalog.indexed_prompt_assets()[0]
            order = catalog.creative_structure_order("template")

        self.assertEqual(changed, 1)
        self.assertEqual(row["sources"][0]["source_path"], next_path)
        self.assertEqual(row["sources"][0]["source_label"], "Women")
        self.assertEqual(order["logs"]["Dataset Creators"]["Women"], [next_path])

    def test_legacy_last_import_structure_entry_is_hidden(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.set_creative_structure_order("prompt", {
                "parents": ["Saved & Imported"],
                "subcategories": {"Saved & Imported": ["Last Import", "Saved Prompts"]},
                "logs": {"Saved & Imported": {"Last Import": ["virtual"], "Saved Prompts": []}},
            })
            order = catalog.creative_structure_order("prompt")

        self.assertEqual(order["subcategories"]["Saved & Imported"], ["Saved Prompts"])
        self.assertNotIn("Last Import", order["logs"]["Saved & Imported"])

    def test_recipe_derived_prompt_ids_can_be_moved_archived_and_deleted_from_gallery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            prompt_id = "creative-prompt:synthetic-saved-recipe"
            moved = catalog.set_prompt_home([prompt_id], "Saved & Imported", "Keepers")
            home = catalog.prompt_override_map([prompt_id])[prompt_id]
            archived = catalog.set_prompt_archived([prompt_id], True)
            archived_row = catalog.prompt_override_map([prompt_id])[prompt_id]
            catalog.set_prompt_archived([prompt_id], False)
            result = catalog.delete_prompt_assets([prompt_id])
            deleted_row = catalog.prompt_override_map([prompt_id])[prompt_id]

        self.assertEqual(moved, 1)
        self.assertEqual(home["primary_parent"], "Saved & Imported")
        self.assertEqual(home["primary_subcategory"], "Keepers")
        self.assertEqual(int(home["home_override"]), 1)
        self.assertEqual(archived, 1)
        self.assertEqual(int(archived_row["archived"]), 1)
        self.assertEqual(result, {"deleted": 0, "archived": 1})
        self.assertEqual(int(deleted_row["archived"]), 1)

    def test_hard_delete_prompt_assets_removes_dependent_navigation_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            imported = catalog.import_prompt_assets(
                [{"value": "A portrait in a field", "source_line": 1, "facets": {}}],
                parent="Dataset Creators", subcategory="Women",
                source_path="Imported Logs/Dataset Creators/Women.txt", source_label="Women",
            )
            prompt_id = imported["prompt_ids"][0]
            folder = catalog.create_prompt_showcase_collection("prompt", "Keepers")
            catalog.add_prompts_to_collections([prompt_id], [folder["collection_id"]], "prompt")
            catalog.set_prompt_home([prompt_id], "Dataset Creators", "Women")
            result = catalog.hard_delete_prompt_assets([prompt_id])
            rows = catalog.indexed_prompt_assets()
            with catalog._connection() as db:
                memberships = db.execute("SELECT COUNT(*) FROM prompt_showcase_memberships WHERE prompt_id=?", (prompt_id,)).fetchone()[0]
                overrides = db.execute("SELECT COUNT(*) FROM prompt_overrides WHERE prompt_id=?", (prompt_id,)).fetchone()[0]

        self.assertEqual(result["deleted"], 1)
        self.assertEqual(rows, [])
        self.assertEqual(memberships, 0)
        self.assertEqual(overrides, 0)

    def test_prompt_source_log_can_be_removed_without_deleting_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            source_path = "Imported Logs/Candid/Party/Electric Forest.txt"
            imported = catalog.import_prompt_assets(
                [{"value": "Neon forest beat", "source_line": 7, "facets": {}}],
                parent="Candid", subcategory="Party", source_path=source_path, source_label="Electric Forest",
            )
            prompt_id = imported["prompt_ids"][0]
            changed = catalog.remove_prompt_source_log(source_path)
            rows = {row["prompt_id"]: row for row in catalog.indexed_prompt_assets()}

        self.assertEqual(changed, 1)
        self.assertIn(prompt_id, rows)
        self.assertEqual(rows[prompt_id]["sources"], [])
        self.assertEqual(rows[prompt_id]["source_count"], 0)

    def test_creative_library_state_returns_counts_and_revision_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.replace_prompt_index([
                {"prompt_id": "prompt:one", "kind": "prompt", "value": "A daylight portrait.", "primary_parent": "Portraits", "primary_subcategory": "General"},
                {"prompt_id": "template:one", "kind": "template", "value": "A poster for NAME.", "placeholder_signature": "NAME", "primary_parent": "Posters", "primary_subcategory": "Graphic"},
            ], [], signature="state")
            catalog.upsert_recipe_component("scene", "a quiet studio", manual=True)
            revisions = catalog.creative_library_revisions()
            counts = catalog.creative_library_counts()

        self.assertEqual(set(revisions), {"recipes", "prompts", "fragments", "components"})
        self.assertEqual(counts["prompts"], 1)
        self.assertEqual(counts["templates"], 1)
        self.assertEqual(counts["scenes"], 1)

    def test_creative_library_counts_do_not_hide_safe_words_containing_child(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.replace_prompt_index([
                {"prompt_id": "prompt:one", "kind": "prompt", "value": "A portrait at a children's fireworks show.", "primary_parent": "Portraits", "primary_subcategory": "Events"},
            ], [], signature="safe-count")
            counts = catalog.creative_library_counts()
        self.assertEqual(counts["prompts"], 1)


if __name__ == "__main__":
    unittest.main()
