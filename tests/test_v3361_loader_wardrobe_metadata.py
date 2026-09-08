from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V3361LoaderWardrobeMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.loader_py = (ROOT / "studio_loader_core.py").read_text(encoding="utf-8")
        cls.loader_js = (ROOT / "js" / "studio_loader_core.js").read_text(encoding="utf-8")
        cls.library_py = (ROOT / "solo_library_review.py").read_text(encoding="utf-8")
        cls.library_js = (ROOT / "js" / "solo_library_review.js").read_text(encoding="utf-8")
        cls.catalog_py = (ROOT / "solo_catalog.py").read_text(encoding="utf-8")
        cls.recipe_py = (ROOT / "solo_recipe_catalog.py").read_text(encoding="utf-8")
        cls.recipe_js = (ROOT / "js" / "solo_recipe_catalog.js").read_text(encoding="utf-8")
        cls.metadata_py = (ROOT / "metadata_core.py").read_text(encoding="utf-8")
        cls.metadata_js = (ROOT / "js" / "studio_metadata_core.js").read_text(encoding="utf-8")

    def test_diffusion_model_has_independent_after_generate_control(self) -> None:
        self.assertIn('"diffusion_control_after_generate": (', self.loader_py)
        self.assertIn('"diffusion_control_after_generate",\n];', self.loader_js)
        self.assertIn('function advanceDiffusionAfterQueued(node)', self.loader_js)
        self.assertIn('"Model after generate", "diffusion_control_after_generate", CONTROL_MODES', self.loader_js)
        self.assertIn('...modelControlValues.slice(0, 16),', self.loader_js)
        self.assertIn('"fixed",\n                ...modelControlValues.slice(16)', self.loader_js)

    def test_wardrobe_can_clear_regenerate_and_manual_load(self) -> None:
        self.assertIn('def clear_wardrobe_preview(self, wardrobe_id: str)', self.catalog_py)
        self.assertIn('/wardrobe-items/{wardrobe_id}/preview', self.recipe_py)
        self.assertIn('function openCatalogRunDialogForItem(singleItem = null, explicitItems = null)', self.recipe_js)
        self.assertIn('REGENERATE THUMBNAIL', self.recipe_js)
        self.assertIn('DELETE THUMBNAIL', self.recipe_js)
        self.assertIn('async function loadWardrobeValue(item, destination = "A")', self.recipe_js)
        self.assertIn('`outfit_source_${slot}`', self.recipe_js)
        self.assertIn('`outfit_manual_${slot}`', self.recipe_js)
        self.assertIn('const loadButton = action("LOAD"', self.recipe_js)

    def test_loader_folder_scope_supports_lora_library_collections(self) -> None:
        self.assertIn('COLLECTION_SCOPE_PREFIX = "[LoRA Collection:"', self.loader_py)
        self.assertIn("def _collection_loras(folder_name: str)", self.loader_py)
        self.assertIn("if _collection_scope_id(folder_name):", self.loader_py)
        self.assertIn('fetch(`${REVIEW_API}/loader-collections`)', self.loader_js)
        self.assertIn('"Folder / Collection Scope"', self.loader_js)
        self.assertIn("const collectionMembers = collection", self.loader_js)
        self.assertIn('/sickollie/library-review/loader-collections', self.library_py)
        self.assertIn('"lora_names": names', self.library_py)
        self.assertIn('String(options.collection || options.collection_id || "").trim()', self.library_js)

    def test_metadata_exposes_component_quick_copy_values(self) -> None:
        self.assertIn('"copy_values": copy_values', self.metadata_py)
        self.assertIn('function metadataQuickCopyEntries(payload = {})', self.metadata_js)
        self.assertIn('layout.buttons[`copy_${entry.key}`] = rect', self.metadata_js)
        self.assertIn('metadataCopy(this, key, entry.value)', self.metadata_js)

    def test_release_version_is_current(self) -> None:
        self.assertIn('version = "4.0.0"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
