from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "js" / "text_input_focus_guard.js"


class TextInputFocusGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_javascript_parses(self) -> None:
        result = subprocess.run(
            ["node", "--check", str(SCRIPT)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_guard_recovers_real_editable_controls_without_blocking_input(self) -> None:
        self.assertIn('const EDITABLE_SELECTOR = "input, textarea, select, [contenteditable]";', self.source)
        self.assertIn('window.addEventListener("pointerdown", onPointerDown, true);', self.source)
        self.assertIn('window.addEventListener("focusin", onFocusIn, true);', self.source)
        self.assertIn('window.addEventListener("focusout", onFocusOut, true);', self.source)
        self.assertIn('window.addEventListener("keydown", onKeyDown, true);', self.source)
        self.assertIn('window.addEventListener("beforeinput", onBeforeInput, true);', self.source)
        self.assertIn('window.addEventListener("focus", onWindowFocus);', self.source)
        self.assertIn('["node_capturing_input", "node_widget"]', self.source)
        self.assertIn('for (const type of ["keydown", "keyup", "keypress"]) editable.addEventListener(type, stopAtEditable);', self.source)
        self.assertIn("event.stopPropagation();", self.source)
        self.assertNotIn("preventDefault()", self.source)
        self.assertNotIn("stopImmediatePropagation()", self.source)

    def test_both_yearbook_systems_release_focus_capture(self) -> None:
        lora = (ROOT / "js" / "solo_library_review.js").read_text(encoding="utf-8")
        creative = (ROOT / "js" / "solo_recipe_catalog.js").read_text(encoding="utf-8")
        self.assertIn('import { recoverTextInputFocus } from "./text_input_focus_guard.js";', lora)
        self.assertIn('import { recoverTextInputFocus } from "./text_input_focus_guard.js";', creative)
        self.assertIn("recoverTextInputFocus();", lora)
        self.assertGreaterEqual(creative.count("recoverTextInputFocus();"), 2)

    def test_wardrobe_destructive_actions_use_library_owned_confirm(self) -> None:
        creative = (ROOT / "js" / "solo_recipe_catalog.js").read_text(encoding="utf-8")
        self.assertIn("async function comfyConfirm", creative)
        self.assertIn('collectionModal(title, "560px")', creative)
        self.assertIn('zIndex: "100052"', creative)
        self.assertIn('await comfyConfirm(`Delete the thumbnail for “${item.value}”?', creative)
        self.assertIn('await comfyConfirm(`Delete wardrobe item “${item.value}”?', creative)
        self.assertNotIn('if (!confirm(`Delete the thumbnail for “${item.value}”?', creative)
        self.assertNotIn('if (confirm(`Delete wardrobe item “${item.value}”?', creative)

    def test_wardrobe_bulk_and_prompt_source_recovery_are_wired(self) -> None:
        creative = (ROOT / "js" / "solo_recipe_catalog.js").read_text(encoding="utf-8")
        self.assertIn('wardrobeSelectionMode ? "DONE SELECTING" : "SELECT MULTIPLE"', creative)
        self.assertIn('request("/wardrobe-items/bulk"', creative)
        self.assertIn('operation: "delete"', creative)
        self.assertIn('operation: "delete_previews"', creative)
        self.assertIn('setStudioWidget(promptNode, sourceName, "log");', creative)
        self.assertIn('"COLLECTIONS"', creative)
        self.assertIn('"HOMES"', creative)


if __name__ == "__main__":
    unittest.main()
