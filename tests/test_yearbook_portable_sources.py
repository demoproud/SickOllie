from test_creative_library import catalog_module, recipe_module, recipe_payload
from pathlib import Path
import tempfile
import unittest

class YearbookPortableSourceTests(unittest.TestCase):
    def test_capture_uses_original_template_and_run_identity_not_connected_loader(self):
        source = 'luminous photo of NAME wearing OUTFIT beside BRAND'
        payload = recipe_payload('luminous photo of Stacey wearing OUTFIT beside Sick Dolls', 'luminous photo of Stacey wearing pink socks beside Sick Dolls', [
            {'token': 'NAME', 'widget': 'name_value', 'value': 'no'},
            {'token': 'BRAND', 'widget': 'item_value', 'value': 'Wrong Brand'},
            {'token': 'OUTFIT', 'widget': 'outfit_value_A', 'value': 'pink socks'},
        ])
        src,res = recipe_module._payload_prompt_variants(payload, canonical_source=source, identity_placeholders=[{'token':'NAME','value':'Stacey'},{'token':'BRAND','value':'Sick Dolls'}])
        self.assertEqual(src, source)
        self.assertEqual(res, 'luminous photo of NAME wearing pink socks beside BRAND')
        src,res = recipe_module._payload_prompt_variants(payload, canonical_source=source)
        self.assertEqual(src,source)
        self.assertEqual(res,'')

    def test_identity_reversal_does_not_replace_parts_of_words(self):
        self.assertEqual(recipe_module._replace_portable_identity_values('luminous knowingly Stacey', [{'token':'NAME','value':'no'}]), 'luminous knowingly Stacey')
        self.assertEqual(recipe_module._replace_portable_identity_values('Ann watches Annette beside A+B.', [{'token':'NAME','value':'Ann'},{'token':'BRAND','value':'A+B'}]), 'NAME watches Annette beside BRAND.')

    def test_repair_preserves_component_choices_and_ordinary_words(self):
        record = {'value':'luminous NAME wearing OUTFIT in SCENE beside BRAND', 'source_prompt_snapshot':'lumiNAMEus Stacey wearing OUTFIT in SCENE beside Sick Dolls', 'resolved_prompt_snapshot':'lumiNAMEus Stacey wearing pink socks in a studio beside Sick Dolls', 'resolved_seed_source':'catalog-run', 'preview_metadata':{'outfit_a':'pink socks','scene':'a studio'}}
        source,resolved = catalog_module.repair_yearbook_prompt_snapshots(record)
        self.assertEqual(source,record['value'])
        self.assertEqual(resolved,'luminous NAME wearing pink socks in a studio beside BRAND')
        record['preview_metadata']={}
        self.assertEqual(catalog_module.repair_yearbook_prompt_snapshots(record),(record['value'],''))
        record['resolved_seed_source']='imported-image'
        self.assertEqual(catalog_module.repair_yearbook_prompt_snapshots(record),(record['source_prompt_snapshot'],record['resolved_prompt_snapshot']))

    def test_existing_database_repairs_on_reopen_without_changing_preview_seed_or_rating(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'catalog.sqlite3';c=catalog_module.SoloCatalog(path)
            row,_=c.import_prompt_asset({'value':'luminous NAME wearing OUTFIT','kind':'template'})
            pid=row['prompt_id'];c.set_prompt_rating(pid,5)
            c.set_prompt_preview(pid,'keep.webp',resolved_seed=42,resolved_seed_source='catalog-run',source_prompt_snapshot='lumiNAMEus Stacey wearing OUTFIT',resolved_prompt_snapshot='lumiNAMEus Stacey wearing pink socks',preview_metadata={'outfit_a':'pink socks'})
            c=catalog_module.SoloCatalog(path)
            actual=next(r for r in c.indexed_prompt_assets() if r['prompt_id']==pid)
            self.assertEqual(actual['source_prompt_snapshot'],'luminous NAME wearing OUTFIT')
            self.assertEqual(actual['resolved_prompt_snapshot'],'luminous NAME wearing pink socks')
            self.assertEqual(actual['preview_ref'],'keep.webp');self.assertEqual(actual['resolved_seed'],42);self.assertEqual(actual['rating'],5)
            self.assertEqual(c.repair_yearbook_prompt_sources(),0)
            c.set_prompt_preview(pid,'new.webp',source_prompt_snapshot='luminous NAME wearing OUTFIT',resolved_prompt_snapshot='',replace_prompt_snapshots=True)
            actual=next(r for r in c.indexed_prompt_assets() if r['prompt_id']==pid)
            self.assertEqual(actual['resolved_prompt_snapshot'],'')

    def test_old_pack_is_repaired_on_import_and_reimport_does_not_restore_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            c=catalog_module.SoloCatalog(Path(directory)/'catalog.sqlite3')
            record={'source_prompt_id':'old-id','value':'NAME wearing OUTFIT','kind':'template','source_prompt_snapshot':'Stacey wearing OUTFIT','resolved_prompt_snapshot':'Stacey wearing socks','resolved_seed_source':'catalog-run','resolved_seed':42,'preview_metadata':{'outfit_a':'socks'},'rating':4}
            data={'prompts':[record]}; manifest={'pack_id':'repair-test','name':'test','export_mode':'backup'}
            c.merge_creative_library_pack_records(manifest,data)
            c.merge_creative_library_pack_records(manifest,data)
            rows=c.indexed_prompt_assets();self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['source_prompt_snapshot'],'NAME wearing OUTFIT')
            self.assertEqual(rows[0]['resolved_prompt_snapshot'],'NAME wearing socks')
            self.assertEqual(record['source_prompt_snapshot'],'Stacey wearing OUTFIT')

if __name__=='__main__':unittest.main()
