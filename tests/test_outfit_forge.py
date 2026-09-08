from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "sickollie_outfit_forge_test"
PACKAGE = types.ModuleType(PACKAGE_NAME)
PACKAGE.__path__ = [str(ROOT)]
sys.modules.setdefault(PACKAGE_NAME, PACKAGE)


def load(name: str):
    qualified = f"{PACKAGE_NAME}.{name}"
    spec = importlib.util.spec_from_file_location(qualified, ROOT / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


anchored_module = load("outfit_forge_anchored_catalog")
catalog_module = load("solo_catalog")
forge_module = load("solo_outfit_forge")


class OutfitForgeTests(unittest.TestCase):
    def test_theme_aware_generation_is_deterministic_unique_and_single_line(self) -> None:
        payload = {"theme": "haunted porcelain doll rave", "count": 100, "seed": 442211}
        first = forge_module.generate_outfits(payload)
        second = forge_module.generate_outfits(payload)

        self.assertEqual(first["lines"], second["lines"])
        self.assertEqual(first["packs"], ["rave"])
        self.assertEqual(len(first["lines"]), 100)
        self.assertEqual(len({line.casefold() for line in first["lines"]}), 100)
        self.assertTrue(all(line and "\n" not in line and "\r" not in line for line in first["lines"]))
        self.assertEqual(first["audit"]["exact_duplicate_count"], 0)
        self.assertEqual(first["audit"]["repeated_opening_count"], 0)
        self.assertGreaterEqual(first["audit"]["score"], 95)

    def test_narrow_garment_theme_stays_in_family_and_uses_clear_prompt_phrases(self) -> None:
        result = forge_module.generate_outfits({
            "theme": "cute sundresses", "count": 100, "seed": 168589834,
            "coverage": 3, "complexity": 3, "realism": 3,
        })

        self.assertEqual(result["packs"], ["dresses"])
        self.assertEqual(result["garment_family"]["id"], "sundress")
        self.assertEqual(result["style_overlays"], ["cute"])
        self.assertEqual(result["experimental_count"], 0)
        self.assertTrue(all("sundress" in line.casefold() for line in result["lines"]))
        self.assertTrue(all("cute sundresses" not in line.casefold() for line in result["lines"]))
        self.assertTrue(all(not line.endswith(".") for line in result["lines"]))
        self.assertLessEqual(max(len(line.split()) for line in result["lines"]), 28)
        self.assertFalse(any("fan geometry" in line.casefold() or "orbital rings" in line.casefold() for line in result["lines"]))
        self.assertEqual(result["audit"]["score"], 100)

    def test_theme_only_overalls_is_a_binding_garment_constraint(self) -> None:
        result = forge_module.generate_outfits({"theme": "overalls", "count": 100, "seed": 1283161652})

        self.assertEqual(result["fidelity"]["interpreted"]["pieces"], ["overalls"])
        self.assertTrue(all("overalls" in line.casefold() for line in result["lines"]))
        self.assertEqual(result["fidelity"]["score"], 100)
        self.assertEqual(len({line.casefold() for line in result["lines"]}), 100)

    def test_theme_only_material_is_preserved_in_every_outfit(self) -> None:
        result = forge_module.generate_outfits({"theme": "velvet", "count": 100, "seed": 1866319177})

        self.assertEqual(result["fidelity"]["interpreted"]["materials"], ["velvet"])
        self.assertTrue(all("velvet" in line.casefold() for line in result["lines"]))
        self.assertEqual(result["fidelity"]["score"], 100)

    def test_multiple_typed_garments_remain_in_every_outfit(self) -> None:
        result = forge_module.generate_outfits({"theme": "tshirt and windbreaker", "count": 100, "seed": 963308855})

        self.assertEqual(result["fidelity"]["interpreted"]["pieces"], ["T-shirt", "windbreaker"])
        self.assertTrue(all("t-shirt" in line.casefold() and "windbreaker" in line.casefold() for line in result["lines"]))
        self.assertEqual(result["fidelity"]["score"], 100)

    def test_piece_specific_colors_are_bound_to_the_requested_composition(self) -> None:
        result = forge_module.generate_outfits({
            "theme": "white turtleneck and black mini dress", "count": 100, "seed": 1866319177,
        })

        self.assertEqual(result["fidelity"]["interpreted"]["pieces"], ["turtleneck", "mini dress"])
        self.assertTrue(all("white" in line.casefold() and "turtleneck" in line.casefold() for line in result["lines"]))
        self.assertTrue(all("black" in line.casefold() and "mini dress" in line.casefold() for line in result["lines"]))
        self.assertEqual(result["fidelity"]["score"], 100)

    def test_piece_specific_color_and_material_survive_a_with_composition(self) -> None:
        result = forge_module.generate_outfits({
            "theme": "pink satin corset with jeans", "count": 100, "seed": 1866319177,
        })

        self.assertTrue(all(all(term in line.casefold() for term in ("pink", "satin", "corset", "jeans")) for line in result["lines"]))
        self.assertEqual(result["fidelity"]["score"], 100)

    def test_multiple_attributes_before_one_garment_are_combined_not_split(self) -> None:
        result = forge_module.generate_outfits({
            "theme": "black and white lace and satin dress", "count": 100, "seed": 9182,
        })

        self.assertTrue(all(all(term in line.casefold() for term in ("black", "white", "lace", "satin", "dress")) for line in result["lines"]))
        self.assertEqual(result["fidelity"]["score"], 100)

    def test_fidelity_report_rejects_an_edited_line_that_drops_a_typed_piece(self) -> None:
        brief = forge_module.parse_theme("t-shirt and windbreaker")
        report = forge_module.fidelity_report(["blue cotton T-shirt with soft shorts"], brief)

        self.assertFalse(report["ok"])
        self.assertEqual(report["score"], 0)
        self.assertIn("windbreaker", report["failed_lines"][0]["missing"])

    def test_output_shape_sliders_materially_change_generated_structure(self) -> None:
        base = {"theme": "cute sundresses", "count": 60, "seed": 7719}
        simple = forge_module.generate_outfits({**base, "complexity": 1})
        maximal = forge_module.generate_outfits({**base, "complexity": 5})
        dreamlike = forge_module.generate_outfits({**base, "realism": 1})
        wearable = forge_module.generate_outfits({**base, "realism": 5})
        exposed = forge_module.generate_outfits({**base, "coverage": 1})
        covered = forge_module.generate_outfits({**base, "coverage": 5})

        self.assertLess(median(len(line.split()) for line in simple["lines"]), median(len(line.split()) for line in maximal["lines"]))
        self.assertEqual(dreamlike["experimental_count"], 60)
        self.assertEqual(wearable["experimental_count"], 0)
        self.assertTrue(all(any(term in line.casefold() for term in ("ultra-short", "open back", "tiny shoulder straps", "high side slits", "plunging")) for line in exposed["lines"]))
        self.assertTrue(all(any(term in line.casefold() for term in ("ankle-length", "high neckline", "long sleeves", "complete lining", "closed side seams")) for line in covered["lines"]))

    def test_unknown_ordinary_theme_does_not_fall_into_experimental_couture(self) -> None:
        result = forge_module.generate_outfits({
            "theme": "retro roadside picnic", "count": 100, "seed": 5521,
            "coverage": 3, "complexity": 3, "realism": 3,
        })

        self.assertEqual(result["packs"], ["everyday"])
        self.assertEqual(result["experimental_count"], 0)
        self.assertFalse(any("inflatable" in line.casefold() or "kinetic mobile" in line.casefold() for line in result["lines"]))
        self.assertEqual(result["audit"]["score"], 100)
        self.assertEqual(result["fidelity"]["score"], 100)
        self.assertLess(result["fidelity"]["brief_coverage"]["score"], 100)
        self.assertIn("roadside", result["fidelity"]["brief_coverage"]["unrepresented"])

    def test_fidelity_does_not_claim_to_understand_an_unsupported_practical_brief(self) -> None:
        result = forge_module.generate_outfits({"theme": "minimal business casual", "count": 12, "seed": 77})
        coverage = result["fidelity"]["brief_coverage"]
        self.assertEqual(result["fidelity"]["constraints"], [])
        self.assertEqual(result["fidelity"]["score"], 100)
        self.assertEqual(coverage["score"], 0)
        self.assertEqual(coverage["unrepresented"], ["minimal", "business", "casual"])

    def test_clear_plausible_default_does_not_add_unrelated_geometry(self) -> None:
        result = forge_module.generate_outfits({
            "theme": "crystal body jewelry", "count": 100, "seed": 8812,
            "coverage": 3, "complexity": 3, "realism": 3,
        })

        self.assertEqual(result["experimental_count"], 0)
        self.assertFalse(any("cocoonlike outer shell" in line.casefold() for line in result["lines"]))

    def test_auto_pack_routing_changes_with_theme(self) -> None:
        cozy = forge_module.generate_outfits({"theme": "cozy rainy-day college clothes", "count": 12, "seed": 7})
        armor = forge_module.generate_outfits({"theme": "ceremonial alien bridal armor", "count": 12, "seed": 7})
        living = forge_module.generate_outfits({"theme": "bioluminescent fungal lingerie", "count": 12, "seed": 7})

        self.assertEqual(cozy["packs"], ["everyday", "cozy"])
        self.assertEqual(armor["packs"], ["formal", "armor"])
        self.assertEqual(living["packs"], ["lingerie", "organic"])
        self.assertNotEqual(cozy["lines"], armor["lines"])
        self.assertNotEqual(armor["lines"], living["lines"])

    def test_explicit_banks_required_terms_and_avoided_terms_are_honored(self) -> None:
        result = forge_module.generate_outfits({
            "theme": "glass garden formalwear",
            "packs": ["formal", "fantasy"],
            "count": 25,
            "seed": 91,
            "materials": "frosted glass organza\ncrystal-thread silk",
            "colors": "sea-glass green\nmoonlit silver",
            "required": "dew-drop clasp",
            "avoided": "leather\nlatex",
        })

        self.assertTrue(all("dew-drop clasp" in line.casefold() for line in result["lines"]))
        self.assertTrue(all("leather" not in line.casefold() and "latex" not in line.casefold() for line in result["lines"]))
        self.assertTrue(all(any(material in line.casefold() for material in ("frosted glass organza", "crystal-thread silk")) for line in result["lines"]))
        self.assertEqual(result["audit"]["unique_count"], 25)

    def test_anchored_preset_catalog_remains_available_as_editable_seed_data(self) -> None:
        self.assertEqual(len(anchored_module.THEMES), 37)
        self.assertEqual(len(anchored_module.STRUCTURES), 100)
        preset = anchored_module.THEMES[0]
        result = forge_module.generate_outfits({
            "theme": preset["name"],
            "packs": ["anchored"],
            "count": 100,
            "seed": 12,
            "materials": preset["materials"],
            "colors": preset["colors"],
            "fasteners": preset["anchors"],
            "motifs": preset["ornaments"],
            "effects": preset["behaviors"],
        })
        self.assertEqual(len(result["lines"]), 100)
        self.assertEqual(result["audit"]["exact_duplicate_count"], 0)
        self.assertEqual(result["audit"]["repeated_opening_count"], 0)

    def test_audit_reports_duplicates_openings_and_restriction_failures(self) -> None:
        lines = [
            "A pink satin dress with pearl buttons.",
            "A pink satin dress with pearl buttons.",
            "A pink satin coat with silver buttons.",
        ]
        audit = forge_module.audit_outfits(lines, required="barefoot", avoided="coat")
        self.assertFalse(audit["ok"])
        self.assertEqual(audit["exact_duplicate_count"], 1)
        self.assertGreaterEqual(audit["repeated_opening_count"], 1)
        messages = [message for row in audit["issues"] for message in row["issues"]]
        self.assertIn("Missing required term: barefoot", messages)
        self.assertIn("Contains avoided term: coat", messages)

    def test_audit_detects_multiline_input_before_normalization(self) -> None:
        audit = forge_module.audit_outfits(["silk dress\nwith pearl straps"])
        self.assertFalse(audit["ok"])
        self.assertIn("Entry is not single-line", audit["issues"][0]["issues"])

    def test_filename_normalization_does_not_duplicate_txt_suffix(self) -> None:
        result = forge_module.generate_outfits({"theme": "soft garden dresses", "filename": "garden.txt", "count": 3, "seed": 9})
        self.assertEqual(result["filename"], "garden.txt")

    def test_blueprint_grammar_agrees_with_plural_ingredients_and_repairs_articles(self) -> None:
        blueprint = next(row for row in forge_module.BLUEPRINTS if row["id"] == "collar-led")
        context = {
            "theme": "alien lingerie", "garment": "underbust corset", "material": "clear acrylic",
            "color": "opal", "construction": "open geometry", "motif": "crystal chains",
            "fastener": "oversized zippers", "accessory": "a collar", "effect": "hard flash reflections",
            "coverage": "high-exposure", "complexity": "layered", "realism": "fashion-plausible",
        }
        line = forge_module._format_blueprint(blueprint, context)
        self.assertIn("an underbust corset", line)
        self.assertIn("oversized zippers keep", line)

    def test_library_export_creates_hierarchy_and_deduplicates_canonical_outfits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_get_catalog = forge_module.get_catalog
            forge_module.get_catalog = lambda: catalog
            recipe_stub = types.ModuleType(f"{PACKAGE_NAME}.solo_recipe_catalog")
            recipe_stub._safe_sync_recipe_component_logs = lambda: None
            previous_recipe = sys.modules.get(f"{PACKAGE_NAME}.solo_recipe_catalog")
            sys.modules[f"{PACKAGE_NAME}.solo_recipe_catalog"] = recipe_stub
            try:
                first = forge_module.export_to_outfit_library(
                    ["pink satin dress", "silver chain body drape"],
                    category="Forge Tests",
                    subcategory="Crystal Night",
                )
                second = forge_module.export_to_outfit_library(
                    ["pink satin dress", "silver chain body drape"],
                    category="Forge Tests",
                    subcategory="Crystal Night",
                )
            finally:
                forge_module.get_catalog = original_get_catalog
                if previous_recipe is None:
                    sys.modules.pop(f"{PACKAGE_NAME}.solo_recipe_catalog", None)
                else:
                    sys.modules[f"{PACKAGE_NAME}.solo_recipe_catalog"] = previous_recipe

            collections = catalog.component_collections("outfit")
            components = catalog.recipe_components("outfit")

        parent = next(row for row in collections if row["name"] == "Forge Tests")
        child = next(row for row in collections if row["name"] == "Crystal Night")
        self.assertEqual(child["parent_id"], parent["collection_id"])
        self.assertEqual(len(components), 2)
        self.assertEqual(first["created"], 2)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["matched"], 2)

    def test_library_export_stays_successful_when_generated_log_sync_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            catalog = catalog_module.SoloCatalog(Path(directory) / "catalog.sqlite3")
            original_get_catalog = forge_module.get_catalog
            forge_module.get_catalog = lambda: catalog
            recipe_stub = types.ModuleType(f"{PACKAGE_NAME}.solo_recipe_catalog")
            recipe_stub._safe_sync_recipe_component_logs = lambda: {"ok": False, "error": "input directory temporarily unavailable"}
            previous_recipe = sys.modules.get(f"{PACKAGE_NAME}.solo_recipe_catalog")
            sys.modules[f"{PACKAGE_NAME}.solo_recipe_catalog"] = recipe_stub
            try:
                result = forge_module.export_to_outfit_library(
                    ["white denim overalls"],
                    category="Overalls",
                    subcategory="Denim",
                )
            finally:
                forge_module.get_catalog = original_get_catalog
                if previous_recipe is None:
                    sys.modules.pop(f"{PACKAGE_NAME}.solo_recipe_catalog", None)
                else:
                    sys.modules[f"{PACKAGE_NAME}.solo_recipe_catalog"] = previous_recipe

            self.assertTrue(result["ok"])
            self.assertFalse(result["log_sync"]["ok"])
            self.assertEqual(catalog.recipe_components("outfit")[0]["value"], "white denim overalls")

    def test_outfit_category_hierarchy_survives_portable_library_merge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = catalog_module.SoloCatalog(root / "source.sqlite3")
            target = catalog_module.SoloCatalog(root / "target.sqlite3")
            outfit = source.upsert_recipe_component("outfit", "iridescent moth-wing festival dress", manual=True)
            parent = source.create_component_collection("outfit", "Festival")
            child = source.create_component_collection("outfit", "Bioluminescent", parent["collection_id"])
            source.set_component_collections(outfit["component_id"], [child["collection_id"]])

            snapshot = source.creative_library_pack_snapshot("starter")
            target.merge_creative_library_pack_records(
                {"pack_id": "soslibrary:forge-test", "name": "Forge Test", "export_mode": "starter"},
                snapshot,
            )
            collections = target.component_collections("outfit")
            components = target.recipe_components("outfit")

        imported_parent = next(row for row in collections if row["name"] == "Festival")
        imported_child = next(row for row in collections if row["name"] == "Bioluminescent")
        self.assertEqual(imported_child["parent_id"], imported_parent["collection_id"])
        self.assertEqual(components[0]["collections"][0]["name"], "Bioluminescent")


if __name__ == "__main__":
    unittest.main()
