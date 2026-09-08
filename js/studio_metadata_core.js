import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { STUDIO_THEME, applyStudioNodeColors, drawStudioSectionFrame } from "./studio_theme.js";

const TARGET = "SOImageMetadataCoreStudio";
const PREVIEW_PROP = "so_metadata_preview_images";
const HIDDEN_FIELDS = [
    "status",
    "final_prompt_display",
    "source_prompt_display",
    "generation_display",
    "models_display",
    "prompt_log_display",
    "outfit_a_display",
    "outfit_b_display",
    "outfit_c_display",
    "scene_display",
    "substitutions_display",
];

const MIN_WIDTH = 1280;
const DEFAULT_WIDTH = 1340;
const MIN_HEIGHT = 1120;
const DEFAULT_HEIGHT = 1340;
const MAX_AUTO_WIDTH = 2320;
const LEFT_MIN = 500;
const LEFT_MAX = 610;
const GAP = 16;
const PAD = 14;
const TOOL_BUTTON_H = 32;
const TOOL_GAP = 7;
const TOOL_HEADER_H = 25;

function widget(node, name) {
    return node.widgets?.find((item) => item.name === name);
}

function unwrap(value) {
    let current = value;
    while (Array.isArray(current) && current.length === 1) current = current[0];
    return current;
}

function normalizePayload(value) {
    let current = unwrap(value);
    if (typeof current === "string") {
        try { current = JSON.parse(current); }
        catch (error) { current = {}; }
    }
    return current && typeof current === "object" ? current : {};
}

function setWidgetText(node, name, value) {
    const target = widget(node, name);
    if (!target) return;
    const text = value == null ? "" : String(value);
    target.value = text;
    if (target.inputEl) target.inputEl.value = text;
}

function hideBackingWidget(target) {
    if (!target) return;
    target.computeSize = () => [0, 0];
    target.hidden = true;
    if (target.inputEl) {
        target.inputEl.style.display = "none";
        target.inputEl.style.height = "0px";
        target.inputEl.style.minHeight = "0px";
        target.inputEl.style.maxHeight = "0px";
    }
}

async function copyText(text) {
    const value = String(text ?? "");
    if (!value.trim()) return false;
    try {
        await navigator.clipboard.writeText(value);
        return true;
    } catch (error) {
        try {
            const input = document.createElement("textarea");
            input.value = value;
            input.style.position = "fixed";
            input.style.opacity = "0";
            document.body.append(input);
            input.select();
            document.execCommand("copy");
            input.remove();
            return true;
        } catch (fallbackError) {
            return false;
        }
    }
}

function imageDataToUrl(data) {
    const filename = encodeURIComponent(data?.filename || "");
    const type = encodeURIComponent(data?.type || "input");
    const subfolder = encodeURIComponent(data?.subfolder || "");
    return api.apiURL(
        `/view?filename=${filename}&type=${type}&subfolder=${subfolder}` +
        `${app.getPreviewFormatParam?.() || ""}${app.getRandParam?.() || ""}`,
    );
}

function cleanImageData(data) {
    if (!data || typeof data !== "object" || !data.filename) return null;
    return {
        filename: String(data.filename),
        type: String(data.type || "input"),
        subfolder: String(data.subfolder || ""),
    };
}

function clearPreview(node) {
    node.__soMetadataPreviewData = [];
    node.__soMetadataPreviewImages = [];
    node.properties = node.properties || {};
    node.properties[PREVIEW_PROP] = [];
    node.images = [];
    node.imgs = [];
    node.imageRects = [];
    node.imageIndex = null;
    node.overIndex = null;
    node.animatedImages = false;
    node.setDirtyCanvas?.(true, true);
}

function loadPreview(node, sourceData, persist = true) {
    const data = (Array.isArray(sourceData) ? sourceData : []).map(cleanImageData).filter(Boolean);
    if (!data.length) {
        clearPreview(node);
        return;
    }

    node.__soMetadataPreviewData = data;
    node.__soMetadataPreviewImages = [];
    if (persist) {
        node.properties = node.properties || {};
        node.properties[PREVIEW_PROP] = data.map((item) => ({ ...item }));
    }

    for (const item of data) {
        const image = new Image();
        image.decoding = "async";
        image.onload = () => {
            autoFitMetadataWidth(node, image.naturalWidth, image.naturalHeight);
            node.setDirtyCanvas?.(true, true);
        };
        image.onerror = () => node.setDirtyCanvas?.(true, true);
        image.src = imageDataToUrl(item);
        node.__soMetadataPreviewImages.push(image);
    }

    node.images = [];
    node.imgs = [];
    node.imageRects = [];
    node.imageIndex = null;
    node.overIndex = null;
    node.animatedImages = false;
    node.setDirtyCanvas?.(true, true);
}

async function fetchUploadedMetadata(imageFile) {
    const value = String(imageFile ?? "").trim();
    if (!value || value === "[None]") return null;
    const response = await fetch(`/sickollie/metadata-core/read?image_file=${encodeURIComponent(value)}`, { method: "GET" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return await response.json();
}

function currentImageToken(node) {
    return String(widget(node, "image_file")?.value || "").trim();
}

function setImageToken(node, value) {
    const imageFile = widget(node, "image_file");
    if (!imageFile) return;
    imageFile.value = value || "[None]";
    if (imageFile.inputEl) imageFile.inputEl.value = imageFile.value;
}

async function clearTempOnServer(token) {
    const value = String(token || "").trim();
    if (!value.startsWith("so-temp::")) return;
    try {
        await fetch("/sickollie/metadata-core/clear-temp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image_file: value }),
        });
    } catch (error) {
        console.warn("[Sick Ollie Image Metadata Core] Could not remove temp image", error);
    }
}

async function clearLoadedImage(node, deleteTemp = false) {
    const previous = currentImageToken(node);
    node.__soMetadataRequest = Symbol("metadata_clear");
    setImageToken(node, "[None]");
    applyPayload(node, {});
    clearPreview(node);
    if (deleteTemp) await clearTempOnServer(previous);
}

async function refreshFromImageFile(node, imageFile) {
    const token = Symbol("metadata_request");
    node.__soMetadataRequest = token;
    const value = String(imageFile ?? "").trim();
    if (!value || value === "[None]") {
        applyPayload(node, {});
        clearPreview(node);
        return;
    }

    try {
        const result = await fetchUploadedMetadata(value);
        if (node.__soMetadataRequest !== token) return;
        applyPayload(node, result?.payload || {});
        loadPreview(node, result?.images || [], true);
    } catch (error) {
        // A temp file may legitimately disappear between Comfy sessions.
        // Clear it quietly instead of leaving a broken saved path behind.
        console.warn("[Sick Ollie Image Metadata Core] Could not preload metadata", error);
        if (String(value).startsWith("so-temp::")) {
            setImageToken(node, "[None]");
            applyPayload(node, {});
            clearPreview(node);
        }
    }
}

async function uploadTempFile(node, file) {
    if (!file) return;
    const lower = String(file.name || "").toLowerCase();
    if (!/\.(png|jpe?g|webp)$/.test(lower)) {
        console.warn("[Sick Ollie Image Metadata Core] Unsupported image type", file.name);
        return;
    }

    const requestToken = Symbol("metadata_upload");
    node.__soMetadataRequest = requestToken;
    const form = new FormData();
    // Keep older temp sources on disk because queued workflows may still
    // reference them after the user moves on to inspect another image.
    form.append("file", file, file.name);

    try {
        const response = await fetch("/sickollie/metadata-core/upload-temp", {
            method: "POST",
            body: form,
        });
        const result = await response.json();
        if (!response.ok || !result?.ok) throw new Error(result?.error || `HTTP ${response.status}`);
        if (node.__soMetadataRequest !== requestToken) return;

        setImageToken(node, result.image_file || "[None]");
        applyPayload(node, result.payload || {});
        loadPreview(node, result.images || [], true);
    } catch (error) {
        console.warn("[Sick Ollie Image Metadata Core] Could not upload temp image", error);
    }
}

function chooseTempFile(node) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp";
    input.style.display = "none";
    input.addEventListener("change", () => {
        const file = input.files?.[0];
        if (file) uploadTempFile(node, file);
        input.remove();
    }, { once: true });
    document.body.appendChild(input);
    input.click();
}

function makeUploadButton(node) {
    if (node.__soUploadButton) return node.__soUploadButton;
    const button = node.addWidget("button", "choose file to upload", null, () => chooseTempFile(node), { serialize: false });
    button.serialize = false;
    button.options = { ...(button.options || {}), serialize: false };
    node.__soUploadButton = button;
    return button;
}

function makeClearButton(node) {
    if (node.__soClearButton) return node.__soClearButton;
    const button = node.addWidget("button", "Clear loaded image", null, () => clearLoadedImage(node, false), { serialize: false });
    button.serialize = false;
    button.options = { ...(button.options || {}), serialize: false };
    node.__soClearButton = button;
    return button;
}

function makeSeedButton(node) {
    if (node.__soSeedButton) return node.__soSeedButton;
    const button = node.addWidget("button", "", null, async () => {
        const seed = String(node.__soMetadataPayload?.seed_text || "").trim();
        if (!seed) return;
        if (await copyText(seed)) {
            const normal = `📋 Copy seed: ${seed}`;
            button.name = "✓ Copied seed";
            node.setDirtyCanvas?.(true, true);
            clearTimeout(button.__soTimer);
            button.__soTimer = setTimeout(() => {
                button.name = normal;
                node.setDirtyCanvas?.(true, true);
            }, 850);
        }
    }, { serialize: false });
    button.serialize = false;
    button.options = { ...(button.options || {}), serialize: false };
    node.__soSeedButton = button;
    return button;
}

function moveWidgetToIndex(node, moving, targetIndex) {
    if (!moving || !node.widgets) return;
    const from = node.widgets.indexOf(moving);
    if (from >= 0) node.widgets.splice(from, 1);
    const bounded = Math.max(0, Math.min(targetIndex, node.widgets.length));
    node.widgets.splice(bounded, 0, moving);
}

function hideActionWidget(target) {
    if (!target) return;
    target.computeSize = () => [0, 0];
    target.hidden = true;
    if (target.inputEl) target.inputEl.style.display = "none";
}

function arrangeTopWidgets(node) {
    const imageFile = widget(node, "image_file");
    const upload = makeUploadButton(node);
    const clear = makeClearButton(node);
    const seed = makeSeedButton(node);

    // All three actions are rendered inside the custom left inspector now.
    // Keep these backing widgets alive for compatibility, but never let the
    // stock Comfy widgets create a second visual toolbar above our UI.
    hideBackingWidget(imageFile);
    moveWidgetToIndex(node, upload, 0);
    moveWidgetToIndex(node, clear, 1);
    moveWidgetToIndex(node, seed, 2);
    hideActionWidget(upload);
    hideActionWidget(clear);
    hideActionWidget(seed);
}

function syncConnectedPromptInputs(node) {
    const graph = app.graph;
    if (!graph) return;
    const values = node.__soLiveOutputs || {};
    for (const outputName of ["final_prompt", "source_prompt"]) {
        const outputIndex = (node.outputs || []).findIndex((slot) => String(slot?.name || slot?.label || "") === outputName);
        if (outputIndex < 0) continue;
        const output = node.outputs?.[outputIndex];
        for (const linkRef of output?.links || []) {
            const link = typeof linkRef === "object" ? linkRef : graph.links?.[linkRef];
            const targetId = link?.target_id ?? link?.targetId;
            const targetSlot = Number(link?.target_slot ?? link?.targetSlot);
            const target = graph.getNodeById?.(targetId);
            if (!target || !Number.isInteger(targetSlot)) continue;
            const input = target.inputs?.[targetSlot];
            const inputName = String(input?.widget?.name ?? input?.name ?? "");
            const targetKinds = [target.type, target.comfyClass].map(value => String(value || ""));
            if (inputName !== "manual_prompt_input" || !targetKinds.some(kind => ["SOPromptLogEngineStudio", "SOPromptLogEngine"].includes(kind))) continue;
            const text = String(values[outputName] ?? "");
            target.properties = target.properties || {};
            // Prompt input is now an explicit Prompt Source. Keep its live value
            // available to Prompt Core without clobbering the user's Manual draft
            // or changing whichever source they deliberately selected.
            target.properties.so_external_manual_prompt_value = text;
            target.setDirtyCanvas?.(true, true);
        }
    }
}

function applyPayload(node, payloadValue) {
    const payload = normalizePayload(payloadValue);
    node.__soMetadataPayload = payload;
    node.properties = node.properties || {};
    node.properties.so_metadata_core_payload = payload;

    setWidgetText(node, "status", payload.status || "");
    setWidgetText(node, "final_prompt_display", payload.final_prompt || "");
    setWidgetText(node, "source_prompt_display", payload.source_prompt || "");
    setWidgetText(node, "generation_display", payload.generation || "");
    setWidgetText(node, "models_display", payload.models || "");
    setWidgetText(node, "prompt_log_display", payload.resolved_inputs || "");

    const seed = makeSeedButton(node);
    const seedText = String(payload.seed_text || "").trim();
    seed.name = seedText ? `📋 Copy seed: ${seedText}` : "";
    hideActionWidget(seed);

    // Expose inspector strings as live frontend values so a connected Prompt
    // Core can mirror final_prompt/source_prompt into its Manual Prompt field
    // immediately, even when the image was loaded from the file inspector.
    node.__soLiveOutputs = {
        ...(node.__soLiveOutputs || {}),
        final_prompt: String(payload.final_prompt || ""),
        source_prompt: String(payload.source_prompt || ""),
        seed: seedText,
    };
    syncConnectedPromptInputs(node);
    ensureMetadataHeight(node);
    node.setDirtyCanvas?.(true, true);
}

function hasWiredImage(node) {
    const input = node.inputs?.find((item) => item.name === "images");
    return input?.link != null;
}

function clearForExecution(node) {
    if (!hasWiredImage(node)) return;
    const previous = currentImageToken(node);
    node.__soMetadataRequest = Symbol("cleared_for_execution");
    setImageToken(node, "[None]");
    applyPayload(node, {});
    clearPreview(node);
    // Fire-and-forget cleanup; execution should never wait on housekeeping.
    clearTempOnServer(previous);
}

function contentTop(node) {
    // Inputs live on the left and outputs on the right, so their socket rows
    // overlap vertically. Treat the bay as the larger *side* instead of
    // stacking every socket into one imaginary column. Also avoid slot.pos:
    // LiteGraph can retain stretched/stale positions after a tall resize,
    // which previously pushed the inspector hundreds of pixels downward and
    // left a huge empty ceiling above the custom UI.
    const inputRows = Math.max(1, (node.inputs || []).length);
    const outputRows = Math.max(1, (node.outputs || []).length);
    const rows = Math.max(inputRows, outputRows);
    const socketBottom = 34 + (rows - 1) * 18;
    return Math.max(190, Math.round(socketBottom + 24));
}

function resolvedLineFromMetadataSection(text) {
    for (const line of String(text || "").split(/\r?\n/)) {
        if (line.startsWith("Resolved line:")) return line.slice("Resolved line:".length).trim();
    }
    return "";
}

function metadataQuickCopyEntries(payload = {}) {
    const direct = payload.copy_values && typeof payload.copy_values === "object" ? payload.copy_values : {};
    return [
        ["outfit_a", "OUTFIT A", payload.outfit_a],
        ["outfit_b", "OUTFIT B", payload.outfit_b],
        ["outfit_c", "OUTFIT C", payload.outfit_c],
        ["scene", "SCENE", payload.scene],
    ].map(([key, label, fallback]) => ({
        key,
        label,
        value: String(direct[key] || resolvedLineFromMetadataSection(fallback) || "").trim(),
    })).filter(entry => entry.value);
}

function inspectorMinimumContentHeight(node) {
    const payload = node.__soMetadataPayload || {};
    const status = Boolean(String(payload.status || "").trim());
    const finalPrompt = Boolean(String(payload.final_prompt || "").trim());
    const sourcePrompt = Boolean(String(payload.source_prompt || "").trim());
    const metadata = Boolean(String(payload.resolved_inputs || "").trim());
    const quickCopies = metadataQuickCopyEntries(payload);
    const buttonH = 30;
    const sectionGap = 10;
    const toolsH = TOOL_HEADER_H + TOOL_BUTTON_H * 3 + TOOL_GAP * 4 + 8;

    let height = toolsH;
    if (status) height += sectionGap + 76;
    if (finalPrompt) height += sectionGap + 220 + 6 + buttonH;
    if (sourcePrompt) height += sectionGap + 175 + 6 + buttonH;
    if (metadata) height += sectionGap + 230 + 6 + buttonH + (quickCopies.length ? 6 + buttonH : 0);
    return Math.max(260, height);
}

function minimumMetadataHeight(node) {
    return Math.max(MIN_HEIGHT, contentTop(node) + inspectorMinimumContentHeight(node) + PAD);
}

function ensureMetadataHeight(node) {
    if (!node?.size) return;
    const minimum = minimumMetadataHeight(node);
    if (Number(node.size[1] || 0) < minimum) node.size[1] = minimum;
}

function autoFitMetadataWidth(node, imageWidth, imageHeight) {
    const iw = Number(imageWidth), ih = Number(imageHeight);
    if (!(iw > 0 && ih > 0) || !node?.size) return;
    const height = Math.max(Number(node.size[1] || DEFAULT_HEIGHT), MIN_HEIGHT);
    const top = contentTop(node);
    const contentH = Math.max(260, height - top - PAD);
    const aspect = iw / ih;
    let target = Math.max(MIN_WIDTH, Number(node.size[0] || DEFAULT_WIDTH));
    for (let i = 0; i < 4; i++) {
        const leftW = Math.max(LEFT_MIN, Math.min(LEFT_MAX, Math.round(target * .36)));
        target = PAD + leftW + GAP + contentH * aspect + PAD;
    }
    target = Math.max(MIN_WIDTH, Math.min(MAX_AUTO_WIDTH, Math.round(target)));
    if (Math.abs(Number(node.size[0] || 0) - target) > 8) node.size[0] = target;
    node.setDirtyCanvas?.(true, true);
}

function columnGeometry(node) {
    const width = node.size?.[0] || MIN_WIDTH;
    const height = node.size?.[1] || MIN_HEIGHT;
    const top = contentTop(node);
    const leftW = Math.max(LEFT_MIN, Math.min(LEFT_MAX, Math.round(width * 0.36)));
    const rightX = PAD + leftW + GAP;
    return {
        top,
        bottom: height - PAD,
        leftX: PAD,
        leftW,
        rightX,
        rightW: Math.max(320, width - rightX - PAD),
        contentH: Math.max(260, height - top - PAD),
    };
}

function roundedRect(ctx, x, y, w, h, r = 8) {
    const radius = Math.max(0, Math.min(r, w / 2, h / 2));
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + w, y, x + w, y + h, radius);
    ctx.arcTo(x + w, y + h, x, y + h, radius);
    ctx.arcTo(x, y + h, x, y, radius);
    ctx.arcTo(x, y, x + w, y, radius);
    ctx.closePath();
}

function wrapLines(ctx, text, maxWidth) {
    const output = [];
    for (const paragraph of String(text || "").split(/\r?\n/)) {
        if (!paragraph.trim()) {
            output.push("");
            continue;
        }
        const words = paragraph.split(/\s+/);
        let line = "";
        for (const word of words) {
            const test = line ? `${line} ${word}` : word;
            if (ctx.measureText(test).width <= maxWidth || !line) {
                line = test;
            } else {
                output.push(line);
                line = word;
            }
        }
        if (line) output.push(line);
    }
    return output;
}

const SO_META_CMYKG = {
    cyan: "#35d7ff",
    magenta: "#ff4ab8",
    yellow: "#f6e65a",
    green: "#6ee7a2",
};

function metadataAccentForTitle(title) {
    const key = String(title || "").toUpperCase();
    if (key.includes("FINAL")) return SO_META_CMYKG.magenta;
    if (key.includes("SOURCE")) return SO_META_CMYKG.yellow;
    if (key.includes("META")) return SO_META_CMYKG.green;
    return SO_META_CMYKG.cyan;
}

function drawTextBox(ctx, rect, title, text) {
    const accent = metadataAccentForTitle(title);
    drawStudioSectionFrame(ctx, rect.x, rect.y, rect.w, rect.h, accent, 8, .52);

    ctx.save();
    ctx.beginPath();
    ctx.rect(rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2);
    ctx.clip();

    ctx.fillStyle = accent;
    ctx.font = "700 12px Segoe UI";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(title, rect.x + 10, rect.y + 8);

    ctx.fillStyle = "#f2f2f2";
    ctx.font = "13px Consolas, monospace";
    const lines = wrapLines(ctx, text, rect.w - 20);
    const lineH = 16;
    const textY = rect.y + 29;
    const maxLines = Math.max(1, Math.floor((rect.h - 38) / lineH));
    const shown = lines.slice(0, maxLines);
    for (let i = 0; i < shown.length; i++) {
        let line = shown[i];
        if (i === maxLines - 1 && lines.length > maxLines && line) line = `${line} …`;
        ctx.fillText(line, rect.x + 10, textY + i * lineH);
    }
    ctx.restore();
}

function metadataPress(node, key) {
    try { navigator.vibrate?.(16); } catch (error) {}
    node.__soMetadataPressedKey = key;
    node.setDirtyCanvas?.(true, true);
    clearTimeout(node.__soMetadataPressTimer);
    node.__soMetadataPressTimer = setTimeout(() => {
        if (node.__soMetadataPressedKey === key) node.__soMetadataPressedKey = "";
        node.setDirtyCanvas?.(true, true);
    }, 115);
}

async function metadataCopy(node, key, text) {
    metadataPress(node, key);
    if (!(await copyText(text))) return false;
    node.__soMetadataFlashKey = key;
    node.setDirtyCanvas?.(true, true);
    clearTimeout(node.__soMetadataFlashTimer);
    node.__soMetadataFlashTimer = setTimeout(() => {
        if (node.__soMetadataFlashKey === key) node.__soMetadataFlashKey = "";
        node.setDirtyCanvas?.(true, true);
    }, 800);
    return true;
}

async function saveLoadedMetadataRecipe(node) {
    const payload = node.__soMetadataPayload || {};
    const metadataJson = String(payload.metadata_json || "").trim();
    if (!metadataJson || !payload.has_metadata) return false;
    metadataPress(node, "recipe");
    node.__soMetadataRecipeBusy = true;
    node.setDirtyCanvas?.(true, true);
    try {
        const preview = cleanImageData(node.__soMetadataPreviewData?.[0]);
        const form = new FormData();
        form.append("metadata_json", metadataJson);
        if (preview) {
            try {
                const imageResponse = await fetch(imageDataToUrl(preview));
                if (imageResponse.ok) {
                    const blob = await imageResponse.blob();
                    form.append("file", blob, preview.filename || "metadata-preview.png");
                }
            } catch (error) {
                console.warn("[Sick Ollie Image Metadata Core] Could not attach Recipe thumbnail", error);
            }
        }
        const response = await fetch("/sickollie/creative-library/import-metadata", {
            method: "POST",
            body: form,
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result?.ok || !result?.saved) {
            throw new Error(result?.error || `HTTP ${response.status}`);
        }
        node.__soMetadataFlashKey = "recipe";
        try { navigator.vibrate?.([18, 35, 18]); } catch (error) {}
        node.setDirtyCanvas?.(true, true);
        clearTimeout(node.__soMetadataFlashTimer);
        node.__soMetadataFlashTimer = setTimeout(() => {
            if (node.__soMetadataFlashKey === "recipe") node.__soMetadataFlashKey = "";
            node.setDirtyCanvas?.(true, true);
        }, 1050);
        window.dispatchEvent(new CustomEvent("sickollie:library-usage-updated", { detail: { source: "metadata-core" } }));
        return true;
    } catch (error) {
        console.warn("[Sick Ollie Image Metadata Core] Could not save loaded image as a Recipe", error);
        alert(error?.message || "Could not save this image as a Recipe.");
        return false;
    } finally {
        node.__soMetadataRecipeBusy = false;
        node.setDirtyCanvas?.(true, true);
    }
}

function drawInspectorButton(ctx, rect, label, accent, enabled = true, pressed = false) {
    const inset = pressed ? 1.5 : 0;
    roundedRect(ctx, rect.x + inset, rect.y + inset, rect.w - inset * 2, rect.h - inset * 2, 7);
    ctx.fillStyle = enabled ? (pressed ? STUDIO_THEME.rowHover : STUDIO_THEME.row) : "rgba(20,18,24,.72)";
    ctx.fill();
    ctx.strokeStyle = enabled ? `${accent}88` : "rgba(255,255,255,.08)";
    ctx.lineWidth = pressed ? 1.6 : 1;
    ctx.stroke();
    ctx.fillStyle = enabled ? "#f4f1f6" : "rgba(255,255,255,.28)";
    ctx.font = "600 12px Segoe UI";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, rect.x + rect.w / 2, rect.y + rect.h / 2 + (pressed ? 1.5 : .5));
}

function drawToolPanel(node, ctx, rect, buttons) {
    drawStudioSectionFrame(ctx, rect.x, rect.y, rect.w, rect.h, SO_META_CMYKG.cyan, 9, .52);
    ctx.fillStyle = SO_META_CMYKG.cyan;
    ctx.font = "700 12px Segoe UI";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText("IMAGE CONTROLS", rect.x + 10, rect.y + TOOL_HEADER_H / 2 + 2);
    const seedText = String(node.__soMetadataPayload?.seed_text || "").trim();
    const flash = node.__soMetadataFlashKey;
    const pressed = node.__soMetadataPressedKey;
    drawInspectorButton(ctx, buttons.upload, "Choose image", SO_META_CMYKG.cyan, true, pressed === "upload");
    drawInspectorButton(ctx, buttons.clear, "Clear image", SO_META_CMYKG.magenta, true, pressed === "clear");
    drawInspectorButton(ctx, buttons.seed, flash === "seed" ? "✓ Seed copied" : (seedText ? `Copy seed · ${seedText}` : "Seed unavailable"), SO_META_CMYKG.yellow, Boolean(seedText), pressed === "seed");
    const recipeReady = Boolean(node.__soMetadataPayload?.has_metadata);
    const recipeLabel = node.__soMetadataRecipeBusy ? "Saving Recipe…" : (flash === "recipe" ? "✓ Recipe saved to Creative Library" : "Save Recipe");
    drawInspectorButton(ctx, buttons.recipe, recipeLabel, SO_META_CMYKG.green, recipeReady && !node.__soMetadataRecipeBusy, pressed === "recipe");
}

function fitMetadataButtonLabel(ctx, text, maxWidth) {
    const value = String(text || "");
    if (ctx.measureText(value).width <= maxWidth) return value;
    const ellipsis = "…";
    let low = 0, high = value.length;
    while (low < high) {
        const mid = Math.ceil((low + high) / 2);
        if (ctx.measureText(value.slice(0, mid) + ellipsis).width <= maxWidth) low = mid;
        else high = mid - 1;
    }
    return value.slice(0, low) + ellipsis;
}

function drawCopyButton(ctx, rect, label, enabled, pressed = false) {
    const inset = pressed ? 1.5 : 0;
    roundedRect(ctx, rect.x + inset, rect.y + inset, rect.w - inset * 2, rect.h - inset * 2, 6);
    ctx.fillStyle = enabled ? (pressed ? STUDIO_THEME.rowHover : STUDIO_THEME.row) : "rgba(20,18,24,.72)";
    ctx.fill();
    const accent = metadataAccentForTitle(label);
    ctx.strokeStyle = enabled ? `${accent}77` : "rgba(255,255,255,.08)";
    ctx.stroke();
    ctx.fillStyle = enabled ? "#f3f3f3" : "rgba(255,255,255,.25)";
    ctx.font = "13px Segoe UI";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(fitMetadataButtonLabel(ctx, label, Math.max(20, rect.w - 12)), rect.x + rect.w / 2, rect.y + rect.h / 2 + 0.5);
}

function drawPreviewPanel(node, ctx, rect) {
    roundedRect(ctx, rect.x, rect.y, rect.w, rect.h, 10);
    ctx.fillStyle = STUDIO_THEME.body;
    ctx.fill();
    const previewGradient = ctx.createLinearGradient(rect.x, rect.y, rect.x + rect.w, rect.y + rect.h);
    previewGradient.addColorStop(0, `${SO_META_CMYKG.cyan}88`);
    previewGradient.addColorStop(.55, `${SO_META_CMYKG.magenta}66`);
    previewGradient.addColorStop(1, `${SO_META_CMYKG.green}66`);
    ctx.strokeStyle = previewGradient;
    ctx.lineWidth = 1.25;
    ctx.stroke();

    const image = node.__soMetadataPreviewImages?.[0];
    if (!image?.complete || !image.naturalWidth || !image.naturalHeight) {
        ctx.fillStyle = "rgba(255,255,255,.30)";
        ctx.font = "14px Segoe UI";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(hasWiredImage(node) ? "Waiting for next image…" : "Load an image to inspect", rect.x + rect.w / 2, rect.y + rect.h / 2);
        return;
    }

    ctx.save();
    roundedRect(ctx, rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2, 9);
    ctx.clip();
    const scale = Math.min(rect.w / image.naturalWidth, rect.h / image.naturalHeight);
    const drawW = image.naturalWidth * scale;
    const drawH = image.naturalHeight * scale;
    const drawX = rect.x + (rect.w - drawW) / 2;
    const drawY = rect.y + (rect.h - drawH) / 2;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(image, drawX, drawY, drawW, drawH);
    ctx.restore();
}

function layoutInspector(node) {
    const g = columnGeometry(node);
    const payload = node.__soMetadataPayload || {};
    const status = String(payload.status || "").trim();
    const finalPrompt = String(payload.final_prompt || "").trim();
    const sourcePrompt = String(payload.source_prompt || "").trim();
    const metadata = String(payload.resolved_inputs || "").trim();
    const quickCopies = metadataQuickCopyEntries(payload);

    const buttonH = 30;
    const sectionGap = 10;
    const toolsH = TOOL_HEADER_H + TOOL_BUTTON_H * 3 + TOOL_GAP * 4 + 8;
    const statusH = status ? 76 : 0;
    const finalH = finalPrompt ? 220 : 0;
    const sourceH = sourcePrompt ? 175 : 0;
    const buttonCount = (finalPrompt ? 1 : 0) + (sourcePrompt ? 1 : 0) + (metadata ? 1 : 0) + (quickCopies.length ? 1 : 0);
    const fixed = toolsH + statusH + finalH + sourceH + buttonCount * buttonH + sectionGap * 8 + (quickCopies.length ? 6 : 0);
    const metaH = metadata ? Math.max(230, g.contentH - fixed) : 0;

    let y = g.top;
    const layout = { buttons: {}, preview: { x: g.rightX, y: g.top, w: g.rightW, h: g.contentH } };
    layout.tools = { x: g.leftX, y, w: g.leftW, h: toolsH };
    const toolInnerX = g.leftX + 8;
    const toolInnerW = g.leftW - 16;
    const half = (toolInnerW - TOOL_GAP) / 2;
    const firstY = y + TOOL_HEADER_H + TOOL_GAP;
    layout.buttons.upload = { x: toolInnerX, y: firstY, w: half, h: TOOL_BUTTON_H };
    layout.buttons.clear = { x: toolInnerX + half + TOOL_GAP, y: firstY, w: half, h: TOOL_BUTTON_H };
    layout.buttons.seed = { x: toolInnerX, y: firstY + TOOL_BUTTON_H + TOOL_GAP, w: toolInnerW, h: TOOL_BUTTON_H };
    layout.buttons.recipe = { x: toolInnerX, y: firstY + (TOOL_BUTTON_H + TOOL_GAP) * 2, w: toolInnerW, h: TOOL_BUTTON_H };
    y += toolsH + sectionGap;
    if (status) {
        layout.status = { x: g.leftX, y, w: g.leftW, h: statusH };
        y += statusH + sectionGap;
    }
    if (finalPrompt) {
        layout.final = { x: g.leftX, y, w: g.leftW, h: finalH };
        y += finalH + 6;
        layout.buttons.final = { x: g.leftX, y, w: g.leftW, h: buttonH };
        y += buttonH + sectionGap;
    }
    if (sourcePrompt) {
        layout.source = { x: g.leftX, y, w: g.leftW, h: sourceH };
        y += sourceH + 6;
        layout.buttons.source = { x: g.leftX, y, w: g.leftW, h: buttonH };
        y += buttonH + sectionGap;
    }
    if (metadata) {
        const afterMetadataH = buttonH + 8 + (quickCopies.length ? buttonH + 6 : 0);
        layout.metadata = { x: g.leftX, y, w: g.leftW, h: Math.max(180, Math.min(metaH, g.bottom - y - afterMetadataH)) };
        y += layout.metadata.h + 6;
        if (quickCopies.length) {
            const copyGap = 5;
            const copyW = (g.leftW - copyGap * (quickCopies.length - 1)) / quickCopies.length;
            layout.quickCopies = quickCopies.map((entry, index) => {
                const rect = { x: g.leftX + index * (copyW + copyGap), y, w: copyW, h: buttonH };
                layout.buttons[`copy_${entry.key}`] = rect;
                return { ...entry, rect };
            });
            y += buttonH + 6;
        }
        layout.buttons.report = { x: g.leftX, y, w: g.leftW, h: buttonH };
    }
    return layout;
}

function drawInspector(node, ctx) {
    if (node.flags?.collapsed) return;
    const payload = node.__soMetadataPayload || {};
    const layout = layoutInspector(node);
    node.__soMetadataHitRects = layout.buttons;

    ctx.save();
    if (layout.tools) drawToolPanel(node, ctx, layout.tools, layout.buttons);
    if (layout.status) drawTextBox(ctx, layout.status, "IMAGE", payload.status || "");
    if (layout.final) drawTextBox(ctx, layout.final, "FINAL PROMPT", payload.final_prompt || "");
    if (layout.source) drawTextBox(ctx, layout.source, "SOURCE PROMPT", payload.source_prompt || "");
    if (layout.metadata) drawTextBox(ctx, layout.metadata, "METADATA", payload.resolved_inputs || "");

    const flash = node.__soMetadataFlashKey;
    const pressed = node.__soMetadataPressedKey;
    if (layout.buttons.final) drawCopyButton(ctx, layout.buttons.final, flash === "final" ? "✓ Final prompt copied" : "📋 Copy final prompt", Boolean(payload.final_prompt), pressed === "final");
    if (layout.buttons.source) drawCopyButton(ctx, layout.buttons.source, flash === "source" ? "✓ Source prompt copied" : "📋 Copy source prompt", Boolean(payload.source_prompt), pressed === "source");
    for (const entry of layout.quickCopies || []) {
        const key = `copy_${entry.key}`;
        drawCopyButton(ctx, entry.rect, flash === key ? "✓ COPIED" : `⧉ ${entry.label} · ${entry.value}`, true, pressed === key);
    }
    if (layout.buttons.report) drawCopyButton(ctx, layout.buttons.report, flash === "report" ? "✓ Metadata copied" : "📋 Copy full metadata report", Boolean(payload.full_report), pressed === "report");
    drawPreviewPanel(node, ctx, layout.preview);
    ctx.restore();
}

function pointInRect(pos, rect) {
    if (!rect || !Array.isArray(pos)) return false;
    return pos[0] >= rect.x && pos[0] <= rect.x + rect.w && pos[1] >= rect.y && pos[1] <= rect.y + rect.h;
}

function installNode(node) {
    node.properties = node.properties || {};
    applyStudioNodeColors(node);
    for (const name of HIDDEN_FIELDS) hideBackingWidget(widget(node, name));
    arrangeTopWidgets(node);

    if (!node.__soMetadataDrawInstalled) {
        node.__soMetadataDrawInstalled = true;
        // This node renders its own preview panel. Do not let Comfy's native
        // image-preview hooks paint the same image a second time underneath/
        // beside our custom preview.
        node.onDrawBackground = function () {};
        node.onDrawForeground = function (ctx) {
            drawInspector(this, ctx);
        };

        const originalDragOver = node.onDragOver;
        node.onDragOver = function (event) {
            if (event?.dataTransfer?.types?.includes?.("Files")) return true;
            return originalDragOver?.apply(this, arguments);
        };

        const originalDragDrop = node.onDragDrop;
        node.onDragDrop = function (event) {
            const file = event?.dataTransfer?.files?.[0];
            if (file && /\.(png|jpe?g|webp)$/i.test(file.name || "")) {
                uploadTempFile(this, file);
                return true;
            }
            return originalDragDrop?.apply(this, arguments);
        };

        const originalMouseDown = node.onMouseDown;
        node.onMouseDown = function (event, pos, graphCanvas) {
            const rects = this.__soMetadataHitRects || {};
            const payload = this.__soMetadataPayload || {};
            if (pointInRect(pos, rects.upload)) {
                metadataPress(this, "upload");
                chooseTempFile(this);
                return true;
            }
            if (pointInRect(pos, rects.clear)) {
                metadataPress(this, "clear");
                clearLoadedImage(this, true);
                return true;
            }
            if (pointInRect(pos, rects.seed)) {
                const seedText = String(payload.seed_text || "").trim();
                if (seedText) metadataCopy(this, "seed", seedText);
                return true;
            }
            if (pointInRect(pos, rects.recipe)) {
                if (payload.has_metadata && !this.__soMetadataRecipeBusy) saveLoadedMetadataRecipe(this);
                return true;
            }
            if (pointInRect(pos, rects.final)) {
                metadataCopy(this, "final", payload.final_prompt || "");
                return true;
            }
            if (pointInRect(pos, rects.source)) {
                metadataCopy(this, "source", payload.source_prompt || "");
                return true;
            }
            for (const entry of metadataQuickCopyEntries(payload)) {
                const key = `copy_${entry.key}`;
                if (pointInRect(pos, rects[key])) {
                    metadataCopy(this, key, entry.value);
                    return true;
                }
            }
            if (pointInRect(pos, rects.report)) {
                metadataCopy(this, "report", payload.full_report || "");
                return true;
            }
            return originalMouseDown?.apply(this, arguments);
        };
    }

    if (node.properties.so_metadata_core_payload) applyPayload(node, node.properties.so_metadata_core_payload);
    else applyPayload(node, {});

    const storedPreview = node.properties?.[PREVIEW_PROP];
    if (Array.isArray(storedPreview) && storedPreview.length && !node.__soMetadataPreviewImages?.length) {
        loadPreview(node, storedPreview, false);
    }

    node.size = [Math.max(node.size?.[0] || DEFAULT_WIDTH, MIN_WIDTH), Math.max(node.size?.[1] || DEFAULT_HEIGHT, MIN_HEIGHT)];
    ensureMetadataHeight(node);
    setTimeout(() => arrangeTopWidgets(node), 0);
    setTimeout(() => arrangeTopWidgets(node), 150);
    node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "SickOllie.Studio.ImageMetadataCore",
    async setup() {
        api.addEventListener("execution_start", () => {
            for (const node of app.graph?._nodes || []) {
                if (node?.type === TARGET || node?.comfyClass === TARGET) clearForExecution(node);
            }
        });
    },
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== TARGET) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        const originalConfigured = nodeType.prototype.onConfigure;
        const originalExecuted = nodeType.prototype.onExecuted;
        const originalSerialized = nodeType.prototype.onSerialize;
        const originalResize = nodeType.prototype.onResize;

        nodeType.prototype.onNodeCreated = function () {
            const result = originalCreated?.apply(this, arguments);
            applyStudioNodeColors(this);
            this.size = [Math.max(DEFAULT_WIDTH, MIN_WIDTH), DEFAULT_HEIGHT];
            setTimeout(() => {
                installNode(this);
                const imageFile = widget(this, "image_file")?.value;
                if (imageFile && imageFile !== "[None]") refreshFromImageFile(this, imageFile);
            }, 0);
            return result;
        };

        nodeType.prototype.onConfigure = function (info) {
            const result = originalConfigured?.apply(this, arguments);
            this.properties = this.properties || {};
            applyStudioNodeColors(this);
            const payload = info?.properties?.so_metadata_core_payload || this.properties.so_metadata_core_payload;
            setTimeout(() => {
                installNode(this);
                if (payload) applyPayload(this, payload);
                const imageFile = widget(this, "image_file")?.value;
                if (imageFile && imageFile !== "[None]" && !hasWiredImage(this)) refreshFromImageFile(this, imageFile);
            }, 0);
            return result;
        };

        nodeType.prototype.onExecuted = function (message) {
            // Do not call Comfy's inherited image-preview execution handler here.
            // It creates the stock preview in addition to our custom side panel.
            applyPayload(this, message?.metadata_payload || {});
            loadPreview(this, message?.images || message?.ui?.images || [], true);
            this.images = [];
            this.imgs = [];
            this.imageRects = [];
            this.imageIndex = null;
            this.overIndex = null;
            this.animatedImages = false;
            this.setDirtyCanvas?.(true, true);
        };

        nodeType.prototype.onResize = function (size) {
            const minimumHeight = minimumMetadataHeight(this);
            if (Array.isArray(size) || (size && typeof size === "object")) {
                size[0] = Math.max(Number(size[0] || 0), MIN_WIDTH);
                size[1] = Math.max(Number(size[1] || 0), minimumHeight);
            }
            const result = originalResize?.apply(this, arguments);
            if (this.size) {
                this.size[0] = Math.max(Number(this.size[0] || 0), MIN_WIDTH);
                this.size[1] = Math.max(Number(this.size[1] || 0), minimumHeight);
            }
            this.setDirtyCanvas?.(true, true);
            return result;
        };

        nodeType.prototype.onSerialize = function (data) {
            const result = originalSerialized?.apply(this, arguments);
            data.properties = data.properties || {};
            data.properties.so_metadata_core_payload = {
                ...(this.__soMetadataPayload || this.properties?.so_metadata_core_payload || {}),
            };
            data.properties[PREVIEW_PROP] = (this.__soMetadataPreviewData || []).map((item) => ({ ...item }));
            return result;
        };
    },
});
