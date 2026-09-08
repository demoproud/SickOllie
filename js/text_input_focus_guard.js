import { app } from "../../../scripts/app.js";

const EDITABLE_SELECTOR = "input, textarea, select, [contenteditable]";
const NON_TEXT_INPUT_TYPES = new Set([
    "button", "checkbox", "color", "file", "hidden", "image",
    "radio", "range", "reset", "submit",
]);

let lastEditable = null;
let lastEditableAt = 0;
let editableBeforeWindowBlur = null;
let focusFrame = null;
let focusTimer = null;
const isolatedEditables = new WeakSet();

function editableFrom(target) {
    if (!(target instanceof Element)) return null;
    const editable = target.closest(EDITABLE_SELECTOR);
    if (!editable || !editable.isConnected) return null;
    if (editable.matches("input, textarea, select")) {
        if (editable.disabled || editable.readOnly || editable.getAttribute("aria-disabled") === "true") return null;
        if (editable instanceof HTMLInputElement && NON_TEXT_INPUT_TYPES.has(String(editable.type || "text").toLowerCase())) return null;
        return editable;
    }
    if (editable.getAttribute("contenteditable") === "false") return null;
    return editable;
}

function canvasElement(canvas = app?.canvas) {
    return canvas?.canvas || app?.canvasEl || document.querySelector("canvas.lgraphcanvas");
}

function releaseComfyCanvasCapture() {
    const canvas = app?.canvas;
    if (!canvas) return false;
    let released = false;
    for (const name of ["node_capturing_input", "node_widget"]) {
        try {
            if (canvas[name] != null) { canvas[name] = null; released = true; }
        } catch (error) {}
    }
    for (const name of ["dragging_canvas", "isDragging"]) {
        try {
            if (canvas[name]) { canvas[name] = false; released = true; }
        } catch (error) {}
    }
    if (released) {
        try { canvas.pointer?.reset?.(); } catch (error) {}
    }
    try {
        const element = canvasElement(canvas);
        if (element && document.activeElement === element && typeof element.blur === "function") {
            element.blur();
            released = true;
        }
    } catch (error) {}
    return released;
}

function isolateEditableKeyboard(editable) {
    if (!editable?.isConnected || isolatedEditables.has(editable)) return;
    const stopAtEditable = event => {
        if (editableFrom(event.target) === editable) event.stopPropagation();
    };
    for (const type of ["keydown", "keyup", "keypress"]) editable.addEventListener(type, stopAtEditable);
    isolatedEditables.add(editable);
}

function rememberEditable(editable) {
    if (!editable?.isConnected) return;
    isolateEditableKeyboard(editable);
    lastEditable = editable;
    lastEditableAt = Date.now();
}

function safelyFocus(editable) {
    if (!editable?.isConnected) return false;
    releaseComfyCanvasCapture();
    try {
        if (typeof document.hasFocus === "function" && !document.hasFocus()) window.focus();
    } catch (error) {}
    if (document.activeElement === editable) return true;
    try { editable.focus({ preventScroll: true }); }
    catch (error) {
        try { editable.focus(); }
        catch (focusError) { return false; }
    }
    return document.activeElement === editable;
}

function cancelScheduledFocus() {
    if (focusFrame !== null) cancelAnimationFrame(focusFrame);
    if (focusTimer !== null) clearTimeout(focusTimer);
    focusFrame = null;
    focusTimer = null;
}

function scheduleFocus(editable) {
    if (!editable?.isConnected) return;
    cancelScheduledFocus();
    queueMicrotask(() => {
        if (lastEditable === editable) safelyFocus(editable);
    });
    focusFrame = requestAnimationFrame(() => {
        focusFrame = null;
        if (lastEditable === editable) safelyFocus(editable);
    });
    focusTimer = setTimeout(() => {
        focusTimer = null;
        if (lastEditable === editable) safelyFocus(editable);
    }, 80);
}

function pointerEditable(event) {
    const editable = editableFrom(event.target);
    if (!editable) {
        lastEditable = null;
        cancelScheduledFocus();
        return null;
    }
    rememberEditable(editable);
    releaseComfyCanvasCapture();
    try {
        if (typeof document.hasFocus === "function" && !document.hasFocus()) window.focus();
    } catch (error) {}
    return editable;
}

function onPointerDown(event) {
    const editable = pointerEditable(event);
    if (editable) queueMicrotask(() => releaseComfyCanvasCapture());
}

function onPointerUp(event) {
    const editable = editableFrom(event.target) || lastEditable;
    if (editable) { rememberEditable(editable); scheduleFocus(editable); }
}

function onFocusIn(event) {
    const editable = editableFrom(event.target);
    if (!editable) return;
    rememberEditable(editable);
    releaseComfyCanvasCapture();
}

function onFocusOut(event) {
    const editable = editableFrom(event.target);
    if (!editable) return;
    queueMicrotask(() => {
        const active = editableFrom(document.activeElement);
        if (!editable.isConnected || !active) releaseComfyCanvasCapture();
    });
}

function onKeyDown(event) {
    let editable = editableFrom(event.target) || editableFrom(document.activeElement);
    if (!editable && lastEditable?.isConnected && Date.now() - lastEditableAt < 15000) {
        const active = document.activeElement;
        const canvas = canvasElement();
        if (!active || active === document.body || active === document.documentElement || active === canvas) {
            editable = lastEditable;
            safelyFocus(editable);
        }
    }
    if (editable) releaseComfyCanvasCapture();
}

function onBeforeInput(event) {
    if (editableFrom(event.target)) releaseComfyCanvasCapture();
}

function onWindowBlur() {
    editableBeforeWindowBlur = editableFrom(document.activeElement) || lastEditable;
}

function onWindowFocus() {
    const editable = editableBeforeWindowBlur;
    editableBeforeWindowBlur = null;
    if (editable?.isConnected) { rememberEditable(editable); scheduleFocus(editable); }
}

export function recoverTextInputFocus(target = document.activeElement) {
    releaseComfyCanvasCapture();
    const editable = editableFrom(target) || (lastEditable?.isConnected ? lastEditable : null);
    if (editable) { rememberEditable(editable); scheduleFocus(editable); }
}

app.registerExtension({
    name: "SickOllie.SOS.TextInputFocusGuard",
    setup() {
        if (window.__soTextInputFocusGuardInstalled) return;
        window.__soTextInputFocusGuardInstalled = true;
        window.addEventListener("pointerdown", onPointerDown, true);
        window.addEventListener("mousedown", onPointerDown, true);
        window.addEventListener("pointerup", onPointerUp, true);
        window.addEventListener("mouseup", onPointerUp, true);
        window.addEventListener("focusin", onFocusIn, true);
        window.addEventListener("focusout", onFocusOut, true);
        window.addEventListener("keydown", onKeyDown, true);
        window.addEventListener("beforeinput", onBeforeInput, true);
        window.addEventListener("blur", onWindowBlur);
        window.addEventListener("focus", onWindowFocus);
    },
});
