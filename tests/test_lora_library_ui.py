from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "js" / "solo_library_review.js"


class LoraLibraryUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_javascript_parses(self) -> None:
        result = subprocess.run(["node", "--check", str(SCRIPT)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bulk_selection_and_batched_collection_picker_are_present(self) -> None:
        self.assertIn("let loraSelectionMode = false;", self.source)
        self.assertIn('action(loraSelectionMode ? "DONE SELECTING" : "SELECT MULTIPLE"', self.source)
        self.assertIn('action("ADD TO COLLECTIONS", "#69e49a")', self.source)
        self.assertIn('action("SAVE COLLECTIONS", "#69e49a")', self.source)
        self.assertIn('request("/lora-collections/members/bulk"', self.source)
        picker = self.source[self.source.index("function openLoraCollectionPicker"):self.source.index("function renderSidebar")]
        self.assertNotIn("await load()", picker)

    def test_library_shell_paints_before_large_catalog_load(self) -> None:
        open_review = self.source[self.source.index("async function openReview"):self.source.index("app.registerExtension")]
        self.assertIn("requestAnimationFrame(() => requestAnimationFrame(resolve))", open_review)
        self.assertLess(open_review.index("document.body.append(root)"), open_review.index("await Promise.all([styles, load()])"))
        self.assertNotIn("await ensureStyle()", open_review)

    def test_large_folder_counts_are_precomputed(self) -> None:
        self.assertIn("function rebuildFolderAssetCounts()", self.source)
        self.assertIn("folderAssetCounts.get(value)", self.source)
        sidebar = self.source[self.source.index("function renderSidebar"):self.source.index("function renderTools")]
        self.assertNotIn("assets.filter(asset =>", sidebar)


    def test_yearbook_waits_for_existing_comfy_queue_before_claiming_previews(self) -> None:
        self.assertIn("async function yearbookComfyQueueState()", self.source)
        self.assertIn('fetch(api.apiURL("/queue")', self.source)
        self.assertIn("WAITING FOR COMFYUI QUEUE", self.source)
        self.assertIn("yearbook.autoQueue && (!yearbook.queueStarted || yearbook.waitingForQueue)", self.source)
        self.assertIn("yearbook.queueStarted = false;", self.source)

    def test_yearbook_supports_low_to_high_epoch_runs(self) -> None:
        self.assertIn("function yearbookEpochNumber(asset)", self.source)
        self.assertIn("function yearbookIncrementalOrder(values)", self.source)
        self.assertIn('rawEpoch === null || rawEpoch === undefined || rawEpoch === ""', self.source)
        self.assertIn('orderMode === "epoch_ascending"', self.source)
        self.assertIn("Incremental epoch/checkpoint · low → high", self.source)
        self.assertIn('folderScope !== ALL_FOLDERS && scopedEpochs.length >= 2', self.source)
        self.assertIn('items: orderedYearbookItems(items, orderMode)', self.source)

    def test_yearbook_routes_saved_images_away_from_project_outputs(self) -> None:
        self.assertIn('const LORA_YEARBOOK_OUTPUT_ROOT = "Sick Ollie Yearbooks/LoRA Library";', self.source)
        self.assertIn('outputs.flatMap(output => captureNodeValues(output, ["output_root"]))', self.source)
        self.assertIn('for (const output of run.outputs || []) setWidget(output, "output_root", LORA_YEARBOOK_OUTPUT_ROOT);', self.source)
        self.assertIn('outputs.some(output => widgetConnected(output, "output_root"))', self.source)

    def test_yearbook_sends_quality_and_optional_lora_preview_settings(self) -> None:
        self.assertIn('Library thumbnail size', self.source)
        self.assertIn('Thumbnail file budget', self.source)
        self.assertIn('Save full image beside each LoRA and update preview_url', self.source)
        self.assertIn('thumbnail_long_edge: thumbnailLongEdge, thumbnail_max_kib: thumbnailMaxKib, save_lora_preview: saveLoraPreview', self.source)
        self.assertIn('thumbnailLongEdge: yearbook.thumbnailLongEdge, thumbnailMaxKib: yearbook.thumbnailMaxKib, saveLoraPreview: yearbook.saveLoraPreview', self.source)

    def test_detail_yearbook_targets_only_selected_lora_and_replaces_its_thumbnail(self) -> None:
        self.assertIn('action("Yearbook this LoRA", "#f4ec51")', self.source)
        self.assertIn('if (openYearbookDialog(selected))', self.source)
        self.assertIn('const visible = selectedAsset ? [selectedAsset].filter(asset => asset.relative_lora)', self.source)
        self.assertIn('const targetMode = selectedAsset ? "all" : modeSelect.value;', self.source)
        self.assertIn('const orderMode = selectedAsset ? "current_view" : orderSelect.value;', self.source)
        self.assertIn('yearbookButton.onclick = () => openYearbookDialog();', self.source)


if __name__ == "__main__":
    unittest.main()
