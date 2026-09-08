from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_NAME = "sickollie_studio_prompt_assembly_test"


def _load_module():
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_input_directory = lambda: tempfile.gettempdir()
    sys.modules["folder_paths"] = folder_paths

    spec = importlib.util.spec_from_file_location(MODULE_NAME, ROOT / "studio_prompt_core.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


prompt_core = _load_module()


def _build(**overrides):
    values = {
        "prompt_source": "manual",
        "manual_prompt": "NAME wears OUTFIT. SCENE",
        "prompt_log_file": prompt_core.NO_FILE,
        "prompt_mode": "fixed",
        "prompt_index": 0,
        "outfit_token_A": "OUTFIT_A",
        "outfit_placement_A": "smart",
        "outfit_log_file_A": "outfits/a.txt",
        "outfit_mode_A": "fixed",
        "outfit_index_A": 0,
        "outfit_token_B": "OUTFIT_B",
        "outfit_placement_B": "off",
        "outfit_log_file_B": prompt_core.NO_FILE,
        "outfit_mode_B": "fixed",
        "outfit_index_B": 0,
        "outfit_token_C": "OUTFIT_C",
        "outfit_placement_C": "off",
        "outfit_log_file_C": prompt_core.NO_FILE,
        "outfit_mode_C": "fixed",
        "outfit_index_C": 0,
        "scene_token": "SCENE",
        "scene_placement": "smart",
        "scene_log_file": "scenes/a.txt",
        "scene_mode": "fixed",
        "scene_index": 0,
        "name_token": "NAME",
        "name_value": "Star",
        "item_token": "ITEM",
        "item_value": "",
        "prefix_enabled": False,
        "prefix_text": "",
        "suffix_enabled": False,
        "suffix_text": "",
        "prefix_suffix_separator": ", ",
        "cleanup_enabled": False,
        "cleanup_rules": "",
        "saved_prompt": "",
        "extra_pnginfo": {},
        "unique_id": "1",
    }
    values.update(overrides)

    def load_line(path, category, index):
        data = {
            ("outfits/a.txt", "outfit"): ("a glossy yellow jacket", 0, 1),
            ("scenes/a.txt", "scene"): ("inside a neon workshop", 0, 1),
        }
        return data.get((path, category), ("", 0, 0))

    with mock.patch.object(prompt_core, "_load_line", side_effect=load_line):
        return prompt_core.SOPromptLogEngine().build_prompt(**values), values["extra_pnginfo"]


class StudioPromptAssemblyTests(unittest.TestCase):
    def test_outfit_alias_and_braced_name_are_resolved(self) -> None:
        result, metadata = _build(manual_prompt="{NAME} wears OUTFIT. {SCENE}")
        self.assertEqual(
            result["result"][0],
            "Star wears a glossy yellow jacket. inside a neon workshop",
        )
        assembly = metadata["so_prompt_core_resolved"]
        self.assertEqual(assembly["outfit_a"]["action"], "replace")
        self.assertEqual(assembly["outfit_a"]["matched_tokens"], ["OUTFIT"])
        self.assertEqual(assembly["name"]["matched_tokens"], ["{NAME}"])

    def test_smart_mode_appends_when_no_placeholder_exists(self) -> None:
        result, metadata = _build(
            manual_prompt="A portrait of NAME.",
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "A portrait of Star. a glossy yellow jacket")
        self.assertEqual(metadata["so_prompt_core_resolved"]["outfit_a"]["action"], "append")

    def test_legacy_token_mode_waits_instead_of_appending(self) -> None:
        result, metadata = _build(
            manual_prompt="A portrait of NAME.",
            outfit_placement_A="token",
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "A portrait of Star.")
        outfit = metadata["so_prompt_core_resolved"]["outfit_a"]
        self.assertFalse(outfit["used"])
        self.assertEqual(outfit["action"], "missing_placeholder")

    def test_append_mode_removes_placeholder_before_appending(self) -> None:
        result, metadata = _build(
            manual_prompt="NAME in OUTFIT.",
            outfit_placement_A="append",
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "Star in. a glossy yellow jacket")
        self.assertEqual(metadata["so_prompt_core_resolved"]["outfit_a"]["action"], "append")

    def test_off_mode_removes_known_placeholder(self) -> None:
        result, metadata = _build(
            manual_prompt="NAME wears OUTFIT_B.",
            outfit_placement_A="off",
            outfit_log_file_A=prompt_core.NO_FILE,
            outfit_placement_B="off",
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "Star wears.")
        self.assertEqual(metadata["so_prompt_core_resolved"]["outfit_b"]["action"], "remove")

    def test_plain_alias_does_not_match_a_longer_placeholder_prefix(self) -> None:
        replaced, matches, count = prompt_core._replace_aliases(
            "OUTFIT_A then OUTFIT",
            prompt_core._token_candidates("OUTFIT"),
            "dress",
        )
        self.assertEqual(replaced, "OUTFIT_A then dress")
        self.assertEqual(matches, ["OUTFIT"])
        self.assertEqual(count, 1)


    def test_connected_prompt_input_does_not_override_manual_source(self) -> None:
        result, metadata = _build(
            prompt_source="manual",
            manual_prompt="butts",
            manual_prompt_input="apples",
            outfit_placement_A="off",
            outfit_log_file_A=prompt_core.NO_FILE,
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "butts")
        resolved = metadata["so_prompt_core_resolved"]
        self.assertEqual(resolved["source_prompt"], "butts")
        self.assertEqual(resolved["prompt"]["source"], "manual")
        self.assertEqual(resolved["prompt"]["manual_prompt"], "butts")
        self.assertFalse(resolved["prompt"]["external_input"])

    def test_prompt_input_is_used_only_when_dedicated_source_is_selected(self) -> None:
        result, metadata = _build(
            prompt_source="input",
            manual_prompt="butts",
            manual_prompt_input="apples",
            outfit_placement_A="off",
            outfit_log_file_A=prompt_core.NO_FILE,
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "apples")
        resolved = metadata["so_prompt_core_resolved"]
        self.assertEqual(resolved["source_prompt"], "apples")
        self.assertEqual(resolved["prompt"]["source"], "input")
        self.assertEqual(resolved["prompt"]["input_prompt"], "apples")
        self.assertTrue(resolved["prompt"]["external_input"])

    def test_runtime_prompt_rewrites_embedded_workflow_snapshot(self) -> None:
        workflow = {
            "nodes": [{
                "id": "1",
                "type": "SOPromptLogEngineStudio",
                "widgets_values": ["manual", "butts", "[None]"],
                "properties": {},
            }]
        }
        extra = {"workflow": workflow}
        result, metadata = _build(
            manual_prompt="apples",
            outfit_placement_A="off",
            outfit_log_file_A=prompt_core.NO_FILE,
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
            extra_pnginfo=extra,
        )
        self.assertEqual(result["result"][0], "apples")
        node = workflow["nodes"][0]
        self.assertEqual(node["widgets_values"][0], "manual")
        self.assertEqual(node["widgets_values"][1], "apples")
        self.assertEqual(node["properties"]["so_runtime_prompt_source"], "manual")
        self.assertEqual(node["properties"]["so_runtime_manual_prompt"], "apples")

    def test_input_runtime_snapshot_preserves_manual_draft(self) -> None:
        workflow = {
            "nodes": [{
                "id": "1",
                "type": "SOPromptLogEngineStudio",
                "widgets_values": ["input", "manual draft", "[None]"],
                "properties": {},
            }]
        }
        extra = {"workflow": workflow}
        result, _ = _build(
            prompt_source="input",
            manual_prompt="manual draft",
            manual_prompt_input="metadata prompt",
            outfit_placement_A="off",
            outfit_log_file_A=prompt_core.NO_FILE,
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
            extra_pnginfo=extra,
        )
        self.assertEqual(result["result"][0], "metadata prompt")
        node = workflow["nodes"][0]
        self.assertEqual(node["widgets_values"][0], "input")
        self.assertEqual(node["widgets_values"][1], "manual draft")
        self.assertEqual(node["properties"]["so_runtime_prompt_source"], "input")
        self.assertEqual(node["properties"]["so_runtime_manual_prompt"], "manual draft")
        self.assertEqual(node["properties"]["so_external_manual_prompt_value"], "metadata prompt")

    def test_trigger_smart_mode_prepends_loader_value(self) -> None:
        result, metadata = _build(
            manual_prompt="A portrait of NAME.",
            outfit_placement_A="off", scene_placement="off", scene_log_file=prompt_core.NO_FILE,
            trigger_placement="smart", main_trigger="Gadget & the Gadgetinis",
        )
        self.assertEqual(result["result"][0], "Gadget & the Gadgetinis, A portrait of Star.")
        self.assertEqual(metadata["so_prompt_core_resolved"]["trigger"]["action"], "prepend")

    def test_trigger_placeholder_only_does_not_append(self) -> None:
        result, metadata = _build(
            manual_prompt="A portrait of NAME.", outfit_placement_A="off", scene_placement="off",
            scene_log_file=prompt_core.NO_FILE, trigger_placement="token", main_trigger="shyla",
        )
        self.assertEqual(result["result"][0], "A portrait of Star.")
        self.assertEqual(metadata["so_prompt_core_resolved"]["trigger"]["action"], "missing_placeholder")

    def test_trigger_override_beats_loader_value(self) -> None:
        result, metadata = _build(
            manual_prompt="TRIGGER, NAME", outfit_placement_A="off", scene_placement="off",
            scene_log_file=prompt_core.NO_FILE, trigger_placement="token", main_trigger="wrong", trigger_override="chosen",
        )
        self.assertEqual(result["result"][0], "chosen, Star")
        self.assertEqual(metadata["so_prompt_core_resolved"]["trigger"]["source"], "override")

    def test_suffix_placeholders_resolve_after_log_source_is_assembled(self) -> None:
        result, metadata = _build(
            prompt_source="log",
            suffix_enabled=True,
            suffix_text="SCENE",
            outfit_placement_A="off",
            outfit_log_file_A=prompt_core.NO_FILE,
            scene_placement="token",
        )
        self.assertEqual(result["result"][0], "inside a neon workshop")
        scene = metadata["so_prompt_core_resolved"]["scene"]
        self.assertTrue(scene["used"])
        self.assertEqual(scene["action"], "replace")
        self.assertEqual(scene["matched_tokens"], ["SCENE"])

    def test_prefix_name_placeholder_resolves_with_manual_source(self) -> None:
        result, _ = _build(
            manual_prompt="portrait",
            prefix_enabled=True,
            prefix_text="NAME",
            outfit_placement_A="off", outfit_log_file_A=prompt_core.NO_FILE,
            scene_placement="off", scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "Star, portrait")

    def test_manual_outfit_value_stays_independent_of_outfit_log(self) -> None:
        result, metadata = _build(
            manual_prompt="NAME wears OUTFIT.",
            outfit_source_A="manual",
            outfit_manual_A="a simple silver sundress",
            outfit_index_A=987,
            scene_placement="off",
            scene_log_file=prompt_core.NO_FILE,
        )
        self.assertEqual(result["result"][0], "Star wears a simple silver sundress.")
        outfit = metadata["so_prompt_core_resolved"]["outfit_a"]
        self.assertEqual(outfit["source"], "manual")
        self.assertEqual(outfit["manual_value"], "a simple silver sundress")
        self.assertNotIn("file", outfit)
        self.assertNotIn("index", outfit)

    def test_manual_scene_value_replaces_scene_placeholder(self) -> None:
        result, metadata = _build(
            manual_prompt="NAME in SCENE",
            outfit_placement_A="off",
            outfit_log_file_A=prompt_core.NO_FILE,
            scene_source="manual",
            scene_manual="a quiet lakeside cabin",
        )
        self.assertEqual(result["result"][0], "Star in a quiet lakeside cabin")
        scene = metadata["so_prompt_core_resolved"]["scene"]
        self.assertEqual(scene["source"], "manual")
        self.assertEqual(scene["action"], "replace")

    def test_outfit_log_collections_include_looks_and_wardrobe(self) -> None:
        class FakeCatalog:
            def library_collections(self, kind):
                return {
                    "outfit": [{"collection_id": "looks:nice", "name": "Nice Looks", "asset_count": 2, "asset_ids": ["look:2", "look:1"]}],
                    "wardrobe": [{"collection_id": "wardrobe:dresses", "name": "Dresses", "asset_count": 2, "asset_ids": ["wardrobe:2", "wardrobe:1"]}],
                    "scene": [{"collection_id": "scene:night", "name": "Night", "asset_count": 1, "asset_ids": ["scene:1"]}],
                }[kind]

            def recipe_components(self, kind):
                return {
                    "outfit": [
                        {"component_id": "look:1", "value": "black slip dress"},
                        {"component_id": "look:2", "value": "white sundress"},
                    ],
                    "scene": [{"component_id": "scene:1", "value": "neon rooftop at night"}],
                }[kind]

            def wardrobe_items(self):
                return [
                    {"wardrobe_id": "wardrobe:1", "value": "mary janes"},
                    {"wardrobe_id": "wardrobe:2", "value": "ribbed mini dress"},
                ]

        fake = FakeCatalog()
        with mock.patch.object(prompt_core, "_collection_catalog", return_value=fake):
            records = prompt_core._collection_scope_records("outfit")
            self.assertEqual([row["source"] for row in records], ["outfit", "wardrobe"])
            look_ref = records[0]["reference"]
            wardrobe_ref = records[1]["reference"]
            self.assertEqual(
                prompt_core._usable_log_lines(look_ref, "outfit"),
                ["white sundress", "black slip dress"],
            )
            self.assertEqual(
                prompt_core._usable_log_lines(wardrobe_ref, "outfit"),
                ["ribbed mini dress", "mary janes"],
            )

    def test_scene_collection_is_a_virtual_scene_log(self) -> None:
        class FakeCatalog:
            def library_collections(self, kind):
                if kind == "scene":
                    return [{"collection_id": "scene:night", "name": "Night", "asset_count": 2, "asset_ids": ["scene:2", "scene:1"]}]
                return []

            def recipe_components(self, kind):
                self_kind = kind
                assert self_kind == "scene"
                return [
                    {"component_id": "scene:1", "value": "quiet motel room"},
                    {"component_id": "scene:2", "value": "city rooftop after rain"},
                ]

        with mock.patch.object(prompt_core, "_collection_catalog", return_value=FakeCatalog()):
            records = prompt_core._collection_scope_records("scene")
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["source"], "scene")
            self.assertEqual(
                prompt_core._usable_log_lines(records[0]["reference"], "scene"),
                ["city rooftop after rain", "quiet motel room"],
            )
            self.assertEqual(prompt_core._usable_log_lines(records[0]["reference"], "outfit"), [])


if __name__ == "__main__":
    unittest.main()
