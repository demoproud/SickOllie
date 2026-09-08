from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class V334MetadataLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata_js = (ROOT / "js" / "studio_metadata_core.js").read_text(encoding="utf-8")

    def test_inspector_top_uses_socket_row_count_not_stale_slot_positions(self) -> None:
        self.assertIn("const rows = Math.max(inputRows, outputRows);", self.metadata_js)
        self.assertIn("const socketBottom = 34 + (rows - 1) * 18;", self.metadata_js)
        content_top = self.metadata_js.split("function contentTop(node)", 1)[1].split("function inspectorMinimumContentHeight", 1)[0]
        self.assertNotIn("slot?.pos", content_top)

    def test_node_height_is_clamped_to_complete_left_inspector(self) -> None:
        self.assertIn("function inspectorMinimumContentHeight(node)", self.metadata_js)
        self.assertIn("function minimumMetadataHeight(node)", self.metadata_js)
        self.assertIn("function ensureMetadataHeight(node)", self.metadata_js)
        self.assertIn("ensureMetadataHeight(node);", self.metadata_js)
        self.assertIn("nodeType.prototype.onResize = function (size)", self.metadata_js)
        self.assertIn("size[1] = Math.max(Number(size[1] || 0), minimumHeight);", self.metadata_js)
        self.assertIn("this.size[1] = Math.max(Number(this.size[1] || 0), minimumHeight);", self.metadata_js)


if __name__ == "__main__":
    unittest.main()
