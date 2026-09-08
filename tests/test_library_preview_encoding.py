from io import BytesIO
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch, Mock
from PIL import Image
from test_creative_library import recipe_module as module


class LibraryPreviewEncodingTests(unittest.TestCase):
    def test_large_portrait_and_landscape_preserve_aspect_and_detail(self):
        for source, expected in [((2400, 3200), (1536, 2048)), ((3200, 1800), (2048, 1152))]:
            with self.subTest(source=source):
                encoded = module._encode_library_preview(Image.new('RGB', source, '#79a5cb'))
                with Image.open(BytesIO(encoded)) as result:
                    self.assertEqual(result.format, 'WEBP')
                    self.assertEqual(result.size, expected)
                self.assertLessEqual(len(encoded), 512 * 1024)

    def test_small_images_are_not_upscaled(self):
        for size in [(400, 500), (800, 1000), (1, 7)]:
            with Image.open(BytesIO(module._encode_library_preview(Image.new('RGB', size)))) as result:
                self.assertEqual(result.size, size)

    def test_exif_orientation_is_applied_before_sizing(self):
        image = Image.new('RGB', (1200, 800))
        image.getexif()[274] = 6
        with Image.open(BytesIO(module._encode_library_preview(image))) as result:
            self.assertEqual(result.size, (800, 1200))

    def test_noisy_image_meets_byte_budget_without_extreme_compression(self):
        size = (1024, 1280)
        image = Image.frombytes('RGB', size, random.Random(91).randbytes(size[0] * size[1] * 3))
        encoded = module._encode_library_preview(image)
        self.assertLessEqual(len(encoded), 512 * 1024)
        with Image.open(BytesIO(encoded)) as result:
            self.assertLessEqual(result.width, size[0])
            self.assertAlmostEqual(result.width / result.height, .8, places=2)

    def test_all_creative_preview_writers_share_the_larger_encoder(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            catalog = Mock()
            catalog.recipe_component_id.return_value = 'outfit:abc'
            catalog.wardrobe_item_id.return_value = 'piece:def'
            with patch.object(module, '_preview_directory', return_value=root), patch.object(module, '_component_preview_directory', return_value=root), patch.object(module, 'get_catalog', return_value=catalog):
                image = Image.new('RGB', (1440, 1920), '#daa3ee')
                names = [module._save_preview(image, 'prompt-a'), module._save_component_preview(image, 'outfit', 'dress'), module._save_wardrobe_preview(image, 'piece', 'shirt')]
                for name in names:
                    with Image.open(root / name) as result:
                        self.assertEqual(result.size, image.size)
                self.assertEqual(sorted(p.name for p in root.iterdir()), sorted(names))

    def test_failed_encode_or_replace_preserves_previous_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'preview.webp'
            target.write_bytes(b'previous preview')
            with patch.object(module, '_encode_library_preview', side_effect=ValueError('failed')):
                with self.assertRaises(ValueError):
                    module._write_library_preview(Image.new('RGB', (20, 20)), target)
            self.assertEqual(target.read_bytes(), b'previous preview')
            with patch.object(Path, 'replace', side_effect=OSError('locked')):
                with self.assertRaises(OSError):
                    module._write_library_preview(Image.new('RGB', (20, 20)), target)
            self.assertEqual(target.read_bytes(), b'previous preview')
            self.assertEqual(list(Path(folder).iterdir()), [target])
