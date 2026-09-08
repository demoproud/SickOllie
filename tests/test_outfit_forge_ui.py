from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "js" / "solo_outfit_forge.js"
STYLE = ROOT / "js" / "solo_outfit_forge.css"
HUB = ROOT / "js" / "solo_hub.js"


class OutfitForgeUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.style = STYLE.read_text(encoding="utf-8")
        cls.hub = HUB.read_text(encoding="utf-8")

    def test_javascript_parses(self) -> None:
        result = subprocess.run(["node", "--check", str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_forge_is_a_first_class_hub_tool(self) -> None:
        self.assertIn('id: "outfit-forge"', self.source)
        self.assertIn('label: "Outfit Forge"', self.source)
        self.assertIn('window.__soOpenOutfitForge', self.source)
        self.assertIn('"outfit-forge": {', self.hub)
        self.assertIn('DESIGN + GENERATE', self.hub)

    def test_forge_has_generation_edit_audit_and_download_workflows(self) -> None:
        self.assertIn('request("/generate"', self.source)
        self.assertIn('request("/audit"', self.source)
        self.assertIn('regenerateLine(index', self.source)
        self.assertIn('DOWNLOAD .TXT', self.source)
        self.assertIn('new Blob([`${draft.lines.join("\\n")}', self.source)
        self.assertIn('localStorage.setItem(DRAFT_KEY', self.source)
        self.assertIn('Advanced controls', self.source)
        self.assertIn('beta interpreter cannot represent yet', self.source)
        self.assertNotIn('Structure packs', self.source)
        self.assertNotIn('Optional editable seed preset', self.source)
        self.assertIn('constraint fidelity', self.source)
        self.assertIn('brief coverage', self.source)
        self.assertIn('Not represented', self.source)
        self.assertIn('OFFLINE OUTFIT SYSTEM · BETA', self.source)
        self.assertIn('clear + plausible', self.source)
        self.assertIn('Wearability 1–2 permits experimental construction', self.source)

    def test_forge_exports_directly_to_canonical_outfit_library(self) -> None:
        self.assertIn('EXPORT TO OUTFIT LOOKS', self.source)
        self.assertIn('request("/export-library"', self.source)
        self.assertIn('New or existing category', self.source)
        self.assertIn('Optional new or existing subcategory', self.source)

    def test_theme_linked_filename_stays_automatic_until_manually_edited(self) -> None:
        self.assertIn('filenameAuto: true', self.source)
        self.assertIn('field === "theme" && draft.filenameAuto !== false', self.source)
        self.assertIn('field === "filename"', self.source)
        self.assertIn('draft.filename = normalizeFilename(draft.theme)', self.source)

    def test_export_refresh_cannot_report_a_false_failure_after_commit(self) -> None:
        self.assertIn('The catalog mutation is the export.', self.source)
        self.assertIn('result.log_sync?.ok === false', self.source)
        self.assertIn('The Looks are saved; generated Prompt Core logs will refresh', self.source)

    def test_first_release_has_no_lm_studio_dependency(self) -> None:
        combined = self.source + self.style
        self.assertNotIn("LM Studio", combined)
        self.assertNotIn("localhost:1234", combined)

    def test_responsive_standalone_window_styles_are_present(self) -> None:
        self.assertIn('.so-forge-overlay', self.style)
        self.assertIn('.so-forge__body', self.style)
        self.assertIn('@media (max-width: 760px)', self.style)
        self.assertIn('.so-forge__entry[data-issue="1"]', self.style)


if __name__ == "__main__":
    unittest.main()
