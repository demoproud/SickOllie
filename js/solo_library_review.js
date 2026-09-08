import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { registerSoloHubItem } from "./solo_hub.js";
import { recoverTextInputFocus } from "./text_input_focus_guard.js";
const LIBRARY_HEADER_URL = new URL("./solo_hub_assets/LoRALibraryHeader.png", import.meta.url).href;
const LIBRARY_BACKGROUND_URL = new URL("./solo_hub_assets/LoRALibraryBackground.webp", import.meta.url).href;

const API = "/sickollie/library-review";
const STYLE_URL = new URL("./solo_library_review.css", import.meta.url).href;
const ALL_FOLDERS = "[All folders]";
const LOADER_TYPES = ["SOLoaderCoreEngineStudio", "SOLoaderCoreEngine"];
const PROMPT_TYPE = "SOPromptLogEngineStudio";
const GENERATION_TYPE = "SOGenerationPipelineStudio";
const OUTPUT_TYPE = "SOOutputBuilderSaveStudio";
const LORA_YEARBOOK_OUTPUT_ROOT = "Sick Ollie Yearbooks/LoRA Library";
const AUTO_FIRST_KEY = "sickollie.library.autoFirstImage";
const YEARBOOK_PROMPT_KEY = "sickollie.library.yearbookPrompt";
const DEFAULT_YEARBOOK_PROMPT = "A clean yearbook portrait of NAME, centered head and shoulders, looking directly at the camera, calm natural expression, simple neutral background, even soft studio light, consistent framing.";
const YEARBOOK_DEFAULT_STRENGTH = 1.0;
const YEARBOOK_DEFAULT_SEED = 4815162342;
const YEARBOOK_THEATER_ENABLED_KEY = "sickollie.library.yearbookTheaterEnabled";
const YEARBOOK_THEATER_SIZE_KEY = "sickollie.library.yearbookTheaterSize";
const YEARBOOK_DIMENSION_PRESETS = [
    ["400x500", "400 × 500 · Fast", 400, 500],
    ["512x640", "512 × 640 · Light", 512, 640],
    ["800x1000", "800 × 1000 · Medium", 800, 1000],
    ["1024x1280", "1024 × 1280 · Large", 1024, 1280],
    ["1440x1920", "1440 × 1920 · Ollie", 1440, 1920],
    ["custom", "Custom dimensions", null, null],
];

let root = null;
let assets = [];
let folderScope = ALL_FOLDERS;
let collectionScope = "";
let loraCollections = [];
const expandedFolders = new Set();
let epochFilter = "";
let statusFilter = "";
let thumbnailFilter = "";
let sortMode = "recent";
let civitaiFilling = false;
let yearbook = null;
let yearbookRunSerial = 0;
let lastPreviewKey = "";
let lastPreviewAt = 0;
let galleryPage = 0;
let liveFolders = [];
let styleReady = null;
let libraryLoadPromise = null;
let folderAssetCounts = new Map();
let catalogRefreshTimer = null;
let reviewMutationSerial = 0;
const reviewMutations = new Map();
let loraCardQueueChain = Promise.resolve();
let loraBatchQueue = null;
let loraSelectionMode = false;
const selectedLoraIds = new Set();

function ensureStyle() {
    if (styleReady) return styleReady;
    const link = document.querySelector(`link[data-so-lib-style="${STYLE_URL}"]`) || document.createElement("link");
    if (!link.parentNode) {
        link.rel = "stylesheet"; link.href = STYLE_URL; link.dataset.soLibStyle = STYLE_URL;
        document.head.append(link);
    }
    styleReady = new Promise(resolve => {
        if (link.sheet) { resolve(); return; }
        link.addEventListener("load", resolve, { once: true });
        // A failed stylesheet should not prevent the user from opening the hub.
        link.addEventListener("error", resolve, { once: true });
    });
    return styleReady;
}

async function request(path, options = {}) {
    const init = { ...options, headers: { ...(options.headers || {}) } };
    if (init.body !== undefined && !(init.body instanceof FormData) && typeof init.body !== "string") {
        init.headers["Content-Type"] = "application/json";
        init.body = JSON.stringify(init.body);
    } else if (typeof init.body === "string") {
        init.headers["Content-Type"] = init.headers["Content-Type"] || "application/json";
    }
    const response = await fetch(`${API}${path}`, init);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
}

function action(label, tone = "#48e8ee", extra = "") {
    const button = document.createElement("button");
    button.type = "button"; button.textContent = label; button.className = `so-lib-button${extra ? ` ${extra}` : ""}`;
    button.style.setProperty("--tone", tone);
    return button;
}

function selectControl(values, current, change) {
    const select = document.createElement("select"); select.className = "so-lib-select";
    for (const [value, label] of values) {
        const option = document.createElement("option"); option.value = value; option.textContent = label; select.append(option);
    }
    select.value = current; select.onchange = () => change(select.value);
    return select;
}

function setFeedback(message, tone = "#69e49a") {
    const field = root?.querySelector("[data-review-status]");
    if (field) { field.textContent = message; field.style.color = tone; }
}
function updateYearbookProgress(message = "") { const field = root?.querySelector("[data-yearbook-progress]"); if (!field || !yearbook) return; const done = yearbook.index, total = yearbook.items.length; field.hidden = false; field.style.setProperty("--progress", `${Math.min(100, Math.round(done / total * 100))}%`); field.textContent = message || `YEARBOOK · ${done}/${total} processed · ${yearbook.captured} captured · ${yearbook.skipped} skipped · ${yearbook.items[done]?.model_name || "finishing…"}`; }

function formatBytes(value) {
    const size = Math.max(0, Number(value || 0));
    if (size >= 1024 ** 3) return `${(size / 1024 ** 3).toFixed(2)} GB`;
    if (size >= 1024 ** 2) return `${Math.round(size / 1024 ** 2)} MB`;
    if (size >= 1024) return `${Math.round(size / 1024)} KB`;
    return `${size} B`;
}

function formatDate(value, fallback = "Never") {
    if (!value) return fallback;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? fallback : date.toLocaleString();
}

function statusTone(value) {
    return ({ favorite: "#f4ec51", keep: "#69e49a", rated: "#b89aff", reject: "#ff3eaf", retest: "#48e8ee" })[value] || "#8c8295";
}

function yearbookTheaterEnabledByDefault() { return localStorage.getItem(YEARBOOK_THEATER_ENABLED_KEY) !== "false"; }
function yearbookTheaterInitialSize() {
    const value = String(localStorage.getItem(YEARBOOK_THEATER_SIZE_KEY) || "fit");
    return ["fit", "fill", "actual"].includes(value) ? value : "fit";
}
function yearbookTheaterCurrent(run) {
    const theater = run?.theater;
    if (!theater?.entries?.length) return null;
    theater.cursor = Math.max(0, Math.min(theater.entries.length - 1, Number(theater.cursor ?? theater.entries.length - 1)));
    return theater.entries[theater.cursor] || null;
}
function closeYearbookTheater(run) {
    const theater = run?.theater;
    if (!theater?.overlay) return;
    theater.dismissed = true;
    theater.overlay.remove(); theater.overlay = null; theater.ui = null;
}
function applyYearbookTheaterSizing(run) {
    const theater = run?.theater; const ui = theater?.ui; if (!ui) return;
    const mode = theater.sizeMode || "fit"; localStorage.setItem(YEARBOOK_THEATER_SIZE_KEY, mode);
    ui.frame.style.overflow = mode === "actual" ? "auto" : "hidden";
    if (mode === "actual") Object.assign(ui.image.style, { width: "auto", height: "auto", maxWidth: "none", maxHeight: "none", objectFit: "contain", margin: "auto" });
    else Object.assign(ui.image.style, { width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%", objectFit: mode === "fill" ? "cover" : "contain", margin: "0" });
    for (const [name, button] of Object.entries(ui.sizeButtons || {})) { const active = name === mode; button.style.background = active ? "rgba(72,232,238,.16)" : "#211d27"; button.style.borderColor = active ? "#48e8ee" : "#4a4452"; button.style.color = active ? "#dffcff" : "#b8b0c1"; }
}
function updateYearbookTheater(run) {
    const theater = run?.theater; const ui = theater?.ui; if (!ui) return; const entry = yearbookTheaterCurrent(run);
    const generated = theater.entries.length; const reviewed = theater.entries.filter(value => value.reviewed).length; const rejected = theater.entries.filter(value => value.rejected).length; const waiting = Math.max(0, generated - reviewed);
    ui.runState.textContent = run.completed ? "● COMPLETE" : run.stopped ? "● STOPPED" : "● RUNNING";
    ui.runState.style.color = run.completed ? "#69e49a" : run.stopped ? "#f4ec51" : "#48e8ee";
    ui.position.textContent = entry ? `${theater.cursor + 1} / ${generated}` : "0 / 0"; ui.stats.textContent = `GENERATED ${generated} / ${Number(run.items?.length || 0)} · REVIEWED ${reviewed} · REJECTED ${rejected} · WAITING ${waiting}`;
    ui.live.textContent = theater.live ? "● LIVE" : "❚❚ FROZEN"; ui.live.style.borderColor = theater.live ? "#69e49a" : "#f4ec51"; ui.live.style.color = theater.live ? "#9ff5c8" : "#fff29a"; ui.previous.disabled = !entry || theater.cursor <= 0; ui.next.disabled = !entry || theater.cursor >= generated - 1;
    if (!entry) { ui.image.hidden = true; ui.image.removeAttribute("src"); ui.empty.hidden = false; ui.title.textContent = "Waiting for the first Yearbook thumbnail…"; ui.subtitle.textContent = "THEATER MODE · LIVE"; ui.path.textContent = "The newest completed LoRA thumbnail will appear here automatically."; ui.reviewButtons.forEach(button => button.disabled = true); return; }
    ui.empty.hidden = true; ui.image.hidden = false; const thumb = entry.thumbnail || {}; const filename = String(thumb.filename || entry.item.thumbnail_ref || ""); if (filename) { const url = `${API}/thumbnail/${encodeURIComponent(filename)}?v=${encodeURIComponent(String(thumb.updated_at || entry.item.thumbnail_updated_at || Date.now()))}`; if (ui.image.src !== new URL(url, window.location.href).href) ui.image.src = url; }
    ui.title.textContent = String(entry.item.model_name || "LoRA"); ui.subtitle.textContent = `LORA YEARBOOK · ${theater.live ? "FOLLOWING NEWEST" : "REVIEWING HISTORY"}`; ui.path.textContent = String(entry.item.relative_lora || entry.item.current_path || "");
    for (const button of ui.reviewButtons) { button.disabled = Boolean(entry.busy); button.classList.toggle("active", String(entry.item.review_state || "none") === button.dataset.reviewState); }
    applyYearbookTheaterSizing(run);
}
async function setYearbookTheaterReview(run, entry, nextState) {
    if (!entry || entry.busy) return; entry.busy = true; updateYearbookTheater(run);
    try {
        const current = String(entry.item.review_state || "none");
        const state = current === nextState ? "none" : nextState;
        await request("/review", { method: "POST", body: { asset_id: entry.item.asset_id, state } });
        entry.item.review_state = state; entry.rejected = state === "reject"; entry.reviewed = true;
        const live = assetById(entry.item.asset_id); if (live) live.review_state = state;
    } catch (error) { alert(error.message || "Could not update this Yearbook review."); } finally { entry.busy = false; updateYearbookTheater(run); }
}
function appendYearbookTheaterEntry(run, item, thumbnail) {
    if (!run?.theaterEnabled) return; if (!run.theater) run.theater = { entries: [], cursor: -1, live: true, sizeMode: yearbookTheaterInitialSize(), overlay: null, ui: null, dismissed: false };
    const theater = run.theater; const key = String(item?.asset_id || item?.relative_lora || item?.model_name || theater.entries.length); let entry = theater.entries.find(value => value.key === key);
    if (!entry) { entry = { key, item, thumbnail, rating: Number(item?.rating || 0), rejected: String(item?.review_state || "") === "reject", reviewed: false, busy: false, previousState: String(item?.review_state || "none"), previousRating: Number(item?.rating || 0) }; theater.entries.push(entry); } else { entry.item = item; entry.thumbnail = thumbnail; }
    if (theater.live || theater.cursor < 0) theater.cursor = theater.entries.length - 1; if (!theater.overlay && !theater.dismissed) openYearbookTheater(run); else updateYearbookTheater(run);
}
function openYearbookTheater(run = yearbook) {
    if (!run || !run.theaterEnabled) return; if (!run.theater) run.theater = { entries: [], cursor: -1, live: true, sizeMode: yearbookTheaterInitialSize(), overlay: null, ui: null, dismissed: false }; const theater = run.theater;
    theater.dismissed = false;
    if (theater.overlay?.isConnected) { updateYearbookTheater(run); theater.overlay.focus(); return; }
    const overlay = document.createElement("div"); overlay.dataset.soYearbookTheater = ""; overlay.tabIndex = -1; Object.assign(overlay.style, { position: "fixed", inset: "0", zIndex: "100090", display: "flex", alignItems: "center", justifyContent: "center", padding: "18px", background: "rgba(1,1,4,.91)", backdropFilter: "blur(10px) saturate(.7)", color: "#f6f2f8" });
    const card = document.createElement("section"); Object.assign(card.style, { width: "min(1500px,calc(100vw - 36px))", height: "min(1120px,calc(100vh - 36px))", minHeight: "520px", display: "grid", gridTemplateRows: "auto minmax(0,1fr) auto", overflow: "hidden", borderRadius: "18px", border: "1px solid #48e8ee77", background: "linear-gradient(160deg,#10151a,#08070c 60%)", boxShadow: "0 32px 110px rgba(0,0,0,.78),0 0 42px rgba(72,232,238,.10)" });
    const head = document.createElement("header"); Object.assign(head.style, { display: "flex", alignItems: "center", gap: "12px", padding: "12px 14px", borderBottom: "1px solid #2d3940", background: "rgba(11,15,18,.96)" }); const headText = document.createElement("div"); headText.style.flex = "1"; const subtitle = document.createElement("div"); Object.assign(subtitle.style, { color: "#48e8ee", font: "900 9px Segoe UI,Arial", letterSpacing: ".14em" }); const title = document.createElement("div"); Object.assign(title.style, { marginTop: "3px", color: "#fff", font: "900 15px Segoe UI,Arial", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }); headText.append(subtitle, title); const runState = document.createElement("span"); Object.assign(runState.style, { font: "900 9px Segoe UI,Arial", letterSpacing: ".09em" }); const position = document.createElement("span"); Object.assign(position.style, { minWidth: "58px", color: "#9b93a2", textAlign: "right", font: "800 10px Segoe UI,Arial" }); const close = action("×", "#8c8295"); close.title = "Close Theater Mode; Yearbook continues"; Object.assign(close.style, { width: "34px", height: "34px", padding: "0", fontSize: "18px" }); close.onclick = () => closeYearbookTheater(run); head.append(headText, runState, position, close);
    const center = document.createElement("div"); Object.assign(center.style, { minHeight: "0", display: "grid", gridTemplateRows: "minmax(0,1fr) auto", padding: "12px", gap: "9px" }); const frame = document.createElement("div"); Object.assign(frame.style, { minHeight: "0", position: "relative", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", borderRadius: "12px", border: "1px solid #27343a", background: "#020204" }); const image = document.createElement("img"); image.alt = "Newest Yearbook thumbnail"; image.draggable = false; image.hidden = true; const empty = document.createElement("div"); empty.textContent = "Waiting for the first thumbnail…"; Object.assign(empty.style, { color: "#756d7a", font: "800 13px Segoe UI,Arial" }); frame.append(image, empty);
    const info = document.createElement("div"); Object.assign(info.style, { display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: "10px", alignItems: "center" }); const path = document.createElement("div"); Object.assign(path.style, { minWidth: "0", color: "#9e98a4", font: "10px Segoe UI,Arial", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }); const sizeWrap = document.createElement("div"); Object.assign(sizeWrap.style, { display: "flex", gap: "5px" }); const sizeButtons = {}; for (const [name, label] of [["fit", "FIT"], ["fill", "FILL"], ["actual", "ACTUAL"]]) { const button = action(label, "#4a4452"); Object.assign(button.style, { padding: "6px 9px", fontSize: "8px" }); button.onclick = () => { theater.sizeMode = name; applyYearbookTheaterSizing(run); }; sizeButtons[name] = button; sizeWrap.append(button); } info.append(path, sizeWrap); center.append(frame, info);
    const controls = document.createElement("footer"); Object.assign(controls.style, { display: "grid", gridTemplateColumns: "auto minmax(300px,1fr) auto", alignItems: "center", gap: "12px", padding: "12px 14px 14px", borderTop: "1px solid #2d3940", background: "rgba(8,12,15,.97)" }); const nav = document.createElement("div"); Object.assign(nav.style, { display: "flex", gap: "6px", alignItems: "center" }); const previous = action("←", "#8c8295"); const next = action("→", "#8c8295"); const live = action("● LIVE", "#69e49a"); previous.onclick = () => { if (!theater.entries.length) return; theater.live = false; theater.cursor = Math.max(0, theater.cursor - 1); updateYearbookTheater(run); }; next.onclick = () => { if (!theater.entries.length) return; theater.live = false; theater.cursor = Math.min(theater.entries.length - 1, theater.cursor + 1); updateYearbookTheater(run); }; live.onclick = () => { theater.live = !theater.live; if (theater.live && theater.entries.length) theater.cursor = theater.entries.length - 1; updateYearbookTheater(run); }; nav.append(previous, next, live);
    const review = document.createElement("div"); Object.assign(review.style, { display: "flex", flexDirection: "column", alignItems: "center", gap: "7px" });
    const reviewRow = document.createElement("div"); Object.assign(reviewRow.style, { display: "grid", gridTemplateColumns: "repeat(4,minmax(94px,1fr))", justifyContent: "center", gap: "8px", width: "min(560px,100%)" });
    const reviewButtons = [];
    for (const [label, state, tone, shortcut] of [["★ FAVORITE", "favorite", "#f4ec51", "1"], ["✓ LIKE", "keep", "#69e49a", "2"], ["↻ RETEST", "retest", "#48e8ee", "3"], ["× REJECT", "reject", "#ff3eaf", "X"]]) {
        const button = action(`${label} [${shortcut}]`, tone); button.dataset.reviewState = state; button.title = `${label.replace(/^[^A-Z]+/, "")} · key ${shortcut}`;
        Object.assign(button.style, { minWidth: "0", padding: "11px 9px", fontSize: "10px" });
        button.onclick = () => { const entry = yearbookTheaterCurrent(run); if (entry) void setYearbookTheaterReview(run, entry, state); };
        reviewButtons.push(button); reviewRow.append(button);
    }
    const stats = document.createElement("div"); Object.assign(stats.style, { color: "#8f8997", font: "800 8px Segoe UI,Arial", letterSpacing: ".06em", textAlign: "center" }); review.append(reviewRow, stats); controls.append(nav, review, document.createElement("span")); card.append(head, center, controls); overlay.append(card); document.body.append(overlay); theater.overlay = overlay; theater.ui = { subtitle, title, runState, position, frame, image, empty, path, sizeButtons, previous, next, live, reviewButtons, stats };
    overlay.addEventListener("keydown", event => { if (event.ctrlKey || event.metaKey || event.altKey) return; const shortcutStates = { "1": "favorite", "2": "keep", "3": "retest", "f": "favorite", "l": "keep", "r": "retest", "x": "reject" }; const shortcutState = shortcutStates[event.key.toLowerCase()]; if (shortcutState) { event.preventDefault(); const entry = yearbookTheaterCurrent(run); if (entry) void setYearbookTheaterReview(run, entry, shortcutState); return; } if (event.key === " ") { event.preventDefault(); theater.live = !theater.live; if (theater.live && theater.entries.length) theater.cursor = theater.entries.length - 1; updateYearbookTheater(run); return; } if (event.key === "ArrowLeft") { event.preventDefault(); if (theater.entries.length) { theater.live = false; theater.cursor = Math.max(0, theater.cursor - 1); updateYearbookTheater(run); } return; } if (event.key === "ArrowRight") { event.preventDefault(); if (theater.entries.length) { theater.live = false; theater.cursor = Math.min(theater.entries.length - 1, theater.cursor + 1); updateYearbookTheater(run); } return; } if (event.key === "Escape") { event.preventDefault(); closeYearbookTheater(run); } }, true); updateYearbookTheater(run); requestAnimationFrame(() => overlay.focus());
}

function hasRenderableThumbnail(asset) {
    if (!asset?.thumbnail_ref) return false;
    return asset.thumbnail_available !== false;
}

function yearbookTargetMatches(asset, mode) {
    const source = String(asset?.thumbnail_source || "");
    const hasVisible = hasRenderableThumbnail(asset);
    if (mode === "missing") return !hasVisible;
    if (mode === "civitai") return hasVisible && source === "civitai-showcase";
    if (mode === "generated") return hasVisible && source.startsWith("generated") && !source.startsWith("generated:yearbook");
    if (mode === "yearbook") return hasVisible && source.startsWith("generated:yearbook");
    if (mode === "non_yearbook") return !hasVisible || (source !== "custom-upload" && !source.startsWith("generated:yearbook"));
    if (mode === "all") return true;
    return false;
}

function yearbookTargets(values, mode) {
    return values.filter(asset => yearbookTargetMatches(asset, mode));
}

function folderTreeAssets() {
    if (collectionScope) {
        const ids = collectionAssetIds();
        return assets.filter(asset => ids.has(String(asset.asset_id)));
    }
    if (folderScope === ALL_FOLDERS) return [...assets];
    return assets.filter(asset => {
        const folder = String(asset.folder || "");
        return folder === folderScope || folder.startsWith(`${folderScope}/`);
    });
}

function isEditableTarget(target) {
    if (!(target instanceof Element)) return false;
    return Boolean(target.closest("input, textarea, select, [contenteditable='true']"));
}

function isolateTextInput(container) {
    if (!container) return;
    for (const type of ["keydown", "keyup", "keypress"]) {
        container.addEventListener(type, event => {
            if (isEditableTarget(event.target)) event.stopPropagation();
        });
    }
    container.addEventListener("pointerdown", event => {
        if (isEditableTarget(event.target)) event.stopPropagation();
    });
}

function releaseFocusInside(container) {
    const active = document.activeElement;
    if (active && container?.contains(active) && typeof active.blur === "function") active.blur();
}

let yearbookFocusRecoveryCleanup = null;

function releaseYearbookCanvasCapture() {
    const canvas = app.canvas;
    if (!canvas) return;
    try { canvas.pointer?.reset?.(); } catch (error) {}
    try { canvas.dragging_canvas = false; } catch (error) {}
    try { canvas.isDragging = false; } catch (error) {}
    try { canvas.node_capturing_input = null; } catch (error) {}
    try { canvas.node_widget = null; } catch (error) {}
    try {
        const canvasElement = canvas.canvas || app.canvasEl;
        if (canvasElement && document.activeElement === canvasElement && typeof canvasElement.blur === "function") canvasElement.blur();
    } catch (error) {}
}

function armYearbookFocusRecovery() {
    yearbookFocusRecoveryCleanup?.();

    let timeout = null;
    const focusEditable = (target) => {
        const editable = target instanceof Element ? target.closest("input, textarea, select, [contenteditable='true']") : null;
        if (!editable || typeof editable.focus !== "function") return;
        const refocus = () => {
            if (!editable.isConnected || document.activeElement === editable) return;
            try { editable.focus({ preventScroll: true }); }
            catch (error) { try { editable.focus(); } catch (focusError) {} }
        };
        queueMicrotask(refocus);
        requestAnimationFrame(refocus);
        setTimeout(refocus, 60);
    };

    const onPointerDown = (event) => focusEditable(event.target);
    const onMouseDown = (event) => focusEditable(event.target);
    const onInput = (event) => {
        if (!isEditableTarget(event.target)) return;
        const inputType = String(event.inputType || "");
        if (!inputType || inputType.startsWith("insert")) yearbookFocusRecoveryCleanup?.();
    };

    // During the recovery window, printable keys that already target a real text
    // control should stay out of Comfy/LiteGraph's global shortcut handlers.
    // We do not preventDefault(), so the browser can still perform normal editing.
    const onKeyDown = (event) => {
        if (!isEditableTarget(event.target)) return;
        if (event.ctrlKey || event.altKey || event.metaKey) return;
        if (event.key.length === 1 || event.key === "Enter" || event.key === "Backspace" || event.key === "Delete") {
            event.stopImmediatePropagation();
        }
    };

    const cleanup = () => {
        window.removeEventListener("pointerdown", onPointerDown, true);
        window.removeEventListener("mousedown", onMouseDown, true);
        window.removeEventListener("keydown", onKeyDown, true);
        window.removeEventListener("input", onInput, true);
        if (timeout !== null) clearTimeout(timeout);
        if (yearbookFocusRecoveryCleanup === cleanup) yearbookFocusRecoveryCleanup = null;
    };
    yearbookFocusRecoveryCleanup = cleanup;

    window.addEventListener("pointerdown", onPointerDown, true);
    window.addEventListener("mousedown", onMouseDown, true);
    window.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("input", onInput, true);
    timeout = setTimeout(cleanup, 5 * 60 * 1000);
}

function thumbUrl(asset) {
    if (hasRenderableThumbnail(asset)) return `${API}/thumbnail/${encodeURIComponent(asset.thumbnail_ref)}?v=${encodeURIComponent(asset.thumbnail_updated_at || asset.updated_at || "")}`;
    // The grid never streams Civitai originals. Remote images are detail-only until
    // cached into the compact local thumbnail store.
    return "";
}

function sourceLabel(asset) {
    const source = String(asset.thumbnail_source || "");
    const hasVisible = hasRenderableThumbnail(asset);
    if (!hasVisible && asset.civitai_preview) return "CIVITAI READY";
    if (source.startsWith("generated:yearbook") && hasVisible) return "YEARBOOK";
    if (source.startsWith("generated") && hasVisible) return "GENERATED";
    if (source === "custom-upload" && hasVisible) return "CUSTOM";
    if (source === "civitai-showcase" && hasVisible) return "CIVITAI";
    if (source === "local-sidecar" && hasVisible) return "LOCAL PREVIEW";
    return hasVisible && source ? source.replaceAll("-", " ").toUpperCase() : "NO THUMBNAIL";
}

function autoFirstEnabled() {
    return localStorage.getItem(AUTO_FIRST_KEY) !== "false";
}

function folderChoices() {
    return [ALL_FOLDERS, ...liveFolders].sort((a, b) => {
        if (a === ALL_FOLDERS) return -1; if (b === ALL_FOLDERS) return 1; return a.localeCompare(b, undefined, { sensitivity: "base" });
    });
}

function rebuildFolderAssetCounts() {
    const counts = new Map([[ALL_FOLDERS, assets.length]]);
    for (const asset of assets) {
        const folder = String(asset.folder || "");
        if (!folder || folder === "[Root]") continue;
        const parts = folder.split("/").filter(Boolean);
        for (let index = 1; index <= parts.length; index++) {
            const path = parts.slice(0, index).join("/");
            counts.set(path, Number(counts.get(path) || 0) + 1);
        }
    }
    folderAssetCounts = counts;
}

function activeLoraCollection() { return loraCollections.find(item => String(item.collection_id) === String(collectionScope)); }
function currentScopeLabel() { return activeLoraCollection()?.name || (folderScope === ALL_FOLDERS ? "All LoRAs" : folderScope); }
function collectionAssetIds() { return new Set((activeLoraCollection()?.asset_ids || []).map(String)); }

function epochChoices() {
    return [...new Set(assets.map(asset => asset.epoch).filter(value => Number.isInteger(value)))].sort((a, b) => a - b);
}

function visibleAssets() {
    const collectionIds = collectionScope ? collectionAssetIds() : null;
    const values = assets.filter(asset => {
        if (collectionIds && !collectionIds.has(String(asset.asset_id))) return false;
        if (folderScope !== ALL_FOLDERS) {
            const folder = String(asset.folder || "");
            if (!(folder === folderScope || folder.startsWith(`${folderScope}/`))) return false;
        }
        if (epochFilter !== "" && Number(asset.epoch) !== Number(epochFilter)) return false;
        const uses = Number(asset.use_count || 0);
        if (statusFilter === "tested" && uses <= 0) return false;
        if (statusFilter === "untested" && uses > 0) return false;
        if (["keep", "favorite", "retest", "reject"].includes(statusFilter) && asset.review_state !== statusFilter) return false;
        const source = String(asset.thumbnail_source || "");
        const hasVisible = hasRenderableThumbnail(asset);
        if (thumbnailFilter === "missing" && hasVisible) return false;
        if (thumbnailFilter === "civitai" && !((hasVisible && source === "civitai-showcase") || (!hasVisible && asset.civitai_preview))) return false;
        if (thumbnailFilter === "generated" && !(hasVisible && source.startsWith("generated"))) return false;
        if (thumbnailFilter === "custom" && !(hasVisible && source === "custom-upload")) return false;
        if (thumbnailFilter === "local" && !(hasVisible && source === "local-sidecar")) return false;
        return true;
    });
    const byName = (a, b) => String(a.model_name || "").localeCompare(String(b.model_name || ""), undefined, { sensitivity: "base" });
    values.sort((a, b) => {
        if (sortMode === "name") return byName(a, b);
        if (sortMode === "most_used") return Number(b.use_count || 0) - Number(a.use_count || 0) || byName(a, b);
        if (sortMode === "least_used") return Number(a.use_count || 0) - Number(b.use_count || 0) || byName(a, b);
        if (sortMode === "last_used") return String(b.last_used_at || "").localeCompare(String(a.last_used_at || "")) || byName(a, b);
        if (sortMode === "thumbnail_newest") {
            const aHasThumbnail = hasRenderableThumbnail(a);
            const bHasThumbnail = hasRenderableThumbnail(b);
            if (aHasThumbnail !== bHasThumbnail) return bHasThumbnail ? 1 : -1;
            const thumbnailOrder = String(b.thumbnail_updated_at || "").localeCompare(String(a.thumbnail_updated_at || ""));
            return thumbnailOrder || String(b.updated_at || "").localeCompare(String(a.updated_at || "")) || byName(a, b);
        }
        return String(b.updated_at || "").localeCompare(String(a.updated_at || "")) || byName(a, b);
    });
    return values;
}

function assetById(assetId) { return assets.find(asset => asset.asset_id === assetId); }

function toggleLoraSelection(assetId) {
    const id = String(assetId || "");
    if (!id) return;
    if (selectedLoraIds.has(id)) selectedLoraIds.delete(id);
    else selectedLoraIds.add(id);
    loraSelectionMode = true;
    renderTools(); renderList();
}

function clearLoraSelection(exitMode = false) {
    selectedLoraIds.clear();
    if (exitMode) loraSelectionMode = false;
}

function overlayPendingReviewState(nextAssets) {
    for (const asset of nextAssets) {
        const mutation = reviewMutations.get(asset.asset_id);
        if (!mutation) continue;
        if (!mutation.pending && asset.review_state === mutation.state) {
            reviewMutations.delete(asset.asset_id);
            continue;
        }
        asset.review_state = mutation.state;
    }
}

async function load() {
    if (libraryLoadPromise) return libraryLoadPromise;
    libraryLoadPromise = (async () => {
        const [nextAssets, nextLiveFolders, nextCollections] = await Promise.all([request(`/assets?sort=recent`), request(`/folders`), request(`/lora-collections`)]);
        overlayPendingReviewState(nextAssets);
        assets = nextAssets;
        liveFolders = nextLiveFolders;
        loraCollections = nextCollections;
        rebuildFolderAssetCounts();
        if (!collectionScope && folderScope !== ALL_FOLDERS && !folderChoices().includes(folderScope)) folderScope = ALL_FOLDERS;
        if (collectionScope && !activeLoraCollection()) collectionScope = "";
        renderSidebar(); renderTools(); renderList(); updateScanButton();
    })();
    try { return await libraryLoadPromise; }
    finally { libraryLoadPromise = null; }
}

function updateCachedThumbnail(assetId, thumbnail) {
    const asset = assets.find(item => item.asset_id === assetId);
    if (!asset || !thumbnail?.filename) return;
    asset.thumbnail_ref = thumbnail.filename;
    asset.thumbnail_available = true;
    asset.thumbnail_source = thumbnail.source || "generated:preview";
    asset.thumbnail_width = Number(thumbnail.width || 0);
    asset.thumbnail_height = Number(thumbnail.height || 0);
    asset.thumbnail_bytes = Number(thumbnail.byte_size || 0);
    asset.thumbnail_updated_at = thumbnail.updated_at || new Date().toISOString();
    renderList();
}

function refreshCatalogAfterYearbook() {
    clearTimeout(catalogRefreshTimer);
    catalogRefreshTimer = setTimeout(() => {
        catalogRefreshTimer = null;
        load().catch(error => setFeedback(error.message, "#ff78bd"));
    }, 450);
}

async function setReview(asset, next) {
    const canonical = assetById(asset.asset_id) || asset;
    const previous = canonical.review_state;
    const state = previous === next ? "none" : next;
    const serial = ++reviewMutationSerial;
    reviewMutations.set(asset.asset_id, { serial, state, previous, pending: true });
    canonical.review_state = state;
    asset.review_state = state;
    renderList();
    try {
        await request("/review", { method: "POST", body: { asset_id: asset.asset_id, state } });
        const mutation = reviewMutations.get(asset.asset_id);
        if (mutation?.serial === serial) {
            mutation.pending = false;
            setTimeout(() => {
                const current = reviewMutations.get(asset.asset_id);
                if (current?.serial === serial && !current.pending) reviewMutations.delete(asset.asset_id);
            }, 5000);
        }
        setFeedback(`${asset.model_name}: ${state === "none" ? "rating cleared" : state}`);
        // The review POST is already durable before it returns. Do not immediately
        // reload the entire catalog here: that extra fetch used to overwrite the
        // optimistic button state for a frame (or longer) and caused the visible
        // on/off/on flicker. Any later catalog refresh is reconciled by
        // overlayPendingReviewState until the server reports the committed state.
        renderList();
        return state;
    } catch (error) {
        const mutation = reviewMutations.get(asset.asset_id);
        if (mutation?.serial === serial) {
            reviewMutations.delete(asset.asset_id);
            const current = assetById(asset.asset_id) || asset;
            current.review_state = previous;
            asset.review_state = previous;
        }
        renderList();
        setFeedback(error.message, "#ff78bd");
        return previous;
    }
}

async function quarantineRejected(button) {
    const rejected = assets.filter(asset => asset.review_state === "reject");
    if (!rejected.length) { alert("There are no rejected LoRAs in the live library."); return; }
    if (!confirm(`Move all ${rejected.length} rejected LoRA${rejected.length === 1 ? "" : "s"} and their recognized adjacent sidecars into the recoverable Sick Ollie quarantine folder?`)) return;
    button.disabled = true; button.textContent = "Quarantining…";
    try {
        const result = await request("/quarantine-rejected", { method: "POST", body: {} });
        await load();
        const suffix = result.skipped ? ` · ${result.skipped} skipped` : "";
        setFeedback(`Quarantined ${result.quarantined} rejected LoRA${result.quarantined === 1 ? "" : "s"}${suffix}.`);
        if (result.errors?.length) console.warn("[Sick Ollie LoRA Library] Rejected quarantine issues:", result.errors);
    } catch (error) {
        alert(error.message || "Could not quarantine rejected LoRAs.");
    } finally {
        button.disabled = false; button.textContent = "Quarantine rejected";
    }
}

function stateButtons(asset, compact = true) {
    const row = document.createElement("div"); row.className = compact ? "so-lib-state-row" : "so-lib-actions";
    const buttons = [];
    const sync = () => {
        const pending = Boolean(reviewMutations.get(asset.asset_id)?.pending);
        for (const [button, value] of buttons) {
            button.classList.toggle("active", asset.review_state === value);
            button.disabled = pending;
        }
    };
    for (const [label, value, tone] of [["★", "favorite", "#f4ec51"], ["✓", "keep", "#69e49a"], ["↻", "retest", "#48e8ee"], ["×", "reject", "#ff3eaf"]]) {
        const button = action(label, tone); button.title = ({ keep: "Like", favorite: "Favorite", retest: "Retest", reject: "Reject" })[value];
        buttons.push([button, value]);
        button.onclick = async event => { event.stopPropagation(); await setReview(asset, value); sync(); };
        row.append(button);
    }
    sync();
    return row;
}

function renderList() {
    const list = root?.querySelector("[data-list]"); if (!list) return;
    list.replaceChildren();
    const visible = visibleAssets();
    const columns = Math.max(1, Math.floor((Math.max(210, list.clientWidth - 28) + 14) / 224));
    const galleryPageSize = columns * 4;
    const totalPages = Math.max(1, Math.ceil(visible.length / galleryPageSize));
    galleryPage = Math.min(galleryPage, totalPages - 1);
    const pageStart = galleryPage * galleryPageSize;
    const shown = visible.slice(pageStart, pageStart + galleryPageSize);
    const status = root.querySelector("[data-review-status]");
    if (status && !yearbook && !civitaiFilling) status.textContent = `${visible.length.toLocaleString()} shown · ${assets.length.toLocaleString()} cataloged`;
    if (!visible.length) {
        const empty = document.createElement("div"); empty.className = "so-lib-empty";
        empty.textContent = assets.length ? "No LoRAs match this folder, epoch, status, and thumbnail combination." : "Nothing cataloged yet. Scan your configured LoRA folders to build the visual library.";
        list.append(empty); return;
    }
    for (const asset of shown) {
        const selected = selectedLoraIds.has(String(asset.asset_id || ""));
        const card = document.createElement("article"); card.className = `so-lib-card${selected ? " selected" : ""}`; card.onclick = () => loraSelectionMode ? toggleLoraSelection(asset.asset_id) : openDetail(asset.asset_id);
        const preview = document.createElement("div"); preview.className = "so-lib-preview"; preview.style.cssText = "aspect-ratio:3 / 4;flex:0 0 auto!important;height:auto!important;min-height:0;";
        const url = thumbUrl(asset);
        if (url) {
            const image = document.createElement("img"); image.src = url; image.alt = asset.model_name || "LoRA thumbnail"; image.loading = "lazy"; image.referrerPolicy = "no-referrer";
            preview.append(image);
        } else {
            const placeholder = document.createElement("div"); placeholder.className = "so-lib-placeholder"; placeholder.textContent = asset.civitai_preview ? "Civitai image ready to cache" : "No local thumbnail yet"; preview.append(placeholder);
        }
        const badge = document.createElement("span"); badge.className = "so-lib-badge"; badge.textContent = sourceLabel(asset); badge.style.setProperty("--badge", hasRenderableThumbnail(asset) ? "#69e49a" : asset.civitai_preview ? "#9c62ff" : "#8c8295"); preview.append(badge);
        if (loraSelectionMode) {
            const selector = document.createElement("button"); selector.type = "button"; selector.className = "so-lib-card-selector"; selector.textContent = selected ? "✓" : ""; selector.title = selected ? "Remove from selection" : "Select LoRA"; selector.setAttribute("aria-pressed", selected ? "true" : "false");
            selector.onclick = event => { event.stopPropagation(); toggleLoraSelection(asset.asset_id); };
            preview.append(selector);
        }
        const uses = Number(asset.use_count || 0); const usage = document.createElement("span"); usage.className = "so-lib-usage-pill"; usage.textContent = uses ? `used ${uses}×` : "untested"; preview.append(usage);
        const body = document.createElement("div"); body.className = "so-lib-card-body"; body.style.cssText = "display:block!important;flex:0 0 auto!important;min-height:92px;";
        const name = document.createElement("strong"); name.className = "so-lib-card-name"; name.textContent = asset.model_name || asset.relative_lora;
        const quick = document.createElement("div"); quick.className = "so-lib-card-quick";
        const loadButton = action("LOAD", "#69e49a"); loadButton.onclick = async event => { event.stopPropagation(); loadButton.disabled = true; loadButton.textContent = "LOADING…"; try { await loadIntoLoader(asset.relative_lora); const strength = widget(findLoader(), "main_strength")?.value; setFeedback(`Loaded ${asset.model_name}${strength !== undefined ? ` · strength ${strength}` : ""} · fixed.`); loadButton.textContent = "LOADED ✓"; } catch (error) { alert(error.message); loadButton.disabled = false; loadButton.textContent = "LOAD"; } };
        const queueButton = action("QUEUE", "#b89aff"); queueButton.title = "Queue this LoRA with the active workflow"; queueButton.onclick = event => { event.stopPropagation(); queueLoraAsset(asset, queueButton); };
        const collectButton = action("＋", "#48e8ee"); collectButton.title = "Add this LoRA to a collection"; collectButton.onclick = event => { event.stopPropagation(); openLoraCollectionPicker([asset.asset_id]); };
        quick.append(loadButton, queueButton, collectButton);
        body.append(name, quick, stateButtons(asset)); card.append(preview, body); list.append(card);
    }
    if (totalPages > 1) {
        const pager = document.createElement("div"); pager.className = "so-lib-pager";
        const prev = action("← Previous", "#48e8ee"); prev.disabled = galleryPage === 0; prev.onclick = () => { galleryPage--; renderList(); list.scrollTo({ top: 0 }); };
        const next = action("Next →", "#48e8ee"); next.disabled = galleryPage >= totalPages - 1; next.onclick = () => { galleryPage++; renderList(); list.scrollTo({ top: 0 }); };
        const label = document.createElement("span"); label.textContent = `Page ${galleryPage + 1} of ${totalPages} · ${visible.length.toLocaleString()} matching LoRAs`;
        pager.append(prev, label, next); list.append(pager);
    }
}

function openFolderPicker() {
    ensureStyle();
    const modal = document.createElement("div"); modal.className = "so-lib-modal";
    const card = document.createElement("section"); card.className = "so-lib-form-card";
    const title = document.createElement("h3"); title.textContent = "FOLDER SCOPE";
    const copy = document.createElement("p"); copy.textContent = "Choose a LoRA folder. A parent scope includes its nested folders, matching Loader Core's folder browser.";
    const search = document.createElement("input"); search.className = "so-lib-picker-search"; search.placeholder = "Find a folder…";
    const list = document.createElement("div"); list.className = "so-lib-picker-list";
    let browserFolder = folderScope === ALL_FOLDERS ? ALL_FOLDERS : folderScope;
    const draw = () => {
        list.replaceChildren(); const needle = search.value.trim().toLowerCase();
        const choices = needle ? folderChoices().filter(item => item !== ALL_FOLDERS && item.toLowerCase().includes(needle)) : folderChoices().filter(item => item === ALL_FOLDERS || (browserFolder === ALL_FOLDERS ? !item.includes("/") : item.startsWith(`${browserFolder}/`) && item.slice(browserFolder.length + 1).indexOf("/") < 0));
        if (!needle && browserFolder !== ALL_FOLDERS) { const select = document.createElement("button"); select.className = `so-lib-picker-item${browserFolder === folderScope ? " active" : ""}`; select.type = "button"; select.textContent = `✓ Use ${browserFolder} + nested folders`; select.onclick = () => { folderScope = browserFolder; modal.remove(); renderTools(); renderList(); }; list.append(select); }
        if (!needle && browserFolder !== ALL_FOLDERS) { const up = document.createElement("button"); up.className = "so-lib-picker-item"; up.type = "button"; up.textContent = "↑ Parent Folder"; up.onclick = () => { browserFolder = browserFolder.includes("/") ? browserFolder.slice(0, browserFolder.lastIndexOf("/")) : ALL_FOLDERS; draw(); }; list.append(up); }
        for (const value of choices) {
            const item = document.createElement("button"); item.className = `so-lib-picker-item${value === folderScope ? " active" : ""}`; item.type = "button";
            item.textContent = value === ALL_FOLDERS ? "⌂ LoRA Root · all folders" : `📁 ${value.split("/").pop()}`;
            item.onclick = () => { if (!needle && value !== ALL_FOLDERS && liveFolders.some(folder => folder.startsWith(`${value}/`))) { browserFolder = value; draw(); } else { folderScope = value; modal.remove(); renderTools(); renderList(); } };
            list.append(item);
        }
    };
    search.oninput = draw; modal.onclick = event => { if (event.target === modal) { releaseFocusInside(modal); modal.remove(); } };
    card.append(title, copy, search, list); modal.append(card); document.body.append(modal); isolateTextInput(modal); draw(); search.focus();
}

async function createLoraCollection(name, assetIds = []) {
    const result = await request("/lora-collections", { method: "POST", body: { name } });
    const collection = result.collection;
    if (assetIds.length) await updateLoraCollectionMemberships([collection.collection_id], assetIds, "add", false);
    loraCollections = await request("/lora-collections");
    collectionScope = String(collection.collection_id || ""); folderScope = ALL_FOLDERS; galleryPage = 0;
    renderSidebar(); renderTools(); renderList(); updateScanButton();
    window.dispatchEvent(new CustomEvent("sickollie:lora-collections-updated"));
    return collection;
}

function applyLocalLoraCollectionMemberships(collectionIds, assetIds, actionName) {
    const collectionSet = new Set((collectionIds || []).map(String));
    const assetSet = new Set((assetIds || []).map(String));
    for (const collection of loraCollections) {
        if (!collectionSet.has(String(collection.collection_id || ""))) continue;
        const members = new Set((collection.asset_ids || []).map(String));
        if (actionName === "remove") for (const id of assetSet) members.delete(id);
        else for (const id of assetSet) members.add(id);
        collection.asset_ids = [...members];
        collection.asset_count = members.size;
    }
}

async function updateLoraCollectionMemberships(collectionIds, assetIds, actionName = "add", redraw = true) {
    const cleanCollections = [...new Set((collectionIds || []).map(String).filter(Boolean))];
    const cleanAssets = [...new Set((assetIds || []).map(String).filter(Boolean))];
    if (!cleanCollections.length || !cleanAssets.length) return { assets: cleanAssets.length, collections: cleanCollections.length, memberships_changed: 0 };
    const result = await request("/lora-collections/members/bulk", { method: "POST", body: { action: actionName, asset_ids: cleanAssets, collection_ids: cleanCollections } });
    applyLocalLoraCollectionMemberships(cleanCollections, cleanAssets, actionName);
    if (redraw) { renderSidebar(); renderTools(); renderList(); updateScanButton(); }
    window.dispatchEvent(new CustomEvent("sickollie:lora-collections-updated"));
    return result;
}

function openLoraCollectionPicker(assetIds) {
    const ids = [...new Set((assetIds || []).map(String).filter(Boolean))];
    const modal = document.createElement("div"); modal.className = "so-lib-modal";
    const card = document.createElement("section"); card.className = "so-lib-form-card";
    const title = document.createElement("h3"); title.textContent = !ids.length ? "NEW LORA COLLECTION" : ids.length === 1 ? "ADD LORA TO COLLECTION" : `ADD ${ids.length} LORAS TO COLLECTION`;
    const copy = document.createElement("p"); copy.textContent = ids.length ? "Choose every collection you want in one pass, then save once. Collections are virtual; LoRA files stay exactly where they live on disk." : "Create a virtual collection without changing any LoRA file locations.";
    const createRow = document.createElement("div"); Object.assign(createRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "7px" });
    const input = document.createElement("input"); input.className = "so-lib-picker-search"; input.placeholder = "New collection name…";
    const create = action(ids.length ? "CREATE + ADD" : "CREATE", "#b89aff"); create.onclick = async () => { const name = input.value.trim(); if (!name) return; create.disabled = true; try { await createLoraCollection(name, ids); modal.remove(); if (ids.length) { clearLoraSelection(true); renderTools(); renderList(); } setFeedback(ids.length ? `Added ${ids.length} LoRA${ids.length === 1 ? "" : "s"} to ${name}.` : `Created ${name}.`); } catch (error) { alert(error.message); create.disabled = false; } };
    createRow.append(input, create);
    const list = document.createElement("div"); list.className = "so-lib-picker-list";
    const touched = new Set();
    for (const collection of ids.length ? loraCollections : []) {
        const memberIds = new Set((collection.asset_ids || []).map(String));
        const insideCount = ids.filter(id => memberIds.has(id)).length;
        const allInside = insideCount === ids.length;
        const partiallyInside = insideCount > 0 && !allInside;
        const row = document.createElement("label"); row.className = `so-lib-picker-item so-lib-picker-check${allInside ? " active" : ""}`;
        const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.value = String(collection.collection_id); checkbox.checked = allInside; checkbox.indeterminate = partiallyInside; checkbox.dataset.initial = allInside ? "all" : partiallyInside ? "some" : "none";
        checkbox.onchange = () => { checkbox.indeterminate = false; touched.add(String(collection.collection_id)); row.classList.toggle("active", checkbox.checked); };
        const name = document.createElement("span"); name.textContent = collection.name; name.style.flex = "1";
        const count = document.createElement("em"); count.textContent = partiallyInside ? `${insideCount}/${ids.length} selected · ${Number(collection.asset_count || 0).toLocaleString()} total` : `${Number(collection.asset_count || 0).toLocaleString()}`;
        row.append(checkbox, name, count);
        list.append(row);
    }
    if (ids.length && !loraCollections.length) { const empty = document.createElement("div"); empty.className = "so-lib-empty"; empty.style.padding = "24px"; empty.textContent = "No collections yet. Create the first one above."; list.append(empty); }
    list.hidden = !ids.length;
    const buttons = document.createElement("div"); buttons.className = "so-lib-form-actions"; const cancel = action("Cancel", "#8c8295"); cancel.onclick = () => modal.remove(); buttons.append(cancel);
    if (ids.length && loraCollections.length) {
        const save = action("SAVE COLLECTIONS", "#69e49a"); save.onclick = async () => {
            const addIds = [], removeIds = [];
            for (const checkbox of list.querySelectorAll('input[type="checkbox"]')) {
                const id = String(checkbox.value || "");
                if (!touched.has(id)) continue;
                if (checkbox.checked) addIds.push(id); else removeIds.push(id);
            }
            if (!addIds.length && !removeIds.length) { modal.remove(); return; }
            save.disabled = true; cancel.disabled = true;
            try {
                if (addIds.length) await updateLoraCollectionMemberships(addIds, ids, "add", false);
                if (removeIds.length) await updateLoraCollectionMemberships(removeIds, ids, "remove", false);
                modal.remove();
                clearLoraSelection(true);
                renderSidebar(); renderTools(); renderList(); updateScanButton();
                const changed = addIds.length + removeIds.length;
                setFeedback(`Updated ${ids.length.toLocaleString()} LoRA${ids.length === 1 ? "" : "s"} across ${changed.toLocaleString()} collection${changed === 1 ? "" : "s"}.`);
            } catch (error) { alert(error.message); save.disabled = false; cancel.disabled = false; }
        };
        buttons.append(save);
    }
    card.append(title, copy, createRow, list, buttons); modal.append(card); document.body.append(modal); isolateTextInput(modal); modal.onclick = event => { if (event.target === modal) modal.remove(); }; input.focus();
}

function renderSidebar() {
    const sidebar = root?.querySelector("[data-lora-sidebar]"); if (!sidebar) return;
    sidebar.replaceChildren();
    const search = document.createElement("input"); search.className = "so-lib-sidebar-search"; search.placeholder = "Find folders…";
    const foldersTitle = document.createElement("div"); foldersTitle.className = "so-lib-sidebar-title"; foldersTitle.textContent = "FOLDERS";
    const folderList = document.createElement("div"); folderList.className = "so-lib-sidebar-list";
    const collectionsTitle = document.createElement("div"); collectionsTitle.className = "so-lib-sidebar-title"; collectionsTitle.textContent = "COLLECTIONS";
    const collectionList = document.createElement("div"); collectionList.className = "so-lib-sidebar-list so-lib-sidebar-collections";
    const chooseFolder = value => { collectionScope = ""; folderScope = value; galleryPage = 0; for (const path of String(value).split("/").slice(0, -1).map((_, index, parts) => parts.slice(0, index + 1).join("/"))) expandedFolders.add(path); renderSidebar(); renderTools(); renderList(); updateScanButton(); };
    const folderCount = value => Number(folderAssetCounts.get(value) || 0);
    const drawFolders = () => {
        folderList.replaceChildren(); const needle = search.value.trim().toLowerCase();
        const rootRow = document.createElement("button"); rootRow.type = "button"; rootRow.className = `so-lib-sidebar-row${!collectionScope && folderScope === ALL_FOLDERS ? " active" : ""}`; rootRow.innerHTML = `<span>⌂</span><b>All LoRAs</b><em>${folderCount(ALL_FOLDERS).toLocaleString()}</em>`; rootRow.onclick = () => chooseFolder(ALL_FOLDERS); folderList.append(rootRow);
        const children = new Map();
        for (const path of liveFolders) { const parent = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : ""; if (!children.has(parent)) children.set(parent, []); children.get(parent).push(path); }
        const addPath = (path, depth, recurse = true) => { const nested = children.get(path) || []; const row = document.createElement("div"); row.className = `so-lib-sidebar-row${!collectionScope && folderScope === path ? " active" : ""}`; row.style.setProperty("--depth", depth); const caret = document.createElement("button"); caret.type = "button"; caret.className = "so-lib-sidebar-caret"; caret.textContent = nested.length ? (expandedFolders.has(path) ? "▾" : "▸") : ""; caret.disabled = !nested.length; caret.onclick = event => { event.stopPropagation(); if (expandedFolders.has(path)) expandedFolders.delete(path); else expandedFolders.add(path); drawFolders(); }; const name = document.createElement("button"); name.type = "button"; name.className = "so-lib-sidebar-name"; name.textContent = `📁 ${path.split("/").pop()}`; name.title = path; name.onclick = () => chooseFolder(path); const count = document.createElement("em"); count.textContent = folderCount(path).toLocaleString(); row.append(caret, name, count); folderList.append(row); if (recurse && expandedFolders.has(path)) for (const child of nested.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))) addPath(child, depth + 1); };
        if (needle) for (const path of liveFolders.filter(path => path.toLowerCase().includes(needle)).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))) addPath(path, Math.min(4, path.split("/").length - 1), false);
        else for (const path of (children.get("") || []).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }))) addPath(path, 0);
    };
    search.oninput = drawFolders;
    const newCollection = document.createElement("button"); newCollection.type = "button"; newCollection.className = "so-lib-sidebar-row so-lib-sidebar-new"; newCollection.innerHTML = "<span>＋</span><b>New collection</b><em></em>"; newCollection.onclick = () => openLoraCollectionPicker([]);
    collectionList.append(newCollection);
    for (const collection of loraCollections) {
        const row = document.createElement("div"); row.className = `so-lib-sidebar-row${String(collectionScope) === String(collection.collection_id) ? " active" : ""}`;
        const icon = document.createElement("span"); icon.textContent = "◆"; icon.style.color = collection.color || "#b89aff";
        const name = document.createElement("button"); name.type = "button"; name.className = "so-lib-sidebar-name"; name.textContent = collection.name; name.onclick = () => { collectionScope = String(collection.collection_id); folderScope = ALL_FOLDERS; galleryPage = 0; renderSidebar(); renderTools(); renderList(); updateScanButton(); };
        const count = document.createElement("em"); count.textContent = Number(collection.asset_count || 0).toLocaleString();
        const remove = document.createElement("button"); remove.type = "button"; remove.className = "so-lib-sidebar-delete"; remove.textContent = "×"; remove.title = "Delete collection only; LoRA files remain"; remove.onclick = async event => { event.stopPropagation(); if (!confirm(`Delete the collection “${collection.name}”? LoRA files and Library entries remain untouched.`)) return; await request(`/lora-collections/${encodeURIComponent(collection.collection_id)}`, { method: "DELETE" }); if (collectionScope === collection.collection_id) collectionScope = ""; await load(); window.dispatchEvent(new CustomEvent("sickollie:lora-collections-updated")); };
        row.append(icon, name, count, remove); collectionList.append(row);
    }
    sidebar.append(search, foldersTitle, folderList, collectionsTitle, collectionList); drawFolders();
}

function renderTools() {
    const tools = root?.querySelector("[data-tools]"); if (!tools) return;
    tools.replaceChildren();
    const epochs = selectControl([["", "All epochs"], ...epochChoices().map(value => [String(value), `Epoch ${value}`])], epochFilter, value => { epochFilter = value; renderList(); });
    const states = selectControl([["", "All review + test states"], ["tested", "Tested"], ["untested", "Never tested"], ["favorite", "Favorite"], ["keep", "Like"], ["retest", "Retest"], ["reject", "Reject"]], statusFilter, value => { statusFilter = value; renderList(); });
    const thumbs = selectControl([["", "All thumbnails"], ["missing", "Missing thumbnail"], ["civitai", "Civitai"], ["generated", "Generated"], ["custom", "Custom"], ["local", "Local preview"]], thumbnailFilter, value => { thumbnailFilter = value; renderList(); });
    const sorts = selectControl([["thumbnail_newest", "Newest thumbnail"], ["recent", "Recently cataloged"], ["name", "Name"], ["most_used", "Most used"], ["least_used", "Least used"], ["last_used", "Recently used"]], sortMode, value => { sortMode = value; galleryPage = 0; renderList(); });
    const auto = document.createElement("label"); auto.className = "so-lib-toggle";
    const check = document.createElement("input"); check.type = "checkbox"; check.checked = autoFirstEnabled(); check.onchange = () => { localStorage.setItem(AUTO_FIRST_KEY, check.checked ? "true" : "false"); setFeedback(check.checked ? "New LoRAs will use their first Preview image automatically." : "Automatic first-image thumbnails are off."); };
    const label = document.createElement("span"); label.textContent = "Auto first image"; auto.append(check, label);
    const refresh = action("Refresh", "#69e49a"); refresh.onclick = () => load().catch(error => setFeedback(error.message, "#ff78bd"));
    const scope = document.createElement("div"); scope.className = "so-lib-current-scope"; scope.textContent = currentScopeLabel();
    const queueScope = action(loraBatchQueue ? "STOP QUEUEING" : "QUEUE CURRENT VIEW", "#b89aff"); queueScope.dataset.queueScope = ""; queueScope.onclick = () => { if (loraBatchQueue) { loraBatchQueue.stopped = true; setFeedback("Stopping LoRA queue submission after the current item…", "#f4ec51"); } else openLoraScopeQueueDialog(); };
    const select = action(loraSelectionMode ? "DONE SELECTING" : "SELECT MULTIPLE", "#48e8ee"); select.onclick = () => { loraSelectionMode = !loraSelectionMode; if (!loraSelectionMode) selectedLoraIds.clear(); renderTools(); renderList(); };
    tools.append(scope, epochs, states, thumbs, sorts, auto, queueScope, select, refresh);
    if (loraSelectionMode) {
        const selection = document.createElement("div"); selection.className = "so-lib-selection-tools";
        const visible = visibleAssets();
        const count = document.createElement("strong"); count.textContent = `${selectedLoraIds.size.toLocaleString()} SELECTED`;
        const selectView = action(`SELECT VIEW · ${visible.length.toLocaleString()}`, "#48e8ee"); selectView.onclick = () => { for (const asset of visible) if (asset.asset_id) selectedLoraIds.add(String(asset.asset_id)); renderTools(); renderList(); };
        const clear = action("CLEAR", "#8c8295"); clear.disabled = !selectedLoraIds.size; clear.onclick = () => { selectedLoraIds.clear(); renderTools(); renderList(); };
        const collect = action("ADD TO COLLECTIONS", "#69e49a"); collect.disabled = !selectedLoraIds.size; collect.onclick = () => openLoraCollectionPicker([...selectedLoraIds]);
        selection.append(count, selectView, clear, collect); tools.append(selection);
    }
}

function fact(label, value, title = "") {
    const item = document.createElement("div"); item.className = "so-lib-fact";
    const key = document.createElement("span"); key.textContent = label;
    const data = document.createElement("strong"); data.textContent = String(value ?? "—"); if (title) data.title = title;
    item.append(key, data); return item;
}

function section(title) {
    const item = document.createElement("section"); item.className = "so-lib-section";
    const heading = document.createElement("div"); heading.className = "so-lib-section-title"; heading.textContent = title;
    item.append(heading); return item;
}

async function reopenDetail(modal, assetId) {
    modal.remove(); await load(); await openDetail(assetId);
}

async function openDetail(assetId) {
    ensureStyle();
    const modal = document.createElement("div"); modal.className = "so-lib-modal";
    const card = document.createElement("section"); card.className = "so-lib-modal-card";
    const head = document.createElement("header"); head.className = "so-lib-modal-head";
    const heading = document.createElement("strong"); heading.textContent = "Loading LoRA entry…";
    const close = action("×", "#48e8ee", "so-lib-icon"); close.onclick = () => { releaseFocusInside(modal); modal.remove(); }; head.append(heading, close);
    const loading = document.createElement("div"); loading.className = "so-lib-empty"; loading.textContent = "Reading triggers, usage, thumbnail provenance, and Civitai sidecars…";
    card.append(head, loading); modal.append(card); document.body.append(modal); isolateTextInput(modal); modal.onclick = event => { if (event.target === modal) { releaseFocusInside(modal); modal.remove(); } };
    let detail;
    try { detail = await request(`/asset/${encodeURIComponent(assetId)}`); }
    catch (error) { loading.textContent = error.message; return; }
    heading.textContent = detail.model_name || detail.relative_lora;
    loading.remove();
    const body = document.createElement("div"); body.className = "so-lib-detail";
    const media = document.createElement("div");
    const main = document.createElement("img"); main.className = "so-lib-main-image"; main.alt = detail.model_name || "LoRA image"; main.referrerPolicy = "no-referrer";
    const localUrl = detail.thumbnail?.filename ? `${API}/thumbnail/${encodeURIComponent(detail.thumbnail.filename)}?v=${encodeURIComponent(detail.thumbnail.updated_at || "")}` : "";
    const remoteImages = Array.isArray(detail.remote_metadata?.images) ? detail.remote_metadata.images : [];
    let selectedRemote = "";
    const initialImage = localUrl || remoteImages[0] || "";
    if (initialImage) main.src = initialImage;
    const showcase = document.createElement("div"); showcase.className = "so-lib-showcase";
    if (localUrl) {
        const local = document.createElement("img"); local.src = localUrl; local.alt = "Current local thumbnail"; local.className = "active";
        local.onclick = () => { selectedRemote = ""; main.src = localUrl; for (const image of showcase.querySelectorAll("img")) image.classList.toggle("active", image === local); };
        showcase.append(local);
    }
    for (const url of remoteImages) {
        const image = document.createElement("img"); image.src = url; image.alt = "Civitai showcase"; image.loading = "lazy"; image.referrerPolicy = "no-referrer";
        image.onclick = () => { selectedRemote = url; main.src = url; for (const item of showcase.querySelectorAll("img")) item.classList.toggle("active", item === image); };
        showcase.append(image);
    }
    const mediaActions = document.createElement("div"); mediaActions.className = "so-lib-actions"; mediaActions.style.marginTop = "9px";
    const upload = action("Set custom image", "#69e49a"); upload.onclick = () => {
        const picker = document.createElement("input"); picker.type = "file"; picker.accept = "image/png,image/jpeg,image/webp";
        picker.onchange = async () => { const file = picker.files?.[0]; if (!file) return; upload.disabled = true; try { const form = new FormData(); form.append("file", file); await request(`/thumbnail/upload/${encodeURIComponent(assetId)}`, { method: "POST", body: form }); await reopenDetail(modal, assetId); } catch (error) { alert(error.message); upload.disabled = false; } };
        picker.click();
    };
    const useCiv = action("Use selected Civitai image", "#9c62ff"); useCiv.disabled = !remoteImages.length; useCiv.onclick = async () => { const url = selectedRemote || remoteImages[0]; if (!url) return; useCiv.disabled = true; try { await request(`/thumbnail/cache-civitai/${encodeURIComponent(assetId)}`, { method: "POST", body: { url } }); await reopenDetail(modal, assetId); } catch (error) { alert(error.message); useCiv.disabled = false; } };
    const clearThumb = action("Clear local default", "#ff3eaf"); clearThumb.disabled = !detail.thumbnail; clearThumb.onclick = async () => { if (!confirm("Clear this local default thumbnail? The LoRA and Civitai showcase are untouched.")) return; await request(`/thumbnail/${encodeURIComponent(assetId)}`, { method: "DELETE" }); await reopenDetail(modal, assetId); };
    mediaActions.append(upload, useCiv, clearThumb); media.append(main, showcase, mediaActions);

    const info = document.createElement("div");
    const actions = section("ENTRY ACTIONS");
    const actionRow = document.createElement("div"); actionRow.className = "so-lib-actions";
    const loadButton = action("Load LoRA", "#69e49a"); loadButton.onclick = async () => { loadButton.disabled = true; loadButton.textContent = "Loading through Loader Core…"; try { await loadIntoLoader(detail.relative_lora); const strength = widget(findLoader(), "main_strength")?.value; setFeedback(`Loaded ${detail.model_name}${strength !== undefined ? ` · strength ${strength}` : ""} · fixed.`); releaseFocusInside(modal); modal.remove(); } catch (error) { alert(error.message); loadButton.disabled = false; loadButton.textContent = "Load LoRA"; } };
    const refreshCiv = action("Refresh Civitai", "#9c62ff"); refreshCiv.onclick = async () => { refreshCiv.disabled = true; refreshCiv.textContent = "Reading exact hash…"; try { await request(`/civitai/${encodeURIComponent(assetId)}`, { method: "POST", body: {} }); await reopenDetail(modal, assetId); } catch (error) { alert(error.message); refreshCiv.disabled = false; refreshCiv.textContent = "Refresh Civitai"; } };
    const civPage = civitaiPage(detail);
    const openCiv = action("Open Civitai", "#48e8ee"); openCiv.disabled = !civPage; openCiv.onclick = () => { if (!civPage) return; const opened = window.open(civPage, "_blank", "noopener,noreferrer"); if (opened) opened.opener = null; };
    const quarantine = action("Quarantine file", "#ff3eaf"); quarantine.onclick = async () => { if (!confirm(`Move ${detail.model_name} and its adjacent sidecars into the recoverable Sick Ollie quarantine folder?`)) return; try { const result = await request("/quarantine", { method: "POST", body: { asset_id: assetId } }); setFeedback(`Moved to ${result.quarantine_path}`); modal.remove(); await load(); } catch (error) { alert(error.message); } };
    actionRow.append(loadButton, refreshCiv, openCiv, quarantine); actions.append(actionRow, stateButtons({ ...detail, review_state: detail.review?.state || "none" }, false));

    const stats = section("USAGE + IDENTITY");
    const facts = document.createElement("div"); facts.className = "so-lib-facts";
    facts.append(
        fact("Uses", detail.usage?.use_count || 0), fact("First used", formatDate(detail.first_used_at)), fact("Last used", formatDate(detail.usage?.last_used_at)),
        fact("Epoch", detail.epoch ?? "—"), fact("Size", formatBytes(detail.size)), fact("Thumbnail", detail.thumbnail ? `${formatBytes(detail.thumbnail.byte_size)} · ${detail.thumbnail.width}×${detail.thumbnail.height}` : remoteImages.length ? "Civitai live" : "Missing"),
        fact("Folder", detail.folder || "[Root]", detail.folder || ""), fact("Base model", detail.remote_metadata?.base_model || "—"), fact("Creator", detail.remote_metadata?.creator || "—"),
    );
    const path = document.createElement("div"); path.className = "so-lib-detail-path"; path.style.marginTop = "9px"; path.textContent = detail.current_path;
    stats.append(facts, path);

    const triggers = section("DETECTED TRIGGERS");
    const chips = document.createElement("div"); chips.className = "so-lib-chips";
    const triggerValues = (detail.triggers || []).length ? detail.triggers : (detail.remote_metadata?.trained_words || []).map(raw_text => ({ raw_text, source: "civitai" }));
    for (const trigger of triggerValues) { const chip = document.createElement("span"); chip.className = "so-lib-chip"; chip.textContent = `${trigger.raw_text || trigger.clean_text}${trigger.source ? ` · ${trigger.source}` : ""}`; chips.append(chip); }
    if (!triggerValues.length) { const none = document.createElement("span"); none.style.color = "#8f8498"; none.textContent = "No explicit activation phrase detected."; chips.append(none); }
    triggers.append(chips);

    const history = section("RECENT GENERATED OUTPUTS");
    const historyList = document.createElement("div"); historyList.className = "so-lib-history";
    for (const event of detail.usage_events || []) { const row = document.createElement("div"); row.className = "so-lib-history-row"; const date = document.createElement("b"); date.textContent = formatDate(event.used_at); const output = document.createElement("div"); output.textContent = event.output_path || "Generation completed before output tracking"; output.title = output.textContent; row.append(date, output); historyList.append(row); }
    if (!(detail.usage_events || []).length) historyList.textContent = "No new per-output history yet. Existing aggregate use counts are preserved.";
    history.append(historyList);
    info.append(actions, stats, triggers, history); body.append(media, info); card.append(body);
}

function widget(node, name) { return node?.widgets?.find(item => item.name === name); }
function setWidget(node, name, value) { const item = widget(node, name); if (!item) return false; item.value = value; try { item.callback?.(value); } catch (error) {} node.setDirtyCanvas?.(true, true); return true; }
function findLoader() { const nodes = app.graph?._nodes || []; return LOADER_TYPES.map(type => nodes.find(node => node.type === type)).find(Boolean); }
function findOutputs() { return (app.graph?._nodes || []).filter(node => node.type === OUTPUT_TYPE); }
function widgetConnected(node, name) { const input = node?.inputs?.find(item => item.widget?.name === name || item.name === name); return input?.link != null || (Array.isArray(input?.links) && input.links.length > 0); }
function activeLoaderLora() { return String(widget(findLoader(), "main_lora")?.value || "").trim(); }
function normalizedLoraPath(value) { return String(value || "").replace(/&(?:amp;)*#x2f;/gi, "/").replaceAll("\\", "/").replace(/^\/+/, "").toLocaleLowerCase(); }
function loaderFolderForLora(value) {
    const clean = String(value || "").replace(/&(?:amp;)*#x2f;/gi, "/").replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
    const slash = clean.lastIndexOf("/");
    return slash >= 0 ? clean.slice(0, slash) : "[LoRA root only]";
}
function civitaiPage(detail) {
    const remote = detail?.remote_metadata || {};
    if (remote.model_page) return String(remote.model_page);
    const modelId = String(remote.model_id || detail?.civitai_model_id || "").trim();
    const versionId = String(remote.version_id || detail?.civitai_version_id || "").trim();
    if (!modelId) return "";
    return `https://civitai.com/models/${encodeURIComponent(modelId)}${versionId ? `?modelVersionId=${encodeURIComponent(versionId)}` : ""}`;
}

async function loadIntoLoader(lora, focus = true, knownLoras = null) {
    const loader = findLoader();
    if (!loader) throw new Error("Add a Loader Core to the current canvas first.");
    if (!lora) throw new Error("This catalog entry is no longer inside a configured LoRA folder.");
    const liveLoras = knownLoras || await request("/lora-files");
    const canonical = liveLoras.find(value => normalizedLoraPath(value) === normalizedLoraPath(lora));
    if (!canonical) throw new Error("This LoRA is not present in ComfyUI's current live LoRA list. Rescan LoRA folders and try again.");
    setWidget(loader, "main_enabled", true);
    setWidget(loader, "control_after_generate", "fixed");
    setWidget(loader, "folder_name", loaderFolderForLora(canonical));
    setWidget(loader, "main_lora", canonical);
    if (focus) { app.canvas?.selectNode?.(loader); app.canvas?.centerOnNode?.(loader); }
}

async function submitLoraToQueue(asset, button = null) {
    if (typeof app.queuePrompt !== "function") throw new Error("This ComfyUI build does not expose workflow queueing.");
    const loader = findLoader(); if (!loader) throw new Error("Add a Loader Core to the current canvas first.");
    const originals = captureNodeValues(loader, ["main_enabled", "folder_name", "main_lora", "control_after_generate"]);
    try {
        if (button) { button.disabled = true; button.textContent = "QUEUING…"; }
        const liveLoras = await request("/lora-files");
        await loadIntoLoader(asset.relative_lora, false, liveLoras);
        await Promise.resolve(app.queuePrompt(0, 1));
        if (button) { button.textContent = "QUEUED ✓"; setTimeout(() => { if (button.isConnected) { button.textContent = "QUEUE"; button.disabled = false; } }, 1100); }
        setFeedback(`Queued ${asset.model_name} with the active workflow.`, "#69e49a");
        return true;
    } finally { restoreNodeValues(originals); }
}

function queueLoraAsset(asset, button) {
    if (loraBatchQueue) { alert("The current LoRA view is already being submitted to the queue."); return; }
    loraCardQueueChain = loraCardQueueChain.catch(() => undefined).then(() => submitLoraToQueue(asset, button)).catch(error => { button.textContent = "QUEUE"; button.disabled = false; alert(error.message || "Could not queue this LoRA."); });
}

function openLoraScopeQueueDialog() {
    const items = visibleAssets().filter(asset => asset.relative_lora);
    if (!items.length) { alert("The current view contains no loadable LoRAs."); return; }
    const modal = document.createElement("div"); modal.className = "so-lib-modal"; const card = document.createElement("section"); card.className = "so-lib-form-card";
    const title = document.createElement("h3"); title.textContent = "QUEUE CURRENT LORA VIEW";
    const copy = document.createElement("p"); copy.textContent = `${items.length.toLocaleString()} LoRA${items.length === 1 ? "" : "s"} from ${currentScopeLabel()} will each be queued once using the workflow's current prompt, dimensions, seed behavior, sampler, and every other active setting.`;
    const shuffle = document.createElement("label"); shuffle.className = "so-lib-toggle so-lib-yearbook-auto"; const check = document.createElement("input"); check.type = "checkbox"; check.checked = false; shuffle.append(check, document.createTextNode("Shuffle queue order"));
    const buttons = document.createElement("div"); buttons.className = "so-lib-form-actions"; const cancel = action("Cancel", "#8c8295"); const start = action(`QUEUE ${items.length.toLocaleString()}`, "#b89aff"); cancel.onclick = () => modal.remove();
    start.onclick = () => { modal.remove(); void queueLoraScope(items, check.checked); }; buttons.append(cancel, start); card.append(title, copy, shuffle, buttons); modal.append(card); document.body.append(modal); modal.onclick = event => { if (event.target === modal) modal.remove(); };
}

async function queueLoraScope(sourceItems, shuffleOrder = false) {
    if (loraBatchQueue) return;
    if (typeof app.queuePrompt !== "function") { alert("This ComfyUI build does not expose workflow queueing."); return; }
    const loader = findLoader(); if (!loader) { alert("Add a Loader Core to the current canvas first."); return; }
    const run = { stopped: false, queued: 0, skipped: 0, total: sourceItems.length }; loraBatchQueue = run; renderTools();
    const originals = captureNodeValues(loader, ["main_enabled", "folder_name", "main_lora", "control_after_generate"]);
    try {
        const liveLoras = await request("/lora-files"); const items = shuffleOrder ? shuffled(sourceItems) : [...sourceItems];
        for (let index = 0; index < items.length && !run.stopped; index += 1) {
            const asset = items[index]; setFeedback(`QUEUEING ${index + 1}/${items.length} · ${asset.model_name}`, "#b89aff");
            try { await loadIntoLoader(asset.relative_lora, false, liveLoras); await Promise.resolve(app.queuePrompt(0, 1)); run.queued += 1; }
            catch (error) { run.skipped += 1; console.warn("[Sick Ollie LoRA Library] Queue submission skipped", asset.relative_lora, error); }
        }
        setFeedback(`${run.stopped ? "LoRA queue submission stopped" : "LoRA view queued"} · ${run.queued} added${run.skipped ? ` · ${run.skipped} skipped` : ""}.`, run.skipped ? "#f4ec51" : "#69e49a");
    } catch (error) { alert(error.message || "Could not queue this LoRA view."); }
    finally { restoreNodeValues(originals); loraBatchQueue = null; renderTools(); }
}

function captureNodeValues(node, names) { return names.map(name => ({ node, name, value: widget(node, name)?.value })).filter(item => widget(node, item.name)); }
function restoreNodeValues(values) { for (const item of values || []) setWidget(item.node, item.name, item.value); }

function clearYearbookTimers(run) {
    for (const timer of run?.timers || []) clearTimeout(timer);
    if (run?.timers) run.timers.clear();
}

function scheduleYearbook(run, callback, delay) {
    if (!run || run.stopped || yearbook !== run) return null;
    const timer = setTimeout(() => {
        run.timers?.delete(timer);
        if (!run.stopped && yearbook === run) callback();
    }, delay);
    run.timers?.add(timer);
    return timer;
}

async function interruptYearbookExecution(run, force = false) {
    if (!run || (run.interruptRequested && !force)) return;
    run.interruptRequested = true;
    try {
        if (typeof api?.interrupt === "function") await api.interrupt();
        else await fetch("/interrupt", { method: "POST" });
    } catch (error) {
        console.warn("[Sick Ollie Yearbook] Could not interrupt current execution", error);
    }
}

function restoreYearbookValues(run) {
    if (!run || run.restored) return;
    run.restored = true;
    restoreNodeValues(run.originals);
}

function stopYearbook(completed = false) {
    if (!yearbook) return;
    const previous = yearbook;
    previous.completed = Boolean(completed);
    previous.stopped = true;
    clearYearbookTimers(previous);
    yearbook = null;
    window.__soYearbookRunActive = false;

    const executionWasLive = Boolean(previous.executionObserved || app.runningNodeId != null);
    console.info("[Sick Ollie Yearbook] Stop requested", {
        executionObserved: previous.executionObserved,
        runningNodeId: app.runningNodeId ?? null,
        activeElement: document.activeElement?.tagName || null,
    });
    recoverTextInputFocus();
    if (!completed && previous.queueStarted) void interruptYearbookExecution(previous);

    const restore = () => restoreYearbookValues(previous);
    // Once the backend has begun executing the Yearbook prompt, serialization is
    // already safely behind us. Restore immediately instead of tying UI recovery
    // to app.queuePrompt() finishing its unrelated frontend housekeeping.
    if (completed || executionWasLive || !previous.queuePromise) restore();
    else Promise.resolve(previous.queuePromise).then(restore, restore);
    const button = root?.querySelector("[data-yearbook]"); if (button) { button.textContent = "Yearbook run"; button.classList.remove("active"); }
    const theaterButton = root?.querySelector("[data-yearbook-theater]"); if (theaterButton) theaterButton.hidden = true;
    updateYearbookTheater(previous);
    setFeedback(completed ? `Yearbook complete · ${previous.captured} captured${previous.skipped ? ` · ${previous.skipped} skipped` : ""}.` : `Yearbook stopped · ${previous.captured} captured · ${previous.skipped} skipped.`, completed && previous.skipped === 0 ? "#69e49a" : "#f4ec51");
    const field = root?.querySelector("[data-yearbook-progress]"); if (field) { field.hidden = false; field.style.setProperty("--progress", `${Math.min(100, Math.round(previous.index / previous.items.length * 100))}%`); field.textContent = completed ? `YEARBOOK COMPLETE · ${previous.captured} captured · ${previous.skipped} skipped` : `YEARBOOK STOPPED · ${previous.captured} captured · ${previous.skipped} skipped`; }
    if (completed) refreshCatalogAfterYearbook();
}

function applyYearbookRunSettings(run) {
    if (!run) return;
    setWidget(run.loader, "main_strength", run.strength);
    setWidget(run.generation, "resolution_mode", "custom");
    setWidget(run.generation, "custom_width", run.width);
    setWidget(run.generation, "custom_height", run.height);
    setWidget(run.generation, "seed_value", run.seed);
    for (const output of run.outputs || []) setWidget(output, "output_root", LORA_YEARBOOK_OUTPUT_ROOT);
}

async function yearbookComfyQueueState() {
    try {
        const response = await fetch(api.apiURL("/queue"), { cache: "no-store" });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload?.error || `HTTP ${response.status}`);
        const running = Array.isArray(payload?.queue_running) ? payload.queue_running.length : 0;
        const pending = Array.isArray(payload?.queue_pending) ? payload.queue_pending.length : 0;
        return { ok: true, running, pending, total: running + pending, idle: running + pending === 0 };
    } catch (error) {
        console.warn("[Sick Ollie Yearbook] Could not read ComfyUI queue state", error);
        return { ok: false, running: 0, pending: 0, total: 0, idle: false, error };
    }
}

function setYearbookCurrent() {
    const run = yearbook;
    if (!run || run.stopped) return;
    const item = run.items[run.index];
    if (!item) { stopYearbook(true); return; }
    const available = Array.isArray(run.liveLoras) ? run.liveLoras.map(String) : [];
    const canonicalLora = available.find(value => normalizedLoraPath(value) === normalizedLoraPath(item.relative_lora));
    if (!canonicalLora) {
        console.warn("[Sick Ollie Yearbook] Catalog path was not present in ComfyUI's live LoRA list", item.relative_lora);
        run.skipped += 1;
        run.index += 1;
        updateYearbookProgress(`YEARBOOK · skipped path absent from Loader Core: ${item.relative_lora}`);
        scheduleYearbook(run, setYearbookCurrent, 0);
        return;
    }
    const loraPath = canonicalLora;
    updateYearbookProgress();
    scheduleYearbook(run, () => {
        setWidget(run.loader, "main_lora", loraPath);
        applyYearbookRunSettings(run);
        const strength = widget(run.loader, "main_strength")?.value;
        console.info(`[Sick Ollie Yearbook] Prepared ${run.index + 1}/${run.items.length}`, { lora: loraPath, strength });
        setFeedback(`Yearbook ${run.index + 1}/${run.items.length} · ${item.model_name}${strength !== undefined ? ` · strength ${strength}` : ""}`, "#48e8ee");
        if (!run.autoQueue) return;
        scheduleYearbook(run, async () => {
            if (typeof app.queuePrompt !== "function") {
                updateYearbookProgress("YEARBOOK ERROR · This ComfyUI build does not expose automatic queueing.");
                stopYearbook(false);
                return;
            }
            const queueState = await yearbookComfyQueueState();
            if (!run || run.stopped || yearbook !== run) return;
            if (!queueState.idle) {
                run.waitingForQueue = true;
                run.queueStarted = false;
                const queueCopy = queueState.ok
                    ? `${queueState.running ? `${queueState.running} running` : ""}${queueState.running && queueState.pending ? " · " : ""}${queueState.pending ? `${queueState.pending} pending` : ""}`
                    : "queue status unavailable";
                updateYearbookProgress(`YEARBOOK · WAITING FOR COMFYUI QUEUE · ${queueCopy}`);
                setFeedback("Yearbook is waiting for the existing ComfyUI queue to clear before it claims a thumbnail.", "#f4ec51");
                scheduleYearbook(run, setYearbookCurrent, queueState.ok ? 900 : 1400);
                return;
            }
            run.waitingForQueue = false;
            console.info("[Sick Ollie Yearbook] Queueing prompt");
            run.queueStarted = true;
            run.executionObserved = false;
            let queued;
            try { queued = app.queuePrompt(0, 1); }
            catch (error) { run.queueStarted = false; updateYearbookProgress(`YEARBOOK ERROR · ${error.message}`); stopYearbook(false); return; }
            run.queuePromise = Promise.resolve(queued);
            run.queuePromise.then(
                () => { if (run.stopped) void interruptYearbookExecution(run, true); },
                error => { if (!run.stopped && yearbook === run) { run.queueStarted = false; updateYearbookProgress(`YEARBOOK ERROR · ${error.message}`); stopYearbook(false); } },
            );
        }, 140);
    }, 120);
}

function shuffled(values) {
    const result = [...values];
    for (let index = result.length - 1; index > 0; index--) { const other = Math.floor(Math.random() * (index + 1)); [result[index], result[other]] = [result[other], result[index]]; }
    return result;
}

function yearbookEpochNumber(asset) {
    const rawEpoch = asset?.epoch;
    const stored = rawEpoch === null || rawEpoch === undefined || rawEpoch === "" ? NaN : Number(rawEpoch);
    if (Number.isInteger(stored) && stored >= 0) return stored;
    const filename = String(asset?.relative_lora || asset?.model_name || "").replaceAll("\\", "/").split("/").pop()?.replace(/\.[^.]+$/, "") || "";
    const explicit = filename.match(/(?:^|[_\-\s])(?:epoch|ep)[_\-\s]?(\d+)(?=$|[_\-\s.])/i);
    if (explicit) return Number(explicit[1]);
    const checkpoint = filename.match(/(?:^|[_\-\s])(\d{3,})(?=$|[_\-\s.])/);
    return checkpoint ? Number(checkpoint[1]) : null;
}

function yearbookIncrementalOrder(values) {
    return [...values].sort((a, b) => {
        const aEpoch = yearbookEpochNumber(a); const bEpoch = yearbookEpochNumber(b);
        if (aEpoch != null && bEpoch != null && aEpoch !== bEpoch) return aEpoch - bEpoch;
        if (aEpoch != null && bEpoch == null) return -1;
        if (aEpoch == null && bEpoch != null) return 1;
        const aPath = String(a?.relative_lora || a?.model_name || "");
        const bPath = String(b?.relative_lora || b?.model_name || "");
        return aPath.localeCompare(bPath, undefined, { sensitivity: "base", numeric: true });
    });
}

function orderedYearbookItems(values, orderMode) {
    if (orderMode === "epoch_ascending") return yearbookIncrementalOrder(values);
    if (orderMode === "current_view") return [...values];
    return shuffled(values);
}

function openYearbookDialog() {
    if (!yearbook && window.__soCreativeLibraryRunActive) { alert("Stop the active Creative Library Catalog Run before starting Yearbook."); return; }
    // The active button is already explicitly labelled “Stop yearbook”. Keep the
    // cancellation path inside our own UI instead of introducing a native modal.
    if (yearbook) { stopYearbook(false); return; }
    const visible = visibleAssets().filter(asset => asset.relative_lora);
    if (!visible.length) { alert("The current filters contain no loadable LoRAs."); return; }
    const loader = findLoader(); const prompt = (app.graph?._nodes || []).find(node => node.type === PROMPT_TYPE); const generation = (app.graph?._nodes || []).find(node => node.type === GENERATION_TYPE); const outputs = findOutputs();
    if (!loader || !prompt || !generation) { alert("Studio Loader Core, Prompt Core, and Generation Core must be on the current canvas for a yearbook run."); return; }
    if (outputs.some(output => widgetConnected(output, "output_root"))) { alert("Output Core's Output root is connected. Disconnect it before Yearbook so generated files can be routed into the dedicated LoRA Library folder."); return; }
    const modal = document.createElement("div"); modal.className = "so-lib-modal";
    const card = document.createElement("section"); card.className = "so-lib-form-card so-lib-yearbook-card";
    const title = document.createElement("h3"); title.textContent = "YEARBOOK THUMBNAIL RUN";
    const copy = document.createElement("p"); copy.textContent = `${visible.length.toLocaleString()} LoRAs are in the filtered scope. Yearbook uses the comparison settings below and keeps generated files under output/${LORA_YEARBOOK_OUTPUT_ROOT}. Your original Loader, Prompt, Generation, and Output values return when the run ends.`;

    const settingsTitle = document.createElement("div"); settingsTitle.className = "so-lib-form-section-title"; settingsTitle.textContent = "COMPARISON SETTINGS";
    const settings = document.createElement("div"); settings.className = "so-lib-yearbook-settings";

    const strengthField = document.createElement("label"); strengthField.className = "so-lib-yearbook-setting";
    const strengthLabel = document.createElement("span"); strengthLabel.textContent = "LoRA strength";
    const strengthInput = document.createElement("input"); strengthInput.type = "number"; strengthInput.min = "-100"; strengthInput.max = "100"; strengthInput.step = "0.01"; strengthInput.value = String(YEARBOOK_DEFAULT_STRENGTH); strengthInput.className = "so-lib-number-input";
    const strengthHint = document.createElement("small"); strengthHint.textContent = "Applied to every LoRA in this run.";
    strengthField.append(strengthLabel, strengthInput, strengthHint);

    const dimensionsField = document.createElement("div"); dimensionsField.className = "so-lib-yearbook-setting so-lib-yearbook-dimensions";
    const dimensionsLabel = document.createElement("span"); dimensionsLabel.textContent = "Dimensions";
    const dimensionPreset = selectControl(YEARBOOK_DIMENSION_PRESETS.map(([value, label]) => [value, label]), "400x500", () => {});
    dimensionPreset.classList.add("so-lib-yearbook-preset");
    const dimensionsRow = document.createElement("div"); dimensionsRow.className = "so-lib-dimension-row";
    const widthInput = document.createElement("input"); widthInput.type = "number"; widthInput.min = "16"; widthInput.max = "16384"; widthInput.step = "8"; widthInput.value = "400"; widthInput.className = "so-lib-number-input"; widthInput.title = "Width";
    const by = document.createElement("span"); by.textContent = "×";
    const heightInput = document.createElement("input"); heightInput.type = "number"; heightInput.min = "16"; heightInput.max = "16384"; heightInput.step = "8"; heightInput.value = "500"; heightInput.className = "so-lib-number-input"; heightInput.title = "Height";
    dimensionsRow.append(widthInput, by, heightInput);
    const dimensionsHint = document.createElement("small"); dimensionsHint.textContent = "Presets fill the exact width × height. Edit either field for Custom.";
    const applyDimensionPreset = () => {
        const preset = YEARBOOK_DIMENSION_PRESETS.find(([value]) => value === dimensionPreset.value);
        if (!preset || preset[0] === "custom") return;
        widthInput.value = String(preset[2]); heightInput.value = String(preset[3]);
    };
    dimensionPreset.onchange = applyDimensionPreset;
    const markCustom = () => {
        const exact = YEARBOOK_DIMENSION_PRESETS.find(([, , width, height]) => width === Number(widthInput.value) && height === Number(heightInput.value));
        dimensionPreset.value = exact ? exact[0] : "custom";
    };
    widthInput.oninput = markCustom; heightInput.oninput = markCustom;
    dimensionsField.append(dimensionsLabel, dimensionPreset, dimensionsRow, dimensionsHint);

    const seedField = document.createElement("label"); seedField.className = "so-lib-yearbook-setting";
    const seedLabel = document.createElement("span"); seedLabel.textContent = "Seed";
    const seedInput = document.createElement("input"); seedInput.type = "number"; seedInput.min = "-1"; seedInput.max = "1125899906842624"; seedInput.step = "1"; seedInput.value = String(YEARBOOK_DEFAULT_SEED); seedInput.className = "so-lib-number-input so-lib-seed-input";
    const seedHint = document.createElement("small"); seedHint.textContent = "Fixed seed keeps every LoRA directly comparable. −1 = random.";
    seedField.append(seedLabel, seedInput, seedHint);
    settings.append(strengthField, dimensionsField, seedField);

    const promptTitle = document.createElement("div"); promptTitle.className = "so-lib-form-section-title"; promptTitle.textContent = "YEARBOOK PROMPT";
    const textarea = document.createElement("textarea"); textarea.className = "so-lib-textarea"; textarea.value = localStorage.getItem(YEARBOOK_PROMPT_KEY) || DEFAULT_YEARBOOK_PROMPT;

    const modeTitle = document.createElement("div"); modeTitle.className = "so-lib-form-section-title"; modeTitle.textContent = "THUMBNAIL ACTION";
    const modeCounts = Object.fromEntries(["missing", "civitai", "generated", "non_yearbook", "yearbook", "all"].map(mode => [mode, yearbookTargets(visible, mode).length]));
    const modeSelect = selectControl([
        ["missing", `Fill missing thumbnails · ${modeCounts.missing}`],
        ["civitai", `Replace Civitai thumbnails · ${modeCounts.civitai}`],
        ["generated", `Replace generated non-Yearbook thumbnails · ${modeCounts.generated}`],
        ["non_yearbook", `Standardize non-Yearbook thumbnails · ${modeCounts.non_yearbook}`],
        ["yearbook", `Rebuild existing Yearbook thumbnails · ${modeCounts.yearbook}`],
        ["all", `Replace every thumbnail · ${modeCounts.all}`],
    ], "missing", () => {});
    const modeCopy = document.createElement("p"); modeCopy.className = "so-lib-yearbook-note"; modeCopy.textContent = "Standardize non-Yearbook fills missing entries and replaces Civitai, generated, local-preview, and other automatic thumbnails while preserving custom images and existing Yearbook thumbnails.";
    const scopedEpochs = [...new Set(visible.map(yearbookEpochNumber).filter(value => value != null))].sort((a, b) => a - b);
    const incrementalDefault = !collectionScope && folderScope !== ALL_FOLDERS && scopedEpochs.length >= 2;
    const orderTitle = document.createElement("div"); orderTitle.className = "so-lib-form-section-title"; orderTitle.textContent = "RUN ORDER";
    const epochRange = scopedEpochs.length ? ` · ${scopedEpochs[0]} → ${scopedEpochs.at(-1)}` : "";
    const orderSelect = selectControl([
        ["epoch_ascending", `Incremental epoch/checkpoint · low → high${epochRange}`],
        ["current_view", "Current filtered view order"],
        ["shuffle", "Shuffle"],
    ], incrementalDefault ? "epoch_ascending" : "shuffle", () => {});
    const orderCopy = document.createElement("p"); orderCopy.className = "so-lib-yearbook-note"; orderCopy.textContent = incrementalDefault
        ? `This folder contains ${scopedEpochs.length} numbered epochs/checkpoints, so Yearbook will start at the lowest and work upward.`
        : "Incremental order reads explicit epoch/ep numbers and common zero-padded checkpoint suffixes. Unnumbered files follow afterward in natural filename order.";
    const auto = document.createElement("label"); auto.className = "so-lib-toggle so-lib-yearbook-auto"; const autoCheck = document.createElement("input"); autoCheck.type = "checkbox"; autoCheck.checked = true; auto.append(autoCheck, document.createTextNode("Queue each next generation automatically"));
    const theaterToggle = document.createElement("label"); theaterToggle.className = "so-lib-toggle so-lib-yearbook-auto"; const theaterCheck = document.createElement("input"); theaterCheck.type = "checkbox"; theaterCheck.checked = yearbookTheaterEnabledByDefault(); theaterToggle.append(theaterCheck, document.createTextNode("Open Theater Mode · Live"));
    const buttons = document.createElement("div"); buttons.className = "so-lib-form-actions"; const cancel = action("Cancel", "#8c8295"); const start = action("Start shuffled run", "#f4ec51");
    const updateStartLabel = () => { start.textContent = orderSelect.value === "epoch_ascending" ? "Start incremental run" : orderSelect.value === "current_view" ? "Start ordered run" : "Start shuffled run"; };
    orderSelect.onchange = updateStartLabel; updateStartLabel();
    const closeModal = () => { releaseFocusInside(modal); modal.remove(); };
    cancel.onclick = closeModal; start.onclick = async () => {
        const targetMode = modeSelect.value;
        const items = yearbookTargets(visible, targetMode);
        if (!items.length) { alert("No LoRAs in this filtered scope match the selected Yearbook target."); return; }
        const promptText = textarea.value.trim(); if (!promptText) { alert("Enter the prompt to use for the yearbook run."); return; }
        const strength = Number(strengthInput.value);
        const width = Math.round(Number(widthInput.value));
        const height = Math.round(Number(heightInput.value));
        const seed = Math.trunc(Number(seedInput.value));
        if (!Number.isFinite(strength) || strength < -100 || strength > 100) { alert("LoRA strength must be a number from -100 to 100."); return; }
        if (!Number.isFinite(width) || width < 16 || width > 16384 || !Number.isFinite(height) || height < 16 || height > 16384) { alert("Yearbook width and height must each be between 16 and 16384 pixels."); return; }
        if (!Number.isFinite(seed) || seed < -1 || seed > 1125899906842624) { alert("Seed must be -1 for random or a whole number from 0 to 1125899906842624."); return; }
        start.disabled = true; start.textContent = "Reading live LoRA list…";
        let liveLoras;
        try { liveLoras = await request("/lora-files"); }
        catch (error) { alert(`Could not read ComfyUI's live LoRA list: ${error.message}`); start.disabled = false; updateStartLabel(); return; }
        localStorage.setItem(YEARBOOK_PROMPT_KEY, promptText);
        localStorage.setItem(YEARBOOK_THEATER_ENABLED_KEY, theaterCheck.checked ? "true" : "false");
        const originals = [
            ...captureNodeValues(loader, ["main_enabled", "main_lora", "main_strength", "control_after_generate"]),
            ...captureNodeValues(prompt, ["prompt_source", "manual_prompt"]),
            ...captureNodeValues(generation, ["resolution_mode", "custom_width", "custom_height", "aspect_preset", "megapixels", "seed_value"]),
            ...outputs.flatMap(output => captureNodeValues(output, ["output_root"])),
        ];
        setWidget(loader, "main_enabled", true); setWidget(loader, "control_after_generate", "fixed");
        setWidget(prompt, "prompt_source", "manual"); setWidget(prompt, "manual_prompt", promptText);
        for (const output of outputs) setWidget(output, "output_root", LORA_YEARBOOK_OUTPUT_ROOT);
        const orderMode = orderSelect.value;
        const run = { runId: ++yearbookRunSerial, items: orderedYearbookItems(items, orderMode), liveLoras, index: 0, captured: 0, skipped: 0, replace: targetMode !== "missing", targetMode, orderMode, autoQueue: autoCheck.checked, theaterEnabled: theaterCheck.checked, theater: null, completed: false, loader, prompt, generation, outputs, strength, width, height, seed, originals, timers: new Set(), stopped: false, restored: false, queuePromise: null, queueStarted: false, waitingForQueue: false, executionObserved: false, interruptRequested: false };
        applyYearbookRunSettings(run);
        yearbook = run;
        window.__soYearbookRunActive = true;
        sortMode = "thumbnail_newest";
        thumbnailFilter = "";
        galleryPage = 0;
        textarea.blur(); closeModal(); const button = root?.querySelector("[data-yearbook]"); if (button) { button.textContent = "Stop yearbook"; button.classList.add("active"); }
        const theaterButton = root?.querySelector("[data-yearbook-theater]"); if (theaterButton) { theaterButton.hidden = !run.theaterEnabled; theaterButton.disabled = false; }
        renderTools(); renderList(); root?.querySelector("[data-list]")?.scrollTo?.({ top: 0 });
        if (run.theaterEnabled) openYearbookTheater(run);
        updateYearbookProgress(); scheduleYearbook(run, setYearbookCurrent, 180);
    };
    buttons.append(cancel, start);
    card.append(title, copy, settingsTitle, settings, promptTitle, textarea, modeTitle, modeSelect, modeCopy, orderTitle, orderSelect, orderCopy, auto, theaterToggle, buttons);
    modal.append(card); document.body.append(modal); isolateTextInput(modal); strengthInput.focus(); strengthInput.select();
}

function catalogMaintenanceScope(scope) {
    if (scope === "all") return [...assets];
    if (scope === "folder") return folderTreeAssets();
    return visibleAssets();
}

function openCatalogTools() {
    if (yearbook || civitaiFilling) { alert("Stop the active Yearbook/Civitai operation before changing catalog storage."); return; }
    const filtered = visibleAssets();
    const folderItems = folderTreeAssets();
    const scopes = [["filtered", `Current filtered results · ${filtered.length}`]];
    if (folderScope !== ALL_FOLDERS) scopes.push(["folder", `Selected folder tree: ${folderScope} · ${folderItems.length}`]);
    scopes.push(["all", "Entire LoRA Library catalog · all records"]);
    const modal = document.createElement("div"); modal.className = "so-lib-modal";
    const card = document.createElement("section"); card.className = "so-lib-form-card";
    const title = document.createElement("h3"); title.textContent = "CATALOG MAINTENANCE";
    const copy = document.createElement("p"); copy.textContent = "Emergency reset tools for the LoRA Library index. LoRA files, adjacent sidecars, Recipe Catalog entries, saved filters, and shared token settings are never deleted.";
    const scopeSelect = selectControl(scopes, filtered.length ? "filtered" : (folderScope !== ALL_FOLDERS && folderItems.length ? "folder" : "all"), () => {});
    const note = document.createElement("p"); note.textContent = "Clear thumbnails removes only compact cached WebPs. Purge + rebuild erases Library review state, usage history, trigger cache, Civitai metadata, thumbnail records, and relocation history for the chosen LoRAs, then rescans the real files from disk.";
    const buttons = document.createElement("div"); buttons.className = "so-lib-form-actions";
    const cancel = action("Cancel", "#8c8295");
    const clear = action("Clear thumbnails", "#9c62ff");
    const purge = action("Purge + rebuild", "#ff3eaf");
    const closeModal = () => { releaseFocusInside(modal); modal.remove(); };
    cancel.onclick = closeModal;
    clear.onclick = async () => {
        const scope = scopeSelect.value; const selected = catalogMaintenanceScope(scope).filter(asset => asset.asset_id);
        if (scope !== "all" && !selected.length) { alert("That scope contains no catalog entries."); return; }
        const clearLabel = scope === "all" ? "all cached LoRA thumbnails" : `${selected.length.toLocaleString()} cached LoRA thumbnail${selected.length === 1 ? "" : "s"}`;
        if (!confirm(`Clear ${clearLabel}? Ratings, usage history, Civitai metadata, and LoRA files remain untouched.`)) return;
        clear.disabled = true; purge.disabled = true;
        try {
            const result = await request("/maintenance", { method: "POST", body: { action: "clear_thumbnails", asset_ids: selected.map(asset => asset.asset_id), all_assets: scope === "all" } });
            closeModal(); await load(); setFeedback(`Thumbnail cache cleared · ${result.cleared.toLocaleString()} record${result.cleared === 1 ? "" : "s"} · ${result.files_deleted.toLocaleString()} file${result.files_deleted === 1 ? "" : "s"} removed.`, "#9c62ff");
        } catch (error) { alert(error.message); clear.disabled = false; purge.disabled = false; }
    };
    purge.onclick = async () => {
        const scope = scopeSelect.value; const selected = catalogMaintenanceScope(scope).filter(asset => asset.asset_id);
        if (scope !== "all" && !selected.length) { alert("That scope contains no catalog entries."); return; }
        const label = scope === "all" ? "the ENTIRE LoRA Library catalog, including stale records" : `${selected.length.toLocaleString()} LoRA catalog entr${selected.length === 1 ? "y" : "ies"}`;
        if (!confirm(`Purge + rebuild ${label}?\n\nThis resets Library ratings/status, tested/use history, trigger cache, Civitai metadata, cached thumbnails, and relocation history in this scope. The actual LoRA files, sidecars, Recipe Catalog, saved filters, and shared token settings are untouched.`)) return;
        clear.disabled = true; purge.disabled = true; purge.textContent = "Purging + rescanning…";
        try {
            const result = await request("/maintenance", { method: "POST", body: { action: "purge_rebuild", asset_ids: selected.map(asset => asset.asset_id), all_assets: scope === "all" } });
            closeModal(); await load(); setFeedback(`Catalog rebuilt · ${result.purged.toLocaleString()} purged · ${result.scanned.toLocaleString()} LoRAs rescanned · ${result.files_deleted.toLocaleString()} cached thumbnail${result.files_deleted === 1 ? "" : "s"} removed.`, "#69e49a");
        } catch (error) { alert(error.message); clear.disabled = false; purge.disabled = false; purge.textContent = "Purge + rebuild"; }
    };
    buttons.append(cancel, clear, purge); card.append(title, copy, scopeSelect, note, buttons); modal.append(card); document.body.append(modal); isolateTextInput(modal); modal.onclick = event => { if (event.target === modal) closeModal(); };
}

async function fillCivitai() {
    if (civitaiFilling) { civitaiFilling = false; setFeedback("Stopping Civitai fill after the current lookup…", "#f4ec51"); return; }
    const queue = visibleAssets().filter(asset => !hasRenderableThumbnail(asset));
    if (!queue.length) { setFeedback("Every visible entry already has a renderable local thumbnail."); return; }
    if (!confirm(`Create compact local Civitai thumbnails for ${queue.length.toLocaleString()} visible LoRA${queue.length === 1 ? "" : "s"}? Each image is downloaded once, converted to a 3:4 WebP, and overwrites any earlier cached Civitai thumbnail. Sidecars are used first; missing sidecars require reading each LoRA once for its SHA-256.`)) return;
    civitaiFilling = true; const button = root?.querySelector("[data-civitai-fill]"); if (button) button.textContent = "Stop Civitai fill";
    let found = 0; const failures = [];
    for (let index = 0; index < queue.length && civitaiFilling; index++) {
        const asset = queue[index]; setFeedback(`Civitai ${index + 1}/${queue.length} · ${asset.model_name}`, "#9c62ff");
        try {
            let images = asset.civitai_preview ? [asset.civitai_preview] : [];
            if (!images.length) { const result = await request(`/civitai/${encodeURIComponent(asset.asset_id)}`, { method: "POST", body: {} }); images = result.metadata?.images || []; }
            if (images.length) { await request(`/thumbnail/cache-civitai/${encodeURIComponent(asset.asset_id)}`, { method: "POST", body: { url: images[0] } }); found++; }
        }
        catch (error) { failures.push(`${asset.model_name}: ${error.message || error}`); }
    }
    civitaiFilling = false; if (button) button.textContent = "Fill from Civitai"; await load();
    if (failures.length) console.warn("[Sick Ollie LoRA Library] Civitai thumbnail failures", failures);
    setFeedback(`Civitai fill finished · ${found} compact local thumbnail${found === 1 ? "" : "s"} cached${failures.length ? ` · ${failures.length} failed (see console)` : ""}.`, failures.length ? "#f4ec51" : "#69e49a");
}

async function savePreviewThumbnail(image, { assetId = "", lora = "", replace = false, source = "generated:preview" } = {}) {
    return request("/thumbnail/from-preview", { method: "POST", body: { asset_id: assetId, lora, image, replace, source } });
}

function previewKey(image) { return `${image?.type || "temp"}/${image?.subfolder || ""}/${image?.filename || ""}`; }

async function handlePreviewExecuted(event) {
    const image = event?.detail?.previewData; const key = previewKey(image);
    const now = Date.now();
    if (!image?.filename || !key || (key === lastPreviewKey && now - lastPreviewAt < 800)) return;
    lastPreviewKey = key; lastPreviewAt = now;
    if (yearbook) {
        if (yearbook.autoQueue && (!yearbook.queueStarted || yearbook.waitingForQueue)) return;
        const item = yearbook.items[yearbook.index]; if (!item) return;
        try {
            const result = await savePreviewThumbnail(image, { assetId: item.asset_id, replace: yearbook.replace, source: "generated:yearbook" });
            if (!result.skipped) updateCachedThumbnail(item.asset_id, result.thumbnail);
            yearbook.captured += 1;
            appendYearbookTheaterEntry(yearbook, item, result.thumbnail);
            yearbook.queueStarted = false;
            yearbook.queuePromise = null;
            yearbook.executionObserved = false;
            yearbook.index += 1; setYearbookCurrent();
        } catch (error) { updateYearbookProgress(`YEARBOOK ERROR · ${item.model_name}: ${error.message}`); alert(`Yearbook thumbnail failed for ${item.model_name}: ${error.message}`); stopYearbook(false); }
        return;
    }
    if (window.__soCreativeLibraryRunActive) return;
    if (!autoFirstEnabled()) return;
    const lora = activeLoaderLora(); if (!lora || lora === "[None]") return;
    try { const result = await savePreviewThumbnail(image, { lora, replace: false, source: "generated:auto-first" }); if (!result.skipped) { updateCachedThumbnail(result.asset_id, result.thumbnail); setFeedback(`Captured the first generated thumbnail for ${lora}.`); } }
    catch (error) { console.warn("[Sick Ollie LoRA Library] Auto thumbnail capture skipped", error); }
}

async function handleManualThumbnail(event) {
    const image = event?.detail?.previewData; const lora = activeLoaderLora();
    if (!image?.filename) { alert("Preview Core does not have a current image yet."); return; }
    if (!lora || lora === "[None]") { alert("Select an active main LoRA in Loader Core first."); return; }
    try { await savePreviewThumbnail(image, { lora, replace: true, source: "generated:manual-preview" }); await load(); setFeedback(`Set the current Preview image as ${lora}'s default thumbnail.`); }
    catch (error) { alert(error.message || "Could not set the LoRA thumbnail."); }
}

function updateScanButton() {
    const scan = root?.querySelector("[data-scan-folders]"); if (!scan) return;
    const inCollection = Boolean(collectionScope);
    scan.disabled = inCollection;
    scan.textContent = inCollection ? "Scan unavailable in collection" : folderScope === ALL_FOLDERS ? "Scan LoRA folders" : "Scan current folder";
    scan.title = inCollection ? "Choose a physical folder in the sidebar before scanning" : folderScope === ALL_FOLDERS ? "Scan every configured LoRA root" : `Scan ${folderScope} and its nested folders only`;
}

async function scanCurrentFolder(button) {
    if (collectionScope) return;
    const folder = folderScope === ALL_FOLDERS ? "" : folderScope;
    button.disabled = true; button.textContent = "Scanning…";
    try {
        const result = await request("/scan", { method: "POST", body: { folder } }); await load();
        setFeedback(`${folder ? `Scanned ${folder}` : "Scanned all LoRA folders"} · ${result.scanned} LoRAs · ${result.thumbnails} local thumbnails · ${result.sidecars} Civitai sidecars.`);
    } catch (error) { setFeedback(error.message, "#ff78bd"); }
    finally { updateScanButton(); }
}

function closeReview() {
    civitaiFilling = false;
    const activeYearbook = yearbook;
    if (yearbook) stopYearbook(false);
    if (activeYearbook) closeYearbookTheater(activeYearbook);
    for (const modal of document.querySelectorAll(".so-lib-modal")) {
        releaseFocusInside(modal);
        modal.remove();
    }
    releaseFocusInside(root);
    root?.remove();
    root = null;
    clearLoraSelection(true);
}

function requestedFolderScope(options) {
    const raw = typeof options === "string" ? options : options?.folder;
    const normalized = String(raw || "").replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
    return normalized || ALL_FOLDERS;
}

async function openReview(options = null) {
    const requestedCollection = typeof options === "object" && options
        ? String(options.collection || options.collection_id || "").trim()
        : "";
    const hasCollectionRequest = Boolean(requestedCollection);
    const hasFolderRequest = typeof options === "string" || Boolean(options && Object.prototype.hasOwnProperty.call(options, "folder"));
    if (hasCollectionRequest) {
        collectionScope = requestedCollection;
        folderScope = ALL_FOLDERS;
        epochFilter = "";
        statusFilter = String(options?.status || "");
        thumbnailFilter = "";
        galleryPage = 0;
    } else if (hasFolderRequest) {
        collectionScope = "";
        folderScope = requestedFolderScope(options);
        epochFilter = "";
        statusFilter = String(options?.status || "");
        thumbnailFilter = "";
        galleryPage = 0;
    }
    const styles = ensureStyle();
    if (root) {
        root.querySelector(".so-lib-shell")?.focus();
        try { await load(); } catch (error) { setFeedback(error.message, "#ff78bd"); }
        return;
    }
    root = document.createElement("div"); root.className = "so-lib-overlay"; isolateTextInput(root);
    Object.assign(root.style, { position: "fixed", inset: "0", zIndex: "100020", display: "grid", placeItems: "center", padding: "16px", background: "rgba(5,3,8,.94)" });
    const panel = document.createElement("section"); panel.className = "so-lib-shell"; panel.tabIndex = -1; panel.style.setProperty("--so-lib-bg", `url(${LIBRARY_BACKGROUND_URL})`);
    Object.assign(panel.style, { boxSizing: "border-box", width: "min(2560px,calc(100vw - 32px))", height: "min(1800px,calc(100vh - 32px))", display: "grid", gridTemplateRows: "auto auto minmax(0,1fr)", overflow: "hidden", border: "1px solid rgba(255,62,175,.42)", borderRadius: "22px", background: "#0d0a12" });
    const header = document.createElement("header"); header.className = "so-lib-header";
    const title = document.createElement("img"); title.className = "so-lib-title-image"; title.src = LIBRARY_HEADER_URL; title.alt = "Sick Ollie LoRA Library"; title.draggable = false;
    const status = document.createElement("span"); status.className = "so-lib-status"; status.dataset.reviewStatus = ""; status.textContent = "Visual catalog, test history, ratings, triggers, and compact thumbnails.";
    const scan = action("Scan LoRA folders", "#ff3eaf"); scan.dataset.scanFolders = ""; scan.onclick = () => void scanCurrentFolder(scan);
    const civitai = action("Fill from Civitai", "#9c62ff"); civitai.dataset.civitaiFill = ""; civitai.onclick = fillCivitai;
    const quarantineRejectedButton = action("Quarantine rejected", "#ff3eaf"); quarantineRejectedButton.onclick = () => quarantineRejected(quarantineRejectedButton);
    const catalogToolsButton = action("Catalog tools", "#9c62ff"); catalogToolsButton.onclick = openCatalogTools;
    const theaterButton = action("THEATER", "#b89aff"); theaterButton.dataset.yearbookTheater = ""; theaterButton.hidden = !(yearbook?.theaterEnabled); theaterButton.onclick = () => { if (!yearbook) return; yearbook.theaterEnabled = true; openYearbookTheater(yearbook); };
    const yearbookButton = action(yearbook ? "Stop yearbook" : "Yearbook run", "#f4ec51"); yearbookButton.dataset.yearbook = ""; if (yearbook) yearbookButton.classList.add("active"); yearbookButton.onclick = openYearbookDialog;
    const x = action("×", "#48e8ee", "so-lib-icon"); x.onclick = closeReview;
    header.append(title, status, scan, civitai, quarantineRejectedButton, catalogToolsButton, theaterButton, yearbookButton, x);
    const progress = document.createElement("div"); progress.className = "so-lib-yearbook-progress"; progress.dataset.yearbookProgress = ""; progress.hidden = true;
    const body = document.createElement("div"); body.className = "so-lib-library-body";
    const sidebar = document.createElement("aside"); sidebar.className = "so-lib-sidebar"; sidebar.dataset.loraSidebar = "";
    const content = document.createElement("main"); content.className = "so-lib-library-content";
    const tools = document.createElement("div"); tools.className = "so-lib-tools"; tools.dataset.tools = "";
    const list = document.createElement("div"); list.className = "so-lib-grid"; list.dataset.list = "";
    const opening = document.createElement("div"); opening.className = "so-lib-empty"; opening.textContent = "Opening LoRA Library…"; Object.assign(opening.style, { padding: "60px 24px", color: "#aaa1b3", textAlign: "center" }); list.append(opening);
    content.append(tools, list); body.append(sidebar, content); panel.append(header, progress, body); root.append(panel); document.body.append(root); updateYearbookProgress(); updateScanButton();
    root.onclick = event => { if (event.target === root) closeReview(); };
    // Paint the shell before stylesheet, filesystem, database, or large-catalog
    // work. Both Loader LIB and Hub opens stay responsive on a cold cache.
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    if (assets.length) { renderSidebar(); renderTools(); renderList(); updateScanButton(); }
    try { await Promise.all([styles, load()]); } catch (error) { setFeedback(error.message, "#ff78bd"); }
}

app.registerExtension({
    name: "SickOllie.SOS.LoRALibrary",
    setup() {
        registerSoloHubItem({ id: "library-review", label: "LoRA Library", description: "Browse thumbnails, triggers, usage, ratings, Civitai showcases, and yearbook runs.", color: "#2cecff", open: openReview });
        window.__soOpenLoRALibrary = options => openReview(options);
        if (!window.__soLoRALibraryOpenListener) {
            window.__soLoRALibraryOpenListener = event => void openReview(event?.detail || null);
            window.addEventListener("sickollie:open-lora-library", window.__soLoRALibraryOpenListener);
        }
        if (window.__soPendingLoRALibraryRequest) {
            const pending = window.__soPendingLoRALibraryRequest;
            delete window.__soPendingLoRALibraryRequest;
            void openReview(pending);
        }
        if (!window.__soLoRALibraryPreviewListener) {
            window.__soLoRALibraryPreviewListener = handlePreviewExecuted;
            window.addEventListener("sickollie:preview-executed", window.__soLoRALibraryPreviewListener);
        }
        if (!window.__soLoRAThumbnailManualListener) {
            window.__soLoRAThumbnailManualListener = handleManualThumbnail;
            window.addEventListener("sickollie:set-lora-thumbnail", window.__soLoRAThumbnailManualListener);
        }
        if (!window.__soLoRALibraryExecutionStartListener) {
            window.__soLoRALibraryExecutionStartListener = () => {
                if (yearbook?.queueStarted && !yearbook.stopped) yearbook.executionObserved = true;
            };
            api.addEventListener("execution_start", window.__soLoRALibraryExecutionStartListener);
            api.addEventListener("executing", window.__soLoRALibraryExecutionStartListener);
        }
    },
    menuCommands: [{ path: ["Sick Ollie"], commands: ["solo.openLoRALibrary"] }],
    commands: [{ id: "solo.openLoRALibrary", label: "Open SOS LoRA Library", function: openReview }],
});

export { openReview, loadIntoLoader };
