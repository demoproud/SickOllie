from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = types.ModuleType("sickollie_recipe_log_test")
PACKAGE.__path__ = [str(ROOT)]
sys.modules.setdefault("sickollie_recipe_log_test", PACKAGE)
SPEC = importlib.util.spec_from_file_location("sickollie_recipe_log_test.solo_recipe_catalog", ROOT / "solo_recipe_catalog.py")
assert SPEC and SPEC.loader
recipe_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recipe_module
SPEC.loader.exec_module(recipe_module)


def prompt_payload(text: str) -> dict:
    return {
        "nodes": [
            {
                "type": recipe_module.STUDIO_PROMPT,
                "title": "Prompt used",
                "widgets": [
                    {"name": "prompt_source", "value": "manual"},
                    {"name": "manual_prompt", "value": text},
                ],
            }
        ]
    }


class RecipePromptLogTests(unittest.TestCase):
    def test_recipe_library_references_map_to_creative_library_homes(self) -> None:
        self.assertEqual(
            recipe_module.canonical_log_reference(
                "prompts/Recipe Library/MASTER - All Recipe Prompts.txt", "prompt",
            ),
            "prompts/Creative Library/MASTER - Saved Recipe Prompts.txt",
        )
        self.assertEqual(
            recipe_module.canonical_log_reference(
                "prompts/Recipe Library/Collections/Faceouts.txt", "prompt",
            ),
            "prompts/Creative Library/Saved Recipe Collections/Faceouts.txt",
        )
        self.assertEqual(
            recipe_module.canonical_log_reference(
                "outfits/Recipe Library/MASTER - Resolved Recipe Outfits.txt", "outfit",
            ),
            "outfits/Creative Library/MASTER - Outfit Looks.txt",
        )
        self.assertEqual(
            recipe_module.canonical_log_reference(
                "scenes/Recipe Library/MASTER - Resolved Recipe Scenes.txt", "scene",
            ),
            "scenes/Creative Library/MASTER - Scenes.txt",
        )

    def test_known_generated_recipe_library_tree_is_retired_without_touching_unknown_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            category_root = Path(directory) / "prompts"
            legacy = category_root / "Recipe Library"
            collections = legacy / "Collections"; collections.mkdir(parents=True)
            (legacy / "MASTER - All Recipe Prompts.txt").write_text("generated\n", encoding="utf-8")
            (collections / "Client Set.txt").write_text("generated\n", encoding="utf-8")
            result = recipe_module.retire_legacy_generated_logs(category_root, "prompt")
            self.assertFalse(legacy.exists())
            self.assertEqual(result["removed_files"], 2)
            self.assertTrue(result["retired"])

            legacy.mkdir()
            unknown = legacy / "My Manual Notes.txt"
            unknown.write_text("keep me\n", encoding="utf-8")
            protected = recipe_module.retire_legacy_generated_logs(category_root, "prompt")
            self.assertTrue(unknown.is_file())
            self.assertFalse(protected["retired"])

    def test_master_and_collection_logs_mirror_recipe_prompts(self) -> None:
        collection = {
            "collection_id": "recipe-collection:abc123",
            "name": "Faceout Posters",
            "color": "#ff4ab8",
        }
        recipes = [
            {
                "recipe_id": "recipe:one",
                "name": "One",
                "created_at": "2026-08-19T01:00:00Z",
                "payload": prompt_payload("First prompt\nwith a wrapped line"),
                "collections": [collection],
            },
            {
                "recipe_id": "recipe:two",
                "name": "Two",
                "created_at": "2026-08-19T02:00:00Z",
                "payload": prompt_payload("Second prompt"),
                "collections": [],
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Creative Library"
            result = recipe_module._sync_recipe_prompt_logs(root, recipes, [collection])
            master = (root / recipe_module.RECIPE_PROMPT_MASTER_FILE).read_text(encoding="utf-8")
            collection_text = (
                root / recipe_module.SAVED_RECIPE_COLLECTION_FOLDER / "Faceout Posters.txt"
            ).read_text(encoding="utf-8")

        self.assertTrue(result["ok"])
        self.assertEqual(master, "First prompt with a wrapped line\nSecond prompt\n")
        self.assertEqual(collection_text, "First prompt with a wrapped line\n")

    def test_collection_logs_remove_stale_files_when_membership_or_collection_disappears(self) -> None:
        collection = {"collection_id": "recipe-collection:abc123", "name": "Client Set", "color": "#35d7ff"}
        recipe = {
            "recipe_id": "recipe:one",
            "name": "One",
            "created_at": "2026-08-19T01:00:00Z",
            "payload": prompt_payload("A prompt"),
            "collections": [collection],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Creative Library"
            recipe_module._sync_recipe_prompt_logs(root, [recipe], [collection])
            old_file = root / recipe_module.SAVED_RECIPE_COLLECTION_FOLDER / "Client Set.txt"
            self.assertTrue(old_file.exists())
            recipe["collections"] = []
            result = recipe_module._sync_recipe_prompt_logs(root, [recipe], [])
            master = (root / recipe_module.RECIPE_PROMPT_MASTER_FILE).read_text(encoding="utf-8")
            self.assertFalse(old_file.exists())

        self.assertEqual(result["removed_files"], 1)
        self.assertEqual(master, "A prompt\n")

    def test_source_template_is_preferred_over_resolved_prompt(self) -> None:
        recipe = {
            "payload": {
                "nodes": [],
                "summary": {
                    "prompt_template": "Portrait of NAME wearing OUTFIT",
                    "resolved_prompt": "Portrait of Jester wearing a blue dress",
                },
            }
        }
        self.assertEqual(
            recipe_module._recipe_prompt_text(recipe),
            "Portrait of NAME wearing OUTFIT",
        )


if __name__ == "__main__":
    unittest.main()
