from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_packaging', ROOT / 'scripts/package_release.py')
packaging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packaging)

class ReleaseHygieneTests(unittest.TestCase):
    def test_exclusions_preserve_engine_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blocked = ['Starter Content/workflows/old.json', 'starter_content/old.soslibrary',
                       'IMPLEMENTATION_LEDGER.md', 'test-results-v3.3.77.txt',
                       'data/catalog.sqlite3', 'nested/cache.sqlite3', '__pycache__/a.pyc',
                       '.cache/index.json', 'yearbook_repairs/recovery.json',
                       'internal/receipt.txt', 'draft.bak', 'atomic.tmp']
            allowed = ['README.md', 'pyproject.toml', 'solo_log_organizer/data/theme_rules.json',
                       'docs/USER_MANUAL.md', 'tests/test_example.py', '.comfyignore']
            for name in blocked + allowed:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('fixture')
            previous = packaging.ROOT
            try:
                packaging.ROOT = root
                for name in blocked:
                    self.assertFalse(packaging.include(root / name), name)
                for name in allowed:
                    self.assertTrue(packaging.include(root / name), name)
            finally:
                packaging.ROOT = previous

    def test_package_has_no_bundled_library_payload(self):
        self.assertFalse((ROOT / 'Starter Content').exists())
        self.assertFalse((ROOT / 'starter_content').exists())
        self.assertEqual(list(ROOT.rglob('*.soslibrary')), [])

if __name__ == '__main__':
    unittest.main()
