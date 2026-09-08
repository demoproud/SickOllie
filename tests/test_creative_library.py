from __future__ import annotations

import importlib.util
import csv
import json
import sys
import tempfile
import types
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = types.ModuleType("sickollie_creative_library_test")
PACKAGE.__path__ = [str(ROOT)]
sys.modules.setdefault("sickollie_creative_library_test", PACKAGE)

CATALOG_SPEC = importlib.util.spec_from_file_location("sickollie_creative_library_test.solo_catalog", ROOT / "solo_catalog.py")
assert CATALOG_SPEC and CATALOG_SPEC.loader
catalog_module = importlib.util.module_from_spec(CATALOG_SPEC)
sys.modules[CATALOG_SPEC.name] = catalog_module
CATALOG_SPEC.loader.exec_module(catalog_module)

RECIPE_SPEC = importlib.util.spec_from_file_location("sickollie_creative_library_test.solo_recipe_catalog", ROOT / "solo_recipe_catalog.py")
assert RECIPE_SPEC and RECIPE_SPEC.loader
recipe_module = importlib.util.module_from_spec(RECIPE_SPEC)
sys.modules[RECIPE_SPEC.name] = recipe_module
RECIPE_SPEC.loader.exec_module(recipe_module)


def recipe_payload(source: str, resolved: str = "", placeholders=None) -> dict:
    return {
        "nodes": [{
            "type": recipe_module.STUDIO_PROMPT,
            "widgets": [
                {"name": "prompt_source", "value": "manual"},
                {"name": "manual_prompt", "value": source},
            ],
        }],
        "summary": {
            "prompt_template": source,
            "resolved_prompt": resolved,
            "placeholders": list(placeholders or []),
        },
    }


class CreativeLibraryTests(unittest.TestCase):
    def test_preview_metadata_platter_extracts_outfit_slots_and_scene(self) -> None:
        payload = recipe_payload("NAME in OUTFIT_A at SCENE", "NAME in silver at a studio", [
            {"token": "OUTFIT_A", "widget": "outfit_log_file_A", "value": "silver halter dress"},
            {"token": "OUTFIT_B", "widget": "outfit_log_file_B", "value": "white platform boots"},
            {"token": "SCENE", "widget": "scene_log_file", "value": "mirrored photo studio"},
            {"token": "NAME", "widget": "name_value", "value": "Tiffany"},
        ])
        self.assertEqual(recipe_module._payload_prompt_preview_metadata(payload), {
            "outfit_a": "silver halter dress",
            "outfit_b": "white platform boots",
            "scene": "mirrored photo studio",
        })

    def test_curated_tree_is_explicit_about_tabs_and_uses_folder_homes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Curated Library"
            (root / "Prompts" / "Candid" / "Girlfriend").mkdir(parents=True)
            (root / "Prompts" / "Wearing OUTFIT").mkdir(parents=True)
            (root / "Templates" / "SCENE+OUTFIT+BRAND").mkdir(parents=True)
            shared = "A candid phone photograph of a young woman smiling beside a window."
            outfit_prompt = "A young woman wearing OUTFIT in a bright apartment, direct phone flash."
            template = "Vintage magazine photograph of SCENE featuring OUTFIT and crisp BRAND lettering."
            (root / "Prompts" / "Candid" / "Girlfriend" / "Casual Candids.txt").write_text(shared + "\n", encoding="utf-8")
            (root / "Prompts" / "Wearing OUTFIT" / "Candid Girlfriend_OUTFIT.txt").write_text(outfit_prompt + "\n", encoding="utf-8")
            (root / "Templates" / "SCENE+OUTFIT+BRAND" / "Vintage Magazine.txt").write_text(template + "\n", encoding="utf-8")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                result = recipe_module._ensure_prompt_corpus_index(root, force=True)
                snapshot = recipe_module._prompt_asset_snapshot(ensure_corpus=False)
            finally:
                recipe_module.get_catalog = original_catalog

        self.assertEqual(result["prompts"], 3)
        self.assertEqual(len(snapshot["prompts"]), 1)
        self.assertEqual(len(snapshot["templates"]), 2)
        outfit_template = next(item for item in snapshot["templates"] if item["value"] == outfit_prompt)
        self.assertEqual(outfit_template["primary_home"], "Wearing OUTFIT / Candid Girlfriend_OUTFIT")
        explicit_template = next(item for item in snapshot["templates"] if item["value"] == template)
        self.assertEqual(explicit_template["primary_home"], "SCENE+OUTFIT+BRAND / Vintage Magazine")
        self.assertEqual(explicit_template["placeholder_signature"], "OUTFIT+BRAND+SCENE")

    def test_fresh_install_has_no_bundled_creative_library_and_snapshot_does_not_auto_rehydrate(self) -> None:
        self.assertFalse((ROOT / "Starter Content" / "input" / "SickOllieLogs").exists())
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_catalog = recipe_module.get_catalog
            original_ensure = recipe_module._ensure_prompt_corpus_index
            recipe_module.get_catalog = lambda: catalog
            recipe_module._ensure_prompt_corpus_index = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("normal snapshot must not auto-index source logs"))
            try:
                snapshot = recipe_module._prompt_asset_snapshot()
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._ensure_prompt_corpus_index = original_ensure

        self.assertEqual(len(snapshot["prompts"]), 0)
        self.assertEqual(len(snapshot["templates"]), 0)

    def test_prompt_purge_preserves_templates_components_and_recipe_used_folders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.replace_prompt_index([
                {"prompt_id": "prompt:one", "kind": "prompt", "value": "Ready prompt one", "primary_parent": "Candid", "primary_subcategory": "Phone"},
                {"prompt_id": "template:one", "kind": "template", "value": "Template NAME", "primary_parent": "NAME", "primary_subcategory": "Variety"},
            ], [], signature="before")
            catalog.set_prompt_preview("prompt:one", "prompt-one.webp")
            catalog.set_prompt_preview("template:one", "template-one.webp")
            catalog.set_prompt_rating("template:one", 5)
            prompt_only = catalog.create_prompt_showcase_collection("prompt", "Prompt only")
            shared_showcase = catalog.create_prompt_showcase_collection("prompt", "Saved Recipe folder")
            shared = catalog.create_recipe_collection("Saved Recipe folder")
            catalog.add_prompts_to_collections(["prompt:one"], [prompt_only["collection_id"], shared_showcase["collection_id"]])
            catalog.save_recipe("recipe:one", "Saved Recipe", {"nodes": []})
            catalog.set_recipe_collections("recipe:one", [shared["collection_id"]])
            outfit = catalog.upsert_recipe_component("outfit", "pink tank and shorts", manual=True)
            scene = catalog.upsert_recipe_component("scene", "sunlit apartment", manual=True)

            result = catalog.purge_prompt_library("prompt")
            remaining = catalog.indexed_prompt_assets()
            remaining_collections = catalog.recipe_collections()
            remaining_outfit = catalog.recipe_component_by_value("outfit", "pink tank and shorts")
            remaining_scene = catalog.recipe_component_by_value("scene", "sunlit apartment")

        self.assertEqual(result["assets"], 1)
        self.assertEqual(result["preview_refs"], ["prompt-one.webp"])
        self.assertEqual(result["collections_deleted"], 2)
        self.assertEqual([item["prompt_id"] for item in remaining], ["template:one"])
        self.assertEqual(remaining[0]["preview_ref"], "template-one.webp")
        self.assertEqual(remaining[0]["rating"], 5)
        self.assertEqual([item["name"] for item in remaining_collections], ["Saved Recipe folder"])
        self.assertEqual(remaining_outfit["component_id"], outfit["component_id"])
        self.assertEqual(remaining_scene["component_id"], scene["component_id"])

    def test_library_purges_clear_saved_structure_order_for_purged_scopes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.set_creative_structure_order("prompt", {"parents": ["Candid", "Editorial"]})
            catalog.set_creative_structure_order("template", {"parents": ["NAME", "OUTFIT"]})
            catalog.set_creative_structure_order("outfit", {"categories": ["Casual", "Editorial"]})
            catalog.set_creative_structure_order("scene", {"categories": ["Urban", "Beach"]})
            catalog.set_creative_structure_order("recipe", {"collections": ["Favorites"]})

            catalog.purge_prompt_library("prompt")
            catalog.purge_components("outfit")

            self.assertEqual(catalog.creative_structure_order("prompt"), {})
            self.assertEqual(catalog.creative_structure_order("outfit"), {})
            self.assertNotEqual(catalog.creative_structure_order("template"), {})
            self.assertNotEqual(catalog.creative_structure_order("scene"), {})
            self.assertNotEqual(catalog.creative_structure_order("recipe"), {})

            catalog.purge_pack_registry()

            self.assertEqual(catalog.creative_structure_order("template"), {})
            self.assertEqual(catalog.creative_structure_order("scene"), {})
            self.assertEqual(catalog.creative_structure_order("recipe"), {})

    def test_prompt_log_import_normalizes_deduplicates_and_routes_templates(self) -> None:
        prompt = "A candid analog portrait beside a neon motel sign."
        prepared = recipe_module._prepare_prompt_import([
            prompt,
            f"  {prompt.upper()}  ",
            "Poster artwork displaying NAME above the subject.",
            "",
            "A quiet editorial portrait in a rain-streaked diner.",
        ], "Travel & Adventure", "Roadside")

        self.assertEqual([item["value"] for item in prepared["prompt_items"]], [
            prompt,
            "A quiet editorial portrait in a rain-streaked diner.",
        ])
        self.assertEqual([item["value"] for item in prepared["template_items"]], [
            "Poster artwork displaying NAME above the subject.",
        ])
        self.assertEqual(prepared["input_duplicates"], 1)
        self.assertEqual(prepared["template_routed"], 1)
        self.assertEqual(prepared["blank"], 1)
        for item in prepared["items"]:
            self.assertEqual(item["facets"]["parent"], ["Travel & Adventure"])
            self.assertEqual(item["facets"]["subcategory"], ["Roadside"])
        self.assertEqual([item["source_line"] for item in prepared["items"]], [1, 3, 5])

    def test_prompt_source_logs_are_browsable_and_sort_in_original_line_order(self) -> None:
        nest_path = "Candid/Party/Nest Roll Journey.txt"
        electric_path = "Candid/Party/Electric Forest.txt"
        assets = [
            {
                "prompt_id": "nest-three", "value": "The third narrative beat", "name": "Third",
                "primary_parent": "Candid", "primary_subcategory": "Party", "rating": 0,
                "facets": {}, "placeholder_signature": "",
                "sources": [{"source_path": nest_path, "source_label": "Nest Roll Journey", "line_number": 3}],
            },
            {
                "prompt_id": "electric-two", "value": "Electric forest beat", "name": "Electric",
                "primary_parent": "Candid", "primary_subcategory": "Party", "rating": 0,
                "facets": {}, "placeholder_signature": "",
                "sources": [{"source_path": electric_path, "source_label": "Electric Forest", "line_number": 2}],
            },
            {
                "prompt_id": "nest-one", "value": "The opening narrative beat", "name": "Opening",
                "primary_parent": "Candid", "primary_subcategory": "Party", "rating": 0,
                "facets": {}, "placeholder_signature": "",
                "sources": [{"source_path": nest_path, "source_label": "Nest Roll Journey", "line_number": 1}],
            },
        ]

        homes = recipe_module._prompt_home_counts(assets)
        filtered = recipe_module._filter_prompt_assets(
            assets, parent="Candid", subcategory="Party", log_path=nest_path, sort="source_order"
        )

        self.assertEqual(homes["logs"]["Candid"]["Party"][nest_path], {"label": "Nest Roll Journey", "count": 2})
        self.assertEqual(homes["logs"]["Candid"]["Party"][electric_path], {"label": "Electric Forest", "count": 1})
        self.assertEqual([row["prompt_id"] for row in filtered], ["nest-one", "nest-three"])

    def test_prompt_home_counts_respect_manual_structure_order_and_empty_folders(self) -> None:
        assets = [
            {"prompt_id": "a", "value": "A", "primary_parent": "Candid", "primary_subcategory": "Party", "sources": [{"source_path": "Candid/Party/Zeta.txt", "source_label": "Zeta", "line_number": 1}]},
            {"prompt_id": "b", "value": "B", "primary_parent": "Editorial", "primary_subcategory": "Studio", "sources": [{"source_path": "Editorial/Studio/Alpha.txt", "source_label": "Alpha", "line_number": 1}]},
            {"prompt_id": "c", "value": "C", "primary_parent": "Candid", "primary_subcategory": "Party", "sources": [{"source_path": "Candid/Party/Alpha.txt", "source_label": "Alpha", "line_number": 2}]},
        ]
        order = {
            "parents": ["Empty Category", "Editorial", "Candid"],
            "subcategories": {"Empty Category": ["Ready Later"], "Candid": ["Party"], "Editorial": ["Studio"]},
            "logs": {"Candid": {"Party": ["Candid/Party/Zeta.txt", "Candid/Party/Alpha.txt"]}},
        }
        homes = recipe_module._prompt_home_counts(assets, order)

        self.assertEqual(list(homes["parents"]), ["Empty Category", "Editorial", "Candid"])
        self.assertEqual(homes["parents"]["Empty Category"], 0)
        self.assertEqual(list(homes["subcategories"]["Empty Category"]), ["Ready Later"])
        self.assertEqual(list(homes["logs"]["Candid"]["Party"]), ["Candid/Party/Zeta.txt", "Candid/Party/Alpha.txt"])

    def test_import_prompt_assets_keeps_log_provenance_and_line_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            result = catalog.import_prompt_assets(
                [
                    {"value": "Opening scene", "facets": {}, "source_line": 1},
                    {"value": "Progressive scene", "facets": {}, "source_line": 4},
                ],
                parent="Candid",
                subcategory="Party",
                source_path="Imported Logs/Candid/Party/Nest Roll Journey.txt",
                source_label="Nest Roll Journey",
            )
            assets = catalog.indexed_prompt_assets()

        self.assertEqual(result["source_links_added"], 2)
        self.assertEqual(result["source_label"], "Nest Roll Journey")
        by_value = {row["value"]: row for row in assets}
        self.assertEqual(by_value["Opening scene"]["sources"], [{
            "source_path": "Imported Logs/Candid/Party/Nest Roll Journey.txt",
            "line_number": 1,
            "source_label": "Nest Roll Journey",
        }])
        self.assertEqual(by_value["Progressive scene"]["sources"][0]["line_number"], 4)
        self.assertEqual(by_value["Opening scene"]["source_count"], 1)
        self.assertEqual(by_value["Opening scene"]["exact_source_occurrences"], 1)

    def test_prompt_log_import_allows_a_category_only_home(self) -> None:
        prepared = recipe_module._prepare_prompt_import(
            ["A resolved daylight portrait.", "A portrait of NAME wearing OUTFIT."],
            "One Level Only",
            "",
        )
        self.assertEqual(prepared["subcategory"], "")
        self.assertEqual(len(prepared["prompt_items"]), 1)
        self.assertEqual(len(prepared["template_items"]), 1)
        self.assertNotIn("subcategory", prepared["items"][0]["facets"])

        assets = [
            {
                "prompt_id": item["kind"], "value": item["value"],
                "primary_parent": "One Level Only", "primary_subcategory": "",
                "sources": [{"source_path": "Imported Logs/One Level Only/Release.txt", "source_label": "Release", "line_number": index}],
            }
            for index, item in enumerate(prepared["items"], 1)
        ]
        homes = recipe_module._prompt_home_counts(assets)
        self.assertEqual(homes["subcategories"]["One Level Only"][""], 2)
        self.assertEqual(homes["logs"]["One Level Only"][""]["Imported Logs/One Level Only/Release.txt"]["count"], 2)

    def test_identity_bearing_image_metadata_never_creates_a_resolved_prompt(self) -> None:
        source = "NAME enters SCENE wearing OUTFIT beside BRAND lettering."
        resolved = "Phoebe enters a neon diner wearing a pink slip dress beside Sick Ollie lettering."
        recipe = {
            "recipe_id": "recipe:identity-safe",
            "name": "Identity safe import",
            "created_at": "2026-09-02T00:00:00Z",
            "payload": recipe_payload(source, resolved, [
                {"token": "NAME", "value": "Phoebe", "widget": "name_value"},
                {"token": "BRAND", "value": "Sick Ollie", "widget": "item_value"},
                {"token": "OUTFIT", "value": "a pink slip dress", "widget": "outfit_log_file_A"},
                {"token": "SCENE", "value": "a neon diner", "widget": "scene_log_file"},
            ]),
        }
        assets = recipe_module._recipe_prompt_assets([recipe])
        self.assertEqual([asset["kind"] for asset in assets], ["template"])
        self.assertEqual(assets[0]["resolved_value"], "NAME enters a neon diner wearing a pink slip dress beside BRAND lettering.")
        self.assertNotIn("Phoebe", assets[0]["resolved_value"])
        self.assertNotIn("Sick Ollie", assets[0]["resolved_value"])

    def test_imported_prompt_log_copy_is_managed_and_does_not_touch_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_root = root / "input"
            input_root.mkdir()
            original = root / "Nest Roll Journey.txt"
            original_text = "first beat\nsecond beat\n"
            original.write_text(original_text, encoding="utf-8")
            fake_folder_paths = types.ModuleType("folder_paths")
            fake_folder_paths.get_input_directory = lambda: str(input_root)
            prior = sys.modules.get("folder_paths")
            sys.modules["folder_paths"] = fake_folder_paths
            try:
                relative, copied = recipe_module._save_imported_prompt_log(
                    original.read_text(encoding="utf-8"), "Candid", "Party", "Nest Roll Journey"
                )
            finally:
                if prior is None:
                    sys.modules.pop("folder_paths", None)
                else:
                    sys.modules["folder_paths"] = prior

            self.assertEqual(relative, "Imported Logs/Candid/Party/Nest Roll Journey.txt")
            self.assertEqual(copied, input_root / "SickOllieLogs" / "prompts" / "Imported Logs" / "Candid" / "Party" / "Nest Roll Journey.txt")
            self.assertEqual(copied.read_text(encoding="utf-8"), original_text)
            self.assertEqual(original.read_text(encoding="utf-8"), original_text)

    def test_managed_log_rename_moves_existing_txt_without_leaving_woman_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_root = root / "input"; input_root.mkdir()
            fake_folder_paths = types.ModuleType("folder_paths")
            fake_folder_paths.get_input_directory = lambda: str(input_root)
            prior = sys.modules.get("folder_paths")
            sys.modules["folder_paths"] = fake_folder_paths
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            source_path = "Imported Logs/Dataset Creators/Woman.txt"
            imported = input_root / "SickOllieLogs" / "prompts" / source_path
            imported.parent.mkdir(parents=True)
            imported.write_text("A woman wearing OUTFIT in a daylight studio.\n", encoding="utf-8")
            catalog.import_prompt_assets(
                [{"value": "A woman wearing OUTFIT in a daylight studio.", "source_line": 1, "facets": {}}],
                parent="Dataset Creators", subcategory="Women", source_path=source_path, source_label="Woman",
            )
            catalog.set_creative_structure_order("template", {
                "parents": ["Dataset Creators"],
                "subcategories": {"Dataset Creators": ["Women"]},
                "logs": {"Dataset Creators": {"Women": [source_path]}},
            })
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                result = recipe_module._rename_prompt_source_file(source_path, "Women")
            finally:
                recipe_module.get_catalog = original_catalog
                if prior is None: sys.modules.pop("folder_paths", None)
                else: sys.modules["folder_paths"] = prior

            txt_files = list(imported.parent.glob("*.txt"))
            row = catalog.indexed_prompt_assets()[0]

        self.assertEqual(result["source_path"], "Imported Logs/Dataset Creators/Women.txt")
        self.assertEqual([path.name for path in txt_files], ["Women.txt"])
        self.assertEqual(row["sources"][0]["source_path"], result["source_path"])

    def test_permanent_category_delete_removes_stale_txts_and_mixed_log_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_root = root / "input"; input_root.mkdir()
            preview_root = root / "previews"; preview_root.mkdir()
            fake_folder_paths = types.ModuleType("folder_paths")
            fake_folder_paths.get_input_directory = lambda: str(input_root)
            prior = sys.modules.get("folder_paths")
            sys.modules["folder_paths"] = fake_folder_paths
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            source_path = "Imported Logs/Dataset Creators/Women.txt"
            source_folder = input_root / "SickOllieLogs" / "prompts" / "Imported Logs" / "Dataset Creators"
            source_folder.mkdir(parents=True)
            (source_folder / "Women.txt").write_text("A woman wearing OUTFIT.\nA resolved portrait.\n", encoding="utf-8")
            (source_folder / "Woman.txt").write_text("stale duplicate\n", encoding="utf-8")
            (source_folder / "Unsorted.txt").write_text("stale duplicate\n", encoding="utf-8")
            catalog.import_prompt_assets(
                [{"value": "A woman wearing OUTFIT.", "source_line": 1, "facets": {}}],
                parent="Dataset Creators", subcategory="Women", source_path=source_path, source_label="Women",
            )
            catalog.import_prompt_assets(
                [{"value": "A resolved portrait.", "source_line": 2, "facets": {}}],
                parent="Dataset Creators", subcategory="Women", source_path=source_path, source_label="Women",
            )
            original_catalog = recipe_module.get_catalog
            original_preview = recipe_module._preview_directory
            recipe_module.get_catalog = lambda: catalog
            recipe_module._preview_directory = lambda: preview_root
            try:
                result = recipe_module._delete_prompt_structure_scope("template", "Dataset Creators")
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._preview_directory = original_preview
                if prior is None: sys.modules.pop("folder_paths", None)
                else: sys.modules["folder_paths"] = prior

            rows = catalog.indexed_prompt_assets()

        self.assertEqual(result["txt_files_deleted"], 3)
        self.assertEqual(result["deleted"], 2)
        self.assertFalse(source_folder.exists())
        self.assertEqual(rows, [])

    def test_generated_prompt_mirror_prunes_stale_renamed_and_unsorted_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stale = root / "Templates" / "Dataset Creators"
            stale.mkdir(parents=True)
            for name in ("Woman.txt", "Women.txt", "Unsorted.txt"):
                (stale / name).write_text("stale\n", encoding="utf-8")
            result = recipe_module._sync_creative_prompt_asset_logs(root, [], [])

        self.assertEqual(result["removed_catalog_files"], 3)
        self.assertFalse(stale.exists())

    def test_one_pass_prompt_filter_metadata_keeps_context_sensitive_counts(self) -> None:
        assets = [
            {"prompt_id": "one", "value": "Analog portrait", "name": "One", "primary_parent": "Portraits", "primary_subcategory": "General", "facets": {"style": ["Analog"], "cast": ["Solo"]}, "placeholder_signature": "", "rating": 5},
            {"prompt_id": "two", "value": "Editorial portrait", "name": "Two", "primary_parent": "Portraits", "primary_subcategory": "Editorial", "facets": {"style": ["Editorial"], "cast": ["Solo"]}, "placeholder_signature": "", "rating": 4},
            {"prompt_id": "three", "value": "Analog travel", "name": "Three", "primary_parent": "Travel", "primary_subcategory": "Roadside", "facets": {"style": ["Analog"], "cast": ["Duo"]}, "placeholder_signature": "", "rating": 3},
        ]
        result = recipe_module._prompt_filter_metadata(
            assets,
            facets={"style": "Analog", "cast": "Solo"},
            parent="Portraits",
            rating="4plus",
        )

        self.assertEqual([row["prompt_id"] for row in result["visible"]], ["one"])
        self.assertEqual(result["facet_counts"]["style"], {"Analog": 1, "Editorial": 1})
        self.assertEqual(result["facet_counts"]["cast"], {"Solo": 1})
        self.assertEqual(result["home_counts"]["parents"], {"Portraits": 1})
        self.assertEqual(result["home_counts"]["subcategories"], {"Portraits": {"General": 1}})

    def test_moved_prompt_browses_from_canonical_home_despite_stale_source_facets(self) -> None:
        moved = {
            "prompt_id": "moved", "value": "A portrait beside a motel sign", "name": "Moved",
            "primary_parent": "Travel", "primary_subcategory": "Roadside",
            "facets": {"parent": ["Portraits"], "subcategory": ["Studio"], "style": ["Editorial"]},
            "placeholder_signature": "", "rating": 0,
        }
        result = recipe_module._prompt_filter_metadata(
            [moved], facets={"parent": "Travel", "subcategory": "Roadside"},
            parent="Travel", subcategory="Roadside",
        )
        self.assertEqual([row["prompt_id"] for row in result["visible"]], ["moved"])

    def test_state_counts_make_browsable_and_stored_assets_explicit(self) -> None:
        class CatalogStub:
            def creative_library_counts(self):
                return {"prompts": 2, "templates": 1, "outfits": 4, "scenes": 3, "wardrobe": 5, "fragments": 0, "recipes": 1, "boards": 0}

            def creative_library_revisions(self):
                return {"recipes": "1", "prompts": "2", "fragments": "0", "components": "7"}

        original_catalog = recipe_module.get_catalog
        original_snapshot = recipe_module._prompt_asset_snapshot
        try:
            recipe_module.get_catalog = lambda: CatalogStub()
            recipe_module._prompt_asset_snapshot = lambda: {"prompts": [{}, {}, {}], "templates": [{}, {}]}
            state = recipe_module._creative_library_state_payload()
        finally:
            recipe_module.get_catalog = original_catalog
            recipe_module._prompt_asset_snapshot = original_snapshot
        self.assertEqual(state["counts"]["prompts"], 3)
        self.assertEqual(state["counts"]["templates"], 2)
        self.assertEqual(state["stored_counts"]["prompts"], 2)
        self.assertEqual(state["derived_counts"], {"prompts": 1, "templates": 1})

    def test_prompt_corpus_index_is_canonical_source_linked_and_excludes_managed_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "prompts"
            (root / "Standard").mkdir(parents=True)
            (root / "Masters").mkdir()
            (root / "Creative Library").mkdir()
            (root / "Fragments").mkdir()
            first = "Candid portrait in a neon alley, direct on-camera flash."
            second = "Wide environmental portrait at dawn, soft window light."
            (root / "Standard" / "Neon.txt").write_text(f"{first}\n{second}\n", encoding="utf-8")
            (root / "Masters" / "Neon Master.txt").write_text(f"{first.upper()}\n", encoding="utf-8")
            (root / "Creative Library" / "MASTER - Ready Prompts.txt").write_text("generated duplicate\n", encoding="utf-8")
            (root / "Fragments" / "Poster Prefix — 1.txt").write_text("curated prefix\n", encoding="utf-8")
            original_bytes = (root / "Standard" / "Neon.txt").read_bytes()
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                result = recipe_module._ensure_prompt_corpus_index(root, force=True)
                assets = catalog.indexed_prompt_assets()
            finally:
                recipe_module.get_catalog = original_catalog

        self.assertEqual(result["prompts"], 2)
        self.assertEqual(result["sources"], 3)
        self.assertEqual(len(assets), 2)
        duplicate = next(item for item in assets if item["value"].casefold() == first.casefold())
        self.assertEqual(len(duplicate["sources"]), 2)
        self.assertTrue(all("Creative Library" not in source["source_path"] for item in assets for source in item["sources"]))
        self.assertEqual(original_bytes, f"{first}\n{second}\n".encode("utf-8"))

    def test_manifest_corpus_splits_templates_prompts_and_assigns_one_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Canonical Corpus"
            manifests = root / "Manifests"
            manifests.mkdir(parents=True)
            fields = [
                "record_id", "kind", "primary_parent", "primary_subcategory", "primary_home",
                "placeholders", "styles", "cast", "content", "time", "shot", "quality_score",
                "exact_source_occurrences", "near_cluster_id", "text",
            ]
            rows = [
                {
                    "record_id": "NP-one", "kind": "prompt", "primary_parent": "Travel & Places",
                    "primary_subcategory": "Roadside Stops", "primary_home": "Travel & Places / Roadside Stops",
                    "placeholders": "", "styles": "Analog", "cast": "Solo", "content": "No Typography",
                    "time": "Night", "shot": "Candid", "quality_score": "91",
                    "exact_source_occurrences": "4", "near_cluster_id": "NC-one",
                    "text": "A candid analog photo of a young woman beside a roadside diner at night.",
                },
                {
                    "record_id": "NT-one", "kind": "template", "primary_parent": "Graphic & Editorial",
                    "primary_subcategory": "Poster Systems", "primary_home": "Graphic & Editorial / Poster Systems",
                    "placeholders": "NAME | SCENE", "styles": "Poster", "cast": "Solo", "content": "Typography",
                    "time": "", "shot": "Portrait", "quality_score": "88",
                    "exact_source_occurrences": "2", "near_cluster_id": "",
                    "text": "Editorial poster portrait of NAME inside SCENE.",
                },
            ]
            with (manifests / "catalog.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader(); writer.writerows(rows)
            provenance = [
                {"representative_id": "NP-one", "source_file": "UV Night Batch Test.txt", "source_line": 7},
                {"representative_id": "NT-one", "source_file": "Unrelated Filename.txt", "source_line": 3},
            ]
            (manifests / "provenance.jsonl").write_text("".join(json.dumps(row) + "\n" for row in provenance), encoding="utf-8")
            (manifests / "validation.json").write_text("{}\n", encoding="utf-8")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                recipe_module._ensure_prompt_corpus_index(root, force=True)
                snapshot = recipe_module._prompt_asset_snapshot(ensure_corpus=False)
            finally:
                recipe_module.get_catalog = original_catalog

        self.assertEqual(len(snapshot["prompts"]), 1)
        self.assertEqual(len(snapshot["templates"]), 1)
        self.assertEqual(snapshot["prompts"][0]["primary_home"], "Travel & Places / Roadside Stops")
        self.assertEqual(snapshot["prompts"][0]["facets"]["parent"], ["Travel & Places"])
        self.assertNotIn("UV Night", snapshot["prompts"][0]["facets"].get("parent", []))
        self.assertEqual(
            [item["prompt_id"] for item in recipe_module._filter_prompt_assets(snapshot["templates"], placeholders=["NAME", "SCENE"])],
            ["NT-one"],
        )
        self.assertEqual(recipe_module._filter_prompt_assets(snapshot["templates"], placeholders=["NAME", "OUTFIT"]), [])

    def test_prompt_rating_and_preview_survive_deterministic_index_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            asset = {
                "prompt_id": "NP-stable", "kind": "prompt", "value": "A neutral studio portrait of a young woman.",
                "primary_parent": "Portraits", "primary_subcategory": "Studio", "quality_score": 80,
            }
            catalog.replace_prompt_index([asset], [], signature="one")
            catalog.set_prompt_rating("NP-stable", 5, "favorite")
            catalog.set_prompt_preview("NP-stable", "prompt-preview.webp", resolved_seed=8675309)
            catalog.replace_prompt_index([asset | {"quality_score": 82}], [], signature="two")
            refreshed = catalog.indexed_prompt_assets()[0]

        self.assertEqual(refreshed["rating"], 5)
        self.assertEqual(refreshed["note"], "favorite")
        self.assertEqual(refreshed["preview_ref"], "prompt-preview.webp")
        self.assertTrue(refreshed["preview_updated_at"])
        self.assertEqual(refreshed["resolved_seed"], 8675309)
        derived = recipe_module._recipe_prompt_assets([], [refreshed])[0]
        self.assertEqual(derived["preview_updated_at"], refreshed["preview_updated_at"])
        self.assertEqual(derived["resolved_seed"], 8675309)
        self.assertEqual(refreshed["quality_score"], 82)

    def test_fragment_miner_uses_recurring_clauses_themes_and_curated_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "prompts"
            (root / "Standard").mkdir(parents=True)
            (root / "Masters").mkdir()
            (root / "Fragments").mkdir()
            shared = "direct on-camera flash"
            first_lines = [f"Candid portrait number {index} in a neon alley, {shared}, subtle 35mm film grain." for index in range(3)]
            second_lines = [f"Editorial portrait number {index} by a motel, {shared}, subtle 35mm film grain." for index in range(3, 6)]
            (root / "Standard" / "Neon Night — Prompt Log — 3.txt").write_text("\n".join(first_lines) + "\n", encoding="utf-8")
            (root / "Masters" / "Neon Night — Master — 3.txt").write_text("\n".join(second_lines) + "\n", encoding="utf-8")
            (root / "Fragments" / "Poster Prefix Comfy — Prefix — 1.txt").write_text("award-winning editorial poster of\n", encoding="utf-8")
            (root / "Fragments" / "Typography — Suffix — 1.txt").write_text("BRAND typography remains crisp and legible\n", encoding="utf-8")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                recipe_module._ensure_prompt_corpus_index(root, force=True)
                result = recipe_module._ensure_fragment_index(force=True, prompt_root=root)
                lighting = catalog.fragments(query=shared, role="lighting", state="active", limit=10)["fragments"]
                curated = catalog.fragments(state="approved", limit=10)["fragments"]
                concepts = catalog.fragments(role="concept", state="active", limit=10)["fragments"]
                prompt = recipe_module._prompt_asset_snapshot(ensure_corpus=False)["prompts"][0]
                decomposed = recipe_module._decompose_prompt_for_builder(prompt["prompt_id"])
            finally:
                recipe_module.get_catalog = original_catalog

        self.assertGreaterEqual(result["total"], 5)
        self.assertEqual(lighting[0]["prompt_count"], 6)
        self.assertEqual(lighting[0]["source_count"], 2)
        self.assertEqual({item["role"] for item in curated}, {"prefix", "suffix"})
        self.assertTrue(any("Neon Night" in item["value"] for item in concepts))
        self.assertTrue(any(segment["fragment_id"] for segment in decomposed["segments"]))
        self.assertIn(shared, " ".join(segment["original_text"] for segment in decomposed["segments"]))
        self.assertTrue(all(segment["source_segment"] for segment in decomposed["segments"]))

    def test_fragment_review_survives_atomic_miner_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            row = {
                "role": "lighting", "value": "direct on-camera flash", "confidence": 0.9,
                "review_state": "suggested", "source_prompt_ids": ["prompt:one"],
                "source_files": [{"source_path": "Standard/Flash.txt"}],
            }
            catalog.replace_mined_fragments([row], signature="one")
            fragment = catalog.fragments(state="active", limit=1)["fragments"][0]
            catalog.set_fragment_review(fragment["fragment_id"], "approved", 5)
            catalog.replace_mined_fragments([row | {"confidence": 0.95}], signature="two")
            refreshed = catalog.fragments(state="active", limit=1)["fragments"][0]

        self.assertEqual(refreshed["review_state"], "approved")
        self.assertEqual(refreshed["rating"], 5)
        self.assertEqual(refreshed["confidence"], 0.95)

    def test_bulk_fragment_review_and_category_override_scale_and_survive_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            rows = [{
                "role": "lighting", "value": f"batch lighting ingredient {index}", "confidence": 0.8,
                "review_state": "review", "source_prompt_ids": [f"prompt:{index}"],
                "source_files": [{"source_path": f"Standard/Batch-{index % 3}.txt"}],
            } for index in range(1200)]
            catalog.replace_mined_fragments(rows, signature="before")
            result = catalog.bulk_update_fragments(
                all_filtered=True, query="batch lighting", role="lighting", state_filter="review",
                review_state="approved", new_role="style",
            )
            changed = catalog.fragments(role="style", state="approved", limit=1300)
            catalog.replace_mined_fragments(rows, signature="after")
            rebuilt = catalog.fragments(role="style", state="approved", limit=1300)

        self.assertEqual(result, {"selected": 1200, "changed": 1200, "merged": 0})
        self.assertEqual(changed["total"], 1200)
        self.assertEqual(rebuilt["total"], 1200)
        self.assertTrue(all(item["role_override"] == "style" and item["mined_role"] == "lighting" for item in rebuilt["fragments"]))

    def test_subject_miner_harvests_people_not_photo_wrappers(self) -> None:
        prompts = []
        subjects = ["young woman", "mature woman", "elderly man", "obese man"]
        for subject_index, subject in enumerate(subjects):
            for source_index in range(2):
                prompts.append({
                    "prompt_id": f"prompt:{subject_index}:{source_index}",
                    "value": f"Photograph of NAME wearing a pink headband, {subject} standing beneath direct flash lighting",
                    "sources": [{"source_path": f"Standard/Subject-{source_index}.txt"}],
                })
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                mined = recipe_module._mine_prompt_fragments(prompts)
            finally:
                recipe_module.get_catalog = original_catalog

        subject_values = {item["value"] for item in mined if item["role"] == "subject"}
        accessory_values = {item["value"] for item in mined if item["role"] == "accessory"}
        identity_values = {item["value"] for item in mined if item["role"] == "identity_hook"}
        self.assertTrue(set(subjects).issubset(subject_values))
        self.assertIn("wearing a pink headband", accessory_values)
        self.assertEqual(identity_values, {"NAME"})
        self.assertFalse(any("photo" in value.casefold() or "photograph" in value.casefold() for value in subject_values))
        self.assertEqual(recipe_module._fragment_role("NAME"), "identity_hook")
        self.assertEqual(recipe_module._fragment_role("name"), "")

    def test_prompt_discovery_facets_are_deterministic_and_non_destructive(self) -> None:
        prompt = "Candid full-body analog fashion photograph on a neon city street at night, playful coy expression."
        facets = recipe_module._prompt_facets(prompt)
        self.assertIn("Full body", facets["structure"])
        self.assertIn("Candid", facets["structure"])
        self.assertIn("Analog", facets["style"])
        self.assertIn("Urban", facets["scene"])
        self.assertIn("Night", facets["scene"])
        self.assertIn("Playful", facets["mood"])
        self.assertEqual(prompt, "Candid full-body analog fashion photograph on a neon city street at night, playful coy expression.")

    def test_prompt_facets_ignore_source_filenames_but_keep_text_filters(self) -> None:
        prompt = "Point-and-shoot photograph of two women, otherwise bare with feet visible at golden hour, BRAND typography."
        facets = recipe_module._prompt_facets(
            prompt,
            [{"source_path": "Concepts/UV Night/Vintage Magazine Prompt Log.txt", "source_label": "UV Night Vintage Magazine"}],
        )
        self.assertEqual(facets["concept"], ["Other"])
        self.assertIn("Point-and-Shoot", facets["style"])
        self.assertEqual(set(facets["content"]), {"Nude / Bare", "Multi-Subject", "Foot Focus", "Typography"})
        self.assertIn("Golden Hour", facets["time"])
        self.assertNotIn("No Typography", facets["content"])

    def test_portable_corpus_prompts_are_live_blueprints_without_recipe_duplication(self) -> None:
        indexed = [
            {"prompt_id": "portable", "value": "Portrait of NAME wearing OUTFIT in SCENE beside a BRAND poster", "sources": [{"source_path": "Standard/Portable.txt"}]},
            {"prompt_id": "lowercase", "value": "Portrait of a name in a scene", "sources": [{"source_path": "Standard/Lowercase.txt"}]},
            {"prompt_id": "trigger", "value": "TRIGGER portrait in a studio", "sources": [{"source_path": "Standard/Trigger.txt"}]},
        ]
        assets = recipe_module._recipe_prompt_assets([], indexed)
        summary = recipe_module._prompt_blueprint_summary(assets)
        blueprints = recipe_module._filter_prompt_assets(assets, blueprint_only=True)
        signature = recipe_module._filter_prompt_assets(assets, signature="NAME+OUTFIT+BRAND+SCENE")

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["component_total"], 1)
        self.assertEqual(summary["signature_counts"], {"NAME+OUTFIT+BRAND+SCENE": 1, "TRIGGER": 1})
        self.assertEqual({item["prompt_id"] for item in blueprints}, {"portable", "trigger"})
        self.assertEqual([item["prompt_id"] for item in signature], ["portable"])
        self.assertFalse(blueprints[0]["from_recipe"])

    def test_prompt_assets_include_facet_counts(self) -> None:
        recipes = [{
            "recipe_id": "recipe:faceted",
            "name": "Analog night portrait",
            "created_at": "2026-08-21T01:00:00Z",
            "payload": recipe_payload("Candid portrait on an urban street at night, analog film grain, playful smile."),
        }]
        assets = recipe_module._recipe_prompt_assets(recipes)
        counts = recipe_module._prompt_facet_counts(assets)
        self.assertEqual(len(assets), 1)
        self.assertEqual(counts["structure"]["Portrait"], 1)
        self.assertEqual(counts["style"]["Analog"], 1)
        self.assertEqual(counts["scene"]["Urban"], 1)
        self.assertEqual(counts["mood"]["Playful"], 1)

    def test_prompt_assets_merge_duplicate_provenance_and_collection_scopes(self) -> None:
        shared = "Candid analog portrait on a city street at night."
        recipes = [
            {
                "recipe_id": "recipe:older", "name": "Older", "created_at": "2026-08-20T01:00:00Z",
                "updated_at": "2026-08-20T01:00:00Z", "payload": recipe_payload(shared),
                "collections": [{"collection_id": "collection:a", "name": "A", "color": "#111111"}],
            },
            {
                "recipe_id": "recipe:newer", "name": "Newer", "created_at": "2026-08-21T01:00:00Z",
                "updated_at": "2026-08-21T01:00:00Z", "preview_ref": "new.webp", "payload": recipe_payload(shared),
                "collections": [{"collection_id": "collection:b", "name": "B", "color": "#222222"}],
            },
        ]
        asset = recipe_module._recipe_prompt_assets(recipes)[0]
        self.assertEqual(asset["uses"], 2)
        self.assertEqual(asset["recipe_id"], "recipe:newer")
        self.assertEqual(asset["preview_ref"], "new.webp")
        self.assertEqual(asset["collections"], [])

    def test_resolved_prompt_variant_keeps_components_but_never_identity_or_brand(self) -> None:
        source = "photo of NAME wearing OUTFIT in SCENE beside BRAND"
        resolved = "photo of Morgan wearing a pink slip dress in a wildflower field beside Sick Ollie"
        placeholders = [
            {"token": "NAME", "value": "Morgan", "widget": "name_value"},
            {"token": "OUTFIT", "value": "a pink slip dress", "widget": "outfit_value_A"},
            {"token": "SCENE", "value": "a wildflower field", "widget": "scene_value"},
            {"token": "BRAND", "value": "Sick Ollie", "widget": "item_value"},
        ]

        portable = recipe_module._portable_resolved_prompt(source, resolved, placeholders)
        unsafe = recipe_module._portable_resolved_prompt(source, resolved, [])

        self.assertEqual(portable, "photo of NAME wearing a pink slip dress in a wildflower field beside BRAND")
        self.assertEqual(unsafe, "")

        unsafe_recipe = {
            "recipe_id": "recipe:unsafe", "name": "Unsafe legacy metadata",
            "created_at": "2026-09-01", "updated_at": "2026-09-01",
            "payload": recipe_payload(source, resolved, placeholders=[]),
        }
        assets = recipe_module._recipe_prompt_assets([unsafe_recipe])
        self.assertEqual([row["kind"] for row in assets], ["template"])
        self.assertEqual(assets[0]["resolved_value"], "")
        self.assertNotIn("Morgan", " ".join(str(row.get("value") or "") for row in assets))

    def test_server_prompt_filtering_combines_search_source_facets_and_scope(self) -> None:
        assets = [
            {
                "prompt_id": "one", "name": "Night portrait", "value": "analog portrait in a neon city at night",
                "from_recipe": True, "uses": 2, "created_at": "2026-08-20", "updated_at": "2026-08-21",
                "facets": {"structure": ["Portrait"], "style": ["Analog"], "scene": ["Urban", "Night"], "mood": ["Dark"]},
                "collections": [{"collection_id": "collection:night"}],
            },
            {
                "prompt_id": "two", "name": "Soft studio", "value": "soft full body photograph in a studio",
                "from_recipe": False, "uses": 1, "created_at": "2026-08-19", "updated_at": "2026-08-19",
                "facets": {"structure": ["Full body"], "style": ["Photoreal"], "scene": ["Studio"], "mood": ["Soft"]},
                "collections": [],
            },
        ]
        rows = recipe_module._filter_prompt_assets(
            assets, query="neon", source="recipe", collection="collection:night",
            facets={"structure": "Portrait", "style": "Analog"}, sort="most_used",
        )
        unfiled = recipe_module._filter_prompt_assets(assets, collection="unfiled")
        counts = recipe_module._prompt_collection_counts(assets)
        self.assertEqual([row["prompt_id"] for row in rows], ["one"])
        self.assertEqual([row["prompt_id"] for row in unfiled], ["two"])
        self.assertEqual(counts, {"": 2, "unfiled": 1, "collection:night": 1})

    def test_prompt_rating_filter_supports_exact_minimum_rated_and_unrated(self) -> None:
        assets = [
            {"prompt_id": "five", "value": "five", "rating": 5, "facets": {}, "collections": []},
            {"prompt_id": "three", "value": "three", "rating": 3, "facets": {}, "collections": []},
            {"prompt_id": "zero", "value": "zero", "rating": 0, "facets": {}, "collections": []},
        ]
        self.assertEqual([row["prompt_id"] for row in recipe_module._filter_prompt_assets(assets, rating="5")], ["five"])
        self.assertEqual({row["prompt_id"] for row in recipe_module._filter_prompt_assets(assets, rating="3plus")}, {"five", "three"})
        self.assertEqual({row["prompt_id"] for row in recipe_module._filter_prompt_assets(assets, rating="rated")}, {"five", "three"})
        self.assertEqual([row["prompt_id"] for row in recipe_module._filter_prompt_assets(assets, rating="unrated")], ["zero"])

    def test_recipe_and_prompt_views_are_distinct(self) -> None:
        recipe = {
            "recipe_id": "recipe:one",
            "name": "Faceout",
            "preview_ref": "one.webp",
            "created_at": "2026-08-19T01:00:00Z",
            "payload": recipe_payload(
                "NAME beside SCENE wearing OUTFIT, BRAND poster",
                "Phoebe beside a neon laundromat wearing a red ringer tee and denim shorts, Sick Ollie poster",
                [
                    {"token": "NAME", "value": "Phoebe", "widget": "name_value"},
                    {"token": "BRAND", "value": "Sick Ollie", "widget": "item_value"},
                    {"token": "SCENE", "value": "a neon laundromat", "widget": "scene_log_file"},
                    {"token": "OUTFIT", "value": "a red ringer tee and denim shorts", "widget": "outfit_log_file_A"},
                ],
            ),
        }
        self.assertTrue(recipe_module._recipe_is_template(recipe))
        self.assertEqual(recipe_module._recipe_portable_prompt_text(recipe), "")
        asset = recipe_module._recipe_prompt_assets([recipe])[0]
        self.assertTrue(asset["from_recipe"])
        self.assertEqual(asset["preview_ref"], "one.webp")

    def test_recipe_prompt_asset_only_carries_trusted_import_or_preview_seed(self) -> None:
        payload = recipe_payload("A candid phone portrait by a window.")
        payload["nodes"].append({
            "type": recipe_module.STUDIO_GENERATION,
            "widgets": [{"name": "seed_value", "value": 123456789}],
        })
        ordinary = recipe_module._recipe_prompt_assets([{
            "recipe_id": "recipe:seeded", "name": "Seeded", "created_at": "2026-08-26T00:00:00Z", "payload": payload,
        }])[0]
        self.assertIsNone(ordinary["resolved_seed"])
        self.assertEqual(ordinary.get("resolved_seed_source", ""), "")

        imported_payload = dict(payload)
        imported_payload["imported_from_image"] = True
        imported = recipe_module._recipe_prompt_assets([{
            "recipe_id": "recipe:imported", "name": "Imported", "created_at": "2026-08-26T00:00:00Z", "payload": imported_payload,
        }])[0]
        self.assertEqual(imported["resolved_seed"], 123456789)
        self.assertEqual(imported["resolved_seed_source"], "imported-image")

        previewed = recipe_module._recipe_prompt_assets([{
            "recipe_id": "recipe:previewed", "name": "Previewed", "preview_ref": "preview.webp",
            "created_at": "2026-08-26T00:00:00Z", "payload": payload,
        }])[0]
        self.assertEqual(previewed["resolved_seed"], 123456789)
        self.assertEqual(previewed["resolved_seed_source"], "preview-image")

    def test_flat_imported_prompt_is_prompt_not_recipe(self) -> None:
        recipe = {
            "recipe_id": "recipe:old",
            "name": "Old output",
            "created_at": "2026-08-19T01:00:00Z",
            "payload": recipe_payload("a young woman in a motel room wearing a black minidress and white socks"),
        }
        self.assertFalse(recipe_module._recipe_is_template(recipe))
        self.assertEqual(recipe_module._recipe_portable_prompt_text(recipe), "a young woman in a motel room wearing a black minidress and white socks")

    def test_template_detection_requires_literal_supported_tokens(self) -> None:
        prose_label = "Scene: The bedroom has an eclectic color theme, with an eclectic hipster vibe."
        true_template = "NAME is in SCENE wearing OUTFIT_B, with BRAND typography."
        self.assertEqual(recipe_module._template_placeholder_signature(prose_label), "")
        self.assertEqual(recipe_module._template_placeholder_signature(true_template), "NAME+OUTFIT_B+BRAND+SCENE")
        indexed = [
            {"prompt_id": "legacy-scene-label", "kind": "template", "placeholder_signature": "SCENE", "value": prose_label},
            {"prompt_id": "portable-template", "kind": "prompt", "placeholder_signature": "", "value": true_template},
        ]
        assets = {item["prompt_id"]: item for item in recipe_module._recipe_prompt_assets([], indexed)}
        self.assertEqual(assets["legacy-scene-label"]["kind"], "prompt")
        self.assertEqual(assets["portable-template"]["kind"], "template")

    def test_every_supported_placeholder_routes_to_templates(self) -> None:
        outfit_only = "A young woman enters the party wearing OUTFIT, smiling at the doorway."
        scene_and_outfit = "Later she curls up in SCENE wearing OUTFIT while the night winds down."
        name_only = "NAME poses against a white seamless backdrop."
        brand_only = "A glossy campaign image with BRAND typography across the lower edge."
        self.assertTrue(recipe_module._creative_library_is_template_text(outfit_only))
        self.assertTrue(recipe_module._creative_library_is_template_text(scene_and_outfit))
        self.assertTrue(recipe_module._creative_library_is_template_text(name_only))
        self.assertTrue(recipe_module._creative_library_is_template_text(brand_only))

        prepared = recipe_module._prepare_prompt_import(
            [outfit_only, "She moves deeper into the room and laughs.", scene_and_outfit, name_only],
            "Narratives",
            "Night Journey",
        )
        self.assertEqual([item["value"] for item in prepared["prompt_items"]], [
            "She moves deeper into the room and laughs.",
        ])
        self.assertEqual([item["value"] for item in prepared["template_items"]], [outfit_only, scene_and_outfit, name_only])
        self.assertEqual(prepared["template_routed"], 3)

    def test_component_only_recipe_creates_template_and_resolved_prompt(self) -> None:
        source = "A young woman walks into SCENE wearing OUTFIT, visibly nervous but curious."
        resolved = "A young woman walks into a crowded loft wearing a pink sundress, visibly nervous but curious."
        recipe = {
            "recipe_id": "recipe:component-only",
            "name": "Narrative opening",
            "created_at": "2026-08-29T00:00:00Z",
            "payload": recipe_payload(
                source,
                resolved,
                [
                    {"token": "OUTFIT", "value": "a pink sundress", "widget": "outfit_log_file_A"},
                    {"token": "SCENE", "value": "a crowded loft", "widget": "scene_log_file"},
                ],
            ),
        }
        self.assertTrue(recipe_module._recipe_is_template(recipe))
        assets = recipe_module._recipe_prompt_assets([recipe])
        self.assertEqual(len(assets), 2)
        by_kind = {asset["kind"]: asset for asset in assets}
        self.assertEqual(by_kind["template"]["value"], source)
        self.assertEqual(by_kind["template"]["resolved_value"], resolved)
        self.assertEqual(by_kind["prompt"]["value"], resolved)

    def test_source_folder_cannot_override_placeholder_classification(self) -> None:
        indexed = [
            {
                "prompt_id": "outfit-in-template-folder",
                "kind": "template",
                "value": "A young woman changes into OUTFIT before leaving the apartment.",
                "sources": [{"source_path": "Templates/Narrative/Opening.txt", "line_number": 1}],
            },
            {
                "prompt_id": "name-in-prompt-folder",
                "kind": "prompt",
                "value": "NAME appears beneath stark BRAND masthead typography.",
                "sources": [{"source_path": "Prompts/Editorial/Faceout.txt", "line_number": 1}],
            },
        ]
        assets = {item["prompt_id"]: item for item in recipe_module._recipe_prompt_assets([], indexed)}
        self.assertEqual(assets["outfit-in-template-folder"]["kind"], "template")
        self.assertEqual(assets["name-in-prompt-folder"]["kind"], "template")

    def test_ready_prompt_master_and_prompt_collection_logs(self) -> None:
        collection = {"collection_id": "recipe-collection:faceout", "name": "Faceout Posters", "color": "#ff4ab8"}
        recipes = [{
            "recipe_id": "recipe:one",
            "name": "Faceout",
            "created_at": "2026-08-19T01:00:00Z",
            "payload": recipe_payload(
                "NAME in SCENE wearing OUTFIT",
                "Phoebe in a white studio wearing a silver mini dress",
                [{"token": "NAME", "value": "Phoebe", "widget": "name_value"}],
            ),
            "collections": [collection],
        }]
        with tempfile.TemporaryDirectory() as directory:
            result = recipe_module._sync_creative_prompt_asset_logs(Path(directory), recipes, [collection])
            master = (Path(directory) / recipe_module.CREATIVE_PROMPT_MASTER_FILE).read_text(encoding="utf-8")
            grouped = (Path(directory) / recipe_module.CREATIVE_PROMPT_COLLECTION_FOLDER / "Faceout Posters.txt").read_text(encoding="utf-8")
        self.assertTrue(result["ok"])
        self.assertEqual(master, "")
        self.assertEqual(grouped, master)

    def test_existing_component_log_scan_ignores_managed_library(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Casual").mkdir()
            (root / "Casual" / "Cozy.txt").write_text("cream sweater and socks\ndenim shorts and tee\n", encoding="utf-8")
            managed = root / recipe_module.RECIPE_COMPONENT_LOG_FOLDER
            managed.mkdir()
            (managed / "MASTER - Resolved Recipe Outfits.txt").write_text("should not import\n", encoding="utf-8")
            imported = root / recipe_module.IMPORTED_COMPONENT_LOG_FOLDER / "Everyday"
            imported.mkdir(parents=True)
            (imported / "Managed Copy.txt").write_text("should not be rediscovered\n", encoding="utf-8")
            original = recipe_module._component_source_log_root
            recipe_module._component_source_log_root = lambda kind: root
            try:
                rows = recipe_module._scan_component_source_logs("outfit")
            finally:
                recipe_module._component_source_log_root = original
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["relative_path"], "Casual/Cozy.txt")
        self.assertEqual(rows[0]["line_count"], 2)
        self.assertEqual(rows[0]["suggested_collections"], ["Casual", "Cozy"])

    def test_existing_logs_import_unique_lines_into_component_assets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "logs"
            root.mkdir()
            (root / "one.txt").write_text("red tee and jeans\nwhite dress\n", encoding="utf-8")
            (root / "two.txt").write_text("RED TEE AND JEANS\nblack bodysuit\n", encoding="utf-8")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_root = recipe_module._component_source_log_root
            original_catalog = recipe_module.get_catalog
            original_sync = recipe_module._safe_sync_recipe_prompt_logs
            recipe_module._component_source_log_root = lambda kind: root
            recipe_module.get_catalog = lambda: catalog
            recipe_module._safe_sync_recipe_prompt_logs = lambda **kwargs: {"ok": True}
            try:
                result = recipe_module._import_component_source_logs("outfit", ["one.txt", "two.txt"])
                rows = catalog.recipe_components("outfit")
            finally:
                recipe_module._component_source_log_root = original_root
                recipe_module.get_catalog = original_catalog
                recipe_module._safe_sync_recipe_prompt_logs = original_sync
        self.assertEqual(result["files"], 2)
        self.assertEqual(result["values"], 3)
        self.assertEqual({row["value"].casefold() for row in rows}, {"red tee and jeans", "white dress", "black bodysuit"})

    def test_existing_logs_can_bootstrap_scoped_component_collections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "logs"
            (root / "Casual").mkdir(parents=True)
            (root / "Casual" / "Cozy.txt").write_text("cream sweater and socks\ndenim shorts and tee\n", encoding="utf-8")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_root = recipe_module._component_source_log_root
            original_catalog = recipe_module.get_catalog
            original_sync = recipe_module._safe_sync_recipe_prompt_logs
            recipe_module._component_source_log_root = lambda kind: root
            recipe_module.get_catalog = lambda: catalog
            recipe_module._safe_sync_recipe_prompt_logs = lambda **kwargs: {"ok": True}
            try:
                result = recipe_module._import_component_source_logs("outfit", ["Casual/Cozy.txt"], "both")
                rows = catalog.recipe_components("outfit")
                groups = catalog.component_collections("outfit")
            finally:
                recipe_module._component_source_log_root = original_root
                recipe_module.get_catalog = original_catalog
                recipe_module._safe_sync_recipe_prompt_logs = original_sync

        self.assertEqual(result["collections"], 2)
        self.assertEqual({group["name"] for group in groups}, {"Casual", "Cozy"})
        self.assertTrue(rows)
        self.assertTrue(all({entry["name"] for entry in row["collections"]} == {"Casual", "Cozy"} for row in rows))

    def test_local_outfit_log_import_matches_prompt_import_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_root = root / "input"; input_root.mkdir()
            original = root / "Cozy Looks.txt"
            original.write_text("cardigan and loafers\ncardigan and loafers\nsatin skirt\n", encoding="utf-8")
            fake_folder_paths = types.ModuleType("folder_paths")
            fake_folder_paths.get_input_directory = lambda: str(input_root)
            prior_folder_paths = sys.modules.get("folder_paths")
            sys.modules["folder_paths"] = fake_folder_paths
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            prior_catalog = recipe_module.get_catalog
            prior_sync = recipe_module._safe_sync_recipe_prompt_logs
            recipe_module.get_catalog = lambda: catalog
            recipe_module._safe_sync_recipe_prompt_logs = lambda **kwargs: {"ok": True}
            try:
                result = recipe_module._import_component_text_log(
                    "outfit",
                    original.read_text(encoding="utf-8"),
                    "Everyday",
                    "Cozy",
                    "Cozy Looks",
                    collection_name="Release Picks",
                )
                rows = catalog.recipe_components("outfit")
                folders = catalog.component_collections("outfit")
                shareable = catalog.library_collections("outfit")
                history = catalog.component_import_batches("outfit")
                undo = catalog.undo_component_import_batch(result["batch_id"])
            finally:
                recipe_module.get_catalog = prior_catalog
                recipe_module._safe_sync_recipe_prompt_logs = prior_sync
                if prior_folder_paths is None:
                    sys.modules.pop("folder_paths", None)
                else:
                    sys.modules["folder_paths"] = prior_folder_paths

            copied = input_root / "SickOllieLogs" / "outfits" / result["source_path"]
            self.assertEqual(original.read_text(encoding="utf-8"), "cardigan and loafers\ncardigan and loafers\nsatin skirt\n")
            self.assertTrue(copied.is_file())
            self.assertEqual({row["value"] for row in rows}, {"cardigan and loafers", "satin skirt"})
            self.assertEqual({row["name"] for row in folders}, {"Everyday", "Cozy"})
            self.assertEqual([row["name"] for row in shareable], ["Release Picks"])
            self.assertEqual(result["input_duplicates"], 1)
            self.assertEqual(len(history), 1)
            self.assertEqual(undo["deleted"], 2)
            self.assertEqual(undo["collections_removed"], 3)
            self.assertEqual(undo["collection_mode"], "managed-log")


    def test_log_import_history_can_undo_only_batch_created_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "logs"
            root.mkdir()
            (root / "Accidental.txt").write_text("red tee and jeans\nwhite dress and knee socks\n", encoding="utf-8")
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            preexisting = catalog.upsert_recipe_component("outfit", "red tee and jeans", manual=True)
            original_root = recipe_module._component_source_log_root
            original_catalog = recipe_module.get_catalog
            original_sync = recipe_module._safe_sync_recipe_prompt_logs
            recipe_module._component_source_log_root = lambda kind: root
            recipe_module.get_catalog = lambda: catalog
            recipe_module._safe_sync_recipe_prompt_logs = lambda **kwargs: {"ok": True}
            try:
                result = recipe_module._import_component_source_logs("outfit", ["Accidental.txt"], "log")
                history = catalog.component_import_batches("outfit")
                undo = catalog.undo_component_import_batch(result["batch_id"])
                remaining = catalog.recipe_components("outfit")
                groups = catalog.component_collections("outfit")
            finally:
                recipe_module._component_source_log_root = original_root
                recipe_module.get_catalog = original_catalog
                recipe_module._safe_sync_recipe_prompt_logs = original_sync

        self.assertEqual(result["new_values"], 1)
        self.assertEqual(result["existing_values"], 1)
        self.assertEqual(len(history), 1)
        self.assertEqual(undo["deleted"], 1)
        self.assertEqual({row["component_id"] for row in remaining}, {preexisting["component_id"]})
        self.assertEqual(groups, [])

    def test_component_bulk_collection_add_handles_large_selections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            component_ids = [catalog.upsert_recipe_component("outfit", f"outfit value {index}", manual=True)["component_id"] for index in range(1200)]
            collection = catalog.create_component_collection("outfit", "Big Test")
            result = catalog.add_components_to_collections(component_ids, [collection["collection_id"]])
            members = catalog.component_collection_member_ids(collection["collection_id"])
        self.assertEqual(result["memberships_added"], 1200)
        self.assertEqual(len(members), 1200)

    def test_component_bulk_home_move_replaces_prior_taxonomy_membership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            first = catalog.create_component_collection("scene", "Interior")
            second = catalog.create_component_collection("scene", "Nature")
            components = [catalog.upsert_recipe_component("scene", value, manual=True) for value in ("red room", "green field")]
            for component in components:
                catalog.set_component_collections(component["component_id"], [first["collection_id"]])
            result = catalog.move_components_home([component["component_id"] for component in components], second["collection_id"])
            first_members = catalog.component_collection_member_ids(first["collection_id"])
            second_members = catalog.component_collection_member_ids(second["collection_id"])
        self.assertEqual(result, {"assets": 2, "homes": 1, "memberships_added": 2})
        self.assertEqual(first_members, set())
        self.assertEqual(second_members, {component["component_id"] for component in components})

    def test_cleanup_report_finds_high_overlap_modifier_variants(self) -> None:
        assets = [
            {"component_id": "one", "value": "cream cropped cardigan, denim shorts, white socks, pearl necklace", "manual": True, "uses": 0},
            {"component_id": "two", "value": "cream cropped cardigan, faded denim shorts, white ankle socks, pearl necklace", "manual": True, "uses": 0},
            {"component_id": "three", "value": "red satin gown with opera gloves and heels", "manual": True, "uses": 0},
        ]
        report = recipe_module._cleanup_component_report(assets, "outfit")
        groups = report["near_duplicate_groups"]
        self.assertTrue(any({item["component_id"] for item in group["items"]} == {"one", "two"} for group in groups))

    def test_component_rating_persists_and_can_be_cleared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            component = catalog.upsert_recipe_component("outfit", "cream cardigan and white socks", manual=True)
            catalog.set_component_rating(component["component_id"], 5)
            rated = catalog.recipe_components("outfit")[0]
            catalog.set_component_rating(component["component_id"], 0)
            cleared = catalog.recipe_components("outfit")[0]
        self.assertEqual(rated["rating"], 5)
        self.assertEqual(cleared["rating"], 0)

    def test_cleanup_report_finds_deterministic_wording_duplicates(self) -> None:
        assets = [
            {"component_id": "one", "value": "cream cropped cardigan with denim shorts and white socks", "manual": True, "uses": 0},
            {"component_id": "two", "value": "cream cropped cardigan, denim shorts, white socks", "manual": True, "uses": 0},
            {"component_id": "three", "value": "white dress", "manual": True, "uses": 0},
        ]
        report = recipe_module._cleanup_component_report(assets, "outfit")
        groups = report["near_duplicate_groups"]
        self.assertTrue(any({item["component_id"] for item in group["items"]} == {"one", "two"} for group in groups))


    def test_wardrobe_decomposer_keeps_garment_details_with_item(self) -> None:
        result = recipe_module._decompose_outfit_look(
            "pale aqua organza babydoll dress with transparent puff sleeves, a satin underlayer, tiny pearl buttons, and white ankle-strap flats"
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["value"], "organza babydoll dress with transparent puff sleeves, a satin underlayer, tiny pearl buttons")
        self.assertEqual(result["items"][0]["subtype"], "Dresses")
        self.assertEqual(result["items"][1]["subtype"], "Flats & Mary Janes")

    def test_wardrobe_decomposer_extracts_finishers_without_destroying_look(self) -> None:
        result = recipe_module._decompose_outfit_look("oversized white button-up shirt and slouchy white crew socks, bare everywhere else")
        self.assertEqual(result["status"], "ready")
        self.assertEqual([item["item_type"] for item in result["items"]], ["piece", "piece", "finisher"])
        self.assertEqual(result["items"][-1]["value"], "bare everywhere else")


    def test_wardrobe_v2_flags_generic_visual_candidates(self) -> None:
        result = recipe_module._decompose_outfit_look("bra")
        self.assertEqual(result["status"], "review")
        self.assertEqual(len(result["items"]), 1)
        self.assertFalse(result["items"][0]["visual_ready"])
        self.assertIn("generic", result["issues"])

    def test_wardrobe_v2_recognizes_sets_and_avoids_integral_cuffs(self) -> None:
        set_result = recipe_module._decompose_outfit_look("black mesh robe over lace lingerie set and stilettos")
        self.assertEqual([item["item_type"] for item in set_result["items"]], ["piece", "set", "piece"])
        self.assertEqual(set_result["items"][1]["category"], "Matching Sets")
        hoodie_result = recipe_module._decompose_outfit_look("a neon green crop hoodie with glowing drawstrings and luminous piping around the hood and cuffs")
        self.assertEqual(len(hoodie_result["items"]), 1)
        self.assertIn("cuffs", hoodie_result["items"][0]["value"])

    def test_wardrobe_v2_summary_distinguishes_occurrences_from_unique_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.upsert_recipe_component("outfit", "black tights and pink cropped camisole", manual=True)
            catalog.upsert_recipe_component("outfit", "black tights and lavender cardigan", manual=True)
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                analysis = recipe_module._analyze_wardrobe_migration(refresh=True, sample_limit=20)
            finally:
                recipe_module.get_catalog = original_catalog
        self.assertGreater(analysis["summary"]["detected_uses"], analysis["summary"]["unique_candidates"])
        self.assertGreaterEqual(analysis["summary"]["reused_occurrences"], 1)

    def test_wardrobe_migration_creates_deduped_pieces_and_relationships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            one = catalog.upsert_recipe_component("outfit", "pink cropped camisole, white shorts, fluffy slippers", manual=True)
            two = catalog.upsert_recipe_component("outfit", "pink cropped camisole, black skirt, white ankle socks", manual=True)
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                analysis = recipe_module._analyze_wardrobe_migration(refresh=True, sample_limit=20)
                migrated = recipe_module._accept_wardrobe_migration(high_confidence_only=True)
                items = catalog.wardrobe_items()
                parts_one = catalog.wardrobe_look_parts(one["component_id"])
                parts_two = catalog.wardrobe_look_parts(two["component_id"])
            finally:
                recipe_module.get_catalog = original_catalog
        self.assertEqual(analysis["summary"]["ready"], 2)
        self.assertEqual(migrated["accepted_looks"], 2)
        self.assertEqual(len([item for item in items if item["value"].casefold() == "camisole"]), 1)
        self.assertEqual(len(parts_one), 3)
        self.assertEqual(len(parts_two), 3)


    def test_wardrobe_migration_reuses_conservative_hyphen_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            one = catalog.upsert_recipe_component("outfit", "black knee-high socks", manual=True)
            two = catalog.upsert_recipe_component("outfit", "black knee high socks", manual=True)
            entries = [
                {"look_component_id": one["component_id"], "confidence": 1.0, "proposal": {"items": [{"item_type": "piece", "category": "Legwear", "subtype": "Knee Socks", "value": "black knee-high socks"}]}},
                {"look_component_id": two["component_id"], "confidence": 1.0, "proposal": {"items": [{"item_type": "piece", "category": "Legwear", "subtype": "Knee Socks", "value": "black knee high socks"}]}},
            ]
            result = catalog.apply_wardrobe_migration_batch(entries, parser_version="wardrobe-v2")
            items = catalog.wardrobe_items()
        self.assertEqual(result["created_items"], 1)
        self.assertEqual(result["matched_items"], 1)
        self.assertEqual(len(items), 1)


    def test_wardrobe_v3_routes_body_styling_to_nonvisual_builder_token(self) -> None:
        result = recipe_module._decompose_outfit_look(
            "a liquid silver body paint finish with cool white reflective highlights tracing the body, crystal dust along the collarbones and waist"
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["item_type"], "styling")
        self.assertEqual(result["items"][0]["category"], "Body Styling")
        self.assertIn("styling", result["issues"])

    def test_wardrobe_v3_recognizes_simple_slip_collar_henley_and_button_up(self) -> None:
        examples = {
            "a satin slip": ("Bodywear", "Chemises & Slips"),
            "black leather collar": ("Accessories", "Chokers & Collars"),
            "a short-sleeve sleep henley with a gentle lounge mood": ("Tops", "Tees"),
            "a relaxed pajama button-up in pale blue": ("Tops", "Shirts & Blouses"),
        }
        for value, expected in examples.items():
            with self.subTest(value=value):
                result = recipe_module._decompose_outfit_look(value)
                self.assertTrue(result["items"])
                self.assertEqual((result["items"][0]["category"], result["items"][0]["subtype"]), expected)

    def test_wardrobe_v4_splits_overalls_and_keeps_relaxed_collar_attached(self) -> None:
        layered = recipe_module._decompose_outfit_look("retro 70s-style striped sweater with denim overalls")
        self.assertEqual([item["value"] for item in layered["items"]], ["retro 70s-style sweater", "denim overalls"])
        self.assertEqual(layered["items"][1]["category"], "Dresses & One-Pieces")
        self.assertEqual(layered["items"][1]["subtype"], "Jumpsuits")

        button_up = recipe_module._decompose_outfit_look("a lilac pajama button-up with a relaxed collar")
        self.assertEqual(len(button_up["items"]), 1)
        self.assertEqual(button_up["items"][0]["value"], "pajama button-up with a relaxed collar")
        self.assertEqual(button_up["items"][0]["category"], "Tops")

    def test_wardrobe_v5_does_not_misread_short_sleeves_as_shorts(self) -> None:
        result = recipe_module._decompose_outfit_look("a cotton blouse with short flutter sleeves")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["subtype"], "Shirts & Blouses")
        self.assertNotEqual(result["items"][0]["subtype"], "Shorts")

    def test_wardrobe_v6_collapses_wear_context_and_splits_independent_pieces(self) -> None:
        bike_shorts = recipe_module._decompose_outfit_look("bike shorts barely visible underneath")
        self.assertEqual([item["value"] for item in bike_shorts["items"]], ["bike shorts"])

        compound = recipe_module._decompose_outfit_look("a black mini skirt, striped arm warmers")
        self.assertEqual([item["value"] for item in compound["items"]], ["skirt", "arm warmers"])
        self.assertEqual(compound["items"][1]["subtype"], "Arm Warmers")

    def test_filtered_migration_accepts_entire_matching_queue_not_page_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            for index in range(75):
                catalog.upsert_recipe_component("outfit", f"pink cropped camisole and black skirt {index}", manual=True)
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                recipe_module._analyze_wardrobe_migration(refresh=True, sample_limit=20, status_filter="ready")
                result = recipe_module._accept_filtered_wardrobe_migration(status_filter="ready")
                states = catalog.wardrobe_migration_states()
            finally:
                recipe_module.get_catalog = original_catalog
        self.assertEqual(result["matched_view"], 75)
        self.assertEqual(result["accepted_looks"], 75)
        self.assertEqual(sum(1 for state in states.values() if state["status"] == "accepted"), 75)

    def test_reapplying_migration_removes_stale_auto_piece_when_no_other_source_needs_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            look = catalog.upsert_recipe_component("outfit", "pink fishnet top with white shorts", manual=True)
            first = [{
                "look_component_id": look["component_id"], "confidence": 0.95,
                "proposal": {"items": [{"item_type": "piece", "category": "Tops", "subtype": "Tees", "value": "pink fishnet top with white shorts"}]},
            }]
            second = [{
                "look_component_id": look["component_id"], "confidence": 0.95,
                "proposal": {"items": [
                    {"item_type": "piece", "category": "Tops", "subtype": "Tees", "value": "pink fishnet top"},
                    {"item_type": "piece", "category": "Bottoms", "subtype": "Shorts", "value": "white shorts", "relation": "with"},
                ]},
            }]
            catalog.apply_wardrobe_migration_batch(first, parser_version="wardrobe-v2")
            catalog.apply_wardrobe_migration_batch(second, parser_version="wardrobe-v3")
            values = {row["value"] for row in catalog.wardrobe_items()}
        self.assertNotIn("pink fishnet top with white shorts", values)
        self.assertIn("pink fishnet top", values)
        self.assertIn("white shorts", values)

    def test_wardrobe_styling_items_are_portable_and_nonvisual(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            item = catalog.upsert_wardrobe_item("styling", "liquid silver body paint across the skin", category="Body Styling", subtype="Metallic & Chrome", manual=False)
            self.assertEqual(item["item_type"], "styling")
            rows = catalog.wardrobe_items("styling")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["category"], "Body Styling")

    def test_purge_wardrobe_preserves_looks_and_resets_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            look = catalog.upsert_recipe_component("outfit", "lavender hoodie, black skirt", manual=True)
            piece = catalog.upsert_wardrobe_item("piece", "lavender hoodie", category="Layers", subtype="Hoodies & Sweatshirts", manual=False)
            catalog.set_wardrobe_rating(piece["wardrobe_id"], 4)
            catalog.set_wardrobe_look_parts(look["component_id"], [{"wardrobe_id": piece["wardrobe_id"], "source_text": "lavender hoodie"}])
            catalog.set_wardrobe_migration_state(look["component_id"], parser_version="wardrobe-v4", status="accepted", confidence=1.0, proposal={"items": []})
            catalog.upsert_wardrobe_pack({"pack_id": "test-pack", "name": "Test Pack"})

            preview_dir = root / "previews"; preview_dir.mkdir()
            preview_name = "wardrobe-preview.webp"
            (preview_dir / preview_name).write_bytes(b"preview")
            with catalog._connection() as db:
                db.execute("UPDATE wardrobe_items SET preview_ref=?, preview_source='generated:catalog' WHERE wardrobe_id=?", (preview_name, piece["wardrobe_id"]))

            original_catalog = recipe_module.get_catalog
            original_component_preview = recipe_module._component_preview_directory
            recipe_module.get_catalog = lambda: catalog
            recipe_module._component_preview_directory = lambda: preview_dir
            try:
                result = recipe_module._purge_wardrobe()
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._component_preview_directory = original_component_preview

            self.assertEqual(result["items"], 1)
            self.assertEqual(result["migration_states"], 1)
            self.assertEqual(result["previews_deleted"], 1)
            self.assertEqual(catalog.wardrobe_items(), [])
            self.assertEqual(catalog.wardrobe_migration_states(), {})
            self.assertEqual(catalog.wardrobe_look_parts(look["component_id"]), [])
            self.assertEqual(catalog.wardrobe_packs(), [])
            self.assertFalse((preview_dir / preview_name).exists())
            self.assertIsNotNone(catalog.recipe_component_by_value("outfit", "lavender hoodie, black skirt"))


    def test_last_import_virtual_subcategory_is_removed_from_catalog_navigation(self) -> None:
        assets = [
            {"prompt_id": "prompt:one", "value": "One", "primary_parent": "Saved & Imported", "primary_subcategory": "Saved Prompts", "sources": [], "last_import": True},
            {"prompt_id": "prompt:two", "value": "Two", "primary_parent": "Saved & Imported", "primary_subcategory": "Saved Prompts", "sources": [], "last_import": False},
            {"prompt_id": "creative-prompt:three", "value": "Three", "primary_parent": "Saved & Imported", "primary_subcategory": "Saved Prompts", "sources": [], "last_import": True},
        ]
        homes = recipe_module._prompt_home_counts(assets)
        self.assertEqual(homes["subcategories"]["Saved & Imported"], {"Saved Prompts": 3})
        self.assertNotIn("Last Import", homes["subcategories"]["Saved & Imported"])

    def test_edit_prompt_asset_text_updates_or_copies_saved_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.import_prompt_assets([
                {"value": "Original prompt", "facets_json": "{}", "source_line": 1},
            ], parent="Saved & Imported", subcategory="Saved Prompts")
            prompt_id = catalog.indexed_prompt_assets()[0]["prompt_id"]

            edited = catalog.edit_prompt_asset_text(prompt_id, "Edited prompt")
            copied = catalog.edit_prompt_asset_text(prompt_id, "Copied prompt", copy_only=True)
            values = sorted(item["value"] for item in catalog.indexed_prompt_assets())

        self.assertFalse(edited["created_copy"])
        self.assertTrue(copied["created_copy"])
        self.assertEqual(values, ["Copied prompt", "Edited prompt"])


if __name__ == "__main__":
    unittest.main()


class PromptHarvestCompatibilityTests(unittest.TestCase):
    def test_classic_flat_metadata_restores_template_and_exact_outfit(self) -> None:
        from io import BytesIO
        from PIL.PngImagePlugin import PngInfo

        source = "A fashion poster featuring a young woman wearing OUTFIT, harsh direct flash. NAME headline."
        resolved = "A fashion poster featuring a young woman wearing black baby tee with a pastel pink plaid micro skirt, harsh direct flash. scout headline."
        info = PngInfo()
        info.add_text("source_prompt", source)
        info.add_text("resolved_prompt", resolved)
        info.add_text("prompt_log_line", source)
        info.add_text("outfit_log_line", "black baby tee with a pastel pink plaid micro skirt")
        info.add_text("scene_log_line", "")
        info.add_text("so_generation_seed_used", "12345")
        info.add_text("so_generation_width", "400")
        info.add_text("so_generation_height", "500")
        info.add_text("so_loader_core_diffusion_model", '"classic_model.safetensors"')
        info.add_text("so_loader_core_applied_loras", '["Characters\\\\scout.safetensors@1"]')
        info.add_text("parameters", resolved + "\nSteps: 9, Sampler: euler, CFG scale: 1.0, Seed: 12345, Size: 400x500, Model: classic_model")
        buffer = BytesIO()
        Image.new("RGB", (400, 500), "black").save(buffer, format="PNG", pnginfo=info)

        payload, _ = recipe_module._recipe_from_image_bytes(buffer.getvalue())
        wrapper = {"payload": payload}
        self.assertTrue(recipe_module._recipe_is_template(wrapper))
        self.assertEqual(payload["summary"]["prompt_template"], source)
        self.assertEqual(payload["summary"]["resolved_prompt"], resolved)
        outfit_values = [item["value"] for item in payload["summary"]["placeholders"] if str(item.get("token", "")).startswith("OUTFIT")]
        self.assertEqual(outfit_values, ["black baby tee with a pastel pink plaid micro skirt"])
        loader = recipe_module._recipe_node_values(payload, recipe_module.STUDIO_LOADER, include_optional=True)
        self.assertEqual(loader.get("main_lora"), "Characters\\scout.safetensors")

    def test_prompt_harvest_extracts_outfit_clause_before_pose_language(self) -> None:
        result = recipe_module._prompt_harvest_outfit_from_text(
            "A 2000s fashion ad featuring a young woman wearing black baby tee with a pastel pink plaid micro skirt, photographed outdoors at night against a white railing, harsh direct flash."
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["candidate"], "black baby tee with a pastel pink plaid micro skirt")

    def test_prompt_harvest_keeps_bare_finisher_with_outfit(self) -> None:
        result = recipe_module._prompt_harvest_outfit_from_text(
            "A vertical poster featuring a young woman wearing pink patent pumps, bare everywhere else, her torso facing away while her face turns back toward camera."
        )
        self.assertIn(result["status"], {"ready", "review"})
        self.assertEqual(result["candidate"], "pink patent pumps, bare everywhere else")

    def test_prompt_harvest_uses_exact_structured_outfit_when_available(self) -> None:
        recipe = {
            "payload": recipe_payload(
                "NAME wearing OUTFIT in SCENE",
                "Scout wearing white cropped tank and denim shorts in a motel room",
                [{"token": "OUTFIT", "value": "white cropped tank and denim shorts", "widget": "outfit_log_file_A"}],
            )
        }
        self.assertEqual(recipe_module._prompt_harvest_exact_outfit(recipe), "white cropped tank and denim shorts")


    def test_share_pack_includes_recipe_derived_saved_imported_prompts_and_new_organization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            preview_root = root / "creative_library_previews"
            preview_root.mkdir()
            Image.new("RGB", (64, 80), "white").save(preview_root / "imported.webp", "WEBP")
            payload = recipe_payload(
                "A candid photo of a young woman smiling in fresh snow.",
                "A candid photo of a young woman smiling in fresh snow.",
            )
            payload["imported_from_image"] = True
            catalog.save_recipe("recipe:imported", "imported", payload, "imported.webp")
            original_catalog = recipe_module.get_catalog
            recipe_module.get_catalog = lambda: catalog
            try:
                recipe_module._PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
                visible = recipe_module._prompt_asset_snapshot()
                asset = next(row for row in visible["prompts"] if row["value"] == "A candid photo of a young woman smiling in fresh snow.")
                self.assertFalse(asset["indexed"])
                catalog.set_prompt_home([asset["prompt_id"]], "Creators", "dr0s")
                collection = catalog.create_prompt_showcase_collection("prompt", "dr0s")
                catalog.set_prompt_collections(asset["prompt_id"], [collection["collection_id"]], "prompt")
                recipe_module._PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})

                snapshot = recipe_module._creative_library_pack_snapshot("starter")
                exported = next(row for row in snapshot["prompts"] if row["value"] == asset["value"])
                self.assertEqual((exported["primary_parent"], exported["primary_subcategory"]), ("Creators", "dr0s"))
                self.assertEqual([row["name"] for row in exported["collections"]], ["dr0s"])
                contents = recipe_module._creative_library_pack_contents(snapshot)
                self.assertEqual(contents["counts"]["prompts"], 1)
                self.assertEqual(contents["prompt_homes"]["prompt"]["Creators"], {"dr0s": 1})
                self.assertEqual(contents["showcase_collections"]["prompt"], ["dr0s"])

                raw, _, manifest = recipe_module._creative_library_pack_export({
                    "mode": "starter",
                    "name": "Imported Prompt Pack",
                    "selection": {
                        "libraries": ["prompts"],
                        "prompt_scopes": {
                            "prompt": {"parents": ["Creators"]},
                            "template": {},
                        },
                        "include_thumbnails": True,
                        "include_taxonomy": True,
                        "include_dependencies": True,
                    },
                })
                with zipfile.ZipFile(BytesIO(raw), "r") as archive:
                    rows = json.loads(archive.read("library/prompts.json"))
                    names = archive.namelist()
                self.assertEqual([row["value"] for row in rows], [asset["value"]])
                self.assertEqual(rows[0]["primary_parent"], "Creators")
                self.assertEqual([row["name"] for row in rows[0]["collections"]], ["dr0s"])
                self.assertTrue(any(name.endswith("/imported.webp") for name in names))
                self.assertEqual(manifest["counts"]["prompts"], 1)
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})

    def test_shareable_library_collections_cover_outfits_scenes_and_wardrobe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            outfit = catalog.upsert_recipe_component("outfit", "black witchy babydoll dress with striped tights", manual=True)
            scene = catalog.upsert_recipe_component("scene", "foggy jack-o-lantern porch at night", manual=True)
            wardrobe = catalog.upsert_wardrobe_item("piece", "black velvet witch hat", category="Accessories", subtype="Headwear", manual=True)
            outfit_group = catalog.create_library_collection("outfit", "Halloween Looks")
            scene_group = catalog.create_library_collection("scene", "Halloween Scenes")
            wardrobe_group = catalog.create_library_collection("wardrobe", "Halloween Wardrobe")
            catalog.set_library_asset_collections("outfit", outfit["component_id"], [outfit_group["collection_id"]])
            catalog.set_library_asset_collections("scene", scene["component_id"], [scene_group["collection_id"]])
            catalog.set_library_asset_collections("wardrobe", wardrobe["wardrobe_id"], [wardrobe_group["collection_id"]])

            components = {row["kind"]: row for row in catalog.recipe_components() if row["component_id"] in {outfit["component_id"], scene["component_id"]}}
            wardrobe_row = next(row for row in catalog.wardrobe_items() if row["wardrobe_id"] == wardrobe["wardrobe_id"])
            self.assertEqual([row["name"] for row in components["outfit"]["pack_collections"]], ["Halloween Looks"])
            self.assertEqual([row["name"] for row in components["scene"]["pack_collections"]], ["Halloween Scenes"])
            self.assertEqual([row["name"] for row in wardrobe_row["pack_collections"]], ["Halloween Wardrobe"])

            snapshot = catalog.creative_library_pack_snapshot("starter")
            self.assertEqual({row["name"] for row in snapshot["library_collections"]}, {"Halloween Looks", "Halloween Scenes", "Halloween Wardrobe"})

    def test_shareable_collection_scope_exports_only_selected_membership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            spooky = catalog.upsert_recipe_component("scene", "abandoned pumpkin patch under a full moon", manual=True)
            summer = catalog.upsert_recipe_component("scene", "bright swimming pool on a summer afternoon", manual=True)
            halloween = catalog.create_library_collection("scene", "Halloween Scenes")
            favorites = catalog.create_library_collection("scene", "Favorites")
            catalog.set_library_asset_collections("scene", spooky["component_id"], [halloween["collection_id"], favorites["collection_id"]])
            catalog.set_library_asset_collections("scene", summer["component_id"], [favorites["collection_id"]])
            snapshot = catalog.creative_library_pack_snapshot("starter")
            scoped, _ = recipe_module._scope_creative_library_snapshot(snapshot, {
                "libraries": ["scenes"],
                "component_scopes": {"scene": {
                    "pack_collections": ["Halloween Scenes"],
                    "included_pack_collections": ["Halloween Scenes"],
                    "filter_pack_collections": True,
                }},
                "include_dependencies": True,
                "include_taxonomy": True,
            })
            self.assertEqual([row["value"] for row in scoped["components"]], [spooky["value"]])
            self.assertEqual([group["name"] for group in scoped["components"][0]["pack_collections"]], ["Halloween Scenes"])
            self.assertEqual([row["name"] for row in scoped["library_collections"]], ["Halloween Scenes"])

class CreativeLibraryPackTests(unittest.TestCase):
    def test_legacy_preview_roots_merge_into_one_creative_library_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            primary = root / "recipe_previews"; primary.mkdir()
            components = root / "recipe_component_previews"; components.mkdir()
            (primary / "prompt.webp").write_bytes(b"prompt-preview")
            (components / "scene.webp").write_bytes(b"scene-preview")
            original_catalog = recipe_module.get_catalog
            try:
                recipe_module.get_catalog = lambda: catalog
                preview_root = recipe_module._preview_directory()
                component_root = recipe_module._component_preview_directory()
            finally:
                recipe_module.get_catalog = original_catalog

            self.assertEqual(preview_root, root / "creative_library_previews")
            self.assertEqual(component_root, preview_root)
            self.assertEqual((preview_root / "prompt.webp").read_bytes(), b"prompt-preview")
            self.assertEqual((preview_root / "scene.webp").read_bytes(), b"scene-preview")
            self.assertFalse(primary.exists())
            self.assertFalse(components.exists())

    def test_starter_pack_round_trip_preserves_local_state_and_imports_missing_preview_and_scene_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_catalog = catalog_module.SoloCatalog(root / "source.sqlite3")
            target_catalog = catalog_module.SoloCatalog(root / "target.sqlite3")
            source_previews = root / "source-previews"; source_previews.mkdir()
            source_components = root / "source-components"; source_components.mkdir()
            target_previews = root / "target-previews"; target_previews.mkdir()
            target_components = root / "target-components"; target_components.mkdir()

            prompt, _ = source_catalog.import_prompt_asset({
                "value": "A candid portrait beside a roadside motel sign.",
                "kind": "prompt", "primary_parent": "Travel", "primary_subcategory": "Roadside",
            })
            source_catalog.set_prompt_rating(prompt["prompt_id"], 5)
            prompt_preview = "prompt.webp"
            Image.new("RGB", (80, 100), "white").save(source_previews / prompt_preview, "WEBP")
            source_catalog.set_prompt_preview(prompt["prompt_id"], prompt_preview, resolved_seed=4815162342, resolved_seed_source="preview-image")

            scene = source_catalog.upsert_recipe_component("scene", "sun-drenched tropical beach with turquoise water", manual=True)
            source_catalog.set_component_rating(scene["component_id"], 4)
            parent = source_catalog.create_component_collection("scene", "Tropical")
            child = source_catalog.create_component_collection("scene", "Beaches", parent_id=parent["collection_id"])
            source_catalog.set_component_collections(scene["component_id"], [child["collection_id"]])
            scene_preview = "scene.webp"
            Image.new("RGB", (100, 80), "white").save(source_components / scene_preview, "WEBP")
            source_catalog.set_recipe_component_preview("scene", scene["value"], scene_preview)

            local, _ = target_catalog.import_prompt_asset({
                "value": prompt["value"], "kind": "prompt", "primary_parent": "Local", "primary_subcategory": "Keep Me",
            })
            target_catalog.set_prompt_rating(local["prompt_id"], 2)

            original_catalog = recipe_module.get_catalog
            original_preview = recipe_module._preview_directory
            original_component_preview = recipe_module._component_preview_directory
            original_sync = recipe_module._safe_sync_recipe_prompt_logs
            try:
                recipe_module.get_catalog = lambda: source_catalog
                recipe_module._preview_directory = lambda: source_previews
                recipe_module._component_preview_directory = lambda: source_components
                recipe_module._safe_sync_recipe_prompt_logs = lambda **_: {"ok": True}
                raw, _, manifest = recipe_module._creative_library_pack_export({"mode": "starter", "name": "Master", "creator": "Sick Ollie", "version": "1.0"})
                _, _, next_manifest = recipe_module._creative_library_pack_export({"mode": "starter", "name": "Master", "creator": "Sick Ollie", "version": "1.1"})
                pack_path = root / "master.soslibrary"; pack_path.write_bytes(raw)

                recipe_module.get_catalog = lambda: target_catalog
                recipe_module._preview_directory = lambda: target_previews
                recipe_module._component_preview_directory = lambda: target_components
                imported = recipe_module._creative_library_pack_import(pack_path)
                imported_again = recipe_module._creative_library_pack_import(pack_path)
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._preview_directory = original_preview
                recipe_module._component_preview_directory = original_component_preview
                recipe_module._safe_sync_recipe_prompt_logs = original_sync

            with target_catalog._connection() as db:
                local_row = db.execute(
                    """SELECT p.primary_parent,p.primary_subcategory,COALESCE(r.rating,0) AS rating,p.preview_ref,p.resolved_seed
                    FROM prompt_assets p LEFT JOIN prompt_reviews r ON r.prompt_id=p.prompt_id WHERE p.prompt_id=?""",
                    (local["prompt_id"],),
                ).fetchone()
                scene_row = db.execute(
                    """SELECT c.component_id,c.preview_ref,COALESCE(r.rating,0) AS rating
                    FROM recipe_components c LEFT JOIN component_reviews r ON r.component_id=c.component_id
                    WHERE c.kind='scene' AND c.value=? COLLATE NOCASE""",
                    (scene["value"],),
                ).fetchone()
                memberships = db.execute(
                    """SELECT child.name AS child,parent.name AS parent FROM component_collection_memberships m
                    JOIN component_collections child ON child.collection_id=m.collection_id
                    LEFT JOIN component_collections parent ON parent.collection_id=child.parent_id
                    WHERE m.component_id=?""", (scene_row["component_id"],),
                ).fetchall()
                prompt_count = db.execute("SELECT COUNT(*) FROM prompt_assets WHERE value=? COLLATE NOCASE", (prompt["value"],)).fetchone()[0]
                scene_count = db.execute("SELECT COUNT(*) FROM recipe_components WHERE kind='scene' AND value=? COLLATE NOCASE", (scene["value"],)).fetchone()[0]

        self.assertEqual(manifest["format"], "sickollie-creative-library-pack")
        self.assertEqual(manifest["pack_id"], next_manifest["pack_id"])
        self.assertEqual(manifest["counts"]["thumbnails"], 2)
        self.assertEqual(imported["matched_prompts"], 1)
        self.assertEqual(imported["previews_added"], 2)
        self.assertEqual(imported_again["created_prompts"], 0)
        self.assertEqual(imported_again["created_components"], 0)
        self.assertEqual(prompt_count, 1)
        self.assertEqual(scene_count, 1)
        self.assertEqual(local_row["rating"], 2)
        self.assertEqual(local_row["resolved_seed"], 4815162342)
        self.assertEqual(local_row["primary_parent"], "Local")
        self.assertEqual(local_row["primary_subcategory"], "Keep Me")
        self.assertTrue(local_row["preview_ref"])
        self.assertEqual(scene_row["rating"], 4)
        self.assertTrue(scene_row["preview_ref"])
        self.assertIn(("Beaches", "Tropical"), [(row["child"], row["parent"]) for row in memberships])

    def test_scenes_only_import_repairs_broken_preview_refs_and_preserves_real_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_catalog = catalog_module.SoloCatalog(root / "source.sqlite3")
            target_catalog = catalog_module.SoloCatalog(root / "target.sqlite3")
            source_previews = root / "source-previews"; source_previews.mkdir()
            source_components = root / "source-components"; source_components.mkdir()
            target_previews = root / "target-previews"; target_previews.mkdir()
            target_components = root / "target-components"

            value = "a cherry blossom grove in Kyoto at night, pale blossoms glowing under lantern light"
            source_scene = source_catalog.upsert_recipe_component("scene", value, manual=True)
            Image.new("RGB", (120, 80), "orchid").save(source_components / "kyoto.webp", "WEBP")
            source_catalog.set_recipe_component_preview("scene", source_scene["value"], "kyoto.webp")

            target_scene = target_catalog.upsert_recipe_component("scene", value, manual=True)
            target_catalog.set_recipe_component_preview("scene", target_scene["value"], "missing-scene.webp")

            original_catalog = recipe_module.get_catalog
            original_preview = recipe_module._preview_directory
            original_component_preview = recipe_module._component_preview_directory
            original_sync = recipe_module._safe_sync_recipe_prompt_logs
            try:
                recipe_module.get_catalog = lambda: source_catalog
                recipe_module._preview_directory = lambda: source_previews
                recipe_module._component_preview_directory = lambda: source_components
                recipe_module._safe_sync_recipe_prompt_logs = lambda **_: {"ok": True}
                raw, _, _ = recipe_module._creative_library_pack_export({
                    "mode": "starter",
                    "name": "Scenes Only",
                    "selection": {"libraries": ["scenes"], "include_thumbnails": True},
                })
                pack_path = root / "scenes-only.soslibrary"; pack_path.write_bytes(raw)

                recipe_module.get_catalog = lambda: target_catalog
                recipe_module._preview_directory = lambda: target_previews
                recipe_module._component_preview_directory = lambda: target_components
                imported = recipe_module._creative_library_pack_import(pack_path, {
                    "libraries": ["scenes"],
                    "include_thumbnails": True,
                    "include_taxonomy": True,
                    "include_dependencies": True,
                })
                with target_catalog._connection() as db:
                    repaired_ref = str(db.execute(
                        "SELECT preview_ref FROM recipe_components WHERE component_id=?",
                        (target_scene["component_id"],),
                    ).fetchone()[0])
                imported_again = recipe_module._creative_library_pack_import(pack_path, {
                    "libraries": ["scenes"],
                    "include_thumbnails": True,
                    "include_taxonomy": True,
                    "include_dependencies": True,
                })
                with target_catalog._connection() as db:
                    preserved_ref = str(db.execute(
                        "SELECT preview_ref FROM recipe_components WHERE component_id=?",
                        (target_scene["component_id"],),
                    ).fetchone()[0])
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._preview_directory = original_preview
                recipe_module._component_preview_directory = original_component_preview
                recipe_module._safe_sync_recipe_prompt_logs = original_sync

            repaired_path = target_components / repaired_ref
            self.assertEqual(imported["matched_components"], 1)
            self.assertEqual(imported["previews_added"], 1)
            self.assertNotEqual(repaired_ref, "missing-scene.webp")
            self.assertTrue(repaired_path.is_file())
            with Image.open(repaired_path) as image:
                self.assertEqual(image.size, (120, 80))
            self.assertEqual(imported_again["previews_added"], 0)
            self.assertEqual(preserved_ref, repaired_ref)

    def test_same_pack_update_reconciles_pack_owned_scene_memberships_and_preserves_local_extras(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            scene = catalog.upsert_recipe_component("scene", "a quiet seaside promenade at blue hour", manual=True)
            old_parent = catalog.create_component_collection("scene", "Old Coast")
            old_child = catalog.create_component_collection("scene", "Old Shore", parent_id=old_parent["collection_id"])
            new_parent = catalog.create_component_collection("scene", "Beach & Coast")
            new_child = catalog.create_component_collection("scene", "Oceanfront & Shore", parent_id=new_parent["collection_id"])
            local = catalog.create_component_collection("scene", "My Favorites")
            catalog.set_component_collections(scene["component_id"], [old_child["collection_id"], local["collection_id"]])

            manifest = {
                "pack_id": "soslibrary:test-master", "name": "Master", "version": "1.1",
                "export_mode": "starter",
            }
            data = {
                "components": [{
                    "kind": "scene", "value": scene["value"],
                    "collections": [{"name": "Oceanfront & Shore", "parent_name": "Beach & Coast"}],
                }],
                "component_collections": [
                    {"kind": "scene", "name": "Beach & Coast", "parent_name": ""},
                    {"kind": "scene", "name": "Oceanfront & Shore", "parent_name": "Beach & Coast"},
                ],
                "previous_component_memberships": [{
                    "kind": "scene", "value": scene["value"],
                    "collections": [{"name": "Old Shore", "parent_name": "Old Coast"}],
                }],
            }
            first = catalog.merge_creative_library_pack_records(manifest, data)
            with catalog._connection() as db:
                first_names = {str(row[0]) for row in db.execute(
                    """SELECT cc.name FROM component_collection_memberships m
                    JOIN component_collections cc ON cc.collection_id=m.collection_id
                    WHERE m.component_id=?""", (scene["component_id"],),
                ).fetchall()}
                owned = db.execute(
                    "SELECT COUNT(*) FROM creative_library_pack_component_memberships WHERE pack_id=?",
                    (manifest["pack_id"],),
                ).fetchone()[0]
            self.assertEqual(first["memberships_removed"], 1)
            self.assertEqual(first_names, {"Oceanfront & Shore", "My Favorites"})
            self.assertEqual(owned, 1)

            third_parent = catalog.create_component_collection("scene", "Water & Wetlands")
            third_child = catalog.create_component_collection("scene", "Lakes & Rivers", parent_id=third_parent["collection_id"])
            manifest2 = {**manifest, "version": "1.2"}
            data2 = {
                "components": [{
                    "kind": "scene", "value": scene["value"],
                    "collections": [{"name": "Lakes & Rivers", "parent_name": "Water & Wetlands"}],
                }],
                "component_collections": [
                    {"kind": "scene", "name": "Water & Wetlands", "parent_name": ""},
                    {"kind": "scene", "name": "Lakes & Rivers", "parent_name": "Water & Wetlands"},
                ],
            }
            second = catalog.merge_creative_library_pack_records(manifest2, data2)
            with catalog._connection() as db:
                second_names = {str(row[0]) for row in db.execute(
                    """SELECT cc.name FROM component_collection_memberships m
                    JOIN component_collections cc ON cc.collection_id=m.collection_id
                    WHERE m.component_id=?""", (scene["component_id"],),
                ).fetchall()}
            self.assertEqual(second["memberships_removed"], 1)
            self.assertEqual(second_names, {"Lakes & Rivers", "My Favorites"})

    def test_export_includes_installed_pack_membership_baseline_for_future_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            scene = catalog.upsert_recipe_component("scene", "a neon rooftop overlooking downtown", manual=True)
            parent = catalog.create_component_collection("scene", "Urban")
            child = catalog.create_component_collection("scene", "Rooftops & Skylines", parent_id=parent["collection_id"])
            catalog.merge_creative_library_pack_records(
                {"pack_id": "soslibrary:test-export", "name": "Master", "creator": "Sick Ollie", "version": "1.0", "export_mode": "starter"},
                {
                    "components": [{"kind": "scene", "value": scene["value"], "collections": [{"name": "Rooftops & Skylines", "parent_name": "Urban"}]}],
                    "component_collections": [
                        {"kind": "scene", "name": "Urban", "parent_name": ""},
                        {"kind": "scene", "name": "Rooftops & Skylines", "parent_name": "Urban"},
                    ],
                },
            )
            original_catalog = recipe_module.get_catalog
            original_preview = recipe_module._preview_directory
            original_component_preview = recipe_module._component_preview_directory
            try:
                recipe_module.get_catalog = lambda: catalog
                recipe_module._preview_directory = lambda: root / "previews"
                recipe_module._component_preview_directory = lambda: root / "component-previews"
                (root / "previews").mkdir(); (root / "component-previews").mkdir()
                raw, _, manifest = recipe_module._creative_library_pack_export({
                    "mode": "starter", "name": "Master", "creator": "Sick Ollie", "version": "1.1",
                    "pack_id": "soslibrary:test-export",
                })
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._preview_directory = original_preview
                recipe_module._component_preview_directory = original_component_preview
            with zipfile.ZipFile(BytesIO(raw), "r") as archive:
                self.assertIn("library/previous-component-memberships.json", archive.namelist())
                baseline = json.loads(archive.read("library/previous-component-memberships.json"))
            self.assertEqual(manifest["merge_policy"], "preserve-local-reconcile-pack-memberships")
            self.assertEqual(len(baseline), 1)
            self.assertEqual(baseline[0]["collections"][0]["name"], "Rooftops & Skylines")

    def test_manifest_inspection_and_selective_import_install_only_requested_prompt_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = catalog_module.SoloCatalog(root / "source.sqlite3")
            target = catalog_module.SoloCatalog(root / "target.sqlite3")
            source.import_prompt_asset({"value": "city prompt", "kind": "prompt", "primary_parent": "Urban", "primary_subcategory": "Street"})
            source.import_prompt_asset({"value": "beach prompt", "kind": "prompt", "primary_parent": "Coast", "primary_subcategory": "Beach"})
            source_previews = root / "source-previews"; source_previews.mkdir()
            source_components = root / "source-components"; source_components.mkdir()
            target_previews = root / "target-previews"; target_previews.mkdir()
            target_components = root / "target-components"; target_components.mkdir()
            original_catalog = recipe_module.get_catalog
            original_preview = recipe_module._preview_directory
            original_component_preview = recipe_module._component_preview_directory
            original_sync = recipe_module._safe_sync_recipe_prompt_logs
            try:
                recipe_module.get_catalog = lambda: source
                recipe_module._preview_directory = lambda: source_previews
                recipe_module._component_preview_directory = lambda: source_components
                recipe_module._safe_sync_recipe_prompt_logs = lambda **_: {"ok": True}
                raw, _, manifest = recipe_module._creative_library_pack_export({
                    "mode": "starter", "name": "Two Prompt Pack",
                    "selection": {"libraries": ["prompts"], "include_thumbnails": False},
                })
                pack_path = root / "two-prompts.soslibrary"; pack_path.write_bytes(raw)
                inspection = recipe_module._creative_library_pack_inspect(pack_path)

                recipe_module.get_catalog = lambda: target
                recipe_module._preview_directory = lambda: target_previews
                recipe_module._component_preview_directory = lambda: target_components
                result = recipe_module._creative_library_pack_import(pack_path, {
                    "libraries": ["prompts"],
                    "prompt_scopes": {"prompt": {"parents": ["Urban"]}},
                    "include_thumbnails": False,
                    "include_taxonomy": True,
                    "include_dependencies": True,
                })
                imported = target.indexed_prompt_assets()
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._preview_directory = original_preview
                recipe_module._component_preview_directory = original_component_preview
                recipe_module._safe_sync_recipe_prompt_logs = original_sync

        self.assertEqual(manifest["schema_version"], 3)
        self.assertEqual(inspection["contents"]["counts"]["prompts"], 2)
        self.assertEqual(manifest["counts"]["thumbnails"], 0)
        self.assertTrue(result["selective"])
        self.assertEqual([row["value"] for row in imported], ["city prompt"])

    def test_shareable_pack_keeps_prompt_log_provenance_for_log_level_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            catalog.import_prompt_assets(
                [{"value": "Nest opening", "facets": {}, "source_line": 1}],
                parent="Candid", subcategory="Party",
                source_path="Imported Logs/Candid/Party/Nest Roll Journey.txt",
                source_label="Nest Roll Journey",
            )
            catalog.import_prompt_assets(
                [{"value": "Electric opening", "facets": {}, "source_line": 1}],
                parent="Candid", subcategory="Party",
                source_path="Imported Logs/Candid/Party/Electric Forest.txt",
                source_label="Electric Forest",
            )
            snapshot = catalog.creative_library_pack_snapshot("starter")
            scoped, _selection = recipe_module._scope_creative_library_snapshot(snapshot, {
                "libraries": ["prompts"],
                "prompt_scopes": {
                    "prompt": {"source_paths": ["Imported Logs/Candid/Party/Nest Roll Journey.txt"]}
                },
            })
            target = catalog_module.SoloCatalog(Path(directory) / "target.sqlite3")
            target.merge_creative_library_pack_records(
                {"pack_id": "log-level-pack", "name": "Log Level", "export_mode": "starter"}, scoped
            )
            imported = target.indexed_prompt_assets()

        self.assertEqual([row["value"] for row in scoped["prompts"]], ["Nest opening"])
        self.assertEqual(scoped["prompts"][0]["sources"][0]["line_number"], 1)
        self.assertEqual([row["value"] for row in imported], ["Nest opening"])
        self.assertEqual(imported[0]["sources"][0]["source_label"], "Nest Roll Journey")

    def test_shareable_pack_round_trip_preserves_manual_prompt_structure_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = catalog_module.SoloCatalog(root / "source.sqlite3")
            target = catalog_module.SoloCatalog(root / "target.sqlite3")
            source_path = "Imported Logs/Candid/Party/Nest Roll Journey.txt"
            source.import_prompt_assets(
                [{"value": "Nest opening", "facets": {}, "source_line": 1}],
                parent="Candid", subcategory="Party", source_path=source_path, source_label="Nest Roll Journey",
            )
            source.set_creative_structure_order("prompt", {
                "parents": ["Future Sets", "Candid"],
                "subcategories": {"Future Sets": ["Reserved"], "Candid": ["Party"]},
                "logs": {"Candid": {"Party": [source_path]}},
            })
            source_previews = root / "source-previews"; source_previews.mkdir()
            source_components = root / "source-components"; source_components.mkdir()
            target_previews = root / "target-previews"; target_previews.mkdir()
            target_components = root / "target-components"; target_components.mkdir()
            original_catalog = recipe_module.get_catalog
            original_preview = recipe_module._preview_directory
            original_component_preview = recipe_module._component_preview_directory
            original_sync = recipe_module._safe_sync_recipe_prompt_logs
            try:
                recipe_module.get_catalog = lambda: source
                recipe_module._preview_directory = lambda: source_previews
                recipe_module._component_preview_directory = lambda: source_components
                recipe_module._safe_sync_recipe_prompt_logs = lambda **_: {"ok": True}
                raw, _, _manifest = recipe_module._creative_library_pack_export({
                    "mode": "starter", "name": "Ordered Prompts",
                    "selection": {"libraries": ["prompts"], "include_thumbnails": False, "include_taxonomy": True},
                })
                pack_path = root / "ordered.soslibrary"; pack_path.write_bytes(raw)
                with zipfile.ZipFile(BytesIO(raw), "r") as archive:
                    packed_order = json.loads(archive.read("library/structure-order.json"))

                recipe_module.get_catalog = lambda: target
                recipe_module._preview_directory = lambda: target_previews
                recipe_module._component_preview_directory = lambda: target_components
                recipe_module._creative_library_pack_import(pack_path)
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._preview_directory = original_preview
                recipe_module._component_preview_directory = original_component_preview
                recipe_module._safe_sync_recipe_prompt_logs = original_sync

            restored = target.creative_structure_order("prompt")

        self.assertEqual(packed_order["prompt"]["parents"], ["Future Sets", "Candid"])
        self.assertEqual(restored["parents"], ["Future Sets", "Candid"])
        self.assertEqual(restored["subcategories"]["Future Sets"], ["Reserved"])
        self.assertEqual(restored["logs"]["Candid"]["Party"], [source_path])

    def test_partial_prompt_pack_prunes_unchecked_log_and_showcase_memberships(self) -> None:
        snapshot = {
            "mode": "starter",
            "prompts": [{
                "source_prompt_id": "prompt:shared", "kind": "prompt", "value": "Shared party prompt",
                "primary_parent": "Candid", "primary_subcategory": "Party",
                "collections": [{"name": "Keep"}, {"name": "Skip"}],
                "sources": [
                    {"source_path": "Imported Logs/Candid/Party/Keep.txt", "line_number": 1},
                    {"source_path": "Imported Logs/Candid/Party/Skip.txt", "line_number": 2},
                ],
            }],
            "recipes": [], "components": [], "wardrobe_items": [], "wardrobe_relations": [],
            "fragments": [], "boards": [], "recipe_collections": [],
            "prompt_showcase_collections": [
                {"kind": "prompt", "name": "Keep"}, {"kind": "prompt", "name": "Skip"},
            ],
            "component_collections": [], "structure_order": {},
        }
        scoped, _selection = recipe_module._scope_creative_library_snapshot(snapshot, {
            "libraries": ["prompts"],
            "prompt_scopes": {"prompt": {
                "parents": ["Candid"],
                "included_collections": ["Keep"], "filter_collections": True,
                "included_source_paths": ["Imported Logs/Candid/Party/Keep.txt"], "filter_sources": True,
            }},
        })
        self.assertEqual([row["name"] for row in scoped["prompts"][0]["collections"]], ["Keep"])
        self.assertEqual([row["source_path"] for row in scoped["prompts"][0]["sources"]], ["Imported Logs/Candid/Party/Keep.txt"])
        self.assertEqual([row["name"] for row in scoped["prompt_showcase_collections"]], ["Keep"])

    def test_selective_outfit_scope_carries_only_linked_wardrobe_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            first = catalog.upsert_recipe_component("outfit", "pink tank with denim shorts", manual=True)
            second = catalog.upsert_recipe_component("outfit", "black dress with boots", manual=True)
            tank = catalog.upsert_wardrobe_item("piece", "pink tank", category="Tops", subtype="Tank")
            shorts = catalog.upsert_wardrobe_item("piece", "denim shorts", category="Bottoms", subtype="Shorts")
            dress = catalog.upsert_wardrobe_item("piece", "black dress", category="Dresses", subtype="Mini")
            catalog.set_wardrobe_look_parts(first["component_id"], [
                {"wardrobe_id": tank["wardrobe_id"], "relation": "top"},
                {"wardrobe_id": shorts["wardrobe_id"], "relation": "bottom"},
            ])
            catalog.set_wardrobe_look_parts(second["component_id"], [{"wardrobe_id": dress["wardrobe_id"], "relation": "dress"}])
            snapshot = catalog.creative_library_pack_snapshot("starter")
            scoped, selection = recipe_module._scope_creative_library_snapshot(snapshot, {
                "libraries": ["outfits"],
                "component_scopes": {"outfit": {"ids": [first["component_id"]]}},
                "include_dependencies": True,
            })

        self.assertEqual([row["value"] for row in scoped["components"]], ["pink tank with denim shorts"])
        self.assertEqual({row["value"] for row in scoped["wardrobe_items"]}, {"pink tank", "denim shorts"})
        self.assertEqual(len(scoped["wardrobe_relations"]), 2)
        self.assertIn("wardrobe", selection["libraries"])

    def test_selective_pack_update_preserves_unselected_pack_owned_memberships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            pack_id = "soslibrary:selective-membership-test"
            initial = {
                "components": [
                    {"kind": "scene", "value": "scene alpha", "collections": [{"name": "Old Alpha", "parent_name": "Old"}]},
                    {"kind": "scene", "value": "scene beta", "collections": [{"name": "Old Beta", "parent_name": "Old"}]},
                ],
                "component_collections": [
                    {"kind": "scene", "name": "Old", "parent_name": ""},
                    {"kind": "scene", "name": "Old Alpha", "parent_name": "Old"},
                    {"kind": "scene", "name": "Old Beta", "parent_name": "Old"},
                ],
            }
            catalog.merge_creative_library_pack_records({"pack_id": pack_id, "name": "Test", "export_mode": "starter"}, initial)
            update = {
                "components": [{"kind": "scene", "value": "scene alpha", "collections": [{"name": "New Alpha", "parent_name": "New"}]}],
                "component_collections": [
                    {"kind": "scene", "name": "New", "parent_name": ""},
                    {"kind": "scene", "name": "New Alpha", "parent_name": "New"},
                ],
            }
            catalog.merge_creative_library_pack_records({
                "pack_id": pack_id, "name": "Test", "export_mode": "starter",
                "selective_import": True, "import_taxonomy": True,
            }, update)
            with catalog._connection() as db:
                rows = db.execute(
                    """SELECT c.value, cc.name FROM component_collection_memberships m
                    JOIN recipe_components c ON c.component_id=m.component_id
                    JOIN component_collections cc ON cc.collection_id=m.collection_id
                    ORDER BY c.value, cc.name"""
                ).fetchall()
                owned = db.execute(
                    """SELECT c.value, cc.name FROM creative_library_pack_component_memberships p
                    JOIN recipe_components c ON c.component_id=p.component_id
                    JOIN component_collections cc ON cc.collection_id=p.collection_id
                    WHERE p.pack_id=? ORDER BY c.value, cc.name""", (pack_id,),
                ).fetchall()

        self.assertEqual([(row["value"], row["name"]) for row in rows], [("scene alpha", "New Alpha"), ("scene beta", "Old Beta")])
        self.assertEqual([(row["value"], row["name"]) for row in owned], [("scene alpha", "New Alpha"), ("scene beta", "Old Beta")])

    def test_selective_import_without_taxonomy_does_not_remove_existing_pack_memberships(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            pack_id = "soslibrary:no-taxonomy-test"
            catalog.merge_creative_library_pack_records({"pack_id": pack_id, "name": "Test", "export_mode": "starter"}, {
                "components": [{"kind": "scene", "value": "scene alpha", "collections": [{"name": "Shore", "parent_name": "Coast"}]}],
                "component_collections": [
                    {"kind": "scene", "name": "Coast", "parent_name": ""},
                    {"kind": "scene", "name": "Shore", "parent_name": "Coast"},
                ],
            })
            catalog.merge_creative_library_pack_records({
                "pack_id": pack_id, "name": "Test", "export_mode": "starter",
                "selective_import": True, "import_taxonomy": False,
            }, {"components": [{"kind": "scene", "value": "scene alpha", "collections": []}], "component_collections": []})
            with catalog._connection() as db:
                names = [row[0] for row in db.execute(
                    """SELECT cc.name FROM component_collection_memberships m
                    JOIN recipe_components c ON c.component_id=m.component_id
                    JOIN component_collections cc ON cc.collection_id=m.collection_id
                    WHERE c.value='scene alpha'"""
                ).fetchall()]
                owned = db.execute("SELECT COUNT(*) FROM creative_library_pack_component_memberships WHERE pack_id=?", (pack_id,)).fetchone()[0]

        self.assertEqual(names, ["Shore"])
        self.assertEqual(owned, 1)

    def test_orphan_thumbnail_cleaner_preserves_every_live_reference(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = catalog_module.SoloCatalog(root / "catalog.sqlite3")
            previews = root / "creative_library_previews"; previews.mkdir()
            prompt, _ = catalog.import_prompt_asset({"value": "a prompt", "kind": "prompt"})
            catalog.set_prompt_preview(prompt["prompt_id"], "keep-prompt.webp")
            scene = catalog.upsert_recipe_component("scene", "a quiet beach", manual=True)
            catalog.set_recipe_component_preview("scene", scene["value"], "keep-scene.webp")
            wardrobe = catalog.upsert_wardrobe_item("piece", "white tank", category="Tops", subtype="Tank")
            catalog.set_wardrobe_preview("piece", wardrobe["value"], "keep-wardrobe.webp", category="Tops", subtype="Tank")
            for path in [previews / "keep-prompt.webp", previews / "keep-scene.webp", previews / "keep-wardrobe.webp", previews / "orphan-a.webp", previews / "orphan-b.png"]:
                path.write_bytes(b"test-bytes")
            original_catalog = recipe_module.get_catalog
            original_preview = recipe_module._preview_directory
            original_component_preview = recipe_module._component_preview_directory
            try:
                recipe_module.get_catalog = lambda: catalog
                recipe_module._preview_directory = lambda: previews
                recipe_module._component_preview_directory = lambda: previews
                scan = recipe_module._creative_library_orphan_previews(delete=False)
                cleaned = recipe_module._creative_library_orphan_previews(delete=True)
            finally:
                recipe_module.get_catalog = original_catalog
                recipe_module._preview_directory = original_preview
                recipe_module._component_preview_directory = original_component_preview
            file_state = {
                "prompt": (previews / "keep-prompt.webp").exists(),
                "scene": (previews / "keep-scene.webp").exists(),
                "wardrobe": (previews / "keep-wardrobe.webp").exists(),
                "orphan_a": (previews / "orphan-a.webp").exists(),
                "orphan_b": (previews / "orphan-b.png").exists(),
            }

        self.assertEqual(scan["orphans"], 2)
        self.assertEqual(cleaned["deleted"], 2)
        self.assertTrue(file_state["prompt"])
        self.assertTrue(file_state["scene"])
        self.assertTrue(file_state["wardrobe"])
        self.assertFalse(file_state["orphan_a"])
        self.assertFalse(file_state["orphan_b"])

    def test_backup_pack_snapshot_restores_provenance_fragments_and_boards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = catalog_module.SoloCatalog(root / "source.sqlite3")
            prompt, _ = source.import_prompt_asset({"value": "Soft window-light portrait", "kind": "prompt"})
            with source._connection() as db:
                db.execute(
                    "INSERT INTO prompt_sources(prompt_id,source_path,line_number,source_label,created_at) VALUES(?,?,?,?,?)",
                    (prompt["prompt_id"], "Standard/Source.txt", 7, "Source", catalog_module._now()),
                )
                db.execute("UPDATE prompt_assets SET source_count=1 WHERE prompt_id=?", (prompt["prompt_id"],))
            wardrobe = source.upsert_wardrobe_item("piece", "white ribbed tank top", category="Tops", subtype="Tank")
            wardrobe_source = source.upsert_wardrobe_source("log", "Outfits/Master.txt", label="Master", metadata={"version": 1})
            source.link_wardrobe_source(wardrobe["wardrobe_id"], wardrobe_source["source_id"])
            source.replace_mined_fragments([{
                "role": "lighting", "value": "soft window light", "confidence": 0.95, "review_state": "approved",
                "source_prompt_ids": [prompt["prompt_id"]],
                "source_files": [{"source_path": "Standard/Source.txt", "line_number": 7, "source_type": "prompt-log"}],
            }], signature="backup-test")
            source.save_creative_board("", "Favorite Mix", {"hello": "world"})

            snapshot = source.creative_library_pack_snapshot("backup")
            target = catalog_module.SoloCatalog(root / "target.sqlite3")
            target.merge_creative_library_pack_records({"pack_id": "backup-test", "name": "Backup", "export_mode": "backup"}, snapshot)
            with target._connection() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM prompt_sources").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM wardrobe_item_sources").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM fragment_prompt_memberships").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM fragment_file_sources").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM creative_boards WHERE name='Favorite Mix'").fetchone()[0], 1)
