import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";
import { installStudioInteractions } from "./studio_interactions.js";
import { registerSoloHubItem } from "./solo_hub.js";
import { recoverTextInputFocus } from "./text_input_focus_guard.js";
const RECIPE_LIBRARY_HEADER_URL = new URL("./solo_hub_assets/RecipeLibraryHeader.png", import.meta.url).href;
const RECIPE_LIBRARY_BACKGROUND_URL = new URL("./solo_hub_assets/RecipeLibraryBackground.webp", import.meta.url).href;

const API = "/sickollie/creative-library";
const STUDIO_TYPES = new Set(["SOLoaderCoreEngineStudio", "SOPromptLogEngineStudio", "SOGenerationPipelineStudio"]);
const TYPE_ALIASES = { SOGenerationCoreStudio: "SOGenerationPipelineStudio", SOOutputBuilderStudio: "SOOutputBuilderSaveStudio" };
const SECTION_LABELS = {
    SOLoaderCoreEngineStudio: "Optional model & LoRA resources",
    SOPromptLogEngineStudio: "Prompt recipe",
    SOGenerationPipelineStudio: "Dimensions & resolved seed",
};
const FIELD_LABELS = {
    diffusion_model: "Diffusion model", weight_dtype: "Model precision", folder_name: "LoRA folder",
    main_enabled: "Main LoRA enabled", main_lora: "Main LoRA", main_strength: "LoRA strength",
    prompt_source: "Prompt source", manual_prompt: "Source prompt used", prompt_log_file: "Prompt log used",
    prompt_mode: "Prompt selection mode", prompt_index: "Prompt line", name_token: "Name placeholder",
    name_value: "NAME value used", item_token: "Item / brand placeholder", item_value: "ITEM / BRAND value used",
    outfit_token_A: "Outfit A placeholder", outfit_log_file_A: "Outfit A source log", outfit_index_A: "Outfit A line",
    outfit_token_B: "Outfit B placeholder", outfit_log_file_B: "Outfit B source log", outfit_index_B: "Outfit B line",
    outfit_token_C: "Outfit C placeholder", outfit_log_file_C: "Outfit C source log", outfit_index_C: "Outfit C line",
    scene_token: "Scene placeholder", scene_log_file: "Scene source log", scene_index: "Scene line",
    trigger_token: "Trigger placeholder", trigger_placement: "Trigger placement", trigger_override: "Trigger override",
    seed_value: "Resolved seed", steps: "Steps", cfg: "CFG", sampler_name: "Sampler", scheduler: "Scheduler",
    denoise: "Denoise", shift: "Model shift", custom_width: "Width", custom_height: "Height",
    batch_size: "Batch size", clip_name: "Text encoder", clip_type: "Encoder type", clip_device: "Encoder device",
    vae_name: "VAE", resolution_mode: "Resolution mode", output_root: "Output folder", extension: "Image format",
    quality: "Image quality", counter_digits: "Counter digits", save_prompt_json: "Embed prompt metadata",
    save_workflow_json: "Embed workflow", save_civitai_parameters: "Embed Civitai metadata",
};
const SAFETY_DEFAULT_OFF = new Set(["diffusion_model", "main_lora", "clip_name", "vae_name"]);
const RECIPE_PROMPT_APPLY_FIELDS = new Set(["manual_prompt", "prefix_enabled", "prefix_text", "suffix_enabled", "suffix_text", "prefix_suffix_separator", "cleanup_enabled", "cleanup_rules"]);
const RECIPE_GENERATION_APPLY_FIELDS = new Set(["resolution_mode", "custom_width", "custom_height", "aspect_preset", "megapixels", "batch_size", "steps", "cfg", "sampler_name", "scheduler", "denoise", "shift", "seed_value"]);
let root = null;
let libraryLoadedOnce = false;
let libraryBootstrapping = false;
let libraryRevisions = null;
let libraryRefreshPromise = null;
let libraryStateCounts = {};
let componentViewsLoaded = { outfit: false, scene: false };
let wardrobeDataLoaded = false;
let workshopExtrasLoaded = false;
let recipes = [];
let recipeIndex = new Map();
let promptAssets = [];
const PROMPT_FACET_AXES = ["style", "cast", "content", "time", "shot"];
const emptyPromptFacets = () => Object.fromEntries(PROMPT_FACET_AXES.map(axis => [axis, {}]));
const emptyPromptFacetFilters = () => Object.fromEntries(PROMPT_FACET_AXES.map(axis => [axis, ""]));
let promptFacetCounts = emptyPromptFacets();
let promptFacetUniverse = emptyPromptFacets();
let promptFacetCovers = emptyPromptFacets();
let promptTotal = 0;
let promptAssetTotal = 0;
let promptCorpusTotals = { prompt: 0, template: 0, all: 0 };
let promptHomeCounts = {
    prompt: { parents: {}, subcategories: {}, logs: {} },
    template: { parents: {}, subcategories: {}, logs: {} },
};
let promptHomeUniverse = { prompt: { parents: {}, subcategories: {}, logs: {} }, template: { parents: {}, subcategories: {}, logs: {} } };
let promptPlaceholderCounts = {};
let promptPlaceholderAvailableCounts = {};
let promptParent = "";
let promptSubcategory = "";
let promptLogPath = "";
let promptLogLabel = "";
let promptPlaceholderFilters = new Set();
let promptBlueprintTotal = 0;
let promptComponentBlueprintTotal = 0;
let promptBlueprintSignatures = {};
let blueprintAssets = [];
let promptCollectionCounts = {
    prompt: { "": 0, unfiled: 0 },
    template: { "": 0, unfiled: 0 },
};
let promptLoading = false;
let promptLoadSerial = 0;
let promptLoadTimer = null;
let promptRunScopeLoading = false;
let promptAssetRevision = 0;
let promptViewCache = { key: "", rows: [] };
let promptSearch = "";
let promptCardQueueChain = Promise.resolve();
let promptFolderQueueActive = false;
let promptRatingFilter = "";
const PROMPT_QUEUE_CAP = 400;
let promptSourceFilter = "";
let promptSignatureFilter = "";
let promptFacetFilters = emptyPromptFacetFilters();
let promptBlueprintOnly = false;
let promptVaultOpen = true;
let promptPage = 0;
let promptSort = "preview_newest";
let promptSelectionMode = false;
let selectedPromptIds = new Set();
let promptSelectAllFiltered = false;
const PROMPT_PAGE_SIZE = 72;
const CATALOG_YEARBOOK_DIMENSION_PRESETS = [
    ["400x500", "400 × 500 · Fast", 400, 500],
    ["512x640", "512 × 640 · Light", 512, 640],
    ["800x1000", "800 × 1000 · Medium", 800, 1000],
    ["1024x1280", "1024 × 1280 · Large", 1024, 1280],
    ["1440x1920", "1440 × 1920 · Ollie", 1440, 1920],
    ["custom", "Custom dimensions", null, null],
];
let fragmentRows = [];
let fragmentSummary = { total: 0, roles: {}, states: {}, sources: {} };
let fragmentTotal = 0;
let fragmentLoading = false;
let fragmentLoadSerial = 0;
let fragmentLoadTimer = null;
let fragmentSearch = "";
let fragmentRole = "";
let fragmentState = "ready";
let fragmentSort = "rank";
let fragmentPage = 0;
const FRAGMENT_PAGE_SIZE = 96;
let fragmentSelectionMode = false;
let fragmentSelectAllFiltered = false;
let selectedFragmentIds = new Set();
const FRAGMENT_ROLE_META = {
    prefix: ["PREFIX", "#ff9b5f"], identity_hook: ["IDENTITY HOOK", "#f2df55"], subject: ["SUBJECT", "#ff78bd"], subject_structure: ["LEGACY SUBJECT SHELL", "#8f8997"],
    capture_medium: ["CAPTURE / MEDIUM", "#67e8f9"], appearance: ["APPEARANCE", "#fb9ac6"], hair_makeup: ["HAIR / MAKEUP", "#ff8fce"],
    concept: ["CONCEPT / THEME", "#b89aff"],
    style: ["STYLE", "#35d7ff"], composition: ["COMPOSITION", "#7dd3fc"], pose_action: ["POSE / ACTION", "#f6e65a"],
    expression_mood: ["EXPRESSION / MOOD", "#ff8fce"], environment: ["ENVIRONMENT", "#63e6a4"],
    body_styling: ["BODY STYLING", "#ff9b5f"], accessory: ["ACCESSORY", "#f6e65a"],
    wardrobe_hook: ["OUTFIT HOOK", "#f6e65a"], scene_hook: ["SCENE HOOK", "#63e6a4"], brand_hook: ["BRAND HOOK", "#ff9b5f"],
    lighting: ["LIGHTING", "#facc15"], time_atmosphere: ["TIME / ATMOSPHERE", "#a5b4fc"], camera: ["CAMERA", "#67e8f9"],
    typography: ["TYPOGRAPHY", "#fb7185"], color_effects: ["COLOR / EFFECTS", "#c084fc"], suffix: ["SUFFIX", "#ff9b5f"],
};
const PROMPT_GALLERY_FAMILIES = [
    { axis: "concept", label: "CONCEPT", color: "#ff4ab8", values: ["UV Night", "Nest Roll", "Electric Forest", "Tactile Fever", "Love Fever", "Oil Realm", "UV House", "Neon", "Roadtrip", "Vintage Magazine", "Faceout", "Sick Light", "Suburban", "Vaporwave", "Y2K", "Bad Date Night"] },
    { axis: "style", label: "STYLE", color: "#35d7ff", values: ["Candid", "Analog", "Point-and-Shoot", "Phone", "High-Key Flash", "Cinematic", "Editorial", "Poster", "Magazine", "Psychedelic", "Photoreal", "Fashion", "Graphic", "Surreal", "Minimal"] },
    { axis: "content", label: "CONTENT", color: "#f6e65a", values: ["Nude / Bare", "Multi-Subject", "Foot Focus", "Typography", "No Typography"] },
    { axis: "time", label: "TIME", color: "#b89aff", values: ["Night", "Dusk", "Dawn", "Golden Hour", "Daylight"] },
    { axis: "structure", label: "SHOT", color: "#7dd3fc", values: ["Portrait", "Close-up", "Full body", "Candid", "Editorial", "Environment", "Concept"] },
    { axis: "scene", label: "WORLD", color: "#63e6a4", values: ["Studio", "Interior", "Urban", "Nature", "Night", "Travel", "Water"] },
    { axis: "mood", label: "MOOD", color: "#ff8fce", values: ["Playful", "Soft", "Bold", "Dark", "Calm", "Energetic", "Romantic"] },
];
let collections = [];
let promptShowcaseCollections = { prompt: [], template: [] };
let boards = [];
let builderDraft = {
    board_id: "",
    recipe_id: "",
    source_prompt_id: "",
    source_prompt_name: "",
    source_prompt_text: "",
    fragments: [],
    outfit_component_id: "",
    outfit_value: "",
    scene_component_id: "",
    scene_value: "",
    outfit_destination: "A",
};
let workshopAssemblyOpen = false;
let componentCollections = { outfit: [], scene: [] };
let libraryCollections = { outfit: [], scene: [], wardrobe: [] };
let activeLibraryCollection = { outfit: "", scene: "", wardrobe: "" };
let derivedValues = { outfits: [], scenes: [], logs: {} };
let activeView = "recipes";
let activeToken = "";
let activeCollection = "";
const AUTO_OUTFITS = "__recipe_outfits__";
const AUTO_SCENES = "__recipe_scenes__";
let selectionMode = false;
let selectedRecipeIds = new Set();
let selectedComponentIds = new Set();
const COMPONENT_PAGE_SIZE = 96;
let componentPage = { outfit: 0, scene: 0 };
let componentSearch = { outfit: "", scene: "" };
let componentRatingFilter = { outfit: "", scene: "" };
let componentThumbnailFilter = { outfit: "", scene: "" };
let componentSort = { outfit: "preview_newest", scene: "preview_newest" };
let wardrobeItems = [];
let outfitMode = "pieces";
let wardrobeCategory = "";
let wardrobeSubtype = "";
let wardrobeSearch = "";
let wardrobeRatingFilter = "";
let wardrobeThumbnailFilter = "";
let wardrobeReviewFilter = "";
let wardrobeSort = "preview_newest";
let wardrobePage = 0;
let wardrobeSelectionMode = false;
let selectedWardrobeIds = new Set();
let wardrobeSelectAllFiltered = false;
let wardrobeBuilder = [];
let wardrobeBuilderOpen = true;
let wardrobeMigrationStatus = { total: 0, accepted: 0, ignored: 0, pending: 0, new: 0 };
const WARDROBE_FINISHERS = ["barefoot", "bare legs", "otherwise bare", "completely naked everywhere else"];
const WARDROBE_COLORS = ["black", "white", "cream", "gray", "brown", "tan", "red", "orange", "yellow", "green", "olive", "blue", "navy", "purple", "pink"];
const WARDROBE_PATTERNS = ["plaid", "tartan", "gingham", "striped", "pinstriped", "checkered", "floral", "polka-dot", "heart-print", "animal-print", "camouflage", "tie-dye", "ombré", "color-blocked"];
const WARDROBE_CUTS = ["cropped", "fitted", "oversized", "high-waisted", "low-rise", "mini", "micro", "midi", "maxi"];
const WARDROBE_WEAR = ["worn underneath", "layered over", "peeking out beneath"];
const WARDROBE_MATERIALS = ["cotton", "jersey", "ribbed cotton", "knit", "denim", "satin", "silk", "lace", "mesh", "sheer mesh", "velvet", "leather", "suede", "vinyl"];
const WARDROBE_GRAPHICS = [
    'a small chest graphic',
    'a large front graphic',
    'an embroidered logo',
    'an all-over graphic print',
    'a graphic that reads "BRAND"',
    'a graphic that reads "NAME"',
];
const WARDROBE_TAXONOMY = {
    "Tops": ["Tees", "Tanks & Camis", "Shirts & Blouses", "Sweaters"],
    "Layers": ["Hoodies & Sweatshirts", "Cardigans", "Jackets", "Coats", "Robes", "Aprons"],
    "Bottoms": ["Shorts", "Skirts", "Pants", "Jeans", "Underwear Bottoms"],
    "Dresses & One-Pieces": ["Dresses", "Rompers", "Jumpsuits"],
    "Bodywear": ["Bodysuits", "Leotards", "Teddies", "Chemises & Slips", "Catsuits", "Corsets & Bustiers"],
    "Legwear": ["Ankle Socks", "Crew Socks", "Knee Socks", "Thigh-Highs", "Stockings", "Tights", "Leg Warmers"],
    "Footwear": ["Sneakers", "Boots", "Flats & Mary Janes", "Heels", "Slippers", "Sandals"],
    "Accessories": ["Jewelry", "Chokers & Collars", "Body Chains", "Harnesses", "Gloves", "Arm Warmers", "Belts", "Headwear"],
    "Matching Sets": ["Lingerie Sets", "Sleepwear Sets", "Coordinated Sets"],
    "Other": ["Uncategorized"],
};
const WARDROBE_STYLING_TAXONOMY = ["Body Paint & Markings", "Skin Finish", "Metallic & Chrome", "Glow, Glitter & Shimmer"];
const FILTER_TOKENS = ["", "NAME", "OUTFIT", "BRAND", "SCENE", "LOCATION", "RARE_EVENT", "LIGHT_SOURCE", "ANALOG_CAPTURE_STYLE", "PRACTICAL_OUTER_LAYER", "SMALL_STYLING_DETAILS", "NATURAL_SURFACE", "TRIGGER"];
const LIBRARY_VIEWS = {
    recipes: { label: "TEMPLATES", color: "#ff4ab8", description: "Every placeholder-bearing source formula, organized by Category → optional Subcategory → Log." },
    prompts: { label: "PROMPTS", color: "#35d7ff", description: "Fully resolved, token-free prompt assets organized by Category → optional Subcategory → Log." },
    outfits: { label: "OUTFITS", color: "#f6e65a", description: "Universal wardrobe assets. Load any entry into Outfit A, B, or C." },
    scenes: { label: "SCENES", color: "#63e6a4", description: "Universal location assets. Load any entry directly into Scene." },
};
const PREVIEW_TYPE = "SOFitPreviewStudio";
const OUTPUT_TYPE = "SOOutputBuilderSaveStudio";
const CREATIVE_YEARBOOK_OUTPUT_ROOT = "Sick Ollie Yearbooks/Creative Library";
const PREVIEW_IMAGES_PROPERTY = "so_fit_preview_images";
const PREVIEW_INDEX_PROPERTY = "so_fit_preview_index";
const PREVIEW_UPDATED_PROPERTY = "so_fit_preview_updated_at";
const CATALOG_OUTFIT_PROMPT_KEY = "sickollie.recipe.catalogOutfitPrompt";
const CATALOG_SCENE_PROMPT_KEY = "sickollie.recipe.catalogScenePrompt";
const LEGACY_CATALOG_OUTFIT_PROMPT = "Clean ecommerce catalog photograph of the complete clothing outfit: OUTFIT. Every garment, shoe, sock, and accessory arranged together as a coordinated flat lay, each piece fully visible and separated, centered composition, seamless warm-white background, soft commercial studio lighting, crisp fabric texture, accurate colors, premium online clothing shop presentation.";
const DEFAULT_CATALOG_OUTFIT_PROMPT = "Clean ecommerce catalog flat-lay photograph of OUTFIT, centered on a flat color solid dark #000000 black background, crisp detail.";
const LEGACY_CATALOG_SCENE_PROMPT = "Wide establishing reference photograph of SCENE. The environment itself is the sole visual subject, clear spatial layout, believable materials and objects, natural depth, balanced composition, detailed location photography.";
const DEFAULT_CATALOG_SCENE_PROMPT = "Clean reference photograph of SCENE, crisp detail.";
let catalogRun = null;
let catalogRunSerial = 0;
let lastCatalogPreviewKey = "";
let lastCatalogPreviewAt = 0;
const CATALOG_THEATER_ENABLED_KEY = "sickollie.recipe.catalogTheaterEnabled";
const CATALOG_THEATER_SIZE_KEY = "sickollie.recipe.catalogTheaterSize";

function catalogTheaterEnabledByDefault() { return localStorage.getItem(CATALOG_THEATER_ENABLED_KEY) !== "false"; }
function catalogTheaterInitialSize() {
    const value = String(localStorage.getItem(CATALOG_THEATER_SIZE_KEY) || "fit");
    return ["fit", "fill", "actual"].includes(value) ? value : "fit";
}
function creativeTheaterEntryKey(item) {
    const kind = String(item?.kind || "");
    if (["prompt", "template"].includes(kind)) return `${kind}:${String(item?.prompt_id || item?.value || "")}`;
    if (kind === "piece") return `${kind}:${String(item?.wardrobe_id || item?.value || "")}`;
    return `${kind}:${String(item?.component_id || item?.value || "")}`;
}
function creativeLibraryPreviewUrl(previewRef, version = "") {
    const ref = String(previewRef || "");
    if (!ref) return "";
    const suffix = version === "" ? "" : `?v=${encodeURIComponent(String(version))}`;
    return `${API}/preview/${encodeURIComponent(ref)}${suffix}`;
}
function isCreativeLibraryPackPreviewSource(source) {
    return /^(?:pack|library-pack|creative-library-pack):/i.test(String(source || ""));
}
function creativeTheaterPreviewUrl(item) {
    const previewRef = String(item?.catalog_preview_ref || item?.preview_ref || "");
    if (!previewRef) return "";
    const version = String(item?.preview_updated_at || item?.updated_at || Date.now());
    return creativeLibraryPreviewUrl(previewRef, version);
}
function creativeTheaterLiveAsset(item) {
    const kind = String(item?.kind || "");
    if (["prompt", "template"].includes(kind)) return promptAssets.find(asset => String(asset?.prompt_id || "") === String(item?.prompt_id || "")) || item;
    if (kind === "piece") return wardrobeItems.find(asset => String(asset?.wardrobe_id || "") === String(item?.wardrobe_id || "")) || item;
    const rows = kind === "scene" ? (derivedValues.scenes || []) : (derivedValues.outfits || []);
    const componentId = String(item?.component_id || "");
    if (componentId) return rows.find(asset => String(asset?.component_id || "") === componentId) || item;
    const value = String(item?.value || "").trim().toLocaleLowerCase();
    return rows.find(asset => String(asset?.value || "").trim().toLocaleLowerCase() === value) || item;
}
function creativeTheaterCurrent(run) {
    const theater = run?.theater;
    if (!theater?.entries?.length) return null;
    theater.cursor = Math.max(0, Math.min(theater.entries.length - 1, Number(theater.cursor ?? theater.entries.length - 1)));
    return theater.entries[theater.cursor] || null;
}
function closeCreativeTheater(run) {
    const theater = run?.theater;
    if (!theater?.overlay) return;
    theater.dismissed = true;
    theater.overlay.remove();
    theater.overlay = null; theater.ui = null;
    recoverTextInputFocus();
}
function applyCreativeTheaterSizing(run) {
    const theater = run?.theater;
    const ui = theater?.ui;
    if (!ui) return;
    const mode = theater.sizeMode || "fit";
    localStorage.setItem(CATALOG_THEATER_SIZE_KEY, mode);
    ui.frame.style.overflow = mode === "actual" ? "auto" : "hidden";
    if (mode === "actual") {
        Object.assign(ui.image.style, { width: "auto", height: "auto", maxWidth: "none", maxHeight: "none", objectFit: "contain", margin: "auto" });
    } else {
        Object.assign(ui.image.style, { width: "100%", height: "100%", maxWidth: "100%", maxHeight: "100%", objectFit: mode === "fill" ? "cover" : "contain", margin: "0" });
    }
    for (const [name, button] of Object.entries(ui.sizeButtons || {})) {
        const active = name === mode;
        button.style.background = active ? "rgba(53,215,255,.18)" : "#211d27";
        button.style.borderColor = active ? "#35d7ff" : "#4a4452";
        button.style.color = active ? "#dffbff" : "#b8b0c1";
    }
}
function updateCreativeTheater(run) {
    const theater = run?.theater;
    const ui = theater?.ui;
    if (!ui) return;
    const entry = creativeTheaterCurrent(run);
    const completed = Boolean(run.completed);
    const stopped = Boolean(run.stopped && !run.completed);
    ui.runState.textContent = completed ? "● COMPLETE" : stopped ? "● STOPPED" : "● RUNNING";
    ui.runState.style.color = completed ? "#6ee7a2" : stopped ? "#f6e65a" : "#ff78bd";
    const generated = theater.entries.length;
    const reviewed = theater.entries.filter(value => value.reviewed).length;
    const rejected = theater.entries.filter(value => value.rejected).length;
    const waiting = Math.max(0, generated - reviewed);
    ui.stats.textContent = `GENERATED ${generated.toLocaleString()} / ${Number(run.items?.length || 0).toLocaleString()} · REVIEWED ${reviewed.toLocaleString()} · REJECTED ${rejected.toLocaleString()} · WAITING ${waiting.toLocaleString()}`;
    ui.position.textContent = entry ? `${theater.cursor + 1} / ${generated}` : "0 / 0";
    ui.live.textContent = theater.live ? "● LIVE" : "❚❚ FROZEN";
    ui.live.style.borderColor = theater.live ? "#63e6a4" : "#f6e65a";
    ui.live.style.color = theater.live ? "#9ff5c8" : "#fff29a";
    ui.previous.disabled = !entry || theater.cursor <= 0;
    ui.next.disabled = !entry || theater.cursor >= generated - 1;
    if (!entry) {
        ui.image.removeAttribute("src"); ui.image.hidden = true; ui.empty.hidden = false;
        ui.title.textContent = "Waiting for the first Catalog thumbnail…";
        ui.kind.textContent = "THEATER MODE · LIVE";
        ui.text.textContent = "The newest completed thumbnail will appear here automatically.";
        ui.reject.disabled = true;
        for (const star of ui.stars) star.disabled = true;
        return;
    }
    ui.empty.hidden = true; ui.image.hidden = false;
    const url = creativeTheaterPreviewUrl(entry.item);
    if (url && ui.image.src !== new URL(url, window.location.href).href) ui.image.src = url;
    const kind = String(entry.item.kind || "asset").toUpperCase();
    ui.kind.textContent = `${kind} · ${theater.live ? "FOLLOWING NEWEST" : "REVIEWING HISTORY"}`;
    ui.title.textContent = String(entry.item.primary_subcategory || entry.item.name || entry.item.model_name || entry.item.value || kind);
    ui.text.textContent = String(entry.item.value || entry.item.name || "");
    const rating = Math.max(0, Math.min(5, Number(entry.rating || 0)));
    for (let index = 0; index < ui.stars.length; index += 1) {
        const button = ui.stars[index]; const value = index + 1; button.disabled = Boolean(entry.busy); button.textContent = value <= rating ? "★" : "☆"; button.style.color = value <= rating ? "#f6e65a" : "#756d7a";
    }
    ui.reject.disabled = Boolean(entry.busy);
    ui.reject.textContent = entry.rejected ? "UNDO REJECT [X]" : "REJECT [X]";
    ui.reject.style.background = entry.rejected ? "rgba(255,74,184,.22)" : "#211d27";
    ui.reject.style.borderColor = entry.rejected ? "#ff4ab8" : "#ff4ab899";
    applyCreativeTheaterSizing(run);
}
async function setCreativeTheaterRating(run, entry, rating) {
    if (!entry || entry.busy) return;
    const value = Math.max(0, Math.min(5, Number(rating || 0)));
    entry.busy = true; updateCreativeTheater(run);
    try {
        const item = entry.item; const kind = String(item?.kind || ""); let result = null;
        if (["prompt", "template"].includes(kind) && item.prompt_id) result = await request(`/prompt-assets/${encodeURIComponent(item.prompt_id)}/rating`, { method: "POST", body: JSON.stringify({ rating: value }) });
        else if (["outfit", "scene"].includes(kind) && item.component_id) result = await request(`/derived-values/${encodeURIComponent(item.component_id)}/rating`, { method: "POST", body: JSON.stringify({ rating: value }) });
        else if (kind === "piece" && item.wardrobe_id) result = await request(`/wardrobe-items/${encodeURIComponent(item.wardrobe_id)}/rating`, { method: "POST", body: JSON.stringify({ rating: value }) });
        else throw new Error("This Catalog item does not expose a persistent rating yet.");
        entry.rating = Number(result?.rating ?? value); entry.reviewed = true; item.rating = entry.rating;
        const live = creativeTheaterLiveAsset(item); if (live) live.rating = entry.rating;
        updateCreativeTheater(run);
    } catch (error) { alert(error.message || "Could not save this Theater rating."); }
    finally { entry.busy = false; updateCreativeTheater(run); }
}
async function ensureCreativeRejectedCollection(kind) {
    if (["prompt", "template"].includes(kind)) {
        const folders = promptShowcaseFolders(kind);
        let collection = folders.find(item => String(item?.name || "").trim().toLocaleLowerCase() === "rejected");
        if (!collection) {
            const result = await request("/showcase-collections", { method: "POST", body: JSON.stringify({ kind, name: "Rejected" }) });
            collection = result?.collection;
            if (collection?.collection_id) { folders.push(collection); folders.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" })); }
        }
        return collection || null;
    }
    if (["outfit", "scene"].includes(kind)) {
        let collection = (componentCollections[kind] || []).find(item => !String(item?.parent_id || "") && String(item?.name || "").trim().toLocaleLowerCase() === "rejected");
        if (!collection) {
            const result = await request("/component-collections", { method: "POST", body: JSON.stringify({ kind, name: "Rejected", parent_id: "" }) });
            collection = result?.collection;
            if (collection?.collection_id) componentCollections[kind] = [...(componentCollections[kind] || []), collection];
        }
        return collection || null;
    }
    return null;
}
async function toggleCreativeTheaterReject(run, entry) {
    if (!entry || entry.busy) return;
    const item = entry.item; const kind = String(item?.kind || "");
    entry.busy = true; updateCreativeTheater(run);
    try {
        if (kind === "piece") {
            const nextRating = entry.rejected ? Number(entry.previousRating || 0) : 1;
            if (!entry.rejected) entry.previousRating = Number(entry.rating || 0);
            if (!item.wardrobe_id) throw new Error("This Wardrobe item cannot be rejected because it has no persistent ID.");
            const result = await request(`/wardrobe-items/${encodeURIComponent(item.wardrobe_id)}/rating`, { method: "POST", body: JSON.stringify({ rating: nextRating }) });
            entry.rating = Number(result?.rating ?? nextRating); item.rating = entry.rating; const live = creativeTheaterLiveAsset(item); if (live) live.rating = entry.rating;
            entry.rejected = !entry.rejected; entry.reviewed = true; return;
        }
        const collection = await ensureCreativeRejectedCollection(kind);
        const collectionId = String(collection?.collection_id || "");
        if (!collectionId) throw new Error("Could not create or find the Rejected collection.");
        const currentCollections = Array.isArray(item.collections) ? [...item.collections] : [];
        if (!entry.rejected) {
            if (["prompt", "template"].includes(kind)) await request("/prompt-assets/bulk/collections", { method: "POST", body: JSON.stringify({ kind, prompt_ids: [String(item.prompt_id || "")], collection_ids: [collectionId] }) });
            else await request("/derived-values/bulk/collections", { method: "POST", body: JSON.stringify({ component_ids: [String(item.component_id || "")], collection_ids: [collectionId] }) });
            if (!currentCollections.some(value => String(value?.collection_id || "") === collectionId)) currentCollections.push(collection);
            item.collections = currentCollections; const live = creativeTheaterLiveAsset(item); if (live) live.collections = currentCollections;
            entry.rejected = true; entry.reviewed = true;
        } else {
            const remaining = currentCollections.filter(value => String(value?.collection_id || "") !== collectionId);
            if (["prompt", "template"].includes(kind)) await request("/prompt-assets/bulk/collections/remove", { method: "POST", body: JSON.stringify({ kind, prompt_ids: [String(item.prompt_id || "")], collection_ids: [collectionId] }) });
            else await request("/derived-values/bulk/collections/remove", { method: "POST", body: JSON.stringify({ component_ids: [String(item.component_id || "")], collection_ids: [collectionId] }) });
            item.collections = remaining; const live = creativeTheaterLiveAsset(item); if (live) live.collections = remaining;
            entry.rejected = false; entry.reviewed = true;
        }
    } catch (error) { alert(error.message || "Could not update the Rejected collection."); }
    finally { entry.busy = false; updateCreativeTheater(run); }
}
function creativeTheaterItemRejected(item) {
    const kind = String(item?.kind || "");
    if (kind === "piece") return false;
    return (Array.isArray(item?.collections) ? item.collections : []).some(value => String(value?.name || "").trim().toLocaleLowerCase() === "rejected");
}
function appendCreativeTheaterEntry(run, item) {
    if (!run?.theaterEnabled) return;
    if (!run.theater) run.theater = { entries: [], cursor: -1, live: true, sizeMode: catalogTheaterInitialSize(), overlay: null, ui: null, dismissed: false };
    const theater = run.theater; const key = creativeTheaterEntryKey(item);
    let entry = theater.entries.find(value => value.key === key);
    if (!entry) { entry = { key, item, rating: Number(item?.rating || 0), rejected: creativeTheaterItemRejected(item), reviewed: false, busy: false, previousRating: Number(item?.rating || 0) }; theater.entries.push(entry); }
    else { entry.item = item; entry.rating = Number(item?.rating ?? entry.rating ?? 0); }
    if (theater.live || theater.cursor < 0) theater.cursor = theater.entries.length - 1;
    if (!theater.overlay && !theater.dismissed) openCreativeTheater(run); else updateCreativeTheater(run);
}
function openCreativeTheater(run = catalogRun) {
    if (!run || !run.theaterEnabled) return;
    if (!run.theater) run.theater = { entries: [], cursor: -1, live: true, sizeMode: catalogTheaterInitialSize(), overlay: null, ui: null, dismissed: false };
    const theater = run.theater;
    theater.dismissed = false;
    if (theater.overlay?.isConnected) { updateCreativeTheater(run); theater.overlay.focus(); return; }
    const overlay = document.createElement("div"); overlay.dataset.soCatalogTheater = ""; overlay.tabIndex = -1;
    Object.assign(overlay.style, { position: "fixed", inset: "0", zIndex: "100090", display: "flex", alignItems: "center", justifyContent: "center", padding: "18px", background: "rgba(1,1,4,.91)", backdropFilter: "blur(10px) saturate(.7)", color: "#f6f2f8" });
    const card = document.createElement("section"); Object.assign(card.style, { width: "min(1500px,calc(100vw - 36px))", height: "min(1120px,calc(100vh - 36px))", minHeight: "520px", display: "grid", gridTemplateRows: "auto minmax(0,1fr) auto", overflow: "hidden", borderRadius: "18px", border: "1px solid #b89aff88", background: "linear-gradient(160deg,#15101c,#08070c 60%)", boxShadow: "0 32px 110px rgba(0,0,0,.78),0 0 42px rgba(184,154,255,.12)" });
    const head = document.createElement("header"); Object.assign(head.style, { display: "flex", alignItems: "center", gap: "12px", padding: "12px 14px", borderBottom: "1px solid #3b3341", background: "rgba(19,15,24,.96)" });
    const headText = document.createElement("div"); headText.style.flex = "1"; const eyebrow = document.createElement("div"); eyebrow.textContent = "SICK OLLIE · THEATER MODE"; Object.assign(eyebrow.style, { color: "#b89aff", font: "900 9px Segoe UI,Arial", letterSpacing: ".14em" });
    const title = document.createElement("div"); Object.assign(title.style, { marginTop: "3px", color: "#fff", font: "900 15px Segoe UI,Arial", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }); headText.append(eyebrow, title);
    const runState = document.createElement("span"); Object.assign(runState.style, { font: "900 9px Segoe UI,Arial", letterSpacing: ".09em" });
    const position = document.createElement("span"); Object.assign(position.style, { minWidth: "58px", color: "#9b93a2", textAlign: "right", font: "800 10px Segoe UI,Arial" });
    const close = action("×", "#8f8997"); Object.assign(close.style, { width: "34px", height: "34px", padding: "0", fontSize: "18px" }); close.title = "Close Theater Mode; Preview Run continues"; close.onclick = () => closeCreativeTheater(run);
    head.append(headText, runState, position, close);
    const center = document.createElement("div"); Object.assign(center.style, { minHeight: "0", display: "grid", gridTemplateRows: "minmax(0,1fr) auto", padding: "12px", gap: "9px" });
    const frame = document.createElement("div"); Object.assign(frame.style, { minHeight: "0", position: "relative", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", borderRadius: "12px", border: "1px solid #2d2733", background: "#020204" });
    const image = document.createElement("img"); image.alt = "Newest Catalog thumbnail"; image.draggable = false; image.hidden = true; frame.append(image);
    const empty = document.createElement("div"); empty.textContent = "Waiting for the first thumbnail…"; Object.assign(empty.style, { color: "#756d7a", font: "800 13px Segoe UI,Arial", letterSpacing: ".04em" }); frame.append(empty);
    const info = document.createElement("div"); Object.assign(info.style, { display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: "10px", alignItems: "center" });
    const infoText = document.createElement("div"); const kind = document.createElement("div"); Object.assign(kind.style, { color: "#63e6a4", font: "900 8px Segoe UI,Arial", letterSpacing: ".1em" });
    const details = document.createElement("details"); const summary = document.createElement("summary"); summary.textContent = "SHOW SOURCE TEXT"; Object.assign(summary.style, { cursor: "pointer", color: "#8f8997", font: "800 8px Segoe UI,Arial", letterSpacing: ".07em" }); const text = document.createElement("div"); Object.assign(text.style, { maxHeight: "88px", overflow: "auto", marginTop: "6px", color: "#bdb5c2", font: "10px/1.45 Segoe UI,Arial" }); details.append(summary, text); infoText.append(kind, details);
    const sizeWrap = document.createElement("div"); Object.assign(sizeWrap.style, { display: "flex", gap: "5px" }); const sizeButtons = {};
    for (const [name, label] of [["fit", "FIT"], ["fill", "FILL"], ["actual", "ACTUAL"]]) { const button = action(label, "#4a4452"); Object.assign(button.style, { padding: "6px 9px", fontSize: "8px" }); button.onclick = () => { theater.sizeMode = name; applyCreativeTheaterSizing(run); }; sizeButtons[name] = button; sizeWrap.append(button); }
    info.append(infoText, sizeWrap); center.append(frame, info);
    const controls = document.createElement("footer"); Object.assign(controls.style, { display: "grid", gridTemplateColumns: "auto minmax(300px,1fr) auto", alignItems: "center", gap: "12px", padding: "12px 14px 14px", borderTop: "1px solid #3b3341", background: "rgba(13,10,18,.97)" });
    const nav = document.createElement("div"); Object.assign(nav.style, { display: "flex", gap: "6px", alignItems: "center" }); const previous = action("←", "#8f8997"); const next = action("→", "#8f8997"); const live = action("● LIVE", "#63e6a4"); previous.title = "Previous generated thumbnail · Left Arrow"; next.title = "Next generated thumbnail · Right Arrow"; live.title = "Space toggles Live / Frozen"; previous.onclick = () => { if (!theater.entries.length) return; theater.live = false; theater.cursor = Math.max(0, theater.cursor - 1); updateCreativeTheater(run); }; next.onclick = () => { if (!theater.entries.length) return; theater.live = false; theater.cursor = Math.min(theater.entries.length - 1, theater.cursor + 1); updateCreativeTheater(run); }; live.onclick = () => { theater.live = !theater.live; if (theater.live && theater.entries.length) theater.cursor = theater.entries.length - 1; updateCreativeTheater(run); }; nav.append(previous, next, live);
    const review = document.createElement("div"); Object.assign(review.style, { display: "flex", flexDirection: "column", alignItems: "center", gap: "7px" }); const stars = []; const starRow = document.createElement("div"); Object.assign(starRow.style, { display: "flex", justifyContent: "center", gap: "10px" });
    for (let value = 1; value <= 5; value += 1) { const star = document.createElement("button"); star.type = "button"; star.textContent = "☆"; star.title = `${value} star${value === 1 ? "" : "s"} · key ${value}`; Object.assign(star.style, { minWidth: "48px", padding: "2px 4px", border: "0", cursor: "pointer", background: "transparent", color: "#756d7a", font: "34px/1 Segoe UI Symbol,Segoe UI,Arial" }); star.onclick = () => { const entry = creativeTheaterCurrent(run); if (entry) void setCreativeTheaterRating(run, entry, value); }; stars.push(star); starRow.append(star); }
    const stats = document.createElement("div"); Object.assign(stats.style, { color: "#8f8997", font: "800 8px Segoe UI,Arial", letterSpacing: ".06em", textAlign: "center" }); review.append(starRow, stats);
    const reject = action("REJECT [X]", "#ff4ab8"); Object.assign(reject.style, { minWidth: "126px", padding: "10px 12px", fontSize: "9px" }); reject.title = "Add to the Rejected collection; X toggles"; reject.onclick = () => { const entry = creativeTheaterCurrent(run); if (entry) void toggleCreativeTheaterReject(run, entry); };
    controls.append(nav, review, reject); card.append(head, center, controls); overlay.append(card); document.body.append(overlay);
    theater.overlay = overlay; theater.ui = { title, runState, position, frame, image, empty, kind, text, sizeButtons, previous, next, live, stars, stats, reject };
    overlay.addEventListener("keydown", event => {
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        if (/^[1-5]$/.test(event.key)) { event.preventDefault(); const entry = creativeTheaterCurrent(run); if (entry) void setCreativeTheaterRating(run, entry, Number(event.key)); return; }
        if (event.key.toLowerCase() === "x") { event.preventDefault(); const entry = creativeTheaterCurrent(run); if (entry) void toggleCreativeTheaterReject(run, entry); return; }
        if (event.key === " ") { event.preventDefault(); theater.live = !theater.live; if (theater.live && theater.entries.length) theater.cursor = theater.entries.length - 1; updateCreativeTheater(run); return; }
        if (event.key === "ArrowLeft") { event.preventDefault(); if (theater.entries.length) { theater.live = false; theater.cursor = Math.max(0, theater.cursor - 1); updateCreativeTheater(run); } return; }
        if (event.key === "ArrowRight") { event.preventDefault(); if (theater.entries.length) { theater.live = false; theater.cursor = Math.min(theater.entries.length - 1, theater.cursor + 1); updateCreativeTheater(run); } return; }
        if (event.key === "Escape") { event.preventDefault(); closeCreativeTheater(run); }
    }, true);
    updateCreativeTheater(run); requestAnimationFrame(() => overlay.focus());
}

async function request(path, options = {}) {
    const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
    if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || `HTTP ${response.status}`);
    return response.json();
}

function action(label, color = "#35d7ff") { const b = document.createElement("button"); b.textContent = label; Object.assign(b.style, { padding: "8px 10px", borderRadius: "7px", cursor: "pointer", border: `1px solid ${color}aa`, color: "#fff", background: "#25232d", font: "700 11px Segoe UI, Arial" }); return b; }
function catalogPromptSetting(key, fallback, legacyValue = "") {
    const stored = String(localStorage.getItem(key) || "").trim();
    if (!stored || (legacyValue && stored === legacyValue)) {
        if (stored && stored !== fallback) localStorage.setItem(key, fallback);
        return fallback;
    }
    return stored;
}
function close() { const theaterRun = catalogRun; if (catalogRun) stopCatalogRun(false); closeCreativeTheater(theaterRun); document.querySelectorAll("[data-so-catalog-theater]").forEach(node => node.remove()); promptLoadSerial += 1; fragmentLoadSerial += 1; if (promptLoadTimer) clearTimeout(promptLoadTimer); if (fragmentLoadTimer) clearTimeout(fragmentLoadTimer); promptLoadTimer = null; fragmentLoadTimer = null; promptLoading = false; fragmentLoading = false; root?.remove(); root = null; selectionMode = false; fragmentSelectionMode = false; fragmentSelectAllFiltered = false; selectedRecipeIds.clear(); selectedComponentIds.clear(); selectedFragmentIds.clear(); }

function askRecipeName(defaultName = "New saved prompt") {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        Object.assign(overlay.style, { position: "fixed", inset: "0", zIndex: "100050", background: "rgba(0,0,0,.66)", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" });
        const card = document.createElement("section");
        Object.assign(card.style, { width: "430px", maxWidth: "92vw", padding: "15px", borderRadius: "12px", border: "1px solid #f6e65a99", background: "linear-gradient(145deg,#17131f,#0d0b12)", boxShadow: "0 24px 70px #000", color: "#f5f1f7" });
        const title = document.createElement("strong"); title.textContent = "SAVE PROMPT + SETTINGS TO LIBRARY"; Object.assign(title.style, { display: "block", color: "#f6e65a", letterSpacing: ".07em", font: "700 12px Segoe UI,Arial", marginBottom: "6px" });
        const help = document.createElement("div"); help.textContent = "Saves the current prompt, reusable placeholders, generation settings, and verified Preview image to Creative Library."; Object.assign(help.style, { color: "#aaa2b4", font: "11px/1.4 Segoe UI,Arial", marginBottom: "10px" });
        const input = document.createElement("input"); input.type = "text"; input.value = String(defaultName || "New saved prompt"); input.autocomplete = "off"; input.spellcheck = false;
        Object.assign(input.style, { boxSizing: "border-box", width: "100%", padding: "10px 11px", borderRadius: "8px", border: "1px solid #4a4452", outline: "none", color: "#fff", background: "#09080d", font: "12px Segoe UI,Arial" });
        const buttons = document.createElement("div"); Object.assign(buttons.style, { display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" });
        const cancel = action("Cancel", "#8f8997"); const save = action("Save to Library", "#f6e65a");
        let settled = false;
        const finish = value => { if (settled) return; settled = true; overlay.remove(); resolve(value); };
        const update = () => { save.disabled = !input.value.trim(); save.style.opacity = save.disabled ? ".45" : "1"; };
        cancel.onclick = () => finish(null);
        save.onclick = () => { const value = input.value.trim(); if (value) finish(value); };
        input.addEventListener("input", update);
        input.addEventListener("keydown", event => { if (event.key === "Escape") { event.preventDefault(); finish(null); } else if (event.key === "Enter" && !save.disabled) { event.preventDefault(); save.click(); } });
        overlay.addEventListener("pointerdown", event => { if (event.target === overlay) finish(null); });
        buttons.append(cancel, save); card.append(title, help, input, buttons); overlay.append(card); document.body.append(overlay); update();
        requestAnimationFrame(() => { input.focus(); input.select(); });
    });
}

function askBoardName(defaultName = "New creative board") {
    return new Promise(resolve => {
        const overlay = document.createElement("div");
        Object.assign(overlay.style, { position: "fixed", inset: "0", zIndex: "100055", background: "rgba(0,0,0,.68)", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" });
        const card = document.createElement("section");
        Object.assign(card.style, { width: "430px", maxWidth: "92vw", padding: "15px", borderRadius: "12px", border: "1px solid #ff4ab899", background: "linear-gradient(145deg,#17131f,#0d0b12)", boxShadow: "0 24px 70px #000", color: "#f5f1f7" });
        const title = document.createElement("strong"); title.textContent = "SAVE CREATIVE BOARD"; Object.assign(title.style, { display: "block", color: "#ff78bd", letterSpacing: ".07em", font: "800 12px Segoe UI,Arial", marginBottom: "6px" });
        const help = document.createElement("div"); help.textContent = "Boards remember editable Ingredient slots, a source Prompt or corpus Blueprint, an optional saved Recipe, Outfit, and Scene without rewriting any canonical source."; Object.assign(help.style, { color: "#aaa2b4", font: "11px/1.4 Segoe UI,Arial", marginBottom: "10px" });
        const input = document.createElement("input"); input.type = "text"; input.value = String(defaultName || "New creative board"); input.autocomplete = "off"; input.spellcheck = false;
        Object.assign(input.style, { boxSizing: "border-box", width: "100%", padding: "10px 11px", borderRadius: "8px", border: "1px solid #4a4452", outline: "none", color: "#fff", background: "#09080d", font: "12px Segoe UI,Arial" });
        const buttons = document.createElement("div"); Object.assign(buttons.style, { display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" });
        const cancel = action("Cancel", "#8f8997"); const save = action("Save board", "#ff4ab8");
        let settled = false;
        const finish = value => { if (settled) return; settled = true; overlay.remove(); resolve(value); };
        const update = () => { save.disabled = !input.value.trim(); save.style.opacity = save.disabled ? ".45" : "1"; };
        cancel.onclick = () => finish(null);
        save.onclick = () => { const value = input.value.trim(); if (value) finish(value); };
        input.addEventListener("input", update);
        input.addEventListener("keydown", event => { if (event.key === "Escape") { event.preventDefault(); finish(null); } else if (event.key === "Enter" && !save.disabled) { event.preventDefault(); save.click(); } });
        overlay.addEventListener("pointerdown", event => { if (event.target === overlay) finish(null); });
        buttons.append(cancel, save); card.append(title, help, input, buttons); overlay.append(card); document.body.append(overlay); update();
        requestAnimationFrame(() => { input.focus(); input.select(); });
    });
}

function newBuilderDraft() {
    return {
        board_id: "", recipe_id: "", source_prompt_id: "", source_prompt_name: "", source_prompt_text: "", fragments: [],
        outfit_component_id: "", outfit_value: "", scene_component_id: "", scene_value: "", outfit_destination: "A",
    };
}

function fragmentMeta(role) {
    return FRAGMENT_ROLE_META[String(role || "")] || [String(role || "CUSTOM").replaceAll("_", " ").toUpperCase(), "#b89aff"];
}

function builderFragments() {
    return Array.isArray(builderDraft.fragments) ? builderDraft.fragments : [];
}

function builderRecipe() {
    return recipes.find(recipe => String(recipe.recipe_id || "") === String(builderDraft.recipe_id || "")) || null;
}

function builderRecipeTemplate(recipe = builderRecipe()) {
    const promptNode = (recipe?.payload?.nodes || []).find(node => String(node?.type || "") === "SOPromptLogEngineStudio");
    const widgets = Array.isArray(promptNode?.widgets) ? promptNode.widgets : [];
    return String(widgets.find(widget => widget?.name === "manual_prompt")?.value || recipe?.payload?.summary?.prompt_template || "").trim();
}

function builderDestinationForRecipe(recipe) {
    const tokens = new Set(recipeTokens(recipe?.payload));
    if (tokens.has("OUTFIT") || tokens.has("OUTFIT_A")) return "A";
    if (tokens.has("OUTFIT_B")) return "B";
    if (tokens.has("OUTFIT_C")) return "C";
    return "A";
}

function replaceBuilderToken(text, token, value, aliases = []) {
    if (!value) return text;
    let output = String(text || "");
    for (const candidate of [token, ...aliases]) {
        const escaped = String(candidate || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        output = output.replace(new RegExp(`(?<![A-Za-z0-9_])(?:\\{${escaped}\\}|${escaped})(?![A-Za-z0-9_])`, "gi"), value);
    }
    return output;
}

function punctuateBuilderFragment(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    return /[.!?;:]$/.test(text) ? text : `${text}.`;
}

function builderTemplateText() {
    const slots = builderFragments();
    const sourceSlots = slots.filter(slot => slot?.source_segment);
    const prefixSlots = slots.filter(slot => String(slot?.role || "") === "prefix");
    const suffixSlots = slots.filter(slot => String(slot?.role || "") === "suffix");
    const contentSlots = slots.filter(slot => !["prefix", "suffix"].includes(String(slot?.role || "")));
    let text = "";
    if (sourceSlots.length) {
        for (const slot of contentSlots) {
            const value = String(slot?.value || "").trim();
            if (!value) continue;
            let separator = String(slot?.separator_before || "");
            if (!text) separator = "";
            else if (!separator || /^[,;.!?]*$/.test(separator.trim())) separator = separator || " ";
            const rendered = slot.source_segment ? value : String(slot?.role || "") === "concept" ? `Creative direction: ${value}.` : punctuateBuilderFragment(value);
            text += `${separator}${rendered}`;
        }
    } else {
        text = String(builderDraft.source_prompt_text || builderRecipeTemplate(builderRecipe()) || "").trim();
        for (const slot of contentSlots) {
            const value = String(slot?.value || "").trim();
            if (!value || text.toLowerCase().includes(value.toLowerCase())) continue;
            const sentence = String(slot?.role || "") === "concept" ? `Creative direction: ${value}.` : punctuateBuilderFragment(value);
            text = `${text}${text ? " " : ""}${sentence}`.trim();
        }
    }
    const prefix = prefixSlots.map(slot => String(slot?.value || "").trim()).filter(Boolean).join(" ");
    const suffix = suffixSlots.map(slot => String(slot?.value || "").trim()).filter(Boolean).join(" ");
    return [prefix, text, suffix].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();
}

function builderPreviewText() {
    let text = builderTemplateText();
    if (!text) return "Start with a Prompt, corpus Blueprint, saved Recipe, or any Ingredient. Every slot stays editable until you send it to Studio.";
    const destination = String(builderDraft.outfit_destination || "A").toUpperCase();
    const outfitToken = destination === "A" ? "OUTFIT" : `OUTFIT_${destination}`;
    text = replaceBuilderToken(text, outfitToken, String(builderDraft.outfit_value || ""), destination === "A" ? ["OUTFIT_A"] : []);
    text = replaceBuilderToken(text, "SCENE", String(builderDraft.scene_value || ""));
    return text;
}

function builderHasContent() {
    return Boolean(builderTemplateText() || builderDraft.outfit_value || builderDraft.scene_value);
}

function builderAsset(kind) {
    const rows = kind === "scene" ? (derivedValues.scenes || []) : (derivedValues.outfits || []);
    const componentId = String(builderDraft[`${kind}_component_id`] || "");
    const value = String(builderDraft[`${kind}_value`] || "");
    return rows.find(item => componentId && String(item.component_id || "") === componentId)
        || rows.find(item => value && String(item.value || "").toLowerCase() === value.toLowerCase())
        || null;
}

function normalizeBuilderDraft() {
    if (!builderDraft || typeof builderDraft !== "object") builderDraft = newBuilderDraft();
    builderDraft.source_prompt_id = String(builderDraft.source_prompt_id || "");
    builderDraft.source_prompt_name = String(builderDraft.source_prompt_name || "");
    builderDraft.source_prompt_text = String(builderDraft.source_prompt_text || "");
    builderDraft.fragments = (Array.isArray(builderDraft.fragments) ? builderDraft.fragments : []).filter(slot => slot && String(slot.value || "").trim()).map((slot, index) => ({
        instance_id: String(slot.instance_id || `builder-fragment:${Date.now()}:${index}`),
        fragment_id: String(slot.fragment_id || ""), role: String(slot.role || "custom"), value: String(slot.value || "").trim(), original_text: String(slot.original_text || ""),
        join_mode: String(slot.join_mode || "sentence"), preferred_position: Number(slot.preferred_position || 50),
        confidence: Number(slot.confidence || 0), review_state: String(slot.review_state || ""), source_kind: String(slot.source_kind || ""),
        separator_before: String(slot.separator_before || ""), source_segment: Boolean(slot.source_segment), locked: Boolean(slot.locked),
        multiple_allowed: slot.multiple_allowed !== false,
    }));
    const recipe = builderRecipe();
    if (!recipe && builderDraft.recipe_id) builderDraft.recipe_id = "";
    for (const kind of ["outfit", "scene"]) {
        const asset = builderAsset(kind);
        if (asset) {
            builderDraft[`${kind}_component_id`] = String(asset.component_id || "");
            builderDraft[`${kind}_value`] = String(asset.value || "");
        }
    }
    if (!["A", "B", "C"].includes(String(builderDraft.outfit_destination || "").toUpperCase())) builderDraft.outfit_destination = "A";
}

function selectBuilderRecipe(recipe) {
    if (!recipe) return;
    builderDraft.board_id = "";
    builderDraft.recipe_id = String(recipe.recipe_id || "");
    builderDraft.source_prompt_id = "";
    builderDraft.source_prompt_name = "";
    builderDraft.source_prompt_text = "";
    builderDraft.fragments = builderFragments().filter(slot => !slot.source_segment);
    builderDraft.outfit_destination = builderDestinationForRecipe(recipe);
    render();
    root?.querySelector("[data-builder-panel]")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    catalogStatus(`Saved Recipe selected: ${recipe.name}`, "#f6e65a");
}

function selectBuilderAsset(kind, asset) {
    if (!["outfit", "scene"].includes(kind) || !asset) return;
    builderDraft.board_id = "";
    builderDraft[`${kind}_component_id`] = String(asset.component_id || "");
    builderDraft[`${kind}_value`] = String(asset.value || "");
    render();
    catalogStatus(`${kind === "scene" ? "Scene" : "Outfit"} added to Builder.`, kind === "scene" ? "#63e6a4" : "#f6e65a");
}

function addBuilderFragment(fragment, options = {}) {
    if (!fragment || !String(fragment.value || "").trim()) return;
    normalizeBuilderDraft();
    const fragmentId = String(fragment.fragment_id || "");
    const role = String(fragment.role || "custom");
    if (fragmentId && builderDraft.fragments.some(slot => String(slot.fragment_id || "") === fragmentId && !slot.source_segment)) {
        catalogStatus("That Ingredient is already in this assembly.", "#b89aff"); return;
    }
    if (fragment.multiple_allowed === false) builderDraft.fragments = builderDraft.fragments.filter(slot => slot.source_segment || String(slot.role || "") !== role);
    const slot = {
        instance_id: `builder-fragment:${Date.now()}:${Math.random().toString(16).slice(2)}`,
        fragment_id: fragmentId, role, value: String(fragment.value || "").trim(), join_mode: String(fragment.join_mode || "sentence"),
        preferred_position: Number(fragment.preferred_position || 50), confidence: Number(fragment.confidence || 0),
        review_state: String(fragment.review_state || ""), source_kind: String(fragment.source_kind || ""), separator_before: " ",
        source_segment: false, locked: Boolean(options.locked), multiple_allowed: fragment.multiple_allowed !== false,
    };
    const insertAt = builderDraft.fragments.findIndex(item => !item.source_segment && Number(item.preferred_position || 50) > slot.preferred_position);
    if (insertAt < 0) builderDraft.fragments.push(slot); else builderDraft.fragments.splice(insertAt, 0, slot);
    builderDraft.board_id = "";
    if (options.render !== false) {
        render();
        root?.querySelector("[data-builder-panel]")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    }
    catalogStatus(`${fragmentMeta(role)[0]} Ingredient added to Builder.`, fragmentMeta(role)[1]);
}

function removeBuilderFragment(instanceId) {
    const slot = builderFragments().find(item => String(item.instance_id) === String(instanceId));
    if (slot?.locked) { catalogStatus("Unlock this Ingredient before removing it.", "#f6e65a"); return; }
    builderDraft.fragments = builderFragments().filter(item => String(item.instance_id) !== String(instanceId));
    builderDraft.board_id = ""; render();
}

function moveBuilderFragment(instanceId, direction) {
    const rows = builderFragments(); const index = rows.findIndex(item => String(item.instance_id) === String(instanceId));
    const target = index + Number(direction || 0);
    if (index < 0 || target < 0 || target >= rows.length || rows[index]?.locked) return;
    [rows[index], rows[target]] = [rows[target], rows[index]]; builderDraft.fragments = rows; builderDraft.board_id = ""; render();
}

function toggleBuilderFragmentLock(instanceId) {
    const slot = builderFragments().find(item => String(item.instance_id) === String(instanceId));
    if (!slot) return; slot.locked = !slot.locked; builderDraft.board_id = ""; render();
}

async function openPromptInBuilder(asset) {
    if (!asset?.prompt_id) return;
    if (String(asset.kind || "") === "template") {
        builderDraft = {
            ...newBuilderDraft(), source_prompt_id: String(asset.prompt_id || ""),
            source_prompt_name: String(asset.primary_subcategory || asset.name || "Template"),
            source_prompt_text: String(asset.value || ""), fragments: [],
        };
        workshopAssemblyOpen = true;
        activeView = "fragments";
        refreshLibraryChrome(); renderCollectionControls(); renderBulkControls(); render();
        if (!fragmentRows.length) queueFragmentPageLoad();
        root?.querySelector("[data-builder-panel]")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
        catalogStatus("Template loaded into Workshop with every placeholder intact.", "#ff4ab8");
        return;
    }
    try {
        catalogStatus("Decomposing Prompt into editable corpus roles…", "#35d7ff");
        const result = await request(`/fragments/decompose/${encodeURIComponent(asset.prompt_id)}`);
        builderDraft = {
            ...newBuilderDraft(), source_prompt_id: String(asset.prompt_id || ""), source_prompt_name: String(asset.name || "Prompt"),
            source_prompt_text: String(asset.value || ""), fragments: Array.isArray(result.segments) ? result.segments : [],
        };
        workshopAssemblyOpen = true;
        activeView = "fragments";
        refreshLibraryChrome(); renderCollectionControls(); renderBulkControls(); render();
        root?.querySelector("[data-builder-panel]")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
        catalogStatus(`Decomposed ${result.segments?.length || 0} clauses · ${result.matched || 0} linked to reusable Ingredients · ${result.fallback || 0} preserved as source clauses.`, "#6ee7a2");
    } catch (error) { alert(error.message || "Could not open this Prompt in the Builder."); }
}

function loadBuilderBoard(board) {
    const payload = board?.payload && typeof board.payload === "object" ? board.payload : {};
    builderDraft = {
        board_id: String(board?.board_id || ""),
        recipe_id: String(payload.recipe_id || ""),
        source_prompt_id: String(payload.source_prompt_id || ""),
        source_prompt_name: String(payload.source_prompt_name || ""),
        source_prompt_text: String(payload.source_prompt_text || ""),
        fragments: Array.isArray(payload.fragments) ? payload.fragments : [],
        outfit_component_id: String(payload.outfit_component_id || ""),
        outfit_value: String(payload.outfit_value || ""),
        scene_component_id: String(payload.scene_component_id || ""),
        scene_value: String(payload.scene_value || ""),
        outfit_destination: ["A", "B", "C"].includes(String(payload.outfit_destination || "").toUpperCase()) ? String(payload.outfit_destination).toUpperCase() : "A",
    };
    normalizeBuilderDraft();
    render();
    root?.querySelector("[data-builder-panel]")?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    catalogStatus(`Loaded Board: ${board.name}`, "#b89aff");
}

function clearBuilderDraft() {
    builderDraft = newBuilderDraft();
    render();
    catalogStatus("Builder cleared. Source assets were untouched.", "#8f8997");
}

async function saveBuilderBoard() {
    const recipe = builderRecipe();
    if (!builderHasContent()) { alert("Add a Prompt, corpus Blueprint, saved Recipe, Ingredient, Outfit, or Scene before saving this Board."); return; }
    const existing = boards.find(board => String(board.board_id || "") === String(builderDraft.board_id || ""));
    const concept = builderFragments().find(slot => String(slot.role || "") === "concept")?.value;
    const name = await askBoardName(existing?.name || builderDraft.source_prompt_name || recipe?.name || concept || "New creative board");
    if (!name) return;
    try {
        const result = await request("/boards", {
            method: "POST",
            body: JSON.stringify({
                board_id: String(builderDraft.board_id || ""),
                name,
                payload: {
                    recipe_id: String(builderDraft.recipe_id || ""),
                    recipe_name: String(recipe?.name || ""),
                    source_prompt_id: String(builderDraft.source_prompt_id || ""),
                    source_prompt_name: String(builderDraft.source_prompt_name || ""),
                    source_prompt_text: String(builderDraft.source_prompt_text || ""),
                    fragments: builderFragments().map(slot => ({ ...slot })),
                    outfit_component_id: String(builderDraft.outfit_component_id || ""),
                    outfit_value: String(builderDraft.outfit_value || ""),
                    scene_component_id: String(builderDraft.scene_component_id || ""),
                    scene_value: String(builderDraft.scene_value || ""),
                    outfit_destination: String(builderDraft.outfit_destination || "A"),
                },
            }),
        });
        builderDraft.board_id = String(result.board?.board_id || builderDraft.board_id || "");
        if (result.board) boards = [result.board, ...boards.filter(board => String(board.board_id || "") !== String(result.board.board_id || ""))];
        normalizeBuilderDraft();
        render();
        catalogStatus(`Saved Board: ${name}`, "#ff78bd");
    } catch (error) { alert(error.message || "Could not save this Board."); }
}

async function deleteBuilderBoard(board) {
    if (!board?.board_id || !confirm(`Delete Board “${board.name}”? Blueprints, prompts, Outfits, and Scenes stay untouched.`)) return;
    try {
        await request(`/boards/${encodeURIComponent(board.board_id)}`, { method: "DELETE" });
        if (String(builderDraft.board_id || "") === String(board.board_id)) builderDraft.board_id = "";
        boards = boards.filter(item => String(item.board_id || "") !== String(board.board_id || ""));
        render();
        catalogStatus(`Deleted Board: ${board.name}`, "#ff8fce");
    } catch (error) { alert(error.message || "Could not delete this Board."); }
}

function showBuilderBlueprintPicker() {
    const savedRecipes = recipes;
    const { overlay, card } = collectionModal("CHOOSE A STARTING FORMULA", "760px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "9px", overflow: "auto" });
    const help = document.createElement("div"); help.textContent = "Templates are canonical formulas with portable placeholder hooks. Saved Recipes are complete Studio generation states. Either can start this Workshop draft without changing its source."; Object.assign(help.style, { color: "#b8b0c1", font: "11px/1.45 Segoe UI,Arial" });
    const browse = action(`BROWSE ${Number(promptBlueprintTotal || 0).toLocaleString()} CORPUS BLUEPRINTS`, "#ff4ab8"); browse.onclick = () => { overlay.remove(); setActiveView("prompts"); openPromptVault({ blueprint: true }); };
    const savedLabel = document.createElement("strong"); savedLabel.textContent = `SAVED RECIPES · ${savedRecipes.length.toLocaleString()}`; Object.assign(savedLabel.style, { marginTop: "7px", color: "#f6e65a", font: "900 8px Segoe UI,Arial", letterSpacing: ".1em" });
    const search = document.createElement("input"); search.type = "search"; search.placeholder = "Search saved Recipes…"; Object.assign(search.style, { width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: "8px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", outline: "none" });
    const list = document.createElement("div"); Object.assign(list.style, { display: "flex", flexDirection: "column", gap: "6px", maxHeight: "58vh", overflow: "auto" });
    const draw = () => {
        list.replaceChildren();
        const needle = search.value.trim().toLowerCase();
        const rows = savedRecipes.filter(recipe => !needle || `${recipe.name || ""} ${builderRecipeTemplate(recipe)}`.toLowerCase().includes(needle)).slice(0, 160);
        if (!rows.length) { const empty = document.createElement("div"); empty.textContent = savedRecipes.length ? "No saved Recipes match this search." : "No saved Recipes yet. Canonical Templates remain available in their own tab."; Object.assign(empty.style, { padding: "20px", color: "#8f8997", textAlign: "center" }); list.append(empty); }
        for (const recipe of rows) {
            const item = document.createElement("button"); item.type = "button";
            Object.assign(item.style, { width: "100%", display: "grid", gridTemplateColumns: "1fr auto", gap: "8px 14px", padding: "10px 12px", borderRadius: "9px", cursor: "pointer", textAlign: "left", color: "#fff", border: `1px solid ${String(builderDraft.recipe_id) === String(recipe.recipe_id) ? "#ff4ab8" : "#3c3542"}`, background: String(builderDraft.recipe_id) === String(recipe.recipe_id) ? "rgba(255,74,184,.12)" : "#121017" });
            const name = document.createElement("strong"); name.textContent = recipe.name || "Recipe"; Object.assign(name.style, { color: "#ff9dce", fontSize: "11px" });
            const tokens = document.createElement("span"); tokens.textContent = recipeTokens(recipe.payload).filter(token => ["OUTFIT", "SCENE", "NAME", "BRAND"].includes(token)).join(" · "); Object.assign(tokens.style, { color: "#35d7ff", font: "800 8px Segoe UI,Arial" });
            const text = document.createElement("span"); text.textContent = builderRecipeTemplate(recipe); Object.assign(text.style, { gridColumn: "1 / -1", color: "#8f8997", font: "9px/1.35 Segoe UI,Arial", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
            item.append(name, tokens, text); item.onclick = () => { selectBuilderRecipe(recipe); overlay.remove(); }; list.append(item);
        }
    };
    search.oninput = draw; body.append(help, browse, savedLabel, search, list); card.append(body); draw(); requestAnimationFrame(() => search.focus());
}

function showBuilderIngredientPicker(kind) {
    if (!["outfit", "scene"].includes(kind)) return;
    const rows = kind === "scene" ? (derivedValues.scenes || []) : (derivedValues.outfits || []);
    const color = kind === "scene" ? "#63e6a4" : "#f6e65a";
    const label = kind === "scene" ? "SCENE" : "OUTFIT";
    const { overlay, card } = collectionModal(`CHOOSE ${label}`, "900px");
    card.style.borderColor = `${color}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "9px", overflow: "auto" });
    const help = document.createElement("div"); help.textContent = `${rows.length.toLocaleString()} canonical ${kind} assets are available. Search narrows the picker without changing source logs, ratings, collections, or previews.`; Object.assign(help.style, { color: "#b8b0c1", font: "11px/1.45 Segoe UI,Arial" });
    const search = document.createElement("input"); search.type = "search"; search.placeholder = `Search ${kind}s…`; Object.assign(search.style, { width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: "8px", border: `1px solid ${color}66`, background: "#09080d", color: "#fff", outline: "none" });
    const range = document.createElement("div"); Object.assign(range.style, { color: "#817b88", font: "8px Segoe UI,Arial", letterSpacing: ".04em" });
    const grid = document.createElement("div"); Object.assign(grid.style, { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(210px,100%),1fr))", gap: "8px", maxHeight: "58vh", overflow: "auto" });
    const draw = () => {
        grid.replaceChildren();
        const needle = search.value.trim().toLowerCase();
        const matches = rows.filter(asset => !needle || String(asset.value || "").toLowerCase().includes(needle));
        const visible = matches.slice(0, 160);
        range.textContent = matches.length > visible.length ? `Showing the first ${visible.length.toLocaleString()} of ${matches.length.toLocaleString()} matches · refine search for more` : `${matches.length.toLocaleString()} match${matches.length === 1 ? "" : "es"}`;
        for (const asset of visible) {
            const item = document.createElement("button"); item.type = "button";
            Object.assign(item.style, { minHeight: "82px", display: "grid", gridTemplateColumns: asset.preview_ref ? "54px 1fr" : "1fr", gap: "9px", alignItems: "center", padding: "8px", borderRadius: "9px", cursor: "pointer", textAlign: "left", color: "#fff", border: `1px solid ${color}44`, background: "linear-gradient(145deg,rgba(255,255,255,.025),#0d0b12)" });
            if (asset.preview_ref) { const image = document.createElement("img"); image.loading = "lazy"; image.decoding = "async"; image.src = creativeLibraryPreviewUrl(asset.preview_ref); image.alt = ""; Object.assign(image.style, { width: "54px", height: kind === "scene" ? "43px" : "67px", objectFit: "contain", borderRadius: "6px", background: "#000" }); item.append(image); }
            const text = document.createElement("span"); text.textContent = asset.value || label; Object.assign(text.style, { display: "-webkit-box", WebkitLineClamp: "4", WebkitBoxOrient: "vertical", overflow: "hidden", color: "#e8e2eb", font: "9px/1.35 Segoe UI,Arial" }); item.append(text);
            item.onclick = () => { selectBuilderAsset(kind, asset); overlay.remove(); }; grid.append(item);
        }
        if (!visible.length) { const empty = document.createElement("div"); empty.textContent = `No ${kind}s match this search.`; Object.assign(empty.style, { gridColumn: "1 / -1", padding: "28px", color: "#8f8997", textAlign: "center" }); grid.append(empty); }
    };
    search.oninput = draw; body.append(help, search, range, grid); card.append(body); draw(); requestAnimationFrame(() => search.focus());
}

function showBuilderFragmentPicker(initialRole = "") {
    const { overlay, card } = collectionModal("ADD A CORPUS INGREDIENT", "1040px");
    card.style.borderColor = "#b89aff99";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "9px", overflow: "auto" });
    const help = document.createElement("div"); help.textContent = "These are recurring authored clauses, source themes, and curated Prefix/Suffix seeds mined from the canonical Prompt corpus. Adding one creates an editable slot; it never changes the source Prompt."; Object.assign(help.style, { color: "#b8b0c1", font: "11px/1.45 Segoe UI,Arial" });
    const controls = document.createElement("div"); Object.assign(controls.style, { display: "grid", gridTemplateColumns: "minmax(150px,210px) 1fr minmax(130px,160px)", gap: "7px" });
    const role = makeSelect([["", "All roles"], ...Object.entries(FRAGMENT_ROLE_META).map(([value, meta]) => [value, meta[0]])], initialRole);
    const search = document.createElement("input"); search.type = "search"; search.placeholder = "Search exact language, theme, scene, camera…"; Object.assign(search.style, { minWidth: "0", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", outline: "none", background: "#09080d", color: "#fff" });
    const state = makeSelect([["ready", "Ready vocabulary"], ["review", "Needs review"], ["active", "All active"]], "ready");
    controls.append(role, search, state);
    const range = document.createElement("div"); Object.assign(range.style, { color: "#817b88", font: "8px Segoe UI,Arial", letterSpacing: ".04em" });
    const grid = document.createElement("div"); Object.assign(grid.style, { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(245px,100%),1fr))", gap: "8px", maxHeight: "51vh", overflow: "auto" });
    let serial = 0; let timer = null;
    const draw = async () => {
        const current = ++serial; grid.replaceChildren(); range.textContent = "Loading corpus vocabulary…";
        const params = new URLSearchParams({ limit: "120", offset: "0", state: state.value || "ready", sort: "rank" });
        if (role.value) params.set("role", role.value); if (search.value.trim()) params.set("q", search.value.trim());
        try {
            const data = await request(`/fragments?${params.toString()}`); if (current !== serial) return;
            const rows = Array.isArray(data.fragments) ? data.fragments : []; range.textContent = `${rows.length.toLocaleString()} shown · ${Number(data.total || 0).toLocaleString()} matches`;
            for (const fragment of rows) {
                const [label, color] = fragmentMeta(fragment.role); const item = document.createElement("div"); Object.assign(item.style, { minHeight: "116px", display: "flex", flexDirection: "column", gap: "7px", padding: "10px", borderRadius: "9px", border: `1px solid ${color}44`, background: `linear-gradient(145deg,${color}0e,#0d0b12)` });
                const meta = document.createElement("div"); meta.textContent = `${label} · ${Number(fragment.prompt_count || 0).toLocaleString()} PROMPTS · ${Number(fragment.source_count || 0).toLocaleString()} SOURCES`; Object.assign(meta.style, { color, font: "900 7px Segoe UI,Arial", letterSpacing: ".07em" });
                const text = document.createElement("div"); text.textContent = fragment.value || ""; Object.assign(text.style, { flex: "1", color: "#e8e2eb", font: "10px/1.42 Segoe UI,Arial", display: "-webkit-box", WebkitLineClamp: "4", WebkitBoxOrient: "vertical", overflow: "hidden" });
                const add = action("ADD TO ASSEMBLY", color); Object.assign(add.style, { alignSelf: "flex-start", padding: "6px 8px", fontSize: "8px" }); add.onclick = () => { addBuilderFragment(fragment); add.textContent = "ADDED ✓"; setTimeout(() => { add.textContent = "ADD TO ASSEMBLY"; }, 900); };
                item.append(meta, text, add); grid.append(item);
            }
            if (!rows.length) { const empty = document.createElement("div"); empty.textContent = "No Ingredients match this view. Try All active or a broader category."; Object.assign(empty.style, { gridColumn: "1 / -1", padding: "28px", color: "#8f8997", textAlign: "center" }); grid.append(empty); }
        } catch (error) { if (current === serial) range.textContent = error.message || "Could not load Ingredients."; }
    };
    const queue = () => { clearTimeout(timer); timer = setTimeout(draw, 160); }; role.onchange = draw; state.onchange = draw; search.oninput = queue;
    const custom = document.createElement("div"); Object.assign(custom.style, { display: "grid", gridTemplateColumns: "minmax(150px,210px) 1fr auto", gap: "7px", paddingTop: "9px", borderTop: "1px solid #342f3b" });
    const customRole = makeSelect(Object.entries(FRAGMENT_ROLE_META).filter(([value]) => !["prefix", "suffix"].includes(value)).map(([value, meta]) => [value, meta[0]]), initialRole && FRAGMENT_ROLE_META[initialRole] ? initialRole : "concept");
    const customText = document.createElement("input"); customText.type = "text"; customText.placeholder = "Write a custom natural-language clause…"; Object.assign(customText.style, { minWidth: "0", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", outline: "none", background: "#09080d", color: "#fff" });
    const addCustom = action("ADD CUSTOM", "#6ee7a2"); addCustom.onclick = () => { if (!customText.value.trim()) return; addBuilderFragment({ role: customRole.value, value: customText.value.trim(), join_mode: "sentence", preferred_position: 50, source_kind: "manual", multiple_allowed: true }); customText.value = ""; };
    custom.append(customRole, customText, addCustom);
    body.append(help, controls, range, grid, custom); card.append(body); void draw(); requestAnimationFrame(() => search.focus());
}

function setBuilderIngredientControls(kind, destination = "A") {
    const promptNode = findStudioNode("SOPromptLogEngineStudio");
    if (!promptNode) return { changed: 0, skipped: 0 };
    const values = kind === "scene"
        ? [["scene_token", "SCENE"], ["scene_placement", "token"]]
        : [[`outfit_token_${destination}`, destination === "A" ? "OUTFIT" : `OUTFIT_${destination}`], [`outfit_placement_${destination}`, "token"]];
    let changed = 0, skipped = 0;
    for (const [name, value] of values) {
        const widget = studioWidget(promptNode, name);
        if (!widget) continue;
        if (isConnected(promptNode, widget)) { skipped++; continue; }
        if (widget.value !== value) { setStudioWidget(promptNode, name, value); changed++; }
    }
    return { changed, skipped };
}

async function applyBuilderToStudio() {
    const recipe = builderRecipe();
    const template = builderTemplateText();
    if (!template) { alert("Add a Prompt, corpus Blueprint, saved Recipe, or Ingredient before sending this assembly to Studio."); return; }
    const promptNode = findStudioNode("SOPromptLogEngineStudio");
    if (!promptNode) { alert("Add a Studio Prompt Core node to the canvas before sending this Board."); return; }
    const manual = studioWidget(promptNode, "manual_prompt");
    if (!manual || isConnected(promptNode, manual)) { alert("Manual prompt is connected on Prompt Core, so the Builder left it untouched."); return; }
    let applied = { changed: 0, skipped: 0 };
    if (recipe) {
        const safeChanges = new Set(recipeDiff(recipe, false).flatMap(group => group.changes || []).filter(change => !change.connected).map(change => change.id));
        applied = applyRecipe(recipe, safeChanges);
    }
    const source = studioWidget(promptNode, "prompt_source");
    if (source && !isConnected(promptNode, source) && source.value !== "manual") setStudioWidget(promptNode, "prompt_source", "manual");
    if (manual.value !== template) setStudioWidget(promptNode, "manual_prompt", template);
    promptNode.setDirtyCanvas?.(true, true);
    let ingredients = 0;
    let protectedFields = Number(applied.skipped || 0);
    const destination = String(builderDraft.outfit_destination || "A").toUpperCase();
    if (builderDraft.outfit_value) {
        const asset = builderAsset("outfit");
        if (!asset) { alert("This Board's Outfit is no longer in the canonical Outfit Library. Choose another Outfit before sending it to Studio."); return; }
        const controls = setBuilderIngredientControls("outfit", destination); protectedFields += controls.skipped;
        if (await loadDerivedValue(asset, destination)) ingredients++;
    }
    if (builderDraft.scene_value) {
        const asset = builderAsset("scene");
        if (!asset) { alert("This Board's Scene is no longer in the canonical Scene Library. Choose another Scene before sending it to Studio."); return; }
        const controls = setBuilderIngredientControls("scene"); protectedFields += controls.skipped;
        if (await loadDerivedValue(asset)) ingredients++;
    }
    const changed = Number(applied.changed || 0) + ingredients + 1;
    catalogStatus(`Sent corpus-built prompt to Studio · ${builderFragments().length} editable slot${builderFragments().length === 1 ? "" : "s"} · ${changed} section${changed === 1 ? "" : "s"} loaded${protectedFields ? ` · ${protectedFields} connected field${protectedFields === 1 ? "" : "s"} protected` : ""}.`, "#6ee7a2");
}

function renderBuilderPanel(list) {
    normalizeBuilderDraft();
    if (!workshopAssemblyOpen) {
        const collapsed = document.createElement("section"); collapsed.dataset.builderPanel = "";
        Object.assign(collapsed.style, { gridColumn: "1 / -1", display: "grid", gridTemplateColumns: "auto minmax(0,1fr) auto", gap: "10px", alignItems: "center", marginBottom: "10px", padding: "10px 12px", borderRadius: "11px", border: "1px solid #b89aff55", background: "linear-gradient(90deg,rgba(184,154,255,.10),#0b0910 42%)" });
        const label = document.createElement("strong"); label.textContent = "PROMPT ASSEMBLY · OPTIONAL"; Object.assign(label.style, { color: "#d4c6ff", font: "900 9px Segoe UI,Arial", letterSpacing: ".09em" });
        const summary = document.createElement("div"); summary.textContent = builderHasContent() ? builderPreviewText() : "Open only when you want to combine a Template, Prompt, Ingredients, Outfit, or Scene."; Object.assign(summary.style, { minWidth: "0", color: builderHasContent() ? "#bdb5c3" : "#7f7885", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "9px Segoe UI,Arial" });
        const open = action(builderHasContent() ? "OPEN ASSEMBLY" : "START ASSEMBLY", "#b89aff"); Object.assign(open.style, { padding: "7px 9px", fontSize: "8px" }); open.onclick = () => { workshopAssemblyOpen = true; render(); };
        collapsed.append(label, summary, open); list.append(collapsed); return;
    }
    const recipe = builderRecipe();
    const panel = document.createElement("section"); panel.dataset.builderPanel = "";
    Object.assign(panel.style, { gridColumn: "1 / -1", minWidth: "0", marginBottom: "10px", padding: "18px", borderRadius: "16px", border: "1px solid #ff4ab866", background: "radial-gradient(circle at 8% 5%,rgba(255,74,184,.14),transparent 30%),radial-gradient(circle at 94% 16%,rgba(53,215,255,.09),transparent 32%),linear-gradient(145deg,#14101a,#09080d 72%)", boxShadow: "0 16px 48px rgba(0,0,0,.28)" });
    const top = document.createElement("div"); Object.assign(top.style, { display: "flex", alignItems: "flex-start", gap: "12px", flexWrap: "wrap", marginBottom: "14px" });
    const copy = document.createElement("div"); copy.style.flex = "1";
    const eyebrow = document.createElement("div"); eyebrow.textContent = "VISUAL ASSEMBLY LAB"; Object.assign(eyebrow.style, { color: "#ff78bd", font: "900 9px Segoe UI,Arial", letterSpacing: ".15em" });
    const title = document.createElement("h2"); title.textContent = "Prompt Builder"; Object.assign(title.style, { margin: "4px 0 4px", color: "#fff", font: "900 25px/1 Segoe UI,Arial", letterSpacing: "-.01em" });
    const intro = document.createElement("div"); intro.textContent = "Build from the authored vocabulary inside your Prompt corpus. Start with a corpus Blueprint, decompose any full Prompt, or shop reusable Ingredients—then reorder, lock, replace, and combine them without touching their sources."; Object.assign(intro.style, { color: "#aaa2b4", font: "11px/1.45 Segoe UI,Arial" }); copy.append(eyebrow, title, intro);
    const capture = action("SAVE CURRENT AS RECIPE", "#35d7ff"); capture.title = "Save the complete current Studio generation state as a Recipe"; capture.onclick = () => saveCurrentStudioRecipe("New Recipe").catch(error => alert(error.message || "Could not save this Recipe."));
    const addFragment = action("+ ADD INGREDIENT", "#b89aff"); addFragment.title = "Browse reusable language mined from the Prompt corpus"; addFragment.onclick = () => showBuilderFragmentPicker();
    const collapse = action("COLLAPSE", "#8f8997"); Object.assign(collapse.style, { padding: "7px 9px", fontSize: "8px" }); collapse.onclick = () => { workshopAssemblyOpen = false; render(); };
    top.append(copy, addFragment, capture, collapse); panel.append(top);

    const startRow = document.createElement("div"); Object.assign(startRow.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "7px", marginBottom: "10px", padding: "9px", borderRadius: "10px", border: "1px solid #3d3545", background: "rgba(255,255,255,.018)" });
    const startLabel = document.createElement("strong"); startLabel.textContent = "START"; Object.assign(startLabel.style, { color: "#8f8997", font: "900 8px Segoe UI,Arial", letterSpacing: ".12em", marginRight: "3px" });
    const scratch = action("FROM SCRATCH", "#b89aff"); Object.assign(scratch.style, { padding: "6px 8px", fontSize: "8px" }); scratch.onclick = () => { builderDraft = newBuilderDraft(); render(); catalogStatus("Blank assembly ready. Add any corpus Ingredient or custom clause.", "#b89aff"); };
    const promptStart = action("CHOOSE ANY PROMPT", "#35d7ff"); Object.assign(promptStart.style, { padding: "6px 8px", fontSize: "8px" }); promptStart.onclick = () => { setActiveView("prompts"); openPromptVault(); };
    const corpusStart = action("CHOOSE TEMPLATE", "#ff4ab8"); Object.assign(corpusStart.style, { padding: "6px 8px", fontSize: "8px" }); corpusStart.onclick = () => { setActiveView("recipes"); openPromptVault({ kind: "template" }); };
    const recipeStart = action("CHOOSE SAVED RECIPE", "#f6e65a"); Object.assign(recipeStart.style, { padding: "6px 8px", fontSize: "8px" }); recipeStart.onclick = showBuilderBlueprintPicker;
    const startState = document.createElement("span"); startState.textContent = builderDraft.source_prompt_id ? `CORPUS PROMPT · ${builderDraft.source_prompt_name || "Prompt"}` : recipe ? `SAVED RECIPE · ${recipe.name}` : builderFragments().length ? "INGREDIENT ASSEMBLY" : "NO STARTING SOURCE"; Object.assign(startState.style, { marginLeft: "auto", minWidth: "0", maxWidth: "45%", color: builderDraft.source_prompt_id ? "#7ddff6" : recipe ? "#ff9dce" : "#8f8997", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "800 8px Segoe UI,Arial", letterSpacing: ".04em" });
    startRow.append(startLabel, scratch, promptStart, corpusStart, recipeStart, startState); panel.append(startRow);

    const slots = document.createElement("div"); Object.assign(slots.style, { display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: "9px" });
    const makeSlot = (label, value, empty, color, onchoose) => {
        const slot = document.createElement("div"); Object.assign(slot.style, { minWidth: "0", minHeight: "112px", display: "flex", flexDirection: "column", padding: "12px", borderRadius: "11px", border: `1px solid ${color}55`, background: `linear-gradient(145deg,${color}10,rgba(10,8,13,.92))` });
        const name = document.createElement("strong"); name.textContent = label; Object.assign(name.style, { color, font: "900 9px Segoe UI,Arial", letterSpacing: ".1em" });
        const text = document.createElement("div"); text.textContent = value || empty; text.title = value || empty; Object.assign(text.style, { flex: "1", margin: "8px 0", color: value ? "#f2edf4" : "#77717d", font: value ? "10px/1.38 Segoe UI,Arial" : "italic 10px/1.38 Segoe UI,Arial", display: "-webkit-box", WebkitLineClamp: "3", WebkitBoxOrient: "vertical", overflow: "hidden" });
        const choose = action(value ? "CHANGE" : "CHOOSE", color); Object.assign(choose.style, { alignSelf: "flex-start", padding: "6px 8px", fontSize: "8px" }); choose.onclick = onchoose;
        slot.append(name, text, choose); return slot;
    };
    const blueprintSlot = makeSlot("OPTIONAL SAVED RECIPE", recipe?.name || "", builderDraft.source_prompt_id ? "A canonical Prompt or Blueprint is the current starting source" : "Choose a complete saved Studio state", "#f6e65a", showBuilderBlueprintPicker);
    const outfitSlot = makeSlot("OPTIONAL OUTFIT", builderDraft.outfit_value, "Choose a complete Look", "#f6e65a", () => showBuilderIngredientPicker("outfit"));
    const destination = makeSelect([["A", "OUTFIT A"], ["B", "OUTFIT B"], ["C", "OUTFIT C"]], String(builderDraft.outfit_destination || "A")); destination.title = "Prompt Core Outfit destination"; Object.assign(destination.style, { width: "96px", alignSelf: "flex-end", marginTop: "-30px", padding: "5px", fontSize: "8px" }); destination.onchange = () => { builderDraft.board_id = ""; builderDraft.outfit_destination = destination.value; render(); }; outfitSlot.append(destination);
    const sceneSlot = makeSlot("OPTIONAL SCENE", builderDraft.scene_value, "Choose a location or environment", "#63e6a4", () => showBuilderIngredientPicker("scene"));
    slots.append(blueprintSlot, outfitSlot, sceneSlot); panel.append(slots);

    const tray = document.createElement("section"); Object.assign(tray.style, { marginTop: "10px", padding: "11px", borderRadius: "11px", border: "1px solid #b89aff55", background: "rgba(184,154,255,.035)" });
    const trayHead = document.createElement("div"); Object.assign(trayHead.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "7px", marginBottom: "9px" });
    const trayTitle = document.createElement("strong"); trayTitle.textContent = "COMPOSITION TRAY"; Object.assign(trayTitle.style, { color: "#cbb9ff", font: "900 9px Segoe UI,Arial", letterSpacing: ".12em" });
    const trayCount = document.createElement("span"); trayCount.textContent = `${builderFragments().length} editable slot${builderFragments().length === 1 ? "" : "s"}`; Object.assign(trayCount.style, { color: "#817b88", font: "8px Segoe UI,Arial" });
    const trayAdd = action("+ INGREDIENT", "#b89aff"); Object.assign(trayAdd.style, { marginLeft: "auto", padding: "6px 8px", fontSize: "8px" }); trayAdd.onclick = () => showBuilderFragmentPicker();
    trayHead.append(trayTitle, trayCount, trayAdd); tray.append(trayHead);
    if (!builderFragments().length) {
        const empty = document.createElement("div"); empty.textContent = "Choose a department to begin. The picker opens on recurring, source-linked Ingredients—not isolated tags."; Object.assign(empty.style, { color: "#8f8997", font: "italic 9px/1.4 Segoe UI,Arial", marginBottom: "8px" }); tray.append(empty);
        const quick = document.createElement("div"); Object.assign(quick.style, { display: "flex", flexWrap: "wrap", gap: "5px" });
        for (const role of ["concept", "style", "environment", "composition", "pose_action", "expression_mood", "lighting", "time_atmosphere", "camera", "typography", "color_effects"]) { const [label, color] = fragmentMeta(role); const button = action(label, color); Object.assign(button.style, { padding: "5px 7px", fontSize: "7px" }); button.onclick = () => showBuilderFragmentPicker(role); quick.append(button); }
        tray.append(quick);
    } else {
        const rail = document.createElement("div"); Object.assign(rail.style, { display: "flex", alignItems: "stretch", gap: "7px", overflowX: "auto", paddingBottom: "4px" });
        builderFragments().forEach((slot, index) => {
            const [label, color] = fragmentMeta(slot.role); const item = document.createElement("div"); Object.assign(item.style, { flex: "0 0 220px", minWidth: "0", minHeight: "124px", display: "flex", flexDirection: "column", gap: "6px", padding: "9px", borderRadius: "9px", border: `1px solid ${color}55`, background: `linear-gradient(145deg,${color}12,#0c0a10)` });
            const meta = document.createElement("div"); meta.textContent = `${index + 1} · ${label}${slot.source_segment ? " · SOURCE" : ""}`; Object.assign(meta.style, { color, font: "900 7px Segoe UI,Arial", letterSpacing: ".07em" });
            const text = document.createElement("div"); text.textContent = slot.value; text.title = slot.original_text && slot.original_text !== slot.value ? `Original: ${slot.original_text}` : slot.value; Object.assign(text.style, { flex: "1", color: "#e8e2eb", font: "9px/1.38 Segoe UI,Arial", display: "-webkit-box", WebkitLineClamp: "4", WebkitBoxOrient: "vertical", overflow: "hidden" });
            const controls = document.createElement("div"); Object.assign(controls.style, { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: "4px" });
            const up = action("←", color); up.title = "Move earlier"; up.disabled = index === 0 || slot.locked; up.onclick = () => moveBuilderFragment(slot.instance_id, -1);
            const down = action("→", color); down.title = "Move later"; down.disabled = index === builderFragments().length - 1 || slot.locked; down.onclick = () => moveBuilderFragment(slot.instance_id, 1);
            const lock = action(slot.locked ? "🔒" : "◇", slot.locked ? "#f6e65a" : "#8f8997"); lock.title = slot.locked ? "Unlock slot" : "Lock slot"; lock.onclick = () => toggleBuilderFragmentLock(slot.instance_id);
            const remove = action("×", "#ff4ab8"); remove.title = "Remove slot"; remove.disabled = slot.locked; remove.onclick = () => removeBuilderFragment(slot.instance_id);
            for (const button of [up, down, lock, remove]) { Object.assign(button.style, { minWidth: "0", padding: "4px", fontSize: "8px", opacity: button.disabled ? ".35" : "1" }); }
            controls.append(up, down, lock, remove); item.append(meta, text, controls); rail.append(item);
        });
        tray.append(rail);
    }
    panel.append(tray);

    const preview = document.createElement("div"); Object.assign(preview.style, { marginTop: "10px", padding: "12px 13px", borderRadius: "10px", border: "1px solid #35d7ff44", background: "rgba(53,215,255,.035)" });
    const previewLabel = document.createElement("div"); previewLabel.textContent = "ASSEMBLY PREVIEW"; Object.assign(previewLabel.style, { marginBottom: "6px", color: "#35d7ff", font: "900 8px Segoe UI,Arial", letterSpacing: ".11em" });
    const previewText = document.createElement("div"); previewText.textContent = builderPreviewText(); Object.assign(previewText.style, { maxHeight: "148px", overflow: "auto", color: builderHasContent() ? "#ded8e2" : "#817b88", whiteSpace: "pre-wrap", wordBreak: "break-word", font: "10px/1.5 Consolas,monospace" }); preview.append(previewLabel, previewText); panel.append(preview);

    const actions = document.createElement("div"); Object.assign(actions.style, { display: "flex", alignItems: "center", gap: "7px", flexWrap: "wrap", marginTop: "10px" });
    const send = action("SEND TO STUDIO", "#6ee7a2"); Object.assign(send.style, { padding: "9px 13px", borderWidth: "2px", background: "rgba(110,231,162,.10)" }); send.disabled = !builderHasContent(); send.style.opacity = builderHasContent() ? "1" : ".42"; send.onclick = () => void applyBuilderToStudio();
    const save = action(builderDraft.board_id ? "UPDATE BOARD" : "SAVE BOARD", "#b89aff"); save.disabled = !builderHasContent(); save.style.opacity = builderHasContent() ? "1" : ".42"; save.onclick = () => void saveBuilderBoard();
    const copyPrompt = action("COPY PROMPT", "#35d7ff"); copyPrompt.disabled = !builderHasContent(); copyPrompt.style.opacity = builderHasContent() ? "1" : ".42"; copyPrompt.onclick = async () => { try { await navigator.clipboard.writeText(builderPreviewText()); copyPrompt.textContent = "COPIED ✓"; setTimeout(() => { copyPrompt.textContent = "COPY PROMPT"; }, 900); } catch (error) { alert("Could not copy this prompt."); } };
    const exportPrompt = action("EXPORT .TXT", "#ff9b5f"); exportPrompt.disabled = !builderHasContent(); exportPrompt.style.opacity = builderHasContent() ? "1" : ".42"; exportPrompt.onclick = () => { const blob = new Blob([`${builderPreviewText()}\n`], { type: "text/plain;charset=utf-8" }); const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `${String(builderDraft.source_prompt_name || builderRecipe()?.name || "sick-ollie-prompt").replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "") || "sick-ollie-prompt"}.txt`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000); };
    const clear = action("CLEAR", "#8f8997"); clear.onclick = clearBuilderDraft;
    const state = document.createElement("span"); state.textContent = builderDraft.board_id ? `Editing ${boards.find(board => String(board.board_id) === String(builderDraft.board_id))?.name || "saved Board"}` : "Unsaved Builder draft"; Object.assign(state.style, { marginLeft: "auto", color: builderDraft.board_id ? "#cbb9ff" : "#716b77", font: "8px Segoe UI,Arial" });
    actions.append(send, save, copyPrompt, exportPrompt, clear, state); panel.append(actions);

    if (boards.length) {
        const boardRail = document.createElement("div"); Object.assign(boardRail.style, { display: "flex", alignItems: "stretch", gap: "7px", marginTop: "13px", paddingTop: "11px", borderTop: "1px solid #332d38", overflowX: "auto" });
        const railLabel = document.createElement("div"); railLabel.textContent = "SAVED\nBOARDS"; Object.assign(railLabel.style, { flex: "0 0 54px", whiteSpace: "pre-line", color: "#b89aff", font: "900 8px/1.25 Segoe UI,Arial", letterSpacing: ".08em" }); boardRail.append(railLabel);
        for (const board of boards) {
            const boardCard = document.createElement("div"); Object.assign(boardCard.style, { flex: "0 0 205px", minWidth: "0", display: "grid", gridTemplateColumns: "1fr auto", gap: "5px", padding: "8px", borderRadius: "9px", border: `1px solid ${String(builderDraft.board_id) === String(board.board_id) ? "#b89aff" : "#4c405a"}`, background: String(builderDraft.board_id) === String(board.board_id) ? "rgba(184,154,255,.13)" : "#111016" });
            const name = document.createElement("button"); name.type = "button"; name.textContent = board.name; name.title = `Load ${board.name}`; Object.assign(name.style, { minWidth: "0", padding: "0", border: "0", cursor: "pointer", textAlign: "left", color: "#e0d6ff", background: "transparent", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "800 9px Segoe UI,Arial" }); name.onclick = () => loadBuilderBoard(board);
            const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "×"; remove.title = "Delete Board"; Object.assign(remove.style, { width: "22px", padding: "0", borderRadius: "6px", border: "1px solid #ff4ab844", cursor: "pointer", color: "#ff8fce", background: "transparent" }); remove.onclick = () => void deleteBuilderBoard(board);
            const detail = document.createElement("div"); detail.textContent = [`${Number(board.payload?.fragments?.length || 0)} slots`, board.payload?.source_prompt_name, board.payload?.recipe_name, board.payload?.outfit_value, board.payload?.scene_value].filter(Boolean).join(" · ") || "Reusable assembly"; Object.assign(detail.style, { gridColumn: "1 / -1", color: "#716b77", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "7px Segoe UI,Arial" }); boardCard.append(name, remove, detail); boardRail.append(boardCard);
        }
        panel.append(boardRail);
    }
    list.append(panel);
}

function renderCorpusBlueprintShelf(list) {
    const shell = document.createElement("section"); shell.dataset.corpusBlueprints = "";
    Object.assign(shell.style, { gridColumn: "1 / -1", minWidth: "0", padding: "15px", borderRadius: "14px", border: "1px solid #ff4ab855", background: "radial-gradient(circle at 8% 0%,rgba(255,74,184,.12),transparent 28%),linear-gradient(145deg,#120e17,#09080d 72%)" });
    const head = document.createElement("div"); Object.assign(head.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "9px" });
    const copy = document.createElement("div"); copy.style.flex = "1";
    const label = document.createElement("strong"); label.textContent = `CORPUS BLUEPRINTS · ${Number(promptBlueprintTotal || 0).toLocaleString()}`; Object.assign(label.style, { display: "block", color: "#ff78bd", font: "900 11px Segoe UI,Arial", letterSpacing: ".1em" });
    const note = document.createElement("div"); note.textContent = `${Number(promptComponentBlueprintTotal || 0).toLocaleString()} accept an Outfit and/or Scene. These are live views of canonical Prompts—nothing is duplicated into Recipes or rewritten in source logs.`; Object.assign(note.style, { marginTop: "4px", color: "#9d95a4", font: "9px/1.4 Segoe UI,Arial" }); copy.append(label, note);
    const browse = action("BROWSE ALL BLUEPRINTS", "#ff4ab8"); browse.onclick = () => { setActiveView("prompts"); openPromptVault({ blueprint: true }); }; head.append(copy, browse); shell.append(head);

    const signatures = document.createElement("div"); Object.assign(signatures.style, { display: "flex", gap: "5px", overflowX: "auto", marginTop: "11px", paddingBottom: "3px" });
    for (const [signature, count] of Object.entries(promptBlueprintSignatures || {}).slice(0, 10)) {
        const chip = action(`${signature} · ${Number(count || 0).toLocaleString()}`, signature.includes("OUTFIT") ? "#f6e65a" : signature.includes("SCENE") ? "#63e6a4" : "#35d7ff");
        Object.assign(chip.style, { flex: "0 0 auto", padding: "5px 7px", fontSize: "7px" });
        chip.onclick = () => { setActiveView("prompts"); openPromptVault({ blueprint: true, signature }); };
        signatures.append(chip);
    }
    shell.append(signatures);

    const grid = document.createElement("div"); Object.assign(grid.style, { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(245px,100%),1fr))", gap: "8px", marginTop: "10px" });
    for (const asset of blueprintAssets.slice(0, 12)) {
        const signature = String(asset.placeholder_signature || "PORTABLE");
        const color = signature.includes("OUTFIT") ? "#f6e65a" : signature.includes("SCENE") ? "#63e6a4" : signature.includes("BRAND") ? "#ff9b5f" : "#35d7ff";
        const card = document.createElement("div"); Object.assign(card.style, { minWidth: "0", minHeight: "176px", display: "flex", flexDirection: "column", gap: "7px", padding: "10px", borderRadius: "10px", border: `1px solid ${color}44`, background: `linear-gradient(145deg,${color}10,#0b0910 68%)` });
        const meta = document.createElement("div"); meta.textContent = `${signature} · ${Number(asset.source_count || asset.uses || 1).toLocaleString()} SOURCE${Number(asset.source_count || asset.uses || 1) === 1 ? "" : "S"}`; Object.assign(meta.style, { color, font: "900 7px Segoe UI,Arial", letterSpacing: ".07em" });
        const name = document.createElement("strong"); name.textContent = asset.name || "Corpus Prompt"; name.title = asset.name || "Corpus Prompt"; Object.assign(name.style, { color: "#e7e0ea", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "800 9px Segoe UI,Arial" });
        const text = document.createElement("div"); text.textContent = asset.value || ""; text.title = asset.value || ""; Object.assign(text.style, { flex: "1", color: "#aaa2b4", font: "9px/1.4 Segoe UI,Arial", display: "-webkit-box", WebkitLineClamp: "4", WebkitBoxOrient: "vertical", overflow: "hidden" });
        const use = action("ADD FORMULA TO BUILDER", color); Object.assign(use.style, { alignSelf: "stretch", padding: "6px 7px", fontSize: "8px" }); use.onclick = () => void openPromptInBuilder(asset);
        card.append(meta, name, text, use); grid.append(card);
    }
    if (!blueprintAssets.length) { const empty = document.createElement("div"); empty.textContent = promptBlueprintTotal ? "Loading corpus Blueprints…" : "No uppercase portable placeholder formulas were found in the canonical Prompt corpus."; Object.assign(empty.style, { gridColumn: "1 / -1", padding: "20px", color: "#8f8997", textAlign: "center" }); grid.append(empty); }
    shell.append(grid); list.append(shell);

    const savedHeading = document.createElement("div"); Object.assign(savedHeading.style, { gridColumn: "1 / -1", display: "flex", alignItems: "baseline", gap: "10px", margin: "4px 2px -2px", paddingTop: "3px" });
    const savedLabel = document.createElement("strong"); savedLabel.textContent = "SAVED RECIPES"; Object.assign(savedLabel.style, { color: "#f6e65a", font: "900 10px Segoe UI,Arial", letterSpacing: ".12em" });
    const savedCount = document.createElement("span"); savedCount.textContent = `${recipes.length.toLocaleString()} complete generation state${recipes.length === 1 ? "" : "s"}`; Object.assign(savedCount.style, { color: "#77717d", font: "9px Segoe UI,Arial" }); savedHeading.append(savedLabel, savedCount); list.append(savedHeading);
}

function recipeTokens(payload) {
    const declared = Array.isArray(payload?.tokens) ? payload.tokens.map(String) : [];
    const promptText = (payload?.nodes || []).filter(node => node?.type === "SOPromptLogEngineStudio").flatMap(node => (node.widgets || []).filter(widget => ["manual_prompt", "saved_prompt", "prefix_text", "suffix_text"].includes(widget?.name)).map(widget => String(widget?.value || ""))).join("\n");
    const matches = promptText.match(/(?<![A-Za-z0-9_])(NAME|BRAND|ITEM|OUTFIT(?:_[ABC])?|SCENE|TRIGGER)(?![A-Za-z0-9_])/g) || [];
    const values = new Set([...declared, ...matches]);
    if (values.has("ITEM")) values.add("BRAND");
    if ([...values].some(value => value === "OUTFIT" || value.startsWith("OUTFIT_"))) values.add("OUTFIT");
    return [...values].sort();
}

function catalogStatus(message, tone = "#6ee7a2") {
    const field = root?.querySelector("[data-catalog-status]");
    if (!field) return;
    field.textContent = message;
    field.style.color = tone;
}

function captureLibraryFieldFocus() {
    const active = document.activeElement;
    if (!active || !root?.contains(active) || !active.dataset?.libraryFocusKey) return null;
    return {
        key: String(active.dataset.libraryFocusKey),
        start: typeof active.selectionStart === "number" ? active.selectionStart : null,
        end: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
        direction: active.selectionDirection || "none",
    };
}

function restoreLibraryFieldFocus(state) {
    if (!state?.key) return;
    const field = root?.querySelector(`[data-library-focus-key="${state.key}"]`);
    if (!field) return;
    field.focus?.({ preventScroll: true });
    if (state.start != null && state.end != null && typeof field.setSelectionRange === "function") {
        const length = String(field.value || "").length;
        field.setSelectionRange(Math.min(state.start, length), Math.min(state.end, length), state.direction);
    }
}

function libraryViewCount(view) {
    if (view === "recipes") return Number(promptCorpusTotals.template || promptBlueprintTotal || libraryStateCounts.templates || 0);
    if (view === "fragments") return Number(fragmentSummary.states?.approved || 0) + Number(fragmentSummary.states?.suggested || 0) || Number(libraryStateCounts.fragments || 0);
    if (view === "prompts") return Number(promptAssetTotal || libraryStateCounts.prompts || 0);
    if (view === "outfits") return componentViewsLoaded.outfit ? (derivedValues.outfits || []).length : Number(libraryStateCounts.outfits || 0);
    if (view === "scenes") return componentViewsLoaded.scene ? (derivedValues.scenes || []).length : Number(libraryStateCounts.scenes || 0);
    return 0;
}

function activePromptKind() {
    return activeView === "recipes" ? "template" : "prompt";
}

function promptShowcaseFolders(kind = activePromptKind()) {
    return promptShowcaseCollections[kind === "template" ? "template" : "prompt"] || [];
}

function promptShowcaseCounts(kind = activePromptKind()) {
    return promptCollectionCounts[kind === "template" ? "template" : "prompt"] || { "": 0, unfiled: 0 };
}

function resetPromptNavigation() {
    promptPage = 0;
    promptSearch = "";
    promptSourceFilter = "";
    promptSignatureFilter = "";
    promptBlueprintOnly = false;
    promptFacetFilters = emptyPromptFacetFilters();
    promptRatingFilter = "";
    promptParent = "";
    promptSubcategory = "";
    promptLogPath = "";
    promptLogLabel = "";
    promptPlaceholderFilters = new Set();
    activeCollection = "";
}

function setActiveView(view) {
    if (!LIBRARY_VIEWS[view]) return;
    const changedView = activeView !== view;
    activeView = view;
    activeToken = ""; activeCollection = ""; selectionMode = false; selectedRecipeIds.clear(); selectedComponentIds.clear();
    if (view === "outfits") { activeLibraryCollection.outfit = ""; activeLibraryCollection.wardrobe = ""; }
    if (view === "scenes") activeLibraryCollection.scene = "";
    if (["recipes", "prompts"].includes(view) && changedView) {
        promptVaultOpen = true;
        resetPromptNavigation();
    }
    if (view === "fragments" && changedView) {
        fragmentPage = 0; fragmentSearch = ""; fragmentRole = ""; fragmentState = "ready"; fragmentSort = "rank";
        resetFragmentSelection(true);
    }
    if (view === "outfits") componentPage.outfit = 0;
    if (view === "scenes") componentPage.scene = 0;
    refreshLibraryChrome(); refreshOutfitModeBar(); renderCollectionControls(); renderBulkControls(); render();
    if (view === "fragments" && changedView) {
        if (workshopExtrasLoaded) queueFragmentPageLoad();
        else { catalogStatus("Loading Workshop data…", "#b89aff"); void load(); }
    }
    if (["recipes", "prompts"].includes(view) && changedView) queuePromptPageLoad();
    if (view === "outfits" && changedView && !componentViewsLoaded.outfit) { catalogStatus("Loading Outfit Library…", "#f6e65a"); void load(); }
    if (view === "scenes" && changedView && !componentViewsLoaded.scene) { catalogStatus("Loading Scene Library…", "#63e6a4"); void load(); }
}

function setOutfitMode(mode) {
    if (mode === "builder") mode = "pieces";
    if (!["looks", "pieces"].includes(mode)) return;
    outfitMode = mode;
    activeCollection = ""; activeLibraryCollection.outfit = ""; activeLibraryCollection.wardrobe = ""; selectionMode = false; selectedComponentIds.clear(); resetWardrobeSelection(false); wardrobePage = 0;
    refreshLibraryChrome(); refreshOutfitModeBar(); renderCollectionControls(); renderBulkControls(); render();
    if (!componentViewsLoaded.outfit || (mode === "pieces" && !wardrobeDataLoaded)) {
        catalogStatus(mode === "pieces" ? "Loading Wardrobe…" : "Loading Outfit Looks…", "#f6e65a");
        void load();
    }
}

function refreshOutfitModeBar() {
    const bar = root?.querySelector("[data-outfit-mode-bar]");
    if (!bar) return;
    bar.style.display = activeView === "outfits" ? "flex" : "none";
    for (const button of bar.querySelectorAll("[data-outfit-mode]")) {
        const mode = button.dataset.outfitMode;
        const active = mode === outfitMode;
        const count = mode === "looks"
            ? (componentViewsLoaded.outfit ? (derivedValues.outfits || []).length : Number(libraryStateCounts.outfits || 0))
            : (wardrobeDataLoaded ? wardrobeItems.length : Number(libraryStateCounts.wardrobe || 0));
        button.textContent = `${mode === "looks" ? "LOOKS" : "WARDROBE"}  ${count.toLocaleString()}`;
        button.style.background = active ? "rgba(246,230,90,.16)" : "rgba(255,255,255,.018)";
        button.style.borderColor = active ? "#f6e65a" : "#4b4652";
        button.style.color = active ? "#fff7a8" : "#aaa4b0";
    }
}

function refreshLibraryChrome() {
    if (!root) return;
    for (const tab of root.querySelectorAll("[data-library-tab]")) {
        const view = tab.dataset.libraryTab; const meta = LIBRARY_VIEWS[view]; const active = view === activeView;
        tab.textContent = `${meta.label}  ${libraryViewCount(view)}`;
        tab.style.borderColor = active ? meta.color : `${meta.color}55`;
        tab.style.color = active ? "#fff" : "#aaa4b0";
        tab.style.background = active ? `${meta.color}22` : "rgba(255,255,255,.018)";
        tab.style.boxShadow = active ? `inset 0 -2px 0 ${meta.color}` : "none";
    }
    const desc = root.querySelector("[data-library-view-description]");
    if (desc) {
        if (activeView === "outfits" && outfitMode === "pieces") desc.textContent = "Browse reusable wardrobe Pieces and matching Sets, then assemble them in the persistent Outfit Builder without changing the original Looks.";
        else desc.textContent = LIBRARY_VIEWS[activeView]?.description || "";
    }
    const menu = root.querySelector("[data-library-menu]");
    const menuTitle = root.querySelector("[data-library-menu-title]");
    const menuCopy = root.querySelector("[data-library-menu-copy]");
    const activeMeta = LIBRARY_VIEWS[activeView] || LIBRARY_VIEWS.prompts;
    const activeLabel = activeView === "outfits" ? `${activeMeta.label} · ${outfitMode === "pieces" ? "WARDROBE" : "LOOKS"}` : activeMeta.label;
    if (menuTitle) menuTitle.textContent = `${activeLabel} · ${libraryViewCount(activeView).toLocaleString()}`;
    if (menuCopy) menuCopy.textContent = activeView === "outfits" && outfitMode === "pieces"
        ? "Wardrobe tools, library packs, image import, and maintenance are collected here so the gallery stays focused on browsing and building."
        : "Tools for this tab, library packs, image import, and maintenance are collected here instead of scattered through the gallery.";
    const menuSummary = menu?.querySelector("summary");
    if (menuSummary) { menuSummary.style.borderColor = `${activeMeta.color}99`; menuSummary.style.boxShadow = `inset 0 1px 0 rgba(255,255,255,.05),0 0 18px ${activeMeta.color}12`; }
    const tokenTools = root.querySelector("[data-recipe-token-tools]"); if (tokenTools) tokenTools.style.display = "none";
    const manage = root.querySelector("[data-manage-collections]"); if (manage) manage.style.display = "none";
    const save = root.querySelector("[data-save-recipe]"); if (save) save.style.display = "none";
    const build = root.querySelector("[data-build-asset]"); if (build) {
        build.style.display = ["outfits", "scenes"].includes(activeView) ? "inline-block" : "none";
        build.textContent = activeView === "outfits" && outfitMode === "pieces" ? "Add wardrobe item" : "Build asset";
        build.title = activeView === "outfits" && outfitMode === "pieces" ? "Add a Piece, Matching Set, or Finisher" : "Create Outfit or Scene values directly";
    }
    const importLogs = root.querySelector("[data-import-logs]"); if (importLogs) {
        const allowed = activeView === "scenes" || (activeView === "outfits" && outfitMode === "looks");
        importLogs.style.display = allowed ? "inline-block" : "none"; importLogs.textContent = activeView === "scenes" ? "Import scene logs" : "Import outfit logs";
    }
    const migrateLooks = root.querySelector("[data-migrate-looks]"); if (migrateLooks) { migrateLooks.style.display = activeView === "outfits" ? "inline-block" : "none"; const pending = Number(wardrobeMigrationStatus.new || 0); migrateLooks.textContent = pending ? `MIGRATE LOOKS · ${pending.toLocaleString()} NEW` : "MIGRATE LOOKS"; }
    const exportWardrobe = root.querySelector("[data-export-wardrobe]"); if (exportWardrobe) exportWardrobe.style.display = activeView === "outfits" ? "inline-block" : "none";
    const importWardrobe = root.querySelector("[data-import-wardrobe]"); if (importWardrobe) importWardrobe.style.display = activeView === "outfits" ? "inline-block" : "none";
    const catalogButton = root.querySelector("[data-catalog-run]"); if (catalogButton) catalogButton.style.display = (["recipes", "prompts", "scenes", "outfits"].includes(activeView)) ? "inline-block" : "none";
    const purgeMenu = root.querySelector("[data-library-menu-purge]"); if (purgeMenu) { purgeMenu.disabled = Boolean(catalogRun); purgeMenu.style.opacity = catalogRun ? ".42" : "1"; }
    const currentMenuSection = root.querySelector("[data-library-menu-current]"); if (currentMenuSection) {
        const visible = [...currentMenuSection.querySelectorAll("[data-library-menu-context-action]")].some(button => button.style.display !== "none");
        currentMenuSection.style.display = visible ? "block" : "none";
    }
    const collectionDivider = root.querySelector("[data-collection-divider]"); if (collectionDivider) collectionDivider.style.display = activeView === "outfits" && outfitMode !== "looks" ? "none" : "inline";
    const bulkDivider = root.querySelector("[data-bulk-divider]"); if (bulkDivider) bulkDivider.style.display = ["recipes", "prompts"].includes(activeView) || (activeView === "outfits" && outfitMode !== "looks") ? "none" : "inline";
    const libraryTools = root.querySelector("[data-library-tools]"); if (libraryTools) libraryTools.style.display = libraryBootstrapping || (activeView === "outfits" && outfitMode !== "looks") ? "none" : "flex";
}

function recipeCollectionIds(recipe) {
    return new Set((recipe?.collections || []).map(collection => String(collection?.collection_id || "")).filter(Boolean));
}

function isDerivedCollection(value = activeCollection) {
    return value === AUTO_OUTFITS || value === AUTO_SCENES;
}

function derivedKind(value = activeCollection) {
    if (value === AUTO_OUTFITS) return "outfit";
    if (value === AUTO_SCENES) return "scene";
    return "";
}

function currentComponentKind() {
    if (activeView === "outfits" && outfitMode === "looks") return "outfit";
    return activeView === "scenes" ? "scene" : "";
}

function currentCatalogKind() {
    if (activeView === "recipes") return "template";
    if (activeView === "prompts") return "prompt";
    if (activeView === "outfits" && outfitMode === "pieces") return "piece";
    if (activeView === "outfits" && outfitMode === "looks") return "outfit";
    return activeView === "scenes" ? "scene" : "";
}

function resetWardrobeSelection(keepMode = true) {
    selectedWardrobeIds.clear();
    wardrobeSelectAllFiltered = false;
    if (!keepMode) wardrobeSelectionMode = false;
}

function wardrobeSelectionCount() {
    return wardrobeSelectAllFiltered ? wardrobeEntries().length : selectedWardrobeIds.size;
}

function wardrobeSelectedIds() {
    if (wardrobeSelectAllFiltered) return wardrobeEntries().map(item => String(item.wardrobe_id || "")).filter(Boolean);
    return [...selectedWardrobeIds];
}

function toggleWardrobeSelection(wardrobeId) {
    const id = String(wardrobeId || "");
    if (!id) return;
    if (wardrobeSelectAllFiltered) {
        wardrobeSelectAllFiltered = false;
        selectedWardrobeIds = new Set(wardrobeEntries().map(item => String(item.wardrobe_id || "")).filter(Boolean));
    }
    if (selectedWardrobeIds.has(id)) selectedWardrobeIds.delete(id);
    else selectedWardrobeIds.add(id);
    wardrobeSelectionMode = true;
    render();
}

function wardrobeEntries() {
    // Only Pieces and Matching Sets are visual catalog cards. Finishers and Body Styling live in Builder extras.
    let rows = wardrobeItems.filter(item => ["piece", "set"].includes(String(item.item_type || "piece")));
    if (wardrobeCategory) rows = rows.filter(item => String(item.category || "Uncategorized") === wardrobeCategory);
    if (wardrobeSubtype) rows = rows.filter(item => String(item.subtype || "") === wardrobeSubtype);
    if (activeLibraryCollection.wardrobe) rows = rows.filter(item => (item.pack_collections || []).some(group => String(group.collection_id || "") === String(activeLibraryCollection.wardrobe)));
    const query = wardrobeSearch.trim().toLowerCase();
    if (query) rows = rows.filter(item => String(item.value || "").toLowerCase().includes(query));
    if (wardrobeRatingFilter) {
        rows = rows.filter(item => {
            const rating = Math.max(0, Math.min(5, Number(item.rating || 0)));
            if (wardrobeRatingFilter === "unrated") return rating === 0;
            if (wardrobeRatingFilter === "5") return rating === 5;
            if (wardrobeRatingFilter === "4plus") return rating >= 4;
            if (wardrobeRatingFilter === "3plus") return rating >= 3;
            if (wardrobeRatingFilter === "low") return rating >= 1 && rating <= 2;
            return true;
        });
    }
    if (wardrobeThumbnailFilter) {
        rows = rows.filter(item => {
            const preview = Boolean(String(item.preview_ref || ""));
            if (wardrobeThumbnailFilter === "missing") return !preview;
            if (wardrobeThumbnailFilter === "catalog") return preview && String(item.preview_source || "").startsWith("generated:catalog");
            return true;
        });
    }
    if (wardrobeReviewFilter) {
        rows = rows.filter(item => {
            const flags = Array.isArray(item.review_flags) ? item.review_flags : [];
            if (wardrobeReviewFilter === "needs_review") return flags.length > 0;
            if (wardrobeReviewFilter === "compound") return flags.includes("compound");
            if (wardrobeReviewFilter === "generic") return flags.includes("generic");
            return true;
        });
    }
    const byName = (a, b) => String(a.value || "").localeCompare(String(b.value || ""), undefined, { sensitivity: "base" });
    rows.sort((a, b) => {
        if (wardrobeSort === "name") return byName(a, b);
        if (wardrobeSort === "rating") return Number(b.rating || 0) - Number(a.rating || 0) || byName(a, b);
        if (wardrobeSort === "preview_newest") {
            const aHas = Boolean(String(a.preview_ref || "")), bHas = Boolean(String(b.preview_ref || ""));
            if (aHas !== bHas) return bHas ? 1 : -1;
            const at = Date.parse(String(a.preview_updated_at || a.updated_at || "")) || 0;
            const bt = Date.parse(String(b.preview_updated_at || b.updated_at || "")) || 0;
            return bt - at || byName(a, b);
        }
        return String(b.created_at || "").localeCompare(String(a.created_at || "")) || byName(a, b);
    });
    return rows;
}

function derivedEntries(kind = currentComponentKind() || derivedKind()) {
    let rows = kind === "outfit" ? [...(derivedValues.outfits || [])] : kind === "scene" ? [...(derivedValues.scenes || [])] : [];
    if (!["outfit", "scene"].includes(kind)) return rows;

    if (activeCollection === "unfiled") rows = rows.filter(asset => !(asset.collections || []).length);
    else if (activeCollection) {
        const scopeIds = componentCollectionScopeIds(kind, activeCollection);
        rows = rows.filter(asset => (asset.collections || []).some(collection => scopeIds.has(String(collection.collection_id || ""))));
    }
    if (activeLibraryCollection[kind]) rows = rows.filter(asset => (asset.pack_collections || []).some(group => String(group.collection_id || "") === String(activeLibraryCollection[kind])));

    const query = String(componentSearch[kind] || "").trim().toLowerCase();
    if (query) rows = rows.filter(asset => String(asset.value || "").toLowerCase().includes(query));

    const ratingFilter = String(componentRatingFilter[kind] || "");
    if (ratingFilter) {
        rows = rows.filter(asset => {
            const rating = Math.max(0, Math.min(5, Number(asset.rating || 0)));
            if (ratingFilter === "unrated") return rating === 0;
            if (ratingFilter === "5") return rating === 5;
            if (ratingFilter === "4plus") return rating >= 4;
            if (ratingFilter === "3plus") return rating >= 3;
            if (ratingFilter === "low") return rating >= 1 && rating <= 2;
            return true;
        });
    }

    const thumbnailFilter = String(componentThumbnailFilter[kind] || "");
    if (thumbnailFilter) {
        rows = rows.filter(asset => {
            const preview = String(asset.preview_ref || "");
            const source = String(asset.preview_source || "");
            if (thumbnailFilter === "missing") return !preview;
            if (thumbnailFilter === "catalog") return Boolean(preview) && source.startsWith("generated:catalog");
            if (thumbnailFilter === "other") return Boolean(preview) && !source.startsWith("generated:catalog");
            return true;
        });
    }

    const sortMode = String(componentSort[kind] || "recent");
    const byName = (a, b) => String(a.value || "").localeCompare(String(b.value || ""), undefined, { sensitivity: "base" });
    rows.sort((a, b) => {
        if (sortMode === "name") return byName(a, b);
        if (sortMode === "rating") return Number(b.rating || 0) - Number(a.rating || 0) || byName(a, b);
        if (sortMode === "most_used") return Number(b.uses || 0) - Number(a.uses || 0) || byName(a, b);
        if (sortMode === "least_used") return Number(a.uses || 0) - Number(b.uses || 0) || byName(a, b);
        if (sortMode === "preview_newest") {
            const aHasPreview = Boolean(String(a.preview_ref || ""));
            const bHasPreview = Boolean(String(b.preview_ref || ""));
            if (aHasPreview !== bHasPreview) return bHasPreview ? 1 : -1;
            const previewTime = value => typeof value === "number" ? value : (Date.parse(String(value || "")) || 0);
            const previewDelta = previewTime(b.preview_updated_at) - previewTime(a.preview_updated_at);
            if (previewDelta) return previewDelta;
            return String(b.updated_at || b.created_at || "").localeCompare(String(a.updated_at || a.created_at || "")) || byName(a, b);
        }
        return String(b.created_at || "").localeCompare(String(a.created_at || "")) || byName(a, b);
    });
    return rows;
}

function componentCollectionById(kind, collectionId) {
    const id = String(collectionId || "");
    return (componentCollections[kind] || []).find(collection => String(collection.collection_id || "") === id) || null;
}

function componentCollectionScopeIds(kind, collectionId) {
    const id = String(collectionId || "");
    if (!id || id === "unfiled") return new Set(id ? [id] : []);
    const groups = componentCollections[kind] || [];
    const selected = componentCollectionById(kind, id);
    const ids = new Set([id]);
    if (selected && !String(selected.parent_id || "")) {
        for (const child of groups) if (String(child.parent_id || "") === id) ids.add(String(child.collection_id || ""));
    }
    return ids;
}

function sceneTaxonomyTree(kind = "scene") {
    const groups = componentCollections[kind] || [];
    const parents = groups.filter(group => !String(group.parent_id || ""));
    const children = new Map();
    for (const parent of parents) children.set(String(parent.collection_id || ""), []);
    for (const group of groups) {
        const parentId = String(group.parent_id || "");
        if (parentId && children.has(parentId)) children.get(parentId).push(group);
    }
    // componentCollections already arrives in the user's persisted manual order.
    // Preserve it here instead of quietly alphabetizing the taxonomy again.
    return { parents, children };
}

function componentCollectionDisplayName(kind, collection) {
    if (!collection) return "";
    const canonical = componentCollectionById(kind, collection.collection_id) || collection;
    const name = String(canonical.name || collection.name || "");
    if (!String(canonical.parent_id || "")) return name;
    const parent = componentCollectionById(kind, canonical.parent_id);
    return parent ? `${parent.name} / ${name}` : name;
}

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function componentPageSize(kind = currentComponentKind()) {
    const list = root?.querySelector("[data-recipes]");
    const width = Math.max(260, Number(list?.clientWidth || 1200) - 28);
    const gap = 14;
    const minimumCardWidth = kind === "scene" ? 250 : 220;
    const columns = Math.max(1, Math.floor((width + gap) / (minimumCardWidth + gap)));
    return Math.max(12, Math.min(84, columns * 4));
}

function recipeIsTemplate(recipe) {
    const tokens = recipeTokens(recipe?.payload);
    return tokens.includes("OUTFIT") || tokens.includes("SCENE");
}

function visibleRecipes() {
    return recipes.filter(recipe => {
        const matchesToken = !activeToken || recipeTokens(recipe.payload).includes(activeToken);
        const recipeCollections = recipeCollectionIds(recipe);
        const matchesCollection = !activeCollection || (activeCollection === "unfiled" ? !recipeCollections.size : recipeCollections.has(activeCollection));
        return matchesToken && matchesCollection;
    });
}

function pruneRecipeSelection() {
    const existingRecipes = new Set(recipes.map(recipe => String(recipe.recipe_id)));
    selectedRecipeIds = new Set([...selectedRecipeIds].filter(recipeId => existingRecipes.has(recipeId)));
    const existingComponents = new Set([...(derivedValues.outfits || []), ...(derivedValues.scenes || [])].map(asset => String(asset.component_id || "")).filter(Boolean));
    selectedComponentIds = new Set([...selectedComponentIds].filter(componentId => existingComponents.has(componentId)));
}

function toggleRecipeSelection(recipeId, force = null) {
    const id = String(recipeId || "");
    if (!id) return;
    const selected = selectedRecipeIds.has(id);
    const next = force == null ? !selected : Boolean(force);
    if (next) selectedRecipeIds.add(id);
    else selectedRecipeIds.delete(id);
    renderBulkControls();
    render();
}

function toggleComponentSelection(componentId, force = null) {
    const id = String(componentId || "");
    if (!id) return;
    const selected = selectedComponentIds.has(id);
    const next = force == null ? !selected : Boolean(force);
    if (next) selectedComponentIds.add(id);
    else selectedComponentIds.delete(id);
    renderBulkControls();
    render();
}

function currentSelectionCount() {
    return ["outfits", "scenes"].includes(activeView) ? selectedComponentIds.size : selectedRecipeIds.size;
}

function setSelectionMode(enabled) {
    selectionMode = Boolean(enabled);
    if (!selectionMode) { selectedRecipeIds.clear(); selectedComponentIds.clear(); }
    renderBulkControls();
    render();
}

function selectVisibleRecipes() {
    selectionMode = true;
    if (activeView === "prompts") {
        for (const asset of visiblePromptAssets()) if (asset.recipe_id) selectedRecipeIds.add(String(asset.recipe_id));
    } else if (activeView === "outfits" || activeView === "scenes") {
        const kind = currentComponentKind();
        for (const asset of derivedEntries(kind)) if (asset.component_id) selectedComponentIds.add(String(asset.component_id));
    } else {
        for (const recipe of visibleRecipes()) selectedRecipeIds.add(String(recipe.recipe_id));
    }
    renderBulkControls();
    render();
}

function clearRecipeSelection() {
    selectedRecipeIds.clear();
    selectedComponentIds.clear();
    renderBulkControls();
    render();
}

function renderBulkControls() {
    const holder = root?.querySelector("[data-recipe-bulk-controls]");
    if (!holder) return;
    if (["recipes", "prompts", "fragments"].includes(activeView)) { holder.style.display = "none"; return; }
    if (activeView === "outfits" && outfitMode !== "looks") { holder.style.display = "none"; return; }
    holder.style.display = "contents";
    const componentView = activeView === "scenes" || (activeView === "outfits" && outfitMode === "looks");
    const count = currentSelectionCount();
    const toggle = holder.querySelector("[data-bulk-select-toggle]");
    const selectVisible = holder.querySelector("[data-bulk-select-visible]");
    const selectedCount = holder.querySelector("[data-bulk-selected-count]");
    const addCollections = holder.querySelector("[data-bulk-add-collections]");
    const moveHome = holder.querySelector("[data-bulk-move-home]");
    if (moveHome) moveHome.style.display = componentView && selectionMode && count ? "inline-block" : "none";
    const removeCollection = holder.querySelector("[data-bulk-remove-collection]");
    const remove = holder.querySelector("[data-bulk-delete]");
    const deleteThumbs = holder.querySelector("[data-bulk-delete-thumbnails]");
    const regenerateThumbs = holder.querySelector("[data-bulk-regenerate-thumbnails]");
    const clear = holder.querySelector("[data-bulk-clear]");

    if (toggle) {
        toggle.textContent = selectionMode ? "DONE SELECTING" : "SELECT";
        toggle.style.borderColor = selectionMode ? "#ff4ab8" : "#35d7ffaa";
        toggle.style.background = selectionMode ? "rgba(255,74,184,.16)" : "#25232d";
    }
    if (selectVisible) {
        selectVisible.style.display = selectionMode ? "inline-block" : "none";
        if (componentView) {
            const kind = currentComponentKind();
            const hasSearch = Boolean(String(componentSearch[kind] || "").trim());
            selectVisible.textContent = hasSearch ? "SELECT FILTERED VIEW" : (activeCollection ? "SELECT COLLECTION" : "SELECT CURRENT VIEW");
        } else selectVisible.textContent = "SELECT VISIBLE";
    }
    if (selectedCount) {
        selectedCount.style.display = selectionMode ? "inline-flex" : "none";
        selectedCount.textContent = `${count} SELECTED`;
    }
    if (addCollections) addCollections.style.display = selectionMode && count && (activeView === "prompts" || componentView) ? "inline-block" : "none";
    if (removeCollection) {
        const inPack = componentView && activeLibraryCollection[currentComponentKind()];
        removeCollection.textContent = inPack ? "REMOVE FROM COLLECTION" : "REMOVE FROM HOME";
        removeCollection.style.display = componentView && selectionMode && count && (inPack || (activeCollection && activeCollection !== "unfiled")) ? "inline-block" : "none";
    }
    if (remove) remove.style.display = selectionMode && count && (activeView === "recipes" || componentView) ? "inline-block" : "none";
    if (deleteThumbs) deleteThumbs.style.display = componentView && selectionMode && count ? "inline-block" : "none";
    if (regenerateThumbs) regenerateThumbs.style.display = componentView && selectionMode && count ? "inline-block" : "none";
    if (clear) clear.style.display = selectionMode && count ? "inline-block" : "none";
}

function showImportedRecipesCollectionEditor(recipeIds) {
    const ids = Array.from(new Set((recipeIds || []).map(value => String(value || "")).filter(Boolean)));
    if (!ids.length || !collections.length) return;
    const { overlay, card } = collectionModal(`ORGANIZE ${ids.length} IMPORTED PROMPT${ids.length === 1 ? "" : "S"}`);
    const body = document.createElement("div");
    Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const help = document.createElement("div");
    help.textContent = `Add all ${ids.length} freshly imported ready prompt${ids.length === 1 ? "" : "s"} to one or more Prompt collections now. You can skip this and organize them later.`;
    Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.45", marginBottom: "12px" });
    body.append(help);

    for (const collection of collections) {
        const label = document.createElement("label");
        Object.assign(label.style, { display: "flex", alignItems: "center", gap: "9px", padding: "9px 10px", marginBottom: "6px", border: `1px solid ${collection.color || "#b89aff"}66`, borderRadius: "8px", cursor: "pointer" });
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = collection.collection_id;
        const dot = document.createElement("span");
        Object.assign(dot.style, { width: "9px", height: "9px", borderRadius: "99px", background: collection.color || "#b89aff" });
        const name = document.createElement("span");
        name.textContent = `${collection.name} · ${collection.recipe_count || 0}`;
        name.style.flex = "1";
        label.append(checkbox, dot, name);
        body.append(label);
    }

    const footer = document.createElement("div");
    Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const skip = action("Skip for now", "#8f8997");
    skip.onclick = () => overlay.remove();
    const save = action(`Add all ${ids.length} to collections`, "#6ee7a2");
    save.onclick = async () => {
        const collectionIds = [...body.querySelectorAll('input[type="checkbox"]:checked')].map(item => item.value);
        if (!collectionIds.length) {
            alert("Choose at least one collection.");
            return;
        }
        save.disabled = true;
        skip.disabled = true;
        try {
            const result = await request("/recipes/bulk/collections", {
                method: "POST",
                body: JSON.stringify({ recipe_ids: ids, collection_ids: collectionIds }),
            });
            await load();
            const recipeCount = result.recipes || ids.length;
            const collectionCount = result.collections || collectionIds.length;
            catalogStatus(`Added all ${recipeCount} imported prompt${recipeCount === 1 ? "" : "s"} to ${collectionCount} collection${collectionCount === 1 ? "" : "s"}.`);
            overlay.remove();
        } catch (error) {
            alert(error.message || "Could not organize the imported recipes.");
        } finally {
            save.disabled = false;
            skip.disabled = false;
        }
    };
    footer.append(skip, save);
    card.append(body, footer);
}

function showBulkCollectionEditor() {
    if (["outfits", "scenes"].includes(activeView)) return showBulkComponentCollectionEditor(currentComponentKind());
    const recipeIds = [...selectedRecipeIds];
    if (!recipeIds.length) return;
    const targetLabel = activeView === "prompts" ? "PROMPTS" : "RECIPES";
    const { overlay, card } = collectionModal(`ADD ${recipeIds.length} ${targetLabel} TO COLLECTIONS`);
    const body = document.createElement("div");
    Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const help = document.createElement("div");
    help.textContent = activeView === "prompts"
        ? "Choose the Prompt collections to add to every selected prompt. Existing collection memberships stay exactly as they are."
        : "Choose the collections to add to every selected saved Recipe. Existing memberships stay exactly as they are.";
    Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.45", marginBottom: "12px" });
    body.append(help);

    if (!collections.length) {
        const empty = document.createElement("div");
        empty.textContent = "Create a collection first with the Collections button in the Creative Library toolbar.";
        Object.assign(empty.style, { color: "#f6e65a", padding: "8px 0" });
        body.append(empty);
    } else {
        for (const collection of collections) {
            const label = document.createElement("label");
            Object.assign(label.style, { display: "flex", alignItems: "center", gap: "9px", padding: "9px 10px", marginBottom: "6px", border: `1px solid ${collection.color || "#b89aff"}66`, borderRadius: "8px", cursor: "pointer" });
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.value = collection.collection_id;
            const dot = document.createElement("span");
            Object.assign(dot.style, { width: "9px", height: "9px", borderRadius: "99px", background: collection.color || "#b89aff" });
            const name = document.createElement("span");
            name.textContent = `${collection.name} · ${collection.recipe_count || 0}`;
            name.style.flex = "1";
            label.append(checkbox, dot, name);
            body.append(label);
        }
    }

    const footer = document.createElement("div");
    Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997");
    cancel.onclick = () => overlay.remove();
    const save = action("Add to collections", "#6ee7a2");
    save.disabled = !collections.length;
    save.style.opacity = collections.length ? "1" : ".45";
    save.onclick = async () => {
        const collectionIds = [...body.querySelectorAll('input[type="checkbox"]:checked')].map(item => item.value);
        if (!collectionIds.length) {
            alert("Choose at least one collection.");
            return;
        }
        save.disabled = true;
        try {
            const result = await request("/recipes/bulk/collections", {
                method: "POST",
                body: JSON.stringify({ recipe_ids: recipeIds, collection_ids: collectionIds }),
            });
            selectedRecipeIds.clear();
            await load();
            renderBulkControls();
            catalogStatus(`Added ${result.recipes || recipeIds.length} ${activeView === "prompts" ? "prompts" : "Recipes"} to ${result.collections || collectionIds.length} collection${(result.collections || collectionIds.length) === 1 ? "" : "s"}.`);
            overlay.remove();
        } catch (error) {
            alert(error.message || "Could not update the selected recipes.");
        } finally {
            save.disabled = false;
        }
    };
    footer.append(cancel, save);
    card.append(body, footer);
}

function showBulkComponentHomeEditor(kind) {
    const componentIds = [...selectedComponentIds];
    if (!componentIds.length || !["outfit", "scene"].includes(kind)) return;
    const groups = componentCollections[kind] || [];
    const labelText = kind === "outfit" ? "OUTFITS" : "SCENES";
    const accent = kind === "outfit" ? "#ff4ab8" : "#63e6a4";
    const { overlay, card } = collectionModal(`MOVE ${componentIds.length} ${labelText} TO HOME`);
    const body = document.createElement("div");
    Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const help = document.createElement("div");
    help.textContent = "Choose one canonical Home for every selected asset. Moving Home changes where the assets live; their many-to-many Collections and previews remain unchanged.";
    Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.45", marginBottom: "12px" });
    body.append(help);
    if (!groups.length) {
        const empty = document.createElement("div"); empty.textContent = `Create a ${kind === "scene" ? "Scene" : "Look"} Home first.`; Object.assign(empty.style, { color: "#f6e65a", padding: "8px 0" }); body.append(empty);
    } else {
        const ordered = [];
        if (["outfit", "scene"].includes(kind)) {
            const { parents, children } = sceneTaxonomyTree(kind);
            for (const parent of parents) {
                ordered.push({ collection: parent, depth: 0 });
                for (const child of children.get(String(parent.collection_id || "")) || []) ordered.push({ collection: child, depth: 1 });
            }
        } else {
            for (const collection of groups) ordered.push({ collection, depth: 0 });
        }
        for (const entry of ordered) {
            const collection = entry.collection;
            const row = document.createElement("label");
            Object.assign(row.style, { display: "flex", alignItems: "center", gap: "9px", padding: "9px 10px", paddingLeft: entry.depth ? "26px" : "10px", marginBottom: "6px", border: `1px solid ${collection.color || accent}66`, borderRadius: "8px", cursor: "pointer", background: entry.depth ? "rgba(255,255,255,.015)" : "rgba(99,230,164,.025)" });
            const checkbox = document.createElement("input"); checkbox.type = "radio"; checkbox.name = `component-home-${kind}`; checkbox.value = collection.collection_id;
            const dot = document.createElement("span"); Object.assign(dot.style, { width: "9px", height: "9px", borderRadius: "99px", background: collection.color || accent });
            const name = document.createElement("span"); name.textContent = `${entry.depth ? "↳  " : ""}${collection.name} · ${collection.asset_count || 0}`; name.style.flex = "1";
            row.append(checkbox, dot, name); body.append(row);
        }
    }
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const save = action("MOVE TO HOME", accent); save.disabled = !groups.length; save.style.opacity = groups.length ? "1" : ".45";
    save.onclick = async () => {
        const collectionIds = [...body.querySelectorAll('input[type="radio"]:checked')].map(item => item.value);
        if (collectionIds.length !== 1) { alert("Choose one Home."); return; }
        save.disabled = true;
        try {
            const result = await request("/derived-values/bulk/collections", { method: "POST", body: JSON.stringify({ component_ids: componentIds, collection_ids: collectionIds, replace_home: true }) });
            selectedComponentIds.clear();
            await load();
            catalogStatus(`Moved ${result.assets || componentIds.length} ${kind}${(result.assets || componentIds.length) === 1 ? "" : "s"} to one Home.`);
            overlay.remove();
        } catch (error) { alert(error.message || `Could not organize the selected ${kind}s.`); }
        finally { save.disabled = false; }
    };
    footer.append(cancel, save); card.append(body, footer);
}

async function removeSelectedComponentsFromActiveCollection() {
    const componentIds = [...selectedComponentIds];
    const kind = currentComponentKind();
    if (!componentIds.length || !kind) return;
    const packId = activeLibraryCollection[kind];
    if (packId) {
        if (!confirm(`Remove ${componentIds.length} selected assets from this Collection?`)) return;
        try {
            await request("/library-collections/bulk/remove", { method: "POST", body: JSON.stringify({ kind, asset_ids: componentIds, collection_id: packId }) });
            selectedComponentIds.clear(); await refreshLibraryCollectionKind(kind); await load();
            catalogStatus("Removed selected assets from the Collection.");
        } catch (error) { alert(error.message || "Could not remove collection memberships."); }
        return;
    }
    if (!activeCollection || activeCollection === "unfiled") return;
    const collection = componentCollectionById(kind, activeCollection);
    if (!collection) return;
    const scopeIds = [...componentCollectionScopeIds(kind, activeCollection)].filter(id => id && id !== "unfiled");
    const noun = kind === "scene" ? (String(collection.parent_id || "") ? "folder" : "category") : "collection";
    if (!confirm(`Remove ${componentIds.length} selected ${kind}${componentIds.length === 1 ? "" : "s"} from “${collection.name}” ${noun}? The assets themselves stay in the Library.`)) return;
    try {
        const result = await request("/derived-values/bulk/collections/remove", { method: "POST", body: JSON.stringify({ component_ids: componentIds, collection_ids: scopeIds }) });
        selectedComponentIds.clear();
        await load();
        catalogStatus(`Removed ${result.memberships_removed || 0} ${kind === "scene" ? "biome" : "collection"} membership${Number(result.memberships_removed || 0) === 1 ? "" : "s"}.`, "#ffcf75");
    } catch (error) { alert(error.message || `Could not remove the selected ${kind}s from this ${noun}.`); }
}

async function deleteSelectedComponents() {
    const componentIds = [...selectedComponentIds];
    const kind = currentComponentKind();
    if (!componentIds.length || !kind) return;
    const everywhere = kind === "scene" || kind === "outfit";
    const deleteLabel = kind === "outfit" ? "Outfit Look" : "Scene";
    const prompt = everywhere
        ? `DELETE EVERYWHERE for ${componentIds.length} selected ${deleteLabel}${componentIds.length === 1 ? "" : "s"}? This removes the canonical ${deleteLabel}${componentIds.length === 1 ? "" : "s"} and Catalog thumbnail${componentIds.length === 1 ? "" : "s"} from the Library. Saved Recipes keep their provenance, but these values are tombstoned so old Recipes and source logs cannot silently recreate them.`
        : `Delete ${componentIds.length} selected ${kind}${componentIds.length === 1 ? "" : "s"} from the manual Creative Library? Values still used by saved Recipes remain available from those Recipes.`;
    if (!confirm(prompt)) return;
    try {
        const result = await request("/derived-values/bulk/delete", { method: "POST", body: JSON.stringify({ component_ids: componentIds, everywhere }) });
        selectedComponentIds.clear(); selectionMode = false;
        await load();
        if (everywhere) {
            catalogStatus(`DELETE EVERYWHERE · removed ${result.deleted || 0} ${deleteLabel}${Number(result.deleted || 0) === 1 ? "" : "s"}${Number(result.tombstoned || 0) ? ` · ${result.tombstoned} tombstoned against resurrection` : ""}.`, "#ff6d9d");
        } else {
            const kept = Number(result.remaining_from_recipes || 0) + Number(result.protected || 0);
            catalogStatus(`Removed ${result.deleted || 0} manual ${kind}${Number(result.deleted || 0) === 1 ? "" : "s"}${kept ? ` · ${kept} recipe-derived value${kept === 1 ? "" : "s"} kept` : ""}.`, "#ff8fce");
        }
    } catch (error) { alert(error.message || `Could not delete the selected ${kind}s.`); }
}

async function deleteSelectedRecipes() {
    if (["outfits", "scenes"].includes(activeView)) return deleteSelectedComponents();
    const recipeIds = [...selectedRecipeIds];
    if (!recipeIds.length) return;
    const noun = activeView === "recipes" ? "Recipe" : "prompt";
    if (!confirm(`Delete ${recipeIds.length} selected ${noun}${recipeIds.length === 1 ? "" : "s"}? Saved thumbnails for those records will also be removed.`)) return;
    try {
        const result = await request("/recipes/bulk/delete", {
            method: "POST",
            body: JSON.stringify({ recipe_ids: recipeIds }),
        });
        selectedRecipeIds.clear();
        selectionMode = false;
        await load();
        catalogStatus(`Deleted ${result.deleted || recipeIds.length} ${noun}${(result.deleted || recipeIds.length) === 1 ? "" : "s"}.`, "#ff8fce");
    } catch (error) {
        alert(error.message || "Could not delete the selected recipes.");
    }
}

function promptAssetRecipe(asset) {
    return recipeIndex.get(String(asset?.recipe_id || "")) || (asset ? {
        recipe_id: String(asset.recipe_id || ""),
        name: String(asset.name || "Prompt"),
        collections: Array.isArray(asset.collections) ? asset.collections : [],
        payload: {},
    } : null);
}

function visiblePromptAssets() {
    return promptAssets || [];
}

function pagedPromptAssets() {
    return visiblePromptAssets();
}

function promptPageParams() {
    const params = new URLSearchParams();
    params.set("kind", activePromptKind());
    params.set("limit", String(PROMPT_PAGE_SIZE));
    params.set("offset", String(Math.max(0, Number(promptPage || 0)) * PROMPT_PAGE_SIZE));
    params.set("sort", String(promptSort || "preview_newest"));
    if (String(promptSearch || "").trim()) params.set("q", String(promptSearch).trim());
    if (promptParent) params.set("parent", String(promptParent));
    if (promptSubcategory) params.set("subcategory", String(promptSubcategory));
    if (promptLogPath) params.set("log", String(promptLogPath));
    if (activeCollection) params.set("collection", String(activeCollection));
    if (promptRatingFilter) params.set("rating", String(promptRatingFilter));
    for (const token of promptPlaceholderFilters) params.append("placeholder", String(token));
    for (const axis of PROMPT_FACET_AXES) {
        if (promptFacetFilters[axis]) params.set(axis, String(promptFacetFilters[axis]));
    }
    return params;
}

async function fetchPromptYearbookScope(kind) {
    const params = promptPageParams();
    params.set("kind", kind);
    params.set("offset", "0");
    params.set("limit", "0");
    params.set("include_all", "1");
    const data = await request(`/prompt-assets?${params.toString()}`);
    return Array.isArray(data?.prompts) ? data.prompts.map(item => ({ ...item, kind, catalog_preview_ref: String(item.preview_ref || "") })) : [];
}

async function fetchWholeLibraryYearbookInventory() {
    const [promptRows, templateRows, componentRows, wardrobeRows] = await Promise.all([
        request("/prompt-assets?kind=prompt&offset=0&limit=0&include_all=1"),
        request("/prompt-assets?kind=template&offset=0&limit=0&include_all=1"),
        request("/derived-values?sync=0"),
        request("/wardrobe-items"),
    ]);
    const prompts = Array.isArray(promptRows?.prompts)
        ? promptRows.prompts.map(item => ({ ...item, kind: "prompt", catalog_preview_ref: String(item.preview_ref || "") })) : [];
    const templates = Array.isArray(templateRows?.prompts)
        ? templateRows.prompts.map(item => ({ ...item, kind: "template", catalog_preview_ref: String(item.preview_ref || "") })) : [];
    const outfits = Array.isArray(componentRows?.outfits)
        ? componentRows.outfits.map(item => ({ ...item, kind: "outfit" })) : [];
    const scenes = Array.isArray(componentRows?.scenes)
        ? componentRows.scenes.map(item => ({ ...item, kind: "scene" })) : [];
    const pieces = Array.isArray(wardrobeRows?.items)
        ? wardrobeRows.items.filter(item => ["piece", "set"].includes(String(item?.item_type || "piece"))).map(item => ({ ...item, kind: "piece" })) : [];
    return { prompts, templates, outfits, pieces, scenes };
}

async function loadPromptPage() {
    const serial = ++promptLoadSerial;
    promptLoading = true;
    // Keep the current cards and focused search field alive until fresh rows
    // arrive. Replacing the whole gallery here made normal typing lose focus.
    const range = root?.querySelector("[data-prompt-page-range]");
    if (range) range.textContent = "Searching…";
    try {
        let data = null;
        for (let attempt = 0; attempt < 2; attempt += 1) {
            data = await request(`/prompt-assets?${promptPageParams().toString()}`);
            if (serial !== promptLoadSerial) return;
            const total = Math.max(0, Number(data?.total || 0));
            const lastPage = Math.max(0, Math.ceil(total / PROMPT_PAGE_SIZE) - 1);
            if (promptPage > lastPage) { promptPage = lastPage; continue; }
            break;
        }
        if (serial !== promptLoadSerial || !data) return;
        promptAssets = Array.isArray(data.prompts) ? data.prompts : [];
        promptTotal = Math.max(0, Number(data.total || 0));
        promptCorpusTotals = data.corpus_totals && typeof data.corpus_totals === "object" ? data.corpus_totals : promptCorpusTotals;
        const kind = String(data.kind || activePromptKind());
        if (kind === "prompt") promptAssetTotal = Math.max(promptTotal, Number(data.total_assets || 0));
        else promptBlueprintTotal = Math.max(promptTotal, Number(data.total_assets || 0));
        if (data.home_counts && typeof data.home_counts === "object") promptHomeCounts[kind] = data.home_counts;
        if (data.home_universe && typeof data.home_universe === "object") promptHomeUniverse[kind] = data.home_universe;
        if (kind === "template" && data.placeholder_counts && typeof data.placeholder_counts === "object") promptPlaceholderCounts = data.placeholder_counts;
        if (kind === "template" && data.placeholder_available_counts && typeof data.placeholder_available_counts === "object") promptPlaceholderAvailableCounts = data.placeholder_available_counts;
        promptFacetCounts = data.facet_counts && typeof data.facet_counts === "object" ? data.facet_counts : promptFacetCounts;
        promptFacetUniverse = data.facet_universe && typeof data.facet_universe === "object" ? data.facet_universe : promptFacetUniverse;
        promptFacetCovers = data.facet_covers && typeof data.facet_covers === "object" ? data.facet_covers : promptFacetCovers;
        promptBlueprintTotal = Math.max(0, Number(data.corpus_totals?.template || data.blueprints?.total || promptBlueprintTotal || 0));
        promptComponentBlueprintTotal = Math.max(0, Number(data.blueprints?.component_total || promptComponentBlueprintTotal || 0));
        promptBlueprintSignatures = data.blueprints?.signature_counts && typeof data.blueprints.signature_counts === "object" ? data.blueprints.signature_counts : promptBlueprintSignatures;
        if (data.collection_counts && typeof data.collection_counts === "object") promptCollectionCounts[kind] = data.collection_counts;
        promptAssetRevision += 1;
        promptViewCache = { key: "", rows: [] };
    } catch (error) {
        if (serial === promptLoadSerial) catalogStatus(error.message || "Could not load this Prompt Vault page.", "#ff78bd");
    } finally {
        if (serial === promptLoadSerial) {
            promptLoading = false;
            renderCollectionControls();
            renderBulkControls();
            render();
        }
    }
}

function queuePromptPageLoad(delay = 0) {
    if (promptLoadTimer) clearTimeout(promptLoadTimer);
    if (delay > 0) promptLoadTimer = setTimeout(() => { promptLoadTimer = null; void loadPromptPage(); }, delay);
    else { promptLoadTimer = null; void loadPromptPage(); }
}

function promptSelectionCount() { return promptSelectAllFiltered ? Number(promptTotal || 0) : selectedPromptIds.size; }
function togglePromptSelection(promptId) { const id = String(promptId || ""); if (!id) return; if (promptSelectAllFiltered) { promptSelectAllFiltered = false; selectedPromptIds = new Set(promptAssets.map(item => String(item.prompt_id || "")).filter(Boolean)); } if (selectedPromptIds.has(id)) selectedPromptIds.delete(id); else selectedPromptIds.add(id); promptSelectionMode = true; render(); }
function promptBulkFilters() { return { q: promptSearch, source: promptSourceFilter, collection: activeCollection, parent: promptParent, subcategory: promptSubcategory, log: promptLogPath, rating: promptRatingFilter, sort: promptSort, placeholders: [...promptPlaceholderFilters], facets: { ...promptFacetFilters } }; }
async function bulkPromptAssets(operation, parent = "", subcategory = "") { const amount = promptSelectAllFiltered ? Number(promptTotal || 0) : selectedPromptIds.size; if (!amount) { alert("Select Prompt records first."); return; } if (operation === "delete" && !confirm(`Archive or remove ${amount.toLocaleString()} selected catalog record${amount === 1 ? "" : "s"}?`)) return; try { const result = await request("/prompt-assets/bulk", { method: "POST", body: JSON.stringify({ operation, prompt_ids: [...selectedPromptIds], all_filtered: promptSelectAllFiltered, kind: activePromptKind(), parent, subcategory, filters: promptBulkFilters() }) }); selectedPromptIds.clear(); promptSelectAllFiltered = false; promptSelectionMode = false; await loadPromptPage(); catalogStatus(`${Number(result.changed || amount).toLocaleString()} catalog record${amount === 1 ? "" : "s"} updated.`, "#6ee7a2"); } catch (error) { alert(error.message || "Could not update selected catalog records."); } }

function fragmentPageParams() {
    const params = new URLSearchParams({
        limit: String(FRAGMENT_PAGE_SIZE), offset: String(Math.max(0, Number(fragmentPage || 0)) * FRAGMENT_PAGE_SIZE),
        state: String(fragmentState || "ready"), sort: String(fragmentSort || "rank"),
    });
    if (String(fragmentSearch || "").trim()) params.set("q", String(fragmentSearch).trim());
    if (fragmentRole) params.set("role", String(fragmentRole));
    return params;
}

async function loadFragmentPage() {
    const serial = ++fragmentLoadSerial; fragmentLoading = true; fragmentRows = []; render();
    try {
        let data = null;
        for (let attempt = 0; attempt < 2; attempt += 1) {
            data = await request(`/fragments?${fragmentPageParams().toString()}`); if (serial !== fragmentLoadSerial) return;
            const total = Math.max(0, Number(data?.total || 0)); const lastPage = Math.max(0, Math.ceil(total / FRAGMENT_PAGE_SIZE) - 1);
            if (fragmentPage > lastPage) { fragmentPage = lastPage; continue; } break;
        }
        if (serial !== fragmentLoadSerial || !data) return;
        fragmentRows = Array.isArray(data.fragments) ? data.fragments : []; fragmentTotal = Math.max(0, Number(data.total || 0));
        fragmentSummary = data.summary && typeof data.summary === "object" ? data.summary : fragmentSummary;
    } catch (error) { if (serial === fragmentLoadSerial) catalogStatus(error.message || "Could not load the Ingredient Catalog.", "#ff78bd"); }
    finally { if (serial === fragmentLoadSerial) { fragmentLoading = false; refreshLibraryChrome(); render(); } }
}

function queueFragmentPageLoad(delay = 0) {
    if (fragmentLoadTimer) clearTimeout(fragmentLoadTimer);
    if (delay > 0) fragmentLoadTimer = setTimeout(() => { fragmentLoadTimer = null; void loadFragmentPage(); }, delay);
    else { fragmentLoadTimer = null; void loadFragmentPage(); }
}

function promptFacetOptions(axis) {
    const counts = promptFacetCounts?.[axis] && typeof promptFacetCounts[axis] === "object" ? promptFacetCounts[axis] : {};
    return Object.entries(counts)
        .filter(([, count]) => Number(count || 0) > 0)
        .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0) || String(a[0]).localeCompare(String(b[0])));
}

function showComponentScopePicker(kind) {
    if (!["outfit", "scene"].includes(kind)) return;
    const accent = kind === "outfit" ? "#f6e65a" : "#63e6a4";
    const labelName = kind === "outfit" ? "OUTFIT" : "SCENE";
    const rows = kind === "outfit" ? (derivedValues.outfits || []) : (derivedValues.scenes || []);
    const groups = componentCollections[kind] || [];
    const { overlay, card } = collectionModal(`${labelName} HOME`, "680px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "9px", overflow: "auto" });
    const copy = document.createElement("div"); copy.textContent = kind === "scene"
        ? "Browse the canonical Scene Library by editable Category → Subcategory. TXT filenames are source provenance only; every Scene has one canonical card and one Catalog thumbnail."
        : "Choose where to browse. The selected Collection becomes the scope for search, ratings, selection, cleanup, and preview generation.";
    Object.assign(copy.style, { color: "#b8b0c1", fontSize: "11px", lineHeight: "1.45" });
    const search = document.createElement("input"); search.type = "search"; search.placeholder = "Find a Home, category, or subcategory…"; Object.assign(search.style, { width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: "8px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", outline: "none" });
    const list = document.createElement("div"); Object.assign(list.style, { display: "flex", flexDirection: "column", gap: "4px", maxHeight: "58vh", overflow: "auto" });
    const addChoice = (choice, depth = 0) => {
        const item = document.createElement("button"); item.type = "button";
        Object.assign(item.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "12px", alignItems: "center", width: "100%", padding: depth ? "8px 11px 8px 27px" : "10px 12px", borderRadius: "8px", cursor: "pointer", textAlign: "left", border: `1px solid ${String(activeCollection) === choice.id ? choice.color : "#34303b"}`, color: depth ? "#c8c1cd" : "#f5f1f7", background: String(activeCollection) === choice.id ? `${choice.color}22` : depth ? "#0f0d13" : "#121017" });
        const name = document.createElement(depth ? "span" : "strong"); name.textContent = `${depth ? "↳  " : ""}${choice.name}`; name.style.fontSize = depth ? "10px" : "11px";
        const count = document.createElement("span"); count.textContent = Number(choice.count || 0).toLocaleString(); Object.assign(count.style, { color: choice.color, font: "800 10px Segoe UI,Arial" });
        item.append(name, count);
        item.onclick = () => { activeCollection = choice.id; componentPage[kind] = 0; selectedComponentIds.clear(); overlay.remove(); renderCollectionControls(); renderBulkControls(); render(); };
        list.append(item);
    };
    const draw = () => {
        list.replaceChildren();
        const needle = search.value.trim().toLowerCase();
        const unsortedCount = rows.filter(asset => !(asset.collections || []).length).length;
        const universal = [
            { id: "", name: `All ${kind === "outfit" ? "Outfits" : "Scenes"}`, count: rows.length, color: accent },
            { id: "unfiled", name: kind === "scene" ? "Unsorted" : "Unfiled", count: unsortedCount, color: "#8f8997" },
        ].filter(choice => choice.id !== "unfiled" || kind === "scene" || choice.count > 0).filter(choice => !needle || choice.name.toLowerCase().includes(needle));
        universal.forEach(choice => addChoice(choice));
        if (kind !== "scene") {
            for (const group of groups) {
                if (needle && !String(group.name || "").toLowerCase().includes(needle)) continue;
                addChoice({ id: String(group.collection_id), name: String(group.name), count: Number(group.asset_count || 0), color: String(group.color || accent) });
            }
            return;
        }
        const { parents, children } = sceneTaxonomyTree();
        for (const parent of parents) {
            const childRows = children.get(String(parent.collection_id || "")) || [];
            const parentMatches = !needle || String(parent.name || "").toLowerCase().includes(needle);
            const matchingChildren = childRows.filter(child => !needle || String(child.name || "").toLowerCase().includes(needle));
            if (!parentMatches && !matchingChildren.length) continue;
            addChoice({ id: String(parent.collection_id), name: String(parent.name), count: Number(parent.asset_count || 0), color: String(parent.color || accent) });
            for (const child of (parentMatches ? childRows : matchingChildren)) addChoice({ id: String(child.collection_id), name: String(child.name), count: Number(child.asset_count || 0), color: String(child.color || accent) }, 1);
        }
    };
    search.oninput = draw; body.append(copy, search, list); card.append(body); draw(); requestAnimationFrame(() => search.focus());
}

function promptCollectionCount(collectionId, kind = activePromptKind()) {
    const key = String(collectionId || "");
    return Math.max(0, Number(promptShowcaseCounts(kind)?.[key] || 0));
}

function showPromptScopePicker() {
    const { overlay, card } = collectionModal("SAVED RECIPE COLLECTION", "620px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "9px", overflow: "auto" });
    const copy = document.createElement("div"); copy.textContent = "The canonical corpus is organized by the visual smart folders above, not dumped into an ‘Unfiled’ bucket. Use this only to narrow the Vault to a collection attached to a saved Recipe."; Object.assign(copy.style, { color: "#b8b0c1", fontSize: "11px", lineHeight: "1.45" });
    const search = document.createElement("input"); search.type = "search"; search.placeholder = "Find a saved Recipe collection…"; Object.assign(search.style, { width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: "8px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", outline: "none" });
    const list = document.createElement("div"); Object.assign(list.style, { display: "flex", flexDirection: "column", gap: "6px", maxHeight: "54vh", overflow: "auto" });
    const draw = () => {
        list.replaceChildren();
        const needle = search.value.trim().toLowerCase();
        const choices = [
            { id: "", name: "All Prompts", count: promptAssetTotal, color: "#35d7ff" },
            ...promptShowcaseFolders().map(collection => ({ id: String(collection.collection_id), name: String(collection.name), count: promptCollectionCount(String(collection.collection_id)), color: String(collection.color || "#b89aff") })),
        ].filter(choice => !needle || choice.name.toLowerCase().includes(needle));
        for (const choice of choices) {
            const item = document.createElement("button"); item.type = "button";
            Object.assign(item.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "12px", alignItems: "center", width: "100%", padding: "10px 12px", borderRadius: "8px", cursor: "pointer", textAlign: "left", border: `1px solid ${String(activeCollection) === choice.id ? choice.color : "#34303b"}`, color: "#f5f1f7", background: String(activeCollection) === choice.id ? `${choice.color}22` : "#121017" });
            const name = document.createElement("strong"); name.textContent = choice.name; name.style.fontSize = "11px";
            const count = document.createElement("span"); count.textContent = Number(choice.count || 0).toLocaleString(); Object.assign(count.style, { color: choice.color, font: "800 10px Segoe UI,Arial" });
            item.append(name, count);
            item.onclick = () => { activeCollection = choice.id; promptPage = 0; selectedRecipeIds.clear(); overlay.remove(); renderCollectionControls(); renderBulkControls(); queuePromptPageLoad(); };
            list.append(item);
        }
    };
    search.oninput = draw; body.append(copy, search, list); card.append(body); draw(); requestAnimationFrame(() => search.focus());
}

function renderCollectionControls() {
    const holder = root?.querySelector("[data-recipe-collections]");
    if (!holder) return;
    holder.replaceChildren();
    const addFilter = (label, id, color, count) => {
        const button = action(`${label} · ${count}`, color);
        const active = activeCollection === id;
        button.style.borderColor = active ? color : `${color}88`;
        button.style.background = active ? `${color}33` : "#25232d";
        button.onclick = () => { activeCollection = id; renderCollectionControls(); render(); };
        holder.append(button);
    };

    if ((activeView === "outfits" && outfitMode === "looks") || activeView === "scenes") {
        const kind = activeView === "outfits" ? "outfit" : "scene";
        const rows = kind === "outfit" ? (derivedValues.outfits || []) : (derivedValues.scenes || []);
        const groups = componentCollections[kind] || [];
        if (activeCollection && activeCollection !== "unfiled" && !groups.some(collection => String(collection.collection_id) === String(activeCollection))) activeCollection = "";
        const accent = LIBRARY_VIEWS[activeView].color;
        holder.hidden = false;
        Object.assign(holder.style, {
            display: "flex", flex: "0 0 100%", width: "100%", order: "-1", padding: "1px 0 7px",
            marginBottom: "2px", alignItems: "center", gap: "9px", borderBottom: `1px solid ${accent}26`,
        });
        const current = activeCollection === "unfiled"
            ? { name: kind === "scene" ? "Unsorted" : "Unfiled", count: rows.filter(asset => !(asset.collections || []).length).length }
            : groups.find(group => String(group.collection_id) === String(activeCollection)) || { name: `All ${activeView}`, count: rows.length };
        const browseLabel = document.createElement("span");
        browseLabel.textContent = "BROWSE LOCATION";
        Object.assign(browseLabel.style, { color: accent, font: "900 9px Segoe UI,Arial", letterSpacing: ".11em", whiteSpace: "nowrap" });
        const scopeName = String(current.name || `All ${activeView}`).toUpperCase();
        const scope = action(`▣ ${scopeName} · ${Number(current.asset_count ?? current.count ?? rows.length).toLocaleString()}  ▾`, accent);
        scope.title = "Choose the main collection / location filter";
        Object.assign(scope.style, {
            minWidth: "235px", padding: "11px 16px", borderWidth: "2px", borderColor: accent,
            background: `linear-gradient(180deg,${accent}30,${accent}12)`, boxShadow: `0 0 0 1px ${accent}16 inset,0 0 18px ${accent}18`,
            font: "900 12px Segoe UI,Arial", letterSpacing: ".025em", textAlign: "left",
        });
        scope.onclick = () => showComponentScopePicker(kind);
        holder.append(browseLabel, scope);
        return;
    }

    if (activeView === "prompts" && promptVaultOpen) {
        holder.hidden = true; holder.style.display = "none";
        if (activeCollection && !promptShowcaseFolders().some(collection => String(collection.collection_id) === String(activeCollection))) activeCollection = "";
        return;
    }

    const enabled = false;
    if (activeView === "outfits" && outfitMode !== "looks") { holder.hidden = true; holder.style.display = "none"; activeCollection = ""; return; }
    holder.hidden = !enabled; holder.style.display = enabled ? "flex" : "none";
    Object.assign(holder.style, { flex: "0 0 100%", width: "100%", order: "3", paddingTop: "2px", paddingBottom: "0", marginBottom: "0", borderBottom: "0", gap: "6px" });
    if (!enabled) { activeCollection = ""; return; }
    if (activeCollection && !promptShowcaseFolders().some(collection => collection.collection_id === activeCollection)) activeCollection = "";
    const selected = promptShowcaseFolders().find(collection => String(collection.collection_id) === String(activeCollection))
        || { name: "All Prompts", color: "#35d7ff", count: promptAssetTotal };
    const browseLabel = document.createElement("span"); browseLabel.textContent = "SAVED RECIPE COLLECTION"; Object.assign(browseLabel.style, { color: "#35d7ff", font: "900 9px Segoe UI,Arial", letterSpacing: ".11em", whiteSpace: "nowrap" });
    const scope = action(`▣ ${String(selected.name || "All Prompts").toUpperCase()} · ${Number(selected.count ?? promptCollectionCount(activeCollection)).toLocaleString()}  ▾`, String(selected.color || "#35d7ff"));
    Object.assign(scope.style, { minWidth: "235px", padding: "10px 14px", borderWidth: "2px", background: `linear-gradient(180deg,${String(selected.color || "#35d7ff")}2b,rgba(10,9,14,.94))`, font: "900 11px Segoe UI,Arial", letterSpacing: ".025em", textAlign: "left" });
    scope.onclick = showPromptScopePicker;
    holder.append(browseLabel, scope);
}

function renderComponentBrowseControls() {
    const holder = root?.querySelector("[data-component-browse-tools]");
    if (!holder) return;
    const kind = currentComponentKind();
    const enabled = ["outfit", "scene"].includes(kind);
    holder.style.display = enabled ? "flex" : "none";
    if (!enabled) return;
    const rows = derivedEntries(kind);
    const pageSize = componentPageSize(kind);
    const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
    componentPage[kind] = Math.max(0, Math.min(Number(componentPage[kind] || 0), pageCount - 1));
    const start = rows.length ? componentPage[kind] * pageSize + 1 : 0;
    const end = Math.min(rows.length, (componentPage[kind] + 1) * pageSize);
    const input = holder.querySelector("[data-component-search]");
    if (input && input.value !== String(componentSearch[kind] || "")) input.value = String(componentSearch[kind] || "");
    const rating = holder.querySelector("[data-component-rating-filter]"); if (rating) rating.value = String(componentRatingFilter[kind] || "");
    const thumbs = holder.querySelector("[data-component-thumbnail-filter]"); if (thumbs) thumbs.value = String(componentThumbnailFilter[kind] || "");
    const sort = holder.querySelector("[data-component-sort]"); if (sort) sort.value = String(componentSort[kind] || "recent");
    const range = holder.querySelector("[data-component-range]"); if (range) range.textContent = rows.length ? `${start.toLocaleString()}–${end.toLocaleString()} of ${rows.length.toLocaleString()}` : "0 results";
    const prev = holder.querySelector("[data-component-prev]"); if (prev) prev.disabled = componentPage[kind] <= 0;
    const next = holder.querySelector("[data-component-next]"); if (next) next.disabled = componentPage[kind] >= pageCount - 1;
    for (const button of [prev, next]) if (button) button.style.opacity = button.disabled ? ".38" : "1";
}

function renderPromptBrowseControls() {
    const holder = root?.querySelector("[data-prompt-browse-tools]");
    if (!holder) return;
    const enabled = false;
    holder.style.display = enabled ? "flex" : "none";
    if (!enabled) return;
    const input = holder.querySelector("[data-prompt-search]");
    if (input && input.value !== String(promptSearch || "")) input.value = String(promptSearch || "");
    const source = holder.querySelector("[data-prompt-source-filter]");
    if (source) source.value = String(promptSourceFilter || "");
    for (const axis of PROMPT_FACET_AXES) {
        const select = holder.querySelector(`[data-prompt-facet="${axis}"]`);
        if (select) select.value = String(promptFacetFilters[axis] || "");
    }
    const blueprint = holder.querySelector("[data-prompt-blueprint-filter]");
    if (blueprint) {
        blueprint.textContent = promptBlueprintOnly ? "✓ BLUEPRINTS" : "BLUEPRINTS";
        blueprint.style.background = promptBlueprintOnly ? "rgba(255,74,184,.22)" : "#25232d";
        blueprint.style.borderWidth = promptBlueprintOnly ? "2px" : "1px";
    }
    const signature = holder.querySelector("[data-prompt-signature-filter]");
    if (signature) {
        const signatureEntries = Object.entries(promptBlueprintSignatures || {}).filter(([, count]) => Number(count || 0) > 0);
        const signatureKey = JSON.stringify(signatureEntries);
        if (signature.dataset.signatureKey !== signatureKey) {
            signature.dataset.signatureKey = signatureKey;
            signature.replaceChildren();
            for (const [value, label] of [["", "Any Blueprint formula"], ...signatureEntries.map(([value, count]) => [value, `${value.replaceAll("+", " + ")} · ${Number(count).toLocaleString()}`])]) {
                const option = document.createElement("option"); option.value = value; option.textContent = label; signature.append(option);
            }
        }
        signature.value = String(promptSignatureFilter || "");
    }
    const sort = holder.querySelector("[data-prompt-sort]"); if (sort) sort.value = String(promptSort || "newest");
    const pageCount = Math.max(1, Math.ceil(promptTotal / PROMPT_PAGE_SIZE));
    promptPage = Math.max(0, Math.min(Number(promptPage || 0), pageCount - 1));
    const start = promptTotal ? promptPage * PROMPT_PAGE_SIZE + 1 : 0;
    const end = Math.min(promptTotal, promptPage * PROMPT_PAGE_SIZE + promptAssets.length);
    const range = holder.querySelector("[data-prompt-range]"); if (range) range.textContent = promptLoading ? "Loading…" : promptTotal ? `${start.toLocaleString()}–${end.toLocaleString()} of ${promptTotal.toLocaleString()}` : "0 results";
    const prev = holder.querySelector("[data-prompt-prev]"); if (prev) prev.disabled = promptPage <= 0;
    const next = holder.querySelector("[data-prompt-next]"); if (next) next.disabled = promptPage >= pageCount - 1;
    for (const button of [prev, next]) if (button) button.style.opacity = button.disabled ? ".38" : "1";
}

async function comfyConfirm(message, title = "Creative Library") {
    return await new Promise(resolve => {
        const { overlay, card, close } = collectionModal(title, "560px");
        card.style.borderColor = "#ff9b5f88";
        const body = document.createElement("div");
        Object.assign(body.style, { padding: "16px", color: "#e7e1ea", font: "11px/1.55 Segoe UI,Arial", whiteSpace: "pre-wrap" });
        body.textContent = String(message || "");
        const footer = document.createElement("div");
        Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
        const cancel = action("Cancel", "#8f8997");
        const accept = action("CONFIRM", "#ff9b5f");
        let settled = false;
        const finish = value => {
            if (settled) return;
            settled = true;
            close();
            resolve(Boolean(value));
        };
        cancel.onclick = () => finish(false);
        accept.onclick = () => finish(true);
        overlay.addEventListener("pointerdown", event => {
            if (event.target !== overlay) return;
            event.stopImmediatePropagation();
            finish(false);
        }, { capture: true });
        card.addEventListener("keydown", event => {
            if (event.key === "Escape") { event.preventDefault(); finish(false); }
            else if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); finish(true); }
        });
        footer.append(cancel, accept);
        card.append(body, footer);
        requestAnimationFrame(() => accept.focus?.({ preventScroll: true }));
    });
}

function collectionModal(title, width = "560px") {
    const parentInspector = document.activeElement?.closest?.("[data-library-inspector]");
    const overlay = document.createElement("div");
    Object.assign(overlay.style, { position: "fixed", inset: "0", zIndex: "100052", background: "rgba(0,0,0,.68)", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" });
    const card = document.createElement("section");
    Object.assign(card.style, { width, maxWidth: "94vw", maxHeight: "86vh", display: "flex", flexDirection: "column", background: "linear-gradient(145deg,#17131f,#0d0b12)", border: "1px solid #b89aff99", borderRadius: "13px", boxShadow: "0 24px 70px #000", color: "#f5f1f7", overflow: "hidden" });
    const head = document.createElement("strong");
    head.textContent = title;
    Object.assign(head.style, { padding: "13px 15px", color: "#d8c7ff", letterSpacing: ".07em", font: "700 12px Segoe UI,Arial", borderBottom: "1px solid #b89aff44" });
    const closeModal = () => {
        const active = document.activeElement;
        if (active && overlay.contains(active) && typeof active.blur === "function") active.blur();
        overlay.remove();
        if (parentInspector?.isConnected) {
            queueMicrotask(() => parentInspector.focus({ preventScroll: true }));
            requestAnimationFrame(() => { if (parentInspector.isConnected) parentInspector.focus({ preventScroll: true }); });
            return;
        }
        queueMicrotask(() => recoverTextInputFocus());
        requestAnimationFrame(() => recoverTextInputFocus());
    };
    card.append(head); overlay.append(card); document.body.append(overlay);
    installStudioInteractions(overlay);
    overlay.addEventListener("pointerdown", event => {
        if (event.target === overlay) closeModal();
    }, { passive: true });
    return { overlay, card, close: closeModal };
}

async function creativeStructureOrder(scope) {
    const data = await request(`/structure-order?scope=${encodeURIComponent(scope)}`);
    return data?.order && typeof data.order === "object" ? data.order : {};
}

async function saveCreativeStructureOrder(scope, order) {
    const data = await request("/structure-order", { method: "PUT", body: JSON.stringify({ scope, order }) });
    libraryRevisions = data?.revisions && typeof data.revisions === "object" ? data.revisions : libraryRevisions;
    return data?.order && typeof data.order === "object" ? data.order : order;
}

function reorderedValues(values, index, direction) {
    const output = [...values];
    const target = index + direction;
    if (index < 0 || index >= output.length || target < 0 || target >= output.length) return output;
    [output[index], output[target]] = [output[target], output[index]];
    return output;
}

function tinyOrderButton(label, title, disabled, onclick, color = "#8f8997") {
    const button = action(label, color); button.title = title; button.disabled = Boolean(disabled);
    Object.assign(button.style, { padding: "4px 6px", minWidth: "27px", fontSize: "9px", opacity: disabled ? ".32" : "1" });
    button.onclick = onclick; return button;
}

const CREATIVE_LIBRARY_PACK_META = [
    ["templates", "TEMPLATES", "#ff4ab8"],
    ["prompts", "PROMPTS", "#35d7ff"],
    ["recipes", "SAVED RECIPES", "#f6e65a"],
    ["outfits", "OUTFIT LOOKS", "#f6e65a"],
    ["scenes", "SCENES", "#63e6a4"],
    ["wardrobe", "WARDROBE", "#ff9b5f"],
];

function libraryPackToggle(label, checked = true, color = "#b89aff") {
    const row = document.createElement("label"); Object.assign(row.style, { display: "flex", alignItems: "center", gap: "8px", minWidth: "0", cursor: "pointer", padding: "6px 7px", borderRadius: "7px", border: `1px solid ${color}33`, background: "rgba(255,255,255,.018)" });
    const input = document.createElement("input"); input.type = "checkbox"; input.checked = Boolean(checked); input.style.accentColor = color;
    const text = document.createElement("span"); text.textContent = label; Object.assign(text.style, { minWidth: "0", color: "#e9e3ed", font: "800 9px Segoe UI,Arial", letterSpacing: ".035em" });
    row.append(input, text); return { row, input, text };
}

function libraryPackScopeBox(title, color = "#b89aff") {
    const details = document.createElement("details"); Object.assign(details.style, { border: `1px solid ${color}33`, borderRadius: "9px", background: "rgba(255,255,255,.012)", overflow: "hidden" });
    const summary = document.createElement("summary"); summary.textContent = title; Object.assign(summary.style, { padding: "8px 10px", cursor: "pointer", color, font: "900 9px Segoe UI,Arial", letterSpacing: ".055em", userSelect: "none" });
    const body = document.createElement("div"); Object.assign(body.style, { display: "grid", gap: "5px", padding: "2px 9px 9px" }); details.append(summary, body); return { details, body };
}

function createCreativeLibraryScopeEditor(contents, mode = "starter") {
    const counts = contents?.counts || {};
    const root = document.createElement("div"); Object.assign(root.style, { display: "grid", gap: "10px" });
    const libraries = document.createElement("div"); Object.assign(libraries.style, { display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: "6px" });
    const libraryChecks = {};
    const libraryControllers = {};
    for (const [key, label, color] of CREATIVE_LIBRARY_PACK_META) {
        if (key === "boards" && mode !== "backup") continue;
        const count = Number(counts[key] || 0);
        const toggle = libraryPackToggle(`${label} · ${count.toLocaleString()}`, count > 0, color);
        if (!count) { toggle.input.disabled = true; toggle.row.style.opacity = ".38"; }
        libraryChecks[key] = toggle.input; libraries.append(toggle.row);
    }
    root.append(libraries);

    const tip = document.createElement("div"); tip.textContent = "Everything starts selected. Uncheck anything inside a library to make that library selective; check the library box at the top again to select everything in it."; Object.assign(tip.style, { color: "#8f8997", font: "10px/1.45 Segoe UI,Arial" }); root.append(tip);

    const promptTrees = {};
    const componentTrees = {};
    const recipeTree = { leaves: [] };
    const wardrobeTree = { categories: [] };

    const leafState = inputs => {
        const live = (inputs || []).filter(input => input && !input.disabled);
        const checked = live.filter(input => input.checked).length;
        return { total: live.length, checked, any: checked > 0, all: live.length > 0 && checked === live.length };
    };
    const syncMain = key => {
        const controller = libraryControllers[key]; const main = libraryChecks[key];
        if (!main || main.disabled || !controller) return;
        const state = leafState(controller.leaves());
        main.checked = state.all;
        main.indeterminate = state.any && !state.all;
    };
    const wireMain = (key, controller) => {
        libraryControllers[key] = controller;
        const main = libraryChecks[key];
        if (!main || main.disabled) return;
        main.onchange = () => {
            controller.setAll(Boolean(main.checked));
            controller.sync();
        };
        controller.sync();
    };

    const addNestedHomeScopes = (kind, title, color) => {
        const homes = contents?.prompt_homes?.[kind] || {};
        const collectionsInPack = contents?.showcase_collections?.[kind]
            || (kind === "prompt" ? (contents?.prompt_collections || []) : []);
        if (!Object.keys(homes).length && !collectionsInPack.length) return;
        const libraryKey = kind === "template" ? "templates" : "prompts";
        const box = libraryPackScopeBox(title, color);
        const tree = { parents: [], collections: [] }; promptTrees[kind] = tree;
        const homeLabel = document.createElement("div"); homeLabel.textContent = "HOME / SUBCATEGORY / LOG"; Object.assign(homeLabel.style, { color: "#756d7a", font: "900 7px Segoe UI,Arial", letterSpacing: ".08em", marginTop: "2px" }); box.body.append(homeLabel);
        for (const parent of Object.keys(homes)) {
            const total = Object.values(homes[parent] || {}).reduce((sum, value) => sum + Number(value || 0), 0);
            const parentToggle = libraryPackToggle(`${parent} · ${total.toLocaleString()}`, true, color); parentToggle.row.style.marginTop = "2px";
            const parentNode = { name: parent, input: parentToggle.input, subcategories: [] }; tree.parents.push(parentNode); box.body.append(parentToggle.row);
            for (const [sub, count] of Object.entries(homes[parent] || {})) {
                const child = libraryPackToggle(`↳ ${sub} · ${Number(count || 0).toLocaleString()}`, true, color); child.row.style.marginLeft = "17px"; child.row.style.background = "rgba(255,255,255,.008)";
                const subNode = { name: sub, input: child.input, logs: [] }; parentNode.subcategories.push(subNode); box.body.append(child.row);
                const logRows = contents?.prompt_logs?.[kind]?.[parent]?.[sub] || {};
                for (const [sourcePath, info] of Object.entries(logRows)) {
                    const logLabel = String(info?.label || sourcePath.split("/").pop()?.replace(/\.txt$/i, "") || "Log");
                    const logToggle = libraryPackToggle(`↳↳ ${logLabel} · ${Number(info?.count || 0).toLocaleString()}`, true, color); logToggle.row.style.marginLeft = "34px"; logToggle.row.style.background = "rgba(255,255,255,.005)";
                    const logNode = { sourcePath, label: logLabel, input: logToggle.input }; subNode.logs.push(logNode); box.body.append(logToggle.row);
                    logToggle.input.onchange = () => tree.sync();
                }
                child.input.onchange = () => { for (const log of subNode.logs) log.input.checked = child.input.checked; tree.sync(); };
            }
            parentToggle.input.onchange = () => {
                for (const subNode of parentNode.subcategories) { subNode.input.checked = parentToggle.input.checked; for (const log of subNode.logs) log.input.checked = parentToggle.input.checked; }
                tree.sync();
            };
        }
        if (collectionsInPack.length) {
            const collectionLabel = document.createElement("div"); collectionLabel.textContent = "COLLECTIONS"; Object.assign(collectionLabel.style, { color: "#756d7a", font: "900 7px Segoe UI,Arial", letterSpacing: ".08em", marginTop: "7px" }); box.body.append(collectionLabel);
            for (const name of collectionsInPack) {
                const toggle = libraryPackToggle(name, true, color); const node = { name, input: toggle.input }; tree.collections.push(node); toggle.input.onchange = () => tree.sync(); box.body.append(toggle.row);
            }
        }
        tree.leaves = () => [
            ...tree.parents.flatMap(parentNode => parentNode.subcategories.flatMap(subNode => subNode.logs.length ? subNode.logs.map(log => log.input) : [subNode.input])),
            ...tree.collections.map(node => node.input),
        ];
        tree.setAll = checked => { for (const input of tree.leaves()) input.checked = checked; };
        tree.sync = () => {
            for (const parentNode of tree.parents) {
                for (const subNode of parentNode.subcategories) {
                    if (subNode.logs.length) {
                        const state = leafState(subNode.logs.map(log => log.input));
                        subNode.input.checked = state.all; subNode.input.indeterminate = state.any && !state.all;
                    } else subNode.input.indeterminate = false;
                }
                const state = leafState(parentNode.subcategories.map(subNode => subNode.input));
                const partial = parentNode.subcategories.some(subNode => subNode.input.indeterminate);
                parentNode.input.checked = state.all && !partial; parentNode.input.indeterminate = partial || (state.any && !state.all);
            }
            syncMain(libraryKey);
        };
        root.append(box.details);
        wireMain(libraryKey, tree);
    };
    addNestedHomeScopes("template", "TEMPLATES", "#ff4ab8");
    addNestedHomeScopes("prompt", "PROMPTS", "#35d7ff");

    if ((contents?.recipe_collections || []).length) {
        const box = libraryPackScopeBox("SAVED RECIPES", "#f6e65a");
        for (const name of contents.recipe_collections) {
            const toggle = libraryPackToggle(name, true, "#f6e65a"); recipeTree.leaves.push({ name, input: toggle.input }); toggle.input.onchange = () => recipeTree.sync(); box.body.append(toggle.row);
        }
        recipeTree.setAll = checked => { for (const leaf of recipeTree.leaves) leaf.input.checked = checked; };
        recipeTree.sync = () => syncMain("recipes");
        root.append(box.details); wireMain("recipes", { leaves: () => recipeTree.leaves.map(leaf => leaf.input), setAll: recipeTree.setAll, sync: recipeTree.sync });
    }

    const addComponentScopes = (kind, title, color) => {
        const taxonomy = contents?.component_taxonomy?.[kind] || {};
        const shareable = contents?.shareable_collections?.[kind] || {};
        if (!Object.keys(taxonomy).length && !Object.keys(shareable).length) return;
        const libraryKey = kind === "outfit" ? "outfits" : "scenes";
        const box = libraryPackScopeBox(title, color); const tree = { categories: [], packCollections: [] }; componentTrees[kind] = tree;
        if (Object.keys(taxonomy).length) {
            const taxonomyLabel = document.createElement("div"); taxonomyLabel.textContent = "COLLECTIONS"; Object.assign(taxonomyLabel.style, { color: "#756d7a", font: "900 7px Segoe UI,Arial", letterSpacing: ".08em", marginTop: "2px" }); box.body.append(taxonomyLabel);
            for (const category of Object.keys(taxonomy)) {
                const submap = taxonomy[category] || {};
                const total = Object.values(submap).reduce((sum, value) => sum + Number(value || 0), 0);
                const categoryToggle = libraryPackToggle(`${category} · ${total.toLocaleString()}`, true, color);
                const categoryNode = { name: category, input: categoryToggle.input, children: [] }; tree.categories.push(categoryNode); box.body.append(categoryToggle.row);
                for (const [sub, count] of Object.entries(submap)) {
                    if (!sub) continue;
                    const child = libraryPackToggle(`↳ ${sub} · ${Number(count || 0).toLocaleString()}`, true, color); child.row.style.marginLeft = "17px";
                    const childNode = { name: sub, input: child.input }; categoryNode.children.push(childNode); child.input.onchange = () => tree.sync(); box.body.append(child.row);
                }
                categoryToggle.input.onchange = () => { for (const child of categoryNode.children) child.input.checked = categoryToggle.input.checked; tree.sync(); };
            }
        }
        if (Object.keys(shareable).length) {
            const collectionLabel = document.createElement("div"); collectionLabel.textContent = "COLLECTIONS"; Object.assign(collectionLabel.style, { color: "#756d7a", font: "900 7px Segoe UI,Arial", letterSpacing: ".08em", marginTop: "7px" }); box.body.append(collectionLabel);
            for (const [name, count] of Object.entries(shareable)) {
                const toggle = libraryPackToggle(`${name} · ${Number(count || 0).toLocaleString()}`, true, color);
                const node = { name, input: toggle.input }; tree.packCollections.push(node); toggle.input.onchange = () => tree.sync(); box.body.append(toggle.row);
            }
        }
        tree.leaves = () => [
            ...tree.categories.flatMap(category => category.children.length ? category.children.map(child => child.input) : [category.input]),
            ...tree.packCollections.map(node => node.input),
        ];
        tree.setAll = checked => { for (const input of tree.leaves()) input.checked = checked; };
        tree.sync = () => {
            for (const category of tree.categories) if (category.children.length) {
                const state = leafState(category.children.map(child => child.input)); category.input.checked = state.all; category.input.indeterminate = state.any && !state.all;
            }
            syncMain(libraryKey);
        };
        root.append(box.details); wireMain(libraryKey, tree);
    };
    addComponentScopes("outfit", "OUTFIT LOOKS", "#f6e65a");
    addComponentScopes("scene", "SCENES", "#63e6a4");

    const wardrobeShareable = contents?.shareable_collections?.wardrobe || {};
    if (Object.keys(contents?.wardrobe_categories || {}).length || Object.keys(wardrobeShareable).length) {
        const box = libraryPackScopeBox("WARDROBE", "#ff9b5f");
        wardrobeTree.packCollections = [];
        if (Object.keys(contents?.wardrobe_categories || {}).length) {
            const taxonomyLabel = document.createElement("div"); taxonomyLabel.textContent = "CATEGORY / TYPE"; Object.assign(taxonomyLabel.style, { color: "#756d7a", font: "900 7px Segoe UI,Arial", letterSpacing: ".08em", marginTop: "2px" }); box.body.append(taxonomyLabel);
            for (const category of Object.keys(contents.wardrobe_categories)) {
                const submap = contents.wardrobe_categories[category] || {};
                const total = Object.values(submap).reduce((sum, value) => sum + Number(value || 0), 0);
                const categoryToggle = libraryPackToggle(`${category} · ${total.toLocaleString()}`, true, "#ff9b5f");
                const categoryNode = { name: category, input: categoryToggle.input, children: [] }; wardrobeTree.categories.push(categoryNode); box.body.append(categoryToggle.row);
                for (const [subtype, count] of Object.entries(submap)) {
                    if (!subtype) continue;
                    const child = libraryPackToggle(`↳ ${subtype} · ${Number(count || 0).toLocaleString()}`, true, "#ff9b5f"); child.row.style.marginLeft = "17px";
                    const childNode = { name: subtype, input: child.input }; categoryNode.children.push(childNode); child.input.onchange = () => wardrobeTree.sync(); box.body.append(child.row);
                }
                categoryToggle.input.onchange = () => { for (const child of categoryNode.children) child.input.checked = categoryToggle.input.checked; wardrobeTree.sync(); };
            }
        }
        if (Object.keys(wardrobeShareable).length) {
            const collectionLabel = document.createElement("div"); collectionLabel.textContent = "COLLECTIONS"; Object.assign(collectionLabel.style, { color: "#756d7a", font: "900 7px Segoe UI,Arial", letterSpacing: ".08em", marginTop: "7px" }); box.body.append(collectionLabel);
            for (const [name, count] of Object.entries(wardrobeShareable)) {
                const toggle = libraryPackToggle(`${name} · ${Number(count || 0).toLocaleString()}`, true, "#ff9b5f");
                const node = { name, input: toggle.input }; wardrobeTree.packCollections.push(node); toggle.input.onchange = () => wardrobeTree.sync(); box.body.append(toggle.row);
            }
        }
        wardrobeTree.leaves = () => [
            ...wardrobeTree.categories.flatMap(category => category.children.length ? category.children.map(child => child.input) : [category.input]),
            ...wardrobeTree.packCollections.map(node => node.input),
        ];
        wardrobeTree.setAll = checked => { for (const input of wardrobeTree.leaves()) input.checked = checked; };
        wardrobeTree.sync = () => {
            for (const category of wardrobeTree.categories) if (category.children.length) {
                const state = leafState(category.children.map(child => child.input)); category.input.checked = state.all; category.input.indeterminate = state.any && !state.all;
            }
            syncMain("wardrobe");
        };
        root.append(box.details); wireMain("wardrobe", wardrobeTree);
    }

    const options = document.createElement("div"); Object.assign(options.style, { display: "grid", gap: "6px" });
    const thumbs = libraryPackToggle("INCLUDE THUMBNAILS", true, "#67e8f9"); options.append(thumbs.row); root.append(options);
    const automatic = document.createElement("div"); automatic.textContent = "Home and Collection organization is included automatically. If a selected Recipe or Outfit Look needs linked library records to work correctly, those required records are bundled automatically too."; Object.assign(automatic.style, { padding: "8px 10px", borderRadius: "8px", border: "1px solid #63e6a433", color: "#9f98a7", background: "rgba(99,230,164,.025)", font: "9px/1.45 Segoe UI,Arial" }); root.append(automatic);

    const librarySelected = key => Boolean(libraryChecks[key]?.checked || libraryChecks[key]?.indeterminate);
    const promptSelection = kind => {
        const tree = promptTrees[kind]; const libraryKey = kind === "template" ? "templates" : "prompts";
        if (!tree || !librarySelected(libraryKey) || libraryChecks[libraryKey]?.checked) return {};
        const parents = [], subcategories = [], source_paths = [], collections = [];
        const included_source_paths = tree.parents.flatMap(parentNode => parentNode.subcategories.flatMap(subNode => subNode.logs.filter(log => log.input.checked).map(log => log.sourcePath)));
        const included_collections = tree.collections.filter(collection => collection.input.checked).map(collection => collection.name);
        for (const parentNode of tree.parents) {
            if (parentNode.input.checked && !parentNode.input.indeterminate) { parents.push(parentNode.name); continue; }
            for (const subNode of parentNode.subcategories) {
                if (subNode.input.checked && !subNode.input.indeterminate) { subcategories.push({ parent: parentNode.name, name: subNode.name }); continue; }
                for (const log of subNode.logs) if (log.input.checked) source_paths.push(log.sourcePath);
            }
        }
        collections.push(...included_collections);
        return { parents, subcategories, source_paths, collections, included_source_paths, included_collections, filter_sources: true, filter_collections: true };
    };
    const componentSelection = kind => {
        const tree = componentTrees[kind]; const libraryKey = kind === "outfit" ? "outfits" : "scenes";
        if (!tree || !librarySelected(libraryKey) || libraryChecks[libraryKey]?.checked) return {};
        const collections = [];
        for (const category of tree.categories) {
            if (category.input.checked && !category.input.indeterminate) collections.push({ parent_name: "", name: category.name });
            else for (const child of category.children) if (child.input.checked) collections.push({ parent_name: category.name, name: child.name });
        }
        const pack_collections = tree.packCollections.filter(node => node.input.checked).map(node => node.name);
        return { collections, pack_collections, included_collections: collections, included_pack_collections: pack_collections, filter_collections: true, filter_pack_collections: true };
    };
    const wardrobeSelection = () => {
        if (!librarySelected("wardrobe") || libraryChecks.wardrobe?.checked) return {};
        const categories = [], category_subtypes = [];
        for (const category of wardrobeTree.categories) {
            if (category.input.checked && !category.input.indeterminate) categories.push(category.name);
            else for (const child of category.children) if (child.input.checked) category_subtypes.push({ parent: category.name, name: child.name });
        }
        const pack_collections = (wardrobeTree.packCollections || []).filter(node => node.input.checked).map(node => node.name);
        return { categories, category_subtypes, pack_collections, included_pack_collections: pack_collections, filter_pack_collections: true };
    };
    const getSelection = () => ({
        libraries: Object.entries(libraryChecks).filter(([key]) => librarySelected(key)).map(([key]) => key),
        prompt_scopes: { template: promptSelection("template"), prompt: promptSelection("prompt") },
        recipe_scope: !librarySelected("recipes") || libraryChecks.recipes?.checked ? {} : (() => { const collections = recipeTree.leaves.filter(leaf => leaf.input.checked).map(leaf => leaf.name); return { collections, included_collections: collections, filter_collections: true }; })(),
        component_scopes: { outfit: componentSelection("outfit"), scene: componentSelection("scene") },
        wardrobe_scope: wardrobeSelection(),
        include_thumbnails: thumbs.input.checked,
        include_taxonomy: true,
        include_dependencies: true,
    });
    const applyPreset = preset => {
        if (preset === "custom" || preset === "current") return;
        const enabled = preset === "wardrobe" ? new Set(["outfits", "wardrobe"]) : new Set(Object.keys(libraryChecks));
        for (const [key, input] of Object.entries(libraryChecks)) {
            if (input.disabled) continue;
            const checked = enabled.has(key); input.checked = checked; input.indeterminate = false;
            const controller = libraryControllers[key];
            if (controller) { controller.setAll(checked); controller.sync(); }
        }
    };
    return { element: root, getSelection, applyPreset };
}
function currentCreativeLibraryScope(mode = "starter") {
    const selection = {
        libraries: [], prompt_scopes: { template: {}, prompt: {} }, recipe_scope: {}, component_scopes: { outfit: {}, scene: {} }, wardrobe_scope: {},
        include_thumbnails: true, include_taxonomy: true, include_dependencies: true,
    };
    if (activeView === "recipes") {
        selection.libraries = ["templates"];
        if (promptLogPath) selection.prompt_scopes.template.source_paths = [promptLogPath];
        else if (promptSubcategory) selection.prompt_scopes.template.subcategories = [{ parent: promptParent || "", name: promptSubcategory }];
        else if (promptParent) selection.prompt_scopes.template.parents = [promptParent];
        const group = promptShowcaseFolders("template").find(item => String(item.collection_id || "") === String(activeCollection || ""));
        if (group?.name) selection.prompt_scopes.template.collections = [group.name];
    } else if (activeView === "prompts") {
        selection.libraries = ["prompts"];
        if (promptLogPath) selection.prompt_scopes.prompt.source_paths = [promptLogPath];
        else if (promptSubcategory) selection.prompt_scopes.prompt.subcategories = [{ parent: promptParent || "", name: promptSubcategory }];
        else if (promptParent) selection.prompt_scopes.prompt.parents = [promptParent];
        const group = promptShowcaseFolders("prompt").find(item => String(item.collection_id || "") === String(activeCollection || ""));
        if (group?.name) selection.prompt_scopes.prompt.collections = [group.name];
    } else if (activeView === "outfits") {
        if (outfitMode === "pieces") {
            selection.libraries = ["wardrobe"];
            const pack = (libraryCollections.wardrobe || []).find(item => String(item.collection_id || "") === String(activeLibraryCollection.wardrobe || ""));
            if (pack?.name) { selection.wardrobe_scope.pack_collections = [pack.name]; selection.wardrobe_scope.included_pack_collections = [pack.name]; selection.wardrobe_scope.filter_pack_collections = true; }
            else {
                if (wardrobeCategory) selection.wardrobe_scope.categories = [wardrobeCategory];
                if (wardrobeSubtype) selection.wardrobe_scope.subtypes = [wardrobeSubtype];
            }
        } else {
            selection.libraries = ["outfits"];
            const pack = (libraryCollections.outfit || []).find(item => String(item.collection_id || "") === String(activeLibraryCollection.outfit || ""));
            if (pack?.name) { selection.component_scopes.outfit.pack_collections = [pack.name]; selection.component_scopes.outfit.included_pack_collections = [pack.name]; selection.component_scopes.outfit.filter_pack_collections = true; }
            else {
                const group = (componentCollections.outfit || []).find(item => String(item.collection_id || "") === String(activeCollection || ""));
                if (group?.name) selection.component_scopes.outfit.collections = [{ parent_name: "", name: group.name }];
            }
        }
    } else if (activeView === "scenes") {
        selection.libraries = ["scenes"];
        const pack = (libraryCollections.scene || []).find(item => String(item.collection_id || "") === String(activeLibraryCollection.scene || ""));
        if (pack?.name) { selection.component_scopes.scene.pack_collections = [pack.name]; selection.component_scopes.scene.included_pack_collections = [pack.name]; selection.component_scopes.scene.filter_pack_collections = true; }
        else {
            const group = (componentCollections.scene || []).find(item => String(item.collection_id || "") === String(activeCollection || ""));
            if (group?.name) {
                const parent = (componentCollections.scene || []).find(item => String(item.collection_id || "") === String(group.parent_id || ""));
                selection.component_scopes.scene.collections = [{ parent_name: parent?.name || "", name: group.name }];
            }
        }
    }
    return selection;
}

async function showCreativeLibraryExport() {
    const { overlay, card } = collectionModal("BUILD LIBRARY PACK", "900px"); card.style.borderColor = "#6ee7a299";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto", display: "grid", gap: "11px" });
    const help = document.createElement("div"); help.textContent = "Every portable Creative Library file is a .soslibrary pack. Choose a useful preset, then refine the included Homes, Collections, logs, or sections when needed."; Object.assign(help.style, { color: "#b9b2c0", fontSize: "11px", lineHeight: "1.55" }); body.append(help);
    const fields = document.createElement("div"); Object.assign(fields.style, { display: "grid", gridTemplateColumns: "170px 2fr 1fr 100px", gap: "8px" });
    const preset = document.createElement("select"); for (const [value, label] of [["starter", "STARTER / SHARE PACK"], ["wardrobe", "WARDROBE & LOOKS"], ["current", "CURRENT SCOPE"], ["backup", "FULL BACKUP"], ["custom", "CUSTOM"]]) { const option = document.createElement("option"); option.value = value; option.textContent = label; preset.append(option); }
    const name = document.createElement("input"); name.placeholder = "Pack name"; name.value = "My Sick Ollie Library";
    const creator = document.createElement("input"); creator.placeholder = "Creator";
    const version = document.createElement("input"); version.placeholder = "Version"; version.value = "1.0";
    for (const input of [preset, name, creator, version]) Object.assign(input.style, { minWidth: "0", padding: "9px 10px", borderRadius: "8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452" });
    fields.append(preset, name, creator, version); body.append(fields);
    const description = document.createElement("textarea"); description.rows = 2; description.placeholder = "Optional pack / backup description…"; Object.assign(description.style, { width: "100%", boxSizing: "border-box", padding: "9px 10px", resize: "vertical", borderRadius: "8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452" }); body.append(description);
    const scopeMode = document.createElement("div"); Object.assign(scopeMode.style, { display: "flex", gap: "7px", alignItems: "center", flexWrap: "wrap" });
    const scopeHint = document.createElement("span"); Object.assign(scopeHint.style, { color: "#8f8997", font: "9px Segoe UI,Arial" }); scopeMode.append(scopeHint); body.append(scopeMode);
    const scopeHost = document.createElement("div"); body.append(scopeHost);
    let editor = null; let useCurrent = false;
    const packMode = () => preset.value === "backup" ? "backup" : "starter";
    const refreshScopeMode = () => {
        scopeHost.style.opacity = useCurrent ? ".34" : "1"; scopeHost.style.pointerEvents = useCurrent ? "none" : "auto";
        scopeHint.textContent = useCurrent ? "Current Scope uses the active tab, Home, Collection, and filters." : "Refine the preset below; required linked dependencies remain automatic.";
    };
    const loadOptions = async () => {
        scopeHost.textContent = "Reading library structure…"; Object.assign(scopeHost.style, { color: "#8f8997", font: "10px Segoe UI,Arial" });
        const response = await request(`/library-pack/options?mode=${encodeURIComponent(packMode())}`);
        editor = createCreativeLibraryScopeEditor(response.contents || {}, packMode()); scopeHost.replaceChildren(editor.element);
        editor.applyPreset?.(preset.value); refreshScopeMode();
    };
    preset.onchange = () => { useCurrent = preset.value === "current"; void loadOptions(); };
    await loadOptions();
    const policy = document.createElement("div"); policy.textContent = "Creative Library keeps packs self-contained automatically: Homes and Collections travel with selected records, and only linked records actually needed by selected Recipes or Outfit Looks are added behind the scenes."; Object.assign(policy.style, { padding: "10px 11px", borderRadius: "9px", border: "1px solid #6ee7a244", color: "#a9a2b1", background: "rgba(255,255,255,.018)", font: "10px/1.5 Segoe UI,Arial" }); body.append(policy);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const exportButton = action("EXPORT .SOSLIBRARY", "#6ee7a2"); exportButton.onclick = async () => {
        if (!editor) return;
        const editorSelection = editor.getSelection();
        const selection = useCurrent ? currentCreativeLibraryScope(packMode()) : editorSelection;
        if (useCurrent) selection.include_thumbnails = editorSelection.include_thumbnails;
        selection.include_taxonomy = true;
        selection.include_dependencies = true;
        if (!selection.libraries.length) { alert("Choose at least one Library to export."); return; }
        exportButton.disabled = true; exportButton.textContent = "PACKING LIBRARY…"; catalogStatus("Packing selected Creative Library records…", "#6ee7a2");
        try {
            const response = await fetch(`${API}/library-pack/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mode: packMode(), preset: preset.value, name: name.value.trim(), creator: creator.value.trim(), version: version.value.trim() || "1.0", description: description.value.trim(), selection }) });
            if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || `HTTP ${response.status}`);
            const blob = await response.blob(); const disposition = String(response.headers.get("Content-Disposition") || ""); const match = disposition.match(/filename="?([^";]+)"?/i); const filename = match?.[1] || "creative-library-pack.soslibrary";
            const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1800);
            catalogStatus(`Exported ${filename} · ${(blob.size / (1024 * 1024)).toFixed(1)} MB`, "#6ee7a2"); overlay.remove();
        } catch (error) { catalogStatus("Creative Library export failed.", "#ff78bd"); alert(error.message || "Could not export the Creative Library Pack."); }
        finally { exportButton.disabled = false; exportButton.textContent = "EXPORT .SOSLIBRARY"; }
    };
    footer.append(cancel, exportButton); card.append(body, footer);
}

function showCreativeLibraryImport(file, inspection) {
    const manifest = inspection?.manifest || {}; const contents = inspection?.contents || {};
    const mode = String(manifest.export_mode || "starter");
    const { overlay, card } = collectionModal("IMPORT CREATIVE LIBRARY PACK", "900px"); card.style.borderColor = "#35d7ff99";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto", display: "grid", gap: "11px" });
    const title = document.createElement("div"); const titleName = document.createElement("strong"); titleName.textContent = String(manifest.name || file.name); titleName.style.color = "#67e8f9"; title.append(titleName, document.createTextNode(` · v${String(manifest.version || "?")} · ${mode === "backup" ? "full backup" : "library pack"}`)); Object.assign(title.style, { font: "11px/1.45 Segoe UI,Arial" }); body.append(title);
    if (manifest.description) { const description = document.createElement("div"); description.textContent = manifest.description; Object.assign(description.style, { color: "#aaa2b4", font: "10px/1.45 Segoe UI,Arial" }); body.append(description); }
    const help = document.createElement("div"); help.textContent = "Choose exactly what to install. Unchecked libraries, categories, subcategories, and collections are ignored. They are never interpreted as deletions from content already installed locally."; Object.assign(help.style, { padding: "9px 10px", borderRadius: "8px", border: "1px solid #35d7ff44", background: "rgba(53,215,255,.04)", color: "#b9b2c0", font: "10px/1.5 Segoe UI,Arial" }); body.append(help);
    const editor = createCreativeLibraryScopeEditor(contents, mode); body.append(editor.element);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const install = action("IMPORT SELECTED", "#35d7ff"); install.onclick = async () => {
        const selection = editor.getSelection(); if (!selection.libraries.length) { alert("Choose at least one Library to import."); return; }
        const form = new FormData(); form.append("file", file, file.name); form.append("selection", JSON.stringify(selection)); install.disabled = true; install.textContent = "IMPORTING…"; catalogStatus(`Installing selected records from ${file.name}…`, "#35d7ff");
        try {
            const response = await fetch(`${API}/library-pack/import`, { method: "POST", body: form }); const result = await response.json().catch(() => ({})); if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
            componentViewsLoaded = { outfit: false, scene: false }; wardrobeDataLoaded = false; workshopExtrasLoaded = false; libraryLoadedOnce = false; await load(); refreshLibraryChrome(); render();
            const created = Number(result.created_prompts || 0) + Number(result.created_components || 0) + Number(result.created_wardrobe || 0) + Number(result.created_fragments || 0) + Number(result.created_recipes || 0);
            const matched = Number(result.matched_prompts || 0) + Number(result.matched_components || 0) + Number(result.matched_wardrobe || 0) + Number(result.matched_fragments || 0) + Number(result.matched_recipes || 0);
            const reassigned = Number(result.memberships_removed || 0); const summary = `${created.toLocaleString()} new records · ${matched.toLocaleString()} existing matched · ${Number(result.previews_added || 0).toLocaleString()} thumbnails added`;
            catalogStatus(`Installed ${result.name || file.name} · ${summary}${reassigned ? ` · ${reassigned.toLocaleString()} old pack memberships replaced` : ""}`, "#6ee7a2");
            alert(`Creative Library import complete.\n\n${summary}\n${Number(result.collections_added || 0).toLocaleString()} Homes/Collections added · ${Number(result.memberships_added || 0).toLocaleString()} memberships added.\n\nUnchecked pack content was left alone.`); overlay.remove();
        } catch (error) { catalogStatus("Creative Library Pack import failed.", "#ff78bd"); alert(error.message || "Could not import the Creative Library Pack."); }
        finally { install.disabled = false; install.textContent = "IMPORT SELECTED"; }
    };
    footer.append(cancel, install); card.append(body, footer);
}

function importCreativeLibraryPack() {
    const picker = document.createElement("input"); picker.type = "file"; picker.accept = ".soslibrary,.zip,application/zip";
    picker.onchange = async () => {
        const file = picker.files?.[0]; if (!file) return;
        const form = new FormData(); form.append("file", file, file.name); catalogStatus(`Inspecting ${file.name}…`, "#35d7ff");
        try {
            const response = await fetch(`${API}/library-pack/inspect`, { method: "POST", body: form }); const inspection = await response.json().catch(() => ({})); if (!response.ok) throw new Error(inspection.error || `HTTP ${response.status}`);
            showCreativeLibraryImport(file, inspection);
        } catch (error) { catalogStatus("Creative Library Pack inspection failed.", "#ff78bd"); alert(error.message || "Could not inspect the Creative Library Pack."); }
    };
    picker.click();
}

function openLibraryPackWorkflow() {
    const { overlay, card } = collectionModal("LIBRARY PACK", "660px");
    card.style.borderColor = "#6ee7a299";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "grid", gap: "9px" });
    const intro = document.createElement("div"); intro.textContent = "One portable .soslibrary format carries selected assets, Homes, Collections, dependencies, and previews. Choose whether to build a pack or inspect one before importing."; Object.assign(intro.style, { color: "#b9b2c0", font: "11px/1.5 Segoe UI,Arial", marginBottom: "3px" }); body.append(intro);
    const choice = (label, detail, color, handler) => {
        const button = action(label, color); Object.assign(button.style, { display: "grid", gap: "3px", width: "100%", padding: "12px", textAlign: "left" });
        const note = document.createElement("span"); note.textContent = detail; Object.assign(note.style, { color: "#99919f", font: "9px/1.35 Segoe UI,Arial", textTransform: "none", letterSpacing: "0" }); button.append(note);
        button.onclick = () => { overlay.remove(); handler(); }; body.append(button);
    };
    choice("BUILD LIBRARY PACK", "Full Backup, Starter / Share, Wardrobe & Looks, Current Scope, or Custom.", "#6ee7a2", () => void showCreativeLibraryExport());
    choice("IMPORT LIBRARY PACK", "Inspect contents and choose exactly what to merge without deleting local records.", "#35d7ff", importCreativeLibraryPack);
    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", padding: "2px 14px 14px" }); const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove(); foot.append(cancel); card.append(body, foot);
}

const CREATIVE_PURGE_AREAS = [
    { key: "templates", label: "Templates", count: () => Number(libraryStateCounts.templates || 0), detail: "Template records, ratings, thumbnails, Template Category/Subcategory navigation, and Template memberships. Source TXT files on disk are preserved." },
    { key: "prompts", label: "Prompts", count: () => Number(libraryStateCounts.prompts || 0), detail: "Prompt records, ratings, previews, Homes, Collections, and source-log provenance. Source TXT files on disk are preserved." },
    { key: "saved_recipes", label: "Saved Generation Recipes", count: () => Number(libraryStateCounts.recipes || 0), detail: "Saved Studio generation Recipes and their Recipe thumbnails. Prompt and Template records are not deleted unless selected separately." },
    { key: "outfit_looks", label: "Outfit Looks", count: () => Number(libraryStateCounts.outfits || 0), detail: "Canonical Outfit Look records, ratings, previews, Homes, Collections, and Look-to-Wardrobe links. Wardrobe items remain unless selected separately." },
    { key: "wardrobe", label: "Wardrobe", count: () => Number(libraryStateCounts.wardrobe || 0), detail: "Wardrobe Pieces, Sets, Finishers, Body Styling, ratings, previews, migration state, source links, pack provenance, and Collections. Outfit Looks remain unless selected separately." },
    { key: "scenes", label: "Scenes", count: () => Number(libraryStateCounts.scenes || 0), detail: "Scene records, ratings, previews, Homes, and Collections." },
    { key: "workshop", label: "Legacy Workshop Data", count: () => Number(libraryStateCounts.fragments || 0) + Number(libraryStateCounts.boards || 0), detail: "Legacy Workshop fragments and Boards left from the retired Workshop interface. Saved Generation Recipes are a separate option above." },
];

function showCreativeLibraryPurge() {
    const { overlay, card } = collectionModal("PURGE CREATIVE LIBRARY", "880px"); card.style.borderColor = "#ff4ab899";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto", display: "grid", gap: "10px" });
    const intro = document.createElement("div"); intro.textContent = "Choose exactly which Creative Library areas to erase. Nothing is selected by default. You will get a second, itemized warning before anything is deleted."; Object.assign(intro.style, { color: "#c9c1cf", font: "10px/1.5 Segoe UI,Arial" }); body.append(intro);
    const totalRow = document.createElement("label"); Object.assign(totalRow.style, { display: "flex", gap: "10px", alignItems: "center", padding: "11px", borderRadius: "9px", border: "1px solid #ff4ab866", background: "rgba(255,74,184,.06)", cursor: "pointer" });
    const totalBox = document.createElement("input"); totalBox.type = "checkbox"; const totalText = document.createElement("div"); totalText.innerHTML = `<strong style="color:#ff9ccc">TOTAL CREATIVE LIBRARY PURGE</strong><div style="margin-top:3px;color:#918997;font:9px/1.35 Segoe UI,Arial">Select every area below and also clear installed Creative Library pack provenance / saved structure-order metadata.</div>`; totalRow.append(totalBox,totalText); body.append(totalRow);
    const rows = document.createElement("div"); Object.assign(rows.style, { display: "grid", gap: "7px" }); body.append(rows);
    const boxes = new Map();
    for (const area of CREATIVE_PURGE_AREAS) {
        const row = document.createElement("label"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "22px 1fr auto", gap: "8px", alignItems: "start", padding: "10px", borderRadius: "8px", border: "1px solid #36313c", background: "rgba(255,255,255,.018)", cursor: "pointer" });
        const box = document.createElement("input"); box.type = "checkbox"; boxes.set(area.key, box);
        const text = document.createElement("div"); const title = document.createElement("strong"); title.textContent = area.label; Object.assign(title.style, { display: "block", color: "#fff", font: "900 10px Segoe UI,Arial" }); const detail = document.createElement("div"); detail.textContent = area.detail; Object.assign(detail.style, { marginTop: "3px", color: "#918997", font: "9px/1.4 Segoe UI,Arial" }); text.append(title,detail);
        const count = document.createElement("span"); count.textContent = area.count().toLocaleString(); Object.assign(count.style, { color: "#ff9ccc", font: "800 9px Consolas,monospace" }); row.append(box,text,count); rows.append(row);
        box.onchange = () => { totalBox.checked = CREATIVE_PURGE_AREAS.every(item => boxes.get(item.key)?.checked); };
    }
    totalBox.onchange = () => boxes.forEach(box => { box.checked = totalBox.checked; });
    const note = document.createElement("div"); note.textContent = "Purge removes Creative Library database records and Library-managed thumbnails. It does not move, rename, or delete your original external TXT files. Imported source copies are treated as source material rather than thumbnails and remain on disk."; Object.assign(note.style, { padding: "9px 10px", borderRadius: "8px", border: "1px solid #f6e65a44", color: "#c7bea0", background: "rgba(246,230,90,.035)", font: "9px/1.45 Segoe UI,Arial" }); body.append(note);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" }); const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove(); const review = action("REVIEW PURGE", "#ff4ab8"); footer.append(cancel,review); card.append(body,footer);
    review.onclick = () => {
        const selected = CREATIVE_PURGE_AREAS.filter(area => boxes.get(area.key)?.checked); if (!selected.length) { alert("Choose at least one Creative Library area to purge."); return; }
        const isTotal = selected.length === CREATIVE_PURGE_AREAS.length;
        body.replaceChildren(); footer.replaceChildren();
        const warning = document.createElement("div"); warning.textContent = isTotal ? "TOTAL CREATIVE LIBRARY PURGE" : "FINAL PURGE REVIEW"; Object.assign(warning.style, { color: "#ff8fbd", font: "900 15px Segoe UI,Arial" }); body.append(warning);
        const warningCopy = document.createElement("div"); warningCopy.textContent = "The following data will be permanently removed. This operation cannot be undone from Creative Library."; Object.assign(warningCopy.style, { color: "#c9c1cf", font: "10px/1.5 Segoe UI,Arial" }); body.append(warningCopy);
        for (const area of selected) {
            const line = document.createElement("div"); line.innerHTML = `<strong style="color:#fff">${area.label} · ${area.count().toLocaleString()}</strong><div style="margin-top:3px;color:#9f97a5;font:9px/1.4 Segoe UI,Arial">${area.detail}</div>`; Object.assign(line.style, { padding: "9px", borderRadius: "8px", border: "1px solid #45313d", background: "rgba(255,74,184,.035)" }); body.append(line);
        }
        if (isTotal) { const extra = document.createElement("div"); extra.textContent = "Because every area is selected, installed .soslibrary pack provenance and saved library structure-order metadata will also be cleared."; Object.assign(extra.style, { padding: "9px", color: "#ffceb8", border: "1px solid #ff9b5f55", borderRadius: "8px", font: "9px/1.4 Segoe UI,Arial" }); body.append(extra); }
        const phrase = isTotal ? "PURGE EVERYTHING" : "PURGE SELECTED"; const confirmation = document.createElement("input"); confirmation.placeholder = `Type ${phrase}`; Object.assign(confirmation.style, { width: "100%", boxSizing: "border-box", padding: "10px", borderRadius: "7px", border: "1px solid #ff4ab866", background: "#09080d", color: "#fff", font: "11px Consolas,monospace" }); body.append(confirmation);
        const back = action("Back", "#8f8997"); back.onclick = () => { overlay.remove(); showCreativeLibraryPurge(); }; const purge = action(isTotal ? "PURGE EVERYTHING" : "PURGE SELECTED", "#ff4ab8"); purge.disabled = true; purge.style.opacity = ".42"; confirmation.oninput = () => { purge.disabled = confirmation.value.trim().toUpperCase() !== phrase; purge.style.opacity = purge.disabled ? ".42" : "1"; };
        purge.onclick = async () => { purge.disabled = true; purge.textContent = "PURGING…"; try { const result = await request("/maintenance/purge", { method: "POST", body: JSON.stringify({ scopes: selected.map(area => area.key), confirm: phrase }) }); libraryStateCounts = result.counts || {}; libraryLoadedOnce = false; componentViewsLoaded = { outfit:false, scene:false }; wardrobeDataLoaded = false; promptAssets = []; derivedValues = { outfits:[], scenes:[], logs:{} }; wardrobeItems = []; activeCollection = ""; activeLibraryCollection = { outfit:"", scene:"", wardrobe:"" }; promptParent = promptSubcategory = promptLogPath = ""; overlay.remove(); await load(); catalogStatus(`Purge complete · ${Number(result.previews_deleted || 0).toLocaleString()} thumbnails removed.`, "#6ee7a2"); } catch (error) { alert(error.message || "Could not purge the selected Creative Library areas."); purge.disabled = false; purge.textContent = isTotal ? "PURGE EVERYTHING" : "PURGE SELECTED"; } };
        footer.append(back,purge);
    };
}

async function showOrphanThumbnailCleaner() {
    const { overlay, card } = collectionModal("CLEAN ORPHAN THUMBNAILS", "720px"); card.style.borderColor = "#ff9b5f99";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto", display: "grid", gap: "10px" });
    const help = document.createElement("div"); help.textContent = "This maintenance scan compares files on disk against every live Prompt, Template, Recipe, Outfit, Scene, and Wardrobe thumbnail reference. It does not reset a Library tab or touch referenced thumbnails."; Object.assign(help.style, { color: "#b9b2c0", font: "10px/1.5 Segoe UI,Arial" }); body.append(help);
    const resultBox = document.createElement("div"); resultBox.textContent = "Scanning…"; Object.assign(resultBox.style, { padding: "12px", borderRadius: "9px", background: "rgba(255,155,95,.05)", border: "1px solid #ff9b5f44", color: "#ffd5bc", font: "800 11px Segoe UI,Arial" }); body.append(resultBox);
    const list = document.createElement("div"); Object.assign(list.style, { maxHeight: "250px", overflow: "auto", color: "#8f8997", font: "9px/1.45 Consolas,monospace", whiteSpace: "pre-wrap" }); body.append(list);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "space-between", gap: "8px", padding: "0 14px 14px" }); const cancel = action("Close", "#8f8997"); cancel.onclick = () => overlay.remove(); const clean = action("DELETE ORPHANS", "#ff9b5f"); clean.disabled = true; clean.style.opacity = ".4"; footer.append(cancel, clean); card.append(body, footer);
    try {
        const scan = await request("/maintenance/orphan-previews"); const mb = Number(scan.bytes || 0) / (1024 * 1024); resultBox.textContent = `${Number(scan.orphans || 0).toLocaleString()} orphan files · ${mb.toFixed(1)} MB reclaimable`;
        list.textContent = (scan.files || []).map(row => `${row.group}/ ${row.name} · ${(Number(row.bytes || 0) / 1024).toFixed(1)} KB`).join("\n") + (scan.truncated ? "\n…preview list truncated" : "");
        clean.disabled = !Number(scan.orphans || 0); clean.style.opacity = clean.disabled ? ".4" : "1";
        clean.onclick = async () => {
            if (!confirm(`Delete ${Number(scan.orphans || 0).toLocaleString()} genuinely unreferenced thumbnail files?\n\nEvery currently referenced Creative Library thumbnail is preserved.`)) return;
            clean.disabled = true; clean.textContent = "CLEANING…";
            try { const result = await request("/maintenance/orphan-previews/clean", { method: "POST", body: JSON.stringify({ confirm: "CLEAN ORPHAN THUMBNAILS" }) }); resultBox.textContent = `Deleted ${Number(result.deleted || 0).toLocaleString()} orphan files · ${(Number(result.deleted_bytes || 0) / (1024 * 1024)).toFixed(1)} MB reclaimed`; list.textContent = "Referenced thumbnails were preserved."; catalogStatus(`Cleaned ${Number(result.deleted || 0).toLocaleString()} orphan thumbnails.`, "#6ee7a2"); clean.remove(); }
            catch (error) { alert(error.message || "Could not clean orphan thumbnails."); clean.disabled = false; clean.textContent = "DELETE ORPHANS"; }
        };
    } catch (error) { resultBox.textContent = "Scan failed."; list.textContent = error.message || String(error); }
}

function migrationItemEditor(item) {
    const row = document.createElement("div"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "100px 150px 170px minmax(180px,1fr) auto", gap: "6px", alignItems: "center", padding: "7px", borderTop: "1px solid #2b2731" });
    const type = makeSelect([["piece", "Piece"], ["set", "Matching Set"], ["finisher", "Finisher"], ["styling", "Body Styling"]], String(item.item_type || "piece")); Object.assign(type.style, { width: "100%", padding: "6px", fontSize: "9px" });
    const category = document.createElement("select"); Object.assign(category.style, { width: "100%", padding: "6px", color: "#fff", background: "#15131a", border: "1px solid #4a4452", borderRadius: "6px", fontSize: "9px" });
    const subtype = document.createElement("select"); Object.assign(subtype.style, { width: "100%", padding: "6px", color: "#fff", background: "#15131a", border: "1px solid #4a4452", borderRadius: "6px", fontSize: "9px" });
    const value = document.createElement("input"); value.value = String(item.value || ""); Object.assign(value.style, { width: "100%", boxSizing: "border-box", padding: "7px 8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452", borderRadius: "6px", fontSize: "10px" });
    const remove = action("×", "#ff4ab8"); Object.assign(remove.style, { padding: "5px 8px" }); remove.onclick = () => row.remove();
    const refreshTaxonomy = () => {
        const categories = type.value === "set" ? ["Matching Sets"] : type.value === "finisher" ? ["Other"] : type.value === "styling" ? ["Body Styling"] : Object.keys(WARDROBE_TAXONOMY).filter(name => !["Matching Sets", "Other"].includes(name)).concat(["Other"]);
        const priorCategory = String(item.category || "Uncategorized"); category.replaceChildren(); categories.forEach(name => { const option = document.createElement("option"); option.value = name; option.textContent = name; category.append(option); }); category.value = categories.includes(priorCategory) ? priorCategory : categories[0];
        const updateSubtype = () => { const values = type.value === "styling" ? WARDROBE_STYLING_TAXONOMY : (WARDROBE_TAXONOMY[category.value] || ["Uncategorized"]); const prior = String(item.subtype || ""); subtype.replaceChildren(); values.forEach(name => { const option = document.createElement("option"); option.value = name; option.textContent = name; subtype.append(option); }); subtype.value = values.includes(prior) ? prior : values[0] || ""; };
        category.onchange = updateSubtype; updateSubtype();
    };
    type.onchange = refreshTaxonomy; refreshTaxonomy(); row.append(type, category, subtype, value, remove); row._migrationControls = { type, category, subtype, value, relation: String(item.relation || "") }; return row;
}

function showMigrationLookEditor(parentOverlay, sourceRow, refreshParent) {
    const { overlay, card } = collectionModal("REVIEW LOOK DECOMPOSITION", "1100px"); card.style.borderColor = "#f6e65a99";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const source = document.createElement("div"); source.textContent = sourceRow.value; Object.assign(source.style, { padding: "11px", marginBottom: "10px", borderRadius: "8px", background: "rgba(246,230,90,.06)", border: "1px solid #f6e65a55", color: "#fff7c2", fontSize: "11px", lineHeight: "1.45" }); body.append(source);
    const header = document.createElement("div"); header.textContent = "TYPE · CATEGORY · SUBTYPE · EXTRACTED VALUE"; Object.assign(header.style, { color: "#8f8997", font: "800 8px Segoe UI,Arial", letterSpacing: ".08em", padding: "4px 7px" }); body.append(header);
    const rows = document.createElement("div"); (sourceRow.items || []).forEach(item => rows.append(migrationItemEditor(item))); body.append(rows);
    const addPiece = action("+ ADD PIECE", "#35d7ff"); Object.assign(addPiece.style, { marginTop: "9px", padding: "6px 9px", fontSize: "9px" }); addPiece.onclick = () => rows.append(migrationItemEditor({ item_type: "piece", category: "Other", subtype: "Uncategorized", value: "" })); body.append(addPiece);
    const footer = document.createElement("div"); Object.assign(footer.style, { padding: "0 14px 14px", display: "flex", justifyContent: "space-between", gap: "8px" });
    const ignore = action("KEEP AS LOOK ONLY", "#8f8997"); ignore.onclick = async () => { await request("/wardrobe-migration/ignore", { method: "POST", body: JSON.stringify({ look_id: sourceRow.component_id, value: sourceRow.value }) }); overlay.remove(); await refreshParent(); };
    const right = document.createElement("div"); Object.assign(right.style, { display: "flex", gap: "8px" }); const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove(); const accept = action("ACCEPT PIECES", "#f6e65a"); accept.onclick = async () => {
        const items = [...rows.children].map(row => row._migrationControls).filter(Boolean).map(control => ({ item_type: control.type.value, category: control.category.value, subtype: control.subtype.value, value: control.value.value.trim(), relation: control.relation })).filter(item => item.value);
        if (!items.length) { alert("Keep at least one Piece, Set, or Finisher, or choose Keep as Look Only."); return; }
        accept.disabled = true; try { await request("/wardrobe-migration/accept-custom", { method: "POST", body: JSON.stringify({ look_id: sourceRow.component_id, items }) }); await load(); overlay.remove(); await refreshParent(); } catch (error) { alert(error.message || "Could not accept this decomposition."); } finally { accept.disabled = false; }
    }; right.append(cancel, accept); footer.append(ignore, right); card.append(body, footer);
}

async function showWardrobeMigration() {
    const { overlay, card } = collectionModal("WARDROBE MIGRATION WORKBENCH", "1440px");
    card.style.borderColor = "#f6e65a99";
    card.style.maxHeight = "92vh";
    const body = document.createElement("div");
    Object.assign(body.style, { padding: "12px", overflow: "hidden", display: "flex", flexDirection: "column", gap: "9px", minHeight: "0" });
    const footer = document.createElement("div");
    Object.assign(footer.style, { padding: "0 12px 12px", display: "flex", justifyContent: "space-between", gap: "8px", alignItems: "center" });
    const status = document.createElement("span");
    Object.assign(status.style, { color: "#9f98a7", fontSize: "10px" });
    const right = document.createElement("div"); Object.assign(right.style, { display: "flex", gap: "8px" });
    const rescan = action("RE-ANALYZE V3", "#35d7ff");
    const migrateView = action("MIGRATE CURRENT VIEW", "#6ee7a2");
    const lookOnlyView = action("LOOK-ONLY CURRENT VIEW", "#8f8997");
    const migrate = action("MIGRATE ALL HIGH CONFIDENCE", "#f6e65a");
    const done = action("Done", "#8f8997"); done.onclick = () => overlay.remove();
    right.append(rescan, lookOnlyView, migrateView, migrate, done); footer.append(status, right); card.append(body, footer);

    let data = null;
    let queueStatus = "all";
    let queueIssue = "";
    let queueNewOnly = false;
    let queueQuery = "";
    let queueOffset = 0;
    const queueLimit = 60;
    let selectedId = "";

    const currentRow = () => (data?.rows || []).find(row => String(row.component_id || "") === selectedId) || (data?.rows || [])[0] || null;

    const collectEditorItems = editorRows => [...editorRows.children]
        .map(row => row._migrationControls)
        .filter(Boolean)
        .map(control => ({ item_type: control.type.value, category: control.category.value, subtype: control.subtype.value, value: control.value.value.trim(), relation: control.relation }))
        .filter(item => item.value);

    const acceptOne = async (rowData, editorRows = null) => {
        if (!rowData) return;
        if (editorRows) {
            const items = collectEditorItems(editorRows);
            if (!items.length) { alert("Keep at least one Piece, Set, Finisher, or Body Styling token, or choose Look Only."); return; }
            await request("/wardrobe-migration/accept-custom", { method: "POST", body: JSON.stringify({ look_id: rowData.component_id, items }) });
        } else {
            await request("/wardrobe-migration/accept", { method: "POST", body: JSON.stringify({ look_ids: [rowData.component_id], manually_reviewed: true }) });
        }
        selectedId = "";
        await load();
        await refresh(false);
    };

    const ignoreOne = async rowData => {
        if (!rowData) return;
        await request("/wardrobe-migration/ignore", { method: "POST", body: JSON.stringify({ look_id: rowData.component_id, value: rowData.value }) });
        selectedId = "";
        await load();
        await refresh(false);
    };

    const metricBox = (label, value, color, hint = "") => {
        const box = document.createElement("div");
        Object.assign(box.style, { padding: "8px 9px", borderRadius: "8px", border: `1px solid ${color}55`, background: `${color}0d`, minWidth: "0" });
        const num = document.createElement("strong"); num.textContent = Number(value || 0).toLocaleString(); Object.assign(num.style, { display: "block", color, fontSize: "15px" });
        const lab = document.createElement("span"); lab.textContent = label; Object.assign(lab.style, { color: "#b7b0bc", font: "800 7px Segoe UI,Arial", letterSpacing: ".04em" });
        box.append(num, lab);
        if (hint) { const sub = document.createElement("div"); sub.textContent = hint; Object.assign(sub.style, { marginTop: "2px", color: "#746e79", fontSize: "7px" }); box.append(sub); }
        return box;
    };

    const draw = () => {
        body.replaceChildren();
        if (!data) { const loading = document.createElement("div"); loading.textContent = "Analyzing existing Looks with Wardrobe Parser v4…"; loading.style.padding = "30px"; body.append(loading); return; }
        const intro = document.createElement("div");
        intro.textContent = "Original Looks stay untouched. Parser v4 separates stable visual Pieces from vague garment words, recognizes more Sets, and keeps anything uncertain in review instead of silently polluting the Wardrobe.";
        Object.assign(intro.style, { color: "#b9b2c0", fontSize: "10px", lineHeight: "1.45" }); body.append(intro);

        const summary = data.summary || {};
        const metrics = document.createElement("div");
        Object.assign(metrics.style, { display: "grid", gridTemplateColumns: "repeat(9,minmax(90px,1fr))", gap: "6px" });
        metrics.append(
            metricBox("LOOKS", summary.total, "#35d7ff"),
            metricBox("NEW", summary.new, "#35d7ff", "not previously analyzed"),
            metricBox("READY", summary.ready, "#6ee7a2"),
            metricBox("REVIEW", summary.review, "#f6e65a"),
            metricBox("UNRESOLVED", summary.unresolved, "#ff9b5f"),
            metricBox("MIGRATED", summary.accepted, "#ff4ab8"),
            metricBox("DETECTED USES", summary.detected_uses, "#b89aff", "all occurrences"),
            metricBox("UNIQUE CANDIDATES", summary.unique_candidates, "#8fdfff", "before migration"),
            metricBox("REUSED OCCURRENCES", summary.reused_occurrences, "#63e6a4", `${Number(summary.generic_candidates || 0).toLocaleString()} generic flagged`),
        );
        body.append(metrics);
        const viewCount = Number(data.queue_total || 0);
        migrateView.textContent = `MIGRATE CURRENT VIEW · ${viewCount.toLocaleString()}`;
        migrateView.disabled = viewCount <= 0 || queueStatus === "unresolved";
        lookOnlyView.textContent = `LOOK-ONLY CURRENT VIEW · ${viewCount.toLocaleString()}`;
        lookOnlyView.disabled = viewCount <= 0;

        const queueTools = document.createElement("div");
        Object.assign(queueTools.style, { display: "grid", gridTemplateColumns: "150px 155px 112px minmax(220px,1fr) auto auto auto", gap: "6px", alignItems: "center", padding: "7px", borderRadius: "8px", border: "1px solid #3a3440", background: "rgba(255,255,255,.018)" });
        const filter = makeSelect([["all", "All pending"], ["review", "Needs review"], ["unresolved", "Unresolved"], ["ready", "Ready / high confidence"]], queueStatus); Object.assign(filter.style, { width: "100%", padding: "6px", fontSize: "9px" });
        filter.onchange = () => { queueStatus = filter.value; queueOffset = 0; selectedId = ""; void refresh(false); };
        const issue = makeSelect([["", "All issue types"], ["generic", "Generic / too vague"], ["set", "Sets detected"], ["complex", "Complex · 4+ items"], ["boundary", "Boundary ambiguity"], ["compound", "Possible multi-item Piece"], ["styling", "Body Styling"], ["unresolved", "No stable pieces"]], queueIssue); Object.assign(issue.style, { width: "100%", padding: "6px", fontSize: "9px" });
        issue.onchange = () => { queueIssue = issue.value; queueOffset = 0; selectedId = ""; void refresh(false); };
        const newOnly = document.createElement("label"); Object.assign(newOnly.style, { display: "flex", alignItems: "center", gap: "6px", color: "#c9c3cd", font: "700 9px Segoe UI,Arial", cursor: "pointer" }); const newCheck = document.createElement("input"); newCheck.type = "checkbox"; newCheck.checked = queueNewOnly; newCheck.onchange = () => { queueNewOnly = newCheck.checked; queueOffset = 0; selectedId = ""; void refresh(false); }; newOnly.append(newCheck, document.createTextNode("NEW ONLY"));
        const search = document.createElement("input"); search.type = "search"; search.placeholder = "Search Look or proposed Piece…"; search.value = queueQuery; Object.assign(search.style, { minWidth: "0", padding: "6px 8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452", borderRadius: "7px", fontSize: "9px" });
        let searchTimer = null; search.oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { queueQuery = search.value.trim(); queueOffset = 0; selectedId = ""; void refresh(false); }, 220); };
        const prev = action("←", "#8f8997"); const range = document.createElement("span"); const next = action("→", "#8f8997");
        const total = Number(data.queue_total || 0); const start = total ? Number(data.queue_offset || 0) + 1 : 0; const finish = Math.min(total, Number(data.queue_offset || 0) + (data.rows || []).length); range.textContent = total ? `${start.toLocaleString()}–${finish.toLocaleString()} / ${total.toLocaleString()}` : "0 results"; Object.assign(range.style, { minWidth: "92px", textAlign: "center", color: "#b5aebc", font: "800 8px Segoe UI,Arial" });
        prev.disabled = queueOffset <= 0; next.disabled = queueOffset + queueLimit >= total; prev.onclick = () => { queueOffset = Math.max(0, queueOffset - queueLimit); selectedId = ""; void refresh(false); }; next.onclick = () => { queueOffset += queueLimit; selectedId = ""; void refresh(false); };
        queueTools.append(filter, issue, newOnly, search, prev, range, next); body.append(queueTools);

        const workbench = document.createElement("div");
        Object.assign(workbench.style, { minHeight: "0", flex: "1 1 auto", display: "grid", gridTemplateColumns: "minmax(390px,.9fr) minmax(520px,1.1fr)", gap: "9px", overflow: "hidden" });
        const listPane = document.createElement("section"); Object.assign(listPane.style, { minHeight: "0", overflow: "auto", border: "1px solid #342f39", borderRadius: "9px", background: "#0c0a10" });
        const editorPane = document.createElement("section"); Object.assign(editorPane.style, { minHeight: "0", overflow: "auto", border: "1px solid #f6e65a44", borderRadius: "9px", background: "linear-gradient(160deg,rgba(246,230,90,.035),#0b0910)" });

        if (!(data.rows || []).length) { const empty = document.createElement("div"); empty.textContent = "Nothing in this queue. Try another status, issue type, or search."; Object.assign(empty.style, { padding: "28px", textAlign: "center", color: "#8f8997" }); listPane.append(empty); }
        for (const rowData of data.rows || []) {
            const selected = String(rowData.component_id || "") === String(selectedId || currentRow()?.component_id || "");
            if (!selectedId && selected) selectedId = String(rowData.component_id || "");
            const row = document.createElement("button"); row.type = "button";
            Object.assign(row.style, { width: "100%", display: "block", textAlign: "left", padding: "8px 9px", border: "0", borderBottom: "1px solid #2a2630", borderLeft: selected ? "3px solid #f6e65a" : "3px solid transparent", background: selected ? "rgba(246,230,90,.07)" : "transparent", cursor: "pointer", color: "inherit" });
            const top = document.createElement("div"); Object.assign(top.style, { display: "flex", gap: "7px", alignItems: "start" });
            const source = document.createElement("div"); source.textContent = rowData.value; Object.assign(source.style, { flex: "1", color: "#eee9f1", fontSize: "9px", lineHeight: "1.32", display: "-webkit-box", WebkitLineClamp: "2", WebkitBoxOrient: "vertical", overflow: "hidden" });
            const badge = document.createElement("span"); badge.textContent = `${rowData.is_new ? "NEW · " : ""}${String(rowData.status || "").toUpperCase()} ${Math.round(Number(rowData.confidence || 0) * 100)}%`; Object.assign(badge.style, { color: rowData.status === "ready" ? "#6ee7a2" : rowData.status === "review" ? "#f6e65a" : "#ff9b5f", font: "800 7px Segoe UI,Arial", whiteSpace: "nowrap" }); top.append(source, badge); row.append(top);
            const chips = document.createElement("div"); Object.assign(chips.style, { display: "flex", flexWrap: "wrap", gap: "3px", marginTop: "5px" });
            for (const item of rowData.items || []) { const generic = item.visual_ready === false; const chip = document.createElement("span"); chip.textContent = `${generic ? "GENERIC" : item.item_type === "set" ? "SET" : item.item_type === "finisher" ? "FINISHER" : item.item_type === "styling" ? "BODY STYLE" : item.subtype || item.category}: ${item.value}`; Object.assign(chip.style, { maxWidth: "220px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding: "2px 5px", borderRadius: "999px", border: `1px solid ${generic ? "#ff9b5f66" : "#4a4452"}`, color: generic ? "#ffb37d" : item.item_type === "set" ? "#d9c9ff" : "#c8efff", fontSize: "7px" }); chips.append(chip); }
            row.append(chips); row.onclick = () => { selectedId = String(rowData.component_id || ""); draw(); }; listPane.append(row);
        }

        const selectedRow = currentRow();
        if (!selectedRow) {
            const empty = document.createElement("div"); empty.textContent = "Select a Look from the queue to review all proposed Pieces in one place."; Object.assign(empty.style, { padding: "36px", textAlign: "center", color: "#8f8997" }); editorPane.append(empty);
        } else {
            const editorHead = document.createElement("div"); Object.assign(editorHead.style, { padding: "10px 11px", borderBottom: "1px solid #3a3440", position: "sticky", top: "0", zIndex: "4", background: "rgba(13,11,17,.97)", backdropFilter: "blur(8px)" });
            const kicker = document.createElement("div"); kicker.textContent = `REVIEW LOOK · ${String(selectedRow.status || "").toUpperCase()} · ${Math.round(Number(selectedRow.confidence || 0) * 100)}%`; Object.assign(kicker.style, { color: "#f6e65a", font: "900 8px Segoe UI,Arial", letterSpacing: ".08em", marginBottom: "5px" });
            const source = document.createElement("div"); source.textContent = selectedRow.value; Object.assign(source.style, { color: "#fff7c2", fontSize: "10px", lineHeight: "1.4" }); editorHead.append(kicker, source); editorPane.append(editorHead);
            const issueRow = document.createElement("div"); Object.assign(issueRow.style, { display: "flex", flexWrap: "wrap", gap: "5px", padding: "8px 10px 0" });
            for (const issueName of selectedRow.issues || []) { const chip = document.createElement("span"); chip.textContent = issueName === "generic" ? "GENERIC VALUE NEEDS DECISION" : issueName === "set" ? "SET DETECTED" : issueName === "complex" ? "COMPLEX LOOK" : issueName === "boundary" ? "BOUNDARY AMBIGUITY" : issueName === "compound" ? "POSSIBLE MULTI-ITEM PIECE" : issueName === "styling" ? "BODY STYLING TOKEN" : "UNRESOLVED"; Object.assign(chip.style, { padding: "3px 6px", borderRadius: "999px", border: "1px solid #ff9b5f66", color: "#ffb37d", font: "800 7px Segoe UI,Arial" }); issueRow.append(chip); } editorPane.append(issueRow);
            const labels = document.createElement("div"); labels.textContent = "TYPE · CATEGORY · SUBTYPE · EXTRACTED VALUE"; Object.assign(labels.style, { color: "#8f8997", font: "800 7px Segoe UI,Arial", letterSpacing: ".08em", padding: "8px 10px 4px" }); editorPane.append(labels);
            const editorRows = document.createElement("div");
            for (const item of selectedRow.items || []) { const editRow = migrationItemEditor(item); if (item.visual_ready === false) { editRow.style.background = "rgba(255,155,95,.055)"; editRow.style.borderLeft = "3px solid #ff9b5f"; editRow.title = item.reason || "Generic candidate. Edit it into a specific visual Piece, remove it, or keep the Look only."; } editorRows.append(editRow); }
            editorPane.append(editorRows);
            const addPiece = action("+ ADD PIECE", "#35d7ff"); Object.assign(addPiece.style, { margin: "8px 10px", padding: "6px 9px", fontSize: "8px" }); addPiece.onclick = () => editorRows.append(migrationItemEditor({ item_type: "piece", category: "Other", subtype: "Uncategorized", value: "" })); editorPane.append(addPiece);
            const help = document.createElement("div"); help.textContent = "Orange rows are too vague for a stable visual thumbnail. Make them more specific if the source Look supports it, remove them, or leave this Look out of the Wardrobe."; Object.assign(help.style, { margin: "0 10px 8px", color: "#8f8997", fontSize: "8px", lineHeight: "1.4" }); editorPane.append(help);
            const editorActions = document.createElement("div"); Object.assign(editorActions.style, { position: "sticky", bottom: "0", display: "grid", gridTemplateColumns: "auto 1fr auto auto", gap: "7px", padding: "9px 10px", borderTop: "1px solid #3a3440", background: "rgba(13,11,17,.97)", backdropFilter: "blur(8px)" });
            const lookOnly = action("LOOK ONLY & NEXT", "#8f8997"); const spacer = document.createElement("span"); const acceptProposal = action("ACCEPT PROPOSAL", "#6ee7a2"); const acceptEdit = action("ACCEPT EDITS & NEXT", "#f6e65a");
            lookOnly.onclick = async () => { lookOnly.disabled = true; try { await ignoreOne(selectedRow); } catch (error) { alert(error.message || "Could not mark this Look only."); } finally { lookOnly.disabled = false; } };
            acceptProposal.onclick = async () => { acceptProposal.disabled = true; try { await acceptOne(selectedRow, null); } catch (error) { alert(error.message || "Could not accept this decomposition."); } finally { acceptProposal.disabled = false; } };
            acceptEdit.onclick = async () => { acceptEdit.disabled = true; try { await acceptOne(selectedRow, editorRows); } catch (error) { alert(error.message || "Could not accept these edits."); } finally { acceptEdit.disabled = false; } };
            editorActions.append(lookOnly, spacer, acceptProposal, acceptEdit); editorPane.append(editorActions);
        }
        workbench.append(listPane, editorPane); body.append(workbench);
        status.textContent = `${Number(summary.accepted || 0).toLocaleString()} Looks migrated · ${wardrobeItems.length.toLocaleString()} Wardrobe items · parser ${data.parser_version || "v3"}`;
    };

    const refresh = async (force = false) => {
        status.textContent = force ? "Re-analyzing Looks with parser v4…" : "Loading migration workbench…";
        try {
            const params = new URLSearchParams({ limit: String(queueLimit), offset: String(queueOffset), status: queueStatus, issue: queueIssue, q: queueQuery });
            if (queueNewOnly) params.set("new", "1");
            if (force) params.set("refresh", "1");
            data = await request(`/wardrobe-migration/analyze?${params.toString()}`);
            const total = Number(data.queue_total || 0);
            if (queueOffset >= total && queueOffset > 0) { queueOffset = Math.max(0, Math.floor(Math.max(0, total - 1) / queueLimit) * queueLimit); return refresh(false); }
            if (selectedId && !(data.rows || []).some(row => String(row.component_id || "") === selectedId)) selectedId = "";
            draw();
        } catch (error) { alert(error.message || "Could not analyze Looks."); overlay.remove(); }
    };

    rescan.onclick = () => { queueOffset = 0; selectedId = ""; void refresh(true); };
    migrateView.onclick = async () => {
        const count = Number(data?.queue_total || 0);
        if (!count) return;
        if (queueStatus === "unresolved") { alert("Unresolved Looks have no stable proposal to migrate. Reclassify them, filter Body Styling after re-analysis, or mark them Look Only."); return; }
        const label = [queueStatus !== "all" ? queueStatus : "all pending", queueIssue || "", queueQuery ? `search: ${queueQuery}` : "", queueNewOnly ? "new only" : ""].filter(Boolean).join(" · ");
        if (!confirm(`Migrate all ${count.toLocaleString()} Looks in the CURRENT FILTERED VIEW?\n\n${label}\n\nThis applies the parser proposal across every matching page, not just the ${queueLimit} rows visible now. Generic visual fragments are skipped. Original Looks remain untouched.`)) return;
        migrateView.disabled = true; status.textContent = `Migrating current view · ${count.toLocaleString()} Looks…`;
        try {
            const result = await request("/wardrobe-migration/accept-filtered", { method: "POST", body: JSON.stringify({ status: queueStatus, issue: queueIssue, q: queueQuery, new_only: queueNewOnly }) });
            await load(); outfitMode = "pieces"; wardrobePage = 0; refreshOutfitModeBar(); render();
            catalogStatus(`Current migration view · ${result.accepted_looks || 0} Looks · ${result.created_items || 0} new · ${result.matched_items || 0} reused`, "#6ee7a2");
            queueOffset = 0; selectedId = ""; await refresh(false);
        } catch (error) { alert(error.message || "Could not migrate the current view."); }
        finally { migrateView.disabled = false; }
    };
    lookOnlyView.onclick = async () => {
        const count = Number(data?.queue_total || 0);
        if (!count) return;
        if (!confirm(`Mark all ${count.toLocaleString()} Looks in the CURRENT FILTERED VIEW as LOOK ONLY?\n\nThis affects every matching page and keeps the source Looks unchanged. Use this for values you intentionally do not want harvested into Wardrobe items.`)) return;
        lookOnlyView.disabled = true; status.textContent = `Marking current view Look Only · ${count.toLocaleString()}…`;
        try {
            const result = await request("/wardrobe-migration/ignore-filtered", { method: "POST", body: JSON.stringify({ status: queueStatus, issue: queueIssue, q: queueQuery, new_only: queueNewOnly }) });
            catalogStatus(`Marked ${result.ignored || 0} Looks as Look Only.`, "#8f8997"); queueOffset = 0; selectedId = ""; await refresh(false);
        } catch (error) { alert(error.message || "Could not mark this view Look Only."); }
        finally { lookOnlyView.disabled = false; }
    };
    migrate.onclick = async () => {
        if (!data?.summary?.ready) { alert("There are no high-confidence Looks waiting to migrate."); return; }
        const count = Number(data.summary.ready || 0);
        if (!confirm(`Migrate ${count.toLocaleString()} high-confidence Looks into the Wardrobe?\n\nStable Pieces/Sets plus non-visual Finishers and Body Styling tokens are accepted. Generic garment words stay in review. Original Looks remain untouched.`)) return;
        migrate.disabled = true; migrate.textContent = "MIGRATING…"; status.textContent = `Migrating ${count.toLocaleString()} high-confidence Looks…`;
        try {
            const result = await request("/wardrobe-migration/accept", { method: "POST", body: JSON.stringify({ high_confidence_only: true }) });
            await load(); outfitMode = "pieces"; wardrobePage = 0; refreshOutfitModeBar(); render();
            catalogStatus(`Wardrobe migration · ${result.created_items || 0} new · ${result.matched_items || 0} reused`, "#f6e65a");
            queueOffset = 0; selectedId = ""; await refresh(false);
        } catch (error) { alert(error.message || "Wardrobe migration failed."); }
        finally { migrate.disabled = false; migrate.textContent = "MIGRATE ALL HIGH CONFIDENCE"; }
    };

    draw(); await refresh(false);
}

function showCollectionManager(context = activeView === "recipes" ? "recipe" : "prompt") {
    const recipeMode = context === "recipe";
    const kind = context === "template" ? "template" : "prompt";
    const currentGroups = () => recipeMode ? collections : promptShowcaseFolders(kind);
    const noun = kind === "template" ? "Template" : "Prompt";
    const accent = recipeMode ? "#f6e65a" : kind === "template" ? "#ff4ab8" : "#b89aff";
    const { overlay, card } = collectionModal(recipeMode ? "SAVED RECIPE COLLECTIONS" : `${noun.toUpperCase()} COLLECTIONS`, "720px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const help = document.createElement("div");
    help.textContent = recipeMode
        ? "Collections organize Saved Recipes without changing the Recipes themselves."
        : `${noun} Collections are independent many-to-many creative sets. Rename, delete, or reorder them without changing an asset's Home. Deleting a Collection never deletes its ${noun}s.`;
    Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.45", marginBottom: "12px" });
    const createRow = document.createElement("div"); Object.assign(createRow.style, { display: "flex", gap: "8px", marginBottom: "12px" });
    const input = document.createElement("input"); input.type = "text"; input.placeholder = `New ${noun} Collection`; input.maxLength = 80;
    Object.assign(input.style, { flex: "1", minWidth: "0", padding: "9px 10px", borderRadius: "8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452" });
    const create = action("＋ CREATE", accent); createRow.append(input, create);
    const list = document.createElement("div"); Object.assign(list.style, { display: "grid", gap: "7px" });

    const persistCurrentOrder = async ids => {
        const values = ids || currentGroups().map(item => String(item.collection_id || "")).filter(Boolean);
        await saveCreativeStructureOrder(recipeMode ? "recipe" : kind, recipeMode ? { collections: values } : { showcase_collections: values });
    };
    const moveCollection = async (index, direction) => {
        const ids = currentGroups().map(item => String(item.collection_id || "")).filter(Boolean);
        const next = reorderedValues(ids, index, direction);
        if (next.join("\n") === ids.join("\n")) return;
        await persistCurrentOrder(next); await load(); renderRows();
    };
    const renderRows = () => {
        list.replaceChildren();
        const groups = currentGroups();
        if (!groups.length) {
            const empty = document.createElement("div"); empty.textContent = `No ${noun} Collections yet. Favorites, campaigns, generation pools—any useful creative set.`;
            Object.assign(empty.style, { color: "#8f8997", padding: "10px 0" }); list.append(empty); return;
        }
        groups.forEach((collection, index) => {
            const row = document.createElement("div"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "auto auto minmax(150px,1fr) auto auto auto", alignItems: "center", gap: "7px", padding: "8px 9px", border: `1px solid ${collection.color || accent}66`, borderRadius: "8px", background: "rgba(255,255,255,.025)" });
            const up = tinyOrderButton("↑", "Move Collection up", index === 0, () => void moveCollection(index, -1));
            const down = tinyOrderButton("↓", "Move Collection down", index === groups.length - 1, () => void moveCollection(index, 1));
            const name = document.createElement("input"); name.type = "text"; name.maxLength = 80; name.value = String(collection.name || "");
            Object.assign(name.style, { minWidth: "0", padding: "7px 8px", borderRadius: "7px", color: "#fff", background: "#09080d", border: `1px solid ${collection.color || accent}66`, fontSize: "10px" });
            const amount = recipeMode ? Number(collection.recipe_count || 0) : promptCollectionCount(collection.collection_id, kind);
            const count = document.createElement("span"); count.textContent = `${amount.toLocaleString()} ${recipeMode ? `recipe${amount === 1 ? "" : "s"}` : `${noun.toLowerCase()}${amount === 1 ? "" : "s"}`}`; Object.assign(count.style, { color: "#aaa2b4", fontSize: "10px", whiteSpace: "nowrap" });
            const save = action("SAVE", accent); Object.assign(save.style, { padding: "6px 8px", fontSize: "8px" });
            save.onclick = async () => {
                const nextName = name.value.trim(); if (!nextName) { alert("Collection name is required."); return; }
                save.disabled = true;
                try { await request(`/${recipeMode ? "collections" : "showcase-collections"}/${encodeURIComponent(collection.collection_id)}`, { method: "PATCH", body: JSON.stringify({ name: nextName }) }); await load(); renderRows(); catalogStatus(`Renamed Collection to ${nextName}.`, accent); }
                catch (error) { alert(error.message || "Could not rename this Collection."); }
                finally { save.disabled = false; }
            };
            const remove = action("DELETE", "#ff4ab8"); Object.assign(remove.style, { padding: "6px 8px", fontSize: "8px" }); remove.title = "Delete Collection only; Library records stay safe";
            remove.onclick = async () => {
                if (!confirm(`Delete Collection “${collection.name}”?\n\nIts memberships are removed, but no ${recipeMode ? "Recipe" : noun}, thumbnail, or source file is deleted.`)) return;
                await request(`/${recipeMode ? "collections" : "showcase-collections"}/${encodeURIComponent(collection.collection_id)}`, { method: "DELETE" });
                if (String(activeCollection) === String(collection.collection_id)) activeCollection = "";
                await load(); await persistCurrentOrder(); renderRows(); catalogStatus(`Deleted Collection ${collection.name}; contents kept.`, "#ff8fce");
            };
            row.append(up, down, name, count, save, remove); list.append(row);
        });
    };
    const createCollection = async () => {
        const name = input.value.trim(); if (!name) return;
        create.disabled = true;
        try {
            await request(recipeMode ? "/collections" : "/showcase-collections", { method: "POST", body: JSON.stringify(recipeMode ? { name } : { kind, name }) }); input.value = ""; await load();
            await persistCurrentOrder(); renderRows(); catalogStatus(`Created ${name}.`, accent);
        } catch (error) { alert(error.message || "Could not create Collection."); }
        finally { create.disabled = false; input.focus(); }
    };
    create.onclick = createCollection; input.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); void createCollection(); } });
    const closeButton = action("DONE", "#35d7ff"); closeButton.onclick = () => overlay.remove();
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", padding: "0 14px 14px" }); footer.append(closeButton);
    body.append(help, createRow, list); card.append(body, footer); renderRows(); input.focus();
}

function promptStructureOrderFromHome(kind) {
    const home = promptHomeUniverse[kind] || promptHomeCounts[kind] || { parents: {}, subcategories: {}, logs: {} };
    const order = { parents: Object.keys(home.parents || {}), subcategories: {}, logs: {} };
    for (const parent of order.parents) {
        order.subcategories[parent] = Object.keys(home.subcategories?.[parent] || {});
        order.logs[parent] = {};
        for (const subcategory of order.subcategories[parent]) order.logs[parent][subcategory] = Object.keys(home.logs?.[parent]?.[subcategory] || {});
    }
    return order;
}

function renamePromptOrderKey(order, oldParent, newParent, oldSubcategory = "", newSubcategory = "") {
    const next = JSON.parse(JSON.stringify(order || {}));
    next.parents = Array.isArray(next.parents) ? next.parents : [];
    next.subcategories = next.subcategories && typeof next.subcategories === "object" ? next.subcategories : {};
    next.logs = next.logs && typeof next.logs === "object" ? next.logs : {};
    if (!oldSubcategory) {
        next.parents = next.parents.map(value => value === oldParent ? newParent : value);
        if (oldParent !== newParent) {
            next.subcategories[newParent] = next.subcategories[oldParent] || [];
            next.logs[newParent] = next.logs[oldParent] || {};
            delete next.subcategories[oldParent]; delete next.logs[oldParent];
        }
        return next;
    }
    const children = Array.isArray(next.subcategories[oldParent]) ? next.subcategories[oldParent] : [];
    next.subcategories[oldParent] = children.filter(value => value !== oldSubcategory);
    if (!Array.isArray(next.subcategories[newParent])) next.subcategories[newParent] = [];
    if (!next.subcategories[newParent].includes(newSubcategory)) next.subcategories[newParent].push(newSubcategory);
    const paths = next.logs?.[oldParent]?.[oldSubcategory] || [];
    if (!next.logs[newParent]) next.logs[newParent] = {};
    const existing = Array.isArray(next.logs[newParent][newSubcategory]) ? next.logs[newParent][newSubcategory] : [];
    next.logs[newParent][newSubcategory] = [...new Set([...existing, ...paths])];
    if (next.logs?.[oldParent] && !(oldParent === newParent && oldSubcategory === newSubcategory)) delete next.logs[oldParent][oldSubcategory];
    return next;
}

function showPromptStructureManager(kind = activePromptKind()) {
    const isTemplate = kind === "template";
    const accent = isTemplate ? "#ff4ab8" : "#35d7ff";
    const noun = isTemplate ? "Template" : "Prompt";
    const { overlay, card } = collectionModal(`${noun.toUpperCase()} LIBRARY STRUCTURE`, "980px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const help = document.createElement("div");
    help.textContent = isTemplate
        ? "Manage the Category → Subcategory → Log structure used by Templates. Rename and move operations update one canonical structure without making TXT copies. DELETE is permanent: it removes the selected folder, contained source TXT files, Template records, and their thumbnails after confirmation."
        : "Manage Prompt Category → Subcategory → Log structure. Rename and move operations update one canonical structure without making TXT copies. DELETE is permanent: it removes the selected folder, contained source TXT files, Prompt records, and their thumbnails after confirmation. Manual order controls the sidebar.";
    Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.5", marginBottom: "10px" }); body.append(help);
    if (!isTemplate) {
        const note = document.createElement("div"); note.textContent = "Moving a Log changes the catalog home of Prompts referenced by that Log. If an exact Prompt is shared by several Logs, its one canonical catalog home moves with it; the other source references stay attached.";
        Object.assign(note.style, { padding: "8px 10px", marginBottom: "12px", borderRadius: "8px", color: "#d8c7ff", background: "rgba(184,154,255,.07)", border: "1px solid #b89aff44", fontSize: "10px", lineHeight: "1.45" }); body.append(note);
    }
    const quick = document.createElement("div"); Object.assign(quick.style, { display: "flex", flexWrap: "wrap", gap: "7px", marginBottom: "10px" });
    const showcases = action(`MANAGE ${noun.toUpperCase()} COLLECTIONS`, isTemplate ? "#ff4ab8" : "#b89aff");
    showcases.onclick = () => showCollectionManager(kind); quick.append(showcases);

    const createPanel = document.createElement("div"); Object.assign(createPanel.style, { display: "grid", gap: "7px", padding: "10px", marginBottom: "12px", border: `1px solid ${accent}33`, borderRadius: "9px", background: "rgba(255,255,255,.018)" });
    const createCategoryRow = document.createElement("div"); Object.assign(createCategoryRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "7px" });
    const createCategoryInput = document.createElement("input"); createCategoryInput.type = "text"; createCategoryInput.maxLength = 80; createCategoryInput.placeholder = `New ${noun} Category`;
    Object.assign(createCategoryInput.style, { minWidth: "0", padding: "8px 9px", borderRadius: "7px", color: "#fff", background: "#09080d", border: "1px solid #48424f" });
    const createCategoryButton = action("＋ CATEGORY", accent); createCategoryRow.append(createCategoryInput, createCategoryButton);
    const createSubRow = document.createElement("div"); Object.assign(createSubRow.style, { display: "grid", gridTemplateColumns: "minmax(150px,.65fr) 1fr auto", gap: "7px" });
    const createSubParent = document.createElement("select"); Object.assign(createSubParent.style, { minWidth: "0", padding: "8px 9px", borderRadius: "7px", color: "#fff", background: "#09080d", border: "1px solid #48424f" });
    const createSubInput = document.createElement("input"); createSubInput.type = "text"; createSubInput.maxLength = 80; createSubInput.placeholder = "New Subcategory"; Object.assign(createSubInput.style, { minWidth: "0", padding: "8px 9px", borderRadius: "7px", color: "#fff", background: "#09080d", border: "1px solid #48424f" });
    const createSubButton = action("＋ SUBCATEGORY", "#b89aff"); createSubRow.append(createSubParent, createSubInput, createSubButton); createPanel.append(createCategoryRow, createSubRow);
    const list = document.createElement("div"); Object.assign(list.style, { display: "grid", gap: "10px" }); body.append(quick, createPanel, list);
    let order = promptStructureOrderFromHome(kind);

    const movePromptScope = async (filters, parent, subcategory) => request("/prompt-assets/bulk", {
        method: "POST",
        body: JSON.stringify({ prompt_ids: [], all_filtered: true, kind, filters: { q: "", source: "", collection: "", rating: "", sort: "newest", placeholders: [], facets: {}, ...filters }, operation: "move", parent, subcategory }),
    });
    const persist = async next => { order = await saveCreativeStructureOrder(kind, next); };
    const reload = async () => { await loadPromptPage(); order = promptStructureOrderFromHome(kind); renderRows(); };
    const createCategory = async () => {
        const name = createCategoryInput.value.trim(); if (!name) return;
        if ((order.parents || []).includes(name)) { alert(`A Category named “${name}” already exists.`); return; }
        const next = JSON.parse(JSON.stringify(order || {}));
        next.parents = Array.isArray(next.parents) ? next.parents : []; next.parents.push(name);
        if (!next.subcategories || typeof next.subcategories !== "object") next.subcategories = {}; if (!next.subcategories[name]) next.subcategories[name] = [];
        if (!next.logs || typeof next.logs !== "object") next.logs = {}; if (!next.logs[name]) next.logs[name] = {};
        await persist(next); createCategoryInput.value = ""; await reload(); catalogStatus(`Created ${noun} Category ${name}.`, accent);
    };
    const createSubcategory = async () => {
        const parent = createSubParent.value; const name = createSubInput.value.trim(); if (!parent || !name) return;
        const children = Array.isArray(order.subcategories?.[parent]) ? order.subcategories[parent] : [];
        if (children.includes(name)) { alert(`A Subcategory named “${name}” already exists under ${parent}.`); return; }
        const next = JSON.parse(JSON.stringify(order || {}));
        if (!next.subcategories || typeof next.subcategories !== "object") next.subcategories = {}; if (!Array.isArray(next.subcategories[parent])) next.subcategories[parent] = []; next.subcategories[parent].push(name);
        if (!next.logs || typeof next.logs !== "object") next.logs = {}; if (!next.logs[parent]) next.logs[parent] = {}; if (!next.logs[parent][name]) next.logs[parent][name] = [];
        await persist(next); createSubInput.value = ""; await reload(); catalogStatus(`Created ${noun} Subcategory ${parent} / ${name}.`, "#b89aff");
    };
    createCategoryButton.onclick = () => void createCategory(); createSubButton.onclick = () => void createSubcategory();
    createCategoryInput.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); void createCategory(); } });
    createSubInput.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); void createSubcategory(); } });
    const moveParent = async (index, direction) => {
        const next = JSON.parse(JSON.stringify(order)); next.parents = reorderedValues(next.parents || [], index, direction); await persist(next); await reload();
    };
    const moveSub = async (parent, index, direction) => {
        const next = JSON.parse(JSON.stringify(order)); next.subcategories[parent] = reorderedValues(next.subcategories?.[parent] || [], index, direction); await persist(next); await reload();
    };
    const moveLogOrder = async (parent, subcategory, index, direction) => {
        const next = JSON.parse(JSON.stringify(order)); if (!next.logs[parent]) next.logs[parent] = {}; next.logs[parent][subcategory] = reorderedValues(next.logs[parent]?.[subcategory] || [], index, direction); await persist(next); await reload();
    };
    const saveParentName = async (parent, nextName) => {
        nextName = nextName.trim(); if (!nextName || nextName === parent) return;
        const home = promptHomeUniverse[kind] || promptHomeCounts[kind] || {};
        if (Object.prototype.hasOwnProperty.call(home.parents || {}, nextName)) { alert(`A Category named “${nextName}” already exists.`); return; }
        const children = Object.keys(home.subcategories?.[parent] || {});
        let changed = 0;
        for (const subcategory of children) { const result = await movePromptScope({ parent, subcategory }, nextName, subcategory); changed += Number(result.changed || 0); }
        await persist(renamePromptOrderKey(order, parent, nextName));
        if (promptParent === parent) promptParent = nextName;
        await reload(); catalogStatus(`Renamed Category ${parent} → ${nextName} · ${changed.toLocaleString()} ${noun.toLowerCase()}s moved.`, accent);
    };
    const saveSubcategory = async (parent, subcategory, nextParent, nextName) => {
        nextName = nextName.trim(); nextParent = nextParent.trim(); if (!nextName || !nextParent) return;
        if (nextParent === parent && nextName === subcategory) return;
        const result = await movePromptScope({ parent, subcategory }, nextParent, nextName);
        await persist(renamePromptOrderKey(order, parent, nextParent, subcategory, nextName));
        if (promptParent === parent && promptSubcategory === subcategory) { promptParent = nextParent; promptSubcategory = nextName; }
        await reload(); catalogStatus(`Moved ${subcategory} → ${nextParent} / ${nextName} · ${Number(result.changed || 0).toLocaleString()} ${noun.toLowerCase()}s.`, accent);
    };
    const deleteParent = async parent => {
        const home = promptHomeUniverse[kind] || promptHomeCounts[kind] || {};
        const count = Number(home.parents?.[parent] || 0);
        if (!confirm(`PERMANENTLY DELETE Category “${parent}”?\n\nThis removes the folder, every source TXT file contained in it, ${count.toLocaleString()} ${noun} record${count === 1 ? "" : "s"}, and thumbnails unique to those records. Mixed TXT logs are canonical files, so records from that same file in the other tab are deleted too.\n\nThis cannot be undone.`)) return;
        const result = await request("/prompt-structure", { method: "DELETE", body: JSON.stringify({ kind, parent }) });
        const next = JSON.parse(JSON.stringify(order)); next.parents = (next.parents || []).filter(value => value !== parent);
        delete next.subcategories[parent]; delete next.logs[parent]; await persist(next);
        if (promptParent === parent) { promptParent = ""; promptSubcategory = ""; promptLogPath = ""; promptLogLabel = ""; }
        const filesDeleted = Number(result.txt_files_deleted || 0) + Number(result.mirror_txt_files_deleted || 0);
        await reload(); catalogStatus(`Deleted Category ${parent} · ${filesDeleted.toLocaleString()} managed TXT file${filesDeleted === 1 ? "" : "s"} · ${Number(result.deleted || 0).toLocaleString()} record${Number(result.deleted || 0) === 1 ? "" : "s"}.`, "#ff6d9d");
    };
    const deleteSubcategory = async (parent, subcategory) => {
        const count = Number((promptHomeUniverse[kind] || promptHomeCounts[kind])?.subcategories?.[parent]?.[subcategory] || 0);
        if (!confirm(`PERMANENTLY DELETE Subcategory “${parent} / ${subcategory}”?\n\nThis removes its source TXT files, ${count.toLocaleString()} ${noun} record${count === 1 ? "" : "s"}, and thumbnails unique to those records. Mixed TXT logs also remove records sourced from that file in the other tab.\n\nThis cannot be undone.`)) return;
        const result = await request("/prompt-structure", { method: "DELETE", body: JSON.stringify({ kind, parent, subcategory }) });
        const next = JSON.parse(JSON.stringify(order));
        next.subcategories[parent] = (next.subcategories?.[parent] || []).filter(value => value !== subcategory);
        if (next.logs?.[parent]) delete next.logs[parent][subcategory];
        await persist(next);
        if (promptParent === parent && promptSubcategory === subcategory) { promptSubcategory = ""; promptLogPath = ""; promptLogLabel = ""; }
        const filesDeleted = Number(result.txt_files_deleted || 0) + Number(result.mirror_txt_files_deleted || 0);
        await reload(); catalogStatus(`Deleted ${parent} / ${subcategory} · ${filesDeleted.toLocaleString()} managed TXT file${filesDeleted === 1 ? "" : "s"} · ${Number(result.deleted || 0).toLocaleString()} record${Number(result.deleted || 0) === 1 ? "" : "s"}.`, "#ff6d9d");
    };
    const renameLog = async (path, label) => {
        const nextLabel = label.trim(); if (!nextLabel) { alert("Log name is required."); return; }
        const result = await request("/prompt-logs/rename", { method: "PATCH", body: JSON.stringify({ source_path: path, label: nextLabel }) });
        if (promptLogPath === path) { promptLogPath = String(result.source_path || path); promptLogLabel = String(result.label || nextLabel); }
        await reload(); catalogStatus(`Renamed Log and its existing TXT file to ${result.label || nextLabel}. No copy was created.`, accent);
    };
    const removeLog = async (parent, subcategory, path, label) => {
        if (!confirm(`PERMANENTLY DELETE Log “${label}”?\n\nThis deletes the source TXT file, every Prompt/Template record sourced by that file, and thumbnails unique to those records.\n\nThis cannot be undone.`)) return;
        const result = await request(`/prompt-logs?source_path=${encodeURIComponent(path)}`, { method: "DELETE" });
        const next = JSON.parse(JSON.stringify(order || {}));
        if (next.logs?.[parent]?.[subcategory]) next.logs[parent][subcategory] = next.logs[parent][subcategory].filter(value => value !== path);
        await persist(next);
        if (promptLogPath === path) { promptLogPath = ""; promptLogLabel = ""; }
        const filesDeleted = Number(result.txt_files_deleted || 0) + Number(result.mirror_txt_files_deleted || 0);
        await reload(); catalogStatus(`Deleted Log ${label} · ${filesDeleted.toLocaleString()} managed TXT file${filesDeleted === 1 ? "" : "s"} · ${Number(result.deleted || 0).toLocaleString()} record${Number(result.deleted || 0) === 1 ? "" : "s"}.`, "#ff6d9d");
    };
    const moveLog = async (parent, subcategory, path, nextParent, nextSubcategory) => {
        if (!nextParent || !nextSubcategory || (nextParent === parent && nextSubcategory === subcategory)) return;
        const result = await movePromptScope({ parent, subcategory, log: path }, nextParent, nextSubcategory);
        const next = JSON.parse(JSON.stringify(order));
        if (!next.logs[parent]) next.logs[parent] = {}; next.logs[parent][subcategory] = (next.logs[parent][subcategory] || []).filter(value => value !== path);
        if (!next.logs[nextParent]) next.logs[nextParent] = {}; if (!next.logs[nextParent][nextSubcategory]) next.logs[nextParent][nextSubcategory] = [];
        if (!next.logs[nextParent][nextSubcategory].includes(path)) next.logs[nextParent][nextSubcategory].push(path);
        await persist(next);
        if (promptLogPath === path) { promptParent = nextParent; promptSubcategory = nextSubcategory; }
        await reload(); catalogStatus(`Moved Log to ${nextParent} / ${nextSubcategory} · ${Number(result.changed || 0).toLocaleString()} canonical Prompts followed.`, accent);
    };

    const fieldStyle = field => Object.assign(field.style, { minWidth: "0", padding: "7px 8px", borderRadius: "7px", color: "#f5f1f7", background: "#09080d", border: "1px solid #48424f", fontSize: "10px" });
    const renderRows = () => {
        list.replaceChildren();
        const home = promptHomeUniverse[kind] || promptHomeCounts[kind] || { parents: {}, subcategories: {}, logs: {} };
        const parents = [...new Set([...(order.parents || []), ...Object.keys(home.parents || {})])];
        const selectedCreateParent = createSubParent.value; createSubParent.replaceChildren();
        for (const parent of parents) { const option = document.createElement("option"); option.value = parent; option.textContent = parent; createSubParent.append(option); }
        if (selectedCreateParent && parents.includes(selectedCreateParent)) createSubParent.value = selectedCreateParent;
        createSubButton.disabled = !parents.length; createSubInput.disabled = !parents.length; createSubParent.disabled = !parents.length;
        if (!parents.length) { const empty = document.createElement("div"); empty.textContent = `No ${noun} Categories exist yet. Import or create content first; its Category and Subcategory will appear here automatically.`; Object.assign(empty.style, { color: "#8f8997", padding: "14px 4px" }); list.append(empty); return; }
        parents.forEach((parent, parentIndex) => {
            const section = document.createElement("section"); Object.assign(section.style, { border: `1px solid ${accent}44`, borderRadius: "10px", overflow: "hidden", background: "rgba(255,255,255,.018)" });
            const parentRow = document.createElement("div"); Object.assign(parentRow.style, { display: "grid", gridTemplateColumns: "auto auto minmax(160px,1fr) auto auto auto", gap: "7px", alignItems: "center", padding: "9px", background: `${accent}0c` });
            const up = tinyOrderButton("↑", "Move Category up", parentIndex === 0, () => void moveParent(parentIndex, -1));
            const down = tinyOrderButton("↓", "Move Category down", parentIndex === parents.length - 1, () => void moveParent(parentIndex, 1));
            const name = document.createElement("input"); name.value = parent; name.maxLength = 80; fieldStyle(name);
            const count = document.createElement("span"); count.textContent = `${Number(home.parents[parent] || 0).toLocaleString()}`; Object.assign(count.style, { color: "#aaa2b4", fontSize: "10px", minWidth: "36px", textAlign: "right" });
            const save = action("SAVE", accent); Object.assign(save.style, { padding: "6px 8px", fontSize: "8px" }); save.onclick = () => void saveParentName(parent, name.value);
            const remove = action("DELETE", "#ff6d9d"); Object.assign(remove.style, { padding: "6px 8px", fontSize: "8px" }); remove.onclick = () => void deleteParent(parent);
            parentRow.append(up, down, name, count, save, remove); section.append(parentRow);

            const children = [...new Set([...(order.subcategories?.[parent] || []), ...Object.keys(home.subcategories?.[parent] || {})])].filter(Boolean);
            children.forEach((subcategory, childIndex) => {
                const childRow = document.createElement("div"); Object.assign(childRow.style, { display: "grid", gridTemplateColumns: "18px auto auto minmax(140px,1fr) minmax(130px,.65fr) auto auto auto", gap: "6px", alignItems: "center", padding: "7px 9px", borderTop: "1px solid #29252d" });
                const arrow = document.createElement("span"); arrow.textContent = "↳"; Object.assign(arrow.style, { color: "#77717e", textAlign: "center" });
                const subUp = tinyOrderButton("↑", "Move Subcategory up", childIndex === 0, () => void moveSub(parent, childIndex, -1));
                const subDown = tinyOrderButton("↓", "Move Subcategory down", childIndex === children.length - 1, () => void moveSub(parent, childIndex, 1));
                const subName = document.createElement("input"); subName.value = subcategory; subName.maxLength = 80; fieldStyle(subName);
                const parentSelect = document.createElement("select"); fieldStyle(parentSelect); for (const candidate of parents) { const option = document.createElement("option"); option.value = candidate; option.textContent = candidate; parentSelect.append(option); } parentSelect.value = parent;
                const childCount = document.createElement("span"); childCount.textContent = Number(home.subcategories[parent][subcategory] || 0).toLocaleString(); Object.assign(childCount.style, { color: "#8f8997", fontSize: "9px", minWidth: "32px", textAlign: "right" });
                const childSave = action("SAVE", "#b89aff"); Object.assign(childSave.style, { padding: "5px 7px", fontSize: "7px" }); childSave.onclick = () => void saveSubcategory(parent, subcategory, parentSelect.value, subName.value);
                const childDelete = action("DELETE", "#ff6d9d"); Object.assign(childDelete.style, { padding: "5px 7px", fontSize: "7px" }); childDelete.onclick = () => void deleteSubcategory(parent, subcategory);
                childRow.append(arrow, subUp, subDown, subName, parentSelect, childCount, childSave, childDelete); section.append(childRow);

                {
                    const logs = home.logs?.[parent]?.[subcategory] || {};
                    const paths = [...new Set([...(order.logs?.[parent]?.[subcategory] || []), ...Object.keys(logs)])].filter(path => Object.prototype.hasOwnProperty.call(logs, path));
                    paths.forEach((path, logIndex) => {
                        const info = logs[path] || {};
                        const logRow = document.createElement("div"); Object.assign(logRow.style, { display: "grid", gridTemplateColumns: "38px auto auto minmax(140px,1fr) minmax(120px,.55fr) minmax(120px,.55fr) auto auto auto", gap: "6px", alignItems: "center", padding: "6px 9px", borderTop: "1px solid #211e26", background: "rgba(53,215,255,.018)" });
                        const marker = document.createElement("span"); marker.textContent = "LOG"; Object.assign(marker.style, { color: "#6d7780", font: "900 7px Segoe UI,Arial", letterSpacing: ".08em", textAlign: "right" });
                        const logUp = tinyOrderButton("↑", "Move Log up", logIndex === 0, () => void moveLogOrder(parent, subcategory, logIndex, -1));
                        const logDown = tinyOrderButton("↓", "Move Log down", logIndex === paths.length - 1, () => void moveLogOrder(parent, subcategory, logIndex, 1));
                        const logName = document.createElement("input"); logName.value = String(info.label || path.split("/").pop()?.replace(/\.txt$/i, "") || "Log"); logName.maxLength = 120; fieldStyle(logName); logName.title = path;
                        const logParent = document.createElement("select"); fieldStyle(logParent); for (const candidate of parents) { const option = document.createElement("option"); option.value = candidate; option.textContent = candidate; logParent.append(option); } logParent.value = parent;
                        const logSub = document.createElement("select"); fieldStyle(logSub);
                        const fillSubs = () => { const current = logSub.value; logSub.replaceChildren(); for (const candidate of Object.keys(home.subcategories?.[logParent.value] || {})) { const option = document.createElement("option"); option.value = candidate; option.textContent = candidate; logSub.append(option); } if ([...logSub.options].some(option => option.value === current)) logSub.value = current; else if (logParent.value === parent && [...logSub.options].some(option => option.value === subcategory)) logSub.value = subcategory; };
                        logParent.onchange = fillSubs; fillSubs();
                        const logSave = action("NAME", accent); Object.assign(logSave.style, { padding: "5px 7px", fontSize: "7px" }); logSave.title = "Rename this Log and move its existing TXT file without copying it"; logSave.onclick = () => void renameLog(path, logName.value);
                        const logMove = action("MOVE", "#63e6a4"); Object.assign(logMove.style, { padding: "5px 7px", fontSize: "7px" }); logMove.onclick = () => void moveLog(parent, subcategory, path, logParent.value, logSub.value);
                        const logRemove = action("DELETE", "#ff6d9d"); Object.assign(logRemove.style, { padding: "5px 7px", fontSize: "7px" }); logRemove.title = "Permanently delete this source TXT file and its catalog records"; logRemove.onclick = () => void removeLog(parent, subcategory, path, String(info.label || logName.value || "Log"));
                        logRow.append(marker, logUp, logDown, logName, logParent, logSub, logSave, logMove, logRemove); section.append(logRow);
                    });
                }
            });
            list.append(section);
        });
    };
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", padding: "0 14px 14px" }); const done = action("DONE", accent); done.onclick = () => overlay.remove(); footer.append(done);
    card.append(body, footer); renderRows();
    // Always reconcile against the current catalog when the manager opens.
    // This makes categories created by the most recent TXT import appear even
    // when the main gallery was still holding an older paginated response.
    void (async () => { await loadPromptPage(); if (!overlay.isConnected) return; order = promptStructureOrderFromHome(kind); renderRows(); })();
}

function showActiveCollectionManager() {
    if (activeView === "recipes") return showPromptStructureManager("template");
    if (activeView === "prompts") return showPromptStructureManager("prompt");
    if (activeView === "outfits") return showComponentCollectionManager("outfit");
    if (activeView === "scenes") return showComponentCollectionManager("scene");
    return showCollectionManager("prompt");
}

function showComponentCollectionManager(kind) {
    if (!["outfit", "scene"].includes(kind)) return;
    return kind === "scene" ? showSceneBiomeManager() : showComponentTaxonomyManager(kind);
}

function showSceneBiomeManager() {
    return showComponentTaxonomyManager("scene");
}

function showComponentTaxonomyManager(kind) {
    const isOutfit = kind === "outfit";
    const singular = isOutfit ? "Outfit Look" : "Scene";
    const plural = isOutfit ? "Outfit Looks" : "Scenes";
    const accent = isOutfit ? "#ff4ab8" : "#63e6a4";
    const { overlay, card } = collectionModal(`${isOutfit ? "OUTFIT LOOK" : "SCENE"} HOMES · CATEGORY → SUBCATEGORY`, "860px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const help = document.createElement("div");
    help.textContent = `${plural} have one canonical Library record, one Home, and one catalog preview. Homes are editable navigation: rename, move, add, delete, or manually reorder them without touching the ${singular} asset. Collections remain separate many-to-many creative sets.`;
    Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.5", marginBottom: "12px" }); body.append(help);

    const controls = document.createElement("div"); Object.assign(controls.style, { display: "grid", gridTemplateColumns: "1fr", gap: "8px", marginBottom: "14px" });
    const categoryRow = document.createElement("div"); Object.assign(categoryRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "8px" });
    const categoryInput = document.createElement("input"); categoryInput.type = "text"; categoryInput.maxLength = 80; categoryInput.placeholder = isOutfit ? "New category, e.g. Festival Wear" : "New category, e.g. Coastal Towns";
    Object.assign(categoryInput.style, { minWidth: "0", padding: "9px 10px", borderRadius: "8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452" });
    const addCategory = action("＋ CATEGORY", accent); categoryRow.append(categoryInput, addCategory);

    const subRow = document.createElement("div"); Object.assign(subRow.style, { display: "grid", gridTemplateColumns: "minmax(160px,.7fr) 1fr auto", gap: "8px" });
    const parentSelect = document.createElement("select"); Object.assign(parentSelect.style, { minWidth: "0", padding: "9px 10px", borderRadius: "8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452" });
    const subInput = document.createElement("input"); subInput.type = "text"; subInput.maxLength = 80; subInput.placeholder = "New subcategory";
    Object.assign(subInput.style, { minWidth: "0", padding: "9px 10px", borderRadius: "8px", color: "#fff", background: "#09080d", border: "1px solid #4a4452" });
    const addSub = action("＋ SUBCATEGORY", "#35d7ff"); subRow.append(parentSelect, subInput, addSub); controls.append(categoryRow, subRow); body.append(controls);

    const list = document.createElement("div"); Object.assign(list.style, { display: "grid", gap: "9px" }); body.append(list);
    const refreshParentSelect = () => {
        const current = parentSelect.value;
        parentSelect.replaceChildren();
        const { parents } = sceneTaxonomyTree(kind);
        for (const parent of parents) { const option = document.createElement("option"); option.value = String(parent.collection_id || ""); option.textContent = parent.name; parentSelect.append(option); }
        if (current && [...parentSelect.options].some(option => option.value === current)) parentSelect.value = current;
        addSub.disabled = !parents.length;
        subInput.disabled = !parents.length;
    };
    const fieldStyle = field => Object.assign(field.style, { minWidth: "0", padding: "7px 8px", borderRadius: "7px", color: "#f5f1f7", background: "#09080d", border: "1px solid #48424f", fontSize: "10px" });
    const sceneFlatOrder = (parents, children) => parents.flatMap(parent => [String(parent.collection_id || ""), ...(children.get(String(parent.collection_id || "")) || []).map(child => String(child.collection_id || ""))]).filter(Boolean);
    const persistSceneOrder = async ids => saveCreativeStructureOrder(kind, { ...await creativeStructureOrder(kind), collections: ids });
    const moveSceneParent = async (index, direction) => {
        const { parents, children } = sceneTaxonomyTree(kind);
        const nextParents = reorderedValues(parents, index, direction);
        await persistSceneOrder(sceneFlatOrder(nextParents, children));
        await load(); renderRows();
    };
    const moveSceneChild = async (parentId, index, direction) => {
        const { parents, children } = sceneTaxonomyTree(kind);
        const key = String(parentId || "");
        children.set(key, reorderedValues(children.get(key) || [], index, direction));
        await persistSceneOrder(sceneFlatOrder(parents, children));
        await load(); renderRows();
    };
    const saveCollection = async (collection, nameField, parentField = null) => {
        const name = nameField.value.trim(); if (!name) { alert("Folder name is required."); return; }
        const payload = { name };
        if (parentField) payload.parent_id = parentField.value;
        try { await request(`/component-collections/${encodeURIComponent(collection.collection_id)}`, { method: "PATCH", body: JSON.stringify(payload) }); await load(); renderRows(); catalogStatus(`Updated ${name}.`, accent); }
        catch (error) { alert(error.message || `Could not update this ${singular} folder.`); }
    };
    const deleteCollection = async collection => {
        const isParent = !String(collection.parent_id || "");
        const scope = componentCollectionScopeIds(kind, collection.collection_id);
        const extra = isParent ? " Its subcategories will also be removed." : "";
        if (!confirm(`Delete ${isParent ? "category" : "subcategory"} “${collection.name}”?${extra} ${singular} cards and thumbnails stay safe; any ${singular} with no remaining memberships moves to Unsorted.`)) return;
        try {
            await request(`/component-collections/${encodeURIComponent(collection.collection_id)}`, { method: "DELETE" });
            if (scope.has(String(activeCollection || ""))) activeCollection = "";
            await load(); renderRows(); catalogStatus(`Deleted folder ${collection.name}; ${singular} assets kept.`, "#ff8fce");
        } catch (error) { alert(error.message || `Could not delete this ${singular} folder.`); }
    };
    const renderRows = () => {
        list.replaceChildren(); refreshParentSelect();
        const { parents, children } = sceneTaxonomyTree(kind);
        if (!parents.length) { const empty = document.createElement("div"); empty.textContent = `No ${singular} categories yet. Create one above; existing ${singular} cards will remain safe in Unsorted.`; Object.assign(empty.style, { color: "#f6e65a", padding: "12px 4px" }); list.append(empty); return; }
        parents.forEach((parent, parentIndex) => {
            const section = document.createElement("section"); Object.assign(section.style, { border: `1px solid ${accent}44`, borderRadius: "9px", overflow: "hidden", background: "rgba(255,255,255,.018)" });
            const parentRow = document.createElement("div"); Object.assign(parentRow.style, { display: "grid", gridTemplateColumns: "auto auto minmax(160px,1fr) auto auto auto", gap: "7px", alignItems: "center", padding: "9px", background: "rgba(99,230,164,.045)" });
            const parentUp = tinyOrderButton("↑", isOutfit ? "Move Outfit Look Category up" : "Move Scene Category up", parentIndex === 0, () => void moveSceneParent(parentIndex, -1));
            const parentDown = tinyOrderButton("↓", isOutfit ? "Move Outfit Look Category down" : "Move Scene Category down", parentIndex === parents.length - 1, () => void moveSceneParent(parentIndex, 1));
            const parentName = document.createElement("input"); parentName.type = "text"; parentName.maxLength = 80; parentName.value = parent.name; fieldStyle(parentName);
            const count = document.createElement("span"); count.textContent = `${parent.asset_count || 0} ${Number(parent.asset_count || 0) === 1 ? singular.toLowerCase() : plural.toLowerCase()}`; Object.assign(count.style, { color: "#9d96a4", fontSize: "9px", whiteSpace: "nowrap" });
            const save = action("SAVE", accent); save.onclick = () => saveCollection(parent, parentName);
            const remove = action("DELETE", "#ff6d9d"); remove.onclick = () => deleteCollection(parent);
            parentRow.append(parentUp, parentDown, parentName, count, save, remove); section.append(parentRow);
            const childRows = children.get(String(parent.collection_id || "")) || [];
            if (!childRows.length) {
                const emptyChild = document.createElement("div"); emptyChild.textContent = "No subcategories"; Object.assign(emptyChild.style, { padding: "8px 12px 9px 28px", color: "#706a76", fontSize: "9px", borderTop: "1px solid #29252d" }); section.append(emptyChild);
            }
            childRows.forEach((child, childIndex) => {
                const childRow = document.createElement("div"); Object.assign(childRow.style, { display: "grid", gridTemplateColumns: "18px auto auto minmax(150px,1fr) minmax(145px,.65fr) auto auto auto", gap: "7px", alignItems: "center", padding: "7px 9px", borderTop: "1px solid #29252d" });
                const arrow = document.createElement("span"); arrow.textContent = "↳"; Object.assign(arrow.style, { color: "#77717e", textAlign: "center" });
                const childUp = tinyOrderButton("↑", isOutfit ? "Move Outfit Look Subcategory up" : "Move Scene Subcategory up", childIndex === 0, () => void moveSceneChild(parent.collection_id, childIndex, -1));
                const childDown = tinyOrderButton("↓", isOutfit ? "Move Outfit Look Subcategory down" : "Move Scene Subcategory down", childIndex === childRows.length - 1, () => void moveSceneChild(parent.collection_id, childIndex, 1));
                const childName = document.createElement("input"); childName.type = "text"; childName.maxLength = 80; childName.value = child.name; fieldStyle(childName);
                const move = document.createElement("select"); fieldStyle(move);
                for (const candidate of parents) { const option = document.createElement("option"); option.value = String(candidate.collection_id || ""); option.textContent = candidate.name; move.append(option); }
                move.value = String(parent.collection_id || ""); move.title = "Parent category";
                const childCount = document.createElement("span"); childCount.textContent = `${child.asset_count || 0}`; Object.assign(childCount.style, { color: "#8f8997", fontSize: "9px", minWidth: "20px", textAlign: "right" });
                const childSave = action("SAVE", "#35d7ff"); childSave.onclick = () => saveCollection(child, childName, move);
                const childDelete = action("DELETE", "#ff6d9d"); childDelete.onclick = () => deleteCollection(child);
                childRow.append(arrow, childUp, childDown, childName, move, childCount, childSave, childDelete); section.append(childRow);
            });
            list.append(section);
        });
    };
    const createCategory = async () => {
        const name = categoryInput.value.trim(); if (!name) return;
        addCategory.disabled = true;
        try { await request("/component-collections", { method: "POST", body: JSON.stringify({ kind, name, parent_id: "" }) }); categoryInput.value = ""; await load(); renderRows(); catalogStatus(`Created ${singular} category ${name}.`, accent); }
        catch (error) { alert(error.message || `Could not create ${singular} category.`); }
        finally { addCategory.disabled = false; categoryInput.focus(); }
    };
    const createSubcategory = async () => {
        const name = subInput.value.trim(); const parentId = parentSelect.value; if (!name || !parentId) return;
        addSub.disabled = true;
        try { await request("/component-collections", { method: "POST", body: JSON.stringify({ kind, name, parent_id: parentId }) }); subInput.value = ""; await load(); renderRows(); catalogStatus(`Created ${singular} subcategory ${name}.`, "#35d7ff"); }
        catch (error) { alert(error.message || `Could not create ${singular} subcategory.`); }
        finally { addSub.disabled = false; subInput.focus(); }
    };
    addCategory.onclick = createCategory; addSub.onclick = createSubcategory;
    categoryInput.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); createCategory(); } });
    subInput.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); createSubcategory(); } });
    const closeButton = action("DONE", accent); closeButton.onclick = () => overlay.remove();
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", padding: "0 14px 14px" }); footer.append(closeButton); card.append(body, footer); renderRows(); categoryInput.focus();
}

async function showComponentCollectionEditor(asset, kind, onSaved = null) {
    if (!["outfit", "scene"].includes(kind) || !asset?.component_id) return;
    const refreshGroups = async () => {
        const response = await request(`/component-collections?kind=${encodeURIComponent(kind)}`);
        componentCollections[kind] = Array.isArray(response?.collections) ? response.collections : [];
    };
    try { await refreshGroups(); } catch (error) {}
    const isOutfit = kind === "outfit";
    const label = isOutfit ? "OUTFIT LOOK" : "SCENE";
    const accent = isOutfit ? "#ff4ab8" : "#63e6a4";
    const { card, close } = collectionModal(isOutfit ? "OUTFIT LOOK HOME" : "SCENE HOME", "620px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const value = document.createElement("div"); value.textContent = String(asset.value || ""); Object.assign(value.style, { marginBottom: "11px", padding: "10px 11px", borderRadius: "8px", border: `1px solid ${accent}55`, color: "#f5f1f7", background: "rgba(255,255,255,.025)", fontSize: "11px", lineHeight: "1.4" }); body.append(value);
    const help = document.createElement("div");
    help.textContent = `Choose the one Home where this ${isOutfit ? "Outfit Look" : "Scene"} lives. Home controls hierarchical browsing; Collections remain separate many-to-many creative sets and Prompt Core pools.`;
    Object.assign(help.style, { color: "#b8b0c1", fontSize: "11px", lineHeight: "1.45", marginBottom: "10px" }); body.append(help);
    let selectedHome = String((asset.collections || [])[0]?.collection_id || "");
    const list = document.createElement("div");
    const redraw = () => {
        list.replaceChildren();
        const groups = componentCollections[kind] || [];
        if (!groups.length) {
            const empty = document.createElement("div"); empty.textContent = `No ${isOutfit ? "Outfit Look" : "Scene"} Homes yet.`; Object.assign(empty.style, { color: "#f6e65a", padding: "8px 0" }); list.append(empty); return;
        }
        const { parents, children } = sceneTaxonomyTree(kind);
        const ordered = [];
        for (const parent of parents) { ordered.push({ collection: parent, depth: 0 }); for (const child of children.get(String(parent.collection_id || "")) || []) ordered.push({ collection: child, depth: 1 }); }
        for (const entry of ordered) {
            const collection = entry.collection;
            const row = document.createElement("label"); Object.assign(row.style, { display: "flex", alignItems: "center", gap: "9px", padding: "9px 10px", paddingLeft: entry.depth ? "26px" : "10px", marginBottom: "6px", border: `1px solid ${collection.color || accent}66`, borderRadius: "8px", cursor: "pointer", background: entry.depth ? "rgba(255,255,255,.012)" : "transparent" });
            const checkbox = document.createElement("input"); checkbox.type = "radio"; checkbox.name = `component-home-${kind}-${asset.component_id}`; checkbox.value = collection.collection_id; checkbox.checked = selectedHome === String(collection.collection_id); checkbox.onchange = () => { if (checkbox.checked) selectedHome = checkbox.value; };
            const dot = document.createElement("span"); Object.assign(dot.style, { width: "9px", height: "9px", borderRadius: "99px", background: collection.color || accent });
            const name = document.createElement("span"); name.textContent = `${entry.depth ? "↳  " : ""}${collection.name} · ${collection.asset_count || 0}`; name.style.flex = "1";
            row.append(checkbox, dot, name); list.append(row);
        }
    };
    if (isOutfit) {
        const createRow = document.createElement("div"); Object.assign(createRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "6px", marginBottom: "10px" });
        const input = document.createElement("input"); input.placeholder = "New Home"; input.maxLength = 80; Object.assign(input.style, { minWidth: "0", padding: "8px", borderRadius: "7px", border: `1px solid ${accent}55`, background: "#09080d", color: "#fff" });
        const create = action("+ CREATE HOME", accent);
        create.onclick = async () => {
            const name = input.value.trim(); if (!name) return;
            create.disabled = true;
            try {
                const response = await request("/component-collections", { method: "POST", body: JSON.stringify({ kind: "outfit", name, parent_id: "" }) });
                const createdId = String(response?.collection?.collection_id || "");
                input.value = ""; await refreshGroups(); if (createdId) selectedHome = createdId; redraw(); catalogStatus(`Created Home ${name}.`, accent);
            } catch (error) { alert(error.message || "Could not create the Home."); }
            finally { create.disabled = false; }
        };
        input.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); create.click(); } });
        createRow.append(input, create); body.append(createRow);
    }
    redraw(); body.append(list);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = close;
    const save = action("MOVE HOME", accent);
    save.onclick = async () => {
        save.disabled = true;
        try {
            const ids = [...list.querySelectorAll('input[type="radio"]:checked')].map(item => item.value);
            if (ids.length !== 1) throw new Error("Choose one Home.");
            const response = await request(`/derived-values/${encodeURIComponent(asset.component_id)}/collections`, { method: "PUT", body: JSON.stringify({ collection_ids: ids }) });
            asset.collections = Array.isArray(response?.collections) ? response.collections : asset.collections;
            await load(); close(); render(); onSaved?.(asset); catalogStatus("Moved Home.", accent);
        } catch (error) { alert(error.message || "Could not move Home."); save.disabled = false; }
    };
    footer.append(cancel, save); card.append(body, footer);
}

function showRecipeCollectionEditor(recipe) {
    const { overlay, card } = collectionModal(`PROMPT COLLECTIONS · ${recipe.name}`);
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto" });
    const help = document.createElement("div"); help.textContent = "Choose the collections for this ready-to-render Prompt. A Prompt can live in more than one collection."; Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.45", marginBottom: "12px" }); body.append(help);
    const selected = recipeCollectionIds(recipe);
    if (!collections.length) { const empty = document.createElement("div"); empty.textContent = "Create a collection first with the Collections button in the Creative Library toolbar."; Object.assign(empty.style, { color: "#f6e65a", padding: "8px 0" }); body.append(empty); }
    else for (const collection of collections) {
        const label = document.createElement("label"); Object.assign(label.style, { display: "flex", alignItems: "center", gap: "9px", padding: "9px 10px", marginBottom: "6px", border: `1px solid ${collection.color || "#b89aff"}66`, borderRadius: "8px", cursor: "pointer" });
        const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.value = collection.collection_id; checkbox.checked = selected.has(collection.collection_id);
        const dot = document.createElement("span"); Object.assign(dot.style, { width: "9px", height: "9px", borderRadius: "99px", background: collection.color || "#b89aff" });
        const name = document.createElement("span"); name.textContent = `${collection.name} · ${collection.recipe_count || 0}`; name.style.flex = "1"; label.append(checkbox, dot, name); body.append(label);
    }
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const save = action("Save collections", "#6ee7a2"); save.onclick = async () => { save.disabled = true; try { const ids = [...body.querySelectorAll("input[type=checkbox]:checked")].map(item => item.value); await request(`/recipes/${encodeURIComponent(recipe.recipe_id)}/collections`, { method: "PUT", body: JSON.stringify({ collection_ids: ids }) }); await load(); catalogStatus(`Updated collections for ${recipe.name}.`); overlay.remove(); } catch (error) { alert(error.message || "Could not update recipe collections."); } finally { save.disabled = false; } };
    footer.append(cancel, save); card.append(body, footer);
}

function cleanPreviewData(data) {
    if (!data || typeof data !== "object" || !String(data.filename || "")) return null;
    return { filename: String(data.filename), type: String(data.type || "temp"), subfolder: String(data.subfolder || "") };
}

function currentStudioPreviewData(preferred = null) {
    const explicit = cleanPreviewData(preferred);
    if (explicit) return explicit;
    const candidates = (app.graph?._nodes || [])
        .filter(node => node.type === PREVIEW_TYPE)
        .map(node => {
            const index = Math.max(0, Number(node.__soFitImageIndex ?? node.properties?.[PREVIEW_INDEX_PROPERTY] ?? 0));
            const live = cleanPreviewData(node.__soFitImageData?.[index]);
            const stored = cleanPreviewData(node.properties?.[PREVIEW_IMAGES_PROPERTY]?.[index]);
            return { data: live || stored, updated: Number(node.properties?.[PREVIEW_UPDATED_PROPERTY] || 0) };
        })
        .filter(item => item.data)
        .sort((a, b) => b.updated - a.updated);
    return candidates[0]?.data || null;
}

function previewOriginalUrl(data) {
    const filename = encodeURIComponent(data?.filename || "");
    const type = encodeURIComponent(data?.type || "temp");
    const subfolder = encodeURIComponent(data?.subfolder || "");
    return api.apiURL(`/view?filename=${filename}&type=${type}&subfolder=${subfolder}${app.getPreviewFormatParam?.() || ""}${app.getRandParam?.() || ""}`);
}

function livePreviewImage(data) {
    const target = cleanPreviewData(data);
    const targetKey = catalogPreviewKey(target);
    if (!targetKey) return null;
    for (const node of app.graph?._nodes || []) {
        if (node.type !== PREVIEW_TYPE) continue;
        const entries = Array.isArray(node.__soFitImageData) ? node.__soFitImageData : [];
        const index = entries.findIndex(entry => catalogPreviewKey(cleanPreviewData(entry)) === targetKey);
        const image = index >= 0 ? node.__soFitImages?.[index] : null;
        if (image?.naturalWidth && image?.naturalHeight) return image;
    }
    return null;
}

async function previewImageBlob(data) {
    const response = await fetch(previewOriginalUrl(data));
    if (response.ok) return response.blob();
    // ComfyUI can clean a temp preview before its image object disappears from
    // Preview Core.  Preserve that visible image instead of surfacing a raw 404.
    const image = livePreviewImage(data);
    if (image) {
        const canvas = document.createElement("canvas");
        canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
        canvas.getContext("2d")?.drawImage(image, 0, 0);
        const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/png"));
        if (blob) return blob;
    }
    throw new Error("Current Preview image is unavailable. Queue it once to refresh Preview Core, then set the thumbnail again.");
}

async function saveRecipeRequest(name, payload, preferredPreview = null) {
    const previewData = currentStudioPreviewData(preferredPreview);
    if (!previewData) return request("/recipes", { method: "POST", body: JSON.stringify({ name, payload }) });
    try {
        const blob = await previewImageBlob(previewData);
        const form = new FormData();
        form.append("name", name);
        form.append("payload", JSON.stringify(payload));
        form.append("file", blob, previewData.filename || "preview.png");
        const response = await fetch(`${API}/save-with-preview`, { method: "POST", body: form });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
        return data;
    } catch (error) {
        console.warn("[Sick Ollie Recipe Catalog] Preview thumbnail verification failed; saving recipe without a thumbnail.", error);
        const result = await request("/recipes", { method: "POST", body: JSON.stringify({ name, payload }) });
        return { ...result, preview_matched: false, preview_reason: error?.message || "Preview verification failed" };
    }
}

function isConnected(node, widget) {
    const input = node.inputs?.find((item) => item.widget?.name === widget.name || item.name === widget.name);
    return input?.link != null || (Array.isArray(input?.links) && input.links.length > 0);
}

function normalizedIndex(value, count) {
    if (!count) return 0;
    const number = Number.isFinite(Number(value)) ? Math.trunc(Number(value)) : 0;
    return ((number % count) + count) % count;
}

function nodeValues(node) {
    return Object.fromEntries((node?.widgets || []).filter(widget => widget.name && widget.serialize !== false).map(widget => [widget.name, widget.value]));
}

function streamLine(node, base, values) {
    const lines = node.__soLogLines?.[base] || [];
    const indexName = base === "prompt" ? "prompt_index" : base === "scene" ? "scene_index" : `outfit_index_${base.slice(-1).toUpperCase()}`;
    const index = normalizedIndex(values[indexName], lines.length);
    return { lines, index, line: String(lines[index] || "") };
}

function tokenPresent(prompt, token, aliases = []) {
    const candidates = [token, ...aliases].filter(Boolean).map(value => String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    return candidates.some(value => new RegExp(`(?<![A-Za-z0-9_])(?:\\{${value}\\}|${value})(?![A-Za-z0-9_])`, "i").test(prompt));
}

function lastExecutedPromptValues(node, source, placeholders) {
    const assembly = node?.__soLastAssembly;
    if (!assembly || typeof assembly !== "object") return null;
    const promptMeta = assembly.prompt && typeof assembly.prompt === "object" ? assembly.prompt : {};
    const sourcePrompt = String(assembly.source_prompt ?? promptMeta.line ?? source.manual_prompt ?? "");
    const values = { prompt_source: "manual", manual_prompt: sourcePrompt };

    if (String(promptMeta.source || "") === "log" && promptMeta.file && promptMeta.file !== "[None]") {
        values.prompt_log_file = String(promptMeta.file);
        values.prompt_mode = "fixed";
        if (promptMeta.index != null && Number.isFinite(Number(promptMeta.index))) values.prompt_index = Number(promptMeta.index);
    }

    for (const [key, letter] of [["outfit_a", "A"], ["outfit_b", "B"], ["outfit_c", "C"]]) {
        const item = assembly[key] && typeof assembly[key] === "object" ? assembly[key] : {};
        if (!item.used) continue;
        const file = String(item.file || source[`outfit_log_file_${letter}`] || "");
        if (!file || file === "[None]") continue;
        values[`outfit_token_${letter}`] = String(item.token || source[`outfit_token_${letter}`] || (letter === "A" ? "OUTFIT" : `OUTFIT_${letter}`));
        values[`outfit_placement_${letter}`] = String(item.placement || source[`outfit_placement_${letter}`] || "token");
        values[`outfit_log_file_${letter}`] = file;
        values[`outfit_mode_${letter}`] = "fixed";
        if (item.index != null && Number.isFinite(Number(item.index))) values[`outfit_index_${letter}`] = Number(item.index);
        if (item.line) placeholders.push({ token: values[`outfit_token_${letter}`], value: String(item.line), widget: `outfit_log_file_${letter}`, source: file });
    }

    const scene = assembly.scene && typeof assembly.scene === "object" ? assembly.scene : {};
    if (scene.used) {
        const file = String(scene.file || source.scene_log_file || "");
        if (file && file !== "[None]") {
            values.scene_token = String(scene.token || source.scene_token || "SCENE");
            values.scene_placement = String(scene.placement || source.scene_placement || "token");
            values.scene_log_file = file;
            values.scene_mode = "fixed";
            if (scene.index != null && Number.isFinite(Number(scene.index))) values.scene_index = Number(scene.index);
            if (scene.line) placeholders.push({ token: values.scene_token, value: String(scene.line), widget: "scene_log_file", source: file });
        }
    }

    for (const [key, tokenField, valueField] of [["name", "name_token", "name_value"], ["item", "item_token", "item_value"]]) {
        const item = assembly[key] && typeof assembly[key] === "object" ? assembly[key] : {};
        if (!item.used || item.value == null || String(item.value).trim() === "") continue;
        values[tokenField] = String(item.token || source[tokenField] || key.toUpperCase());
        values[valueField] = item.value;
        placeholders.push({ token: values[tokenField], value: item.value, widget: valueField });
    }

    for (const key of ["prefix", "suffix"]) {
        const item = assembly[key] && typeof assembly[key] === "object" ? assembly[key] : {};
        if (item.enabled && String(item.text || "").trim()) Object.assign(values, { [`${key}_enabled`]: true, [`${key}_text`]: String(item.text) });
    }
    return values;
}

function captureRecipe() {
    const graphNodes = app.graph?._nodes || [];
    const promptNode = graphNodes.find(node => node.type === "SOPromptLogEngineStudio");
    const generationNode = graphNodes.find(node => node.type === "SOGenerationPipelineStudio");
    const loaderNode = graphNodes.find(node => node.type === "SOLoaderCoreEngineStudio");
    const nodes = [];
    const optionalNodes = [];
    const placeholders = [];

    if (promptNode) {
        const source = nodeValues(promptNode);
        let values = lastExecutedPromptValues(promptNode, source, placeholders);
        if (!values) {
            const promptSelection = streamLine(promptNode, "prompt", source);
            const fromLog = String(source.prompt_source) === "log";
            const usedPrompt = fromLog ? promptSelection.line : String(source.manual_prompt || "");
            values = { prompt_source: "manual", manual_prompt: usedPrompt };
            if (fromLog && source.prompt_log_file && source.prompt_log_file !== "[None]") Object.assign(values, { prompt_log_file: source.prompt_log_file, prompt_mode: "fixed", prompt_index: promptSelection.index });

            for (const letter of ["A", "B", "C"]) {
                const base = `outfit_${letter}`;
                const selection = streamLine(promptNode, base, source);
                const file = source[`outfit_log_file_${letter}`];
                const token = String(source[`outfit_token_${letter}`] || `OUTFIT_${letter}`);
                const placement = String(source[`outfit_placement_${letter}`] || "token");
                const aliases = letter === "A" ? ["OUTFIT", "OUTFIT_A"] : [`OUTFIT_${letter}`];
                const used = file && file !== "[None]" && selection.line && placement !== "off" && (placement !== "token" && placement !== "placeholder" || tokenPresent(usedPrompt, token, aliases));
                if (used) Object.assign(values, { [`outfit_token_${letter}`]: token, [`outfit_placement_${letter}`]: placement, [`outfit_log_file_${letter}`]: file, [`outfit_mode_${letter}`]: "fixed", [`outfit_index_${letter}`]: selection.index });
            }

            const sceneSelection = streamLine(promptNode, "scene", source);
            const sceneToken = String(source.scene_token || "SCENE");
            const scenePlacement = String(source.scene_placement || "token");
            const sceneUsed = source.scene_log_file && source.scene_log_file !== "[None]" && sceneSelection.line && scenePlacement !== "off" && (scenePlacement !== "token" && scenePlacement !== "placeholder" || tokenPresent(usedPrompt, sceneToken));
            if (sceneUsed) Object.assign(values, { scene_token: sceneToken, scene_placement: scenePlacement, scene_log_file: source.scene_log_file, scene_mode: "fixed", scene_index: sceneSelection.index });

            for (const [tokenField, valueField] of [["name_token", "name_value"], ["item_token", "item_value"]]) {
                if (String(source[valueField] ?? "").trim()) {
                    values[tokenField] = source[tokenField]; values[valueField] = source[valueField];
                    placeholders.push({ token: source[tokenField] || tokenField, value: source[valueField], widget: valueField });
                }
            }
            for (const key of ["prefix", "suffix"]) if (source[`${key}_enabled`] && String(source[`${key}_text`] || "").trim()) Object.assign(values, { [`${key}_enabled`]: true, [`${key}_text`]: source[`${key}_text`] });
        }
        nodes.push({ type: promptNode.type, title: "Prompt used", widgets: Object.entries(values).filter(([, value]) => value != null && value !== "").map(([name, value]) => ({ name, value })) });
    }

    if (generationNode) {
        const source = nodeValues(generationNode);
        const seed = Number(source.seed_value) === -1 ? Number(generationNode.__soLastUsedSeed) : Number(source.seed_value);
        const values = { resolution_mode: "custom", custom_width: Number(generationNode.__soLastWidth ?? source.custom_width), custom_height: Number(generationNode.__soLastHeight ?? source.custom_height) };
        if (Number.isInteger(seed) && seed >= 0) values.seed_value = seed;
        nodes.push({ type: generationNode.type, title: "Dimensions & resolved seed", widgets: Object.entries(values).filter(([, value]) => Number.isFinite(value) || typeof value === "string").map(([name, value]) => ({ name, value })) });
        const resources = Object.fromEntries(["clip_name", "clip_type", "clip_device", "vae_name"].filter(name => source[name] != null && source[name] !== "").map(name => [name, source[name]]));
        if (Object.keys(resources).length) optionalNodes.push({ type: generationNode.type, title: "Optional encoder & VAE resources", widgets: Object.entries(resources).map(([name, value]) => ({ name, value })) });
    }

    if (loaderNode) {
        const source = nodeValues(loaderNode);
        const resources = Object.fromEntries(["diffusion_model", "weight_dtype"].filter(name => source[name] != null && source[name] !== "").map(name => [name, source[name]]));
        if (source.main_enabled && source.main_lora && !["None", "[None]", "no_lora"].includes(String(source.main_lora))) Object.assign(resources, { folder_name: source.folder_name, main_enabled: true, main_lora: source.main_lora, main_strength: source.main_strength });
        for (let index = 1; index <= 10; index++) { const value = source[`secondary_lora_${index}`]; if (value?.lora && !["None", "[None]", "no_lora"].includes(String(value.lora))) resources[`secondary_lora_${index}`] = value; }
        if (Object.keys(resources).length) optionalNodes.push({ type: loaderNode.type, title: "Optional model & LoRA resources", widgets: Object.entries(resources).map(([name, value]) => ({ name, value })) });
    }

    const payload = { schema: 4, catalog_focus: "prompt", captured_at: new Date().toISOString(), nodes, optional_nodes: optionalNodes, summary: { placeholders } };
    payload.tokens = recipeTokens(payload); return payload;
}

function displayValue(value) {
    if (value == null || value === "") return "Not set";
    if (typeof value === "boolean") return value ? "On" : "Off";
    if (typeof value === "object") {
        if (Object.prototype.hasOwnProperty.call(value, "lora")) return value.lora ? `${value.on === false ? "Disabled" : "Enabled"} · ${value.lora} · strength ${value.strength ?? 1}` : "Empty LoRA slot";
        return JSON.stringify(value);
    }
    return String(value);
}

function humanField(name) {
    if (FIELD_LABELS[name]) return FIELD_LABELS[name];
    return String(name || "Value").replaceAll("_", " ").replace(/\b\w/g, letter => letter.toUpperCase());
}

function recipeDiff(recipe, includeResources = false) {
    const output = [];
    const savedNodes = [
        ...(recipe.payload?.nodes || []).map(node => ({ ...node, __optional: false })),
        ...(includeResources ? (recipe.payload?.optional_nodes || []).map(node => ({ ...node, __optional: true })) : []),
    ];
    for (const saved of savedNodes) {
        const savedType = TYPE_ALIASES[saved.type] || saved.type;
        const current = (app.graph?._nodes || []).find(node => node.type === savedType);
        if (!current) { output.push({ type: savedType, label: saved.title || "No matching current Studio node", changes: [], missing: true, optional: saved.__optional }); continue; }
        const changes = [];
        const imported = !Array.isArray(saved.widgets) && Array.isArray(saved.widget_values);
        const savedWidgets = imported
            ? saved.widget_values.map((value, index) => ({ name: current.widgets?.filter(widget => widget.name && widget.serialize !== false)[index]?.name, value })).filter(entry => entry.name)
            : (saved.widgets || []);
        for (const entry of savedWidgets) {
            if (!saved.__optional) {
                if (savedType === "SOPromptLogEngineStudio" && !RECIPE_PROMPT_APPLY_FIELDS.has(entry.name)) continue;
                if (savedType === "SOGenerationPipelineStudio" && !RECIPE_GENERATION_APPLY_FIELDS.has(entry.name)) continue;
                if (savedType === "SOLoaderCoreEngineStudio") continue;
            }
            const target = current.widgets?.find(widget => widget.name === entry.name);
            if (!target || JSON.stringify(target.value) === JSON.stringify(entry.value)) continue;
            changes.push({ id: `${savedType}:${saved.__optional ? "optional:" : ""}${entry.name}`, name: entry.name, from: target.value, to: entry.value, connected: isConnected(current, target), checked: !saved.__optional && !SAFETY_DEFAULT_OFF.has(entry.name) });
        }
        output.push({ type: savedType, label: saved.title, node: current, changes, missing: false, imported, optional: saved.__optional });
    }
    return output;
}

function applyRecipe(recipe, selected = null) {
    const diff = recipeDiff(recipe, true); let changed = 0, skipped = 0;
    const promptNode = findStudioNode("SOPromptLogEngineStudio");
    const source = studioWidget(promptNode, "prompt_source");
    if (source && !isConnected(promptNode, source) && source.value !== "manual") { source.value = "manual"; try { source.callback?.("manual"); } catch (error) {} promptNode?.setDirtyCanvas?.(true, true); changed++; }
    for (const entry of diff) for (const change of entry.changes) {
        if (change.connected || (selected && !selected.has(change.id))) { skipped++; continue; }
        const target = entry.node.widgets?.find(widget => widget.name === change.name);
        target.value = change.to; try { target.callback?.(change.to); } catch (error) {}
        entry.node.setDirtyCanvas?.(true, true); changed++;
    }
    return { changed, skipped };
}

function writeComboValues(comboWidget, values) {
    if (!comboWidget) return;
    comboWidget.options = comboWidget.options || {};
    comboWidget.options.values = [...values];
}

function studioWidget(node, name) { return node?.widgets?.find(item => item.name === name); }
function setStudioWidget(node, name, value) { const item = studioWidget(node, name); if (!item) return false; item.value = value; try { item.callback?.(value); } catch (error) {} node.setDirtyCanvas?.(true, true); return true; }
function findStudioNode(type) { return (app.graph?._nodes || []).find(node => node.type === type); }
function findStudioOutputs() { return (app.graph?._nodes || []).filter(node => node.type === OUTPUT_TYPE); }
function captureStudioValues(node, names) { return names.map(name => ({ node, name, value: studioWidget(node, name)?.value })).filter(item => studioWidget(node, item.name)); }
function restoreStudioValues(values) { for (const item of values || []) setStudioWidget(item.node, item.name, item.value); }
function copySecondaryStack(loader) { return (loader?.__soSecondaryWidgets || []).map(item => ({ on: item?.value?.on !== false, lora: item?.value?.lora ?? null, strength: Number(item?.value?.strength ?? 1) })); }
function applySecondaryStack(loader, values, enabledOverride = null) {
    const rows = loader?.__soSecondaryWidgets || [];
    for (let index = 0; index < rows.length; index += 1) {
        const source = values?.[index] || rows[index]?.value || { on: false, lora: null, strength: 1 };
        rows[index].value = { ...source, on: enabledOverride == null ? source.on !== false : Boolean(enabledOverride && source.on !== false) };
    }
    loader?.setDirtyCanvas?.(true, true);
}
function catalogPreviewKey(image) { return `${image?.type || "temp"}/${image?.subfolder || ""}/${image?.filename || ""}`; }
function catalogRunLabel() { return "PREVIEW RUN"; }
function catalogProgress(message = "") {
    const field = root?.querySelector("[data-catalog-run-progress]");
    if (!field) return;
    if (!catalogRun && !message) { field.hidden = true; return; }
    field.hidden = false;
    const done = catalogRun?.index || 0;
    const total = catalogRun?.items?.length || 0;
    const percent = total ? Math.min(100, Math.round(done / total * 100)) : 0;
    field.style.setProperty("--progress", `${percent}%`);
    const current = catalogRun?.items?.[catalogRun.index];
    const failures = Number(catalogRun?.failed || 0);
    const skipped = Number(catalogRun?.skipped || 0);
    const extras = `${failures ? ` · ${failures} failed` : ""}${skipped ? ` · ${skipped} skipped` : ""}`;
    field.textContent = message || `${catalogRunLabel()} · ${done}/${total} processed · ${catalogRun?.captured || 0} captured${extras} · ${current ? `${current.kind.toUpperCase()} · ${current.value}` : "finishing…"}`;
}
function scheduleCatalogRun(run, callback, delay) {
    if (!run || run.stopped || catalogRun !== run) return null;
    const timer = setTimeout(() => { run.timers.delete(timer); if (!run.stopped && catalogRun === run) callback(); }, delay);
    run.timers.add(timer); return timer;
}
function catalogRunTargetMatches(item, targetMode) {
    const hasCatalog = Boolean(String(item?.catalog_preview_ref || item?.preview_ref || ""));
    if (targetMode === "missing") return !hasCatalog;
    if (targetMode === "replace") return hasCatalog;
    if (targetMode === "all") return true;
    return false;
}
function catalogRunTargets(items, targetMode) {
    return (items || []).filter(item => catalogRunTargetMatches(item, targetMode)).map(item => ({ ...item }));
}
function sortLoadedPromptPreviews() {
    if (promptSort !== "preview_newest") return;
    const previewTime = item => {
        const value = item?.preview_updated_at;
        return typeof value === "number" ? value : (Date.parse(String(value || "")) || 0);
    };
    promptAssets.sort((a, b) => {
        const aHasPreview = Boolean(String(a?.preview_ref || ""));
        const bHasPreview = Boolean(String(b?.preview_ref || ""));
        if (aHasPreview !== bHasPreview) return bHasPreview ? 1 : -1;
        return previewTime(b) - previewTime(a)
            || String(a?.value || "").localeCompare(String(b?.value || ""), undefined, { sensitivity: "base" });
    });
}
function promotePromptPreview(item, result = {}) {
    const kind = String(item?.kind || "");
    if (!item?.prompt_id || !["prompt", "template"].includes(kind) || activePromptKind() !== kind || promptSort !== "preview_newest") return false;
    const id = String(item.prompt_id);
    const existing = promptAssets.find(asset => String(asset?.prompt_id || "") === id) || {};
    const promoted = {
        ...item,
        ...existing,
        catalog_preview_ref: String(result.preview_ref || item.catalog_preview_ref || item.preview_ref || ""),
        preview_ref: String(result.preview_ref || item.preview_ref || ""),
        preview_source: String(result.preview_source || item.preview_source || "generated:catalog"),
        preview_updated_at: result.preview_updated_at || item.preview_updated_at || new Date().toISOString(),
        updated_at: result.updated_at || item.updated_at || new Date().toISOString(),
        source_value: String(result.source_prompt_snapshot || item.source_value || existing.source_value || item.value || ""),
        resolved_value: typeof result.resolved_prompt_snapshot === "string" ? result.resolved_prompt_snapshot : String(item.resolved_value || existing.resolved_value || ""),
        preview_metadata: result.preview_metadata && typeof result.preview_metadata === "object"
            ? { ...result.preview_metadata } : (item.preview_metadata || existing.preview_metadata || {}),
        resolved_seed: (() => {
            const candidate = Number(result?.resolved_seed);
            return Number.isInteger(candidate) && candidate >= 0 && candidate <= 1125899906842624
                ? candidate : (item.resolved_seed ?? existing.resolved_seed ?? -1);
        })(),
    };
    promptAssets = [promoted, ...promptAssets.filter(asset => String(asset?.prompt_id || "") !== id)];
    sortLoadedPromptPreviews();
    promptAssets = promptAssets.slice(0, PROMPT_PAGE_SIZE);
    promptPage = 0;
    promptAssetRevision += 1;
    promptViewCache = { key: "", rows: [] };
    return true;
}
function shuffledCatalogItems(items) {
    const values = [...(items || [])];
    for (let index = values.length - 1; index > 0; index -= 1) {
        const other = Math.floor(Math.random() * (index + 1));
        [values[index], values[other]] = [values[other], values[index]];
    }
    return values;
}

function fillCatalogPrompt(template, item) {
    if (["prompt", "template"].includes(String(item?.kind || ""))) return String(item?.value || "").trim();
    const token = item.kind === "scene" ? "SCENE" : "OUTFIT";
    const source = String(template || "").trim();
    if (!source) return "";
    const pattern = new RegExp(`(?<![A-Za-z0-9_])${token}(?![A-Za-z0-9_])`, "gi");
    return pattern.test(source) ? source.replace(pattern, item.value) : `${source} ${item.value}`;
}
function replaceCatalogRunToken(text, candidates, value) {
    let output = String(text || "");
    const replacement = String(value ?? "");
    for (const raw of candidates || []) {
        const token = String(raw || "").trim(); if (!token) continue;
        const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        output = output.replace(new RegExp(`(?<![A-Za-z0-9_])${escaped}(?![A-Za-z0-9_])`, "gi"), () => replacement);
    }
    return output;
}
function resolvePromptYearbookDirectValues(run, text) {
    if (!run?.directPrompt) return String(text || "");
    const nameToken = String(studioWidget(run.prompt, "name_token")?.value || "NAME");
    const itemToken = String(studioWidget(run.prompt, "item_token")?.value || "ITEM");
    let output = replaceCatalogRunToken(text, [nameToken, "NAME"], run.yearbookName || "Tiffany");
    output = replaceCatalogRunToken(output, [itemToken, "ITEM", "BRAND"], run.yearbookItem || "BRAND");
    return output;
}
function setCatalogRunButton(active) {
    for (const button of root?.querySelectorAll("[data-catalog-run], [data-library-yearbook]") || []) {
        button.textContent = active ? "STOP PREVIEW RUN" : "GENERATE PREVIEWS";
        button.style.borderColor = active ? "#ff4ab8" : "#6ee7a299";
        button.style.background = active ? "rgba(255,74,184,.16)" : "rgba(110,231,162,.07)";
    }
    const theaterButton = root?.querySelector("[data-catalog-theater]");
    if (theaterButton) { theaterButton.hidden = !active; theaterButton.disabled = !active; }
}
async function interruptCatalogExecution(run) {
    if (!run || run.interruptRequested) return;
    run.interruptRequested = true;
    try { if (typeof api?.interrupt === "function") await api.interrupt(); else await fetch("/interrupt", { method: "POST" }); }
    catch (error) { console.warn("[Sick Ollie Creative Library] Could not interrupt Preview Run", error); }
}
function restoreCatalogRun(run) {
    if (!run || run.restored) return;
    run.restored = true;
    restoreStudioValues(run.originals);
    applySecondaryStack(run.loader, run.secondaryOriginals, null);
}
function stopCatalogRun(completed = false) {
    if (!catalogRun) return;
    const run = catalogRun;
    run.stopped = true; run.completed = Boolean(completed);
    for (const timer of run.timers) clearTimeout(timer);
    run.timers.clear();
    catalogRun = null;
    window.__soCreativeLibraryRunActive = false;
    recoverTextInputFocus();
    if (!completed && run.queueStarted) void interruptCatalogExecution(run);
    const restore = () => restoreCatalogRun(run);
    if (completed || app.runningNodeId != null || !run.queuePromise) restore(); else Promise.resolve(run.queuePromise).then(restore, restore);
    setCatalogRunButton(false);
    render();
    updateCreativeTheater(run);
    const runLabel = catalogRunLabel(run);
    const failureCopy = Number(run.failed || 0) ? ` · ${Number(run.failed || 0)} failed` : "";
    const skippedCopy = Number(run.skipped || 0) ? ` · ${Number(run.skipped || 0)} skipped` : "";
    catalogProgress(completed ? `${runLabel} COMPLETE · ${run.captured} preview${run.captured === 1 ? "" : "s"} captured${failureCopy}${skippedCopy}.` : `${runLabel} STOPPED · ${run.captured} captured${failureCopy}${skippedCopy}.`);
    catalogStatus(completed ? `${runLabel} complete · ${run.captured} preview${run.captured === 1 ? "" : "s"} captured${failureCopy}${skippedCopy}.` : `${runLabel} stopped · ${run.captured} captured${failureCopy}${skippedCopy}.`, completed ? "#6ee7a2" : "#f6e65a");
    if (completed) void load();
}
async function catalogComfyQueueState() {
    try {
        const response = await fetch(api.apiURL("/queue"), { cache: "no-store" });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(payload?.error || `HTTP ${response.status}`);
        const running = Array.isArray(payload?.queue_running) ? payload.queue_running.length : 0;
        const pending = Array.isArray(payload?.queue_pending) ? payload.queue_pending.length : 0;
        return { ok: true, running, pending, total: running + pending, idle: running + pending === 0 };
    } catch (error) {
        console.warn("[Sick Ollie Creative Library] Could not read ComfyUI queue state", error);
        return { ok: false, running: 0, pending: 0, total: 0, idle: false, error };
    }
}

function catalogPreviewDimensions(run, item) {
    const width = Number(run.promptWidth || 400), height = Number(run.promptHeight || 500);
    if (item.kind === "scene") return { width: Math.max(width, height), height: Math.min(width, height) };
    return { width, height };
}

function prepareCatalogRunCurrent() {
    const run = catalogRun;
    if (!run || run.stopped) return;
    const item = run.items[run.index];
    if (!item) { stopCatalogRun(true); return; }
    const template = item.kind === "scene" ? run.scenePrompt : run.outfitPrompt;
    const promptText = resolvePromptYearbookDirectValues(run, fillCatalogPrompt(template, item));
    if (!promptText) { run.skipped = Number(run.skipped || 0) + 1; run.index += 1; scheduleCatalogRun(run, prepareCatalogRunCurrent, 0); return; }
    setStudioWidget(run.prompt, "manual_prompt", promptText);
    for (const output of run.outputs || []) setStudioWidget(output, "output_root", CREATIVE_YEARBOOK_OUTPUT_ROOT);
    if (run.libraryWide || !run.directPrompt) {
        const dimensions = catalogPreviewDimensions(run, item);
        setStudioWidget(run.generation, "custom_width", dimensions.width);
        setStudioWidget(run.generation, "custom_height", dimensions.height);
    }
    catalogProgress();
    catalogStatus(`${catalogRunLabel(run)} ${run.index + 1}/${run.items.length} · ${item.kind} preview`, item.kind === "scene" ? "#63e6a4" : ["prompt", "template"].includes(String(item.kind || "")) ? "#67e8f9" : "#ff78bd");
    if (!run.autoQueue) return;
    scheduleCatalogRun(run, async () => {
        if (typeof app.queuePrompt !== "function") { catalogProgress("PREVIEW RUN ERROR · Automatic queueing is unavailable in this ComfyUI build."); stopCatalogRun(false); return; }
        const queueState = await catalogComfyQueueState();
        if (!run || run.stopped || catalogRun !== run) return;
        if (!queueState.idle) {
            run.waitingForQueue = true;
            run.queueStarted = false;
            const queueCopy = queueState.ok
                ? `${queueState.running ? `${queueState.running} running` : ""}${queueState.running && queueState.pending ? " · " : ""}${queueState.pending ? `${queueState.pending} pending` : ""}`
                : "queue status unavailable";
            catalogProgress(`${catalogRunLabel(run)} · WAITING FOR COMFYUI QUEUE · ${queueCopy}`);
            catalogStatus("Preview Run is waiting for the existing ComfyUI queue to clear before it claims a thumbnail.", "#f6e65a");
            scheduleCatalogRun(run, prepareCatalogRunCurrent, queueState.ok ? 900 : 1400);
            return;
        }
        run.waitingForQueue = false;
        run.queueStarted = true;
        let queued;
        try { queued = app.queuePrompt(0, 1); }
        catch (error) { run.queueStarted = false; catalogProgress(`PREVIEW RUN ERROR · ${error.message}`); stopCatalogRun(false); return; }
        run.queuePromise = Promise.resolve(queued);
        run.queuePromise.catch(error => { if (!run.stopped && catalogRun === run) { run.queueStarted = false; catalogProgress(`PREVIEW RUN ERROR · ${error.message}`); stopCatalogRun(false); } });
    }, 140);
}
async function saveCatalogPreview(image, item, run = null) {
    const blob = await previewImageBlob(image);
    const form = new FormData();
    if (["prompt", "template"].includes(String(item.kind || ""))) {
        form.append("file", blob, image.filename || "catalog-preview.png");
        form.append("seed_source", "catalog-run");
        form.append("source_prompt_snapshot", String(item.value || ""));
        if (run?.directPrompt) form.append("identity_placeholders", JSON.stringify([
            { token: "NAME", value: run.yearbookName || "Tiffany" },
            { token: "BRAND", value: run.yearbookItem || "BRAND" },
        ]));
        const response = await fetch(`${API}/prompt-assets/${encodeURIComponent(item.prompt_id)}/preview`, { method: "POST", body: form });
        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${response.status}`);
        return payload;
    }
    form.append("kind", item.kind);
    form.append("value", item.value);
    if (item.kind === "piece") { form.append("item_type", String(item.item_type || "piece")); form.append("category", String(item.category || "Uncategorized")); form.append("subtype", String(item.subtype || "")); }
    form.append("file", blob, image.filename || "catalog-preview.png");
    const response = await fetch(`${API}/derived-values/preview`, { method: "POST", body: form });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.ok === false) throw new Error(payload.error || `HTTP ${response.status}`);
    return payload;
}
async function handleCatalogPreviewExecuted(event) {
    if (!catalogRun) return;
    if (event?.detail?.nodeId != null && catalogRun.previewNodeId != null && Number(event.detail.nodeId) !== Number(catalogRun.previewNodeId)) return;
    const run = catalogRun;
    // Automatic Yearbook/Catalog runs may exist while unrelated work is still
    // draining from ComfyUI. Never let those foreign Preview events advance the
    // run or steal a thumbnail slot. The runner only arms capture after it has
    // observed an empty queue and submitted its own single generation.
    if (run.autoQueue && (!run.queueStarted || run.waitingForQueue)) return;
    const image = cleanPreviewData(event?.detail?.previewData);
    const key = catalogPreviewKey(image);
    const now = Date.now();
    if (!image?.filename || !key || (key === lastCatalogPreviewKey && now - lastCatalogPreviewAt < 800)) return;
    lastCatalogPreviewKey = key; lastCatalogPreviewAt = now;
    const item = run.items[run.index];
    if (!item) return;
    try {
        const result = await saveCatalogPreview(image, item, run);
        item.catalog_preview_ref = result.preview_ref || "";
        item.preview_ref = item.catalog_preview_ref;
        item.preview_source = "generated:catalog";
        item.preview_updated_at = result.preview_updated_at || new Date().toISOString();
        item.updated_at = result.updated_at || item.updated_at || item.preview_updated_at;
        const previewSeed = Number(result?.resolved_seed);
        if (Number.isInteger(previewSeed) && previewSeed >= 0 && previewSeed <= 1125899906842624) item.resolved_seed = previewSeed;
        if (result.source_prompt_snapshot) item.source_value = String(result.source_prompt_snapshot);
        if (typeof result.resolved_prompt_snapshot === "string") item.resolved_value = String(result.resolved_prompt_snapshot);
        if (result.preview_metadata && typeof result.preview_metadata === "object") item.preview_metadata = { ...result.preview_metadata };
        if (result?.component?.component_id) item.component_id = String(result.component.component_id);
        if (result?.component?.wardrobe_id) item.wardrobe_id = String(result.component.wardrobe_id);
        const entries = ["prompt", "template"].includes(String(item.kind || "")) ? promptAssets : item.kind === "piece" ? wardrobeItems : item.kind === "outfit" ? (derivedValues.outfits || []) : (derivedValues.scenes || []);
        const itemKind = String(item.kind || "");
        const itemPromptId = String(item.prompt_id || "");
        const itemComponentId = String(item.component_id || "");
        const itemWardrobeId = String(item.wardrobe_id || "");
        const itemValue = String(item.value || "").trim().toLocaleLowerCase();
        const live = entries.find(asset => {
            if (["prompt", "template"].includes(itemKind)) return Boolean(itemPromptId) && String(asset.prompt_id || "") === itemPromptId;
            if (itemKind === "piece") return Boolean(itemWardrobeId) && String(asset.wardrobe_id || "") === itemWardrobeId;
            if (["outfit", "scene"].includes(itemKind)) {
                if (itemComponentId && String(asset.component_id || "") === itemComponentId) return true;
                return Boolean(itemValue) && String(asset.kind || itemKind) === itemKind && String(asset.value || "").trim().toLocaleLowerCase() === itemValue;
            }
            return false;
        });
        if (live) {
            live.catalog_preview_ref = item.catalog_preview_ref; live.preview_ref = item.catalog_preview_ref; live.preview_source = "generated:catalog";
            live.preview_updated_at = result.preview_updated_at || item.preview_updated_at; live.updated_at = result.updated_at || live.updated_at;
            if (Number.isInteger(previewSeed) && previewSeed >= 0 && previewSeed <= 1125899906842624) live.resolved_seed = previewSeed;
            if (result.source_prompt_snapshot) live.source_value = String(result.source_prompt_snapshot);
            if (typeof result.resolved_prompt_snapshot === "string") live.resolved_value = String(result.resolved_prompt_snapshot);
            if (result.preview_metadata && typeof result.preview_metadata === "object") live.preview_metadata = { ...result.preview_metadata };
        }
        if (["prompt", "template"].includes(String(item.kind || ""))) promotePromptPreview(item, result);
        run.captured += 1;
        run.queueStarted = false;
        run.queuePromise = null;
        appendCreativeTheaterEntry(run, item);
        run.index += 1;
        render();
        scheduleCatalogRun(run, prepareCatalogRunCurrent, 120);
    } catch (error) {
        if (run.libraryWide && run.continueOnError) {
            run.failed = Number(run.failed || 0) + 1;
            console.warn(`[Sick Ollie Creative Library] Preview Run skipped ${item.kind}: ${item.value}`, error);
            catalogStatus(`Preview Run skipped one ${item.kind} after a thumbnail save error · continuing.`, "#ff9b5f");
            run.index += 1;
            catalogProgress();
            scheduleCatalogRun(run, prepareCatalogRunCurrent, 180);
            return;
        }
        catalogProgress(`PREVIEW RUN ERROR · ${error.message}`);
        alert(`Catalog preview failed for ${item.value}: ${error.message}`);
        stopCatalogRun(false);
    }
}
function handleCatalogExecutionError(event) {
    const run = catalogRun;
    if (!run?.libraryWide || !run.continueOnError || run.stopped || !run.queueStarted) return;
    const item = run.items?.[run.index];
    if (!item) return;
    run.failed = Number(run.failed || 0) + 1;
    const message = String(event?.detail?.exception_message || event?.detail?.error || event?.detail?.message || "generation error");
    console.warn(`[Sick Ollie Creative Library] Preview Run generation failed for ${item.kind}: ${item.value} · continuing`, message);
    run.index += 1;
    run.queueStarted = false;
    run.queuePromise = null;
    catalogStatus(`Preview Run skipped one ${item.kind} after a generation error · continuing.`, "#ff9b5f");
    catalogProgress();
    scheduleCatalogRun(run, prepareCatalogRunCurrent, 260);
}

function makeSelect(options, current) {
    const select = document.createElement("select");
    Object.assign(select.style, { width: "100%", padding: "9px 10px", borderRadius: "8px", border: "1px solid #4a4452", background: "#09080d", color: "#f5f1f7" });
    for (const [value, label] of options) { const option = document.createElement("option"); option.value = value; option.textContent = label; select.append(option); }
    select.value = current; return select;
}

function previewRunLogOptionLabel(promptNode, widgetName, value) {
    const raw = String(value || "");
    if (!raw) return "No shuffle source";
    const base = widgetName === "scene_log_file" ? "scene"
        : widgetName === "outfit_log_file_B" ? "outfit_B"
            : widgetName === "outfit_log_file_C" ? "outfit_C" : "outfit_A";
    const scope = (promptNode?.__soLogCollections?.[base] || []).find(row => String(row?.reference || "") === raw);
    if (scope) {
        const source = String(scope.source || "") === "wardrobe" ? "Wardrobe" : String(scope.source || "") === "scene" ? "Scenes" : "Looks";
        const noun = String(scope.source || "") === "wardrobe" ? "items" : String(scope.source || "") === "scene" ? "scenes" : "looks";
        return `◆ ${source} · ${String(scope.name || "Collection")} · ${Number(scope.asset_count || 0).toLocaleString()} ${noun}`;
    }
    const match = raw.match(/^\[(Outfit Looks|Wardrobe|Scene) Collection:([^\]]+)\]$/);
    if (match) {
        const source = match[1] === "Outfit Looks" ? "Looks" : match[1] === "Scene" ? "Scenes" : "Wardrobe";
        return `◆ ${source} · Collection`;
    }
    return raw.replace(/^.*\//, "");
}
function showCurrentAssetBuilder() {
    if (activeView === "outfits" && outfitMode === "pieces") return showWardrobeItemBuilder();
    return showAssetBuilder();
}

function showWardrobeItemEditor(item, onSaved = null) {
    if (!item?.wardrobe_id) return;
    const { overlay, card, close } = collectionModal("EDIT WARDROBE ITEM", "680px");
    card.style.borderColor = "#35d7ff99";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "10px" });
    const copy = document.createElement("div"); copy.textContent = "Edit the reusable wardrobe asset itself. Existing Look relationships, ratings, sources, and thumbnail are preserved. If the new text already exists, Studio safely merges the two assets."; Object.assign(copy.style, { color: "#b8b0c1", fontSize: "11px", lineHeight: "1.45" });
    const type = makeSelect([["piece", "Piece"], ["set", "Matching Set"], ["finisher", "Finisher / coverage directive"], ["styling", "Body Styling / body paint"]], String(item.item_type || "piece"));
    const category = makeSelect([], "");
    const subtype = makeSelect([], "");
    const value = document.createElement("textarea"); value.rows = 4; value.value = String(item.value || ""); Object.assign(value.style, { width: "100%", boxSizing: "border-box", resize: "vertical", minHeight: "92px", padding: "11px", borderRadius: "9px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", font: "12px/1.45 Segoe UI,Arial" });
    const setOptions = (select, values, selected) => { select.replaceChildren(); for (const name of values) { const option = document.createElement("option"); option.value = name; option.textContent = name || "General"; select.append(option); } select.value = values.includes(selected) ? selected : (values[0] || ""); };
    const refreshTaxonomy = () => {
        const wantedCategory = category.value || String(item.category || "");
        const wantedSubtype = subtype.value || String(item.subtype || "");
        if (type.value === "finisher") {
            setOptions(category, ["Finishers"], "Finishers"); setOptions(subtype, [""], ""); category.disabled = true; subtype.disabled = true; return;
        }
        if (type.value === "styling") {
            setOptions(category, ["Body Styling"], "Body Styling"); setOptions(subtype, WARDROBE_STYLING_TAXONOMY, wantedSubtype); category.disabled = true; subtype.disabled = false; return;
        }
        category.disabled = false; subtype.disabled = false;
        const categories = Object.keys(WARDROBE_TAXONOMY);
        const selectedCategory = type.value === "set" ? "Matching Sets" : (categories.includes(wantedCategory) ? wantedCategory : "Other");
        setOptions(category, categories, selectedCategory);
        const updateSubtype = () => setOptions(subtype, WARDROBE_TAXONOMY[category.value] || ["Uncategorized"], wantedSubtype);
        category.onchange = updateSubtype; updateSubtype();
    };
    type.onchange = refreshTaxonomy; refreshTaxonomy();
    const flags = Array.isArray(item.review_flags) ? item.review_flags : [];
    if (flags.length) { const warning = document.createElement("div"); warning.textContent = flags.includes("compound") ? "⚠ This Piece appears to contain multiple independently wearable items. Split it into separate Pieces if appropriate." : "⚠ This Piece may be too generic for a stable visual thumbnail. Add identifying detail if the source supports it."; Object.assign(warning.style, { padding: "9px 10px", borderRadius: "8px", border: "1px solid #ff9b5f66", background: "rgba(255,155,95,.07)", color: "#ffc18f", fontSize: "10px", lineHeight: "1.4" }); body.append(copy, warning, type, category, subtype, value); }
    else body.append(copy, type, category, subtype, value);
    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = close;
    const save = action("Save changes", "#35d7ff"); save.onclick = async () => {
        const clean = value.value.trim(); if (!clean) { alert("Wardrobe item text cannot be empty."); return; }
        save.disabled = true;
        try {
            const result = await request(`/wardrobe-items/${encodeURIComponent(item.wardrobe_id)}`, { method: "PATCH", body: JSON.stringify({ item_type: type.value, category: category.value, subtype: subtype.value, value: clean }) });
            if (result?.item) wardrobeBuilder = wardrobeBuilder.map(entry => String(entry.wardrobe_id || "") === String(item.wardrobe_id) ? { ...entry, ...result.item } : entry);
            await load();
            const merged = Boolean(result.merged); catalogStatus(merged ? "Wardrobe item merged with an existing matching asset." : "Wardrobe item updated.", merged ? "#b89aff" : "#35d7ff");
            if (result?.item) Object.assign(item, result.item);
            onSaved?.(item);
            close();
        } catch (error) { alert(error.message || "Could not update this wardrobe item."); } finally { save.disabled = false; }
    };
    foot.append(cancel, save); card.append(body, foot); requestAnimationFrame(() => value.focus());
}

function showWardrobeItemBuilder(prefill = {}) {
    const { overlay, card } = collectionModal("ADD WARDROBE ITEM", "680px");
    card.style.borderColor = "#f6e65a99";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "10px" });
    const copy = document.createElement("div"); copy.textContent = "Add reusable Pieces, coordinated Matching Sets, Builder finishers, or non-visual Body Styling tokens. This does not change any existing Looks."; Object.assign(copy.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.45" });
    const type = makeSelect([["piece", "Piece"], ["set", "Matching Set"], ["finisher", "Finisher / coverage directive"], ["styling", "Body Styling / body paint"]], String(prefill.item_type || "piece"));
    const category = makeSelect([], "");
    const subtype = makeSelect([], "");
    const textarea = document.createElement("textarea"); textarea.rows = 6; textarea.value = String(prefill.value || ""); textarea.placeholder = "One reusable wardrobe value per line…"; Object.assign(textarea.style, { width: "100%", boxSizing: "border-box", resize: "vertical", minHeight: "130px", padding: "11px", borderRadius: "9px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", font: "12px/1.45 Segoe UI,Arial" });
    const refreshTaxonomy = () => {
        const priorCategory = String(prefill.category || category.value || "");
        const priorSubtype = String(prefill.subtype || subtype.value || "");
        category.replaceChildren(); subtype.replaceChildren();
        if (type.value === "finisher") {
            const option = document.createElement("option"); option.value = "Finishers"; option.textContent = "Finishers"; category.append(option); category.value = "Finishers";
            const sub = document.createElement("option"); sub.value = ""; sub.textContent = "General"; subtype.append(sub);
            category.disabled = true; subtype.disabled = true; return;
        }
        if (type.value === "styling") {
            const option = document.createElement("option"); option.value = "Body Styling"; option.textContent = "Body Styling"; category.append(option); category.value = "Body Styling";
            for (const name of WARDROBE_STYLING_TAXONOMY) { const sub = document.createElement("option"); sub.value = name; sub.textContent = name; subtype.append(sub); }
            subtype.value = WARDROBE_STYLING_TAXONOMY.includes(priorSubtype) ? priorSubtype : WARDROBE_STYLING_TAXONOMY[0];
            category.disabled = true; subtype.disabled = false; return;
        }
        category.disabled = false; subtype.disabled = false;
        const categories = Object.keys(WARDROBE_TAXONOMY);
        const forced = type.value === "set" ? "Matching Sets" : (categories.includes(priorCategory) ? priorCategory : "Tops");
        for (const name of categories) { const option = document.createElement("option"); option.value = name; option.textContent = name; category.append(option); }
        category.value = categories.includes(forced) ? forced : categories[0];
        const updateSubtypes = () => {
            const current = category.value; subtype.replaceChildren();
            const values = WARDROBE_TAXONOMY[current] || ["Uncategorized"];
            for (const name of values) { const option = document.createElement("option"); option.value = name; option.textContent = name; subtype.append(option); }
            subtype.value = values.includes(priorSubtype) ? priorSubtype : values[0] || "";
        };
        category.onchange = updateSubtypes; updateSubtypes();
    };
    type.onchange = refreshTaxonomy; refreshTaxonomy();
    const hint = document.createElement("div"); hint.textContent = "Tip: keep a Matching Set together when it is useful as one coordinated choice. Use Pieces for independently swappable garments."; Object.assign(hint.style, { color: "#8f8997", fontSize: "10px", lineHeight: "1.4" });
    body.append(copy, type, category, subtype, textarea, hint);
    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const add = action("Add to Pieces", "#f6e65a"); add.onclick = async () => {
        const values = textarea.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
        if (!values.length) { alert("Add at least one wardrobe value."); return; }
        add.disabled = true;
        try {
            const result = await request("/wardrobe-items", { method: "POST", body: JSON.stringify({ item_type: type.value, category: category.value, subtype: subtype.value, values }) });
            outfitMode = "pieces"; wardrobeCategory = ["finisher", "styling"].includes(type.value) ? "" : category.value; wardrobeSubtype = ["finisher", "styling"].includes(type.value) ? "" : subtype.value; wardrobePage = 0;
            await load(); refreshOutfitModeBar();
            catalogStatus(`Added ${result.added || values.length} wardrobe item${(result.added || values.length) === 1 ? "" : "s"}.`);
            overlay.remove();
        } catch (error) { alert(error.message || "Could not add these wardrobe items."); } finally { add.disabled = false; }
    };
    foot.append(cancel, add); card.append(body, foot); requestAnimationFrame(() => textarea.focus());
}

function showComponentValueEditor(asset, kind, onSaved = null) {
    const { card, close } = collectionModal(`EDIT ${kind === "scene" ? "SCENE" : "OUTFIT LOOK"}`, "720px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "grid", gap: "10px" });
    const value = document.createElement("textarea"); value.value = String(asset.value || ""); value.maxLength = 8000;
    Object.assign(value.style, { width: "100%", boxSizing: "border-box", minHeight: "180px", resize: "vertical", padding: "12px", color: "#fff", background: "#09080d", border: "1px solid #595064", borderRadius: "8px" });
    const note = document.createElement("div"); note.textContent = "Edit this library value. Its category, collections, rating, and thumbnail are kept. Regenerate the thumbnail if the appearance changes."; Object.assign(note.style, { color: "#b8b0c1", font: "11px/1.5 Segoe UI,Arial" });
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", gap: "8px", justifyContent: "flex-end" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = close;
    const save = action("SAVE VALUE", libraryCollectionAccent(kind)); save.onclick = async () => {
        if (!value.value.trim()) return;
        save.disabled = true;
        try {
            const oldId = asset.component_id;
            const result = await request(`/derived-values/${encodeURIComponent(oldId)}`, { method: "PATCH", body: JSON.stringify({ value: value.value }) });
            Object.assign(asset, result.item);
            if (selectedComponentIds.delete(oldId)) selectedComponentIds.add(asset.component_id);
            await refreshLibraryCollectionKind(kind); await load(); close(); onSaved?.(asset); catalogStatus("Library value updated.");
        } catch (error) { alert(error.message || "Could not edit this value."); save.disabled = false; }
    };
    footer.append(cancel, save); body.append(note, value, footer); card.append(body); requestAnimationFrame(() => value.focus());
}

function showAssetBuilder() {
    return showComponentLogImporter(activeView === "scenes" ? "scene" : "outfit", true);
}

function showOutfitLogImporter() { return showComponentLogImporter("outfit"); }

function showComponentLogImporter(kind, building = false) {
    const label = kind === "scene" ? "Scene" : "Outfit";
    const valueLabel = kind === "scene" ? "Scene" : "Look";
    const title = building ? `BUILD ${label.toUpperCase()} ASSETS` : `IMPORT ${label.toUpperCase()} LOG`;
    const accent = libraryCollectionAccent(kind);
    const groups = componentCollections[kind] || [];
    const parents = groups.filter(group => !String(group.parent_id || "")).sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" }));
    const activeGroup = groups.find(group => String(group.collection_id || "") === String(activeCollection || ""));
    const initialParentId = activeGroup ? String(activeGroup.parent_id || activeGroup.collection_id || "") : "";
    const initialParent = groups.find(group => String(group.collection_id || "") === initialParentId);
    const initialSubcategory = activeGroup && String(activeGroup.parent_id || "") ? String(activeGroup.name || "") : "";
    const { overlay, card } = collectionModal(title, "940px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { minHeight: "0", padding: "14px", display: "flex", flexDirection: "column", gap: "12px", overflow: "auto" });
    const intro = document.createElement("div"); intro.textContent = `Select a local .txt ${label} log or paste one value per line. Choose or create a Category, optional Subcategory, and Collection. Exact matches reuse existing assets. Your chosen destination controls placement. The original file stays untouched.`; Object.assign(intro.style, { color: "#bcb4c4", font: "11px/1.52 Segoe UI,Arial" });

    const sourceHead = document.createElement("div"); Object.assign(sourceHead.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "7px" });
    const sourceLabel = document.createElement("strong"); sourceLabel.textContent = `${label.toUpperCase()} VALUES`; Object.assign(sourceLabel.style, { color: accent, font: "900 9px Segoe UI,Arial", letterSpacing: ".11em" });
    const fileButton = action("SELECT .TXT FILE", accent); fileButton.title = "Choose a local plain-text log; the original file stays where it is";
    const fileSummary = document.createElement("span"); Object.assign(fileSummary.style, { color: "#7f7885", font: "9px Segoe UI,Arial" });
    const picker = document.createElement("input"); picker.type = "file"; picker.accept = ".txt,text/plain"; picker.multiple = false; picker.hidden = true;
    sourceHead.append(sourceLabel, fileButton, fileSummary, picker);
    const textarea = document.createElement("textarea"); textarea.placeholder = `Paste one complete ${valueLabel} per line…`; textarea.spellcheck = false; Object.assign(textarea.style, { boxSizing: "border-box", width: "100%", minHeight: "250px", resize: "vertical", padding: "11px 12px", borderRadius: "9px", border: `1px solid ${accent}55`, outline: "none", color: "#f5f1f7", background: "#08070c", font: "11px/1.48 Consolas,monospace" });
    const lineSummary = document.createElement("div"); Object.assign(lineSummary.style, { color: "#8d8693", font: "9px Segoe UI,Arial" });

    const location = document.createElement("section"); Object.assign(location.style, { display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: "9px", padding: "11px", borderRadius: "10px", border: "1px solid #39333e", background: "rgba(255,255,255,.018)" });
    const field = labelText => { const shell = document.createElement("label"); Object.assign(shell.style, { minWidth: "0", display: "flex", flexDirection: "column", gap: "6px" }); const label = document.createElement("span"); label.textContent = labelText; Object.assign(label.style, { color: "#aaa2b4", font: "900 8px Segoe UI,Arial", letterSpacing: ".08em" }); shell.append(label); return shell; };
    const categoryField = field("CATEGORY");
    const category = makeSelect([["", "Choose category…"], ...parents.map(group => [String(group.name || ""), String(group.name || "")]), ["__new__", "＋ New category…"]], String(initialParent?.name || ""));
    const newCategory = document.createElement("input"); newCategory.type = "text"; newCategory.placeholder = "New category name…"; newCategory.hidden = true; categoryField.append(category, newCategory);
    const subcategoryField = field("SUBCATEGORY · OPTIONAL");
    const subcategory = makeSelect([["", "No subcategory · Category only"]], "");
    const newSubcategory = document.createElement("input"); newSubcategory.type = "text"; newSubcategory.placeholder = "New subcategory name…"; newSubcategory.hidden = true; subcategoryField.append(subcategory, newSubcategory);
    const logField = field("LOG NAME");
    const logName = document.createElement("input"); logName.type = "text"; logName.placeholder = kind === "scene" ? "e.g. Flat Backgrounds" : "e.g. Cozy Layers"; if (building) logName.value = `${label} Values`; logField.append(logName);
    const collectionField = field("COLLECTION · OPTIONAL");
    const collection = makeSelect([["", "No Collection"], ...(libraryCollections[kind] || []).map(item => [String(item.collection_id || ""), String(item.name || "Collection")]), ["__new__", "＋ New Collection…"]], "");
    const newCollection = document.createElement("input"); newCollection.type = "text"; newCollection.placeholder = "New collection name…"; newCollection.hidden = true; collectionField.append(collection, newCollection);
    location.append(categoryField, subcategoryField, logField, collectionField);
    for (const input of [newCategory, newSubcategory, logName, newCollection]) Object.assign(input.style, { boxSizing: "border-box", width: "100%", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", outline: "none", color: "#fff", background: "#09080d" });

    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px", padding: "0 14px 14px" });
    const note = document.createElement("span"); note.textContent = "The managed copy keeps the Log name and original line order. Import History can undo newly added values, memberships, folders, the optional collection, and this managed copy without touching your original file."; Object.assign(note.style, { color: "#7f7885", font: "9px/1.4 Segoe UI,Arial" });
    const actions = document.createElement("div"); Object.assign(actions.style, { display: "flex", gap: "8px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const submit = action(title, accent); actions.append(cancel, submit); foot.append(note, actions);

    const resolvedCategory = () => category.value === "__new__" ? newCategory.value.trim() : category.value;
    const resolvedSubcategory = () => subcategory.value === "__new__" ? newSubcategory.value.trim() : subcategory.value;
    const update = () => {
        const lines = textarea.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
        const unique = new Set(lines.map(value => value.replace(/\s+/g, " ").toLocaleLowerCase()));
        lineSummary.textContent = `${lines.length.toLocaleString()} non-empty line${lines.length === 1 ? "" : "s"} · ${unique.size.toLocaleString()} exact unique ${valueLabel}${unique.size === 1 ? "" : "s"}`;
        submit.disabled = !lines.length || !resolvedCategory() || !logName.value.trim() || (subcategory.value === "__new__" && !newSubcategory.value.trim()) || (collection.value === "__new__" && !newCollection.value.trim());
        submit.style.opacity = submit.disabled ? ".42" : "1";
    };
    const refreshSubcategories = () => {
        const parent = parents.find(group => String(group.name || "") === resolvedCategory());
        const values = parent ? groups.filter(group => String(group.parent_id || "") === String(parent.collection_id || "")).map(group => String(group.name || "")).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" })) : [];
        const preferred = parent && String(parent.name || "") === String(initialParent?.name || "") && values.includes(initialSubcategory) ? initialSubcategory : "";
        subcategory.replaceChildren(...[["", "No subcategory · Category only"], ...values.map(value => [value, value]), ["__new__", "＋ New subcategory…"]].map(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; option.selected = value === preferred; return option; }));
        newSubcategory.hidden = true; newSubcategory.value = ""; update();
    };
    category.onchange = () => { newCategory.hidden = category.value !== "__new__"; if (!newCategory.hidden) requestAnimationFrame(() => newCategory.focus()); refreshSubcategories(); };
    subcategory.onchange = () => { newSubcategory.hidden = subcategory.value !== "__new__"; if (!newSubcategory.hidden) requestAnimationFrame(() => newSubcategory.focus()); update(); };
    collection.onchange = () => { newCollection.hidden = collection.value !== "__new__"; if (!newCollection.hidden) requestAnimationFrame(() => newCollection.focus()); update(); };
    textarea.oninput = update; newCategory.oninput = () => { refreshSubcategories(); update(); }; newSubcategory.oninput = update; logName.oninput = update; newCollection.oninput = update;
    fileButton.onclick = () => picker.click();
    picker.onchange = async () => {
        const file = (picker.files || [])[0]; if (!file) return;
        fileButton.disabled = true;
        try { textarea.value = await file.text(); const stem = String(file.name || "").replace(/\.[^.]+$/, "").trim(); if (stem) logName.value = stem; fileSummary.textContent = `${file.name} · local original stays untouched`; update(); }
        catch (error) { alert(error?.message || `Could not read this ${label} text file.`); }
        finally { fileButton.disabled = false; picker.value = ""; }
    };
    submit.onclick = async () => {
        update(); if (submit.disabled) return;
        submit.disabled = true; cancel.disabled = true; submit.textContent = "IMPORTING…";
        try {
            const result = await request("/component-assets/import", { method: "POST", body: JSON.stringify({ text: textarea.value, kind, parent: resolvedCategory(), subcategory: resolvedSubcategory(), log_name: logName.value.trim(), collection_id: collection.value && collection.value !== "__new__" ? collection.value : "", collection_name: collection.value === "__new__" ? newCollection.value.trim() : "" }) });
            activeView = kind === "scene" ? "scenes" : "outfits"; activeLibraryCollection[kind] = ""; activeCollection = String(result.folder_id || ""); componentPage[kind] = 0;
            await refreshLibraryCollectionKind(kind); await load(); overlay.remove();
            const skipped = Number(result.blank || 0) + Number(result.input_duplicates || 0);
            const details = [`${Number(result.values || 0).toLocaleString()} ${valueLabel}s`, `${Number(result.new_values || 0).toLocaleString()} new`, `${Number(result.existing_values || 0).toLocaleString()} existing reused`];
            if (skipped) details.push(`${skipped.toLocaleString()} blank/duplicate skipped`);
            if (result.saved_copy) details.push(`copy saved as ${result.saved_copy}`);
            catalogStatus(`${label} log import complete · ${details.join(" · ")}.`, "#6ee7a2");
        } catch (error) { alert(error?.message || `Could not import this ${label} log.`); submit.disabled = false; cancel.disabled = false; submit.textContent = title; update(); }
    };
    body.append(intro, sourceHead, textarea, lineSummary, location); card.append(body, foot); refreshSubcategories(); update(); requestAnimationFrame(() => textarea.focus());
}

async function showLogImporter(kind = (activeView === "scenes" ? "scene" : "outfit")) {
    if (!["outfit", "scene"].includes(kind)) return;
    return showComponentLogImporter(kind);
}

async function showImportHistory(kind = currentComponentKind()) {
    if (!["outfit", "scene"].includes(kind)) return;
    let data;
    try { data = await request(`/import-batches?kind=${encodeURIComponent(kind)}&limit=30`); }
    catch (error) { alert(error.message || "Could not load import history."); return; }
    const batches = Array.isArray(data?.batches) ? data.batches : [];
    const accent = kind === "outfit" ? "#ff4ab8" : "#63e6a4";
    const { overlay, card } = collectionModal(`${kind === "outfit" ? "OUTFIT" : "SCENE"} IMPORT HISTORY`, "820px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "auto", display: "grid", gap: "8px" });
    const help = document.createElement("div"); help.textContent = "Each log import is tracked as a reversible batch. Undo removes only values and collection memberships that import created; pre-existing shared values stay safe."; Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.45", marginBottom: "4px" }); body.append(help);
    if (!batches.length) {
        const empty = document.createElement("div"); empty.textContent = "No tracked log imports yet. Imports made before this build are still in the Library, but they predate reversible batch history."; Object.assign(empty.style, { padding: "24px 8px", color: "#f6e65a", textAlign: "center" }); body.append(empty);
    }
    for (const batch of batches) {
        const row = document.createElement("section"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "10px", alignItems: "center", padding: "11px", borderRadius: "9px", border: `1px solid ${accent}44`, background: "rgba(255,255,255,.025)" });
        const info = document.createElement("div");
        const title = document.createElement("strong"); const when = new Date(batch.created_at); title.textContent = `${Number(batch.file_count || 0)} log${Number(batch.file_count || 0) === 1 ? "" : "s"} · ${Number(batch.new_count || 0)} new · ${Number(batch.matched_count || 0)} already existed`; Object.assign(title.style, { display: "block", color: "#f5f1f7", fontSize: "11px" });
        const date = document.createElement("div"); date.textContent = Number.isNaN(when.getTime()) ? String(batch.created_at || "") : when.toLocaleString(); Object.assign(date.style, { color: "#817b88", fontSize: "9px", marginTop: "3px" });
        const paths = document.createElement("div"); const sourcePaths = Array.isArray(batch.source_paths) ? batch.source_paths : []; paths.textContent = sourcePaths.slice(0, 3).join(" · ") + (sourcePaths.length > 3 ? ` · +${sourcePaths.length - 3} more` : ""); Object.assign(paths.style, { color: "#a9a1b2", fontSize: "10px", marginTop: "5px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "620px" });
        info.append(title, date, paths);
        const undo = action("UNDO IMPORT", "#ff8fce"); undo.onclick = async () => {
            if (!confirm(`Undo this ${kind} log import? Only assets and collection memberships created by this import will be removed. Shared/pre-existing values remain.`)) return;
            undo.disabled = true;
            try {
                const result = await request(`/import-batches/${encodeURIComponent(batch.batch_id)}/undo`, { method: "POST", body: "{}" });
                await load(); overlay.remove();
                catalogStatus(`Undid import · removed ${result.deleted || 0} asset${Number(result.deleted || 0) === 1 ? "" : "s"} and ${result.memberships_removed || 0} collection membership${Number(result.memberships_removed || 0) === 1 ? "" : "s"}${Number(result.retained || 0) ? ` · ${result.retained} shared value${Number(result.retained) === 1 ? "" : "s"} kept` : ""}.`, "#ffcf75");
            } catch (error) { alert(error.message || "Could not undo this import."); undo.disabled = false; }
        };
        row.append(info, undo); body.append(row);
    }
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", padding: "0 14px 14px" }); const done = action("Done", "#35d7ff"); done.onclick = () => overlay.remove(); footer.append(done); card.append(body, footer);
}

function stageCleanupSelection(ids, message) {
    selectedComponentIds = new Set((ids || []).map(String).filter(Boolean));
    selectionMode = true;
    renderBulkControls(); render();
    catalogStatus(message || `Staged ${selectedComponentIds.size} cleanup candidate${selectedComponentIds.size === 1 ? "" : "s"}.`, "#f6e65a");
}

async function showCleanupReview(kind = currentComponentKind()) {
    if (!["outfit", "scene"].includes(kind)) return;
    let report;
    const scopedIds = derivedEntries(kind).map(item => String(item.component_id || "")).filter(Boolean);
    try { report = await request("/cleanup", { method: "POST", body: JSON.stringify({ kind, component_ids: scopedIds }) }); }
    catch (error) { alert(error.message || "Could not analyze this Library."); return; }

    const accent = kind === "outfit" ? "#ff4ab8" : "#63e6a4";
    const { overlay, card } = collectionModal(`${kind === "outfit" ? "OUTFIT" : "SCENE"} LIBRARY CLEANUP`, "1080px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", overflow: "hidden", display: "flex", flexDirection: "column", gap: "10px", minHeight: "620px" });
    const help = document.createElement("div"); help.textContent = "Review first, stage second. Cleanup never deletes anything by itself. You can mark candidates across many groups/categories, then send the whole batch into normal Library selection for one final look before deleting."; Object.assign(help.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.5" }); body.append(help);

    const groups = Array.isArray(report.near_duplicate_groups) ? report.near_duplicate_groups : [];
    const nearCandidateCount = groups.reduce((sum, group) => sum + Math.max(0, Number((group.items || []).length) - 1), 0);
    const tabs = [
        { id: "near", label: "Near-dupe candidates", count: nearCandidateCount, color: accent },
        { id: "short", label: "Short / fragments", count: (report.short || []).length, color: "#f6e65a" },
        { id: "long", label: "Very long", count: (report.very_long || []).length, color: "#ff9b5f" },
        { id: "prompt", label: "Prompt-like", count: (report.prompt_like || []).length, color: "#b89aff" },
    ];
    let activeTab = tabs[0].count ? "near" : (tabs.find(tab => tab.count)?.id || "near");
    const staged = new Set();
    const keeperByGroup = new Map();
    for (const [index, group] of groups.entries()) {
        const first = (group.items || [])[0];
        if (first?.component_id) keeperByGroup.set(index, String(first.component_id));
    }

    const metrics = document.createElement("div"); Object.assign(metrics.style, { display: "grid", gridTemplateColumns: "repeat(5,minmax(120px,1fr))", gap: "8px" });
    const totalMetric = document.createElement("button"); totalMetric.type = "button"; totalMetric.disabled = true; Object.assign(totalMetric.style, { textAlign: "left", padding: "10px", borderRadius: "9px", border: "1px solid #35d7ff55", background: "#35d7ff0d", color: "inherit" });
    const totalNum = document.createElement("strong"); totalNum.textContent = Number(report.total || 0).toLocaleString(); Object.assign(totalNum.style, { display: "block", color: "#35d7ff", font: "900 20px Segoe UI,Arial" }); const totalLabel = document.createElement("span"); totalLabel.textContent = "IN THIS SCOPE"; Object.assign(totalLabel.style, { color: "#aaa2b4", font: "800 9px Segoe UI,Arial", letterSpacing: ".05em" }); totalMetric.append(totalNum, totalLabel); metrics.append(totalMetric);
    const tabButtons = new Map();
    for (const tab of tabs) {
        const button = document.createElement("button"); button.type = "button"; Object.assign(button.style, { textAlign: "left", padding: "10px", borderRadius: "9px", cursor: tab.count ? "pointer" : "default", border: `1px solid ${tab.color}55`, background: `${tab.color}0d`, color: "inherit", opacity: tab.count ? "1" : ".45" });
        const num = document.createElement("strong"); num.textContent = Number(tab.count || 0).toLocaleString(); Object.assign(num.style, { display: "block", color: tab.color, font: "900 20px Segoe UI,Arial" }); const label = document.createElement("span"); label.textContent = tab.label.toUpperCase(); Object.assign(label.style, { color: "#aaa2b4", font: "800 9px Segoe UI,Arial", letterSpacing: ".05em" }); button.append(num, label); button.disabled = !tab.count; button.onclick = () => { activeTab = tab.id; draw(); }; metrics.append(button); tabButtons.set(tab.id, button);
    }
    body.append(metrics);

    const explanation = document.createElement("div"); Object.assign(explanation.style, { padding: "9px 10px", borderRadius: "8px", background: "rgba(255,255,255,.025)", border: "1px solid #302b36", color: "#a9a1b2", fontSize: "10px", lineHeight: "1.45" }); body.append(explanation);
    const bulk = document.createElement("div"); Object.assign(bulk.style, { display: "flex", gap: "7px", alignItems: "center", flexWrap: "wrap" });
    const selectTab = action("SELECT ALL IN TAB", "#35d7ff"); const clearTab = action("CLEAR TAB", "#8f8997"); const marked = document.createElement("span"); Object.assign(marked.style, { marginLeft: "auto", color: "#f6e65a", font: "800 10px Segoe UI,Arial" }); bulk.append(selectTab, clearTab, marked); body.append(bulk);
    const review = document.createElement("div"); Object.assign(review.style, { flex: "1 1 auto", minHeight: "0", overflow: "auto", display: "flex", flexDirection: "column", gap: "8px", paddingRight: "4px" }); body.append(review);

    const itemRow = (item, reason = "") => {
        const id = String(item.component_id || "");
        const row = document.createElement("label"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "24px 1fr auto", gap: "9px", alignItems: "start", padding: "9px 10px", borderRadius: "8px", border: `1px solid ${staged.has(id) ? accent : "#302b36"}`, background: staged.has(id) ? `${accent}12` : "rgba(255,255,255,.018)", cursor: "pointer" });
        const check = document.createElement("input"); check.type = "checkbox"; check.checked = staged.has(id); check.onchange = () => { if (check.checked) staged.add(id); else staged.delete(id); draw(); };
        const info = document.createElement("div"); const text = document.createElement("div"); text.textContent = String(item.value || ""); Object.assign(text.style, { color: "#eee9f0", fontSize: "11px", lineHeight: "1.4" }); info.append(text);
        if (reason) { const why = document.createElement("div"); why.textContent = reason; Object.assign(why.style, { marginTop: "4px", color: "#8f8997", fontSize: "9px" }); info.append(why); }
        const meta = document.createElement("span"); const rating = Number(item.rating || 0); meta.textContent = `${Number(item.uses || 0)} use${Number(item.uses || 0) === 1 ? "" : "s"}${rating ? ` · ${rating}★` : ""}`; Object.assign(meta.style, { color: rating >= 4 ? "#f6e65a" : "#817b88", fontSize: "9px", whiteSpace: "nowrap" });
        row.append(check, info, meta); return row;
    };

    const candidateIdsForTab = () => {
        if (activeTab === "short") return (report.short || []).map(item => String(item.component_id || "")).filter(Boolean);
        if (activeTab === "long") return (report.very_long || []).map(item => String(item.component_id || "")).filter(Boolean);
        if (activeTab === "prompt") return (report.prompt_like || []).map(item => String(item.component_id || "")).filter(Boolean);
        const ids = [];
        for (const [index, group] of groups.entries()) {
            const keeper = keeperByGroup.get(index) || "";
            for (const item of group.items || []) { const id = String(item.component_id || ""); if (id && id !== keeper) ids.push(id); }
        }
        return ids;
    };

    const draw = () => {
        for (const tab of tabs) { const button = tabButtons.get(tab.id); if (button) { button.style.boxShadow = activeTab === tab.id ? `inset 0 -3px 0 ${tab.color},0 0 0 1px ${tab.color}33` : "none"; button.style.background = activeTab === tab.id ? `${tab.color}20` : `${tab.color}0d`; } }
        review.replaceChildren();
        if (activeTab === "near") {
            explanation.innerHTML = `<b style="color:${accent}">NEAR DUPLICATES</b> found ${groups.length.toLocaleString()} wording group${groups.length === 1 ? "" : "s"} containing ${nearCandidateCount.toLocaleString()} likely extra value${nearCandidateCount === 1 ? "" : "s"}. Pick one keeper per group. You can mark candidates across <b>all groups at once</b>; wording similarity is deterministic, not AI judgment.`;
            if (!groups.length) { const empty = document.createElement("div"); empty.textContent = "No strong deterministic near-duplicate groups were found in this scope."; Object.assign(empty.style, { padding: "28px", textAlign: "center", color: "#8f8997" }); review.append(empty); }
            for (const [groupIndex, group] of groups.slice(0, 250).entries()) {
                const members = Array.isArray(group.items) ? group.items : []; if (members.length < 2) continue;
                const box = document.createElement("section"); Object.assign(box.style, { padding: "10px", borderRadius: "9px", border: `1px solid ${accent}3d`, background: "rgba(255,255,255,.02)" });
                const top = document.createElement("div"); Object.assign(top.style, { display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" });
                const title = document.createElement("strong"); title.textContent = `Group ${groupIndex + 1} · ${members.length} values · ${group.mode || "similar wording"}`; Object.assign(title.style, { flex: "1", color: "#d8d0dc", fontSize: "10px" });
                const markGroup = action("MARK EXTRAS", accent); Object.assign(markGroup.style, { padding: "5px 7px", fontSize: "9px" }); markGroup.onclick = () => { const keeper = keeperByGroup.get(groupIndex) || ""; for (const item of members) { const id = String(item.component_id || ""); if (id && id !== keeper) staged.add(id); else staged.delete(id); } draw(); };
                top.append(title, markGroup); box.append(top);
                const radioName = `cleanup-keeper-${groupIndex}-${Date.now()}`;
                for (const item of members) {
                    const id = String(item.component_id || ""); const row = document.createElement("div"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "92px 26px 1fr auto", gap: "7px", alignItems: "start", padding: "6px 0", borderTop: "1px solid #25212b" });
                    const keeperLabel = document.createElement("label"); Object.assign(keeperLabel.style, { display: "flex", alignItems: "center", gap: "5px", color: keeperByGroup.get(groupIndex) === id ? "#6ee7a2" : "#817b88", font: "800 9px Segoe UI,Arial", cursor: "pointer" }); const radio = document.createElement("input"); radio.type = "radio"; radio.name = radioName; radio.checked = keeperByGroup.get(groupIndex) === id; radio.onchange = () => { if (!radio.checked) return; keeperByGroup.set(groupIndex, id); staged.delete(id); draw(); }; keeperLabel.append(radio, document.createTextNode("KEEP"));
                    const check = document.createElement("input"); check.type = "checkbox"; check.checked = staged.has(id); check.disabled = keeperByGroup.get(groupIndex) === id; check.title = check.disabled ? "Keeper is protected" : "Mark this duplicate candidate"; check.onchange = () => { if (check.checked) staged.add(id); else staged.delete(id); draw(); };
                    const text = document.createElement("div"); text.textContent = String(item.value || ""); Object.assign(text.style, { color: "#eee9f0", fontSize: "11px", lineHeight: "1.35" });
                    const meta = document.createElement("span"); const rating = Number(item.rating || 0); meta.textContent = `${Number(item.uses || 0)} use${Number(item.uses || 0) === 1 ? "" : "s"}${rating ? ` · ${rating}★` : ""}`; Object.assign(meta.style, { color: rating >= 4 ? "#f6e65a" : "#817b88", fontSize: "9px", whiteSpace: "nowrap" });
                    row.append(keeperLabel, check, text, meta); box.append(row);
                }
                review.append(box);
            }
        } else if (activeTab === "short") {
            explanation.innerHTML = `<b style="color:#f6e65a">SHORT / FRAGMENTS</b> are values with two words or fewer, or fewer than 14 characters. These can be perfectly valid simple assets, so this is only a review bucket.`;
            for (const item of report.short || []) review.append(itemRow(item, "Short by deterministic length/word-count rule."));
        } else if (activeTab === "long") {
            explanation.innerHTML = `<b style="color:#ff9b5f">VERY LONG</b> values contain at least 48 words or 280 characters. They may be detailed outfits/scenes, or a full prompt that slipped into the component library.`;
            for (const item of report.very_long || []) review.append(itemRow(item, "Long by deterministic length/word-count rule."));
        } else {
            explanation.innerHTML = `<b style="color:#b89aff">PROMPT-LIKE</b> means the value contains at least two camera, lighting, framing, pose, or photography terms. It does <b>not</b> mean the value is bad. It means “this may be a whole image prompt rather than only a ${kind}.”`;
            for (const item of report.prompt_like || []) review.append(itemRow(item, `Matched prompt markers: ${(item.markers || []).join(", ") || "camera / composition language"}.`));
        }
        const tabIds = new Set(candidateIdsForTab());
        const selectedInTab = [...staged].filter(id => tabIds.has(id)).length;
        marked.textContent = `${staged.size.toLocaleString()} marked total · ${selectedInTab.toLocaleString()} in this tab`;
        selectTab.disabled = !tabIds.size; clearTab.disabled = !selectedInTab;
    };

    selectTab.onclick = () => { for (const id of candidateIdsForTab()) staged.add(id); draw(); };
    clearTab.onclick = () => { for (const id of candidateIdsForTab()) staged.delete(id); draw(); };
    draw();

    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const done = action("Done", "#8f8997"); done.onclick = () => overlay.remove();
    const stage = action("STAGE MARKED", accent); stage.onclick = () => { if (!staged.size) { alert("Mark at least one cleanup candidate first."); return; } stageCleanupSelection([...staged], `Staged ${staged.size} cleanup candidate${staged.size === 1 ? "" : "s"} for final Library review.`); overlay.remove(); };
    footer.append(done, stage); card.append(body, footer);
}

async function openPromptCatalogRunDialog(explicitItems = null) {
    if (catalogRun) { stopCatalogRun(false); return; }
    const explicitScope = Array.isArray(explicitItems) && explicitItems.length > 0;
    if (!explicitScope && promptRunScopeLoading) { catalogStatus("Reading the active Library scope for previews…", "#67e8f9"); return; }
    const loader = findStudioNode("SOLoaderCoreEngineStudio");
    const prompt = findStudioNode("SOPromptLogEngineStudio");
    const generation = findStudioNode("SOGenerationPipelineStudio");
    const preview = findStudioNode(PREVIEW_TYPE);
    const outputs = findStudioOutputs();
    if (!loader || !prompt || !generation || !preview) { alert("Preview Run needs Loader Core, Prompt Core, Generation Core, and Preview Core on the current canvas."); return; }
    if (window.__soYearbookRunActive) { alert("Stop the active LoRA preview run before starting this Creative Library Preview Run."); return; }
    const protectedNames = [[prompt, "prompt_source"], [prompt, "manual_prompt"], [prompt, "prefix_enabled"], [prompt, "suffix_enabled"], [prompt, "outfit_log_file_A"], [prompt, "scene_log_file"], [generation, "batch_size"], [generation, "seed_value"], [generation, "custom_width"], [generation, "custom_height"], ...outputs.map(output => [output, "output_root"])];
    const blocked = protectedNames.find(([node, name]) => { const target = studioWidget(node, name); return target && isConnected(node, target); });
    if (blocked) { alert(`${humanField(blocked[1])} is connected, so Preview Run cannot safely take temporary control of it.`); return; }
    const explicitKind = String(explicitItems?.[0]?.kind || "").toLowerCase();
    const kind = explicitScope && ["prompt", "template"].includes(explicitKind) ? explicitKind : activePromptKind();
    let items = [];
    if (explicitScope) {
        items = explicitItems.map(item => ({ ...item, kind, catalog_preview_ref: String(item.catalog_preview_ref || item.preview_ref || "") }));
    } else {
        promptRunScopeLoading = true;
        catalogStatus("Reading the full active Library scope for previews…", "#67e8f9");
        try {
            items = await fetchPromptYearbookScope(kind);
        } catch (error) {
            alert(error.message || "Could not read the active Library scope for previews.");
            return;
        } finally {
            promptRunScopeLoading = false;
        }
    }
    if (!items.length) { alert(explicitScope ? "No selected records are available for thumbnail regeneration." : "This folder and filter combination has no records to run. Widen the scope first."); return; }

    const modalTitle = explicitScope ? `GENERATE ${items.length.toLocaleString()} ${kind === "template" ? "TEMPLATE" : "PROMPT"} PREVIEW${items.length === 1 ? "" : "S"}` : `GENERATE ${kind === "template" ? "TEMPLATE" : "PROMPT"} PREVIEWS`;
    const { overlay, card } = collectionModal(modalTitle, "800px");
    card.style.borderColor = kind === "template" ? "#ff4ab899" : "#35d7ff99";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "10px", overflow: "auto" });
    const intro = document.createElement("div"); intro.textContent = explicitScope
        ? `${items.length.toLocaleString()} selected ${kind === "template" ? "template" : "prompt"}${items.length === 1 ? "" : "s"} will get fresh generated thumbnails. The catalog text and organization stay unchanged, and your live workflow is restored when the run ends.`
        : `${items.length.toLocaleString()} ${kind === "template" ? "templates" : "prompts"} are in the active filtered scope. This run uses the explicit comparison settings and temporary prompt values below, then restores your live workflow when it ends.`; Object.assign(intro.style, { color: "#bbb3c1", font: "11px/1.5 Segoe UI,Arial" });
    const actionLabel = document.createElement("strong"); actionLabel.textContent = "THUMBNAIL ACTION"; actionLabel.style.color = "#f6e65a";
    const target = makeSelect([], explicitScope ? "all" : "missing");
    const targetHelp = document.createElement("div"); Object.assign(targetHelp.style, { color: "#817b88", font: "9px/1.4 Segoe UI,Arial" });
    const refreshTargets = () => {
        const prior = target.value || (explicitScope ? "all" : "missing");
        const counts = { missing: items.filter(item => catalogRunTargetMatches(item, "missing")).length, replace: items.filter(item => catalogRunTargetMatches(item, "replace")).length, all: items.length };
        target.replaceChildren();
        for (const [value, label] of [["missing", `Fill missing thumbnails · ${counts.missing.toLocaleString()}`], ["replace", `Replace existing thumbnails · ${counts.replace.toLocaleString()}`], ["all", `Rebuild entire scope · ${counts.all.toLocaleString()}`]]) { const option = document.createElement("option"); option.value = value; option.textContent = label; target.append(option); }
        target.value = ["missing", "replace", "all"].includes(prior) ? prior : (explicitScope ? "all" : "missing");
        targetHelp.textContent = "The clean database text and category home never change during a thumbnail run.";
    };
    target.onchange = refreshTargets; refreshTargets();
    const options = document.createElement("div"); Object.assign(options.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "16px" });
    const auto = document.createElement("label"); const autoCheck = document.createElement("input"); autoCheck.type = "checkbox"; autoCheck.checked = true; auto.append(autoCheck, document.createTextNode(" Queue each image automatically"));
    const shuffle = document.createElement("label"); const shuffleCheck = document.createElement("input"); shuffleCheck.type = "checkbox"; shuffleCheck.checked = false; shuffle.append(shuffleCheck, document.createTextNode(" Shuffle run order"));
    const theater = document.createElement("label"); const theaterCheck = document.createElement("input"); theaterCheck.type = "checkbox"; theaterCheck.checked = catalogTheaterEnabledByDefault(); theater.append(theaterCheck, document.createTextNode(" Open Theater Mode · Live"));
    for (const label of [auto, shuffle, theater]) Object.assign(label.style, { color: "#d7d1dc", fontSize: "11px" }); options.append(auto, shuffle, theater);
    const settingsTitle = document.createElement("strong"); settingsTitle.textContent = "COMPARISON SETTINGS"; settingsTitle.style.color = "#67e8f9";
    const comparisonSettings = document.createElement("div"); Object.assign(comparisonSettings.style, { display: "grid", gridTemplateColumns: "minmax(280px,1.25fr) minmax(210px,.85fr)", gap: "10px" });
    const settingCard = (label) => { const wrap = document.createElement("label"); Object.assign(wrap.style, { display: "flex", flexDirection: "column", gap: "7px", padding: "10px", border: "1px solid #39313d", borderRadius: "9px", background: "#0a090e", color: "#d7d1dc", font: "800 10px Segoe UI,Arial" }); const heading = document.createElement("span"); heading.textContent = label; wrap.append(heading); comparisonSettings.append(wrap); return wrap; };
    const inputStyle = { width: "100%", boxSizing: "border-box", padding: "8px 9px", borderRadius: "6px", border: "1px solid #4a4452", background: "#111015", color: "#fff" };
    const dimensionsField = settingCard("Dimensions");
    const dimensionPreset = makeSelect(CATALOG_YEARBOOK_DIMENSION_PRESETS.map(([value, label]) => [value, label]), "800x1000"); Object.assign(dimensionPreset.style, inputStyle);
    const dimensionsRow = document.createElement("div"); Object.assign(dimensionsRow.style, { display: "grid", gridTemplateColumns: "1fr 16px 1fr", alignItems: "center", gap: "6px" });
    const widthValue = document.createElement("input"); widthValue.type = "number"; widthValue.min = "16"; widthValue.max = "16384"; widthValue.step = "8"; widthValue.value = "800"; Object.assign(widthValue.style, inputStyle);
    const by = document.createElement("span"); by.textContent = "×"; by.style.textAlign = "center";
    const heightValue = document.createElement("input"); heightValue.type = "number"; heightValue.min = "16"; heightValue.max = "16384"; heightValue.step = "8"; heightValue.value = "1000"; Object.assign(heightValue.style, inputStyle);
    dimensionsRow.append(widthValue, by, heightValue);
    const dimensionsHint = document.createElement("small"); dimensionsHint.textContent = "Presets fill the exact width × height. Edit either field for Custom. Saved previews: up to 2048 px, compact WebP."; Object.assign(dimensionsHint.style, { color: "#827c88", font: "9px/1.4 Segoe UI,Arial" });
    const applyDimensions = () => { const preset = CATALOG_YEARBOOK_DIMENSION_PRESETS.find(([value]) => value === dimensionPreset.value); if (preset && preset[0] !== "custom") { widthValue.value = String(preset[2]); heightValue.value = String(preset[3]); } };
    const markCustomDimensions = () => { const preset = CATALOG_YEARBOOK_DIMENSION_PRESETS.find(([, , width, height]) => width === Number(widthValue.value) && height === Number(heightValue.value)); dimensionPreset.value = preset ? preset[0] : "custom"; };
    dimensionPreset.onchange = applyDimensions; widthValue.oninput = markCustomDimensions; heightValue.oninput = markCustomDimensions;
    dimensionsField.append(dimensionPreset, dimensionsRow, dimensionsHint);
    const seedField = settingCard("Seed");
    const seedValue = document.createElement("input"); seedValue.type = "number"; seedValue.min = "-1"; seedValue.max = "1125899906842624"; seedValue.step = "1"; seedValue.value = "4815162342"; Object.assign(seedValue.style, inputStyle);
    const seedHint = document.createElement("small"); seedHint.textContent = "Fixed seed keeps images directly comparable. −1 = random."; Object.assign(seedHint.style, { color: "#827c88", font: "9px/1.4 Segoe UI,Arial" }); seedField.append(seedValue, seedHint);
    const overrideTitle = document.createElement("strong"); overrideTitle.textContent = "PROMPT VALUES · TEMPORARY"; overrideTitle.style.color = kind === "template" ? "#ff8fce" : "#67e8f9";
    const overrides = document.createElement("div"); Object.assign(overrides.style, { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(180px,1fr))", gap: "8px", padding: "10px", border: "1px solid #39313d", borderRadius: "9px", background: "#0a090e" });
    const runField = (label, value, type = "text") => { const wrap = document.createElement("label"); wrap.textContent = label; Object.assign(wrap.style, { display: "flex", flexDirection: "column", gap: "4px", color: "#b8b0c1", font: "800 8px Segoe UI,Arial", letterSpacing: ".06em" }); const input = document.createElement("input"); input.type = type; input.value = value; Object.assign(input.style, inputStyle); wrap.append(input); overrides.append(wrap); return input; };
    const nameValue = runField("NAME", "Tiffany"); const brandValue = runField("BRAND / ITEM", "BRAND");
    const logField = (label, widgetName) => { const wrap = document.createElement("label"); wrap.textContent = label; Object.assign(wrap.style, { display: "flex", flexDirection: "column", gap: "4px", color: "#b8b0c1", font: "800 8px Segoe UI,Arial", letterSpacing: ".06em" }); const values = (studioWidget(prompt, widgetName)?.options?.values || []).filter(value => value && value !== "[None]"); const select = makeSelect([["", "No shuffle source"], ...values.map(value => [value, previewRunLogOptionLabel(prompt, widgetName, value)])], values[0] || ""); Object.assign(select.style, inputStyle); wrap.append(select); overrides.append(wrap); return select; };
    const outfitLog = logField("OUTFIT LOG · SHUFFLE", "outfit_log_file_A"); const sceneLog = logField("SCENE LOG · SHUFFLE", "scene_log_file");
    const overrideNote = document.createElement("div"); overrideNote.textContent = `NAME and BRAND / ITEM are pre-resolved inside each temporary preview prompt. Generated files are kept under output/${CREATIVE_YEARBOOK_OUTPUT_ROOT}; your original Output Core folder returns when the run ends.`; Object.assign(overrideNote.style, { gridColumn: "1 / -1", color: "#827c88", font: "9px/1.4 Segoe UI,Arial" }); overrides.append(overrideNote);
    body.append(intro, settingsTitle, comparisonSettings, overrideTitle, overrides, actionLabel, target, targetHelp, options);
    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const start = action(explicitScope ? `Regenerate ${items.length === 1 ? "thumbnail" : "thumbnails"}` : "Start yearbook run", kind === "template" ? "#ff4ab8" : "#35d7ff"); start.onclick = () => {
        let selected = catalogRunTargets(items, target.value);
        if (!selected.length) { alert(target.value === "missing" ? "Every record in this filtered scope already has a thumbnail." : "No records match that thumbnail action in this filtered scope."); return; }
        const width = Math.round(Number(widthValue.value));
        const height = Math.round(Number(heightValue.value));
        const seed = Math.trunc(Number(seedValue.value));
        if (!Number.isFinite(width) || width < 16 || width > 16384 || !Number.isFinite(height) || height > 16384 || height < 16) { alert("Preview width and height must each be between 16 and 16384 pixels."); return; }
        if (!Number.isFinite(seed) || seed < -1 || seed > 1125899906842624) { alert("Seed must be −1 for random or a whole number from 0 to 1125899906842624."); return; }
        if (shuffleCheck.checked) selected = shuffledCatalogItems(selected);
        const originals = [
            ...captureStudioValues(prompt, ["prompt_source", "manual_prompt", "prefix_enabled", "suffix_enabled", "outfit_log_file_A", "outfit_mode_A", "scene_log_file", "scene_mode"]),
            ...captureStudioValues(generation, ["resolution_mode", "custom_width", "custom_height", "seed_value", "batch_size"]),
            ...outputs.flatMap(output => captureStudioValues(output, ["output_root"])),
        ];
        const secondaryOriginals = copySecondaryStack(loader);
        setStudioWidget(prompt, "prompt_source", "manual"); setStudioWidget(prompt, "prefix_enabled", false); setStudioWidget(prompt, "suffix_enabled", false);
        if (outfitLog.value) { setStudioWidget(prompt, "outfit_log_file_A", outfitLog.value); setStudioWidget(prompt, "outfit_mode_A", "randomize"); }
        if (sceneLog.value) { setStudioWidget(prompt, "scene_log_file", sceneLog.value); setStudioWidget(prompt, "scene_mode", "randomize"); }
        setStudioWidget(generation, "resolution_mode", "custom"); setStudioWidget(generation, "custom_width", width); setStudioWidget(generation, "custom_height", height); setStudioWidget(generation, "seed_value", seed); setStudioWidget(generation, "batch_size", 1);
        for (const output of outputs) setStudioWidget(output, "output_root", CREATIVE_YEARBOOK_OUTPUT_ROOT);
        localStorage.setItem(CATALOG_THEATER_ENABLED_KEY, theaterCheck.checked ? "true" : "false");
        catalogRun = { runId: ++catalogRunSerial, items: selected, index: 0, captured: 0, loader, prompt, generation, outputs, previewNodeId: preview.id, originals, secondaryOriginals, outfitPrompt: "", scenePrompt: "", yearbookName: nameValue.value.trim() || "Tiffany", yearbookItem: brandValue.value.trim() || "BRAND", autoQueue: autoCheck.checked, targetMode: target.value, locationMode: explicitScope ? "selected" : "filtered-scope", directPrompt: true, theaterEnabled: theaterCheck.checked, theater: theaterCheck.checked ? { entries: [], cursor: -1, live: true, sizeMode: catalogTheaterInitialSize(), overlay: null, ui: null } : null, timers: new Set(), stopped: false, completed: false, restored: false, queueStarted: false, queuePromise: null, waitingForQueue: false, interruptRequested: false };
        window.__soCreativeLibraryRunActive = true;
        promptSort = "preview_newest"; promptPage = 0;
        overlay.remove(); setCatalogRunButton(true); render(); queuePromptPageLoad(); catalogProgress(); if (catalogRun.theaterEnabled) openCreativeTheater(catalogRun); scheduleCatalogRun(catalogRun, prepareCatalogRunCurrent, 160);
    };
    foot.append(cancel, start); card.append(body, foot);
}

async function openWholeLibraryYearbookDialog() {
    if (catalogRun) { stopCatalogRun(false); return; }
    if (window.__soYearbookRunActive) { alert("Stop the active LoRA preview run before starting a Creative Library Preview Run."); return; }
    const loader = findStudioNode("SOLoaderCoreEngineStudio");
    const prompt = findStudioNode("SOPromptLogEngineStudio");
    const generation = findStudioNode("SOGenerationPipelineStudio");
    const preview = findStudioNode(PREVIEW_TYPE);
    const outputs = findStudioOutputs();
    if (!loader || !prompt || !generation || !preview) { alert("Preview Run needs Loader Core, Prompt Core, Generation Core, and Preview Core on the current canvas."); return; }
    const protectedNames = [
        [prompt, "prompt_source"], [prompt, "manual_prompt"], [prompt, "prefix_enabled"], [prompt, "suffix_enabled"],
        [prompt, "outfit_log_file_A"], [prompt, "scene_log_file"], [generation, "resolution_mode"],
        [generation, "custom_width"], [generation, "custom_height"], [generation, "batch_size"], [generation, "seed_value"],
        ...outputs.map(output => [output, "output_root"]),
    ];
    const blocked = protectedNames.find(([node, name]) => { const target = studioWidget(node, name); return target && isConnected(node, target); });
    if (blocked) { alert(`${humanField(blocked[1])} is connected, so Preview Run cannot safely take temporary control of it.`); return; }

    catalogStatus("Scanning the Creative Library for preview coverage…", "#6ee7a2");
    let inventory;
    try { inventory = await fetchWholeLibraryYearbookInventory(); }
    catch (error) { alert(error.message || "Could not scan the complete Creative Library."); return; }

    const groups = [
        { key: "templates", label: "Templates", color: "#ff4ab8", rows: inventory.templates || [] },
        { key: "prompts", label: "Prompts", color: "#35d7ff", rows: inventory.prompts || [] },
        { key: "outfits", label: "Outfit Looks", color: "#f6e65a", rows: inventory.outfits || [] },
        { key: "pieces", label: "Wardrobe", color: "#f6e65a", rows: inventory.pieces || [] },
        { key: "scenes", label: "Scenes", color: "#63e6a4", rows: inventory.scenes || [] },
    ].map(group => ({ ...group, missing: catalogRunTargets(group.rows, "missing").length }));
    const totalAssets = groups.reduce((sum, group) => sum + group.rows.length, 0);
    const totalMissing = groups.reduce((sum, group) => sum + group.missing, 0);
    if (!totalAssets) { alert("Creative Library does not contain any preview-capable assets yet."); return; }

    const { overlay, card } = collectionModal("GENERATE PREVIEWS · LIBRARY SECTIONS", "940px");
    card.style.borderColor = "#6ee7a299";
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "11px", overflow: "auto" });
    const intro = document.createElement("div"); intro.innerHTML = `<b style="color:#6ee7a2">ONE RUN FOR THE WHOLE LIBRARY.</b> It found <b>${totalMissing.toLocaleString()}</b> missing thumbnail${totalMissing === 1 ? "" : "s"} across ${totalAssets.toLocaleString()} total assets. The runner submits one generation at a time, waits for its Preview thumbnail to be captured, then advances automatically. Keep ComfyUI, this browser tab, and the computer awake while you are away.`; Object.assign(intro.style, { color: "#bbb3c1", font: "11px/1.55 Segoe UI,Arial", padding: "11px", border: "1px solid #31463c", borderRadius: "9px", background: "rgba(110,231,162,.045)" });

    const scopeTitle = document.createElement("strong"); scopeTitle.textContent = "LIBRARIES TO FILL · MISSING THUMBNAILS ONLY"; scopeTitle.style.color = "#6ee7a2";
    const scopeGrid = document.createElement("div"); Object.assign(scopeGrid.style, { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(160px,1fr))", gap: "8px" });
    const groupChecks = new Map();
    for (const group of groups) {
        const label = document.createElement("label"); Object.assign(label.style, { display: "grid", gridTemplateColumns: "22px 1fr", gap: "7px", alignItems: "center", padding: "9px", border: `1px solid ${group.color}55`, borderRadius: "8px", background: "rgba(255,255,255,.018)", cursor: group.missing ? "pointer" : "default" });
        const check = document.createElement("input"); check.type = "checkbox"; check.checked = group.missing > 0; check.disabled = !group.missing; groupChecks.set(group.key, check);
        const copy = document.createElement("span"); copy.innerHTML = `<b style="color:${group.color}">${group.label}</b><br><small style="color:#8f8997">${group.missing.toLocaleString()} missing · ${group.rows.length.toLocaleString()} total</small>`;
        label.append(check, copy); scopeGrid.append(label);
    }

    const inputStyle = { width: "100%", boxSizing: "border-box", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", font: "11px Segoe UI,Arial" };
    const settingsTitle = document.createElement("strong"); settingsTitle.textContent = "UNATTENDED RUN SETTINGS"; settingsTitle.style.color = "#67e8f9";
    const settings = document.createElement("div"); Object.assign(settings.style, { display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(190px,1fr))", gap: "8px" });
    const setting = labelText => { const wrap = document.createElement("label"); wrap.textContent = labelText; Object.assign(wrap.style, { display: "flex", flexDirection: "column", gap: "5px", padding: "9px", border: "1px solid #322d38", borderRadius: "8px", color: "#b8b0c1", font: "800 8px Segoe UI,Arial", letterSpacing: ".06em" }); settings.append(wrap); return wrap; };
    const dimensions = setting("PREVIEW SIZE · ALL SECTIONS");
    const dimensionPreset = makeSelect(CATALOG_YEARBOOK_DIMENSION_PRESETS.map(([value, label]) => [value, label]), "800x1000"); Object.assign(dimensionPreset.style, inputStyle);
    const dimensionsRow = document.createElement("div"); Object.assign(dimensionsRow.style, { display: "grid", gridTemplateColumns: "1fr 16px 1fr", gap: "5px", alignItems: "center" });
    const widthValue = document.createElement("input"); widthValue.type = "number"; widthValue.min = "16"; widthValue.max = "16384"; widthValue.step = "8"; widthValue.value = "800"; Object.assign(widthValue.style, inputStyle);
    const by = document.createElement("span"); by.textContent = "×"; by.style.textAlign = "center";
    const heightValue = document.createElement("input"); heightValue.type = "number"; heightValue.min = "16"; heightValue.max = "16384"; heightValue.step = "8"; heightValue.value = "1000"; Object.assign(heightValue.style, inputStyle);
    dimensionsRow.append(widthValue, by, heightValue); dimensions.append(dimensionPreset, dimensionsRow);
    const applyDimensions = () => { const preset = CATALOG_YEARBOOK_DIMENSION_PRESETS.find(([value]) => value === dimensionPreset.value); if (preset && preset[0] !== "custom") { widthValue.value = String(preset[2]); heightValue.value = String(preset[3]); } };
    const markCustomDimensions = () => { const preset = CATALOG_YEARBOOK_DIMENSION_PRESETS.find(([, , width, height]) => width === Number(widthValue.value) && height === Number(heightValue.value)); dimensionPreset.value = preset ? preset[0] : "custom"; };
    dimensionPreset.onchange = applyDimensions; widthValue.oninput = markCustomDimensions; heightValue.oninput = markCustomDimensions;
    const seedWrap = setting("SEED"); const seedValue = document.createElement("input"); seedValue.type = "number"; seedValue.min = "-1"; seedValue.max = "1125899906842624"; seedValue.step = "1"; seedValue.value = "4815162342"; Object.assign(seedValue.style, inputStyle); seedWrap.append(seedValue);
    const nameWrap = setting("NAME · TEMPORARY"); const nameValue = document.createElement("input"); nameValue.value = "Tiffany"; Object.assign(nameValue.style, inputStyle); nameWrap.append(nameValue);
    const brandWrap = setting("BRAND / ITEM · TEMPORARY"); const brandValue = document.createElement("input"); brandValue.value = "BRAND"; Object.assign(brandValue.style, inputStyle); brandWrap.append(brandValue);
    const logSelect = (labelText, widgetName) => { const wrap = setting(labelText); const values = (studioWidget(prompt, widgetName)?.options?.values || []).filter(value => value && value !== "[None]"); const select = makeSelect([["", "No shuffle source"], ...values.map(value => [value, previewRunLogOptionLabel(prompt, widgetName, value)])], values[0] || ""); Object.assign(select.style, inputStyle); wrap.append(select); return select; };
    const outfitLog = logSelect("OUTFIT LOG · FOR OUTFIT TOKENS", "outfit_log_file_A");
    const sceneLog = logSelect("SCENE LOG · FOR SCENE TOKENS", "scene_log_file");

    const catalogTitle = document.createElement("strong"); catalogTitle.textContent = "OUTFIT / SCENE CATALOG PROMPTS"; catalogTitle.style.color = "#f6e65a";
    const catalogGrid = document.createElement("div"); Object.assign(catalogGrid.style, { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" });
    const outfitPrompt = document.createElement("textarea"); outfitPrompt.rows = 3; outfitPrompt.value = catalogPromptSetting(CATALOG_OUTFIT_PROMPT_KEY, DEFAULT_CATALOG_OUTFIT_PROMPT, LEGACY_CATALOG_OUTFIT_PROMPT);
    const scenePrompt = document.createElement("textarea"); scenePrompt.rows = 3; scenePrompt.value = catalogPromptSetting(CATALOG_SCENE_PROMPT_KEY, DEFAULT_CATALOG_SCENE_PROMPT, LEGACY_CATALOG_SCENE_PROMPT);
    for (const field of [outfitPrompt, scenePrompt]) Object.assign(field.style, { ...inputStyle, resize: "vertical", font: "11px/1.4 Segoe UI,Arial" });
    const outfitBox = document.createElement("label"); outfitBox.textContent = "OUTFITS / WARDROBE · SELECTED SIZE"; Object.assign(outfitBox.style, { color: "#f6e65a", font: "800 8px Segoe UI,Arial", display: "flex", flexDirection: "column", gap: "5px" }); outfitBox.append(outfitPrompt);
    const sceneBox = document.createElement("label"); sceneBox.textContent = "SCENES · SELECTED SIZE, LANDSCAPE"; Object.assign(sceneBox.style, { color: "#63e6a4", font: "800 8px Segoe UI,Arial", display: "flex", flexDirection: "column", gap: "5px" }); sceneBox.append(scenePrompt); catalogGrid.append(outfitBox, sceneBox);

    const options = document.createElement("div"); Object.assign(options.style, { display: "flex", flexWrap: "wrap", gap: "16px", padding: "9px", border: "1px solid #322d38", borderRadius: "8px" });
    const toggle = (labelText, checked) => { const label = document.createElement("label"); Object.assign(label.style, { display: "flex", alignItems: "center", gap: "7px", color: "#d7d1dc", fontSize: "11px" }); const input = document.createElement("input"); input.type = "checkbox"; input.checked = checked; label.append(input, document.createTextNode(labelText)); options.append(label); return input; };
    const autoCheck = toggle("Queue each next image automatically", true);
    const shuffleCheck = toggle("Shuffle the whole run for broad coverage", true);
    const continueCheck = toggle("Continue past individual generation/save errors", true);
    const theaterCheck = toggle("Open Theater Mode · Live", false);
    const note = document.createElement("div"); note.textContent = `For an away-from-keyboard run, leave automatic queueing and continue-on-error enabled. Theater defaults off to keep the browser lighter. Generated files are kept under output/${CREATIVE_YEARBOOK_OUTPUT_ROOT}. Existing thumbnails are never replaced.`; Object.assign(note.style, { color: "#827c88", font: "9px/1.45 Segoe UI,Arial" });
    body.append(intro, scopeTitle, scopeGrid, settingsTitle, settings, catalogTitle, catalogGrid, options, note);

    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const start = action(`START · FILL ${totalMissing.toLocaleString()} MISSING`, "#6ee7a2");
    const updateStart = () => { const count = groups.reduce((sum, group) => sum + (groupChecks.get(group.key)?.checked ? group.missing : 0), 0); start.textContent = `START · FILL ${count.toLocaleString()} MISSING`; start.disabled = count === 0; };
    for (const check of groupChecks.values()) check.addEventListener("change", updateStart); updateStart();
    start.onclick = () => {
        let items = [];
        for (const group of groups) if (groupChecks.get(group.key)?.checked) items.push(...catalogRunTargets(group.rows, "missing"));
        if (!items.length) { alert("Select at least one library that still has missing thumbnails."); return; }
        const width = Math.round(Number(widthValue.value)), height = Math.round(Number(heightValue.value)), seed = Math.trunc(Number(seedValue.value));
        if (!Number.isFinite(width) || width < 16 || width > 16384 || !Number.isFinite(height) || height < 16 || height > 16384) { alert("Prompt / Template width and height must each be between 16 and 16384 pixels."); return; }
        if (!Number.isFinite(seed) || seed < -1 || seed > 1125899906842624) { alert("Seed must be −1 for random or a whole number from 0 to 1125899906842624."); return; }
        const outfitText = outfitPrompt.value.trim(), sceneText = scenePrompt.value.trim();
        if (items.some(item => ["outfit", "piece"].includes(String(item.kind || ""))) && !outfitText) { alert("Keep an Outfit / Wardrobe catalog prompt for this run."); return; }
        if (items.some(item => String(item.kind || "") === "scene") && !sceneText) { alert("Keep a Scene catalog prompt for this run."); return; }
        if (shuffleCheck.checked) items = shuffledCatalogItems(items);
        localStorage.setItem(CATALOG_OUTFIT_PROMPT_KEY, outfitText || DEFAULT_CATALOG_OUTFIT_PROMPT);
        localStorage.setItem(CATALOG_SCENE_PROMPT_KEY, sceneText || DEFAULT_CATALOG_SCENE_PROMPT);
        localStorage.setItem(CATALOG_THEATER_ENABLED_KEY, theaterCheck.checked ? "true" : "false");
        const originals = [
            ...captureStudioValues(loader, ["main_enabled", "control_after_generate"]),
            ...captureStudioValues(prompt, ["prompt_source", "manual_prompt", "prefix_enabled", "suffix_enabled", "outfit_log_file_A", "outfit_mode_A", "scene_log_file", "scene_mode"]),
            ...captureStudioValues(generation, ["resolution_mode", "custom_width", "custom_height", "seed_value", "batch_size"]),
            ...outputs.flatMap(output => captureStudioValues(output, ["output_root"])),
        ];
        const secondaryOriginals = copySecondaryStack(loader);
        setStudioWidget(loader, "main_enabled", false); setStudioWidget(loader, "control_after_generate", "fixed"); applySecondaryStack(loader, secondaryOriginals, false);
        setStudioWidget(prompt, "prompt_source", "manual"); setStudioWidget(prompt, "prefix_enabled", false); setStudioWidget(prompt, "suffix_enabled", false);
        if (outfitLog.value) { setStudioWidget(prompt, "outfit_log_file_A", outfitLog.value); setStudioWidget(prompt, "outfit_mode_A", "randomize"); }
        if (sceneLog.value) { setStudioWidget(prompt, "scene_log_file", sceneLog.value); setStudioWidget(prompt, "scene_mode", "randomize"); }
        setStudioWidget(generation, "resolution_mode", "custom"); setStudioWidget(generation, "custom_width", width); setStudioWidget(generation, "custom_height", height); setStudioWidget(generation, "seed_value", seed); setStudioWidget(generation, "batch_size", 1);
        for (const output of outputs) setStudioWidget(output, "output_root", CREATIVE_YEARBOOK_OUTPUT_ROOT);
        catalogRun = {
            runId: ++catalogRunSerial, libraryWide: true, directPrompt: true, items, index: 0, captured: 0, failed: 0, skipped: 0,
            loader, prompt, generation, outputs, previewNodeId: preview.id, originals, secondaryOriginals,
            outfitPrompt: outfitText || DEFAULT_CATALOG_OUTFIT_PROMPT, scenePrompt: sceneText || DEFAULT_CATALOG_SCENE_PROMPT,
            promptWidth: width, promptHeight: height, yearbookName: nameValue.value.trim() || "Tiffany", yearbookItem: brandValue.value.trim() || "BRAND",
            autoQueue: autoCheck.checked, targetMode: "missing", locationMode: "whole-library", continueOnError: continueCheck.checked,
            theaterEnabled: theaterCheck.checked, theater: theaterCheck.checked ? { entries: [], cursor: -1, live: true, sizeMode: catalogTheaterInitialSize(), overlay: null, ui: null } : null,
            timers: new Set(), stopped: false, completed: false, restored: false, queueStarted: false, queuePromise: null, waitingForQueue: false, interruptRequested: false,
        };
        window.__soCreativeLibraryRunActive = true;
        overlay.remove(); setCatalogRunButton(true); render(); catalogProgress();
        if (catalogRun.theaterEnabled) openCreativeTheater(catalogRun);
        scheduleCatalogRun(catalogRun, prepareCatalogRunCurrent, 180);
    };
    foot.append(cancel, start); card.append(body, foot);
}

function openCatalogRunDialog() { return openCatalogRunDialogForItem(null); }

async function selectedPreviewItems() {
    if (["recipes", "prompts"].includes(activeView)) return selectedPromptThumbnailItems();
    if (activeView === "outfits" && outfitMode === "pieces") {
        const ids = new Set(wardrobeSelectedIds());
        return wardrobeEntries().filter(item => ids.has(String(item.wardrobe_id || ""))).map(item => ({ ...item, kind: "piece" }));
    }
    return selectedComponentThumbnailAssets();
}

async function openGeneratePreviewsDialog() {
    if (catalogRun) { stopCatalogRun(false); return; }
    const { overlay, card } = collectionModal("GENERATE PREVIEWS", "720px");
    card.style.borderColor = "#6ee7a299";
    const body = document.createElement("div");
    Object.assign(body.style, { padding: "14px", display: "grid", gap: "9px", overflow: "auto" });
    const intro = document.createElement("div");
    intro.textContent = "Choose the scope once. Creative Library will use the appropriate Prompt/Template or catalog-preview runner internally.";
    Object.assign(intro.style, { color: "#b9b2c0", font: "11px/1.5 Segoe UI,Arial", marginBottom: "3px" });
    body.append(intro);
    const option = (title, detail, color, handler, disabled = false) => {
        const button = action(title, color); button.disabled = disabled;
        Object.assign(button.style, { display: "grid", gap: "3px", width: "100%", padding: "11px 12px", textAlign: "left", opacity: disabled ? ".38" : "1" });
        const note = document.createElement("span"); note.textContent = detail; Object.assign(note.style, { color: "#99919f", font: "9px/1.35 Segoe UI,Arial", textTransform: "none", letterSpacing: "0" });
        button.append(note); button.onclick = async () => { overlay.remove(); await handler(); }; body.append(button);
    };
    const selectedCount = ["recipes", "prompts"].includes(activeView)
        ? promptSelectionCount()
        : (activeView === "outfits" && outfitMode === "pieces" ? wardrobeSelectionCount() : selectedComponentIds.size);
    option(
        `SELECTED ITEMS${selectedCount ? ` · ${selectedCount.toLocaleString()}` : ""}`,
        "Generate or regenerate previews only for the current multi-selection.", "#f6e65a",
        async () => {
            const items = await selectedPreviewItems();
            if (!items.length) { alert("Select Library items first."); return; }
            if (["recipes", "prompts"].includes(activeView)) await openPromptCatalogRunDialog(items);
            else openCatalogRunDialogForItem(null, items);
        }, !selectedCount,
    );
    option(
        "CURRENT FILTERED RESULTS",
        "Uses the current tab, search, Home, Collection, rating, and other active filters.", "#35d7ff",
        () => openCatalogRunDialog(),
    );
    option(
        "SELECT LIBRARY SECTIONS",
        "Choose Templates, Prompts, Outfit Looks, Wardrobe, and/or Scenes; the same dialog can cover the entire Creative Library.", "#6ee7a2",
        () => openWholeLibraryYearbookDialog(),
    );
    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", padding: "2px 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove(); foot.append(cancel); card.append(body, foot);
}

function openCatalogRunDialogForItem(singleItem = null, explicitItems = null) {
    const explicitScope = Array.isArray(explicitItems) && explicitItems.length > 0;
    if (!singleItem && !explicitScope && ["recipes", "prompts"].includes(activeView)) { openPromptCatalogRunDialog(); return; }
    if (catalogRun) { stopCatalogRun(false); return; }
    const loader = findStudioNode("SOLoaderCoreEngineStudio");
    const prompt = findStudioNode("SOPromptLogEngineStudio");
    const generation = findStudioNode("SOGenerationPipelineStudio");
    const preview = findStudioNode(PREVIEW_TYPE);
    const outputs = findStudioOutputs();
    if (!loader || !prompt || !generation || !preview) { alert("Preview Run needs Loader Core, Prompt Core, Generation Core, and Preview Core on the current canvas."); return; }
    if (window.__soYearbookRunActive) { alert("Stop the active LoRA preview run before starting a Creative Library Preview Run."); return; }
    const protectedNames = [[prompt, "prompt_source"], [prompt, "manual_prompt"], [prompt, "prefix_enabled"], [prompt, "suffix_enabled"], [generation, "resolution_mode"], [generation, "custom_width"], [generation, "custom_height"], [generation, "batch_size"], ...outputs.map(output => [output, "output_root"])];
    const blocked = protectedNames.find(([node, name]) => { const target = studioWidget(node, name); return target && isConnected(node, target); });
    if (blocked) { alert(`${humanField(blocked[1])} is connected, so Preview Run cannot safely take temporary control of it.`); return; }

    const outfits = derivedValues.outfits || [];
    const scenes = derivedValues.scenes || [];
    const pieces = wardrobeItems.filter(item => ["piece", "set"].includes(String(item.item_type || "piece"))).map(item => ({ ...item, kind: "piece" }));
    const regenerateItem = singleItem?.wardrobe_id ? { ...singleItem, kind: "piece" } : null;
    const regenerationItems = explicitScope ? explicitItems.map(item => ({ ...item, kind: String(item.kind || currentCatalogKind() || "outfit") })) : (regenerateItem ? [regenerateItem] : []);
    if (!regenerationItems.length && !outfits.length && !scenes.length && !pieces.length) { alert("There are no Looks, Pieces, or Scene assets yet. Add wardrobe assets or import existing Outfit / Scene logs first."); return; }

    const currentKind = currentCatalogKind();
    const currentAll = currentKind === "piece" ? pieces : currentKind === "outfit" ? outfits : currentKind === "scene" ? scenes : [];
    const currentFiltered = currentKind === "piece" ? wardrobeEntries().filter(item => ["piece", "set"].includes(String(item.item_type || "piece"))).map(item => ({ ...item, kind: "piece" })) : currentKind ? derivedEntries(currentKind) : [];
    const currentCollectionRows = ["outfit", "scene"].includes(currentKind) ? currentAll.filter(asset => {
        if (!activeCollection) return true;
        if (activeCollection === "unfiled") return !(asset.collections || []).length;
        return (asset.collections || []).some(collection => String(collection.collection_id || "") === String(activeCollection));
    }) : currentAll;
    const selected = [...outfits, ...scenes].filter(asset => selectedComponentIds.has(String(asset.component_id || "")));
    const locationMap = new Map();
    const locationOptions = [];
    const addLocation = (id, label, rows) => {
        const unique = [...new Map((rows || []).map(item => [String(item.component_id || `${item.kind}:${item.value}`), item])).values()];
        if (!unique.length) return;
        locationMap.set(id, unique); locationOptions.push([id, `${label} · ${unique.length.toLocaleString()}`]);
    };
    if (regenerationItems.length) {
        addLocation("explicit", regenerationItems.length === 1 ? `This ${String(regenerationItems[0].kind || "asset")}` : `Selected assets`, regenerationItems);
    } else {
    if (selected.length && currentKind !== "piece") addLocation("selected", "Selected assets", selected);
    if (currentKind) addLocation("filtered", `Current filtered ${currentKind === "piece" ? "Pieces" : currentKind === "outfit" ? "Looks" : "Scene"} view`, currentFiltered);
    if (["outfit", "scene"].includes(currentKind) && activeCollection) {
        const group = activeCollection === "unfiled" ? null : (componentCollections[currentKind] || []).find(item => String(item.collection_id) === String(activeCollection));
        addLocation("collection", activeCollection === "unfiled" ? "Unfiled collection scope" : `Collection · ${group?.name || "Current"}`, currentCollectionRows);
    }
    if (currentKind === "piece") {
        addLocation("current-kind", "All Pieces + Matching Sets", pieces);
        for (const category of Object.keys(WARDROBE_TAXONOMY)) {
            const rows = pieces.filter(item => String(item.category || "Uncategorized") === category);
            addLocation(`piece-category:${category}`, `Pieces · ${category}`, rows);
        }
        if (wardrobeCategory) {
            for (const subtype of WARDROBE_TAXONOMY[wardrobeCategory] || []) {
                const rows = pieces.filter(item => String(item.category || "Uncategorized") === wardrobeCategory && String(item.subtype || "") === subtype);
                addLocation(`piece-subtype:${wardrobeCategory}:${subtype}`, `${wardrobeCategory} · ${subtype}`, rows);
            }
        }
    } else if (currentKind) {
        addLocation("current-kind", `All ${currentKind === "outfit" ? "Looks" : "Scenes"}`, currentAll);
        for (const group of componentCollections[currentKind] || []) {
            const groupId = String(group.collection_id || "");
            const rows = currentAll.filter(asset => (asset.collections || []).some(collection => String(collection.collection_id || "") === groupId));
            addLocation(`collection:${groupId}`, `Collection · ${String(group.name || "Untitled")}`, rows);
        }
    }
    if (!currentKind) {
        if (outfits.length && scenes.length) addLocation("all", "All Looks + Scenes", [...outfits, ...scenes]);
        else addLocation("all", outfits.length ? "All Looks" : scenes.length ? "All Scenes" : "All Pieces", outfits.length ? outfits : scenes.length ? scenes : pieces);
    }
    }
    if (!locationOptions.length) {
        const fallback = pieces.length ? pieces : outfits.length ? outfits : scenes;
        addLocation("all", pieces.length ? "All Pieces + Matching Sets" : outfits.length ? "All Looks" : "All Scenes", fallback);
    }
    if (!locationOptions.length) { alert("There are no previewable assets in this gallery yet."); return; }

    const regenerationMode = regenerationItems.length > 0;
    const regenerateTitle = regenerationItems.length === 1 ? "REGENERATE THUMBNAIL" : `REGENERATE ${regenerationItems.length.toLocaleString()} THUMBNAILS`;
    const { overlay, card, close } = collectionModal(regenerationMode ? regenerateTitle : "GENERATE PREVIEWS", "820px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "10px", overflow: "auto" });
    const copy = document.createElement("div"); copy.textContent = regenerationMode
        ? (regenerationItems.length === 1 ? `Generate a fresh Catalog thumbnail for “${regenerationItems[0].value}”. The Library value itself stays unchanged.` : `Generate fresh Catalog thumbnails for ${regenerationItems.length.toLocaleString()} selected assets. Their Library values and collection memberships stay unchanged.`)
        : "Preview Run follows the same Home / Collection scope model across Looks, Wardrobe Pieces, and Scenes. Choose a filtered view, then fill missing previews, replace generated previews, or rebuild everything in that scope. Stored text remains canonical."; Object.assign(copy.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.5" });

    const locationLabel = document.createElement("strong"); locationLabel.textContent = "LOCATION / SCOPE"; locationLabel.style.color = "#35d7ff";
    const defaultLocation = regenerationMode ? "explicit" : selected.length && currentKind !== "piece" ? "selected" : currentKind ? "filtered" : "all";
    const location = makeSelect(locationOptions, locationMap.has(defaultLocation) ? defaultLocation : locationOptions[0][0]);
    const targetLabel = document.createElement("strong"); targetLabel.textContent = "THUMBNAIL ACTION"; targetLabel.style.color = "#f6e65a";
    const target = makeSelect([], regenerationMode ? "all" : "missing");
    const targetHelp = document.createElement("div"); Object.assign(targetHelp.style, { color: "#8f8997", fontSize: "10px", lineHeight: "1.4" });
    const refreshTargetOptions = () => {
        const rows = locationMap.get(location.value) || [];
        const prior = target.value || (regenerationMode ? "all" : "missing");
        const counts = {
            missing: rows.filter(item => catalogRunTargetMatches(item, "missing")).length,
            replace: rows.filter(item => catalogRunTargetMatches(item, "replace")).length,
            all: rows.length,
        };
        target.replaceChildren();
        for (const [value, label] of [
            ["missing", `Fill missing Catalog previews · ${counts.missing.toLocaleString()}`],
            ["replace", `Replace existing Catalog previews · ${counts.replace.toLocaleString()}`],
            ["all", `Rebuild every preview in scope · ${counts.all.toLocaleString()}`],
        ]) { const option = document.createElement("option"); option.value = value; option.textContent = label; target.append(option); }
        target.value = ["missing", "replace", "all"].includes(prior) ? prior : (regenerationMode ? "all" : "missing");
        targetHelp.textContent = target.value === "missing" ? "Fill only assets that do not yet have a generated Catalog preview." : target.value === "replace" ? "Replace only assets that already have a generated Catalog preview." : "Generate a fresh Catalog preview for every asset in the chosen location.";
    };
    location.onchange = refreshTargetOptions; target.onchange = refreshTargetOptions; refreshTargetOptions();

    const sizeLabel = document.createElement("label"); sizeLabel.textContent = "PREVIEW SIZE";
    Object.assign(sizeLabel.style, {display:"flex",flexDirection:"column",gap:"6px",color:"#b8b0c1"});
    const dimensionPreset = makeSelect(CATALOG_YEARBOOK_DIMENSION_PRESETS.filter(([value]) => value !== "custom").map(([value,label]) => [value,label]), "800x1000");
    const sizeHint = document.createElement("small"); sizeHint.textContent = "Scenes use the same size in landscape. Saved WebP previews keep up to 2048 pixels on the longest edge, within 512 KB.";
    sizeLabel.append(dimensionPreset,sizeHint);
    const outfitLabel = document.createElement("strong"); outfitLabel.textContent = "LOOK / PIECE PREVIEW TEMPLATE"; outfitLabel.style.color = "#ff78bd";
    const outfitPrompt = document.createElement("textarea"); outfitPrompt.rows = 3; outfitPrompt.value = catalogPromptSetting(CATALOG_OUTFIT_PROMPT_KEY, DEFAULT_CATALOG_OUTFIT_PROMPT, LEGACY_CATALOG_OUTFIT_PROMPT);
    const sceneLabel = document.createElement("strong"); sceneLabel.textContent = "SCENE PREVIEW TEMPLATE"; sceneLabel.style.color = "#63e6a4";
    const scenePrompt = document.createElement("textarea"); scenePrompt.rows = 3; scenePrompt.value = catalogPromptSetting(CATALOG_SCENE_PROMPT_KEY, DEFAULT_CATALOG_SCENE_PROMPT, LEGACY_CATALOG_SCENE_PROMPT);
    for (const field of [outfitPrompt, scenePrompt]) Object.assign(field.style, { width: "100%", boxSizing: "border-box", resize: "vertical", padding: "10px", borderRadius: "8px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", font: "12px/1.4 Segoe UI,Arial" });

    const optionsRow = document.createElement("div"); Object.assign(optionsRow.style, { display: "flex", gap: "18px", flexWrap: "wrap", alignItems: "center" });
    const auto = document.createElement("label"); Object.assign(auto.style, { display: "flex", alignItems: "center", gap: "8px", color: "#d7d1dc", fontSize: "12px" }); const autoCheck = document.createElement("input"); autoCheck.type = "checkbox"; autoCheck.checked = true; auto.append(autoCheck, document.createTextNode("Queue each next image automatically"));
    const shuffle = document.createElement("label"); Object.assign(shuffle.style, { display: "flex", alignItems: "center", gap: "8px", color: "#d7d1dc", fontSize: "12px" }); const shuffleCheck = document.createElement("input"); shuffleCheck.type = "checkbox"; shuffleCheck.checked = true; shuffle.append(shuffleCheck, document.createTextNode("Shuffle run order"));
    const theater = document.createElement("label"); Object.assign(theater.style, { display: "flex", alignItems: "center", gap: "8px", color: "#d7d1dc", fontSize: "12px" }); const theaterCheck = document.createElement("input"); theaterCheck.type = "checkbox"; theaterCheck.checked = catalogTheaterEnabledByDefault(); theater.append(theaterCheck, document.createTextNode("Open Theater Mode · Live"));
    optionsRow.append(auto, shuffle, theater);
    body.append(copy, locationLabel, location, targetLabel, target, targetHelp, sizeLabel, outfitLabel, outfitPrompt, sceneLabel, scenePrompt, optionsRow);

    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = close;
    const start = action(regenerationMode ? (regenerationItems.length === 1 ? "Regenerate preview" : "Regenerate previews") : "Generate previews", "#f6e65a"); start.onclick = () => {
        const sourceItems = locationMap.get(location.value) || [];
        let items = catalogRunTargets(sourceItems, target.value);
        if (!items.length) { alert(target.value === "missing" ? "Every asset in this location already has a Catalog preview." : target.value === "replace" ? "No existing Catalog previews are available to replace in this location." : "No assets match this location."); return; }
        if (shuffleCheck.checked) items = shuffledCatalogItems(items);
        const outfitText = outfitPrompt.value.trim(), sceneText = scenePrompt.value.trim();
        if ((items.some(item => item.kind !== "scene") && !outfitText) || (items.some(item => item.kind === "scene") && !sceneText)) { alert("Keep a preview template for every asset type in this run."); return; }
        localStorage.setItem(CATALOG_OUTFIT_PROMPT_KEY, outfitText || DEFAULT_CATALOG_OUTFIT_PROMPT);
        localStorage.setItem(CATALOG_SCENE_PROMPT_KEY, sceneText || DEFAULT_CATALOG_SCENE_PROMPT);
        const originals = [
            ...captureStudioValues(loader, ["main_enabled", "control_after_generate"]),
            ...captureStudioValues(prompt, ["prompt_source", "manual_prompt", "prefix_enabled", "suffix_enabled"]),
            ...captureStudioValues(generation, ["resolution_mode", "custom_width", "custom_height", "batch_size"]),
            ...outputs.flatMap(output => captureStudioValues(output, ["output_root"])),
        ];
        const dimensions = CATALOG_YEARBOOK_DIMENSION_PRESETS.find(([value]) => value === dimensionPreset.value);
        const secondaryOriginals = copySecondaryStack(loader);
        setStudioWidget(loader, "main_enabled", false); setStudioWidget(loader, "control_after_generate", "fixed"); applySecondaryStack(loader, secondaryOriginals, false);
        setStudioWidget(prompt, "prompt_source", "manual"); setStudioWidget(prompt, "prefix_enabled", false); setStudioWidget(prompt, "suffix_enabled", false);
        setStudioWidget(generation, "resolution_mode", "custom"); setStudioWidget(generation, "batch_size", 1);
        for (const output of outputs) setStudioWidget(output, "output_root", CREATIVE_YEARBOOK_OUTPUT_ROOT);
        localStorage.setItem(CATALOG_THEATER_ENABLED_KEY, theaterCheck.checked ? "true" : "false");
        catalogRun = { promptWidth: dimensions[2], promptHeight: dimensions[3], runId: ++catalogRunSerial, items, index: 0, captured: 0, loader, prompt, generation, outputs, previewNodeId: preview.id, originals, secondaryOriginals, outfitPrompt: outfitText || DEFAULT_CATALOG_OUTFIT_PROMPT, scenePrompt: sceneText || DEFAULT_CATALOG_SCENE_PROMPT, autoQueue: autoCheck.checked, targetMode: target.value, locationMode: location.value, theaterEnabled: theaterCheck.checked, theater: theaterCheck.checked ? { entries: [], cursor: -1, live: true, sizeMode: catalogTheaterInitialSize(), overlay: null, ui: null } : null, timers: new Set(), stopped: false, completed: false, restored: false, queueStarted: false, queuePromise: null, waitingForQueue: false, interruptRequested: false };
        window.__soCreativeLibraryRunActive = true;
        if (currentKind === "piece") {
            wardrobeSort = "preview_newest"; wardrobeThumbnailFilter = ""; wardrobePage = 0;
        } else if (currentKind) {
            componentSort[currentKind] = "preview_newest";
            componentThumbnailFilter[currentKind] = "";
            componentPage[currentKind] = 0;
        }
        close(); setCatalogRunButton(true); render();
        root?.querySelector("[data-recipes]")?.scrollTo?.({ top: 0 });
        catalogProgress(); if (catalogRun.theaterEnabled) openCreativeTheater(catalogRun); scheduleCatalogRun(catalogRun, prepareCatalogRunCurrent, 160);
    };
    foot.append(cancel, start); card.append(body, foot);
}

async function loadWardrobeValue(item, destination = "A") {
    if (!item?.value) return false;
    const slot = ["A", "B", "C"].includes(String(destination || "A").toUpperCase()) ? String(destination || "A").toUpperCase() : "A";
    const promptNode = (app.graph?._nodes || []).find(node => node.type === "SOPromptLogEngineStudio");
    if (!promptNode) {
        alert("Add a Studio Prompt Core node to the canvas before loading this Wardrobe value.");
        return false;
    }
    const sourceName = `outfit_source_${slot}`;
    const manualName = `outfit_manual_${slot}`;
    const sourceWidget = studioWidget(promptNode, sourceName);
    const manualWidget = studioWidget(promptNode, manualName);
    if (!sourceWidget || !manualWidget) {
        alert(`The current Prompt Core does not expose Outfit ${slot} manual-entry controls.`);
        return false;
    }
    const protectedWidget = [sourceWidget, manualWidget].find(target => isConnected(promptNode, target));
    if (protectedWidget) {
        alert(`${humanField(protectedWidget.name)} is connected on Prompt Core, so Creative Library left it untouched.`);
        return false;
    }
    setStudioWidget(promptNode, sourceName, "manual");
    setStudioWidget(promptNode, manualName, String(item.value));
    catalogStatus(`Loaded Outfit ${slot} manual value · ${item.value}`, "#35d7ff");
    return true;
}

async function loadDerivedValue(asset, destination = "A") {
    const kind = String(asset?.kind || derivedKind());
    if (!asset || !["outfit", "scene"].includes(kind)) return false;
    const promptNode = (app.graph?._nodes || []).find(node => node.type === "SOPromptLogEngineStudio");
    if (!promptNode) {
        alert("Add a Studio Prompt Core node to the canvas before loading this value.");
        return false;
    }

    const slot = String(destination || "A").toUpperCase();
    const sourceName = kind === "scene" ? "scene_source" : `outfit_source_${slot}`;
    const fileName = kind === "scene" ? "scene_log_file" : `outfit_log_file_${slot}`;
    const modeName = kind === "scene" ? "scene_mode" : `outfit_mode_${slot}`;
    const indexName = kind === "scene" ? "scene_index" : `outfit_index_${slot}`;
    const sourceWidget = promptNode.widgets?.find(widget => widget.name === sourceName);
    const fileWidget = promptNode.widgets?.find(widget => widget.name === fileName);
    const modeWidget = promptNode.widgets?.find(widget => widget.name === modeName);
    const indexWidget = promptNode.widgets?.find(widget => widget.name === indexName);
    if (!sourceWidget || !fileWidget || !modeWidget || !indexWidget) {
        alert(`The current Prompt Core does not expose the ${kind} controls needed for this Creative Library value.`);
        return false;
    }
    const protectedWidget = [sourceWidget, fileWidget, modeWidget, indexWidget].find(target => isConnected(promptNode, target));
    if (protectedWidget) {
        alert(`${humanField(protectedWidget.name)} is connected on Prompt Core, so Creative Library left it untouched.`);
        return false;
    }

    const logFile = String(derivedValues.logs?.[kind] || "");
    if (!logFile) {
        alert(`The Creative Library ${kind} master log is not available yet.`);
        return false;
    }
    try {
        const response = await fetch(`/sickollie/studio/prompt-core/log-files?category=${encodeURIComponent(kind)}`);
        const payload = await response.json().catch(() => ({}));
        const values = Array.isArray(payload?.files) ? payload.files.map(String) : [];
        if (!response.ok || !values.includes(logFile)) throw new Error(`Generated log ${logFile} was not found by Prompt Core.`);
        writeComboValues(fileWidget, values);
        setStudioWidget(promptNode, sourceName, "log");
        fileWidget.value = logFile;
        modeWidget.value = "fixed";
        indexWidget.value = Number(asset.index || 0);
        try { fileWidget.callback?.(fileWidget.value); } catch (error) {}
        try { modeWidget.callback?.(modeWidget.value); } catch (error) {}
        try { indexWidget.callback?.(indexWidget.value); } catch (error) {}
        promptNode.setDirtyCanvas?.(true, true);
        const destinationLabel = kind === "scene" ? "Scene" : `Outfit ${String(destination || "A").toUpperCase()}`;
        catalogStatus(`Loaded ${destinationLabel}: ${asset.value}`);
        return true;
    } catch (error) {
        alert(error.message || `Could not load this ${kind} into Prompt Core.`);
        return false;
    }
}

async function setComponentRating(asset, nextRating) {
    const componentId = String(asset?.component_id || "");
    if (!componentId) return;
    const previous = Math.max(0, Math.min(5, Number(asset.rating || 0)));
    const rating = previous === Number(nextRating) ? 0 : Math.max(0, Math.min(5, Number(nextRating || 0)));
    asset.rating = rating;
    render();
    try {
        await request(`/derived-values/${encodeURIComponent(componentId)}/rating`, { method: "POST", body: JSON.stringify({ rating }) });
        const rows = asset.kind === "scene" ? (derivedValues.scenes || []) : (derivedValues.outfits || []);
        const canonical = rows.find(item => String(item.component_id || "") === componentId);
        if (canonical) canonical.rating = rating;
        catalogStatus(`${asset.kind === "scene" ? "Scene" : "Outfit"} rating ${rating ? `${rating}★` : "cleared"}.`, rating >= 4 ? "#f6e65a" : "#6ee7a2");
        render();
    } catch (error) {
        asset.rating = previous;
        const rows = asset.kind === "scene" ? (derivedValues.scenes || []) : (derivedValues.outfits || []);
        const canonical = rows.find(item => String(item.component_id || "") === componentId);
        if (canonical) canonical.rating = previous;
        render();
        alert(error.message || "Could not save the rating.");
    }
}

function componentRatingButtons(asset, accent) {
    const row = document.createElement("div"); Object.assign(row.style, { display: "flex", alignItems: "center", gap: "2px", minHeight: "23px" });
    const current = Math.max(0, Math.min(5, Number(asset.rating || 0)));
    for (let rating = 1; rating <= 5; rating += 1) {
        const star = document.createElement("button"); star.type = "button"; star.textContent = rating <= current ? "★" : "☆"; star.title = current === rating ? `Clear ${rating}-star rating` : `Rate ${rating} star${rating === 1 ? "" : "s"}`;
        Object.assign(star.style, { padding: "0 1px", border: "0", background: "transparent", color: rating <= current ? "#f6e65a" : "#655f6b", cursor: "pointer", font: "700 16px/1 Segoe UI Symbol,Segoe UI,Arial" });
        star.onclick = event => { event.stopPropagation(); void setComponentRating(asset, rating); };
        row.append(star);
    }
    const label = document.createElement("span"); label.textContent = current ? `${current}★` : "unrated"; Object.assign(label.style, { marginLeft: "4px", color: current >= 4 ? "#f6e65a" : "#817b88", font: "700 8px Segoe UI,Arial", letterSpacing: ".03em" }); row.append(label);
    return row;
}


async function copyLibraryValue(text) {
    const value = String(text || "");
    if (!value) return false;
    try {
        if (navigator?.clipboard?.writeText) {
            await navigator.clipboard.writeText(value);
            return true;
        }
    } catch (error) {}
    try {
        const textarea = document.createElement("textarea");
        textarea.value = value;
        textarea.setAttribute("readonly", "");
        Object.assign(textarea.style, { position: "fixed", left: "-9999px", top: "-9999px", opacity: "0" });
        document.body.append(textarea);
        textarea.select();
        const copied = document.execCommand?.("copy") !== false;
        textarea.remove();
        return copied;
    } catch (error) {
        return false;
    }
}

async function copyComponentValue(asset, button) {
    const kind = asset?.kind === "scene" ? "Scene" : "Outfit";
    const copied = await copyLibraryValue(asset?.value);
    if (!copied) {
        alert(`Could not copy this ${kind.toLowerCase()} value.`);
        return;
    }
    const previous = button?.textContent || "COPY";
    if (button) {
        button.textContent = "COPIED";
        button.disabled = true;
        window.setTimeout(() => { button.textContent = previous; button.disabled = false; }, 850);
    }
    catalogStatus(`Copied ${kind.toLowerCase()} value.`, kind === "Scene" ? "#63e6a4" : "#ff8fce");
}

function libraryCollectionAccent(kind) { return kind === "scene" ? "#63e6a4" : kind === "wardrobe" ? "#ff9b5f" : "#f6e65a"; }
function libraryCollectionLabel(kind) { return kind === "scene" ? "Scene" : kind === "wardrobe" ? "Wardrobe" : "Outfit Looks"; }
async function refreshLibraryCollectionKind(kind) {
    const response = await request(`/library-collections?kind=${encodeURIComponent(kind)}`);
    libraryCollections[kind] = Array.isArray(response.collections) ? response.collections : [];
    window.dispatchEvent(new CustomEvent("sickollie:library-collections-changed", { detail: { kind } }));
    return libraryCollections[kind];
}
function currentLibraryCollectionAssetIds(kind) {
    if (kind === "wardrobe") return wardrobeEntries().map(item => String(item.wardrobe_id || "")).filter(Boolean);
    if (["outfit", "scene"].includes(kind)) return derivedEntries(kind).map(item => String(item.component_id || "")).filter(Boolean);
    return [];
}

function showLibraryCollectionManager(kind) {
    const accent = libraryCollectionAccent(kind); const label = libraryCollectionLabel(kind);
    const { overlay, card } = collectionModal(`${label.toUpperCase()} COLLECTIONS`, "760px"); card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding:"14px", overflow:"auto", display:"grid", gap:"9px" });
    const help = document.createElement("div"); help.textContent = `Collections are portable, shareable groups. They do not move an asset out of its ${label} Home. Use them for themes such as Halloween, Summer, Editorial, Favorites, or any custom set you want to export or use as a generation pool.`; Object.assign(help.style,{color:"#aaa2b4",font:"10px/1.5 Segoe UI,Arial"}); body.append(help);
    const createRow = document.createElement("div"); Object.assign(createRow.style,{display:"grid",gridTemplateColumns:"1fr auto",gap:"7px"}); const input=document.createElement("input"); input.placeholder=`New ${label} collection`; Object.assign(input.style,{padding:"8px",borderRadius:"7px",border:`1px solid ${accent}55`,background:"#09080d",color:"#fff"}); const create=action("+ CREATE",accent); createRow.append(input,create); body.append(createRow);
    const viewNote = document.createElement("div"); viewNote.textContent = "ADD VIEW adds every asset matching the gallery's current folder/search/filter view to that Collection. Existing memberships are preserved."; Object.assign(viewNote.style,{color:"#716b77",font:"8px/1.4 Segoe UI,Arial"}); body.append(viewNote);
    const rows=document.createElement("div"); Object.assign(rows.style,{display:"grid",gap:"6px"}); body.append(rows);
    const redraw=()=>{
        rows.replaceChildren();
        for(const [index, collection] of (libraryCollections[kind]||[]).entries()){
            const row=document.createElement("div"); Object.assign(row.style,{display:"grid",gridTemplateColumns: ["outfit", "scene"].includes(kind) ? "auto auto minmax(0,1fr) auto auto auto auto" : "minmax(0,1fr) auto auto auto auto",gap:"6px",alignItems:"center",padding:"7px",border:"1px solid #302b35",borderRadius:"8px",background:"rgba(255,255,255,.018)"});
            const name=document.createElement("input"); name.value=String(collection.name||""); Object.assign(name.style,{minWidth:"0",padding:"7px",borderRadius:"6px",border:"1px solid #49424f",background:"#0b0910",color:"#fff"});
            const count=document.createElement("span"); count.textContent=`${Number(collection.asset_count||0).toLocaleString()} items`; Object.assign(count.style,{color:"#827b89",font:"8px Segoe UI,Arial",whiteSpace:"nowrap"});
            const addView=action("+ ADD VIEW", "#6ee7a2"); Object.assign(addView.style,{padding:"5px 7px",fontSize:"8px"}); addView.title="Add the entire current filtered gallery view to this Collection"; addView.onclick=async()=>{
                const ids=currentLibraryCollectionAssetIds(kind); if(!ids.length){alert("The current gallery view has no assets to collect.");return;}
                if(!confirm(`Add all ${ids.length.toLocaleString()} assets in the current gallery view to “${collection.name}”? Existing Collection memberships stay in place.`))return;
                addView.disabled=true; try{ const result=await request("/library-collections/bulk",{method:"POST",body:JSON.stringify({kind,asset_ids:ids,collection_ids:[String(collection.collection_id||"")]})}); await refreshLibraryCollectionKind(kind); redraw(); render(); catalogStatus(`Collected ${Number(result.assets||ids.length).toLocaleString()} ${label} assets into ${collection.name}.`,accent); }catch(error){alert(error.message||"Could not collect the current view.");}finally{addView.disabled=false;}
            };
            const save=action("SAVE",accent); Object.assign(save.style,{padding:"5px 7px",fontSize:"8px"}); save.onclick=async()=>{ try{ await request(`/library-collections/${encodeURIComponent(collection.collection_id)}`,{method:"PATCH",body:JSON.stringify({name:name.value})}); await refreshLibraryCollectionKind(kind); redraw(); render(); }catch(error){alert(error.message||"Could not rename the collection.");} };
            const del=action("DELETE","#ff4ab8"); Object.assign(del.style,{padding:"5px 7px",fontSize:"8px"}); del.onclick=async()=>{ if(!confirm(`Delete collection “${collection.name}”? Its ${label} assets and thumbnails stay in the Library.`))return; try{ await request(`/library-collections/${encodeURIComponent(collection.collection_id)}`,{method:"DELETE"}); if(activeLibraryCollection[kind]===String(collection.collection_id)) activeLibraryCollection[kind]=""; await refreshLibraryCollectionKind(kind); redraw(); render(); }catch(error){alert(error.message||"Could not delete the collection.");} };
            if (["outfit", "scene"].includes(kind)) {
                const move = async direction => {
                    try {
                        const ids = reorderedValues(libraryCollections[kind], index, direction).map(item => String(item.collection_id));
                        await saveCreativeStructureOrder(kind, { ...await creativeStructureOrder(kind), library_collections: ids });
                        await refreshLibraryCollectionKind(kind); redraw(); render();
                    } catch (error) { alert(error.message || "Could not reorder Collections."); }
                };
                row.append(tinyOrderButton("↑", "Move Collection up", index === 0, () => void move(-1)), tinyOrderButton("↓", "Move Collection down", index === libraryCollections[kind].length - 1, () => void move(1)));
            }
            row.append(name,count,addView,save,del); rows.append(row);
        }
        if (!(libraryCollections[kind]||[]).length) { const empty=document.createElement("div"); empty.textContent="No shareable Collections yet. Create one above."; Object.assign(empty.style,{padding:"10px",color:"#817b88",fontSize:"9px"}); rows.append(empty); }
    };
    create.onclick=async()=>{ const name=input.value.trim(); if(!name)return; create.disabled=true; try{ await request("/library-collections",{method:"POST",body:JSON.stringify({kind,name})}); input.value=""; await refreshLibraryCollectionKind(kind); redraw(); render(); }catch(error){alert(error.message||"Could not create the collection.");}finally{create.disabled=false;} }; redraw();
    const footer=document.createElement("div"); Object.assign(footer.style,{display:"flex",justifyContent:"flex-end",padding:"0 14px 14px"}); const done=action("DONE",accent); done.onclick=()=>overlay.remove(); footer.append(done); card.append(body,footer);
}

async function showLibraryAssetCollectionEditor(asset, kind, onSaved = null) {
    const accent = libraryCollectionAccent(kind);
    const label = libraryCollectionLabel(kind);
    const assetId = String(kind === "wardrobe" ? asset?.wardrobe_id : asset?.component_id || "");
    if (!assetId) return;
    try { await refreshLibraryCollectionKind(kind); } catch (error) {}
    const { overlay, card, close } = collectionModal(`ADD TO ${label.toUpperCase()} COLLECTIONS`, "650px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div");
    Object.assign(body.style, { padding: "14px", overflow: "auto", display: "grid", gap: "8px" });
    const value = document.createElement("div");
    value.textContent = String(asset?.value || "");
    Object.assign(value.style, { padding: "9px", border: `1px solid ${accent}44`, borderRadius: "8px", color: "#fff", font: "10px/1.4 Segoe UI,Arial" });
    body.append(value);

    const existing = new Set((asset?.pack_collections || []).map(row => String(row.collection_id || "")));
    const checks = new Map();
    const list = document.createElement("div");
    Object.assign(list.style, { display: "grid", gap: "5px" });
    const redrawCollections = () => {
        if (checks.size) {
            existing.clear();
            for (const [id, box] of checks) if (box.checked) existing.add(id);
        }
        list.replaceChildren();
        checks.clear();
        for (const collection of libraryCollections[kind] || []) {
            const row = document.createElement("label");
            Object.assign(row.style, { display: "flex", alignItems: "center", gap: "8px", padding: "8px", border: "1px solid #302b35", borderRadius: "7px", cursor: "pointer" });
            const box = document.createElement("input");
            box.type = "checkbox";
            box.checked = existing.has(String(collection.collection_id));
            checks.set(String(collection.collection_id), box);
            const text = document.createElement("span");
            text.textContent = `${collection.name} · ${Number(collection.asset_count || 0).toLocaleString()}`;
            Object.assign(text.style, { color: "#c9c1cf", font: "9px Segoe UI,Arial" });
            row.append(box, text);
            list.append(row);
        }
        if (!(libraryCollections[kind] || []).length) {
            const empty = document.createElement("div");
            empty.textContent = "No collections yet. Create the first one below without leaving this item.";
            Object.assign(empty.style, { padding: "9px", color: "#f6e65a", font: "9px/1.4 Segoe UI,Arial" });
            list.append(empty);
        }
    };
    redrawCollections();
    body.append(list);

    const createRow = document.createElement("div");
    Object.assign(createRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "6px", marginTop: "3px" });
    const createInput = document.createElement("input");
    createInput.placeholder = `New ${label} collection`;
    Object.assign(createInput.style, { minWidth: "0", padding: "8px", borderRadius: "7px", border: `1px solid ${accent}55`, background: "#09080d", color: "#fff" });
    const create = action("+ CREATE", accent);
    create.onclick = async () => {
        const name = createInput.value.trim();
        if (!name) return;
        create.disabled = true;
        try {
            const response = await request("/library-collections", { method: "POST", body: JSON.stringify({ kind, name }) });
            const createdId = String(response?.collection?.collection_id || "");
            createInput.value = "";
            await refreshLibraryCollectionKind(kind);
            redrawCollections();
            if (createdId && checks.has(createdId)) checks.get(createdId).checked = true;
            catalogStatus(`Created ${label} collection ${name}.`, accent);
        } catch (error) { alert(error.message || "Could not create the collection."); }
        finally { create.disabled = false; }
    };
    createInput.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); create.click(); } });
    createRow.append(createInput, create);
    body.append(createRow);

    const footer = document.createElement("div");
    Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997");
    cancel.onclick = close;
    const save = action("SAVE COLLECTIONS", accent);
    save.onclick = async () => {
        const ids = [...checks].filter(([, box]) => box.checked).map(([id]) => id);
        save.disabled = true;
        try {
            const response = await request(`/library-collections/${encodeURIComponent(kind)}/${encodeURIComponent(assetId)}`, { method: "PUT", body: JSON.stringify({ collection_ids: ids }) });
            asset.pack_collections = Array.isArray(response.collections) ? response.collections : [];
            await refreshLibraryCollectionKind(kind);
            close();
            render();
            onSaved?.(asset);
            catalogStatus(`Updated ${label} collections.`, accent);
        } catch (error) { alert(error.message || "Could not update collections."); save.disabled = false; }
    };
    footer.append(cancel, save);
    card.append(body, footer);
}

function selectedComponentThumbnailAssets() {
    const kind = currentComponentKind();
    if (!["outfit", "scene"].includes(kind)) return [];
    const ids = new Set([...selectedComponentIds].map(value => String(value || "")).filter(Boolean));
    const rows = kind === "outfit" ? (derivedValues.outfits || []) : (derivedValues.scenes || []);
    return rows.filter(item => ids.has(String(item.component_id || ""))).map(item => ({ ...item, kind }));
}

async function deleteComponentThumbnail(asset) {
    const componentId = String(asset?.component_id || "");
    if (!componentId || !asset?.preview_ref) return;
    const label = asset.kind === "scene" ? "Scene" : "Outfit";
    if (!(await comfyConfirm(`Delete this ${label} thumbnail? The ${label.toLowerCase()} value and collections stay intact.`, `Delete ${label} thumbnail?`))) return;
    try {
        await request(`/derived-values/${encodeURIComponent(componentId)}/preview`, { method: "DELETE" });
        await load();
        catalogStatus(`${label} thumbnail deleted.`, "#ff9b5f");
        return true;
    } catch (error) { alert(error.message || `Could not delete this ${label.toLowerCase()} thumbnail.`); }
}

async function deleteSelectedComponentThumbnails() {
    const items = selectedComponentThumbnailAssets();
    if (!items.length) { alert("Select Outfit / Scene assets first."); return; }
    const withPreview = items.filter(item => String(item.preview_ref || "")).length;
    if (!withPreview) { alert("None of the selected assets have thumbnails."); return; }
    const label = currentComponentKind() === "scene" ? "Scene" : "Outfit";
    if (!(await comfyConfirm(`Delete ${withPreview.toLocaleString()} thumbnail${withPreview === 1 ? "" : "s"} from the selected ${label} assets? Their Library values stay intact.`, `Delete selected ${label} thumbnails?`))) return;
    try {
        const result = await request("/derived-values/bulk/previews/delete", { method: "POST", body: JSON.stringify({ component_ids: items.map(item => String(item.component_id || "")) }) });
        await load();
        catalogStatus(`Deleted ${Number(result.changed || withPreview).toLocaleString()} selected ${label} thumbnail${Number(result.changed || withPreview) === 1 ? "" : "s"}.`, "#ff9b5f");
    } catch (error) { alert(error.message || "Could not delete the selected thumbnails."); }
}

function regenerateSelectedComponentThumbnails() {
    const items = selectedComponentThumbnailAssets();
    if (!items.length) { alert("Select Outfit / Scene assets first."); return; }
    openCatalogRunDialogForItem(null, items);
}

function renderDerivedAssets(list, kind) {
    const assets = derivedEntries(kind);
    const pageSize = componentPageSize();
    const pageCount = Math.max(1, Math.ceil(assets.length / pageSize));
    componentPage[kind] = Math.max(0, Math.min(Number(componentPage[kind] || 0), pageCount - 1));
    const pageStart = componentPage[kind] * pageSize;
    const pageAssets = assets.slice(pageStart, pageStart + pageSize);
    renderComponentBrowseControls();
    if (!assets.length) {
        const empty = document.createElement("div");
        const searching = Boolean(String(componentSearch[kind] || "").trim()) || Boolean(activeCollection);
        empty.textContent = searching
            ? `No ${kind === "outfit" ? "outfits" : "scenes"} match this view.`
            : `No ${kind === "outfit" ? "outfits" : "scenes"} are in the Library yet. Use Build asset, import metadata-bearing Studio images, or save recipes that used ${kind} values.`;
        Object.assign(empty.style, { gridColumn: "1 / -1", padding: "42px", color: "#afa9b6", textAlign: "center" });
        list.append(empty);
        return;
    }
    for (const asset of pageAssets) {
        const componentId = String(asset.component_id || "");
        const selected = componentId && selectedComponentIds.has(componentId);
        const accent = kind === "outfit" ? "#ff4ab8" : "#63e6a4";
        const card = document.createElement("div");
        Object.assign(card.style, { minWidth: "0", minHeight: "0", height: "auto", alignSelf: "start", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden", border: selected ? `1px solid ${accent}` : `1px solid ${accent}55`, borderRadius: "10px", background: selected ? `linear-gradient(150deg,${accent}22,rgba(53,215,255,.05) 55%,rgba(10,9,14,.96))` : "linear-gradient(150deg,rgba(255,255,255,.035),rgba(10,9,14,.96))", boxShadow: selected ? `0 0 0 1px ${accent}33,0 10px 24px rgba(0,0,0,.30)` : "0 8px 22px rgba(0,0,0,.22)" });
        const preview = document.createElement("div");
        Object.assign(preview.style, { width: "100%", aspectRatio: kind === "outfit" ? "4 / 5" : "5 / 4", minHeight: "0", flex: "0 0 auto", position: "relative", overflow: "hidden", cursor: "pointer", background: kind === "outfit" ? "#050507" : "radial-gradient(circle at 18% 15%,#63e6a433,transparent 34%),radial-gradient(circle at 82% 20%,#35d7ff28,transparent 38%),#0b0910" });
        preview.role = "button"; preview.tabIndex = 0; preview.title = selectionMode ? `Select this ${kind}` : `Inspect this ${kind} and browse the current gallery scope`;
        const inspectComponent = () => { const itemIndex = Math.max(0, assets.findIndex(row => String(row.component_id || "") === componentId)); const structural = activeCollection && activeCollection !== "unfiled" ? componentCollectionById(kind, activeCollection) : null; const pack = (libraryCollections[kind] || []).find(row => String(row.collection_id || "") === String(activeLibraryCollection[kind] || "")); const scopeLabel = pack ? `Collection · ${pack.name}` : structural ? `Home · ${componentCollectionDisplayName(kind, structural)}` : activeCollection === "unfiled" ? "Home · Unsorted" : `All ${kind === "outfit" ? "Outfit Looks" : "Scenes"}`; openLibraryInspector({ kind, item: asset, index: itemIndex, total: assets.length, scopeLabel, fetchAt: async target => assets[target] || null }); };
        preview.onclick = () => selectionMode && componentId ? toggleComponentSelection(componentId) : inspectComponent();
        preview.onkeydown = event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); preview.click(); } };
        if (asset.preview_ref) {
            const image = document.createElement("img");
            image.loading = "lazy";
            image.decoding = "async";
            const previewSource = String(asset.preview_source || "");
            const componentBackedPreview = previewSource.startsWith("generated:catalog") || isCreativeLibraryPackPreviewSource(previewSource);
            image.src = creativeLibraryPreviewUrl(asset.preview_ref, asset.preview_updated_at || asset.updated_at || "");
            image.alt = asset.value;
            Object.assign(image.style, { width: "100%", height: "100%", objectFit: componentBackedPreview && kind === "outfit" ? "contain" : "cover", display: "block", background: componentBackedPreview && kind === "outfit" ? "#000000" : "transparent" });
            preview.append(image);
        }
        const badge = document.createElement("span");
        const generatedCatalogPreview = String(asset.preview_source || "").startsWith("generated:catalog");
        const importedPackPreview = isCreativeLibraryPackPreviewSource(asset.preview_source);
        badge.textContent = generatedCatalogPreview || importedPackPreview ? "CATALOG" : (asset.manual ? "LIBRARY" : "RECIPE");
        Object.assign(badge.style, { position: "absolute", left: "8px", top: "8px", padding: "3px 6px", borderRadius: "999px", color: "#fff", background: `${accent}cc`, font: "800 8px Segoe UI,Arial", letterSpacing: ".07em" });
        preview.append(badge);
        if (selectionMode && componentId) {
            const selector = document.createElement("button"); selector.type = "button"; selector.textContent = selected ? "✓" : ""; selector.setAttribute("aria-pressed", selected ? "true" : "false");
            Object.assign(selector.style, { position: "absolute", right: "8px", top: "8px", zIndex: "4", width: "28px", height: "28px", display: "grid", placeItems: "center", padding: "0", borderRadius: "8px", cursor: "pointer", border: `1px solid ${selected ? accent : "#35d7ffaa"}`, color: "#fff", background: selected ? `${accent}dd` : "rgba(8,7,12,.82)", boxShadow: "0 3px 12px rgba(0,0,0,.35)", font: "700 15px Segoe UI,Arial" });
            selector.onclick = event => { event.stopPropagation(); toggleComponentSelection(componentId); };
            preview.append(selector);
        }

        const body = document.createElement("div"); Object.assign(body.style, { padding: kind === "outfit" ? "10px 10px 11px" : "10px", display: "flex", flexDirection: "column", flex: "1 1 auto", minHeight: kind === "outfit" ? "154px" : "142px", gap: kind === "outfit" ? "7px" : "6px", position: "relative" });
        const value = document.createElement("strong"); value.textContent = asset.value; value.title = asset.value;
        Object.assign(value.style, { color: "#f5f1f7", display: "-webkit-box", WebkitLineClamp: "3", WebkitBoxOrient: "vertical", overflow: "hidden", minHeight: "43px", lineHeight: "1.32", fontSize: "11px" });
        const uses = Number(asset.uses || 0);
        const meta = document.createElement("div");
        meta.textContent = uses ? `${uses} Recipe use${uses === 1 ? "" : "s"}` : (asset.manual ? "Library asset" : "Recipe-derived");
        meta.title = `Managed master line ${Number(asset.index || 0) + 1}`;
        Object.assign(meta.style, { color: "#88818f", fontSize: "9px", lineHeight: "1.2" });
        const ratingRow = componentRatingButtons(asset, accent);

        const collectionChips = document.createElement("div"); Object.assign(collectionChips.style, { display: "flex", flexWrap: "nowrap", alignItems: "center", gap: "4px", minHeight: "17px", overflow: "hidden" });
        const shownCollections = (asset.collections || []).slice(0, 1);
        for (const collection of shownCollections) { const chip = document.createElement("span"); const displayName = componentCollectionDisplayName(kind, collection); chip.textContent = `HOME · ${displayName}`; chip.title = displayName; Object.assign(chip.style, { maxWidth: "125px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding: "2px 5px", borderRadius: "999px", border: `1px solid ${collection.color || accent}66`, color: collection.color || accent, font: "700 8px Segoe UI,Arial" }); collectionChips.append(chip); }
        if ((asset.collections || []).length > 1) { const moreChip = document.createElement("span"); moreChip.textContent = `+${asset.collections.length - 1}`; moreChip.title = (asset.collections || []).slice(1).map(collection => componentCollectionDisplayName(kind, collection)).join(", "); Object.assign(moreChip.style, { flex: "0 0 auto", padding: "2px 5px", borderRadius: "999px", color: "#aaa2b4", border: "1px solid #4a4452", font: "700 8px Segoe UI,Arial" }); collectionChips.append(moreChip); }
        const packCollection = (asset.pack_collections || [])[0];
        if (packCollection) { const chip = document.createElement("span"); chip.textContent = `COLLECTION · ${String(packCollection.name || "Collection")}`; chip.title = (asset.pack_collections || []).map(row => String(row.name || "")).filter(Boolean).join(", "); Object.assign(chip.style, { maxWidth: "135px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding: "2px 5px", borderRadius: "999px", border: `1px solid ${kind === "scene" ? "#63e6a4" : "#ff9b5f"}66`, color: kind === "scene" ? "#9df6c7" : "#ffc49f", font: "700 7px Segoe UI,Arial" }); collectionChips.append(chip); }

        const primary = document.createElement("div"); Object.assign(primary.style, { display: selectionMode ? "none" : "flex", gap: "5px", alignItems: "center", marginTop: "auto", minHeight: "29px" });
        const compactButton = (label, color, title) => {
            const button = action(label, color);
            button.title = title || label;
            Object.assign(button.style, { minWidth: "29px", height: "27px", padding: "0 7px", display: "grid", placeItems: "center", fontSize: "9px", lineHeight: "1", borderRadius: "7px", fontWeight: "800" });
            return button;
        };
        if (kind === "outfit") {
            const loadLabel = document.createElement("span"); loadLabel.textContent = "LOAD"; Object.assign(loadLabel.style, { color: "#8c8592", font: "800 8px Segoe UI,Arial", letterSpacing: ".08em", marginRight: "1px" });
            const loadA = compactButton("A", "#ff4ab8", "LOAD OUTFIT A");
            const loadB = compactButton("B", "#f6e65a", "Load into Outfit B");
            const loadC = compactButton("C", "#35d7ff", "Load into Outfit C");
            loadA.onclick = () => loadDerivedValue(asset, "A"); loadB.onclick = () => loadDerivedValue(asset, "B"); loadC.onclick = () => loadDerivedValue(asset, "C");
            primary.append(loadLabel, loadA, loadB, loadC);
        } else {
            const loadScene = compactButton("LOAD", "#63e6a4", "LOAD SCENE");
            Object.assign(loadScene.style, { minWidth: "48px" });
            loadScene.onclick = () => loadDerivedValue(asset);
            primary.append(loadScene);
        }
        const copy = compactButton("COPY", "#b89aff", kind === "outfit" ? "Copy outfit value" : "Copy scene value");
        Object.assign(copy.style, { minWidth: "46px", marginLeft: "auto" });
        copy.onclick = event => { event.stopPropagation(); void copyComponentValue(asset, copy); };
        primary.append(copy);

        const more = compactButton("•••", "#8f8997", "More actions");
        Object.assign(more.style, { minWidth: "30px", padding: "0 6px" });
        primary.append(more);

        const extras = document.createElement("div");
        Object.assign(extras.style, { display: "none", position: "absolute", right: "8px", bottom: "43px", zIndex: "12", minWidth: "126px", padding: "6px", flexDirection: "column", gap: "5px", borderRadius: "9px", border: `1px solid ${accent}66`, background: "rgba(12,10,16,.97)", boxShadow: "0 10px 28px rgba(0,0,0,.48)", backdropFilter: "blur(8px)" });
        const menuButton = (label, color) => { const button = action(label, color); Object.assign(button.style, { width: "100%", padding: "7px 8px", fontSize: "9px", textAlign: "left" }); return button; };
        if (componentId) {
            const edit = menuButton("EDIT VALUE", "#f6e65a"); edit.onclick = () => { extras.style.display = "none"; showComponentValueEditor(asset, kind); }; extras.append(edit);
            const collect = menuButton("COLLECTIONS", "#ff9b5f"); collect.onclick = () => { extras.style.display = "none"; void showLibraryAssetCollectionEditor(asset, kind); }; extras.append(collect);
            const organize = menuButton("MOVE HOME", "#b89aff"); organize.onclick = () => { extras.style.display = "none"; showComponentCollectionEditor(asset, kind); }; extras.append(organize);
            const deleteThumb = menuButton("DELETE THUMBNAIL", "#ff9b5f"); deleteThumb.disabled = !asset.preview_ref; deleteThumb.style.opacity = asset.preview_ref ? "1" : ".38"; deleteThumb.onclick = () => { extras.style.display = "none"; void deleteComponentThumbnail({ ...asset, kind }); }; extras.append(deleteThumb);
            const regenerateThumb = menuButton("REGENERATE THUMBNAIL", "#6ee7a2"); regenerateThumb.onclick = () => { extras.style.display = "none"; openCatalogRunDialogForItem(null, [{ ...asset, kind }]); }; extras.append(regenerateThumb);
        }
        if (kind === "scene" && componentId && activeCollection && activeCollection !== "unfiled") {
            const activeFolder = componentCollectionById("scene", activeCollection);
            if (activeFolder) {
                const removeHere = menuButton("REMOVE FROM THIS HOME", "#ffcf75");
                removeHere.onclick = async () => {
                    extras.style.display = "none";
                    const scopeIds = [...componentCollectionScopeIds("scene", activeCollection)].filter(Boolean);
                    if (!confirm(`Remove this Scene from Home “${activeFolder.name}”? The canonical Scene and preview stay in the Library.`)) return;
                    try { await request("/derived-values/bulk/collections/remove", { method: "POST", body: JSON.stringify({ component_ids: [componentId], collection_ids: scopeIds }) }); await load(); catalogStatus(`Removed Scene from ${activeFolder.name}; asset kept.`, "#ffcf75"); }
                    catch (error) { alert(error.message || "Could not remove this Scene from the Home."); }
                };
                extras.append(removeHere);
            }
        }
        const sourceRecipe = recipes.find(recipe => String(recipe.recipe_id) === String(asset.recipe_id));
        if (sourceRecipe) { const source = menuButton("SOURCE RECIPE", "#8f8997"); source.onclick = () => { extras.style.display = "none"; showDiff(sourceRecipe); }; extras.append(source); }
        if (asset.manual && componentId && kind !== "scene") {
            const removeAsset = menuButton("DELETE", "#ff4ab8"); removeAsset.onclick = async () => { extras.style.display = "none"; if (!confirm(`Remove this ${kind} from the manually built Library?${uses ? " It is also present in saved recipes, so the recipe-derived copy will remain." : ""}`)) return; try { await request(`/derived-values/${encodeURIComponent(componentId)}`, { method: "DELETE" }); await load(); catalogStatus(`Removed manual ${kind} asset.`, "#ff8fce"); } catch (error) { alert(error.message || `Could not remove this ${kind}.`); } }; extras.append(removeAsset);
        }
        if (componentId) {
            const deleteEverywhere = menuButton("DELETE EVERYWHERE", "#ff4f7b");
            deleteEverywhere.onclick = async () => {
                extras.style.display = "none";
                const label = kind === "outfit" ? "Outfit Look" : "Scene";
                if (!confirm(`DELETE EVERYWHERE for this ${label}? The canonical ${label} and its Catalog thumbnail will be removed. Saved Recipes keep provenance, but this value is tombstoned so old Recipes and source logs cannot silently recreate it.`)) return;
                try { const result = await request("/derived-values/bulk/delete", { method: "POST", body: JSON.stringify({ component_ids: [componentId], everywhere: true }) }); await load(); catalogStatus(`DELETE EVERYWHERE · ${result.deleted || 0} ${label} removed${Number(result.tombstoned || 0) ? " and tombstoned" : ""}.`, "#ff6d9d"); }
                catch (error) { alert(error.message || `Could not delete this ${label} everywhere.`); }
            };
            extras.append(deleteEverywhere);
        }
        more.onclick = event => { event.stopPropagation(); extras.style.display = extras.style.display === "none" ? "flex" : "none"; };
        body.append(value, meta, ratingRow, collectionChips, primary, extras); card.append(preview, body); list.append(card);
    }
}

function renderOutfitLooksLibrary(list) {
    const accent="#f6e65a"; const allLooks=derivedValues.outfits||[]; const groups=componentCollections.outfit||[];
    const { parents, children }=sceneTaxonomyTree("outfit");
    const workspace=document.createElement("div"); Object.assign(workspace.style,{gridColumn:"1 / -1",display:"grid",gridTemplateColumns:"210px minmax(0,1fr)",gap:"12px",alignItems:"start",minWidth:"0"});
    const sidebar=document.createElement("aside"); Object.assign(sidebar.style,{position:"sticky",top:"8px",maxHeight:"calc(100vh - 260px)",overflow:"auto",border:`1px solid ${accent}44`,borderRadius:"10px",background:"#0b0910"});
    const title=document.createElement("div"); title.textContent="HOME"; Object.assign(title.style,{position:"sticky",top:"0",zIndex:"2",padding:"10px",color:accent,background:"#0b0910",font:"900 9px Segoe UI,Arial",letterSpacing:".1em",borderBottom:"1px solid #302b35"}); sidebar.append(title);
    const sectionTitle=text=>{const node=document.createElement("div");node.textContent=text;Object.assign(node.style,{padding:"8px 9px 5px",color:"#8b8390",font:"900 7px Segoe UI,Arial",letterSpacing:".11em",borderBottom:"1px solid #242029",background:"rgba(255,255,255,.012)"});sidebar.append(node);};
    const nav=(label,count,handler,selected,depth=0)=>{const button=document.createElement("button");button.type="button";button.innerHTML=`<span>${depth?"↳&nbsp;&nbsp;":""}${escapeHtml(label)}</span><span>${Number(count||0).toLocaleString()}</span>`;Object.assign(button.style,{width:"100%",display:"flex",justifyContent:"space-between",gap:"8px",padding:depth?"7px 9px 7px 20px":"8px 9px",border:"0",borderBottom:"1px solid #242029",cursor:"pointer",textAlign:"left",color:selected?"#fff7a8":depth?"#9f98a5":"#b7b0bc",background:selected?"rgba(246,230,90,.10)":"transparent",font:depth?"650 8px Segoe UI,Arial":"750 9px Segoe UI,Arial"});button.onclick=handler;sidebar.append(button);};
    sectionTitle("COLLECTIONS");
    nav("＋ Manage collections",0,()=>showLibraryCollectionManager("outfit"),false);
    for(const group of libraryCollections.outfit||[]){const id=String(group.collection_id||"");nav(String(group.name||"Collection"),Number(group.asset_count||0),()=>{activeLibraryCollection.outfit=id;activeCollection="";componentPage.outfit=0;render();},String(activeLibraryCollection.outfit)===id,1);}
    sectionTitle("HOMES");
    nav("All Looks",allLooks.length,()=>{activeCollection="";activeLibraryCollection.outfit="";componentPage.outfit=0;render();},!activeCollection&&!activeLibraryCollection.outfit);
    const unsorted=allLooks.filter(asset=>!(asset.collections||[]).length).length; nav("Unsorted",unsorted,()=>{activeCollection="unfiled";activeLibraryCollection.outfit="";componentPage.outfit=0;render();},activeCollection==="unfiled");
    for(const group of parents){const id=String(group.collection_id||"");nav(String(group.name||"Category"),Number(group.asset_count||0),()=>{activeCollection=id;activeLibraryCollection.outfit="";componentPage.outfit=0;render();},String(activeCollection)===id);if(String(activeCollection)===id||(children.get(id)||[]).some(child=>String(child.collection_id||"")===String(activeCollection))){for(const child of children.get(id)||[]){const childId=String(child.collection_id||"");nav(String(child.name||"Subcategory"),Number(child.asset_count||0),()=>{activeCollection=childId;activeLibraryCollection.outfit="";componentPage.outfit=0;render();},String(activeCollection)===childId,1);}}}
    const manage=action("＋ MANAGE CATEGORIES",accent);Object.assign(manage.style,{width:"calc(100% - 16px)",margin:"8px",padding:"7px 8px",fontSize:"8px"});manage.onclick=()=>showComponentCollectionManager("outfit");sidebar.append(manage);
    const main=document.createElement("main");Object.assign(main.style,{minWidth:"0"}); const structural=activeCollection&&activeCollection!=="unfiled"?(groups.find(row=>String(row.collection_id||"")===String(activeCollection))):null; const structuralParent=structural&&String(structural.parent_id||"")?componentCollectionById("outfit",structural.parent_id):null; const pack=(libraryCollections.outfit||[]).find(row=>String(row.collection_id||"")===String(activeLibraryCollection.outfit)); const heading=document.createElement("div");heading.textContent=pack?`COLLECTION · ${pack.name}`:activeCollection==="unfiled"?"UNSORTED LOOKS":structural?`${structuralParent?`${structuralParent.name}  /  `:""}${String(structural.name||"COLLECTION")}`:"ALL OUTFIT LOOKS";Object.assign(heading.style,{margin:"1px 0 8px",color:pack?"#ff9b5f":accent,font:"900 9px Segoe UI,Arial",letterSpacing:".09em"});main.append(heading);
    const grid=document.createElement("div");Object.assign(grid.style,{display:"grid",gridTemplateColumns:"repeat(auto-fill,minmax(min(230px,100%),1fr))",gap:"14px",alignItems:"start",minWidth:"0"});renderDerivedAssets(grid,"outfit");main.append(grid);workspace.append(sidebar,main);list.append(workspace);
}

function renderSceneLibrary(list) {
    const accent = "#63e6a4";
    const allScenes = derivedValues.scenes || [];
    const unsortedCount = allScenes.filter(asset => !(asset.collections || []).length).length;
    const { parents, children } = sceneTaxonomyTree();
    const workspace = document.createElement("div");
    Object.assign(workspace.style, { gridColumn: "1 / -1", display: "grid", gridTemplateColumns: "190px minmax(0,1fr)", gap: "12px", alignItems: "start", minWidth: "0" });

    const sidebar = document.createElement("aside");
    Object.assign(sidebar.style, { position: "sticky", top: "8px", maxHeight: "calc(100vh - 260px)", overflow: "auto", border: `1px solid ${accent}44`, borderRadius: "10px", background: "#0b0910" });
    const sideTitle = document.createElement("div"); sideTitle.textContent = "SCENE HOMES";
    Object.assign(sideTitle.style, { position: "sticky", top: "0", zIndex: "2", padding: "10px", color: accent, background: "#0b0910", font: "900 9px Segoe UI,Arial", letterSpacing: ".1em", borderBottom: "1px solid #302b35" }); sidebar.append(sideTitle);
    const note = document.createElement("div"); note.textContent = "CATEGORY → SUBCATEGORY\nCreate and arrange your own categories";
    Object.assign(note.style, { whiteSpace: "pre-line", padding: "8px 10px", color: "#77717e", font: "700 7px/1.45 Segoe UI,Arial", letterSpacing: ".04em", borderBottom: "1px solid #242029" }); sidebar.append(note);
    const addNav = (label, count, id, depth = 0) => {
        const button = document.createElement("button"); button.type = "button";
        const selected = !activeLibraryCollection.scene && String(activeCollection || "") === String(id || "");
        button.innerHTML = `<span>${depth ? "↳&nbsp;&nbsp;" : ""}${escapeHtml(label)}</span><span>${Number(count || 0).toLocaleString()}</span>`;
        Object.assign(button.style, { width: "100%", display: "flex", justifyContent: "space-between", gap: "8px", padding: depth ? "7px 9px 7px 20px" : "8px 9px", border: "0", borderBottom: "1px solid #242029", cursor: "pointer", textAlign: "left", color: selected ? "#d8fff0" : depth ? "#9f98a5" : "#b7b0bc", background: selected ? "rgba(99,230,164,.11)" : "transparent", font: depth ? "650 8px Segoe UI,Arial" : "750 9px Segoe UI,Arial" });
        button.onclick = () => { activeCollection = String(id || ""); activeLibraryCollection.scene = ""; componentPage.scene = 0; selectedComponentIds.clear(); renderCollectionControls(); renderBulkControls(); render(); };
        sidebar.append(button);
    };
    addNav("All Scenes", allScenes.length, "");
    addNav("Unsorted", unsortedCount, "unfiled");
    for (const parent of parents) {
        const parentId = String(parent.collection_id || "");
        addNav(String(parent.name || "Category"), Number(parent.asset_count || 0), parentId);
        if (String(activeCollection || "") === parentId || (children.get(parentId) || []).some(child => String(child.collection_id || "") === String(activeCollection || ""))) {
            for (const child of children.get(parentId) || []) addNav(String(child.name || "Subcategory"), Number(child.asset_count || 0), String(child.collection_id || ""), 1);
        }
    }
    const manage = action("＋ MANAGE CATEGORIES", accent); manage.title = "Create, rename, move, or delete Scene Home categories and subcategories";
    Object.assign(manage.style, { width: "calc(100% - 16px)", margin: "8px", padding: "7px 8px", fontSize: "8px" }); manage.onclick = () => showComponentCollectionManager("scene"); sidebar.append(manage);
    const packTitle = document.createElement("div"); packTitle.textContent = "COLLECTIONS"; Object.assign(packTitle.style, { padding:"8px 9px 5px", color:"#8b8390", font:"900 7px Segoe UI,Arial", letterSpacing:".11em", borderTop:"1px solid #302b35", borderBottom:"1px solid #242029" }); sidebar.append(packTitle);
    for (const group of libraryCollections.scene || []) {
        const id = String(group.collection_id || ""); const selected = String(activeLibraryCollection.scene || "") === id; const button = document.createElement("button"); button.type="button"; button.innerHTML=`<span>${escapeHtml(String(group.name || "Collection"))}</span><span>${Number(group.asset_count || 0).toLocaleString()}</span>`; Object.assign(button.style,{width:"100%",display:"flex",justifyContent:"space-between",gap:"8px",padding:"8px 9px",border:"0",borderBottom:"1px solid #242029",cursor:"pointer",textAlign:"left",color:selected?"#d8fff0":"#b7b0bc",background:selected?"rgba(99,230,164,.11)":"transparent",font:"750 9px Segoe UI,Arial"}); button.onclick=()=>{activeLibraryCollection.scene=id;activeCollection="";componentPage.scene=0;selectedComponentIds.clear();render();}; sidebar.append(button);
    }
    const manageCollections = action("＋ MANAGE COLLECTIONS", "#ff9b5f"); Object.assign(manageCollections.style,{width:"calc(100% - 16px)",margin:"8px",padding:"7px 8px",fontSize:"8px"}); manageCollections.onclick=()=>showLibraryCollectionManager("scene"); sidebar.append(manageCollections);

    const main = document.createElement("main"); Object.assign(main.style, { minWidth: "0" });
    const active = activeCollection === "unfiled" ? null : componentCollectionById("scene", activeCollection);
    const heading = document.createElement("div");
    const activeParent = active && String(active.parent_id || "") ? componentCollectionById("scene", active.parent_id) : null;
    const activePack = (libraryCollections.scene || []).find(row => String(row.collection_id || "") === String(activeLibraryCollection.scene || ""));
    heading.textContent = activePack ? `COLLECTION · ${activePack.name}` : activeCollection === "unfiled" ? "UNSORTED" : active ? `${activeParent ? `${activeParent.name}  /  ` : ""}${active.name}` : "ALL SCENES";
    Object.assign(heading.style, { margin: "1px 0 8px", color: accent, font: "900 9px Segoe UI,Arial", letterSpacing: ".09em" }); main.append(heading);
    const grid = document.createElement("div"); Object.assign(grid.style, { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(250px,100%),1fr))", gap: "14px", alignItems: "start", minWidth: "0" });
    renderDerivedAssets(grid, "scene");
    main.append(grid); workspace.append(sidebar, main); list.append(workspace);
}

function wardrobePageSize() {
    const list = root?.querySelector("[data-recipes]");
    const width = Math.max(520, Number(list?.clientWidth || 1400) - (wardrobeBuilderOpen ? 570 : 285));
    const columns = Math.max(1, Math.floor((width + 12) / (210 + 12)));
    return Math.max(12, Math.min(80, columns * 4));
}

async function setWardrobeRating(item, nextRating) {
    const wardrobeId = String(item?.wardrobe_id || "");
    if (!wardrobeId) return;
    const previous = Math.max(0, Math.min(5, Number(item.rating || 0)));
    const rating = previous === Number(nextRating) ? 0 : Math.max(0, Math.min(5, Number(nextRating || 0)));
    item.rating = rating; render();
    try {
        await request(`/wardrobe-items/${encodeURIComponent(wardrobeId)}/rating`, { method: "POST", body: JSON.stringify({ rating }) });
        const canonical = wardrobeItems.find(row => String(row.wardrobe_id || "") === wardrobeId); if (canonical) canonical.rating = rating;
        catalogStatus(`Wardrobe rating ${rating ? `${rating}★` : "cleared"}.`, rating >= 4 ? "#f6e65a" : "#6ee7a2"); render();
    } catch (error) { item.rating = previous; render(); alert(error.message || "Could not save the wardrobe rating."); }
}

function wardrobeRatingButtons(item) {
    const row = document.createElement("div"); Object.assign(row.style, { display: "flex", alignItems: "center", gap: "1px", minHeight: "20px" });
    const current = Math.max(0, Math.min(5, Number(item.rating || 0)));
    for (let rating = 1; rating <= 5; rating += 1) {
        const star = document.createElement("button"); star.type = "button"; star.textContent = rating <= current ? "★" : "☆";
        Object.assign(star.style, { padding: "0 1px", border: "0", background: "transparent", color: rating <= current ? "#f6e65a" : "#655f6b", cursor: "pointer", font: "700 15px/1 Segoe UI Symbol,Segoe UI,Arial" });
        star.onclick = event => { event.stopPropagation(); void setWardrobeRating(item, rating); }; row.append(star);
    }
    const label = document.createElement("span"); label.textContent = current ? `${current}★` : "unrated"; Object.assign(label.style, { marginLeft: "4px", color: current >= 4 ? "#f6e65a" : "#817b88", font: "700 8px Segoe UI,Arial" }); row.append(label);
    return row;
}

function addBuilderItem(item) {
    const value = String(item?.value || "").trim(); if (!value) return;
    const key = `${String(item?.item_type || "piece")}:${value.toLocaleLowerCase()}`;
    if (!wardrobeBuilder.some(entry => `${String(entry.item_type || "piece")}:${String(entry.value || "").toLocaleLowerCase()}` === key)) wardrobeBuilder.push({ ...item, value });
    refreshOutfitModeBar(); render(); catalogStatus(`Added to Outfit Builder · ${value}`, "#f6e65a");
}
function removeBuilderItem(index) { wardrobeBuilder.splice(index, 1); refreshOutfitModeBar(); render(); }
function cleanBuilderAttribute(value) {
    return String(value || "").replace(/[\r\n,]+/g, " ").replace(/\s+/g, " ").trim();
}
function coloredBuilderValue(item) {
    const value = String(item?.value || "").trim();
    if (!value || ["finisher", "styling"].includes(String(item?.item_type || ""))) return value;
    const modifiers = [item?.builderColor, item?.builderPattern, item?.builderCut, item?.builderMaterial].map(cleanBuilderAttribute).filter(Boolean);
    const wear = cleanBuilderAttribute(item?.builderWear);
    const graphic = cleanBuilderAttribute(item?.builderGraphic);
    const article = value.match(/^(a|an|the)\s+/i);
    let assembled = modifiers.length ? (article ? `${article[0]}${modifiers.join(" ")} ${value.slice(article[0].length)}` : `${modifiers.join(" ")} ${value}`) : value;
    if (graphic) assembled = `${assembled} ${/^with\b/i.test(graphic) ? graphic : `with ${graphic}`}`;
    return wear ? `${assembled} ${wear}` : assembled;
}
function compiledBuilderValue() { return wardrobeBuilder.map(coloredBuilderValue).filter(Boolean).join(", "); }
function refreshBuilderOutputText() {
    const output = root?.querySelector?.("[data-wardrobe-builder-output]");
    if (output) output.value = compiledBuilderValue();
}
async function saveBuilderLook(destination = "") {
    const value = compiledBuilderValue();
    if (!value) { alert("Add at least one Piece, Set, or finisher to the Builder first."); return; }
    try {
        await request("/derived-values", { method: "POST", body: JSON.stringify({ kind: "outfit", value }) });
        await load();
        const asset = (derivedValues.outfits || []).find(item => String(item.value || "").toLocaleLowerCase() === value.toLocaleLowerCase());
        if (destination && asset) await loadDerivedValue(asset, destination);
        catalogStatus(destination ? `Saved build as a Look and loaded Outfit ${destination}.` : "Saved Builder result as a reusable Look.", "#f6e65a");
    } catch (error) { alert(error.message || "Could not save this Builder result."); }
}

function renderBuilderTray() {
    const listHost = root?.querySelector?.("[data-recipes]");
    const availableHeight = Math.max(430, Number(listHost?.clientHeight || 0) - 28);
    const tray = document.createElement("aside"); Object.assign(tray.style, { minWidth: "0", position: "sticky", top: "0", alignSelf: "start", height: `${availableHeight}px`, maxHeight: "calc(100vh - 290px)", display: "flex", flexDirection: "column", border: "1px solid #f6e65a66", borderRadius: "12px", background: "linear-gradient(160deg,rgba(246,230,90,.08),rgba(255,74,184,.04),#0b0910)", overflow: "hidden" });
    if (!wardrobeBuilderOpen) {
        const open = action(`BUILD · ${wardrobeBuilder.length}`, "#f6e65a"); open.title = "Open Outfit Builder"; Object.assign(open.style, { width: "100%", minHeight: "180px", padding: "10px 5px", writingMode: "vertical-rl", transform: "rotate(180deg)", letterSpacing: ".08em", fontSize: "9px" }); open.onclick = () => { wardrobeBuilderOpen = true; render(); }; tray.append(open); return tray;
    }
    const head = document.createElement("div"); Object.assign(head.style, { padding: "11px 12px", borderBottom: "1px solid #f6e65a44", display: "grid", gridTemplateColumns: "1fr auto", gap: "8px", alignItems: "start" });
    const titleWrap = document.createElement("div"); const title = document.createElement("strong"); title.textContent = `YOUR OUTFIT · ${wardrobeBuilder.length}`; Object.assign(title.style, { color: "#fff7a8", font: "900 12px Segoe UI,Arial", letterSpacing: ".06em" });
    const subtitle = document.createElement("div"); subtitle.textContent = "Selections stay here while you browse categories."; Object.assign(subtitle.style, { marginTop: "4px", color: "#918a96", fontSize: "9px" }); titleWrap.append(title, subtitle);
    const collapse = action("‹", "#8f8997"); collapse.title = "Collapse Builder"; Object.assign(collapse.style, { padding: "4px 8px", fontSize: "12px" }); collapse.onclick = () => { wardrobeBuilderOpen = false; render(); }; head.append(titleWrap, collapse); tray.append(head);
    const rows = document.createElement("div"); Object.assign(rows.style, { padding: "8px", display: "grid", gap: "6px", flex: "1 1 auto", minHeight: "120px", alignContent: "start", overflow: "auto" });
    if (!wardrobeBuilder.length) { const empty = document.createElement("div"); empty.textContent = "Pick Pieces or Sets from the gallery, then add optional Body Styling or an explicit finisher if the outfit needs one."; Object.assign(empty.style, { padding: "13px 8px", color: "#8f8997", fontSize: "10px", lineHeight: "1.45" }); rows.append(empty); }
    wardrobeBuilder.forEach((item, index) => {
        const row = document.createElement("div"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "7px", alignItems: "start", padding: "8px", borderRadius: "8px", background: "rgba(255,255,255,.025)", border: "1px solid #39333f" });
        const text = document.createElement("div"); const tag = document.createElement("span"); tag.textContent = String(item.item_type || "piece").toUpperCase(); Object.assign(tag.style, { display: "block", color: item.item_type === "finisher" ? "#ff9b5f" : item.item_type === "styling" ? "#b89aff" : "#35d7ff", font: "800 8px Segoe UI,Arial", marginBottom: "3px" }); const value = document.createElement("span"); value.textContent = coloredBuilderValue(item); value.dataset.wardrobeBuilderRowValue = ""; Object.assign(value.style, { color: "#f5f1f7", fontSize: "10px", lineHeight: "1.3" }); text.append(tag, value);
        if (!["finisher", "styling"].includes(String(item.item_type || ""))) {
            const attributes = document.createElement("div"); Object.assign(attributes.style, { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px", marginTop: "6px" });
            const attributeControl = (label, values, property, placeholder) => {
                const wrap = document.createElement("div"); Object.assign(wrap.style, { minWidth: "0" });
                const select = document.createElement("select"); select.title = `Optionally add ${label.toLowerCase()} without creating another Wardrobe record`; Object.assign(select.style, { minWidth: "0", width: "100%", padding: "5px 4px", borderRadius: "6px", color: item[property] ? "#fff7a8" : "#a49daa", background: "#111016", border: "1px solid #4a4452", font: "800 7px Segoe UI,Arial" });
                const automatic = document.createElement("option"); automatic.value = ""; automatic.textContent = `${label} · NONE`; select.append(automatic);
                for (const name of values) { const option = document.createElement("option"); option.value = name; option.textContent = name.toUpperCase(); select.append(option); }
                const custom = document.createElement("option"); custom.value = "__custom__"; custom.textContent = "CUSTOM…"; select.append(custom);
                const customFlag = `__${property}CustomOpen`;
                const current = cleanBuilderAttribute(item[property]);
                const currentIsPreset = values.includes(current);
                const customOpen = Boolean(item[customFlag]) || Boolean(current && !currentIsPreset);
                select.value = customOpen ? "__custom__" : currentIsPreset ? current : "";
                const input = document.createElement("input"); input.type = "text"; input.placeholder = placeholder; input.value = customOpen ? current : ""; Object.assign(input.style, { display: customOpen ? "block" : "none", boxSizing: "border-box", width: "100%", marginTop: "4px", padding: "5px 6px", borderRadius: "6px", color: "#fff", background: "#09080d", border: "1px solid #f6e65a55", outline: "none", font: "8px Segoe UI,Arial" });
                const liveRefresh = () => { value.textContent = coloredBuilderValue(item); refreshBuilderOutputText(); select.style.color = item[property] ? "#fff7a8" : "#a49daa"; };
                select.onchange = () => {
                    if (select.value === "__custom__") {
                        item[customFlag] = true;
                        if (values.includes(cleanBuilderAttribute(item[property]))) item[property] = "";
                        input.value = cleanBuilderAttribute(item[property]);
                        input.style.display = "block";
                        liveRefresh();
                        requestAnimationFrame(() => input.focus());
                        return;
                    }
                    item[customFlag] = false;
                    item[property] = cleanBuilderAttribute(select.value);
                    input.style.display = "none";
                    liveRefresh();
                };
                input.oninput = () => { item[property] = cleanBuilderAttribute(input.value); liveRefresh(); };
                input.onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); input.blur(); } };
                input.onblur = () => { item[property] = cleanBuilderAttribute(input.value); liveRefresh(); };
                wrap.append(select, input);
                return wrap;
            };
            attributes.append(
                attributeControl("COLOR", WARDROBE_COLORS, "builderColor", "Custom color / treatment"),
                attributeControl("PATTERN", WARDROBE_PATTERNS, "builderPattern", "Custom pattern / print"),
                attributeControl("CUT / FIT", WARDROBE_CUTS, "builderCut", "Custom cut / fit / length"),
                attributeControl("MATERIAL", WARDROBE_MATERIALS, "builderMaterial", "Custom fabric / material"),
                attributeControl("WEAR", WARDROBE_WEAR, "builderWear", "Custom layering / wear"),
                attributeControl("GRAPHIC / TEXT", WARDROBE_GRAPHICS, "builderGraphic", 'Custom graphic, logo, or text'),
            );
            text.append(attributes);
        }
        const remove = action("×", "#ff4ab8"); Object.assign(remove.style, { padding: "3px 7px", fontSize: "10px" }); remove.onclick = () => removeBuilderItem(index); row.append(text, remove); rows.append(row);
    }); tray.append(rows);
    const stylingItems = wardrobeItems.filter(item => String(item.item_type || "") === "styling");
    if (stylingItems.length) {
        const styling = document.createElement("div"); Object.assign(styling.style, { padding: "8px 10px", borderTop: "1px solid #2b2730" });
        const st = document.createElement("strong"); st.textContent = `BODY STYLING · ${stylingItems.length}`; Object.assign(st.style, { display: "block", color: "#b89aff", font: "800 8px Segoe UI,Arial", letterSpacing: ".07em", marginBottom: "6px" });
        const pickerRow = document.createElement("div"); Object.assign(pickerRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "5px" });
        const select = document.createElement("select"); Object.assign(select.style, { minWidth: "0", padding: "6px", borderRadius: "6px", color: "#fff", background: "#111016", border: "1px solid #4a4452", fontSize: "8px" });
        for (const item of [...stylingItems].sort((a,b) => String(a.value).localeCompare(String(b.value)))) { const option = document.createElement("option"); option.value = item.wardrobe_id; option.textContent = item.value; select.append(option); }
        const addStyle = action("+ ADD", "#b89aff"); Object.assign(addStyle.style, { padding: "5px 7px", fontSize: "8px" }); addStyle.onclick = () => { const item = stylingItems.find(entry => String(entry.wardrobe_id) === String(select.value)); if (item) addBuilderItem(item); };
        pickerRow.append(select, addStyle); styling.append(st, pickerRow); tray.append(styling);
    }
    const finishers = document.createElement("div"); Object.assign(finishers.style, { padding: "8px 10px", borderTop: "1px solid #2b2730" }); const ft = document.createElement("strong"); ft.textContent = "QUICK FINISHERS"; Object.assign(ft.style, { display: "block", color: "#ff9b5f", font: "800 8px Segoe UI,Arial", letterSpacing: ".07em", marginBottom: "6px" }); finishers.append(ft);
    const chips = document.createElement("div"); Object.assign(chips.style, { display: "flex", flexWrap: "wrap", gap: "5px" });
    for (const value of WARDROBE_FINISHERS) { const chip = action(`+ ${value}`, "#ff9b5f"); Object.assign(chip.style, { padding: "5px 7px", fontSize: "8px" }); chip.onclick = () => addBuilderItem({ item_type: "finisher", category: "Finishers", subtype: "", value }); chips.append(chip); } finishers.append(chips); tray.append(finishers);
    const output = document.createElement("div"); Object.assign(output.style, { padding: "10px", borderTop: "1px solid #2b2730" }); const label = document.createElement("strong"); label.textContent = "ASSEMBLED OUTFIT"; Object.assign(label.style, { display: "block", color: "#f6e65a", font: "800 8px Segoe UI,Arial", letterSpacing: ".07em", marginBottom: "6px" });
    const text = document.createElement("textarea"); text.dataset.wardrobeBuilderOutput = ""; text.readOnly = true; text.rows = 5; text.value = compiledBuilderValue(); text.placeholder = "Your assembled OUTFIT value appears here."; Object.assign(text.style, { width: "100%", boxSizing: "border-box", resize: "vertical", padding: "8px", borderRadius: "7px", border: "1px solid #4a4452", background: "#07070a", color: "#fff", font: "10px/1.4 Segoe UI,Arial" }); output.append(label, text);
    const actions = document.createElement("div"); Object.assign(actions.style, { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", marginTop: "8px" });
    const copy = action("COPY ALL", "#35d7ff"); copy.onclick = async () => { if (await copyLibraryValue(compiledBuilderValue())) catalogStatus("Copied assembled OUTFIT value.", "#35d7ff"); };
    const save = action("SAVE AS LOOK", "#f6e65a"); save.onclick = () => void saveBuilderLook();
    const loadA = action("LOAD OUTFIT A", "#ff4ab8"); loadA.onclick = () => void saveBuilderLook("A");
    const clear = action("CLEAR ALL", "#8f8997"); clear.onclick = () => { wardrobeBuilder = []; refreshOutfitModeBar(); render(); };
    actions.append(copy, save, loadA, clear); output.append(actions);
    const alt = document.createElement("div"); Object.assign(alt.style, { display: "flex", gap: "5px", marginTop: "6px" }); const b = action("LOAD B", "#f6e65a"), c = action("LOAD C", "#35d7ff"); b.onclick = () => void saveBuilderLook("B"); c.onclick = () => void saveBuilderLook("C"); Object.assign(b.style, { flex: "1", padding: "5px" }); Object.assign(c.style, { flex: "1", padding: "5px" }); alt.append(b, c); output.append(alt); tray.append(output);
    return tray;
}

function confirmWardrobePurge(itemCount) {
    return new Promise(resolve => {
        const { overlay, card } = collectionModal("PURGE WARDROBE", "620px");
        card.style.borderColor = "#ff4ab899";
        const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "10px" });
        const warning = document.createElement("div");
        warning.textContent = `This resets the derived Wardrobe layer: ${Number(itemCount || 0).toLocaleString()} Pieces/Sets/Body Styling items, their thumbnails and ratings, Look relationships, migration decisions, and imported Library Pack provenance.`;
        Object.assign(warning.style, { color: "#ffb5db", lineHeight: "1.5", fontSize: "11px" });
        const safe = document.createElement("div"); safe.textContent = "PRESERVED: original Outfit Looks, Look thumbnails, Collections, saved Recipes, source logs, and exported .soslibrary files."; Object.assign(safe.style, { color: "#6ee7a2", lineHeight: "1.45", font: "800 10px Segoe UI,Arial" });
        const hint = document.createElement("div"); hint.textContent = "Type PURGE below to confirm. Every Look will become eligible for fresh migration again."; Object.assign(hint.style, { color: "#aaa2b4", fontSize: "10px" });
        const input = document.createElement("input"); input.type = "text"; input.autocomplete = "off"; input.spellcheck = false; input.placeholder = "PURGE"; Object.assign(input.style, { width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: "7px", color: "#fff", background: "#09080d", border: "1px solid #ff4ab866", outline: "none", font: "12px Segoe UI,Arial" });
        const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
        const cancel = action("Cancel", "#8f8997"); const purge = action("PURGE WARDROBE", "#ff4ab8"); purge.disabled = true; purge.style.opacity = ".42";
        let settled = false; const finish = value => { if (settled) return; settled = true; overlay.remove(); resolve(value); };
        input.oninput = () => { const enabled = input.value.trim().toUpperCase() === "PURGE"; purge.disabled = !enabled; purge.style.opacity = enabled ? "1" : ".42"; };
        input.onkeydown = event => { if (event.key === "Escape") { event.preventDefault(); finish(false); } else if (event.key === "Enter" && !purge.disabled) { event.preventDefault(); finish(true); } };
        cancel.onclick = () => finish(false); purge.onclick = () => finish(true); overlay.addEventListener("pointerdown", event => { if (event.target === overlay) finish(false); });
        body.append(warning, safe, hint, input); footer.append(cancel, purge); card.append(body, footer); requestAnimationFrame(() => input.focus());
    });
}

async function purgeWardrobe() {
    if (catalogRun) { alert("Stop Preview Run before purging the Wardrobe."); return; }
    const itemCount = wardrobeItems.length;
    if (!await confirmWardrobePurge(itemCount)) { catalogStatus("Wardrobe purge cancelled.", "#f6e65a"); return; }
    try {
        catalogStatus("Purging Wardrobe…", "#ff9b5f");
        const result = await request("/wardrobe-items/purge", { method: "POST", body: JSON.stringify({ confirm: "PURGE" }) });
        wardrobeBuilder = []; wardrobeSearch = ""; wardrobeCategory = ""; wardrobeSubtype = ""; wardrobeReviewFilter = ""; wardrobePage = 0;
        await load();
        catalogStatus(`Wardrobe reset · ${Number(result.items || 0).toLocaleString()} items removed · ${Number(result.previews_deleted || 0).toLocaleString()} cached thumbnails deleted. Original Looks preserved.`, "#ff9b5f");
    } catch (error) {
        alert(error.message || "Could not purge the Wardrobe.");
    }
}

function confirmPromptLibraryPurge(kind, itemCount) {
    const isTemplate = kind === "template";
    const plural = isTemplate ? "TEMPLATES" : "PROMPTS";
    const accent = isTemplate ? "#ff4ab8" : "#35d7ff";
    const phrase = `PURGE ${plural}`;
    return new Promise(resolve => {
        const { overlay, card } = collectionModal(`CLEAR ${plural} LIBRARY`, "650px");
        card.style.borderColor = "#ff4ab899";
        const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "10px" });
        const warning = document.createElement("div");
        warning.textContent = `This permanently removes all ${Number(itemCount || 0).toLocaleString()} current ${isTemplate ? "Template" : "Prompt"} gallery records, their attached previews, ratings, manual Homes, archive state, and Collection memberships. This tab will be left empty until you import or create new content.`;
        Object.assign(warning.style, { color: "#ffb5db", lineHeight: "1.5", fontSize: "11px" });
        const safe = document.createElement("div");
        safe.textContent = `PRESERVED: ${isTemplate ? "Prompts" : "Templates"}, OUTFITS, SCENES, Wardrobe, LoRA Library, saved Recipes, and every thumbnail belonging to those libraries.${isTemplate ? "" : " Any folder still used by a saved Recipe also stays with that Recipe."} Use Clean Orphan Thumbnails separately for genuinely unreferenced files.`;
        Object.assign(safe.style, { color: "#6ee7a2", lineHeight: "1.45", font: "800 10px Segoe UI,Arial" });
        const hint = document.createElement("div"); hint.textContent = `Type ${phrase} below to confirm.`; Object.assign(hint.style, { color: "#aaa2b4", fontSize: "10px" });
        const input = document.createElement("input"); input.type = "text"; input.autocomplete = "off"; input.spellcheck = false; input.placeholder = phrase; Object.assign(input.style, { width: "100%", boxSizing: "border-box", padding: "9px 10px", borderRadius: "7px", color: "#fff", background: "#09080d", border: `1px solid ${accent}66`, outline: "none", font: "12px Segoe UI,Arial" });
        const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
        const cancel = action("Cancel", "#8f8997"); const purge = action(`CLEAR ${plural}`, "#ff4ab8"); purge.disabled = true; purge.style.opacity = ".42";
        let settled = false; const finish = value => { if (settled) return; settled = true; overlay.remove(); resolve(value); };
        input.oninput = () => { const enabled = input.value.trim().toUpperCase() === phrase; purge.disabled = !enabled; purge.style.opacity = enabled ? "1" : ".42"; };
        input.onkeydown = event => { if (event.key === "Escape") { event.preventDefault(); finish(false); } else if (event.key === "Enter" && !purge.disabled) { event.preventDefault(); finish(true); } };
        cancel.onclick = () => finish(false); purge.onclick = () => finish(true); overlay.addEventListener("pointerdown", event => { if (event.target === overlay) finish(false); });
        body.append(warning, safe, hint, input); footer.append(cancel, purge); card.append(body, footer); requestAnimationFrame(() => input.focus());
    });
}

async function purgePromptLibrary(kind) {
    if (catalogRun) { alert("Stop Preview Run before clearing this Library tab."); return; }
    const isTemplate = kind === "template";
    const plural = isTemplate ? "Templates" : "Prompts";
    const count = Number(promptCorpusTotals[kind] || (isTemplate ? promptBlueprintTotal : promptAssetTotal) || 0);
    if (!await confirmPromptLibraryPurge(kind, count)) { catalogStatus(`${plural} clear cancelled.`, "#f6e65a"); return; }
    try {
        catalogStatus(`Clearing ${plural}…`, "#ff9b5f");
        const result = await request("/prompt-assets/purge", { method: "POST", body: JSON.stringify({ kind, confirm: `PURGE ${kind.toUpperCase()}S` }) });
        activeCollection = ""; promptParent = ""; promptSubcategory = ""; promptLogPath = ""; promptLogLabel = ""; promptSearch = ""; promptPage = 0; promptRatingFilter = ""; promptPlaceholderFilters.clear(); promptFacetFilters = emptyPromptFacetFilters(); selectedPromptIds.clear(); promptSelectAllFiltered = false; promptSelectionMode = false;
        await load();
        const fresh = Number(promptCorpusTotals[kind] || 0);
        catalogStatus(`${plural} cleared · ${fresh.toLocaleString()} records remain · ${Number(result.previews_deleted || 0).toLocaleString()} attached thumbnails removed${Number(result.collections_deleted || 0) ? ` · ${Number(result.collections_deleted).toLocaleString()} Prompt-only folders removed` : ""}.`, "#6ee7a2");
    } catch (error) {
        alert(error.message || `Could not clear the ${plural} Library.`);
    }
}

async function bulkWardrobeDeleteSelected() {
    const ids = wardrobeSelectedIds();
    if (!ids.length) { alert("Select Wardrobe items first."); return; }
    if (!(await comfyConfirm(`Delete ${ids.length.toLocaleString()} selected Wardrobe item${ids.length === 1 ? "" : "s"}? Existing Outfit Looks stay intact.`, "Delete selected Wardrobe items?"))) return;
    try {
        const result = await request("/wardrobe-items/bulk", { method: "POST", body: JSON.stringify({ operation: "delete", wardrobe_ids: ids }) });
        resetWardrobeSelection(false);
        await load();
        catalogStatus(`Deleted ${Number(result.deleted || ids.length).toLocaleString()} Wardrobe item${Number(result.deleted || ids.length) === 1 ? "" : "s"}.`, "#ff78bd");
    } catch (error) { alert(error.message || "Could not delete the selected Wardrobe items."); }
}

async function bulkWardrobeDeletePreviews() {
    const ids = wardrobeSelectedIds();
    if (!ids.length) { alert("Select Wardrobe items first."); return; }
    const withPreview = wardrobeItems.filter(item => ids.includes(String(item.wardrobe_id || "")) && String(item.preview_ref || "")).length;
    if (!withPreview) { alert("None of the selected Wardrobe items have thumbnails."); return; }
    if (!(await comfyConfirm(`Delete ${withPreview.toLocaleString()} thumbnail${withPreview === 1 ? "" : "s"} from the selected Wardrobe items? The items themselves stay in the Library.`, "Delete selected thumbnails?"))) return;
    try {
        const result = await request("/wardrobe-items/bulk", { method: "POST", body: JSON.stringify({ operation: "delete_previews", wardrobe_ids: ids }) });
        resetWardrobeSelection(false);
        await load();
        catalogStatus(`Deleted ${Number(result.previews_deleted || withPreview).toLocaleString()} Wardrobe thumbnail${Number(result.previews_deleted || withPreview) === 1 ? "" : "s"}.`, "#ff9b5f");
    } catch (error) { alert(error.message || "Could not delete the selected thumbnails."); }
}

function addSelectedWardrobeToBuilder() {
    const ids = new Set(wardrobeSelectedIds());
    if (!ids.size) { alert("Select Wardrobe items first."); return; }
    let added = 0;
    for (const item of wardrobeItems) {
        if (!ids.has(String(item.wardrobe_id || ""))) continue;
        const value = String(item?.value || "").trim();
        if (!value) continue;
        const key = `${String(item?.item_type || "piece")}:${value.toLocaleLowerCase()}`;
        if (!wardrobeBuilder.some(entry => `${String(entry.item_type || "piece")}:${String(entry.value || "").toLocaleLowerCase()}` === key)) { wardrobeBuilder.push({ ...item, value }); added++; }
    }
    resetWardrobeSelection(false);
    wardrobeBuilderOpen = true;
    refreshOutfitModeBar();
    render();
    catalogStatus(`Added ${added.toLocaleString()} selected Wardrobe item${added === 1 ? "" : "s"} to Outfit Builder.`, "#f6e65a");
}

async function showBulkComponentCollectionEditor(kind) {
    const ids = [...selectedComponentIds];
    if (!ids.length) { alert("Select library assets first."); return; }
    try { await refreshLibraryCollectionKind(kind); } catch (error) {}
    const accent = libraryCollectionAccent(kind);
    const { card, close } = collectionModal(`COLLECT ${ids.length.toLocaleString()} ${libraryCollectionLabel(kind).toUpperCase()}`, "620px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "grid", gap: "8px", overflow: "auto" });
    const note = document.createElement("div"); note.textContent = "Choose one or more Collections. Existing memberships are preserved."; Object.assign(note.style, { color: "#b9b2c0", font: "10px/1.45 Segoe UI,Arial" }); body.append(note);
    const list = document.createElement("div"); Object.assign(list.style, { display: "grid", gap: "5px" }); body.append(list);
    const checks = new Map();
    const redraw = () => {
        const selected = new Set([...checks].filter(([, box]) => box.checked).map(([id]) => id));
        list.replaceChildren(); checks.clear();
        for (const collection of libraryCollections[kind] || []) {
            const row = document.createElement("label"); Object.assign(row.style, { display: "flex", alignItems: "center", gap: "8px", padding: "8px", border: "1px solid #302b35", borderRadius: "7px", cursor: "pointer" });
            const box = document.createElement("input"); box.type = "checkbox"; box.checked = selected.has(String(collection.collection_id || "")); checks.set(String(collection.collection_id || ""), box);
            const text = document.createElement("span"); text.textContent = `${collection.name} · ${Number(collection.asset_count || 0).toLocaleString()}`; Object.assign(text.style, { color: "#c9c1cf", font: "9px Segoe UI,Arial" });
            row.append(box, text); list.append(row);
        }
        if (!(libraryCollections[kind] || []).length) { const empty = document.createElement("div"); empty.textContent = "No Collections yet. Create one below."; Object.assign(empty.style, { color: "#f6e65a", padding: "8px", fontSize: "9px" }); list.append(empty); }
    };
    redraw();
    const createRow = document.createElement("div"); Object.assign(createRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "6px" });
    const input = document.createElement("input"); input.placeholder = `New ${libraryCollectionLabel(kind)} Collection`; Object.assign(input.style, { minWidth: "0", padding: "8px", borderRadius: "7px", border: `1px solid ${accent}55`, background: "#09080d", color: "#fff" });
    const create = action("+ CREATE", accent); create.onclick = async () => { const name = input.value.trim(); if (!name) return; create.disabled = true; try { const response = await request("/library-collections", { method: "POST", body: JSON.stringify({ kind: kind, name }) }); const createdId = String(response?.collection?.collection_id || ""); input.value = ""; await refreshLibraryCollectionKind(kind); redraw(); if (createdId && checks.has(createdId)) checks.get(createdId).checked = true; } catch (error) { alert(error.message || "Could not create the collection."); } finally { create.disabled = false; } };
    input.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); create.click(); } });
    createRow.append(input, create); body.append(createRow);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = close;
    const save = action("ADD TO COLLECTIONS", accent); save.onclick = async () => { const collectionIds = [...checks].filter(([, box]) => box.checked).map(([id]) => id); if (!collectionIds.length) { alert("Choose at least one Collection."); return; } save.disabled = true; try { const result = await request("/library-collections/bulk", { method: "POST", body: JSON.stringify({ kind: kind, asset_ids: ids, collection_ids: collectionIds }) }); await refreshLibraryCollectionKind(kind); selectedComponentIds.clear(); close(); await load(); catalogStatus(`Collected ${Number(result.assets || ids.length).toLocaleString()} library assets.`, accent); } catch (error) { alert(error.message || "Could not collect the selected library assets."); save.disabled = false; } };
    footer.append(cancel, save); card.append(body, footer);
}

async function showWardrobeBulkCollectionEditor() {
    const ids = wardrobeSelectedIds();
    if (!ids.length) { alert("Select Wardrobe items first."); return; }
    try { await refreshLibraryCollectionKind("wardrobe"); } catch (error) {}
    const accent = "#ff9b5f";
    const { card, close } = collectionModal(`COLLECT ${ids.length.toLocaleString()} WARDROBE ITEMS`, "620px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "grid", gap: "8px", overflow: "auto" });
    const note = document.createElement("div"); note.textContent = "Choose one or more Collections. Existing memberships are preserved."; Object.assign(note.style, { color: "#b9b2c0", font: "10px/1.45 Segoe UI,Arial" }); body.append(note);
    const list = document.createElement("div"); Object.assign(list.style, { display: "grid", gap: "5px" }); body.append(list);
    const checks = new Map();
    const redraw = () => {
        list.replaceChildren(); checks.clear();
        for (const collection of libraryCollections.wardrobe || []) {
            const row = document.createElement("label"); Object.assign(row.style, { display: "flex", alignItems: "center", gap: "8px", padding: "8px", border: "1px solid #302b35", borderRadius: "7px", cursor: "pointer" });
            const box = document.createElement("input"); box.type = "checkbox"; checks.set(String(collection.collection_id || ""), box);
            const text = document.createElement("span"); text.textContent = `${collection.name} · ${Number(collection.asset_count || 0).toLocaleString()}`; Object.assign(text.style, { color: "#c9c1cf", font: "9px Segoe UI,Arial" });
            row.append(box, text); list.append(row);
        }
        if (!(libraryCollections.wardrobe || []).length) { const empty = document.createElement("div"); empty.textContent = "No Collections yet. Create one below."; Object.assign(empty.style, { color: "#f6e65a", padding: "8px", fontSize: "9px" }); list.append(empty); }
    };
    redraw();
    const createRow = document.createElement("div"); Object.assign(createRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "6px" });
    const input = document.createElement("input"); input.placeholder = "New Wardrobe Collection"; Object.assign(input.style, { minWidth: "0", padding: "8px", borderRadius: "7px", border: `1px solid ${accent}55`, background: "#09080d", color: "#fff" });
    const create = action("+ CREATE", accent); create.onclick = async () => { const name = input.value.trim(); if (!name) return; create.disabled = true; try { const response = await request("/library-collections", { method: "POST", body: JSON.stringify({ kind: "wardrobe", name }) }); const createdId = String(response?.collection?.collection_id || ""); input.value = ""; await refreshLibraryCollectionKind("wardrobe"); redraw(); if (createdId && checks.has(createdId)) checks.get(createdId).checked = true; } catch (error) { alert(error.message || "Could not create the collection."); } finally { create.disabled = false; } };
    input.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); create.click(); } });
    createRow.append(input, create); body.append(createRow);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = close;
    const save = action("ADD TO COLLECTIONS", accent); save.onclick = async () => { const collectionIds = [...checks].filter(([, box]) => box.checked).map(([id]) => id); if (!collectionIds.length) { alert("Choose at least one Collection."); return; } save.disabled = true; try { const result = await request("/library-collections/bulk", { method: "POST", body: JSON.stringify({ kind: "wardrobe", asset_ids: ids, collection_ids: collectionIds }) }); await refreshLibraryCollectionKind("wardrobe"); resetWardrobeSelection(false); close(); await load(); catalogStatus(`Collected ${Number(result.assets || ids.length).toLocaleString()} Wardrobe items.`, accent); } catch (error) { alert(error.message || "Could not collect the selected Wardrobe items."); save.disabled = false; } };
    footer.append(cancel, save); card.append(body, footer);
}

function renderWardrobePieces(list, builderMode = false) {
    const allRows = wardrobeEntries();
    const pageSize = wardrobePageSize(); const pageCount = Math.max(1, Math.ceil(allRows.length / pageSize)); wardrobePage = Math.max(0, Math.min(wardrobePage, pageCount - 1));
    const pageRows = allRows.slice(wardrobePage * pageSize, wardrobePage * pageSize + pageSize);
    const workspace = document.createElement("div"); Object.assign(workspace.style, { display: "grid", gridTemplateColumns: builderMode ? `190px minmax(0,1fr) ${wardrobeBuilderOpen ? "330px" : "48px"}` : "190px minmax(0,1fr)", gap: "12px", alignItems: "start" });
    const sidebar = document.createElement("aside"); Object.assign(sidebar.style, { position: "sticky", top: "8px", maxHeight: "calc(100vh - 260px)", overflow: "auto", border: "1px solid #3b3541", borderRadius: "10px", background: "#0b0910" });
    const sideTitle = document.createElement("div"); sideTitle.textContent = "BROWSE"; Object.assign(sideTitle.style, { position: "sticky", top: "0", zIndex: "2", padding: "10px", color: "#f6e65a", background: "#0b0910", font: "900 9px Segoe UI,Arial", letterSpacing: ".1em", borderBottom: "1px solid #302b35" }); sidebar.append(sideTitle);
    const sectionTitle = (text, color = "#8b8390") => { const node = document.createElement("div"); node.textContent = text; Object.assign(node.style, { padding: "9px 9px 5px", color, font: "900 7px Segoe UI,Arial", letterSpacing: ".11em", borderBottom: "1px solid #242029", background: "rgba(255,255,255,.012)" }); sidebar.append(node); };
    const folderButton = (label, count, selected, depth, handler) => { const button = document.createElement("button"); button.type = "button"; button.innerHTML = `<span>${depth ? "↳&nbsp;&nbsp;" : ""}${escapeHtml(label)}</span><span>${Number(count || 0).toLocaleString()}</span>`; Object.assign(button.style, { width: "100%", display: "flex", justifyContent: "space-between", gap: "8px", padding: depth ? "7px 9px 7px 21px" : "8px 9px", border: "0", borderBottom: "1px solid #242029", borderLeft: selected ? "3px solid #f6e65a" : "3px solid transparent", cursor: "pointer", textAlign: "left", color: selected ? "#fff7a8" : depth ? "#99929e" : "#b7b0bc", background: selected ? "rgba(246,230,90,.10)" : "transparent", font: `${selected ? "800" : "650"} ${depth ? "8" : "9"}px Segoe UI,Arial` }); button.onclick = handler; sidebar.append(button); };
    const galleryItems = wardrobeItems.filter(item => ["piece", "set"].includes(String(item.item_type || "piece")));
    const categories = ["", ...new Set([...Object.keys(WARDROBE_TAXONOMY), ...galleryItems.map(item => String(item.category || "Uncategorized"))])];
    sectionTitle("COLLECTIONS", "#ff9b5f");
    folderButton("＋ New Collection", 0, false, 0, () => showLibraryCollectionManager("wardrobe"));
    for (const collection of libraryCollections.wardrobe || []) {
        const id = String(collection.collection_id || "");
        folderButton(String(collection.name || "Collection"), Number(collection.asset_count || 0), String(activeLibraryCollection.wardrobe || "") === id, 1, () => { activeLibraryCollection.wardrobe = id; wardrobeCategory = ""; wardrobeSubtype = ""; wardrobePage = 0; resetWardrobeSelection(true); render(); });
    }
    sectionTitle("HOMES", "#f6e65a");
    for (const categoryName of categories) {
        const count = categoryName ? galleryItems.filter(item => String(item.category || "Uncategorized") === categoryName).length : galleryItems.length;
        folderButton(categoryName || "All Wardrobe", count, wardrobeCategory === categoryName && !wardrobeSubtype && !activeLibraryCollection.wardrobe, 0, () => { wardrobeCategory = categoryName; wardrobeSubtype = ""; activeLibraryCollection.wardrobe = ""; wardrobePage = 0; resetWardrobeSelection(true); render(); });
        if (categoryName && wardrobeCategory === categoryName && !activeLibraryCollection.wardrobe) {
            const known = new Set([...(WARDROBE_TAXONOMY[categoryName] || []), ...galleryItems.filter(item => String(item.category || "Uncategorized") === categoryName).map(item => String(item.subtype || "Uncategorized"))]);
            for (const subtypeName of known) {
                const subtypeCount = galleryItems.filter(item => String(item.category || "Uncategorized") === categoryName && String(item.subtype || "Uncategorized") === subtypeName).length;
                if (!subtypeCount) continue;
                folderButton(subtypeName, subtypeCount, wardrobeSubtype === subtypeName, 1, () => { wardrobeSubtype = subtypeName; wardrobePage = 0; resetWardrobeSelection(true); render(); });
            }
        }
    }
    const managePackCollections=action("＋ MANAGE COLLECTIONS","#ff9b5f");Object.assign(managePackCollections.style,{width:"calc(100% - 16px)",margin:"8px",padding:"7px 8px",fontSize:"8px"});managePackCollections.onclick=()=>showLibraryCollectionManager("wardrobe");sidebar.append(managePackCollections);
    const main = document.createElement("main"); Object.assign(main.style, { minWidth: "0" });
    const top = document.createElement("div"); Object.assign(top.style, { display: "flex", gap: "6px", flexWrap: "wrap", alignItems: "center", marginBottom: "8px" });
    const search = document.createElement("input"); search.dataset.libraryFocusKey = "wardrobe-piece-search"; search.type = "search"; search.placeholder = "Search pieces…"; search.value = wardrobeSearch; Object.assign(search.style, { width: "190px", padding: "7px 9px", borderRadius: "7px", color: "#fff", background: "#111016", border: "1px solid #4a4452", outline: "none", font: "10px Segoe UI,Arial" }); search.oninput = () => { wardrobeSearch = search.value; wardrobePage = 0; resetWardrobeSelection(true); render(); };
    const ratings = makeSelect([["", "All ratings"], ["unrated", "Unrated"], ["5", "5★ only"], ["4plus", "4★ +"], ["3plus", "3★ +"], ["low", "1–2★"]], wardrobeRatingFilter); Object.assign(ratings.style, { width: "120px", padding: "7px", fontSize: "10px" }); ratings.onchange = () => { wardrobeRatingFilter = ratings.value; wardrobePage = 0; resetWardrobeSelection(true); render(); };
    const thumbs = makeSelect([["", "All previews"], ["missing", "Missing preview"], ["catalog", "Catalog preview"]], wardrobeThumbnailFilter); Object.assign(thumbs.style, { width: "130px", padding: "7px", fontSize: "10px" }); thumbs.onchange = () => { wardrobeThumbnailFilter = thumbs.value; wardrobePage = 0; resetWardrobeSelection(true); render(); };
    const review = makeSelect([["", "All items"], ["needs_review", "Needs cleanup"], ["compound", "Possible multi-item"], ["generic", "Too generic"]], wardrobeReviewFilter); Object.assign(review.style, { width: "138px", padding: "7px", fontSize: "10px" }); review.title = "Audit Pieces already in the Wardrobe for older-parser composites or vague visual assets"; review.onchange = () => { wardrobeReviewFilter = review.value; wardrobePage = 0; resetWardrobeSelection(true); render(); };
    const sort = makeSelect([["preview_newest", "Newest preview"], ["recent", "Recently added"], ["name", "A → Z"], ["rating", "Highest rated"]], wardrobeSort); Object.assign(sort.style, { width: "130px", padding: "7px", fontSize: "10px" }); sort.onchange = () => { wardrobeSort = sort.value; wardrobePage = 0; render(); };
    const selectMode = action(wardrobeSelectionMode ? "DONE SELECTING" : "SELECT MULTIPLE", "#35d7ff"); Object.assign(selectMode.style, { padding: "7px 9px", fontSize: "9px" }); selectMode.onclick = () => { wardrobeSelectionMode = !wardrobeSelectionMode; if (!wardrobeSelectionMode) resetWardrobeSelection(true); render(); };
    const add = action("+ ADD ITEM", "#f6e65a"); Object.assign(add.style, { padding: "7px 9px", fontSize: "9px", marginLeft: "auto" }); add.onclick = () => showWardrobeItemBuilder({ category: wardrobeCategory, subtype: wardrobeSubtype });
    top.append(search, ratings, thumbs, review, sort, selectMode, add); main.append(top);
    if (wardrobeSelectionMode) {
        const bulk = document.createElement("div"); Object.assign(bulk.style, { display: "flex", flexWrap: "wrap", gap: "6px", alignItems: "center", margin: "0 0 8px", padding: "7px 8px", borderRadius: "8px", border: "1px solid #35d7ff44", background: "rgba(53,215,255,.045)" });
        const selectPage = action("SELECT PAGE", "#35d7ff"); selectPage.onclick = () => { for (const item of pageRows) if (item.wardrobe_id) selectedWardrobeIds.add(String(item.wardrobe_id)); wardrobeSelectAllFiltered = false; render(); };
        const selectAll = action(`SELECT ALL ${allRows.length.toLocaleString()}`, "#35d7ff"); selectAll.onclick = () => { wardrobeSelectAllFiltered = true; selectedWardrobeIds.clear(); render(); };
        const collect = action("COLLECT", "#ff9b5f"); collect.onclick = () => void showWardrobeBulkCollectionEditor();
        const build = action("+ BUILDER", "#f6e65a"); build.onclick = addSelectedWardrobeToBuilder;
        const deleteThumbs = action("DELETE THUMBS", "#ff9b5f"); deleteThumbs.onclick = () => void bulkWardrobeDeletePreviews();
        const remove = action("DELETE ITEMS", "#ff4ab8"); remove.onclick = () => void bulkWardrobeDeleteSelected();
        const status = document.createElement("span"); status.textContent = `${wardrobeSelectionCount().toLocaleString()} selected`; Object.assign(status.style, { color: "#bcefff", font: "800 9px Segoe UI,Arial", marginLeft: "2px" });
        bulk.append(selectPage, selectAll, collect, build, deleteThumbs, remove, status); main.append(bulk);
    }
    const location = document.createElement("div"); location.textContent = activeLibraryCollection.wardrobe ? `Collection / ${(libraryCollections.wardrobe || []).find(item => String(item.collection_id || "") === String(activeLibraryCollection.wardrobe))?.name || "Collection"}` : `Home / ${[wardrobeCategory || "All Wardrobe", wardrobeSubtype].filter(Boolean).join(" / ")}`; Object.assign(location.style, { marginBottom: "8px", color: "#eee8f0", font: "800 10px Segoe UI,Arial" }); main.append(location);
    const rangeRow = document.createElement("div"); Object.assign(rangeRow.style, { display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "8px", color: "#8f8997", fontSize: "9px" }); const label = document.createElement("span"); const start = allRows.length ? wardrobePage * pageSize + 1 : 0, end = Math.min(allRows.length, (wardrobePage + 1) * pageSize); label.textContent = `${start.toLocaleString()}–${end.toLocaleString()} of ${allRows.length.toLocaleString()}`; const nav = document.createElement("div"); Object.assign(nav.style, { display: "flex", gap: "5px" }); const prev = action("←", "#8f8997"), next = action("→", "#8f8997"); prev.disabled = wardrobePage <= 0; next.disabled = wardrobePage >= pageCount - 1; prev.onclick = () => { wardrobePage--; render(); }; next.onclick = () => { wardrobePage++; render(); }; Object.assign(prev.style, { padding: "4px 9px" }); Object.assign(next.style, { padding: "4px 9px" }); nav.append(prev, next); rangeRow.append(label, nav); main.append(rangeRow);
    const grid = document.createElement("div"); Object.assign(grid.style, { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(195px,100%),1fr))", gap: "10px", alignItems: "stretch" });
    if (!pageRows.length) { const empty = document.createElement("div"); empty.textContent = wardrobeItems.length ? "No wardrobe pieces match this Home or filter." : "No Pieces yet. Your existing Outfit values are preserved as Looks. Use MIGRATE LOOKS to harvest Pieces safely, add Pieces manually, or import a .soslibrary pack."; Object.assign(empty.style, { gridColumn: "1/-1", padding: "44px 20px", textAlign: "center", color: "#9b94a1", lineHeight: "1.5" }); grid.append(empty); }
    for (const item of pageRows) {
        const wardrobeId = String(item.wardrobe_id || "");
        const selected = Boolean(wardrobeId && (wardrobeSelectAllFiltered || selectedWardrobeIds.has(wardrobeId)));
        const card = document.createElement("div"); Object.assign(card.style, { minWidth: "0", height: "100%", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden", borderRadius: "9px", border: selected ? "2px solid #35d7ff" : "1px solid #f6e65a44", background: selected ? "linear-gradient(160deg,rgba(53,215,255,.11),#0b0910)" : "linear-gradient(160deg,rgba(246,230,90,.04),#0b0910)" });
        const preview = document.createElement("div"); Object.assign(preview.style, { width: "100%", aspectRatio: "4 / 5", flex: "0 0 auto", position: "relative", overflow: "hidden", background: "#000", cursor: "pointer" });
        preview.role = "button"; preview.tabIndex = 0; preview.title = wardrobeSelectionMode ? "Select this Wardrobe item" : "Inspect this Wardrobe item and browse the current gallery scope";
        const inspectWardrobe = () => { const itemIndex = Math.max(0, allRows.findIndex(row => String(row.wardrobe_id || "") === wardrobeId)); const collection = (libraryCollections.wardrobe || []).find(row => String(row.collection_id || "") === String(activeLibraryCollection.wardrobe || "")); const scopeLabel = collection ? `Collection · ${collection.name}` : `Home · ${[wardrobeCategory || "All Wardrobe", wardrobeSubtype].filter(Boolean).join(" / ")}`; openLibraryInspector({ kind: "piece", item, index: itemIndex, total: allRows.length, scopeLabel, fetchAt: async target => allRows[target] || null }); };
        preview.onclick = () => wardrobeSelectionMode && wardrobeId ? toggleWardrobeSelection(wardrobeId) : inspectWardrobe();
        preview.onkeydown = event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); preview.click(); } };
        if (item.preview_ref) { const img = document.createElement("img"); img.loading = "lazy"; img.decoding = "async"; img.src = creativeLibraryPreviewUrl(item.preview_ref, item.preview_updated_at || item.updated_at || ""); img.alt = item.value; Object.assign(img.style, { width: "100%", height: "100%", objectFit: "contain", display: "block", background: "#000" }); preview.append(img); }
        const badge = document.createElement("span"); badge.textContent = String(item.item_type || "piece").toUpperCase(); Object.assign(badge.style, { position: "absolute", left: "7px", top: "7px", padding: "3px 6px", borderRadius: "99px", background: item.item_type === "set" ? "#b89affdd" : "#f6e65add", color: item.item_type === "piece" ? "#16120b" : "#fff", font: "900 7px Segoe UI,Arial", letterSpacing: ".06em" }); preview.append(badge);
        const reviewFlags = Array.isArray(item.review_flags) ? item.review_flags : [];
        if (reviewFlags.length) { const check = document.createElement("span"); check.textContent = reviewFlags.includes("compound") ? "CHECK · MULTI" : "CHECK · GENERIC"; check.title = reviewFlags.includes("compound") ? "This existing Piece may contain more than one independently wearable item." : "This existing Piece may be too vague for a stable visual thumbnail."; Object.assign(check.style, { position: "absolute", right: "7px", top: wardrobeSelectionMode ? "42px" : "7px", padding: "3px 6px", borderRadius: "99px", background: "#ff9b5fe6", color: "#1a0f08", font: "900 7px Segoe UI,Arial", letterSpacing: ".04em" }); preview.append(check); }
        if (wardrobeSelectionMode && wardrobeId) {
            const selector = document.createElement("button"); selector.type = "button"; selector.textContent = selected ? "✓" : ""; selector.setAttribute("aria-pressed", selected ? "true" : "false");
            Object.assign(selector.style, { position: "absolute", right: "7px", top: "7px", zIndex: "4", width: "28px", height: "28px", display: "grid", placeItems: "center", padding: "0", borderRadius: "8px", cursor: "pointer", border: selected ? "1px solid #35d7ff" : "1px solid #35d7ffaa", color: "#fff", background: selected ? "rgba(53,215,255,.88)" : "rgba(8,7,12,.82)", boxShadow: "0 3px 12px rgba(0,0,0,.35)", font: "700 15px Segoe UI,Arial" });
            selector.onclick = event => { event.stopPropagation(); toggleWardrobeSelection(wardrobeId); }; preview.append(selector);
        }
        card.append(preview);
        const body = document.createElement("div"); Object.assign(body.style, { padding: "8px", minHeight: "118px", flex: "1 1 auto", display: "flex", flexDirection: "column", gap: "5px" });
        const value = document.createElement("strong"); value.textContent = item.value; value.title = item.value; Object.assign(value.style, { color: "#f5f1f7", display: "-webkit-box", WebkitLineClamp: "3", WebkitBoxOrient: "vertical", overflow: "hidden", fontSize: "10px", lineHeight: "1.3", minHeight: "39px" });
        const meta = document.createElement("div"); meta.textContent = [item.category, item.subtype].filter(Boolean).join(" · "); Object.assign(meta.style, { color: "#8f8997", fontSize: "8px", lineHeight: "1.25", minHeight: "20px", display: "-webkit-box", WebkitLineClamp: "2", WebkitBoxOrient: "vertical", overflow: "hidden" });
        const rating = wardrobeRatingButtons(item);
        const buttons = document.createElement("div"); Object.assign(buttons.style, { display: wardrobeSelectionMode ? "none" : "grid", gridTemplateColumns: "1fr 42px 30px 30px", gap: "5px", marginTop: "auto" });
        const addBuild = action("+ BUILD", "#f6e65a"); addBuild.title = "Add to Outfit Builder";
        const loadButton = action("LOAD", "#b89aff"); loadButton.title = "Load as Outfit A manual value in Prompt Core";
        const copy = action("⧉", "#35d7ff"); copy.title = "Copy wardrobe value";
        const more = action("•••", "#8f8997"); more.title = "More actions";
        for (const button of [addBuild, loadButton, copy, more]) Object.assign(button.style, { minWidth: "0", padding: "5px 6px", fontSize: [addBuild, loadButton].includes(button) ? "8px" : "11px" });
        addBuild.onclick = () => addBuilderItem(item);
        loadButton.onclick = () => void loadWardrobeValue(item, "A");
        copy.onclick = async () => { const previous = copy.textContent; if (await copyLibraryValue(item.value)) { copy.textContent = "✓"; catalogStatus("Copied wardrobe value.", "#35d7ff"); window.setTimeout(() => { copy.textContent = previous; }, 700); } else alert("Could not copy this wardrobe value."); };
        const menu = document.createElement("div"); Object.assign(menu.style, { display: "none", position: "absolute", right: "8px", bottom: "39px", zIndex: "8", padding: "6px", borderRadius: "8px", border: "1px solid #ff4ab866", background: "#121017", boxShadow: "0 8px 24px rgba(0,0,0,.5)", minWidth: "146px" });
        const menuAction = (label, color, handler) => { const button = action(label, color); Object.assign(button.style, { padding: "6px 9px", fontSize: "8px", width: "100%", marginBottom: "5px" }); button.onclick = handler; return button; };
        const edit = menuAction("EDIT ITEM", "#b89aff", () => { menu.style.display = "none"; showWardrobeItemEditor(item); });
        const loadB = menuAction("LOAD AS OUTFIT B", "#b89aff", () => { menu.style.display = "none"; void loadWardrobeValue(item, "B"); });
        const loadC = menuAction("LOAD AS OUTFIT C", "#b89aff", () => { menu.style.display = "none"; void loadWardrobeValue(item, "C"); });
        const collect = menuAction("COLLECTIONS", "#ff9b5f", () => { menu.style.display = "none"; void showLibraryAssetCollectionEditor(item, "wardrobe"); });
        const regenerate = menuAction("REGENERATE THUMBNAIL", "#f6e65a", () => { menu.style.display = "none"; openCatalogRunDialogForItem(item); });
        const clearPreview = item.preview_ref ? menuAction("DELETE THUMBNAIL", "#ff9b5f", async () => {
            menu.style.display = "none";
            if (!(await comfyConfirm(`Delete the thumbnail for “${item.value}”? The Wardrobe item stays intact.`, "Delete Wardrobe thumbnail?"))) return;
            await request(`/wardrobe-items/${encodeURIComponent(item.wardrobe_id)}/preview`, { method: "DELETE" });
            item.preview_ref = ""; item.preview_source = ""; item.catalog_preview_ref = ""; item.preview_updated_at = "";
            recoverTextInputFocus();
            render(); catalogStatus("Deleted Wardrobe thumbnail. The item is ready for a fresh preview.", "#ff9b5f");
        }) : null;
        const remove = menuAction("DELETE ITEM", "#ff4ab8", async () => {
            if (!(await comfyConfirm(`Delete wardrobe item “${item.value}”? Existing Looks are not affected.`, "Delete Wardrobe item?"))) return;
            await request(`/wardrobe-items/${encodeURIComponent(item.wardrobe_id)}`, { method: "DELETE" });
            recoverTextInputFocus();
            await load(); catalogStatus("Deleted wardrobe item.", "#ff78bd");
        });
        remove.style.marginBottom = "0";
        menu.append(edit, loadB, loadC, collect, regenerate); if (clearPreview) menu.append(clearPreview); menu.append(remove);
        more.onclick = event => { event.stopPropagation(); menu.style.display = menu.style.display === "none" ? "block" : "none"; };
        buttons.append(addBuild, loadButton, copy, more); body.append(value, meta, rating, buttons); card.append(body, menu); grid.append(card);
    }
    main.append(grid); workspace.append(sidebar, main); if (builderMode) workspace.append(renderBuilderTray()); list.append(workspace);
}

function promptAssetSeedSource(asset) {
    const source = String(asset?.resolved_seed_source || "").trim().toLowerCase();
    return ["imported-image", "preview-image"].includes(source) ? source : "";
}

function promptAssetResolvedSeed(asset) {
    if (!promptAssetSeedSource(asset)) return null;
    const attachedSeed = Number(asset?.resolved_seed);
    return Number.isInteger(attachedSeed) && attachedSeed >= 0 && attachedSeed <= 1125899906842624 ? attachedSeed : null;
}

function promptAssetSourceText(asset) {
    return String(asset?.source_value || asset?.value || "").trim();
}

function promptAssetResolvedText(asset) {
    const source = promptAssetSourceText(asset);
    const resolved = String(asset?.resolved_value || "").trim();
    return resolved && resolved.toLocaleLowerCase() !== source.toLocaleLowerCase() ? resolved : "";
}

function promptAssetText(asset, mode = "source") {
    return mode === "resolved" && promptAssetResolvedText(asset)
        ? promptAssetResolvedText(asset)
        : promptAssetSourceText(asset);
}

function applyPromptAsset(asset, options = {}) {
    const promptNode = findStudioNode("SOPromptLogEngineStudio");
    if (!promptNode) { alert("Add a Studio Prompt Core node before loading this prompt."); return { changed: 0, seedApplied: false }; }
    const manual = studioWidget(promptNode, "manual_prompt");
    const source = studioWidget(promptNode, "prompt_source");
    if (!manual) { alert("The current Prompt Core does not expose its manual prompt field."); return { changed: 0, seedApplied: false }; }
    if (isConnected(promptNode, manual)) { alert("Manual prompt is connected on Prompt Core, so Creative Library left it untouched."); return { changed: 0, seedApplied: false }; }
    let changed = 0;
    if (source && !isConnected(promptNode, source) && source.value !== "manual") { source.value = "manual"; try { source.callback?.("manual"); } catch (error) {} changed++; }
    manual.value = String(options.promptText ?? asset?.value ?? ""); try { manual.callback?.(manual.value); } catch (error) {} changed++;
    promptNode.setDirtyCanvas?.(true, true);

    const savedSeed = promptAssetResolvedSeed(asset);
    let seedApplied = false; let seedBlocked = false;
    if (options.applySeed === true && savedSeed != null) {
        const generationNode = findStudioNode("SOGenerationPipelineStudio");
        const seedWidget = studioWidget(generationNode, "seed_value");
        if (seedWidget && !isConnected(generationNode, seedWidget)) {
            setStudioWidget(generationNode, "seed_value", savedSeed); seedApplied = true;
        } else seedBlocked = true;
    }
    return { changed, savedSeed, seedApplied, seedBlocked };
}

async function submitPromptAssetToQueue(asset, button = null, announce = true, queuePosition = 0) {
    if (typeof app.queuePrompt !== "function") throw new Error("Queueing is unavailable in this ComfyUI build.");
    const promptNode = findStudioNode("SOPromptLogEngineStudio");
    // A connected Prompt input no longer blocks Library queue overrides because
    // Prompt Core now has a dedicated Input source. The temporary Manual source
    // selected below is authoritative for this queued run, then the user's source
    // choice is restored immediately afterward.
    const sourceWidget = studioWidget(promptNode, "prompt_source");
    const manualWidget = studioWidget(promptNode, "manual_prompt");
    const backgroundDraft = {
        prompt_source: sourceWidget?.value,
        manual_prompt: manualWidget?.value,
    };
    const result = applyPromptAsset(asset, { applySeed: false });
    if (!result.changed) return false;
    if (button) button.textContent = "QUEUING…";
    try {
        // Queue with the Library asset temporarily loaded so the execution graph
        // receives the correct prompt. Prompt Core's backend then rewrites the
        // embedded workflow snapshot to this runtime value before Output Core
        // saves it, making a later image reimport truthful as well.
        await Promise.resolve(app.queuePrompt(queuePosition, 1));
    } finally {
        // QUEUE is intentionally non-destructive to the user's working draft.
        // LOAD remains the explicit action for replacing visible Prompt Core state.
        if (sourceWidget && backgroundDraft.prompt_source !== undefined) setStudioWidget(promptNode, "prompt_source", backgroundDraft.prompt_source);
        if (manualWidget && backgroundDraft.manual_prompt !== undefined) setStudioWidget(promptNode, "manual_prompt", backgroundDraft.manual_prompt);
        promptNode?.setDirtyCanvas?.(true, true);
    }
    if (button) {
        button.textContent = "QUEUED ✓";
        window.setTimeout(() => { if (button.isConnected) { button.textContent = button.dataset.queueLabel || "QUEUE"; button.disabled = false; } }, 1100);
    }
    if (announce) catalogStatus(`${queuePosition === -1 ? "Queued next" : "Queued"} prompt using the current workflow seed: ${asset.name || "Prompt"}`, "#6ee7a2");
    return true;
}

function queuePromptAsset(asset, button, queuePosition = 0) {
    if (promptFolderQueueActive) { alert("A Prompt scope is already being added to the queue."); return promptCardQueueChain; }
    button.disabled = true;
    promptCardQueueChain = promptCardQueueChain
        .catch(() => undefined)
        .then(() => submitPromptAssetToQueue(asset, button, true, queuePosition))
        .catch(error => {
            button.textContent = button.dataset.queueLabel || "QUEUE";
            button.disabled = false;
            alert(error?.message || "Could not queue this prompt.");
        });
    return promptCardQueueChain;
}

function currentPromptFolderLabel() {
    if (activeCollection) return promptShowcaseFolders().find(item => String(item.collection_id) === String(activeCollection))?.name || "Collection";
    return [promptParent || (activePromptKind() === "template" ? "All Templates" : "All Prompts"), promptSubcategory, promptLogLabel].filter(Boolean).join(" / ");
}

function activePromptSource(asset) {
    if (!promptLogPath) return null;
    const target = String(promptLogPath || "").replaceAll("\\", "/").toLocaleLowerCase();
    return (asset?.sources || []).find(source => String(source?.source_path || "").replaceAll("\\", "/").toLocaleLowerCase() === target) || null;
}

async function fetchPromptQueueScope() {
    const params = promptPageParams();
    params.set("kind", activePromptKind());
    params.set("offset", "0");
    params.set("limit", "0");
    params.set("include_all", "1");
    // The cap limits how many matching records we fetch/submit, not whether a
    // larger folder is allowed to queue. This keeps huge leaf folders usable.
    params.set("max_results", String(PROMPT_QUEUE_CAP));
    return request(`/prompt-assets?${params.toString()}`);
}

async function openPromptFolderQueueDialog() {
    if (promptFolderQueueActive) return;
    const kindLabel = activePromptKind() === "template" ? "Templates" : "Prompts";
    if (!promptParent && !promptLogPath && !activeCollection) { alert(`Choose a Home or Collection first. All ${kindLabel} can never be queued as one batch.`); return; }
    let data;
    try {
        catalogStatus("Checking this Prompt scope…", "#f6e65a");
        data = await fetchPromptQueueScope();
    } catch (error) { alert(error.message || "Could not read this Prompt scope."); return; }
    const total = Math.max(0, Number(data?.total || 0));
    const items = (Array.isArray(data?.prompts) ? data.prompts : []).slice(0, PROMPT_QUEUE_CAP);
    const queueCount = items.length;
    const capped = total > queueCount;
    const label = currentPromptFolderLabel();
    const { overlay, card } = collectionModal(`QUEUE ${activePromptKind() === "template" ? "TEMPLATE" : "PROMPT"} SCOPE`, "700px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "15px", display: "flex", flexDirection: "column", gap: "12px" });
    const title = document.createElement("strong"); title.textContent = label; Object.assign(title.style, { color: "#fff", font: "900 17px Segoe UI,Arial" });
    const itemNoun = activePromptKind() === "template" ? "template" : "prompt";
    const count = document.createElement("div"); count.textContent = `${total.toLocaleString()} ${itemNoun}${total === 1 ? "" : "s"} match the current Home or Collection and filters.`; Object.assign(count.style, { color: capped ? "#f6e65a" : "#6ee7a2", font: "800 12px Segoe UI,Arial" });
    const copy = document.createElement("div"); copy.textContent = capped
        ? `This scope is larger than the ${PROMPT_QUEUE_CAP}-prompt safety cap, so only the first ${queueCount.toLocaleString()} matching prompts will be queued and then it will stop. After that batch finishes, run this again to continue with the next matching prompts.`
        : "Each prompt will use the workflow exactly as it is currently configured. Scope Queue never changes Generation Core's seed; every submission uses whatever seed behavior is already active in the workflow.";
    Object.assign(copy.style, { padding: "11px", borderRadius: "9px", border: `1px solid ${capped ? "#f6e65a66" : "#35d7ff55"}`, color: "#bdb5c4", font: "11px/1.5 Segoe UI,Arial" });
    body.append(title, count, copy);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 15px 15px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const startLabel = capped ? `QUEUE FIRST ${queueCount.toLocaleString()}` : `QUEUE ${queueCount.toLocaleString()} ${itemNoun.toUpperCase()}${queueCount === 1 ? "" : "S"}`;
    const start = action(startLabel, "#6ee7a2"); start.disabled = !queueCount; start.style.opacity = start.disabled ? ".4" : "1";
    start.onclick = () => {
        start.disabled = true; cancel.disabled = true; promptFolderQueueActive = true; overlay.remove(); render();
        promptCardQueueChain = promptCardQueueChain.catch(() => undefined).then(async () => {
            let queued = 0;
            try {
                for (const asset of items) {
                    if (!await submitPromptAssetToQueue(asset, null, false)) throw new Error("A Prompt could not be loaded safely, so the remaining folder queue was stopped.");
                    queued += 1;
                    catalogStatus(`Queueing ${label} · ${queued.toLocaleString()}/${queueCount.toLocaleString()}`, "#f6e65a");
                }
                catalogStatus(capped
                    ? `Queued first ${queued.toLocaleString()} of ${total.toLocaleString()} matching prompts from ${label}. Safety cap reached; run again after this batch finishes to continue.`
                    : `Queued all ${queued.toLocaleString()} prompts from ${label}.`, "#6ee7a2");
            } finally { promptFolderQueueActive = false; render(); }
        }).catch(error => { promptFolderQueueActive = false; alert(error?.message || "Could not finish queueing this scope."); render(); });
    };
    footer.append(cancel, start); card.append(body, footer);
}

function showPromptApply(asset) {
    const { overlay, card } = collectionModal(`LOAD PROMPT · ${asset.name || "Prompt"}`, "820px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "15px", display: "flex", flexDirection: "column", gap: "12px", overflow: "auto" });
    const sourceText = promptAssetSourceText(asset);
    const resolvedText = promptAssetResolvedText(asset);
    let promptMode = "source";
    const intro = document.createElement("div"); intro.textContent = resolvedText
        ? "Choose the reusable source or the exact OUTFIT / SCENE combination captured with this thumbnail."
        : asset.builder_ready
            ? "This Blueprint loads into Manual mode with its exact uppercase portable hooks intact."
            : "This loads the canonical Prompt into Manual mode without changing component-log controls.";
    Object.assign(intro.style, { color: "#b8b0c1", fontSize: "12px", lineHeight: "1.5" });
    const promptBox = document.createElement("div"); Object.assign(promptBox.style, { padding: "14px", borderRadius: "9px", border: "1px solid #35d7ff66", background: "rgba(53,215,255,.045)", color: "#f5f1f7", whiteSpace: "pre-wrap", wordBreak: "break-word", font: "12px/1.5 Consolas,monospace", maxHeight: "330px", overflow: "auto" });
    const versionPanel = document.createElement("div"); Object.assign(versionPanel.style, { display: "grid", gridTemplateColumns: resolvedText ? "1fr 1fr" : "1fr", gap: "7px" });
    const versionRows = [];
    const versionChoice = (mode, labelText, detailText, color) => {
        const row = document.createElement("label"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "18px minmax(0,1fr)", gap: "7px", alignItems: "start", padding: "9px", borderRadius: "8px", border: `1px solid ${color}55`, cursor: "pointer", background: "rgba(255,255,255,.018)" });
        const radio = document.createElement("input"); radio.type = "radio"; radio.name = `prompt-version-${String(asset.prompt_id || Math.random())}`; radio.checked = mode === "source";
        const copy = document.createElement("div"); copy.innerHTML = `<strong style="color:${color}">${labelText}</strong><div style="margin-top:3px;color:#8f8997;font:9px/1.4 Segoe UI,Arial">${detailText}</div>`;
        radio.onchange = () => { if (!radio.checked) return; promptMode = mode; promptBox.textContent = promptAssetText(asset, promptMode); for (const [candidate, shell] of versionRows) shell.style.background = candidate.checked ? `${color}12` : "rgba(255,255,255,.018)"; };
        row.append(radio, copy); versionRows.push([radio, row]); return row;
    };
    versionPanel.append(versionChoice("source", "SOURCE · REUSABLE", "Keeps OUTFIT and SCENE placeholders for Prompt Core to resolve.", "#35d7ff"));
    if (resolvedText) versionPanel.append(versionChoice("resolved", "THUMBNAIL COMBINATION", "Uses the captured OUTFIT and SCENE text shown by this thumbnail.", "#6ee7a2"));
    promptBox.textContent = sourceText;
    const protectedBox = document.createElement("div"); protectedBox.innerHTML = `<strong style="color:#f6e65a">NAME + BRAND ALWAYS STAY PORTABLE</strong><div style="margin-top:5px;color:#a9a1b2">Neither choice will restore a saved identity or brand value. A resolved variant is only offered when those hooks remain literal placeholders.</div>`; Object.assign(protectedBox.style, { padding: "10px 11px", borderRadius: "9px", border: "1px solid #f6e65a44", fontSize: "11px", lineHeight: "1.4" });
    body.append(intro, versionPanel, promptBox, protectedBox);

    const savedSeed = promptAssetResolvedSeed(asset);
    let useSavedSeed = false;
    const seedPanel = document.createElement("div"); Object.assign(seedPanel.style, { display: "grid", gap: "7px", padding: "10px 11px", borderRadius: "9px", border: "1px solid #3b3541", background: "rgba(255,255,255,.018)" });
    const seedTitle = document.createElement("strong"); seedTitle.textContent = "SEED BEHAVIOR"; Object.assign(seedTitle.style, { color: "#35d7ff", font: "900 9px Segoe UI,Arial", letterSpacing: ".08em" }); seedPanel.append(seedTitle);
    const choice = (labelText, detailText, saved = false) => {
        const row = document.createElement("label"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "18px 1fr", gap: "7px", alignItems: "start", padding: "8px", borderRadius: "7px", border: "1px solid #332e38", cursor: "pointer" });
        const radio = document.createElement("input"); radio.type = "radio"; radio.name = `prompt-seed-${String(asset.prompt_id || Math.random())}`; radio.checked = !saved;
        const text = document.createElement("div"); text.innerHTML = `<strong style="color:${saved ? "#6ee7a2" : "#f2edf4"}">${labelText}</strong><div style="margin-top:3px;color:#918997;font:9px/1.4 Segoe UI,Arial">${detailText}</div>`;
        radio.onchange = () => { if (radio.checked) useSavedSeed = saved; }; row.append(radio, text); return row;
    };
    seedPanel.append(choice("USE EXISTING WORKFLOW SEED", "Default. Loading the Prompt leaves Generation Core's current seed and randomization behavior exactly as it is."));
    if (savedSeed != null) {
        const origin = promptAssetSeedSource(asset) === "imported-image" ? "an imported image" : "a Preview image";
        seedPanel.append(choice(`USE SAVED SEED · ${savedSeed}`, `Optional. This seed was captured from ${origin}. It is applied only for this Load action, and only when Generation Core's seed input is not connected.`, true));
    } else {
        const note = document.createElement("div"); note.textContent = "No trusted saved seed is attached to this Prompt. Preview-run seeds, legacy seed 0 values, and ordinary TXT-file records are intentionally ignored."; Object.assign(note.style, { color: "#77717d", font: "9px/1.4 Segoe UI,Arial", padding: "2px 3px" }); seedPanel.append(note);
    }
    body.append(seedPanel);

    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 15px 15px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const load = action("Load prompt", "#35d7ff"); load.onclick = () => {
        const result = applyPromptAsset(asset, { applySeed: useSavedSeed, promptText: promptAssetText(asset, promptMode) });
        if (!result.changed) return;
        const seedNote = result.seedApplied ? ` · saved seed ${result.savedSeed}` : " · workflow seed unchanged";
        catalogStatus(`Loaded ${promptMode === "resolved" ? "thumbnail combination" : "source prompt"}: ${asset.name || "Prompt"}${seedNote}`);
        if (useSavedSeed && result.seedBlocked && result.savedSeed != null) alert(`Prompt loaded, but Generation Core's seed input is connected, so saved seed ${result.savedSeed} was not applied.`);
        overlay.remove();
    };
    foot.append(cancel, load); card.append(body, foot);
}

function openPromptVault(filters = {}) {
    if (filters.blueprint || filters.kind === "template") activeView = "recipes";
    else if (filters.kind === "prompt") activeView = "prompts";
    promptVaultOpen = true;
    resetPromptNavigation();
    if (filters.signature) promptPlaceholderFilters = new Set(String(filters.signature).split("+").filter(Boolean));
    promptParent = String(filters.parent || "");
    promptSubcategory = String(filters.subcategory || "");
    for (const axis of PROMPT_FACET_AXES) if (filters[axis]) promptFacetFilters[axis] = String(filters[axis]);
    selectionMode = false;
    selectedRecipeIds.clear();
    refreshLibraryChrome();
    renderCollectionControls();
    renderBulkControls();
    render();
    queuePromptPageLoad();
}

function closePromptVault() {
    promptVaultOpen = true;
    resetPromptNavigation();
    selectionMode = false;
    selectedRecipeIds.clear();
    promptLoadSerial += 1;
    if (promptLoadTimer) { clearTimeout(promptLoadTimer); promptLoadTimer = null; }
    promptLoading = false;
    promptAssets = [];
    promptTotal = promptAssetTotal;
    refreshLibraryChrome();
    renderCollectionControls();
    renderBulkControls();
    render();
}

function renderPromptDiscovery(list) {
    const shell = document.createElement("section"); shell.dataset.promptDiscovery = "";
    Object.assign(shell.style, { gridColumn: "1 / -1", minWidth: "0", padding: "clamp(18px,2.4vw,34px)", borderRadius: "18px", border: "1px solid #35d7ff55", background: "radial-gradient(circle at 12% 5%,rgba(53,215,255,.13),transparent 27%),radial-gradient(circle at 88% 7%,rgba(255,74,184,.11),transparent 31%),linear-gradient(145deg,#11101a,#09080d 70%)", boxShadow: "0 18px 55px rgba(0,0,0,.28)" });
    const hero = document.createElement("div"); Object.assign(hero.style, { display: "flex", alignItems: "flex-end", flexWrap: "wrap", gap: "13px", marginBottom: "18px" });
    const copy = document.createElement("div"); copy.style.flex = "1";
    const eyebrow = document.createElement("div"); eyebrow.textContent = "PROMPT GALLERIES"; Object.assign(eyebrow.style, { color: "#35d7ff", font: "900 10px Segoe UI,Arial", letterSpacing: ".16em" });
    const headline = document.createElement("h2"); headline.textContent = "Shop the archive by idea."; Object.assign(headline.style, { margin: "7px 0 5px", color: "#fff", font: "900 clamp(24px,3vw,38px)/1.05 Segoe UI,Arial", letterSpacing: "-.02em" });
    const intro = document.createElement("p"); intro.textContent = `${promptAssetTotal.toLocaleString()} canonical Prompts stay safely in the Vault. Every Prompt has one navigation home; filter facets never duplicate or relocate it.`; Object.assign(intro.style, { maxWidth: "820px", margin: "0", color: "#b9b1c2", font: "12px/1.55 Segoe UI,Arial" });
    copy.append(eyebrow, headline, intro);
    const blueprint = action(`CORPUS BLUEPRINTS · ${Number(promptBlueprintTotal || 0).toLocaleString()}`, "#ff4ab8"); Object.assign(blueprint.style, { padding: "10px 13px", borderWidth: "2px", background: "rgba(255,74,184,.10)" }); blueprint.onclick = () => openPromptVault({ blueprint: true });
    const full = action(`FULL VAULT · ${promptAssetTotal.toLocaleString()}`, "#35d7ff"); Object.assign(full.style, { padding: "10px 13px", borderWidth: "2px", background: "rgba(53,215,255,.10)" }); full.onclick = () => openPromptVault();
    hero.append(copy, blueprint, full); shell.append(hero);

    const fallbackPalettes = [
        ["#ff4ab8", "#6b1cff", "#091126"], ["#35d7ff", "#1464ff", "#150824"], ["#f6e65a", "#ff6b2c", "#190a18"],
        ["#63e6a4", "#00a9a5", "#10071d"], ["#b89aff", "#ff4ab8", "#071521"], ["#ff9b5f", "#f6e65a", "#14081b"],
    ];
    for (const [familyIndex, family] of PROMPT_GALLERY_FAMILIES.entries()) {
        const counts = promptFacetCounts?.[family.axis] || {};
        const dynamic = Object.keys(counts).filter(label => label !== "Other" && !family.values.includes(label));
        const values = [...family.values, ...dynamic].filter(label => Number(counts[label] || 0) > 0);
        if (!values.length) continue;
        const shelf = document.createElement("section"); Object.assign(shelf.style, { minWidth: "0", marginTop: familyIndex ? "17px" : "0", paddingTop: familyIndex ? "15px" : "0", borderTop: familyIndex ? "1px solid #302b36" : "0" });
        const shelfHead = document.createElement("div"); Object.assign(shelfHead.style, { display: "flex", alignItems: "baseline", gap: "9px", marginBottom: "8px" });
        const label = document.createElement("strong"); label.textContent = family.label; Object.assign(label.style, { color: family.color, font: "900 10px Segoe UI,Arial", letterSpacing: ".13em" });
        const hint = document.createElement("span"); hint.textContent = "CLICK A FOLDER TO OPEN ITS PROMPTS"; Object.assign(hint.style, { color: "#716b77", font: "700 7px Segoe UI,Arial", letterSpacing: ".07em" }); shelfHead.append(label, hint); shelf.append(shelfHead);
        const rail = document.createElement("div"); Object.assign(rail.style, { display: "flex", alignItems: "stretch", gap: "9px", overflowX: "auto", padding: "1px 1px 7px" });
        values.forEach((labelText, index) => {
            const count = Number(counts[labelText] || 0);
            const button = document.createElement("button"); button.type = "button";
            Object.assign(button.style, { flex: "0 0 170px", minWidth: "170px", padding: "0", overflow: "hidden", borderRadius: "11px", cursor: "pointer", textAlign: "left", color: "#fff", border: `1px solid ${family.color}55`, background: "#0c0a10", boxShadow: "0 8px 22px rgba(0,0,0,.22)" });
            const cover = document.createElement("div"); Object.assign(cover.style, { position: "relative", height: "94px", overflow: "hidden", background: "#0a0810" });
            const previewRef = String(promptFacetCovers?.[family.axis]?.[labelText] || "");
            if (previewRef) { const image = document.createElement("img"); image.loading = "lazy"; image.decoding = "async"; image.src = creativeLibraryPreviewUrl(previewRef); image.alt = ""; Object.assign(image.style, { width: "100%", height: "100%", objectFit: "cover", display: "block" }); cover.append(image); }
            else {
                const palette = fallbackPalettes[(familyIndex + index) % fallbackPalettes.length];
                cover.style.background = `radial-gradient(circle at 18% 15%,${palette[0]}cc,transparent 34%),radial-gradient(circle at 82% 25%,${palette[1]}aa,transparent 40%),repeating-linear-gradient(125deg,transparent 0 13px,rgba(255,255,255,.035) 13px 14px),linear-gradient(150deg,${palette[2]},#050409)`;
                const monogram = document.createElement("span"); monogram.textContent = labelText.split(/\s+/).map(word => word[0]).join("").slice(0, 3).toUpperCase(); Object.assign(monogram.style, { position: "absolute", right: "9px", bottom: "4px", color: "rgba(255,255,255,.18)", font: "900 31px/1 Segoe UI,Arial", letterSpacing: "-.06em" }); cover.append(monogram);
            }
            const body = document.createElement("div"); Object.assign(body.style, { padding: "9px 10px 10px" });
            const name = document.createElement("strong"); name.textContent = labelText; Object.assign(name.style, { display: "block", color: "#f3eef5", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "900 10px Segoe UI,Arial" });
            const amount = document.createElement("span"); amount.textContent = `${count.toLocaleString()} prompt${count === 1 ? "" : "s"}`; Object.assign(amount.style, { display: "block", marginTop: "4px", color: family.color, font: "800 8px Segoe UI,Arial" }); body.append(name, amount); button.append(cover, body);
            button.onclick = () => openPromptVault({ [family.axis]: labelText }); rail.append(button);
        });
        shelf.append(rail); shell.append(shelf);
    }

    const stats = document.createElement("div"); Object.assign(stats.style, { display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: "8px", marginTop: "17px", paddingTop: "14px", borderTop: "1px solid #302b36" });
    for (const [value, label, color] of [[promptBlueprintTotal, "corpus Blueprints", "#ff78bd"], [recipes.length, "saved Recipes", "#f6e65a"], [boards.length, "saved Boards", "#b89aff"], [(derivedValues.outfits || []).length + (derivedValues.scenes || []).length, "visual ingredients", "#63e6a4"]]) {
        const item = document.createElement("div"); Object.assign(item.style, { padding: "9px 11px", borderRadius: "9px", border: `1px solid ${color}33`, background: "rgba(255,255,255,.018)" });
        const number = document.createElement("strong"); number.textContent = Number(value || 0).toLocaleString(); Object.assign(number.style, { display: "block", color, font: "900 15px Segoe UI,Arial" });
        const caption = document.createElement("span"); caption.textContent = label; Object.assign(caption.style, { color: "#817b88", font: "8px Segoe UI,Arial", letterSpacing: ".04em" }); item.append(number, caption); stats.append(item);
    }
    shell.append(stats); list.append(shell);
}

function renderPromptAssets(list) {
    const assets = pagedPromptAssets();
    if (!assets.length) {
        const empty = document.createElement("div"); empty.textContent = promptLoading ? "Loading this Vault page…" : promptAssetTotal ? "No prompts match this Vault view. Clear a facet or search term to widen it." : "No ready-to-render prompts yet. Import old output images or save generations; resolved Outfit / Scene values become Prompt assets automatically.";
        Object.assign(empty.style, { gridColumn: "1 / -1", padding: "42px", color: "#afa9b6", textAlign: "center" }); list.append(empty); return;
    }
    for (const asset of assets) {
        const recipe = promptAssetRecipe(asset);
        const recipeId = String(asset.recipe_id || recipe?.recipe_id || "");
        const selected = recipeId && selectedRecipeIds.has(recipeId);
        const card = document.createElement("div");
        Object.assign(card.style, { minWidth: "0", height: "100%", alignSelf: "stretch", display: "flex", flexDirection: "column", overflow: "hidden", border: selected ? "1px solid #ff4ab8" : "1px solid #35d7ff66", borderRadius: "11px", background: selected ? "linear-gradient(150deg,rgba(255,74,184,.18),rgba(53,215,255,.08) 55%,rgba(10,9,14,.96))" : "linear-gradient(150deg,rgba(53,215,255,.085),rgba(255,74,184,.035) 55%,rgba(10,9,14,.97))", boxShadow: selected ? "0 0 0 1px rgba(255,74,184,.22),0 10px 28px rgba(0,0,0,.30)" : "0 8px 22px rgba(0,0,0,.22)" });
        const preview = document.createElement("div"); Object.assign(preview.style, { width: "100%", aspectRatio: "4 / 5", minHeight: "230px", flex: "0 0 auto", position: "relative", overflow: "hidden", cursor: "pointer", background: "radial-gradient(circle at 18% 15%,#35d7ff36,transparent 34%),radial-gradient(circle at 82% 20%,#ff4ab82a,transparent 38%),#08070c" });
        preview.title = selectionMode ? `Select ${asset.name || "prompt"}` : `Load ${asset.name || "prompt"}`;
        preview.onclick = () => selectionMode && recipeId ? toggleRecipeSelection(recipeId) : showPromptApply(asset);
        if (asset.preview_ref) { const image = document.createElement("img"); image.loading = "lazy"; image.decoding = "async"; image.src = creativeLibraryPreviewUrl(asset.preview_ref, asset.preview_updated_at || asset.updated_at || ""); image.alt = asset.name || "Prompt"; Object.assign(image.style, { width: "100%", height: "100%", objectFit: "contain", display: "block", background: "#08070c" }); preview.append(image); }
        const badge = document.createElement("span"); badge.textContent = asset.builder_ready ? "BLUEPRINT" : asset.from_recipe ? "RECIPE PROMPT" : "PROMPT"; Object.assign(badge.style, { position: "absolute", left: "8px", top: "8px", padding: "3px 6px", borderRadius: "999px", color: "#fff", background: asset.builder_ready ? "rgba(255,74,184,.90)" : asset.from_recipe ? "rgba(184,154,255,.88)" : "rgba(33,167,204,.90)", font: "800 8px Segoe UI,Arial", letterSpacing: ".07em" }); preview.append(badge);
        if ((selectionMode || selected) && recipeId) {
            const selector = document.createElement("button"); selector.type = "button"; selector.textContent = selected ? "✓" : ""; selector.title = selected ? "Remove from selection" : "Select prompt"; selector.setAttribute("aria-pressed", selected ? "true" : "false");
            Object.assign(selector.style, { position: "absolute", right: "8px", top: "8px", zIndex: "4", width: "28px", height: "28px", display: "grid", placeItems: "center", padding: "0", borderRadius: "8px", cursor: "pointer", border: selected ? "1px solid #ff4ab8" : "1px solid #35d7ffaa", color: selected ? "#fff" : "#d7f8ff", background: selected ? "rgba(255,74,184,.88)" : "rgba(8,7,12,.78)", boxShadow: "0 3px 12px rgba(0,0,0,.35)", font: "700 15px Segoe UI,Arial" });
            selector.onclick = event => { event.stopPropagation(); toggleRecipeSelection(recipeId); }; preview.append(selector);
        }

        const body = document.createElement("div"); Object.assign(body.style, { padding: "10px", display: "flex", flexDirection: "column", flex: "1 1 auto", gap: "7px" });
        const text = document.createElement("div"); text.textContent = asset.value; text.title = asset.value; Object.assign(text.style, { color: "#f2edf4", fontSize: "10px", lineHeight: "1.42", display: "-webkit-box", WebkitLineClamp: "4", WebkitBoxOrient: "vertical", overflow: "hidden", minHeight: "57px" });
        const provenance = document.createElement("div"); provenance.textContent = asset.name || "Prompt"; provenance.title = asset.name || "Prompt"; Object.assign(provenance.style, { color: "#77717d", fontSize: "8px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
        const collectionSummary = document.createElement("div"); Object.assign(collectionSummary.style, { display: "flex", minHeight: "15px", gap: "4px", overflow: "hidden" });
        const promptCollections = recipe?.collections || [];
        for (const collection of promptCollections.slice(0, 1)) { const chip = document.createElement("span"); chip.textContent = collection.name; Object.assign(chip.style, { maxWidth: "145px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding: "2px 5px", borderRadius: "999px", border: `1px solid ${collection.color || "#b89aff"}66`, color: collection.color || "#d8c7ff", font: "700 8px Segoe UI,Arial" }); collectionSummary.append(chip); }
        if (promptCollections.length > 1) { const moreChip = document.createElement("span"); moreChip.textContent = `+${promptCollections.length - 1}`; Object.assign(moreChip.style, { padding: "2px 5px", borderRadius: "999px", color: "#88818f", border: "1px solid #413b47", font: "700 8px Segoe UI,Arial" }); collectionSummary.append(moreChip); }
        const facetSummary = document.createElement("div"); Object.assign(facetSummary.style, { display: "flex", minHeight: "15px", gap: "4px", overflow: "hidden" });
        const facetLabels = PROMPT_FACET_AXES.flatMap(axis => Array.isArray(asset?.facets?.[axis]) ? asset.facets[axis] : []).filter(label => label !== "Other").slice(0, 3);
        for (const label of facetLabels) { const chip = document.createElement("span"); chip.textContent = label; Object.assign(chip.style, { maxWidth: "88px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding: "2px 5px", borderRadius: "999px", border: "1px solid #35d7ff33", color: "#8fcfe0", font: "700 7px Segoe UI,Arial" }); facetSummary.append(chip); }

        const buttons = document.createElement("div"); Object.assign(buttons.style, { marginTop: "auto", display: "grid", gridTemplateColumns: "1fr auto auto auto", gap: "5px", alignItems: "center" });
        const load = action("LOAD", "#35d7ff"); load.title = "Load this Prompt into Prompt Core"; Object.assign(load.style, { padding: "6px 8px", fontSize: "9px" }); load.onclick = () => showPromptApply(asset);
        const copy = action("⧉", "#35d7ff"); copy.title = "Copy prompt text"; Object.assign(copy.style, { width: "31px", padding: "6px 0", fontSize: "11px" }); copy.onclick = async () => { try { await navigator.clipboard.writeText(String(asset.value || "")); const old = copy.textContent; copy.textContent = "✓"; setTimeout(() => { copy.textContent = old; }, 800); } catch (error) { alert("Could not copy this prompt."); } };
        const harvest = action("✂", "#f6e65a"); harvest.title = "Harvest an Outfit Look from this Prompt"; Object.assign(harvest.style, { width: "31px", padding: "6px 0", fontSize: "11px" }); harvest.onclick = () => showPromptHarvestWorkbench({ query: asset.name || "" });
        const more = action("•••", "#8f8997"); more.title = "More prompt actions"; Object.assign(more.style, { width: "34px", padding: "6px 0", fontSize: "9px" });
        buttons.append(load, copy, harvest, more);
        const extras = document.createElement("div"); Object.assign(extras.style, { display: "none", flexWrap: "wrap", gap: "5px" });
        if (recipe) { const organize = action("COLLECTIONS", "#b89aff"); Object.assign(organize.style, { padding: "5px 7px", fontSize: "8px" }); organize.onclick = () => showRecipeCollectionEditor(recipe); extras.append(organize); }
        if (asset.from_recipe && recipe && recipeIsTemplate(recipe)) { const source = action("SOURCE RECIPE", "#8f8997"); Object.assign(source.style, { padding: "5px 7px", fontSize: "8px" }); source.onclick = () => showDiff(recipe); extras.append(source); }
        more.onclick = () => { extras.style.display = extras.style.display === "none" ? "flex" : "none"; };
        body.append(text, provenance, facetSummary, collectionSummary, buttons, extras); card.append(preview, body); list.append(card);
    }
}

async function setPromptAssetRating(asset, rating) {
    if (!asset?.prompt_id) return;
    try {
        const result = await request(`/prompt-assets/${encodeURIComponent(asset.prompt_id)}/rating`, {
            method: "POST", body: JSON.stringify({ rating }),
        });
        asset.rating = Number(result.rating || 0);
        render();
    } catch (error) { alert(error.message || "Could not save this rating."); }
}

async function deletePromptAssetPreview(asset) {
    const promptId = String(asset?.prompt_id || "");
    if (!promptId || !asset?.preview_ref) return;
    const label = activePromptKind() === "template" ? "Template" : "Prompt";
    if (!(await comfyConfirm(`Delete this ${label} thumbnail? The ${label.toLowerCase()} text, folders, rating, and source metadata stay intact.`, `Delete ${label} thumbnail?`))) return;
    try {
        await request(`/prompt-assets/${encodeURIComponent(promptId)}/preview`, { method: "DELETE" });
        asset.preview_ref = ""; asset.preview_source = ""; asset.preview_updated_at = "";
        await loadPromptPage();
        catalogStatus(`${label} thumbnail deleted.`, "#ff9b5f");
    } catch (error) { alert(error.message || `Could not delete this ${label.toLowerCase()} thumbnail.`); }
}

async function selectedPromptThumbnailItems() {
    const kind = activePromptKind();
    const scope = await fetchPromptYearbookScope(kind);
    if (promptSelectAllFiltered) return scope;
    const ids = new Set([...selectedPromptIds].map(value => String(value || "")).filter(Boolean));
    return scope.filter(item => ids.has(String(item.prompt_id || "")));
}

async function regenerateSelectedPromptThumbnails() {
    try {
        const items = await selectedPromptThumbnailItems();
        if (!items.length) { alert("Select Prompt / Template records first."); return; }
        await openPromptCatalogRunDialog(items);
    } catch (error) { alert(error.message || "Could not prepare the selected thumbnail run."); }
}

async function deleteSelectedPromptThumbnails() {
    const amount = promptSelectAllFiltered ? Number(promptTotal || 0) : selectedPromptIds.size;
    if (!amount) { alert("Select Prompt / Template records first."); return; }
    const label = activePromptKind() === "template" ? "Template" : "Prompt";
    if (!(await comfyConfirm(`Delete thumbnails from the ${amount.toLocaleString()} selected ${label}${amount === 1 ? "" : "s"}? The catalog records themselves stay intact.`, `Delete selected ${label} thumbnails?`))) return;
    try {
        const result = await request("/prompt-assets/bulk", { method: "POST", body: JSON.stringify({ operation: "delete_previews", prompt_ids: [...selectedPromptIds], all_filtered: promptSelectAllFiltered, kind: activePromptKind(), filters: promptBulkFilters() }) });
        await loadPromptPage();
        catalogStatus(`Deleted ${Number(result.previews_cleared ?? result.changed ?? 0).toLocaleString()} selected ${label} thumbnail${Number(result.previews_cleared ?? result.changed ?? 0) === 1 ? "" : "s"}.`, "#ff9b5f");
    } catch (error) { alert(error.message || "Could not delete the selected thumbnails."); }
}

function promptInspectorPlatter(asset) {
    const recipe = promptAssetRecipe(asset);
    const captured = asset?.preview_metadata && typeof asset.preview_metadata === "object" ? asset.preview_metadata : {};
    const placeholders = Array.isArray(recipe?.payload?.summary?.placeholders) ? recipe.payload.summary.placeholders : [];
    const byComponent = (name) => placeholders.find(row => {
        const token = String(row?.token || "").replace(/[{}]/g, "").toUpperCase();
        const widget = String(row?.widget || "").toLowerCase();
        if (name === "scene") return token === "SCENE" || widget.startsWith("scene_");
        if (name === "outfit_b") return token === "OUTFIT_B" || widget.includes("outfit_b");
        if (name === "outfit_c") return token === "OUTFIT_C" || widget.includes("outfit_c");
        return token === "OUTFIT" || token === "OUTFIT_A" || widget.includes("outfit_a");
    });
    const value = name => String(captured[name] || byComponent(name)?.value || "").trim();
    const source = promptAssetSourceText(asset);
    return {
        finalPrompt: promptAssetResolvedText(asset) || source,
        sourcePrompt: source,
        outfitA: value("outfit_a"), outfitB: value("outfit_b"), outfitC: value("outfit_c"),
        scene: value("scene"), seed: promptAssetResolvedSeed(asset), recipe,
    };
}

function inspectorCollections(asset, kind) {
    if (["prompt", "template"].includes(kind)) return Array.isArray(asset?.collections) ? asset.collections : [];
    return Array.isArray(asset?.pack_collections) ? asset.pack_collections : [];
}

function inspectorHome(asset, kind) {
    if (["prompt", "template"].includes(kind)) return String(asset?.primary_home || [asset?.primary_parent, asset?.primary_subcategory].filter(Boolean).join(" / ") || "Unsorted");
    if (kind === "piece") return [asset?.category, asset?.subtype].filter(Boolean).join(" / ") || "Uncategorized";
    const homes = (asset?.collections || []).map(row => componentCollectionDisplayName(kind, row)).filter(Boolean);
    return homes.join(" · ") || "Unsorted";
}

function inspectorKindMeta(kind) {
    if (kind === "template") return { label: "TEMPLATE", accent: "#ff4ab8" };
    if (kind === "prompt") return { label: "PROMPT", accent: "#35d7ff" };
    if (kind === "outfit") return { label: "OUTFIT LOOK", accent: "#f6e65a" };
    if (kind === "scene") return { label: "SCENE", accent: "#63e6a4" };
    return { label: "WARDROBE PIECE", accent: "#ff9b5f" };
}

function inspectorCopyField(label, value, accent, { empty = "Not captured for this image", compact = false } = {}) {
    const shell = document.createElement("section");
    shell.dataset.inspectorField = label.toLowerCase().replaceAll(" ", "-");
    Object.assign(shell.style, { minWidth: "0", padding: compact ? "8px 9px" : "10px", borderRadius: "9px", border: `1px solid ${accent}38`, background: "rgba(3,3,6,.48)" });
    const head = document.createElement("div"); Object.assign(head.style, { display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" });
    const title = document.createElement("strong"); title.textContent = label; Object.assign(title.style, { color: accent, font: "900 10px Segoe UI,Arial", letterSpacing: ".09em" });
    const copy = action("COPY", accent); copy.disabled = !String(value || ""); copy.style.opacity = copy.disabled ? ".34" : "1"; Object.assign(copy.style, { marginLeft: "auto", padding: "4px 7px", fontSize: "9px" });
    copy.onclick = async () => { if (!String(value || "")) return; const prior = copy.textContent; if (await copyLibraryValue(String(value))) { copy.textContent = "COPIED"; window.setTimeout(() => { if (copy.isConnected) copy.textContent = prior; }, 800); } else alert(`Could not copy ${label.toLowerCase()}.`); };
    const text = document.createElement("div"); text.textContent = String(value || empty); Object.assign(text.style, { maxHeight: compact ? "110px" : "240px", overflow: "auto", color: value ? "#e8e2eb" : "#6f6873", whiteSpace: "pre-wrap", overflowWrap: "anywhere", font: `${compact ? "11" : "12"}px/1.48 Consolas,monospace` });
    head.append(title, copy); shell.append(head, text); return shell;
}

async function showPromptAssetCollectionEditor(asset, onSaved = null) {
    const kind = String(asset?.kind || activePromptKind()) === "template" ? "template" : "prompt";
    const accent = kind === "template" ? "#ff4ab8" : "#35d7ff";
    const folders = promptShowcaseFolders(kind);
    const { card, close } = collectionModal(`MANAGE ${kind.toUpperCase()} COLLECTIONS`, "650px");
    card.style.borderColor = `${accent}99`;
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "grid", gap: "7px", overflow: "auto" });
    const note = document.createElement("div"); note.textContent = "Choose the exact Collections for this record. Its one true Home does not change."; Object.assign(note.style, { color: "#b8b0c1", font: "10px/1.45 Segoe UI,Arial" }); body.append(note);
    const list = document.createElement("div"); Object.assign(list.style, { display: "grid", gap: "6px" }); body.append(list);
    const existing = new Set((asset?.collections || []).map(row => String(row.collection_id || "")));
    const checks = new Map();
    const redraw = (selectId = "") => { if (selectId) existing.add(String(selectId)); list.replaceChildren(); checks.clear(); for (const folder of folders) { const row = document.createElement("label"); Object.assign(row.style, { display: "flex", alignItems: "center", gap: "8px", padding: "8px 9px", border: `1px solid ${folder.color || accent}55`, borderRadius: "8px", cursor: "pointer" }); const box = document.createElement("input"); box.type = "checkbox"; box.checked = existing.has(String(folder.collection_id || "")); checks.set(String(folder.collection_id || ""), box); const name = document.createElement("span"); name.textContent = `${folder.name} · ${promptCollectionCount(folder.collection_id).toLocaleString()}`; name.style.flex = "1"; row.append(box, name); list.append(row); } if (!folders.length) { const empty = document.createElement("div"); empty.textContent = "No Collections yet. Create one below."; Object.assign(empty.style, { padding: "9px", color: "#8f8997" }); list.append(empty); } };
    redraw();
    const createRow = document.createElement("div"); Object.assign(createRow.style, { display: "grid", gridTemplateColumns: "1fr auto", gap: "6px" }); const input = document.createElement("input"); input.placeholder = "New Collection"; Object.assign(input.style, { minWidth: "0", padding: "8px", borderRadius: "7px", border: `1px solid ${accent}55`, background: "#09080d", color: "#fff" }); const create = action("+ CREATE", accent); create.onclick = async () => { const name = input.value.trim(); if (!name) return; create.disabled = true; try { const result = await request("/showcase-collections", { method: "POST", body: JSON.stringify({ kind, name }) }); const created = result?.collection; if (created?.collection_id) { folders.push(created); folders.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""))); input.value = ""; redraw(created.collection_id); } } catch (error) { alert(error.message || "Could not create the Collection."); } finally { create.disabled = false; } }; input.onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); create.click(); } }; createRow.append(input, create); body.append(createRow);
    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" }); const cancel = action("CANCEL", "#8f8997"); cancel.onclick = close; const save = action("SAVE COLLECTIONS", accent); save.onclick = async () => { save.disabled = true; try { const ids = [...checks].filter(([, box]) => box.checked).map(([id]) => id); const result = await request(`/prompt-assets/${encodeURIComponent(String(asset.prompt_id || ""))}/collections`, { method: "PUT", body: JSON.stringify({ kind, collection_ids: ids }) }); asset.collections = Array.isArray(result?.collections) ? result.collections : []; close(); await loadPromptPage(); onSaved?.(asset); catalogStatus(`Updated ${kind} Collections.`, accent); } catch (error) { alert(error.message || "Could not update Collections."); save.disabled = false; } }; foot.append(cancel, save); card.append(body, foot);
}

function openLibraryInspector({ kind, item, index = 0, total = 1, scopeLabel = "Current gallery", fetchAt = null }) {
    const meta = inspectorKindMeta(kind);
    const { overlay, card, close } = collectionModal("LIBRARY INSPECTOR", "min(2800px,96vw)");
    overlay.dataset.libraryInspector = kind;
    overlay.tabIndex = -1;
    card.setAttribute("role", "dialog"); card.setAttribute("aria-modal", "true"); card.setAttribute("aria-label", "Library Inspector");
    Object.assign(overlay.style, { padding: "12px" });
    Object.assign(card.style, { height: "94vh", maxHeight: "94vh", maxWidth: "96vw", borderColor: `${meta.accent}99` });
    const styles = document.createElement("style");
    styles.textContent = `
        [data-library-inspector] .inspector-layout { display:grid; grid-template-columns:minmax(360px,30%) minmax(0,1fr); height:100%; min-height:0; }
        [data-library-inspector] .inspector-rail { min-height:0; overflow:auto; overscroll-behavior:contain; }
        [data-library-inspector] .inspector-rail > * { flex-shrink:0; }
        [data-library-inspector] button:focus-visible, [data-library-inspector] img:focus-visible { outline:2px solid #fff; outline-offset:2px; }
        [data-library-inspector] button:disabled { opacity:.35; cursor:default; }
        @media(max-width:760px) { [data-library-inspector] .inspector-layout { grid-template-columns:1fr; grid-template-rows:minmax(0,1fr) minmax(0,1fr); } [data-library-inspector] .inspector-viewer { grid-row:1; } }
    `;
    overlay.append(styles);
    const title = card.querySelector(":scope > strong"); if (title) title.style.flexShrink = "0";
    const nav = document.createElement("div"); nav.dataset.inspectorNavigation = "";
    Object.assign(nav.style, { display:"flex", gap:"10px", alignItems:"center", padding:"10px 14px", flexShrink:"0", borderBottom:`1px solid ${meta.accent}33` });
    const previous = action("←", meta.accent); previous.title = "Previous item · Left Arrow";
    const next = action("→", meta.accent); next.title = "Next item · Right Arrow";
    const scope = document.createElement("div"); Object.assign(scope.style, { flex:"1", minWidth:"0" });
    const scopeName = document.createElement("strong"); scopeName.textContent = scopeLabel;
    Object.assign(scopeName.style, { display:"block", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", font:"800 12px Segoe UI,Arial" });
    const position = document.createElement("span"); position.setAttribute("aria-live", "polite"); Object.assign(position.style,{font:"11px Segoe UI,Arial", color:"#aaa2b4"}); scope.append(scopeName,position);
    const done = action("DONE", "#8f8997"); done.onclick = close;
    nav.append(previous,scope,next,done);
    const content = document.createElement("div"); content.dataset.inspectorContent = "";
    Object.assign(content.style, { minHeight:"0", flex:"1 1 0", overflow:"hidden" }); card.append(nav,content);
    // Freeze the session order. Rating/deleting cannot shift live server offsets.
    const slots = Array.from({length:total}, (_,i)=>i);
    const cache = new Map([[index,item]]);
    let cursor = Math.max(0, Math.min(index,slots.length-1));
    let current = item, requestSerial = 0, busy = false, zoom = 1, rateButtons = [], removeButton;
    const syncNavigation = () => { previous.disabled = busy || cursor <= 0; next.disabled = busy || cursor >= slots.length-1; };
    const navigate = async direction => {
        if (busy) return;
        const target = cursor + direction;
        if (target < 0 || target >= slots.length) return;
        const serial = ++requestSerial;
        cursor = target; current = cache.get(slots[cursor]) || null; renderCurrent();
        if (!current && fetchAt) {
            try {
                const loaded = await fetchAt(slots[target]);
                if (!overlay.isConnected || serial !== requestSerial) return;
                current = loaded || null; if (current) cache.set(slots[cursor],current); renderCurrent();
            } catch (error) { if (overlay.isConnected && serial === requestSerial) content.textContent = error.message || "Could not load this item. Use the arrows to retry."; }
        }
    };
    const refreshGallery = async () => { if (["prompt","template"].includes(kind)) await loadPromptPage(); else await load(); };
    const saveRating = async rating => {
        if (busy || !current) return;
        const asset = current; busy = true; renderCurrent();
        try {
            const id = asset.prompt_id || asset.component_id || asset.wardrobe_id;
            const path = ["prompt","template"].includes(kind) ? "prompt-assets" : kind === "piece" ? "wardrobe-items" : "derived-values";
            await request(`/${path}/${encodeURIComponent(id)}/rating`, {method:"POST",body:JSON.stringify({rating})});
            asset.rating = rating;
            // Commit the inspector immediately; refresh failure is a separate issue.
            try { await refreshGallery(); } catch (error) { catalogStatus("Rating saved; reopen the gallery to refresh its filters.", "#ff9b5f"); }
        } catch(error) { alert(error.message || "Could not save this rating."); }
        finally { busy = false; if (overlay.isConnected) renderCurrent(); }
    };
    const removeAsset = async () => {
        if (busy || !current) return;
        const asset = current; busy = true; renderCurrent();
        try {
            const note = ["prompt","template"].includes(kind)
                ? "Remove this record from the Library? Source-backed records are archived; imported records are deleted. Original source files and saved Recipes are preserved."
                : kind === "piece" ? "Delete this Wardrobe item, its thumbnail, and its Library relationships? Saved Look text is preserved."
                : "Delete this asset and its thumbnail everywhere in the Library? Saved Recipes keep their original text. The deleted value is blocked from being silently recreated by old sources.";
            if (!(await comfyConfirm(note, `Delete ${meta.label.toLowerCase()}?`))) return;
            let result;
            if (["prompt","template"].includes(kind)) result = await request("/prompt-assets/bulk", {method:"POST",body:JSON.stringify({operation:"delete",prompt_ids:[asset.prompt_id],all_filtered:false,kind})});
            else if (kind === "piece") result = await request("/wardrobe-items/bulk", {method:"POST",body:JSON.stringify({operation:"delete",wardrobe_ids:[asset.wardrobe_id]})});
            else result = await request("/derived-values/bulk/delete", {method:"POST",body:JSON.stringify({component_ids:[asset.component_id],everywhere:true})});
            if (!Number(result.changed ?? result.deleted ?? 0)) throw new Error("The asset was not removed. Refresh the Library and try again.");
            selectedPromptIds.delete(String(asset.prompt_id || "")); selectedComponentIds.delete(String(asset.component_id || "")); selectedWardrobeIds.delete(String(asset.wardrobe_id || ""));
            cache.delete(slots[cursor]); slots.splice(cursor,1); ++requestSerial;
            cursor = Math.min(cursor,slots.length-1); current = null;
            try { await refreshGallery(); } catch(error) { catalogStatus("Asset deleted; reopen the gallery to refresh its counts.", "#ff9b5f"); }
        } catch(error) { alert(error.message || "Could not delete this asset."); }
        finally {
            busy = false;
            if (overlay.isConnected) {
                if (current) renderCurrent();
                else if (slots.length) await navigate(0);
                else renderCurrent();
            }
        }
    };
    const actionButton = (label,color,handler,titleText="") => { const button = action(label,color); button.title = titleText || label; Object.assign(button.style,{padding:"9px 11px",fontSize:"10px"}); button.onclick = handler; return button; };
    const renderCurrent = () => {
        if (overlay.contains(document.activeElement)) requestAnimationFrame(() => { if (overlay.isConnected && (!document.activeElement || document.activeElement === document.body)) overlay.focus({preventScroll:true}); });
        syncNavigation(); rateButtons = []; removeButton = null;
        position.textContent = slots.length ? `${cursor+1} of ${slots.length} · ← → browse · 1–5 rate · 0 clear · Delete remove` : "This review scope is empty";
        if (title) title.textContent = `LIBRARY INSPECTOR · ${meta.label}`;
        content.replaceChildren();
        if (!current) { const message = document.createElement("div"); message.textContent = slots.length ? "Loading item…" : "All items in this review have been removed. Done returns to the Library."; Object.assign(message.style,{padding:"40px",color:"#aaa2b4"}); content.append(message); return; }
        const asset = current;
        const platter = ["prompt","template"].includes(kind) ? promptInspectorPlatter(asset) : null;
        const layout = document.createElement("div"); layout.className = "inspector-layout";
        const rail = document.createElement("aside"); rail.className = "inspector-rail";
        Object.assign(rail.style,{padding:"14px",display:"flex",flexDirection:"column",gap:"10px",borderRight:`1px solid ${meta.accent}33`,minWidth:"0"});
        const record = document.createElement("section"); Object.assign(record.style,{padding:"12px",borderRadius:"9px",border:`1px solid ${meta.accent}44`});
        const name = document.createElement("strong"); name.textContent = asset.name || asset.value || meta.label; Object.assign(name.style,{display:"block",font:"800 14px/1.4 Segoe UI,Arial",overflowWrap:"anywhere"});
        const home = document.createElement("div"); home.textContent = `HOME · ${inspectorHome(asset,kind)}`; Object.assign(home.style,{marginTop:"7px",color:meta.accent,font:"10px/1.5 Segoe UI,Arial"});
        const memberships = inspectorCollections(asset,kind); const collections = document.createElement("div"); collections.textContent = memberships.length ? `COLLECTIONS · ${memberships.map(row=>row.name).join(" · ")}` : "COLLECTIONS · None"; Object.assign(collections.style,{color:"#b9acc9",font:"10px/1.5 Segoe UI,Arial"}); record.append(name,home,collections); rail.append(record);
        if (platter) {
            rail.append(inspectorCopyField("FINAL PROMPT",platter.finalPrompt,"#6ee7a2"),inspectorCopyField("SOURCE PROMPT",platter.sourcePrompt,meta.accent));
            const components = document.createElement("div"); Object.assign(components.style,{display:"grid",gridTemplateColumns:"repeat(2,minmax(0,1fr))",gap:"8px"});
            components.append(inspectorCopyField("OUTFIT A",platter.outfitA,"#ff8fce",{compact:true}),inspectorCopyField("OUTFIT B",platter.outfitB,"#f6e65a",{compact:true}),inspectorCopyField("OUTFIT C",platter.outfitC,"#35d7ff",{compact:true}),inspectorCopyField("SCENE",platter.scene,"#63e6a4",{compact:true})); rail.append(components);
            rail.append(inspectorCopyField("SEED",platter.seed == null ? "" : String(platter.seed),"#f6e65a",{compact:true,empty:"No trusted image seed captured"}));
            rail.append(actionButton("COPY ALL",meta.accent,async event=>{
                const entries = [["Final Prompt",platter.finalPrompt],["Source Prompt",platter.sourcePrompt],["Outfit A",platter.outfitA],["Outfit B",platter.outfitB],["Outfit C",platter.outfitC],["Scene",platter.scene],["Seed",platter.seed]];
                const text = entries.filter(([,value])=>value !== null && value !== undefined && String(value) !== "").map(([label,value])=>`${label}:\n${value}`).join("\n\n");
                if (await copyLibraryValue(text)) { const button = event.currentTarget; button.textContent = "COPIED"; window.setTimeout(() => { if (button.isConnected) button.textContent = "COPY ALL"; }, 800); } else alert("Could not copy the metadata.");
            },"Copy all captured fields with labels; unavailable fields are omitted"));
        } else rail.append(inspectorCopyField(kind === "scene" ? "SCENE" : kind === "outfit" ? "OUTFIT LOOK" : "WARDROBE VALUE",asset.value,meta.accent));
        const actions = document.createElement("div"); actions.dataset.inspectorActions = ""; Object.assign(actions.style,{display:"flex",flexWrap:"wrap",gap:"7px"});
        if (["prompt", "template"].includes(kind)) {
            actions.append(actionButton("LOAD", meta.accent, () => showPromptApply(asset)), actionButton("QUEUE", "#6ee7a2", event => { event.currentTarget.dataset.queueLabel = "QUEUE"; void queuePromptAsset(asset, event.currentTarget, 0); }), actionButton("QUEUE NEXT", "#f6e65a", event => { event.currentTarget.dataset.queueLabel = "QUEUE NEXT"; void queuePromptAsset(asset, event.currentTarget, -1); }), actionButton("EDIT", "#f6e65a", () => void editPromptAssetCard(asset, renderCurrent)), actionButton("COLLECTIONS", "#b89aff", () => void showPromptAssetCollectionEditor(asset, renderCurrent)), actionButton("GENERATE PREVIEW", "#6ee7a2", () => void openPromptCatalogRunDialog([{ ...asset, kind, catalog_preview_ref: String(asset.preview_ref || "") }])));
            const removeThumb = actionButton("DELETE THUMBNAIL", "#ff9b5f", async () => { await deletePromptAssetPreview(asset); renderCurrent(); }); removeThumb.disabled = !asset.preview_ref; removeThumb.style.opacity = asset.preview_ref ? "1" : ".35"; actions.append(removeThumb);
        } else if (["outfit", "scene"].includes(kind)) {
            if (kind === "outfit") actions.append(actionButton("LOAD A", "#ff4ab8", () => loadDerivedValue(asset, "A")), actionButton("LOAD B", "#f6e65a", () => loadDerivedValue(asset, "B")), actionButton("LOAD C", "#35d7ff", () => loadDerivedValue(asset, "C")));
            else actions.append(actionButton("LOAD SCENE", meta.accent, () => loadDerivedValue(asset)));
            actions.append(actionButton("EDIT", "#f6e65a", () => showComponentValueEditor(asset, kind, renderCurrent)), actionButton("MOVE HOME", "#b89aff", () => showComponentCollectionEditor(asset, kind, renderCurrent)), actionButton("COLLECTIONS", "#ff9b5f", () => void showLibraryAssetCollectionEditor(asset, kind, renderCurrent)), actionButton("GENERATE PREVIEW", "#6ee7a2", () => openCatalogRunDialogForItem(null, [{ ...asset, kind }])));
            const removeThumb = actionButton("DELETE THUMBNAIL", "#ff9b5f", async () => { if (await deleteComponentThumbnail({ ...asset, kind })) { asset.preview_ref = ""; renderCurrent(); } }); removeThumb.disabled = !asset.preview_ref; removeThumb.style.opacity = asset.preview_ref ? "1" : ".35"; actions.append(removeThumb);
            const sourceRecipe = recipes.find(recipe => String(recipe.recipe_id || "") === String(asset.recipe_id || "")); if (sourceRecipe) actions.append(actionButton("SOURCE RECIPE", "#8f8997", () => showDiff(sourceRecipe)));
        } else {
            actions.append(actionButton("+ BUILDER", "#f6e65a", () => addBuilderItem(asset)), actionButton("LOAD A", "#ff4ab8", () => void loadWardrobeValue(asset, "A")), actionButton("LOAD B", "#f6e65a", () => void loadWardrobeValue(asset, "B")), actionButton("LOAD C", "#35d7ff", () => void loadWardrobeValue(asset, "C")), actionButton("EDIT", "#b89aff", () => showWardrobeItemEditor(asset, renderCurrent)), actionButton("COLLECTIONS", "#ff9b5f", () => void showLibraryAssetCollectionEditor(asset, "wardrobe", renderCurrent)), actionButton("GENERATE PREVIEW", "#6ee7a2", () => openCatalogRunDialogForItem(asset)));
        }
        for (const button of actions.querySelectorAll("button")) if (busy) button.disabled = true;
        rail.append(actions);
        const viewer = document.createElement("main"); viewer.className = "inspector-viewer";
        Object.assign(viewer.style,{minWidth:"0",minHeight:"0",display:"flex",flexDirection:"column",background:"#030205"});
        const review = document.createElement("div"); review.dataset.inspectorRating = "";
        Object.assign(review.style,{display:"flex",gap:"8px",alignItems:"center",flexWrap:"wrap",padding:"10px 14px",flexShrink:"0",borderBottom:"1px solid #302637"});
        for (let n=1;n<=5;n++) {
            const star = actionButton(n <= Number(asset.rating || 0) ? "★" : "☆","#f6e65a",()=>void saveRating(Number(asset.rating || 0) === n ? 0 : n),`Rate ${n} stars · click current rating to clear`);
            star.setAttribute("aria-label",`Rate ${n} stars`); star.setAttribute("aria-pressed",String(Number(asset.rating || 0) === n)); star.style.fontSize="22px"; star.disabled=busy; rateButtons.push(star); review.append(star);
        }
        const ratingLabel = document.createElement("span"); ratingLabel.textContent = busy ? "Saving…" : asset.rating ? `${asset.rating} / 5` : "Unrated"; Object.assign(ratingLabel.style,{font:"11px Segoe UI,Arial",color:"#aaa2b4"}); review.append(ratingLabel);
        removeButton = actionButton("DELETE ASSET","#ff6d9d",()=>void removeAsset(),"Delete the Library record, with confirmation"); removeButton.style.marginLeft="auto"; removeButton.disabled=busy; review.append(removeButton);
        const zoomBar = document.createElement("div"); Object.assign(zoomBar.style,{display:"flex",alignItems:"center",justifyContent:"center",gap:"8px",padding:"8px",flexShrink:"0"});
        const zoomLabel = document.createElement("span"); Object.assign(zoomLabel.style,{minWidth:"85px",textAlign:"center",font:"11px Segoe UI,Arial",color:"#aaa2b4"});
        const stage = document.createElement("div"); stage.dataset.inspectorStage = ""; Object.assign(stage.style,{minHeight:"0",flex:"1 1 0",overflow:"auto",overscrollBehavior:"contain",position:"relative"});
        const canvas = document.createElement("div"); Object.assign(canvas.style,{display:"flex",alignItems:"center",justifyContent:"center"}); stage.append(canvas);
        let image = null;
        const applyZoom = () => {
            zoomLabel.textContent = zoom === 1 ? "FIT" : `${Math.round(zoom*100)}% of fit`;
            canvas.style.width = `${zoom*100}%`; canvas.style.height = `${zoom*100}%`;
            canvas.style.margin = zoom < 1 ? "auto" : "0";
            if (image) { image.style.cursor = zoom === 1 ? "zoom-in" : "zoom-out"; }
            if (zoom === 1) { stage.scrollLeft=0;stage.scrollTop=0; }
        };
        zoomBar.append(actionButton("−","#8f8997",()=>{zoom=Math.max(.5,zoom-.25);applyZoom();}),zoomLabel,actionButton("+","#8f8997",()=>{zoom=Math.min(4,zoom+.25);applyZoom();}),actionButton("FIT",meta.accent,()=>{zoom=1;applyZoom();}));
        if (asset.preview_ref) {
            image = document.createElement("img"); image.dataset.inspectorImage = "";
            image.src = creativeLibraryPreviewUrl(String(asset.preview_ref),asset.preview_updated_at || asset.updated_at || ""); image.alt = asset.name || asset.value || meta.label;
            image.setAttribute("role","button");image.tabIndex=0;image.title="Click to toggle Fit / 200% of fit";
            Object.assign(image.style,{display:"block",width:"100%",height:"100%",objectFit:"contain",flexShrink:"0"});
            image.onclick=()=>{zoom=zoom === 1 ? 2 : 1;applyZoom();};
            image.onkeydown=event=>{if(event.key === "Enter" || event.key === " "){event.preventDefault();image.click();}};
            image.onerror=()=>{canvas.replaceChildren();const missing=document.createElement("div");missing.textContent="Preview unavailable. Regenerate it from the actions panel.";missing.style.color="#aaa2b4";canvas.append(missing);};
            canvas.append(image);
        } else { const empty=document.createElement("div");empty.textContent="No thumbnail yet. Use Generate Preview to create one.";empty.style.color="#aaa2b4";canvas.append(empty); }
        applyZoom(); viewer.append(review,zoomBar,stage);layout.append(rail,viewer);content.append(layout);
    };
    previous.onclick=()=>void navigate(-1);next.onclick=()=>void navigate(1);
    overlay.addEventListener("keydown",event=>{
        const tag=String(event.target?.tagName || "").toLowerCase();
        if (["input","textarea","select"].includes(tag) || event.target?.isContentEditable || event.ctrlKey || event.altKey || event.metaKey) return;
        // A nested editor/confirmation must own its keyboard interaction.
        if (document.activeElement && !overlay.contains(document.activeElement)) return;
        if (event.key === "ArrowLeft") {event.preventDefault();event.stopPropagation();previous.click();}
        else if (event.key === "ArrowRight") {event.preventDefault();event.stopPropagation();next.click();}
        else if (/^[1-5]$/.test(event.key) && !event.repeat) {event.preventDefault();void saveRating(Number(event.key));}
        else if (event.key === "0" && !event.repeat) {event.preventDefault();void saveRating(0);}
        else if (event.key === "Delete" && !event.repeat) {event.preventDefault();removeButton?.click();}
        else if (event.key === "Escape") {event.preventDefault();event.stopPropagation();if(!busy)close();}
    });
    renderCurrent();requestAnimationFrame(()=>overlay.focus({preventScroll:true}));
}

let promptInspectorOpenSerial = 0;
async function openPromptThumbnail(asset) {
    const serial = ++promptInspectorOpenSerial;
    const kind = String(asset?.kind || activePromptKind()) === "template" ? "template" : "prompt";
    const scopeLabel = activeCollection ? `Collection · ${currentPromptFolderLabel()}` : `Home · ${currentPromptFolderLabel()}`;
    const scoped = promptPageParams(); scoped.set("offset","0"); scoped.set("limit","0"); scoped.set("include_all","1");
    try {
        // Capture once so rating filters/sorts cannot skip or repeat off-page items.
        const data = await request(`/prompt-assets?${scoped.toString()}`);
        if (serial !== promptInspectorOpenSerial) return;
        const rows = Array.isArray(data?.prompts) ? data.prompts : [];
        const index = rows.findIndex(row=>String(row.prompt_id) === String(asset.prompt_id));
        if (index < 0) { catalogStatus("This asset has left the current scope. Refresh the gallery.","#ff9b5f");return; }
        openLibraryInspector({kind,item:rows[index],index,total:rows.length,scopeLabel,fetchAt:async target=>rows[target] || null});
    } catch(error) {alert(error.message || "Could not open the Library Inspector.");}
}

function promptFilterSelect(axis, label, accent) {
    const counts = promptFacetCounts?.[axis] && typeof promptFacetCounts[axis] === "object" ? promptFacetCounts[axis] : {};
    const universe = promptFacetUniverse?.[axis] && typeof promptFacetUniverse[axis] === "object" ? promptFacetUniverse[axis] : counts;
    const options = [["", `Any ${label}`], ...Object.keys(universe)
        .sort((a, b) => Number(counts[b] || 0) - Number(counts[a] || 0) || String(a).localeCompare(String(b)))
        .map(value => [value, `${value} · ${Number(counts[value] || 0).toLocaleString()}`])];
    const select = makeSelect(options, String(promptFacetFilters[axis] || ""));
    for (const option of select.options) if (option.value && !Number(counts[option.value] || 0) && option.value !== promptFacetFilters[axis]) { option.disabled = true; option.style.color = "#6b6570"; }
    Object.assign(select.style, { flex: "1 1 150px", width: "auto", minWidth: "130px", padding: "8px 9px", borderColor: `${accent}44` });
    select.onchange = () => { promptFacetFilters[axis] = select.value; promptPage = 0; queuePromptPageLoad(); };
    return select;
}

function showPromptFolderEditor(promptIds = [], allFiltered = false) {
    const ids = [...new Set((promptIds || []).map(value => String(value || "")).filter(Boolean))];
    const amount = allFiltered ? Number(promptTotal || 0) : ids.length;
    const recordLabel = activePromptKind() === "template" ? "TEMPLATE" : "PROMPT";
    const showcaseFolders = promptShowcaseFolders();
    const { overlay, card } = collectionModal(amount ? `ADD ${amount.toLocaleString()} ${recordLabel}${amount === 1 ? "" : "S"} TO COLLECTION` : "NEW COLLECTION", "680px");
    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px", display: "flex", flexDirection: "column", gap: "10px", overflow: "auto" });
    const help = document.createElement("div"); help.textContent = amount
        ? "Choose one or more non-destructive Collections. The asset’s canonical Home and every existing Collection membership stay unchanged."
        : "Create a Collection now, then collect strong assets from cards or Select Multiple.";
    Object.assign(help.style, { color: "#b8b0c1", font: "11px/1.48 Segoe UI,Arial" });
    const createRow = document.createElement("div"); Object.assign(createRow.style, { display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: "7px" });
    const input = document.createElement("input"); input.type = "text"; input.placeholder = "New Collection name…"; Object.assign(input.style, { minWidth: "0", padding: "9px 10px", borderRadius: "8px", border: "1px solid #b89aff55", background: "#09080d", color: "#fff", outline: "none" });
    const create = action("CREATE COLLECTION", "#b89aff"); createRow.append(input, create);
    const list = document.createElement("div"); Object.assign(list.style, { display: "flex", flexDirection: "column", gap: "6px", maxHeight: "44vh", overflow: "auto" });
    const draw = (selectId = "") => {
        const selectedIds = new Set([...list.querySelectorAll('input[type="checkbox"]:checked')].map(item => item.value));
        if (selectId) selectedIds.add(String(selectId));
        list.replaceChildren();
        if (!showcaseFolders.length) { const empty = document.createElement("div"); empty.textContent = `No ${recordLabel.toLowerCase()} Collections yet.`; Object.assign(empty.style, { padding: "12px", color: "#817a87", textAlign: "center" }); list.append(empty); return; }
        for (const collection of showcaseFolders) {
            const row = document.createElement("label"); Object.assign(row.style, { display: "grid", gridTemplateColumns: amount ? "auto minmax(0,1fr) auto" : "minmax(0,1fr) auto", gap: "9px", alignItems: "center", padding: "9px 10px", borderRadius: "8px", border: `1px solid ${collection.color || "#b89aff"}55`, cursor: amount ? "pointer" : "default" });
            if (amount) { const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.value = String(collection.collection_id); checkbox.checked = selectedIds.has(String(collection.collection_id)); checkbox.style.accentColor = collection.color || "#b89aff"; row.append(checkbox); }
            const name = document.createElement("strong"); name.textContent = String(collection.name || "Collection"); Object.assign(name.style, { minWidth: "0", overflow: "hidden", textOverflow: "ellipsis", color: "#eee8f0", fontSize: "11px" });
            const count = document.createElement("span"); count.textContent = `${promptCollectionCount(collection.collection_id).toLocaleString()} prompts`; Object.assign(count.style, { color: collection.color || "#b89aff", font: "800 9px Segoe UI,Arial" }); row.append(name, count); list.append(row);
        }
    };
    create.onclick = async () => {
        const name = input.value.trim(); if (!name) { input.focus(); return; }
        create.disabled = true;
        try {
            const result = await request("/showcase-collections", { method: "POST", body: JSON.stringify({ kind: activePromptKind(), name }) });
            const collection = result?.collection; if (!collection?.collection_id) throw new Error("Collection was not created.");
            showcaseFolders.push(collection); showcaseFolders.sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" }));
            promptShowcaseCounts()[String(collection.collection_id)] = 0; input.value = ""; draw(String(collection.collection_id)); catalogStatus(`Created ${recordLabel.toLowerCase()} Collection: ${collection.name}.`, "#b89aff");
        } catch (error) { alert(error.message || "Could not create this Collection."); }
        finally { create.disabled = false; }
    };
    input.onkeydown = event => { if (event.key === "Enter") { event.preventDefault(); create.click(); } };
    body.append(help, createRow, list); draw();
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", justifyContent: "flex-end", gap: "8px", padding: "0 14px 14px" });
    const cancel = action(amount ? "Cancel" : "Done", "#8f8997"); cancel.onclick = () => { overlay.remove(); if (!amount) render(); }; footer.append(cancel);
    if (amount) {
        const save = action("ADD TO COLLECTION", "#6ee7a2"); save.onclick = async () => {
            const collectionIds = [...list.querySelectorAll('input[type="checkbox"]:checked')].map(item => item.value);
            if (!collectionIds.length) { alert("Choose at least one Collection."); return; }
            save.disabled = true;
            try {
                const result = await request("/prompt-assets/bulk/collections", { method: "POST", body: JSON.stringify({ prompt_ids: ids, all_filtered: allFiltered, kind: activePromptKind(), collection_ids: collectionIds, filters: promptBulkFilters() }) });
                selectedPromptIds.clear(); promptSelectAllFiltered = false; promptSelectionMode = false; overlay.remove(); await loadPromptPage();
                catalogStatus(`Added ${Number(result.prompts || amount).toLocaleString()} prompt${Number(result.prompts || amount) === 1 ? "" : "s"} to ${Number(result.collections || collectionIds.length)} Collection${Number(result.collections || collectionIds.length) === 1 ? "" : "s"}.`, "#6ee7a2");
            } catch (error) { alert(error.message || "Could not add these prompts to the Collection."); }
            finally { save.disabled = false; }
        }; footer.append(save);
    }
    card.append(body, footer); requestAnimationFrame(() => input.focus());
}

function showPromptLogImporter() {
    const importKind = activePromptKind();
    const isTemplate = importKind === "template";
    const accent = isTemplate ? "#ff4ab8" : "#35d7ff";
    const universe = promptHomeUniverse[importKind]?.parents && Object.keys(promptHomeUniverse[importKind].parents).length
        ? promptHomeUniverse[importKind]
        : promptHomeCounts[importKind] || { parents: {}, subcategories: {} };
    const { overlay, card } = collectionModal("IMPORT PROMPT / TEMPLATE LOG", "940px");
    const body = document.createElement("div"); Object.assign(body.style, { minHeight: "0", padding: "14px", display: "flex", flexDirection: "column", gap: "12px", overflow: "auto" });
    const intro = document.createElement("div"); intro.textContent = "Select a local .txt log or paste one here. Every placeholder-bearing line routes to Templates; fully resolved, token-free lines route to Prompts. Mixed logs populate both tabs automatically while exact matches reuse the existing record. Subcategory is optional, so a Log can live directly under its Category. A selected file is copied into SickOllieLogs/prompts/Imported Logs; the original local file is never moved or changed."; Object.assign(intro.style, { color: "#bcb4c4", font: "11px/1.52 Segoe UI,Arial" });

    const sourceHead = document.createElement("div"); Object.assign(sourceHead.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "7px" });
    const sourceLabel = document.createElement("strong"); sourceLabel.textContent = "PROMPT / TEMPLATE VALUES"; Object.assign(sourceLabel.style, { color: accent, font: "900 9px Segoe UI,Arial", letterSpacing: ".11em" });
    const fileButton = action("SELECT .TXT FILE", accent); fileButton.title = "Choose a local plain-text Prompt log; the original file stays where it is";
    const fileSummary = document.createElement("span"); Object.assign(fileSummary.style, { color: "#7f7885", font: "9px Segoe UI,Arial" });
    const picker = document.createElement("input"); picker.type = "file"; picker.accept = ".txt,text/plain"; picker.multiple = false; picker.hidden = true;
    sourceHead.append(sourceLabel, fileButton, fileSummary, picker);
    const textarea = document.createElement("textarea"); textarea.placeholder = "Paste one complete prompt per line…"; textarea.spellcheck = false; Object.assign(textarea.style, { boxSizing: "border-box", width: "100%", minHeight: "250px", resize: "vertical", padding: "11px 12px", borderRadius: "9px", border: `1px solid ${accent}55`, outline: "none", color: "#f5f1f7", background: "#08070c", font: "11px/1.48 Consolas,monospace" });
    const lineSummary = document.createElement("div"); Object.assign(lineSummary.style, { color: "#8d8693", font: "9px Segoe UI,Arial" });

    const location = document.createElement("section"); Object.assign(location.style, { display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: "9px", padding: "11px", borderRadius: "10px", border: "1px solid #39333e", background: "rgba(255,255,255,.018)" });
    const field = (labelText) => { const shell = document.createElement("label"); Object.assign(shell.style, { minWidth: "0", display: "flex", flexDirection: "column", gap: "6px" }); const label = document.createElement("span"); label.textContent = labelText; Object.assign(label.style, { color: "#aaa2b4", font: "900 8px Segoe UI,Arial", letterSpacing: ".08em" }); shell.append(label); return shell; };
    const categoryField = field("CATEGORY · ONE TRUE HOME");
    const categoryNames = Object.keys(universe.parents || {}).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
    const category = makeSelect([["", "Choose category…"], ...categoryNames.map(value => [value, value]), ["__new__", "＋ New category…"]], categoryNames.includes(promptParent) ? promptParent : "");
    const newCategory = document.createElement("input"); newCategory.type = "text"; newCategory.placeholder = "New category name…"; newCategory.hidden = true;
    categoryField.append(category, newCategory);
    const subcategoryField = field("SUBCATEGORY · OPTIONAL");
    const subcategory = makeSelect([["", "No subcategory · Category only"]], "");
    const newSubcategory = document.createElement("input"); newSubcategory.type = "text"; newSubcategory.placeholder = "New subcategory name…"; newSubcategory.hidden = true;
    subcategoryField.append(subcategory, newSubcategory);
    const logField = field("LOG / SCENE NAME");
    const logName = document.createElement("input"); logName.type = "text"; logName.placeholder = "e.g. Nest Roll Journey"; logName.value = promptLogLabel || "";
    Object.assign(logName.style, { boxSizing: "border-box", width: "100%", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", outline: "none", color: "#fff", background: "#09080d" }); logField.append(logName);
    const collectionField = field("COLLECTION · OPTIONAL");
    const collection = makeSelect([["", "No Collection"], ...promptShowcaseFolders(importKind).map(item => [String(item.collection_id || ""), String(item.name || "Collection")]), ["__new__", `＋ New ${isTemplate ? "Template" : "Prompt"} Collection…`]], "");
    const newCollection = document.createElement("input"); newCollection.type = "text"; newCollection.placeholder = "New Collection name…"; newCollection.hidden = true;
    collectionField.append(collection, newCollection); location.append(categoryField, subcategoryField, logField, collectionField);
    for (const input of [newCategory, newSubcategory, newCollection]) Object.assign(input.style, { boxSizing: "border-box", width: "100%", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", outline: "none", color: "#fff", background: "#09080d" });

    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "8px", padding: "0 14px 14px" });
    const note = document.createElement("span"); note.textContent = `The imported copy keeps the Log name and original line order. A selected Collection applies to ${isTemplate ? "Template" : "Prompt"} lines from this import; lines routed to the other tab remain unfiled.`; Object.assign(note.style, { color: "#7f7885", font: "9px/1.4 Segoe UI,Arial" });
    const actions = document.createElement("div"); Object.assign(actions.style, { display: "flex", gap: "8px" });
    const cancel = action("Cancel", "#8f8997"); cancel.onclick = () => overlay.remove();
    const submit = action("IMPORT LOG", accent); actions.append(cancel, submit); foot.append(note, actions);

    const resolvedCategory = () => category.value === "__new__" ? newCategory.value.trim() : category.value;
    const resolvedSubcategory = () => subcategory.value === "__new__" ? newSubcategory.value.trim() : subcategory.value;
    const update = () => {
        const lines = textarea.value.split(/\r?\n/).map(value => value.trim()).filter(Boolean);
        const unique = new Set(lines.map(value => value.replace(/\s+/g, " ").toLocaleLowerCase()));
        lineSummary.textContent = `${lines.length.toLocaleString()} non-empty line${lines.length === 1 ? "" : "s"} · ${unique.size.toLocaleString()} exact unique value${unique.size === 1 ? "" : "s"}`;
        submit.disabled = !lines.length || !resolvedCategory() || !logName.value.trim() || (collection.value === "__new__" && !newCollection.value.trim());
        submit.style.opacity = submit.disabled ? ".42" : "1";
    };
    const refreshSubcategories = () => {
        const parent = resolvedCategory();
        const values = category.value === "__new__" ? [] : Object.keys(universe.subcategories?.[parent] || {}).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
        const preferred = parent === promptParent && values.includes(promptSubcategory) ? promptSubcategory : "";
        subcategory.replaceChildren(...[["", "No subcategory · Category only"], ...values.filter(Boolean).map(value => [value, value]), ["__new__", "＋ New subcategory…"]].map(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; option.selected = value === preferred; return option; }));
        newSubcategory.hidden = true; newSubcategory.value = ""; update();
    };
    category.onchange = () => { newCategory.hidden = category.value !== "__new__"; if (!newCategory.hidden) requestAnimationFrame(() => newCategory.focus()); refreshSubcategories(); };
    subcategory.onchange = () => { newSubcategory.hidden = subcategory.value !== "__new__"; if (!newSubcategory.hidden) requestAnimationFrame(() => newSubcategory.focus()); update(); };
    collection.onchange = () => { newCollection.hidden = collection.value !== "__new__"; if (!newCollection.hidden) requestAnimationFrame(() => newCollection.focus()); update(); };
    textarea.oninput = update; newCategory.oninput = () => { refreshSubcategories(); update(); }; newSubcategory.oninput = update; logName.oninput = update; newCollection.oninput = update;
    fileButton.onclick = () => picker.click();
    picker.onchange = async () => {
        const file = (picker.files || [])[0]; if (!file) return;
        fileButton.disabled = true;
        try {
            textarea.value = await file.text();
            const stem = String(file.name || "").replace(/\.[^.]+$/, "").trim();
            if (stem) logName.value = stem;
            fileSummary.textContent = `${file.name} · local original stays untouched`;
            update();
        } catch (error) { alert(error?.message || "Could not read this text file."); }
        finally { fileButton.disabled = false; picker.value = ""; }
    };
    submit.onclick = async () => {
        update(); if (submit.disabled) return;
        submit.disabled = true; cancel.disabled = true; submit.textContent = "IMPORTING…";
        try {
            const result = await request("/prompt-assets/import", {
                method: "POST",
                body: JSON.stringify({
                    text: textarea.value,
                    kind: importKind,
                    parent: resolvedCategory(),
                    subcategory: resolvedSubcategory(),
                    log_name: logName.value.trim(),
                    collection_id: collection.value && collection.value !== "__new__" ? collection.value : "",
                    collection_name: collection.value === "__new__" ? newCollection.value.trim() : "",
                }),
            });
            if (result.collection?.collection_id && !promptShowcaseFolders(importKind).some(item => String(item.collection_id) === String(result.collection.collection_id))) {
                promptShowcaseCollections[importKind] = [...promptShowcaseFolders(importKind), result.collection].sort((a, b) => String(a.name || "").localeCompare(String(b.name || ""), undefined, { sensitivity: "base" }));
            }
            libraryRevisions = result.revisions && typeof result.revisions === "object" ? result.revisions : null;
            activeView = result.default_kind === "template" ? "recipes" : "prompts"; activeCollection = ""; promptParent = String(result.parent || resolvedCategory()); promptSubcategory = String(result.subcategory ?? resolvedSubcategory()); promptLogPath = String(result.source_path || ""); promptLogLabel = String(result.log_name || logName.value.trim()); promptSort = promptLogPath ? "source_order" : promptSort; promptPage = 0; promptSearch = ""; promptFacetFilters = emptyPromptFacetFilters(); promptRatingFilter = "";
            await loadPromptPage();
            overlay.remove();
            const skipped = Number(result.input_duplicates || 0) + Number(result.blank || 0) + Number(result.safety_excluded || 0);
            const detail = [`${Number(result.prompts || 0).toLocaleString()} Prompts`, `${Number(result.templates || 0).toLocaleString()} Templates`, `${Number(result.created || 0).toLocaleString()} new`, `${Number(result.matched || 0).toLocaleString()} existing reused`];
            if (skipped) detail.push(`${skipped.toLocaleString()} skipped`);
            if (result.saved_copy) detail.push(`copy saved as ${result.saved_copy}`);
            catalogStatus(`Log import complete · ${detail.join(" · ")}.`, "#6ee7a2");
        } catch (error) {
            alert(error?.message || "Could not import this Prompt / Template log.");
            submit.disabled = false; cancel.disabled = false; submit.textContent = "IMPORT LOG"; update();
        }
    };

    body.append(intro, sourceHead, textarea, lineSummary, location); card.append(body, foot); refreshSubcategories(); update(); requestAnimationFrame(() => textarea.focus());
}

function renderPromptLibrary(list) {
    const kind = activePromptKind();
    const isTemplate = kind === "template";
    const accent = isTemplate ? "#ff4ab8" : "#35d7ff";
    const home = promptHomeCounts[kind] || { parents: {}, subcategories: {} };
    const total = Number(promptCorpusTotals[kind] || (isTemplate ? promptBlueprintTotal : promptAssetTotal) || 0);

    const shell = document.createElement("section");
    Object.assign(shell.style, { gridColumn: "1 / -1", minWidth: "0", display: "flex", flexDirection: "column", gap: "10px", marginBottom: "10px" });
    const header = document.createElement("div");
    Object.assign(header.style, { display: "flex", alignItems: "flex-start", flexWrap: "wrap", gap: "10px", padding: "13px 14px", borderRadius: "12px", border: `1px solid ${accent}55`, background: `linear-gradient(135deg,${accent}12,#0a090e 62%)` });
    const copy = document.createElement("div"); copy.style.flex = "1";
    const eyebrow = document.createElement("div"); eyebrow.textContent = isTemplate ? "REUSABLE FORMULAS" : "IDENTITY-NEUTRAL CATALOG"; Object.assign(eyebrow.style, { color: accent, font: "900 8px Segoe UI,Arial", letterSpacing: ".14em" });
    const title = document.createElement("h2"); title.textContent = isTemplate ? "Templates" : "Prompt Catalog"; Object.assign(title.style, { margin: "3px 0 4px", color: "#fff", font: "900 22px/1.05 Segoe UI,Arial" });
    const intro = document.createElement("div"); intro.textContent = isTemplate
        ? `${total.toLocaleString()} placeholder formulas. Every exact placeholder-bearing source lives here; browse Category → optional Subcategory → original Log.`
        : `${total.toLocaleString()} fully resolved, token-free prompts. Browse Category → optional Subcategory → original Log, then use Original log order when a sequence is meant to read progressively.`;
    Object.assign(intro.style, { maxWidth: "900px", color: "#aaa2b4", font: "10px/1.45 Segoe UI,Arial" }); copy.append(eyebrow, title, intro);
    const headerActions = document.createElement("div"); Object.assign(headerActions.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px" });
    const run = action(catalogRun ? "PREVIEW RUN ACTIVE" : "GENERATE PREVIEWS", accent); run.title = "Generate previews for the active Home, Collection, and filter scope"; run.disabled = Boolean(catalogRun); run.style.opacity = catalogRun ? ".62" : "1"; run.onclick = openGeneratePreviewsDialog;
    headerActions.append(run);
    const manageStructure = action("MANAGE STRUCTURE", "#b89aff"); manageStructure.title = `Rename, move, delete, and manually reorder ${isTemplate ? "Template" : "Prompt"} Categories${isTemplate ? " and Subcategories" : ", Subcategories, and Logs"}`; manageStructure.onclick = () => showPromptStructureManager(kind); headerActions.append(manageStructure);
    const importLog = action("IMPORT LOG", accent); importLog.title = "Import a local TXT log; placeholder lines route to Templates and resolved lines route to Prompts automatically"; importLog.onclick = showPromptLogImporter; headerActions.append(importLog);
    const queueFolder = action(promptFolderQueueActive ? "QUEUEING COLLECTION…" : "QUEUE THIS COLLECTION", "#6ee7a2");
    const hasFolder = Boolean(promptParent || activeCollection);
    queueFolder.disabled = promptFolderQueueActive || !hasFolder; queueFolder.style.opacity = queueFolder.disabled ? ".45" : "1";
    queueFolder.title = hasFolder ? `Queue up to the first ${PROMPT_QUEUE_CAP} ${isTemplate ? "templates" : "prompts"} in this filtered scope, then stop` : "Choose a Home or Collection first";
    queueFolder.onclick = () => void openPromptFolderQueueDialog(); headerActions.append(queueFolder);
    if (catalogRun) { const stop = action("STOP RUN", "#ff789b"); stop.title = "Stop this Preview Run and restore the prior workflow settings"; stop.onclick = () => stopCatalogRun(false); headerActions.append(stop); }
    header.append(copy, headerActions); shell.append(header);

    if (isTemplate) {
        const placeholders = document.createElement("div"); Object.assign(placeholders.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "5px", padding: "9px 10px", borderRadius: "10px", border: "1px solid #3a303b", background: "#0b0910" });
        const label = document.createElement("span"); label.textContent = "EXACT PLACEHOLDERS"; Object.assign(label.style, { marginRight: "4px", color: "#ff8fce", font: "900 7px Segoe UI,Arial", letterSpacing: ".11em" }); placeholders.append(label);
        const placeholderOrder = ["NAME", "OUTFIT", "OUTFIT_B", "OUTFIT_C", "BRAND", "ITEM", "SCENE", "LOCATION", "RARE_EVENT", "LIGHT_SOURCE", "ANALOG_CAPTURE_STYLE", "PRACTICAL_OUTER_LAYER", "SMALL_STYLING_DETAILS", "NATURAL_SURFACE", "TRIGGER"];
        for (const token of [...new Set([...placeholderOrder, ...Object.keys(promptPlaceholderCounts || {})])].filter(token => Number(promptPlaceholderCounts?.[token] || 0) || promptPlaceholderFilters.has(token))) {
            const count = Number(promptPlaceholderAvailableCounts[token] ?? promptPlaceholderCounts[token] ?? 0);
            const selected = promptPlaceholderFilters.has(token);
            const chip = action(`${token.replaceAll("_", " ")} · ${Number(count || 0).toLocaleString()}`, "#ff4ab8");
            Object.assign(chip.style, { padding: "5px 7px", fontSize: "7px", background: selected ? "rgba(255,74,184,.25)" : "#17131b", borderWidth: selected ? "2px" : "1px" });
            chip.onclick = () => { if (selected) promptPlaceholderFilters.delete(token); else promptPlaceholderFilters.add(token); promptPage = 0; queuePromptPageLoad(); };
            placeholders.append(chip);
        }
        if (promptPlaceholderFilters.size) { const clear = action("CLEAR", "#8f8997"); Object.assign(clear.style, { padding: "5px 7px", fontSize: "7px" }); clear.onclick = () => { promptPlaceholderFilters.clear(); promptPage = 0; queuePromptPageLoad(); }; placeholders.append(clear); }
        shell.append(placeholders);
    }

    const filters = document.createElement("div"); Object.assign(filters.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px", padding: "8px 9px", borderRadius: "10px", border: "1px solid #312c36", background: "rgba(9,8,13,.82)" });
    const search = document.createElement("input"); search.dataset.libraryFocusKey = "prompt-catalog-search"; search.type = "search"; search.value = promptSearch; search.placeholder = isTemplate ? "Search template wording…" : "Search prompt wording…"; Object.assign(search.style, { flex: "2 1 260px", minWidth: "190px", padding: "8px 9px", borderRadius: "8px", border: `1px solid ${accent}44`, outline: "none", background: "#09080d", color: "#fff" }); search.oninput = () => { promptSearch = search.value; promptPage = 0; queuePromptPageLoad(260); };
    filters.append(search);
    for (const [axis, label] of [["style", "style"], ["cast", "cast"], ["content", "content"], ["time", "time"], ["shot", "shot"]]) filters.append(promptFilterSelect(axis, label, accent));
    const ratings = makeSelect([["", "All ratings"], ["5", "5★ only"], ["4plus", "4★ +"], ["3plus", "3★ +"], ["2plus", "2★ +"], ["1plus", "1★ +"], ["rated", "Any rated"], ["unrated", "Unrated"]], promptRatingFilter); Object.assign(ratings.style, { flex: "1 1 135px", width: "auto", minWidth: "128px", padding: "8px 9px" }); ratings.onchange = () => { promptRatingFilter = ratings.value; promptPage = 0; queuePromptPageLoad(); }; filters.append(ratings);
    const sort = makeSelect([["preview_newest", "Newest Thumbnail"], ["source_order", "Original log order"], ["rating", "Highest rated"], ["name", "A → Z"], ["newest", "Newest catalog entry"]], promptSort || "preview_newest"); Object.assign(sort.style, { flex: "1 1 150px", width: "auto", minWidth: "150px", padding: "8px 9px" }); sort.onchange = () => { promptSort = sort.value; promptPage = 0; queuePromptPageLoad(); }; filters.append(sort); shell.append(filters);
    const selectBar = document.createElement("div"); Object.assign(selectBar.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px", padding: "7px 9px", borderRadius: "9px", border: `1px solid ${accent}44`, background: "#0b0910" });
    const selectMode = action(promptSelectionMode ? "DONE SELECTING" : "SELECT MULTIPLE", accent); selectMode.onclick = () => { promptSelectionMode = !promptSelectionMode; if (!promptSelectionMode) { selectedPromptIds.clear(); promptSelectAllFiltered = false; } render(); }; selectBar.append(selectMode);
    if (promptSelectionMode) {
        const page = action("SELECT PAGE", accent); page.onclick = () => { for (const item of promptAssets) if (item.prompt_id) selectedPromptIds.add(String(item.prompt_id)); render(); };
        const all = action(`SELECT ALL ${promptTotal.toLocaleString()}`, accent); all.onclick = () => { promptSelectAllFiltered = true; selectedPromptIds.clear(); render(); };
        const addCollection = action("ADD TO COLLECTION", "#6ee7a2"); addCollection.onclick = () => showPromptFolderEditor([...selectedPromptIds], promptSelectAllFiltered);
        const destinations = promptHomeUniverse[kind] || home;
        const moveParent = makeSelect([["", "Move to Home…"], ...Object.keys(destinations.parents || {}).map(value => [value, value])], "");
        const moveSub = makeSelect([["", "Then subcategory…"]], "");
        moveParent.onchange = () => { moveSub.replaceChildren(...[["", "Then subcategory…"], ...Object.keys(destinations.subcategories?.[moveParent.value] || {}).map(value => [value, value])].map(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; return option; })); };
        const move = action("MOVE", accent); move.onclick = () => { if (!moveParent.value || !moveSub.value) { alert("Choose a destination Home and subcategory."); return; } void bulkPromptAssets("move", moveParent.value, moveSub.value); };
        const archive = action("ARCHIVE / DELETE", "#ff789b"); archive.onclick = () => void bulkPromptAssets("delete");
        const auto = action("RESTORE AUTO HOME", "#b89aff"); auto.onclick = () => void bulkPromptAssets("auto_home");
        const deleteThumbs = action("DELETE PREVIEWS", "#ff9b5f"); deleteThumbs.onclick = () => void deleteSelectedPromptThumbnails();
        const generateThumbs = action("GENERATE PREVIEWS", "#6ee7a2"); generateThumbs.onclick = () => void regenerateSelectedPromptThumbnails();
        const status = document.createElement("span"); status.textContent = `${promptSelectionCount().toLocaleString()} selected`; Object.assign(status.style, { color: "#bcb4c4", font: "800 9px Segoe UI,Arial" });
        selectBar.append(page, all, addCollection, moveParent, moveSub, move, auto, deleteThumbs, generateThumbs, archive, status);
    }
    shell.append(selectBar);

    const workspace = document.createElement("div"); Object.assign(workspace.style, { display: "grid", gridTemplateColumns: "minmax(190px,240px) minmax(0,1fr)", gap: "10px", minHeight: "0" });
    const sidebar = document.createElement("aside"); Object.assign(sidebar.style, { alignSelf: "start", maxHeight: "calc(100vh - 300px)", overflow: "auto", borderRadius: "10px", border: `1px solid ${accent}44`, background: "#0c0a10" });
    const sideTitle = document.createElement("div"); sideTitle.textContent = "BROWSE"; Object.assign(sideTitle.style, { position: "sticky", top: "0", zIndex: "2", padding: "9px 10px", color: accent, background: "#0c0a10", borderBottom: "1px solid #302a34", font: "900 8px Segoe UI,Arial", letterSpacing: ".12em" }); sidebar.append(sideTitle);
    const folderButton = (labelText, count, selected, depth, onClick) => { const button = document.createElement("button"); button.type = "button"; const indent = depth >= 2 ? "7px 10px 7px 36px" : depth ? "7px 10px 7px 22px" : "9px 10px"; Object.assign(button.style, { width: "100%", display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: "8px", padding: indent, border: "0", borderBottom: "1px solid #25212a", borderLeft: selected ? `3px solid ${accent}` : "3px solid transparent", cursor: "pointer", textAlign: "left", color: selected ? "#fff" : depth >= 2 ? "#817a87" : depth ? "#aaa2b4" : "#d8d1dc", background: selected ? `${accent}18` : "transparent", font: `${selected ? "800" : "600"} ${depth >= 2 ? "8" : depth ? "9" : "10"}px Segoe UI,Arial` }); const name = document.createElement("span"); name.textContent = labelText; name.style.overflow = "hidden"; name.style.textOverflow = "ellipsis"; const amount = document.createElement("span"); amount.textContent = Number(count || 0).toLocaleString(); amount.style.color = selected ? accent : "#716b77"; button.append(name, amount); button.onclick = onClick; return button; };
    const showcaseTitle = document.createElement("div"); showcaseTitle.textContent = "COLLECTIONS"; Object.assign(showcaseTitle.style, { padding: "9px 10px 6px", color: "#b89aff", borderBottom: "1px solid #25212a", font: "900 7px Segoe UI,Arial", letterSpacing: ".11em" }); sidebar.append(showcaseTitle);
    const createFolder = folderButton("＋ New Collection", 0, false, 0, () => showPromptFolderEditor()); createFolder.style.color = "#d8c7ff"; sidebar.append(createFolder);
    for (const collection of promptShowcaseFolders()) sidebar.append(folderButton(String(collection.name || "Folder"), promptCollectionCount(collection.collection_id), String(activeCollection) === String(collection.collection_id), 1, () => { activeCollection = String(collection.collection_id); promptParent = ""; promptSubcategory = ""; promptLogPath = ""; promptLogLabel = ""; promptPage = 0; queuePromptPageLoad(); }));
    const catalogTitle = document.createElement("div"); catalogTitle.textContent = "HOMES"; Object.assign(catalogTitle.style, { padding: "11px 10px 6px", color: accent, borderBottom: "1px solid #25212a", font: "900 7px Segoe UI,Arial", letterSpacing: ".11em" }); sidebar.append(catalogTitle);
    sidebar.append(folderButton(isTemplate ? "All Templates" : "All Prompts", total, !promptParent && !activeCollection, 0, () => { activeCollection = ""; promptParent = ""; promptSubcategory = ""; promptLogPath = ""; promptLogLabel = ""; promptPage = 0; queuePromptPageLoad(); }));
    for (const [parent, count] of Object.entries(home.parents || {})) {
        const parentSelected = promptParent === parent;
        sidebar.append(folderButton(parent, count, parentSelected && !promptSubcategory && !activeCollection, 0, () => { activeCollection = ""; promptParent = parent; promptSubcategory = ""; promptLogPath = ""; promptLogLabel = ""; promptPage = 0; queuePromptPageLoad(); }));
        if (parentSelected && !activeCollection) {
            const directLogs = home.logs?.[parent]?.[""] || {};
            for (const [path, info] of Object.entries(directLogs)) {
                const label = String(info?.label || path.split("/").pop()?.replace(/\.txt$/i, "") || "Log");
                sidebar.append(folderButton(label, Number(info?.count || 0), promptLogPath === path, 1, () => { activeCollection = ""; promptSubcategory = ""; promptLogPath = path; promptLogLabel = label; promptSort = "source_order"; promptPage = 0; queuePromptPageLoad(); }));
            }
            for (const [subcategory, childCount] of Object.entries(home.subcategories?.[parent] || {}).filter(([subcategory]) => Boolean(subcategory))) {
                const subSelected = promptSubcategory === subcategory;
                sidebar.append(folderButton(subcategory, childCount, subSelected && !promptLogPath, 1, () => { activeCollection = ""; promptSubcategory = subcategory; promptLogPath = ""; promptLogLabel = ""; promptPage = 0; queuePromptPageLoad(); }));
                if (subSelected) {
                    const logs = home.logs?.[parent]?.[subcategory] || {};
                    for (const [path, info] of Object.entries(logs)) {
                        const label = String(info?.label || path.split("/").pop()?.replace(/\.txt$/i, "") || "Log");
                        sidebar.append(folderButton(label, Number(info?.count || 0), promptLogPath === path, 2, () => { activeCollection = ""; promptLogPath = path; promptLogLabel = label; promptSort = "source_order"; promptPage = 0; queuePromptPageLoad(); }));
                    }
                }
            }
        }
    }

    const main = document.createElement("main"); Object.assign(main.style, { minWidth: "0", display: "flex", flexDirection: "column", gap: "8px" });
    const pageBar = document.createElement("div"); Object.assign(pageBar.style, { display: "flex", alignItems: "center", gap: "7px", padding: "3px 1px" });
    const location = document.createElement("strong"); location.textContent = activeCollection ? `Collection / ${currentPromptFolderLabel()}` : [promptParent || (isTemplate ? "All Templates" : "All Prompts"), promptSubcategory, promptLogLabel].filter(Boolean).join(" / "); Object.assign(location.style, { flex: "1", minWidth: "0", color: "#eee8f0", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "800 10px Segoe UI,Arial" });
    const pageCount = Math.max(1, Math.ceil(promptTotal / PROMPT_PAGE_SIZE)); const start = promptTotal ? promptPage * PROMPT_PAGE_SIZE + 1 : 0; const end = Math.min(promptTotal, promptPage * PROMPT_PAGE_SIZE + promptAssets.length);
    const range = document.createElement("span"); range.dataset.promptPageRange = ""; range.textContent = promptLoading ? "Loading…" : `${start.toLocaleString()}–${end.toLocaleString()} of ${promptTotal.toLocaleString()}`; Object.assign(range.style, { color: "#8f8997", font: "800 8px Segoe UI,Arial" });
    const prev = action("←", "#8f8997"), next = action("→", "#8f8997"); prev.disabled = promptPage <= 0; next.disabled = promptPage >= pageCount - 1; prev.onclick = () => { promptPage = Math.max(0, promptPage - 1); queuePromptPageLoad(); }; next.onclick = () => { promptPage += 1; queuePromptPageLoad(); }; for (const button of [prev, next]) Object.assign(button.style, { padding: "5px 8px", opacity: button.disabled ? ".4" : "1" }); pageBar.append(location, range, prev, next); main.append(pageBar);

    const cards = document.createElement("div"); Object.assign(cards.style, { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(330px,100%),1fr))", gap: "8px", alignItems: "start" });
    if (!promptAssets.length) { const empty = document.createElement("div"); empty.textContent = promptLoading ? "Loading this folder…" : "No records match this combination. Remove a filter or choose a wider folder."; Object.assign(empty.style, { gridColumn: "1 / -1", padding: "38px", color: "#9d96a4", textAlign: "center", border: "1px dashed #3b3540", borderRadius: "10px" }); cards.append(empty); }
    for (const asset of promptAssets) {
        const hasPreview = Boolean(asset.preview_ref);
        const card = document.createElement("article"); Object.assign(card.style, { minWidth: "0", minHeight: "184px", display: "grid", gridTemplateColumns: hasPreview ? "112px minmax(0,1fr)" : "minmax(0,1fr)", overflow: "hidden", borderRadius: "10px", border: `1px solid ${accent}44`, background: `linear-gradient(145deg,${accent}0d,#0b0910 72%)` });
        if (hasPreview) { const image = document.createElement("img"); image.loading = "lazy"; image.decoding = "async"; const version = String(asset.preview_updated_at || asset.updated_at || ""); image.src = creativeLibraryPreviewUrl(asset.preview_ref, version); image.alt = ""; image.title = "Inspect thumbnail and browse the current gallery scope"; image.role = "button"; image.tabIndex = 0; image.onclick = () => openPromptThumbnail(asset); image.onkeydown = event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); image.click(); } }; Object.assign(image.style, { width: "112px", height: "100%", minHeight: "156px", objectFit: "cover", display: "block", cursor: "zoom-in", background: "#060509" }); card.append(image); }
        const body = document.createElement("div"); Object.assign(body.style, { minWidth: "0", display: "flex", flexDirection: "column", gap: "6px", padding: "9px" });
        if (promptSelectionMode) { const check = document.createElement("input"); check.type = "checkbox"; check.checked = promptSelectAllFiltered || selectedPromptIds.has(String(asset.prompt_id || "")); check.onchange = () => togglePromptSelection(asset.prompt_id); Object.assign(check.style, { alignSelf: "flex-end", accentColor: accent, cursor: "pointer" }); body.append(check); }
        const source = activePromptSource(asset); const sourceLine = Number(source?.line_number || 0);
        const meta = document.createElement("div"); meta.textContent = [asset.primary_parent || "Other", asset.primary_subcategory || "", promptLogLabel || ""].filter(Boolean).join(" / ") + (sourceLine ? ` · #${sourceLine}` : ""); Object.assign(meta.style, { color: accent, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "900 7px Segoe UI,Arial", letterSpacing: ".06em" });
        const text = document.createElement("div"); text.textContent = asset.value || ""; text.title = asset.value || ""; Object.assign(text.style, { color: "#eee9f0", font: "10px/1.42 Segoe UI,Arial", display: "-webkit-box", WebkitLineClamp: hasPreview ? "5" : "4", WebkitBoxOrient: "vertical", overflow: "hidden" });
        const tags = document.createElement("div"); Object.assign(tags.style, { display: "flex", flexWrap: "wrap", gap: "4px", minHeight: "14px" });
        if (asset.collections?.length) { const folderTag = document.createElement("span"); folderTag.textContent = `COLLECTION · ${asset.collections[0].name}`; folderTag.title = asset.collections.map(item => item.name).join(", "); Object.assign(folderTag.style, { maxWidth: "130px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", padding: "2px 5px", borderRadius: "999px", color: asset.collections[0].color || "#d8c7ff", border: `1px solid ${asset.collections[0].color || "#b89aff"}55`, font: "800 7px Segoe UI,Arial" }); tags.append(folderTag); }
        if (promptAssetResolvedText(asset)) { const resolvedTag = document.createElement("span"); resolvedTag.textContent = "SOURCE + THUMB COMBO"; resolvedTag.title = "Load either the reusable source or the thumbnail-matched OUTFIT / SCENE combination"; Object.assign(resolvedTag.style, { padding: "2px 5px", borderRadius: "999px", color: "#bfffe0", border: "1px solid #6ee7a244", font: "800 7px Segoe UI,Arial" }); tags.append(resolvedTag); }
        if (isTemplate) for (const token of String(asset.placeholder_signature || "").split("+").filter(Boolean)) { const tag = document.createElement("span"); tag.textContent = token; Object.assign(tag.style, { padding: "2px 5px", borderRadius: "999px", color: "#ffd8ed", border: "1px solid #ff4ab844", font: "800 7px Segoe UI,Arial" }); tags.append(tag); }
        else for (const labelText of PROMPT_FACET_AXES.flatMap(axis => asset.facets?.[axis] || []).filter(value => value && value !== "Other").slice(0, 3)) { const tag = document.createElement("span"); tag.textContent = labelText; Object.assign(tag.style, { padding: "2px 5px", borderRadius: "999px", color: "#bcefff", border: "1px solid #35d7ff33", font: "700 7px Segoe UI,Arial" }); tags.append(tag); }
        const stats = document.createElement("div"); const cardSeed = promptAssetResolvedSeed(asset); stats.textContent = `quality ${Math.round(Number(asset.quality_score || 0))} · ${Number(asset.exact_source_occurrences || asset.source_count || 1).toLocaleString()} source occurrence${Number(asset.exact_source_occurrences || asset.source_count || 1) === 1 ? "" : "s"}${cardSeed != null ? ` · seed ${cardSeed}` : ""}`; Object.assign(stats.style, { color: "#6f6975", font: "7px Segoe UI,Arial" });
        const rating = document.createElement("div"); Object.assign(rating.style, { display: "flex", alignItems: "center", gap: "1px" }); for (let star = 1; star <= 5; star += 1) { const button = document.createElement("button"); button.type = "button"; button.textContent = star <= Number(asset.rating || 0) ? "★" : "☆"; button.title = `${star} star${star === 1 ? "" : "s"}`; Object.assign(button.style, { padding: "0", border: "0", cursor: "pointer", color: star <= Number(asset.rating || 0) ? "#f6e65a" : "#5f5964", background: "transparent", font: "13px/1 Segoe UI,Arial" }); button.onclick = () => void setPromptAssetRating(asset, Number(asset.rating || 0) === star ? 0 : star); rating.append(button); }
        const quickActions = document.createElement("div"); Object.assign(quickActions.style, { display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: "4px", marginTop: "auto" });
        const queue = action("QUEUE", "#6ee7a2"); queue.dataset.queueLabel = "QUEUE"; queue.title = `Queue this ${isTemplate ? "template" : "prompt"} after the pending queue`; queue.onclick = () => void queuePromptAsset(asset, queue, 0); Object.assign(queue.style, { width: "100%", minWidth: "0", padding: "6px 5px", fontSize: "7px" });
        const queueNext = action("QUEUE NEXT", "#f6e65a"); queueNext.dataset.queueLabel = "QUEUE NEXT"; queueNext.title = `Put this ${isTemplate ? "template" : "prompt"} at the front of the pending queue`; queueNext.onclick = () => void queuePromptAsset(asset, queueNext, -1); Object.assign(queueNext.style, { width: "100%", minWidth: "0", padding: "6px 4px", fontSize: "7px" });
        const folder = action("＋ COLLECTION", "#b89aff"); folder.title = `Add this ${isTemplate ? "template" : "prompt"} to a Collection`; folder.onclick = () => showPromptFolderEditor([String(asset.prompt_id || "")], false); Object.assign(folder.style, { width: "100%", minWidth: "0", padding: "6px 4px", fontSize: "7px" }); quickActions.append(queue, queueNext, folder);
        const buttons = document.createElement("div"); Object.assign(buttons.style, { display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: "4px", marginTop: "0", minWidth: "0" });
        const compactButton = (button) => Object.assign(button.style, { minWidth: "0", width: "100%", padding: "5px 2px", fontSize: "7px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
        const load = action("LOAD", accent); compactButton(load); load.title = isTemplate ? "Load this template" : "Load this prompt"; load.onclick = () => showPromptApply(asset);
        const copyButton = action("COPY", "#8f8997"); compactButton(copyButton); copyButton.title = "Copy text"; copyButton.onclick = async () => { try { await navigator.clipboard.writeText(String(asset.value || "")); copyButton.textContent = "DONE"; setTimeout(() => { copyButton.textContent = "COPY"; }, 700); } catch (error) { alert("Could not copy this record."); } };
        const edit = action("EDIT", "#f6e65a"); compactButton(edit); edit.title = isTemplate ? "Edit this saved Template" : "Edit this saved Prompt"; edit.onclick = () => void editPromptAssetCard(asset);
        const view = action("VIEW", "#67e8f9"); compactButton(view); view.title = "Open Library Inspector"; view.onclick = () => openPromptThumbnail(asset);
        buttons.append(load, copyButton, edit, view); body.append(meta, text, tags, stats, rating, quickActions, buttons); card.append(body); cards.append(card);
    }
    main.append(cards); workspace.append(sidebar, main); shell.append(workspace); list.append(shell);
}

async function editPromptAssetCard(asset, onSaved = null) {
    const isTemplate = String(asset?.kind || '') === 'template';
    const { overlay, card, close } = collectionModal(isTemplate ? 'EDIT TEMPLATE' : 'EDIT PROMPT', '760px');
    const body = document.createElement('div');
    Object.assign(body.style, { display: 'flex', flexDirection: 'column', gap: '8px' });
    const note = document.createElement('div');
    note.textContent = 'Edit the text, then save in place or save a copy. Existing thumbnails, folders, and metadata stay attached whenever possible.';
    Object.assign(note.style, { color: '#bcb4c4', font: '10px/1.5 Segoe UI,Arial' });
    const textarea = document.createElement('textarea');
    textarea.value = String(asset?.value || '');
    Object.assign(textarea.style, { minHeight: '180px', resize: 'vertical', padding: '10px', borderRadius: '10px', border: '1px solid #3a303b', background: '#09080d', color: '#fff', font: '12px/1.5 Segoe UI,Arial' });
    const actions = document.createElement('div');
    Object.assign(actions.style, { display: 'flex', gap: '8px', justifyContent: 'flex-end', flexWrap: 'wrap' });
    const cancel = action('CANCEL', '#8f8997');
    const saveCopy = action('SAVE AS COPY', '#b89aff');
    const save = action('SAVE', '#6ee7a2');
    const submit = async (mode) => {
        const value = String(textarea.value || '').trim().replace(/\s+/g, ' ');
        if (!value) { alert('Prompt text is required.'); return; }
        for (const button of [cancel, saveCopy, save]) button.disabled = true;
        try {
            const result = await request(`/prompt-assets/${encodeURIComponent(String(asset.prompt_id || ''))}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    value,
                    mode,
                    kind: String(asset.kind || 'prompt'),
                    recipe_id: String(asset.recipe_id || ''),
                    parent: String(asset.primary_parent || ''),
                    subcategory: String(asset.primary_subcategory || ''),
                }),
            });
            if (mode !== 'copy') { asset.value = result.value || value; if (result.prompt_id) asset.prompt_id = result.prompt_id; onSaved?.(asset); }
            close();
            promptAssetRevision += 1;
            queuePromptPageLoad();
            catalogStatus(mode === 'copy' ? 'Saved copy into Creative Library.' : 'Prompt card updated.', '#6ee7a2');
        } catch (error) {
            alert(error.message || 'Could not save this card.');
        } finally {
            for (const button of [cancel, saveCopy, save]) button.disabled = false;
        }
    };
    cancel.onclick = close;
    saveCopy.onclick = () => void submit('copy');
    save.onclick = () => void submit('save');
    actions.append(cancel, saveCopy, save);
    body.append(note, textarea, actions);
    card.append(body);
    document.body.append(overlay);
    textarea.focus();
    textarea.select();
}

function openPromptsForFragment(fragment) {
    activeView = "prompts"; promptVaultOpen = true; resetPromptNavigation(); promptSearch = String(fragment?.value || "");
    refreshLibraryChrome(); renderCollectionControls(); renderBulkControls(); render(); queuePromptPageLoad();
}

function resetFragmentSelection(exitMode = false) {
    selectedFragmentIds.clear();
    fragmentSelectAllFiltered = false;
    if (exitMode) fragmentSelectionMode = false;
}

function fragmentSelectionCount() {
    return fragmentSelectAllFiltered ? Number(fragmentTotal || 0) : selectedFragmentIds.size;
}

function toggleFragmentSelection(fragmentId) {
    const id = String(fragmentId || ""); if (!id) return;
    if (fragmentSelectAllFiltered) {
        fragmentSelectAllFiltered = false;
        selectedFragmentIds = new Set(fragmentRows.map(fragment => String(fragment.fragment_id || "")).filter(Boolean));
    }
    if (selectedFragmentIds.has(id)) selectedFragmentIds.delete(id); else selectedFragmentIds.add(id);
    fragmentSelectionMode = true; render();
}

function selectFragmentPage() {
    fragmentSelectionMode = true; fragmentSelectAllFiltered = false;
    for (const fragment of fragmentRows) if (fragment.fragment_id) selectedFragmentIds.add(String(fragment.fragment_id));
    render();
}

function selectAllFragmentMatches() {
    if (!fragmentTotal) return;
    fragmentSelectionMode = true; fragmentSelectAllFiltered = true; selectedFragmentIds.clear(); render();
}

function describeFragmentBulkChange(changes = {}) {
    if (changes.state === "approved") return "approve";
    if (changes.state === "review") return "send to Needs review";
    if (changes.state === "rejected") return "hide";
    if (changes.reset_role) return "restore the mined category for";
    if (changes.role) return `move to ${fragmentMeta(changes.role)[0]}`;
    return "update";
}

async function bulkUpdateFragments(changes = {}, explicitIds = null) {
    const ids = Array.isArray(explicitIds) ? explicitIds.map(value => String(value || "")).filter(Boolean) : [...selectedFragmentIds];
    const allFiltered = !explicitIds && fragmentSelectAllFiltered;
    const amount = allFiltered ? Number(fragmentTotal || 0) : ids.length;
    if (!amount) { alert("Select a page, specific Ingredients, or all matches first."); return; }
    const operation = describeFragmentBulkChange(changes);
    if (allFiltered && amount > FRAGMENT_PAGE_SIZE && !confirm(`${operation[0].toUpperCase()}${operation.slice(1)} all ${amount.toLocaleString()} Ingredients in the current filtered view?\n\nThis changes the derived catalog only. Canonical Prompt sources stay untouched.`)) return;
    try {
        const result = await request("/fragments/bulk", {
            method: "POST",
            body: JSON.stringify({
                fragment_ids: ids,
                all_filtered: allFiltered,
                filters: { q: fragmentSearch, role: fragmentRole, state: fragmentState },
                ...changes,
            }),
        });
        if (result.summary && typeof result.summary === "object") fragmentSummary = result.summary;
        resetFragmentSelection(true);
        await loadFragmentPage();
        catalogStatus(`Ingredient Catalog · ${Number(result.changed || amount).toLocaleString()} updated${Number(result.merged || 0) ? ` · ${Number(result.merged).toLocaleString()} duplicate${Number(result.merged) === 1 ? "" : "s"} merged` : ""}.`, "#6ee7a2");
    } catch (error) { alert(error.message || "Could not update the selected Ingredients."); }
}

function renderFragmentLibrary(list) {
    const shell = document.createElement("section"); Object.assign(shell.style, { gridColumn: "1 / -1", padding: "16px", borderRadius: "15px", border: "1px solid #b89aff55", background: "radial-gradient(circle at 10% 5%,rgba(184,154,255,.13),transparent 30%),linear-gradient(145deg,#121018,#09080d 72%)" });
    const top = document.createElement("div"); Object.assign(top.style, { display: "flex", alignItems: "flex-start", flexWrap: "wrap", gap: "10px" });
    const copy = document.createElement("div"); copy.style.flex = "1"; const eyebrow = document.createElement("div"); eyebrow.textContent = "PROMPT PARTS · ADD-TO-BUILDER CATALOG"; Object.assign(eyebrow.style, { color: "#b89aff", font: "900 9px Segoe UI,Arial", letterSpacing: ".14em" });
    const title = document.createElement("h2"); title.textContent = "Ingredient Catalog"; Object.assign(title.style, { margin: "4px 0", color: "#fff", font: "900 24px/1 Segoe UI,Arial" });
    const intro = document.createElement("div"); intro.textContent = `${Number(promptAssetTotal || 0).toLocaleString()} canonical Prompts are dissected into reusable Subjects, concepts, poses, lighting, typography, identity hooks, styling, and more. Shop the Ready aisles like Wardrobe; open Needs review only when you want to curate the miner.`; Object.assign(intro.style, { maxWidth: "900px", color: "#aaa2b4", font: "11px/1.5 Segoe UI,Arial" }); copy.append(eyebrow, title, intro);
    const rebuild = action("REBUILD FROM SOURCES", "#ff9b5f"); rebuild.title = "Re-read Prompt logs and atomically rebuild the derived Prompt and Ingredient indexes"; rebuild.onclick = async () => { try { rebuild.disabled = true; rebuild.textContent = "MINING CORPUS…"; catalogStatus("Re-indexing canonical Prompt sources and mining reusable Ingredients…", "#ff9b5f"); const result = await request("/fragments/rebuild", { method: "POST", body: "{}" }); fragmentPage = 0; await load(); await loadFragmentPage(); const total = Number(result.fragment_index?.total || fragmentSummary.total || 0); catalogStatus(`Ingredient index rebuilt · ${total.toLocaleString()} source-linked elements.`, "#6ee7a2"); } catch (error) { alert(error.message || "Could not rebuild the Ingredient index."); } finally { rebuild.disabled = false; rebuild.textContent = "REBUILD FROM SOURCES"; } };
    top.append(copy, rebuild); shell.append(top);
    const metrics = document.createElement("div"); Object.assign(metrics.style, { display: "flex", flexWrap: "wrap", gap: "7px", marginTop: "13px" });
    const readyCount = Number(fragmentSummary.states?.approved || 0) + Number(fragmentSummary.states?.suggested || 0);
    for (const [value, label, color] of [[readyCount, "READY TO SHOP", "#35d7ff"], [fragmentSummary.states?.approved || 0, "CURATED", "#6ee7a2"], [fragmentSummary.states?.review || 0, "OPTIONAL REVIEW QUEUE", "#f6e65a"], [fragmentSummary.sources?.["source-theme"] || 0, "SOURCE THEMES", "#b89aff"]]) { const item = document.createElement("div"); Object.assign(item.style, { minWidth: "135px", padding: "7px 9px", borderRadius: "8px", border: `1px solid ${color}33`, background: `${color}08` }); const number = document.createElement("strong"); number.textContent = Number(value || 0).toLocaleString(); Object.assign(number.style, { display: "block", color, font: "900 14px Segoe UI,Arial" }); const caption = document.createElement("span"); caption.textContent = label; Object.assign(caption.style, { color: "#817b88", font: "7px Segoe UI,Arial", letterSpacing: ".07em" }); item.append(number, caption); metrics.append(item); }
    shell.append(metrics); list.append(shell);

    const controls = document.createElement("section"); Object.assign(controls.style, { gridColumn: "1 / -1", display: "flex", flexDirection: "column", gap: "8px", padding: "10px", borderRadius: "11px", border: "1px solid #3a3442", background: "rgba(9,8,13,.76)" });
    const aisleLabel = document.createElement("div"); aisleLabel.textContent = "SHOP BY INGREDIENT AISLE"; Object.assign(aisleLabel.style, { color: "#8f8997", font: "900 7px Segoe UI,Arial", letterSpacing: ".11em" });
    const roles = document.createElement("div"); Object.assign(roles.style, { display: "flex", flexWrap: "wrap", gap: "5px" });
    for (const role of ["", ...Object.keys(FRAGMENT_ROLE_META)]) { const [label, color] = role ? fragmentMeta(role) : ["ALL AISLES", "#b89aff"]; const count = role ? Number(fragmentSummary.roles?.[role] || 0) : Number(fragmentSummary.total || 0); if (role && !count) continue; const button = action(`${label} · ${count.toLocaleString()}`, color); Object.assign(button.style, { padding: "6px 8px", fontSize: "7px", background: fragmentRole === role ? `${color}22` : "#17141c", borderWidth: fragmentRole === role ? "2px" : "1px" }); button.onclick = () => { fragmentRole = role; fragmentPage = 0; resetFragmentSelection(true); queueFragmentPageLoad(); }; roles.append(button); }
    const filters = document.createElement("div"); Object.assign(filters.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px" });
    const search = document.createElement("input"); search.type = "search"; search.value = fragmentSearch; search.placeholder = "Search Ingredients, categories, themes…"; Object.assign(search.style, { flex: "1 1 260px", minWidth: "180px", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", outline: "none", background: "#09080d", color: "#fff" }); search.oninput = () => { fragmentSearch = search.value; fragmentPage = 0; resetFragmentSelection(true); queueFragmentPageLoad(180); };
    const state = makeSelect([["ready", "Ready to shop"], ["review", "Needs review"], ["active", "All active"], ["approved", "Curated only"], ["suggested", "High recurrence"]], fragmentState); state.onchange = () => { fragmentState = state.value; fragmentPage = 0; resetFragmentSelection(true); queueFragmentPageLoad(); };
    const sort = makeSelect([["rank", "Most sourced"], ["confidence", "Confidence"], ["role", "Role order"], ["name", "A → Z"]], fragmentSort); sort.onchange = () => { fragmentSort = sort.value; fragmentPage = 0; queueFragmentPageLoad(); };
    const prev = action("←", "#8f8997"); const next = action("→", "#8f8997"); const pageCount = Math.max(1, Math.ceil(fragmentTotal / FRAGMENT_PAGE_SIZE)); prev.disabled = fragmentPage <= 0; next.disabled = fragmentPage >= pageCount - 1; prev.onclick = () => { fragmentPage = Math.max(0, fragmentPage - 1); queueFragmentPageLoad(); }; next.onclick = () => { fragmentPage += 1; queueFragmentPageLoad(); };
    const range = document.createElement("span"); const start = fragmentTotal ? fragmentPage * FRAGMENT_PAGE_SIZE + 1 : 0; const end = Math.min(fragmentTotal, fragmentPage * FRAGMENT_PAGE_SIZE + fragmentRows.length); range.textContent = fragmentLoading ? "Mining / loading…" : `${start.toLocaleString()}–${end.toLocaleString()} of ${fragmentTotal.toLocaleString()}`; Object.assign(range.style, { minWidth: "112px", textAlign: "center", color: "#aaa2b4", font: "800 8px Segoe UI,Arial" });
    filters.append(search, state, sort, prev, range, next);

    const selection = document.createElement("div"); Object.assign(selection.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px", paddingTop: "8px", borderTop: "1px solid #302b36" });
    const selectToggle = action(fragmentSelectionMode ? "DONE SELECTING" : "SELECT INGREDIENTS", "#35d7ff"); selectToggle.onclick = () => { fragmentSelectionMode = !fragmentSelectionMode; if (!fragmentSelectionMode) resetFragmentSelection(false); render(); }; selection.append(selectToggle);
    if (fragmentSelectionMode) {
        const selectPage = action(`SELECT PAGE · ${fragmentRows.length.toLocaleString()}`, "#35d7ff"); selectPage.onclick = selectFragmentPage;
        const selectMatches = action(`SELECT ALL MATCHES · ${fragmentTotal.toLocaleString()}`, "#ff4ab8"); selectMatches.onclick = selectAllFragmentMatches;
        const selectedCount = document.createElement("span"); selectedCount.textContent = fragmentSelectAllFiltered ? `ALL ${fragmentSelectionCount().toLocaleString()} MATCHES` : `${fragmentSelectionCount().toLocaleString()} SELECTED`; Object.assign(selectedCount.style, { minHeight: "28px", display: "inline-flex", alignItems: "center", padding: "0 8px", borderRadius: "7px", border: "1px solid #ff4ab866", color: "#ffc1e6", background: "rgba(255,74,184,.08)", font: "800 8px Segoe UI,Arial", letterSpacing: ".05em" });
        const approve = action("APPROVE", "#6ee7a2"); approve.onclick = () => bulkUpdateFragments({ state: "approved" });
        const needsReview = action("NEEDS REVIEW", "#f6e65a"); needsReview.onclick = () => bulkUpdateFragments({ state: "review" });
        const hide = action("HIDE", "#ff4ab8"); hide.onclick = () => bulkUpdateFragments({ state: "rejected" });
        const categoryChoices = [["", "Change category…"], ...Object.keys(FRAGMENT_ROLE_META).filter(role => role !== "subject_structure").map(role => [role, fragmentMeta(role)[0]])];
        const category = makeSelect(categoryChoices, ""); Object.assign(category.style, { width: "175px", padding: "7px 8px", fontSize: "9px" });
        const change = action("APPLY CATEGORY", "#b89aff"); change.onclick = () => { if (!category.value) { alert("Choose an Ingredient category first."); return; } void bulkUpdateFragments({ role: category.value }); };
        const reset = action("RESTORE AUTO TYPE", "#8f8997"); reset.onclick = () => bulkUpdateFragments({ reset_role: true });
        const clear = action("CLEAR SELECTION", "#8f8997"); clear.onclick = () => { resetFragmentSelection(false); render(); };
        const activeSelection = fragmentSelectionCount() > 0;
        for (const button of [approve, needsReview, hide, change, reset, clear]) { button.disabled = !activeSelection; button.style.opacity = activeSelection ? "1" : ".38"; }
        selection.append(selectPage, selectMatches, selectedCount, approve, needsReview, hide, category, change, reset, clear);
    } else {
        const hint = document.createElement("span"); hint.textContent = "Select one page or every filtered match, then approve, hide, or reclassify the batch."; Object.assign(hint.style, { color: "#817b88", font: "8px Segoe UI,Arial" }); selection.append(hint);
    }
    controls.append(aisleLabel, roles, filters, selection); list.append(controls);

    if (!fragmentRows.length) { const empty = document.createElement("div"); empty.textContent = fragmentLoading ? "Mining and loading source-linked Ingredients…" : "No Ingredients match this view."; Object.assign(empty.style, { gridColumn: "1 / -1", padding: "38px", textAlign: "center", color: "#8f8997" }); list.append(empty); return; }
    for (const fragment of fragmentRows) {
        const [label, color] = fragmentMeta(fragment.role); const selected = fragmentSelectAllFiltered || selectedFragmentIds.has(String(fragment.fragment_id || "")); const card = document.createElement("div"); Object.assign(card.style, { minWidth: "0", minHeight: "190px", display: "flex", flexDirection: "column", gap: "8px", padding: "11px", borderRadius: "11px", cursor: fragmentSelectionMode ? "pointer" : "default", border: selected ? "2px solid #ff4ab8" : `1px solid ${color}55`, background: selected ? `linear-gradient(145deg,rgba(255,74,184,.17),${color}12,#0b0910 70%)` : `linear-gradient(145deg,${color}10,#0b0910 68%)`, boxShadow: selected ? "0 0 0 1px rgba(255,74,184,.18)" : "none" });
        card.onclick = () => { if (fragmentSelectionMode) toggleFragmentSelection(fragment.fragment_id); };
        const role = document.createElement("div"); role.textContent = `${selected ? "✓ · " : ""}${label} · ${String(fragment.review_state || "").toUpperCase()}${fragment.role_override ? " · HUMAN TYPE" : ""}`; Object.assign(role.style, { color: selected ? "#ff9bd4" : color, font: "900 8px Segoe UI,Arial", letterSpacing: ".08em" });
        const text = document.createElement("div"); text.textContent = fragment.value || ""; text.title = fragment.value || ""; Object.assign(text.style, { flex: "1", color: "#f0ebf3", font: "10px/1.45 Segoe UI,Arial", display: "-webkit-box", WebkitLineClamp: "6", WebkitBoxOrient: "vertical", overflow: "hidden" });
        const provenance = document.createElement("div"); const source = fragment.source_files?.[0]?.source_path || fragment.source_kind || "corpus"; provenance.textContent = `${Number(fragment.prompt_count || 0).toLocaleString()} prompts · ${Number(fragment.source_count || 0).toLocaleString()} sources · ${Math.round(Number(fragment.confidence || 0) * 100)}% · ${source}`; provenance.title = (fragment.source_files || []).map(item => item.source_path).join("\n"); Object.assign(provenance.style, { color: "#77717d", font: "7px/1.35 Segoe UI,Arial", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
        const buttons = document.createElement("div"); Object.assign(buttons.style, { display: "grid", gridTemplateColumns: "1fr auto auto", gap: "5px" });
        const add = action("ADD TO BUILDER", color); Object.assign(add.style, { padding: "6px 7px", fontSize: "8px" }); add.onclick = event => { event.stopPropagation(); addBuilderFragment(fragment); };
        const sources = action("PROMPTS", "#35d7ff"); sources.title = "Find canonical Prompts containing this exact Ingredient"; Object.assign(sources.style, { padding: "6px 7px", fontSize: "8px" }); sources.onclick = event => { event.stopPropagation(); openPromptsForFragment(fragment); };
        const review = action("EDIT TYPE", "#8f8997"); Object.assign(review.style, { padding: "6px 7px", fontSize: "8px" });
        buttons.append(add, sources, review); const reviewRow = document.createElement("div"); Object.assign(reviewRow.style, { display: "none", gap: "5px", flexWrap: "wrap" });
        for (const [stateValue, stateLabel, stateColor] of [["approved", "APPROVE", "#6ee7a2"], ["review", "NEEDS REVIEW", "#f6e65a"], ["rejected", "HIDE", "#ff4ab8"]]) { const button = action(stateLabel, stateColor); Object.assign(button.style, { padding: "5px 6px", fontSize: "7px" }); button.onclick = event => { event.stopPropagation(); void bulkUpdateFragments({ state: stateValue }, [fragment.fragment_id]); }; reviewRow.append(button); }
        const category = makeSelect(Object.keys(FRAGMENT_ROLE_META).filter(roleKey => roleKey !== "subject_structure").map(roleKey => [roleKey, fragmentMeta(roleKey)[0]]), fragment.role); Object.assign(category.style, { flex: "1 1 150px", minWidth: "145px", padding: "5px 6px", fontSize: "8px" }); category.onclick = event => event.stopPropagation();
        const applyCategory = action("CHANGE CATEGORY", "#b89aff"); Object.assign(applyCategory.style, { padding: "5px 6px", fontSize: "7px" }); applyCategory.onclick = event => { event.stopPropagation(); void bulkUpdateFragments({ role: category.value }, [fragment.fragment_id]); };
        const resetCategory = action("AUTO TYPE", "#8f8997"); Object.assign(resetCategory.style, { padding: "5px 6px", fontSize: "7px", display: fragment.role_override ? "inline-flex" : "none" }); resetCategory.onclick = event => { event.stopPropagation(); void bulkUpdateFragments({ reset_role: true }, [fragment.fragment_id]); };
        reviewRow.append(category, applyCategory, resetCategory);
        review.onclick = event => { event.stopPropagation(); reviewRow.style.display = reviewRow.style.display === "none" ? "flex" : "none"; };
        reviewRow.onclick = event => event.stopPropagation();
        card.append(role, text, provenance, buttons, reviewRow); list.append(card);
    }
}

function renderWorkshopIngredients(list) {
    const shell = document.createElement("section"); Object.assign(shell.style, { gridColumn: "1 / -1", minWidth: "0", marginBottom: "10px", borderRadius: "11px", border: "1px solid #b89aff55", background: "#0a090e", overflow: "hidden" });
    const head = document.createElement("div"); Object.assign(head.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "8px", padding: "10px 12px", borderBottom: "1px solid #302a35", background: "linear-gradient(90deg,rgba(184,154,255,.12),transparent 55%)" });
    const copy = document.createElement("div"); copy.style.flex = "1"; const title = document.createElement("strong"); title.textContent = "INGREDIENT DRAWER"; Object.assign(title.style, { display: "block", color: "#d3c3ff", font: "900 10px Segoe UI,Arial", letterSpacing: ".11em" }); const note = document.createElement("span"); note.textContent = `${Number(fragmentSummary.total || 0).toLocaleString()} compact prompt inserts, organized like Wardrobe. Review tools operate on pages or entire filtered folders.`; Object.assign(note.style, { display: "block", marginTop: "3px", color: "#8f8997", font: "9px Segoe UI,Arial" }); copy.append(title, note);
    const rebuild = action("REBUILD INDEX", "#ff9b5f"); Object.assign(rebuild.style, { padding: "6px 8px", fontSize: "8px" }); rebuild.onclick = async () => { try { rebuild.disabled = true; catalogStatus("Rebuilding the derived ingredient index…", "#ff9b5f"); await request("/fragments/rebuild", { method: "POST", body: "{}" }); fragmentPage = 0; await loadFragmentPage(); catalogStatus("Ingredient index rebuilt from the clean canonical corpus.", "#6ee7a2"); } catch (error) { alert(error.message || "Could not rebuild the Ingredient index."); } finally { rebuild.disabled = false; } };
    head.append(copy, rebuild); shell.append(head);

    const workspace = document.createElement("div"); Object.assign(workspace.style, { display: "grid", gridTemplateColumns: "minmax(190px,235px) minmax(0,1fr)", minHeight: "0" });
    const sidebar = document.createElement("aside"); Object.assign(sidebar.style, { maxHeight: "610px", overflow: "auto", borderRight: "1px solid #302a35", background: "#0d0b11" });
    const roleButton = (role, labelText, count, color) => { const selected = fragmentRole === role; const button = document.createElement("button"); button.type = "button"; Object.assign(button.style, { width: "100%", display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: "8px", padding: "9px 10px", border: "0", borderBottom: "1px solid #26212b", borderLeft: selected ? `3px solid ${color}` : "3px solid transparent", cursor: "pointer", textAlign: "left", color: selected ? "#fff" : "#b9b1bf", background: selected ? `${color}18` : "transparent", font: `${selected ? "800" : "600"} 9px Segoe UI,Arial` }); const name = document.createElement("span"); name.textContent = labelText; name.style.overflow = "hidden"; name.style.textOverflow = "ellipsis"; const amount = document.createElement("span"); amount.textContent = Number(count || 0).toLocaleString(); amount.style.color = selected ? color : "#6f6875"; button.append(name, amount); button.onclick = () => { fragmentRole = role; fragmentPage = 0; resetFragmentSelection(true); queueFragmentPageLoad(); }; return button; };
    sidebar.append(roleButton("", "All Ingredients", fragmentSummary.total, "#b89aff"));
    for (const role of Object.keys(FRAGMENT_ROLE_META)) { const count = Number(fragmentSummary.roles?.[role] || 0); if (!count) continue; const [labelText, color] = fragmentMeta(role); sidebar.append(roleButton(role, labelText, count, color)); }

    const main = document.createElement("main"); Object.assign(main.style, { minWidth: "0", display: "flex", flexDirection: "column", maxHeight: "610px" });
    const filters = document.createElement("div"); Object.assign(filters.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "6px", padding: "9px", borderBottom: "1px solid #2b2630" });
    const search = document.createElement("input"); search.type = "search"; search.value = fragmentSearch; search.placeholder = "Search this ingredient folder…"; Object.assign(search.style, { flex: "2 1 260px", minWidth: "180px", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", outline: "none", background: "#09080d", color: "#fff" }); search.oninput = () => { fragmentSearch = search.value; fragmentPage = 0; resetFragmentSelection(true); queueFragmentPageLoad(180); };
    const state = makeSelect([["ready", "Ready"], ["active", "All active"], ["review", "Needs review"], ["approved", "Curated"], ["suggested", "Suggested"]], fragmentState); Object.assign(state.style, { flex: "0 1 135px", width: "135px", padding: "8px" }); state.onchange = () => { fragmentState = state.value; fragmentPage = 0; resetFragmentSelection(true); queueFragmentPageLoad(); };
    const sort = makeSelect([["rank", "Most sourced"], ["name", "A → Z"], ["role", "Role order"], ["confidence", "Confidence"]], fragmentSort); Object.assign(sort.style, { flex: "0 1 145px", width: "145px", padding: "8px" }); sort.onchange = () => { fragmentSort = sort.value; fragmentPage = 0; queueFragmentPageLoad(); };
    filters.append(search, state, sort); main.append(filters);

    const bulk = document.createElement("div"); Object.assign(bulk.style, { display: "flex", alignItems: "center", flexWrap: "wrap", gap: "5px", padding: "7px 9px", borderBottom: "1px solid #2b2630", background: "rgba(184,154,255,.025)" });
    const selectPage = action("SELECT PAGE", "#35d7ff"); const selectAll = action("SELECT ALL MATCHES", "#35d7ff"); const clear = action("CLEAR", "#8f8997"); for (const button of [selectPage, selectAll, clear]) Object.assign(button.style, { padding: "5px 7px", fontSize: "7px" }); selectPage.onclick = selectFragmentPage; selectAll.onclick = selectAllFragmentMatches; clear.onclick = () => { resetFragmentSelection(true); render(); };
    const selected = document.createElement("span"); selected.textContent = `${fragmentSelectionCount().toLocaleString()} selected`; Object.assign(selected.style, { minWidth: "72px", color: fragmentSelectionCount() ? "#bfefff" : "#716b77", font: "800 8px Segoe UI,Arial" });
    const reviewAction = makeSelect([["", "Review action…"], ["approved", "Approve"], ["review", "Needs review"], ["rejected", "Hide"]], ""); Object.assign(reviewAction.style, { width: "125px", padding: "6px", fontSize: "8px" });
    const categoryAction = makeSelect([["", "Keep category"], ...Object.keys(FRAGMENT_ROLE_META).map(role => [role, fragmentMeta(role)[0]])], ""); Object.assign(categoryAction.style, { width: "145px", padding: "6px", fontSize: "8px" });
    const apply = action("APPLY TO SELECTION", "#6ee7a2"); Object.assign(apply.style, { padding: "6px 8px", fontSize: "7px" }); apply.onclick = () => { if (!reviewAction.value && !categoryAction.value) { alert("Choose a review action, a new category, or both."); return; } void bulkUpdateFragments({ ...(reviewAction.value ? { state: reviewAction.value } : {}), ...(categoryAction.value ? { role: categoryAction.value } : {}) }); };
    bulk.append(selectPage, selectAll, clear, selected, reviewAction, categoryAction, apply); main.append(bulk);

    const rows = document.createElement("div"); Object.assign(rows.style, { minHeight: "0", overflow: "auto", flex: "1 1 auto" });
    if (!fragmentRows.length) { const empty = document.createElement("div"); empty.textContent = fragmentLoading ? "Loading ingredients…" : "No ingredients match this folder and filter."; Object.assign(empty.style, { padding: "36px", color: "#8f8997", textAlign: "center" }); rows.append(empty); }
    for (const fragment of fragmentRows) {
        const id = String(fragment.fragment_id || ""); const checked = fragmentSelectAllFiltered || selectedFragmentIds.has(id); const [labelText, color] = fragmentMeta(fragment.role);
        const row = document.createElement("div"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "26px minmax(105px,150px) minmax(0,1fr) auto auto", gap: "8px", alignItems: "center", minHeight: "45px", padding: "6px 9px", borderBottom: "1px solid #25212a", background: checked ? `${color}10` : "transparent" });
        const check = document.createElement("input"); check.type = "checkbox"; check.checked = checked; check.onclick = () => toggleFragmentSelection(id);
        const role = document.createElement("span"); role.textContent = labelText; Object.assign(role.style, { color, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "900 7px Segoe UI,Arial", letterSpacing: ".05em" });
        const value = document.createElement("div"); value.textContent = fragment.value || ""; value.title = fragment.value || ""; Object.assign(value.style, { minWidth: "0", color: "#e5dfe8", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "10px Segoe UI,Arial" });
        const meta = document.createElement("span"); meta.textContent = `${Number(fragment.prompt_count || 0).toLocaleString()} prompts`; Object.assign(meta.style, { color: "#746d7a", whiteSpace: "nowrap", font: "7px Segoe UI,Arial" });
        const actions = document.createElement("div"); Object.assign(actions.style, { display: "flex", gap: "4px" }); const add = action("+ ADD", color); const view = action("PROMPTS", "#35d7ff"); for (const button of [add, view]) Object.assign(button.style, { padding: "5px 7px", fontSize: "7px" }); add.onclick = () => addBuilderFragment(fragment); view.onclick = () => openPromptsForFragment(fragment); actions.append(add, view); row.append(check, role, value, meta, actions); rows.append(row);
    }
    main.append(rows);
    const footer = document.createElement("div"); Object.assign(footer.style, { display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "7px", padding: "7px 9px", borderTop: "1px solid #302a35" }); const pageCount = Math.max(1, Math.ceil(fragmentTotal / FRAGMENT_PAGE_SIZE)); const first = fragmentTotal ? fragmentPage * FRAGMENT_PAGE_SIZE + 1 : 0; const last = Math.min(fragmentTotal, fragmentPage * FRAGMENT_PAGE_SIZE + fragmentRows.length); const range = document.createElement("span"); range.textContent = `${first.toLocaleString()}–${last.toLocaleString()} of ${fragmentTotal.toLocaleString()}`; Object.assign(range.style, { color: "#817b88", font: "800 8px Segoe UI,Arial" }); const prev = action("←", "#8f8997"), next = action("→", "#8f8997"); prev.disabled = fragmentPage <= 0; next.disabled = fragmentPage >= pageCount - 1; prev.onclick = () => { fragmentPage = Math.max(0, fragmentPage - 1); queueFragmentPageLoad(); }; next.onclick = () => { fragmentPage += 1; queueFragmentPageLoad(); }; for (const button of [prev, next]) Object.assign(button.style, { padding: "5px 8px", opacity: button.disabled ? ".4" : "1" }); footer.append(range, prev, next); main.append(footer);
    workspace.append(sidebar, main); shell.append(workspace); list.append(shell);
}

function renderWorkshopRecipes(list) {
    const section = document.createElement("section"); Object.assign(section.style, { gridColumn: "1 / -1", padding: "11px", borderRadius: "11px", border: "1px solid #f6e65a33", background: "#0b0910" });
    const heading = document.createElement("div"); heading.textContent = `SAVED GENERATION RECIPES · ${recipes.length.toLocaleString()}`; Object.assign(heading.style, { marginBottom: "8px", color: "#f6e65a", font: "900 9px Segoe UI,Arial", letterSpacing: ".1em" }); section.append(heading);
    const grid = document.createElement("div"); Object.assign(grid.style, { display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(min(280px,100%),1fr))", gap: "7px" });
    if (!recipes.length) { const empty = document.createElement("div"); empty.textContent = "No saved generation Recipes yet. Saving one preserves Studio settings; its reusable formula and resolved prompt are catalogued separately."; Object.assign(empty.style, { padding: "15px", color: "#817b88", fontSize: "9px" }); grid.append(empty); }
    for (const recipe of recipes) {
        const row = document.createElement("div"); Object.assign(row.style, { minWidth: "0", display: "grid", gridTemplateColumns: recipe.preview_ref ? "58px minmax(0,1fr)" : "minmax(0,1fr)", gap: "8px", padding: "7px", borderRadius: "9px", border: "1px solid #3e3742", background: "#111016" });
        if (recipe.preview_ref) { const image = document.createElement("img"); image.loading = "lazy"; image.decoding = "async"; image.src = creativeLibraryPreviewUrl(recipe.preview_ref, recipe.updated_at || ""); Object.assign(image.style, { width: "58px", height: "72px", objectFit: "cover", borderRadius: "6px" }); row.append(image); }
        const body = document.createElement("div"); Object.assign(body.style, { minWidth: "0", display: "flex", flexDirection: "column", gap: "5px" }); const name = document.createElement("strong"); name.textContent = recipe.name || "Recipe"; Object.assign(name.style, { color: "#eee8f0", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "800 9px Segoe UI,Arial" }); const meta = document.createElement("div"); meta.textContent = `${recipeTokens(recipe.payload).join(" · ") || "token free"} · ${new Date(recipe.updated_at).toLocaleDateString()}`; Object.assign(meta.style, { color: "#746d7a", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "7px Segoe UI,Arial" }); const actions = document.createElement("div"); Object.assign(actions.style, { display: "flex", gap: "4px", marginTop: "auto" }); const use = action("USE IN ASSEMBLY", "#f6e65a"); const inspect = action("REVIEW", "#6ee7a2"); Object.assign(use.style, { padding: "5px 7px", fontSize: "7px" }); Object.assign(inspect.style, { padding: "5px 7px", fontSize: "7px" }); use.onclick = () => { workshopAssemblyOpen = true; selectBuilderRecipe(recipe); }; inspect.onclick = () => showDiff(recipe); actions.append(use, inspect); body.append(name, meta, actions); row.append(body); grid.append(row);
    }
    section.append(grid); list.append(section);
}

async function showPromptHarvestWorkbench(options = {}) {
    const overlay = document.createElement("div");
    Object.assign(overlay.style, { position: "fixed", inset: "0", zIndex: "100080", background: "rgba(0,0,0,.78)", display: "flex", alignItems: "center", justifyContent: "center", padding: "18px" });
    const shell = document.createElement("section");
    Object.assign(shell.style, { width: "min(1420px,96vw)", height: "min(900px,92vh)", display: "flex", flexDirection: "column", overflow: "hidden", borderRadius: "14px", border: "1px solid #35d7ff99", background: "#0d0a12", color: "#f5f1f7", boxShadow: "0 28px 90px #000" });
    const head = document.createElement("div"); Object.assign(head.style, { padding: "13px 15px", borderBottom: "1px solid #35d7ff44", background: "linear-gradient(90deg,rgba(53,215,255,.10),rgba(246,230,90,.04))" });
    const title = document.createElement("strong"); title.textContent = "PROMPT → OUTFIT HARVEST"; Object.assign(title.style, { color: "#35d7ff", font: "900 13px Segoe UI,Arial", letterSpacing: ".07em" });
    const intro = document.createElement("div"); intro.textContent = "Deterministic bootstrap extraction. Structured OUTFIT metadata is exact; flattened prompts are parsed around explicit clothing language such as ‘wearing’. Nothing uncertain is added without review."; Object.assign(intro.style, { marginTop: "5px", color: "#aaa2b4", font: "10px/1.45 Segoe UI,Arial" });
    head.append(title, intro);

    const metrics = document.createElement("div"); Object.assign(metrics.style, { display: "grid", gridTemplateColumns: "repeat(6,minmax(95px,1fr))", gap: "7px", padding: "10px 12px 0" });
    const metric = (label, color) => { const box = document.createElement("div"); Object.assign(box.style, { padding: "8px 9px", borderRadius: "8px", border: `1px solid ${color}55`, background: `${color}0d` }); const value = document.createElement("strong"); value.dataset.value = label; value.textContent = "0"; Object.assign(value.style, { display: "block", color, font: "900 17px Segoe UI,Arial" }); const caption = document.createElement("span"); caption.textContent = label.toUpperCase(); Object.assign(caption.style, { color: "#8f8997", font: "800 7px Segoe UI,Arial", letterSpacing: ".08em" }); box.append(value, caption); return box; };
    for (const [label,color] of [["total","#35d7ff"],["exact","#b89aff"],["ready","#6ee7a2"],["review","#f6e65a"],["unresolved","#ff9b5f"],["existing","#8f8997"]]) metrics.append(metric(label,color));

    const filters = document.createElement("div"); Object.assign(filters.style, { display: "flex", alignItems: "center", gap: "7px", padding: "10px 12px" });
    const status = makeSelect([["", "All prompts"], ["ready", "Ready"], ["review", "Needs review"], ["unresolved", "No outfit found"], ["existing", "Already in Looks"]], String(options.status || "")); Object.assign(status.style, { width: "155px" });
    const search = document.createElement("input"); search.type = "search"; search.placeholder = "Search prompt or extracted Outfit…"; search.value = String(options.query || ""); Object.assign(search.style, { flex: "1", minWidth: "220px", padding: "8px 9px", borderRadius: "7px", border: "1px solid #4a4452", background: "#09080d", color: "#fff", outline: "none" });
    const range = document.createElement("span"); Object.assign(range.style, { minWidth: "100px", textAlign: "center", color: "#8f8997", font: "700 9px Segoe UI,Arial" });
    const prev = action("←", "#8f8997"); const next = action("→", "#8f8997");
    filters.append(status, search, range, prev, next);

    const content = document.createElement("div"); Object.assign(content.style, { display: "grid", gridTemplateColumns: "minmax(360px,44%) 1fr", gap: "0", minHeight: "0", flex: "1 1 auto", borderTop: "1px solid #24212a" });
    const queue = document.createElement("div"); Object.assign(queue.style, { minHeight: "0", overflow: "auto", borderRight: "1px solid #302b36", background: "rgba(255,255,255,.012)" });
    const editor = document.createElement("div"); Object.assign(editor.style, { minHeight: "0", overflow: "auto", padding: "13px", display: "flex", flexDirection: "column", gap: "10px" });
    content.append(queue, editor);

    const foot = document.createElement("div"); Object.assign(foot.style, { padding: "10px 12px", borderTop: "1px solid #302b36", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" });
    const hint = document.createElement("span"); hint.textContent = "Accepted values become Outfit Looks. Run MIGRATE LOOKS afterward to decompose newly harvested Looks into Wardrobe Pieces."; Object.assign(hint.style, { color: "#817b88", font: "9px/1.35 Segoe UI,Arial" });
    const actions = document.createElement("div"); Object.assign(actions.style, { display: "flex", gap: "7px" });
    const bulk = action("HARVEST CURRENT VIEW", "#f6e65a"); const done = action("Done", "#8f8997"); done.onclick = () => overlay.remove(); actions.append(bulk, done); foot.append(hint, actions);
    shell.append(head, metrics, filters, content, foot); overlay.append(shell); document.body.append(overlay);

    let offset = 0; const limit = 60; let rows = []; let selectedId = ""; let queueTotal = 0; let timer = null;
    const setMetric = (name, value) => { const el = metrics.querySelector(`[data-value="${name}"]`); if (el) el.textContent = Number(value || 0).toLocaleString(); };
    const selectRow = row => { selectedId = String(row?.prompt_id || ""); drawQueue(); drawEditor(row); };
    const drawEditor = row => {
        editor.replaceChildren();
        if (!row) { const empty = document.createElement("div"); empty.textContent = "Choose a prompt on the left."; empty.style.color = "#8f8997"; editor.append(empty); return; }
        const top = document.createElement("div"); Object.assign(top.style, { display: "grid", gridTemplateColumns: row.preview_ref ? "140px 1fr" : "1fr", gap: "11px" });
        if (row.preview_ref) { const img = document.createElement("img"); img.loading = "lazy"; img.decoding = "async"; img.src = creativeLibraryPreviewUrl(row.preview_ref, row.updated_at || ""); Object.assign(img.style, { width: "140px", aspectRatio: "4/5", objectFit: "cover", borderRadius: "9px", border: "1px solid #35d7ff44" }); top.append(img); }
        const copy = document.createElement("div"); const name = document.createElement("strong"); name.textContent = row.name || "Prompt"; Object.assign(name.style, { color: "#fff", fontSize: "12px" });
        const source = document.createElement("div"); source.textContent = `${String(row.source || "none").replaceAll("-"," ")} · ${Math.round(Number(row.confidence || 0) * 100)}% confidence`; Object.assign(source.style, { marginTop: "4px", color: row.source === "structured-metadata" ? "#b89aff" : row.status === "ready" ? "#6ee7a2" : "#f6e65a", font: "800 9px Segoe UI,Arial", textTransform: "uppercase" });
        const promptText = document.createElement("div"); promptText.textContent = row.prompt || ""; Object.assign(promptText.style, { marginTop: "8px", maxHeight: "145px", overflow: "auto", padding: "9px", borderRadius: "8px", background: "#09080d", border: "1px solid #302b36", color: "#bdb6c3", font: "10px/1.45 Consolas,monospace" });
        copy.append(name, source, promptText); top.append(copy); editor.append(top);
        const label = document.createElement("strong"); label.textContent = "OUTFIT LOOK"; Object.assign(label.style, { color: "#f6e65a", font: "900 9px Segoe UI,Arial", letterSpacing: ".08em" });
        const input = document.createElement("textarea"); input.value = row.candidate || ""; input.placeholder = "No reliable Outfit clause was detected. Enter one manually if this prompt contains a reusable outfit."; Object.assign(input.style, { boxSizing: "border-box", width: "100%", minHeight: "92px", resize: "vertical", padding: "10px", borderRadius: "8px", border: `1px solid ${row.status === "unresolved" ? "#ff9b5f66" : "#f6e65a66"}`, background: "#09080d", color: "#fff", outline: "none", font: "11px/1.45 Segoe UI,Arial" });
        const meta = document.createElement("div"); meta.textContent = row.status === "existing" ? "This exact Outfit Look is already in the Outfit library." : "Accepting adds this as an Outfit Look without changing the source Prompt."; Object.assign(meta.style, { color: "#8f8997", fontSize: "9px" });
        const buttons = document.createElement("div"); Object.assign(buttons.style, { display: "flex", justifyContent: "flex-end", gap: "7px" });
        const accept = action(row.status === "existing" ? "ALREADY HARVESTED" : "HARVEST OUTFIT", row.status === "existing" ? "#8f8997" : "#6ee7a2"); accept.disabled = row.status === "existing"; accept.style.opacity = accept.disabled ? ".45" : "1";
        accept.onclick = async () => { try { accept.disabled = true; await request("/prompt-harvest/accept", { method: "POST", body: JSON.stringify({ prompt_id: row.prompt_id, outfit_value: input.value }) }); await load(); await refresh(false); catalogStatus(`Harvested Outfit Look from ${row.name || "Prompt"}.`, "#f6e65a"); } catch (error) { alert(error.message || "Could not harvest this Outfit."); } finally { accept.disabled = false; } };
        buttons.append(accept); editor.append(label, input, meta, buttons);
    };
    const drawQueue = () => { queue.replaceChildren(); if (!rows.length) { const e = document.createElement("div"); e.textContent = "No prompts match this Harvest view."; Object.assign(e.style, { padding: "24px", color: "#8f8997" }); queue.append(e); drawEditor(null); return; } for (const row of rows) { const selected = String(row.prompt_id || "") === selectedId; const item = document.createElement("button"); item.type = "button"; Object.assign(item.style, { width: "100%", display: "block", textAlign: "left", padding: "9px 10px", border: "0", borderBottom: "1px solid #29252f", borderLeft: selected ? "3px solid #35d7ff" : "3px solid transparent", background: selected ? "rgba(53,215,255,.09)" : "transparent", cursor: "pointer", color: "#fff" }); const title = document.createElement("div"); title.textContent = row.name || "Prompt"; Object.assign(title.style, { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "700 10px Segoe UI,Arial" }); const candidate = document.createElement("div"); candidate.textContent = row.candidate || "No Outfit detected"; Object.assign(candidate.style, { marginTop: "3px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: row.status === "ready" ? "#dfffea" : row.status === "review" ? "#f6e65a" : row.status === "existing" ? "#8f8997" : "#ffb27d", fontSize: "9px" }); item.append(title,candidate); item.onclick = () => selectRow(row); queue.append(item); } };
    const refresh = async (reset = true) => { if (reset) offset = 0; const params = new URLSearchParams({ limit: String(limit), offset: String(offset) }); if (status.value) params.set("status", status.value); if (search.value.trim()) params.set("query", search.value.trim()); const data = await request(`/prompt-harvest/analyze?${params.toString()}`); rows = Array.isArray(data.rows) ? data.rows : []; queueTotal = Number(data.queue_total || 0); const summary = data.summary || {}; for (const key of ["total","exact","ready","review","unresolved","existing"]) setMetric(key, summary[key]); range.textContent = queueTotal ? `${(offset+1).toLocaleString()}–${Math.min(queueTotal,offset+limit).toLocaleString()} of ${queueTotal.toLocaleString()}` : "0 results"; prev.disabled = offset <= 0; next.disabled = offset + limit >= queueTotal; selectedId = rows.some(row => String(row.prompt_id) === selectedId) ? selectedId : String(rows[0]?.prompt_id || ""); drawQueue(); drawEditor(rows.find(row => String(row.prompt_id) === selectedId) || rows[0] || null); };
    status.onchange = () => refresh(true); search.oninput = () => { clearTimeout(timer); timer = setTimeout(() => refresh(true), 180); }; prev.onclick = () => { offset = Math.max(0, offset - limit); refresh(false); }; next.onclick = () => { offset += limit; refresh(false); };
    bulk.onclick = async () => { const viewStatus = status.value || "ready"; if (viewStatus === "unresolved" || viewStatus === "existing") { alert("Choose Ready or Needs review before bulk harvesting. Unresolved prompts need a manual Outfit value, and Existing prompts are already present."); return; } if (!confirm(`Harvest every Outfit candidate in the current ${viewStatus === "review" ? "Needs review" : "Ready"} view${search.value.trim() ? " matching this search" : ""}?\n\nSource Prompts are never changed.`)) return; try { bulk.disabled = true; const result = await request("/prompt-harvest/accept-filtered", { method: "POST", body: JSON.stringify({ status: viewStatus, query: search.value.trim() }) }); await load(); await refresh(true); catalogStatus(`Prompt Harvest · ${Number(result.created || 0).toLocaleString()} new Looks · ${Number(result.matched || 0).toLocaleString()} already present.`, "#f6e65a"); } catch (error) { alert(error.message || "Could not harvest this view."); } finally { bulk.disabled = false; } };
    overlay.addEventListener("pointerdown", event => { if (event.target === overlay) overlay.remove(); });
    await refresh(true);
}

function showDiff(recipe) {
    const diff = recipeDiff(recipe, true);
    const modal = document.createElement("div");
    Object.assign(modal.style, { position: "fixed", inset: "0", zIndex: "100031", background: "rgba(0,0,0,.70)", display: "flex", alignItems: "center", justifyContent: "center", padding: "24px" });
    const card = document.createElement("div");
    Object.assign(card.style, { width: "880px", maxWidth: "96vw", maxHeight: "90vh", display: "flex", flexDirection: "column", background: "linear-gradient(145deg,#17131f,#0d0b12)", color: "#f4f1f6", border: "1px solid #35d7ff99", borderRadius: "14px", boxShadow: "0 24px 80px #000", overflow: "hidden" });
    const head = document.createElement("div");
    const title = document.createElement("strong"); title.textContent = `APPLY RECIPE · ${recipe.name}`; Object.assign(title.style, { color: "#35d7ff", letterSpacing: ".04em" });
    const subtitle = document.createElement("div"); subtitle.textContent = "Load the reusable formula, not the identity or the ingredients currently selected in Prompt Core."; Object.assign(subtitle.style, { marginTop: "4px", color: "#aaa2b4", fontSize: "11px" });
    head.append(title, subtitle); Object.assign(head.style, { padding: "14px 16px", borderBottom: "1px solid #ff4ab844" }); card.append(head);

    const body = document.createElement("div"); Object.assign(body.style, { padding: "14px 16px", overflow: "auto", display: "flex", flexDirection: "column", gap: "11px" });

    const rule = document.createElement("div");
    rule.innerHTML = `<strong style="color:#f6e65a">PORTABLE BY DESIGN</strong><div style="margin-top:5px;color:#b8b0c1">NAME and BRAND values are never restored. Their placeholder controls stay exactly as your current workflow has them. Outfit A/B/C and Scene selections also stay untouched. Loading a Recipe always switches the full prompt source to <b style="color:#fff">Manual</b>.</div>`;
    Object.assign(rule.style, { padding: "11px 12px", borderRadius: "9px", border: "1px solid #f6e65a55", background: "rgba(246,230,90,.035)", fontSize: "11px", lineHeight: "1.45" });
    body.append(rule);

    const promptGroup = diff.find(group => group.type === "SOPromptLogEngineStudio" && !group.optional);
    const savedPromptNode = (recipe.payload?.nodes || []).find(node => (TYPE_ALIASES[node.type] || node.type) === "SOPromptLogEngineStudio");
    const savedPromptEntry = (savedPromptNode?.widgets || []).find(entry => entry.name === "manual_prompt");
    const savedPrompt = String(savedPromptEntry?.value || recipe.payload?.summary?.prompt_template || "");
    const promptSection = document.createElement("section"); Object.assign(promptSection.style, { border: "1px solid #35d7ff55", borderRadius: "10px", overflow: "hidden", background: "rgba(53,215,255,.025)" });
    const promptHead = document.createElement("div"); promptHead.textContent = "PROMPT FORMULA"; Object.assign(promptHead.style, { padding: "9px 11px", color: "#35d7ff", font: "800 11px Segoe UI,Arial", letterSpacing: ".06em", background: "rgba(53,215,255,.08)" }); promptSection.append(promptHead);
    const promptChange = promptGroup?.changes?.find(change => change.name === "manual_prompt");
    const promptRow = document.createElement("label"); Object.assign(promptRow.style, { display: "grid", gridTemplateColumns: promptChange ? "24px 1fr" : "1fr", gap: "8px", alignItems: "start", padding: "11px", cursor: promptChange?.connected ? "not-allowed" : "pointer" });
    if (promptChange) { const check = document.createElement("input"); check.type = "checkbox"; check.dataset.changeId = promptChange.id; check.checked = !promptChange.connected; check.disabled = promptChange.connected; promptRow.append(check); }
    const promptCopy = document.createElement("div");
    const promptStatus = document.createElement("div"); promptStatus.textContent = promptChange ? (promptChange.connected ? "Manual prompt is connected and protected" : "Replace current manual prompt") : "Prompt formula already matches"; Object.assign(promptStatus.style, { color: promptChange?.connected ? "#8f8997" : "#f5f1f7", font: "700 11px Segoe UI,Arial", marginBottom: "7px" });
    const promptText = document.createElement("div"); promptText.textContent = savedPrompt || "No reusable prompt text was stored."; Object.assign(promptText.style, { maxHeight: "220px", overflow: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word", padding: "10px", borderRadius: "8px", background: "#09080d", color: "#dcd6e1", font: "11px/1.48 Consolas,monospace" });
    promptCopy.append(promptStatus, promptText); promptRow.append(promptCopy); promptSection.append(promptRow); body.append(promptSection);

    const generationGroup = diff.find(group => group.type === "SOGenerationPipelineStudio" && !group.optional);
    const generationSection = document.createElement("section"); Object.assign(generationSection.style, { border: "1px solid #6ee7a244", borderRadius: "10px", overflow: "hidden", background: "rgba(110,231,162,.018)" });
    const generationHead = document.createElement("div"); generationHead.textContent = "GENERATION SETTINGS"; Object.assign(generationHead.style, { padding: "9px 11px", color: "#6ee7a2", font: "800 11px Segoe UI,Arial", letterSpacing: ".06em", background: "rgba(110,231,162,.07)" }); generationSection.append(generationHead);
    if (!generationGroup || generationGroup.missing) {
        const missing = document.createElement("div"); missing.textContent = generationGroup?.missing ? "Generation Core is not on this canvas." : "No generation settings are stored in this Recipe."; Object.assign(missing.style, { padding: "11px", color: "#8f8997" }); generationSection.append(missing);
    } else if (!generationGroup.changes.length) {
        const same = document.createElement("div"); same.textContent = "Generation settings already match."; Object.assign(same.style, { padding: "11px", color: "#8f8997" }); generationSection.append(same);
    } else {
        for (const change of generationGroup.changes) {
            const row = document.createElement("label"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "24px minmax(130px,180px) 1fr", gap: "8px", alignItems: "center", padding: "9px 11px", borderTop: "1px solid #2b2731", cursor: change.connected ? "not-allowed" : "pointer" });
            const check = document.createElement("input"); check.type = "checkbox"; check.dataset.changeId = change.id; check.checked = change.checked && !change.connected; check.disabled = change.connected;
            const label = document.createElement("strong"); label.textContent = `${humanField(change.name)}${change.connected ? "  🔒" : ""}`; Object.assign(label.style, { color: change.connected ? "#8b8491" : "#f2edf4", fontSize: "11px" });
            const values = document.createElement("div"); values.innerHTML = `<span style="color:#fff">${displayValue(change.to)}</span><span style="color:#817b88;margin-left:8px;font-size:10px">Current: ${displayValue(change.from)}</span>`;
            row.append(check, label, values); generationSection.append(row);
        }
    }
    body.append(generationSection);

    const optionalGroups = diff.filter(group => group.optional);
    if (optionalGroups.length) {
        const optionalSection = document.createElement("section"); Object.assign(optionalSection.style, { border: "1px solid #f6e65a44", borderRadius: "10px", overflow: "hidden", background: "rgba(246,230,90,.018)" });
        const optionalToggle = document.createElement("label"); Object.assign(optionalToggle.style, { display: "flex", alignItems: "center", gap: "9px", padding: "10px 11px", cursor: "pointer", color: "#f6e65a", font: "700 11px Segoe UI,Arial" });
        const toggle = document.createElement("input"); toggle.type = "checkbox"; const text = document.createElement("span"); text.textContent = "OPTIONAL ENVIRONMENT · model / LoRAs / text encoder / VAE"; optionalToggle.append(toggle, text); optionalSection.append(optionalToggle);
        const optionalBody = document.createElement("div"); optionalBody.style.display = "none";
        for (const group of optionalGroups) {
            const label = document.createElement("div"); label.textContent = group.label || SECTION_LABELS[group.type] || group.type; Object.assign(label.style, { padding: "8px 11px", color: "#d9ca77", font: "700 10px Segoe UI,Arial", borderTop: "1px solid #3b3424" }); optionalBody.append(label);
            if (group.missing) { const missing = document.createElement("div"); missing.textContent = "Matching Studio node is not on this canvas."; Object.assign(missing.style, { padding: "8px 11px", color: "#8f8997" }); optionalBody.append(missing); continue; }
            if (!group.changes.length) { const same = document.createElement("div"); same.textContent = "Already matches."; Object.assign(same.style, { padding: "8px 11px", color: "#8f8997" }); optionalBody.append(same); continue; }
            for (const change of group.changes) {
                const row = document.createElement("label"); Object.assign(row.style, { display: "grid", gridTemplateColumns: "24px minmax(150px,210px) 1fr", gap: "8px", alignItems: "center", padding: "8px 11px", borderTop: "1px solid #2b2731", cursor: change.connected ? "not-allowed" : "pointer" });
                const check = document.createElement("input"); check.type = "checkbox"; check.dataset.changeId = change.id; check.checked = false; check.disabled = change.connected;
                const name = document.createElement("strong"); name.textContent = `${humanField(change.name)}${change.connected ? "  🔒" : ""}`; Object.assign(name.style, { fontSize: "10px", color: change.connected ? "#8f8997" : "#eee8d0" });
                const value = document.createElement("span"); value.textContent = displayValue(change.to); Object.assign(value.style, { color: "#d8d2dc", fontSize: "10px", overflow: "hidden", textOverflow: "ellipsis" }); row.append(check, name, value); optionalBody.append(row);
            }
        }
        toggle.onchange = () => { optionalBody.style.display = toggle.checked ? "block" : "none"; };
        optionalSection.append(optionalBody); body.append(optionalSection);
    }

    const original = recipe.payload?.summary?.placeholders || [];
    const identityValues = original.filter(item => ["NAME", "BRAND", "ITEM"].includes(String(item?.token || "").toUpperCase()) || ["name_value", "item_value"].includes(String(item?.widget || "")));
    if (identityValues.length) {
        const provenance = document.createElement("div"); provenance.textContent = `Original image used ${identityValues.map(item => `${String(item.token || "value").toUpperCase()}: ${item.value}`).join(" · ")}. These are shown only for provenance and will not be applied.`; Object.assign(provenance.style, { color: "#817b88", fontSize: "10px", lineHeight: "1.4", padding: "0 2px" }); body.append(provenance);
    }

    card.append(body);
    const foot = document.createElement("div"); Object.assign(foot.style, { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", padding: "12px 14px", borderTop: "1px solid #2c2932" });
    const hint = document.createElement("span"); hint.textContent = "Only checked Recipe fields change. Identity and ingredient selectors are protected automatically."; Object.assign(hint.style, { color: "#85808d", fontSize: "10px" });
    const buttons = document.createElement("div"); Object.assign(buttons.style, { display: "flex", gap: "8px" });
    const cancel = action("Cancel", "#888"); cancel.onclick = () => modal.remove();
    const apply = action("Apply Recipe", "#6ee7a2"); apply.onclick = () => { const selected = new Set([...body.querySelectorAll("input[data-change-id]:checked")].map(item => item.dataset.changeId)); const result = applyRecipe(recipe, selected); catalogStatus(`Applied Recipe · ${result.changed} value${result.changed === 1 ? "" : "s"} changed.`); modal.remove(); };
    buttons.append(cancel, apply); foot.append(hint, buttons); card.append(foot); modal.append(card); document.body.append(modal);
    modal.addEventListener("pointerdown", event => { if (event.target === modal) modal.remove(); });
}

function applyListLayout(list) {
    if (!list) return;
    Object.assign(list.style, { justifyContent: "start", alignContent: "start", alignItems: "start" });
    if (activeView === "outfits" && outfitMode !== "looks") {
        Object.assign(list.style, { display: "block", gridTemplateColumns: "none", gap: "0" });
        return;
    }
    list.style.display = "grid";
    if (activeView === "outfits") {
        Object.assign(list.style, { gridTemplateColumns: "repeat(auto-fill,minmax(min(220px,100%),1fr))", gap: "14px" });
        return;
    }
    if (activeView === "scenes") {
        Object.assign(list.style, { gridTemplateColumns: "repeat(auto-fill,minmax(min(250px,100%),1fr))", gap: "14px" });
        return;
    }
    if (["recipes", "prompts", "fragments"].includes(activeView)) {
        Object.assign(list.style, { display: "block", gridTemplateColumns: "none", gap: "0" });
        return;
    }
    Object.assign(list.style, { gridTemplateColumns: "repeat(auto-fill,minmax(230px,1fr))", gap: "12px" });
}

function renderPersistentBuilderDock(list) {
    if (!builderHasContent()) return;
    const dock = document.createElement("aside"); dock.dataset.builderDock = ""; Object.assign(dock.style, { gridColumn: "1 / -1", position: "sticky", bottom: "0", zIndex: "12", minWidth: "0", display: "grid", gridTemplateColumns: "auto minmax(0,1fr) auto auto", gap: "9px", alignItems: "center", padding: "10px 11px", borderRadius: "11px", border: "1px solid #ff4ab888", background: "linear-gradient(90deg,rgba(255,74,184,.20),rgba(17,14,22,.97) 24%,rgba(11,9,15,.98))", boxShadow: "0 -10px 28px rgba(0,0,0,.42)", backdropFilter: "blur(10px)" });
    const count = document.createElement("strong"); count.textContent = `${builderFragments().length} SLOT${builderFragments().length === 1 ? "" : "S"}`; Object.assign(count.style, { color: "#ff9dce", font: "900 9px Segoe UI,Arial", letterSpacing: ".08em" });
    const preview = document.createElement("div"); preview.textContent = builderPreviewText(); Object.assign(preview.style, { minWidth: "0", color: "#c7c0ca", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", font: "9px Consolas,monospace" });
    const add = action("+ INGREDIENT", "#b89aff"); Object.assign(add.style, { padding: "6px 8px", fontSize: "8px" }); add.onclick = () => showBuilderFragmentPicker();
    const open = action("OPEN WORKSHOP", "#b89aff"); Object.assign(open.style, { padding: "7px 9px", fontSize: "8px", borderWidth: "2px" }); open.onclick = () => { workshopAssemblyOpen = true; setActiveView("fragments"); };
    dock.append(count, preview, add, open); list.append(dock);
}

function render() {
    const list = root?.querySelector("[data-recipes]"); if (!list) return;
    const focus = captureLibraryFieldFocus();
    const finish = () => restoreLibraryFieldFocus(focus);
    list.replaceChildren();
    applyListLayout(list);
    renderBulkControls();
    renderComponentBrowseControls();
    renderPromptBrowseControls();
    refreshOutfitModeBar();
    if (activeView === "fragments") { renderBuilderPanel(list); renderWorkshopIngredients(list); renderWorkshopRecipes(list); finish(); return; }
    if (["recipes", "prompts"].includes(activeView)) { renderPromptLibrary(list); finish(); return; }
    if (activeView === "outfits" && outfitMode === "looks") { renderOutfitLooksLibrary(list); finish(); return; }
    if (activeView === "outfits" && outfitMode === "pieces") { renderWardrobePieces(list, true); finish(); return; }
    if (activeView === "scenes") { renderSceneLibrary(list); finish(); return; }
    renderBuilderPanel(list);
    renderCorpusBlueprintShelf(list);
    const visible = visibleRecipes();
    if (!visible.length) {
        const e = document.createElement("div"); e.textContent = recipes.length ? (activeToken ? `No saved Recipes use ${activeToken}.` : "No saved Recipes match this view.") : "No saved Recipes yet. The corpus Blueprint shelf above is already available; save a Recipe when you want to preserve the full Studio generation state.";
        Object.assign(e.style, { gridColumn: "1 / -1", padding: "42px", color: "#afa9b6", textAlign: "center" }); list.append(e); finish(); return;
    }
    for (const recipe of visible) {
        // ComfyUI themes can apply fixed sizing to semantic <article> elements.
        // A plain div plus explicit max-content grid sizing keeps the details and
        // actions below the thumbnail visible even when many cards are present.
        const recipeId = String(recipe.recipe_id);
        const selected = selectedRecipeIds.has(recipeId);
        const card = document.createElement("div"); Object.assign(card.style, { minWidth: "0", minHeight: "0", height: "auto", alignSelf: "start", display: "flex", flexDirection: "column", position: "relative", overflow: "hidden", border: selected ? "1px solid #ff4ab8" : "1px solid #403249", borderRadius: "11px", background: selected ? "linear-gradient(150deg,rgba(255,74,184,.20),rgba(53,215,255,.07) 55%,rgba(10,9,14,.95))" : "linear-gradient(150deg,rgba(255,74,184,.10),rgba(53,215,255,.04) 55%,rgba(10,9,14,.95))", boxShadow: selected ? "0 0 0 1px rgba(255,74,184,.25),0 12px 32px rgba(0,0,0,.34)" : "0 10px 28px rgba(0,0,0,.25)" });
        card.style.setProperty("height", "auto", "important");
        card.style.setProperty("align-self", "start", "important");
        const preview = document.createElement("div"); Object.assign(preview.style, { width: "100%", height: "220px", minHeight: "220px", flex: "0 0 220px", position: "relative", overflow: "hidden", cursor: "pointer", background: "radial-gradient(circle at 18% 15%,#ff4ab855,transparent 34%),radial-gradient(circle at 82% 20%,#35d7ff44,transparent 38%),#0b0910" });
        preview.title = selectionMode ? `Select ${recipe.name}` : `Use Recipe ${recipe.name} in Prompt Builder`;
        preview.onclick = () => selectionMode ? toggleRecipeSelection(recipeId) : selectBuilderRecipe(recipe);
        if (recipe.preview_ref) {
            const image = document.createElement("img"); image.loading = "lazy"; image.decoding = "async"; image.src = creativeLibraryPreviewUrl(recipe.preview_ref, recipe.updated_at || ""); image.alt = recipe.name; Object.assign(image.style, { width: "100%", height: "100%", objectFit: "cover", display: "block" }); preview.append(image);
        }
        if (recipe.payload?.imported_from_image) { const badge = document.createElement("span"); badge.textContent = "IMPORTED"; Object.assign(badge.style, { position: "absolute", left: "9px", top: "9px", padding: "4px 7px", borderRadius: "999px", color: "#fff", background: "rgba(169,140,255,.82)", font: "700 9px Segoe UI,Arial", letterSpacing: ".08em" }); preview.append(badge); }
        if (selectionMode || selected) {
            const selector = document.createElement("button");
            selector.type = "button";
            selector.textContent = selected ? "✓" : "";
            selector.title = selected ? "Remove from selection" : "Select recipe";
            selector.setAttribute("aria-pressed", selected ? "true" : "false");
            Object.assign(selector.style, {
                position: "absolute", right: "9px", top: "9px", zIndex: "4", width: "30px", height: "30px",
                display: "grid", placeItems: "center", padding: "0", borderRadius: "8px", cursor: "pointer",
                border: selected ? "1px solid #ff4ab8" : "1px solid #35d7ffaa",
                color: selected ? "#fff" : "#d7f8ff", background: selected ? "rgba(255,74,184,.88)" : "rgba(8,7,12,.78)",
                boxShadow: "0 3px 12px rgba(0,0,0,.35)", font: "700 16px Segoe UI,Arial",
            });
            selector.onclick = event => { event.stopPropagation(); toggleRecipeSelection(recipeId); };
            preview.append(selector);
        }
        const body = document.createElement("div"); Object.assign(body.style, { position: "relative", zIndex: "1", padding: "12px" });
        const h = document.createElement("strong"); h.textContent = recipe.name; Object.assign(h.style, { color: "#f5f1f7", display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" });
        const optional = recipe.payload?.optional_nodes?.length || 0; const meta = document.createElement("div"); meta.textContent = `Saved generation Recipe${optional ? ` · ${optional} optional resource section${optional === 1 ? "" : "s"}` : ""} · ${new Date(recipe.updated_at).toLocaleDateString()}`; Object.assign(meta.style, { color: "#a9a1b2", fontSize: "10px", margin: "5px 0 8px" });
        const tags = document.createElement("div"); Object.assign(tags.style, { minHeight: "20px", display: "flex", flexWrap: "wrap", gap: "4px", marginBottom: "10px" });
        for (const token of recipeTokens(recipe.payload).filter(token => ["NAME", "OUTFIT", "BRAND", "SCENE", "TRIGGER"].includes(token))) { const chip = document.createElement("span"); chip.textContent = token; Object.assign(chip.style, { padding: "3px 6px", borderRadius: "999px", border: "1px solid #35d7ff55", color: "#c9f5ff", font: "700 9px Segoe UI,Arial" }); tags.append(chip); }
        const buttons = document.createElement("div"); Object.assign(buttons.style, { position: "relative", zIndex: "2", display: "grid", gridTemplateColumns: "1fr auto auto", gap: "7px", pointerEvents: "auto" });
        const use = action("USE IN BUILDER", "#ff4ab8"); use.onclick = () => selectBuilderRecipe(recipe);
        const review = action("⚙", "#6ee7a2"); review.title = "Review Recipe fields and apply selectively"; review.onclick = () => showDiff(recipe);
        const remove = action("×", "#ff4ab8"); remove.title = "Delete Recipe"; remove.onclick = async () => { if (confirm(`Delete Recipe “${recipe.name}”? Saved Boards that reference it will no longer be loadable.`)) { await request(`/recipes/${encodeURIComponent(recipe.recipe_id)}`, { method: "DELETE" }); await load(); catalogStatus(`Deleted ${recipe.name}.`, "#ff8fce"); } };
        buttons.append(use, review, remove); body.append(h, meta, tags, buttons); card.append(preview, body); list.append(card);
    }
    finish();
}

async function load() {
    const activeKind = activePromptKind();
    const wantsPromptPage = ["recipes", "prompts"].includes(activeView);
    const componentKind = activeView === "outfits" ? "outfit" : activeView === "scenes" ? "scene" : "";
    const wantsWorkshopExtras = activeView === "fragments";
    const wantsDerivedValues = Boolean(componentKind || wantsWorkshopExtras);
    const wantsWardrobe = activeView === "outfits" && outfitMode === "pieces";
    const activePromptParams = wantsPromptPage ? promptPageParams() : null;
    activePromptParams?.set("kind", activeKind);
    const [recipeRows, collectionRows, promptShowcaseRows, templateShowcaseRows, derivedRows, activePromptRows, fragmentRowsResponse, outfitCollectionRows, sceneCollectionRows, wardrobeRows, migrationStatusRows, boardRows, stateRows, outfitPackRows, scenePackRows, wardrobePackRows] = await Promise.all([
        request("/recipes?sync=0"),
        request("/collections"),
        request("/showcase-collections?kind=prompt"),
        request("/showcase-collections?kind=template"),
        wantsDerivedValues ? request(`/derived-values?sync=0${componentKind ? `&kind=${componentKind}` : ""}`) : Promise.resolve(null),
        wantsPromptPage ? request(`/prompt-assets?${activePromptParams.toString()}`) : Promise.resolve(null),
        wantsWorkshopExtras ? request(`/fragments?${fragmentPageParams().toString()}`).catch(() => null) : Promise.resolve(null),
        componentKind === "outfit" || wantsWorkshopExtras ? request("/component-collections?kind=outfit") : Promise.resolve(null),
        componentKind === "scene" || wantsWorkshopExtras ? request("/component-collections?kind=scene") : Promise.resolve(null),
        wantsWardrobe ? request("/wardrobe-items") : Promise.resolve(null),
        wantsWardrobe ? request("/wardrobe-migration/status").catch(() => null) : Promise.resolve(null),
        wantsWorkshopExtras ? request("/boards").catch(() => null) : Promise.resolve(null),
        request("/state").catch(() => ({ revisions: null, counts: null })),
        request("/library-collections?kind=outfit").catch(() => null),
        request("/library-collections?kind=scene").catch(() => null),
        request("/library-collections?kind=wardrobe").catch(() => null),
    ]);
    recipes = Array.isArray(recipeRows) ? recipeRows : [];
    recipeIndex = new Map(recipes.map(recipe => [String(recipe.recipe_id || ""), recipe]));
    collections = Array.isArray(collectionRows) ? collectionRows : [];
    promptShowcaseCollections.prompt = Array.isArray(promptShowcaseRows?.collections) ? promptShowcaseRows.collections : [];
    promptShowcaseCollections.template = Array.isArray(templateShowcaseRows?.collections) ? templateShowcaseRows.collections : [];
    if (derivedRows && typeof derivedRows === "object") {
        derivedValues = {
            ...derivedValues,
            ...(Array.isArray(derivedRows.outfits) ? { outfits: derivedRows.outfits } : {}),
            ...(Array.isArray(derivedRows.scenes) ? { scenes: derivedRows.scenes } : {}),
            logs: { ...(derivedValues.logs || {}), ...(derivedRows.logs || {}) },
        };
        if (Array.isArray(derivedRows.outfits)) componentViewsLoaded.outfit = true;
        if (Array.isArray(derivedRows.scenes)) componentViewsLoaded.scene = true;
    }
    if (activePromptRows) {
        promptAssets = Array.isArray(activePromptRows.prompts) ? activePromptRows.prompts : [];
        promptTotal = Math.max(0, Number(activePromptRows.total || 0));
        promptCorpusTotals = activePromptRows.corpus_totals && typeof activePromptRows.corpus_totals === "object" ? activePromptRows.corpus_totals : promptCorpusTotals;
        promptAssetTotal = Math.max(0, Number(promptCorpusTotals.prompt || (activeKind === "prompt" ? activePromptRows.total_assets : promptAssetTotal) || 0));
        promptBlueprintTotal = Math.max(0, Number(promptCorpusTotals.template || (activeKind === "template" ? activePromptRows.total_assets : promptBlueprintTotal) || 0));
        if (activePromptRows.home_counts && typeof activePromptRows.home_counts === "object") promptHomeCounts[activeKind] = activePromptRows.home_counts;
        if (activePromptRows.home_universe && typeof activePromptRows.home_universe === "object") promptHomeUniverse[activeKind] = activePromptRows.home_universe;
        if (activeKind === "template" && activePromptRows.placeholder_counts && typeof activePromptRows.placeholder_counts === "object") promptPlaceholderCounts = activePromptRows.placeholder_counts;
        if (activeKind === "template" && activePromptRows.placeholder_available_counts && typeof activePromptRows.placeholder_available_counts === "object") promptPlaceholderAvailableCounts = activePromptRows.placeholder_available_counts;
        if (activePromptRows.collection_counts && typeof activePromptRows.collection_counts === "object") promptCollectionCounts[activeKind] = activePromptRows.collection_counts;
        promptAssetRevision += 1;
        promptViewCache = { key: "", rows: [] };
        promptFacetCounts = activePromptRows.facet_counts && typeof activePromptRows.facet_counts === "object" ? activePromptRows.facet_counts : emptyPromptFacets();
        promptFacetUniverse = activePromptRows.facet_universe && typeof activePromptRows.facet_universe === "object" ? activePromptRows.facet_universe : promptFacetUniverse;
        promptFacetCovers = activePromptRows.facet_covers && typeof activePromptRows.facet_covers === "object" ? activePromptRows.facet_covers : emptyPromptFacets();
        promptBlueprintTotal = Math.max(0, Number(promptCorpusTotals.template || activePromptRows.blueprints?.total || promptBlueprintTotal || 0));
        promptComponentBlueprintTotal = Math.max(0, Number(activePromptRows.blueprints?.component_total || promptComponentBlueprintTotal || 0));
        promptBlueprintSignatures = activePromptRows.blueprints?.signature_counts && typeof activePromptRows.blueprints.signature_counts === "object" ? activePromptRows.blueprints.signature_counts : promptBlueprintSignatures;
        blueprintAssets = [];
    }
    if (fragmentRowsResponse) {
        fragmentRows = Array.isArray(fragmentRowsResponse.fragments) ? fragmentRowsResponse.fragments : [];
        fragmentSummary = fragmentRowsResponse.summary && typeof fragmentRowsResponse.summary === "object" ? fragmentRowsResponse.summary : fragmentSummary;
        fragmentTotal = Math.max(0, Number(fragmentRowsResponse.total || fragmentSummary.total || 0));
        workshopExtrasLoaded = true;
    }
    if (boardRows) boards = Array.isArray(boardRows.boards) ? boardRows.boards : boards;
    if (wardrobeRows) { wardrobeItems = Array.isArray(wardrobeRows.items) ? wardrobeRows.items : []; wardrobeDataLoaded = true; }
    if (migrationStatusRows && typeof migrationStatusRows === "object") wardrobeMigrationStatus = migrationStatusRows;
    if (outfitCollectionRows) componentCollections.outfit = Array.isArray(outfitCollectionRows.collections) ? outfitCollectionRows.collections : componentCollections.outfit;
    if (sceneCollectionRows) componentCollections.scene = Array.isArray(sceneCollectionRows.collections) ? sceneCollectionRows.collections : componentCollections.scene;
    if (outfitPackRows) libraryCollections.outfit = Array.isArray(outfitPackRows.collections) ? outfitPackRows.collections : libraryCollections.outfit;
    if (scenePackRows) libraryCollections.scene = Array.isArray(scenePackRows.collections) ? scenePackRows.collections : libraryCollections.scene;
    if (wardrobePackRows) libraryCollections.wardrobe = Array.isArray(wardrobePackRows.collections) ? wardrobePackRows.collections : libraryCollections.wardrobe;
    libraryLoadedOnce = true;
    libraryRevisions = stateRows?.revisions && typeof stateRows.revisions === "object" ? stateRows.revisions : libraryRevisions;
    libraryStateCounts = stateRows?.counts && typeof stateRows.counts === "object" ? stateRows.counts : libraryStateCounts;
    normalizeBuilderDraft();
    pruneRecipeSelection();
    refreshLibraryChrome(); refreshOutfitModeBar();
    renderCollectionControls();
    renderBulkControls();
    render();
}

function sameLibraryRevisions(left, right) {
    if (!left || !right) return false;
    return ["recipes", "prompts", "fragments", "components"].every(key => String(left[key] ?? "") === String(right[key] ?? ""));
}

function refreshLibraryIfStale() {
    if (libraryRefreshPromise) return libraryRefreshPromise;
    libraryRefreshPromise = (async () => {
        try {
            const state = await request("/state");
            const revisions = state?.revisions && typeof state.revisions === "object" ? state.revisions : null;
            if (state?.counts && typeof state.counts === "object") libraryStateCounts = state.counts;
            if (sameLibraryRevisions(libraryRevisions, revisions)) {
                refreshLibraryChrome(); refreshOutfitModeBar();
                catalogStatus("Ready · reopened from cache", "#6ee7a2");
                return false;
            }
            if (String(libraryRevisions?.components ?? "") !== String(revisions?.components ?? "")) {
                componentViewsLoaded = { outfit: false, scene: false };
                wardrobeDataLoaded = false;
            }
            if (String(libraryRevisions?.fragments ?? "") !== String(revisions?.fragments ?? "")) workshopExtrasLoaded = false;
            catalogStatus("Library changed · refreshing…", "#35d7ff");
            await load();
            return true;
        } catch (error) {
            catalogStatus("Showing cached Library · refresh unavailable", "#f6e65a");
            return false;
        }
    })().finally(() => { libraryRefreshPromise = null; });
    return libraryRefreshPromise;
}

async function importRecipeImage(file) {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`${API}/import-image`, { method: "POST", body: form });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok || !data.saved) {
        throw new Error(data.error || `Could not import ${file.name || "this image"}.`);
    }
    return data;
}

async function bulkImportRecipeImages(files, onProgress = null) {
    const selected = Array.from(files || []).filter(Boolean);
    const saved = [];
    const skipped = [];
    for (let index = 0; index < selected.length; index += 1) {
        const file = selected[index];
        onProgress?.(index + 1, selected.length, file);
        try {
            saved.push(await importRecipeImage(file));
        } catch (error) {
            skipped.push({ file, error: error?.message || "Import failed." });
        }
    }
    if (saved.length) {
        try {
            await request('/recipes/last-import', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ recipe_ids: saved.map(item => String(item.recipe_id || '')).filter(Boolean) }) });
        } catch (error) { console.warn('[Sick Ollie Creative Library] Could not stamp last import batch.', error); }
    }
    return { saved, skipped };
}

async function saveCurrentStudioRecipe(defaultName = "New saved prompt", options = {}) {
    const payload = captureRecipe();
    if (!payload.nodes?.length) throw new Error("Add a Studio Prompt Core or Generation Core before saving a recipe.");
    const name = await askRecipeName(defaultName);
    if (!name) return null;
    const result = await saveRecipeRequest(name, payload, options.previewData);
    if (root) await load();
    if (result.preview_matched === true) catalogStatus(`Saved ${name} to Creative Library · prompt, settings, and thumbnail captured from the current Preview image.`);
    else if (result.preview_matched === false) catalogStatus(`Saved ${name} · thumbnail skipped because the Preview did not verify against the saved recipe.`, "#f6e65a");
    else catalogStatus(`Saved ${name}.`);
    window.dispatchEvent(new CustomEvent("sickollie:recipe-saved", { detail: { name, recipe_id: result.recipe_id, preview_ref: result.preview_ref || "" } }));
    return result;
}


function renderLibraryLoadError(error) {
    const list = root?.querySelector("[data-recipes]"); if (!list) return;
    list.replaceChildren(); applyListLayout(list);
    const card = document.createElement("div"); Object.assign(card.style, { maxWidth: "760px", margin: "40px auto", padding: "20px", borderRadius: "12px", border: "1px solid #ff789b66", background: "rgba(255,120,155,.055)", color: "#d8d1dc", textAlign: "center" });
    const title = document.createElement("strong"); title.textContent = "Creative Library could not finish opening"; Object.assign(title.style, { display: "block", color: "#ff9ab6", font: "900 15px Segoe UI,Arial" });
    const detail = document.createElement("div"); detail.textContent = error?.message || "The Library API did not respond."; Object.assign(detail.style, { marginTop: "8px", color: "#aaa2b4", font: "11px/1.5 Consolas,monospace", wordBreak: "break-word" });
    const retry = action("RETRY LIBRARY LOAD", "#6ee7a2"); Object.assign(retry.style, { marginTop: "14px" }); retry.onclick = async () => { retry.disabled = true; libraryBootstrapping = true; refreshLibraryChrome(); list.replaceChildren(); const wait = document.createElement("div"); wait.textContent = "Reopening Creative Library…"; Object.assign(wait.style,{padding:"48px",textAlign:"center",color:"#b9b1c2"}); list.append(wait); try { await load(); libraryBootstrapping = false; refreshLibraryChrome(); render(); catalogStatus("Ready", "#6ee7a2"); } catch (nextError) { libraryBootstrapping = false; refreshLibraryChrome(); renderLibraryLoadError(nextError); catalogStatus(nextError?.message || "Library load failed", "#ff78bd"); } };
    card.append(title, detail, retry); list.append(card);
}

async function openRecipes() {
    if (root) return;
    outfitMode = "pieces";
    root = document.createElement("div");
    installStudioInteractions(root);
    Object.assign(root.style, { position: "fixed", inset: "0", zIndex: "100030", background: "rgba(5,3,8,.92)", display: "flex", alignItems: "center", justifyContent: "center", padding: "16px" });
    const panel = document.createElement("section");
    Object.assign(panel.style, { boxSizing: "border-box", width: "min(2560px,calc(100vw - 32px))", height: "min(1800px,calc(100vh - 32px))", minWidth: "min(780px,calc(100vw - 32px))", minHeight: "min(620px,calc(100vh - 32px))", display: "flex", flexDirection: "column", background: "#0d0a12", border: "1px solid #ff4ab899", borderRadius: "22px", overflow: "hidden", color: "#f4f1f6", boxShadow: "0 30px 100px rgba(0,0,0,.62),0 0 42px rgba(255,74,184,.14)" });

    const head = document.createElement("header");
    Object.assign(head.style, { padding: "12px 16px", minHeight: "76px", display: "flex", alignItems: "center", gap: "10px", background: `linear-gradient(90deg,rgba(7,5,10,.16),rgba(7,5,10,.42) 58%,rgba(7,5,10,.60)), url(${RECIPE_LIBRARY_BACKGROUND_URL}) center / cover no-repeat`, borderBottom: "1px solid #35d7ff55" });
    const titleWrap = document.createElement("div"); Object.assign(titleWrap.style, { flex: "1", minWidth: "260px" });
    const eyebrow = document.createElement("div"); eyebrow.textContent = "SICK OLLIE STUDIO"; Object.assign(eyebrow.style, { color: "#35d7ff", font: "800 10px Segoe UI,Arial", letterSpacing: ".16em" });
    const title = document.createElement("div"); title.textContent = "CREATIVE LIBRARY"; Object.assign(title.style, { marginTop: "2px", color: "#fff", font: "900 28px/1 Segoe UI,Arial", letterSpacing: ".025em", textShadow: "0 2px 14px rgba(255,74,184,.5)" });
    const copy = document.createElement("div"); copy.textContent = "Build visually, discover calmly, and keep the giant source corpus reversible and out of your way."; Object.assign(copy.style, { marginTop: "6px", color: "#c3bbc9", fontSize: "11px" });
    titleWrap.append(eyebrow, title, copy);

    const save = action("Save Recipe", "#f6e65a"); save.dataset.saveRecipe = ""; save.onclick = async () => { save.disabled = true; try { await saveCurrentStudioRecipe("New Recipe"); } catch (error) { catalogStatus(error.message, "#ff78bd"); alert(error.message); } finally { save.disabled = false; } };
    const importImage = action("Import image", "#6ee7a2");
    const bulkImport = action("Bulk import images", "#b89aff"); bulkImport.title = "Import multiple metadata-bearing PNG, JPG, or WEBP outputs";
    const buildAsset = action("Build asset", "#6ee7a2"); buildAsset.dataset.buildAsset = ""; buildAsset.title = "Create Outfit or Scene values directly"; buildAsset.onclick = showCurrentAssetBuilder;
    const importLogs = action("Import outfit logs", "#35d7ff"); importLogs.dataset.importLogs = ""; importLogs.title = "Import existing .txt logs into the Outfit or Scene Library"; importLogs.onclick = () => showLogImporter(activeView === "scenes" ? "scene" : "outfit");
    const migrateLooks = action("Migrate looks", "#f6e65a"); migrateLooks.dataset.migrateLooks = ""; migrateLooks.title = "Analyze existing Outfit Looks and non-destructively harvest reusable Pieces"; migrateLooks.onclick = showWardrobeMigration;
    const libraryPack = action("Library Pack", "#6ee7a2"); libraryPack.title = "Build or import one portable .soslibrary pack"; libraryPack.onclick = openLibraryPackWorkflow;
    const cleanOrphanThumbs = action("Clean orphan thumbnails", "#ff9b5f"); cleanOrphanThumbs.title = "Dry-run scan for thumbnail files no live Creative Library record references"; cleanOrphanThumbs.onclick = () => void showOrphanThumbnailCleaner();
    const generatePreviews = action(catalogRun ? "STOP PREVIEW RUN" : "GENERATE PREVIEWS", "#6ee7a2"); generatePreviews.dataset.libraryYearbook = ""; generatePreviews.dataset.catalogRun = ""; generatePreviews.title = "Generate previews for selected items, the current filtered scope, selected Library sections, or the entire Creative Library"; generatePreviews.onclick = openGeneratePreviewsDialog;
    const theaterButton = action("THEATER", "#b89aff"); theaterButton.dataset.catalogTheater = ""; theaterButton.hidden = !catalogRun; theaterButton.disabled = !catalogRun; theaterButton.title = "Reopen Theater Mode for the active Preview Run"; theaterButton.onclick = () => { if (catalogRun) { catalogRun.theaterEnabled = true; if (!catalogRun.theater) catalogRun.theater = { entries: [], cursor: -1, live: true, sizeMode: catalogTheaterInitialSize(), overlay: null, ui: null, dismissed: false }; openCreativeTheater(catalogRun); } };

    const pickImages = (multiple) => {
        const picker = document.createElement("input"); picker.type = "file"; picker.accept = "image/png,image/jpeg,image/webp"; picker.multiple = multiple;
        picker.onchange = async () => {
            const files = Array.from(picker.files || []); if (!files.length) return;
            importImage.disabled = true; bulkImport.disabled = true;
            try {
                const result = await bulkImportRecipeImages(files, (index, total, file) => {
                    const label = total === 1 ? `Reading ${file.name}…` : `Importing ${index}/${total}: ${file.name}`;
                    importImage.textContent = total === 1 ? "Importing…" : `Importing ${index}/${total}…`;
                    bulkImport.textContent = total === 1 ? "Importing…" : `Importing ${index}/${total}…`;
                    catalogStatus(label, "#35d7ff");
                });
                if (result.saved.length) await load();
                if (!result.skipped.length) {
                    const data = result.saved[0];
                    const detail = result.saved.length === 1 ? `Imported ${data.name} · Creative Library classified the reusable assets automatically.` : `Imported ${result.saved.length} images into Creative Library.`;
                    catalogStatus(detail);
                } else if (result.saved.length) {
                    catalogStatus(`Imported ${result.saved.length} image${result.saved.length === 1 ? "" : "s"} · skipped ${result.skipped.length}.`, "#f6e65a");
                    console.warn("[Sick Ollie Creative Library] Some bulk imports were skipped.", result.skipped);
                } else {
                    const detail = result.skipped.slice(0, 3).map(item => `${item.file.name}: ${item.error}`).join("\n");
                    catalogStatus("No images imported. Check the selected files' metadata.", "#ff78bd");
                    alert(`No Creative Library items were imported.\n${detail || "Choose metadata-bearing PNG, JPG, or WEBP output images."}`);
                }
                if (multiple && result.saved.length && collections.length) showImportedRecipesCollectionEditor(result.saved.map(item => item.recipe_id));
            } finally {
                importImage.disabled = false; bulkImport.disabled = false; importImage.textContent = "Import image"; bulkImport.textContent = "Bulk import images";
            }
        };
        picker.click();
    };
    importImage.onclick = () => pickImages(false); bulkImport.onclick = () => pickImages(true);
    const x = action("×"); x.onclick = close;
    const moreTools = document.createElement("details"); moreTools.dataset.libraryMenu = ""; Object.assign(moreTools.style, { position: "relative", zIndex: "8" });
    const moreSummary = document.createElement("summary"); moreSummary.textContent = "LIBRARY MENU"; Object.assign(moreSummary.style, { listStyle: "none", padding: "9px 12px", borderRadius: "8px", cursor: "pointer", border: "1px solid #b89aff99", color: "#fff", background: "linear-gradient(180deg,#302a39,#201d27)", boxShadow: "inset 0 1px 0 rgba(255,255,255,.05)", font: "900 10px Segoe UI,Arial", letterSpacing: ".06em" });
    const moreTray = document.createElement("div"); moreTray.dataset.libraryMenuTray = ""; Object.assign(moreTray.style, { position: "absolute", right: "0", top: "calc(100% + 8px)", width: "390px", maxHeight: "min(720px,calc(100vh - 130px))", overflowY: "auto", display: "flex", flexDirection: "column", gap: "8px", padding: "10px", borderRadius: "13px", border: "1px solid #b89aff66", background: "linear-gradient(180deg,#15121a,#0e0c12)", boxShadow: "0 22px 70px rgba(0,0,0,.68),0 0 28px rgba(184,154,255,.08)" });

    const menuHero = document.createElement("div"); Object.assign(menuHero.style, { padding: "10px 11px", borderRadius: "10px", border: "1px solid #41394a", background: "linear-gradient(135deg,rgba(184,154,255,.10),rgba(53,215,255,.035))" });
    const menuHeroEyebrow = document.createElement("div"); menuHeroEyebrow.textContent = "CREATIVE LIBRARY"; Object.assign(menuHeroEyebrow.style, { color: "#b89aff", font: "900 8px Segoe UI,Arial", letterSpacing: ".14em" });
    const menuHeroTitle = document.createElement("div"); menuHeroTitle.dataset.libraryMenuTitle = ""; Object.assign(menuHeroTitle.style, { marginTop: "3px", color: "#fff", font: "900 14px Segoe UI,Arial" });
    const menuHeroCopy = document.createElement("div"); menuHeroCopy.dataset.libraryMenuCopy = ""; Object.assign(menuHeroCopy.style, { marginTop: "4px", color: "#9f98a7", font: "10px/1.4 Segoe UI,Arial" });
    menuHero.append(menuHeroEyebrow, menuHeroTitle, menuHeroCopy); moreTray.append(menuHero);

    const menuSection = (label, hint = "") => {
        const section = document.createElement("section"); Object.assign(section.style, { padding: "9px", borderRadius: "10px", border: "1px solid #302b36", background: "rgba(255,255,255,.018)" });
        const header = document.createElement("div"); Object.assign(header.style, { display: "flex", justifyContent: "space-between", gap: "10px", alignItems: "baseline", marginBottom: "7px" });
        const name = document.createElement("strong"); name.textContent = label; Object.assign(name.style, { color: "#d8d1dc", font: "900 8px Segoe UI,Arial", letterSpacing: ".11em" }); header.append(name);
        if (hint) { const copy = document.createElement("span"); copy.textContent = hint; Object.assign(copy.style, { color: "#736d7b", font: "8px Segoe UI,Arial", textAlign: "right" }); header.append(copy); }
        const grid = document.createElement("div"); Object.assign(grid.style, { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px" }); section.append(header, grid);
        return { section, grid };
    };
    const menuButton = button => { Object.assign(button.style, { minWidth: "0", width: "100%", minHeight: "33px", fontSize: "9px", padding: "7px 8px" }); return button; };

    const currentSection = menuSection("CURRENT LIBRARY", "changes with the active tab"); currentSection.section.dataset.libraryMenuCurrent = "";
    const currentMenuButtons = [buildAsset, importLogs, migrateLooks];
    for (const button of currentMenuButtons) { button.dataset.libraryMenuContextAction = ""; currentSection.grid.append(menuButton(button)); }
    moreTray.append(currentSection.section);

    const transferSection = menuSection("PACKS + TRANSFER", "portable library content");
    transferSection.grid.append(menuButton(libraryPack)); moreTray.append(transferSection.section);

    const imageSection = menuSection("IMAGES", "metadata-aware import");
    imageSection.grid.append(menuButton(importImage), menuButton(bulkImport)); moreTray.append(imageSection.section);

    const maintenanceSection = menuSection("MAINTENANCE", "cleanup + deliberate purge"); maintenanceSection.section.dataset.libraryMenuMaintenance = "";
    maintenanceSection.grid.append(menuButton(cleanOrphanThumbs));
    const purgeLibraryMenu = menuButton(action("Purge…", "#ff4ab8")); purgeLibraryMenu.dataset.libraryMenuPurge = ""; purgeLibraryMenu.title = "Choose any Creative Library areas to completely purge, or purge the entire Creative Library"; purgeLibraryMenu.onclick = () => showCreativeLibraryPurge(); purgeLibraryMenu.style.background = "rgba(255,74,184,.07)"; maintenanceSection.grid.append(purgeLibraryMenu);
    moreTray.append(maintenanceSection.section);

    const safety = document.createElement("div"); safety.textContent = "Purge always opens an itemized second warning before changing library data."; Object.assign(safety.style, { padding: "2px 3px 0", color: "#786f7f", font: "8px/1.35 Segoe UI,Arial", textAlign: "center" }); moreTray.append(safety);
    moreTools.append(moreSummary, moreTray);
    head.append(titleWrap, save, generatePreviews, theaterButton, moreTools, x);

    const progress = document.createElement("div"); progress.dataset.catalogRunProgress = ""; progress.hidden = !catalogRun;
    Object.assign(progress.style, { position: "relative", overflow: "hidden", flex: "0 0 auto", padding: "7px 16px", borderBottom: "1px solid #4d4130", color: "#f6e65a", background: `linear-gradient(90deg,rgba(246,230,90,.20) 0 var(--progress,0%),#151114 var(--progress,0%) 100%)`, font: "800 10px Segoe UI,Arial", letterSpacing: ".05em" });

    const tabs = document.createElement("nav"); Object.assign(tabs.style, { display: "grid", gridTemplateColumns: `repeat(${Object.keys(LIBRARY_VIEWS).length},minmax(112px,1fr))`, flex: "0 0 auto", background: "#0a080e", borderBottom: "1px solid #2c2932" });
    for (const [view, meta] of Object.entries(LIBRARY_VIEWS)) {
        const tab = document.createElement("button"); tab.type = "button"; tab.dataset.libraryTab = view; tab.textContent = meta.label;
        Object.assign(tab.style, { minHeight: "46px", padding: "9px 12px", border: "0", borderRight: "1px solid #211e26", borderBottom: "2px solid transparent", cursor: "pointer", color: "#aaa4b0", background: "rgba(255,255,255,.018)", font: "800 11px Segoe UI,Arial", letterSpacing: ".07em" });
        tab.onclick = () => setActiveView(view); tabs.append(tab);
    }
    const viewDescription = document.createElement("div"); viewDescription.dataset.libraryViewDescription = ""; Object.assign(viewDescription.style, { flex: "0 0 auto", padding: "7px 14px", color: "#9f98a7", background: "rgba(11,9,15,.92)", borderBottom: "1px solid #211e26", font: "11px Segoe UI,Arial" });
    const outfitModeBar = document.createElement("nav"); outfitModeBar.dataset.outfitModeBar = ""; Object.assign(outfitModeBar.style, { display: "none", flex: "0 0 auto", gap: "7px", padding: "8px 14px", borderBottom: "1px solid #3a3422", background: "linear-gradient(90deg,rgba(246,230,90,.045),rgba(9,8,13,.82))" });
    for (const mode of ["looks", "pieces"]) { const button = action(mode === "looks" ? "LOOKS" : "WARDROBE", "#f6e65a"); button.dataset.outfitMode = mode; Object.assign(button.style, { minWidth: "138px", padding: "8px 12px", fontSize: "10px", letterSpacing: ".06em" }); button.onclick = () => setOutfitMode(mode); outfitModeBar.append(button); }

    const tools = document.createElement("div"); tools.dataset.libraryTools = ""; Object.assign(tools.style, { display: "none", flex: "0 0 auto", flexWrap: "wrap", alignItems: "center", gap: "6px", padding: "9px 14px", borderBottom: "1px solid #2c2932", background: "rgba(9,8,13,.68)", position: "relative", zIndex: "2" });
    const tokenTools = document.createElement("div"); tokenTools.dataset.recipeTokenTools = ""; Object.assign(tokenTools.style, { display: "none", gap: "6px", alignItems: "center", flexWrap: "wrap" });
    for (const token of FILTER_TOKENS) { const filter = action(token || "ALL", token === activeToken ? "#ff4ab8" : "#35d7ff"); filter.dataset.recipeFilter = token; filter.onclick = () => { activeToken = token; for (const item of tokenTools.querySelectorAll("[data-recipe-filter]")) item.style.borderColor = item.dataset.recipeFilter === activeToken ? "#ff4ab8" : "#35d7ffaa"; render(); }; tokenTools.append(filter); }
    tools.append(tokenTools);

    const collectionDivider = document.createElement("span"); collectionDivider.dataset.collectionDivider = ""; collectionDivider.textContent = "|"; collectionDivider.style.color = "#514b5a";
    const manageCollections = action("PROMPT COLLECTIONS", "#b89aff"); manageCollections.dataset.manageCollections = ""; manageCollections.onclick = showActiveCollectionManager;
    const collectionTools = document.createElement("div"); collectionTools.dataset.recipeCollections = ""; Object.assign(collectionTools.style, { display: "none", flex: "0 0 100%", width: "100%", alignItems: "center", gap: "6px", flexWrap: "wrap", order: "3", paddingTop: "2px" });
    tools.append(collectionDivider, manageCollections);

    const componentBrowseTools = document.createElement("div"); componentBrowseTools.dataset.componentBrowseTools = ""; Object.assign(componentBrowseTools.style, { display: "none", alignItems: "center", gap: "6px", flexWrap: "wrap" });
    const componentSearchInput = document.createElement("input"); componentSearchInput.dataset.componentSearch = ""; componentSearchInput.type = "search"; componentSearchInput.placeholder = "Search library…";
    Object.assign(componentSearchInput.style, { width: "190px", padding: "7px 9px", borderRadius: "7px", color: "#fff", background: "#111016", border: "1px solid #4a4452", outline: "none", font: "10px Segoe UI,Arial" });
    componentSearchInput.oninput = () => { const kind = currentComponentKind(); if (!kind) return; componentSearch[kind] = componentSearchInput.value; componentPage[kind] = 0; selectedComponentIds.clear(); renderBulkControls(); render(); };

    const componentRating = makeSelect([["", "All ratings"], ["unrated", "Unrated"], ["5", "5★ only"], ["4plus", "4★ +"], ["3plus", "3★ +"], ["low", "1–2★"]], "");
    componentRating.dataset.componentRatingFilter = ""; Object.assign(componentRating.style, { width: "132px", padding: "7px 8px", fontSize: "10px" });
    componentRating.onchange = () => { const kind = currentComponentKind(); if (!kind) return; componentRatingFilter[kind] = componentRating.value; componentPage[kind] = 0; selectedComponentIds.clear(); renderBulkControls(); render(); };

    const componentThumbs = makeSelect([["", "All previews"], ["missing", "Missing preview"], ["catalog", "Catalog preview"], ["other", "Other preview"]], "");
    componentThumbs.dataset.componentThumbnailFilter = ""; Object.assign(componentThumbs.style, { width: "142px", padding: "7px 8px", fontSize: "10px" });
    componentThumbs.onchange = () => { const kind = currentComponentKind(); if (!kind) return; componentThumbnailFilter[kind] = componentThumbs.value; componentPage[kind] = 0; selectedComponentIds.clear(); renderBulkControls(); render(); };

    const componentSortSelect = makeSelect([["preview_newest", "Newest preview"], ["recent", "Recently added"], ["name", "A → Z"], ["rating", "Highest rated"], ["most_used", "Most used"], ["least_used", "Least used"]], "preview_newest");
    componentSortSelect.dataset.componentSort = ""; Object.assign(componentSortSelect.style, { width: "135px", padding: "7px 8px", fontSize: "10px" });
    componentSortSelect.onchange = () => { const kind = currentComponentKind(); if (!kind) return; componentSort[kind] = componentSortSelect.value; componentPage[kind] = 0; render(); };

    const componentPrev = action("← Previous", "#8f8997"); componentPrev.dataset.componentPrev = ""; componentPrev.title = "Previous page"; componentPrev.onclick = () => { const kind = currentComponentKind(); if (!kind) return; componentPage[kind] = Math.max(0, Number(componentPage[kind] || 0) - 1); render(); root?.querySelector("[data-recipes]")?.scrollTo?.({ top: 0 }); };
    const componentRange = document.createElement("span"); componentRange.dataset.componentRange = ""; Object.assign(componentRange.style, { minWidth: "116px", textAlign: "center", color: "#aaa2b4", font: "700 9px Segoe UI,Arial" });
    const componentNext = action("Next →", "#8f8997"); componentNext.dataset.componentNext = ""; componentNext.title = "Next page"; componentNext.onclick = () => { const kind = currentComponentKind(); if (!kind) return; componentPage[kind] = Number(componentPage[kind] || 0) + 1; render(); root?.querySelector("[data-recipes]")?.scrollTo?.({ top: 0 }); };
    const cleanup = action("CLEAN UP", "#f6e65a"); cleanup.title = "Review near-duplicates, fragments, long values, and prompt-like values"; cleanup.onclick = () => showCleanupReview(currentComponentKind());
    const importHistory = action("IMPORT HISTORY", "#ff9b5f"); importHistory.title = "Review or undo recent Outfit / Scene log imports"; importHistory.onclick = () => showImportHistory(currentComponentKind());
    const refreshComponents = action("Refresh", "#6ee7a2"); refreshComponents.onclick = () => load().catch(error => catalogStatus(error.message, "#ff78bd"));
    componentBrowseTools.append(componentSearchInput, componentRating, componentThumbs, componentSortSelect, componentPrev, componentRange, componentNext, cleanup, importHistory, refreshComponents); tools.append(componentBrowseTools);

    const promptBrowseTools = document.createElement("div"); promptBrowseTools.dataset.promptBrowseTools = ""; Object.assign(promptBrowseTools.style, { display: "none", alignItems: "center", gap: "6px", flexWrap: "wrap" });
    const promptDiscover = action("← DISCOVER", "#35d7ff"); promptDiscover.title = "Return to guided Prompt discovery"; promptDiscover.onclick = closePromptVault;
    const promptSearchInput = document.createElement("input"); promptSearchInput.dataset.promptSearch = ""; promptSearchInput.type = "search"; promptSearchInput.placeholder = "Search prompts…";
    Object.assign(promptSearchInput.style, { width: "220px", padding: "7px 9px", borderRadius: "7px", color: "#fff", background: "#111016", border: "1px solid #4a4452", outline: "none", font: "10px Segoe UI,Arial" });
    promptSearchInput.oninput = () => { promptSearch = promptSearchInput.value; promptPage = 0; selectedRecipeIds.clear(); renderBulkControls(); queuePromptPageLoad(180); };
    const promptFacetChoices = {
        concept: [["", "Any concept"], ...PROMPT_GALLERY_FAMILIES.find(family => family.axis === "concept").values.map(value => [value, value])],
        style: [["", "Any style"], ...PROMPT_GALLERY_FAMILIES.find(family => family.axis === "style").values.map(value => [value, value])],
        content: [["", "Any content"], ...PROMPT_GALLERY_FAMILIES.find(family => family.axis === "content").values.map(value => [value, value])],
        time: [["", "Any time"], ...PROMPT_GALLERY_FAMILIES.find(family => family.axis === "time").values.map(value => [value, value])],
    };
    const promptFacetSelects = [];
    for (const axis of ["concept", "style", "content", "time"]) {
        const select = makeSelect(promptFacetChoices[axis], ""); select.dataset.promptFacet = axis; Object.assign(select.style, { width: axis === "concept" ? "132px" : "118px", padding: "7px 8px", fontSize: "10px" });
        select.onchange = () => { promptFacetFilters[axis] = select.value; promptPage = 0; selectedRecipeIds.clear(); renderBulkControls(); queuePromptPageLoad(); }; promptFacetSelects.push(select);
    }
    const blueprintFilter = action("BLUEPRINTS", "#ff4ab8"); blueprintFilter.dataset.promptBlueprintFilter = ""; blueprintFilter.title = "Show only canonical Prompts with portable uppercase placeholder formulas";
    blueprintFilter.onclick = () => { promptBlueprintOnly = !promptBlueprintOnly; if (!promptBlueprintOnly) promptSignatureFilter = ""; promptPage = 0; selectedRecipeIds.clear(); queuePromptPageLoad(); };
    const signatureFilter = makeSelect([["", "Any Blueprint formula"]], ""); signatureFilter.dataset.promptSignatureFilter = ""; Object.assign(signatureFilter.style, { width: "190px", padding: "7px 8px", fontSize: "10px" });
    signatureFilter.onchange = () => { promptSignatureFilter = signatureFilter.value; if (promptSignatureFilter) promptBlueprintOnly = true; promptPage = 0; selectedRecipeIds.clear(); queuePromptPageLoad(); };
    const promptSource = makeSelect([["", "All prompt sources"], ["ready", "Canonical corpus"], ["recipe", "Saved Recipe prompts"]], "");
    promptSource.dataset.promptSourceFilter = ""; Object.assign(promptSource.style, { width: "155px", padding: "7px 8px", fontSize: "10px" });
    promptSource.onchange = () => { promptSourceFilter = promptSource.value; promptPage = 0; queuePromptPageLoad(); };
    const promptSortSelect = makeSelect([["newest", "Newest"], ["oldest", "Oldest"], ["source_order", "Original log order"], ["name", "A → Z"], ["most_used", "Most used"]], "newest"); promptSortSelect.dataset.promptSort = ""; Object.assign(promptSortSelect.style, { width: "105px", padding: "7px 8px", fontSize: "10px" }); promptSortSelect.onchange = () => { promptSort = promptSortSelect.value; promptPage = 0; queuePromptPageLoad(); };
    const clearPromptFilters = action("CLEAR", "#8f8997"); clearPromptFilters.title = "Clear Prompt Vault search and facets"; clearPromptFilters.onclick = () => { promptSearch = ""; promptSourceFilter = ""; promptSignatureFilter = ""; promptBlueprintOnly = false; promptFacetFilters = emptyPromptFacetFilters(); activeCollection = ""; promptPage = 0; queuePromptPageLoad(); };
    const promptPrev = action("←", "#8f8997"); promptPrev.dataset.promptPrev = ""; promptPrev.onclick = () => { promptPage = Math.max(0, promptPage - 1); queuePromptPageLoad(); root?.querySelector("[data-recipes]")?.scrollTo?.({ top: 0 }); };
    const promptRange = document.createElement("span"); promptRange.dataset.promptRange = ""; Object.assign(promptRange.style, { minWidth: "116px", textAlign: "center", color: "#aaa2b4", font: "700 9px Segoe UI,Arial" });
    const promptNext = action("→", "#8f8997"); promptNext.dataset.promptNext = ""; promptNext.onclick = () => { promptPage += 1; queuePromptPageLoad(); root?.querySelector("[data-recipes]")?.scrollTo?.({ top: 0 }); };
    const harvestOutfits = action("HARVEST", "#f6e65a"); harvestOutfits.dataset.promptHarvest = ""; harvestOutfits.title = "Maintenance: detect reusable Outfit Looks inside imported / flattened prompts"; harvestOutfits.onclick = () => showPromptHarvestWorkbench();
    promptBrowseTools.append(promptDiscover, promptSearchInput, blueprintFilter, signatureFilter, ...promptFacetSelects, promptSource, promptSortSelect, clearPromptFilters, promptPrev, promptRange, promptNext, harvestOutfits); tools.append(promptBrowseTools);

    const bulkDivider = document.createElement("span"); bulkDivider.dataset.bulkDivider = ""; bulkDivider.textContent = "|"; bulkDivider.style.color = "#514b5a";
    const bulkControls = document.createElement("div"); bulkControls.dataset.recipeBulkControls = ""; Object.assign(bulkControls.style, { display: "contents" });
    const selectToggle = action("SELECT", "#35d7ff"); selectToggle.dataset.bulkSelectToggle = ""; selectToggle.onclick = () => setSelectionMode(!selectionMode);
    const selectVisible = action("SELECT VISIBLE", "#35d7ff"); selectVisible.dataset.bulkSelectVisible = ""; selectVisible.onclick = selectVisibleRecipes;
    const selectedCount = document.createElement("span"); selectedCount.dataset.bulkSelectedCount = ""; Object.assign(selectedCount.style, { display: "none", alignItems: "center", minHeight: "30px", padding: "0 8px", borderRadius: "7px", border: "1px solid #ff4ab866", color: "#ffc1e6", background: "rgba(255,74,184,.08)", font: "700 10px Segoe UI,Arial", letterSpacing: ".05em" });
    const addCollections = action("ADD TO COLLECTIONS", "#b89aff"); addCollections.dataset.bulkAddCollections = ""; addCollections.onclick = showBulkCollectionEditor;
    const moveHome = action("MOVE HOME", "#35d7ff"); moveHome.dataset.bulkMoveHome = ""; moveHome.onclick = () => showBulkComponentHomeEditor(currentComponentKind());
    const removeCollection = action("REMOVE FROM HOME", "#ff9b5f"); removeCollection.dataset.bulkRemoveCollection = ""; removeCollection.onclick = removeSelectedComponentsFromActiveCollection;
    const bulkDelete = action("DELETE", "#ff4ab8"); bulkDelete.dataset.bulkDelete = ""; bulkDelete.onclick = deleteSelectedRecipes;
    const bulkDeleteThumbs = action("DELETE THUMBNAILS", "#ff9b5f"); bulkDeleteThumbs.dataset.bulkDeleteThumbnails = ""; bulkDeleteThumbs.onclick = () => void deleteSelectedComponentThumbnails();
    const bulkRegenerateThumbs = action("REGENERATE THUMBNAILS", "#6ee7a2"); bulkRegenerateThumbs.dataset.bulkRegenerateThumbnails = ""; bulkRegenerateThumbs.onclick = regenerateSelectedComponentThumbnails;
    const bulkClear = action("CLEAR", "#8f8997"); bulkClear.dataset.bulkClear = ""; bulkClear.onclick = clearRecipeSelection;
    bulkControls.append(selectToggle, selectVisible, selectedCount, addCollections, moveHome, removeCollection, bulkDeleteThumbs, bulkRegenerateThumbs, bulkDelete, bulkClear); tools.append(bulkDivider, bulkControls, collectionTools);

    const status = document.createElement("span"); status.dataset.catalogStatus = ""; status.textContent = "Ready"; Object.assign(status.style, { marginLeft: "auto", color: "#85808d", font: "11px Segoe UI,Arial", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }); tools.append(status);
    const list = document.createElement("div"); list.dataset.recipes = ""; Object.assign(list.style, { flex: "1 1 auto", minHeight: "0", position: "relative", zIndex: "0", overflow: "auto", padding: "14px", display: "grid", gridAutoFlow: "row", gridAutoRows: "max-content", gridTemplateColumns: "repeat(auto-fill,minmax(230px,1fr))", gap: "12px", alignContent: "start", alignItems: "start" });
    list.style.setProperty("grid-auto-rows", "max-content", "important"); list.style.setProperty("align-items", "start", "important");
    const initialLoad = document.createElement("div"); initialLoad.textContent = "Opening Creative Library · checking canonical Prompt sources and reusable Ingredient index…"; Object.assign(initialLoad.style, { gridColumn: "1 / -1", padding: "48px 20px", textAlign: "center", color: "#b9b1c2", font: "11px/1.5 Segoe UI,Arial" }); list.append(initialLoad);
    panel.append(head, progress, tabs, viewDescription, outfitModeBar, tools, list); root.append(panel); document.body.append(root);
    root.addEventListener("pointerdown", e => { if (e.target === root) close(); });
    if (libraryLoadedOnce) {
        libraryBootstrapping = false;
        normalizeBuilderDraft();
        refreshLibraryChrome(); refreshOutfitModeBar(); renderCollectionControls(); renderBulkControls(); render();
        catalogProgress(); setCatalogRunButton(Boolean(catalogRun));
        void refreshLibraryIfStale();
    } else {
        libraryBootstrapping = true;
        refreshLibraryChrome(); refreshOutfitModeBar();
        catalogStatus(`Loading ${LIBRARY_VIEWS[activeView]?.label || "Library"}…`, LIBRARY_VIEWS[activeView]?.color || "#35d7ff");
        try {
            await load();
            libraryBootstrapping = false; refreshLibraryChrome(); catalogProgress(); setCatalogRunButton(Boolean(catalogRun));
        } catch (error) {
            libraryBootstrapping = false; refreshLibraryChrome(); catalogProgress(); setCatalogRunButton(Boolean(catalogRun));
            renderLibraryLoadError(error); catalogStatus(error?.message || "Creative Library load failed", "#ff78bd");
        }
    }
}

app.registerExtension({
    name: "SickOllie.SOS.RecipeLibrary",
    menuCommands: [{ path: ["Sick Ollie"], commands: ["solo.openRecipeCatalog"] }],
    commands: [{ id: "solo.openRecipeCatalog", label: "Open SOS Creative Library", icon: "pi pi-book", function: openRecipes }],
    async setup() {
        window.__soOpenCreativeLibrary = openRecipes;
        if (!window.__soCreativeLibraryOpenListener) {
            window.__soCreativeLibraryOpenListener = () => openRecipes();
            window.addEventListener("sickollie:open-creative-library", window.__soCreativeLibraryOpenListener);
        }
        registerSoloHubItem({ id: "recipes", label: "Creative Library", description: "Browse source-linked Templates and Prompts, visual Outfit Looks, reusable Wardrobe pieces, and Scenes in one portable Creative Library.", color: "#ff42bd", open: openRecipes });
        if (!window.__soPromptRecipeSaveListener) {
            window.__soPromptRecipeSaveListener = async event => {
                try { await saveCurrentStudioRecipe(event?.detail?.defaultName || "New saved prompt", { previewData: event?.detail?.previewData || null }); }
                catch (error) { alert(error.message || "Could not save the prompt and settings to Creative Library."); }
            };
            window.addEventListener("sickollie:save-studio-recipe", window.__soPromptRecipeSaveListener);
        }
        if (!window.__soRecipeCatalogPreviewListener) {
            window.__soRecipeCatalogPreviewListener = handleCatalogPreviewExecuted;
            window.addEventListener("sickollie:preview-executed", window.__soRecipeCatalogPreviewListener);
        }
        if (!window.__soRecipeCatalogExecutionErrorListener) {
            window.__soRecipeCatalogExecutionErrorListener = handleCatalogExecutionError;
            api.addEventListener?.("execution_error", window.__soRecipeCatalogExecutionErrorListener);
        }
    },
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "SOOutputBuilderSaveStudio") return;
        const originalMenu = nodeType.prototype.getExtraMenuOptions;
        nodeType.prototype.getExtraMenuOptions = function (_, options) {
            const result = originalMenu?.apply(this, arguments);
            options.unshift({ content: "📚 Open SOS Creative Library", callback: () => openRecipes() });
            return result;
        };
    },
});
export { openRecipes, saveCurrentStudioRecipe };
