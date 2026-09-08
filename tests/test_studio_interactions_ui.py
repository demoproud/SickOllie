from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "js" / "studio_interactions.js"
CREATIVE_LIBRARY = ROOT / "js" / "solo_recipe_catalog.js"
OUTFIT_FORGE = ROOT / "js" / "solo_outfit_forge.js"


class StudioInteractionsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.creative_library = CREATIVE_LIBRARY.read_text(encoding="utf-8")
        cls.outfit_forge = OUTFIT_FORGE.read_text(encoding="utf-8")

    def test_shared_interaction_module_parses(self) -> None:
        result = subprocess.run(["node", "--check", str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_shared_feedback_covers_active_controls_but_skips_disabled_controls(self) -> None:
        self.assertIn("button,[role='button'],summary,a[href]", self.source)
        self.assertIn("input[type='checkbox']:not(:disabled),input[type='radio']:not(:disabled)", self.source)
        self.assertIn(":disabled,[aria-disabled='true']", self.source)
        self.assertIn("navigator.vibrate?.(pulse)", self.source)
        self.assertIn("target.animate?.([", self.source)

    def test_creative_library_and_outfit_forge_install_shared_feedback(self) -> None:
        for source in (self.creative_library, self.outfit_forge):
            self.assertIn('import { installStudioInteractions } from "./studio_interactions.js";', source)
            self.assertIn("installStudioInteractions(root);", source)


if __name__ == "__main__":
    unittest.main()
