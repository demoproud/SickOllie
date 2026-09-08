from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def _load_module(filename: str, name: str):
    folder_paths = types.ModuleType("folder_paths")
    folder_paths.get_input_directory = lambda: tempfile.gettempdir()
    sys.modules["folder_paths"] = folder_paths
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


classic = _load_module("prompt_core.py", "sickollie_v337_classic")
studio = _load_module("studio_prompt_core.py", "sickollie_v337_studio")


class PrefixSuffixTokenTests(unittest.TestCase):
    def test_classic_suffix_scene_token_is_resolved(self) -> None:
        def load_line(path, category, index):
            if category == "prompt":
                return "portrait from a read-only log", 0, 1
            if category == "scene":
                return "inside a neon workshop", 0, 1
            return "", 0, 0

        values = dict(
            prompt_source="log", manual_prompt="", prompt_log_file="prompts/a.txt", prompt_mode="fixed", prompt_index=0,
            outfit_token_A="OUTFIT_A", outfit_log_file_A=classic.NO_FILE, outfit_mode_A="fixed", outfit_index_A=0,
            outfit_token_B="OUTFIT_B", outfit_log_file_B=classic.NO_FILE, outfit_mode_B="fixed", outfit_index_B=0,
            outfit_token_C="OUTFIT_C", outfit_log_file_C=classic.NO_FILE, outfit_mode_C="fixed", outfit_index_C=0,
            scene_token="SCENE", scene_log_file="scenes/a.txt", scene_mode="fixed", scene_index=0,
            name_token="NAME", name_value="", item_token="ITEM", item_value="",
            prefix_enabled=False, prefix_text="", suffix_enabled=True, suffix_text="SCENE",
            prefix_suffix_separator=", ", cleanup_enabled=False, cleanup_rules="", saved_prompt="",
            extra_pnginfo={}, unique_id="1",
        )
        with mock.patch.object(classic, "_load_line", side_effect=load_line):
            result = classic.SOPromptLogEngine().build_prompt(**values)
        self.assertEqual(result["result"][0], "portrait from a read-only log, inside a neon workshop")
        self.assertNotIn("SCENE", result["result"][0])

    def test_studio_suffix_scene_token_is_resolved(self) -> None:
        def load_line(path, category, index):
            if category == "prompt":
                return "portrait from a read-only log", 0, 1
            if category == "scene":
                return "inside a neon workshop", 0, 1
            return "", 0, 0

        values = dict(
            prompt_source="log", manual_prompt="", prompt_log_file="prompts/a.txt", prompt_mode="fixed", prompt_index=0,
            outfit_token_A="OUTFIT_A", outfit_placement_A="off", outfit_log_file_A=studio.NO_FILE, outfit_mode_A="fixed", outfit_index_A=0,
            outfit_token_B="OUTFIT_B", outfit_placement_B="off", outfit_log_file_B=studio.NO_FILE, outfit_mode_B="fixed", outfit_index_B=0,
            outfit_token_C="OUTFIT_C", outfit_placement_C="off", outfit_log_file_C=studio.NO_FILE, outfit_mode_C="fixed", outfit_index_C=0,
            scene_token="SCENE", scene_placement="token", scene_log_file="scenes/a.txt", scene_mode="fixed", scene_index=0,
            trigger_token="TRIGGER", trigger_placement="off", trigger_override="", main_trigger="",
            name_token="NAME", name_value="", item_token="ITEM", item_value="",
            prefix_enabled=False, prefix_text="", suffix_enabled=True, suffix_text="SCENE",
            prefix_suffix_separator=", ", cleanup_enabled=False, cleanup_rules="", saved_prompt="",
            extra_pnginfo={}, unique_id="1",
        )
        with mock.patch.object(studio, "_load_line", side_effect=load_line):
            result = studio.SOPromptLogEngine().build_prompt(**values)
        self.assertEqual(result["result"][0], "portrait from a read-only log, inside a neon workshop")
        self.assertNotIn("SCENE", result["result"][0])


if __name__ == "__main__":
    unittest.main()
