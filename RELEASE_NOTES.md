# SICK OLLIE Creator Studio + Toolkit 4.0.0

A major update from the supplied public v3.0.0 release. v4 connects reusable creative assets, model testing, image review and metadata reuse in one Studio workflow.

## Creative Library

Templates, Prompts, Outfits and Scenes now form the main creative workspace. Home is where an asset lives; Collection is a reusable group that does not move it. Saved Generation Recipes remain behind generation-state reuse.

## Loader Core

- **Model After generate.** Cycle diffusion models independently through Fixed, Increment, Decrement, Randomize or Shuffle.
- **LoRA Collection scope.** Use a virtual LoRA group without moving model files.
- **LIB scope jump.** Open LoRA Library in the active physical folder or Collection.
- **Dynamic secondary stack.** Add up to ten secondary LoRAs with independent enable, strength, copy, edit, info and remove controls.
- **Automatic trigger discovery.** Read explicit embedded evidence, training tags and safe Civitai fallback; model titles are not activation phrases.
- **Exact persistent trigger override.** Save a durable activation phrase for one LoRA.
- **Matching epoch family override.** Vary only the epoch/ep numeric token in the same folder; future matching files inherit the rule.
- **Exact > family > automatic priority.** Resolve a predictable effective trigger without overwriting more specific choices.
- **Disabled Main trigger suppression.** An inactive or zero-strength Main LoRA supplies no live trigger.

## Prompt Core

- **Manual / Prompt Input / Prompt Log.** Keep a prompt wire attached while choosing a separate Manual draft or a log.
- **Prompt Input socket.** Receive Final Prompt or Source Prompt from Image Metadata Core.
- **Manual Outfit A/B/C and Scene.** Type fixed component values independently of the main prompt source.
- **Collection-backed component logs.** Choose Wardrobe, Looks or Scene Collections as live pools with stable identities.
- **Affix placeholder resolution and progression.** Resolve components across prefix, source and suffix, and advance used log streams.
- **Trigger Builder and placement.** Follow Loader or choose a candidate; placement controls actual insertion.
- **Save / clear active LoRA override.** Persist an override from Prompt Core and return to Loader resolution when cleared.

## Generation Core

- **seed_input.** An external INT overrides the seed widget for that run; -1 randomizes.
- **Live applied LoRA shelf.** See LoRAs actually applied, associated with the connected Loader when available.

## Preview Core

- **Pin + Compare.** Capture the displayed result and open it beside the live preview in one action.
- **Clear comparison.** Remove the reference and restore the normal preview width.
- **Save to Library.** Save the verified displayed image and available generation state for reuse.

## Image Metadata Core

- **Image upload / clear / optional IMAGE.** Inspect a chosen file; a genuinely connected image input takes precedence.
- **Final / Source prompt / seed outputs.** Recover prompt text, seed, settings, models, components and reports when metadata exists.
- **Individual copy fields / full report.** Copy available seed, Outfit A/B/C, Scene and prompt data directly.
- **Save to Library.** Save normalized displayed metadata and its loaded image into Creative Library.
- **Queued source lifetime.** Previously queued imports survive subsequent image loading and clearing.

## Creative Library

- **Templates / Prompts / Outfits / Scenes.** Browse reusable formulas, resolved prompts, outfit material and locations in four primary areas.
- **Home vs Collection.** Home is the canonical location; Collections group assets without moving them.
- **Template classification.** Recognized unresolved portable tokens classify an asset as a Template.
- **TXT import / mixed routing / Original Log.** Split mixed logs line by line while retaining managed source provenance and order.
- **Search / facets / placeholder / rating filters.** Narrow the view before reviewing or running scoped operations.
- **Source / Reusable vs Thumbnail Combination.** Choose portable source text or the captured resolved component combination.
- **Load into active workflow.** Apply selected text and available metadata deliberately to the current Studio graph.
- **Queue / Queue Next.** Submit an asset and restore visible state; Queue Next fronts pending work, not the running job.
- **400-item Prompt batch limit.** Process large Prompt batches in separate passes.
- **Saved Generation Recipes.** Preserve generation-state assets behind reuse, metadata import and portable packs.
- **Select Multiple / bulk curation.** Use applicable bulk Collection, Home, Builder, thumbnail and deletion actions.
- **Library Menu / Purge / Clean Orphan Thumbnails.** Inspect destructive scopes and remove only previews not referenced by live records.

## Library Inspector

- **Thumbnail / View / no-thumbnail entry.** Open review without loading the record into the active workflow.
- **Fixed large frame / independent panes.** Review within a viewport-bounded frame with independently scrolling metadata.
- **Scope snapshot / Left / Right.** Browse the active filtered set without rating changes reordering the session.
- **Fit / 50%-400% of fit / image toggle.** Zoom relative to Fit; image click switches Fit and 200% of fit.
- **Stars / keys 1-5 / 0.** Rate persistently; 0 clears, and clicking the current star rating clears too.
- **Delete Asset / Delete key.** Confirm type-specific record deletion and continue to the next surviving item.
- **Metadata platter / Copy All.** Copy only available fields; a trusted captured seed of zero remains valid.
- **Prompt / Template actions.** Load, Queue, Queue Next, Edit, Collections, Generate Preview and Delete Thumbnail.
- **Look / Scene actions.** Load a component, Move Home, manage Collections, preview, or inspect an available source Recipe.
- **Wardrobe actions.** Add to Builder, Load A/B/C, Edit, Collections or Generate Preview; thumbnail deletion is a bulk workflow.

## Generate Previews

- **Unified scopes across five asset kinds.** Choose selected items, filtered results, Homes, Collections, sections or the whole Creative Library.
- **Sequential capture / queue-safe start.** Wait for existing queue work, then generate and capture each planned asset in sequence.
- **Default 800 x 1000 / presets / custom.** Use Fast, larger presets or custom dimensions; Scene runs use landscape orientation.
- **2048 px / 512 KiB / WebP / atomic.** Preserve aspect and EXIF orientation, avoid upscaling and retain the old preview if replacement fails.

## Creative Theater

- **Live / Frozen / history / run progress.** Follow completed previews or browse past frames while generation continues.
- **Fit / Fill / Actual.** Choose how the review image fills the Theater surface.
- **1-5 stars / Reject / keyboard.** Use 1-5 for stars, X for Reject, Space for Live/Frozen and arrows for history.
- **Close / reopen without stopping run.** Review can close independently of the underlying preview run.

## Library Packs

- **One .soslibrary format / presets.** Use Starter / Share Pack, Wardrobe & Looks, Current Scope, Full Backup or Custom.
- **Selective import preview / merge.** Review and select content; merge without deleting unrelated local assets.
- **Pack reimport reconciliation.** Reconcile pack-supplied organization while preserving user-owned review and organization state.

## Distribution

- **Content-free distribution.** v4 ships without starter logs, sample workflows, bundled Library Packs or old manuals. Import a separately supplied Library Pack deliberately.

## Outfits

- **Wardrobe vs Looks.** Keep reusable pieces and complete outfit values distinct within Outfits.
- **Outfit Builder assembly.** Combine and reorder pieces, copy the result, load an Outfit slot or save a Look.
- **Color / Pattern / Cut-Fit / Material / Wear / Graphic-Text.** Tune per-piece attributes inline rather than duplicating color variants in Wardrobe.
- **Direct Wardrobe Load A/B/C.** Load a piece as a Manual Outfit value; loading a Look returns the slot to log behavior.

## Outfit Forge

- **Local deterministic beta generation.** Generate complete Outfit Look logs from recognized themes without an external language model.
- **Theme / count / seed / three sliders.** Set coverage, complexity and wearability, then inspect how the brief was interpreted.
- **Optional refinements / required / avoided.** Refine generation through editable vocabulary and phrase constraints.
- **Edit / duplicate / remove / reforge / search / autosave.** Curate a browser-saved draft without regenerating every line.
- **Audit / Constraint Fidelity / Brief Coverage.** Distinguish structural diversity, enforced constraints and unrepresented brief terms.
- **Copy / TXT / Export to Outfit Looks.** Publish complete Looks into a chosen category/subcategory or keep an editable log.

## LoRA Library

- **Nested folders / scoped scans.** Scan configured physical roots or one subtree; Collection scopes cannot scan files.
- **Collections / multi-select membership.** Group LoRAs across folders and feed the group into Loader or Yearbook.
- **Card Queue / Queue Current View.** Queue LoRAs with current workflow settings in visible order or shuffled.

## LoRA Yearbook

- **Comparison prompt / strength / dimensions / seed.** Run consistent LoRA tests with temporary comparison settings.
- **Epoch/checkpoint numeric progression.** Test detected training families from low to high; ordered and shuffled alternatives remain.

## LoRA Theater

- **Live/Frozen / history / Fit-Fill-Actual / progress.** Browse the active Yearbook run while generation continues.
- **Favorite / Like / Retest / Reject / keys.** F or 1 Favorite; L or 2 Like/Keep; R or 3 Retest; X Reject; Space toggles Live.

## Automated runs

- **Dedicated output roots / restored state.** Route runs under Sick Ollie Yearbooks/LoRA Library or Creative Library and restore original settings afterward.

## Studio Hub

- **Focused tool navigation.** Open Creative Library, LoRA Library, Outfit Forge or LoRA Organizer from the Studio hub.

## Compatibility

- **Classic IDs and legacy Preview migration.** Keep Classic workflows and migrate retired preview nodes without changing user data.
- **Legacy Log Organizer remains registered.** Older workflow nodes remain usable; the tool is not a primary Hub destination.
- **Canonical log / preview path migration.** Read compatible old references and move managed previews into a shared canonical store.

## Quality of life

- **Input focus / modal stacking / press feedback.** Recover Studio-owned typing focus and provide consistent button feedback on supported devices.

## Retired and consolidated

The former Workshop-first and Recipe Catalog navigation gives way to the four Creative Library areas. Home and Collection replace overlapping organization terms. Creative Library automation is Generate Previews; LoRA testing retains Yearbook. Library Pack uses .soslibrary in place of the separate Wardrobe Pack workflow. Preview’s main actions are Pin + Compare, Clear and Save to Library. Prompt/Template thumbnail maintenance lives in Inspector and bulk workflows.

## A clean distribution

v4 includes no starter logs, sample workflows, bundled Library Pack, historical manuals or development checkpoint history. Import a separately supplied Library Pack when available, or your own TXT logs. Existing user-owned content is preserved by normal extension replacement.

## Install or update

Back up ComfyUI user data and input/SickOllieLogs. Close ComfyUI, replace the ComfyUI-SickOllie extension folder, restart and hard-refresh the frontend. rgthree-comfy remains required for Loader’s shared model-information services. Select compatible locally installed model files. See [README](README.md) and the [v4 User Manual](docs/SICK-OLLIE-v4-User-Manual.pdf).