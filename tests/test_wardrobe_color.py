from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wardrobe_color", ROOT / "wardrobe_color.py")
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class WardrobeColorTests(unittest.TestCase):
    def test_plain_colors_are_removed_but_material_and_shape_remain(self) -> None:
        self.assertEqual(module.neutralize_wardrobe_color("black loafers"), "loafers")
        self.assertEqual(module.neutralize_wardrobe_color("a pale pink satin slip dress"), "satin slip dress")
        self.assertEqual(module.neutralize_wardrobe_color("dark brown patent Mary Janes"), "patent Mary Janes")

    def test_pattern_defining_and_metallic_language_is_preserved(self) -> None:
        self.assertEqual(module.neutralize_wardrobe_color("black-and-white striped tee"), "black-and-white striped tee")
        self.assertEqual(module.neutralize_wardrobe_color("rose gold body chain"), "rose gold body chain")
        self.assertEqual(module.neutralize_wardrobe_color("silver platform heels"), "silver platform heels")

    def test_finishers_and_body_styling_are_not_rewritten(self) -> None:
        self.assertEqual(module.neutralize_wardrobe_color("red body paint", "styling"), "red body paint")
        self.assertEqual(module.neutralize_wardrobe_color("otherwise bare", "finisher"), "otherwise bare")

    def test_assembly_attributes_share_one_catalog_identity(self) -> None:
        self.assertEqual(module.wardrobe_color_key("cream platform loafers"), "platform loafers")
        self.assertEqual(module.wardrobe_color_key("black platform loafers"), "platform loafers")
        self.assertEqual(module.wardrobe_color_key("black-and-white striped tee"), "tee")
        self.assertEqual(module.wardrobe_color_key("pink plaid tee"), "tee")

    def test_context_cut_and_pattern_fragments_leave_the_garment_identity(self) -> None:
        self.assertEqual(module.canonicalize_wardrobe_value("bike shorts barely visible underneath"), "bike shorts")
        self.assertEqual(module.canonicalize_wardrobe_value("bike shorts underneath"), "bike shorts")
        self.assertEqual(module.canonicalize_wardrobe_value("a pastel pink plaid micro skirt"), "skirt")
        self.assertEqual(module.canonicalize_wardrobe_value("a pink plaid pleated mini skirt"), "pleated skirt")
        self.assertEqual(module.canonicalize_wardrobe_value("a satin mini skirt"), "satin skirt")

    def test_only_unmistakable_independent_comma_parts_are_split(self) -> None:
        self.assertEqual(module.split_wardrobe_compound("a black mini skirt, striped arm warmers"), [
            ("a black mini skirt", "Bottoms", "Skirts"),
            ("striped arm warmers", "Accessories", "Arm Warmers"),
        ])
        self.assertEqual(module.split_wardrobe_compound("bikini bottom, and flip-flops"), [
            ("bikini bottom", "Bodywear", "Bodysuits"),
            ("flip-flops", "Footwear", "Sandals"),
        ])
        self.assertEqual(module.split_wardrobe_compound("satin skirt, with pearl buttons and a lace hem"), [
            ("satin skirt, with pearl buttons and a lace hem", "", ""),
        ])
