import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { registerSoloHubItem } from "./solo_hub.js";
import { installStudioInteractions } from "./studio_interactions.js";

const API = "/sickollie/outfit-forge";
const STYLE_URL = new URL("./solo_outfit_forge.css", import.meta.url).href;
const STYLE_ID = "sickollie-outfit-forge-style";
const DRAFT_KEY = "sickollie.outfitForge.draft.v2";

let root = null;
let config = null;
let auditTimer = null;
let generationSerial = 0;

const BANK_FIELDS = [
    ["garments", "Garments + outfit families"],
    ["materials", "Materials"],
    ["colors", "Palette"],
    ["construction", "Construction logic"],
    ["motifs", "Motifs + details"],
    ["fasteners", "Fasteners + anchors"],
    ["accessories", "Accessories"],
    ["effects", "Effects + movement"],
];

const LEVEL_LABELS = {
    coverage: ["", "barely-there", "high-exposure", "balanced", "substantial", "fully covered"],
    complexity: ["", "simple", "clean", "detailed", "ornate", "maximal"],
    realism: ["", "dream logic", "editorial", "clear + plausible", "wearable", "production-ready"],
};

function emptyDraft() {
    return {
        theme: "",
        filename: "",
        filenameAuto: true,
        count: 100,
        seed: Math.floor(Math.random() * 2_000_000_000),
        coverage: 3,
        complexity: 3,
        realism: 3,
        required: "",
        avoided: "",
        garments: "",
        materials: "",
        colors: "",
        construction: "",
        motifs: "",
        fasteners: "",
        accessories: "",
        effects: "",
        lines: [],
        audit: null,
        interpretation: null,
        briefCoverage: null,
        search: "",
        revision: 0,
    };
}

function restoreDraft() {
    try {
        const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
        if (!saved || typeof saved !== "object") return emptyDraft();
        const draft = { ...emptyDraft(), ...saved };
        draft.lines = Array.isArray(saved.lines) ? saved.lines.map(value => String(value || "")) : [];
        // Older Forge drafts had no way to distinguish an auto-generated filename
        // from a user-authored one. Treat legacy filenames as theme-linked until
        // the user edits the filename field in this build.
        if (typeof saved.filenameAuto !== "boolean") draft.filenameAuto = true;
        if (draft.filenameAuto) draft.filename = String(draft.theme || "").trim() ? normalizeFilename(draft.theme) : "";
        return draft;
    } catch {
        return emptyDraft();
    }
}

let draft = restoreDraft();

function persist() {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(draft)); } catch { /* Browser storage is optional. */ }
}

function ensureStyles() {
    if (document.getElementById(STYLE_ID)) return;
    const link = document.createElement("link");
    link.id = STYLE_ID;
    link.rel = "stylesheet";
    link.href = STYLE_URL;
    document.head.append(link);
}

async function request(path, options = {}) {
    const response = await api.fetchApi(`${API}${path}`, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    let data = null;
    try { data = await response.json(); } catch { data = null; }
    if (!response.ok || data?.ok === false) throw new Error(data?.error || `Outfit Forge request failed (${response.status})`);
    return data;
}

function el(tag, className = "", text = "") {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== "") node.textContent = text;
    return node;
}

function button(label, title = "") {
    const node = document.createElement("button");
    node.type = "button";
    node.textContent = label;
    if (title) node.title = title;
    return node;
}

function labelFor(text, control) {
    const label = document.createElement("label");
    label.append(el("span", "", text), control);
    return label;
}

function setStatus(message, color = "#99919f") {
    const status = root?.querySelector("[data-forge-status]");
    if (!status) return;
    status.textContent = message;
    status.style.color = color;
}

function normalizeFilename(value) {
    const clean = String(value || "Outfit Forge Log")
        .replace(/[^a-z0-9._ -]+/gi, "")
        .trim()
        .replace(/\s+/g, " ") || "Outfit Forge Log";
    return clean.toLowerCase().endsWith(".txt") ? clean : `${clean}.txt`;
}

function textareaValue(field) {
    return String(draft[field] || "");
}

function inputControl(field, type = "text", attributes = {}) {
    const input = document.createElement("input");
    input.type = type;
    input.value = String(draft[field] ?? "");
    for (const [key, value] of Object.entries(attributes)) input.setAttribute(key, String(value));
    input.addEventListener("input", () => {
        draft[field] = type === "number" || type === "range" ? Number(input.value) : input.value;
        if (field === "filename") {
            // Any explicit filename edit detaches it from Theme. Clearing the
            // field opts back into automatic theme-linked naming.
            draft.filenameAuto = !String(input.value || "").trim();
            if (draft.filenameAuto && String(draft.theme || "").trim()) {
                draft.filename = normalizeFilename(draft.theme);
                input.value = draft.filename;
            }
        } else if (field === "theme" && draft.filenameAuto !== false) {
            draft.filename = String(input.value || "").trim() ? normalizeFilename(input.value) : "";
            const filename = root?.querySelector('[data-forge-field="filename"]');
            if (filename) filename.value = draft.filename;
        }
        persist();
    });
    input.dataset.forgeField = field;
    return input;
}

function textAreaControl(field, placeholder = "One phrase per line") {
    const area = document.createElement("textarea");
    area.value = textareaValue(field);
    area.placeholder = placeholder;
    area.dataset.forgeField = field;
    area.addEventListener("input", () => { draft[field] = area.value; persist(); });
    return area;
}

function section(title) {
    const box = el("section", "so-forge__section");
    box.append(el("div", "so-forge__section-title", title));
    return box;
}

function levelControl(field, label, low, high) {
    const row = el("div", "so-forge__range");
    row.append(el("span", "", label));
    const input = inputControl(field, "range", { min: 1, max: 5, step: 1 });
    const levelText = value => `${value} · ${LEVEL_LABELS[field]?.[Number(value)] || ""}`;
    const output = el("span", "so-forge__range-output", levelText(draft[field] || 3));
    input.addEventListener("input", () => { output.textContent = levelText(input.value); });
    input.title = `${low} ↔ ${high}`;
    row.append(input, output);
    return row;
}

function renderSetup() {
    const host = root?.querySelector("[data-forge-setup]");
    if (!host || !config) return;
    host.replaceChildren();

    const brief = section("Creative brief");
    if (draft.filenameAuto !== false) draft.filename = String(draft.theme || "").trim() ? normalizeFilename(draft.theme) : "";
    const theme = inputControl("theme");
    theme.placeholder = "e.g. haunted porcelain doll rave";
    const filename = inputControl("filename");
    filename.placeholder = normalizeFilename(draft.theme || "Outfit Forge Log");
    brief.append(
        labelFor("Theme", theme),
        labelFor("Log filename", filename),
        el("div", "so-forge__hint", "Named garments, colors, and materials become binding instructions. Forge identifies any brief words its beta interpreter cannot represent yet."),
    );
    const understood = draft.interpretation || {};
    const understoodParts = [
        ...((understood.bindings || []).length ? understood.bindings : (understood.pieces || [])),
        ...(understood.colors || []),
        ...(understood.materials || []),
        ...(understood.styles || []),
    ];
    if (understoodParts.length) brief.append(el("div", "so-forge__understood", `Understood · ${understoodParts.join(" · ")}`));
    const unsupported = draft.briefCoverage?.unrepresented || [];
    if (unsupported.length) brief.append(el("div", "so-forge__understood", `Not represented · ${unsupported.join(" · ")}`));
    host.append(brief);

    const shape = section("Output shape");
    const count = inputControl("count", "number", { min: 1, max: config.max_lines || 500, step: 1 });
    const seed = inputControl("seed", "number", { step: 1 });
    const topRow = el("div", "so-forge__row");
    topRow.append(labelFor("Line count", count), labelFor("Seed", seed));
    shape.append(
        topRow,
        levelControl("coverage", "Coverage", "barely-there", "fully covered"),
        levelControl("complexity", "Complexity", "pared-back", "maximalist"),
        levelControl("realism", "Wearability", "impossible", "production-ready"),
        el("div", "so-forge__hint", "Coverage changes exposure and layering. Complexity changes detail density. Wearability 1–2 permits experimental construction; 3–5 stays clear and plausible."),
    );
    host.append(shape);

    const vocabulary = section("Optional refinements");
    const advanced = el("details", "so-forge__advanced");
    if (draft.required || draft.avoided || BANK_FIELDS.some(([field]) => textareaValue(field))) advanced.open = true;
    advanced.append(el("summary", "", "Advanced controls"));
    advanced.append(el("div", "so-forge__hint", "Usually the theme and sliders are enough. These fields can narrow vocabulary, but explicit words in the theme always remain mandatory."));
    advanced.append(
        labelFor("Required", textAreaControl("required", "Required phrases, one per line")),
        labelFor("Avoid", textAreaControl("avoided", "Avoided words or phrases, one per line")),
    );
    const banks = el("div", "so-forge__banks");
    for (const [field, label] of BANK_FIELDS) banks.append(labelFor(label, textAreaControl(field)));
    advanced.append(banks);
    vocabulary.append(advanced);
    host.append(vocabulary);

    const actions = el("div", "so-forge__generate");
    const generate = button(draft.lines.length ? "REBUILD OUTFIT LOG" : "FORGE OUTFIT LOG", "Generate a fresh deterministic log from this brief");
    generate.className = "so-forge__generate-main";
    generate.onclick = () => generateLog(generate);
    const newSeed = button("NEW SEED", "Change only the generation seed");
    newSeed.onclick = () => {
        draft.seed = Math.floor(Math.random() * 2_000_000_000);
        persist();
        renderSetup();
        setStatus("New seed ready", "#2cecff");
    };
    actions.append(generate, newSeed);
    host.append(actions);
}

function payload(overrides = {}) {
    return {
        theme: draft.theme,
        filename: draft.filename || draft.theme,
        count: draft.count,
        seed: draft.seed,
        coverage: draft.coverage,
        complexity: draft.complexity,
        realism: draft.realism,
        required: draft.required,
        avoided: draft.avoided,
        garments: draft.garments,
        materials: draft.materials,
        colors: draft.colors,
        construction: draft.construction,
        motifs: draft.motifs,
        fasteners: draft.fasteners,
        accessories: draft.accessories,
        effects: draft.effects,
        ...overrides,
    };
}

async function generateLog(trigger) {
    const serial = ++generationSerial;
    if (!String(draft.theme || "").trim()) {
        root?.querySelector('[data-forge-field="theme"]')?.focus();
        setStatus("Describe a theme first", "#ff78bd");
        return;
    }
    trigger.disabled = true;
    const prior = trigger.textContent;
    trigger.textContent = "FORGING…";
    setStatus(`Building ${Number(draft.count || 100).toLocaleString()} conceptually varied outfits…`, "#fff04d");
    try {
        const result = await request("/generate", { method: "POST", body: JSON.stringify(payload()) });
        if (serial !== generationSerial) return;
        draft.lines = result.lines || [];
        draft.audit = result.audit || null;
        draft.seed = result.seed;
        draft.filename = draft.filenameAuto === false
            ? String(draft.filename || result.filename || draft.theme)
            : String(result.filename || normalizeFilename(draft.theme));
        draft.interpretation = result.fidelity?.interpreted || null;
        draft.briefCoverage = result.fidelity?.brief_coverage || null;
        draft.revision += 1;
        persist();
        renderSetup();
        renderWorkspace();
        const understood = draft.interpretation || {};
        const route = [...((understood.bindings || []).length ? understood.bindings : (understood.pieces || [])), ...(understood.materials || []), ...(understood.styles || [])].join(" · ");
        setStatus(`${draft.lines.length.toLocaleString()} outfits forged${route ? ` · ${route}` : ""}`, "#6ee7a2");
    } catch (error) {
        setStatus(error.message || "Generation failed", "#ff78bd");
        alert(error.message || "Outfit Forge could not generate this log.");
    } finally {
        trigger.disabled = false;
        trigger.textContent = prior;
    }
}

function issueMap() {
    const map = new Map();
    for (const row of draft.audit?.issues || []) map.set(Number(row.line) - 1, Array.isArray(row.issues) ? row.issues : []);
    return map;
}

function renderMetrics(toolbar) {
    const count = el("span", "so-forge__metric");
    count.innerHTML = `<strong>${draft.lines.length.toLocaleString()}</strong> lines`;
    const unique = el("span", "so-forge__metric");
    unique.innerHTML = `<strong>${Number(draft.audit?.unique_count ?? new Set(draft.lines.map(value => value.toLowerCase())).size).toLocaleString()}</strong> unique`;
    const score = el("span", "so-forge__metric so-forge__metric--score");
    score.innerHTML = `audit <strong>${Number(draft.audit?.score ?? 0)}</strong>`;
    toolbar.append(count, unique, score);
}

function scheduleAudit() {
    clearTimeout(auditTimer);
    auditTimer = setTimeout(() => runAudit(false), 550);
}

async function runAudit(announce = true) {
    if (!draft.lines.length) return;
    if (announce) setStatus("Auditing diversity, openings, duplicates, and restrictions…", "#fff04d");
    try {
        const result = await request("/audit", { method: "POST", body: JSON.stringify({ theme: draft.theme, lines: draft.lines, required: draft.required, avoided: draft.avoided }) });
        draft.audit = result.audit;
        persist();
        renderWorkspace();
        if (announce) setStatus(`Audit complete · score ${draft.audit.score}`, draft.audit.ok ? "#6ee7a2" : "#ff9b5f");
    } catch (error) {
        if (announce) setStatus(error.message || "Audit failed", "#ff78bd");
    }
}

function renderAuditBanner(host) {
    const audit = draft.audit;
    host.dataset.visible = audit && draft.lines.length ? "1" : "0";
    host.replaceChildren();
    if (!audit || !draft.lines.length) return;
    const score = el("div", "so-forge__audit-score", String(audit.score));
    const copy = el("div", "so-forge__audit-copy");
    const issueLines = Array.isArray(audit.issues) ? audit.issues.length : 0;
    const closest = audit.closest_pair || {};
    const fidelity = audit.fidelity || null;
    copy.innerHTML = `<strong>${audit.unique_count}/${audit.line_count} unique</strong> · ${audit.exact_duplicate_count} exact duplicates · ${audit.repeated_opening_count} repeated openings` +
        (fidelity ? ` · constraint fidelity ${Number(fidelity.score || 0)}%` : "") +
        (fidelity?.brief_coverage ? ` · brief coverage ${Number(fidelity.brief_coverage.score || 0)}%` : "") +
        (Number(closest.score || 0) ? ` · closest pair ${closest.left}/${closest.right} at ${Math.round(Number(closest.score) * 100)}%` : "") +
        (issueLines ? `<br>${issueLines} line${issueLines === 1 ? "" : "s"} need attention; issue badges appear beneath their editors.` : "<br>The log passes the current structural audit.");
    const rerun = button("RUN AUDIT", "Recalculate audit after edits");
    rerun.onclick = () => runAudit(true);
    host.append(score, copy, rerun);
}

async function regenerateLine(index, trigger) {
    trigger.disabled = true;
    setStatus(`Reforging line ${index + 1}…`, "#fff04d");
    try {
        draft.revision = Number(draft.revision || 0) + 1;
        const seed = Number(draft.seed || 0) + (index + 1) * 7919 + draft.revision * 104729;
        const result = await request("/generate", { method: "POST", body: JSON.stringify(payload({ count: 1, seed })) });
        draft.lines[index] = String(result.lines?.[0] || draft.lines[index]);
        persist();
        await runAudit(false);
        setStatus(`Line ${index + 1} reforged`, "#6ee7a2");
    } catch (error) {
        setStatus(error.message || "Could not reforge this line", "#ff78bd");
    } finally { trigger.disabled = false; }
}

function renderEntries(host) {
    host.replaceChildren();
    if (!draft.lines.length) {
        const empty = el("div", "so-forge__empty");
        empty.innerHTML = "Describe the outfit theme and shape it with the three sliders,<br>then forge a complete editable OUTFIT log.";
        host.append(empty);
        return;
    }
    const list = el("div", "so-forge__entry-list");
    const issues = issueMap();
    const query = String(draft.search || "").trim().toLowerCase();
    draft.lines.forEach((line, index) => {
        if (query && !String(line).toLowerCase().includes(query) && !String(index + 1).includes(query)) return;
        const entryIssues = issues.get(index) || [];
        const row = el("article", "so-forge__entry");
        row.dataset.issue = entryIssues.length ? "1" : "0";
        const number = el("div", "so-forge__index", String(index + 1));
        const main = el("div", "so-forge__entry-main");
        const area = document.createElement("textarea");
        area.value = line;
        area.setAttribute("aria-label", `Outfit line ${index + 1}`);
        area.oninput = () => {
            draft.lines[index] = area.value.replace(/[\r\n]+/g, " ");
            persist();
            scheduleAudit();
        };
        main.append(area);
        if (entryIssues.length) {
            const badges = el("div", "so-forge__issues");
            for (const issue of entryIssues) badges.append(el("span", "so-forge__issue", issue));
            main.append(badges);
        }
        const actions = el("div", "so-forge__entry-actions");
        const regen = button("↻", "Regenerate only this entry");
        regen.onclick = () => regenerateLine(index, regen);
        const duplicate = button("+", "Duplicate as an editable new line");
        duplicate.onclick = () => {
            draft.lines.splice(index + 1, 0, draft.lines[index]);
            persist();
            renderWorkspace();
            scheduleAudit();
        };
        const remove = button("×", "Remove this entry");
        remove.onclick = () => {
            draft.lines.splice(index, 1);
            persist();
            renderWorkspace();
            scheduleAudit();
        };
        actions.append(regen, duplicate, remove);
        row.append(number, main, actions);
        list.append(row);
    });
    if (!list.childElementCount) list.append(el("div", "so-forge__empty", "No Outfit lines match this search."));
    host.append(list);
}

function copyLines() {
    if (!draft.lines.length) return;
    navigator.clipboard?.writeText(`${draft.lines.join("\n")}\n`)
        .then(() => setStatus("Outfit log copied", "#6ee7a2"))
        .catch(() => setStatus("Clipboard access was unavailable", "#ff78bd"));
}

function downloadLines() {
    if (!draft.lines.length) return;
    const blob = new Blob([`${draft.lines.join("\n")}\n`], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = normalizeFilename(draft.filename || draft.theme);
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1200);
    setStatus(`Downloaded ${link.download}`, "#6ee7a2");
}

function modal(title) {
    const overlay = el("div", "so-forge-modal");
    const card = el("div", "so-forge-modal__card");
    const head = el("div", "so-forge-modal__head", title);
    const body = el("div", "so-forge-modal__body");
    const foot = el("div", "so-forge-modal__foot");
    card.append(head, body, foot);
    overlay.append(card);
    overlay.onpointerdown = event => { if (event.target === overlay) overlay.remove(); };
    document.body.append(overlay);
    return { overlay, card, body, foot };
}

function parentCollections() {
    return (config?.collections || []).filter(row => !String(row.parent_id || ""));
}

function showLibraryExport() {
    if (!draft.lines.length) return;
    const { overlay, body, foot } = modal("EXPORT TO OUTFIT LOOKS");
    const intro = el("div", "so-forge__hint", `Publish ${draft.lines.length.toLocaleString()} reviewed Forge lines as canonical Outfit assets. Existing identical outfits are matched, not duplicated.`);
    body.append(intro);

    const categoryList = document.createElement("datalist");
    categoryList.id = `so-forge-categories-${Date.now()}`;
    for (const row of parentCollections()) categoryList.append(new Option(row.name, row.name));
    const category = document.createElement("input");
    category.placeholder = "New or existing category";
    category.value = String(draft.theme || "Outfit Forge");
    category.setAttribute("list", categoryList.id);

    const subcategoryList = document.createElement("datalist");
    subcategoryList.id = `so-forge-subcategories-${Date.now()}`;
    const subcategory = document.createElement("input");
    subcategory.placeholder = "Optional new or existing subcategory";
    subcategory.setAttribute("list", subcategoryList.id);
    const refreshSubcategories = () => {
        subcategoryList.replaceChildren();
        const parent = parentCollections().find(row => String(row.name || "").toLowerCase() === category.value.trim().toLowerCase());
        if (!parent) return;
        for (const row of config.collections || []) {
            if (String(row.parent_id || "") === String(parent.collection_id || "")) subcategoryList.append(new Option(row.name, row.name));
        }
    };
    category.oninput = refreshSubcategories;
    refreshSubcategories();
    body.append(labelFor("Category", category), categoryList, labelFor("Subcategory (optional)", subcategory), subcategoryList);

    const cancel = button("CANCEL");
    cancel.onclick = () => overlay.remove();
    const publish = button("EXPORT OUTFITS");
    publish.style.borderColor = "#ff42bd";
    publish.onclick = async () => {
        if (!category.value.trim()) { category.focus(); return; }
        publish.disabled = true;
        publish.textContent = "EXPORTING…";
        try {
            const result = await request("/export-library", { method: "POST", body: JSON.stringify({ lines: draft.lines, category: category.value, subcategory: subcategory.value }) });
            // The catalog mutation is the export. Refreshing local collection
            // suggestions afterward is best-effort and must never turn a
            // successful publish into a scary false failure dialog.
            try {
                const fresh = await request("/config");
                config.collections = fresh.collections || config.collections;
            } catch { /* The exported Looks are already safely committed. */ }
            overlay.remove();
            const target = subcategory.value.trim() || category.value.trim();
            const syncWarning = result.log_sync?.ok === false ? " · Prompt Core log refresh deferred" : "";
            setStatus(`${result.created} new + ${result.matched} matched Looks exported to ${target}${syncWarning}`, result.log_sync?.ok === false ? "#fff04d" : "#6ee7a2");
            alert(`Outfit Looks export complete.\n\n${result.created} new Looks\n${result.matched} existing Looks matched\n${result.memberships_added} category memberships added${result.log_sync?.ok === false ? "\n\nThe Looks are saved; generated Prompt Core logs will refresh on the next normal Library sync." : ""}`);
        } catch (error) {
            alert(error.message || "Could not export to Outfit Looks.");
            publish.disabled = false;
            publish.textContent = "EXPORT OUTFITS";
        }
    };
    foot.append(cancel, publish);
}

function clearDraft() {
    if (draft.lines.length && !confirm("Clear the current Outfit Forge brief and all generated lines?")) return;
    draft = emptyDraft();
    persist();
    renderSetup();
    renderWorkspace();
    setStatus("New Forge draft ready", "#2cecff");
}

function addBlankLine() {
    draft.lines.push("");
    persist();
    renderWorkspace();
    const entries = root?.querySelector("[data-forge-entries]");
    if (entries) entries.scrollTop = entries.scrollHeight;
}

function renderWorkspace() {
    if (!root) return;
    const toolbar = root.querySelector("[data-forge-toolbar]");
    const banner = root.querySelector("[data-forge-audit]");
    const entries = root.querySelector("[data-forge-entries]");
    if (!toolbar || !banner || !entries) return;
    toolbar.replaceChildren();
    renderMetrics(toolbar);

    const audit = button("AUDIT", "Run the structural diversity audit");
    audit.onclick = () => runAudit(true);
    const copy = button("COPY", "Copy all Outfit lines");
    copy.onclick = copyLines;
    const download = button("DOWNLOAD .TXT", "Download the exact single-line log");
    download.onclick = downloadLines;
    const exportLibrary = button("EXPORT TO OUTFIT LOOKS", "Create or update a Looks Category → Subcategory in Creative Library");
    exportLibrary.style.borderColor = "#ff42bd";
    exportLibrary.onclick = showLibraryExport;
    const add = button("+ LINE", "Add an empty editable line");
    add.onclick = addBlankLine;
    const reset = button("NEW", "Clear this draft");
    reset.onclick = clearDraft;
    for (const control of [audit, copy, download, exportLibrary]) control.disabled = !draft.lines.length;

    const search = document.createElement("input");
    search.type = "search";
    search.className = "so-forge__search";
    search.placeholder = "Find in this log…";
    search.value = draft.search || "";
    search.oninput = () => { draft.search = search.value; persist(); renderEntries(entries); };
    toolbar.append(audit, copy, download, exportLibrary, add, reset, search);
    renderAuditBanner(banner);
    renderEntries(entries);
}

function close() {
    root?.remove();
    root = null;
}

function shell() {
    ensureStyles();
    const overlay = el("div", "so-forge-overlay");
    overlay.dataset.sickOllieOutfitForge = "1";
    const panel = el("div", "so-forge");
    const header = el("header", "so-forge__header");
    const mark = el("div", "so-forge__mark", "✦");
    const titleBlock = el("div", "so-forge__title-block");
    titleBlock.append(
        el("div", "so-forge__eyebrow", "OFFLINE OUTFIT SYSTEM · BETA"),
        el("h2", "so-forge__title", "Outfit Forge"),
        el("div", "so-forge__subtitle", "Theme-first generation · constraint + diversity audit · direct Outfit Looks export"),
    );
    const status = el("div", "so-forge__header-status", "Restoring Forge draft…");
    status.dataset.forgeStatus = "";
    const closeButton = button("×", "Close Outfit Forge");
    closeButton.className = "so-forge__close";
    closeButton.onclick = close;
    header.append(mark, titleBlock, status, closeButton);

    const body = el("div", "so-forge__body");
    const setup = el("aside", "so-forge__setup");
    setup.dataset.forgeSetup = "";
    const workspace = el("main", "so-forge__workspace");
    const toolbar = el("div", "so-forge__toolbar");
    toolbar.dataset.forgeToolbar = "";
    const audit = el("div", "so-forge__audit-banner");
    audit.dataset.forgeAudit = "";
    const entries = el("div", "so-forge__entries");
    entries.dataset.forgeEntries = "";
    workspace.append(toolbar, audit, entries);
    body.append(setup, workspace);
    panel.append(header, body);
    overlay.append(panel);
    overlay.onpointerdown = event => { if (event.target === overlay) close(); };
    return overlay;
}

async function openOutfitForge() {
    if (root?.isConnected) {
        root.querySelector('[data-forge-field="theme"]')?.focus();
        return;
    }
    root = shell();
    installStudioInteractions(root);
    document.body.append(root);
    renderWorkspace();
    try {
        config = await request("/config");
        renderSetup();
        renderWorkspace();
        setStatus(draft.lines.length ? `Draft restored · ${draft.lines.length} lines` : "Ready to forge", "#6ee7a2");
    } catch (error) {
        setStatus(error.message || "Outfit Forge could not load", "#ff78bd");
        const setup = root.querySelector("[data-forge-setup]");
        if (setup) setup.append(el("div", "so-forge__empty", "Outfit Forge backend did not load. Restart ComfyUI after installing this build."));
    }
}

app.registerExtension({
    name: "SickOllie.SOS.OutfitForge",
    menuCommands: [{ path: ["Sick Ollie"], commands: ["solo.openOutfitForge"] }],
    commands: [{ id: "solo.openOutfitForge", label: "Open SOS Outfit Forge", icon: "pi pi-sparkles", function: openOutfitForge }],
    async setup() {
        window.__soOpenOutfitForge = openOutfitForge;
        registerSoloHubItem({
            id: "outfit-forge",
            label: "Outfit Forge",
            description: "Forge varied, editable OUTFIT logs from a theme, audit repetition, and export complete categories into Outfit Looks.",
            color: "#ff42bd",
            open: openOutfitForge,
        });
    },
});

export { openOutfitForge };
