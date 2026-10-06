from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = types.ModuleType("sickollie_yearbook_test")
PACKAGE.__path__ = [str(ROOT)]
sys.modules.setdefault(PACKAGE.__name__, PACKAGE)
sys.modules.setdefault("folder_paths", types.ModuleType("folder_paths"))

SPEC = importlib.util.spec_from_file_location(f"{PACKAGE.__name__}.solo_library_review", ROOT / "solo_library_review.py")
assert SPEC and SPEC.loader
review = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = review
SPEC.loader.exec_module(review)


class YearbookPreviewTests(unittest.TestCase):
    def test_full_image_copy_updates_only_preview_url(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lora = root / "portrait.safetensors"
            lora.write_bytes(b"model")
            original = root / "original.png"
            Image.new("RGB", (800, 1000), "magenta").save(original)
            sidecar = root / "portrait.metadata.json"
            sidecar.write_text(json.dumps({"model_name": "Portrait", "preview_url": "old.jpeg", "civitai": {"id": 42}}), encoding="utf-8")

            with patch.object(review, "_lora_roots", return_value=[root]):
                saved = review._save_yearbook_lora_preview(original, lora)

            self.assertEqual(saved.name, "portrait.yearbook.png")
            self.assertEqual(saved.read_bytes(), original.read_bytes())
            self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8")), {
                "model_name": "Portrait", "preview_url": saved.as_posix(), "civitai": {"id": 42},
            })

    def test_invalid_sidecar_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lora = root / "portrait.safetensors"
            lora.write_bytes(b"model")
            original = root / "original.png"
            Image.new("RGB", (800, 1000), "magenta").save(original)
            sidecar = root / "portrait.metadata.json"
            sidecar.write_text("invalid json", encoding="utf-8")

            with patch.object(review, "_lora_roots", return_value=[root]):
                with self.assertRaisesRegex(ValueError, "invalid metadata sidecar"):
                    review._save_yearbook_lora_preview(original, lora)

            self.assertEqual(sidecar.read_text(encoding="utf-8"), "invalid json")
            self.assertFalse((root / "portrait.yearbook.png").exists())

    def test_higher_thumbnail_setting_keeps_more_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            class Catalog:
                path = root / "catalog.sqlite"

                def set_thumbnail(self, *args, **kwargs):
                    pass

            with patch.object(review, "get_catalog", return_value=Catalog()):
                result = review._save_thumbnail(Image.new("RGB", (800, 1000), "magenta"), "asset", "generated:yearbook", bound=(1024, 1024), max_bytes=1024 * 1024, crop_portrait=False)

            self.assertEqual((result["width"], result["height"]), (800, 1000))
            self.assertLessEqual(result["byte_size"], 1024 * 1024)
            self.assertTrue((root / "lora_thumbnails" / result["filename"]).is_file())


if __name__ == "__main__":
    unittest.main()
