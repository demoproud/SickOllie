from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V333PromptMetadataUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prompt_js = (ROOT / "js" / "studio_prompt_core.js").read_text(encoding="utf-8")
        cls.metadata_js = (ROOT / "js" / "studio_metadata_core.js").read_text(encoding="utf-8")
        cls.library_js = (ROOT / "js" / "solo_recipe_catalog.js").read_text(encoding="utf-8")
        cls.prompt_py = (ROOT / "studio_prompt_core.py").read_text(encoding="utf-8")

    def test_prompt_core_exposes_dedicated_external_prompt_source(self) -> None:
        self.assertIn('"manual_prompt_input": ("STRING", {"forceInput": True})', self.prompt_py)
        self.assertIn('MAIN_PROMPT_SOURCES = ["manual", "input", "log"]', self.prompt_py)
        self.assertIn('manual_prompt_input: "Prompt input · final/source"', self.prompt_js)
        self.assertIn('const MAIN_PROMPT_SOURCES = ["manual", "input", "log"]', self.prompt_js)
        self.assertIn('function syncExternalManualPrompt(node)', self.prompt_js)
        self.assertIn('PROMPT INPUT', self.prompt_js)
        self.assertIn('Connect the Prompt input above', self.prompt_js)

    def test_library_queue_restores_background_draft_but_runtime_snapshot_is_truthful(self) -> None:
        self.assertIn('const backgroundDraft = {', self.library_js)
        self.assertIn('QUEUE is intentionally non-destructive to the user\'s working draft.', self.library_js)
        self.assertIn('setStudioWidget(promptNode, "manual_prompt", backgroundDraft.manual_prompt)', self.library_js)
        self.assertIn('widgets_values[1] = runtime_manual_prompt', self.prompt_py)
        self.assertIn('so_runtime_manual_prompt', self.prompt_py)

    def test_metadata_controls_are_integrated_and_haptic(self) -> None:
        self.assertIn('ctx.fillText("IMAGE CONTROLS"', self.metadata_js)
        self.assertIn('layout.buttons.upload', self.metadata_js)
        self.assertIn('layout.buttons.clear', self.metadata_js)
        self.assertIn('layout.buttons.seed', self.metadata_js)
        self.assertIn('navigator.vibrate?.(16)', self.metadata_js)
        self.assertIn('metadataCopy(this, "final"', self.metadata_js)
        self.assertIn('metadataCopy(this, "source"', self.metadata_js)
        self.assertIn('metadataCopy(this, "report"', self.metadata_js)
        self.assertIn('hideActionWidget(upload)', self.metadata_js)
        self.assertIn('syncConnectedPromptInputs(node)', self.metadata_js)


if __name__ == "__main__":
    unittest.main()
