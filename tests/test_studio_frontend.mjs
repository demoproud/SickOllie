import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";


const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function executableSource(filename, appendedTests) {
    let source = fs.readFileSync(path.join(root, "js", filename), "utf8");
    source = source.replace(
        /import \{ app \} from "\.\.\/\.\.\/\.\.\/scripts\/app\.js";\s*/,
        "const app = { graph: { links: {} }, registerExtension() {} };\n",
    );
    source = source.replace(
        /import \{ api \} from "\.\.\/\.\.\/\.\.\/scripts\/api\.js";\s*/,
        "const api = { apiURL(value) { return value; } };\n",
    );
    source = source.replace(
        /import \{[\s\S]*?\} from "\.\/studio_theme\.js";\s*/,
        `const STUDIO_LAYOUT = { minWidth: 820, pad: 12, gap: 8, rowHeight: 36, headerHeight: 96, socketStart: 120, socketStep: 21, socketGap: 12, sectionGap: 10, bottomPad: 18 };
         const STUDIO_THEME = { cyan: "#35d7ff", magenta: "#ff4ab8", yellow: "#f6e65a", green: "#6ee7a2", ink: "#08070c", panel: "#111", row: "#222", rowHover: "#333", outline: "#444", label: "#aaa", text: "#fff", body: "#000" };
         const applyStudioNodeColors = () => {};
         const drawStudioChrome = () => {};
         const drawStudioSectionFrame = () => {};
        `,
    );
    return `${source}\n${appendedTests}`;
}

eval(executableSource("studio_prompt_core.js", `
    assert.deepEqual(aliasesInText("OUTFIT_A then OUTFIT", ["OUTFIT"]), ["OUTFIT"]);
    assert.deepEqual(aliasesInText("{OUTFIT_A} and OUTFIT", tokenCandidates("OUTFIT_A", "OUTFIT")), ["{OUTFIT_A}", "OUTFIT"]);

    const legacyValues = LEGACY_V10_NAMES.map((name) => {
        if (name === "manual_prompt") return "legacy prompt";
        if (name === "outfit_token_A") return "OUTFIT";
        return DEFAULTS[name];
    });
    const migrated = migratePromptWorkflow({ properties: { so_prompt_core_schema_version: 10 }, widgets_values: legacyValues });
    assert.equal(migrated.widgets_values.length, CANONICAL_NAMES.length);
    assert.equal(migrated.widgets_values[CANONICAL_NAMES.indexOf("manual_prompt")], "legacy prompt");
    assert.equal(migrated.widgets_values[CANONICAL_NAMES.indexOf("outfit_token_A")], "OUTFIT");
    for (const name of Object.keys(LEGACY_PLACEMENTS)) {
        assert.equal(migrated.widgets_values[CANONICAL_NAMES.indexOf(name)], "token");
        assert.equal(DEFAULTS[name], "smart");
    }

    const legacyLibraryPaths = canonicalValues({
        prompt_log_file: "prompts/Recipe Library/MASTER - All Recipe Prompts.txt",
        outfit_log_file_A: "outfits/Recipe Library/MASTER - Resolved Recipe Outfits.txt",
        scene_log_file: "scenes/Recipe Library/MASTER - Resolved Recipe Scenes.txt",
    });
    const migratedLibraryPaths = migratePromptWorkflow({
        properties: { so_prompt_core_schema_version: 14 },
        widgets_values: legacyLibraryPaths,
    }).widgets_values;
    assert.equal(migratedLibraryPaths[CANONICAL_NAMES.indexOf("prompt_log_file")], "prompts/Creative Library/MASTER - Saved Recipe Prompts.txt");
    assert.equal(migratedLibraryPaths[CANONICAL_NAMES.indexOf("outfit_log_file_A")], "outfits/Creative Library/MASTER - Outfit Looks.txt");
    assert.equal(migratedLibraryPaths[CANONICAL_NAMES.indexOf("scene_log_file")], "scenes/Creative Library/MASTER - Scenes.txt");

    const legacyConnectedInputValues = canonicalValues({ prompt_source: "manual", manual_prompt: "saved manual draft" });
    const migratedConnectedInput = migratePromptWorkflow({
        properties: { so_prompt_core_schema_version: 15 },
        inputs: [{ name: "manual_prompt_input", link: 77 }],
        widgets_values: legacyConnectedInputValues,
    }).widgets_values;
    assert.equal(migratedConnectedInput[CANONICAL_NAMES.indexOf("prompt_source")], "input");
    assert.equal(migratedConnectedInput[CANONICAL_NAMES.indexOf("manual_prompt")], "saved manual draft");


    const v12TriggerValues = canonicalValues({ trigger_placement: "off", trigger_override: "sicktype" });
    const migratedTrigger = migratePromptWorkflow({ properties: { so_prompt_core_schema_version: 12 }, widgets_values: v12TriggerValues });
    assert.equal(migratedTrigger.widgets_values[CANONICAL_NAMES.indexOf("trigger_placement")], "smart");
    assert.equal(migratedTrigger.widgets_values[CANONICAL_NAMES.indexOf("trigger_override")], "sicktype");

    const stateNode = {
        widgets: CANONICAL_NAMES.map((name) => ({ name, value: DEFAULTS[name], options: {}, callback() {} })),
        __soLogLines: { outfit_A: ["yellow jacket"] },
        __soLogLineFiles: { outfit_A: "outfits/a.txt" },
        __sooutfit_index_preview_A: { options: {} },
        properties: {},
        setDirtyCanvas() {},
    };
    widget(stateNode, "manual_prompt").value = "NAME wears OUTFIT";
    widget(stateNode, "outfit_log_file_A").value = "outfits/a.txt";
    assert.equal(streamAssemblyState(stateNode, "outfit_A").action, "replace");

    const inputSourceNode = {
        widgets: CANONICAL_NAMES.map((name) => ({ name, value: DEFAULTS[name], options: {}, callback() {} })),
        inputs: [{ name: "manual_prompt_input", link: 77 }],
        properties: {},
        setDirtyCanvas() {},
    };
    widget(inputSourceNode, "manual_prompt").value = "manual stays put";
    app.graph.links[77] = { origin_id: 70, origin_slot: 0 };
    app.graph.getNodeById = id => id === 70 ? ({
        title: "Image Metadata Core",
        outputs: [{ name: "source_prompt" }],
        __soLiveOutputs: { source_prompt: "metadata prompt" },
    }) : null;
    widget(inputSourceNode, "prompt_source").value = "manual";
    assert.equal(activeSourceTemplate(inputSourceNode), "manual stays put");
    syncExternalManualPrompt(inputSourceNode);
    assert.equal(widget(inputSourceNode, "manual_prompt").value, "manual stays put");
    assert.equal(widget(inputSourceNode, "prompt_source").value, "manual");
    widget(inputSourceNode, "prompt_source").value = "input";
    assert.equal(activeSourceTemplate(inputSourceNode), "metadata prompt");
    assert.equal(streamAssemblyState(inputSourceNode, "prompt").label, "Prompt Input");

    widget(stateNode, "manual_prompt").value = "NAME portrait";
    widget(stateNode, "outfit_placement_A").value = "token";
    widget(stateNode, "outfit_mode_A").value = "increment";
    advanceStream(stateNode, "outfit_A");
    assert.equal(widget(stateNode, "outfit_index_A").value, 0);
    widget(stateNode, "outfit_placement_A").value = "smart";
    advanceStream(stateNode, "outfit_A");
    assert.equal(widget(stateNode, "outfit_index_A").value, 1);

    const affixNode = {
        widgets: CANONICAL_NAMES.map((name) => ({ name, value: DEFAULTS[name], options: {}, callback() {} })),
        inputs: [],
        __soLogLines: { prompt: ["portrait"], scene: ["rooftop", "desert"], outfit_A: [] },
        __soLogLineFiles: { prompt: "prompts/a.txt", scene: "scenes/a.txt", outfit_A: "[None]" },
        __soscene_index_preview: { options: {} },
        __sooutfit_index_preview_A: { options: {} },
        properties: {},
        setDirtyCanvas() {},
    };
    widget(affixNode, "prompt_source").value = "log";
    widget(affixNode, "prompt_log_file").value = "prompts/a.txt";
    widget(affixNode, "suffix_enabled").value = true;
    widget(affixNode, "suffix_text").value = "SCENE";
    widget(affixNode, "scene_log_file").value = "scenes/a.txt";
    widget(affixNode, "scene_placement").value = "token";
    widget(affixNode, "scene_mode").value = "shuffle";
    assert.equal(streamAssemblyState(affixNode, "scene").used, true);
    assert.equal(promptLiveResolvedPrompt(affixNode), "portrait, rooftop");
    advanceStream(affixNode, "scene");
    assert.equal(widget(affixNode, "scene_index").value, 1);
    assert.equal(promptLiveResolvedPrompt(affixNode), "portrait, desert");

    widget(affixNode, "suffix_text").value = "OUTFIT";
    affixNode.__soLogLines.outfit_A = ["red dress", "blue dress"];
    affixNode.__soLogLineFiles.outfit_A = "outfits/a.txt";
    widget(affixNode, "outfit_log_file_A").value = "outfits/a.txt";
    widget(affixNode, "outfit_placement_A").value = "token";
    widget(affixNode, "outfit_mode_A").value = "increment";
    assert.equal(streamAssemblyState(affixNode, "outfit_A").used, true);
    assert.equal(promptLiveResolvedPrompt(affixNode), "portrait, red dress");
    advanceStream(affixNode, "outfit_A");
    assert.equal(widget(affixNode, "outfit_index_A").value, 1);
    assert.equal(promptLiveResolvedPrompt(affixNode), "portrait, blue dress");

    widget(stateNode, "item_token").value = "{BRAND}";
    assert.equal(configuredPlaceholderLabel(stateNode, "item_token", "ITEM"), "BRAND");
    assert.equal(promptExternalInputLabel(stateNode, "item_value"), "BRAND value");

    widget(stateNode, "prompt_source").value = "log";
    assert.equal(promptSourceHeight(stateNode), 255);
    const sourceFrame = promptSourceFrameGeometry(100, 373);
    const modeIndexBottom = 373 - PROMPT_LOG_BOTTOM_PAD;
    assert.equal(sourceFrame.bottom - modeIndexBottom, 18);

    stateNode.inputs = [{ name: "prefix_text", link: 11 }];
    stateNode.__soLastAssembly = { prefix: { text: "linked prefix" } };
    app.graph.links[11] = { origin_id: 7, origin_slot: 0 };
    app.graph.getNodeById = () => ({
        title: "Text Source",
        outputs: [{ name: "text" }],
        __soLiveOutputs: { text: "live prefix" },
    });
    const prefixState = promptConnectedTextState(stateNode, "prefix_text", "prefix");
    assert.equal(prefixState.connected, true);
    assert.equal(prefixState.display, "Text Source → text · live prefix");

    stateNode.inputs = [{ name: "name_value", link: 12 }];
    stateNode.__soLastAssembly = { name: { value: "previous run" } };
    widget(stateNode, "prompt_source").value = "manual";
    widget(stateNode, "manual_prompt").value = "NAME portrait";
    app.graph.links[12] = { origin_id: 8, origin_slot: 1 };
    const loaderOrigin = {
        title: "Loader Core",
        outputs: [{ name: "model" }, { name: "clean_name" }],
        __soLiveOutputs: { clean_name: "current LoRA" },
    };
    app.graph.getNodeById = () => loaderOrigin;
    assert.equal(substitutionState(stateNode, "name").value, "current LoRA");
    loaderOrigin.__soLiveOutputs.clean_name = "next LoRA";
    assert.equal(substitutionState(stateNode, "name").value, "next LoRA");


    const missingLogNode = {
        widgets: CANONICAL_NAMES.map((name) => ({ name, value: DEFAULTS[name], options: {}, callback() {} })),
        properties: {},
        setDirtyCanvas() {},
    };
    const missingPrompt = widget(missingLogNode, "prompt_log_file");
    missingPrompt.value = "prompts/renamed-away.txt";
    missingPrompt.options.values = [NO_FILE, "prompts/current.txt"];
    widget(missingLogNode, "prompt_source").value = "manual";
    assert.equal(healMissingLogSelection(missingLogNode, "prompt"), true);
    assert.equal(missingPrompt.value, NO_FILE);
    assert.equal(widget(missingLogNode, "prompt_source").value, "manual");

    missingPrompt.value = "prompts/moved.txt";
    widget(missingLogNode, "prompt_source").value = "log";
    assert.equal(healMissingLogSelection(missingLogNode, "prompt"), true);
    assert.equal(missingPrompt.value, NO_FILE);
    assert.equal(widget(missingLogNode, "prompt_source").value, "manual");

    const collectionNode = {
        __soLogCollections: {
            outfit_A: [{
                reference: "[Wardrobe Collection:wardrobe:dresses]",
                collection_id: "wardrobe:dresses",
                name: "Tasteful Dresses",
                source: "wardrobe",
                asset_count: 20,
            }],
        },
    };
    assert.deepEqual(collectionLogScopeId("[Wardrobe Collection:wardrobe:dresses]"), { source: "wardrobe", collection_id: "wardrobe:dresses" });
    assert.equal(collectionLogDisplay(collectionNode, "outfit_A", "[Wardrobe Collection:wardrobe:dresses]"), "◆ Wardrobe · Tasteful Dresses");
    assert.equal(collectionLogRowLabel(collectionNode.__soLogCollections.outfit_A[0]), "Wardrobe · Tasteful Dresses · 20 items");

    const triggerNode = {
        widgets: CANONICAL_NAMES.map((name) => ({ name, value: DEFAULTS[name], options: {}, callback() {} })),
        inputs: [{ name: "main_trigger", link: 993 }],
        properties: {},
        setDirtyCanvas() {},
    };
    widget(triggerNode, "manual_prompt").value = "{TRIGGER} portrait";
    chooseTriggerOverride(triggerNode, "sicktype");
    assert.equal(widget(triggerNode, "trigger_override").value, "sicktype");
    // Choosing a source no longer changes placement behind the user's back.
    assert.equal(widget(triggerNode, "trigger_placement").value, "off");
    widget(triggerNode, "trigger_placement").value = "smart";
    assert.equal(triggerAssemblyState(triggerNode).used, true);

    // Candidate overrides are scoped to the LoRA that was active when chosen.
    const triggerLoader = {
        title: "Loader Core",
        widgets: [
            { name: "main_lora", value: "styles/a.safetensors" },
            { name: "main_enabled", value: true },
            { name: "main_strength", value: 1 },
        ],
        outputs: [
            { name: "model", links: [] },
            { name: "clean_name", links: [993] },
            { name: "main_trigger", links: [] },
            { name: "main_folder", links: [] },
        ],
        __soMainTrigger: "style_a",
        __soLiveOutputs: { clean_name: "a", main_trigger: "style_a" },
    };
    app.graph.links[993] = { id: 993, origin_id: 99, origin_slot: 1, type: "STRING" };
    app.graph.getNodeById = id => id === 99 ? triggerLoader : loaderOrigin;
    assert.equal(repairPromptTriggerConnection(triggerNode), true);
    assert.equal(app.graph.links[993].origin_slot, 2);
    assert.deepEqual(triggerLoader.outputs[1].links, []);
    assert.deepEqual(triggerLoader.outputs[2].links, [993]);
    assert.equal(repairPromptTriggerConnection(triggerNode), false);
    chooseTriggerOverride(triggerNode, "style_a");
    assert.equal(triggerNode.properties.so_trigger_override_lora, "styles/a.safetensors");
    triggerLoader.widgets[0].value = "styles/b.safetensors";
    assert.equal(syncTriggerOverrideScope(triggerNode), true);
    assert.equal(widget(triggerNode, "trigger_override").value, "");

    // Loader-owned overrides update the live connection instead of becoming a
    // second Prompt Core pin or a detected-candidate entry.
    triggerLoader.__soTriggerButton = { name: "" };
    assert.equal(applyConnectedLoaderTrigger(triggerNode, triggerLoader, {
        trigger: "jester, blue-skinned tiefling, curved horns",
        source: "user.override",
    }), "jester, blue-skinned tiefling, curved horns");
    assert.equal(triggerLoader.__soLiveOutputs.main_trigger, "jester, blue-skinned tiefling, curved horns");
    assert.equal(triggerLoader.__soMainTriggerSource, "user.override");
    assert.match(triggerLoader.__soTriggerButton.name, /blue-skinned tiefling/);
    widget(triggerNode, "manual_prompt").value = "vertical mirror selfie";
    widget(triggerNode, "trigger_placement").value = "prepend";
    assert.equal(triggerAssemblyState(triggerNode).value, "jester, blue-skinned tiefling, curved horns");
    assert.match(triggerAssemblyState(triggerNode).label, /Saved LoRA override/);
    assert.equal(
        promptLiveResolvedPrompt(triggerNode),
        "jester, blue-skinned tiefling, curved horns, vertical mirror selfie",
    );

    // Turning Main LoRA off must immediately suppress its connected trigger,
    // even if the Loader still has a previously resolved live value cached.
    widget(triggerLoader, "main_enabled").value = false;
    assert.equal(triggerAssemblyState(triggerNode).value, "");
    assert.equal(promptLiveResolvedPrompt(triggerNode), "vertical mirror selfie");
    widget(triggerLoader, "main_enabled").value = true;

    layoutPromptInputSockets(triggerNode);
    assert.equal(triggerNode.inputs[0].label, " ");
    assert.equal(promptExternalInputLabel(triggerNode, "main_trigger"), "TRIGGER value");
`));

eval(executableSource("studio_preview_core.js", `
    const legacyPreview = {
        version: 0.4,
        nodes: [{
            id: 7,
            type: "SOFitPreview",
            pos: [100, 200],
            size: [480, 620],
            widgets_values: ["Cover", "Checkerboard", "#123456"],
            properties: { so_fit_preview_images: [{ filename: "preview.png", type: "temp", subfolder: "" }] },
        }],
        links: [[9, 2, 0, 7, 0, "IMAGE"]],
        definitions: {
            subgraphs: [{
                nodes: [{ id: 11, type: "SOFitPreview", widgets_values: ["Actual Size", "Solid", "#000000"] }],
            }],
        },
    };
    const before = JSON.parse(JSON.stringify(legacyPreview));
    assert.equal(migrateLegacyPreviewNodes(legacyPreview), 2);
    assert.equal(legacyPreview.nodes[0].type, "SOFitPreviewStudio");
    assert.equal(legacyPreview.definitions.subgraphs[0].nodes[0].type, "SOFitPreviewStudio");
    assert.deepEqual(legacyPreview.nodes[0].pos, before.nodes[0].pos);
    assert.deepEqual(legacyPreview.nodes[0].size, before.nodes[0].size);
    assert.deepEqual(legacyPreview.nodes[0].widgets_values, before.nodes[0].widgets_values);
    assert.deepEqual(legacyPreview.nodes[0].properties, before.nodes[0].properties);
    assert.deepEqual(legacyPreview.links, before.links);
    assert.equal(migrateLegacyPreviewNodes(legacyPreview), 0);
`));

eval(executableSource("studio_generation_core.js", `
    const dimensionNode = {
        widgets: [
            { name: "custom_width", value: 1440, callback() {} },
            { name: "custom_height", value: 1920, callback() {} },
        ],
        setDirtyCanvas() {},
    };
    swapCustomDimensions(dimensionNode);
    assert.equal(widget(dimensionNode, "custom_width").value, 1920);
    assert.equal(widget(dimensionNode, "custom_height").value, 1440);
`));

eval(executableSource("studio_preview_core.js", `
    const compareNode = { properties: {}, size: [700, 620], setDirtyCanvas() {} };
    rememberPreviewPaneWidth(compareNode, 700);
    assert.equal(syncCompareLayout(compareNode), false);
    assert.equal(compareNode.size[0], 700);
    compareNode.properties.so_fit_preview_compare = true;
    compareNode.properties[PINNED_IMAGES_PROPERTY] = [{ filename: "pin.png", type: "temp", subfolder: "" }];
    assert.equal(syncCompareLayout(compareNode), true);
    assert.equal(compareNode.size[0], 1410);
    assert.equal(previewPaneWidth(compareNode), 700);
    compareNode.properties[PINNED_IMAGES_PROPERTY] = [];
    assert.equal(syncCompareLayout(compareNode), false);
    assert.equal(compareNode.size[0], 700);
    compareNode.properties.so_fit_preview_compare = true;
    compareNode.properties[PINNED_IMAGES_PROPERTY] = [{ filename: "pin.png", type: "temp", subfolder: "" }];
    clearPinnedPreviews(compareNode);
    assert.equal(compareNode.properties.so_fit_preview_compare, false);
    assert.deepEqual(compareNode.properties[PINNED_IMAGES_PROPERTY], []);
    assert.equal(compareNode.size[0], 700);
`));

const generationSource = fs.readFileSync(path.join(root, "js", "studio_generation_core.js"), "utf8");
assert.match(generationSource, /so_last_width/);
assert.match(generationSource, /so_last_height/);

const themeSource = fs.readFileSync(path.join(root, "js", "studio_theme.js"), "utf8");
for (const core of ["Loader", "Prompt", "Generation", "Output"]) {
    assert.match(themeSource, new RegExp(`HeaderBranding${core}Core_v2_1_1\\.png`));
}

const loaderSource = fs.readFileSync(path.join(root, "js", "studio_loader_core.js"), "utf8");
const promptTriggerSource = fs.readFileSync(path.join(root, "js", "studio_prompt_core.js"), "utf8");
assert.match(loaderSource, /function publishLoaderLiveOutputs\(node\)/);
assert.match(loaderSource, /function mainLoraTriggerActive\(node\)/);
assert.match(loaderSource, /if \(!mainLoraTriggerActive\(node\)\)/);
assert.match(loaderSource, /main_trigger:\s*mainLoraTriggerActive\(node\) \? String\(node\.__soMainTrigger/);
assert.match(loaderSource, /\["main_enabled", "main_strength"\]/);
assert.match(promptTriggerSource, /if \(!enabled \|\| !selected \|\| \(Number\.isFinite\(strength\) && strength === 0\)\) return "";/);
assert.match(loaderSource, /clean_name:\s*dashboardCleanName\(node\)/);
assert.match(loaderSource, /refreshCleanNameChoices\(node\)[\s\S]*?publishLoaderLiveOutputs\(node\)/);
assert.match(loaderSource, /\[★ Favorites\]/);
assert.match(loaderSource, /\[✓ Tested\]/);
assert.match(loaderSource, /\[◌ Untested \/ Retest\]/);
assert.match(loaderSource, /library_filter/);
assert.match(loaderSource, /LoaderCore_LIB_button\.png/);
assert.match(loaderSource, /sickollie:open-lora-library/);
assert.match(loaderSource, /openLoRALibraryFromLoader\(node\)/);
assert.match(loaderSource, /lora_sort/);
assert.match(loaderSource, /Most used/);
assert.match(loaderSource, /review-lora/);
assert.match(loaderSource, /loraUseCount\(node, value\) > 0 \? reviewTone\("tested"\)/);
assert.match(loaderSource, /function openSecondaryLoraBrowser\(node, targetSecondary = null\)/);
assert.match(loaderSource, /Filter folders or LoRAs/);
assert.match(loaderSource, /ADD SECONDARY LoRA/);
assert.match(loaderSource, /function drawSecondaryDashboardSection\(ctx, node, x, startY, w\)/);
assert.match(loaderSource, /const SECONDARY_ROW_H = 40/);
assert.match(loaderSource, /secondary_lora_stack/);
assert.doesNotMatch(loaderSource, /drawSecondarySectionSegment/);
assert.match(loaderSource, /dashText\(ctx, "Strength"/);
assert.match(loaderSource, /copyTrigger/);
assert.match(loaderSource, /fetchMainTriggerFromServer\(loraName\)/);
assert.match(loaderSource, /CUSTOM LoRA TRIGGER/);
assert.match(loaderSource, /SAVE THIS LoRA/);
assert.match(loaderSource, /SAVE EPOCH FAMILY/);
assert.match(loaderSource, /trigger-override/);
assert.match(loaderSource, /Trigger · Custom/);
assert.match(loaderSource, /__soMainTriggerRequestId/);
assert.match(loaderSource, /previous LoRA lookup must never overwrite a newer selection/);
assert.match(promptTriggerSource, /followLoader\.textContent = "Follow Loader Core"/);
assert.match(promptTriggerSource, /SAVED OVERRIDE FOR THIS LORA/);
assert.match(promptTriggerSource, /Save LoRA override/);
assert.match(promptTriggerSource, /Clear override/);
assert.match(promptTriggerSource, /✓ Following Loader Core · ON/);
assert.match(promptTriggerSource, /repairPromptTriggerConnection\(node\)/);
assert.match(promptTriggerSource, /followLoader\.onclick = async \(\) =>/);
assert.doesNotMatch(promptTriggerSource, /followLoader\.onclick[\s\S]{0,500}clearLoaderTriggerOverride/);
assert.match(loaderSource, /secondary-edit-/);
assert.match(loaderSource, /rgba\(246,230,90,\.72\)/);
assert.doesNotMatch(loaderSource, /Folder output:/);
assert.doesNotMatch(loaderSource, /showLoraChooser/);
assert.doesNotMatch(loaderSource, /RgthreeBaseWidget/);
assert.doesNotMatch(loaderSource, /RgthreeDividerWidget/);
assert.doesNotMatch(loaderSource, /drawTogglePart/);
assert.match(loaderSource, /function ensureSecondaryBackingWidget\(node\)/);
assert.match(loaderSource, /widget\(node, "secondary_lora_stack"\)/);
assert.match(loaderSource, /backing\.serializeValue = \(\) =>/);
assert.match(loaderSource, /JSON\.stringify\(secondaryStackValues\(node\)\)/);
assert.doesNotMatch(loaderSource, /class SecondaryStackBackingWidget/);
assert.match(loaderSource, /drawSecondaryDashboardSection\(ctx, node, x, y, w\)/);

const promptSource = fs.readFileSync(path.join(root, "js", "studio_prompt_core.js"), "utf8");
assert.match(promptSource, /function refreshAvailableLogFiles\(node, base\)/);
assert.match(promptSource, /\/sickollie\/studio\/prompt-core\/log-files/);
assert.match(promptSource, /await refreshAvailableLogFiles\(node, base\)/);

const recipeSource = fs.readFileSync(path.join(root, "js", "solo_recipe_catalog.js"), "utf8");
assert.match(recipeSource, /SOGenerationPipelineStudio/);
assert.match(recipeSource, /SOOutputBuilderSaveStudio/);
assert.match(recipeSource, /Apply Recipe/);
assert.match(recipeSource, /PORTABLE BY DESIGN/);
assert.match(recipeSource, /RECIPE_PROMPT_APPLY_FIELDS/);
const recipePromptApplyFields = recipeSource.match(/const RECIPE_PROMPT_APPLY_FIELDS = new Set\(\[([^\]]*)\]\)/)?.[1] || "";
for (const forbidden of ["name_value", "item_value", "prompt_log_file", "prompt_index", "outfit_log_file", "scene_log_file", "prompt_source"]) assert.doesNotMatch(recipePromptApplyFields, new RegExp(forbidden));
assert.match(recipeSource, /prompt_source/);
assert.match(recipeSource, /Resolved seed/);
assert.match(recipeSource, /optional_nodes/);
assert.match(recipeSource, /OPTIONAL ENVIRONMENT/);
assert.match(recipeSource, /prompt_mode:\s*"fixed"/);
assert.doesNotMatch(recipeSource, /Empty LoRA slot"\s*\}\);/);
assert.match(recipeSource, /function askRecipeName\(/);
assert.match(recipeSource, /save-with-preview/);
assert.match(recipeSource, /currentStudioPreviewData/);
assert.match(recipeSource, /function lastExecutedPromptValues\(/);
assert.match(recipeSource, /__soLastAssembly/);
assert.doesNotMatch(recipeSource, /window\.prompt\(/);

const previewSource = fs.readFileSync(path.join(root, "js", "studio_preview_core.js"), "utf8");
assert.match(recipeSource, /async function bulkImportRecipeImages\(files, onProgress = null\)/);
assert.match(recipeSource, /function showImportedRecipesCollectionEditor\(recipeIds\)/);
assert.match(recipeSource, /ORGANIZE \${ids\.length} IMPORTED PROMPT/);
assert.match(recipeSource, /Add all \${ids\.length} to collections/);
assert.match(recipeSource, /multiple && result\.saved\.length && collections\.length/);
assert.match(recipeSource, /result\.saved\.map\(item => item\.recipe_id\)/);
assert.match(recipeSource, /picker\.multiple = multiple/);
assert.match(recipeSource, /Bulk import images/);
assert.match(recipeSource, /Importing \$\{index\}\/\$\{total\}/);
assert.match(recipeSource, /skipped \$\{result\.skipped\.length\}/);
assert.match(recipeSource, /showCollectionManager/);
assert.match(recipeSource, /showRecipeCollectionEditor/);
assert.match(recipeSource, /\/collections/);
assert.match(recipeSource, /Unfiled/);
assert.match(recipeSource, /document\.createElement\("div"\); Object\.assign\(card\.style/);
assert.match(recipeSource, /grid-auto-rows", "max-content", "important"/);
assert.match(recipeSource, /preview\.onclick = \(\) => selectionMode \? toggleRecipeSelection/);
assert.match(recipeSource, /let selectionMode = false/);
assert.match(recipeSource, /selectedRecipeIds = new Set/);
assert.match(recipeSource, /ADD TO COLLECTIONS/);
assert.match(recipeSource, /SELECT VISIBLE/);
assert.match(recipeSource, /\/recipes\/bulk\/collections/);
assert.match(recipeSource, /\/recipes\/bulk\/delete/);
assert.match(recipeSource, /CREATIVE LIBRARY/);
assert.match(recipeSource, /data-library-tab/);
assert.match(recipeSource, /PROMPTS/);
assert.match(recipeSource, /OUTFITS/);
assert.match(recipeSource, /SCENES/);
assert.match(recipeSource, /\/derived-values/);
assert.match(recipeSource, /LOAD OUTFIT A/);
assert.match(recipeSource, /LOAD SCENE/);
assert.match(recipeSource, /prompt-core\/log-files\?category=/);
assert.match(recipeSource, /GENERATE PREVIEWS/);
assert.match(recipeSource, /Build asset/);
assert.match(recipeSource, /Import outfit logs/);
assert.match(recipeSource, /\/component-assets\/import/);
assert.match(recipeSource, /\/component-collections/);
assert.match(recipeSource, /function showComponentCollectionManager/);
assert.match(recipeSource, /function showComponentCollectionEditor/);
assert.match(recipeSource, /COLLECTIONS/);
assert.match(recipeSource, /SCENE HOMES/);
assert.match(recipeSource, /CATEGORY → SUBCATEGORY/);
assert.match(recipeSource, /DELETE EVERYWHERE/);
assert.match(recipeSource, /REMOVE FROM THIS HOME/);
assert.match(recipeSource, /function renderSceneLibrary/);
assert.match(recipeSource, /COMPONENT_PAGE_SIZE = 96/);
assert.match(recipeSource, /SELECT CURRENT VIEW/);
assert.match(recipeSource, /REMOVE FROM COLLECTION/);
assert.match(recipeSource, /CLEAN UP/);
assert.match(recipeSource, /IMPORT HISTORY/);
assert.match(recipeSource, /derived-values\/bulk\/collections/);
assert.match(recipeSource, /derived-values\/bulk\/delete/);
assert.match(recipeSource, /import-batches/);
assert.match(recipeSource, /MARK EXTRAS/);
assert.match(recipeSource, /STAGE MARKED/);
assert.match(recipeSource, /PROMPT-LIKE/);
assert.match(recipeSource, /whole image prompt rather than only/);
assert.match(recipeSource, /componentRatingFilter/);
assert.match(recipeSource, /Highest rated/);
assert.match(recipeSource, /derived-values\/\$\{encodeURIComponent\(componentId\)\}\/rating/);
assert.match(recipeSource, /function renderPromptAssets/);
assert.doesNotMatch(recipeSource, /isLastImportNode/);
assert.match(recipeSource, /function showPromptApply/);
assert.match(recipeSource, /VISUAL ASSEMBLY LAB/);
assert.match(recipeSource, /Prompt Builder/);
assert.match(recipeSource, /function renderBuilderPanel/);
assert.match(recipeSource, /function applyBuilderToStudio/);
assert.match(recipeSource, /function saveBuilderBoard/);
assert.match(recipeSource, /function renderFragmentLibrary/);
assert.match(recipeSource, /function showBuilderFragmentPicker/);
assert.match(recipeSource, /function openPromptInBuilder/);
assert.match(recipeSource, /function builderTemplateText/);
assert.match(recipeSource, /COMPOSITION TRAY/);
assert.match(recipeSource, /PROMPT PARTS · ADD-TO-BUILDER CATALOG/);
assert.match(recipeSource, /Ingredient Catalog/);
assert.match(recipeSource, /fragments\/decompose/);
assert.match(recipeSource, /request\("\/fragments\/bulk"/);
assert.match(recipeSource, /SELECT ALL MATCHES/);
assert.match(recipeSource, /APPLY CATEGORY/);
assert.match(recipeSource, /RESTORE AUTO TYPE/);
assert.match(recipeSource, /REBUILD FROM SOURCES/);
assert.match(recipeSource, /EXPORT \.TXT/);
assert.match(recipeSource, /request\("\/boards"/);
assert.match(recipeSource, /SEND TO STUDIO/);
assert.match(recipeSource, /CORPUS BLUEPRINTS/);
assert.match(recipeSource, /PROMPT GALLERIES/);
assert.match(recipeSource, /Shop the archive by idea/);
assert.match(recipeSource, /FULL VAULT/);
assert.match(recipeSource, /PROMPT_GALLERY_FAMILIES/);
for (const category of ["UV Night", "Vintage Magazine", "Nude \/ Bare", "Golden Hour", "Point-and-Shoot"]) assert.match(recipeSource, new RegExp(category.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
assert.match(recipeSource, /PROMPT_PAGE_SIZE = 72/);
assert.match(recipeSource, /request\("\/recipes\?sync=0"\)/);
assert.match(recipeSource, /function promptPageParams\(\)/);
assert.match(recipeSource, /promptSort = "preview_newest"/);
assert.match(recipeSource, /async function loadPromptPage/);
assert.match(recipeSource, /new URLSearchParams\(\)/);
assert.match(recipeSource, /promptAssetTotal/);
assert.match(recipeSource, /promptFacetFilters/);
assert.match(recipeSource, /function pagedPromptAssets/);
assert.match(recipeSource, /LIBRARY MENU/);
assert.match(recipeSource, /Catalog run/);
assert.match(recipeSource, /LOCATION \/ SCOPE/);
assert.match(recipeSource, /Fill missing Catalog previews/);
assert.match(recipeSource, /Replace existing Catalog previews/);
assert.match(recipeSource, /Rebuild every preview in scope/);
assert.match(recipeSource, /Selected assets/);
assert.match(recipeSource, /Shuffle run order/);
assert.match(recipeSource, /derived-values\/preview/);
assert.match(recipeSource, /Boolean\(itemPromptId\)/);
assert.match(recipeSource, /itemComponentId && String\(asset\.component_id \|\| ""\) === itemComponentId/);
assert.doesNotMatch(recipeSource, /String\(asset\.prompt_id \|\| ""\) === String\(item\.prompt_id \|\| ""\) \|\|/);
assert.match(recipeSource, /function creativeLibraryPreviewUrl/);
assert.match(recipeSource, /creative-library-pack/);
assert.doesNotMatch(recipeSource, /image\.src = componentBackedPreview/);
assert.match(recipeSource, /DEFAULT_CATALOG_OUTFIT_PROMPT/);
assert.match(recipeSource, /DEFAULT_CATALOG_SCENE_PROMPT/);
assert.match(recipeSource, /Clean ecommerce catalog flat-lay photograph of OUTFIT, centered on a flat color solid dark #000000 black background, crisp detail\./);
assert.match(recipeSource, /Clean reference photograph of SCENE, crisp detail\./);
assert.match(recipeSource, /catalogPreviewDimensions\(run, item\)/);
assert.match(recipeSource, /width: Math\.max\(width, height\), height: Math\.min\(width, height\)/);
assert.match(recipeSource, /BROWSE LOCATION/);
assert.match(recipeSource, /Choose the main collection \/ location filter/);
assert.match(recipeSource, /window\.__soCreativeLibraryRunActive = true/);
assert.match(recipeSource, /preview_newest/);
assert.match(recipeSource, /Newest preview/);
assert.match(recipeSource, /WARDROBE_TAXONOMY/);
assert.match(recipeSource, /LOOKS/);
assert.match(recipeSource, /WARDROBE/);
assert.match(recipeSource, /YOUR OUTFIT/);
assert.match(recipeSource, /WARDROBE_MATERIALS/);
assert.match(recipeSource, /WARDROBE_GRAPHICS/);
assert.match(recipeSource, /GRAPHIC \/ TEXT/);
assert.match(recipeSource, /data-wardrobe-builder-output/);
assert.doesNotMatch(recipeSource, /mode === "builder" \? "BUILDER"/);
assert.match(recipeSource, /function renderWardrobePieces/);
assert.match(recipeSource, /SAVE AS LOOK/);
assert.match(recipeSource, /QUICK FINISHERS/);
assert.match(recipeSource, /wardrobe-items/);
assert.match(recipeSource, /copyComponentValue/);
assert.match(recipeSource, /Copy outfit value/);
assert.match(recipeSource, /Copy scene value/);
assert.match(recipeSource, /repeat\(auto-fill,minmax\(min\(220px,100%\),1fr\)\)/);
assert.match(recipeSource, /componentThumbnailFilter\[currentKind\] = ""/);
assert.match(recipeSource, /sickollie:preview-executed/);
assert.match(recipeSource, /applySecondaryStack\(loader, secondaryOriginals, false\)/);
assert.match(previewSource, /PREVIEW_CONTROLS_HEIGHT/);
assert.match(previewSource, /const PREVIEW_CONTROLS_HEIGHT = 40/);
assert.match(previewSource, /sickollie:save-studio-recipe/);
assert.match(previewSource, /📚 SAVE TO LIBRARY/);
assert.match(previewSource, /📌 PIN \+ COMPARE/);
assert.doesNotMatch(previewSource, /★ LIBRARY THUMB/);
assert.doesNotMatch(previewSource, /sickollie:set-lora-thumbnail/);
assert.match(previewSource, /BACKGROUND COLOR/);
assert.match(previewSource, /const x = 10, y = PREVIEW_CONTROLS_TOP, width = previewPaneWidth\(node\) - 20, gap = 6, groupGap = 16/);
assert.match(previewSource, /function previewActionFeedback\(/);
assert.match(previewSource, /navigator\?\.vibrate\?\.\(16\)/);
assert.match(previewSource, /sickollie:preview-executed/);
assert.match(previewSource, /function syncCompareLayout\(/);
assert.match(previewSource, /PINNED REFERENCE/);
assert.match(previewSource, /BASE_WIDTH_PROPERTY/);
assert.match(previewSource, /PREVIEW_UPDATED_PROPERTY/);
assert.match(previewSource, /previewData/);
assert.doesNotMatch(previewSource, /thumbW/);

const librarySource = fs.readFileSync(path.join(root, "js", "solo_library_review.js"), "utf8");
assert.match(librarySource, /Auto first image/);
assert.match(librarySource, /YEARBOOK THUMBNAIL RUN/);
assert.match(librarySource, /action\("Load LoRA"/);
assert.doesNotMatch(librarySource, /Load LoRA · keep strength/);
assert.match(librarySource, /Fill from Civitai/);
assert.match(librarySource, /Quarantine rejected/);
assert.match(librarySource, /request\("\/quarantine-rejected"/);
assert.match(librarySource, /function updateCachedThumbnail\(/);
assert.match(librarySource, /function refreshCatalogAfterYearbook\(/);
assert.match(librarySource, /if \(completed\) refreshCatalogAfterYearbook\(\)/);
assert.match(librarySource, /folderScope/);
assert.match(librarySource, /request\("\/lora-files"\)/);
assert.match(librarySource, /loaderFolderForLora/);
assert.match(librarySource, /window\.__soOpenLoRALibrary/);
assert.match(librarySource, /requestedFolderScope\(options\)/);
assert.match(librarySource, /setWidget\(loader, "folder_name", loaderFolderForLora\(canonical\)\)/);
assert.match(librarySource, /thumbnail_updated_at \|\| asset.updated_at/);
assert.match(librarySource, /thumbnail_newest/);
assert.match(librarySource, /Newest thumbnail/);
assert.match(librarySource, /thumbnailFilter = ""/);
assert.match(librarySource, /Open Civitai/);
assert.match(librarySource, /const styles = ensureStyle\(\)/);
assert.match(librarySource, /await Promise\.all\(\[styles, load\(\)\]\)/);
assert.match(librarySource, /requestAnimationFrame\(\(\) => requestAnimationFrame\(resolve\)\)/);
assert.match(librarySource, /let styleReady = null/);
assert.match(librarySource, /normalizedLoraPath/);
assert.match(librarySource, /YEARBOOK_PROMPT_KEY/);
assert.match(librarySource, /YEARBOOK_DEFAULT_STRENGTH = 1\.0/);
assert.match(librarySource, /YEARBOOK_DEFAULT_SEED = 4815162342/);
assert.match(librarySource, /400 × 500 · Fast/);
assert.match(librarySource, /1024 × 1280 · Large/);
assert.match(librarySource, /1440 × 1920 · Ollie/);
assert.match(librarySource, /Custom dimensions/);
assert.match(librarySource, /COMPARISON SETTINGS/);
assert.match(librarySource, /LoRA strength/);
assert.match(librarySource, /Fixed seed keeps every LoRA directly comparable/);
assert.match(librarySource, /Open Theater Mode · Live/);
assert.match(librarySource, /function openYearbookTheater\(/);
assert.match(librarySource, /function yearbookIncrementalOrder\(/);
assert.match(librarySource, /Incremental epoch\/checkpoint · low → high/);
assert.match(librarySource, /items: orderedYearbookItems\(items, orderMode\)/);
assert.match(librarySource, /function appendYearbookTheaterEntry\(/);
assert.match(librarySource, /data-yearbook-theater/);
assert.match(librarySource, /× REJECT/);
assert.match(librarySource, /★ FAVORITE/);
assert.match(librarySource, /✓ LIKE/);
assert.match(librarySource, /↻ RETEST/);
assert.match(librarySource, /theater\.dismissed = true/);
assert.match(librarySource, /!theater\.overlay && !theater\.dismissed/);
assert.match(librarySource, /function applyYearbookRunSettings\(/);
assert.match(librarySource, /setWidget\(run\.loader, "main_strength", run\.strength\)/);
assert.match(librarySource, /setWidget\(run\.generation, "custom_width", run\.width\)/);
assert.match(librarySource, /setWidget\(run\.generation, "custom_height", run\.height\)/);
assert.match(librarySource, /setWidget\(run\.generation, "seed_value", run\.seed\)/);
assert.match(librarySource, /Use \$\{browserFolder\} \+ nested folders/);
assert.match(librarySource, /GENERATION_TYPE/);
assert.match(librarySource, /Loading through Loader Core/);
assert.match(librarySource, /so-lib-usage-pill/);
assert.match(librarySource, /function queueLoraAsset\(/);
assert.match(librarySource, /QUEUE CURRENT VIEW/);
assert.match(librarySource, /Shuffle queue order/);
assert.match(librarySource, /function renderSidebar\(/);
assert.match(librarySource, /\/lora-collections/);
assert.match(librarySource, /Scan current folder/);
assert.match(librarySource, /captured: 0, skipped: 0/);
assert.match(librarySource, /function hasRenderableThumbnail\(/);
assert.match(librarySource, /CIVITAI READY/);
assert.match(librarySource, /function scheduleYearbook\(/);
assert.match(librarySource, /api\?\.interrupt/);
assert.match(librarySource, /recoverTextInputFocus\(\)/);
assert.match(librarySource, /function overlayPendingReviewState\(/);
assert.match(librarySource, /reviewMutations\.set\(asset\.asset_id/);
assert.match(librarySource, /mutation\?\.serial === serial\) \{[\s\S]*?mutation\.pending = false/);
assert.match(librarySource, /reviewMutations\.delete\(asset\.asset_id\)/);
assert.doesNotMatch(librarySource, /setFeedback\(`\$\{asset\.model_name\}: \$\{state === "none" \? "rating cleared" : state\}`\);\s*await load\(\);/);
assert.match(librarySource, /executionObserved/);
assert.match(librarySource, /api\.addEventListener\("execution_start"/);
assert.match(librarySource, /if \(yearbook\) \{ stopYearbook\(false\); return; \}/);
assert.match(librarySource, /window\.__soYearbookRunActive = true/);
assert.match(librarySource, /window\.__soCreativeLibraryRunActive/);
assert.doesNotMatch(librarySource, /Stop the active yearbook run\?/);
assert.doesNotMatch(librarySource, /queueUi\?\.update/);
assert.match(librarySource, /Replace Civitai thumbnails/);
assert.match(librarySource, /Replace generated non-Yearbook thumbnails/);
assert.match(librarySource, /Standardize non-Yearbook thumbnails/);
assert.match(librarySource, /Rebuild existing Yearbook thumbnails/);
assert.match(librarySource, /Catalog tools/);
assert.match(librarySource, /request\("\/maintenance"/);
assert.match(librarySource, /Purge \+ rebuild/);
assert.match(librarySource, /captureNodeValues\(loader, \["main_enabled", "main_lora", "main_strength", "control_after_generate"\]\)/);
assert.doesNotMatch(librarySource, /setWidget\([^\n]*"include_subfolders"/);
assert.doesNotMatch(librarySource, /mainWidget\?\.options\?\.values/);
assert.doesNotMatch(librarySource, /Filter name or path/);

const libraryCss = fs.readFileSync(path.join(root, "js", "solo_library_review.css"), "utf8");
assert.match(libraryCss, /grid-template-rows:\s*auto auto minmax\(0,1fr\)/);
assert.match(libraryCss, /flex:\s*0 0 auto !important; aspect-ratio:\s*3 \/ 4/);
assert.match(libraryCss, /grid-auto-rows:\s*max-content !important/);
assert.match(libraryCss, /flex:\s*0 0 124px !important/);
assert.match(libraryCss, /so-lib-sidebar/);
assert.match(libraryCss, /so-lib-yearbook-progress\[hidden\][^}]*display:\s*none\s*!important/);
assert.match(libraryCss, /so-lib-yearbook-settings/);
assert.match(libraryCss, /so-lib-number-input/);
assert.match(libraryCss, /so-lib-seed-input/);
assert.doesNotMatch(libraryCss, /backdrop-filter:/);

const organizerSource = fs.readFileSync(path.join(root, "js", "solo_lora_organizer.js"), "utf8");
assert.match(organizerSource, /solo-overlay solo-lora-overlay/);
const organizerCss = fs.readFileSync(path.join(root, "js", "solo_lora_organizer.css"), "utf8");
assert.match(organizerCss, /\.solo-lora-overlay \.solo-progress-track/);
assert.match(organizerCss, /max-height:\s*12px/);

const legacyLogSource = fs.readFileSync(path.join(root, "js", "solo_log_organizer.js"), "utf8");
const hubSource = fs.readFileSync(path.join(root, "js", "solo_hub.js"), "utf8");
assert.doesNotMatch(legacyLogSource, /SickOllieRegisterSoloHubItem/);
assert.doesNotMatch(legacyLogSource, /menuCommands:\s*\[/);
assert.match(legacyLogSource, /nodeData\.name !== "SOLO_Log_Organizer"/);
assert.doesNotMatch(hubSource, /"log-organizer"\s*:/);

console.log("Studio frontend behavior tests passed");

const promptDashboardSource = fs.readFileSync(path.join(root, "js", "studio_prompt_core.js"), "utf8");
const loaderDashboardSource = fs.readFileSync(path.join(root, "js", "studio_loader_core.js"), "utf8");
const generationDashboardSource = fs.readFileSync(path.join(root, "js", "studio_generation_core.js"), "utf8");
const outputDashboardSource = fs.readFileSync(path.join(root, "js", "studio_output_core.js"), "utf8");
assert.match(promptDashboardSource, /setup\(\) \{\s*ensurePromptBrowserPointerTracker\(\);/);
assert.match(loaderDashboardSource, /setup\(\) \{\s*ensurePointerTracker\(\);/);
assert.match(generationDashboardSource, /setup\(\) \{\s*ensurePointerTracker\(\);/);
assert.match(outputDashboardSource, /setup\(\) \{\s*ensurePointerTracker\(\);/);
