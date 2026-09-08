from test_creative_library import catalog_module, recipe_module
from pathlib import Path
import tempfile
import types
import sys
import unittest
from unittest.mock import patch

class ManualOrganizationTests(unittest.TestCase):
    def test_scene_import_manual_placement_reuse_reload_and_undo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            c = catalog_module.SoloCatalog(root / 'catalog.sqlite3')
            old = c.create_component_collection('scene', 'Old Category')
            existing = c.upsert_recipe_component('scene', 'a pink flat background', manual=True)
            cid = existing['component_id']
            c.set_component_collections(cid, [old['collection_id']])
            c.set_component_rating(cid, 5)
            c.set_recipe_component_preview('scene', existing['value'], 'retained.webp')
            keep = c.create_library_collection('scene', 'Keep Me')
            c.add_library_assets_to_collections('scene', [cid], [keep['collection_id']])
            folder_paths = types.ModuleType('folder_paths')
            folder_paths.get_input_directory = lambda: str(root)
            with patch.dict(sys.modules, {'folder_paths': folder_paths}), patch.object(recipe_module, 'get_catalog', lambda: c), patch.object(recipe_module, '_safe_sync_recipe_prompt_logs', lambda: {}):
                result = recipe_module._import_component_text_log('scene', 'a pink flat background\na pink flat background\na blue flat background\n', 'Custom Backdrops', 'Flat Colors', 'My Scenes', collection_name='My Pack')
                self.assertEqual(result['values'], 2)
                self.assertEqual(result['input_duplicates'], 1)
                reloaded = catalog_module.SoloCatalog(root / 'catalog.sqlite3')
                rows = reloaded.recipe_components('scene')
                self.assertTrue(all([h['collection_id'] for h in r['collections']] == [result['folder_id']] for r in rows))
                retained = next(r for r in rows if r['component_id'] == cid)
                self.assertEqual(retained['rating'], 5)
                self.assertEqual(retained['preview_ref'], 'retained.webp')
                self.assertEqual({p['name'] for p in retained['pack_collections']}, {'Keep Me', 'My Pack'})
                recipe_module._ensure_scene_taxonomy(c)
                self.assertEqual([h['collection_id'] for h in c.recipe_components('scene')[0]['collections']], [result['folder_id']])
                undo = c.undo_component_import_batch(result['batch_id'])
                self.assertEqual(undo['deleted'], 1)
                row = c.recipe_components('scene')[0]
                self.assertEqual([h['collection_id'] for h in row['collections']], [old['collection_id']])
                self.assertEqual([p['name'] for p in row['pack_collections']], ['Keep Me'])

    def test_edit_preserves_relations_and_prevents_resurrection_or_duplicate_loss(self):
        for kind in ('outfit', 'scene'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                c = catalog_module.SoloCatalog(Path(directory) / 'catalog.sqlite3')
                old = c.upsert_recipe_component(kind, 'original value', manual=True)
                cid = old['component_id']
                home = c.create_component_collection(kind, 'Custom Home')
                pack = c.create_library_collection(kind, 'Favorites')
                c.set_component_collections(cid, [home['collection_id']])
                c.add_library_assets_to_collections(kind, [cid], [pack['collection_id']])
                c.set_component_rating(cid, 4)
                c.set_recipe_component_preview(kind, old['value'], 'kept.webp')
                edited = c.update_recipe_component_value(cid, 'edited value')
                self.assertNotEqual(cid, edited['component_id'])
                row = c.recipe_components(kind)[0]
                self.assertEqual(row['rating'], 4)
                self.assertEqual(row['preview_ref'], 'kept.webp')
                self.assertEqual([h['collection_id'] for h in row['collections']], [home['collection_id']])
                self.assertEqual([h['collection_id'] for h in row['pack_collections']], [pack['collection_id']])
                self.assertTrue(c.upsert_recipe_component(kind, 'original value')['tombstoned'])
                c.upsert_recipe_component(kind, 'other value', manual=True)
                with self.assertRaises(ValueError):
                    c.update_recipe_component_value(edited['component_id'], 'other value')
                self.assertEqual(len(c.recipe_components(kind)), 2)
                with c._connection() as db:
                    self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_collection_changes_invalidate_cached_gallery_and_order_survives_reload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.sqlite3'
            c = catalog_module.SoloCatalog(path)
            cid = c.upsert_recipe_component('scene', 'flat lavender', manual=True)['component_id']
            packs = [c.create_library_collection('scene', name)['collection_id'] for name in ('First', 'Second')]
            with patch.object(recipe_module, 'get_catalog', lambda: c):
                before = recipe_module._derived_value_snapshot('scene', sync_logs=False)
                self.assertEqual(before['scenes'][0]['pack_collections'], [])
                c.add_library_assets_to_collections('scene', [cid], [packs[0]])
                after = recipe_module._derived_value_snapshot('scene', sync_logs=False)
                self.assertEqual(after['scenes'][0]['pack_collections'][0]['collection_id'], packs[0])
                c.remove_library_assets_from_collection('scene', [cid], packs[0])
                removed = recipe_module._derived_value_snapshot('scene', sync_logs=False)
                self.assertEqual(removed['scenes'][0]['pack_collections'], [])
            c.set_creative_structure_order('scene', {'collections': ['home'], 'library_collections': packs[::-1]})
            reloaded = catalog_module.SoloCatalog(path)
            self.assertEqual([p['collection_id'] for p in reloaded.library_collections('scene')], packs[::-1])
            self.assertEqual(reloaded.creative_structure_order('scene')['collections'], ['home'])

    def test_bulk_collections_do_not_change_home_and_remove_only_one_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            c = catalog_module.SoloCatalog(Path(directory) / 'catalog.sqlite3')
            for kind in ('outfit', 'scene'):
                assets = [c.upsert_recipe_component(kind, v, manual=True)['component_id'] for v in ('one', 'two', 'unselected')]
                home = c.create_component_collection(kind, 'Custom Home')
                c.move_components_home(assets, home['collection_id'])
                packs = [c.create_library_collection(kind, n)['collection_id'] for n in ('A', 'B')]
                c.add_library_assets_to_collections(kind, assets[:2], packs)
                c.remove_library_assets_from_collection(kind, assets[:1], packs[0])
                rows = {r['component_id']: r for r in c.recipe_components(kind)}
                self.assertEqual([p['collection_id'] for p in rows[assets[0]]['pack_collections']], [packs[1]])
                self.assertEqual(len(rows[assets[1]]['pack_collections']), 2)
                self.assertEqual(rows[assets[2]]['pack_collections'], [])
                self.assertTrue(all([h['collection_id'] for h in r['collections']] == [home['collection_id']] for r in rows.values()))

if __name__ == '__main__': unittest.main()
