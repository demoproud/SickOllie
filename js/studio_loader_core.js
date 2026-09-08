/*
 * Loader Core Studio UI with folder-browser secondary LoRA stack.
 *
 * Secondary controls are painted directly inside the Loader Core Studio
 * dashboard. A single hidden backing widget carries the serialized stack;
 * rgthree remains only for the shared LoRA metadata/info dialog service.
 */

import { app } from "../../../scripts/app.js";
import {
    STUDIO_LAYOUT,
    STUDIO_THEME,
    applyStudioNodeColors,
    drawStudioChrome,
    drawStudioSectionFrame,
} from "./studio_theme.js";

import { fitString } from "/extensions/rgthree-comfy/utils_canvas.js";

import { RgthreeLoraInfoDialog } from "/extensions/rgthree-comfy/dialog_info.js";
import { rgthree } from "/extensions/rgthree-comfy/rgthree.js";
import { rgthreeApi } from "/rgthree/common/rgthree_api.js";
import { LORA_INFO_SERVICE } from "/rgthree/common/model_info_service.js";

const TARGET = "SOLoaderCoreEngineStudio";
const LOADER_LIBRARY_BUTTON_URL = new URL("./assets/LoaderCore_LIB_button.png", import.meta.url).href;
const loaderLibraryButtonImage = new Image();
loaderLibraryButtonImage.addEventListener("load", () => app.graph?.setDirtyCanvas?.(true, true), { once: true });
loaderLibraryButtonImage.src = LOADER_LIBRARY_BUTTON_URL;
const NONE = "None";
const ALL_FOLDERS = "[All LoRA folders]";
const ROOT_FOLDER = "[LoRA root only]";
const FAVORITES_FOLDER = "[★ Favorites]";
const UNTESTED_FOLDER = "[◌ Untested / Retest]";
const COLLECTION_SCOPE_PREFIX = "[LoRA Collection:";
const REVIEW_API = "/sickollie/library-review";
const ALL_EPOCHS = "[All epochs]";
const NO_EPOCH_TAG = "[No epoch tag]";
const ALL_LIBRARY_STATES = "[All Library statuses]";
const FAVORITES_FILTER = "[★ Favorites]";
const TESTED_FILTER = "[✓ Tested]";
const UNTESTED_FILTER = "[◌ Untested / Retest]";
const LIBRARY_FILTERS = [ALL_LIBRARY_STATES, FAVORITES_FILTER, TESTED_FILTER, UNTESTED_FILTER];
const LORA_SORT_MODES = ["Name", "Most used", "Least used", "Recently used"];
const CONTROL_MODES = ["fixed", "increment", "decrement", "randomize", "shuffle"];
const DEFAULT_CLEAN_NAME_MODE = "auto:1";
const SECONDARY_PREFIX = "secondary_lora_";
const MAX_SECONDARY_LORAS = 10;
const LOADER_DASHBOARD_VERSION = 5;
const LOADER_CANONICAL_NAMES = [
    "diffusion_model",
    "weight_dtype",
    "folder_name",
    "epoch_filter",
    "main_enabled",
    "main_lora",
    "main_strength",
    "include_subfolders",
    "loop_folder",
    "control_after_generate",
    "skip_none_during_cycle",
    "off_name",
    "auto_clean_name",
    "cleanup_rules",
    "library_filter",
    "lora_sort",
    "diffusion_control_after_generate",
];

function widget(node, name) {
    return node.widgets?.find((item) => item.name === name);
}

function normalizePath(value) {
    return String(value ?? "")
        .replaceAll("\\", "/")
        .replace(/^\/+|\/+$/g, "");
}

function loraReviewState(node, loraName) {
    return node?.__soReviewStates?.[normalizePath(loraName).toLowerCase()] || "none";
}

function reviewTone(state) {
    return ({ favorite: "#f6e65a", keep: "#6ee7a2", generated: "#f4f1f6", retest: "#35d7ff", reject: "#ff536e", tested: "#f4f1f6" })[state] || "#8a8490";
}

function collectionScopeValue(collection) {
    const id = String(collection?.collection_id ?? "").trim();
    return id ? `${COLLECTION_SCOPE_PREFIX}${id}]` : "";
}

function collectionScopeId(value) {
    const text = String(value ?? "").trim();
    if (!text.startsWith(COLLECTION_SCOPE_PREFIX) || !text.endsWith("]")) return "";
    return text.slice(COLLECTION_SCOPE_PREFIX.length, -1).trim();
}

function isCollectionScope(value) {
    return Boolean(collectionScopeId(value));
}

function collectionForScope(node, value) {
    const id = collectionScopeId(value);
    if (!id) return null;
    return (node?.__soLoraCollections || []).find(
        (collection) => String(collection?.collection_id ?? "") === id,
    ) || null;
}

function collectionDisplayName(node, value) {
    const collection = collectionForScope(node, value);
    return collection?.name ? `◆ ${collection.name}` : "◆ LoRA Collection";
}

function openLoRALibraryFromLoader(node) {
    const selected = String(widget(node, "folder_name")?.value ?? ALL_FOLDERS);
    const collectionId = collectionScopeId(selected);
    const request = {
        folder: (collectionId || [ALL_FOLDERS, ROOT_FOLDER, FAVORITES_FOLDER, UNTESTED_FOLDER].includes(selected)) ? "" : normalizePath(selected),
        collection: collectionId,
        status: selected === FAVORITES_FOLDER ? "favorite" : selected === UNTESTED_FOLDER ? "untested" : "",
    };
    // Preserve the request if extension setup order means the Library has not
    // installed its public function yet.
    window.__soPendingLoRALibraryRequest = request;
    if (typeof window.__soOpenLoRALibrary === "function") {
        void window.__soOpenLoRALibrary(request);
        delete window.__soPendingLoRALibraryRequest;
    } else {
        window.dispatchEvent(new CustomEvent("sickollie:open-lora-library", { detail: request }));
        const execute = app.extensionManager?.commands?.execute || app.extensionManager?.command?.execute;
        try { execute?.("solo.openLoRALibrary"); } catch (error) { console.warn("[Sick Ollie Loader Core] LoRA Library command is unavailable", error); }
    }
    node.__soLibraryOpenFlash = Date.now() + 700;
    node.setDirtyCanvas?.(true, true);
}

function loraUseCount(node, loraName) {
    return Math.max(0, Number(node?.__soReviewUsage?.[normalizePath(loraName).toLowerCase()] || 0));
}

function loraLastUsed(node, loraName) {
    return String(node?.__soReviewLastUsed?.[normalizePath(loraName).toLowerCase()] || "");
}

async function refreshReviewCollections(node) {
    try {
        const [reviewResponse, collectionResponse] = await Promise.all([
            fetch(`${REVIEW_API}/collections`),
            fetch(`${REVIEW_API}/loader-collections`),
        ]);
        if (!reviewResponse.ok) throw new Error(`HTTP ${reviewResponse.status}`);
        if (!collectionResponse.ok) throw new Error(`HTTP ${collectionResponse.status}`);
        const data = await reviewResponse.json();
        const collections = await collectionResponse.json();
        node.__soReviewStates = data.states || {};
        node.__soReviewUsage = data.usage || {};
        node.__soReviewLastUsed = data.last_used || {};
        node.__soLoraCollections = Array.isArray(collections) ? collections : [];

        const folderWidget = widget(node, "folder_name");
        if (folderWidget) {
            const baseChoices = (node.__soAllFolderChoices || readValues(folderWidget))
                .map((value) => String(value ?? ""))
                .filter((value) => value && !isCollectionScope(value));
            node.__soAllFolderChoices = baseChoices;
            writeValues(folderWidget, [
                ...node.__soLoraCollections.map(collectionScopeValue),
                ...baseChoices,
            ]);
            const current = String(folderWidget.value ?? ALL_FOLDERS);
            if (isCollectionScope(current) && !collectionForScope(node, current)) {
                folderWidget.value = ALL_FOLDERS;
            }
        }

        refreshEpochChoices(node);
        refreshMainChoices(node, false);
        refreshCleanNameChoices(node);
        node.setDirtyCanvas?.(true, true);
        return node.__soLoraCollections;
    } catch (error) {
        console.warn("[Sick Ollie Loader Core] Could not load review collections", error);
        return [];
    }
}

async function setLoaderReview(node, state) {
    const lora = String(widget(node, "main_lora")?.value ?? NONE);
    if (!lora || lora === NONE) return;
    const key = normalizePath(lora).toLowerCase();
    const previous = loraReviewState(node, lora);
    const next = previous === state ? "none" : state;
    node.__soReviewStates = { ...(node.__soReviewStates || {}), [key]: next };
    node.__soReviewFlash = next; node.setDirtyCanvas?.(true, true);
    try { navigator.vibrate?.(18); } catch (error) {}
    try {
        const response = await fetch(`${REVIEW_API}/review-lora`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lora, state: next }) });
        if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || `HTTP ${response.status}`);
        if (String(widget(node, "library_filter")?.value) !== ALL_LIBRARY_STATES) refreshMainChoices(node, true);
    } catch (error) {
        node.__soReviewStates[key] = previous;
        console.warn("[Sick Ollie Loader Core] Review update failed", error);
    }
    clearTimeout(node.__soReviewFlashTimer);
    node.__soReviewFlashTimer = setTimeout(() => { node.__soReviewFlash = ""; node.setDirtyCanvas?.(true, true); }, 850);
}

function parentFolder(loraName) {
    const normalized = normalizePath(loraName);
    const index = normalized.lastIndexOf("/");
    return index < 0 ? "" : normalized.slice(0, index);
}

function readValues(comboWidget) {
    const source = comboWidget?.options?.values;

    if (Array.isArray(source)) {
        return [...source];
    }

    if (typeof source === "function") {
        try {
            const result = source();
            return Array.isArray(result) ? [...result] : [];
        } catch (error) {
            console.warn(
                "[Sick Ollie Loader Core] Could not read combo values",
                error,
            );
        }
    }

    return [];
}

function writeValues(comboWidget, values) {
    if (!comboWidget) return;
    comboWidget.options = comboWidget.options || {};
    comboWidget.options.values = [...values];
}


function hideNativeWidget(target) {
    if (!target) return;
    if (!target.__soHiddenByNavigator) {
        target.__soHiddenByNavigator = true;
        target.__soOriginalType = target.type;
        target.__soOriginalComputeSize = target.computeSize;
    }
    // Dashboard-owned backing widgets must remain serializable/callable, but
    // they should never participate in the stock LiteGraph widget layout or
    // paint pass. `hidden` handles newer frontends while the custom type and
    // negative height keep legacy canvas builds from stacking ghost rows.
    target.hidden = true;
    target.type = "so-hidden-backing-widget";
    target.computeSize = () => [0, -4];
    target.draw = () => {};
    target.mouse = () => false;
    if (target.inputEl) {
        target.inputEl.style.display = "none";
        target.inputEl.style.visibility = "hidden";
        target.inputEl.style.pointerEvents = "none";
    }
}

function moveFrontendWidgetAfter(node, added, anchor, offset = 1) {
    if (!added || !anchor || !Array.isArray(node.widgets)) return;
    const addedIndex = node.widgets.indexOf(added);
    const anchorIndex = node.widgets.indexOf(anchor);
    if (addedIndex < 0 || anchorIndex < 0) return;
    node.widgets.splice(addedIndex, 1);
    node.widgets.splice(anchorIndex + offset, 0, added);
}

function allFolderPaths(node) {
    if (!Array.isArray(node.__soAllFolderChoices)) {
        const target = widget(node, "folder_name");
        node.__soAllFolderChoices = readValues(target);
    }
    return (node.__soAllFolderChoices || [])
        .map((value) => String(value ?? ""))
        .filter((value) => value && !isCollectionScope(value) && ![ALL_FOLDERS, ROOT_FOLDER, FAVORITES_FOLDER, UNTESTED_FOLDER].includes(value));
}

function folderNavigatorChildren(node, selectedValue) {
    const selected = String(selectedValue ?? ALL_FOLDERS);
    if (isCollectionScope(selected) || [FAVORITES_FOLDER, UNTESTED_FOLDER].includes(selected)) return [];
    const base = selected === ALL_FOLDERS || selected === ROOT_FOLDER
        ? ""
        : normalizePath(selected);
    const children = new Map();

    for (const fullPath of allFolderPaths(node)) {
        const normalized = normalizePath(fullPath);
        let remainder = normalized;
        if (base) {
            if (!normalized.startsWith(base + "/")) continue;
            remainder = normalized.slice(base.length + 1);
        }
        if (!remainder) continue;
        const leaf = remainder.split("/")[0];
        if (!leaf) continue;
        const childPath = base ? `${base}/${leaf}` : leaf;
        children.set(leaf, childPath);
    }

    return [...children.entries()].sort((a, b) =>
        a[0].localeCompare(b[0], undefined, { sensitivity: "base" }),
    );
}

function loraBrowserBasename(value) {
    const normalized = normalizePath(value);
    if (!normalized || normalized === NONE) return "None";
    const slash = normalized.lastIndexOf("/");
    return slash < 0 ? normalized : normalized.slice(slash + 1);
}

function loaderBrowserFolderText(value, node = null) {
    const selected = String(value ?? ALL_FOLDERS);
    if (selected === ALL_FOLDERS) return "LoRA Root · all folders";
    if (selected === ROOT_FOLDER) return "LoRA Root · files only";
    if (selected === FAVORITES_FOLDER) return "★ Favorites";
    if (selected === UNTESTED_FOLDER) return "◌ Untested / Retest";
    if (isCollectionScope(selected)) return collectionDisplayName(node, selected);
    return normalizePath(selected);
}

function loaderBrowserButtonText(node) {
    const folder = loaderBrowserFolderText(widget(node, "folder_name")?.value, node);
    const main = loraBrowserBasename(widget(node, "main_lora")?.value);
    return `📁 LoRA Browser   ${folder}  ·  ${main}`;
}

function ensurePointerTracker() {
    if (window.__soBrowserPointerTrackerInstalled) return;
    window.__soBrowserPointerTrackerInstalled = true;
    window.__soBrowserLastPointer = { x: Math.round(window.innerWidth / 2), y: 180 };
    document.addEventListener("pointerdown", (event) => {
        window.__soBrowserLastPointer = { x: event.clientX, y: event.clientY };
    }, true);
}

function closeSOFolderBrowser() {
    const existing = document.getElementById("so-loader-folder-browser-popup");
    if (existing) existing.remove();
    if (window.__soLoaderBrowserEscape) {
        document.removeEventListener("keydown", window.__soLoaderBrowserEscape, true);
        window.__soLoaderBrowserEscape = null;
    }
    if (window.__soLoaderBrowserOutside) {
        document.removeEventListener("pointerdown", window.__soLoaderBrowserOutside, true);
        window.__soLoaderBrowserOutside = null;
    }
}

function createBrowserShell(id, title, subtitle, onSearch) {
    closeSOFolderBrowser();
    const root = document.createElement("div");
    root.id = id;
    Object.assign(root.style, {
        position: "fixed",
        zIndex: "100000",
        width: "510px",
        maxWidth: "calc(100vw - 24px)",
        background: "#151519",
        border: "1px solid rgba(53,215,255,.62)",
        borderRadius: "9px",
        boxShadow: "0 12px 36px rgba(0,0,0,.58), 0 0 0 1px rgba(255,74,184,.10) inset",
        color: "#eee",
        font: "13px Arial, sans-serif",
        overflow: "hidden",
    });

    const header = document.createElement("div");
    Object.assign(header.style, { padding: "10px 12px 6px", borderBottom: "1px solid rgba(255,74,184,.34)" });
    const titleEl = document.createElement("div");
    titleEl.textContent = title;
    Object.assign(titleEl.style, { fontWeight: "700", fontSize: "14px" });
    const subtitleEl = document.createElement("div");
    subtitleEl.textContent = subtitle;
    Object.assign(subtitleEl.style, { marginTop: "3px", color: "#aaa", fontSize: "12px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
    header.append(titleEl, subtitleEl);

    const search = document.createElement("input");
    search.type = "text";
    search.placeholder = "Filter folders or LoRAs";
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
    window.__soLoaderBrowserEscape = (event) => {
        if (event.key === "Escape") closeSOFolderBrowser();
    };
    document.addEventListener("keydown", window.__soLoaderBrowserEscape, true);
    window.__soLoaderBrowserOutside = (event) => {
        if (!root.contains(event.target)) closeSOFolderBrowser();
    };
    setTimeout(() => {
        document.addEventListener("pointerdown", window.__soLoaderBrowserOutside, true);
        search.focus();
    }, 0);
    return { root, header, subtitleEl, search, list };
}

function browserRow(list, label, kind, callback, hint = "") {
    const row = document.createElement("div");
    const icon = kind === "folder" ? "📁" : kind === "collection" ? "◆" : kind === "action" ? "" : "";
    row.textContent = `${icon}${icon ? "  " : ""}${label}`;
    Object.assign(row.style, {
        padding: "7px 12px",
        cursor: "pointer",
        borderBottom: "1px solid #242424",
        whiteSpace: "nowrap",
        overflow: "hidden",
        textOverflow: "ellipsis",
        color: kind === "action" ? "#ccc" : "#f4f4f4",
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

function browserDivider(list) {
    const divider = document.createElement("div");
    Object.assign(divider.style, { height: "1px", background: "rgba(110,231,162,.34)", margin: "5px 0" });
    list.append(divider);
}

function setLoaderFolder(node, value) {
    const folderWidget = widget(node, "folder_name");
    if (!folderWidget) return;
    const next = String(value ?? ALL_FOLDERS);
    folderWidget.value = next;
    try { folderWidget.callback?.(next); } catch (error) {}
    refreshLoaderFolderNavigator(node);
    node.setDirtyCanvas?.(true, true);
}

function setLoaderMainLora(node, value) {
    const mainWidget = widget(node, "main_lora");
    if (!mainWidget) return;
    mainWidget.value = String(value ?? NONE);
    try { mainWidget.callback?.(mainWidget.value); } catch (error) {}
    refreshLoaderFolderNavigator(node);
    node.setDirtyCanvas?.(true, true);
}

function directLorasForBrowser(node, folderValue) {
    const selected = String(folderValue ?? ALL_FOLDERS);
    if (isCollectionScope(selected) || selected === FAVORITES_FOLDER || selected === UNTESTED_FOLDER) return folderScopedLoras(node).sort((a, b) => loraBrowserBasename(a).localeCompare(loraBrowserBasename(b)));
    const parent = selected === ALL_FOLDERS || selected === ROOT_FOLDER ? "" : normalizePath(selected);
    return (node.__soAllMainLoras || [])
        .map((value) => String(value ?? ""))
        .filter((value) => value && value !== NONE && parentFolder(value) === parent)
        .sort((a, b) => loraBrowserBasename(a).localeCompare(loraBrowserBasename(b), undefined, { sensitivity: "base" }));
}

function renderLoaderBrowser(node, shell, query = "") {
    const folderValue = String(widget(node, "folder_name")?.value ?? ALL_FOLDERS);
    const folderText = loaderBrowserFolderText(folderValue, node);
    shell.subtitleEl.textContent = folderText;
    shell.list.replaceChildren();
    const q = String(query ?? "").trim().toLowerCase();
    const collections = [...(node.__soLoraCollections || [])]
        .filter((collection) => collectionScopeValue(collection))
        .sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" }));

    if (q) {
        const collectionHits = collections.filter((collection) => String(collection.name || "").toLowerCase().includes(q)).slice(0, 80);
        const folderHits = allFolderPaths(node)
            .filter((path) => normalizePath(path).toLowerCase().includes(q))
            .slice(0, 220);
        for (const collection of collectionHits) {
            const scope = collectionScopeValue(collection);
            const count = Number(collection.live_count ?? collection.asset_count ?? 0);
            browserRow(shell.list, `${collection.name}   ·   ${count.toLocaleString()} LoRAs`, "collection", () => {
                setLoaderFolder(node, scope);
                shell.search.value = "";
                renderLoaderBrowser(node, shell, "");
            }, `Collection · ${collection.name}`);
        }
        if (collectionHits.length && folderHits.length) browserDivider(shell.list);
        for (const path of folderHits) {
            browserRow(shell.list, normalizePath(path), "folder", () => {
                setLoaderFolder(node, path);
                shell.search.value = "";
                renderLoaderBrowser(node, shell, "");
            }, path);
        }
        if (!collectionHits.length && !folderHits.length) browserRow(shell.list, "No matching collections or folders", "action", () => {});
        return;
    }

    if (collections.length) {
        for (const collection of collections) {
            const scope = collectionScopeValue(collection);
            const active = scope === folderValue;
            const count = Number(collection.live_count ?? collection.asset_count ?? 0);
            browserRow(shell.list, `${active ? "✓  " : ""}${collection.name}   ·   ${count.toLocaleString()} LoRAs`, "collection", () => {
                setLoaderFolder(node, scope);
                renderLoaderBrowser(node, shell, "");
            }, `LoRA Library collection · ${collection.name}`);
        }
        browserDivider(shell.list);
    }

    if (folderValue !== ALL_FOLDERS) {
        browserRow(shell.list, "↑ Parent Folder", "action", () => {
            if (isCollectionScope(folderValue) || folderValue === ROOT_FOLDER) {
                setLoaderFolder(node, ALL_FOLDERS);
            } else {
                const normalized = normalizePath(folderValue);
                const slash = normalized.lastIndexOf("/");
                setLoaderFolder(node, slash < 0 ? ALL_FOLDERS : normalized.slice(0, slash));
            }
            renderLoaderBrowser(node, shell, "");
        });
    }
    browserRow(shell.list, "⌂ LoRA Root · all folders", "action", () => {
        setLoaderFolder(node, ALL_FOLDERS);
        renderLoaderBrowser(node, shell, "");
    });
    if (folderValue !== ROOT_FOLDER) {
        browserRow(shell.list, "• LoRA Root · files only", "action", () => {
            setLoaderFolder(node, ROOT_FOLDER);
            renderLoaderBrowser(node, shell, "");
        });
    }
    browserDivider(shell.list);

    if (isCollectionScope(folderValue)) {
        const selected = collectionForScope(node, folderValue);
        const count = Number(selected?.live_count ?? selected?.asset_count ?? 0);
        browserRow(shell.list, `${selected?.name || "Collection"} selected · ${count.toLocaleString()} LoRAs`, "action", () => {});
        return;
    }

    const children = folderNavigatorChildren(node, folderValue);
    for (const [leaf, path] of children) {
        browserRow(shell.list, leaf, "folder", () => {
            setLoaderFolder(node, path);
            renderLoaderBrowser(node, shell, "");
        }, path);
    }

    if (!children.length) {
        browserRow(shell.list, "No deeper folders · current folder is selected", "action", () => {});
    }
}

function openLoaderFolderBrowser(node) {
    ensurePointerTracker();
    const shell = createBrowserShell(
        "so-loader-folder-browser-popup",
        "Folder / Collection Scope",
        loaderBrowserFolderText(widget(node, "folder_name")?.value, node),
        (query) => renderLoaderBrowser(node, shell, query),
    );
    shell.search.placeholder = "Filter collections or folders";
    renderLoaderBrowser(node, shell, "");
    void refreshReviewCollections(node).then(() => {
        if (document.getElementById("so-loader-folder-browser-popup") === shell.root) {
            renderLoaderBrowser(node, shell, shell.search.value);
        }
    });
}

function allSecondaryBrowserLoras(node) {
    const source = Array.isArray(node.__soAllMainLoras)
        ? node.__soAllMainLoras
        : readValues(widget(node, "main_lora"));
    return [...new Set(
        source
            .map((value) => String(value ?? ""))
            .filter((value) => value && value !== NONE),
    )].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
}

function secondaryBrowserFolderText(value) {
    const normalized = normalizePath(value);
    return normalized || "LoRA Root";
}

function secondaryBrowserChildren(node, folderValue) {
    const base = normalizePath(folderValue);
    const children = new Map();
    for (const fullPath of allFolderPaths(node)) {
        const normalized = normalizePath(fullPath);
        let remainder = normalized;
        if (base) {
            if (!normalized.startsWith(base + "/")) continue;
            remainder = normalized.slice(base.length + 1);
        }
        if (!remainder) continue;
        const leaf = remainder.split("/")[0];
        if (!leaf) continue;
        children.set(leaf, base ? `${base}/${leaf}` : leaf);
    }
    return [...children.entries()].sort((a, b) =>
        a[0].localeCompare(b[0], undefined, { sensitivity: "base" }),
    );
}

function secondaryBrowserDirectLoras(node, folderValue) {
    const base = normalizePath(folderValue);
    return allSecondaryBrowserLoras(node)
        .filter((value) => parentFolder(value) === base)
        .sort((a, b) =>
            loraBrowserBasename(a).localeCompare(loraBrowserBasename(b), undefined, { sensitivity: "base" }),
        );
}

function setSecondaryBrowserFolder(node, shell, value) {
    const next = normalizePath(value);
    shell.__soFolder = next;
    node.__soSecondaryBrowserFolder = next;
    shell.search.value = "";
}

function chooseSecondaryBrowserLora(node, targetSecondary, loraName, shell) {
    const selected = String(loraName ?? NONE);
    if (!selected || selected === NONE) return;

    let target = targetSecondary;
    if (!target) {
        target = (node.__soSecondaryWidgets || []).find((item) => !item.isPopulated());
    }
    if (!target) {
        console.warn(
            `[Sick Ollie Loader Core] Maximum of ${MAX_SECONDARY_LORAS} secondary LoRAs reached.`,
        );
        return;
    }

    const wasPopulated = target.isPopulated();
    const previousOn = Boolean(target.value.on);
    target.setLora(selected);
    // Preserve the established safety behavior for a newly-added secondary: it
    // is selected first, then explicitly enabled with its row toggle. Replacing
    // an existing row keeps that row's current on/off state.
    target.value.on = wasPopulated ? previousOn : false;
    node.__soSecondaryBrowserFolder = parentFolder(selected);
    refreshFixedSecondaryVisibility(node);
    layoutLoaderDashboard(node, true);
    node.setDirtyCanvas?.(true, true);
    closeSOFolderBrowser();
}

function renderSecondaryBrowser(node, shell, targetSecondary, query = "") {
    const folderValue = normalizePath(shell.__soFolder);
    shell.subtitleEl.textContent = secondaryBrowserFolderText(folderValue);
    shell.list.replaceChildren();
    const q = String(query ?? "").trim().toLowerCase();

    if (q) {
        const folderHits = allFolderPaths(node)
            .filter((path) => normalizePath(path).toLowerCase().includes(q))
            .slice(0, 120);
        const loraHits = allSecondaryBrowserLoras(node)
            .filter((value) => {
                const normalized = normalizePath(value).toLowerCase();
                return normalized.includes(q) || loraBrowserBasename(value).toLowerCase().includes(q);
            })
            .slice(0, 220);

        for (const path of folderHits) {
            browserRow(shell.list, normalizePath(path), "folder", () => {
                setSecondaryBrowserFolder(node, shell, path);
                renderSecondaryBrowser(node, shell, targetSecondary, "");
            }, path);
        }
        if (folderHits.length && loraHits.length) browserDivider(shell.list);
        for (const lora of loraHits) {
            const folder = parentFolder(lora) || "LoRA Root";
            browserRow(
                shell.list,
                `${loraBrowserBasename(lora)}   ·   ${folder}`,
                "file",
                () => chooseSecondaryBrowserLora(node, targetSecondary, lora, shell),
                lora,
            );
        }
        if (!folderHits.length && !loraHits.length) {
            browserRow(shell.list, "No matching folders or LoRAs", "action", () => {});
        }
        return;
    }

    if (folderValue) {
        browserRow(shell.list, "↑ Parent Folder", "action", () => {
            const slash = folderValue.lastIndexOf("/");
            setSecondaryBrowserFolder(node, shell, slash < 0 ? "" : folderValue.slice(0, slash));
            renderSecondaryBrowser(node, shell, targetSecondary, "");
        });
    }
    browserRow(shell.list, "⌂ LoRA Root", "action", () => {
        setSecondaryBrowserFolder(node, shell, "");
        renderSecondaryBrowser(node, shell, targetSecondary, "");
    });
    browserDivider(shell.list);

    const children = secondaryBrowserChildren(node, folderValue);
    for (const [leaf, path] of children) {
        browserRow(shell.list, leaf, "folder", () => {
            setSecondaryBrowserFolder(node, shell, path);
            renderSecondaryBrowser(node, shell, targetSecondary, "");
        }, path);
    }

    const directLoras = secondaryBrowserDirectLoras(node, folderValue);
    if (children.length && directLoras.length) browserDivider(shell.list);
    if (directLoras.length) {
        for (const lora of directLoras) {
            const active = targetSecondary?.isPopulated?.() && targetSecondary.value.lora === lora;
            browserRow(
                shell.list,
                `${active ? "✓  " : ""}${loraBrowserBasename(lora)}`,
                "file",
                () => chooseSecondaryBrowserLora(node, targetSecondary, lora, shell),
                lora,
            );
        }
    } else if (!children.length) {
        browserRow(shell.list, "No LoRAs in this folder", "action", () => {});
    }
}

function openSecondaryLoraBrowser(node, targetSecondary = null) {
    ensurePointerTracker();
    if (!targetSecondary) {
        const free = (node.__soSecondaryWidgets || []).some((item) => !item.isPopulated());
        if (!free) {
            console.warn(
                `[Sick Ollie Loader Core] Maximum of ${MAX_SECONDARY_LORAS} secondary LoRAs reached.`,
            );
            return;
        }
    }

    const selectedFolder = targetSecondary?.isPopulated?.()
        ? parentFolder(targetSecondary.value.lora)
        : normalizePath(node.__soSecondaryBrowserFolder);
    let shell;
    shell = createBrowserShell(
        "so-loader-folder-browser-popup",
        targetSecondary?.isPopulated?.() ? "Replace Secondary LoRA" : "Add Secondary LoRA",
        secondaryBrowserFolderText(selectedFolder),
        (query) => renderSecondaryBrowser(node, shell, targetSecondary, query),
    );
    shell.__soFolder = normalizePath(selectedFolder);
    shell.search.placeholder = "Filter folders or LoRAs";
    renderSecondaryBrowser(node, shell, targetSecondary, "");
}

function refreshLoaderFolderNavigator(node) {
    node.setDirtyCanvas?.(true, true);
}

function ensureLoaderFolderNavigator(node) {
    const folderWidget = widget(node, "folder_name");
    const mainWidget = widget(node, "main_lora");
    if (!folderWidget || !mainWidget) return;

    if (!Array.isArray(node.__soAllFolderChoices)) node.__soAllFolderChoices = readValues(folderWidget);
    hideNativeWidget(folderWidget);
    hideNativeWidget(mainWidget);

    // dev26/27 used a standalone frontend browser button. The dashboard owns
    // browsing now, so collapse any stale copy without touching saved values.
    if (node.__soFolderBrowserButton) hideNativeWidget(node.__soFolderBrowserButton);

    if (!folderWidget.__soNavigatorBound) {
        folderWidget.__soNavigatorBound = true;
        const previousCallback = folderWidget.callback;
        folderWidget.callback = function (...args) {
            const result = previousCallback?.apply(this, args);
            refreshLoaderFolderNavigator(node);
            return result;
        };
    }

    if (!mainWidget.__soBrowserLabelBound) {
        mainWidget.__soBrowserLabelBound = true;
        const previousCallback = mainWidget.callback;
        mainWidget.callback = function (...args) {
            const result = previousCallback?.apply(this, args);
            refreshLoaderFolderNavigator(node);
            return result;
        };
    }

    refreshLoaderFolderNavigator(node);
}

async function copyText(value) {
    const text = String(value ?? "");
    if (!text) return false;

    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (error) {}

    try {
        const input = document.createElement("textarea");
        input.value = text;
        input.style.position = "fixed";
        input.style.opacity = "0";
        document.body.append(input);
        input.select();
        document.execCommand("copy");
        input.remove();
        return true;
    } catch (error) {
        return false;
    }
}

function triggerCopyFeedback(node) {
    // Browsers cannot provide true desktop haptics, but supported devices can
    // vibrate briefly. The dashboard always provides a visual confirmation so
    // desktop users get the same immediate "click" feedback.
    try {
        if (typeof navigator?.vibrate === "function") navigator.vibrate(18);
    } catch (error) {}

    node.__soTriggerCopied = true;
    node.setDirtyCanvas?.(true, true);
    clearTimeout(node.__soTriggerCopiedTimer);
    node.__soTriggerCopiedTimer = setTimeout(() => {
        node.__soTriggerCopied = false;
        node.setDirtyCanvas?.(true, true);
    }, 850);
}

function folderMatches(loraName, folderName, includeSubfolders) {
    const parent = parentFolder(loraName);

    if (folderName === ALL_FOLDERS) return true;
    if (folderName === ROOT_FOLDER) return parent === "";
    if (folderName === FAVORITES_FOLDER || folderName === UNTESTED_FOLDER) return true;

    const selected = normalizePath(folderName);

    return includeSubfolders
        ? parent === selected || parent.startsWith(selected + "/")
        : parent === selected;
}

function epochNumber(loraName) {
    const normalized = normalizePath(loraName);
    const filename = normalized.slice(normalized.lastIndexOf("/") + 1);
    const stem = filename.replace(/\.[^.]+$/, "");
    const match = stem.match(/epoch[\s_-]*0*(\d+)/i);
    return match ? Number.parseInt(match[1], 10) : null;
}

function epochLabel(number) {
    return `Epoch ${Number(number)}`;
}

function parseCleanModeIndex(value) {
    const text = String(value ?? "").trim();
    const auto = text.match(/^auto:(\d+)$/i);
    if (auto) return Math.max(1, Number.parseInt(auto[1], 10));
    const direct = text.match(/^(\d+)\b/);
    if (direct) return Math.max(1, Number.parseInt(direct[1], 10));
    const keep = text.match(/keep[_:\s-]*(\d+)/i);
    if (keep) return Math.max(1, Number.parseInt(keep[1], 10));
    return 1;
}

function stemGroups(stem) {
    let value = String(stem ?? "")
        .trim()
        .replace(/^[ _\-.]+|[ _\-.]+$/g, "");
    if (!value) return [];

    const epochMatch = value.match(/(?:[_\-\s]|^)epoch[\s_-]*0*\d+$/i);
    let epochGroup = null;

    if (epochMatch) {
        epochGroup = epochMatch[0].replace(/^[ _\-.]+/g, "");
        value = value.slice(0, epochMatch.index).replace(/[ _\-.]+$/g, "");
    }

    const groups = value.split("_").filter(Boolean);
    if (epochGroup) groups.push(epochGroup);
    return groups;
}

function canonicalSuffixGroup(group) {
    const value = String(group ?? "").trim().toLowerCase();
    return /^epoch[\s_-]*0*\d+$/i.test(value) ? "<epoch>" : value;
}

function recognizedSuffixCount(stem) {
    const groups = stemGroups(stem);
    let count = 0;

    for (let index = groups.length - 1; index >= 0; index--) {
        const value = canonicalSuffixGroup(groups[index]);
        if (
            value === "<epoch>" ||
            /^(?:krea\d*|sickollie|sdxl|flux\d*|pony|illustrious|v\d+(?:\.\d+)*|ver\d+|version\d+|step\d+)$/i.test(value)
        ) {
            count++;
            continue;
        }
        break;
    }

    return Math.min(count, Math.max(0, groups.length - 1));
}

function commonSuffixCount(loraNames) {
    const grouped = (loraNames || [])
        .filter((name) => name && name !== NONE)
        .map((name) => {
            const normalized = normalizePath(name);
            const filename = normalized.slice(normalized.lastIndexOf("/") + 1);
            return stemGroups(filename.replace(/\.[^.]+$/, ""));
        })
        .filter((groups) => groups.length);

    if (!grouped.length) return 0;
    if (grouped.length === 1) {
        return recognizedSuffixCount(grouped[0].join("_"));
    }

    const maxDepth = Math.min(
        ...grouped.map((groups) => Math.max(0, groups.length - 1)),
    );
    let common = 0;

    for (let depth = 1; depth <= maxDepth; depth++) {
        const values = new Set(
            grouped.map((groups) => canonicalSuffixGroup(groups[groups.length - depth])),
        );
        if (values.size !== 1) break;
        common++;
    }

    return common;
}

function trimSuffixGroups(stem, count) {
    const groups = stemGroups(stem);
    const remove = Math.max(
        0,
        Math.min(Number(count) || 0, Math.max(0, groups.length - 1)),
    );
    const kept = remove ? groups.slice(0, -remove) : groups;
    return kept.join("_") || String(stem ?? "");
}

function delimiterPrefixes(stem) {
    const value = String(stem ?? "")
        .trim()
        .replace(/^[ _\-.]+|[ _\-.]+$/g, "");
    if (!value) return [];

    const prefixes = [];
    const delimiterPattern = /[_.\-\s]+/g;
    let match;
    while ((match = delimiterPattern.exec(value)) !== null) {
        const candidate = value
            .slice(0, match.index)
            .replace(/[ _\-.]+$/g, "");
        if (candidate && !prefixes.includes(candidate)) prefixes.push(candidate);
    }
    if (!prefixes.includes(value)) prefixes.push(value);
    return prefixes;
}

function cleanModeCandidate(value) {
    const text = String(value ?? "");
    const marker = text.indexOf("·");
    return marker >= 0 ? text.slice(marker + 1).trim() : "";
}

function currentMainStem(node) {
    const mainValue = String(widget(node, "main_lora")?.value ?? NONE);
    if (!mainValue || mainValue === NONE) return "clean_name";
    const normalized = normalizePath(mainValue);
    const filename = normalized.slice(normalized.lastIndexOf("/") + 1);
    return filename.replace(/\.[^.]+$/, "") || "clean_name";
}

function cleanNameModeChoices(node) {
    const stem = currentMainStem(node);
    const prefixes = delimiterPrefixes(stem);
    const choices = prefixes.map(
        (candidate, index) => `${index + 1} · ${candidate}`,
    );
    return choices.length ? choices : [`1 · ${stem}`];
}

function legacyRecommendedCleanName(node, modeIndex = 1) {
    const stem = currentMainStem(node);
    const shared = Math.max(
        commonSuffixCount(allowedMainLoras(node)),
        recognizedSuffixCount(stem),
    );
    const remove = Math.max(0, shared - (Math.max(1, modeIndex) - 1));
    return trimSuffixGroups(stem, remove);
}

function ensureCleanNameCombo(node) {
    const existing = widget(node, "cleanup_rules");
    if (!existing || existing.__soCleanNameCombo) return existing;

    const index = node.widgets?.indexOf(existing) ?? -1;
    const savedValue = existing.value;

    // The Python input remains a STRING in the same serialized slot, but the
    // frontend widget itself must be a genuine LiteGraph combo. Merely changing
    // an existing STRING widget's `type` leaves its text-editor mouse behavior
    // attached, which is what caused the generic Value popup.
    try {
        existing.inputEl?.remove?.();
    } catch (error) {}
    try {
        existing.onRemove?.();
    } catch (error) {}

    const combo = node.addWidget(
        "combo",
        "cleanup_rules",
        savedValue,
        () => {
            publishLoaderLiveOutputs(node);
            node.setDirtyCanvas?.(true, true);
        },
        { values: [] },
    );

    combo.label = "clean_name";
    combo.__soCleanNameCombo = true;
    combo.options = combo.options || {};
    combo.options.serialize = true;

    const appendedIndex = node.widgets?.indexOf(combo) ?? -1;
    if (index >= 0 && appendedIndex >= 0 && appendedIndex !== index) {
        node.widgets.splice(appendedIndex, 1);
        node.widgets.splice(index, 1, combo);
    }

    return combo;
}

function refreshCleanNameChoices(node) {
    const cleanWidget = ensureCleanNameCombo(node);
    if (!cleanWidget) return;

    const previousValue = String(cleanWidget.value ?? "");
    const previousCandidate = cleanModeCandidate(previousValue);
    const currentIndex = parseCleanModeIndex(previousValue);
    const choices = cleanNameModeChoices(node);

    writeValues(cleanWidget, choices);

    // If an existing saved candidate is still valid for this filename, keep it
    // selected. This avoids changing old workflows merely because the dropdown
    // now exposes more delimiter-based choices.
    const exact = previousCandidate
        ? choices.find((choice) => cleanModeCandidate(choice) === previousCandidate)
        : null;

    const legacyCandidate = !previousCandidate
        ? legacyRecommendedCleanName(node, currentIndex)
        : "";
    const legacyMatch = legacyCandidate
        ? choices.find((choice) => cleanModeCandidate(choice) === legacyCandidate)
        : null;

    cleanWidget.value = exact ?? legacyMatch ??
        choices[Math.min(Math.max(currentIndex, 1), choices.length) - 1] ??
        choices[0];

    publishLoaderLiveOutputs(node);
    node.setDirtyCanvas?.(true, true);
}

function folderScopedLoras(node) {
    const folderName =
        widget(node, "folder_name")?.value ?? ALL_FOLDERS;
    const includeSubfolders = Boolean(
        widget(node, "include_subfolders")?.value,
    );

    const collection = collectionForScope(node, folderName);
    const collectionMembers = collection
        ? new Set((collection.lora_names || []).map((value) => normalizePath(value).toLowerCase()))
        : null;
    let names = (node.__soAllMainLoras || []).filter(
        (name) =>
            name !== NONE &&
            (collectionMembers
                ? collectionMembers.has(normalizePath(name).toLowerCase())
                : folderMatches(name, folderName, includeSubfolders)),
    );
    const libraryFilter = String(widget(node, "library_filter")?.value ?? ALL_LIBRARY_STATES);
    const effectiveFilter = folderName === FAVORITES_FOLDER ? FAVORITES_FILTER : folderName === UNTESTED_FOLDER ? UNTESTED_FILTER : libraryFilter;
    if (effectiveFilter === FAVORITES_FILTER) names = names.filter((name) => loraReviewState(node, name) === "favorite");
    if (effectiveFilter === TESTED_FILTER) names = names.filter((name) => loraUseCount(node, name) > 0 && loraReviewState(node, name) !== "retest");
    if (effectiveFilter === UNTESTED_FILTER) names = names.filter((name) => loraUseCount(node, name) === 0 || loraReviewState(node, name) === "retest");
    return names;
}

function epochMatches(loraName, filterValue) {
    const selected = String(filterValue ?? ALL_EPOCHS);
    if (selected === ALL_EPOCHS) return true;

    const number = epochNumber(loraName);
    if (selected === NO_EPOCH_TAG) return number == null;

    const match = selected.match(/^Epoch\s+(\d+)$/i);
    if (!match) return true;
    return number === Number.parseInt(match[1], 10);
}

function detectedEpochChoices(node) {
    const names = folderScopedLoras(node);
    const numbers = [...new Set(
        names
            .map(epochNumber)
            .filter((number) => Number.isInteger(number)),
    )].sort((a, b) => a - b);

    const choices = [ALL_EPOCHS, ...numbers.map(epochLabel)];
    if (numbers.length && names.some((name) => epochNumber(name) == null)) {
        choices.push(NO_EPOCH_TAG);
    }
    return choices;
}

function refreshEpochChoices(node) {
    const epochWidget = widget(node, "epoch_filter");
    if (!epochWidget) return;

    const choices = detectedEpochChoices(node);
    writeValues(epochWidget, choices);

    const current = String(epochWidget.value ?? ALL_EPOCHS);
    if (!choices.includes(current)) {
        epochWidget.value = ALL_EPOCHS;
        try {
            epochWidget.callback?.(epochWidget.value);
        } catch (error) {}
    }

    node.setDirtyCanvas?.(true, true);
}

function allowedMainLoras(node) {
    const epochFilter =
        widget(node, "epoch_filter")?.value ?? ALL_EPOCHS;

    const names = folderScopedLoras(node).filter(
        (name) => epochMatches(name, epochFilter),
    );
    const sortMode = String(widget(node, "lora_sort")?.value ?? "Name");
    if (sortMode === "Most used") return names.sort((a, b) => loraUseCount(node, b) - loraUseCount(node, a) || a.localeCompare(b));
    if (sortMode === "Least used") return names.sort((a, b) => loraUseCount(node, a) - loraUseCount(node, b) || a.localeCompare(b));
    if (sortMode === "Recently used") {
        return names.sort((a, b) => loraLastUsed(node, b).localeCompare(loraLastUsed(node, a)) || a.localeCompare(b));
    }
    return names.sort((a, b) => a.localeCompare(b));
}

function refreshMainChoices(node, chooseFirst = false) {
    const mainWidget = widget(node, "main_lora");
    if (!mainWidget) return;

    const allowed = allowedMainLoras(node);
    const displayed = [NONE, ...allowed];

    writeValues(mainWidget, displayed);

    const current = String(mainWidget.value ?? NONE);

    if (chooseFirst || !displayed.includes(current)) {
        mainWidget.value = allowed[0] ?? NONE;
        try {
            mainWidget.callback?.(mainWidget.value);
        } catch (error) {}
    }

    node.setDirtyCanvas?.(true, true);
}

function shuffledCopy(values) {
    const result = [...values];
    for (let index = result.length - 1; index > 0; index--) {
        const swap = Math.floor(Math.random() * (index + 1));
        [result[index], result[swap]] = [result[swap], result[index]];
    }
    return result;
}

function loaderShuffleState(node) {
    node.properties = node.properties || {};
    const existing = node.properties.so_loader_shuffle_state;
    if (!existing || typeof existing !== "object") {
        node.properties.so_loader_shuffle_state = {};
    }
    return node.properties.so_loader_shuffle_state;
}

function nextShuffledMainValue(node, cycle, current, loop) {
    if (!cycle.length) return NONE;
    if (cycle.length === 1) return cycle[0];

    const key = cycle.join("\u001f");
    const state = loaderShuffleState(node);

    if (state.key !== key || !Array.isArray(state.remaining)) {
        state.key = key;
        // The current value is the value that was just queued, so consider it
        // consumed when beginning a fresh bag.
        state.remaining = shuffledCopy(cycle.filter((value) => value !== current));
        state.last = current;
    }

    // Remove the just-used value if it is still waiting in the bag. This also
    // makes a manually selected LoRA count as consumed for the current cycle.
    state.remaining = state.remaining.filter((value) => value !== current);

    if (!state.remaining.length) {
        if (!loop) {
            state.last = current;
            return current;
        }
        state.remaining = shuffledCopy(cycle.filter((value) => value !== current));
    }

    const next = state.remaining.shift() ?? current;
    state.last = next;
    return next;
}

function nextMainValue(node) {
    const mainWidget = widget(node, "main_lora");
    const mode = String(
        widget(node, "control_after_generate")?.value ?? "fixed",
    );
    const loop = Boolean(widget(node, "loop_folder")?.value);
    const skipNone = Boolean(
        widget(node, "skip_none_during_cycle")?.value,
    );

    if (!mainWidget || mode === "fixed") return mainWidget?.value;

    const allowed = allowedMainLoras(node);
    const cycle = skipNone ? allowed : [NONE, ...allowed];

    if (!cycle.length) return NONE;

    const current = String(mainWidget.value ?? NONE);
    let index = cycle.indexOf(current);

    if (mode === "randomize") {
        const pool = cycle.filter((value) => value !== current);
        return pool.length
            ? pool[Math.floor(Math.random() * pool.length)]
            : cycle[0];
    }

    if (mode === "shuffle") {
        return nextShuffledMainValue(node, cycle, current, loop);
    }

    if (index < 0) {
        return mode === "decrement"
            ? cycle[cycle.length - 1]
            : cycle[0];
    }

    if (mode === "increment") {
        if (index < cycle.length - 1) return cycle[index + 1];
        return loop ? cycle[0] : cycle[cycle.length - 1];
    }

    if (mode === "decrement") {
        if (index > 0) return cycle[index - 1];
        return loop ? cycle[cycle.length - 1] : cycle[0];
    }

    return current;
}

function advanceMainAfterQueued(node) {
    const mainWidget = widget(node, "main_lora");
    if (!mainWidget) return;

    const next = nextMainValue(node);

    if (next == null || String(next) === String(mainWidget.value)) {
        return;
    }

    mainWidget.value = next;

    try {
        mainWidget.callback?.(next);
    } catch (error) {}

    node.setDirtyCanvas?.(true, true);
}

function diffusionShuffleState(node) {
    node.properties = node.properties || {};
    const existing = node.properties.so_loader_diffusion_shuffle_state;
    if (!existing || typeof existing !== "object") {
        node.properties.so_loader_diffusion_shuffle_state = {};
    }
    return node.properties.so_loader_diffusion_shuffle_state;
}

function nextShuffledDiffusionValue(node, cycle, current) {
    if (!cycle.length) return current;
    if (cycle.length === 1) return cycle[0];

    const key = cycle.join("\u001f");
    const state = diffusionShuffleState(node);
    if (state.key !== key || !Array.isArray(state.remaining)) {
        state.key = key;
        state.remaining = shuffledCopy(cycle.filter((value) => value !== current));
    }
    state.remaining = state.remaining.filter((value) => value !== current);
    if (!state.remaining.length) {
        state.remaining = shuffledCopy(cycle.filter((value) => value !== current));
    }
    return state.remaining.shift() ?? current;
}

function nextDiffusionModelValue(node) {
    const modelWidget = widget(node, "diffusion_model");
    const mode = String(widget(node, "diffusion_control_after_generate")?.value ?? "fixed");
    if (!modelWidget || mode === "fixed") return modelWidget?.value;

    const cycle = readValues(modelWidget).map(String).filter(Boolean);
    if (!cycle.length) return modelWidget.value;
    const current = String(modelWidget.value ?? cycle[0]);
    let index = cycle.indexOf(current);

    if (mode === "randomize") {
        const pool = cycle.filter((value) => value !== current);
        return pool.length ? pool[Math.floor(Math.random() * pool.length)] : cycle[0];
    }
    if (mode === "shuffle") return nextShuffledDiffusionValue(node, cycle, current);
    if (index < 0) return mode === "decrement" ? cycle[cycle.length - 1] : cycle[0];
    if (mode === "increment") return cycle[(index + 1) % cycle.length];
    if (mode === "decrement") return cycle[(index - 1 + cycle.length) % cycle.length];
    return current;
}

function advanceDiffusionAfterQueued(node) {
    const modelWidget = widget(node, "diffusion_model");
    if (!modelWidget) return;
    const next = nextDiffusionModelValue(node);
    if (next == null || String(next) === String(modelWidget.value)) return;
    modelWidget.value = next;
    try { modelWidget.callback?.(next); } catch (error) {}
    node.setDirtyCanvas?.(true, true);
}


function displayTriggerValue(value) {
    const text = String(value ?? "").trim();
    return text.length ? text : "none";
}

function mainLoraTriggerActive(node) {
    const selected = String(widget(node, "main_lora")?.value ?? NONE).trim();
    const enabled = Boolean(widget(node, "main_enabled")?.value);
    const strength = Number(widget(node, "main_strength")?.value ?? 0);
    return enabled && Boolean(selected) && selected !== NONE && Number.isFinite(strength) && strength !== 0;
}

function showMainLoraInfo(node) {
    const value = String(widget(node, "main_lora")?.value ?? NONE);
    if (!value || value === NONE) return;
    const dialog = new RgthreeLoraInfoDialog(value).show();
    // This is deliberately the same metadata dialog used by Secondary LoRAs,
    // so the Main LoRA finally has an honest Civitai/metadata inspection path
    // without asking users to temporarily add it as a secondary.
    dialog.addEventListener?.("close", () => node.setDirtyCanvas?.(true, true));
}

async function fetchMainTriggerFromServer(mainValue) {
    const value = String(mainValue ?? "").trim();
    if (!value || value === NONE) {
        return { trigger: "", source: "" };
    }

    const url = `/sickollie/studio/loader-core/main-trigger?lora=${encodeURIComponent(value)}`;
    const response = await fetch(url, { method: "GET" });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    return {
        trigger: String(payload?.trigger ?? "").trim(),
        source: String(payload?.source ?? "").trim(),
    };
}

async function fetchTriggerOverrideState(loraName) {
    const value = String(loraName ?? "").trim();
    if (!value || value === NONE) return {
        override: "", source: "", exact_override: "", exact_source: "",
        family_override: "", family_source: "", family_available: false,
        family_pattern: "", family_folder: "", family_count: 0, family_members: [],
        automatic: "", automatic_source: "",
    };
    const response = await fetch(`/sickollie/studio/loader-core/trigger-override?lora=${encodeURIComponent(value)}`, { method: "GET" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `HTTP ${response.status}`);
    return {
        override: String(payload?.override ?? "").trim(),
        source: String(payload?.source ?? "").trim(),
        exact_override: String(payload?.exact_override ?? "").trim(),
        exact_source: String(payload?.exact_source ?? "").trim(),
        family_override: String(payload?.family_override ?? "").trim(),
        family_source: String(payload?.family_source ?? "").trim(),
        family_available: Boolean(payload?.family_available),
        family_pattern: String(payload?.family_pattern ?? "").trim(),
        family_folder: String(payload?.family_folder ?? "").trim(),
        family_count: Math.max(0, Number(payload?.family_count || 0)),
        family_members: Array.isArray(payload?.family_members) ? payload.family_members.map((item) => String(item ?? "")) : [],
        automatic: String(payload?.automatic ?? "").trim(),
        automatic_source: String(payload?.automatic_source ?? "").trim(),
    };
}

async function saveTriggerOverrideToServer(loraName, trigger, scope = "lora") {
    const response = await fetch(`/sickollie/studio/loader-core/trigger-override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            lora: String(loraName ?? ""),
            trigger: String(trigger ?? ""),
            scope: String(scope || "lora"),
        }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `HTTP ${response.status}`);
    return payload;
}

async function clearTriggerOverrideOnServer(loraName, scope = "lora") {
    const response = await fetch(`/sickollie/studio/loader-core/trigger-override?lora=${encodeURIComponent(String(loraName ?? ""))}&scope=${encodeURIComponent(String(scope || "lora"))}`, { method: "DELETE" });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload?.ok === false) throw new Error(payload?.error || `HTTP ${response.status}`);
    return payload;
}

function triggerSourceLabel(source) {
    const value = String(source ?? "");
    if (value === "user.family_override") return "Epoch-family override";
    if (value.startsWith("user.")) return "Custom override";
    if (value.startsWith("civitai")) return "Civitai";
    if (value === "ss_tag_frequency") return "training tags";
    if (value.startsWith("modelspec") || value.includes("trigger")) return "embedded metadata";
    return value || "none detected";
}

async function showTriggerOverrideEditor(node, loraName, afterChange = null) {
    const selected = String(loraName ?? "").trim();
    if (!selected || selected === NONE) return;

    let state;
    try {
        state = await fetchTriggerOverrideState(selected);
    } catch (error) {
        alert(error.message || "Could not read this LoRA's trigger settings.");
        return;
    }

    const overlay = document.createElement("div");
    Object.assign(overlay.style, {
        position: "fixed", inset: "0", zIndex: "100000", display: "grid", placeItems: "center",
        background: "rgba(4,3,7,.78)", backdropFilter: "blur(3px)", padding: "22px",
    });
    const card = document.createElement("section");
    Object.assign(card.style, {
        width: "700px", maxWidth: "94vw", maxHeight: "92vh", overflow: "auto", borderRadius: "13px",
        color: "#f4f1f6", border: "1px solid rgba(184,154,255,.72)",
        background: "linear-gradient(145deg,#17131f,#0b0910)",
        boxShadow: "0 24px 80px rgba(0,0,0,.72)", fontFamily: "Segoe UI,Arial,sans-serif",
    });
    const head = document.createElement("div");
    Object.assign(head.style, { padding: "14px 16px 12px", borderBottom: "1px solid rgba(184,154,255,.22)" });
    const title = document.createElement("div"); title.textContent = "CUSTOM LoRA TRIGGER";
    Object.assign(title.style, { color: "#d4c4ff", fontWeight: "800", fontSize: "13px", letterSpacing: ".07em" });
    const model = document.createElement("div"); model.textContent = selected;
    Object.assign(model.style, { marginTop: "5px", color: "#8f8997", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
    head.append(title, model);

    const body = document.createElement("div");
    Object.assign(body.style, { padding: "14px 16px", display: "grid", gap: "11px" });

    const help = document.createElement("div");
    help.textContent = "Save a trigger for only this LoRA, or share it across matching epoch files in the same folder. Exact LoRA overrides always win over family rules; automatic metadata/Civitai detection is only used when neither saved rule exists.";
    Object.assign(help.style, { color: "#b7b0bd", fontSize: "11px", lineHeight: "1.45" });

    const detected = document.createElement("div");
    Object.assign(detected.style, { padding: "10px 11px", borderRadius: "8px", border: "1px solid #34303b", background: "rgba(255,255,255,.025)" });
    const detectedLabel = document.createElement("div"); detectedLabel.textContent = `AUTOMATIC FALLBACK · ${triggerSourceLabel(state.automatic_source)}`;
    Object.assign(detectedLabel.style, { color: "#77717f", fontSize: "9px", fontWeight: "800", letterSpacing: ".06em" });
    const detectedValue = document.createElement("div"); detectedValue.textContent = state.automatic || "No automatic trigger detected";
    Object.assign(detectedValue.style, { marginTop: "5px", color: state.automatic ? "#d9d4de" : "#77717f", fontSize: "11px", lineHeight: "1.4", wordBreak: "break-word" });
    detected.append(detectedLabel, detectedValue);

    const scopeWrap = document.createElement("div");
    Object.assign(scopeWrap.style, { display: "grid", gap: "7px" });
    const scopeTitle = document.createElement("div"); scopeTitle.textContent = "SAVE SCOPE";
    Object.assign(scopeTitle.style, { color: "#b89aff", fontSize: "9px", fontWeight: "800", letterSpacing: ".07em" });
    scopeWrap.append(scopeTitle);

    let selectedScope = state.family_override && !state.exact_override ? "family" : "lora";
    const familyUsable = Boolean(state.family_pattern && (state.family_available || state.family_override));
    if (selectedScope === "family" && !familyUsable) selectedScope = "lora";

    const scopeGroupName = `so-trigger-scope-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const makeScope = (scope, heading, detail, enabled = true) => {
        const label = document.createElement("label");
        Object.assign(label.style, {
            display: "grid", gridTemplateColumns: "18px 1fr", gap: "9px", alignItems: "start",
            padding: "9px 10px", borderRadius: "8px", cursor: enabled ? "pointer" : "default",
            border: `1px solid ${scope === "family" ? "#35d7ff55" : "#b89aff55"}`,
            background: "rgba(255,255,255,.02)", opacity: enabled ? "1" : ".4",
        });
        const radio = document.createElement("input");
        radio.type = "radio"; radio.name = scopeGroupName; radio.value = scope;
        radio.checked = selectedScope === scope; radio.disabled = !enabled;
        radio.onchange = () => {
            if (!radio.checked) return;
            selectedScope = scope;
            updateSaveLabel();
        };
        const copy = document.createElement("div");
        const h = document.createElement("div"); h.textContent = heading;
        Object.assign(h.style, { fontSize: "10px", fontWeight: "800", color: "#eeeaf1" });
        const d = document.createElement("div"); d.textContent = detail;
        Object.assign(d.style, { marginTop: "3px", fontSize: "9px", lineHeight: "1.35", color: "#8f8997" });
        copy.append(h, d); label.append(radio, copy);
        return label;
    };

    const exactDetail = state.exact_override
        ? "This file already has its own saved override."
        : "A one-file exception. It takes priority over any matching family rule.";
    scopeWrap.append(makeScope("lora", "THIS LoRA ONLY", exactDetail, true));

    const familyDetail = state.family_pattern
        ? `${state.family_pattern} · ${state.family_count || 0} matching LoRA${state.family_count === 1 ? "" : "s"} · same folder only${state.family_folder ? ` · ${state.family_folder}` : ""}. New matching epochs inherit this rule automatically.`
        : "No epoch token was found in this filename, so a safe family rule cannot be built.";
    scopeWrap.append(makeScope(
        "family",
        `MATCHING EPOCH FAMILY${state.family_count ? ` · ${state.family_count}` : ""}`,
        familyDetail,
        familyUsable,
    ));

    if (state.family_override) {
        const familyActive = document.createElement("div");
        Object.assign(familyActive.style, { padding: "9px 10px", borderRadius: "8px", border: "1px solid #35d7ff44", background: "rgba(53,215,255,.045)" });
        const a = document.createElement("div"); a.textContent = "SAVED EPOCH-FAMILY OVERRIDE";
        Object.assign(a.style, { color: "#35d7ff", fontSize: "9px", fontWeight: "800", letterSpacing: ".06em" });
        const v = document.createElement("div"); v.textContent = state.family_override;
        Object.assign(v.style, { marginTop: "4px", color: "#dcecf0", fontSize: "10px", lineHeight: "1.4", wordBreak: "break-word" });
        familyActive.append(a, v);
        scopeWrap.append(familyActive);
    }

    const label = document.createElement("label"); label.textContent = "TRIGGER OVERRIDE";
    Object.assign(label.style, { color: "#b89aff", fontSize: "9px", fontWeight: "800", letterSpacing: ".07em" });
    const input = document.createElement("textarea");
    input.value = state.exact_override || state.family_override || "";
    input.placeholder = "e.g. karissa, freckles, large round green eyes, ...";
    Object.assign(input.style, {
        width: "100%", minHeight: "92px", resize: "vertical", boxSizing: "border-box", padding: "10px 11px",
        borderRadius: "8px", border: "1px solid rgba(184,154,255,.58)", outline: "none", color: "#f5f1f7",
        background: "#0d0b12", font: "12px/1.45 Segoe UI,Arial",
    });
    label.append(input);

    const hint = document.createElement("div");
    hint.textContent = "Family matching changes only the epoch number after “epoch” or “ep”. The rest of the filename and the parent folder must match exactly.";
    Object.assign(hint.style, { color: "#77717f", fontSize: "9px", lineHeight: "1.35" });
    body.append(help, detected, scopeWrap, label, hint);

    const foot = document.createElement("div");
    Object.assign(foot.style, { display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center", padding: "0 16px 15px" });
    const makeButton = (text, border, fill = "rgba(255,255,255,.025)") => {
        const button = document.createElement("button"); button.type = "button"; button.textContent = text;
        Object.assign(button.style, { padding: "8px 11px", borderRadius: "7px", border: `1px solid ${border}`, background: fill, color: "#f4f1f6", cursor: "pointer", font: "700 10px Segoe UI,Arial" });
        return button;
    };
    const useDetected = makeButton("USE DETECTED", "#35d7ff77");
    useDetected.disabled = !state.automatic; useDetected.style.opacity = state.automatic ? "1" : ".35";
    useDetected.onclick = () => { if (state.automatic) { input.value = state.automatic; input.focus(); } };

    const clearExact = makeButton("CLEAR THIS LoRA", "#ff9b5f77");
    clearExact.style.display = state.exact_override ? "inline-block" : "none";
    const clearFamily = makeButton("CLEAR FAMILY", "#35d7ff77");
    clearFamily.style.display = state.family_override ? "inline-block" : "none";

    const spacer = document.createElement("div"); spacer.style.flex = "1";
    const cancel = makeButton("CANCEL", "#5c5663"); cancel.onclick = () => overlay.remove();
    const save = makeButton("", "#b89aff", "rgba(184,154,255,.12)");
    function updateSaveLabel() {
        save.textContent = selectedScope === "family" ? "SAVE EPOCH FAMILY" : "SAVE THIS LoRA";
    }
    updateSaveLabel();

    const refresh = async () => {
        await refreshMainTrigger(node, true);
        try { await afterChange?.(); } catch (error) {}
        node.setDirtyCanvas?.(true, true);
    };
    const haptic = () => { try { navigator.vibrate?.(18); } catch (error) {} };

    clearExact.onclick = async () => {
        clearExact.disabled = true; save.disabled = true; clearExact.textContent = "CLEARING…";
        try {
            await clearTriggerOverrideOnServer(selected, "lora");
            haptic(); overlay.remove(); await refresh();
        } catch (error) {
            clearExact.disabled = false; save.disabled = false; clearExact.textContent = "CLEAR THIS LoRA";
            alert(error.message || "Could not clear the saved LoRA trigger override.");
        }
    };
    clearFamily.onclick = async () => {
        clearFamily.disabled = true; save.disabled = true; clearFamily.textContent = "CLEARING…";
        try {
            await clearTriggerOverrideOnServer(selected, "family");
            haptic(); overlay.remove(); await refresh();
        } catch (error) {
            clearFamily.disabled = false; save.disabled = false; clearFamily.textContent = "CLEAR FAMILY";
            alert(error.message || "Could not clear the saved epoch-family trigger override.");
        }
    };
    save.onclick = async () => {
        const value = String(input.value ?? "").trim();
        if (!value) { input.focus(); return; }
        save.disabled = true; clearExact.disabled = true; clearFamily.disabled = true;
        const previousText = save.textContent; save.textContent = "SAVING…";
        try {
            await saveTriggerOverrideToServer(selected, value, selectedScope);
            haptic(); overlay.remove(); await refresh();
        } catch (error) {
            save.disabled = false; clearExact.disabled = false; clearFamily.disabled = false; save.textContent = previousText;
            alert(error.message || "Could not save the trigger override.");
        }
    };

    foot.append(useDetected, clearExact, clearFamily, spacer, cancel, save);
    card.append(head, body, foot); overlay.append(card); document.body.append(overlay);
    overlay.addEventListener("pointerdown", (event) => { if (event.target === overlay) overlay.remove(); });
    requestAnimationFrame(() => input.focus());
}

function updateTriggerButton(node) {
    const text = String(node.__soMainTrigger ?? "").trim();
    if (node.__soTriggerButton) {
        node.__soTriggerButton.name = `📋 Copy trigger: ${displayTriggerValue(text)}`;
    }
    node.setDirtyCanvas?.(true, true);
}

function flashTriggerButton(node, button, normalName) {
    if (!button) return;
    button.name = `✓ Copied ${normalName.replace(/^📋 Copy\s*/, "")}`;
    node.setDirtyCanvas?.(true, true);

    clearTimeout(button.__soResetTimer);
    button.__soResetTimer = setTimeout(() => {
        button.name = normalName;
        node.setDirtyCanvas?.(true, true);
    }, 850);
}

function ensureTriggerButton(node) {
    if (node.__soTriggerButton) return node.__soTriggerButton;

    node.__soMainTrigger = String(node.__soMainTrigger ?? "");

    const button = node.addWidget(
        "button",
        "📋 Copy trigger: none",
        null,
        async () => {
            const value = String(node.__soMainTrigger ?? "").trim();
            if (!value) return;
            const normalName = `📋 Copy trigger: ${displayTriggerValue(value)}`;
            if (await copyText(value)) {
                triggerCopyFeedback(node);
                flashTriggerButton(node, button, normalName);
            }
        },
        { serialize: false },
    );

    button.serialize = false;
    node.__soTriggerButton = button;

    const cleanWidget = widget(node, "cleanup_rules");
    const secondaryDivider = node.__soSecondaryDivider;
    if (Array.isArray(node.widgets)) {
        const buttonIndex = node.widgets.indexOf(button);
        if (buttonIndex >= 0) node.widgets.splice(buttonIndex, 1);
        let insertAt = node.widgets.length;
        if (secondaryDivider && node.widgets.includes(secondaryDivider)) {
            insertAt = node.widgets.indexOf(secondaryDivider);
        } else if (cleanWidget && node.widgets.includes(cleanWidget)) {
            insertAt = node.widgets.indexOf(cleanWidget) + 1;
        }
        node.widgets.splice(insertAt, 0, button);
    }

    updateTriggerButton(node);
    return button;
}

async function refreshMainTrigger(node, force = false) {
    const mainValue = String(widget(node, "main_lora")?.value ?? NONE);
    const requestId = Number(node.__soMainTriggerRequestId || 0) + 1;
    node.__soMainTriggerRequestId = requestId;
    node.__soMainTrigger = "";
    node.__soMainTriggerSource = "";
    publishLoaderLiveOutputs(node);

    // Trigger output mirrors the *applied* Main LoRA, not merely the selected
    // filename. Turning Main off (or setting its strength to zero) must
    // immediately make the connected Prompt Core see an empty trigger.
    if (!mainLoraTriggerActive(node)) {
        updateTriggerButton(node);
        publishLoaderLiveOutputs(node);
        return "";
    }

    try {
        const resolved = await fetchMainTriggerFromServer(mainValue);
        // A previous LoRA lookup must never overwrite a newer selection.
        if (node.__soMainTriggerRequestId !== requestId || String(widget(node, "main_lora")?.value ?? NONE) !== mainValue) {
            return String(node.__soMainTrigger ?? "");
        }
        node.__soMainTrigger = resolved.trigger;
        node.__soMainTriggerSource = resolved.source;
    } catch (error) {
        if (node.__soMainTriggerRequestId !== requestId) return String(node.__soMainTrigger ?? "");
        console.warn(
            "[Sick Ollie Loader Core] Could not resolve the main LoRA trigger",
            error,
        );
        node.__soMainTrigger = "";
        node.__soMainTriggerSource = "";
    }

    updateTriggerButton(node);
    publishLoaderLiveOutputs(node);
    return node.__soMainTrigger;
}


const DASH_MIN_WIDTH = STUDIO_LAYOUT.minWidth;
const DASH_PAD = STUDIO_LAYOUT.pad;
const DASH_GAP = STUDIO_LAYOUT.gap;
const DASH_ROW_H = STUDIO_LAYOUT.rowHeight;
const DASH_SECTION_GAP = STUDIO_LAYOUT.sectionGap;
const DASH_COLLAPSED_H = 437;
const DASH_EXPANDED_H = 473;
const SECONDARY_ROW_H = 40;
const SECONDARY_HEADER_H = 18;
const SECONDARY_ADD_H = 34;

// Loader Core has four visible outputs but no visible inputs. Stock LiteGraph
// stacks those outputs at the full node-slot spacing, which leaves a noticeably
// larger empty shelf above the dashboard than the other Studio Core nodes.
// Keep the sockets and labels intact, but compact just this output stack so the
// MODEL card can sit at the same visual height as its siblings.
const LOADER_OUTPUT_START_Y = STUDIO_LAYOUT.socketStart;
const LOADER_OUTPUT_STEP_Y = STUDIO_LAYOUT.socketStep;
const LOADER_DASH_MIN_TOP = STUDIO_LAYOUT.headerHeight + STUDIO_LAYOUT.socketGap;

const DASH_COLORS = {
    card: STUDIO_THEME.panel,
    row: STUDIO_THEME.row,
    outline: STUDIO_THEME.outline,
    label: STUDIO_THEME.label,
    text: STUDIO_THEME.text,
    cyan: STUDIO_THEME.cyan,
    magenta: STUDIO_THEME.magenta,
    yellow: STUDIO_THEME.yellow,
    green: STUDIO_THEME.green,
    accent: STUDIO_THEME.magenta,
};

function layoutLoaderOutputSockets(node) {
    const outputs = node.outputs || [];
    const right = Number(node.size?.[0] || DASH_MIN_WIDTH);

    for (let index = 0; index < outputs.length; index++) {
        const y = LOADER_OUTPUT_START_Y + index * LOADER_OUTPUT_STEP_Y;
        outputs[index].pos = [right, y];
    }
}

function loaderOutputBottom(node) {
    const count = node.outputs?.length || 0;
    if (!count) return 44;
    return LOADER_OUTPUT_START_Y + (count - 1) * LOADER_OUTPUT_STEP_Y + 7;
}

function loaderOutputAnchor(node, slotIndex) {
    const output = node.outputs?.[slotIndex];
    if (!output) return null;
    layoutLoaderOutputSockets(node);
    const y = Number(output.pos?.[1]);
    if (!Number.isFinite(y)) return null;
    return { x: Number(node.size?.[0] || DASH_MIN_WIDTH), y };
}

function loaderDashboardTop(node) {
    layoutLoaderOutputSockets(node);
    return Math.max(LOADER_DASH_MIN_TOP, loaderOutputBottom(node) + STUDIO_LAYOUT.socketGap);
}

function secondaryDashboardSectionHeight(node) {
    const count = secondaryVisibleRows(node).length;
    const rowsHeight = count
        ? count * SECONDARY_ROW_H + Math.max(0, count - 1) * DASH_GAP + DASH_GAP
        : 0;
    return SECONDARY_HEADER_H + rowsHeight + SECONDARY_ADD_H + 9;
}

function loaderDashboardHeight(node) {
    const base = node.properties?.so_loader_dashboard_advanced ? DASH_EXPANDED_H : DASH_COLLAPSED_H;
    return base + DASH_SECTION_GAP + secondaryDashboardSectionHeight(node);
}

function drawRoundRect(ctx, x, y, w, h, radius = 7, fill = null, stroke = null) {
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
    if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
}

function drawCMYKGFrame(ctx, x, y, w, h, radius = 9, alpha = .48, accent = DASH_COLORS.magenta) {
    drawStudioSectionFrame(ctx, x, y, w, h, accent, radius, alpha);
}

function dashText(ctx, text, x, y, options = {}) {
    ctx.save();
    ctx.fillStyle = options.color || DASH_COLORS.text;
    ctx.font = options.font || "12px Arial";
    ctx.textAlign = options.align || "left";
    ctx.textBaseline = "middle";
    ctx.fillText(String(text ?? ""), x, y);
    ctx.restore();
}

function dashSection(ctx, label, x, y, color = DASH_COLORS.label) {
    dashText(ctx, String(label).toUpperCase(), x, y, { color, font: "700 10px Arial" });
}

function dashValueRow(ctx, x, y, w, h, label, value, options = {}) {
    drawRoundRect(ctx, x, y, w, h, 7, DASH_COLORS.row, DASH_COLORS.outline);
    dashText(ctx, label, x + 11, y + h / 2, { color: DASH_COLORS.label, font: "11px Arial" });
    ctx.save();
    ctx.font = options.valueFont || "12px Arial";
    const max = Math.max(38, w - Math.min(130, w * .43) - 27);
    const shown = fitString(ctx, String(value ?? ""), max);
    ctx.restore();
    dashText(ctx, shown, x + w - (options.chevron === false ? 11 : 21), y + h / 2, { align: "right", color: options.valueColor || DASH_COLORS.text, font: options.valueFont || "12px Arial" });
    if (options.chevron !== false) dashText(ctx, "▾", x + w - 8, y + h / 2, { align: "right", color: DASH_COLORS.label, font: "10px Arial" });
}

function dashToggleRow(ctx, x, y, w, h, label, enabled) {
    drawRoundRect(ctx, x, y, w, h, 7, DASH_COLORS.row, DASH_COLORS.outline);
    dashText(ctx, label, x + 11, y + h / 2, { font: "11px Arial" });
    const pw = 34, ph = 18, px = x + w - pw - 10, py = y + (h - ph) / 2;
    drawRoundRect(ctx, px, py, pw, ph, ph / 2, enabled ? "rgba(126,193,146,.78)" : "rgba(82,82,88,.95)", null);
    ctx.beginPath();
    ctx.arc(px + (enabled ? pw - ph / 2 : ph / 2), py + ph / 2, 6.5, 0, Math.PI * 2);
    ctx.fillStyle = "#f2f2f2";
    ctx.fill();
}

function dashHit(node, name, x, y, w, h, callback) {
    node.__soLoaderDashboardHits = node.__soLoaderDashboardHits || {};
    node.__soLoaderDashboardHits[name] = { x, y, w, h, callback };
}

function pointInHit(pos, hit) {
    return Boolean(hit && pos && pos[0] >= hit.x && pos[0] <= hit.x + hit.w && pos[1] >= hit.y && pos[1] <= hit.y + hit.h);
}

function dashboardSet(node, name, value) {
    const target = widget(node, name);
    if (!target) return;
    target.value = value;
    try { target.callback?.(value); } catch (error) {}
    node.setDirtyCanvas?.(true, true);
}

function dashboardToggle(node, name) {
    const target = widget(node, name);
    if (target) dashboardSet(node, name, !Boolean(target.value));
}

function dashboardMainFolderLeaf(node) {
    const parent = parentFolder(widget(node, "main_lora")?.value ?? "");
    return parent ? parent.slice(parent.lastIndexOf("/") + 1) : "LoRA root";
}

function dashboardCleanName(node) {
    const raw = String(widget(node, "cleanup_rules")?.value ?? "");
    return cleanModeCandidate(raw) || legacyRecommendedCleanName(node, parseCleanModeIndex(raw));
}

function publishLoaderLiveOutputs(node) {
    if (!node) return;
    node.__soLiveOutputs = {
        ...(node.__soLiveOutputs || {}),
        raw_stem: currentMainStem(node),
        clean_name: dashboardCleanName(node),
        main_trigger: mainLoraTriggerActive(node) ? String(node.__soMainTrigger ?? "") : "",
        main_folder: dashboardMainFolderLeaf(node),
    };
}

function openDashboardChoice(node, title, widgetName, values, formatter = null) {
    const target = widget(node, widgetName);
    if (!target) return;
    const choices = (values || []).map((value) => String(value));
    if (!choices.length) return;
    ensurePointerTracker();
    let render;
    const shell = createBrowserShell(
        "so-loader-folder-browser-popup",
        title,
        String(target.value ?? ""),
        (query) => render(query),
    );
    shell.search.placeholder = `Filter ${title.toLowerCase()}`;
    render = (query = "") => {
        const q = String(query).trim().toLowerCase();
        shell.list.replaceChildren();
        const filtered = choices.filter((value) => {
            const shown = formatter ? formatter(value) : value;
            return !q || String(shown).toLowerCase().includes(q) || value.toLowerCase().includes(q);
        });
        for (const value of filtered.slice(0, 280)) {
            const shown = formatter ? formatter(value) : value;
            const active = String(target.value ?? "") === value;
            const row = browserRow(shell.list, `${active ? "✓  " : ""}${shown}`, "file", () => {
                dashboardSet(node, widgetName, value);
                closeSOFolderBrowser();
            }, value);
            if (widgetName === "main_lora" && value !== NONE) {
                const state = loraReviewState(node, value);
                row.style.color = state === "none" && loraUseCount(node, value) > 0 ? reviewTone("tested") : reviewTone(state);
            }
        }
        if (!filtered.length) browserRow(shell.list, "No matches", "action", () => {});
    };
    render("");
}

function drawLoaderDashboard(node, ctx) {
    if (!node.__soLoaderDashboardReady) return;
    node.__soLoaderDashboardHits = {};
    const top = loaderDashboardTop(node);
    const x = DASH_PAD;
    const w = node.size[0] - DASH_PAD * 2;
    const rowH = DASH_ROW_H;
    const gap = DASH_GAP;
    let y = top;

    ctx.save();
    drawRoundRect(ctx, x - 2, y - 4, w + 4, loaderDashboardHeight(node), 10, "rgba(10,8,14,.48)", null);
    drawCMYKGFrame(ctx, x - 2, y - 4, w + 4, loaderDashboardHeight(node), 10, .28, DASH_COLORS.magenta);
    if (Number(node.__soAttentionUntil || 0) > Date.now()) {
        drawCMYKGFrame(ctx, x - 7, y - 9, w + 14, loaderDashboardHeight(node) + 10, 12, .95, DASH_COLORS.green);
    }

    drawCMYKGFrame(ctx, x - 4, y - 5, w + 8, 68, 9, .52, DASH_COLORS.cyan);
    dashSection(ctx, "Model", x + 2, y + 7, DASH_COLORS.cyan);
    y += 17;
    const modelW = w * .54;
    const modelModeW = w * .22;
    const weightW = w - modelW - modelModeW - gap * 2;
    const modelModeX = x + modelW + gap;
    const weightX = modelModeX + modelModeW + gap;
    dashValueRow(ctx, x, y, modelW, rowH, "Diffusion model", loraBrowserBasename(widget(node, "diffusion_model")?.value ?? ""), { valueFont: "11px Arial" });
    dashValueRow(ctx, modelModeX, y, modelModeW, rowH, "After generate", widget(node, "diffusion_control_after_generate")?.value ?? "fixed");
    dashValueRow(ctx, weightX, y, weightW, rowH, "Weight", widget(node, "weight_dtype")?.value ?? "default");
    dashHit(node, "model", x, y, modelW, rowH, () => openDashboardChoice(node, "Diffusion model", "diffusion_model", readValues(widget(node, "diffusion_model")), loraBrowserBasename));
    dashHit(node, "model-mode", modelModeX, y, modelModeW, rowH, () => openDashboardChoice(node, "Model after generate", "diffusion_control_after_generate", CONTROL_MODES));
    dashHit(node, "weight", weightX, y, weightW, rowH, () => openDashboardChoice(node, "Weight dtype", "weight_dtype", readValues(widget(node, "weight_dtype"))));
    y += rowH + 13 + DASH_SECTION_GAP;

    drawCMYKGFrame(ctx, x - 4, y - 5, w + 8, 246, 9, .52, DASH_COLORS.magenta);
    dashSection(ctx, "Main LoRA", x + 2, y + 7, DASH_COLORS.magenta);
    y += 17;
    // Folder navigation and LoRA selection are intentionally separate. The
    // folder defines the testing pool; the LoRA selector is a searchable view
    // of that pool after include-subfolders + epoch filtering are applied.
    const libraryW = 54;
    const folderW = w - libraryW - gap;
    dashValueRow(ctx, x, y, folderW, rowH, "Folder scope", `📁 ${loaderBrowserFolderText(widget(node, "folder_name")?.value, node)}`);
    const libraryX = x + folderW + gap;
    const libraryActive = Number(node.__soLibraryOpenFlash || 0) > Date.now();
    drawRoundRect(ctx, libraryX, y, libraryW, rowH, 7, libraryActive ? "rgba(255,74,184,.26)" : "rgba(8,7,12,.95)", libraryActive ? "#ff9ad6" : "#ff4ab8aa");
    if (loaderLibraryButtonImage.complete && loaderLibraryButtonImage.naturalWidth) {
        const scale = Math.min((libraryW - 5) / loaderLibraryButtonImage.naturalWidth, (rowH - 4) / loaderLibraryButtonImage.naturalHeight);
        const iconW = loaderLibraryButtonImage.naturalWidth * scale;
        const iconH = loaderLibraryButtonImage.naturalHeight * scale;
        ctx.drawImage(loaderLibraryButtonImage, libraryX + (libraryW - iconW) / 2, y + (rowH - iconH) / 2, iconW, iconH);
    } else {
        dashText(ctx, "LIB", libraryX + libraryW / 2, y + rowH / 2, { align: "center", color: "#ffd5ed", font: "800 10px Arial" });
    }
    dashHit(node, "browser", x, y, folderW, rowH, () => openLoaderFolderBrowser(node));
    dashHit(node, "library-folder", libraryX, y, libraryW, rowH, () => openLoRALibraryFromLoader(node));
    y += rowH + gap;

    const allowedMain = allowedMainLoras(node);
    const mainValue = String(widget(node, "main_lora")?.value ?? NONE);
    const mainShownValue = mainValue === NONE ? "None" : loraBrowserBasename(mainValue);
    const reviewButtons = [
        ["★", "favorite", "Favorite"], ["✓", "keep", "Keep"], ["↻", "retest", "Retest"], ["×", "reject", "Reject"],
    ];
    const reviewButtonW = Math.max(25, rowH - 5);
    const reviewGap = 4;
    const reviewTotalW = reviewButtons.length * reviewButtonW + (reviewButtons.length - 1) * reviewGap;
    const currentReview = loraReviewState(node, mainValue);
    reviewButtons.forEach(([symbol, state, label], index) => {
        const bx = x + index * (reviewButtonW + reviewGap);
        const tone = reviewTone(state);
        const active = currentReview === state || node.__soReviewFlash === state;
        drawRoundRect(ctx, bx, y, reviewButtonW, rowH, 7, active ? `${tone}42` : DASH_COLORS.row, active ? tone : `${tone}99`);
        dashText(ctx, symbol, bx + reviewButtonW / 2, y + rowH / 2, { align: "center", color: tone, font: "700 14px Arial" });
        dashHit(node, `review-${state}`, bx, y, reviewButtonW, rowH, () => setLoaderReview(node, state));
    });
    const mainX = x + reviewTotalW + gap;
    const mainW = w - reviewTotalW - gap;
    const usedCount = loraUseCount(node, mainValue);
    const mainLabel = `Main LoRA · ${allowedMain.length} available${usedCount ? ` · used ${usedCount}×` : ""}`;
    dashValueRow(ctx, mainX, y, mainW, rowH, mainLabel, mainShownValue, { valueColor: currentReview === "none" && usedCount ? reviewTone("tested") : reviewTone(currentReview) });
    dashHit(node, "mainlora", mainX, y, mainW, rowH, () => {
        openDashboardChoice(
            node,
            `Main LoRA · ${allowedMain.length} available`,
            "main_lora",
            [NONE, ...allowedMain],
            loraBrowserBasename,
        );
    });
    y += rowH + gap;

    const third = (w - gap * 2) / 3;
    dashToggleRow(ctx, x, y, third, rowH, "Enabled", Boolean(widget(node, "main_enabled")?.value));
    dashValueRow(ctx, x + third + gap, y, third, rowH, "Strength", Number(widget(node, "main_strength")?.value ?? 1).toFixed(2), { chevron: false });
    dashValueRow(ctx, x + (third + gap) * 2, y, third, rowH, "Epoch", widget(node, "epoch_filter")?.value ?? ALL_EPOCHS);
    dashHit(node, "enabled", x, y, third, rowH, () => dashboardToggle(node, "main_enabled"));
    dashHit(node, "strength", x + third + gap, y, third, rowH, (event) => {
        app.canvas.prompt("Main LoRA Strength", widget(node, "main_strength")?.value ?? 1, (value) => {
            const n = Number(value); if (Number.isFinite(n)) dashboardSet(node, "main_strength", n);
        }, event);
    });
    dashHit(node, "epoch", x + (third + gap) * 2, y, third, rowH, () => openDashboardChoice(node, "Epoch filter", "epoch_filter", readValues(widget(node, "epoch_filter"))));
    y += rowH + gap;

    const filterHalf = (w - gap) / 2;
    dashValueRow(ctx, x, y, filterHalf, rowH, "Library filter", widget(node, "library_filter")?.value ?? ALL_LIBRARY_STATES);
    dashValueRow(ctx, x + filterHalf + gap, y, filterHalf, rowH, "Sort", widget(node, "lora_sort")?.value ?? "Name");
    dashHit(node, "library-filter", x, y, filterHalf, rowH, () => openDashboardChoice(node, "Library filter", "library_filter", LIBRARY_FILTERS));
    dashHit(node, "lora-sort", x + filterHalf + gap, y, filterHalf, rowH, () => openDashboardChoice(node, "LoRA sort", "lora_sort", LORA_SORT_MODES));
    y += rowH + gap;

    const cleanW = Math.floor((w - gap) * .43);
    const triggerX = x + cleanW + gap;
    const triggerW = w - cleanW - gap;
    const infoW = Math.max(28, Math.min(32, rowH));
    const editW = infoW;
    const buttonGap = 4;
    const triggerBodyW = triggerW - infoW - editW - buttonGap * 2;
    dashValueRow(ctx, x, y, cleanW, rowH, "Clean name", dashboardCleanName(node));
    const triggerCopied = Boolean(node.__soTriggerCopied);
    drawRoundRect(
        ctx,
        triggerX,
        y,
        triggerBodyW,
        rowH,
        7,
        triggerCopied ? "rgba(74, 132, 101, .34)" : DASH_COLORS.row,
        triggerCopied ? "rgba(137, 213, 166, .82)" : DASH_COLORS.outline,
    );
    const triggerSource = String(node.__soMainTriggerSource ?? "");
    const customTrigger = triggerSource.startsWith("user.");
    const triggerLabel = customTrigger ? "Trigger · Custom" : (triggerSource.startsWith("civitai") ? "Trigger · Civitai" : "Trigger");
    dashText(
        ctx,
        triggerCopied ? "Trigger · copied" : triggerLabel,
        triggerX + 11,
        y + rowH / 2,
        { color: triggerCopied ? "#9cddb4" : (customTrigger ? "#b89aff" : DASH_COLORS.label), font: "11px Arial" },
    );
    const trigger = displayTriggerValue(node.__soMainTrigger ?? "");
    ctx.save(); ctx.font = "12px Arial";
    const trigShown = fitString(ctx, trigger, Math.max(40, triggerBodyW - 105)); ctx.restore();
    dashText(
        ctx,
        trigShown,
        triggerX + triggerBodyW - 35,
        y + rowH / 2,
        { align: "right", color: triggerCopied ? "#b9efca" : (trigger === "none" ? DASH_COLORS.label : DASH_COLORS.text) },
    );
    dashText(ctx, triggerCopied ? "✓" : "📋", triggerX + triggerBodyW - 11, y + rowH / 2, { align: "right", color: triggerCopied ? "#9cddb4" : DASH_COLORS.accent });
    const editX = triggerX + triggerBodyW + buttonGap;
    const infoX = editX + editW + buttonGap;
    drawRoundRect(ctx, editX, y, editW, rowH, 7, customTrigger ? "rgba(74,49,107,.94)" : "rgba(34,28,45,.96)", customTrigger ? "rgba(184,154,255,.92)" : "rgba(184,154,255,.60)");
    dashText(ctx, "✎", editX + editW / 2, y + rowH / 2, { align: "center", color: "#cdb9ff", font: "bold 14px Arial" });
    drawRoundRect(ctx, infoX, y, infoW, rowH, 7, "rgba(45,40,24,.95)", "rgba(246,230,90,.72)");
    dashText(ctx, "ⓘ", infoX + infoW / 2, y + rowH / 2, { align: "center", color: "#f6e65a", font: "bold 13px Arial" });
    dashHit(node, "clean", x, y, cleanW, rowH, () => openDashboardChoice(node, "Clean name", "cleanup_rules", readValues(widget(node, "cleanup_rules")), cleanModeCandidate));
    dashHit(node, "trigger-edit", editX, y, editW, rowH, () => showTriggerOverrideEditor(node, widget(node, "main_lora")?.value));
    dashHit(node, "main-info", infoX, y, infoW, rowH, () => showMainLoraInfo(node));
    dashHit(node, "trigger", triggerX, y, triggerBodyW, rowH, async () => {
        const value = String(node.__soMainTrigger ?? "").trim();
        if (!value) return;
        if (await copyText(value)) triggerCopyFeedback(node);
    });
    y += rowH + 17 + DASH_SECTION_GAP;

    const expanded = Boolean(node.properties?.so_loader_dashboard_advanced);
    drawCMYKGFrame(ctx, x - 4, y - 5, w + 8, expanded ? 140 : 104, 9, .52, DASH_COLORS.yellow);
    dashSection(ctx, "Testing", x + 2, y + 7, DASH_COLORS.yellow);
    y += 17;
    dashValueRow(ctx, x, y, third, rowH, "After generate", widget(node, "control_after_generate")?.value ?? "fixed");
    dashToggleRow(ctx, x + third + gap, y, third, rowH, "Include subfolders", Boolean(widget(node, "include_subfolders")?.value));
    dashToggleRow(ctx, x + (third + gap) * 2, y, third, rowH, "Skip None", Boolean(widget(node, "skip_none_during_cycle")?.value));
    dashHit(node, "mode", x, y, third, rowH, () => openDashboardChoice(node, "After generate", "control_after_generate", CONTROL_MODES));
    dashHit(node, "include", x + third + gap, y, third, rowH, () => dashboardToggle(node, "include_subfolders"));
    dashHit(node, "skip", x + (third + gap) * 2, y, third, rowH, () => dashboardToggle(node, "skip_none_during_cycle"));
    y += rowH + 9;

    drawRoundRect(ctx, x, y, w, 28, 7, "rgba(31,31,34,.96)", "rgba(110,231,162,.28)");
    dashText(ctx, `Advanced ${expanded ? "▾" : "▸"}`, x + 11, y + 14, { color: DASH_COLORS.green, font: "700 10px Arial" });
    dashText(ctx, "loop + off-state name", x + w - 11, y + 14, { align: "right", color: "#77777e", font: "10px Arial" });
    dashHit(node, "advanced", x, y, w, 28, () => {
        node.properties = node.properties || {};
        node.properties.so_loader_dashboard_advanced = !expanded;
        layoutLoaderDashboard(node, true);
    });
    y += 35;

    if (expanded) {
        const advHalf = (w - gap) / 2;
        dashToggleRow(ctx, x, y, advHalf, rowH, "Loop cycle", Boolean(widget(node, "loop_folder")?.value));
        dashValueRow(ctx, x + advHalf + gap, y, advHalf, rowH, "Off name", widget(node, "off_name")?.value ?? "no_lora", { chevron: false });
        dashHit(node, "loop", x, y, advHalf, rowH, () => dashboardToggle(node, "loop_folder"));
        dashHit(node, "offname", x + advHalf + gap, y, advHalf, rowH, (event) => {
            app.canvas.prompt("Off-state name", widget(node, "off_name")?.value ?? "no_lora", (value) => dashboardSet(node, "off_name", String(value ?? "")), event);
        });
        y += rowH;
    }

    y += DASH_SECTION_GAP;
    drawSecondaryDashboardSection(ctx, node, x, y, w);

    ctx.restore();
}

function repairLoaderDashboardValues(node) {
    const mode = widget(node, "control_after_generate");
    if (mode && !CONTROL_MODES.includes(String(mode.value))) {
        mode.value = "fixed";
    }
    const diffusionMode = widget(node, "diffusion_control_after_generate");
    if (diffusionMode && !CONTROL_MODES.includes(String(diffusionMode.value))) {
        diffusionMode.value = "fixed";
    }
    const loop = widget(node, "loop_folder");
    if (loop && typeof loop.value !== "boolean") loop.value = true;
    const skip = widget(node, "skip_none_during_cycle");
    if (skip && typeof skip.value !== "boolean") skip.value = true;
    const include = widget(node, "include_subfolders");
    if (include && typeof include.value !== "boolean") include.value = true;
    const enabled = widget(node, "main_enabled");
    if (enabled && typeof enabled.value !== "boolean") enabled.value = true;
    const offName = widget(node, "off_name");
    if (offName && typeof offName.value !== "string") offName.value = "no_lora";
    const auto = widget(node, "auto_clean_name");
    if (auto) auto.value = true;
    const libraryFilter = widget(node, "library_filter");
    if (libraryFilter && !LIBRARY_FILTERS.includes(String(libraryFilter.value))) libraryFilter.value = ALL_LIBRARY_STATES;
    const loraSort = widget(node, "lora_sort");
    if (loraSort && !LORA_SORT_MODES.includes(String(loraSort.value))) loraSort.value = "Name";
}

function hideLoaderDashboardBackingWidgets(node) {
    for (const name of LOADER_CANONICAL_NAMES) hideNativeWidget(widget(node, name));
    const auto = widget(node, "auto_clean_name");
    if (auto && auto.value !== true) {
        auto.value = true;
        try { auto.callback?.(true); } catch (error) {}
    }
    if (node.__soFolderBrowserButton) hideNativeWidget(node.__soFolderBrowserButton);
    if (node.__soTriggerButton) hideNativeWidget(node.__soTriggerButton);
    if (node.__soSecondaryStackWidget) hideNativeWidget(node.__soSecondaryStackWidget);
}

function layoutLoaderDashboard(node, refit = false) {
    if (!node.__soLoaderDashboardReady) return;
    repairLoaderDashboardValues(node);
    hideLoaderDashboardBackingWidgets(node);
    const top = loaderDashboardTop(node);
    node.widgets_start_y = top + loaderDashboardHeight(node) + 10;
    node.size[0] = Math.max(Number(node.size?.[0] || 0), DASH_MIN_WIDTH);
    applyStudioNodeColors(node);
    if (refit) {
        // Secondary LoRAs are painted inside the Loader dashboard now. Fit the
        // node to that one continuous Studio surface instead of leaving a
        // native-widget basement below it.
        node.size[1] = top + loaderDashboardHeight(node) + 14;
        setTimeout(() => {
            if (!node.__soLoaderDashboardReady || !node.size) return;
            const currentTop = loaderDashboardTop(node);
            node.size[0] = Math.max(Number(node.size[0] || 0), DASH_MIN_WIDTH);
            node.widgets_start_y = currentTop + loaderDashboardHeight(node) + 10;
            node.size[1] = currentTop + loaderDashboardHeight(node) + 14;
            node.setDirtyCanvas?.(true, true);
        }, 0);
    }
    node.setDirtyCanvas?.(true, true);
}

function ensureLoaderDashboard(node) {
    node.properties = node.properties || {};
    node.properties.so_loader_dashboard_version = LOADER_DASHBOARD_VERSION;
    node.__soLoaderDashboardReady = true;
    applyStudioNodeColors(node);
    repairLoaderDashboardValues(node);
    hideLoaderDashboardBackingWidgets(node);
    layoutLoaderDashboard(node, true);
}

function installLoaderDashboardHooks(nodeType) {
    // Match the compact visual stack with the actual cable anchor positions.
    // This is output-only and Studio-Loader-only, so graph semantics and the
    // other Core nodes remain completely untouched.
    const originalGetConnectionPos = nodeType.prototype.getConnectionPos;
    nodeType.prototype.getConnectionPos = function (isInput, slot, out) {
        if (!isInput && this.__soLoaderDashboardReady) {
            let slotIndex = typeof slot === "number" ? slot : this.findOutputSlot?.(slot);
            if (!Number.isInteger(slotIndex) || slotIndex < 0) slotIndex = Number(slot);
            const anchor = loaderOutputAnchor(this, slotIndex);
            if (anchor) {
                const result = out || [0, 0];
                result[0] = Number(this.pos?.[0] || 0) + anchor.x;
                result[1] = Number(this.pos?.[1] || 0) + anchor.y;
                return result;
            }
        }
        return originalGetConnectionPos?.apply(this, arguments);
    };

    const originalGetOutputPos = nodeType.prototype.getOutputPos;
    if (typeof originalGetOutputPos === "function") {
        nodeType.prototype.getOutputPos = function (slotIndex, out) {
            if (this.__soLoaderDashboardReady) {
                const anchor = loaderOutputAnchor(this, slotIndex);
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
        drawStudioChrome(this, ctx, "loader");
        try { originalForeground?.apply(this, arguments); } catch (error) {}
        drawLoaderDashboard(this, ctx);
    };

    const originalMouseDown = nodeType.prototype.onMouseDown;
    nodeType.prototype.onMouseDown = function (event, pos, canvas) {
        if (this.__soLoaderDashboardReady) {
            for (const hit of Object.values(this.__soLoaderDashboardHits || {})) {
                if (pointInHit(pos, hit)) {
                    hit.callback(event, pos, this);
                    return true;
                }
            }
        }
        return originalMouseDown?.apply(this, arguments);
    };
}

function secondaryVisibleRows(node) {
    return (node.__soSecondaryWidgets || []).filter((item) => item.isPopulated());
}

function secondaryStackValues(node) {
    return (node.__soSecondaryWidgets || []).slice(0, MAX_SECONDARY_LORAS).map((secondary) => ({
        on: secondary?.value?.on !== false,
        lora: secondary?.value?.lora ?? null,
        strength: Number(secondary?.value?.strength ?? 1),
    }));
}

class SecondaryLoraState {
    constructor(slotIndex = 1) {
        this.name = `${SECONDARY_PREFIX}${slotIndex}`;
        this.slotIndex = Number(slotIndex) || 1;
        this._value = { on: false, lora: null, strength: 1 };
        this.loraInfoPromise = null;
        this.loraInfo = null;
        this.triggerPromise = null;
        this.triggerText = "";
        this.triggerSource = "";
        this.triggerCopied = false;
        this.triggerCopiedTimer = null;
        this.__soNode = null;
    }

    set value(value) {
        if (!value || typeof value !== "object") {
            this._value = { on: false, lora: null, strength: 1 };
        } else {
            this._value = {
                on: value.on !== false,
                lora: value.lora ?? null,
                strength: Number(value.strength ?? 1),
            };
        }
        this.resetTriggerState();
        this.loraInfo = null;
        this.loraInfoPromise = null;
    }

    get value() {
        return this._value;
    }

    setLora(lora) {
        this._value.lora = lora;
        this.loraInfo = null;
        this.loraInfoPromise = null;
        this.resetTriggerState();
    }

    resetTriggerState() {
        this.triggerPromise = null;
        this.triggerText = "";
        this.triggerSource = "";
        this.triggerCopied = false;
        clearTimeout(this.triggerCopiedTimer);
        this.triggerCopiedTimer = null;
    }

    clear() {
        this.value = { on: false, lora: null, strength: 1 };
    }

    isPopulated() {
        return Boolean(this.value.lora && this.value.lora !== NONE);
    }

    async copyTrigger() {
        if (!this.isPopulated()) return false;
        const resolved = await this.getTrigger(false);
        const trigger = String(resolved?.trigger ?? this.triggerText ?? "").trim();
        if (!trigger || !await copyText(trigger)) return false;
        try { navigator.vibrate?.(18); } catch (error) {}
        this.triggerCopied = true;
        this.__soNode?.setDirtyCanvas?.(true, true);
        clearTimeout(this.triggerCopiedTimer);
        this.triggerCopiedTimer = setTimeout(() => {
            this.triggerCopied = false;
            this.__soNode?.setDirtyCanvas?.(true, true);
        }, 850);
        return true;
    }

    showLoraInfoDialog() {
        if (!this.value.lora || this.value.lora === NONE) return;
        const dialog = new RgthreeLoraInfoDialog(this.value.lora).show();
        dialog.addEventListener("close", (event) => {
            if (event.detail?.dirty) {
                this.getLoraInfo(true);
                this.resetTriggerState();
            }
        });
    }

    getLoraInfo(force = false) {
        if (!this.loraInfoPromise || force) {
            const promise = this.value.lora && this.value.lora !== NONE
                ? LORA_INFO_SERVICE.getInfo(this.value.lora, force, true)
                : Promise.resolve(null);
            this.loraInfoPromise = promise.then((value) => {
                this.loraInfo = value;
                this.__soNode?.setDirtyCanvas?.(true, true);
                return value;
            });
        }
        return this.loraInfoPromise;
    }

    getTrigger(force = false) {
        if (!this.isPopulated()) {
            this.triggerText = "";
            this.triggerSource = "";
            return Promise.resolve({ trigger: "", source: "" });
        }
        if (!this.triggerPromise || force) {
            const loraName = String(this.value.lora);
            this.triggerPromise = fetchMainTriggerFromServer(loraName)
                .then((resolved) => {
                    if (String(this.value.lora) === loraName) {
                        this.triggerText = String(resolved?.trigger ?? "").trim();
                        this.triggerSource = String(resolved?.source ?? "").trim();
                        this.__soNode?.setDirtyCanvas?.(true, true);
                    }
                    return resolved;
                })
                .catch((error) => {
                    console.warn("[Sick Ollie Loader Core] Could not resolve secondary trigger", error);
                    if (String(this.value.lora) === loraName) {
                        this.triggerText = "";
                        this.triggerSource = "";
                        this.__soNode?.setDirtyCanvas?.(true, true);
                    }
                    return { trigger: "", source: "" };
                });
        }
        return this.triggerPromise;
    }
}

function secondaryStackJson(node) {
    return JSON.stringify(secondaryStackValues(node));
}

function decodeSecondaryStack(value) {
    if (Array.isArray(value)) return value;
    if (typeof value !== "string") return null;
    try {
        const decoded = JSON.parse(value);
        return Array.isArray(decoded) ? decoded : null;
    } catch (error) {
        return null;
    }
}

function syncSecondaryBackingWidget(node) {
    const backing = node?.__soSecondaryStackWidget || widget(node, "secondary_lora_stack");
    if (!backing) return;
    backing.value = secondaryStackJson(node);
}

function ensureSecondaryBackingWidget(node) {
    const backing = widget(node, "secondary_lora_stack");
    if (!backing) {
        console.warn("[Sick Ollie Loader Core] Missing secondary_lora_stack backing input; secondary LoRAs cannot reach execution.");
        return null;
    }

    node.__soSecondaryStackWidget = backing;
    backing.options = { ...(backing.options || {}), serialize: true };
    backing.serialize = true;
    backing.serializeValue = () => {
        const value = secondaryStackJson(node);
        backing.value = value;
        return value;
    };
    hideNativeWidget(backing);
    return backing;
}

function drawSecondaryToggle(ctx, x, y, w, h, enabled) {
    drawRoundRect(
        ctx,
        x,
        y,
        w,
        h,
        7,
        DASH_COLORS.row,
        enabled ? "rgba(110,231,162,.62)" : DASH_COLORS.outline,
    );
    const pillW = 34;
    const pillH = 18;
    const pillX = x + (w - pillW) / 2;
    const pillY = y + (h - pillH) / 2;
    drawRoundRect(
        ctx,
        pillX,
        pillY,
        pillW,
        pillH,
        pillH / 2,
        enabled ? "rgba(126,193,146,.80)" : "rgba(82,82,88,.95)",
        null,
    );
    ctx.beginPath();
    ctx.arc(
        pillX + (enabled ? pillW - pillH / 2 : pillH / 2),
        pillY + pillH / 2,
        6.5,
        0,
        Math.PI * 2,
    );
    ctx.fillStyle = "#f2f2f2";
    ctx.fill();
}

function drawSecondaryDashboardSection(ctx, node, x, startY, w) {
    const rows = secondaryVisibleRows(node);
    const rowH = SECONDARY_ROW_H;
    const gap = DASH_GAP;
    const sectionH = secondaryDashboardSectionHeight(node);
    let y = startY;

    drawCMYKGFrame(ctx, x - 4, y - 5, w + 8, sectionH, 9, .52, DASH_COLORS.cyan);
    dashSection(ctx, "Secondary LoRAs", x + 2, y + 7, DASH_COLORS.cyan);
    dashText(
        ctx,
        `${rows.length} / ${MAX_SECONDARY_LORAS} selected`,
        x + w - 2,
        y + 7,
        { align: "right", color: DASH_COLORS.label, font: "10px Arial" },
    );
    y += SECONDARY_HEADER_H;

    for (const secondary of rows) {
        const enabled = Boolean(secondary.value.on);
        const toggleW = 54;
        const squareW = rowH;
        const strengthW = Math.max(112, Math.min(136, w * .14));
        const fixedRightW = strengthW + squareW * 4 + gap * 5;
        const loraX = x + toggleW + gap;
        const loraW = Math.max(190, w - toggleW - gap - fixedRightW);
        const strengthX = loraX + loraW + gap;
        const copyX = strengthX + strengthW + gap;
        const editX = copyX + squareW + gap;
        const infoX = editX + squareW + gap;
        const clearX = infoX + squareW + gap;

        drawSecondaryToggle(ctx, x, y, toggleW, rowH, enabled);
        dashHit(node, `secondary-toggle-${secondary.slotIndex}`, x, y, toggleW, rowH, () => {
            secondary.value.on = !secondary.value.on;
            syncSecondaryBackingWidget(node);
            node.setDirtyCanvas?.(true, true);
        });

        drawRoundRect(
            ctx,
            loraX,
            y,
            loraW,
            rowH,
            7,
            DASH_COLORS.row,
            enabled ? "rgba(110,231,162,.56)" : DASH_COLORS.outline,
        );
        const loraName = loraBrowserBasename(secondary.value.lora);
        const folder = parentFolder(secondary.value.lora) || "LoRA Root";
        ctx.save();
        ctx.font = "700 11px Arial";
        const shownLoraName = fitString(ctx, loraName, loraW - 43);
        ctx.font = "9px Arial";
        const shownFolder = fitString(ctx, folder, loraW - 43);
        ctx.restore();
        dashText(ctx, shownLoraName, loraX + 11, y + rowH * .36, {
            color: enabled ? DASH_COLORS.text : "rgba(244,241,246,.72)",
            font: "700 11px Arial",
        });
        dashText(ctx, shownFolder, loraX + 11, y + rowH * .70, {
            color: DASH_COLORS.label,
            font: "9px Arial",
        });
        dashText(ctx, "›", loraX + loraW - 12, y + rowH / 2, {
            align: "right",
            color: DASH_COLORS.cyan,
            font: "700 16px Arial",
        });
        dashHit(node, `secondary-lora-${secondary.slotIndex}`, loraX, y, loraW, rowH, () => {
            node.__soOpenSecondaryBrowser?.(secondary);
        });

        drawRoundRect(ctx, strengthX, y, strengthW, rowH, 7, DASH_COLORS.row, DASH_COLORS.outline);
        dashText(ctx, "Strength", strengthX + 10, y + rowH / 2, { color: DASH_COLORS.label, font: "10px Arial" });
        dashText(ctx, Number(secondary.value.strength ?? 1).toFixed(2), strengthX + strengthW - 10, y + rowH / 2, {
            align: "right",
            color: DASH_COLORS.text,
            font: "700 12px Arial",
        });
        dashHit(node, `secondary-strength-${secondary.slotIndex}`, strengthX, y, strengthW, rowH, (event) => {
            app.canvas.prompt("Secondary LoRA Strength", secondary.value.strength, (value) => {
                const number = Number(value);
                if (Number.isFinite(number)) {
                    secondary.value.strength = number;
                    syncSecondaryBackingWidget(node);
                    node.setDirtyCanvas?.(true, true);
                }
            }, event);
        });

        const copied = Boolean(secondary.triggerCopied);
        drawRoundRect(
            ctx,
            copyX,
            y,
            squareW,
            rowH,
            7,
            copied ? "rgba(74,132,101,.34)" : "rgba(22,29,34,.96)",
            copied ? "rgba(137,213,166,.82)" : "rgba(53,215,255,.62)",
        );
        dashText(ctx, copied ? "✓" : "📋", copyX + squareW / 2, y + rowH / 2, {
            align: "center",
            color: copied ? "#9cddb4" : DASH_COLORS.cyan,
            font: "700 13px Arial",
        });
        dashHit(node, `secondary-copy-${secondary.slotIndex}`, copyX, y, squareW, rowH, () => void secondary.copyTrigger());

        const secondaryCustom = String(secondary.triggerSource ?? "").startsWith("user.");
        drawRoundRect(ctx, editX, y, squareW, rowH, 7, secondaryCustom ? "rgba(74,49,107,.94)" : "rgba(34,28,45,.96)", secondaryCustom ? "rgba(184,154,255,.92)" : "rgba(184,154,255,.60)");
        dashText(ctx, "✎", editX + squareW / 2, y + rowH / 2, {
            align: "center", color: "#cdb9ff", font: "bold 14px Arial",
        });
        dashHit(node, `secondary-edit-${secondary.slotIndex}`, editX, y, squareW, rowH, () => showTriggerOverrideEditor(node, secondary.value.lora, async () => {
            secondary.resetTriggerState();
            await secondary.getTrigger(true);
        }));

        drawRoundRect(ctx, infoX, y, squareW, rowH, 7, "rgba(45,40,24,.95)", "rgba(246,230,90,.72)");
        dashText(ctx, "ⓘ", infoX + squareW / 2, y + rowH / 2, {
            align: "center",
            color: "#f6e65a",
            font: "bold 14px Arial",
        });
        dashHit(node, `secondary-info-${secondary.slotIndex}`, infoX, y, squareW, rowH, () => secondary.showLoraInfoDialog());

        drawRoundRect(ctx, clearX, y, squareW, rowH, 7, "rgba(47,22,30,.72)", "rgba(255,83,110,.58)");
        dashText(ctx, "×", clearX + squareW / 2, y + rowH / 2, {
            align: "center",
            color: "rgba(255,105,130,.98)",
            font: "700 15px Arial",
        });
        dashHit(node, `secondary-clear-${secondary.slotIndex}`, clearX, y, squareW, rowH, () => node.__soClearSecondary?.(secondary));

        y += rowH + gap;
    }

    if (rows.length) y -= gap;
    if (rows.length) y += gap;
    drawRoundRect(ctx, x, y, w, SECONDARY_ADD_H, 7, "rgba(31,31,34,.96)", "rgba(53,215,255,.56)");
    dashText(ctx, "＋  ADD SECONDARY LoRA", x + w / 2, y + SECONDARY_ADD_H / 2, {
        align: "center",
        color: DASH_COLORS.cyan,
        font: "700 11px Arial",
    });
    dashHit(node, "secondary-add", x, y, w, SECONDARY_ADD_H, () => node.__soOpenSecondaryBrowser?.(null));
}

function installFixedSecondaryMethods(node) {
    node.serialize_widgets = true;
    node.__soSecondaryWidgets = node.__soSecondaryWidgets || [];

    node.__soOpenSecondaryBrowser = (secondary = null) => {
        openSecondaryLoraBrowser(node, secondary);
    };

    node.__soVisibleSecondaries = () => secondaryVisibleRows(node);

    node.__soAllSecondaryState = () => {
        const activeRows = node.__soVisibleSecondaries();
        if (!activeRows.length) return false;
        const allOn = activeRows.every((item) => item.value.on);
        const allOff = activeRows.every((item) => !item.value.on);
        if (allOn) return true;
        if (allOff) return false;
        return null;
    };

    node.__soToggleAllSecondaries = () => {
        const rows = node.__soVisibleSecondaries();
        const turnOn = node.__soAllSecondaryState() !== true;
        for (const secondary of rows) secondary.value.on = turnOn;
        syncSecondaryBackingWidget(node);
        node.setDirtyCanvas?.(true, true);
    };

    node.__soRevealNextSecondary = (lora) => {
        const target = (node.__soSecondaryWidgets || []).find((item) => !item.isPopulated());
        if (!target) {
            console.warn(`[Sick Ollie Loader Core] Maximum of ${MAX_SECONDARY_LORAS} secondary LoRAs reached.`);
            return null;
        }
        target.setLora(lora);
        target.value.on = false;
        refreshFixedSecondaryVisibility(node);
        return target;
    };

    node.__soClearSecondary = (secondary) => {
        secondary?.clear?.();
        refreshFixedSecondaryVisibility(node);
    };
}

function refreshFixedSecondaryVisibility(node) {
    syncSecondaryBackingWidget(node);
    if (node.__soLoaderDashboardReady) layoutLoaderDashboard(node, true);
    node.setDirtyCanvas?.(true, true);
}

function addFixedSecondaryUI(node, restoredValues = []) {
    if (node.__soFixedSecondaryReady) {
        if (restoredValues.length) {
            for (let index = 0; index < MAX_SECONDARY_LORAS; index += 1) {
                node.__soSecondaryWidgets[index].value = restoredValues[index] && typeof restoredValues[index] === "object"
                    ? { ...restoredValues[index] }
                    : { on: false, lora: null, strength: 1 };
            }
        }
        refreshFixedSecondaryVisibility(node);
        return;
    }

    node.__soFixedSecondaryReady = true;
    installFixedSecondaryMethods(node);
    node.__soSecondaryWidgets = [];

    for (let slot = 1; slot <= MAX_SECONDARY_LORAS; slot += 1) {
        const secondary = new SecondaryLoraState(slot);
        secondary.__soNode = node;
        if (restoredValues[slot - 1]) secondary.value = { ...restoredValues[slot - 1] };
        node.__soSecondaryWidgets.push(secondary);
    }

    ensureSecondaryBackingWidget(node);
    node.size[0] = Math.max(node.size[0], 560);
    refreshFixedSecondaryVisibility(node);
}

function looksLikeLegacyPreEpochValues(values) {
    return (
        Array.isArray(values) &&
        typeof values[3] === "boolean" &&
        typeof values[4] === "string" &&
        typeof values[5] === "number" &&
        typeof values[6] === "boolean" &&
        typeof values[7] === "boolean" &&
        CONTROL_MODES.includes(String(values[8])) &&
        typeof values[9] === "boolean" &&
        typeof values[10] === "string" &&
        typeof values[11] === "boolean" &&
        typeof values[12] === "string"
    );
}

function looksLikeSavedShiftedEpochValues(values) {
    // A workflow saved after the bad one-slot load has already lost several
    // original values through widget coercion. Detect that shape so we can at
    // least restore a safe, valid Loader Core instead of shifting it again.
    return (
        Array.isArray(values) &&
        typeof values[3] === "boolean" &&
        typeof values[4] === "boolean" &&
        typeof values[5] === "number" &&
        typeof values[8] === "boolean" &&
        !CONTROL_MODES.includes(String(values[9]))
    );
}

function migrateEpochFilterWorkflow(info) {
    const values = info?.widgets_values;
    if (!Array.isArray(values)) return info;

    // Loader Core 1.0.0 had main_enabled at index 3. This migration must run
    // before LiteGraph applies widget values, otherwise every later widget is
    // configured one slot late.
    if (looksLikeLegacyPreEpochValues(values)) {
        return {
            ...info,
            widgets_values: [
                ...values.slice(0, 3),
                ALL_EPOCHS,
                ...values.slice(3),
            ],
        };
    }

    if (looksLikeSavedShiftedEpochValues(values)) {
        const dynamicSecondaries = values
            .slice(13)
            .filter(
                (value) =>
                    value &&
                    typeof value === "object" &&
                    typeof value.lora !== "undefined",
            );

        console.warn(
            "[Sick Ollie Loader Core] Repairing a workflow saved after the " +
                "epoch widget shift. Main LoRA and edited cleanup text could " +
                "not be recovered, so safe defaults were restored.",
        );

        return {
            ...info,
            widgets_values: [
                values[0],
                values[1],
                values[2],
                ALL_EPOCHS,
                true,
                NONE,
                1,
                Boolean(values[7]),
                true,
                "fixed",
                true,
                "no_lora",
                true,
                DEFAULT_CLEAN_NAME_MODE,
                ...dynamicSecondaries,
            ],
        };
    }

    return info;
}

function dynamicValuesFromWorkflow(info) {
    const raw = info?.widgets_values || [];
    const tail = raw.slice(LOADER_CANONICAL_NAMES.length);
    let stack = tail.find((value) => Array.isArray(value) && value.some((item) => item && typeof item === "object" && typeof item.lora !== "undefined"));
    if (!Array.isArray(stack)) {
        for (const value of tail) {
            const decoded = decodeSecondaryStack(value);
            if (Array.isArray(decoded)) {
                stack = decoded;
                break;
            }
        }
    }
    if (Array.isArray(stack)) {
        return stack.slice(0, MAX_SECONDARY_LORAS).map((value) =>
            value && typeof value === "object"
                ? { ...value }
                : { on: false, lora: null, strength: 1 },
        );
    }

    const values = [];
    for (const value of raw) {
        if (value && typeof value === "object" && !Array.isArray(value) && typeof value.lora !== "undefined") {
            values.push({ ...value });
        }
    }

    // Migrate Loader Core v4's old fixed four-slot format.
    if (!values.length) {
        const old = raw;
        const oldMasterEnabled = old[13];
        if (typeof oldMasterEnabled === "boolean") {
            for (let slot = 0; slot < 4; slot++) {
                const lora = old[14 + slot * 2];
                const strength = old[15 + slot * 2];
                if (typeof lora === "string" && lora !== NONE) {
                    values.push({
                        on: oldMasterEnabled,
                        lora,
                        strength: Number.isFinite(Number(strength)) ? Number(strength) : 1,
                    });
                }
            }
        }
    }

    return values;
}

function installContextMenuHooks(nodeType) {
    const originalGetSlotInPosition =
        nodeType.prototype.getSlotInPosition;

    nodeType.prototype.getSlotInPosition = function (
        canvasX,
        canvasY,
    ) {
        const slot =
            originalGetSlotInPosition?.apply(
                this,
                arguments,
            );

        if (slot) return slot;

        let lastWidget = null;

        for (const item of this.widgets || []) {
            if (item.last_y == null) continue;

            if (canvasY > this.pos[1] + item.last_y) {
                lastWidget = item;
                continue;
            }

            break;
        }

        if (
            lastWidget?._soVisible &&
            lastWidget?.name?.startsWith(SECONDARY_PREFIX)
        ) {
            return {
                widget: lastWidget,
                output: {
                    type: "SECONDARY LORA",
                },
            };
        }

        return slot;
    };

    const originalGetSlotMenuOptions =
        nodeType.prototype.getSlotMenuOptions;

    nodeType.prototype.getSlotMenuOptions = function (
        slot,
    ) {
        if (
            slot?.widget?.name?.startsWith(
                SECONDARY_PREFIX,
            )
        ) {
            const secondary = slot.widget;
            const items = [
                {
                    content: "📁 Browse / Replace",
                    callback: () => this.__soOpenSecondaryBrowser?.(secondary),
                },
                {
                    content: "ℹ️ Show Info",
                    disabled: !secondary.isPopulated(),
                    callback: () =>
                        secondary.showLoraInfoDialog(),
                },
                null,
                {
                    content: secondary.value.on
                        ? "⚫ Toggle Off"
                        : "🟢 Toggle On",
                    disabled: !secondary.isPopulated(),
                    callback: () => {
                        secondary.value.on =
                            !secondary.value.on;
                        this.setDirtyCanvas?.(true, true);
                    },
                },
                {
                    content: "🗑️ Clear Row",
                    disabled: !secondary.isPopulated(),
                    callback: () => {
                        this.__soClearSecondary?.(secondary);
                    },
                },
            ];

            new LiteGraph.ContextMenu(items, {
                title: `SECONDARY LORA ${secondary.slotIndex}`,
                event: rgthree.lastCanvasMouseEvent,
            });

            return undefined;
        }

        return originalGetSlotMenuOptions?.apply(
            this,
            arguments,
        );
    };
}


function normalizeLoaderWorkflow(info) {
    let migrated = migrateEpochFilterWorkflow(info);
    const values = migrated?.widgets_values;
    if (!Array.isArray(values)) return migrated;

    // dev27 inserted a non-serialized browser widget between folder_name and
    // epoch_filter. Current LiteGraph serialization can leave a null hole at
    // that position. Repair that exact shape before any native widget receives
    // values, then gather secondary rows by object shape instead of position.
    if (
        values.length >= 15 &&
        values[3] == null &&
        typeof values[4] === "string" &&
        (values[4] === ALL_EPOCHS || values[4] === NO_EPOCH_TAG || /^Epoch\s+\d+$/i.test(values[4]))
    ) {
        const secondaries = values
            .filter((value) => value && typeof value === "object" && typeof value.lora !== "undefined")
            .slice(0, MAX_SECONDARY_LORAS);
        migrated = {
            ...migrated,
            widgets_values: [
                values[0], values[1], values[2], values[4], values[5], values[6],
                values[7], values[8], values[9], values[10], values[11], values[12],
                values[13], values[14], ...secondaries,
            ],
        };
    }

    const repairedValues = migrated?.widgets_values;
    const hasLibraryControls = Array.isArray(repairedValues)
        && LIBRARY_FILTERS.includes(String(repairedValues[14]))
        && LORA_SORT_MODES.includes(String(repairedValues[15]));
    if (Array.isArray(repairedValues) && repairedValues.length > 14 && !hasLibraryControls) {
        migrated = {
            ...migrated,
            widgets_values: [
                ...repairedValues.slice(0, 14),
                ALL_LIBRARY_STATES,
                "Name",
                ...repairedValues.slice(14),
            ],
        };
    }

    // v3.3.61 appends model cycling after all prior canonical Loader values so
    // existing workflows keep every historical widget index unchanged. Insert
    // the fixed default before any legacy secondary-stack payload.
    const modelControlValues = migrated?.widgets_values;
    if (Array.isArray(modelControlValues) && !CONTROL_MODES.includes(String(modelControlValues[16]))) {
        migrated = {
            ...migrated,
            widgets_values: [
                ...modelControlValues.slice(0, 16),
                "fixed",
                ...modelControlValues.slice(16),
            ],
        };
    }

    // Secondary LoRAs used to serialize as one custom widget per row. Collapse
    // every known legacy shape into one stack value so LiteGraph only has a
    // single invisible backing widget. That removes the widget-layout seams
    // that could show up as black strips between our Studio-drawn rows.
    const normalizedValues = migrated?.widgets_values;
    if (Array.isArray(normalizedValues) && normalizedValues.length >= LOADER_CANONICAL_NAMES.length) {
        const head = normalizedValues.slice(0, LOADER_CANONICAL_NAMES.length);
        const tail = normalizedValues.slice(LOADER_CANONICAL_NAMES.length);
        let stack = tail.find((value) => Array.isArray(value));
        if (!Array.isArray(stack)) {
            for (const value of tail) {
                const decoded = decodeSecondaryStack(value);
                if (Array.isArray(decoded)) {
                    stack = decoded;
                    break;
                }
            }
        }
        if (!Array.isArray(stack)) {
            const legacyRows = tail.filter((value) => value && typeof value === "object" && typeof value.lora !== "undefined");
            if (legacyRows.length) stack = legacyRows;
        }
        if (Array.isArray(stack)) {
            const normalizedStack = stack.slice(0, MAX_SECONDARY_LORAS).map((value) =>
                value && typeof value === "object"
                    ? { ...value }
                    : { on: false, lora: null, strength: 1 },
            );
            migrated = {
                ...migrated,
                widgets_values: [
                    ...head,
                    JSON.stringify(normalizedStack),
                ],
            };
        }
    }

    return migrated;
}

function loaderCanonicalValues(node) {
    return LOADER_CANONICAL_NAMES.map((name) => widget(node, name)?.value);
}

function loaderSecondaryValues(node) {
    return [secondaryStackJson(node)];
}

app.registerExtension({
    name: "SickOllie.Studio.LoaderCore",

    setup() {
        ensurePointerTracker();
        if (window.__soLibraryUsageListener) return;
        window.__soLibraryUsageListener = () => {
            for (const node of app.graph?._nodes || []) if (node.type === TARGET) refreshReviewCollections(node);
        };
        window.addEventListener("sickollie:library-usage-updated", window.__soLibraryUsageListener);
        window.addEventListener("sickollie:lora-collections-updated", window.__soLibraryUsageListener);
    },

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== TARGET) return;

        installContextMenuHooks(nodeType);
        installLoaderDashboardHooks(nodeType);

        // LiteGraph applies widgets_values inside configure() and only calls
        // onConfigure() afterward. Intercept configure itself so migrations
        // happen before any widget receives a shifted value.
        const originalNodeConfigure = nodeType.prototype.configure;
        nodeType.prototype.configure = function (info) {
            return originalNodeConfigure.call(
                this,
                normalizeLoaderWorkflow(info),
            );
        };

        const originalSerialize = nodeType.prototype.serialize;
        nodeType.prototype.serialize = function () {
            const data = originalSerialize?.apply(this, arguments) || {};
            data.properties = {
                ...(data.properties || {}),
                so_loader_dashboard_version: LOADER_DASHBOARD_VERSION,
            };
            // Always write a compact, canonical array. This deliberately
            // excludes frontend-only UI elements so they cannot create sparse
            // holes and positional shifts on reload.
            data.widgets_values = [
                ...loaderCanonicalValues(this),
                ...loaderSecondaryValues(this),
            ];
            return data;
        };

        const originalCreated =
            nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result =
                originalCreated?.apply(
                    this,
                    arguments,
                );

            applyStudioNodeColors(this);
            // Prompt Core's Trigger Setup delegates per-LoRA overrides back to
            // Loader Core. Expose the canonical refresh path so the connected
            // live output, dashboard, and copy action update together.
            this.__soRefreshMainTrigger = (force = true) => refreshMainTrigger(this, force);
            ensureCleanNameCombo(this);

            const diffusionWidget = widget(this, "diffusion_model");
            if (diffusionWidget) {
                const originalDiffusionAfterQueued = diffusionWidget.afterQueued;
                diffusionWidget.afterQueued = () => {
                    try {
                        originalDiffusionAfterQueued?.call(diffusionWidget);
                    } finally {
                        advanceDiffusionAfterQueued(this);
                    }
                };
            }

            const mainWidget = widget(
                this,
                "main_lora",
            );

            if (mainWidget) {
                this.__soAllMainLoras =
                    readValues(mainWidget);

                const originalAfterQueued =
                    mainWidget.afterQueued;

                mainWidget.afterQueued = () => {
                    try {
                        originalAfterQueued?.call(
                            mainWidget,
                        );
                    } finally {
                        advanceMainAfterQueued(this);
                        refreshCleanNameChoices(this);
                        refreshMainTrigger(this, false);
                    }
                };

                const originalMainCallback =
                    mainWidget.callback;

                mainWidget.callback = (value) => {
                    try {
                        originalMainCallback?.call(
                            mainWidget,
                            value,
                        );
                    } finally {
                        refreshCleanNameChoices(this);
                        refreshMainTrigger(this, false);
                    }
                };
            }

            for (const name of ["main_enabled", "main_strength"]) {
                const activeWidget = widget(this, name);
                if (!activeWidget) continue;
                const originalActiveCallback = activeWidget.callback;
                activeWidget.callback = (value) => {
                    try {
                        originalActiveCallback?.call(activeWidget, value);
                    } finally {
                        refreshMainTrigger(this, false);
                    }
                };
            }

            for (const name of [
                "folder_name",
                "include_subfolders",
                "library_filter",
                "lora_sort",
            ]) {
                const filterWidget = widget(
                    this,
                    name,
                );

                if (!filterWidget) continue;

                const originalCallback =
                    filterWidget.callback;

                filterWidget.callback = (value) => {
                    try {
                        originalCallback?.call(
                            filterWidget,
                            value,
                        );
                    } finally {
                        refreshEpochChoices(this);
                        refreshMainChoices(
                            this,
                            true,
                        );
                        refreshCleanNameChoices(this);
                        refreshReviewCollections(this);
                    }
                };
            }

            const epochWidget = widget(
                this,
                "epoch_filter",
            );

            if (epochWidget) {
                const originalEpochCallback =
                    epochWidget.callback;

                epochWidget.callback = (value) => {
                    try {
                        originalEpochCallback?.call(
                            epochWidget,
                            value,
                        );
                    } finally {
                        refreshMainChoices(
                            this,
                            true,
                        );
                        refreshCleanNameChoices(this);
                    }
                };
            }

            ensureLoaderFolderNavigator(this);
            rgthreeApi.getLoras();
            addFixedSecondaryUI(this);
            ensureLoaderDashboard(this);
            refreshEpochChoices(this);
            refreshMainChoices(this, false);
            refreshCleanNameChoices(this);
            refreshMainTrigger(this, false);
            refreshReviewCollections(this);
            layoutLoaderDashboard(this, true);

            return result;
        };

        const originalConfigure =
            nodeType.prototype.onConfigure;

        nodeType.prototype.onConfigure = function (info) {
            applyStudioNodeColors(this);
            this.__soRefreshMainTrigger = (force = true) => refreshMainTrigger(this, force);
            const configuredInfo =
                normalizeLoaderWorkflow(info);

            const result =
                originalConfigure?.call(
                    this,
                    configuredInfo,
                );

            const values =
                dynamicValuesFromWorkflow(configuredInfo);

            setTimeout(() => {
                ensureLoaderFolderNavigator(this);
                addFixedSecondaryUI(
                    this,
                    values,
                );
                ensureLoaderDashboard(this);
                refreshEpochChoices(this);
                refreshMainChoices(this, false);
                refreshCleanNameChoices(this);
                refreshMainTrigger(this, false);
                refreshReviewCollections(this);
                layoutLoaderDashboard(this, true);
            }, 0);

            return result;
        };
    },
});
