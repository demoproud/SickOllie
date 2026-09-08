from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "js" / "solo_recipe_catalog.js"


class CreativeLibraryUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_javascript_parses(self) -> None:
        result = subprocess.run(
            ["node", "--check", str(SCRIPT)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_primary_navigation_matches_canonical_library_jobs_and_retires_workshop(self) -> None:
        self.assertIn('recipes: { label: "TEMPLATES"', self.source)
        self.assertIn('prompts: { label: "PROMPTS"', self.source)
        self.assertIn('outfits: { label: "OUTFITS"', self.source)
        self.assertIn('scenes: { label: "SCENES"', self.source)
        views = self.source[self.source.index('const LIBRARY_VIEWS = {'):self.source.index('};', self.source.index('const LIBRARY_VIEWS = {'))]
        self.assertNotIn('WORKSHOP', views)
        self.assertNotIn('fragments:', views)
        pack_meta = self.source[self.source.index('const CREATIVE_LIBRARY_PACK_META = ['):self.source.index('];', self.source.index('const CREATIVE_LIBRARY_PACK_META = ['))]
        self.assertNotIn('WORKSHOP', pack_meta)

    def test_template_filters_are_multi_placeholder_and_prompt_navigation_is_single_home(self) -> None:
        self.assertIn('for (const token of promptPlaceholderFilters)', self.source)
        self.assertIn('params.append("placeholder"', self.source)
        self.assertIn('promptHomeCounts[kind]', self.source)
        self.assertIn('promptParent', self.source)
        self.assertIn('promptSubcategory', self.source)
        self.assertIn('Every placeholder-bearing line routes to Templates', self.source)
        self.assertIn('fully resolved, token-free prompts', self.source)

    def test_retired_workshop_data_stays_purgeable_without_a_visible_tab(self) -> None:
        self.assertIn('{ key: "workshop", label: "Legacy Workshop Data"', self.source)
        self.assertIn('Saved Generation Recipes are a separate option above.', self.source)
        self.assertIn('PURGE EVERYTHING', self.source)

    def test_whole_library_preview_run_can_fill_missing_thumbnails_unattended(self) -> None:
        self.assertIn('async function fetchWholeLibraryYearbookInventory()', self.source)
        self.assertIn('async function openWholeLibraryYearbookDialog()', self.source)
        self.assertIn('GENERATE PREVIEWS · LIBRARY SECTIONS', self.source)
        self.assertIn('LIBRARIES TO FILL · MISSING THUMBNAILS ONLY', self.source)
        self.assertIn('Templates', self.source)
        self.assertIn('Prompts', self.source)
        self.assertIn('Outfit Looks', self.source)
        self.assertIn('Wardrobe', self.source)
        self.assertIn('Scenes', self.source)
        self.assertIn('locationMode: "whole-library"', self.source)
        self.assertIn('libraryWide: true', self.source)
        self.assertIn('continueOnError: continueCheck.checked', self.source)
        self.assertIn('Shuffle the whole run for broad coverage', self.source)
        self.assertIn('Theater defaults off to keep the browser lighter', self.source)
        self.assertIn('data.libraryYearbook', self.source.replace('dataset.libraryYearbook', 'data.libraryYearbook'))
        self.assertIn('api.addEventListener?.("execution_error"', self.source)
        self.assertIn('catalogPreviewDimensions(run, item)', self.source)
        self.assertIn('async function catalogComfyQueueState()', self.source)
        self.assertIn('fetch(api.apiURL("/queue")', self.source)
        self.assertIn('WAITING FOR COMFYUI QUEUE', self.source)
        self.assertIn('run.autoQueue && (!run.queueStarted || run.waitingForQueue)', self.source)

    def test_yearbook_routes_saved_images_away_from_project_outputs(self) -> None:
        self.assertIn('const CREATIVE_YEARBOOK_OUTPUT_ROOT = "Sick Ollie Yearbooks/Creative Library";', self.source)
        self.assertIn('outputs.flatMap(output => captureStudioValues(output, ["output_root"]))', self.source)
        self.assertIn('for (const output of run.outputs || []) setStudioWidget(output, "output_root", CREATIVE_YEARBOOK_OUTPUT_ROOT);', self.source)
        self.assertIn('...outputs.map(output => [output, "output_root"])', self.source)

    def test_prompt_and_template_preview_paths_are_available(self) -> None:
        self.assertIn('async function openPromptCatalogRunDialog', self.source)
        self.assertIn('function fetchPromptYearbookScope', self.source)
        self.assertIn('params.set("include_all", "1")', self.source)
        self.assertIn('GENERATE ${kind === "template" ? "TEMPLATE" : "PROMPT"} PREVIEWS', self.source)
        self.assertIn('COMPARISON SETTINGS', self.source)
        self.assertIn('CATALOG_YEARBOOK_DIMENSION_PRESETS', self.source)
        self.assertIn('/prompt-assets/${encodeURIComponent(item.prompt_id)}/preview', self.source)
        self.assertIn('function sortLoadedPromptPreviews', self.source)
        self.assertIn('function promotePromptPreview', self.source)
        self.assertIn('promptAssets = [promoted, ...promptAssets.filter', self.source)
        self.assertIn('promptPage = 0;', self.source)
        self.assertIn('function openPromptThumbnail', self.source)
        self.assertIn('data-library-focus-key', self.source)
        self.assertIn('async function previewImageBlob', self.source)
        self.assertIn('STOP RUN', self.source)

    def test_prompt_edit_modal_has_working_close_and_central_button_feedback(self) -> None:
        modal = self.source[self.source.index('function collectionModal(title'):self.source.index('async function creativeStructureOrder', self.source.index('function collectionModal(title'))]
        self.assertIn('const closeModal = () => {', modal)
        self.assertIn('requestAnimationFrame(() => recoverTextInputFocus());', modal)
        self.assertIn('return { overlay, card, close: closeModal };', modal)
        self.assertIn('installStudioInteractions(overlay);', modal)
        editor = self.source[self.source.index('async function editPromptAssetCard(asset, onSaved = null)'):self.source.index('function openPromptsForFragment', self.source.index('async function editPromptAssetCard(asset, onSaved = null)'))]
        self.assertIn('const { overlay, card, close } = collectionModal', editor)
        self.assertIn('cancel.onclick = close;', editor)
        self.assertIn('close();', editor)

    def test_prompt_cards_can_queue_without_closing_the_library(self) -> None:
        self.assertIn('let promptCardQueueChain = Promise.resolve();', self.source)
        self.assertIn('function queuePromptAsset(asset, button, queuePosition = 0)', self.source)
        self.assertIn('async function submitPromptAssetToQueue(asset, button = null, announce = true, queuePosition = 0)', self.source)
        self.assertIn('app.queuePrompt(queuePosition, 1)', self.source)
        self.assertIn('action("QUEUE", "#6ee7a2")', self.source)
        self.assertIn('action("QUEUE NEXT", "#f6e65a")', self.source)

    def test_outfit_builder_supports_live_per_piece_finetuning_without_duplicate_records(self) -> None:
        self.assertIn('const WARDROBE_COLORS = [', self.source)
        self.assertIn('const WARDROBE_MATERIALS = [', self.source)
        self.assertIn('const WARDROBE_GRAPHICS = [', self.source)
        self.assertIn('a graphic that reads "BRAND"', self.source)
        self.assertIn('a graphic that reads "NAME"', self.source)
        self.assertIn('function coloredBuilderValue(item)', self.source)
        self.assertIn('attributeControl("COLOR", WARDROBE_COLORS', self.source)
        self.assertIn('attributeControl("MATERIAL", WARDROBE_MATERIALS', self.source)
        self.assertIn('attributeControl("GRAPHIC / TEXT", WARDROBE_GRAPHICS', self.source)
        self.assertIn('`${label} · NONE`', self.source)
        self.assertIn('CUSTOM…', self.source)
        self.assertIn('input.oninput = () => { item[property] = cleanBuilderAttribute(input.value); liveRefresh(); };', self.source)
        self.assertNotIn('prompt(customPrompt', self.source)
        self.assertIn('wardrobeBuilder.map(coloredBuilderValue)', self.source)

    def test_outfit_builder_uses_the_available_library_height_instead_of_a_tiny_item_scroller(self) -> None:
        self.assertIn('const availableHeight = Math.max(430, Number(listHost?.clientHeight || 0) - 28);', self.source)
        self.assertIn('height: `${availableHeight}px`', self.source)
        self.assertIn('flex: "1 1 auto", minHeight: "120px"', self.source)
        self.assertNotIn('maxHeight: "290px"', self.source)
        self.assertIn('queuePromptAsset(asset, queueNext, -1)', self.source)
        self.assertIn('function promptAssetResolvedSeed(asset)', self.source)
        self.assertIn('applyPromptAsset(asset, { applySeed: false })', self.source)
        self.assertIn('? "Queued next" : "Queued"', self.source)
        self.assertIn('prompt using the current workflow seed', self.source)
        queue_fn = self.source[self.source.index('async function submitPromptAssetToQueue'):self.source.index('function queuePromptAsset', self.source.index('async function submitPromptAssetToQueue'))]
        self.assertNotIn('setStudioWidget(generationNode, "seed_value"', queue_fn)

    def test_prompt_collections_rating_filter_and_queue_cap(self) -> None:
        self.assertIn('const PROMPT_QUEUE_CAP = 400;', self.source)
        self.assertIn('function showPromptFolderEditor(promptIds = [], allFiltered = false)', self.source)
        self.assertIn('ADD TO COLLECTION', self.source)
        self.assertIn('QUEUE THIS COLLECTION', self.source)
        self.assertIn('params.set("max_results", String(PROMPT_QUEUE_CAP))', self.source)
        self.assertIn('const items = (Array.isArray(data?.prompts) ? data.prompts : []).slice(0, PROMPT_QUEUE_CAP);', self.source)
        self.assertIn('const start = action(startLabel, "#6ee7a2"); start.disabled = !queueCount;', self.source)
        self.assertNotIn('start.disabled = !total || total > PROMPT_QUEUE_CAP', self.source)
        self.assertIn('QUEUE FIRST ${queueCount.toLocaleString()}', self.source)
        self.assertIn('All ${kindLabel} can never be queued as one batch.', self.source)
        self.assertIn('["5", "5★ only"]', self.source)
        self.assertIn('if (promptRatingFilter) params.set("rating", String(promptRatingFilter));', self.source)

    def test_library_reopens_from_revision_aware_cache_and_loads_heavy_tabs_on_demand(self) -> None:
        self.assertIn('let libraryLoadedOnce = false;', self.source)
        self.assertIn('function refreshLibraryIfStale()', self.source)
        self.assertIn('request("/state")', self.source)
        self.assertIn('request("/recipes?sync=0")', self.source)
        self.assertIn('request(`/derived-values?sync=0', self.source)
        self.assertIn('componentViewsLoaded', self.source)
        self.assertIn('wardrobeDataLoaded', self.source)
        self.assertIn('image.loading = "lazy";', self.source)
        self.assertIn('Ready · reopened from cache', self.source)

    def test_catalog_theater_mode_is_live_first_and_reviewable(self) -> None:
        self.assertIn('function openCreativeTheater', self.source)
        self.assertIn('function appendCreativeTheaterEntry', self.source)
        self.assertIn('Open Theater Mode · Live', self.source)
        self.assertIn('data-catalog-theater', self.source)
        self.assertIn('REJECT [X]', self.source)
        self.assertIn('"fit", "FIT"', self.source)
        self.assertIn('"fill", "FILL"', self.source)
        self.assertIn('"actual", "ACTUAL"', self.source)
        self.assertIn('/^[1-5]$/.test(event.key)', self.source)
        self.assertIn('event.key.toLowerCase() === "x"', self.source)
        self.assertIn('event.key === "ArrowLeft"', self.source)
        self.assertIn('event.key === " "', self.source)
        self.assertIn('name: "Rejected"', self.source)
        self.assertIn('/prompt-assets/bulk/collections/remove', self.source)
        self.assertIn('/derived-values/bulk/collections/remove', self.source)
        self.assertIn('theater.dismissed = true', self.source)
        self.assertIn('!theater.overlay && !theater.dismissed', self.source)

    def test_yearbook_presets_include_ollie_resolution(self) -> None:
        self.assertIn('["1440x1920", "1440 × 1920 · Ollie", 1440, 1920]', self.source)

    def test_prompt_catalog_can_import_a_local_text_log_without_moving_the_original(self) -> None:
        self.assertIn('function showPromptLogImporter()', self.source)
        self.assertIn('action("IMPORT LOG", accent)', self.source)
        self.assertIn('picker.multiple = false', self.source)
        self.assertIn('SELECT .TXT FILE', self.source)
        self.assertIn('/prompt-assets/import', self.source)
        self.assertIn('CATEGORY · ONE TRUE HOME', self.source)
        self.assertIn('SUBCATEGORY · OPTIONAL', self.source)
        self.assertIn('No subcategory · Category only', self.source)
        self.assertIn('LOG / SCENE NAME', self.source)
        self.assertIn('COLLECTION · OPTIONAL', self.source)
        self.assertIn('the original local file is never moved or changed', self.source)
        self.assertIn('Imported Logs', self.source)
        self.assertIn('Every placeholder-bearing line routes to Templates', self.source)
        self.assertIn('Mixed logs populate both tabs automatically', self.source)
        self.assertNotIn('if (!isTemplate) {\n        const importLog = action("IMPORT LOG"', self.source)

    def test_component_log_import_matches_prompt_log_workflow(self) -> None:
        self.assertIn('function showComponentLogImporter(kind, building = false)', self.source)
        self.assertIn('return showComponentLogImporter(kind)', self.source)
        self.assertIn('/component-assets/import', self.source)
        self.assertIn('SELECT .TXT FILE', self.source)
        self.assertIn('SUBCATEGORY · OPTIONAL', self.source)
        self.assertIn('COLLECTION · OPTIONAL', self.source)
        self.assertIn('Your chosen destination controls placement', self.source)
        self.assertIn('The original file stays untouched', self.source)

    def test_wardrobe_builder_uses_attributes_instead_of_duplicate_catalog_items(self) -> None:
        self.assertIn('const WARDROBE_PATTERNS =', self.source)
        self.assertIn('const WARDROBE_CUTS =', self.source)
        self.assertIn('const WARDROBE_WEAR =', self.source)
        self.assertIn('attributeControl("PATTERN"', self.source)
        self.assertIn('attributeControl("CUT / FIT"', self.source)
        self.assertIn('attributeControl("WEAR"', self.source)
        self.assertIn('sectionTitle("HOMES"', self.source)
        self.assertIn('folderButton(subtypeName', self.source)

    def test_prompt_catalog_has_source_log_navigation_and_original_line_sort(self) -> None:
        self.assertIn('let promptLogPath = "";', self.source)
        self.assertIn('Original log order', self.source)
        self.assertIn('home.logs?.[parent]?.[subcategory]', self.source)
        self.assertIn('promptSort = "source_order"', self.source)
        self.assertIn('` · #${sourceLine}`', self.source)
        self.assertIn('const parents = [], subcategories = [], source_paths = [], collections = [];', self.source)
        self.assertIn('prompt_scopes.prompt.source_paths', self.source)

    def test_creative_library_structure_managers_cover_editable_taxonomies(self) -> None:
        self.assertIn('function showPromptStructureManager(kind = activePromptKind())', self.source)
        self.assertIn('MANAGE STRUCTURE', self.source)
        self.assertIn('`${noun.toUpperCase()} LIBRARY STRUCTURE`', self.source)
        self.assertIn('Manage Prompt Category → Subcategory → Log structure.', self.source)
        self.assertIn('Manage the Category → Subcategory → Log structure used by Templates.', self.source)
        self.assertIn('OUTFIT LOOK HOME', self.source)
        self.assertIn('function showSceneBiomeManager()', self.source)
        self.assertIn('＋ MANAGE COLLECTIONS', self.source)
        self.assertIn('/structure-order', self.source)
        self.assertIn('/prompt-logs/rename', self.source)
        self.assertIn('/prompt-structure', self.source)
        self.assertIn('method: "DELETE"', self.source)
        self.assertIn('PERMANENTLY DELETE Category', self.source)
        self.assertIn('No copy was created.', self.source)
        self.assertIn('＋ CATEGORY', self.source)
        self.assertIn('＋ SUBCATEGORY', self.source)
        self.assertIn('Move Log up', self.source)
        self.assertIn('Move Scene Category up', self.source)
        self.assertIn('Move Collection up', self.source)
        self.assertNotIn('Deleted folders move their contents to Unsorted', self.source)
        self.assertNotIn('Last Import', self.source)
        self.assertNotIn('isLastImportNode', self.source)
        self.assertIn('promptHomeUniverse[kind] || promptHomeCounts[kind]', self.source)

    def test_export_builder_defaults_to_all_checked_and_hides_internal_pack_plumbing(self) -> None:
        self.assertIn('addNestedHomeScopes("template", "TEMPLATES"', self.source)
        self.assertIn('addNestedHomeScopes("prompt", "PROMPTS"', self.source)
        self.assertIn('libraryPackScopeBox("SAVED RECIPES"', self.source)
        self.assertNotIn('NARROW TEMPLATES', self.source)
        self.assertNotIn('NARROW PROMPTS', self.source)
        self.assertNotIn('CUSTOM PACK BUILDER', self.source)
        self.assertNotIn('INCLUDE TAXONOMY + MEMBERSHIPS', self.source)
        self.assertNotIn('INCLUDE REQUIRED DEPENDENCIES', self.source)
        self.assertIn('main.indeterminate = state.any && !state.all;', self.source)
        self.assertIn('include_taxonomy: true', self.source)
        self.assertIn('include_dependencies: true', self.source)
        self.assertIn('included_source_paths', self.source)
        self.assertIn('included_collections', self.source)
        self.assertIn('INCLUDE THUMBNAILS', self.source)

    def test_prompt_seed_haptics_wardrobe_default_and_connected_clean_name_yearbook_qol(self) -> None:
        self.assertIn('let outfitMode = "pieces";', self.source)
        self.assertIn('outfitMode = "pieces";', self.source)
        self.assertIn('import { installStudioInteractions } from "./studio_interactions.js";', self.source)
        self.assertIn('installStudioInteractions(root);', self.source)
        self.assertIn('const attachedSeed = Number(asset?.resolved_seed);', self.source)
        self.assertIn('const previewSeed = Number(result?.resolved_seed);', self.source)
        self.assertIn('live.resolved_seed = previewSeed', self.source)
        self.assertIn('const escaped = token.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&");', self.source)
        self.assertIn('applyPromptAsset(asset, { applySeed: false })', self.source)
        self.assertIn('resolvePromptYearbookDirectValues(run, fillCatalogPrompt(template, item))', self.source)
        self.assertIn('NAME and BRAND / ITEM are pre-resolved', self.source)
        yearbook = self.source[self.source.index('async function openPromptCatalogRunDialog(explicitItems = null)'):self.source.index('function openCatalogRunDialog()')]
        protected = yearbook[yearbook.index('const protectedNames ='):yearbook.index('const blocked =')]
        self.assertNotIn('name_value', protected)
        self.assertNotIn('item_value', protected)

    def test_library_inspector_browses_scope_and_exposes_metadata_copy_platter(self) -> None:
        self.assertIn('function openLibraryInspector({ kind, item, index = 0, total = 1', self.source)
        self.assertIn('overlay.dataset.libraryInspector = kind;', self.source)
        self.assertIn('event.key === "ArrowLeft"', self.source)
        self.assertIn('event.key === "ArrowRight"', self.source)
        self.assertIn('scoped.set("include_all","1")', self.source)
        self.assertIn('const slots = Array.from({length:total}', self.source)
        for field in ('FINAL PROMPT', 'SOURCE PROMPT', 'OUTFIT A', 'OUTFIT B', 'OUTFIT C', 'SCENE', 'SEED'):
            self.assertIn(f'inspectorCopyField("{field}"', self.source)
        for action_label in ('LOAD', 'QUEUE', 'QUEUE NEXT', 'EDIT', 'COLLECTIONS', 'GENERATE PREVIEW', 'DELETE THUMBNAIL'):
            self.assertIn(f'actionButton("{action_label}"', self.source)
        self.assertIn('/prompt-assets/${encodeURIComponent(String(asset.prompt_id || ""))}/collections', self.source)
        self.assertIn('image.title="Click to toggle Fit / 200% of fit"', self.source)

    def test_gallery_thumbnails_open_inspector_and_preview_run_uses_friendly_collection_labels(self) -> None:
        self.assertIn('function previewRunLogOptionLabel(promptNode, widgetName, value)', self.source)
        self.assertIn('◆ ${source} · ${String(scope.name || "Collection")}', self.source)
        self.assertGreaterEqual(self.source.count('previewRunLogOptionLabel(prompt, widgetName, value)'), 2)
        self.assertIn('Inspect this ${kind} and browse the current gallery scope', self.source)
        self.assertIn('Inspect this Wardrobe item and browse the current gallery scope', self.source)
        self.assertIn('image.onclick = () => openPromptThumbnail(asset)', self.source)
        self.assertIn('preview.role = "button"', self.source)

    def test_universal_purge_lives_in_shared_library_menu_with_secondary_review(self) -> None:
        self.assertIn('moreSummary.textContent = "LIBRARY MENU"', self.source)
        self.assertIn('menuSection("MAINTENANCE"', self.source)
        self.assertIn('data-library-menu-purge', self.source)
        self.assertIn('function showCreativeLibraryPurge()', self.source)
        self.assertIn('TOTAL CREATIVE LIBRARY PURGE', self.source)
        self.assertIn('FINAL PURGE REVIEW', self.source)
        self.assertIn('PURGE SELECTED', self.source)
        self.assertIn('PURGE EVERYTHING', self.source)
        for label in ('Templates', 'Prompts', 'Saved Generation Recipes', 'Outfit Looks', 'Wardrobe', 'Scenes', 'Legacy Workshop Data'):
            self.assertIn(f'label: "{label}"', self.source)
        self.assertIn('/maintenance/purge', self.source)
        self.assertNotIn('data-library-menu-clear-templates', self.source)
        self.assertNotIn('data-library-menu-clear-prompts', self.source)
        self.assertNotIn('data-library-menu-purge-wardrobe', self.source)


    def test_recipe_derived_outfit_looks_offer_delete_everywhere(self) -> None:
        self.assertIn('const label = kind === "outfit" ? "Outfit Look" : "Scene";', self.source)
        self.assertIn('if (componentId) {', self.source)
        self.assertIn('JSON.stringify({ component_ids: [componentId], everywhere: true })', self.source)
        self.assertIn('DELETE EVERYWHERE for this ${label}', self.source)

    def test_bulk_delete_outfit_looks_is_delete_everywhere(self) -> None:
        self.assertIn('const everywhere = kind === "scene" || kind === "outfit";', self.source)
        self.assertIn('const deleteLabel = kind === "outfit" ? "Outfit Look" : "Scene";', self.source)
        self.assertIn('DELETE EVERYWHERE for ${componentIds.length} selected ${deleteLabel}', self.source)
        self.assertIn('JSON.stringify({ component_ids: componentIds, everywhere })', self.source)

    def test_collections_cover_looks_scenes_and_wardrobe_and_export_scope(self) -> None:
        self.assertIn('let libraryCollections = { outfit: [], scene: [], wardrobe: [] };', self.source)
        self.assertIn('COLLECTIONS', self.source)
        self.assertIn('＋ MANAGE COLLECTIONS', self.source)
        self.assertIn('function showLibraryCollectionManager(kind)', self.source)
        self.assertIn('+ ADD VIEW', self.source)
        self.assertIn('/library-collections/bulk', self.source)
        self.assertIn('included_pack_collections', self.source)
        self.assertIn('filter_pack_collections: true', self.source)

    def test_prompt_load_defaults_to_workflow_seed_and_only_offers_trusted_saved_seed(self) -> None:
        self.assertIn('function promptAssetSeedSource(asset)', self.source)
        self.assertIn('["imported-image", "preview-image"].includes(source)', self.source)
        self.assertIn('USE EXISTING WORKFLOW SEED', self.source)
        self.assertIn('USE SAVED SEED · ${savedSeed}', self.source)
        self.assertIn('seed_source", "catalog-run"', self.source)
        self.assertIn('Preview-run seeds, legacy seed 0 values', self.source)

    def test_prompt_template_outfit_scene_thumbnail_controls_use_delete_and_regenerate(self) -> None:
        self.assertNotIn('action("THUMB", "#6ee7a2")', self.source)
        self.assertNotIn('action("DEL THUMB", "#ff9b5f")', self.source)
        self.assertNotIn('action("PREVIEW", "#6ee7a2")', self.source)
        self.assertIn('buttons.append(load, copyButton, edit, view);', self.source)
        self.assertIn('view.title = "Open Library Inspector";', self.source)
        self.assertIn('DELETE THUMBNAILS', self.source)
        self.assertIn('GENERATE PREVIEWS', self.source)
        self.assertIn('deleteSelectedPromptThumbnails()', self.source)
        self.assertIn('regenerateSelectedPromptThumbnails()', self.source)
        self.assertIn('deleteSelectedComponentThumbnails()', self.source)
        self.assertIn('regenerateSelectedComponentThumbnails()', self.source)
        self.assertIn('/derived-values/bulk/previews/delete', self.source)
        self.assertIn('openCatalogRunDialogForItem(null, items)', self.source)
        backend = (ROOT / "solo_recipe_catalog.py").read_text(encoding="utf-8")
        self.assertIn('/prompt-assets/{prompt_id}/preview', backend)
        self.assertIn('/derived-values/{component_id}/preview', backend)
        self.assertIn('/derived-values/bulk/previews/delete', backend)

    def test_templates_can_queue_and_use_collections(self) -> None:
        self.assertIn('params.set("kind", activePromptKind())', self.source)
        self.assertIn('if (activeCollection) params.set("collection"', self.source)
        self.assertIn('Queue this ${isTemplate ? "template" : "prompt"}', self.source)
        self.assertIn('Add this ${isTemplate ? "template" : "prompt"} to a Collection', self.source)
        self.assertIn('request("/showcase-collections?kind=prompt")', self.source)
        self.assertIn('request("/showcase-collections?kind=template")', self.source)
        self.assertIn('MANAGE ${noun.toUpperCase()} COLLECTIONS', self.source)
        self.assertIn('collection_counts_by_kind', (ROOT / "solo_recipe_catalog.py").read_text(encoding="utf-8"))

    def test_prompt_load_can_choose_source_or_thumbnail_combination(self) -> None:
        self.assertIn('function promptAssetSourceText(asset)', self.source)
        self.assertIn('function promptAssetResolvedText(asset)', self.source)
        self.assertIn('SOURCE · REUSABLE', self.source)
        self.assertIn('THUMBNAIL COMBINATION', self.source)
        self.assertIn('NAME + BRAND ALWAYS STAY PORTABLE', self.source)
        self.assertIn('promptText: promptAssetText(asset, promptMode)', self.source)


if __name__ == "__main__":
    unittest.main()

class CreativeLibraryPackUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_portable_library_pack_controls_are_present(self) -> None:
        self.assertIn('async function showCreativeLibraryExport()', self.source)
        self.assertIn('function showCreativeLibraryImport(file, inspection)', self.source)
        self.assertIn('function importCreativeLibraryPack()', self.source)
        self.assertIn('async function showOrphanThumbnailCleaner()', self.source)
        self.assertIn('.soslibrary', self.source)
        self.assertIn('BUILD LIBRARY PACK', self.source)
        self.assertIn('STARTER / SHARE PACK', self.source)
        self.assertIn('WARDROBE & LOOKS', self.source)
        self.assertIn('FULL BACKUP', self.source)
        self.assertIn('IMPORT LIBRARY PACK', self.source)
        self.assertIn('function openLibraryPackWorkflow()', self.source)
        self.assertIn('Clean orphan thumbnails', self.source)
        self.assertIn('/library-pack/inspect', self.source)
        self.assertIn('Unchecked pack content was left alone.', self.source)
        self.assertNotIn('.soswardrobe', self.source)
        self.assertNotIn('/wardrobe-pack/', self.source)

    def test_one_preview_entry_point_exposes_consistent_scopes(self) -> None:
        self.assertIn('async function openGeneratePreviewsDialog()', self.source)
        self.assertIn('SELECTED ITEMS', self.source)
        self.assertIn('CURRENT FILTERED RESULTS', self.source)
        self.assertIn('SELECT LIBRARY SECTIONS', self.source)
        self.assertIn('action(catalogRun ? "STOP PREVIEW RUN" : "GENERATE PREVIEWS"', self.source)

    def test_first_open_hides_legacy_shell_and_surfaces_retryable_failures(self) -> None:
        self.assertIn('let libraryBootstrapping = false;', self.source)
        self.assertIn('function renderLibraryLoadError(error)', self.source)
        self.assertIn('RETRY LIBRARY LOAD', self.source)
        self.assertIn('libraryBootstrapping = true;', self.source)
        self.assertIn('Object.assign(tools.style, { display: "none"', self.source)
        self.assertIn('Object.assign(tokenTools.style, { display: "none"', self.source)
