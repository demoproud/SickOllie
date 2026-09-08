from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V335MetadataRecipeLiveLoraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata_js = (ROOT / "js" / "studio_metadata_core.js").read_text(encoding="utf-8")
        cls.generation_js = (ROOT / "js" / "studio_generation_core.js").read_text(encoding="utf-8")
        cls.loader_py = (ROOT / "studio_loader_core.py").read_text(encoding="utf-8")
        cls.recipe_py = (ROOT / "solo_recipe_catalog.py").read_text(encoding="utf-8")

    def test_metadata_core_has_studio_theme_and_save_recipe_action(self) -> None:
        self.assertIn("applyStudioNodeColors", self.metadata_js)
        self.assertIn('drawStudioSectionFrame', self.metadata_js)
        self.assertIn('"Save Recipe"', self.metadata_js)
        self.assertIn('saveLoadedMetadataRecipe', self.metadata_js)
        self.assertIn('/sickollie/creative-library/import-metadata', self.metadata_js)
        self.assertIn('buttons.recipe', self.metadata_js)
        self.assertIn('TOOL_BUTTON_H * 3', self.metadata_js)

    def test_metadata_recipe_route_uses_image_metadata_and_thumbnail(self) -> None:
        self.assertIn('@_creative_library_route("post", "/import-metadata")', self.recipe_py)
        self.assertIn('_structured_metadata_overlay(recipe, structured)', self.recipe_py)
        self.assertIn('recipe["_sickollie_seed_source"] = "imported-image"', self.recipe_py)
        self.assertIn('_save_preview(image.copy(), uuid.uuid4().hex)', self.recipe_py)

    def test_loader_publishes_runtime_loras_before_sampling(self) -> None:
        self.assertIn('PromptServer.instance.send_sync("sickollie_active_loras", live_payload)', self.loader_py)
        self.assertIn('"role": "main"', self.loader_py)
        self.assertIn('"role": "secondary"', self.loader_py)

    def test_generation_core_renders_live_lora_feed(self) -> None:
        self.assertIn('api.addEventListener("sickollie_active_loras", receiveGenerationLiveState)', self.generation_js)
        self.assertIn('LORAS CURRENTLY IN USE', self.generation_js)
        self.assertIn('drawLiveLoraShelf(this, ctx)', self.generation_js)
        self.assertIn('LIVE ·', self.generation_js)
        self.assertIn('generationDirectLoaderId', self.generation_js)

    def test_metadata_and_generation_core_backend_fixes_exist(self) -> None:
        metadata_py = (ROOT / "metadata_core.py").read_text(encoding="utf-8")
        generation_py = (ROOT / "studio_generation_core.py").read_text(encoding="utf-8")
        self.assertIn('def _input_is_linked(prompt: Any, unique_id: Any, input_name: str) -> bool:', metadata_py)
        self.assertIn('has_wired_image = _input_is_linked(prompt, unique_id, "images")', metadata_py)
        self.assertIn('placeholder 64x64 tensor', metadata_py)
        self.assertIn('"seed_input": (', generation_py)
        self.assertIn('"forceInput": True', generation_py)
        self.assertIn('seed_source = seed_input if seed_input is not None else seed_value', generation_py)
        self.assertIn('def _cleanup_stale_temp_files(max_age_seconds: int = TEMP_FILE_MAX_AGE_SECONDS) -> int:', metadata_py)
        self.assertNotIn('_delete_temp_token(previous_token)', metadata_py)
        self.assertIn('Queued workflows may still reference earlier tokens', metadata_py)
        self.assertIn('\"seed_input\",', self.generation_js)
        self.assertIn('version = "4.0.0"', (ROOT / 'pyproject.toml').read_text(encoding='utf-8'))


if __name__ == "__main__":
    unittest.main()
