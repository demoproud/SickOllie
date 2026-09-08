import { app } from "../../../scripts/app.js";
import {
    STUDIO_LAYOUT,
    STUDIO_THEME,
    applyStudioNodeColors,
    drawStudioChrome,
    drawStudioSectionFrame,
} from "./studio_theme.js";

const TARGET = "SOPromptLogEngineStudio";
const SCHEMA_VERSION = 16;
const NO_FILE = "[None]";
const OUTFIT_COLLECTION_SCOPE_PREFIX = "[Outfit Looks Collection:";
const WARDROBE_COLLECTION_SCOPE_PREFIX = "[Wardrobe Collection:";
const SCENE_COLLECTION_SCOPE_PREFIX = "[Scene Collection:";
const LARGE_RANDOM_MAX = 1000000000;
const MODES = ["fixed", "increment", "decrement", "randomize", "shuffle"];
const PLACEMENTS = ["smart", "token", "append", "prepend", "off"];
const MAIN_PROMPT_SOURCES = ["manual", "input", "log"];

const DEFAULT_CLEANUP = String.raw`\?\[|\]
\\?[()]
:\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)`;

const DEFAULTS = {
    prompt_source: "manual",
    manual_prompt: "",
    prompt_log_file: NO_FILE,
    prompt_mode: "increment",
    prompt_index: 0,
    outfit_token_A: "OUTFIT_A",
    outfit_placement_A: "smart",
    outfit_log_file_A: NO_FILE,
    outfit_mode_A: "randomize",
    outfit_index_A: 0,
    outfit_token_B: "OUTFIT_B",
    outfit_placement_B: "smart",
    outfit_log_file_B: NO_FILE,
    outfit_mode_B: "randomize",
    outfit_index_B: 0,
    outfit_token_C: "OUTFIT_C",
    outfit_placement_C: "smart",
    outfit_log_file_C: NO_FILE,
    outfit_mode_C: "randomize",
    outfit_index_C: 0,
    scene_token: "SCENE",
    scene_placement: "smart",
    scene_log_file: NO_FILE,
    scene_mode: "randomize",
    scene_index: 0,
    name_token: "NAME",
    name_value: "",
    item_token: "ITEM",
    item_value: "",
    prefix_enabled: false,
    prefix_text: "",
    suffix_enabled: false,
    suffix_text: "",
    prefix_suffix_separator: ", ",
    cleanup_enabled: true,
    cleanup_rules: DEFAULT_CLEANUP,
    saved_prompt: "",
    trigger_token: "TRIGGER",
    trigger_placement: "off",
    trigger_override: "",
    outfit_source_A: "log",
    outfit_manual_A: "",
    outfit_source_B: "log",
    outfit_manual_B: "",
    outfit_source_C: "log",
    outfit_manual_C: "",
    scene_source: "log",
    scene_manual: "",
};

const CANONICAL_NAMES = Object.keys(DEFAULTS);

function canonicalCreativeLibraryLogReference(value, category = "") {
    const clean = String(value ?? "").trim().replaceAll("\\", "/");
    if (!clean || clean === NO_FILE) return clean;
    const parts = clean.split("/");
    const inferred = { prompts: "prompt", outfits: "outfit", scenes: "scene" }[String(parts[0] || "").toLowerCase()] || "";
    const kind = String(category || inferred).toLowerCase();
    if (parts.length < 2 || String(parts[1]).toLowerCase() !== "recipe library") return clean;
    parts[1] = "Creative Library";
    if (kind === "prompt" && String(parts[2] || "").toLowerCase() === "master - all recipe prompts.txt") parts[2] = "MASTER - Saved Recipe Prompts.txt";
    else if (kind === "prompt" && String(parts[2] || "").toLowerCase() === "collections") parts[2] = "Saved Recipe Collections";
    else if (kind === "outfit" && String(parts[2] || "").toLowerCase() === "master - resolved recipe outfits.txt") parts[2] = "MASTER - Outfit Looks.txt";
    else if (kind === "scene" && String(parts[2] || "").toLowerCase() === "master - resolved recipe scenes.txt") parts[2] = "MASTER - Scenes.txt";
    return parts.join("/");
}

function canonicalizeLogWidgetValues(values) {
    const output = [...values];
    for (const [name, category] of [
        ["prompt_log_file", "prompt"], ["outfit_log_file_A", "outfit"], ["outfit_log_file_B", "outfit"],
        ["outfit_log_file_C", "outfit"], ["scene_log_file", "scene"],
    ]) {
        const index = CANONICAL_NAMES.indexOf(name);
        if (index >= 0) output[index] = canonicalCreativeLibraryLogReference(output[index], category);
    }
    return output;
}
const COMPONENT_SOURCE_NAMES = [
    "outfit_source_A", "outfit_manual_A",
    "outfit_source_B", "outfit_manual_B",
    "outfit_source_C", "outfit_manual_C",
    "scene_source", "scene_manual",
];
const V13_NAMES = CANONICAL_NAMES.filter((name) => !COMPONENT_SOURCE_NAMES.includes(name));
const LEGACY_V10_NAMES = V13_NAMES.filter((name) => !name.includes("_placement") && !name.startsWith("trigger_"));
const V11_NAMES = V13_NAMES.filter((name) => !name.startsWith("trigger_"));
const LEGACY_PLACEMENTS = {
    outfit_placement_A: "token",
    outfit_placement_B: "token",
    outfit_placement_C: "token",
    scene_placement: "token",
};

const COPY_BUTTONS = [
    ["outfit_A", "outfit_token_A", "OUTFIT_A"],
    ["outfit_B", "outfit_token_B", "OUTFIT_B"],
    ["outfit_C", "outfit_token_C", "OUTFIT_C"],
    ["scene", "scene_token", "SCENE"],
    ["name", "name_token", "NAME"],
    ["item", "item_token", "ITEM"],
];

const PLACEMENT_LABELS = {
    smart: "Auto · placeholder or end",
    token: "Placeholder only",
    append: "End of prompt",
    prepend: "Beginning of prompt",
    off: "Off",
};
const PLACEMENT_SHORT_LABELS = {
    smart: "Auto",
    token: "Placeholder",
    append: "End",
    prepend: "Beginning",
    off: "Off",
};

const TEXT_HEIGHTS = {
    manual_prompt: 520,
    prefix_text: 60,
    suffix_text: 60,
    cleanup_rules: 64,
    saved_prompt: 140,
};

function widget(node, name) {
    return node?.widgets?.find((item) => item.name === name);
}

function readValues(comboWidget) {
    const source = comboWidget?.options?.values;
    if (Array.isArray(source)) return [...source];
    if (typeof source === "function") {
        try {
            const result = source();
            return Array.isArray(result) ? [...result] : [];
        } catch (error) {}
    }
    return [];
}

function writeValues(comboWidget, values) {
    if (!comboWidget) return;
    comboWidget.options = comboWidget.options || {};
    comboWidget.options.values = [...values];
}

function isMode(value) {
    return MODES.includes(String(value));
}

function canonicalValues(overrides = {}) {
    return CANONICAL_NAMES.map((name) =>
        Object.prototype.hasOwnProperty.call(overrides, name)
            ? overrides[name]
            : DEFAULTS[name],
    );
}

function legacyCanonicalValues(overrides = {}) {
    return canonicalValues({ ...LEGACY_PLACEMENTS, ...overrides });
}

function workflowInputConnected(info, name) {
    const input = (info?.inputs || []).find((slot) => String(slot?.widget?.name ?? slot?.name ?? "") === String(name));
    return Boolean(input && (input.link != null || (Array.isArray(input.links) && input.links.length)));
}

function upgradeDedicatedPromptInputSource(info, widgetsValues) {
    const output = [...widgetsValues];
    const sourceIndex = CANONICAL_NAMES.indexOf("prompt_source");
    const previousSchema = Number(info?.properties?.so_prompt_core_schema_version || 0);
    // Before schema 16, a connected Prompt input forcibly masqueraded as Manual.
    // Preserve that old behavior exactly once by migrating connected workflows
    // to the new dedicated Input source. After that, Manual stays truly manual.
    if (previousSchema < 16 && sourceIndex >= 0 && String(output[sourceIndex] ?? "manual") === "manual" && workflowInputConnected(info, "manual_prompt_input")) {
        output[sourceIndex] = "input";
    }
    return output;
}

function withSchema(info, widgetsValues) {
    return {
        ...info,
        properties: {
            ...(info?.properties || {}),
            so_prompt_core_schema_version: SCHEMA_VERSION,
        },
        widgets_values: canonicalizeLogWidgetValues(upgradeDedicatedPromptInputSource(info, widgetsValues)),
    };
}

function migrateLegacy30(info, values) {
    const sharedAffixEnabled = Boolean(values[22]);
    return withSchema(info, legacyCanonicalValues({
        prompt_source: values[0],
        manual_prompt: values[1],
        prompt_log_file: values[2],
        prompt_mode: values[3],
        prompt_index: values[4],
        outfit_token_A: values[8] || "OUTFIT_A",
        outfit_log_file_A: values[7] || NO_FILE,
        outfit_mode_A: values[9] || "randomize",
        outfit_index_A: values[10] ?? 0,
        scene_token: values[14] || "SCENE",
        scene_log_file: values[13] || NO_FILE,
        scene_mode: values[15] || "randomize",
        scene_index: values[16] ?? 0,
        name_token: values[18] || "NAME",
        name_value: values[19] ?? "",
        item_token: values[20] || "ITEM",
        item_value: values[21] ?? "",
        prefix_enabled: sharedAffixEnabled,
        prefix_text: values[23] ?? "",
        suffix_enabled: sharedAffixEnabled,
        suffix_text: values[24] ?? "",
        prefix_suffix_separator: values[25] ?? ", ",
        cleanup_enabled: values[27] ?? true,
        cleanup_rules: values[28] ?? DEFAULT_CLEANUP,
        saved_prompt: values[29] ?? info?.properties?.so_saved_final_prompt ?? "",
    }));
}

function migrateDev9DisplayOrder(info, values) {
    const sharedAffixEnabled = Boolean(values[25]);
    return withSchema(info, legacyCanonicalValues({
        prompt_source: values[0],
        manual_prompt: values[1],
        prompt_log_file: values[2],
        prompt_mode: values[3],
        prompt_index: values[4],
        outfit_token_A: values[5] || "OUTFIT_A",
        outfit_log_file_A: values[6] || NO_FILE,
        outfit_mode_A: values[7] || "randomize",
        outfit_index_A: values[8] ?? 0,
        outfit_token_B: values[9] || "OUTFIT_B",
        outfit_log_file_B: values[10] || NO_FILE,
        outfit_mode_B: values[11] || "randomize",
        outfit_index_B: values[12] ?? 0,
        outfit_token_C: values[13] || "OUTFIT_C",
        outfit_log_file_C: values[14] || NO_FILE,
        outfit_mode_C: values[15] || "randomize",
        outfit_index_C: values[16] ?? 0,
        scene_token: values[17] || "SCENE",
        scene_log_file: values[18] || NO_FILE,
        scene_mode: values[19] || "randomize",
        scene_index: values[20] ?? 0,
        name_token: values[21] || "NAME",
        name_value: values[22] ?? "",
        item_token: values[23] || "ITEM",
        item_value: values[24] ?? "",
        prefix_enabled: sharedAffixEnabled,
        prefix_text: values[26] ?? "",
        suffix_enabled: sharedAffixEnabled,
        suffix_text: values[27] ?? "",
        prefix_suffix_separator: values[28] ?? ", ",
        cleanup_enabled: values[29] ?? true,
        cleanup_rules: values[30] ?? DEFAULT_CLEANUP,
        saved_prompt: values[31] ?? info?.properties?.so_saved_final_prompt ?? "",
    }));
}

function migrateDev9BackendOrder(info, values) {
    const sharedAffixEnabled = Boolean(values[22]);
    return withSchema(info, legacyCanonicalValues({
        prompt_source: values[0],
        manual_prompt: values[1],
        prompt_log_file: values[2],
        prompt_mode: values[3],
        prompt_index: values[4],
        outfit_token_A: values[8] || "OUTFIT_A",
        outfit_log_file_A: values[7] || NO_FILE,
        outfit_mode_A: values[9] || "randomize",
        outfit_index_A: values[10] ?? 0,
        outfit_token_B: values[30] || "OUTFIT_B",
        outfit_log_file_B: values[31] || NO_FILE,
        outfit_mode_B: values[32] || "randomize",
        outfit_index_B: values[33] ?? 0,
        outfit_token_C: values[34] || "OUTFIT_C",
        outfit_log_file_C: values[35] || NO_FILE,
        outfit_mode_C: values[36] || "randomize",
        outfit_index_C: values[37] ?? 0,
        scene_token: values[14] || "SCENE",
        scene_log_file: values[13] || NO_FILE,
        scene_mode: values[15] || "randomize",
        scene_index: values[16] ?? 0,
        name_token: values[18] || "NAME",
        name_value: values[19] ?? "",
        item_token: values[20] || "ITEM",
        item_value: values[21] ?? "",
        prefix_enabled: sharedAffixEnabled,
        prefix_text: values[23] ?? "",
        suffix_enabled: sharedAffixEnabled,
        suffix_text: values[24] ?? "",
        prefix_suffix_separator: values[25] ?? ", ",
        cleanup_enabled: values[27] ?? true,
        cleanup_rules: values[28] ?? DEFAULT_CLEANUP,
        saved_prompt: values[29] ?? info?.properties?.so_saved_final_prompt ?? "",
    }));
}

function migrateDev9ButtonOrder(info, values) {
    const sharedAffixEnabled = Boolean(values[31]);
    return withSchema(info, legacyCanonicalValues({
        prompt_source: values[0],
        manual_prompt: values[1],
        prompt_log_file: values[2],
        prompt_mode: values[3],
        prompt_index: values[4],
        outfit_token_A: values[6] || "OUTFIT_A",
        outfit_log_file_A: values[7] || NO_FILE,
        outfit_mode_A: values[8] || "randomize",
        outfit_index_A: values[9] ?? 0,
        outfit_token_B: values[11] || "OUTFIT_B",
        outfit_log_file_B: values[12] || NO_FILE,
        outfit_mode_B: values[13] || "randomize",
        outfit_index_B: values[14] ?? 0,
        outfit_token_C: values[16] || "OUTFIT_C",
        outfit_log_file_C: values[17] || NO_FILE,
        outfit_mode_C: values[18] || "randomize",
        outfit_index_C: values[19] ?? 0,
        scene_token: values[21] || "SCENE",
        scene_log_file: values[22] || NO_FILE,
        scene_mode: values[23] || "randomize",
        scene_index: values[24] ?? 0,
        name_token: values[26] || "NAME",
        name_value: values[27] ?? "",
        item_token: values[29] || "ITEM",
        item_value: values[30] ?? "",
        prefix_enabled: sharedAffixEnabled,
        prefix_text: values[32] ?? "",
        suffix_enabled: sharedAffixEnabled,
        suffix_text: values[33] ?? "",
        prefix_suffix_separator: values[34] ?? ", ",
        cleanup_enabled: values[35] ?? true,
        cleanup_rules: values[36] ?? DEFAULT_CLEANUP,
        saved_prompt: values[37] ?? info?.properties?.so_saved_final_prompt ?? "",
    }));
}

function migratePromptWorkflow(info) {
    const values = info?.widgets_values;
    if (!Array.isArray(values)) return info;

    if (
        Number(info?.properties?.so_prompt_core_schema_version) >= SCHEMA_VERSION &&
        values.length === CANONICAL_NAMES.length
    ) {
        return info;
    }

    if (values.length === V13_NAMES.length) {
        const restored = {};
        V13_NAMES.forEach((name, index) => { restored[name] = values[index]; });
        return withSchema(info, canonicalValues(restored));
    }

    if (values.length === LEGACY_V10_NAMES.length) {
        const restored = {};
        LEGACY_V10_NAMES.forEach((name, index) => { restored[name] = values[index]; });
        return withSchema(info, legacyCanonicalValues(restored));
    }

    // v11 was the first Studio placement build. Later versions appended the
    // trigger controls and then the manual Outfit/Scene source controls, so
    // preserve every older value and fill only the new channels safely.
    if (values.length === V11_NAMES.length) {
        const restored = {};
        V11_NAMES.forEach((name, index) => { restored[name] = values[index]; });
        return withSchema(info, canonicalValues(restored));
    }

    if (values.length === 30) {
        return migrateLegacy30(info, values);
    }

    if (values.length === 44) {
        return migrateDev9ButtonOrder(info, values);
    }

    if (values.length === 38) {
        const looksDisplayOrder =
            typeof values[5] === "string" &&
            isMode(values[7]) &&
            isMode(values[11]) &&
            isMode(values[15]) &&
            isMode(values[19]);

        const looksBackendOrder =
            typeof values[5] === "boolean" &&
            isMode(values[9]) &&
            isMode(values[15]) &&
            isMode(values[32]) &&
            isMode(values[36]);

        if (looksDisplayOrder) return migrateDev9DisplayOrder(info, values);
        if (looksBackendOrder) return migrateDev9BackendOrder(info, values);

        console.warn(
            "[Sick Ollie Prompt Core] A dev9 workflow appears to have been saved " +
            "after its widgets shifted. Restoring safe defaults for the new channels.",
        );
        return withSchema(info, legacyCanonicalValues({
            prompt_source: values[0] ?? "manual",
            manual_prompt: values[1] ?? "",
            prompt_log_file: values[2] ?? NO_FILE,
            prompt_mode: isMode(values[3]) ? values[3] : "increment",
            prompt_index: Number.isFinite(Number(values[4])) ? Number(values[4]) : 0,
            saved_prompt: info?.properties?.so_saved_final_prompt ?? "",
        }));
    }

    if (values.length === CANONICAL_NAMES.length) {
        const upgraded = [...values];
        // v12's Trigger Builder could save an override while leaving placement
        // stuck at Off because the builder had no reachable placement control.
        // A non-empty override in that exact legacy state is therefore treated
        // as the user's attempted trigger selection and upgraded to Smart.
        if (Number(info?.properties?.so_prompt_core_schema_version || 0) <= 12) {
            const placementIndex = CANONICAL_NAMES.indexOf("trigger_placement");
            const overrideIndex = CANONICAL_NAMES.indexOf("trigger_override");
            if (String(upgraded[placementIndex] ?? "off") === "off" && String(upgraded[overrideIndex] ?? "").trim()) {
                upgraded[placementIndex] = "smart";
            }
        }
        return withSchema(info, upgraded);
    }

    return info;
}

function setWidgetHeight(widgetRef, contentHeight) {
    if (!widgetRef) return;
    const height = Number(contentHeight);
    widgetRef.computeSize = (width) => [width || 0, height + 18];
    widgetRef.options = { ...(widgetRef.options || {}), min_height: height };
    if (widgetRef.inputEl) {
        widgetRef.inputEl.style.minHeight = `${height}px`;
        widgetRef.inputEl.style.height = `${height}px`;
        widgetRef.inputEl.style.maxHeight = `${height}px`;
        widgetRef.inputEl.style.resize = "none";
    }
}

function setTextWidget(node, name, value) {
    const target = widget(node, name);
    if (!target || value == null) return;
    target.value = String(value);
    if (target.inputEl) target.inputEl.value = String(value);
    node.setDirtyCanvas?.(true, true);
}

function moveButtonBefore(node, button, targetName) {
    const buttonIndex = node.widgets?.indexOf(button) ?? -1;
    if (buttonIndex >= 0) node.widgets.splice(buttonIndex, 1);
    const targetIndex = node.widgets?.findIndex((item) => item.name === targetName) ?? -1;
    if (targetIndex >= 0) node.widgets.splice(targetIndex, 0, button);
    else node.widgets.push(button);
}

function createCopyButtons(node) {
    if (node.__soPromptCopyButtons) return;
    node.__soPromptCopyButtons = {};

    for (const [key, tokenName, fallback] of COPY_BUTTONS) {
        const button = node.addWidget(
            "button",
            `📋 Copy ${fallback}`,
            null,
            async () => {
                const value = String(widget(node, tokenName)?.value || fallback).trim() || fallback;
                try {
                    await navigator.clipboard.writeText(value);
                } catch (error) {}
            },
            { serialize: false },
        );
        button.serialize = false;
        button.options = { ...(button.options || {}), serialize: false };
        node.__soPromptCopyButtons[key] = button;
        moveButtonBefore(node, button, tokenName);
    }
}

function updateCopyButtons(node) {
    if (!node.__soPromptCopyButtons) return;
    for (const [key, tokenName, fallback] of COPY_BUTTONS) {
        const button = node.__soPromptCopyButtons[key];
        if (!button) continue;
        const value = String(widget(node, tokenName)?.value || fallback).trim() || fallback;
        button.name = `📋 Copy ${value}`;
    }
    node.setDirtyCanvas?.(true, true);
}

function bindTokenCallbacks(node) {
    for (const [, tokenName] of COPY_BUTTONS) {
        const target = widget(node, tokenName);
        if (!target || target.__soCopyBound) continue;
        target.__soCopyBound = true;
        const originalCallback = target.callback;
        target.callback = function (...args) {
            const result = originalCallback?.apply(this, args);
            updateCopyButtons(node);
            return result;
        };
        target.inputEl?.addEventListener("input", () => updateCopyButtons(node));
    }
}

const STREAM_BASES = ["prompt", "outfit_A", "outfit_B", "outfit_C", "scene"];

function streamCategory(base) {
    if (base === "prompt") return "prompt";
    if (base.startsWith("outfit_")) return "outfit";
    return "scene";
}

function streamTokenWidget(base) {
    if (base === "outfit_A") return "outfit_token_A";
    if (base === "outfit_B") return "outfit_token_B";
    if (base === "outfit_C") return "outfit_token_C";
    if (base === "scene") return "scene_token";
    return "";
}

function streamPlacementWidget(base) {
    if (base === "outfit_A") return "outfit_placement_A";
    if (base === "outfit_B") return "outfit_placement_B";
    if (base === "outfit_C") return "outfit_placement_C";
    if (base === "scene") return "scene_placement";
    return "";
}

function streamSourceWidget(base) {
    if (base === "outfit_A") return "outfit_source_A";
    if (base === "outfit_B") return "outfit_source_B";
    if (base === "outfit_C") return "outfit_source_C";
    if (base === "scene") return "scene_source";
    return "";
}

function streamManualWidget(base) {
    if (base === "outfit_A") return "outfit_manual_A";
    if (base === "outfit_B") return "outfit_manual_B";
    if (base === "outfit_C") return "outfit_manual_C";
    if (base === "scene") return "scene_manual";
    return "";
}

function streamUsesManualSource(node, base) {
    const sourceName = streamSourceWidget(base);
    return Boolean(sourceName) && String(widget(node, sourceName)?.value ?? "log") === "manual";
}

function tokenCandidates(configuredToken, ...standardAliases) {
    const values = [];
    const add = (raw) => {
        const token = String(raw ?? "").trim();
        if (!token) return;
        if (token.startsWith("{") && token.endsWith("}") && token.length > 2) {
            const bare = token.slice(1, -1).trim();
            for (const value of [token, bare]) if (value && !values.includes(value)) values.push(value);
            return;
        }
        for (const value of [`{${token}}`, token]) if (!values.includes(value)) values.push(value);
    };
    add(configuredToken);
    standardAliases.forEach(add);
    return values.sort((a, b) => b.length - a.length);
}

function streamTokenCandidates(node, base) {
    const configured = String(widget(node, streamTokenWidget(base))?.value ?? "");
    if (base === "outfit_A") return tokenCandidates(configured, "OUTFIT_A", "OUTFIT");
    if (base === "outfit_B") return tokenCandidates(configured, "OUTFIT_B");
    if (base === "outfit_C") return tokenCandidates(configured, "OUTFIT_C");
    if (base === "scene") return tokenCandidates(configured, "SCENE");
    return [];
}

function aliasPattern(candidates) {
    const escape = (value) => String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const wordEdge = /[A-Za-z0-9_]/;
    const parts = (candidates || []).filter(Boolean).map((candidate) => {
        const token = String(candidate);
        const left = wordEdge.test(token[0]) ? "(?<![A-Za-z0-9_])" : "";
        const right = wordEdge.test(token[token.length - 1]) ? "(?![A-Za-z0-9_])" : "";
        return `${left}(?:${escape(token)})${right}`;
    });
    try { return parts.length ? new RegExp(parts.join("|"), "g") : null; }
    catch (error) { return null; }
}

function aliasesInText(text, candidates) {
    const pattern = aliasPattern(candidates);
    if (!pattern) return [];
    const found = [];
    for (const match of String(text ?? "").matchAll(pattern)) {
        if (match[0] && !found.includes(match[0])) found.push(match[0]);
    }
    return found;
}

function normalizedIndex(value, count) {
    if (!count) return 0;
    let number = Number(value ?? 0);
    if (!Number.isFinite(number)) number = 0;
    return ((Math.trunc(number) % count) + count) % count;
}

function shuffledIndices(count, exclude = null) {
    const values = Array.from({ length: count }, (_, index) => index)
        .filter((index) => index !== exclude);
    for (let index = values.length - 1; index > 0; index--) {
        const swap = Math.floor(Math.random() * (index + 1));
        [values[index], values[swap]] = [values[swap], values[index]];
    }
    return values;
}

function promptShuffleState(node) {
    node.properties = node.properties || {};
    if (!node.properties.so_prompt_shuffle_state || typeof node.properties.so_prompt_shuffle_state !== "object") {
        node.properties.so_prompt_shuffle_state = {};
    }
    return node.properties.so_prompt_shuffle_state;
}

function resetShuffleBag(node, base) {
    const all = promptShuffleState(node);
    delete all[base];
}

function nextShuffledIndex(node, base, current, count, fileValue) {
    if (!count) return current;
    if (count === 1) return 0;

    const currentResolved = normalizedIndex(current, count);
    const key = `${String(fileValue ?? NO_FILE)}\u001f${count}`;
    const all = promptShuffleState(node);
    let state = all[base];

    if (!state || state.key !== key || !Array.isArray(state.remaining)) {
        state = {
            key,
            remaining: shuffledIndices(count, currentResolved),
            last: currentResolved,
        };
        all[base] = state;
    }

    // A value manually selected during the cycle counts as consumed.
    state.remaining = state.remaining.filter((index) => index !== currentResolved);

    if (!state.remaining.length) {
        // Every usable line has now appeared once. Begin a fresh shuffled cycle,
        // but do not immediately repeat the line that just ran.
        state.remaining = shuffledIndices(count, currentResolved);
    }

    const next = state.remaining.shift();
    state.last = next;
    return Number.isInteger(next) ? next : currentResolved;
}

async function fetchLogLines(category, fileValue) {
    const file = String(fileValue ?? NO_FILE);
    if (!file || file === NO_FILE) return [];
    const response = await fetch(
        `/sickollie/studio/prompt-core/log-lines?category=${encodeURIComponent(category)}&file=${encodeURIComponent(file)}`,
        { method: "GET" },
    );
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    return Array.isArray(payload?.lines) ? payload.lines.map((line) => String(line)) : [];
}

async function refreshStreamLines(node, base, force = false) {
    const [fileName] = streamConfig(base);
    const fileValue = String(widget(node, fileName)?.value ?? NO_FILE);
    node.__soLogLines = node.__soLogLines || {};
    node.__soLogLineFiles = node.__soLogLineFiles || {};

    if (!force && node.__soLogLineFiles[base] === fileValue && Array.isArray(node.__soLogLines[base])) {
        refreshStreamIndexPreview(node, base);
        return node.__soLogLines[base];
    }

    const requestToken = Symbol(base);
    node.__soLogRequests = node.__soLogRequests || {};
    node.__soLogRequests[base] = requestToken;

    try {
        const lines = await fetchLogLines(streamCategory(base), fileValue);
        if (node.__soLogRequests[base] !== requestToken) return [];
        node.__soLogLineFiles[base] = fileValue;
        node.__soLogLines[base] = lines;
        resetShuffleBag(node, base);
        refreshStreamIndexPreview(node, base);
        node.setDirtyCanvas?.(true, true);
        return lines;
    } catch (error) {
        console.warn(`[Sick Ollie Prompt Core] Could not read ${base} log`, error);
        if (node.__soLogRequests[base] === requestToken) {
            node.__soLogLineFiles[base] = fileValue;
            node.__soLogLines[base] = [];
            refreshStreamIndexPreview(node, base);
        }
        return [];
    }
}

function activeSourceTemplate(node) {
    const source = String(widget(node, "prompt_source")?.value ?? "manual");
    if (source === "input") return externalManualPromptState(node).value;
    if (source !== "log") return String(widget(node, "manual_prompt")?.value ?? "");
    const lines = node.__soLogLines?.prompt || [];
    if (!lines.length) return "";
    const index = normalizedIndex(widget(node, "prompt_index")?.value, lines.length);
    return String(lines[index] ?? "");
}

// Prefix and suffix belong to the template before placeholder resolution.
// Keep the frontend participation checks in the same order as the backend so
// a token introduced by an affix (for example SCENE on a read-only log) is
// treated as genuinely used for status, shuffle, increment, decrement, and randomize.
function activeAssembledTemplate(node) {
    const separator = String(widget(node, "prefix_suffix_separator")?.value ?? ", ");
    return [
        Boolean(widget(node, "prefix_enabled")?.value) ? promptConnectedOrWidgetValue(node, "prefix_text", "prefix") : "",
        activeSourceTemplate(node),
        Boolean(widget(node, "suffix_enabled")?.value) ? promptConnectedOrWidgetValue(node, "suffix_text", "suffix") : "",
    ].map((part) => String(part ?? "").trim()).filter(Boolean).join(separator);
}

function streamAssemblyState(node, base) {
    if (base === "prompt") {
        const source = String(widget(node, "prompt_source")?.value ?? "manual");
        return {
            used: source === "log",
            action: source,
            label: source === "log" ? "Prompt Log" : (source === "input" ? "Prompt Input" : "Manual"),
            tone: "active",
            matches: [],
        };
    }
    const [fileName] = streamConfig(base);
    const placementName = streamPlacementWidget(base);
    const placement = String(widget(node, placementName)?.value ?? "token");
    const manualSource = streamUsesManualSource(node, base);
    const manualValue = String(widget(node, streamManualWidget(base))?.value ?? "").trim();
    const fileValue = String(widget(node, fileName)?.value ?? NO_FILE);
    const fileSelected = Boolean(fileValue && fileValue !== NO_FILE);
    const lines = node.__soLogLines?.[base] || [];
    const loadedFile = String(node.__soLogLineFiles?.[base] ?? "");
    const loading = fileSelected && loadedFile !== fileValue;
    const matches = aliasesInText(activeAssembledTemplate(node), streamTokenCandidates(node, base));
    const firstMatch = matches[0] || "";

    if (placement === "off") {
        return {
            used: false,
            action: matches.length ? "remove" : "off",
            label: matches.length ? `Off · removes ${firstMatch}` : "Off",
            tone: matches.length ? "warning" : "off",
            matches,
        };
    }
    if (manualSource && !manualValue) {
        return {
            used: false,
            action: "missing_source",
            label: firstMatch ? `${firstMatch} found · enter value` : "Enter manual value",
            tone: "warning",
            matches,
        };
    }
    if (!manualSource && !fileSelected) {
        return {
            used: false,
            action: "missing_source",
            label: firstMatch ? `${firstMatch} found · choose log` : "Choose a log",
            tone: "warning",
            matches,
        };
    }
    if (!manualSource && loading) return { used: false, action: "loading", label: "Loading log…", tone: "warning", matches };
    if (!manualSource && !lines.length) return { used: false, action: "missing_source", label: "Log has no usable lines", tone: "warning", matches };
    if (placement === "token") {
        return matches.length
            ? { used: true, action: "replace", label: `${manualSource ? "Manual · " : ""}replace ${firstMatch}`, tone: "active", matches }
            : { used: false, action: "missing_placeholder", label: "Waiting for placeholder", tone: "warning", matches };
    }
    if (placement === "smart") {
        return matches.length
            ? { used: true, action: "replace", label: `${manualSource ? "Manual · " : "Auto · "}replace ${firstMatch}`, tone: "active", matches }
            : { used: true, action: "append", label: `${manualSource ? "Manual · " : "Auto · "}append`, tone: "active", matches };
    }
    if (placement === "prepend") return { used: true, action: "prepend", label: "Prepend", tone: "active", matches };
    return { used: true, action: "append", label: "Append", tone: "active", matches };
}

function shuffleStreamIsUsed(node, base) {
    return streamAssemblyState(node, base).used;
}

function previewChoice(index, line) {
    const compact = String(line ?? "").replace(/\s+/g, " ").trim();
    const shown = compact.length > 150 ? `${compact.slice(0, 149).trimEnd()}…` : compact;
    return `${index} · ${shown}`;
}

function previewWidgetName(base) {
    if (base === "prompt") return "prompt_index_preview";
    if (base === "outfit_A") return "outfit_index_preview_A";
    if (base === "outfit_B") return "outfit_index_preview_B";
    if (base === "outfit_C") return "outfit_index_preview_C";
    return "scene_index_preview";
}

function previewNoLinesValue() {
    return "0 · [no usable lines]";
}

function previewLabel(base, count) {
    const [, , indexName] = streamConfig(base);
    return `${indexName} · ${count} ${count === 1 ? "line" : "lines"}`;
}

function ensureStreamIndexPreview(node, base) {
    const key = `__so${previewWidgetName(base)}`;
    if (node[key]) return node[key];
    const [, , indexName] = streamConfig(base);
    const original = widget(node, indexName);
    if (!original) return null;

    const originalIndex = node.widgets?.indexOf(original) ?? -1;
    original.__soHiddenPreviewIndex = true;
    original.computeSize = () => [0, 0];
    if (original.inputEl) original.inputEl.style.display = "none";

    const combo = node.addWidget(
        "combo",
        previewWidgetName(base),
        previewNoLinesValue(),
        (value) => {
            const match = String(value ?? "").match(/^(-?\d+)\s*·/);
            if (!match) return;
            const index = Number.parseInt(match[1], 10);
            if (!Number.isFinite(index)) return;
            resetShuffleBag(node, base);
            original.value = index;
            try { original.callback?.(index); } catch (error) {}
            refreshStreamIndexPreview(node, base);
        },
        { values: [previewNoLinesValue()], serialize: false },
    );
    combo.serialize = false;
    combo.options = { ...(combo.options || {}), serialize: false };
    combo.label = previewLabel(base, 0);

    const appendedIndex = node.widgets?.indexOf(combo) ?? -1;
    if (originalIndex >= 0 && appendedIndex >= 0) {
        node.widgets.splice(appendedIndex, 1);
        node.widgets.splice(originalIndex + 1, 0, combo);
    }

    node[key] = combo;
    return combo;
}

function refreshStreamIndexPreview(node, base) {
    const combo = ensureStreamIndexPreview(node, base);
    const [, , indexName] = streamConfig(base);
    const indexWidget = widget(node, indexName);
    if (!combo || !indexWidget) return;
    const lines = node.__soLogLines?.[base] || [];
    if (!lines.length) {
        writeValues(combo, [previewNoLinesValue()]);
        combo.value = previewNoLinesValue();
        combo.label = previewLabel(base, 0);
        return;
    }
    const choices = lines.map((line, index) => previewChoice(index, line));
    writeValues(combo, choices);
    const current = normalizedIndex(indexWidget.value, lines.length);
    combo.value = choices[current] ?? choices[0];
    combo.label = previewLabel(base, lines.length);
}

function ensurePromptIndexPreview(node) {
    return ensureStreamIndexPreview(node, "prompt");
}

function refreshPromptIndexPreview(node) {
    return refreshStreamIndexPreview(node, "prompt");
}


function logCategoryFolder(base) {
    if (base === "prompt") return "prompts";
    if (base.startsWith("outfit_")) return "outfits";
    return "scenes";
}

function logBrowserLabel(base) {
    if (base === "prompt") return "Prompt Log";
    if (base === "outfit_A") return "Outfit A Log";
    if (base === "outfit_B") return "Outfit B Log";
    if (base === "outfit_C") return "Outfit C Log";
    return "Scene Log";
}

function collectionLogScopeId(value) {
    const text = String(value ?? "").trim();
    for (const [source, prefix] of [
        ["outfit", OUTFIT_COLLECTION_SCOPE_PREFIX],
        ["wardrobe", WARDROBE_COLLECTION_SCOPE_PREFIX],
        ["scene", SCENE_COLLECTION_SCOPE_PREFIX],
    ]) {
        if (text.startsWith(prefix) && text.endsWith("]")) {
            return { source, collection_id: text.slice(prefix.length, -1).trim() };
        }
    }
    return null;
}

function collectionLogScopes(node, base) {
    return Array.isArray(node?.__soLogCollections?.[base]) ? node.__soLogCollections[base] : [];
}

function collectionLogScope(node, base, value) {
    const wanted = String(value ?? "");
    return collectionLogScopes(node, base).find((scope) => String(scope?.reference ?? "") === wanted) || null;
}

function collectionLogSourceLabel(source) {
    if (source === "wardrobe") return "Wardrobe";
    if (source === "scene") return "Scenes";
    return "Looks";
}

function collectionLogDisplay(node, base, value) {
    const scope = collectionLogScope(node, base, value);
    if (scope) return `◆ ${collectionLogSourceLabel(scope.source)} · ${scope.name || "Collection"}`;
    const parsed = collectionLogScopeId(value);
    if (!parsed) return "";
    return `◆ ${collectionLogSourceLabel(parsed.source)} Collection`;
}

function collectionLogRowLabel(scope) {
    const count = Math.max(0, Number(scope?.asset_count || 0));
    const noun = scope?.source === "wardrobe" ? "items" : scope?.source === "scene" ? "scenes" : "looks";
    return `${collectionLogSourceLabel(scope?.source)} · ${scope?.name || "Collection"} · ${count.toLocaleString()} ${noun}`;
}

function logRelativeFile(base, fileValue) {
    const value = String(fileValue ?? NO_FILE).replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
    if (!value || value === NO_FILE) return "";
    const category = logCategoryFolder(base);
    const prefix = `${category}/`;
    return value.startsWith(prefix) ? value.slice(prefix.length) : "";
}

function logFolderForFile(base, fileValue) {
    if (collectionLogScopeId(fileValue)) return "";
    const relative = logRelativeFile(base, fileValue);
    if (!relative) return "";
    const slash = relative.lastIndexOf("/");
    return slash < 0 ? "" : relative.slice(0, slash);
}

function logBrowserButtonText(node, base) {
    const [fileName] = streamConfig(base);
    const selected = String(widget(node, fileName)?.value ?? NO_FILE);
    const collection = collectionLogDisplay(node, base, selected);
    if (collection) return `◆ ${logBrowserLabel(base)}   ${collection.replace(/^◆\s*/, "")}`;
    const relative = logRelativeFile(base, selected);
    return relative
        ? `📄 ${logBrowserLabel(base)}   ${relative}`
        : `📄 ${logBrowserLabel(base)}   [None]`;
}

function allLogFiles(node, base) {
    node.__soAllLogFiles = node.__soAllLogFiles || {};
    if (!Array.isArray(node.__soAllLogFiles[base])) {
        const [fileName] = streamConfig(base);
        node.__soAllLogFiles[base] = readValues(widget(node, fileName));
    }
    return node.__soAllLogFiles[base] || [];
}

async function refreshAvailableLogFiles(node, base) {
    const category = base === "prompt" ? "prompt" : base.startsWith("outfit_") ? "outfit" : "scene";
    try {
        const response = await fetch(`/sickollie/studio/prompt-core/log-files?category=${encodeURIComponent(category)}`);
        if (!response.ok) return allLogFiles(node, base);
        const payload = await response.json();
        const values = Array.isArray(payload?.files) ? payload.files.map(String) : [];
        node.__soLogCollections = node.__soLogCollections || {};
        node.__soLogCollections[base] = Array.isArray(payload?.collections)
            ? payload.collections.map((scope) => ({
                reference: String(scope?.reference ?? ""),
                collection_id: String(scope?.collection_id ?? ""),
                name: String(scope?.name ?? "Collection"),
                source: String(scope?.source ?? ""),
                asset_count: Math.max(0, Number(scope?.asset_count || 0)),
            })).filter((scope) => scope.reference)
            : [];
        if (!values.length) return allLogFiles(node, base);
        const [fileName] = streamConfig(base);
        const fileWidget = widget(node, fileName);
        writeValues(fileWidget, values);
        node.__soAllLogFiles = node.__soAllLogFiles || {};
        node.__soAllLogFiles[base] = [...values];
        return values;
    } catch (error) {
        console.warn("[Sick Ollie Prompt Core] Could not refresh log file list", error);
        return allLogFiles(node, base);
    }
}

function healMissingLogSelection(node, base) {
    const [fileName, , indexName] = streamConfig(base);
    const fileWidget = widget(node, fileName);
    if (!fileWidget) return false;
    const current = String(fileWidget.value ?? NO_FILE);
    if (!current || current === NO_FILE) return false;

    // Combo choices come from the backend's current filesystem scan. A stale
    // workflow/image can legitimately reference a file that was renamed, moved,
    // or deleted. Do not let that dormant value poison Comfy's queue validation.
    const available = readValues(fileWidget).map((value) => String(value));
    const category = base === "prompt" ? "prompt" : base.startsWith("outfit_") ? "outfit" : "scene";
    const canonical = canonicalCreativeLibraryLogReference(current, category);
    if (canonical !== current && available.includes(canonical)) {
        fileWidget.value = canonical;
        return true;
    }
    if (!available.length || available.includes(current)) return false;

    console.warn(`[Sick Ollie Prompt Core] Missing ${base} log was cleared: ${current}`);
    fileWidget.value = NO_FILE;
    const indexWidget = widget(node, indexName);
    if (indexWidget) indexWidget.value = 0;

    node.__soLogLines = node.__soLogLines || {};
    node.__soLogLineFiles = node.__soLogLineFiles || {};
    node.__soLogLines[base] = [];
    node.__soLogLineFiles[base] = NO_FILE;
    resetShuffleBag(node, base);

    // If the missing file was the active Prompt Source, fall back to Manual so
    // an old image cannot leave the workflow pointing at a source that no longer
    // exists. The curated/manual source prompt remains intact.
    if (base === "prompt" && String(widget(node, "prompt_source")?.value ?? "manual") === "log") {
        const sourceWidget = widget(node, "prompt_source");
        if (sourceWidget) sourceWidget.value = "manual";
    }

    node.__soMissingLogsCleared = node.__soMissingLogsCleared || [];
    node.__soMissingLogsCleared.push({ base, file: current });
    return true;
}

function healMissingLogSelections(node) {
    let changed = false;
    for (const base of STREAM_BASES) changed = healMissingLogSelection(node, base) || changed;
    if (changed) {
        node.__soAllLogFiles = {};
        node.setDirtyCanvas?.(true, true);
    }
    return changed;
}

function directLogFiles(node, base, folder) {
    const wanted = String(folder ?? "").replace(/^\/+|\/+$/g, "");
    const values = [];
    for (const fullValue of allLogFiles(node, base)) {
        const full = String(fullValue ?? "");
        if (!full || full === NO_FILE) continue;
        const relative = logRelativeFile(base, full);
        if (!relative) continue;
        const slash = relative.lastIndexOf("/");
        const parent = slash < 0 ? "" : relative.slice(0, slash);
        if (parent === wanted) values.push(full);
    }
    return values.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

function immediateLogFolders(node, base, folder) {
    const wanted = String(folder ?? "").replace(/^\/+|\/+$/g, "");
    const children = new Set();
    for (const fullValue of allLogFiles(node, base)) {
        const relative = logRelativeFile(base, fullValue);
        if (!relative) continue;
        let remainder = relative;
        if (wanted) {
            if (!relative.startsWith(wanted + "/")) continue;
            remainder = relative.slice(wanted.length + 1);
        }
        const slash = remainder.indexOf("/");
        if (slash < 0) continue;
        const child = remainder.slice(0, slash);
        if (child) children.add(child);
    }
    return [...children].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

function moveFrontendWidgetBefore(node, added, anchorWidget) {
    if (!added || !anchorWidget || !Array.isArray(node.widgets)) return;
    const addedIndex = node.widgets.indexOf(added);
    const anchorIndex = node.widgets.indexOf(anchorWidget);
    if (addedIndex < 0 || anchorIndex < 0) return;
    node.widgets.splice(addedIndex, 1);
    node.widgets.splice(anchorIndex, 0, added);
}

function hideLogFileWidget(target) {
    if (!target || target.__soHiddenByFolderNavigator) return;
    target.__soHiddenByFolderNavigator = true;
    target.computeSize = () => [0, 0];
    if (target.inputEl) target.inputEl.style.display = "none";
}

function ensurePromptBrowserPointerTracker() {
    if (window.__soBrowserPointerTrackerInstalled) return;
    window.__soBrowserPointerTrackerInstalled = true;
    window.__soBrowserLastPointer = { x: Math.round(window.innerWidth / 2), y: 180 };
    document.addEventListener("pointerdown", (event) => {
        window.__soBrowserLastPointer = { x: event.clientX, y: event.clientY };
    }, true);
}

function closePromptLogBrowser() {
    const existing = document.getElementById("so-prompt-log-browser-popup");
    if (existing) existing.remove();
    if (window.__soPromptBrowserEscape) {
        document.removeEventListener("keydown", window.__soPromptBrowserEscape, true);
        window.__soPromptBrowserEscape = null;
    }
    if (window.__soPromptBrowserOutside) {
        document.removeEventListener("pointerdown", window.__soPromptBrowserOutside, true);
        window.__soPromptBrowserOutside = null;
    }
}

function promptBrowserShell(base, folder, onSearch) {
    closePromptLogBrowser();
    const root = document.createElement("div");
    root.id = "so-prompt-log-browser-popup";
    Object.assign(root.style, {
        position: "fixed", zIndex: "100000", width: "510px",
        maxWidth: "calc(100vw - 24px)", background: "#151519",
        border: "1px solid rgba(53,215,255,.62)", borderRadius: "9px",
        boxShadow: "0 12px 36px rgba(0,0,0,.58), 0 0 0 1px rgba(255,74,184,.10) inset", color: "#eee",
        font: "13px Arial, sans-serif", overflow: "hidden",
    });

    const header = document.createElement("div");
    Object.assign(header.style, { padding: "10px 12px 6px", borderBottom: "1px solid rgba(255,74,184,.34)" });
    const title = document.createElement("div");
    title.textContent = logBrowserLabel(base);
    Object.assign(title.style, { fontWeight: "700", fontSize: "14px" });
    const subtitle = document.createElement("div");
    subtitle.textContent = folder ? `${logCategoryFolder(base)} / ${folder}` : `${logCategoryFolder(base)} root`;
    Object.assign(subtitle.style, { marginTop: "3px", color: "#aaa", fontSize: "12px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
    header.append(title, subtitle);

    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = `Filter ${logBrowserLabel(base).toLowerCase()} files or folders`;
    Object.assign(search.style, {
        boxSizing: "border-box", width: "calc(100% - 20px)", margin: "9px 10px 7px",
        padding: "7px 9px", background: "#0d0d10", border: "1px solid rgba(246,230,90,.48)",
        borderRadius: "4px", color: "#fff", outline: "none",
    });

    const list = document.createElement("div");
    Object.assign(list.style, { maxHeight: "540px", overflowY: "auto", padding: "3px 0 7px" });
    root.append(header, search, list);
    document.body.append(root);

    const pointer = window.__soBrowserLastPointer || { x: window.innerWidth / 2, y: 180 };
    let left = Math.min(pointer.x - 18, window.innerWidth - 530);
    let top = Math.min(pointer.y + 12, window.innerHeight - 620);
    left = Math.max(10, left);
    top = Math.max(10, top);
    root.style.left = `${left}px`;
    root.style.top = `${top}px`;

    search.addEventListener("input", () => onSearch(search.value));
    root.addEventListener("pointerdown", (event) => event.stopPropagation());
    window.__soPromptBrowserEscape = (event) => {
        if (event.key === "Escape") closePromptLogBrowser();
    };
    document.addEventListener("keydown", window.__soPromptBrowserEscape, true);
    window.__soPromptBrowserOutside = (event) => {
        if (!root.contains(event.target)) closePromptLogBrowser();
    };
    setTimeout(() => {
        document.addEventListener("pointerdown", window.__soPromptBrowserOutside, true);
        search.focus();
    }, 0);
    return { root, subtitle, search, list };
}

function promptBrowserRow(list, label, kind, callback, hint = "") {
    const row = document.createElement("div");
    const icon = kind === "folder" ? "📁  " : kind === "collection" ? "◆  " : "";
    row.textContent = `${icon}${label}`;
    Object.assign(row.style, {
        padding: "7px 12px", cursor: "pointer", borderBottom: "1px solid #242424",
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        color: kind === "action" ? "#ccc" : kind === "collection" ? "#fff6a8" : "#f4f4f4",
    });
    if (hint) row.title = hint;
    row.addEventListener("mouseenter", () => row.style.background = "rgba(53,215,255,.10)");
    row.addEventListener("mouseleave", () => row.style.background = "transparent");
    row.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        callback();
    });
    list.append(row);
    return row;
}

function promptBrowserSection(list, label) {
    const row = document.createElement("div");
    row.textContent = String(label || "").toUpperCase();
    Object.assign(row.style, {
        padding: "7px 12px 4px", color: "#8c8492", font: "800 9px Segoe UI, Arial",
        letterSpacing: ".10em", pointerEvents: "none",
    });
    list.append(row);
    return row;
}

function promptBrowserDivider(list) {
    const divider = document.createElement("div");
    Object.assign(divider.style, { height: "1px", background: "rgba(110,231,162,.34)", margin: "5px 0" });
    list.append(divider);
}

function refreshLogBrowserButton(node, base) {
    const button = node.__soLogBrowserButtons?.[base];
    if (button) button.name = logBrowserButtonText(node, base);
    node.setDirtyCanvas?.(true, true);
}

function selectLogFile(node, base, full) {
    const [fileName] = streamConfig(base);
    const fileWidget = widget(node, fileName);
    if (!fileWidget) return;
    fileWidget.value = String(full ?? NO_FILE);
    try { fileWidget.callback?.(fileWidget.value); } catch (error) {}
    node.__soLogBrowseFolders = node.__soLogBrowseFolders || {};
    if (fileWidget.value !== NO_FILE) node.__soLogBrowseFolders[base] = logFolderForFile(base, fileWidget.value);
    refreshLogBrowserButton(node, base);
}

function renderPromptLogBrowser(node, base, shell, query = "") {
    node.__soLogBrowseFolders = node.__soLogBrowseFolders || {};
    let folder = String(node.__soLogBrowseFolders[base] ?? "").replace(/^\/+|\/+$/g, "");
    shell.subtitle.textContent = folder ? `${logCategoryFolder(base)} / ${folder}` : `${logCategoryFolder(base)} root`;
    shell.list.replaceChildren();
    const q = String(query ?? "").trim().toLowerCase();

    if (q) {
        const collectionHits = collectionLogScopes(node, base).filter((scope) =>
            `${scope?.name || ""} ${collectionLogSourceLabel(scope?.source)}`.toLowerCase().includes(q)
        );
        const folderSet = new Set();
        const fileHits = [];
        for (const fullValue of allLogFiles(node, base)) {
            const full = String(fullValue ?? "");
            if (!full || full === NO_FILE) continue;
            const relative = logRelativeFile(base, full);
            if (!relative) continue;
            const parts = relative.split("/");
            for (let i = 1; i < parts.length; i++) {
                const folderPath = parts.slice(0, i).join("/");
                if (folderPath.toLowerCase().includes(q)) folderSet.add(folderPath);
            }
            if (relative.toLowerCase().includes(q)) fileHits.push(full);
        }
        if (collectionHits.length) {
            promptBrowserSection(shell.list, "Collections");
            for (const scope of collectionHits.slice(0, 80)) {
                promptBrowserRow(shell.list, collectionLogRowLabel(scope), "collection", () => {
                    selectLogFile(node, base, scope.reference);
                    closePromptLogBrowser();
                }, scope.reference);
            }
        }
        const folderHits = [...folderSet].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" })).slice(0, 120);
        if (collectionHits.length && (folderHits.length || fileHits.length)) promptBrowserDivider(shell.list);
        for (const path of folderHits) {
            promptBrowserRow(shell.list, path, "folder", () => {
                node.__soLogBrowseFolders[base] = path;
                shell.search.value = "";
                renderPromptLogBrowser(node, base, shell, "");
            }, path);
        }
        if (folderHits.length && fileHits.length) promptBrowserDivider(shell.list);
        for (const full of fileHits.slice(0, 180)) {
            const relative = logRelativeFile(base, full);
            promptBrowserRow(shell.list, relative, "file", () => {
                selectLogFile(node, base, full);
                closePromptLogBrowser();
            }, full);
        }
        if (!collectionHits.length && !folderHits.length && !fileHits.length) promptBrowserRow(shell.list, "No matches", "action", () => {});
        return;
    }

    promptBrowserRow(shell.list, "[None] · clear selected log", "action", () => {
        selectLogFile(node, base, NO_FILE);
        closePromptLogBrowser();
    });
    const collections = collectionLogScopes(node, base);
    if (collections.length) {
        promptBrowserSection(shell.list, "Collections");
        for (const scope of collections) {
            promptBrowserRow(shell.list, collectionLogRowLabel(scope), "collection", () => {
                selectLogFile(node, base, scope.reference);
                closePromptLogBrowser();
            }, scope.reference);
        }
        promptBrowserDivider(shell.list);
    }
    if (folder) {
        promptBrowserRow(shell.list, "↑ Parent Folder", "action", () => {
            const slash = folder.lastIndexOf("/");
            node.__soLogBrowseFolders[base] = slash < 0 ? "" : folder.slice(0, slash);
            renderPromptLogBrowser(node, base, shell, "");
        });
    }
    promptBrowserRow(shell.list, `⌂ ${logCategoryFolder(base)} Root`, "action", () => {
        node.__soLogBrowseFolders[base] = "";
        renderPromptLogBrowser(node, base, shell, "");
    });
    promptBrowserDivider(shell.list);

    const children = immediateLogFolders(node, base, folder);
    for (const child of children) {
        promptBrowserRow(shell.list, child, "folder", () => {
            node.__soLogBrowseFolders[base] = folder ? `${folder}/${child}` : child;
            renderPromptLogBrowser(node, base, shell, "");
        });
    }

    const files = directLogFiles(node, base, folder);
    if (children.length && files.length) promptBrowserDivider(shell.list);
    for (const full of files) {
        const relative = logRelativeFile(base, full);
        const slash = relative.lastIndexOf("/");
        const basename = slash < 0 ? relative : relative.slice(slash + 1);
        promptBrowserRow(shell.list, basename, "file", () => {
            selectLogFile(node, base, full);
            closePromptLogBrowser();
        }, full);
    }

    if (!children.length && !files.length) promptBrowserRow(shell.list, "No folders or .txt files here", "action", () => {});
}

async function openPromptLogBrowser(node, base) {
    ensurePromptBrowserPointerTracker();
    await refreshAvailableLogFiles(node, base);
    node.__soLogBrowseFolders = node.__soLogBrowseFolders || {};
    const [fileName] = streamConfig(base);
    const selected = String(widget(node, fileName)?.value ?? NO_FILE);
    if (collectionLogScopeId(selected)) await refreshStreamLines(node, base, true);
    if (selected !== NO_FILE) node.__soLogBrowseFolders[base] = logFolderForFile(base, selected);
    if (!Object.prototype.hasOwnProperty.call(node.__soLogBrowseFolders, base)) node.__soLogBrowseFolders[base] = "";

    const shell = promptBrowserShell(
        base,
        node.__soLogBrowseFolders[base],
        (query) => renderPromptLogBrowser(node, base, shell, query),
    );
    renderPromptLogBrowser(node, base, shell, "");
}

function ensureLogNavigator(node, base) {
    node.__soLogBrowserButtons = node.__soLogBrowserButtons || {};
    const [fileName] = streamConfig(base);
    const fileWidget = widget(node, fileName);
    if (!fileWidget) return null;

    allLogFiles(node, base);
    hideLogFileWidget(fileWidget);

    let button = node.__soLogBrowserButtons[base];
    if (!button) {
        button = node.addWidget(
            "button",
            logBrowserButtonText(node, base),
            null,
            () => openPromptLogBrowser(node, base),
            { serialize: false },
        );
        button.serialize = false;
        button.options = { ...(button.options || {}), serialize: false };
        node.__soLogBrowserButtons[base] = button;
        moveFrontendWidgetBefore(node, button, fileWidget);
    }

    if (!fileWidget.__soFolderNavigatorBound) {
        fileWidget.__soFolderNavigatorBound = true;
        const previousCallback = fileWidget.callback;
        fileWidget.callback = function (...args) {
            const result = previousCallback?.apply(this, args);
            refreshLogBrowserButton(node, base);
            return result;
        };
    }

    refreshLogBrowserButton(node, base);
    return button;
}

function ensureAllLogNavigators(node) {
    for (const base of STREAM_BASES) ensureLogNavigator(node, base);
}

function bindLogControls(node) {
    for (const base of STREAM_BASES) {
        const [fileName, modeName] = streamConfig(base);
        const fileWidget = widget(node, fileName);
        if (fileWidget && !fileWidget.__soLogRefreshBound) {
            fileWidget.__soLogRefreshBound = true;
            const originalCallback = fileWidget.callback;
            fileWidget.callback = function (...args) {
                const result = originalCallback?.apply(this, args);
                healMissingLogSelection(node, base);
                refreshStreamLines(node, base, true);
                return result;
            };
        }
        const modeWidget = widget(node, modeName);
        if (modeWidget && !modeWidget.__soShuffleModeBound) {
            modeWidget.__soShuffleModeBound = true;
            const originalCallback = modeWidget.callback;
            modeWidget.callback = function (...args) {
                const result = originalCallback?.apply(this, args);
                resetShuffleBag(node, base);
                return result;
            };
        }
        const placementName = streamPlacementWidget(base);
        const placementWidget = placementName ? widget(node, placementName) : null;
        if (placementWidget && !placementWidget.__soPlacementBound) {
            placementWidget.__soPlacementBound = true;
            const originalCallback = placementWidget.callback;
            placementWidget.callback = function (...args) {
                const result = originalCallback?.apply(this, args);
                resetShuffleBag(node, base);
                node.setDirtyCanvas?.(true, true);
                return result;
            };
        }
        refreshStreamLines(node, base, false);
        if (base !== "prompt") {
            void refreshAvailableLogFiles(node, base).then(() => {
                refreshLogBrowserButton(node, base);
                node.setDirtyCanvas?.(true, true);
            });
        }
    }
}

async function refreshCollectionBackedStreams(kind = "") {
    const cleanKind = String(kind || "").toLowerCase();
    const bases = cleanKind === "scene"
        ? ["scene"]
        : cleanKind === "outfit" || cleanKind === "wardrobe"
            ? ["outfit_A", "outfit_B", "outfit_C"]
            : ["outfit_A", "outfit_B", "outfit_C", "scene"];
    for (const node of app.graph?._nodes || []) {
        if (node?.type !== TARGET && node?.comfyClass !== TARGET) continue;
        for (const base of bases) {
            await refreshAvailableLogFiles(node, base);
            healMissingLogSelection(node, base);
            refreshLogBrowserButton(node, base);
            const [fileName] = streamConfig(base);
            const selected = String(widget(node, fileName)?.value ?? NO_FILE);
            const parsed = collectionLogScopeId(selected);
            if (!parsed) continue;
            if (cleanKind && parsed.source !== cleanKind) continue;
            await refreshStreamLines(node, base, true);
        }
        node.setDirtyCanvas?.(true, true);
    }
}

if (typeof window !== "undefined" && !window.__soPromptCollectionRefreshBound) {
    window.__soPromptCollectionRefreshBound = true;
    window.addEventListener("sickollie:library-collections-changed", (event) => {
        void refreshCollectionBackedStreams(event?.detail?.kind || "");
    });
}

function streamConfig(base) {
    if (base === "prompt") return ["prompt_log_file", "prompt_mode", "prompt_index"];
    if (base === "outfit_A") return ["outfit_log_file_A", "outfit_mode_A", "outfit_index_A"];
    if (base === "outfit_B") return ["outfit_log_file_B", "outfit_mode_B", "outfit_index_B"];
    if (base === "outfit_C") return ["outfit_log_file_C", "outfit_mode_C", "outfit_index_C"];
    return ["scene_log_file", "scene_mode", "scene_index"];
}

function advanceStream(node, base) {
    const [fileName, modeName, indexName] = streamConfig(base);
    if (base === "prompt" && String(widget(node, "prompt_source")?.value) !== "log") return;
    if (base !== "prompt" && streamUsesManualSource(node, base)) return;
    if (String(widget(node, fileName)?.value ?? NO_FILE) === NO_FILE) return;
    // Components advance only when they actually participate. Smart append,
    // explicit append/prepend, and matched placeholders all count as used.
    if (base !== "prompt" && !shuffleStreamIsUsed(node, base)) return;

    const mode = String(widget(node, modeName)?.value ?? "fixed");
    const indexWidget = widget(node, indexName);
    if (!indexWidget || mode === "fixed") return;

    let current = Number(indexWidget.value ?? 0);
    if (!Number.isFinite(current)) current = 0;
    let next = current;

    if (mode === "shuffle") {
        const lines = node.__soLogLines?.[base] || [];
        if (!lines.length) return;
        next = nextShuffledIndex(
            node,
            base,
            current,
            lines.length,
            widget(node, fileName)?.value,
        );
    } else if (mode === "increment") {
        next = current + 1;
    } else if (mode === "decrement") {
        next = current - 1;
    } else if (mode === "randomize") {
        next = Math.floor(Math.random() * LARGE_RANDOM_MAX);
    }

    indexWidget.value = next;
    try { indexWidget.callback?.(next); } catch (error) {}
    refreshStreamIndexPreview(node, base);
    node.setDirtyCanvas?.(true, true);
}

function bindQueueProgression(node) {
    for (const base of ["prompt", "outfit_A", "outfit_B", "outfit_C", "scene"]) {
        const [, , indexName] = streamConfig(base);
        const indexWidget = widget(node, indexName);
        if (!indexWidget || indexWidget.__soQueueBound) continue;
        indexWidget.__soQueueBound = true;
        const originalAfterQueued = indexWidget.afterQueued;
        indexWidget.afterQueued = () => {
            try { originalAfterQueued?.call(indexWidget); }
            finally { advanceStream(node, base); }
        };
    }
}


const PROMPT_DASH_VERSION = 10;
const PROMPT_DASH_MIN_WIDTH = STUDIO_LAYOUT.minWidth;
const PROMPT_DASH_PAD = STUDIO_LAYOUT.pad;
const PROMPT_DASH_GAP = STUDIO_LAYOUT.gap;
const PROMPT_DASH_ROW_H = STUDIO_LAYOUT.rowHeight;
const PROMPT_SECTION_GAP = STUDIO_LAYOUT.sectionGap + 8;
const PROMPT_LOG_BOTTOM_PAD = 24;
const PROMPT_LIBRARY_HEIGHT = 60;
const PROMPT_LIBRARY_TOP_PAD = 12;
const PROMPT_LIBRARY_BOTTOM_PAD = 24;
const PROMPT_SOURCE_FRAME_BOTTOM_GAP = 6;
const PROMPT_DASH_COLLAPSED_H = 1275;
const PROMPT_DASH_EXPANDED_H = 1365;
const SO_CMYKG = {
    cyan: STUDIO_THEME.cyan,
    magenta: STUDIO_THEME.magenta,
    yellow: STUDIO_THEME.yellow,
    green: STUDIO_THEME.green,
    ink: STUDIO_THEME.ink,
    panel: STUDIO_THEME.panel,
    row: STUDIO_THEME.row,
    outline: STUDIO_THEME.outline,
    label: STUDIO_THEME.label,
    text: STUDIO_THEME.text,
};

function promptDashTop(node) {
    return STUDIO_LAYOUT.headerHeight;
}

function layoutPromptOutputSockets(node) {
    const right = Number(node.size?.[0] || PROMPT_DASH_MIN_WIDTH);
    for (let index = 0; index < (node.outputs?.length || 0); index++) {
        node.outputs[index].pos = [right, STUDIO_LAYOUT.socketStart + index * STUDIO_LAYOUT.socketStep];
    }
}

function promptOutputAnchor(node, slotIndex) {
    const output = node.outputs?.[Number(slotIndex)];
    if (!output) return null;
    layoutPromptOutputSockets(node);
    const y = Number(output.pos?.[1]);
    if (!Number.isFinite(y)) return null;
    return { x: Number(node.size?.[0] || PROMPT_DASH_MIN_WIDTH), y };
}

function promptOutputBottom(node) {
    layoutPromptOutputSockets(node);
    const outputCount = node.outputs?.length || 0;
    return outputCount
        ? STUDIO_LAYOUT.socketStart + outputCount * STUDIO_LAYOUT.socketStep + 5
        : STUDIO_LAYOUT.headerHeight;
}

const PROMPT_FORCE_INPUT_NAMES = ["main_trigger", "manual_prompt_input"];

const PROMPT_VISIBLE_INPUT_NAMES = [
    "manual_prompt_input",
    "name_value",
    "item_value",
    "prefix_text",
    "suffix_text",
    "main_trigger",
];

function promptInputIsConnected(input) {
    return input?.link != null || (Array.isArray(input?.links) && input.links.length > 0);
}

function promptShouldExposeInput(input) {
    const name = promptInputName(input);
    // Four intentionally useful jack points are always visible. Any legacy/
    // unusual socket that is already connected remains visible so old workflows
    // do not silently lose a connection endpoint.
    return PROMPT_VISIBLE_INPUT_NAMES.includes(name) || promptInputIsConnected(input);
}

function promptExternalInputs(node) {
    return (node.inputs || []).filter((input) => {
        const name = promptInputName(input);
        return Boolean(name) && (CANONICAL_NAMES.includes(name) || PROMPT_FORCE_INPUT_NAMES.includes(name)) && promptShouldExposeInput(input);
    });
}

function configuredPlaceholderLabel(node, widgetName, fallback) {
    const configured = String(widget(node, widgetName)?.value ?? fallback).trim() || fallback;
    if (configured.startsWith("{") && configured.endsWith("}")) {
        return configured.slice(1, -1).trim() || fallback;
    }
    return configured;
}

function promptExternalInputLabel(node, name) {
    const itemLabel = configuredPlaceholderLabel(node, "item_token", "ITEM");
    const labels = {
        name_value: "NAME value",
        item_value: `${itemLabel} value`,
        prefix_text: "Prefix text",
        suffix_text: "Suffix text",
        main_trigger: "TRIGGER value",
        manual_prompt_input: "Prompt input · final/source",
    };
    return labels[name] || String(name || "Input").replaceAll("_", " ");
}

function layoutPromptInputSockets(node) {
    node.__soPromptInputAnchors = {};
    node.__soPromptExternalInputAnchors = {};
    let y = STUDIO_LAYOUT.socketStart;
    for (const input of node.inputs || []) {
        const name = promptInputName(input);
        if (!name || !(CANONICAL_NAMES.includes(name) || PROMPT_FORCE_INPUT_NAMES.includes(name))) continue;
        if (promptShouldExposeInput(input)) {
            node.__soPromptInputAnchors[name] = y;
            node.__soPromptExternalInputAnchors[name] = y;
            input.pos = [0, y];
            // main_trigger is a true forceInput socket, so LiteGraph draws its
            // native label in addition to our dashboard label. Suppress only that
            // native text to avoid the doubled raw "main_trigger" / dashboard label ghosting.
            // A single space is intentional: LiteGraph falls back to input.name when
            // label is an empty string, which is why main_trigger still appeared.
            input.label = PROMPT_FORCE_INPUT_NAMES.includes(name) ? " " : promptExternalInputLabel(node, name);
            input.color_on = SO_CMYKG.green;
            input.color_off = "#7f8792";
            y += 21;
        } else {
            // Keep the backend/input object intact but move unused converted
            // widget sockets completely outside the visible node surface.
            node.__soPromptInputAnchors[name] = -10000;
            input.pos = [-10000, -10000];
            input.label = "";
        }
    }
    return y;
}

function promptInputSocketsBottom(node) {
    const count = promptExternalInputs(node).length;
    return count
        ? STUDIO_LAYOUT.socketStart + count * STUDIO_LAYOUT.socketStep + 5
        : STUDIO_LAYOUT.headerHeight;
}

function promptSourceTop(node) {
    return Math.max(promptOutputBottom(node), promptInputSocketsBottom(node)) + STUDIO_LAYOUT.socketGap
        + PROMPT_LIBRARY_TOP_PAD + PROMPT_LIBRARY_HEIGHT + PROMPT_LIBRARY_BOTTOM_PAD;
}

function promptSourceHeight(node) {
    const sourceMode = String(widget(node, "prompt_source")?.value ?? "manual");
    // Keep a comfortable cyan gutter beneath the Prompt Log Mode/Index row.
    return sourceMode === "log" ? 255 : 205;
}

function promptLowerStart(node) {
    return Math.max(
        promptSourceTop(node) + promptSourceHeight(node) + PROMPT_SECTION_GAP,
        promptOutputBottom(node) + PROMPT_SECTION_GAP,
    );
}

function promptLowerHeight(node) {
    // Everything from Prompt Assembly through the copy-resolved button.
    return 1054 + (node.properties?.so_prompt_dashboard_advanced ? 90 : 0);
}

function promptSourceFrameGeometry(sourceTop, lowerTop) {
    const top = sourceTop - 5;
    const bottom = lowerTop - PROMPT_SOURCE_FRAME_BOTTOM_GAP;
    return { top, bottom, height: Math.max(20, bottom - top) };
}

function promptDashHeight(node) {
    return promptLowerStart(node) - promptDashTop(node) + promptLowerHeight(node);
}

function promptDashBottom(node) {
    return promptLowerStart(node) + promptLowerHeight(node);
}

function promptRoundRect(ctx, x, y, w, h, radius = 8, fill = null, stroke = null, lineWidth = 1) {
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, h, radius);
    else {
        const r = Math.min(radius, w / 2, h / 2);
        ctx.moveTo(x + r, y);
        ctx.arcTo(x + w, y, x + w, y + h, r);
        ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r);
        ctx.arcTo(x, y, x + w, y, r);
    }
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lineWidth; ctx.stroke(); }
}

function promptGradientFrame(ctx, x, y, w, h, radius = 11, alpha = .42, accent = SO_CMYKG.magenta) {
    drawStudioSectionFrame(ctx, x, y, w, h, accent, radius, alpha);
}

function promptDashText(ctx, text, x, y, options = {}) {
    ctx.save();
    ctx.fillStyle = options.color || SO_CMYKG.text;
    ctx.font = options.font || "12px Segoe UI, Arial";
    ctx.textAlign = options.align || "left";
    ctx.textBaseline = options.baseline || "middle";
    ctx.fillText(String(text ?? ""), x, y);
    ctx.restore();
}

function promptSection(ctx, label, x, y, color = SO_CMYKG.cyan) {
    promptDashText(ctx, String(label).toUpperCase(), x, y, { color, font: "700 10px Segoe UI, Arial" });
}

function promptFit(ctx, text, width) {
    const raw = String(text ?? "");
    if (ctx.measureText(raw).width <= width) return raw;
    let out = raw;
    while (out.length > 1 && ctx.measureText(`${out}…`).width > width) out = out.slice(0, -1);
    return `${out.trimEnd()}…`;
}

function promptWrap(ctx, text, width) {
    const output = [];
    for (const para of String(text ?? "").split(/\r?\n/)) {
        if (!para.trim()) { output.push(""); continue; }
        let line = "";
        for (const word of para.split(/\s+/)) {
            const test = line ? `${line} ${word}` : word;
            if (!line || ctx.measureText(test).width <= width) line = test;
            else { output.push(line); line = word; }
        }
        if (line) output.push(line);
    }
    return output;
}

function promptValueRow(ctx, x, y, w, h, label, value, options = {}) {
    promptRoundRect(ctx, x, y, w, h, 8, SO_CMYKG.row, options.stroke || SO_CMYKG.outline);
    promptDashText(ctx, label, x + 12, y + h / 2, { color: SO_CMYKG.label, font: "11px Segoe UI, Arial" });
    ctx.save();
    ctx.font = options.valueFont || "12px Segoe UI, Arial";
    const labelAllowance = Math.min(150, w * .42);
    const shown = promptFit(ctx, String(value ?? ""), Math.max(42, w - labelAllowance - 32));
    ctx.restore();
    promptDashText(ctx, shown, x + w - (options.chevron === false ? 12 : 23), y + h / 2, {
        align: "right", color: options.valueColor || SO_CMYKG.text, font: options.valueFont || "12px Segoe UI, Arial",
    });
    if (options.chevron !== false) promptDashText(ctx, "▾", x + w - 9, y + h / 2, { align: "right", color: SO_CMYKG.label, font: "10px Arial" });
}

function promptToggleRow(ctx, x, y, w, h, label, enabled, color = SO_CMYKG.green) {
    promptRoundRect(ctx, x, y, w, h, 8, SO_CMYKG.row, SO_CMYKG.outline);
    promptDashText(ctx, label, x + 12, y + h / 2, { font: "11px Segoe UI, Arial" });
    const tw = 36, th = 18, tx = x + w - tw - 10, ty = y + (h - th) / 2;
    promptRoundRect(ctx, tx, ty, tw, th, th / 2, enabled ? color : "rgba(82,82,90,.95)", null);
    ctx.beginPath();
    ctx.arc(tx + (enabled ? tw - th / 2 : th / 2), ty + th / 2, 6.6, 0, Math.PI * 2);
    ctx.fillStyle = "#f5f5f5";
    ctx.fill();
}

function promptConnectedSource(node, inputName) {
    const input = node.inputs?.find((slot) => promptInputName(slot) === String(inputName));
    if (!input || !promptInputIsConnected(input)) return null;
    const reference = input.link ?? (Array.isArray(input.links) ? input.links[0] : null);
    const link = reference && typeof reference === "object" ? reference : app.graph?.links?.[reference];
    if (!link) return { label: "Connected input", node: null, output: "" };
    const origin = app.graph?.getNodeById?.(link.origin_id) || app.graph?._nodes_by_id?.[link.origin_id];
    const output = origin?.outputs?.[Number(link.origin_slot)];
    const nodeLabel = String(origin?.title || origin?.constructor?.title || origin?.type || "Upstream node");
    const outputLabel = String(output?.label || output?.name || `output ${Number(link.origin_slot) + 1}`);
    const outputName = String(output?.name || output?.label || "");
    return {
        label: `${nodeLabel} → ${outputLabel}`,
        node: origin,
        output: outputLabel,
        outputName,
        outputIndex: Number(link.origin_slot),
        input,
        inputIndex: Number(node.inputs?.indexOf(input) ?? -1),
        link,
        linkId: reference && typeof reference === "object" ? (reference.id ?? reference) : reference,
    };
}

function loaderTriggerOutputIndex(loader) {
    return (loader?.outputs || []).findIndex((output) =>
        [output?.name, output?.label].some((value) => String(value ?? "").trim() === "main_trigger")
    );
}

function samePromptLink(left, right) {
    if (left === right) return true;
    if (left == null || right == null) return false;
    return String(left) === String(right);
}

/**
 * Early Studio workflows connected Prompt Core's trigger socket to Loader
 * Core's clean_name output because main_trigger did not exist yet.  Once the
 * dedicated output was added, LiteGraph correctly preserved the old slot
 * number -- but that meant the backend continued receiving only values such
 * as "jester" while Loader Core's UI showed the full saved override.
 *
 * Repair only this unambiguous Loader Core case.  Arbitrary STRING sources are
 * left untouched, and the original link id/input remain stable so saved
 * workflows upgrade in place without dropping their wire.
 */
function repairPromptTriggerConnection(node) {
    const connection = promptConnectedSource(node, "main_trigger");
    const loader = connection?.node;
    const targetIndex = loaderTriggerOutputIndex(loader);
    if (!connection?.link || targetIndex < 0 || connection.outputIndex === targetIndex) return false;

    const previousIndex = Number(connection.link.origin_slot);
    const previousOutput = loader?.outputs?.[previousIndex];
    const targetOutput = loader?.outputs?.[targetIndex];
    if (!targetOutput) return false;

    if (Array.isArray(previousOutput?.links)) {
        previousOutput.links = previousOutput.links.filter((value) => !samePromptLink(value, connection.linkId));
    }
    if (!Array.isArray(targetOutput.links)) targetOutput.links = [];
    if (!targetOutput.links.some((value) => samePromptLink(value, connection.linkId))) {
        targetOutput.links.push(connection.linkId);
    }

    connection.link.origin_slot = targetIndex;
    if (targetOutput.type) connection.link.type = targetOutput.type;
    node.properties = node.properties || {};
    node.properties.so_trigger_connection_repaired = true;
    node.__soTriggerConnectionRepair = {
        from: String(previousOutput?.name || previousOutput?.label || `output ${previousIndex + 1}`),
        to: "main_trigger",
    };
    loader?.setDirtyCanvas?.(true, true);
    node.setDirtyCanvas?.(true, true);
    app.graph?.setDirtyCanvas?.(true, true);
    return true;
}

function promptConnectedLiveValue(connection) {
    const origin = connection?.node;
    const values = origin?.__soLiveOutputs;
    if (!values || typeof values !== "object") return undefined;
    const keys = [connection?.outputName, connection?.output]
        .map((value) => String(value ?? "").trim())
        .filter(Boolean);
    for (const key of keys) {
        if (Object.prototype.hasOwnProperty.call(values, key)) return values[key];
    }
    return undefined;
}

function externalManualPromptState(node) {
    const connection = promptConnectedSource(node, "manual_prompt_input");
    const liveValue = promptConnectedLiveValue(connection);
    const remembered = node?.properties?.so_external_manual_prompt_value;
    const value = connection
        ? (liveValue !== undefined ? String(liveValue ?? "") : String(remembered ?? ""))
        : "";
    return { connection, connected: Boolean(connection), liveValue, value };
}

function syncExternalManualPrompt(node) {
    const state = externalManualPromptState(node);
    if (!state.connected || state.liveValue === undefined) return false;
    const text = String(state.liveValue ?? "");
    node.properties = node.properties || {};
    if (String(node.properties.so_external_manual_prompt_value ?? "") === text) return false;
    // Keep a live/fallback copy for the dedicated Prompt Input source, but never
    // overwrite the Manual draft and never change the selected source.
    node.properties.so_external_manual_prompt_value = text;
    node.setDirtyCanvas?.(true, true);
    return true;
}

function promptConnectedTriggerValue(connection) {
    const loader = connection?.node;
    if (loaderTriggerOutputIndex(loader) >= 0) {
        const enabledWidget = widget(loader, "main_enabled");
        const strengthWidget = widget(loader, "main_strength");
        const selectedWidget = widget(loader, "main_lora");
        const enabled = enabledWidget ? Boolean(enabledWidget.value) : true;
        const strength = strengthWidget ? Number(strengthWidget.value ?? 0) : 1;
        const selected = selectedWidget ? String(selectedWidget.value ?? "").trim() : "active";
        if (!enabled || !selected || (Number.isFinite(strength) && strength === 0)) return "";
        if (Object.prototype.hasOwnProperty.call(loader, "__soMainTrigger")) {
            return loader.__soMainTrigger;
        }
    }
    return promptConnectedLiveValue(connection);
}

function promptConnectedTextState(node, inputName, metadataKey) {
    const connection = promptConnectedSource(node, inputName);
    const liveValue = promptConnectedLiveValue(connection);
    const lastText = node.__soLastAssembly?.[metadataKey]?.text;
    return {
        connection,
        connected: Boolean(connection),
        display: connection
            ? `${connection.label}${liveValue !== undefined
                ? ` · ${String(liveValue)}`
                : (lastText ? ` · ${String(lastText)}` : "")}`
            : String(widget(node, inputName)?.value ?? ""),
    };
}

function pulseConnectedSource(node, inputName) {
    const source = promptConnectedSource(node, inputName)?.node;
    if (!source) return;
    source.__soAttentionUntil = Date.now() + 900;
    source.setDirtyCanvas?.(true, true);
    node.setDirtyCanvas?.(true, true);
    clearTimeout(source.__soAttentionTimer);
    source.__soAttentionTimer = setTimeout(() => source.setDirtyCanvas?.(true, true), 940);
}

function substitutionState(node, kind) {
    const isName = kind === "name";
    const tokenName = isName ? "name_token" : "item_token";
    const valueName = isName ? "name_value" : "item_value";
    const standard = isName ? "NAME" : "ITEM";
    const token = String(widget(node, tokenName)?.value ?? standard);
    const matches = aliasesInText(activeAssembledTemplate(node), tokenCandidates(token, standard));
    const connection = promptConnectedSource(node, valueName);
    const liveValue = promptConnectedLiveValue(connection);
    const lastValue = node.__soLastAssembly?.[kind]?.value;
    const value = connection
        ? (liveValue !== undefined
            ? String(liveValue)
            : (lastValue != null ? String(lastValue) : ""))
        : String(widget(node, valueName)?.value ?? "");
    if (!value && !connection) return { used: false, tone: "warning", label: "Enter a value", token, value, connection, matches };
    if (!matches.length) return { used: false, tone: "warning", label: "Not placed in prompt", token, value, connection, matches };
    return {
        used: true,
        tone: "active",
        label: connection ? `Linked · replace ${matches[0]}` : `Replace ${matches[0]}`,
        token,
        value,
        connection,
        matches,
    };
}

function connectedTriggerLora(node) {
    repairPromptTriggerConnection(node);
    const connection = promptConnectedSource(node, "main_trigger");
    return String(widget(connection?.node, "main_lora")?.value ?? "").trim();
}

function syncTriggerOverrideScope(node) {
    const target = widget(node, "trigger_override");
    const override = String(target?.value ?? "").trim();
    node.properties = node.properties || {};
    if (!override) {
        delete node.properties.so_trigger_override_lora;
        return false;
    }
    const currentLora = connectedTriggerLora(node);
    const pinnedLora = String(node.properties.so_trigger_override_lora ?? "").trim();
    // Upgrade old Prompt Core overrides into a LoRA-scoped pin the first time
    // they are seen with a connected Loader Core.
    if (!pinnedLora && currentLora) {
        node.properties.so_trigger_override_lora = currentLora;
        return false;
    }
    if (pinnedLora && pinnedLora !== currentLora) {
        promptDashboardSet(node, "trigger_override", "");
        delete node.properties.so_trigger_override_lora;
        return true;
    }
    return false;
}

function triggerAssemblyState(node) {
    repairPromptTriggerConnection(node);
    syncTriggerOverrideScope(node);
    const token = String(widget(node, "trigger_token")?.value ?? "TRIGGER");
    const placement = String(widget(node, "trigger_placement")?.value ?? "off");
    const override = String(widget(node, "trigger_override")?.value ?? "").trim();
    const connection = promptConnectedSource(node, "main_trigger");
    const liveValue = promptConnectedTriggerValue(connection);
    const executed = node.__soLastAssembly?.trigger?.value;
    const value = override || (liveValue !== undefined ? String(liveValue) : String(executed ?? ""));
    const matches = aliasesInText(activeAssembledTemplate(node), tokenCandidates(token, "TRIGGER"));
    if (placement === "off") return { used: false, tone: value ? "warning" : "off", label: value ? `Off · ${value}` : "Off", token, value, connection, matches, placement };
    if (!value) return { used: false, tone: "warning", label: connection ? "Waiting for Loader" : "Connect Loader", token, value, connection, matches, placement };
    if (placement === "token" && !matches.length) return { used: false, tone: "warning", label: "Not placed in prompt", token, value, connection, matches, placement };
    const placementLabel = { smart: "Auto", token: "Placeholder", prepend: "Beginning", append: "End" }[placement] || placement;
    const loaderSource = String(connection?.node?.__soMainTriggerSource ?? "");
    const followingLabel = loaderSource.startsWith("user.")
        ? `${placementLabel} · Saved LoRA override ✓`
        : `${placementLabel} · Loader Core · ${value}`;
    return { used: true, tone: "active", label: override ? `Pinned · ${placementLabel} · ${value}` : followingLabel, token, value, connection, matches, placement };
}

function promptReplaceAliases(text, candidates, value) {
    const pattern = aliasPattern(candidates);
    return pattern ? String(text ?? "").replace(pattern, String(value ?? "")) : String(text ?? "");
}

function promptCompactRemovedPlaceholder(text) {
    return String(text ?? "")
        .replace(/[ \t]+([,.;:!?])/g, "$1")
        .replace(/[ \t]{2,}/g, " ");
}

function promptJoinComponentParts(separator, parts) {
    const values = (parts || []).map((part) => String(part ?? "").trim()).filter(Boolean);
    if (!values.length) return "";
    let result = values[0];
    for (const value of values.slice(1)) {
        const joiner = String(separator) === ", " && /[.,;:!?]$/.test(result) ? " " : String(separator);
        result += `${joiner}${value}`;
    }
    return result;
}

function promptSelectedStreamValue(node, base) {
    if (base !== "prompt" && streamUsesManualSource(node, base)) {
        return String(widget(node, streamManualWidget(base))?.value ?? "");
    }
    const lines = node.__soLogLines?.[base] || [];
    if (!lines.length) return "";
    const [, , indexName] = streamConfig(base);
    return String(lines[normalizedIndex(widget(node, indexName)?.value, lines.length)] ?? "");
}

function promptConnectedOrWidgetValue(node, inputName, metadataKey = "") {
    const connection = promptConnectedSource(node, inputName);
    const live = promptConnectedLiveValue(connection);
    if (live !== undefined) return String(live ?? "");
    const previous = metadataKey ? node.__soLastAssembly?.[metadataKey]?.text : undefined;
    if (connection && previous !== undefined) return String(previous ?? "");
    return String(widget(node, inputName)?.value ?? "");
}

function promptApplyCleanupRules(text, rulesText) {
    const rules = [];
    for (const rawLine of String(rulesText ?? "").split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line || line.startsWith("#")) continue;
        const marker = line.indexOf("=>");
        const patternText = (marker >= 0 ? line.slice(0, marker) : line).trim();
        const pythonReplacement = marker >= 0 ? line.slice(marker + 2).trim() : "";
        const replacement = pythonReplacement.replace(/\\([0-9]+)/g, (_match, group) => `$${group}`);
        try { rules.push([new RegExp(patternText, "g"), replacement]); }
        catch (error) {}
    }
    let result = String(text ?? "");
    for (let pass = 0; pass < 20; pass++) {
        const previous = result;
        for (const [pattern, replacement] of rules) {
            pattern.lastIndex = 0;
            result = result.replace(pattern, replacement);
        }
        if (result === previous) break;
    }
    return result.trim();
}

/** Mirror the backend assembly for immediate, honest dashboard feedback. */
function promptLiveResolvedPrompt(node) {
    // Mirror backend order exactly: assemble affixes first, then resolve every
    // component/identity/trigger placeholder across that complete template.
    let assembled = activeAssembledTemplate(node);
    const prepended = [];
    const appended = [];
    const separator = String(widget(node, "prefix_suffix_separator")?.value ?? ", ");

    for (const base of ["outfit_A", "outfit_B", "outfit_C", "scene"]) {
        const placement = String(widget(node, streamPlacementWidget(base))?.value ?? "token");
        const candidates = streamTokenCandidates(node, base);
        const matches = aliasesInText(assembled, candidates);
        const line = promptSelectedStreamValue(node, base).trim();
        if (placement === "off") {
            if (matches.length) assembled = promptCompactRemovedPlaceholder(promptReplaceAliases(assembled, candidates, ""));
        } else if (line && placement === "token" && matches.length) {
            assembled = promptReplaceAliases(assembled, candidates, line);
        } else if (line && placement === "smart") {
            if (matches.length) assembled = promptReplaceAliases(assembled, candidates, line);
            else appended.push(line);
        } else if (line && (placement === "prepend" || placement === "append")) {
            if (matches.length) assembled = promptCompactRemovedPlaceholder(promptReplaceAliases(assembled, candidates, ""));
            (placement === "prepend" ? prepended : appended).push(line);
        }
    }

    const trigger = triggerAssemblyState(node);
    const triggerCandidates = tokenCandidates(trigger.token, "TRIGGER");
    const triggerMatches = aliasesInText(assembled, triggerCandidates);
    if (trigger.placement === "off") {
        if (triggerMatches.length) assembled = promptCompactRemovedPlaceholder(promptReplaceAliases(assembled, triggerCandidates, ""));
    } else if (trigger.value && trigger.placement === "token" && triggerMatches.length) {
        assembled = promptReplaceAliases(assembled, triggerCandidates, trigger.value);
    } else if (trigger.value && trigger.placement === "smart") {
        if (triggerMatches.length) assembled = promptReplaceAliases(assembled, triggerCandidates, trigger.value);
        else prepended.push(trigger.value);
    } else if (trigger.value && (trigger.placement === "prepend" || trigger.placement === "append")) {
        if (triggerMatches.length) assembled = promptCompactRemovedPlaceholder(promptReplaceAliases(assembled, triggerCandidates, ""));
        (trigger.placement === "prepend" ? prepended : appended).push(trigger.value);
    }

    assembled = promptJoinComponentParts(separator, [...prepended, assembled, ...appended]);

    for (const [kind, tokenName, valueName, standard] of [
        ["name", "name_token", "name_value", "NAME"],
        ["item", "item_token", "item_value", "ITEM"],
    ]) {
        const value = substitutionState(node, kind).value;
        const candidates = tokenCandidates(widget(node, tokenName)?.value ?? standard, standard);
        if (value && aliasesInText(assembled, candidates).length) assembled = promptReplaceAliases(assembled, candidates, value);
    }

    return Boolean(widget(node, "cleanup_enabled")?.value)
        ? promptApplyCleanupRules(assembled, widget(node, "cleanup_rules")?.value ?? DEFAULT_CLEANUP)
        : assembled.trim();
}

function promptStatusChip(ctx, x, y, w, h, title, detail, tone = "off") {
    const color = tone === "active" ? SO_CMYKG.green : tone === "warning" ? SO_CMYKG.yellow : "#777782";
    const fill = tone === "active"
        ? "rgba(28,69,48,.42)"
        : tone === "warning" ? "rgba(86,73,24,.34)" : "rgba(31,31,36,.92)";
    promptRoundRect(ctx, x, y, w, h, 7, fill, `${color}77`);
    promptDashText(ctx, title, x + 9, y + h / 2, { color, font: "700 9px Segoe UI, Arial" });
    ctx.save();
    ctx.font = "10px Segoe UI, Arial";
    const shown = promptFit(ctx, detail, Math.max(30, w - 83));
    ctx.restore();
    promptDashText(ctx, shown, x + w - 9, y + h / 2, { align: "right", color: SO_CMYKG.text, font: "10px Segoe UI, Arial" });
}

function promptDrawAssemblySummary(node, ctx, x, y, w) {
    const gap = 6;
    const chipH = 28;
    const chipW = (w - gap * 2) / 3;
    const entries = [
        ["NAME", substitutionState(node, "name"), "name"],
        ["OUTFIT A", streamAssemblyState(node, "outfit_A"), "outfit_A"],
        ["OUTFIT B", streamAssemblyState(node, "outfit_B"), "outfit_B"],
        ["OUTFIT C", streamAssemblyState(node, "outfit_C"), "outfit_C"],
        ["SCENE", streamAssemblyState(node, "scene"), "scene"],
        [configuredPlaceholderLabel(node, "item_token", "ITEM"), substitutionState(node, "item"), "item"],
        ["TRIGGER", triggerAssemblyState(node), "trigger"],
    ];
    entries.forEach(([title, state, key], index) => {
        const row = Math.floor(index / 3);
        const column = index % 3;
        const px = x + column * (chipW + gap);
        const py = y + row * (chipH + gap);
        promptStatusChip(ctx, px, py, chipW, chipH, title, state.label, state.tone);
        if (key === "trigger") {
            promptHit(node, "assembly_trigger", px, py, chipW, chipH, () => promptTriggerBuilder(node));
            return;
        }
        if (["outfit_A", "outfit_B", "outfit_C", "scene", "trigger"].includes(key)) {
            const placementName = streamPlacementWidget(key);
            promptHit(node, `assembly_${key}`, px, py, chipW, chipH, () => promptChoicePopup(
                node,
                `${title} placement`,
                PLACEMENTS,
                key === "trigger" ? (widget(node, "trigger_placement")?.value ?? "off") : (widget(node, placementName)?.value ?? "smart"),
                (value) => promptDashboardSet(node, key === "trigger" ? "trigger_placement" : placementName, value),
                (value) => PLACEMENT_LABELS[value] || value,
            ));
        }
    });
    return chipH * 3 + gap * 2;
}

function promptTokenPalette(node) {
    const item = configuredPlaceholderLabel(node, "item_token", "ITEM");
    return [
        [configuredPlaceholderLabel(node, "name_token", "NAME"), SO_CMYKG.yellow],
        [configuredPlaceholderLabel(node, "outfit_token_A", "OUTFIT_A"), SO_CMYKG.magenta],
        [configuredPlaceholderLabel(node, "outfit_token_B", "OUTFIT_B"), SO_CMYKG.yellow],
        [configuredPlaceholderLabel(node, "outfit_token_C", "OUTFIT_C"), SO_CMYKG.cyan],
        [configuredPlaceholderLabel(node, "scene_token", "SCENE"), SO_CMYKG.green],
        [item, SO_CMYKG.cyan],
        [configuredPlaceholderLabel(node, "trigger_token", "TRIGGER"), "#b89aff"],
    ].filter(([token]) => token);
}

function promptHighlightedText(ctx, node, line, x, y) {
    const palette = promptTokenPalette(node);
    const escaped = palette.map(([token]) => String(token).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((a, b) => b.length - a.length);
    // Prompt substitution is intentionally case-sensitive, so visual feedback
    // must not imply that lowercase prose will be replaced.
    const matcher = escaped.length ? new RegExp(`(\\{?(?:${escaped.join("|")})\\}?)`, "g") : null;
    const parts = matcher ? String(line).split(matcher) : [String(line)];
    let cursor = x;
    for (const part of parts) {
        const bare = String(part).replace(/^\{|\}$/g, "");
        const tone = palette.find(([token]) => String(token) === bare)?.[1] || SO_CMYKG.text;
        ctx.fillStyle = tone;
        ctx.fillText(part, cursor, y);
        cursor += ctx.measureText(part).width;
    }
}

function promptTextCard(node, ctx, x, y, w, h, title, text, color, emptyText = "Nothing to display") {
    promptRoundRect(ctx, x, y, w, h, 9, "rgba(29,29,33,.98)", color ? `${color}80` : SO_CMYKG.outline);
    promptDashText(ctx, title, x + 12, y + 14, { color: color || SO_CMYKG.label, font: "700 10px Segoe UI, Arial" });
    ctx.save();
    ctx.beginPath(); ctx.rect(x + 8, y + 25, w - 16, h - 31); ctx.clip();
    ctx.font = "12px Consolas, monospace";
    const content = String(text ?? "").trim() || emptyText;
    const lines = promptWrap(ctx, content, w - 24);
    const lineH = 15;
    const maxLines = Math.max(1, Math.floor((h - 36) / lineH));
    ctx.textAlign = "left"; ctx.textBaseline = "top";
    for (let i = 0; i < Math.min(lines.length, maxLines); i++) {
        let line = lines[i];
        if (i === maxLines - 1 && lines.length > maxLines && line) line = `${line} …`;
        if (String(text ?? "").trim()) promptHighlightedText(ctx, node, line, x + 12, y + 30 + i * lineH);
        else { ctx.fillStyle = "rgba(255,255,255,.35)"; ctx.fillText(line, x + 12, y + 30 + i * lineH); }
    }
    ctx.restore();
}

function promptHit(node, name, x, y, w, h, callback) {
    node.__soPromptDashboardHits = node.__soPromptDashboardHits || {};
    node.__soPromptDashboardHits[name] = { x, y, w, h, callback };
}

function promptPointIn(pos, hit) {
    return Boolean(hit && pos && pos[0] >= hit.x && pos[0] <= hit.x + hit.w && pos[1] >= hit.y && pos[1] <= hit.y + hit.h);
}

function promptInputName(input) {
    return String(input?.widget?.name ?? input?.name ?? "");
}

function promptAnchorInput(node, name, y) {
    const input = node.inputs?.find((slot) => promptInputName(slot) === String(name));
    if (!input) return;
    // Dashboard rows no longer drag every possible converted widget socket into
    // view. Only our four intentional jack points (plus already-connected legacy
    // sockets) live at the top of the node.
    if (!promptShouldExposeInput(input)) return;
    const anchorY = Number(node.__soPromptInputAnchors?.[String(name)]);
    if (!Number.isFinite(anchorY)) return;
    input.pos = [0, anchorY];
    input.label = PROMPT_FORCE_INPUT_NAMES.includes(name) ? " " : promptExternalInputLabel(node, name);
    input.color_on = SO_CMYKG.green;
    input.color_off = "#7f8792";
}

function promptClearStaleInputAnchors(node) {
    layoutPromptInputSockets(node);
}

function promptDashboardInputAnchor(node, slotIndex) {
    const input = node.inputs?.[Number(slotIndex)];
    if (!input) return null;
    const name = promptInputName(input);
    const y = Number(node.__soPromptInputAnchors?.[name]);
    if (!(CANONICAL_NAMES.includes(name) || PROMPT_FORCE_INPUT_NAMES.includes(name)) || !Number.isFinite(y) || y < 0) return null;
    return { name, y };
}

function promptDashboardSet(node, name, value) {
    const target = widget(node, name);
    if (!target) return;
    target.value = value;
    try { target.callback?.(value); } catch (error) {}
    if (name.includes("index")) {
        const base = STREAM_BASES.find((candidate) => streamConfig(candidate)[2] === name);
        if (base) { resetShuffleBag(node, base); refreshStreamIndexPreview(node, base); }
    }
    if (name.includes("placement")) {
        const base = ["outfit_A", "outfit_B", "outfit_C", "scene"]
            .find((candidate) => streamPlacementWidget(candidate) === name);
        if (base) resetShuffleBag(node, base);
    }
    const componentSourceBase = ["outfit_A", "outfit_B", "outfit_C", "scene"]
        .find((candidate) => streamSourceWidget(candidate) === name);
    if (componentSourceBase) resetShuffleBag(node, componentSourceBase);
    if (name === "prompt_source" || componentSourceBase) {
        layoutPromptDashboard(node, true);
    }
    node.setDirtyCanvas?.(true, true);
}

function promptDashboardToggle(node, name) {
    const target = widget(node, name);
    if (target) promptDashboardSet(node, name, !Boolean(target.value));
}

function closePromptChoicePopup() {
    const root = document.getElementById("so-prompt-dashboard-choice");
    if (root) root.remove();
    if (window.__soPromptChoiceOutside) {
        document.removeEventListener("pointerdown", window.__soPromptChoiceOutside, true);
        window.__soPromptChoiceOutside = null;
    }
    if (window.__soPromptChoiceEscape) {
        document.removeEventListener("keydown", window.__soPromptChoiceEscape, true);
        window.__soPromptChoiceEscape = null;
    }
}

function promptChoicePopup(node, title, values, selected, onChoose, formatter = null) {
    closePromptChoicePopup();
    closePromptLogBrowser();
    ensurePromptBrowserPointerTracker();
    const root = document.createElement("div");
    root.id = "so-prompt-dashboard-choice";
    Object.assign(root.style, {
        position: "fixed", zIndex: "100001", width: "520px", maxWidth: "calc(100vw - 24px)",
        background: "#151519", border: `1px solid ${SO_CMYKG.cyan}99`, borderRadius: "10px",
        boxShadow: `0 14px 42px rgba(0,0,0,.62), 0 0 0 1px ${SO_CMYKG.magenta}22 inset`,
        color: "#f3f3f5", font: "13px Segoe UI, Arial", overflow: "hidden",
    });
    const head = document.createElement("div");
    head.textContent = title;
    Object.assign(head.style, { padding: "10px 12px", fontWeight: "700", borderBottom: `1px solid ${SO_CMYKG.magenta}55` });
    const search = document.createElement("input");
    search.placeholder = `Filter ${String(title).toLowerCase()}`;
    Object.assign(search.style, { boxSizing: "border-box", width: "calc(100% - 20px)", margin: "9px 10px 7px", padding: "7px 9px", background: "#0d0d10", border: `1px solid ${SO_CMYKG.yellow}77`, borderRadius: "5px", color: "#fff", outline: "none" });
    const list = document.createElement("div");
    Object.assign(list.style, { maxHeight: "520px", overflowY: "auto", paddingBottom: "6px" });
    root.append(head, search, list); document.body.append(root);
    const pointer = window.__soBrowserLastPointer || { x: innerWidth / 2, y: 180 };
    root.style.left = `${Math.max(10, Math.min(pointer.x - 20, innerWidth - 540))}px`;
    root.style.top = `${Math.max(10, Math.min(pointer.y + 10, innerHeight - 610))}px`;
    root.addEventListener("pointerdown", (event) => event.stopPropagation());

    const render = () => {
        list.replaceChildren();
        const q = search.value.trim().toLowerCase();
        const filtered = (values || []).filter((value) => {
            const shown = formatter ? formatter(value) : String(value);
            return !q || shown.toLowerCase().includes(q) || String(value).toLowerCase().includes(q);
        });
        for (const value of filtered.slice(0, 400)) {
            const row = document.createElement("div");
            const shown = formatter ? formatter(value) : String(value);
            row.textContent = `${String(value) === String(selected) ? "✓  " : ""}${shown}`;
            Object.assign(row.style, { padding: "8px 12px", cursor: "pointer", borderBottom: "1px solid #29292f", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
            row.addEventListener("mouseenter", () => row.style.background = "rgba(53,215,255,.10)");
            row.addEventListener("mouseleave", () => row.style.background = "transparent");
            row.addEventListener("click", (event) => { event.stopPropagation(); onChoose(value); closePromptChoicePopup(); });
            list.append(row);
        }
        if (!filtered.length) {
            const row = document.createElement("div"); row.textContent = "No matches";
            Object.assign(row.style, { padding: "9px 12px", color: "#888" }); list.append(row);
        }
    };
    search.addEventListener("input", render); render();
    window.__soPromptChoiceEscape = (event) => { if (event.key === "Escape") closePromptChoicePopup(); };
    document.addEventListener("keydown", window.__soPromptChoiceEscape, true);
    window.__soPromptChoiceOutside = (event) => { if (!root.contains(event.target)) closePromptChoicePopup(); };
    setTimeout(() => { document.addEventListener("pointerdown", window.__soPromptChoiceOutside, true); search.focus(); }, 0);
}

function closePromptTriggerBuilder() {
    document.getElementById("so-prompt-trigger-builder")?.remove();
}

function chooseTriggerOverride(node, value, lora = connectedTriggerLora(node)) {
    promptDashboardSet(node, "trigger_override", String(value ?? "").trim());
    node.properties = node.properties || {};
    if (String(value ?? "").trim() && lora) node.properties.so_trigger_override_lora = String(lora);
    else delete node.properties.so_trigger_override_lora;
}

function chooseConnectedTrigger(node) {
    promptDashboardSet(node, "trigger_override", "");
    node.properties = node.properties || {};
    delete node.properties.so_trigger_override_lora;
}

async function writeLoaderTriggerOverride(node, value, lora = connectedTriggerLora(node)) {
    const selected = String(lora ?? "").trim();
    const trigger = String(value ?? "").trim();
    if (!selected) throw new Error("Connect Loader Core and select a Main LoRA first.");
    if (!trigger) throw new Error("Custom trigger cannot be empty.");
    const response = await fetch("/sickollie/studio/loader-core/trigger-override", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lora: selected, trigger }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `HTTP ${response.status}`);
    chooseConnectedTrigger(node);
    await refreshConnectedLoaderTrigger(node, selected, payload);
    return payload;
}

async function clearLoaderTriggerOverride(node, lora = connectedTriggerLora(node)) {
    const selected = String(lora ?? "").trim();
    if (!selected) throw new Error("Connect Loader Core and select a Main LoRA first.");
    const response = await fetch(`/sickollie/studio/loader-core/trigger-override?lora=${encodeURIComponent(selected)}`, { method: "DELETE" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `HTTP ${response.status}`);
    chooseConnectedTrigger(node);
    await refreshConnectedLoaderTrigger(node, selected);
    return payload;
}

async function refreshConnectedLoaderTrigger(node, expectedLora, resolved = null) {
    repairPromptTriggerConnection(node);
    const connection = promptConnectedSource(node, "main_trigger");
    const loader = connection?.node;
    if (!loader || String(widget(loader, "main_lora")?.value ?? "").trim() !== String(expectedLora ?? "").trim()) return "";
    if (typeof loader.__soRefreshMainTrigger === "function") {
        const value = String(await loader.__soRefreshMainTrigger(true) ?? "");
        node.setDirtyCanvas?.(true, true);
        app.graph?.setDirtyCanvas?.(true, true);
        return value;
    }
    let payload = resolved;
    if (!payload?.trigger) {
        const response = await fetch(`/sickollie/studio/loader-core/main-trigger?lora=${encodeURIComponent(String(expectedLora ?? ""))}`);
        payload = await response.json().catch(() => ({}));
        if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `HTTP ${response.status}`);
    }
    return applyConnectedLoaderTrigger(node, loader, payload);
}

function applyConnectedLoaderTrigger(node, loader, payload = {}) {
    if (!loader) return "";
    loader.__soMainTrigger = String(payload?.trigger ?? "");
    loader.__soMainTriggerSource = String(payload?.source ?? "");
    loader.__soLiveOutputs = { ...(loader.__soLiveOutputs || {}), main_trigger: loader.__soMainTrigger };
    if (loader.__soTriggerButton) loader.__soTriggerButton.name = `📋 Copy trigger: ${loader.__soMainTrigger || "none"}`;
    loader.setDirtyCanvas?.(true, true);
    node?.setDirtyCanvas?.(true, true);
    return loader.__soMainTrigger;
}

const TRIGGER_PLACEMENT_OPTIONS = [
    { value: "smart", label: "Auto", help: "Uses the TRIGGER placeholder when it exists; otherwise places the trigger at the beginning of the prompt." },
    { value: "token", label: "Placeholder", help: "Only replaces the TRIGGER placeholder. If the placeholder is absent, the trigger is not inserted." },
    { value: "prepend", label: "Beginning", help: "Always places the trigger before the prompt and removes a TRIGGER placeholder if one is present." },
    { value: "append", label: "End", help: "Always places the trigger after the prompt and removes a TRIGGER placeholder if one is present." },
    { value: "off", label: "Off", help: "Does not inject a trigger. A TRIGGER placeholder in the prompt is removed." },
];

function triggerSourceLabel(source = "") {
    const value = String(source);
    if (value === "modelspec.title") return "model title hint";
    if (value === "modelspec.trigger_phrase") return "embedded trigger phrase";
    if (value === "ss_tag_frequency") return "training tag frequency";
    if (value.startsWith("civitai.")) return "Civitai";
    if (value === "embedded") return "embedded metadata";
    return value || "metadata";
}

async function promptTriggerBuilder(node) {
    closePromptTriggerBuilder(); closePromptChoicePopup(); closePromptLogBrowser();
    repairPromptTriggerConnection(node);
    syncTriggerOverrideScope(node);
    const connection = promptConnectedSource(node, "main_trigger");
    const loader = connection?.node;
    const lora = String(widget(loader, "main_lora")?.value ?? "").trim();
    let automaticCandidate = null;
    if (lora && typeof loader?.__soRefreshMainTrigger === "function") {
        try { await loader.__soRefreshMainTrigger(true); } catch (error) {}
    }

    const root = document.createElement("div"); root.id = "so-prompt-trigger-builder";
    Object.assign(root.style, { position: "fixed", zIndex: "100003", inset: "0", background: "rgba(0,0,0,.64)", display: "flex", alignItems: "center", justifyContent: "center", padding: "22px" });
    const card = document.createElement("div");
    Object.assign(card.style, { width: "780px", maxWidth: "96vw", maxHeight: "90vh", overflow: "auto", background: "#151519", border: `1px solid ${SO_CMYKG.magenta}bb`, borderRadius: "12px", boxShadow: "0 18px 60px rgba(0,0,0,.7)", color: "#f3f3f5", font: "13px Segoe UI, Arial" });
    const header = document.createElement("div"); header.textContent = "TRIGGER SETUP";
    Object.assign(header.style, { padding: "13px 15px", fontWeight: "800", color: SO_CMYKG.magenta, borderBottom: `1px solid ${SO_CMYKG.cyan}55`, letterSpacing: ".03em" });
    const detail = document.createElement("div");
    detail.textContent = lora ? `Main LoRA: ${lora}` : "Connect Loader Core → main_trigger to follow the selected Main LoRA.";
    Object.assign(detail.style, { padding: "10px 15px", color: "#b8b8c0", borderBottom: "1px solid #2b2b31" });

    const sourceSection = document.createElement("section");
    Object.assign(sourceSection.style, { padding: "12px", borderBottom: "1px solid #2b2b31" });
    const sourceHeading = document.createElement("div"); sourceHeading.textContent = "TRIGGER SOURCE";
    Object.assign(sourceHeading.style, { color: SO_CMYKG.cyan, fontWeight: "800", fontSize: "11px", letterSpacing: ".06em", marginBottom: "8px" });
    const sourceStatus = document.createElement("div");
    Object.assign(sourceStatus.style, { padding: "10px 11px", borderRadius: "8px", border: "1px solid #3d3d45", background: "#1b1b20", marginBottom: "8px", lineHeight: "1.35" });
    const sourceActions = document.createElement("div"); Object.assign(sourceActions.style, { display: "flex", gap: "7px", flexWrap: "wrap", alignItems: "center" });
    const followLoader = document.createElement("button"); followLoader.textContent = "Follow Loader Core";
    Object.assign(followLoader.style, { padding: "8px 11px", borderRadius: "7px", border: `1px solid ${SO_CMYKG.green}aa`, background: "#25252a", color: "#fff", cursor: connection ? "pointer" : "default", opacity: connection ? "1" : ".45", fontWeight: "700" });
    followLoader.disabled = !connection;
    sourceActions.append(followLoader);
    sourceSection.append(sourceHeading, sourceStatus, sourceActions);

    const renderSourceStatus = () => {
        repairPromptTriggerConnection(node);
        syncTriggerOverrideScope(node);
        const override = String(widget(node, "trigger_override")?.value ?? "").trim();
        const currentConnection = promptConnectedSource(node, "main_trigger");
        const connectedLive = promptConnectedTriggerValue(currentConnection);
        const live = loader && Object.prototype.hasOwnProperty.call(loader, "__soMainTrigger")
            ? loader.__soMainTrigger
            : connectedLive;
        const loaderSource = String(loader?.__soMainTriggerSource ?? automaticCandidate?.source ?? "");
        const automatic = automaticCandidate?.suggested || automaticCandidate?.raw || "";
        sourceStatus.replaceChildren();
        const title = document.createElement("div");
        const value = document.createElement("div");
        const note = document.createElement("div");
        Object.assign(title.style, { fontWeight: "800", color: override ? SO_CMYKG.yellow : SO_CMYKG.green, marginBottom: "2px" });
        Object.assign(value.style, { color: "#f5f5f7", fontWeight: "650" });
        Object.assign(note.style, { color: "#92929b", fontSize: "11px", marginTop: "3px" });
        const following = Boolean(currentConnection) && !override;
        followLoader.textContent = following ? "✓ Following Loader Core · ON" : "Follow Loader Core";
        followLoader.setAttribute("aria-pressed", following ? "true" : "false");
        followLoader.style.borderColor = following ? `${SO_CMYKG.green}ee` : `${SO_CMYKG.green}88`;
        followLoader.style.background = following ? "rgba(28,69,48,.64)" : "#25252a";
        followLoader.style.color = following ? "#eafff2" : "#fff";
        if (override) {
            title.textContent = "Pinned for this LoRA";
            value.textContent = override;
            note.textContent = "This manual choice resets automatically when the connected Main LoRA changes.";
        } else {
            title.textContent = "Following Loader Core";
            value.textContent = String(live ?? automatic ?? "").trim() || "No automatic trigger detected";
            note.textContent = connection
                ? (loaderSource.startsWith("user.")
                    ? `Connected through ${currentConnection?.label || "Loader Core → main_trigger"}. Using this LoRA's saved override; switching the Main LoRA loads that LoRA's own override.`
                    : `Connected through ${currentConnection?.label || "Loader Core → main_trigger"}. Switching the Main LoRA resolves its own automatic trigger or saved override.`)
                : "Connect Loader Core → main_trigger to use dynamic trigger detection.";
        }
        sourceStatus.append(title, value, note);
    };
    // Source selection and LoRA override storage are independent. Following
    // Loader Core must never delete a per-LoRA override.
    followLoader.onclick = async () => {
        chooseConnectedTrigger(node);
        repairPromptTriggerConnection(node);
        followLoader.disabled = true;
        followLoader.textContent = "Refreshing Loader Core…";
        try {
            if (lora) await refreshConnectedLoaderTrigger(node, lora);
        } catch (error) {
            console.warn("[Sick Ollie Prompt Core] Could not refresh Loader Core's trigger", error);
        } finally {
            followLoader.disabled = !connection;
            renderSourceStatus();
        }
    };

    const placementSection = document.createElement("section");
    Object.assign(placementSection.style, { padding: "12px", borderBottom: "1px solid #2b2b31", background: "rgba(255,255,255,.012)" });
    const placementHeading = document.createElement("div"); placementHeading.textContent = "PLACEMENT";
    Object.assign(placementHeading.style, { color: SO_CMYKG.magenta, fontWeight: "800", fontSize: "11px", letterSpacing: ".06em", marginBottom: "8px" });
    const placementButtonsWrap = document.createElement("div"); Object.assign(placementButtonsWrap.style, { display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap" });
    const placementHelp = document.createElement("div"); Object.assign(placementHelp.style, { color: "#9898a1", fontSize: "11px", lineHeight: "1.35", marginTop: "8px" });
    const placementButtons = new Map();
    const refreshPlacementButtons = () => {
        const current = String(widget(node, "trigger_placement")?.value ?? "off");
        for (const option of TRIGGER_PLACEMENT_OPTIONS) {
            const button = placementButtons.get(option.value);
            const active = option.value === current;
            button.style.borderColor = active ? `${SO_CMYKG.green}dd` : "#4a4a50";
            button.style.background = active ? "rgba(28,69,48,.55)" : "#222227";
            button.style.color = active ? "#eafff2" : "#d6d6da";
            if (active) placementHelp.textContent = option.help;
        }
    };
    for (const option of TRIGGER_PLACEMENT_OPTIONS) {
        const button = document.createElement("button"); button.textContent = option.label;
        Object.assign(button.style, { padding: "7px 9px", borderRadius: "6px", border: "1px solid #4a4a50", background: "#222227", color: "#d6d6da", cursor: "pointer", fontSize: "11px", fontWeight: "650" });
        button.onclick = () => { promptDashboardSet(node, "trigger_placement", option.value); refreshPlacementButtons(); };
        placementButtons.set(option.value, button); placementButtonsWrap.append(button);
    }
    placementSection.append(placementHeading, placementButtonsWrap, placementHelp);
    refreshPlacementButtons();

    const candidateSection = document.createElement("section"); Object.assign(candidateSection.style, { padding: "12px" });
    const candidateHeading = document.createElement("div"); candidateHeading.textContent = "DETECTED FOR THIS LORA";
    Object.assign(candidateHeading.style, { color: SO_CMYKG.cyan, fontWeight: "800", fontSize: "11px", letterSpacing: ".06em", marginBottom: "8px" });
    const list = document.createElement("div"); list.textContent = lora ? "Checking embedded metadata and Civitai candidates…" : "No connected Main LoRA yet.";
    Object.assign(list.style, { marginBottom: "10px" });

    const overrideHeading = document.createElement("div"); overrideHeading.textContent = "SAVED OVERRIDE FOR THIS LORA";
    Object.assign(overrideHeading.style, { color: SO_CMYKG.magenta, fontWeight: "800", fontSize: "11px", letterSpacing: ".06em", marginTop: "12px", paddingTop: "12px", borderTop: "1px solid #2b2b31" });
    const overrideHelp = document.createElement("div");
    overrideHelp.textContent = "This replaces Loader Core's detected trigger for this LoRA only. Prompt Core can keep following Loader Core while each LoRA remembers its own value.";
    Object.assign(overrideHelp.style, { color: "#92929b", fontSize: "11px", lineHeight: "1.35", marginTop: "5px" });
    const customRow = document.createElement("div"); Object.assign(customRow.style, { display: "grid", gridTemplateColumns: "minmax(0,1fr) auto auto", gap: "7px", marginTop: "9px" });
    const customInput = document.createElement("input"); customInput.type = "text"; customInput.placeholder = "Custom trigger for this LoRA";
    Object.assign(customInput.style, { minWidth: "0", padding: "8px 9px", borderRadius: "7px", border: "1px solid #494951", background: "#0f0f13", color: "#fff", outline: "none" });
    const customUse = document.createElement("button"); customUse.textContent = "Save LoRA override";
    Object.assign(customUse.style, { padding: "8px 11px", borderRadius: "7px", border: `1px solid ${SO_CMYKG.yellow}88`, background: "#25252a", color: "#fff", cursor: "pointer", fontWeight: "700" });
    const customClear = document.createElement("button"); customClear.textContent = "Clear override";
    Object.assign(customClear.style, { padding: "8px 11px", borderRadius: "7px", border: `1px solid ${SO_CMYKG.magenta}66`, background: "#25252a", color: "#fff", cursor: "pointer", fontWeight: "700", display: "none" });
    const refreshOverrideControls = () => {
        const source = String(loader?.__soMainTriggerSource ?? automaticCandidate?.source ?? "");
        customClear.style.display = source.startsWith("user.") ? "inline-block" : "none";
    };
    const useLoaderOverride = async (value) => {
        const trigger = String(value ?? "").trim();
        if (!trigger) return;
        customUse.disabled = true;
        customUse.textContent = "Saving…";
        try {
            await writeLoaderTriggerOverride(node, trigger, lora);
            automaticCandidate = { suggested: trigger, raw: trigger, source: "user.override", pinned: true };
            customInput.value = trigger;
            renderSourceStatus();
            refreshOverrideControls();
        } catch (error) {
            alert(error.message || "Could not save the Loader Core trigger override.");
        } finally {
            customUse.disabled = false;
            customUse.textContent = "Save LoRA override";
        }
    };
    customUse.onclick = () => useLoaderOverride(customInput.value);
    customClear.onclick = async () => {
        customClear.disabled = true;
        customClear.textContent = "Clearing…";
        try {
            await clearLoaderTriggerOverride(node, lora);
            automaticCandidate = {
                suggested: String(loader?.__soMainTrigger ?? ""),
                raw: String(loader?.__soMainTrigger ?? ""),
                source: String(loader?.__soMainTriggerSource ?? ""),
            };
            customInput.value = "";
            renderSourceStatus();
            refreshOverrideControls();
        } catch (error) {
            alert(error.message || "Could not clear the saved Loader Core trigger override.");
        } finally {
            customClear.disabled = false;
            customClear.textContent = "Clear override";
        }
    };
    customInput.addEventListener("keydown", event => { if (event.key === "Enter") customUse.click(); });
    customRow.append(customInput, customUse, customClear);
    candidateSection.append(candidateHeading, list, overrideHeading, overrideHelp, customRow);

    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "12px", borderTop: "1px solid #2b2b31" });
    const close = document.createElement("button"); close.textContent = "Done";
    Object.assign(close.style, { padding: "8px 12px", borderRadius: "6px", border: "1px solid #555", background: "#25252a", color: "#fff", cursor: "pointer" });
    close.onclick = closePromptTriggerBuilder; footer.append(close);
    card.append(header, detail, sourceSection, placementSection, candidateSection, footer); root.append(card); document.body.append(root);
    root.addEventListener("pointerdown", event => { if (event.target === root) closePromptTriggerBuilder(); });
    renderSourceStatus();

    if (!lora) return;
    try {
        const response = await fetch(`/sickollie/studio/loader-core/trigger-candidates?lora=${encodeURIComponent(lora)}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const payload = await response.json();
        const candidates = Array.isArray(payload?.candidates) ? payload.candidates : [];
        automaticCandidate = payload?.active && typeof payload.active === "object"
            ? payload.active
            : (payload?.automatic && typeof payload.automatic === "object" ? payload.automatic : null);
        if (String(automaticCandidate?.source ?? "").startsWith("user.")) {
            customInput.value = String(automaticCandidate?.suggested || automaticCandidate?.raw || "");
        }
        renderSourceStatus();
        refreshOverrideControls();
        list.replaceChildren();
        if (!candidates.length) {
            const empty = document.createElement("div"); empty.textContent = "No explicit trigger candidates were found for this LoRA.";
            Object.assign(empty.style, { color: "#9999a2", padding: "7px 2px" }); list.append(empty); return;
        }
        const grouped = new Map();
        for (const candidate of candidates) {
            const value = String(candidate.suggested || candidate.raw || "").trim();
            if (!value) continue;
            const key = value.toLocaleLowerCase();
            if (!grouped.has(key)) grouped.set(key, { value, candidates: [] });
            grouped.get(key).candidates.push(candidate);
        }
        for (const group of grouped.values()) {
            const reliable = group.candidates.some(candidate => !(candidate.flags || []).includes("identity-only"));
            const auto = group.candidates.some(candidate => candidate.auto_select);
            const sources = [...new Set(group.candidates.map(candidate => triggerSourceLabel(candidate.source)))];
            const flags = [...new Set(group.candidates.flatMap(candidate => Array.isArray(candidate.flags) ? candidate.flags : []))];
            const row = document.createElement("button");
            row.type = "button";
            Object.assign(row.style, { display: "block", width: "100%", textAlign: "left", padding: "10px 11px", marginBottom: "6px", borderRadius: "8px", border: `1px solid ${reliable ? (auto ? SO_CMYKG.green : SO_CMYKG.yellow) : "#55545c"}77`, background: reliable ? (auto ? "rgba(28,69,48,.32)" : "rgba(86,73,24,.24)") : "rgba(45,45,50,.45)", color: reliable ? "#f3f3f5" : "#9a9aa3", cursor: reliable ? "pointer" : "default" });
            const valueLine = document.createElement("div"); valueLine.textContent = group.value;
            Object.assign(valueLine.style, { fontWeight: "750", color: reliable ? "#f6f6f8" : "#aaaab2" });
            const sourceLine = document.createElement("div");
            const extraFlags = flags.filter(flag => flag !== "identity-only");
            sourceLine.textContent = reliable
                ? `${sources.join(" + ")}${extraFlags.length ? ` · ${extraFlags.join(", ")}` : ""}`
                : `${sources.join(" + ")} · identity hint, not used as an activation trigger`;
            Object.assign(sourceLine.style, { marginTop: "2px", fontSize: "10px", color: reliable ? "#9d9da6" : "#74747c" });
            row.append(valueLine, sourceLine);
            row.title = reliable ? "Pin this trigger for the current Main LoRA." : "Model title metadata is shown as context only.";
            if (reliable) row.onclick = () => useLoaderOverride(group.value);
            list.append(row);
        }
    } catch (error) {
        list.textContent = `Could not load trigger candidates: ${error.message}`;
    }
}

function closePromptTextEditor() {
    const root = document.getElementById("so-prompt-dashboard-editor");
    if (root) root.remove();
}

function promptTextEditor(node, title, widgetName, multiline = true) {
    closePromptTextEditor(); closePromptChoicePopup(); closePromptLogBrowser();
    const target = widget(node, widgetName); if (!target) return;
    const root = document.createElement("div"); root.id = "so-prompt-dashboard-editor";
    Object.assign(root.style, { position: "fixed", zIndex: "100002", inset: "0", background: "rgba(0,0,0,.55)", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" });
    const card = document.createElement("div");
    Object.assign(card.style, { width: multiline ? "760px" : "560px", maxWidth: "95vw", background: "#151519", border: `1px solid ${SO_CMYKG.magenta}aa`, borderRadius: "12px", boxShadow: `0 18px 60px rgba(0,0,0,.7), 0 0 0 1px ${SO_CMYKG.cyan}22 inset`, overflow: "hidden" });
    const header = document.createElement("div"); header.textContent = title;
    Object.assign(header.style, { padding: "12px 14px", font: "700 14px Segoe UI, Arial", color: "#f4f4f5", borderBottom: `1px solid ${SO_CMYKG.yellow}55` });
    const input = multiline ? document.createElement("textarea") : document.createElement("input");
    input.value = String(target.value ?? "");
    Object.assign(input.style, { boxSizing: "border-box", width: "calc(100% - 24px)", margin: "12px", minHeight: multiline ? "360px" : "38px", resize: multiline ? "vertical" : "none", padding: "10px 11px", background: "#0d0d10", color: "#f4f4f5", border: `1px solid ${SO_CMYKG.cyan}77`, borderRadius: "7px", outline: "none", font: multiline ? "13px Consolas, monospace" : "13px Segoe UI, Arial" });
    let toolbar = null;
    if (widgetName === "manual_prompt" && multiline) {
        toolbar = document.createElement("div");
        Object.assign(toolbar.style, { display: "flex", flexWrap: "wrap", gap: "6px", padding: "10px 12px 0" });
        const insertions = [
            ["NAME", "name_token", "NAME"],
            ["OUTFIT A", "outfit_token_A", "OUTFIT_A"],
            ["OUTFIT B", "outfit_token_B", "OUTFIT_B"],
            ["OUTFIT C", "outfit_token_C", "OUTFIT_C"],
            ["SCENE", "scene_token", "SCENE"],
            ["ITEM", "item_token", "ITEM"],
            ["TRIGGER", "trigger_token", "TRIGGER"],
        ];
        for (const [label, tokenWidgetName, fallback] of insertions) {
            const button = document.createElement("button");
            const configured = String(widget(node, tokenWidgetName)?.value ?? fallback).trim() || fallback;
            const configuredLabel = configured.startsWith("{") && configured.endsWith("}")
                ? configured.slice(1, -1).trim()
                : configured;
            button.textContent = `+ ${configuredLabel || label}`;
            Object.assign(button.style, { padding: "6px 9px", borderRadius: "6px", border: `1px solid ${SO_CMYKG.cyan}66`, background: "#24242a", color: "#f4f4f5", cursor: "pointer", font: "700 10px Segoe UI, Arial" });
            button.onclick = () => {
                const raw = String(widget(node, tokenWidgetName)?.value ?? fallback).trim() || fallback;
                const bare = raw.startsWith("{") && raw.endsWith("}") ? raw.slice(1, -1).trim() : raw;
                const token = `{${bare}}`;
                const start = Number.isFinite(input.selectionStart) ? input.selectionStart : input.value.length;
                const end = Number.isFinite(input.selectionEnd) ? input.selectionEnd : start;
                const before = input.value.slice(0, start);
                const after = input.value.slice(end);
                const left = before && !/\s$/.test(before) ? " " : "";
                const right = after && !/^[\s,.;:!?]/.test(after) ? " " : "";
                input.value = `${before}${left}${token}${right}${after}`;
                const caret = before.length + left.length + token.length + right.length;
                input.focus();
                input.setSelectionRange(caret, caret);
            };
            toolbar.append(button);
        }
    }
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 12px 12px" });
    const cancel = document.createElement("button"); cancel.textContent = "Cancel";
    const save = document.createElement("button"); save.textContent = "Save";
    for (const btn of [cancel, save]) Object.assign(btn.style, { padding: "8px 16px", borderRadius: "6px", border: "1px solid #555", background: "#25252a", color: "#fff", cursor: "pointer" });
    save.style.borderColor = `${SO_CMYKG.green}aa`; save.style.background = "rgba(52,105,73,.7)";
    cancel.onclick = () => closePromptTextEditor();
    save.onclick = () => { promptDashboardSet(node, widgetName, input.value); closePromptTextEditor(); };
    root.addEventListener("pointerdown", (event) => { if (event.target === root) closePromptTextEditor(); });
    input.addEventListener("keydown", (event) => { if ((event.ctrlKey || event.metaKey) && event.key === "Enter") save.click(); if (event.key === "Escape") closePromptTextEditor(); });
    footer.append(cancel, save);
    card.append(header);
    if (toolbar) card.append(toolbar);
    card.append(input, footer);
    root.append(card); document.body.append(root); setTimeout(() => input.focus(), 0);
}

async function promptCopyValue(node, key, value) {
    const text = String(value ?? "").trim(); if (!text) return;
    let ok = false;
    try { await navigator.clipboard.writeText(text); ok = true; } catch (error) {}
    if (!ok) return;
    try { if (navigator?.vibrate) navigator.vibrate(12); } catch (error) {}
    node.__soPromptCopyFlash = key;
    node.setDirtyCanvas?.(true, true);
    clearTimeout(node.__soPromptCopyTimer);
    node.__soPromptCopyTimer = setTimeout(() => { node.__soPromptCopyFlash = ""; node.setDirtyCanvas?.(true, true); }, 850);
}

function promptLogDisplay(node, base) {
    const [fileName] = streamConfig(base);
    const value = String(widget(node, fileName)?.value ?? NO_FILE);
    if (!value || value === NO_FILE) return "[None]";
    const collection = collectionLogDisplay(node, base, value);
    if (collection) return collection;
    const relative = logRelativeFile(base, value);
    return relative || value;
}

function promptStreamLine(node, base) {
    const lines = node.__soLogLines?.[base] || [];
    const [, , indexName] = streamConfig(base);
    if (!lines.length) return "[no usable lines]";
    return String(lines[normalizedIndex(widget(node, indexName)?.value, lines.length)] ?? "");
}

function promptStreamIndexLabel(node, base) {
    const lines = node.__soLogLines?.[base] || [];
    const [, , indexName] = streamConfig(base);
    const index = lines.length ? normalizedIndex(widget(node, indexName)?.value, lines.length) : 0;
    return `${index} · ${lines.length} ${lines.length === 1 ? "line" : "lines"}`;
}

function promptOpenIndexChoice(node, base) {
    const lines = node.__soLogLines?.[base] || [];
    if (!lines.length) return;
    const [, , indexName] = streamConfig(base);
    const values = lines.map((_, index) => index);
    const current = normalizedIndex(widget(node, indexName)?.value, lines.length);
    promptChoicePopup(node, `${logBrowserLabel(base)} index · ${lines.length} lines`, values, current, (value) => promptDashboardSet(node, indexName, Number(value)), (value) => previewChoice(Number(value), lines[Number(value)]));
}

function promptDrawStreamCard(node, ctx, base, x, y, w, accent, hitPrefix) {
    const h = 112;
    const [fileName, modeName, indexName] = streamConfig(base);
    const tokenName = streamTokenWidget(base);
    const placementName = streamPlacementWidget(base);
    promptAnchorInput(node, tokenName, y + 39);
    promptAnchorInput(node, placementName, y + 39);
    promptAnchorInput(node, fileName, y + 68);
    promptAnchorInput(node, modeName, y + 97);
    promptAnchorInput(node, indexName, y + 97);
    promptAnchorInput(node, streamSourceWidget(base), y + 68);
    promptAnchorInput(node, streamManualWidget(base), y + 68);
    promptRoundRect(ctx, x, y, w, h, 9, "rgba(25,25,29,.98)", `${accent}88`);
    const token = String(widget(node, tokenName)?.value ?? (base === "scene" ? "SCENE" : base.replace("outfit_", "OUTFIT_")));
    const title = base === "scene" ? "SCENE" : base.replace("outfit_", "OUTFIT ").toUpperCase();
    const state = streamAssemblyState(node, base);
    const statusColor = state.tone === "active" ? SO_CMYKG.green : state.tone === "warning" ? SO_CMYKG.yellow : SO_CMYKG.label;
    promptDashText(ctx, title, x + 12, y + 14, { color: accent, font: "700 10px Segoe UI, Arial" });
    ctx.save(); ctx.font = "10px Segoe UI, Arial";
    const status = promptFit(ctx, state.label, Math.min(330, w * .48));
    ctx.restore();
    promptDashText(ctx, status, x + w - 12, y + 14, { align: "right", color: statusColor, font: "10px Segoe UI, Arial" });

    const innerX = x + 8;
    const innerW = w - 16;
    const gap = 6;
    const placementW = Math.min(300, innerW * .42);
    const tokenW = innerW - placementW - gap;
    const controlY = y + 26;
    const placement = String(widget(node, placementName)?.value ?? "smart");
    promptValueRow(ctx, innerX, controlY, placementW, 25, "Placement", PLACEMENT_SHORT_LABELS[placement] || placement, { stroke: `${accent}44` });
    promptValueRow(ctx, innerX + placementW + gap, controlY, tokenW, 25, "Placeholder ✎", token, { stroke: `${accent}44`, chevron: false });
    promptHit(node, `${hitPrefix}_placement`, innerX, controlY, placementW, 25, () => promptChoicePopup(node, `${title} placement`, PLACEMENTS, placement, (value) => promptDashboardSet(node, placementName, value), (value) => PLACEMENT_LABELS[value] || value));
    promptHit(node, `${hitPrefix}_token_edit`, innerX + placementW + gap, controlY, tokenW, 25, () => promptTextEditor(node, `${title} placeholder`, tokenName, false));

    const fileY = controlY + 29;
    const sourceName = streamSourceWidget(base);
    const manualName = streamManualWidget(base);
    const source = String(widget(node, sourceName)?.value ?? "log") === "manual" ? "manual" : "log";
    const sourceW = Math.min(190, (w - 16) * .28);
    const sourceValueW = w - 16 - sourceW - gap;
    promptValueRow(ctx, x + 8, fileY, sourceW, 25, "Source", source === "manual" ? "Manual" : "Log", { stroke: `${accent}44` });
    promptValueRow(ctx, x + 8 + sourceW + gap, fileY, sourceValueW, 25, source === "manual" ? "Manual value ✎" : "Log", source === "manual" ? String(widget(node, manualName)?.value ?? "") : promptLogDisplay(node, base), { stroke: `${accent}44`, chevron: source !== "manual" });
    promptHit(node, `${hitPrefix}_source`, x + 8, fileY, sourceW, 25, () => promptChoicePopup(node, `${title} source`, ["manual", "log"], source, (value) => promptDashboardSet(node, sourceName, value), (value) => value === "manual" ? "Manual value" : "Outfit / Scene log"));
    promptHit(node, `${hitPrefix}_source_value`, x + 8 + sourceW + gap, fileY, sourceValueW, 25, () => {
        if (source === "manual") promptTextEditor(node, `${title} manual value`, manualName, false);
        else { closePromptChoicePopup(); openPromptLogBrowser(node, base); }
    });

    const bottomY = fileY + 29;
    if (source === "manual") {
        promptValueRow(ctx, x + 8, bottomY, w - 16, 25, "Manual value", "Stays fixed while the Prompt Log cycles", { chevron: false, stroke: `${accent}33` });
    } else {
        const half = (w - 16 - gap) / 2;
        promptValueRow(ctx, x + 8, bottomY, half, 25, "Mode", widget(node, modeName)?.value ?? "fixed");
        promptValueRow(ctx, x + 8 + half + gap, bottomY, half, 25, "Index", promptStreamIndexLabel(node, base));
        promptHit(node, `${hitPrefix}_mode`, x + 8, bottomY, half, 25, () => promptChoicePopup(node, `${title} mode`, MODES, widget(node, modeName)?.value, (value) => promptDashboardSet(node, modeName, value)));
        promptHit(node, `${hitPrefix}_index`, x + 8 + half + gap, bottomY, half, 25, () => promptOpenIndexChoice(node, base));
    }
    return h;
}

function drawPromptExternalInputs(node, ctx, x, y, w) {
    // Keep these intentionally simple, matching Comfy's classic socket labels:
    // the actual graph socket remains native, while we draw the readable label.
    const inputs = promptExternalInputs(node);
    if (!inputs.length) return 0;

    for (const input of inputs) {
        const name = promptInputName(input);
        const anchorY = Number(node.__soPromptInputAnchors?.[name]);
        if (!Number.isFinite(anchorY) || anchorY < 0) continue;

        const connected = promptInputIsConnected(input);
        promptDashText(ctx, promptExternalInputLabel(node, name), x + 2, anchorY, {
            color: connected ? SO_CMYKG.green : "#a8a8b2",
            font: connected ? "700 11px Segoe UI, Arial" : "11px Segoe UI, Arial",
            baseline: "middle",
        });
    }
    return inputs.length * 21;
}

function drawPromptDashboard(node, ctx) {
    if (!node.__soPromptDashboardReady || node.flags?.collapsed) return;
    syncExternalManualPrompt(node);
    node.__soPromptDashboardHits = {};
    const top = promptDashTop(node);
    let x = PROMPT_DASH_PAD;
    const fullW = node.size[0] - PROMPT_DASH_PAD * 2;
    let w = fullW;
    const gap = PROMPT_DASH_GAP;
    const rowH = PROMPT_DASH_ROW_H;
    layoutPromptInputSockets(node);
    let y = promptSourceTop(node);
    ctx.save();

    // Labels for the small native input sockets at the upper-left.
    drawPromptExternalInputs(node, ctx, 12, 0, node.size[0] - 24);

    const libraryX = x + 12;
    const libraryW = w - 24;
    const libraryY = y - PROMPT_LIBRARY_HEIGHT - PROMPT_LIBRARY_BOTTOM_PAD;
    const libraryPressed = Number(node.__soCreativeLibraryPressUntil || 0) > Date.now();
    const libraryHover = Boolean(node.__soCreativeLibraryHover);
    const faceY = libraryY + (libraryPressed ? 3 : 0);
    const border = ctx.createLinearGradient(libraryX, 0, libraryX + libraryW, 0);
    border.addColorStop(0, SO_CMYKG.cyan);
    border.addColorStop(.5, "#b79aff");
    border.addColorStop(1, SO_CMYKG.magenta);
    const face = ctx.createLinearGradient(libraryX, faceY, libraryX + libraryW, faceY + PROMPT_LIBRARY_HEIGHT);
    face.addColorStop(0, libraryHover || libraryPressed ? "#204b60" : "#193547");
    face.addColorStop(.5, libraryHover || libraryPressed ? "#393458" : "#29253d");
    face.addColorStop(1, libraryHover || libraryPressed ? "#652a53" : "#48213d");
    promptRoundRect(ctx, libraryX, libraryY + 5, libraryW, PROMPT_LIBRARY_HEIGHT, 12, "#08060e", "#553451", 1.5);
    promptRoundRect(ctx, libraryX, faceY, libraryW, PROMPT_LIBRARY_HEIGHT, 12, face, border, libraryHover ? 2.5 : 1.8);
    promptRoundRect(ctx, libraryX + 3, faceY + 3, libraryW - 6, PROMPT_LIBRARY_HEIGHT - 6, 9, null, "rgba(255,255,255,.1)");
    for (let index = 0; index < 3; index++) {
        promptRoundRect(ctx, libraryX + 22 + index * 8, faceY + 19 - index * 2, 5, 23 + index * 2, 1.5,
            [SO_CMYKG.cyan, "#b79aff", SO_CMYKG.magenta][index]);
    }
    promptDashText(ctx, "OPEN CREATIVE LIBRARY", libraryX + libraryW / 2, faceY + 23, { align: "center", color: "#ffffff", font: "800 14px Segoe UI, Arial" });
    promptDashText(ctx, "Templates · Prompts · Outfits · Scenes", libraryX + libraryW / 2, faceY + 43, { align: "center", color: "#d5cde6", font: "11px Segoe UI, Arial" });
    promptRoundRect(ctx, libraryX + libraryW - 52, faceY + 14, 32, 32, 8, "rgba(255,74,184,.16)", `${SO_CMYKG.magenta}aa`);
    promptDashText(ctx, "↗", libraryX + libraryW - 36, faceY + 30, { align: "center", color: "#ffabe0", font: "700 21px Segoe UI, Arial" });
    promptHit(node, "creative_library", libraryX, libraryY, libraryW, PROMPT_LIBRARY_HEIGHT + 5, () => {
        node.__soCreativeLibraryPressUntil = Date.now() + 160;
        node.setDirtyCanvas?.(true, true);
        setTimeout(() => node.setDirtyCanvas?.(true, true), 180);
        try { navigator.vibrate?.(18); } catch (error) {}
        closePromptChoicePopup();
        if (typeof window.__soOpenCreativeLibrary === "function") window.__soOpenCreativeLibrary();
        else window.dispatchEvent(new CustomEvent("sickollie:open-creative-library"));
    });

    const sourceTop = y;

    // The socket bay lives above this point. From Prompt Source downward the
    // dashboard is one cohesive full-width surface again.
    const lowerTop = promptLowerStart(node);
    const sourceFrame = promptSourceFrameGeometry(sourceTop, lowerTop);
    promptRoundRect(ctx, x - 3, sourceFrame.top, w + 6, sourceFrame.height, 11, "rgba(9,9,12,.52)", null);
    promptGradientFrame(ctx, x - 3, sourceFrame.top, w + 6, sourceFrame.height, 11, .48, SO_CMYKG.cyan);
    promptRoundRect(ctx, PROMPT_DASH_PAD - 3, lowerTop - 5, fullW + 6, promptLowerHeight(node) + 10, 11, "rgba(9,9,12,.52)", null);
    promptGradientFrame(ctx, PROMPT_DASH_PAD - 3, lowerTop - 5, fullW + 6, promptLowerHeight(node) + 10, 11, .48, SO_CMYKG.magenta);

    promptSection(ctx, "Prompt Source", x + 2, y + 8, SO_CMYKG.cyan); y += 19;
    const externalPromptState = externalManualPromptState(node);
    const rawSourceMode = String(widget(node, "prompt_source")?.value ?? "manual");
    const sourceMode = MAIN_PROMPT_SOURCES.includes(rawSourceMode) ? rawSourceMode : "manual";
    const sourceLabel = sourceMode === "log" ? "Prompt Log" : (sourceMode === "input" ? "Prompt Input" : "Manual");
    const formatPromptSource = (value) => value === "log" ? "Prompt Log" : (value === "input" ? "Prompt Input" : "Manual");
    promptAnchorInput(node, "prompt_source", y + 16);
    const modeW = Math.min(170, w * .28); const sourceRowW = w - modeW - gap;
    if (sourceMode === "log") {
        promptValueRow(ctx, x, y, modeW, rowH, "Source", sourceLabel);
        promptHit(node, "source_mode", x, y, modeW, rowH, () => promptChoicePopup(node, "Prompt source", MAIN_PROMPT_SOURCES, sourceMode, (value) => promptDashboardSet(node, "prompt_source", value), formatPromptSource));
        promptValueRow(ctx, x + modeW + gap, y, sourceRowW, rowH, "Prompt log", promptLogDisplay(node, "prompt"), { stroke: `${SO_CMYKG.cyan}66` });
        promptAnchorInput(node, "prompt_log_file", y + rowH / 2);
        promptHit(node, "prompt_file", x + modeW + gap, y, sourceRowW, rowH, () => { closePromptChoicePopup(); openPromptLogBrowser(node, "prompt"); });
    } else {
        const inputActive = sourceMode === "input";
        const inputConnected = inputActive && externalPromptState.connected;
        promptValueRow(ctx, x, y, w, rowH, "Source", inputActive && !externalPromptState.connected ? "Prompt Input · not connected" : sourceLabel, {
            stroke: inputConnected ? `${SO_CMYKG.green}88` : `${SO_CMYKG.cyan}55`,
            valueColor: inputConnected ? SO_CMYKG.green : SO_CMYKG.text,
            chevron: true,
        });
        promptHit(node, "source_mode", x, y, w, rowH, () => promptChoicePopup(node, "Prompt source", MAIN_PROMPT_SOURCES, sourceMode, (value) => promptDashboardSet(node, "prompt_source", value), formatPromptSource));
    }
    y += rowH + gap;

    const sourceText = sourceMode === "log"
        ? promptStreamLine(node, "prompt")
        : (sourceMode === "input" ? externalPromptState.value : String(widget(node, "manual_prompt")?.value ?? ""));
    const trailingSourceH = sourceMode === "log" ? (gap + rowH + PROMPT_LOG_BOTTOM_PAD) : (gap + 6);
    const sourceCardH = Math.max(128, lowerTop - y - trailingSourceH);
    promptAnchorInput(node, sourceMode === "log" ? "prompt_index" : "manual_prompt", y + sourceCardH / 2);
    const sourceTitle = sourceMode === "log" ? "SELECTED PROMPT LINE" : (sourceMode === "input" ? "PROMPT INPUT" : "MANUAL PROMPT");
    const sourceEmpty = sourceMode === "log"
        ? "Choose a prompt log"
        : (sourceMode === "input" ? (externalPromptState.connected ? "Connected prompt is empty" : "Connect the Prompt input above") : "Click to write a prompt");
    promptTextCard(node, ctx, x, y, w, sourceCardH, sourceTitle, sourceText, sourceMode === "input" && externalPromptState.connected ? SO_CMYKG.green : SO_CMYKG.cyan, sourceEmpty);
    promptAnchorInput(node, "manual_prompt_input", y + sourceCardH / 2);
    promptHit(node, "source_text", x, y, w, sourceCardH, () => {
        if (sourceMode === "input" && externalPromptState.connected) pulseConnectedSource(node, "manual_prompt_input");
        else if (sourceMode === "manual") promptTextEditor(node, "Manual prompt", "manual_prompt", true);
        else if (sourceMode === "log") promptOpenIndexChoice(node, "prompt");
    });
    y += sourceCardH + gap;
    if (sourceMode === "log") {
        const half = (w - gap) / 2;
        promptValueRow(ctx, x, y, half, rowH, "Mode", widget(node, "prompt_mode")?.value ?? "fixed");
        promptValueRow(ctx, x + half + gap, y, half, rowH, "Index", promptStreamIndexLabel(node, "prompt"));
        promptAnchorInput(node, "prompt_mode", y + rowH / 2);
        promptAnchorInput(node, "prompt_index", y + rowH / 2);
        promptHit(node, "prompt_mode", x, y, half, rowH, () => promptChoicePopup(node, "Prompt mode", MODES, widget(node, "prompt_mode")?.value, (value) => promptDashboardSet(node, "prompt_mode", value)));
        promptHit(node, "prompt_index", x + half + gap, y, half, rowH, () => promptOpenIndexChoice(node, "prompt"));
        y += rowH + PROMPT_LOG_BOTTOM_PAD;
    } else y += 6;

    y = Math.max(y, lowerTop);

    promptSection(ctx, "Prompt Assembly", x + 2, y + 7, SO_CMYKG.magenta); y += 18;
    y += promptDrawAssemblySummary(node, ctx, x, y, w) + 12;
    y += promptDrawStreamCard(node, ctx, "outfit_A", x, y, w, SO_CMYKG.magenta, "outfit_a") + gap;
    y += promptDrawStreamCard(node, ctx, "outfit_B", x, y, w, SO_CMYKG.yellow, "outfit_b") + gap;
    y += promptDrawStreamCard(node, ctx, "outfit_C", x, y, w, SO_CMYKG.cyan, "outfit_c") + gap;
    y += promptDrawStreamCard(node, ctx, "scene", x, y, w, SO_CMYKG.green, "scene") + 12;

    promptSection(ctx, "Substitutions", x + 2, y + 7, SO_CMYKG.yellow); y += 18;
    const nameToken = String(widget(node, "name_token")?.value ?? "NAME");
    const itemToken = String(widget(node, "item_token")?.value ?? "ITEM");
    const nameState = substitutionState(node, "name");
    const itemState = substitutionState(node, "item");
    const subTokenW = Math.min(210, w * .27);
    const subValueW = w - subTokenW - gap;
    const drawSubstitution = (kind, token, state, tokenName, valueName) => {
        const connected = Boolean(state.connection);
        const valueLabel = connected ? "Connected value 🔒" : "Manual value";
        const linkedDisplay = connected
            ? `${state.connection.label}${state.value ? ` · ${state.value}` : ""}`
            : state.value;
        promptValueRow(ctx, x, y, subTokenW, rowH, "Placeholder ✎", token, { stroke: `${SO_CMYKG.yellow}55`, chevron: false });
        promptValueRow(ctx, x + subTokenW + gap, y, subValueW, rowH, valueLabel, linkedDisplay, {
            stroke: connected ? `${SO_CMYKG.green}88` : `${SO_CMYKG.yellow}55`,
            valueColor: connected ? SO_CMYKG.green : SO_CMYKG.text,
            chevron: false,
        });
        promptAnchorInput(node, tokenName, y + rowH / 2);
        promptAnchorInput(node, valueName, y + rowH / 2);
        promptHit(node, `${kind}_token`, x, y, subTokenW, rowH, () => promptTextEditor(node, `${token} placeholder`, tokenName, false));
        if (!connected) {
            promptHit(node, `${kind}_value`, x + subTokenW + gap, y, subValueW, rowH, () => promptTextEditor(node, `${token} value`, valueName, false));
        } else {
            promptHit(node, `${kind}_source`, x + subTokenW + gap, y, subValueW, rowH, () => pulseConnectedSource(node, valueName));
        }
        y += rowH;
    };
    drawSubstitution("name", nameToken, nameState, "name_token", "name_value");
    y += gap;
    drawSubstitution("item", itemToken, itemState, "item_token", "item_value");
    y += 12;

    promptSection(ctx, "Prompt Additions", x + 2, y + 7, SO_CMYKG.green); y += 18;
    const toggleW = Math.min(155, w * .22); const textW = w - toggleW - gap;
    const drawAffix = (kind, enabledName, textName) => {
        const title = kind === "prefix" ? "Prefix" : "Suffix";
        const textState = promptConnectedTextState(node, textName, kind);
        promptToggleRow(ctx, x, y, toggleW, rowH, title, Boolean(widget(node, enabledName)?.value), SO_CMYKG.green);
        promptValueRow(ctx, x + toggleW + gap, y, textW, rowH, textState.connected ? "Connected text 🔒" : "Text", textState.display, {
            stroke: textState.connected ? `${SO_CMYKG.green}88` : `${SO_CMYKG.green}55`,
            valueColor: textState.connected ? SO_CMYKG.green : SO_CMYKG.text,
            chevron: false,
        });
        promptAnchorInput(node, enabledName, y + rowH / 2);
        promptAnchorInput(node, textName, y + rowH / 2);
        promptHit(node, `${kind}_toggle`, x, y, toggleW, rowH, () => promptDashboardToggle(node, enabledName));
        if (!textState.connected) {
            promptHit(node, textName, x + toggleW + gap, y, textW, rowH, () => promptTextEditor(node, `Prompt ${kind}`, textName, true));
        } else {
            promptHit(node, `${kind}_source`, x + toggleW + gap, y, textW, rowH, () => pulseConnectedSource(node, textName));
        }
        y += rowH;
    };
    drawAffix("prefix", "prefix_enabled", "prefix_text");
    y += gap;
    drawAffix("suffix", "suffix_enabled", "suffix_text");
    y += 9;

    const expanded = Boolean(node.properties?.so_prompt_dashboard_advanced);
    promptRoundRect(ctx, x, y, w, 28, 8, "rgba(31,31,36,.98)", "rgba(246,230,90,.28)");
    promptDashText(ctx, `Advanced ${expanded ? "▾" : "▸"}`, x + 12, y + 14, { color: SO_CMYKG.label, font: "700 10px Segoe UI, Arial" });
    promptDashText(ctx, "separator + cleanup", x + w - 12, y + 14, { align: "right", color: "#777782", font: "10px Segoe UI, Arial" });
    promptHit(node, "advanced", x, y, w, 28, () => { node.properties.so_prompt_dashboard_advanced = !expanded; layoutPromptDashboard(node, true); });
    y += 36;
    if (expanded) {
        const advHalf = (w - gap) / 2;
        promptValueRow(ctx, x, y, advHalf, rowH, "Prefix/suffix separator", widget(node, "prefix_suffix_separator")?.value ?? ", ", { chevron: false });
        promptToggleRow(ctx, x + advHalf + gap, y, advHalf, rowH, "Cleanup", Boolean(widget(node, "cleanup_enabled")?.value), SO_CMYKG.yellow);
        promptAnchorInput(node, "prefix_suffix_separator", y + rowH / 2);
        promptAnchorInput(node, "cleanup_enabled", y + rowH / 2);
        promptHit(node, "separator", x, y, advHalf, rowH, () => promptTextEditor(node, "Prefix/suffix separator", "prefix_suffix_separator", false));
        promptHit(node, "cleanup_toggle", x + advHalf + gap, y, advHalf, rowH, () => promptDashboardToggle(node, "cleanup_enabled"));
        y += rowH + gap;
        promptValueRow(ctx, x, y, w, rowH, "Cleanup rules", "Click to edit regex rules", { stroke: `${SO_CMYKG.yellow}44`, chevron: false });
        promptAnchorInput(node, "cleanup_rules", y + rowH / 2);
        promptHit(node, "cleanup_rules", x, y, w, rowH, () => promptTextEditor(node, "Cleanup rules", "cleanup_rules", true));
        y += rowH + 10;
    }

    promptSection(ctx, "Resolved Prompt", x + 2, y + 7, SO_CMYKG.cyan); y += 18;
    const resolvedH = 130;
    const executedResolved = String(widget(node, "saved_prompt")?.value ?? node.properties?.so_saved_final_prompt ?? "");
    const liveResolved = promptLiveResolvedPrompt(node);
    const resolved = liveResolved || executedResolved;
    const pendingRun = Boolean(liveResolved && liveResolved !== executedResolved);
    promptAnchorInput(node, "saved_prompt", y + resolvedH / 2);
    promptTextCard(
        node, ctx, x, y, w, resolvedH,
        pendingRun ? "LIVE ASSEMBLY PREVIEW · READY FOR NEXT RUN" : "LIVE ASSEMBLY PREVIEW",
        resolved,
        pendingRun ? SO_CMYKG.yellow : SO_CMYKG.cyan,
        "Choose or write a prompt to preview the resolved assembly",
    );
    y += resolvedH + 6;
    const copied = node.__soPromptCopyFlash === "resolved";
    promptRoundRect(ctx, x, y, w, 29, 7, copied ? "rgba(54,119,81,.45)" : SO_CMYKG.row, copied ? `${SO_CMYKG.green}cc` : `${SO_CMYKG.cyan}55`);
    promptDashText(ctx, copied ? "✓ Copied resolved prompt" : "📋 Copy resolved prompt", x + w / 2, y + 14.5, { align: "center", color: copied ? SO_CMYKG.green : SO_CMYKG.text, font: "11px Segoe UI, Arial" });
    promptHit(node, "copy_resolved", x, y, w, 29, () => promptCopyValue(node, "resolved", resolved));

    ctx.restore();
}

function hidePromptDashboardWidget(target) {
    if (!target) return;
    target.__soPromptDashboardHidden = true;
    target.computeSize = () => [0, 0];
    target.draw = () => {};
    target.mouse = () => false;
    if (target.inputEl) {
        target.inputEl.style.display = "none";
        target.inputEl.style.pointerEvents = "none";
    }
}

function hidePromptDashboardBackingWidgets(node) {
    for (const name of CANONICAL_NAMES) hidePromptDashboardWidget(widget(node, name));
    for (const button of Object.values(node.__soPromptCopyButtons || {})) hidePromptDashboardWidget(button);
    for (const button of Object.values(node.__soLogBrowserButtons || {})) hidePromptDashboardWidget(button);
    for (const base of STREAM_BASES) {
        const preview = widget(node, previewWidgetName(base));
        if (preview) hidePromptDashboardWidget(preview);
    }
}

function layoutPromptDashboard(node, refit = false) {
    if (!node.__soPromptDashboardReady) return;
    hidePromptDashboardBackingWidgets(node);
    layoutPromptInputSockets(node);
    layoutPromptOutputSockets(node);
    node.widgets_start_y = promptDashBottom(node) + 10;
    node.size[0] = Math.max(Number(node.size?.[0] || 0), PROMPT_DASH_MIN_WIDTH);
    applyStudioNodeColors(node);
    if (refit) {
        // Fit exactly around the custom dashboard. Converted widget inputs no
        // longer reserve a hidden native-widget basement below this height.
        node.size[1] = promptDashBottom(node) + 14;
        setTimeout(() => {
            if (!node.__soPromptDashboardReady || !node.size) return;
            node.size[0] = Math.max(Number(node.size[0] || 0), PROMPT_DASH_MIN_WIDTH);
            node.size[1] = promptDashBottom(node) + 14;
            node.setDirtyCanvas?.(true, true);
        }, 0);
    }
    node.setDirtyCanvas?.(true, true);
}

function ensurePromptDashboard(node) {
    node.properties = node.properties || {};
    node.properties.so_prompt_dashboard_version = PROMPT_DASH_VERSION;
    node.__soPromptDashboardReady = true;
    applyStudioNodeColors(node);
    hidePromptDashboardBackingWidgets(node);
    layoutPromptDashboard(node, true);
}

function installPromptDashboardHooks(nodeType) {
    if (nodeType.prototype.__soPromptDashboardHooks) return;
    nodeType.prototype.__soPromptDashboardHooks = true;

    // Converted widgets remain real graph inputs so existing wires keep working,
    // but their connection geometry is owned by the dashboard. This prevents
    // LiteGraph from stacking invisible widget-input ports below the custom UI.
    const originalGetConnectionPos = nodeType.prototype.getConnectionPos;
    nodeType.prototype.getConnectionPos = function (isInput, slot, out) {
        if (isInput && this.__soPromptDashboardReady) {
            let slotIndex = typeof slot === "number" ? slot : this.findInputSlot?.(slot);
            if (!Number.isInteger(slotIndex) || slotIndex < 0) slotIndex = Number(slot);
            const input = this.inputs?.[slotIndex];
            const inputName = promptInputName(input);
            const anchor = promptDashboardInputAnchor(this, slotIndex);
            if (anchor) {
                const result = out || [0, 0];
                result[0] = Number(this.pos?.[0] || 0);
                result[1] = Number(this.pos?.[1] || 0) + anchor.y;
                return result;
            }
            // Canonical widgets that are intentionally hidden must not fall
            // back to LiteGraph's native slot stack. That fallback was drawing
            // mystery sockets in the empty basement below the custom dashboard.
            // Connected legacy inputs are still exposed by promptShouldExposeInput().
            if (CANONICAL_NAMES.includes(inputName) && !promptShouldExposeInput(input)) {
                const result = out || [0, 0];
                result[0] = Number(this.pos?.[0] || 0) - 10000;
                result[1] = Number(this.pos?.[1] || 0) - 10000;
                return result;
            }
        }
        if (!isInput && this.__soPromptDashboardReady) {
            let slotIndex = typeof slot === "number" ? slot : this.findOutputSlot?.(slot);
            if (!Number.isInteger(slotIndex) || slotIndex < 0) slotIndex = Number(slot);
            const anchor = promptOutputAnchor(this, slotIndex);
            if (anchor) {
                const result = out || [0, 0];
                result[0] = Number(this.pos?.[0] || 0) + anchor.x;
                result[1] = Number(this.pos?.[1] || 0) + anchor.y;
                return result;
            }
        }
        return originalGetConnectionPos?.apply(this, arguments);
    };

    const originalGetInputPos = nodeType.prototype.getInputPos;
    if (typeof originalGetInputPos === "function") {
        nodeType.prototype.getInputPos = function (slotIndex, out) {
            if (this.__soPromptDashboardReady) {
                const input = this.inputs?.[Number(slotIndex)];
                const inputName = promptInputName(input);
                const anchor = promptDashboardInputAnchor(this, slotIndex);
                if (anchor) {
                    const result = out || [0, 0];
                    result[0] = Number(this.pos?.[0] || 0);
                    result[1] = Number(this.pos?.[1] || 0) + anchor.y;
                    return result;
                }
                if (CANONICAL_NAMES.includes(inputName) && !promptShouldExposeInput(input)) {
                    const result = out || [0, 0];
                    result[0] = Number(this.pos?.[0] || 0) - 10000;
                    result[1] = Number(this.pos?.[1] || 0) - 10000;
                    return result;
                }
            }
            return originalGetInputPos.apply(this, arguments);
        };
    }

    const originalGetOutputPos = nodeType.prototype.getOutputPos;
    if (typeof originalGetOutputPos === "function") {
        nodeType.prototype.getOutputPos = function (slotIndex, out) {
            if (this.__soPromptDashboardReady) {
                const anchor = promptOutputAnchor(this, slotIndex);
                if (anchor) {
                    const result = out || [0, 0];
                    result[0] = Number(this.pos?.[0] || 0) + anchor.x;
                    result[1] = Number(this.pos?.[1] || 0) + anchor.y;
                    return result;
                }
            }
            return originalGetOutputPos.apply(this, arguments);
        };
    }

    const originalForeground = nodeType.prototype.onDrawForeground;
    nodeType.prototype.onDrawForeground = function (ctx) {
        drawStudioChrome(this, ctx, "prompt");
        try { originalForeground?.apply(this, arguments); } catch (error) {}
        drawPromptDashboard(this, ctx);
    };
    const originalMouseDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function (event, pos, canvas) {
        if (this.__soPromptDashboardReady) {
            for (const hit of Object.values(this.__soPromptDashboardHits || {})) {
                if (promptPointIn(pos, hit)) { hit.callback(event, pos, this); return true; }
            }
        }
        return originalMouseDown?.apply(this, arguments);
    };

    const originalMouseMove = nodeType.prototype.onMouseMove;
    nodeType.prototype.onMouseMove = function (event, pos, canvas) {
        const hover = Boolean(this.__soPromptDashboardReady && !this.flags?.collapsed
            && promptPointIn(pos, this.__soPromptDashboardHits?.creative_library));
        if (hover !== Boolean(this.__soCreativeLibraryHover)) {
            this.__soCreativeLibraryHover = hover;
            this.setDirtyCanvas?.(true, true);
        }
        return originalMouseMove?.apply(this, arguments);
    };
    const originalMouseLeave = nodeType.prototype.onMouseLeave;
    nodeType.prototype.onMouseLeave = function () {
        this.__soCreativeLibraryHover = false;
        this.setDirtyCanvas?.(true, true);
        return originalMouseLeave?.apply(this, arguments);
    };

    const originalConnectionsChange = nodeType.prototype.onConnectionsChange;
    nodeType.prototype.onConnectionsChange = function () {
        const result = originalConnectionsChange?.apply(this, arguments);
        // LiteGraph fires this while the link is still settling. Defer one
        // frame, then upgrade a legacy Loader Core clean_name wire to the
        // dedicated main_trigger output if needed.
        setTimeout(() => {
            repairPromptTriggerConnection(this);
            this.setDirtyCanvas?.(true, true);
        }, 0);
        return result;
    };

    const originalResize = nodeType.prototype.onResize;
    nodeType.prototype.onResize = function (size) {
        if (Array.isArray(size) || (size && typeof size === "object")) {
            size[0] = Math.max(Number(size[0] || 0), PROMPT_DASH_MIN_WIDTH);
            if (this.__soPromptDashboardReady) {
                // The custom dashboard owns Prompt Core's vertical layout. Use
                // its real bottom instead of preserving a stale serialized or
                // native-widget height, which created the large empty basement.
                size[1] = promptDashBottom(this) + 14;
            }
        }
        const result = originalResize?.apply(this, arguments);
        if (this.size) {
            this.size[0] = Math.max(Number(this.size[0] || 0), PROMPT_DASH_MIN_WIDTH);
            if (this.__soPromptDashboardReady) this.size[1] = promptDashBottom(this) + 14;
        }
        this.setDirtyCanvas?.(true, true);
        return result;
    };
}

function applyLayout(node) {
    node.properties = node.properties || {};
    node.properties.so_prompt_core_schema_version = SCHEMA_VERSION;

    // Keep all existing backend/frontend mechanics alive; the dashboard merely
    // becomes the visible interface over those stable values.
    repairPromptTriggerConnection(node);
    syncExternalManualPrompt(node);
    healMissingLogSelections(node);
    createCopyButtons(node);
    bindTokenCallbacks(node);
    for (const base of STREAM_BASES) ensureStreamIndexPreview(node, base);
    bindLogControls(node);
    ensureAllLogNavigators(node);
    bindQueueProgression(node);
    for (const base of STREAM_BASES) refreshStreamIndexPreview(node, base);
    updateCopyButtons(node);
    ensurePromptDashboard(node);
}


app.registerExtension({
    name: "SickOllie.Studio.PromptCore",
    setup() {
        ensurePromptBrowserPointerTracker();
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== TARGET) return;
        installPromptDashboardHooks(nodeType);

        const originalConfigureMethod = nodeType.prototype.configure;
        nodeType.prototype.configure = function (info) {
            return originalConfigureMethod.call(this, migratePromptWorkflow(info));
        };

        const originalSerialize = nodeType.prototype.serialize;
        nodeType.prototype.serialize = function () {
            syncTriggerOverrideScope(this);
            healMissingLogSelections(this);
            const data = originalSerialize?.apply(this, arguments) || {};
            data.properties = {
                ...(data.properties || {}),
                so_prompt_core_schema_version: SCHEMA_VERSION,
            };
            // Copy buttons are frontend decoration. Always serialize only the
            // canonical backend widgets, in backend order, with no null
            // button placeholders.
            data.widgets_values = CANONICAL_NAMES.map((name) => {
                const target = widget(this, name);
                return target ? target.value : DEFAULTS[name];
            });
            return data;
        };

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            // Defer frontend-only buttons until after LiteGraph has configured
            // all native widgets from the saved canonical array.
            setTimeout(() => applyLayout(this), 0);
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function (info) {
            const result = originalConfigure?.apply(this, arguments);
            const stored = this.properties?.so_saved_final_prompt;
            if (stored != null && stored !== "") setTextWidget(this, "saved_prompt", stored);
            const runtimeManual = this.properties?.so_runtime_manual_prompt;
            const runtimeSource = this.properties?.so_runtime_prompt_source;
            if (runtimeManual != null) setTextWidget(this, "manual_prompt", runtimeManual);
            if (runtimeSource === "manual" || runtimeSource === "input" || runtimeSource === "log") {
                const sourceWidget = widget(this, "prompt_source");
                if (sourceWidget) sourceWidget.value = runtimeSource;
            }
            // Runtime snapshot hints are one-shot import recovery markers. Once
            // consumed, remove them so a later hand-edited workflow save cannot
            // resurrect an older generated prompt on its next load.
            if (this.properties) {
                delete this.properties.so_runtime_manual_prompt;
                delete this.properties.so_runtime_prompt_source;
            }
            if (this.properties?.so_last_assembly_status && typeof this.properties.so_last_assembly_status === "object") {
                this.__soLastAssembly = this.properties.so_last_assembly_status;
            }
            applyLayout(this);
            setTimeout(() => applyLayout(this), 0);
            return result;
        };

        const originalExecuted = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            originalExecuted?.apply(this, arguments);
            let resolved = message?.resolved_prompt;
            if (Array.isArray(resolved)) resolved = resolved[0];
            if (resolved != null) {
                this.properties = this.properties || {};
                this.properties.so_saved_final_prompt = String(resolved);
                setTextWidget(this, "saved_prompt", resolved);
            }
            let assembly = message?.assembly_status;
            if (Array.isArray(assembly)) assembly = assembly[0];
            if (assembly && typeof assembly === "object") {
                this.__soLastAssembly = assembly;
                this.properties = this.properties || {};
                this.properties.so_last_assembly_status = assembly;
            }
            updateCopyButtons(this);
            applyLayout(this);
        };
    },
});
