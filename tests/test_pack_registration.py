from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackRegistrationTests(unittest.TestCase):
    def test_requested_node_families_and_organizers_are_registered(self) -> None:
        source = (ROOT / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("CLASSIC_PREVIEW_CLASSES", source)
        self.assertNotIn("CLASSIC_METADATA_CLASSES", source)
        self.assertNotIn("STUDIO_PERSIST_CLASSES", source)
        self.assertIn("ORGANIZER_CLASSES", source)
        self.assertIn("solo_lora_organizer", source)
        self.assertIn("solo_log_organizer", source)
        self.assertIn("solo_outfit_forge", source)

    def test_release_contains_no_sample_workflows_or_starter_payload(self) -> None:
        self.assertFalse((ROOT / "Starter Content").exists())
        self.assertFalse((ROOT / "starter_content").exists())
        self.assertEqual(list(ROOT.rglob("*.soslibrary")), [])


if __name__ == "__main__":
    unittest.main()
