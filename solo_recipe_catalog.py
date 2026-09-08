from __future__ import annotations

"""Local persistence API for reusable Studio recipes."""

import uuid
import csv
import copy
import json
import re
import hashlib
import zipfile
import tempfile
import threading
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .creative_library_paths import (
    CREATIVE_LIBRARY_LOG_FOLDER,
    LEGACY_RECIPE_LIBRARY_LOG_FOLDER,
    OUTFIT_MASTER_FILE,
    SAVED_RECIPE_COLLECTION_FOLDER,
    SAVED_RECIPE_MASTER_FILE,
    SCENE_MASTER_FILE,
    canonical_log_reference,
    creative_library_preview_directory,
    retire_legacy_generated_logs,
)
from .solo_catalog import get_catalog
from .wardrobe_color import canonicalize_wardrobe_value
from .image_metadata_compat import parse_json_parameters, generic_top_level_metadata

try:
    from aiohttp import web
    from server import PromptServer
except Exception:  # pragma: no cover
    web = None
    PromptServer = None


STUDIO_LOADER = "SOLoaderCoreEngineStudio"
STUDIO_PROMPT = "SOPromptLogEngineStudio"
STUDIO_GENERATION = "SOGenerationPipelineStudio"
STUDIO_OUTPUT = "SOOutputBuilderSaveStudio"
PORTABLE_PLACEHOLDER_ORDER = (
    "NAME", "OUTFIT", "OUTFIT_A", "OUTFIT_B", "OUTFIT_C", "BRAND", "SCENE", "LOCATION",
    "RARE_EVENT", "LIGHT_SOURCE", "ANALOG_CAPTURE_STYLE", "PRACTICAL_OUTER_LAYER",
    "SMALL_STYLING_DETAILS", "NATURAL_SURFACE", "TRIGGER",
)
TEMPLATE_PLACEHOLDER_ORDER = (
    "NAME", "OUTFIT", "OUTFIT_A", "OUTFIT_B", "OUTFIT_C", "BRAND", "ITEM", "SCENE",
)
TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(
        re.escape(token) for token in sorted((*PORTABLE_PLACEHOLDER_ORDER, "ITEM"), key=len, reverse=True)
    ) + r")(?![A-Za-z0-9_]|\s*:)"
)

PROMPT_RECIPE_FIELDS = {
    "prompt_source", "manual_prompt", "prompt_log_file", "prompt_mode", "prompt_index",
    *(name for letter in "ABC" for name in (
        f"outfit_token_{letter}", f"outfit_placement_{letter}", f"outfit_log_file_{letter}",
        f"outfit_mode_{letter}", f"outfit_index_{letter}",
    )),
    "scene_token", "scene_placement", "scene_log_file", "scene_mode", "scene_index",
    "name_token", "name_value", "item_token", "item_value",
    "prefix_enabled", "prefix_text", "suffix_enabled", "suffix_text",
}
GENERATION_RECIPE_FIELDS = {"resolution_mode", "custom_width", "custom_height", "seed_value"}
LOADER_RESOURCE_FIELDS = {
    "diffusion_model", "weight_dtype", "folder_name", "main_enabled", "main_lora", "main_strength",
    *(f"secondary_lora_{index}" for index in range(1, 11)),
}
GENERATION_RESOURCE_FIELDS = {"clip_name", "clip_type", "clip_device", "vae_name"}

RECIPE_PROMPT_LOG_FOLDER = CREATIVE_LIBRARY_LOG_FOLDER
RECIPE_PROMPT_MASTER_FILE = SAVED_RECIPE_MASTER_FILE
RECIPE_PROMPT_COLLECTION_FOLDER = SAVED_RECIPE_COLLECTION_FOLDER
CREATIVE_PROMPT_LOG_FOLDER = CREATIVE_LIBRARY_LOG_FOLDER
CREATIVE_PROMPT_MASTER_FILE = "MASTER - Ready Prompts.txt"
CREATIVE_PROMPT_COLLECTION_FOLDER = "Prompt Collections"
IMPORTED_PROMPT_LOG_FOLDER = "Imported Logs"
IMPORTED_COMPONENT_LOG_FOLDER = "Imported Logs"
RECIPE_COMPONENT_LOG_FOLDER = CREATIVE_LIBRARY_LOG_FOLDER
RECIPE_COMPONENT_COLLECTION_FOLDER = "Collections"
RECIPE_OUTFIT_MASTER_FILE = OUTFIT_MASTER_FILE
RECIPE_SCENE_MASTER_FILE = SCENE_MASTER_FILE
SCENE_TAXONOMY_VERSION = "scene-biomes-v1"
SCENE_TAXONOMY_META_KEY = "scene_taxonomy_version"
SCENE_TAXONOMY_MAP_META_KEY = "scene_taxonomy_id_map"

# Scene folders are deliberately based on the scene description itself rather
# than the source TXT filename.  The order is also the automatic classifier's
# tie-break priority, so visually specific biomes (Beach, Arctic, Desert) beat
# broad catch-alls such as Urban or Interiors when both appear in one line.
SCENE_TAXONOMY: tuple[dict[str, Any], ...] = (
    {"name": "Beach & Coast", "patterns": (r"\bbeach(?:es)?\b", r"\bcoast(?:al|line)?\b", r"\bshore(?:line)?\b", r"\boceanfront\b", r"\bseaside\b", r"\bsea\b", r"\blagoon\b"), "children": (
        ("Sandy Beach", (r"\bsand(?:y)?\b", r"\bbeach\b")),
        ("Rocky Coast & Cliffs", (r"\brocky coast\b", r"\bsea cliffs?\b", r"\bcoastal cliffs?\b")),
        ("Boardwalks & Piers", (r"\bboardwalk\b", r"\bpier\b", r"\bjetty\b", r"\bmarina\b")),
        ("Oceanfront & Shore", (r"\boceanfront\b", r"\bshore(?:line)?\b", r"\bseaside\b", r"\bcoast(?:al|line)?\b", r"\bsea\b", r"\blagoon\b")),
    )},
    {"name": "Arctic & Snow", "patterns": (r"\barctic\b", r"\btundra\b", r"\bsnow(?:y|field)?\b", r"\bice\b", r"\bglacier\b", r"\bfrozen\b", r"\bblizzard\b"), "children": (
        ("Snowfields & Tundra", (r"\btundra\b", r"\bsnowfield\b", r"\bsnowy field\b", r"\bopen snow\b")),
        ("Ice & Glaciers", (r"\bglacier\b", r"\bice cave\b", r"\bice field\b", r"\bfrozen lake\b", r"\biceberg\b")),
        ("Winter Settlements", (r"\bsnowy (?:town|village|street|cabin)\b", r"\bwinter (?:town|village|street|cabin)\b")),
    )},
    {"name": "Desert", "patterns": (r"\bdesert\b", r"\bdunes?\b", r"\bbadlands?\b", r"\barid\b", r"\bmesa\b", r"\bsalt flats?\b", r"\bdry basin\b"), "children": (
        ("Dunes & Open Desert", (r"\bdunes?\b", r"\bopen desert\b", r"\bsand sea\b")),
        ("Rocky Desert & Canyon", (r"\bbadlands?\b", r"\bmesa\b", r"\bdesert canyon\b", r"\brocky desert\b")),
        ("Desert Roads & Roadside", (r"\bdesert road\b", r"\bdesert highway\b", r"\broadside\b", r"\bgas station\b")),
        ("Salt Flats & Dry Basins", (r"\bsalt flats?\b", r"\bdry basin\b", r"\bplaya\b")),
    )},
    {"name": "Tropical", "patterns": (r"\btropical\b", r"\bjungle\b", r"\brainforest\b", r"\bpalm(?:s| tree)?\b", r"\bisland\b"), "children": (
        ("Jungle & Rainforest", (r"\bjungle\b", r"\brainforest\b", r"\bdense tropical\b")),
        ("Tropical Gardens", (r"\btropical garden\b", r"\bpalm garden\b", r"\blush tropical\b")),
        ("Island & Resort", (r"\bisland\b", r"\btropical resort\b", r"\bresort grounds\b")),
    )},
    {"name": "Forest & Woodland", "patterns": (r"\bforests?\b", r"\bwoods?\b", r"\bwoodland\b", r"\bgroves?\b", r"\borchards?\b", r"\btrees?\b"), "children": (
        ("Deep Forest", (r"\bdense forest\b", r"\bdeep forest\b", r"\bwoodland trail\b", r"\bforest path\b")),
        ("Clearings & Meadows", (r"\bclearing\b", r"\bmeadow\b", r"\bforest glade\b")),
        ("Autumn & Temperate Woods", (r"\bautumn (?:forest|woods?)\b", r"\bfall foliage\b", r"\btemperate forest\b")),
    )},
    {"name": "Mountains & Highlands", "patterns": (r"\bmountains?\b", r"\balpine\b", r"\bhighlands?\b", r"\bpeak\b", r"\bridgeline\b", r"\bcanyon\b", r"\bcliffs?\b"), "children": (
        ("Peaks & Ridges", (r"\bmountain peak\b", r"\bridgeline\b", r"\bsummit\b")),
        ("Canyons & Cliffs", (r"\bcanyons?\b", r"\bcliffs?\b", r"\bgorge\b")),
        ("Alpine & Highlands", (r"\balpine\b", r"\bhighlands?\b", r"\bmountain meadow\b")),
    )},
    {"name": "Water & Wetlands", "patterns": (r"\blakes?\b", r"\brivers?\b", r"\bcreeks?\b", r"\bponds?\b", r"\bpools?\b", r"\bwaterfalls?\b", r"\bwetlands?\b", r"\bswamps?\b", r"\bmarsh(?:es)?\b", r"\bcenotes?\b"), "children": (
        ("Lakes & Rivers", (r"\blake\b", r"\briver\b", r"\bcreek\b", r"\bpond\b")),
        ("Pools & Hot Springs", (r"\bpools?\b", r"\bhot springs?\b", r"\bspa pool\b", r"\bcenotes?\b")),
        ("Waterfalls & Wetlands", (r"\bwaterfall\b", r"\bwetlands?\b", r"\bswamp\b", r"\bmarsh\b")),
    )},
    {"name": "Rural & Grassland", "patterns": (r"\bfields?\b", r"\bprairie\b", r"\bgrassland\b", r"\bfarms?\b", r"\branch\b", r"\bbarns?\b", r"\bcountryside\b", r"\bcountry road\b", r"\bplantations?\b", r"\bvineyards?\b", r"\bpaddies\b", r"\bfarmland\b"), "children": (
        ("Fields & Prairie", (r"\bfields?\b", r"\bprairie\b", r"\bgrassland\b", r"\bwildflower meadow\b", r"\bpaddies\b")),
        ("Farms, Vineyards & Plantations", (r"\bfarms?\b", r"\branch\b", r"\bbarns?\b", r"\bpasture\b", r"\bplantations?\b", r"\bvineyards?\b", r"\bfarmland\b")),
        ("Country Roads", (r"\bcountry road\b", r"\brural road\b", r"\bbackroad\b")),
    )},
    {"name": "Parks & Gardens", "patterns": (r"\bparks?\b", r"\bgardens?\b", r"\bcourtyard\b", r"\bgreenhouse\b", r"\bplayground\b", r"\bblossoms?\b", r"\bflowers?\b", r"\bblooms?\b"), "children": (
        ("Gardens & Courtyards", (r"\bgarden\b", r"\bcourtyard\b")),
        ("Parks & Playgrounds", (r"\bpark\b", r"\bplayground\b")),
        ("Greenhouses & Conservatories", (r"\bgreenhouse\b", r"\bconservatory\b", r"\bglasshouse\b")),
        ("Floral Landscapes", (r"\bblossoms?\b", r"\bflowers?\b", r"\bblooms?\b", r"\bflowering\b")),
    )},
    {"name": "Urban", "patterns": (r"\burban\b", r"\bcity\b", r"\bdowntown\b", r"\bstreets?\b", r"\balleys?\b", r"\brooftops?\b", r"\bsubway\b", r"\bparking\b", r"\bstorefronts?\b", r"\bshops?\b"), "children": (
        ("Streets & Sidewalks", (r"\bstreet\b", r"\bsidewalk\b", r"\bcrosswalk\b", r"\bdowntown\b")),
        ("Alleys & Backstreets", (r"\balley\b", r"\bbackstreet\b", r"\bservice lane\b")),
        ("Rooftops & Skylines", (r"\brooftop\b", r"\bskyline\b", r"\bhigh-rise roof\b")),
        ("Transit & Infrastructure", (r"\bsubway\b", r"\bmetro\b", r"\bparking (?:garage|lot)\b", r"\boverpass\b", r"\bunderpass\b")),
        ("Commercial & Public", (r"\bstorefront\b", r"\bshop\b", r"\bmall\b", r"\bconvenience store\b", r"\blaundromat\b")),
    )},
    {"name": "Suburban & Residential", "patterns": (r"\bsuburb\b", r"\bresidential\b", r"\bbackyard\b", r"\bfront yard\b", r"\bporch\b", r"\bdriveway\b", r"\bneighborhood\b"), "children": (
        ("Backyards & Patios", (r"\bbackyard\b", r"\bpatio\b", r"\bdeck\b")),
        ("Porches & Driveways", (r"\bporch\b", r"\bdriveway\b", r"\bfront steps\b")),
        ("Neighborhoods", (r"\bneighborhood\b", r"\bresidential street\b", r"\bsuburb\b")),
    )},
    {"name": "Interiors", "patterns": (r"\bbedroom\b", r"\bbathroom\b", r"\bkitchen\b", r"\bdining room\b", r"\bliving room\b", r"\bapartment\b", r"\bhallway\b", r"\bcloset\b", r"\binterior\b"), "children": (
        ("Bedroom", (r"\bbedroom\b", r"\bbedside\b")),
        ("Bathroom", (r"\bbathroom\b", r"\bshower\b", r"\bbathtub\b")),
        ("Kitchen & Dining", (r"\bkitchen\b", r"\bdining room\b", r"\bdining table\b")),
        ("Living Space", (r"\bliving room\b", r"\blounge\b", r"\bapartment interior\b")),
        ("Hallway & Utility", (r"\bhallway\b", r"\bcloset\b", r"\blaundry room\b", r"\butility room\b")),
    )},
    {"name": "Studio & Stage", "patterns": (r"\bstudio\b", r"\bseamless\b", r"\bcyclorama\b", r"\bbackdrop\b", r"\bstage\b", r"\bphoto set\b"), "children": (
        ("Seamless Studio", (r"\bseamless\b", r"\bcyclorama\b", r"\bwhite studio\b", r"\bsolid color backdrop\b")),
        ("Editorial Set", (r"\beditorial set\b", r"\bphoto set\b", r"\bstudio set\b")),
        ("Stage & Backdrop", (r"\bstage\b", r"\bbackdrop\b", r"\btheatrical set\b")),
    )},
    {"name": "Hospitality & Travel", "patterns": (r"\bhotel\b", r"\bmotel\b", r"\bairport\b", r"\bterminal\b", r"\btrain\b", r"\bstation\b", r"\blobby\b"), "children": (
        ("Hotel & Motel", (r"\bhotel\b", r"\bmotel\b", r"\bhotel lobby\b")),
        ("Airport & Terminal", (r"\bairport\b", r"\bterminal\b", r"\bdeparture gate\b")),
        ("Station & Train", (r"\btrain\b", r"\bstation\b", r"\bplatform\b")),
    )},
    {"name": "Nightlife & Entertainment", "patterns": (r"\bnightclub\b", r"\bclub\b", r"\bbar\b", r"\bcasino\b", r"\barcade\b", r"\btheater\b", r"\bconcert\b", r"\bvenue\b"), "children": (
        ("Bar & Club", (r"\bbar\b", r"\bnightclub\b", r"\bclub interior\b")),
        ("Arcade & Casino", (r"\barcade\b", r"\bcasino\b")),
        ("Theater & Venue", (r"\btheater\b", r"\bconcert\b", r"\bvenue\b", r"\bauditorium\b")),
    )},
    {"name": "Industrial", "patterns": (r"\bwarehouse\b", r"\bfactory\b", r"\bworkshop\b", r"\bgarage\b", r"\bconstruction\b", r"\bindustrial\b", r"\bmachine shop\b", r"\bquarr(?:y|ies)\b", r"\bmines?\b"), "children": (
        ("Warehouse & Factory", (r"\bwarehouse\b", r"\bfactory\b", r"\bindustrial floor\b")),
        ("Workshop & Garage", (r"\bworkshop\b", r"\bgarage\b", r"\bmachine shop\b")),
        ("Construction & Utility", (r"\bconstruction\b", r"\butility tunnel\b", r"\bboiler room\b", r"\bquarr(?:y|ies)\b", r"\bmines?\b")),
    )},
    {"name": "Historic & Cultural", "patterns": (r"\btemples?\b", r"\bpagodas?\b", r"\bshrines?\b", r"\bmonaster(?:y|ies)\b", r"\bcathedrals?\b", r"\bruins?\b", r"\barchaeological\b", r"\bancient city\b", r"\bold town\b", r"\bhistoric village\b"), "children": (
        ("Temples & Sacred Sites", (r"\btemples?\b", r"\bpagodas?\b", r"\bshrines?\b", r"\bmonaster(?:y|ies)\b", r"\bcathedrals?\b")),
        ("Ruins & Archaeology", (r"\bruins?\b", r"\barchaeological\b", r"\bancient city\b")),
        ("Historic Towns & Villages", (r"\bold town\b", r"\bhistoric village\b", r"\bstone village\b")),
    )},
    {"name": "Fantasy & Futuristic", "patterns": (r"\bfantasy\b", r"\bcastle\b", r"\bdungeon\b", r"\bspaceship\b", r"\bspace station\b", r"\bfuturistic\b", r"\bcyberpunk\b", r"\bsurreal\b", r"\bdreamlike\b"), "children": (
        ("Fantasy", (r"\bfantasy\b", r"\bcastle\b", r"\bdungeon\b", r"\bmagical\b")),
        ("Sci-Fi & Futuristic", (r"\bspaceship\b", r"\bspace station\b", r"\bfuturistic\b", r"\bcyberpunk\b", r"\bsci[- ]fi\b")),
        ("Surreal & Dreamlike", (r"\bsurreal\b", r"\bdreamlike\b", r"\bimpossible landscape\b")),
    )},
)
CURATED_PROMPT_CORPUS_FOLDER = "Curated Library"
PROMPT_INDEX_VERSION = "prompt-curated-v3-all-placeholders-template"
FRAGMENT_MINER_VERSION = "fragment-miner-v2-atomic-ingredients"
PROMPT_IMPORT_LIMIT = 10_000
PROMPT_INDEX_EXCLUDED_FOLDERS = {"creative library", "recipe library", "fragments"}
FRAGMENT_ROLE_ORDER = {
    "prefix": 5,
    "identity_hook": 8,
    "subject": 10,
    "subject_structure": 11,
    "capture_medium": 15,
    "appearance": 16,
    "hair_makeup": 17,
    "concept": 20,
    "style": 30,
    "composition": 40,
    "pose_action": 50,
    "expression_mood": 55,
    "environment": 60,
    "body_styling": 62,
    "accessory": 64,
    "wardrobe_hook": 65,
    "scene_hook": 66,
    "brand_hook": 67,
    "lighting": 70,
    "time_atmosphere": 75,
    "camera": 80,
    "typography": 85,
    "color_effects": 90,
    "suffix": 95,
}
_PROMPT_INDEX_LOCK = threading.RLock()

STUDIO_WIDGETS = {
    STUDIO_LOADER: {
        "diffusion_model", "weight_dtype", "folder_name", "epoch_filter", "main_enabled", "main_lora",
        "main_strength", "include_subfolders", "loop_folder", "control_after_generate",
        "skip_none_during_cycle", "off_name", "auto_clean_name", "cleanup_rules",
        *(f"secondary_lora_{index}" for index in range(1, 11)),
    },
    STUDIO_PROMPT: {
        "prompt_source", "manual_prompt", "prompt_log_file", "prompt_mode", "prompt_index",
        *(name for letter in "ABC" for name in (
            f"outfit_token_{letter}", f"outfit_placement_{letter}", f"outfit_log_file_{letter}",
            f"outfit_mode_{letter}", f"outfit_index_{letter}",
        )),
        "scene_token", "scene_placement", "scene_log_file", "scene_mode", "scene_index",
        "name_token", "name_value", "item_token", "item_value", "prefix_enabled", "prefix_text",
        "suffix_enabled", "suffix_text", "prefix_suffix_separator", "cleanup_enabled", "cleanup_rules",
        "saved_prompt", "trigger_token", "trigger_placement", "trigger_override",
    },
    STUDIO_GENERATION: {
        "clip_name", "clip_type", "clip_device", "vae_name", "resolution_mode", "custom_width",
        "custom_height", "aspect_preset", "megapixels", "batch_size", "steps", "cfg",
        "sampler_name", "scheduler", "denoise", "shift", "seed_value",
    },
    STUDIO_OUTPUT: {
        "output_root", "subfolder_literal", "subfolder_var_1", "subfolder_var_2", "subfolder_var_3",
        "subfolder_var_4", "subfolder_delimiter", "filename_literal", "filename_var_1",
        "filename_var_2", "filename_var_3", "filename_var_4", "filename_var_5", "filename_var_6",
        "filename_delimiter", "extension", "quality", "counter_digits", "save_prompt_json",
        "save_workflow_json", "save_civitai_parameters",
    },
}


def _preview_directory() -> Path:
    return creative_library_preview_directory(get_catalog().path.parent)


def _component_preview_directory() -> Path:
    # Compatibility wrapper for older callers.  Every Creative Library card
    # now shares one physical thumbnail store and one serving contract.
    return _preview_directory()


def _single_line_recipe_prompt(value: Any) -> str:
    """Flatten one reusable recipe prompt to one Prompt Core log line."""
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _prompt_from_log_reference(relative_path: str, index_value: Any) -> str:
    """Resolve a fixed prompt-log reference when a legacy recipe has no snapshot."""
    value = canonical_log_reference(relative_path, "prompt")
    if not value or value in {"[None]", "None"}:
        return ""
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "prompts":
        return ""
    try:
        import folder_paths
        root = (Path(folder_paths.get_input_directory()) / "SickOllieLogs").resolve()
    except Exception:
        return ""
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return ""
    if not candidate.is_file():
        return ""
    text = ""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = candidate.read_text(encoding=encoding)
            break
        except Exception:
            continue
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    try:
        index = int(index_value) % len(lines)
    except Exception:
        index = 0
    return _single_line_recipe_prompt(lines[index])


def _recipe_prompt_text(recipe: dict[str, Any]) -> str:
    """Return the reusable source/template prompt represented by a recipe.

    Prefer the stored source template over the fully resolved prompt so NAME,
    OUTFIT, SCENE, and other placeholders remain useful when this generated
    master list is selected from Prompt Core.
    """
    payload = recipe.get("payload") if isinstance(recipe, dict) else None
    if not isinstance(payload, dict):
        return ""
    values = _recipe_node_values(payload, STUDIO_PROMPT, include_optional=True)
    manual = _single_line_recipe_prompt(values.get("manual_prompt"))
    if manual:
        return manual
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    template = _single_line_recipe_prompt(summary.get("prompt_template"))
    if template:
        return template
    saved = _single_line_recipe_prompt(values.get("saved_prompt"))
    if saved:
        return saved
    referenced = _prompt_from_log_reference(values.get("prompt_log_file", ""), values.get("prompt_index", 0))
    if referenced:
        return referenced
    return _single_line_recipe_prompt(summary.get("resolved_prompt"))


def _has_swappable_component_placeholder(text: Any) -> bool:
    signature = set(_template_placeholder_signature(text).split("+"))
    return bool(signature.intersection({"OUTFIT", "OUTFIT_B", "OUTFIT_C", "SCENE"}))


def _replace_portable_identity_values(text: str, placeholders: list[dict[str, Any]]) -> str:
    """Restore portable NAME/BRAND hooks inside an otherwise resolved prompt.

    Outfit and scene values intentionally stay resolved for Prompt assets.  Only
    identity / brand substitutions are abstracted back to portable tokens.
    """
    result = str(text or "")
    replacements: list[tuple[str, str]] = []
    for item in placeholders or []:
        if not isinstance(item, dict):
            continue
        token = str(item.get("token") or "").strip().upper()
        value = _single_line_recipe_prompt(item.get("value"))
        widget = str(item.get("widget") or "")
        if not value:
            continue
        if token == "NAME" or widget == "name_value":
            replacements.append((value, "NAME"))
        elif token in {"BRAND", "ITEM"} or widget == "item_value":
            replacements.append((value, "BRAND"))
    # Longest first prevents a short brand/name from partially replacing a
    # longer phrase that contains it. Explicit identifier boundaries keep short
    # values from replacing fragments of ordinary words, while allowing punctuation.
    for value, token in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        result = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(value) + r"(?![A-Za-z0-9_])", lambda match: token, result, flags=re.IGNORECASE)
    return _single_line_recipe_prompt(result)


def _portable_resolved_prompt(
    source: str, resolved: str, placeholders: list[dict[str, Any]] | None = None,
) -> str:
    """Keep a thumbnail's component choices without ever flattening identity.

    Resolved OUTFIT/SCENE text is useful, but a resolved NAME or BRAND is not a
    reusable Library asset. Structured placeholder values are restored first;
    if an identity hook from the source is still missing, the resolved variant
    is withheld completely instead of risking a baked identity.
    """
    clean_source = _single_line_recipe_prompt(source)
    clean_resolved = _single_line_recipe_prompt(resolved)
    if not clean_resolved:
        return ""
    portable = _replace_portable_identity_values(clean_resolved, placeholders or [])
    source_tokens = {token.upper() for token in TOKEN_PATTERN.findall(clean_source)}
    portable_tokens = {token.upper() for token in TOKEN_PATTERN.findall(portable)}
    if "NAME" in source_tokens and "NAME" not in portable_tokens:
        return ""
    if source_tokens.intersection({"BRAND", "ITEM"}) and not portable_tokens.intersection({"BRAND", "ITEM"}):
        return ""
    if portable.casefold() == clean_source.casefold():
        return ""
    return portable


def _recipe_prompt_variants(recipe: dict[str, Any]) -> tuple[str, str]:
    payload = recipe.get("payload") if isinstance(recipe, dict) else None
    if not isinstance(payload, dict):
        return "", ""
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    placeholders = summary.get("placeholders") if isinstance(summary.get("placeholders"), list) else []
    source = _replace_portable_identity_values(_recipe_prompt_text(recipe), placeholders)
    resolved = _portable_resolved_prompt(source, summary.get("resolved_prompt"), placeholders)
    return source, resolved


def _payload_prompt_variants(
    payload: dict[str, Any], fallback_source: str = "", *,
    canonical_source: str = "", identity_placeholders: list[dict[str, Any]] | None = None,
) -> tuple[str, str]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    placeholders = summary.get("placeholders") if isinstance(summary.get("placeholders"), list) else []
    if canonical_source:
        # Yearbook pre-resolves temporary identity text before Prompt Core runs.
        # Its connected Loader metadata therefore cannot describe those substitutions.
        placeholders = [row for row in placeholders if isinstance(row, dict) and str(row.get("token") or "").upper() not in {"NAME", "ITEM", "BRAND"} and str(row.get("widget") or "") not in {"name_value", "item_value"}]
        placeholders.extend(identity_placeholders or [])
        source = _single_line_recipe_prompt(canonical_source)
    else:
        source = _replace_portable_identity_values(
            _single_line_recipe_prompt(summary.get("prompt_template")) or _single_line_recipe_prompt(fallback_source),
            placeholders,
        )
    return source, _portable_resolved_prompt(source, summary.get("resolved_prompt"), placeholders)


def _payload_prompt_preview_metadata(payload: dict[str, Any]) -> dict[str, str]:
    """Keep the exact Outfit/Scene platter values embedded in a preview image."""
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    placeholders = summary.get("placeholders") if isinstance(summary.get("placeholders"), list) else []
    output: dict[str, str] = {}
    for row in placeholders:
        if not isinstance(row, dict):
            continue
        token = str(row.get("token") or "").strip().strip("{}").upper()
        widget = str(row.get("widget") or "").strip().lower()
        value = _single_line_recipe_prompt(row.get("value"))
        if not value:
            continue
        if token == "SCENE" or widget.startswith("scene_"):
            output.setdefault("scene", value)
        elif token == "OUTFIT_B" or "outfit_b" in widget:
            output.setdefault("outfit_b", value)
        elif token == "OUTFIT_C" or "outfit_c" in widget:
            output.setdefault("outfit_c", value)
        elif token in {"OUTFIT", "OUTFIT_A"} or "outfit_a" in widget:
            output.setdefault("outfit_a", value)
    return output


def _recipe_is_template(recipe: dict[str, Any]) -> bool:
    """A Template is any reusable formula that still contains a placeholder."""
    return _creative_library_is_template_text(_recipe_prompt_variants(recipe)[0])


def _recipe_portable_prompt_text(recipe: dict[str, Any]) -> str:
    """Return a ready-to-render Prompt asset derived from a saved record.

    Placeholder-bearing source text always belongs in Templates. A second
    Prompt record is emitted only when the thumbnail's resolved form is fully
    token-free after NAME/BRAND identity protection. This gives OUTFIT/SCENE
    formulas a useful resolved twin without ever baking a person or brand into
    the Prompt catalog.
    """
    payload = recipe.get("payload") if isinstance(recipe, dict) else None
    if not isinstance(payload, dict):
        return ""
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    placeholders = summary.get("placeholders") if isinstance(summary.get("placeholders"), list) else []
    source = _replace_portable_identity_values(_recipe_prompt_text(recipe), placeholders)
    resolved = _single_line_recipe_prompt(summary.get("resolved_prompt"))
    if _creative_library_is_template_text(source):
        candidate = _portable_resolved_prompt(source, resolved, placeholders)
    else:
        candidate = source or _replace_portable_identity_values(resolved, placeholders)
    return "" if _creative_library_is_template_text(candidate) else candidate


def _set_recipe_prompt_text(recipe: dict[str, Any], kind: str, value: str) -> dict[str, Any]:
    payload = dict(recipe.get("payload") if isinstance(recipe.get("payload"), dict) else {})
    nodes = list(payload.get("nodes") or [])
    clean_value = _single_line_recipe_prompt(value)
    if not clean_value:
        raise ValueError("Prompt text is required")
    prompt_nodes = [node for node in nodes if isinstance(node, dict) and str(node.get("type") or "") == STUDIO_PROMPT]
    if not prompt_nodes:
        raise ValueError("This saved record no longer has an editable Studio Prompt Core")
    prompt_node = prompt_nodes[0]
    widgets = prompt_node.get("widgets") if isinstance(prompt_node.get("widgets"), list) else []
    widget_names = {str((widget or {}).get("name") or ""): widget for widget in widgets if isinstance(widget, dict)}
    def set_widget(name: str, widget_value: Any) -> None:
        widget = widget_names.get(name)
        if widget is not None:
            widget["value"] = widget_value
            return
        widgets.append({"name": name, "value": widget_value})
        widget_names[name] = widgets[-1]
    summary = dict(payload.get("summary") if isinstance(payload.get("summary"), dict) else {})
    source_text = _recipe_prompt_text(recipe)
    if kind == "template":
        set_widget("prompt_source", "manual")
        set_widget("manual_prompt", clean_value)
        summary["prompt_template"] = clean_value
    else:
        if _has_swappable_component_placeholder(source_text) and _creative_library_is_template_text(source_text):
            summary["resolved_prompt"] = clean_value
        else:
            set_widget("prompt_source", "manual")
            set_widget("manual_prompt", clean_value)
            summary["prompt_template"] = clean_value
            summary["resolved_prompt"] = clean_value
    prompt_node["widgets"] = widgets
    payload["nodes"] = nodes
    payload["summary"] = summary
    updated = dict(recipe)
    updated["payload"] = payload
    return updated


def _placeholder_signature(value: Any) -> str:
    tokens = {str(match).upper() for match in TOKEN_PATTERN.findall(str(value or ""))}
    # OUTFIT_A is the portable base outfit slot.  B/C and ITEM are meaningful
    # distinct slots, so do not collapse them into OUTFIT or BRAND here.
    normalized = {"OUTFIT" if token == "OUTFIT_A" else token for token in tokens}
    order = tuple(dict.fromkeys((
        "NAME", "OUTFIT", "OUTFIT_B", "OUTFIT_C", "BRAND", "ITEM", "SCENE",
        *("OUTFIT" if token == "OUTFIT_A" else token for token in PORTABLE_PLACEHOLDER_ORDER),
    )))
    return "+".join(token for token in order if token in normalized)


def _template_placeholder_signature(value: Any) -> str:
    """Return every exact portable placeholder recognized by Creative Library."""
    return _placeholder_signature(value)


def _creative_library_is_template_text(value: Any) -> bool:
    """Every exact placeholder-bearing formula belongs in Templates."""
    return bool(_template_placeholder_signature(value))


def _builder_ready_signature(signature: Any) -> bool:
    tokens = {token for token in str(signature or "").upper().split("+") if token}
    return bool(tokens)


def _component_ready_signature(signature: Any) -> bool:
    tokens = {token for token in str(signature or "").upper().split("+") if token}
    return bool(tokens & {"OUTFIT", "SCENE"})


def _prompt_corpus_root(prompt_root: Path | str | None = None) -> Path | None:
    if prompt_root is not None:
        return Path(prompt_root)
    candidates: list[Path] = []
    try:
        import folder_paths
        candidates.append(Path(folder_paths.get_input_directory()) / "SickOllieLogs" / "prompts" / CURATED_PROMPT_CORPUS_FOLDER)
    except Exception:
        pass
    for candidate in candidates:
        if (
            (candidate / "Manifests" / "catalog.csv").is_file()
            or (candidate / "Prompts").is_dir()
            or (candidate / "Templates").is_dir()
        ):
            return candidate
    return None


def _read_prompt_source(path: Path) -> list[str]:
    text = ""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
        except OSError:
            return []
    return [_single_line_recipe_prompt(line) for line in text.splitlines() if line.strip()]


def _prompt_source_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    manifest_files = [
        root / "Manifests" / "catalog.csv",
        root / "Manifests" / "provenance.jsonl",
        root / "Manifests" / "validation.json",
    ]
    if manifest_files[0].is_file():
        return [path for path in manifest_files if path.is_file()]
    output: list[Path] = []
    for path in root.rglob("*.txt"):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part.casefold() in PROMPT_INDEX_EXCLUDED_FOLDERS for part in relative.parts[:-1]):
            continue
        if path.is_file():
            output.append(path)
    return sorted(output, key=lambda item: str(item).casefold())


def _file_set_signature(root: Path, files: list[Path], version: str) -> str:
    digest = hashlib.sha256(str(version or "").encode("utf-8"))
    for path in files:
        try:
            stat = path.stat()
            relative = str(path.relative_to(root)).replace("\\", "/")
        except (OSError, ValueError):
            continue
        digest.update(f"\0{relative}\0{stat.st_size}\0{stat.st_mtime_ns}".encode("utf-8"))
    return digest.hexdigest()


def _prompt_source_home(root: Path, path: Path) -> tuple[str, str, str, bool]:
    """Derive one editable gallery home from the curated source tree.

    ``Prompts`` and ``Templates`` remain source-location hints, while the live
    Creative Library tab is derived from the prompt text: NAME/BRAND/ITEM make
    a Template; OUTFIT/SCENE alone remain Prompts. The next folder is the
    category. A nested folder becomes the subcategory; a file directly inside
    a category uses its stem as the subcategory. Source files remain untouched.
    """
    try:
        relative = path.relative_to(root)
    except ValueError:
        return "prompt", "Other", "General", False
    parts = relative.parts
    root_name = str(parts[0] if parts else "").casefold()
    explicit = root_name in {"prompts", "templates"}
    kind = "template" if root_name == "templates" else "prompt"
    if not explicit:
        return kind, "Other", "General", False
    parent = _single_line_recipe_prompt(parts[1] if len(parts) >= 3 else "Other") or "Other"
    subcategory = _single_line_recipe_prompt(parts[2] if len(parts) >= 4 else path.stem) or "General"
    return kind, parent, subcategory, True


def _build_prompt_corpus_index(root: Path, files: list[Path] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Build a lean canonical index without modifying any source log."""
    manifest_path = root / "Manifests" / "catalog.csv"
    if manifest_path.is_file():
        provenance_by_representative: dict[str, list[dict[str, Any]]] = defaultdict(list)
        provenance_path = root / "Manifests" / "provenance.jsonl"
        if provenance_path.is_file():
            with provenance_path.open("r", encoding="utf-8") as stream:
                for raw in stream:
                    try:
                        item = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    representative_id = str(item.get("representative_id") or item.get("record_id") or "").strip()
                    source_path = str(item.get("source_file") or "").replace("\\", "/").strip()
                    if not representative_id or not source_path:
                        continue
                    provenance_by_representative[representative_id].append({
                        "source_path": source_path,
                        "line_number": max(0, int(item.get("source_line") or 0)),
                        "source_label": "",
                    })

        def values(raw: Any) -> list[str]:
            return [part.strip() for part in str(raw or "").split("|") if part.strip()]

        assets: list[dict[str, Any]] = []
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                prompt_id = str(row.get("record_id") or "").strip()
                text = _single_line_recipe_prompt(row.get("text"))
                if not prompt_id or not text or re.search(r"\bchild\b", text, re.IGNORECASE):
                    continue
                parent = _single_line_recipe_prompt(row.get("primary_parent") or "Other") or "Other"
                subcategory = _single_line_recipe_prompt(row.get("primary_subcategory") or "General") or "General"
                sources = provenance_by_representative.get(prompt_id, [])
                for source in sources:
                    source["source_label"] = f"{parent} / {subcategory}"
                facets = {
                    "parent": [parent],
                    "subcategory": [subcategory],
                    "style": values(row.get("styles")),
                    "cast": values(row.get("cast")),
                    "content": values(row.get("content")),
                    "time": values(row.get("time")),
                    "shot": values(row.get("shot")),
                    # Compatibility alias for older UI/tests; it is metadata,
                    # never a second navigation home.
                    "structure": values(row.get("shot")),
                }
                try:
                    quality_score = float(row.get("quality_score") or 0)
                except (TypeError, ValueError):
                    quality_score = 0.0
                try:
                    exact_occurrences = max(0, int(row.get("exact_source_occurrences") or 0))
                except (TypeError, ValueError):
                    exact_occurrences = 0
                derived_kind = "template" if _creative_library_is_template_text(text) else "prompt"
                assets.append({
                    "prompt_id": prompt_id,
                    "kind": derived_kind,
                    "value": text,
                    "placeholder_signature": _placeholder_signature(text),
                    "primary_parent": parent,
                    "primary_subcategory": subcategory,
                    "facets": facets,
                    "quality_score": quality_score,
                    "exact_source_occurrences": exact_occurrences,
                    "near_cluster_id": str(row.get("near_cluster_id") or ""),
                    "source_count": len(sources) or exact_occurrences,
                    "sources": sources,
                })
        file_rows = []
        for path in _prompt_source_files(root):
            stat = path.stat()
            with path.open("r", encoding="utf-8", errors="replace") as source_stream:
                line_count = sum(1 for _ in source_stream)
            file_rows.append({
                "source_path": str(path.relative_to(root)).replace("\\", "/"),
                "byte_size": int(stat.st_size),
                "modified_ns": int(stat.st_mtime_ns),
                "line_count": line_count,
            })
        return assets, file_rows

    selected = list(files if files is not None else _prompt_source_files(root))
    by_text: dict[str, dict[str, Any]] = {}
    file_rows: list[dict[str, Any]] = []
    for path in selected:
        try:
            relative = str(path.relative_to(root)).replace("\\", "/")
            stat = path.stat()
        except (OSError, ValueError):
            continue
        lines = _read_prompt_source(path)
        source_kind, source_parent, source_subcategory, explicit_kind = _prompt_source_home(root, path)
        file_rows.append({
            "source_path": relative,
            "byte_size": int(stat.st_size),
            "modified_ns": int(stat.st_mtime_ns),
            "line_count": len(lines),
        })
        for line_number, value in enumerate(lines, 1):
            key = value.casefold()
            if not key:
                continue
            item = by_text.get(key)
            if item is None:
                derived_kind = "template" if _creative_library_is_template_text(value) else "prompt"
                prompt_id = f"curated-{derived_kind}:{hashlib.sha1(key.encode('utf-8')).hexdigest()}" if explicit_kind else f"corpus-{derived_kind}:{hashlib.sha1(key.encode('utf-8')).hexdigest()}"
                item = {
                    "prompt_id": prompt_id,
                    "kind": derived_kind,
                    "value": value,
                    "placeholder_signature": _placeholder_signature(value),
                    "primary_parent": source_parent,
                    "primary_subcategory": source_subcategory,
                    "sources": [],
                }
                by_text[key] = item
            item["sources"].append({
                "source_path": relative,
                "line_number": line_number,
                "source_label": path.stem,
            })
    assets = list(by_text.values())
    for item in assets:
        item["facets"] = _prompt_facets(item["value"], item.get("sources") or [])
        item["facets"]["parent"] = [str(item.get("primary_parent") or "Other")]
        item["facets"]["subcategory"] = [str(item.get("primary_subcategory") or "General")]
        item["source_count"] = len(item.get("sources") or [])
        item["exact_source_occurrences"] = len(item.get("sources") or [])
    return assets, file_rows


def _ensure_prompt_corpus_index(prompt_root: Path | str | None = None, *, force: bool = False) -> dict[str, Any]:
    """Refresh the prompt index only when source-file metadata changes."""
    root = _prompt_corpus_root(prompt_root)
    if root is None or not root.is_dir():
        return {"ok": True, "indexed": False, "reason": "source-folder-unavailable"}
    with _PROMPT_INDEX_LOCK:
        files = _prompt_source_files(root)
        if not files:
            return {"ok": True, "indexed": False, "reason": "no-source-files"}
        signature = _file_set_signature(root, files, PROMPT_INDEX_VERSION)
        catalog = get_catalog()
        if not force and catalog.metadata_value("prompt_index_signature") == signature:
            return {"ok": True, "indexed": False, "signature": signature}
        assets, file_rows = _build_prompt_corpus_index(root, files)
        result = catalog.replace_prompt_index(assets, file_rows, signature=signature)
        return {"ok": True, "indexed": True, "signature": signature, **result}


_FRAGMENT_ROLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "lighting": re.compile(r"\b(?:light(?:ing)?|lit|flash|neon|blacklight|glow|backlit|rim light|sunlight|moonlight|shadow|exposure|chiaroscuro|strobe|fluorescent|tungsten|golden hour)\b", re.IGNORECASE),
    "time_atmosphere": re.compile(r"\b(?:night|midnight|dawn|dusk|sunset|sunrise|haze|fog|mist|rain|humid|atmosphere|storm|smoke|dreamy|overcast)\b", re.IGNORECASE),
    "camera": re.compile(r"\b(?:camera|lens|\d{2,3}mm|f/\d|35mm|film grain|point[- ]and[- ]shoot|disposable|polaroid|analog|depth of field|bokeh|motion blur|shutter|iso|aperture|photograph|photo)\b", re.IGNORECASE),
    "composition": re.compile(r"\b(?:close[- ]?up|full[- ]?body|headshot|portrait|wide shot|medium shot|low angle|high angle|overhead|bird.?s eye|worm.?s eye|profile|side view|centered|symmetr\w*|framing|frame|foreground|background|composition|layout|crop|perspective|three-quarter|eye level)\b", re.IGNORECASE),
    "pose_action": re.compile(r"\b(?:kneel|sit|stand|walk|run|lean|lie|lying|crouch|recline|reach|hold|look|gaze|turn|pose|dance|jump|bend|arch|hug|embrac|climb|resting|grip|press)\w*\b", re.IGNORECASE),
    "expression_mood": re.compile(r"\b(?:smile|smirk|grin|laugh|expression|playful|coy|shy|wistful|confident|fierce|calm|serene|mood|melanchol|sultry|surpris|joy|tender|intense|dreamy)\w*\b", re.IGNORECASE),
    "typography": re.compile(r"\b(?:typography|text|lettering|masthead|headline|caption|logo|wordmark|font|poster|magazine cover|editorial layout|label|stencil(?:ed)?|signage|microtype|typeset|written|spelled)\b", re.IGNORECASE),
    "color_effects": re.compile(r"\b(?:palette|color|colour|neon|cmyk|halftone|chromatic|glitch|grain|vignette|bloom|marbled|psychedelic|gradient|duotone|saturated|monochrome|black and white|iridescent|holographic)\b", re.IGNORECASE),
    "environment": re.compile(r"\b(?:studio|bedroom|bathroom|kitchen|living room|hotel|motel|apartment|street|city|alley|subway|parking lot|rooftop|forest|woods|meadow|garden|field|mountain|desert|beach|ocean|pool|lake|river|shore|car|train|airport|highway|nightclub|bar|environment|scene|backdrop|room)\b", re.IGNORECASE),
    "style": re.compile(r"\b(?:editorial|fashion|cinematic|analog|photoreal|realistic|illustration|vector|screenprint|surreal|minimal|documentary|commercial|fine art|vintage|retro|y2k|vaporwave|gothic|bohemian|candid|snapshot|campaign|lookbook)\b", re.IGNORECASE),
    "accessory": re.compile(r"\b(?:headband|hair clip|barrette|bow|hat|cap|beanie|glasses|sunglasses|earrings?|necklace|choker|bracelet|ring|belt|scarf|gloves?|handbag|purse|backpack)\b", re.IGNORECASE),
    "hair_makeup": re.compile(r"\b(?:hair|hairstyle|bangs|braids?|ponytail|pigtails?|bun|bob cut|makeup|eyeliner|lipstick|mascara|eye shadow|nail polish|manicure)\b", re.IGNORECASE),
    "body_styling": re.compile(r"\b(?:nude|naked|bare|topless|bottomless|oiled|glossy skin|wet skin|body paint|painted skin|glittered skin|tattooed|freckled)\b", re.IGNORECASE),
    "appearance": re.compile(r"\b(?:tall|short|petite|slim|thin|curvy|plus[- ]size|obese|muscular|athletic|stocky|lanky|mature|elderly|middle[- ]aged)\b", re.IGNORECASE),
}
_FRAGMENT_ROLE_WEIGHTS = {
    "typography": 4.0,
    "camera": 3.5,
    "lighting": 3.4,
    "composition": 3.2,
    "pose_action": 2.8,
    "expression_mood": 2.7,
    "time_atmosphere": 2.5,
    "environment": 2.4,
    "color_effects": 2.3,
    "style": 2.0,
    "accessory": 3.0,
    "hair_makeup": 2.9,
    "body_styling": 2.9,
    "appearance": 2.2,
}
_FRAGMENT_CLAUSE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\s*;\s*|,\s+(?=(?:and\s+)?[A-Za-z0-9])")
_FRAGMENT_LOW_VALUE = re.compile(r"^(?:high quality|best quality|masterpiece|highly detailed|ultra detailed|award winning)[.!]?$", re.IGNORECASE)
_SUBJECT_PHRASE_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:an?\s+)?((?:(?:young adult|young|adult|mature|elderly|older|middle[- ]aged|obese|plus[- ]size|petite|slim|thin|curvy|muscular|athletic|stocky|lanky)\s+){0,3}(?:woman|man|female subject|male subject|person)|(?:young|adult|mature|elderly|older)\s+couple|couple|two women|two men|group of (?:women|men|friends|people))\b",
    re.IGNORECASE,
)
_SUBJECT_WRAPPER_PATTERN = re.compile(
    r"^(?:(?:an?|the)\s+)?(?:photo(?:graph)?|portrait|image|shot)\s+of\s+(?:(?:an?|the)\s+)?(?:(?-i:NAME)|(?:(?:young adult|young|adult|mature|elderly|older|middle[- ]aged|obese|plus[- ]size|petite|slim|thin|curvy|muscular|athletic|stocky|lanky)\s+){0,3}(?:woman|man|female subject|male subject|person))\b[,:-]?\s*",
    re.IGNORECASE,
)


def _normalize_subject_label(value: str) -> str:
    text = re.sub(r"^(?:an?|the)\s+", "", _single_line_recipe_prompt(value), flags=re.IGNORECASE)
    text = re.sub(r"\bfemale subject\b", "woman", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmale subject\b", "man", text, flags=re.IGNORECASE)
    return text.casefold()


def _atomic_subject_ingredients(value: str) -> list[str]:
    output: list[str] = []
    for match in _SUBJECT_PHRASE_PATTERN.finditer(value):
        label = _normalize_subject_label(match.group(1))
        if label and label not in output:
            output.append(label)
    return output


def _strip_subject_wrapper(value: str) -> str:
    """Remove non-creative scaffolding while keeping the authored modifier."""
    stripped = _SUBJECT_WRAPPER_PATTERN.sub("", _single_line_recipe_prompt(value), count=1).strip(" ,;:-")
    if stripped.casefold() == _single_line_recipe_prompt(value).casefold():
        return _single_line_recipe_prompt(value)
    stripped = re.sub(r"^(?:and\s+)?(?=fully\b|wearing\b|with\b|in\b|under\b|against\b|while\b)", "", stripped, flags=re.IGNORECASE)
    return stripped.strip(" ,;:-")


def _fragment_role(value: str) -> str:
    token_matches = {str(token).upper() for token in TOKEN_PATTERN.findall(value)}
    if "SCENE" in token_matches:
        return "scene_hook"
    if any(token.startswith("OUTFIT") for token in token_matches):
        return "wardrobe_hook"
    if token_matches & {"BRAND", "ITEM"}:
        return "brand_hook"
    if _single_line_recipe_prompt(value) == "NAME":
        return "identity_hook"
    if _SUBJECT_PHRASE_PATTERN.fullmatch(_single_line_recipe_prompt(value)):
        return "subject"
    if re.fullmatch(r"(?:photo(?:graph)?|portrait|image|shot|phone photo|point[- ]and[- ]shoot photograph)", value, re.IGNORECASE):
        return "capture_medium"
    if re.search(r"\b(?:flash|lighting|light|lit|blacklight|backlit|rim light|sunlight|moonlight|strobe|fluorescent|tungsten)\b", value, re.IGNORECASE) and not re.search(r"\b(?:lens|\d{2,3}mm|f/\d|aperture|shutter|iso)\b", value, re.IGNORECASE):
        return "lighting"
    scored: list[tuple[float, int, str]] = []
    for role, pattern in _FRAGMENT_ROLE_PATTERNS.items():
        count = len(pattern.findall(value))
        if count:
            scored.append((count * _FRAGMENT_ROLE_WEIGHTS[role], -FRAGMENT_ROLE_ORDER.get(role, 50), role))
    return max(scored)[2] if scored else ""


def _neutralize_subject_fragment(value: str) -> str:
    """Legacy compatibility hook; subject vocabulary now stays semantic."""
    return _single_line_recipe_prompt(value)


def _fragment_family_id(role: str, value: str) -> str:
    normalized = TOKEN_PATTERN.sub("TOKEN", value.casefold())
    normalized = re.sub(r"\b(?:a|an|the|very|really)\b", " ", normalized)
    normalized = re.sub(r"\d+(?:\.\d+)?", "#", normalized)
    normalized = re.sub(r"[^a-z#]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return f"fragment-family:{role}:{hashlib.sha1(normalized.encode('utf-8')).hexdigest()}"


def _fragment_join_mode(role: str, value: str) -> str:
    if role in {"prefix", "suffix", "concept"}:
        return role
    if re.match(r"^(?:with|featuring|wearing|in|under|against|while|as)\b", value, re.IGNORECASE):
        return "with-clause"
    return "sentence"


def _fragment_confidence(prompt_count: int, source_count: int, *, curated: bool = False) -> float:
    if curated:
        return 1.0
    if prompt_count >= 100:
        base = 0.99
    elif prompt_count >= 50:
        base = 0.96
    elif prompt_count >= 20:
        base = 0.92
    elif prompt_count >= 10:
        base = 0.88
    elif prompt_count >= 5:
        base = 0.82
    else:
        base = 0.76
    return round(min(0.995, base + (0.025 if source_count >= 3 else 0.01 if source_count >= 2 else 0)), 3)


def _source_theme_label(source_path: str) -> str:
    stem = Path(str(source_path or "")).stem.replace("_", " ").replace("—", " - ")
    stem = re.sub(r"\b(?:token free|outfit master|name only|prompt logs?|prompts?|master|standard|templates?|ready|cleaned|variant(?: \d+)?|one per line|identity neutral|comfy|values|full prompts?|with subjects|original|test)\b", " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\b\d+\b", " ", stem)
    stem = re.sub(r"\s*-\s*", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" ._-")
    if not stem or len(stem) > 72 or stem.casefold() in {"all", "untitled", "misc", "needs review"}:
        return ""
    return stem


def _mine_prompt_fragments(prompts: list[dict[str, Any]], prompt_root: Path | None = None) -> list[dict[str, Any]]:
    """Mine recurring authored clauses and source themes from live Prompt data.

    The miner never rewrites a Prompt. It keeps exact clause wording and links
    every candidate back to prompt IDs and source logs for inspection.
    """
    clause_rows: dict[str, dict[str, Any]] = {}
    source_prompt_ids: dict[str, set[str]] = defaultdict(set)
    home_prompt_ids: dict[tuple[str, str], set[str]] = defaultdict(set)

    def collect(value: str, prompt_id: str, source_paths: set[str], *, role_hint: str = "", source_kind: str = "mined-clause") -> None:
        clean_value = _single_line_recipe_prompt(value).strip(" ,;")
        key = re.sub(r"[^a-z0-9]+", " ", clean_value.casefold()).strip()
        if not key:
            return
        item = clause_rows.setdefault(key, {
            "value": clean_value, "prompt_ids": set(), "source_paths": set(),
            "role_hint": role_hint, "source_kind": source_kind,
        })
        item["prompt_ids"].add(prompt_id)
        item["source_paths"].update(source_paths)
        if role_hint:
            item["role_hint"] = role_hint
        if source_kind != "mined-clause":
            item["source_kind"] = source_kind

    for prompt in prompts:
        prompt_id = str(prompt.get("prompt_id") or "")
        text = _single_line_recipe_prompt(prompt.get("value"))
        if not prompt_id or not text:
            continue
        source_paths = {
            str((source or {}).get("source_path") or "").replace("\\", "/")
            for source in prompt.get("sources") or [] if str((source or {}).get("source_path") or "")
        }
        parent = _single_line_recipe_prompt(prompt.get("primary_parent"))
        subcategory = _single_line_recipe_prompt(prompt.get("primary_subcategory"))
        has_manifest_home = prompt_id.startswith(("NP-", "NT-")) or (parent and parent != "Other")
        if has_manifest_home:
            home_prompt_ids[(parent, subcategory or "General")].add(prompt_id)
        else:
            # Legacy explicit test roots retain their filename-derived themes.
            # Canonical manifest records use taxonomy homes instead, so source
            # filenames can never leak back into navigation or ingredients.
            for source_path in source_paths:
                source_prompt_ids[source_path].add(prompt_id)

        for subject in _atomic_subject_ingredients(text):
            collect(subject, prompt_id, source_paths, role_hint="subject", source_kind="atomic-subject")
        if re.search(r"(?<![A-Za-z0-9_])NAME(?![A-Za-z0-9_])", text):
            collect("NAME", prompt_id, source_paths, role_hint="identity_hook", source_kind="identity-hook")

        prompt_clauses: set[str] = set()
        for raw in _FRAGMENT_CLAUSE_SPLIT.split(text):
            clause = _strip_subject_wrapper(_single_line_recipe_prompt(raw).strip(" ,;"))
            word_count = len(clause.split())
            if not (3 <= word_count <= 36 and 16 <= len(clause) <= 260):
                continue
            if _FRAGMENT_LOW_VALUE.fullmatch(clause):
                continue
            key = re.sub(r"[^a-z0-9]+", " ", clause.casefold()).strip()
            if not key or key in prompt_clauses:
                continue
            prompt_clauses.add(key)
            collect(clause, prompt_id, source_paths)

    fragments: list[dict[str, Any]] = []
    for item in clause_rows.values():
        prompt_count = len(item["prompt_ids"])
        source_count = len(item["source_paths"])
        contains_token = bool(TOKEN_PATTERN.search(item["value"]))
        role_hint = str(item.get("role_hint") or "")
        minimum_prompts = 2 if contains_token else 3
        if role_hint == "subject":
            minimum_prompts = 2
        if prompt_count < minimum_prompts:
            continue
        if source_count < 2 and prompt_count < 5:
            continue
        role = role_hint or _fragment_role(item["value"])
        if not role:
            continue
        fragment_value = item["value"]
        confidence = _fragment_confidence(prompt_count, source_count)
        fragments.append({
            "role": role,
            "value": fragment_value,
            "family_id": _fragment_family_id(role, fragment_value),
            "join_mode": _fragment_join_mode(role, fragment_value),
            "preferred_position": FRAGMENT_ROLE_ORDER.get(role, 50),
            "placeholder_signature": _placeholder_signature(fragment_value),
            "confidence": confidence,
            "review_state": "suggested" if prompt_count >= 10 and source_count >= 2 else "review",
            "source_kind": str(item.get("source_kind") or "mined-clause"),
            "source_prompt_ids": sorted(item["prompt_ids"]),
            "source_files": [
                {"source_path": path, "source_type": "prompt-log"}
                for path in sorted(item["source_paths"], key=str.casefold)
            ],
            "multiple_allowed": role not in {"identity_hook", "subject", "subject_structure", "capture_medium", "wardrobe_hook", "scene_hook", "brand_hook"},
        })

    theme_rows: dict[str, dict[str, Any]] = {}
    for source_path, prompt_ids in source_prompt_ids.items():
        label = _source_theme_label(source_path)
        if not label:
            continue
        key = label.casefold()
        theme = theme_rows.setdefault(key, {"value": label, "prompt_ids": set(), "source_paths": set()})
        theme["prompt_ids"].update(prompt_ids)
        theme["source_paths"].add(source_path)
    for item in theme_rows.values():
        if len(item["prompt_ids"]) < 5:
            continue
        fragments.append({
            "role": "concept",
            "value": item["value"],
            "family_id": _fragment_family_id("concept", item["value"]),
            "join_mode": "concept",
            "preferred_position": FRAGMENT_ROLE_ORDER["concept"],
            "confidence": _fragment_confidence(len(item["prompt_ids"]), len(item["source_paths"])),
            "review_state": "suggested",
            "source_kind": "source-theme",
            "source_prompt_ids": sorted(item["prompt_ids"]),
            "source_files": [
                {"source_path": path, "source_type": "theme-source"}
                for path in sorted(item["source_paths"], key=str.casefold)
            ],
            "multiple_allowed": False,
        })

    for (parent, subcategory), prompt_ids in home_prompt_ids.items():
        label = subcategory if subcategory and subcategory != "General" else parent
        if len(prompt_ids) < 5 or not label:
            continue
        fragments.append({
            "role": "concept",
            "value": label,
            "family_id": _fragment_family_id("concept", label),
            "join_mode": "concept",
            "preferred_position": FRAGMENT_ROLE_ORDER["concept"],
            "confidence": _fragment_confidence(len(prompt_ids), 1),
            "review_state": "suggested",
            "source_kind": "taxonomy-home",
            "source_prompt_ids": sorted(prompt_ids),
            "source_files": [],
            "multiple_allowed": False,
        })

    root = Path(prompt_root) if prompt_root is not None else _prompt_corpus_root()
    if root is not None:
        fragment_root = root / "Fragments"
        if fragment_root.is_dir():
            for path in sorted(fragment_root.rglob("*.txt"), key=lambda item: str(item).casefold()):
                folded_name = path.name.casefold()
                role = "prefix" if "prefix" in folded_name else "suffix" if "suffix" in folded_name else ""
                if not role:
                    continue
                try:
                    relative = str(path.relative_to(root)).replace("\\", "/")
                except ValueError:
                    relative = path.name
                for line_number, value in enumerate(_read_prompt_source(path), 1):
                    fragments.append({
                        "role": role,
                        "value": value,
                        "family_id": _fragment_family_id(role, value),
                        "join_mode": role,
                        "preferred_position": FRAGMENT_ROLE_ORDER[role],
                        "placeholder_signature": _placeholder_signature(value),
                        "confidence": 1.0,
                        "review_state": "approved",
                        "source_kind": "curated-seed",
                        "source_prompt_ids": [],
                        "source_files": [{"source_path": relative, "line_number": line_number, "source_type": "curated-fragment"}],
                        "multiple_allowed": True,
                    })

    by_id: dict[str, dict[str, Any]] = {}
    catalog = get_catalog()
    for fragment in fragments:
        fragment_id = catalog.fragment_id(fragment["role"], fragment["value"])
        existing = by_id.get(fragment_id)
        if existing is None:
            by_id[fragment_id] = {**fragment, "fragment_id": fragment_id}
            continue
        existing["source_prompt_ids"] = sorted(set(existing.get("source_prompt_ids") or []) | set(fragment.get("source_prompt_ids") or []))
        source_map = {
            (str(source.get("source_path") or ""), int(source.get("line_number") or 0), str(source.get("source_type") or "")): source
            for source in [*(existing.get("source_files") or []), *(fragment.get("source_files") or [])]
        }
        existing["source_files"] = list(source_map.values())
        if fragment.get("source_kind") == "curated-seed":
            existing.update({"confidence": 1.0, "review_state": "approved", "source_kind": "curated-seed"})
    return list(by_id.values())


def _fragment_source_signature(root: Path | None) -> str:
    if root is None or not (root / "Fragments").is_dir():
        return "none"
    files = sorted((root / "Fragments").rglob("*.txt"), key=lambda item: str(item).casefold())
    return _file_set_signature(root, files, "curated-fragments-v1")


def _ensure_fragment_index(*, force: bool = False, prompt_root: Path | str | None = None) -> dict[str, Any]:
    # Normal Library operation mines the canonical database only. An explicit
    # prompt_root remains available for tests/manual migration tools, but source
    # folders are never an implicit built-in Creative Library anymore.
    if prompt_root is not None:
        _ensure_prompt_corpus_index(prompt_root)
    root = _prompt_corpus_root(prompt_root) if prompt_root is not None else None
    catalog = get_catalog()
    snapshot = _prompt_asset_snapshot(ensure_corpus=False)
    signature = hashlib.sha256(
        f"{FRAGMENT_MINER_VERSION}\0{catalog.prompt_revision()}\0{catalog.recipe_revision()}\0{_fragment_source_signature(root)}".encode("utf-8")
    ).hexdigest()
    if not force and catalog.metadata_value("fragment_index_signature") == signature and catalog.fragment_summary()["total"]:
        return {"ok": True, "rebuilt": False, "signature": signature, **catalog.fragment_summary()}
    fragments = _mine_prompt_fragments(snapshot["records"], root)
    result = catalog.replace_mined_fragments(fragments, signature=signature)
    return {"ok": True, "rebuilt": True, "signature": signature, **result, **catalog.fragment_summary()}


def _decompose_prompt_for_builder(prompt_id: str) -> dict[str, Any]:
    """Split a canonical Prompt into editable, provenance-aware Builder slots."""
    clean_id = str(prompt_id or "").strip()
    asset = next((item for item in _prompt_asset_snapshot(ensure_corpus=False)["prompts"] if str(item.get("prompt_id") or "") == clean_id), None)
    if asset is None:
        raise ValueError("Prompt asset no longer exists")
    value = _single_line_recipe_prompt(asset.get("value"))
    linked = get_catalog().fragments_for_prompt(clean_id, limit=200)
    exact: dict[tuple[str, str], dict[str, Any]] = {}
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fragment in linked:
        role = str(fragment.get("role") or "")
        normalized = re.sub(r"[^a-z0-9]+", " ", str(fragment.get("value") or "").casefold()).strip()
        exact[(role, normalized)] = fragment
        by_role[role].append(fragment)

    segments: list[dict[str, Any]] = []
    cursor = 0
    for index, raw in enumerate(_FRAGMENT_CLAUSE_SPLIT.split(value)):
        text = _single_line_recipe_prompt(raw).strip(" ,;")
        if not text:
            continue
        start = value.find(raw, cursor)
        if start < 0:
            start = cursor
        separator = value[cursor:start]
        cursor = max(cursor, start + len(raw))
        role = _fragment_role(text) or "custom"
        canonical = _neutralize_subject_fragment(text) if role == "subject_structure" else text
        normalized = re.sub(r"[^a-z0-9]+", " ", canonical.casefold()).strip()
        fragment = exact.get((role, normalized))
        if fragment is None and role in by_role:
            # A neutralized family may have merged multiple source wordings.
            family_id = _fragment_family_id(role, canonical)
            fragment = next((item for item in by_role[role] if str(item.get("family_id") or "") == family_id), None)
        slot_text = str(fragment.get("value") or canonical) if fragment else canonical
        segments.append({
            "instance_id": f"segment:{index}:{hashlib.sha1(f'{clean_id}\0{index}\0{text}'.encode('utf-8')).hexdigest()[:12]}",
            "fragment_id": str(fragment.get("fragment_id") or "") if fragment else "",
            "role": role,
            "value": slot_text,
            "original_text": text,
            "join_mode": str(fragment.get("join_mode") or "source-clause") if fragment else "source-clause",
            "preferred_position": int(fragment.get("preferred_position") or FRAGMENT_ROLE_ORDER.get(role, 50)) if fragment else FRAGMENT_ROLE_ORDER.get(role, 50),
            "confidence": float(fragment.get("confidence") or 0) if fragment else 0.0,
            "review_state": str(fragment.get("review_state") or "source-fallback") if fragment else "source-fallback",
            "source_kind": str(fragment.get("source_kind") or "source-fallback") if fragment else "source-fallback",
            "separator_before": separator,
            "source_segment": True,
            "locked": False,
        })
    return {
        "ok": True,
        "prompt": asset,
        "segments": segments,
        "matched": sum(bool(segment["fragment_id"]) for segment in segments),
        "fallback": sum(not bool(segment["fragment_id"]) for segment in segments),
    }


PROMPT_FACET_RULES: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "concept": tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
        ("UV Night", r"\b(?:uv night|ultraviolet night)\b"),
        ("Nest Roll", r"\bnest roll\b"),
        ("Electric Forest", r"\belectric forest\b"),
        ("Tactile Fever", r"\btactile fever\b"),
        ("Love Fever", r"\blove fever\b"),
        ("Oil Realm", r"\boil realm\b"),
        ("UV House", r"\buv house\b"),
        ("Neon", r"\bneon\b"),
        ("Roadtrip", r"\broad[ -]?trip\b"),
        ("Vintage Magazine", r"\bvintage magazine\b"),
        ("Faceout", r"\bface[ -]?out\b"),
        ("Sick Light", r"\bsick light\b"),
        ("Suburban", r"\bsuburban\b"),
        ("Vaporwave", r"\bvaporwave\b"),
        ("Y2K", r"\by2k\b"),
        ("Bad Date Night", r"\bbad date night\b"),
    )),
    "structure": tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
        ("Portrait", r"\b(?:portrait|headshot|head and shoulders|shoulders up|bust shot)\b"),
        ("Close-up", r"\b(?:close[- ]?up|extreme close|macro|facial detail|beauty shot)\b"),
        ("Full body", r"\b(?:full[- ]?body|head to toe|whole body|feet visible|fills? the frame)\b"),
        ("Candid", r"\b(?:candid|snapshot|phone photo|point[- ]and[- ]shoot|spontaneous|caught mid)\b"),
        ("Editorial", r"\b(?:editorial|fashion shoot|fashion photograph|magazine|campaign|lookbook|runway)\b"),
        ("Environment", r"\b(?:establishing shot|wide shot|environment|landscape|location study|scene reference)\b"),
        ("Concept", r"\b(?:conceptual|surreal|experimental|abstract|fantasy|dreamlike|otherworldly)\b"),
    )),
    "style": tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
        ("Candid", r"\b(?:candid|spontaneous|caught mid)\w*\b"),
        ("Photoreal", r"\b(?:photoreal|realistic photo|lifelike|real photograph|natural skin)\b"),
        ("Analog", r"\b(?:analog|film grain|35mm|polaroid|point[- ]and[- ]shoot|disposable camera|y2k photo)\b"),
        ("Point-and-Shoot", r"\b(?:point[- ]and[- ]shoot|compact camera|disposable camera)\b"),
        ("Phone", r"\b(?:phone photo|phone camera|smartphone|iphone|android photo|cellphone)\b"),
        ("High-Key Flash", r"\b(?:high[- ]key flash|hard flash|direct flash|on[- ]camera flash|beauty flash)\b"),
        ("Cinematic", r"\b(?:cinematic|film still|movie still|anamorphic|cinemascope)\b"),
        ("Editorial", r"\b(?:editorial|fashion shoot|campaign|lookbook)\b"),
        ("Poster", r"\b(?:poster|one[- ]sheet|key art)\b"),
        ("Magazine", r"\b(?:magazine|cover story|masthead)\b"),
        ("Psychedelic", r"\b(?:psychedelic|acid art|marbled|kaleidoscop)\w*\b"),
        ("Fashion", r"\b(?:fashion|editorial|lookbook|campaign|couture|runway|catalog)\b"),
        ("Graphic", r"\b(?:graphic poster|flat color|illustration|vector|screenprint|typography|comic)\b"),
        ("Surreal", r"\b(?:surreal|dreamlike|psychedelic|abstract|marbled|impossible|otherworldly)\b"),
        ("Minimal", r"\b(?:minimal|minimalist|seamless background|solid background|clean studio|simple backdrop)\b"),
    )),
    "content": tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
        ("Nude / Bare", r"\b(?:nude|naked|topless|bottomless|bare(?:foot|feet|leg|skin|body| everywhere| from)|otherwise bare|unclothed)\b"),
        ("Multi-Subject", r"\b(?:two|three|four|multiple)\s+(?:women|men|people|subjects|figures)\b|\b(?:couple|duo|pair|group of|friends together|multi[- ]subject)\b"),
        ("Foot Focus", r"\b(?:foot focus|feet focus|feet visible|bare feet|barefoot|toes?|soles?|foot close[- ]?up)\b"),
        ("Typography", r"\b(?:typography|text|lettering|masthead|headline|caption|logo|wordmark|font|typeset|signage|microtype|stencil(?:ed)?)\b|(?<![A-Za-z0-9_])(?:BRAND|ITEM)(?![A-Za-z0-9_])"),
    )),
    "time": tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
        ("Night", r"\b(?:night|midnight|after dark|nocturnal)\b"),
        ("Dusk", r"\b(?:dusk|twilight|blue hour|evening light)\b"),
        ("Dawn", r"\b(?:dawn|sunrise|early morning)\b"),
        ("Golden Hour", r"\b(?:golden hour|late afternoon sun|warm sunset light)\b"),
        ("Daylight", r"\b(?:daylight|daytime|midday|morning light|sunlit|bright day)\b"),
    )),
    "scene": tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
        ("Studio", r"\b(?:studio|seamless|backdrop|cyclorama|photo set)\b"),
        ("Interior", r"\b(?:bedroom|bathroom|kitchen|living room|hotel|motel|apartment|indoor|interior)\b"),
        ("Urban", r"\b(?:street|city|alley|subway|parking lot|rooftop|downtown|urban|storefront)\b"),
        ("Nature", r"\b(?:forest|woods|meadow|garden|field|mountain|desert|nature|outdoor)\b"),
        ("Night", r"\b(?:night|midnight|after dark|moonlight|neon-lit|nightclub|bar)\b"),
        ("Travel", r"\b(?:road trip|roadtrip|car|train|airport|airplane|station|highway|travel)\b"),
        ("Water", r"\b(?:beach|ocean|pool|lake|river|underwater|shore|waterfall)\b"),
    )),
    "mood": tuple((label, re.compile(pattern, re.IGNORECASE)) for label, pattern in (
        ("Playful", r"\b(?:playful|coy|teasing|mischievous|cheeky|wink|smirk|giggl)\w*\b"),
        ("Soft", r"\b(?:soft|gentle|tender|delicate|dreamy|wistful|shy|cozy)\b"),
        ("Bold", r"\b(?:bold|confident|glam|glamorous|powerful|striking|fierce)\b"),
        ("Dark", r"\b(?:dark|moody|brooding|ominous|gothic|melanchol|disgust|angry)\w*\b"),
        ("Calm", r"\b(?:calm|quiet|serene|peaceful|relaxed|sleepy|contemplative)\b"),
        ("Energetic", r"\b(?:energetic|dynamic|excited|laughing|dancing|running|motion)\b"),
        ("Romantic", r"\b(?:romantic|intimate|sensual|flirt|valentine|love|date night)\w*\b"),
    )),
}
PROMPT_FILTER_AXES = ("parent", "subcategory", "style", "cast", "content", "time", "shot")
PROMPT_HOME_AXES = frozenset({"parent", "subcategory"})
PROMPT_DISCOVERY_FILTER_AXES = tuple(axis for axis in PROMPT_FILTER_AXES if axis not in PROMPT_HOME_AXES)

def _prompt_facets(value: Any, sources: list[dict[str, Any]] | None = None) -> dict[str, list[str]]:
    """Classify prompt text into deterministic discovery facets.

    Facets are a reversible index over the canonical prompt. They never rewrite
    prompt text or source logs, so the classifier can evolve safely over time.
    """
    text = _single_line_recipe_prompt(value)
    # Source filenames are provenance only.  They must never assign a Prompt
    # to a concept, style, or scene—the old database contamination came from
    # treating filenames as content.
    searchable = text
    output: dict[str, list[str]] = {}
    for axis, rules in PROMPT_FACET_RULES.items():
        matches = [label for label, pattern in rules if pattern.search(searchable)]
        if axis == "content" and "Typography" not in matches:
            matches.append("No Typography")
        output[axis] = matches or ["Other"]
    output["shot"] = list(output.get("structure") or ["Other"])
    if re.search(r"\b(?:young woman and (?:a )?(?:young |older |elderly )?man|woman and man|heterosexual couple)\b", searchable, re.IGNORECASE):
        output["cast"] = ["Woman & Man"]
    elif re.search(r"\b(?:two young women|two women|woman and woman)\b", searchable, re.IGNORECASE):
        output["cast"] = ["Woman & Woman"]
    elif re.search(r"\b(?:group of|three |four |multiple |crowd)\b", searchable, re.IGNORECASE):
        output["cast"] = ["Group / Multi-Subject"]
    else:
        output["cast"] = ["Solo"]
    return output


def _prompt_facet_counts(assets: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    # Keep legacy axes in summary metadata for extension compatibility while
    # the new navigation only exposes PROMPT_FILTER_AXES.
    axes = tuple(dict.fromkeys((*PROMPT_FILTER_AXES, *PROMPT_FACET_RULES.keys())))
    counts: dict[str, dict[str, int]] = {axis: {} for axis in axes}
    for asset in assets:
        facets = asset.get("facets") if isinstance(asset.get("facets"), dict) else {}
        for axis in axes:
            for label in facets.get(axis) or ["Other"]:
                bucket = counts[axis]
                bucket[str(label)] = bucket.get(str(label), 0) + 1
    return counts


def _valid_resolved_seed(value: Any) -> int | None:
    try:
        seed = int(value)
    except (TypeError, ValueError):
        return None
    return seed if 0 <= seed <= 1125899906842624 else None


TRUSTED_PROMPT_SEED_SOURCES = {"imported-image", "preview-image"}

def _recipe_resolved_seed(recipe: dict[str, Any]) -> int | None:
    payload = recipe.get("payload") if isinstance(recipe.get("payload"), dict) else {}
    values = _recipe_node_values(payload, STUDIO_GENERATION, include_optional=True) if payload else {}
    return _valid_resolved_seed(values.get("seed_value"))

def _recipe_prompt_seed_source(recipe: dict[str, Any]) -> str:
    payload = recipe.get("payload") if isinstance(recipe.get("payload"), dict) else {}
    source = str(payload.get("_sickollie_seed_source") or "").strip().lower()
    if source in TRUSTED_PROMPT_SEED_SOURCES:
        return source
    # Backward-compatible provenance for Recipes saved before explicit seed-source
    # tagging existed. Imported images are unambiguous; an existing Recipe preview
    # means the state was explicitly captured with a Preview image rather than
    # produced by a Prompt/Template Yearbook run.
    if bool(payload.get("imported_from_image")):
        return "imported-image"
    if str(recipe.get("preview_ref") or "").strip():
        return "preview-image"
    return ""


def _recipe_prompt_assets(
    recipes: list[dict[str, Any]],
    indexed_prompts: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build semantic Template and Prompt records.

    Any placeholder-bearing source is a Template. Prompt records are fully
    resolved, token-free assets only; identity-bearing resolved text is never
    admitted unless it can be made safe without leaving placeholders behind.
    """
    ordered = sorted(recipes, key=lambda item: (str(item.get("created_at") or ""), str(item.get("recipe_id") or "")))
    by_text: dict[tuple[str, str], dict[str, Any]] = {}

    for indexed in indexed_prompts or []:
        value = _single_line_recipe_prompt(indexed.get("value"))
        if not value:
            continue
        # Re-derive this from the text every time.  Older manifests could have
        # marked a prose heading such as ``Scene:`` as the SCENE placeholder;
        # no stored kind/signature should be allowed to preserve that mistake.
        sources = [dict(source) for source in indexed.get("sources") or [] if isinstance(source, dict)]
        source_paths = list(dict.fromkeys(
            str(source.get("source_path") or "") for source in sources if str(source.get("source_path") or "")
        ))
        inferred_signature = _placeholder_signature(value)
        template_signature = _template_placeholder_signature(value)
        # The tab is semantic rather than source-folder-driven: any exact
        # portable token makes this a Template.
        kind = "template" if _creative_library_is_template_text(value) else "prompt"
        parent = str(indexed.get("primary_parent") or "Other")
        subcategory = str(indexed.get("primary_subcategory") if indexed.get("primary_subcategory") is not None else "General")
        signature = template_signature if kind == "template" else inferred_signature
        home = f"{parent} / {subcategory}" if subcategory else parent
        key = (kind, value.casefold())
        by_text[key] = {
            "prompt_id": str(indexed.get("prompt_id") or f"corpus-{kind}:{hashlib.sha1(value.casefold().encode('utf-8')).hexdigest()}"),
            "kind": kind,
            "value": value,
            "source_value": _single_line_recipe_prompt(indexed.get("source_prompt_snapshot")) or value,
            "resolved_value": _portable_resolved_prompt(
                _single_line_recipe_prompt(indexed.get("source_prompt_snapshot")) or value,
                _single_line_recipe_prompt(indexed.get("resolved_prompt_snapshot")),
            ),
            "name": home,
            "primary_parent": parent,
            "primary_subcategory": subcategory,
            "primary_home": home,
            "recipe_id": "",
            "recipe_ids": [],
            "preview_ref": str(indexed.get("preview_ref") or ""),
            "preview_source": str(indexed.get("preview_source") or ""),
            "preview_updated_at": str(indexed.get("preview_updated_at") or ""),
            "resolved_seed": _valid_resolved_seed(indexed.get("resolved_seed")),
            "resolved_seed_source": str(indexed.get("resolved_seed_source") or ""),
            "preview_metadata": indexed.get("preview_metadata") if isinstance(indexed.get("preview_metadata"), dict) else {},
            "rating": int(indexed.get("rating") or 0),
            "note": str(indexed.get("note") or ""),
            "created_at": str(indexed.get("created_at") or ""),
            "updated_at": str(indexed.get("updated_at") or indexed.get("created_at") or ""),
            "uses": max(1, int(indexed.get("source_count") or len(sources) or 1)),
            "source_count": int(indexed.get("source_count") or len(sources) or 0),
            "quality_score": float(indexed.get("quality_score") or 0),
            "exact_source_occurrences": int(indexed.get("exact_source_occurrences") or 0),
            "near_cluster_id": str(indexed.get("near_cluster_id") or ""),
            "from_recipe": False,
            "indexed": True,
            "placeholder_signature": signature,
            "facets": indexed.get("facets") if isinstance(indexed.get("facets"), dict) and indexed.get("facets") else _prompt_facets(value),
            "collections": [],
            "sources": sources,
            "source_paths": source_paths,
            "builder_ready": kind == "template",
            "component_ready": kind == "template" and _component_ready_signature(signature),
        }

    def merge_recipe_asset(
        recipe: dict[str, Any], value: str, kind: str, *, source_value: str = "", resolved_value: str = "",
    ) -> None:
        value = _single_line_recipe_prompt(value)
        if not value:
            return
        key = (kind, value.casefold())
        recipe_id = str(recipe.get("recipe_id") or "")
        updated_at = str(recipe.get("updated_at") or recipe.get("created_at") or "")
        recipe_seed_source = _recipe_prompt_seed_source(recipe)
        recipe_seed = _recipe_resolved_seed(recipe) if recipe_seed_source else None
        recipe_preview_metadata = _payload_prompt_preview_metadata(
            recipe.get("payload") if isinstance(recipe.get("payload"), dict) else {}
        )
        if key in by_text:
            existing = by_text[key]
            existing["uses"] += 1
            existing["recipe_ids"].append(recipe_id)
            existing["from_recipe"] = True
            if source_value:
                existing["source_value"] = _single_line_recipe_prompt(source_value)
            if resolved_value:
                existing["resolved_value"] = _single_line_recipe_prompt(resolved_value)
            if recipe_preview_metadata and not existing.get("preview_metadata"):
                existing["preview_metadata"] = recipe_preview_metadata
            if updated_at >= str(existing.get("updated_at") or ""):
                existing.update({
                    "name": str(recipe.get("name") or existing.get("name") or kind.title()),
                    "recipe_id": recipe_id or str(existing.get("recipe_id") or ""),
                    "preview_ref": str(recipe.get("preview_ref") or existing.get("preview_ref") or ""),
                    "updated_at": updated_at,
                })
                if recipe_seed is not None:
                    existing["resolved_seed"] = recipe_seed
                    existing["resolved_seed_source"] = recipe_seed_source
            elif (existing.get("resolved_seed") is None or not str(existing.get("resolved_seed_source") or "")) and recipe_seed is not None:
                existing["resolved_seed"] = recipe_seed
                existing["resolved_seed_source"] = recipe_seed_source
            return

        parent = "Saved & Imported"
        subcategory = "Saved Templates" if kind == "template" else "Saved Prompts"
        facets = _prompt_facets(value)
        facets["parent"] = [parent]
        facets["subcategory"] = [subcategory]
        signature = _placeholder_signature(value)
        by_text[key] = {
            "prompt_id": f"creative-{kind}:{hashlib.sha1(value.casefold().encode('utf-8')).hexdigest()}",
            "kind": kind,
            "value": value,
            "source_value": _single_line_recipe_prompt(source_value) or value,
            "resolved_value": _single_line_recipe_prompt(resolved_value),
            "name": str(recipe.get("name") or kind.title()),
            "primary_parent": parent,
            "primary_subcategory": subcategory,
            "primary_home": f"{parent} / {subcategory}",
            "recipe_id": recipe_id,
            "recipe_ids": [recipe_id],
            "preview_ref": str(recipe.get("preview_ref") or ""),
            "preview_source": "recipe",
            "resolved_seed": recipe_seed,
            "resolved_seed_source": recipe_seed_source,
            "preview_metadata": _payload_prompt_preview_metadata(recipe.get("payload") if isinstance(recipe.get("payload"), dict) else {}),
            "rating": 0,
            "note": "",
            "created_at": str(recipe.get("created_at") or ""),
            "updated_at": updated_at,
            "uses": 1,
            "source_count": 0,
            "quality_score": 0,
            "exact_source_occurrences": 0,
            "near_cluster_id": "",
            "from_recipe": True,
            "indexed": False,
            "placeholder_signature": signature,
            "facets": facets,
            "collections": [],
            "sources": [],
            "source_paths": [],
            "builder_ready": kind == "template",
            "component_ready": kind == "template" and _component_ready_signature(signature),
        }

    for recipe in ordered:
        source_value, resolved_value = _recipe_prompt_variants(recipe)
        is_template = _recipe_is_template(recipe)
        if is_template:
            merge_recipe_asset(
                recipe, source_value, "template",
                source_value=source_value, resolved_value=resolved_value,
            )
        prompt_value = _recipe_portable_prompt_text(recipe)
        merge_recipe_asset(
            recipe, prompt_value, "prompt",
            source_value=prompt_value if is_template else source_value,
            resolved_value="" if is_template else resolved_value,
        )
    return list(by_text.values())


_PROMPT_SNAPSHOT_CACHE: dict[str, Any] = {"key": None, "value": None}
_PROMPT_FILTER_METADATA_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def _prompt_collection_counts(assets: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"": len(assets), "unfiled": 0}
    for asset in assets:
        collection_ids = {
            str((item or {}).get("collection_id") or "")
            for item in asset.get("collections") or [] if str((item or {}).get("collection_id") or "")
        }
        if not collection_ids:
            counts["unfiled"] += 1
        for collection_id in collection_ids:
            counts[collection_id] = counts.get(collection_id, 0) + 1
    return counts


def _prompt_blueprint_summary(assets: list[dict[str, Any]]) -> dict[str, Any]:
    ready = [asset for asset in assets if str(asset.get("kind") or "") == "template"]
    signatures: dict[str, int] = {}
    for asset in ready:
        signature = str(asset.get("placeholder_signature") or "TOKEN FREE") or "TOKEN FREE"
        signatures[signature] = signatures.get(signature, 0) + 1
    return {
        "total": len(ready),
        "component_total": sum(bool(asset.get("component_ready")) for asset in ready),
        "signature_counts": dict(sorted(signatures.items(), key=lambda item: (-item[1], item[0]))),
    }


def _ordered_structure_values(values: list[str], preferred: Any, fallback_key) -> list[str]:
    wanted = [str(value) for value in preferred] if isinstance(preferred, list) else []
    available = set(values)
    output = [value for value in wanted if value in available]
    seen = set(output)
    output.extend(sorted((value for value in values if value not in seen), key=fallback_key))
    return output


def _prompt_home_counts(assets: list[dict[str, Any]], order: dict[str, Any] | None = None) -> dict[str, Any]:
    order = order if isinstance(order, dict) else {}
    parents: dict[str, int] = {}
    subcategories: dict[str, dict[str, int]] = {}
    logs: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    for asset in assets:
        parent = str(asset.get("primary_parent") or "Other")
        subcategory = str(asset.get("primary_subcategory") if asset.get("primary_subcategory") is not None else "General")
        parents[parent] = parents.get(parent, 0) + 1
        children = subcategories.setdefault(parent, {})
        children[subcategory] = children.get(subcategory, 0) + 1
        seen_paths: set[str] = set()
        for source in asset.get("sources") or []:
            if not isinstance(source, dict):
                continue
            source_path = str(source.get("source_path") or "").replace("\\", "/").strip()
            if not source_path or source_path in seen_paths:
                continue
            seen_paths.add(source_path)
            label = _single_line_recipe_prompt(source.get("source_label")) or Path(source_path).stem
            bucket = logs.setdefault(parent, {}).setdefault(subcategory, {})
            row = bucket.setdefault(source_path, {"label": label, "count": 0})
            row["count"] = int(row.get("count") or 0) + 1

    preferred_parents = order.get("parents") if isinstance(order.get("parents"), list) else []
    # Persisted structure may intentionally contain empty curator-created folders.
    # Keep those visible so a user can build taxonomy before importing content.
    parent_values = list(dict.fromkeys([*preferred_parents, *parents.keys()]))
    parent_names = _ordered_structure_values(
        parent_values, preferred_parents, lambda value: (-int(parents.get(value, 0)), value.casefold())
    )
    ordered_parents = {parent: int(parents.get(parent, 0)) for parent in parent_names}

    ordered_subcategories: dict[str, dict[str, int]] = {}
    ordered_logs: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
    sub_order_map = order.get("subcategories") if isinstance(order.get("subcategories"), dict) else {}
    log_order_map = order.get("logs") if isinstance(order.get("logs"), dict) else {}
    for parent in parent_names:
        child_map = subcategories.get(parent, {})
        preferred_children = sub_order_map.get(parent, []) if isinstance(sub_order_map.get(parent), list) else []
        child_values = list(dict.fromkeys([*preferred_children, *child_map.keys()]))
        child_names = _ordered_structure_values(
            child_values, preferred_children, lambda value: (-int(child_map.get(value, 0)), value.casefold())
        )
        ordered_subcategories[parent] = {child: int(child_map.get(child, 0)) for child in child_names}
        if parent not in logs:
            continue
        parent_logs: dict[str, dict[str, dict[str, Any]]] = {}
        preferred_parent_logs = log_order_map.get(parent, {}) if isinstance(log_order_map.get(parent), dict) else {}
        log_subcategories = list(dict.fromkeys([*child_names, *logs.get(parent, {}).keys()]))
        for subcategory in log_subcategories:
            rows = logs.get(parent, {}).get(subcategory, {})
            if not rows:
                continue
            log_paths = _ordered_structure_values(
                list(rows), preferred_parent_logs.get(subcategory, []),
                lambda value: (str(rows[value].get("label") or "").casefold(), value.casefold()),
            )
            parent_logs[subcategory] = {path: rows[path] for path in log_paths}
        if parent_logs:
            ordered_logs[parent] = parent_logs
    return {"parents": ordered_parents, "subcategories": ordered_subcategories, "logs": ordered_logs}


def _prompt_placeholder_counts(assets: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in assets:
        for token in str(asset.get("placeholder_signature") or "").split("+"):
            clean = token.strip().upper()
            if clean:
                counts[clean] = counts.get(clean, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _prompt_facet_covers(assets: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    covers: dict[str, dict[str, str]] = {axis: {} for axis in PROMPT_FILTER_AXES}
    candidates = sorted(
        (asset for asset in assets if str(asset.get("preview_ref") or "")),
        key=lambda asset: (int(asset.get("uses") or 0), str(asset.get("updated_at") or "")),
        reverse=True,
    )
    for asset in candidates:
        for axis, labels in (asset.get("facets") or {}).items():
            if axis not in covers:
                continue
            for label in labels or []:
                covers[axis].setdefault(str(label), str(asset.get("preview_ref") or ""))
    return covers


def _prompt_asset_snapshot(*, ensure_corpus: bool = False) -> dict[str, Any]:
    """Cache the expensive deterministic prompt index until recipes change."""
    if ensure_corpus:
        _ensure_prompt_corpus_index()
    catalog = get_catalog()
    key = (str(catalog.path), catalog.recipe_revision(), catalog.prompt_revision())
    if _PROMPT_SNAPSHOT_CACHE.get("key") == key and isinstance(_PROMPT_SNAPSHOT_CACHE.get("value"), dict):
        return _PROMPT_SNAPSHOT_CACHE["value"]

    recipes = catalog.recipes()
    for recipe in recipes:
        payload = recipe.get("payload")
        if isinstance(payload, dict):
            recipe["payload"] = _curate_prompt_catalog_recipe(payload)
            recipe["payload"]["tokens"] = _recipe_tokens(recipe["payload"])
    records = [
        asset for asset in _recipe_prompt_assets(recipes, catalog.indexed_prompt_assets())
        if not re.search(r"\bchild\b", str(asset.get("value") or ""), re.IGNORECASE)
    ]
    prompt_ids = [str(asset.get("prompt_id") or "") for asset in records]
    overrides = catalog.prompt_override_map(prompt_ids)
    for asset in records:
        override = overrides.get(str(asset.get("prompt_id") or ""))
        if not override:
            continue
        if bool(override.get("home_override")):
            asset["primary_parent"] = str(override.get("primary_parent") or asset.get("primary_parent") or "Other")
            asset["primary_subcategory"] = str(override.get("primary_subcategory") or asset.get("primary_subcategory") or "General")
        asset["archived"] = bool(override.get("archived"))
    direct_collections = catalog.prompt_collection_map(prompt_ids)
    for asset in records:
        asset_kind = "template" if str(asset.get("kind") or "").casefold() == "template" else "prompt"
        collection_map = {
            str(item.get("collection_id") or ""): dict(item)
            for item in asset.get("collections") or []
            if str(item.get("collection_id") or "") and str(item.get("kind") or asset_kind) == asset_kind
        }
        for collection in direct_collections.get(str(asset.get("prompt_id") or ""), []):
            if str(collection.get("kind") or "") != asset_kind:
                continue
            collection_map[str(collection.get("collection_id") or "")] = dict(collection)
        asset["collections"] = list(collection_map.values())
    prompts = [asset for asset in records if str(asset.get("kind") or "prompt") == "prompt"]
    templates = [asset for asset in records if str(asset.get("kind") or "") == "template"]
    snapshot = {
        "revision": key,
        "recipe_templates": [recipe for recipe in recipes if _recipe_is_template(recipe)],
        "templates": templates,
        "prompts": prompts,
        "records": records,
        "facet_counts": {"prompt": _prompt_facet_counts(prompts), "template": _prompt_facet_counts(templates)},
        "home_counts": {
            "prompt": _prompt_home_counts(prompts, catalog.creative_structure_order("prompt")),
            "template": _prompt_home_counts(templates, catalog.creative_structure_order("template")),
        },
        "placeholder_counts": _prompt_placeholder_counts(templates),
        "collection_counts": _prompt_collection_counts(prompts),
        "collection_counts_by_kind": {
            "prompt": _prompt_collection_counts(prompts),
            "template": _prompt_collection_counts(templates),
        },
        "blueprints": _prompt_blueprint_summary(templates),
        "facet_covers": {"prompt": _prompt_facet_covers(prompts), "template": _prompt_facet_covers(templates)},
    }
    _PROMPT_FILTER_METADATA_CACHE.clear()
    _PROMPT_SNAPSHOT_CACHE.update({"key": key, "value": snapshot})
    return snapshot


def _prompt_source_order_key(asset: dict[str, Any], source_path: str = "") -> tuple[Any, ...]:
    clean_path = str(source_path or "").replace("\\", "/").strip().casefold()
    sources = [source for source in asset.get("sources") or [] if isinstance(source, dict)]
    if clean_path:
        sources = [source for source in sources if str(source.get("source_path") or "").replace("\\", "/").strip().casefold() == clean_path]
    candidates = []
    for source in sources:
        path = str(source.get("source_path") or "").replace("\\", "/").strip()
        try:
            line_number = max(0, int(source.get("line_number") or 0))
        except (TypeError, ValueError):
            line_number = 0
        candidates.append((path.casefold(), line_number or 10**9, str(asset.get("value") or "").casefold()))
    return min(candidates) if candidates else ("~", 10**9, str(asset.get("value") or "").casefold())


def _sort_prompt_assets(assets: list[dict[str, Any]], sort: str, source_path: str = "") -> None:
    if sort == "source_order":
        assets.sort(key=lambda item: _prompt_source_order_key(item, source_path))
    elif sort == "name":
        assets.sort(key=lambda item: str(item.get("name") or item.get("value") or "").casefold())
    elif sort == "rating":
        assets.sort(key=lambda item: (int(item.get("rating") or 0), float(item.get("quality_score") or 0), str(item.get("value") or "").casefold()), reverse=True)
    elif sort == "quality":
        assets.sort(key=lambda item: (float(item.get("quality_score") or 0), int(item.get("source_count") or 0), str(item.get("value") or "").casefold()), reverse=True)
    elif sort == "preview_newest":
        assets.sort(key=lambda item: (bool(item.get("preview_ref")), str(item.get("preview_updated_at") or ""), str(item.get("value") or "").casefold()), reverse=True)
    elif sort == "oldest":
        assets.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("prompt_id") or "")))
    elif sort == "most_used":
        assets.sort(key=lambda item: (int(item.get("uses") or 0), str(item.get("updated_at") or item.get("created_at") or "")), reverse=True)
    else:
        assets.sort(key=lambda item: (str(item.get("updated_at") or item.get("created_at") or ""), str(item.get("prompt_id") or "")), reverse=True)


def _filter_prompt_assets(
    assets: list[dict[str, Any]], *, query: str = "", source: str = "", collection: str = "",
    facets: dict[str, str] | None = None, sort: str = "newest", blueprint_only: bool = False,
    signature: str = "", placeholders: list[str] | None = None,
    parent: str = "", subcategory: str = "", log_path: str = "", include_archived: bool = False, rating: str = "",
    omit_facet_axes: set[str] | None = None, omit_home: bool = False, sort_results: bool = True,
) -> list[dict[str, Any]]:
    needle = _single_line_recipe_prompt(query).casefold()
    clean_source = str(source or "").strip().casefold()
    clean_collection = str(collection or "").strip()
    clean_signature = str(signature or "").strip().upper()
    clean_parent = str(parent or "").strip().casefold()
    clean_subcategory = str(subcategory or "").strip().casefold()
    clean_log_path = str(log_path or "").replace("\\", "/").strip().casefold()
    clean_rating = str(rating or "").strip().casefold()
    required_placeholders = {str(token or "").strip().upper() for token in placeholders or [] if str(token or "").strip()}
    # A pure NAME formula exists, so NAME-only remains an exact request.  Some
    # useful slots (notably SCENE) only occur inside formulas with companions;
    # let a one-chip request discover those instead of disabling the chip.
    exact_signatures = {
        str(item.get("placeholder_signature") or "").upper()
        for item in assets
    } if required_placeholders else set()
    allow_dependent_single = bool(required_placeholders) and len(required_placeholders) == 1 and "+".join(sorted(required_placeholders)) not in exact_signatures
    selected_facets = {axis: str((facets or {}).get(axis) or "").strip() for axis in PROMPT_DISCOVERY_FILTER_AXES}
    omitted = set(omit_facet_axes or set())
    filtered: list[dict[str, Any]] = []
    for asset in assets:
        if not include_archived and bool(asset.get("archived")):
            continue
        asset_rating = max(0, min(5, int(asset.get("rating") or 0)))
        if clean_rating == "unrated" and asset_rating:
            continue
        if clean_rating == "rated" and not asset_rating:
            continue
        if clean_rating.endswith("plus"):
            try:
                if asset_rating < int(clean_rating.removesuffix("plus")):
                    continue
            except ValueError:
                pass
        elif clean_rating.isdigit() and asset_rating != int(clean_rating):
            continue
        if not omit_home and clean_parent and str(asset.get("primary_parent") or "").strip().casefold() != clean_parent:
            continue
        if not omit_home and clean_subcategory and str(asset.get("primary_subcategory") or "").strip().casefold() != clean_subcategory:
            continue
        if not omit_home and clean_log_path and not any(
            str((source or {}).get("source_path") or "").replace("\\", "/").strip().casefold() == clean_log_path
            for source in asset.get("sources") or [] if isinstance(source, dict)
        ):
            continue
        if blueprint_only and not asset.get("builder_ready"):
            continue
        if clean_signature and str(asset.get("placeholder_signature") or "").upper() != clean_signature:
            continue
        asset_placeholders = {token for token in str(asset.get("placeholder_signature") or "").upper().split("+") if token}
        # Template chips are a signature picker: NAME means NAME-only, not a
        # template that also requires BRAND, ITEM, or another hidden value.
        if required_placeholders and (
            required_placeholders != asset_placeholders
            and not (allow_dependent_single and required_placeholders.issubset(asset_placeholders))
        ):
            continue
        if clean_source == "recipe" and not asset.get("from_recipe"):
            continue
        if clean_source == "ready" and asset.get("from_recipe"):
            continue
        if needle:
            source_text = " ".join(
                f"{(source or {}).get('source_label') or ''} {(source or {}).get('source_path') or ''}"
                for source in asset.get("sources") or [] if isinstance(source, dict)
            )
            if needle not in f"{asset.get('name') or ''} {asset.get('value') or ''} {source_text}".casefold():
                continue
        collection_ids = {
            str((item or {}).get("collection_id") or "")
            for item in asset.get("collections") or [] if str((item or {}).get("collection_id") or "")
        }
        if clean_collection and not (
            (clean_collection == "unfiled" and not collection_ids) or clean_collection in collection_ids
        ):
            continue
        asset_facets = asset.get("facets") if isinstance(asset.get("facets"), dict) else {}
        if any(
            axis not in omitted and selected and selected not in (asset_facets.get(axis) or ["Other"])
            for axis, selected in selected_facets.items()
        ):
            continue
        filtered.append(asset)

    if sort_results:
        _sort_prompt_assets(filtered, sort, log_path)
    return filtered


def _prompt_filter_metadata(
    assets: list[dict[str, Any]], *, query: str = "", source: str = "", collection: str = "",
    facets: dict[str, str] | None = None, sort: str = "preview_newest", blueprint_only: bool = False,
    signature: str = "", placeholders: list[str] | None = None, parent: str = "", subcategory: str = "", log_path: str = "",
    include_archived: bool = False, rating: str = "",
) -> dict[str, Any]:
    """Return context-sensitive counts in one catalog pass.

    The old implementation called the full filter fourteen times per request.
    That made a 14k-record catalog spend seconds recomputing the same base
    predicates for every dropdown.  This pass evaluates shared constraints
    once, then derives each facet/home/placeholder availability count from the
    same row state.
    """
    needle = _single_line_recipe_prompt(query).casefold()
    clean_source = str(source or "").strip().casefold()
    clean_collection = str(collection or "").strip()
    clean_signature = str(signature or "").strip().upper()
    clean_parent = str(parent or "").strip().casefold()
    clean_subcategory = str(subcategory or "").strip().casefold()
    clean_log_path = str(log_path or "").replace("\\", "/").strip().casefold()
    clean_rating = str(rating or "").strip().casefold()
    selected_facets = {axis: str((facets or {}).get(axis) or "").strip() for axis in PROMPT_DISCOVERY_FILTER_AXES}
    selected_placeholders = {str(value).strip().upper() for value in placeholders or [] if str(value).strip()}
    exact_signatures = {str(item.get("placeholder_signature") or "").upper() for item in assets}
    placeholder_tokens = ("NAME", "OUTFIT", "OUTFIT_B", "OUTFIT_C", "BRAND", "ITEM", "SCENE")
    placeholder_candidates = {
        token: (selected_placeholders - {token} if token in selected_placeholders else selected_placeholders | {token})
        for token in placeholder_tokens
    }

    def rating_matches(value: int) -> bool:
        if clean_rating == "unrated":
            return value == 0
        if clean_rating == "rated":
            return value > 0
        if clean_rating.endswith("plus"):
            try:
                return value >= int(clean_rating.removesuffix("plus"))
            except ValueError:
                return True
        if clean_rating.isdigit():
            return value == int(clean_rating)
        return True

    def placeholders_match(asset_tokens: set[str], required: set[str]) -> bool:
        if not required:
            return True
        allow_dependent = len(required) == 1 and "+".join(sorted(required)) not in exact_signatures
        return required == asset_tokens or (allow_dependent and required.issubset(asset_tokens))

    visible: list[dict[str, Any]] = []
    facet_counts: dict[str, dict[str, int]] = {axis: {} for axis in PROMPT_FILTER_AXES}
    home_counts: dict[str, Any] = {"parents": {}, "subcategories": {}, "logs": {}}
    placeholder_available = {token: 0 for token in placeholder_tokens}

    for asset in assets:
        if not include_archived and bool(asset.get("archived")):
            continue
        if not rating_matches(max(0, min(5, int(asset.get("rating") or 0)))):
            continue
        if blueprint_only and not asset.get("builder_ready"):
            continue
        if clean_signature and str(asset.get("placeholder_signature") or "").upper() != clean_signature:
            continue
        if clean_source == "recipe" and not asset.get("from_recipe"):
            continue
        if clean_source == "ready" and asset.get("from_recipe"):
            continue
        if needle:
            source_text = " ".join(
                f"{(source or {}).get('source_label') or ''} {(source or {}).get('source_path') or ''}"
                for source in asset.get("sources") or [] if isinstance(source, dict)
            )
            if needle not in f"{asset.get('name') or ''} {asset.get('value') or ''} {source_text}".casefold():
                continue
        collection_ids = {
            str((item or {}).get("collection_id") or "")
            for item in asset.get("collections") or [] if str((item or {}).get("collection_id") or "")
        }
        if clean_collection and not (
            (clean_collection == "unfiled" and not collection_ids) or clean_collection in collection_ids
        ):
            continue

        asset_parent = str(asset.get("primary_parent") or "Other")
        asset_subcategory = str(asset.get("primary_subcategory") if asset.get("primary_subcategory") is not None else "General")
        asset_sources = [source for source in asset.get("sources") or [] if isinstance(source, dict)]
        log_match = not clean_log_path or any(
            str(source.get("source_path") or "").replace("\\", "/").strip().casefold() == clean_log_path
            for source in asset_sources
        )
        home_match = (
            (not clean_parent or asset_parent.casefold() == clean_parent)
            and (not clean_subcategory or asset_subcategory.casefold() == clean_subcategory)
            and log_match
        )
        asset_facets = asset.get("facets") if isinstance(asset.get("facets"), dict) else {}
        facet_values = {
            axis: [str(value or "Other") for value in (asset_facets.get(axis) or ["Other"])]
            for axis in PROMPT_FILTER_AXES
        }
        failed_facets = {
            axis for axis, selected in selected_facets.items()
            if selected and selected not in facet_values[axis]
        }
        all_facets_match = not failed_facets
        asset_placeholders = {
            token for token in str(asset.get("placeholder_signature") or "").upper().split("+") if token
        }
        selected_placeholders_match = placeholders_match(asset_placeholders, selected_placeholders)

        if home_match and selected_placeholders_match:
            for axis in PROMPT_FILTER_AXES:
                if failed_facets - {axis}:
                    continue
                bucket = facet_counts[axis]
                for label in facet_values[axis]:
                    bucket[label] = bucket.get(label, 0) + 1
        if all_facets_match and selected_placeholders_match:
            home_counts["parents"][asset_parent] = home_counts["parents"].get(asset_parent, 0) + 1
            bucket = home_counts["subcategories"].setdefault(asset_parent, {})
            bucket[asset_subcategory] = bucket.get(asset_subcategory, 0) + 1
            seen_source_paths: set[str] = set()
            for source in asset_sources:
                source_path = str(source.get("source_path") or "").replace("\\", "/").strip()
                if not source_path or source_path in seen_source_paths:
                    continue
                seen_source_paths.add(source_path)
                label = _single_line_recipe_prompt(source.get("source_label")) or Path(source_path).stem
                log_bucket = home_counts["logs"].setdefault(asset_parent, {}).setdefault(asset_subcategory, {})
                row = log_bucket.setdefault(source_path, {"label": label, "count": 0})
                row["count"] = int(row.get("count") or 0) + 1
        if home_match and all_facets_match:
            for token, candidate in placeholder_candidates.items():
                if placeholders_match(asset_placeholders, candidate):
                    placeholder_available[token] += 1
        if home_match and all_facets_match and selected_placeholders_match:
            visible.append(asset)

    _sort_prompt_assets(visible, sort, log_path)
    return {
        "visible": visible,
        "facet_counts": facet_counts,
        "home_counts": home_counts,
        "placeholder_available_counts": placeholder_available,
    }


def _cached_prompt_filter_metadata(
    snapshot: dict[str, Any], kind: str, assets: list[dict[str, Any]], filters: dict[str, Any],
) -> dict[str, Any]:
    facets = filters.get("facets") if isinstance(filters.get("facets"), dict) else {}
    key = (
        *(snapshot.get("revision") or ("", "", "")),
        str(kind), str(filters.get("query") or ""), str(filters.get("source") or ""),
        str(filters.get("collection") or ""), str(filters.get("sort") or ""),
        bool(filters.get("blueprint_only")), str(filters.get("signature") or ""),
        tuple(str(value) for value in filters.get("placeholders") or []),
        str(filters.get("parent") or ""), str(filters.get("subcategory") or ""), str(filters.get("log_path") or ""),
        str(filters.get("rating") or ""), bool(filters.get("include_archived")),
        tuple((axis, str(facets.get(axis) or "")) for axis in PROMPT_FILTER_AXES),
    )
    cached = _PROMPT_FILTER_METADATA_CACHE.get(key)
    if cached is not None:
        return cached
    result = _prompt_filter_metadata(assets, **filters)
    _PROMPT_FILTER_METADATA_CACHE[key] = result
    while len(_PROMPT_FILTER_METADATA_CACHE) > 48:
        _PROMPT_FILTER_METADATA_CACHE.pop(next(iter(_PROMPT_FILTER_METADATA_CACHE)))
    return result


def _prepare_prompt_import(values: list[Any], parent: str, subcategory: str) -> dict[str, Any]:
    """Normalize a pasted log and route every line by placeholder content."""
    clean_parent = _single_line_recipe_prompt(parent)
    clean_subcategory = _single_line_recipe_prompt(subcategory)
    if not clean_parent:
        raise ValueError("Choose a Category")
    if len(values or []) > PROMPT_IMPORT_LIMIT:
        raise ValueError(f"One import is limited to {PROMPT_IMPORT_LIMIT:,} lines")
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    prompt_items: list[dict[str, Any]] = []
    template_items: list[dict[str, Any]] = []
    blank = duplicate = safety_excluded = 0
    for line_number, raw in enumerate(values or [], 1):
        value = _single_line_recipe_prompt(raw)
        if not value:
            blank += 1
            continue
        key = value.casefold()
        if key in seen:
            duplicate += 1
            continue
        seen.add(key)
        if re.search(r"\bchild\b", value, re.IGNORECASE):
            safety_excluded += 1
            continue
        kind = "template" if _creative_library_is_template_text(value) else "prompt"
        facets = _prompt_facets(value)
        facets["parent"] = [clean_parent]
        if clean_subcategory:
            facets["subcategory"] = [clean_subcategory]
        item = {
            "value": value,
            "kind": kind,
            "placeholder_signature": _placeholder_signature(value) if kind == "template" else "",
            "facets": facets,
            "source_line": line_number,
        }
        items.append(item)
        (template_items if kind == "template" else prompt_items).append(item)
    return {
        "items": items,
        "prompt_items": prompt_items,
        "template_items": template_items,
        "submitted": len(values or []),
        "blank": blank,
        "input_duplicates": duplicate,
        "safety_excluded": safety_excluded,
        "template_routed": len(template_items),
        "prompt_routed": len(prompt_items),
        "parent": clean_parent,
        "subcategory": clean_subcategory,
    }


def _imported_prompt_log_root() -> Path | None:
    try:
        import folder_paths
        return Path(folder_paths.get_input_directory()) / "SickOllieLogs" / "prompts" / IMPORTED_PROMPT_LOG_FOLDER
    except Exception:
        return None


def _safe_prompt_log_component(value: Any, fallback: str) -> str:
    clean = _single_line_recipe_prompt(value) or fallback
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip(" .")
    return (clean[:120].strip(" .") or fallback)


def _save_imported_prompt_log(raw_text: str, parent: str, subcategory: str, log_name: str) -> tuple[str, Path]:
    root = _imported_prompt_log_root()
    if root is None:
        raise ValueError("ComfyUI input directory is unavailable")
    clean_parent = _safe_prompt_log_component(parent, "Imported")
    clean_log = _safe_prompt_log_component(log_name, "Imported Log")
    folder = root / clean_parent
    if _single_line_recipe_prompt(subcategory):
        folder = folder / _safe_prompt_log_component(subcategory, "General")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{clean_log}.txt"
    if target.exists():
        base = target.stem
        counter = 2
        while target.exists():
            target = folder / f"{base} ({counter}).txt"
            counter += 1
    text = str(raw_text or "")
    target.write_text(text if text.endswith("\n") or not text else text + "\n", encoding="utf-8")
    relative = str(target.relative_to(root.parent)).replace("\\", "/")
    return relative, target


def _managed_prompt_roots() -> tuple[Path, Path]:
    try:
        import folder_paths
        prompt_root = Path(folder_paths.get_input_directory()) / "SickOllieLogs" / "prompts"
    except Exception as error:
        raise ValueError("ComfyUI input directory is unavailable") from error
    return prompt_root, prompt_root / CURATED_PROMPT_CORPUS_FOLDER


def _path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _resolve_managed_prompt_source(source_path: str, *, must_exist: bool = True) -> Path:
    clean = str(source_path or "").replace("\\", "/").strip().lstrip("/")
    relative = Path(clean)
    if not clean or relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Prompt Log path is invalid")
    prompt_root, corpus_root = _managed_prompt_roots()
    candidates = [prompt_root / relative, corpus_root / relative]
    allowed = [prompt_root / IMPORTED_PROMPT_LOG_FOLDER, corpus_root]
    for candidate in candidates:
        if not any(_path_inside(candidate, root) for root in allowed):
            continue
        if candidate.is_file() or not must_exist:
            return candidate
    if must_exist:
        raise ValueError("The source TXT file no longer exists")
    return candidates[0]


def _managed_prompt_source_name(path: Path) -> str:
    prompt_root, corpus_root = _managed_prompt_roots()
    if _path_inside(path, corpus_root):
        return str(path.resolve(strict=False).relative_to(corpus_root.resolve(strict=False))).replace("\\", "/")
    if _path_inside(path, prompt_root / IMPORTED_PROMPT_LOG_FOLDER):
        return str(path.resolve(strict=False).relative_to(prompt_root.resolve(strict=False))).replace("\\", "/")
    raise ValueError("Prompt Log is outside the managed source folders")


def _rename_prompt_source_file(source_path: str, label: str) -> dict[str, Any]:
    clean_label = _safe_prompt_log_component(label, "")
    if not clean_label:
        raise ValueError("Source Log name is required")
    source = _resolve_managed_prompt_source(source_path)
    target = source.with_name(f"{clean_label}.txt")
    same_target = source.resolve(strict=False) == target.resolve(strict=False)
    if target.exists() and not same_target:
        raise ValueError("A TXT file with that Log name already exists in this folder")
    old_name = str(source_path or "").replace("\\", "/").strip()
    next_name = _managed_prompt_source_name(target)
    if same_target:
        changed = get_catalog().rename_prompt_source_log(old_name, clean_label)
    else:
        source.replace(target)
        try:
            changed = get_catalog().move_prompt_source_log(old_name, next_name, clean_label)
            if not changed:
                raise ValueError("That Prompt Log is no longer referenced by the library")
        except Exception:
            if target.exists() and not source.exists():
                target.replace(source)
            raise
    if not changed:
        raise ValueError("That Prompt Log is no longer referenced by the library")
    return {"changed": changed, "source_path": next_name, "label": clean_label}


def _stage_prompt_deletions(paths: set[Path]) -> tuple[list[tuple[Path, Path]], int]:
    existing = sorted({path.resolve(strict=False) for path in paths if path.exists()}, key=lambda value: len(value.parts))
    top_level: list[Path] = []
    for path in existing:
        if any(_path_inside(path, parent) for parent in top_level):
            continue
        top_level.append(path)
    text_files = sum(1 for path in top_level for _ in ([path] if path.is_file() and path.suffix.casefold() == ".txt" else path.rglob("*.txt") if path.is_dir() else []))
    staged: list[tuple[Path, Path]] = []
    try:
        for original in top_level:
            temporary = original.with_name(f".{original.name}.sickollie-delete-{uuid.uuid4().hex}")
            original.replace(temporary)
            staged.append((temporary, original))
    except Exception:
        for temporary, original in reversed(staged):
            if temporary.exists() and not original.exists():
                temporary.replace(original)
        raise
    return staged, text_files


def _rollback_prompt_deletions(staged: list[tuple[Path, Path]]) -> None:
    for temporary, original in reversed(staged):
        if temporary.exists() and not original.exists():
            temporary.replace(original)


def _finish_prompt_deletions(staged: list[tuple[Path, Path]]) -> None:
    for temporary, _original in staged:
        if temporary.is_dir():
            shutil.rmtree(temporary)
        else:
            temporary.unlink(missing_ok=True)


def _prune_empty_prompt_source_folders() -> None:
    prompt_root, corpus_root = _managed_prompt_roots()
    roots = (
        prompt_root / IMPORTED_PROMPT_LOG_FOLDER,
        corpus_root / "Prompts",
        corpus_root / "Templates",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for directory in sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda value: len(value.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass


def _scope_prompt_source_paths(kind: str, parent: str, subcategory: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    clean_kind = "template" if str(kind or "").casefold() == "template" else "prompt"
    clean_parent = _single_line_recipe_prompt(parent)
    clean_subcategory = None if subcategory is None else _single_line_recipe_prompt(subcategory)
    if not clean_parent:
        raise ValueError("Category is required")
    assets = get_catalog().indexed_prompt_assets()
    scoped = [
        asset for asset in assets
        if str(asset.get("kind") or "prompt") == clean_kind
        and str(asset.get("primary_parent") or "") == clean_parent
        and (clean_subcategory is None or str(asset.get("primary_subcategory") or "") == clean_subcategory)
    ]
    source_paths = {
        str(source.get("source_path") or "").replace("\\", "/").strip()
        for asset in scoped for source in asset.get("sources") or [] if isinstance(source, dict)
    }
    return assets, scoped, {value for value in source_paths if value}


def _delete_prompt_structure_scope(kind: str, parent: str, subcategory: str | None = None) -> dict[str, Any]:
    clean_kind = "template" if str(kind or "").casefold() == "template" else "prompt"
    clean_parent = _safe_prompt_log_component(parent, "")
    clean_subcategory = None if subcategory is None else _safe_prompt_log_component(subcategory, "")
    if not clean_parent or (subcategory is not None and not clean_subcategory):
        raise ValueError("A valid Category and Subcategory are required")
    assets, scoped, source_paths = _scope_prompt_source_paths(clean_kind, parent, subcategory)
    prompt_root, corpus_root = _managed_prompt_roots()
    paths: set[Path] = set()
    for source_path in source_paths:
        try:
            paths.add(_resolve_managed_prompt_source(source_path))
        except ValueError:
            continue
    imported_target = prompt_root / IMPORTED_PROMPT_LOG_FOLDER / clean_parent
    corpus_target = corpus_root / ("Templates" if clean_kind == "template" else "Prompts") / clean_parent
    if clean_subcategory is None:
        paths.update((imported_target, corpus_target))
    else:
        paths.update((imported_target / clean_subcategory, corpus_target / clean_subcategory, corpus_target / f"{clean_subcategory}.txt"))
    # Include every record sourced by a TXT that is about to disappear.  Mixed
    # Prompt/Template logs are one canonical file, so deleting that file is a
    # deliberate cross-tab deletion rather than leaving dangling records.
    physical_sources = set(source_paths)
    for target in list(paths):
        files = [target] if target.is_file() else list(target.rglob("*.txt")) if target.is_dir() else []
        for file_path in files:
            try:
                physical_sources.add(_managed_prompt_source_name(file_path))
            except ValueError:
                pass
    scoped_ids = {str(asset.get("prompt_id") or "") for asset in scoped}
    affected = [
        asset for asset in assets
        if str(asset.get("prompt_id") or "") in scoped_ids
        or any(str(source.get("source_path") or "").replace("\\", "/").strip() in physical_sources for source in asset.get("sources") or [] if isinstance(source, dict))
    ]
    staged, text_files = _stage_prompt_deletions(paths)
    try:
        result = get_catalog().hard_delete_prompt_assets([str(asset.get("prompt_id") or "") for asset in affected])
    except Exception:
        _rollback_prompt_deletions(staged)
        raise
    _finish_prompt_deletions(staged)
    _prune_empty_prompt_source_folders()
    previews_deleted = 0
    for preview_ref in result.get("preview_refs") or []:
        target = _preview_directory() / Path(str(preview_ref)).name
        if target.is_file():
            target.unlink(missing_ok=True)
            previews_deleted += 1
    return {
        "deleted": int(result.get("deleted") or 0),
        "txt_files_deleted": text_files,
        "previews_deleted": previews_deleted,
        "source_paths": sorted(physical_sources),
    }


def _delete_prompt_source_file(source_path: str) -> dict[str, Any]:
    clean_path = str(source_path or "").replace("\\", "/").strip()
    assets = get_catalog().indexed_prompt_assets()
    affected = [
        asset for asset in assets
        if any(str(source.get("source_path") or "").replace("\\", "/").strip() == clean_path for source in asset.get("sources") or [] if isinstance(source, dict))
    ]
    paths: set[Path] = set()
    try:
        paths.add(_resolve_managed_prompt_source(clean_path))
    except ValueError:
        if not affected:
            raise
    staged, text_files = _stage_prompt_deletions(paths)
    try:
        result = get_catalog().hard_delete_prompt_assets([str(asset.get("prompt_id") or "") for asset in affected])
    except Exception:
        _rollback_prompt_deletions(staged)
        raise
    _finish_prompt_deletions(staged)
    _prune_empty_prompt_source_folders()
    previews_deleted = 0
    for preview_ref in result.get("preview_refs") or []:
        target = _preview_directory() / Path(str(preview_ref)).name
        if target.is_file(): target.unlink(missing_ok=True); previews_deleted += 1
    return {"changed": len(affected), "deleted": int(result.get("deleted") or 0), "txt_files_deleted": text_files, "previews_deleted": previews_deleted, "source_path": clean_path}


def _creative_prompt_log_root(prompt_root: Path | str | None = None) -> Path | None:
    if prompt_root is not None:
        return Path(prompt_root)
    try:
        import folder_paths
        return Path(folder_paths.get_input_directory()) / "SickOllieLogs" / "prompts" / CREATIVE_PROMPT_LOG_FOLDER
    except Exception:
        return None


def _sync_creative_prompt_asset_logs(
    prompt_root: Path | str | None = None,
    recipes: list[dict[str, Any]] | None = None,
    collections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    root = _creative_prompt_log_root(prompt_root)
    if root is None:
        return {"ok": False, "reason": "ComfyUI input directory is unavailable"}
    catalog = get_catalog() if recipes is None or collections is None else None
    recipe_rows = list(recipes if recipes is not None else catalog.recipes())
    collection_rows = list(collections if collections is not None else catalog.recipe_collections())
    # Explicit roots are used by compatibility callers/tests that expect only
    # saved recipe output. Runtime sync writes the complete canonical catalog.
    if prompt_root is not None:
        assets = [item for item in _recipe_prompt_assets(recipe_rows) if str(item.get("kind") or "prompt") == "prompt"]
        templates: list[dict[str, Any]] = []
    else:
        snapshot = _prompt_asset_snapshot()
        assets = [item for item in snapshot["prompts"] if not item.get("archived")]
        templates = [item for item in snapshot["templates"] if not item.get("archived")]
    root.mkdir(parents=True, exist_ok=True)
    collection_root = root / CREATIVE_PROMPT_COLLECTION_FOLDER
    collection_root.mkdir(parents=True, exist_ok=True)
    changed = 0
    removed_catalog_files = 0
    master_content = "\n".join(item["value"] for item in assets) + ("\n" if assets else "")
    if _write_text_if_changed(root / CREATIVE_PROMPT_MASTER_FILE, master_content):
        changed += 1

    # Prompt Core reads these generated masters instead of raw historical log
    # filenames.  Each catalog home remains a stable selectable folder.
    for label, records in (("Prompts", assets), ("Templates", templates)):
        catalog_root = root / label
        catalog_root.mkdir(parents=True, exist_ok=True)
        targets: dict[Path, str] = {catalog_root / f"All {label}.txt": "\n".join(item["value"] for item in records) + ("\n" if records else "")}
        grouped: dict[tuple[str, str], list[str]] = {}
        for item in records:
            parent = _safe_recipe_log_component(str(item.get("primary_parent") or "Other"))
            subcategory = _safe_recipe_log_component(str(item.get("primary_subcategory") or "Other"))
            grouped.setdefault((parent, subcategory), []).append(str(item.get("value") or ""))
        for (parent, subcategory), values in grouped.items():
            targets[catalog_root / f"{parent}.txt"] = "\n".join(sum((lines for (p, _), lines in grouped.items() if p == parent), [])) + "\n"
            targets[catalog_root / parent / f"{subcategory}.txt"] = "\n".join(values) + "\n"
        for path, content in targets.items():
            if _write_text_if_changed(path, content): changed += 1
        desired_targets = {path.resolve(strict=False) for path in targets}
        for existing in catalog_root.rglob("*.txt"):
            if existing.resolve(strict=False) in desired_targets:
                continue
            existing.unlink(missing_ok=True)
            removed_catalog_files += 1
        for directory in sorted(
            (path for path in catalog_root.rglob("*") if path.is_dir()),
            key=lambda value: len(value.parts), reverse=True,
        ):
            try:
                directory.rmdir()
            except OSError:
                pass

    recipe_collection_map: dict[str, set[str]] = {}
    for recipe in recipe_rows:
        recipe_collection_map[str(recipe.get("recipe_id") or "")] = {
            str((entry or {}).get("collection_id") or "") for entry in (recipe.get("collections") or []) if str((entry or {}).get("collection_id") or "")
        }
    desired: set[str] = set()
    used_names: set[str] = set()
    for collection in sorted(collection_rows, key=lambda item: str(item.get("name") or "").casefold()):
        collection_id = str(collection.get("collection_id") or "")
        base = _safe_recipe_log_component(str(collection.get("name") or "Collection"))
        filename = f"{base}.txt"
        folded = filename.casefold()
        if folded in used_names:
            suffix = re.sub(r"[^a-fA-F0-9]", "", collection_id)[-6:] or "copy"
            filename = f"{base} - {suffix}.txt"
            folded = filename.casefold()
        used_names.add(folded); desired.add(folded)
        lines = []
        for asset in assets:
            source_ids = [str(value or "") for value in asset.get("recipe_ids") or []]
            direct_ids = {
                str((entry or {}).get("collection_id") or "")
                for entry in asset.get("collections") or [] if str((entry or {}).get("collection_id") or "")
            }
            if collection_id in direct_ids or any(collection_id in recipe_collection_map.get(recipe_id, set()) for recipe_id in source_ids):
                lines.append(asset["value"])
        content = "\n".join(lines) + ("\n" if lines else "")
        if _write_text_if_changed(collection_root / filename, content):
            changed += 1
    removed = 0
    for path in collection_root.glob("*.txt"):
        if path.name.casefold() not in desired:
            path.unlink(missing_ok=True); removed += 1
    return {
        "ok": True,
        "master_file": f"prompts/{CREATIVE_PROMPT_LOG_FOLDER}/{CREATIVE_PROMPT_MASTER_FILE}",
        "master_prompts": len(assets),
        "collection_files": len(collection_rows),
        "changed_files": changed,
        "removed_files": removed + removed_catalog_files,
        "removed_catalog_files": removed_catalog_files,
    }


def _safe_recipe_log_component(value: str, fallback: str = "Collection") -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', " - ", str(value or ""))
    clean = re.sub(r"\s+", " ", clean).strip().rstrip(". ")
    if not clean:
        clean = fallback
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if clean.upper() in reserved:
        clean = f"{clean}_"
    return clean[:120].rstrip(". ") or fallback


def _recipe_prompt_log_root(prompt_root: Path | str | None = None) -> Path | None:
    if prompt_root is not None:
        return Path(prompt_root)
    try:
        import folder_paths
        return Path(folder_paths.get_input_directory()) / "SickOllieLogs" / "prompts" / RECIPE_PROMPT_LOG_FOLDER
    except Exception:
        return None


def _write_text_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            return False
    except Exception:
        pass
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)
    return True


def _sync_recipe_prompt_logs(
    prompt_root: Path | str | None = None,
    recipes: list[dict[str, Any]] | None = None,
    collections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Mirror saved Recipe prompts inside the canonical Creative Library tree."""
    root = _recipe_prompt_log_root(prompt_root)
    if root is None:
        return {"ok": False, "reason": "ComfyUI input directory is unavailable"}

    catalog = get_catalog() if recipes is None or collections is None else None
    recipe_rows = list(recipes if recipes is not None else catalog.recipes())
    collection_rows = list(collections if collections is not None else catalog.recipe_collections())
    recipe_rows.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("recipe_id") or "")))

    master_prompts: list[str] = []
    prompts_by_collection: dict[str, list[str]] = {str(item.get("collection_id")): [] for item in collection_rows}
    for recipe in recipe_rows:
        prompt = _recipe_prompt_text(recipe)
        if not prompt:
            continue
        master_prompts.append(prompt)
        for collection in recipe.get("collections") or []:
            collection_id = str((collection or {}).get("collection_id") or "")
            if collection_id in prompts_by_collection:
                prompts_by_collection[collection_id].append(prompt)

    root.mkdir(parents=True, exist_ok=True)
    collection_root = root / RECIPE_PROMPT_COLLECTION_FOLDER
    collection_root.mkdir(parents=True, exist_ok=True)
    changed = 0

    master_content = "\n".join(master_prompts) + ("\n" if master_prompts else "")
    if _write_text_if_changed(root / RECIPE_PROMPT_MASTER_FILE, master_content):
        changed += 1

    desired_collection_files: set[str] = set()
    used_names: set[str] = set()
    for collection in sorted(collection_rows, key=lambda item: str(item.get("name") or "").casefold()):
        collection_id = str(collection.get("collection_id") or "")
        base = _safe_recipe_log_component(str(collection.get("name") or "Collection"))
        filename = f"{base}.txt"
        folded = filename.casefold()
        if folded in used_names:
            suffix = re.sub(r"[^a-fA-F0-9]", "", collection_id)[-6:] or "copy"
            filename = f"{base} - {suffix}.txt"
            folded = filename.casefold()
        used_names.add(folded)
        desired_collection_files.add(folded)
        lines = prompts_by_collection.get(collection_id, [])
        content = "\n".join(lines) + ("\n" if lines else "")
        if _write_text_if_changed(collection_root / filename, content):
            changed += 1

    removed = 0
    for path in collection_root.glob("*.txt"):
        if path.name.casefold() not in desired_collection_files:
            path.unlink(missing_ok=True)
            removed += 1

    retired = {"removed_files": 0, "removed_folders": 0, "retired": False}
    if prompt_root is None:
        retired = retire_legacy_generated_logs(root.parent, "prompt")
    return {
        "ok": True,
        "master_file": f"prompts/{RECIPE_PROMPT_LOG_FOLDER}/{RECIPE_PROMPT_MASTER_FILE}",
        "master_prompts": len(master_prompts),
        "collection_files": len(collection_rows),
        "changed_files": changed,
        "removed_files": removed + int(retired.get("removed_files") or 0),
        "legacy_folders_removed": int(retired.get("removed_folders") or 0),
    }


def _recipe_component_log_root(category: str, override: Path | str | None = None) -> Path | None:
    if override is not None:
        return Path(override)
    if category not in {"outfit", "scene"}:
        return None
    try:
        import folder_paths
        folder = "outfits" if category == "outfit" else "scenes"
        return Path(folder_paths.get_input_directory()) / "SickOllieLogs" / folder / RECIPE_COMPONENT_LOG_FOLDER
    except Exception:
        return None


def _component_source_log_root(category: str) -> Path | None:
    if category not in {"outfit", "scene"}:
        return None
    try:
        import folder_paths
        folder = "outfits" if category == "outfit" else "scenes"
        return Path(folder_paths.get_input_directory()) / "SickOllieLogs" / folder
    except Exception:
        return None


def _save_imported_component_log(
    raw_text: str, category: str, parent: str, subcategory: str, log_name: str,
) -> tuple[str, Path]:
    root = _component_source_log_root(category)
    if root is None:
        raise ValueError("ComfyUI input directory is unavailable")
    clean_parent = _safe_prompt_log_component(parent, "Imported")
    clean_log = _safe_prompt_log_component(log_name, "Imported Log")
    folder = root / IMPORTED_COMPONENT_LOG_FOLDER / clean_parent
    if _single_line_recipe_prompt(subcategory):
        folder = folder / _safe_prompt_log_component(subcategory, "General")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{clean_log}.txt"
    if target.exists():
        base = target.stem
        counter = 2
        while target.exists():
            target = folder / f"{base} ({counter}).txt"
            counter += 1
    text = str(raw_text or "")
    target.write_text(text if text.endswith("\n") or not text else text + "\n", encoding="utf-8")
    relative = str(target.relative_to(root)).replace("\\", "/")
    return relative, target


def _resolve_imported_component_log(category: str, relative_path: str) -> Path | None:
    root = _component_source_log_root(category)
    if root is None:
        return None
    clean = str(relative_path or "").replace("\\", "/").strip().lstrip("/")
    relative = Path(clean)
    if not clean or relative.is_absolute() or ".." in relative.parts:
        return None
    imported_root = (root / IMPORTED_COMPONENT_LOG_FOLDER).resolve(strict=False)
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(imported_root)
    except ValueError:
        return None
    return candidate


def _prune_empty_component_import_folders(category: str) -> None:
    root = _component_source_log_root(category)
    imported = root / IMPORTED_COMPONENT_LOG_FOLDER if root is not None else None
    if imported is None or not imported.is_dir():
        return
    for directory in sorted((path for path in imported.rglob("*") if path.is_dir()), key=lambda value: len(value.parts), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def _read_component_log_lines(path: Path) -> list[str]:
    text = ""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = path.read_text(encoding=encoding)
            break
        except Exception:
            continue
    seen: set[str] = set()
    lines: list[str] = []
    for raw in text.splitlines():
        line = _single_line_recipe_prompt(raw)
        folded = line.casefold()
        if line and folded not in seen:
            seen.add(folded)
            lines.append(line)
    return lines


def _classify_scene_taxonomy(value: str) -> tuple[str, str]:
    """Return the best Category/Subcategory for a scene description.

    This intentionally reads only the canonical scene text. Source filenames,
    folders, Recipe collections, and prompt provenance are never considered.
    """
    text = _single_line_recipe_prompt(value).casefold()
    if not text:
        return "", ""
    best: tuple[int, int, int, str, str] | None = None
    for category_index, category in enumerate(SCENE_TAXONOMY):
        category_patterns = tuple(category.get("patterns") or ())
        category_score = sum(1 for pattern in category_patterns if re.search(pattern, text, re.IGNORECASE))
        child_best_score = 0
        child_best_name = ""
        for child_index, child in enumerate(category.get("children") or ()):
            child_name = str(child[0])
            child_patterns = tuple(child[1] or ())
            child_score = sum(1 for pattern in child_patterns if re.search(pattern, text, re.IGNORECASE))
            if child_score > child_best_score:
                child_best_score = child_score
                child_best_name = child_name
        total = category_score * 2 + child_best_score * 3
        if total <= 0:
            continue
        # Earlier taxonomy entries win true ties. Specific child matches beat
        # broad parent-only hits via the second tuple field.
        candidate = (total, child_best_score, -category_index, str(category.get("name") or ""), child_best_name)
        if best is None or candidate[:3] > best[:3]:
            best = candidate
    if best is None:
        return "", ""
    return best[3], best[4]


def _scene_taxonomy_collection_map(catalog) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    rows = list(catalog.component_collections("scene"))
    by_id = {str(row.get("collection_id") or ""): row for row in rows}
    parents = {
        str(row.get("name") or "").casefold(): row
        for row in rows if not str(row.get("parent_id") or "")
    }
    children: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        parent_id = str(row.get("parent_id") or "")
        if not parent_id:
            continue
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        children[(str(parent.get("name") or "").casefold(), str(row.get("name") or "").casefold())] = row
    return parents, children


def _scene_taxonomy_id_map(catalog) -> dict[str, dict[str, str]]:
    """Return stable rule→collection IDs so renamed default folders keep working."""
    raw = catalog.schema_meta_value(SCENE_TAXONOMY_MAP_META_KEY, "")
    try:
        data = json.loads(raw) if raw else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        data = {}
    parents = data.get("parents") if isinstance(data, dict) else {}
    children = data.get("children") if isinstance(data, dict) else {}
    return {
        "parents": {str(k): str(v) for k, v in (parents or {}).items() if str(k) and str(v)},
        "children": {str(k): str(v) for k, v in (children or {}).items() if str(k) and str(v)},
    }


def _scene_taxonomy_target_id(catalog, parent_name: str, child_name: str = "") -> str:
    """Resolve the classifier's logical default folder without depending on its display name.

    Default Scene Biomes are editable. Their display labels may be renamed or a
    subcategory may be moved, so the automatic classifier remembers the IDs it
    created during migration. Deleted folders are never recreated implicitly.
    """
    logical_parent = str(parent_name or "").casefold()
    logical_child = str(child_name or "").casefold()
    rows = list(catalog.component_collections("scene"))
    by_id = {str(row.get("collection_id") or ""): row for row in rows}
    stable = _scene_taxonomy_id_map(catalog)
    if logical_child:
        stable_id = stable["children"].get(f"{logical_parent}::{logical_child}", "")
        if stable_id and stable_id in by_id:
            return stable_id
    stable_parent_id = stable["parents"].get(logical_parent, "")
    if stable_parent_id and stable_parent_id in by_id:
        if not logical_child:
            return stable_parent_id
        # If the original child was deliberately deleted, use the still-live
        # parent as a graceful general-category fallback rather than recreating it.
        return stable_parent_id

    # Compatibility fallback for databases created by an early preview of this
    # migration before the stable-ID map existed.
    parents, children = _scene_taxonomy_collection_map(catalog)
    parent = parents.get(logical_parent)
    if parent is None:
        return ""
    if logical_child:
        child = children.get((logical_parent, logical_child))
        if child is not None:
            return str(child.get("collection_id") or "")
    return str(parent.get("collection_id") or "")


def _classify_scene_component_into_existing_taxonomy(catalog, component: dict[str, Any]) -> list[str]:
    component_id = str(component.get("component_id") or "")
    if not component_id or bool(component.get("tombstoned")):
        return []
    current = next(
        (row for row in catalog.recipe_components("scene") if str(row.get("component_id") or "") == component_id),
        None,
    )
    existing_ids = [str(item.get("collection_id") or "") for item in (current or {}).get("collections") or [] if str(item.get("collection_id") or "")]
    if existing_ids:
        # Once a user has organized a Scene, automatic classification becomes
        # hands-off. Re-importing a legacy TXT must not erase custom placement.
        return existing_ids
    parent_name, child_name = _classify_scene_taxonomy(str(component.get("value") or ""))
    if not parent_name:
        return []
    target_id = _scene_taxonomy_target_id(catalog, parent_name, child_name)
    if not target_id:
        return []
    catalog.set_component_collections(component_id, [target_id])
    return [target_id]


def _ensure_scene_taxonomy(catalog=None) -> dict[str, Any]:
    """Preserve user-owned Scene taxonomy and migrate only unmistakable legacy folders.

    v3.3.25 no longer seeds Scene categories into an empty Creative Library.
    Existing v3.3.24 taxonomy lives in user data and is left alone. Imported or
    manually-created taxonomies are also authoritative. The old destructive
    biome migration remains only for unmistakable pre-taxonomy ``*.txt`` folder
    records so an ordinary load can never overwrite a portable pack's structure.
    """
    catalog = catalog or get_catalog()
    current = catalog.schema_meta_value(SCENE_TAXONOMY_META_KEY)
    if current == SCENE_TAXONOMY_VERSION:
        return {"ok": True, "migrated": False, "version": current}

    components = list(catalog.recipe_components("scene"))
    existing_collections = list(catalog.component_collections("scene"))
    legacy_collection_names = [
        str(row.get("name") or "") for row in existing_collections
        if str(row.get("name") or "").strip().casefold().endswith(".txt")
    ]

    # Empty/new databases and imported/user-created taxonomies are already the
    # desired architecture: there is nothing built in to create. Record any
    # exact legacy default-name IDs that already exist so the text classifier can
    # continue following those folders if users later rename them.
    if not components or not legacy_collection_names:
        by_id = {str(row.get("collection_id") or ""): row for row in existing_collections}
        parents_by_name = {
            str(row.get("name") or "").casefold(): row
            for row in existing_collections if not str(row.get("parent_id") or "")
        }
        parent_ids: dict[str, str] = {}
        child_ids: dict[str, str] = {}
        for category in SCENE_TAXONOMY:
            parent_name = str(category.get("name") or "")
            parent = parents_by_name.get(parent_name.casefold())
            if parent is None:
                continue
            parent_id = str(parent.get("collection_id") or "")
            if not parent_id:
                continue
            parent_ids[parent_name.casefold()] = parent_id
            children_by_name = {
                str(row.get("name") or "").casefold(): row
                for row in existing_collections
                if str(row.get("parent_id") or "") == parent_id and str(row.get("collection_id") or "") in by_id
            }
            for child_name, _patterns in category.get("children") or ():
                child = children_by_name.get(str(child_name).casefold())
                if child is not None and str(child.get("collection_id") or ""):
                    child_ids[f"{parent_name.casefold()}::{str(child_name).casefold()}"] = str(child.get("collection_id") or "")
        catalog.set_schema_meta_value(SCENE_TAXONOMY_MAP_META_KEY, json.dumps({"parents": parent_ids, "children": child_ids}, sort_keys=True))
        catalog.set_schema_meta_value(SCENE_TAXONOMY_META_KEY, SCENE_TAXONOMY_VERSION)
        return {
            "ok": True, "migrated": False, "version": SCENE_TAXONOMY_VERSION,
            "empty_library": not components and not existing_collections,
            "preserved_collections": len(existing_collections),
        }

    legacy_collections = catalog.clear_component_collections("scene")
    parent_ids: dict[str, str] = {}
    child_ids: dict[tuple[str, str], str] = {}
    for category in SCENE_TAXONOMY:
        parent_name = str(category.get("name") or "")
        parent = catalog.create_component_collection("scene", parent_name)
        parent_id = str(parent.get("collection_id") or "")
        parent_ids[parent_name.casefold()] = parent_id
        for child_name, _patterns in category.get("children") or ():
            child = catalog.create_component_collection("scene", str(child_name), parent_id=parent_id)
            child_ids[(parent_name.casefold(), str(child_name).casefold())] = str(child.get("collection_id") or "")

    catalog.set_schema_meta_value(SCENE_TAXONOMY_MAP_META_KEY, json.dumps({
        "parents": parent_ids,
        "children": {f"{parent}::{child}": collection_id for (parent, child), collection_id in child_ids.items()},
    }, sort_keys=True))

    classified = 0
    unsorted = 0
    for component in catalog.recipe_components("scene"):
        parent_name, child_name = _classify_scene_taxonomy(str(component.get("value") or ""))
        target_id = ""
        if parent_name:
            target_id = child_ids.get((parent_name.casefold(), child_name.casefold()), "") if child_name else ""
            target_id = target_id or parent_ids.get(parent_name.casefold(), "")
        if target_id:
            catalog.set_component_collections(str(component.get("component_id") or ""), [target_id])
            classified += 1
        else:
            catalog.set_component_collections(str(component.get("component_id") or ""), [])
            unsorted += 1
    catalog.set_schema_meta_value(SCENE_TAXONOMY_META_KEY, SCENE_TAXONOMY_VERSION)
    return {
        "ok": True,
        "migrated": True,
        "version": SCENE_TAXONOMY_VERSION,
        "legacy_collections_removed": legacy_collections,
        "classified": classified,
        "unsorted": unsorted,
    }


def _scan_component_source_logs(category: str) -> list[dict[str, Any]]:
    """List existing user Outfit/Scene logs without re-importing managed masters."""
    root = _component_source_log_root(category)
    if root is None or not root.is_dir():
        return []
    results: list[dict[str, Any]] = []
    managed_names = {
        RECIPE_COMPONENT_LOG_FOLDER.casefold(),
        LEGACY_RECIPE_LIBRARY_LOG_FOLDER.casefold(),
        IMPORTED_COMPONENT_LOG_FOLDER.casefold(),
    }
    for path in sorted(root.rglob("*.txt"), key=lambda item: str(item).casefold()):
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if relative.parts and relative.parts[0].casefold() in managed_names:
            continue
        lines = _read_component_log_lines(path)
        if not lines:
            continue
        parent_parts = list(relative.parent.parts) if str(relative.parent) != "." else []
        if category == "scene":
            suggestions = []
            seen_suggestions: set[str] = set()
            for line in lines:
                parent_name, child_name = _classify_scene_taxonomy(line)
                label = f"{parent_name} / {child_name}" if parent_name and child_name else parent_name
                if label and label.casefold() not in seen_suggestions:
                    seen_suggestions.add(label.casefold())
                    suggestions.append(label)
        else:
            suggestions = [part for part in parent_parts if part and part not in {".", ".."}]
            stem = path.stem.strip()
            if stem and stem.casefold() not in {item.casefold() for item in suggestions}:
                suggestions.append(stem)
        results.append({
            "path": str(Path("outfits" if category == "outfit" else "scenes") / relative).replace("\\", "/"),
            "relative_path": str(relative).replace("\\", "/"),
            "name": path.stem,
            "line_count": len(lines),
            "suggested_collections": suggestions,
        })
    return results


def _import_component_source_logs(category: str, relative_paths: list[str], collection_mode: str = "none") -> dict[str, Any]:
    root = _component_source_log_root(category)
    if root is None:
        raise ValueError("ComfyUI SickOllieLogs folder is unavailable")
    requested = list(dict.fromkeys(str(value or "").replace("\\", "/").strip() for value in relative_paths if str(value or "").strip()))
    if not requested:
        raise ValueError("Choose at least one log file")
    mode = str(collection_mode or "none").strip().lower()
    if mode not in {"none", "log", "folders", "both"}:
        mode = "none"
    catalog = get_catalog()
    if category == "scene":
        _ensure_scene_taxonomy(catalog)
        # Scene source filenames are provenance only.  Canonical organization
        # always comes from the actual scene description.
        mode = "taxonomy"
    existing_components = {str(item.get("value") or "").casefold(): str(item.get("component_id") or "") for item in catalog.recipe_components(category)}
    existing_collections = {str(item.get("name") or "").casefold(): str(item.get("collection_id") or "") for item in catalog.component_collections(category)}
    unique_values: dict[str, str] = {}
    component_created: dict[str, bool] = {}
    batch_memberships: set[tuple[str, str]] = set()
    batch_collections: dict[str, bool] = {}
    imported_paths: list[str] = []
    files = 0
    created_collection_ids: set[str] = set()
    memberships = 0
    for relative_value in requested:
        relative = Path(relative_value)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        expected = "outfits" if category == "outfit" else "scenes"
        if relative.parts and relative.parts[0].casefold() == expected:
            relative = Path(*relative.parts[1:])
        if relative.parts and relative.parts[0].casefold() in {
            RECIPE_COMPONENT_LOG_FOLDER.casefold(), LEGACY_RECIPE_LIBRARY_LOG_FOLDER.casefold(),
            IMPORTED_COMPONENT_LOG_FOLDER.casefold(),
        }:
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if not candidate.is_file() or candidate.suffix.casefold() != ".txt":
            continue
        files += 1
        imported_paths.append(str(relative).replace("\\", "/"))
        file_component_ids: list[str] = []
        for line in _read_component_log_lines(candidate):
            key = line.casefold()
            unique_values.setdefault(key, line)
            existed = key in existing_components
            component = catalog.upsert_recipe_component(category, line, manual=True)
            component_id = str(component.get("component_id") or "")
            if component_id:
                file_component_ids.append(component_id)
                component_created[component_id] = component_created.get(component_id, False) or not existed
                existing_components.setdefault(key, component_id)
                if category == "scene":
                    before = next((row for row in catalog.recipe_components("scene") if str(row.get("component_id") or "") == component_id), None)
                    before_ids = {str(item.get("collection_id") or "") for item in (before or {}).get("collections") or []}
                    assigned_ids = _classify_scene_component_into_existing_taxonomy(catalog, component)
                    memberships += len([collection_id for collection_id in assigned_ids if collection_id not in before_ids])
        collection_names: list[str] = []
        if category != "scene" and mode in {"folders", "both"}:
            collection_names.extend(part for part in relative.parent.parts if part and part not in {".", ".."})
        if category != "scene" and mode in {"log", "both"}:
            stem = candidate.stem.strip()
            if stem:
                collection_names.append(stem)
        collection_names = list(dict.fromkeys(name for name in collection_names if name))
        for name in collection_names:
            folded_name = name.casefold()
            collection_was_new = folded_name not in existing_collections
            collection = catalog.create_component_collection(category, name)
            collection_id = str(collection.get("collection_id") or "")
            if not collection_id:
                continue
            existing_collections.setdefault(folded_name, collection_id)
            created_collection_ids.add(collection_id)
            batch_collections[collection_id] = batch_collections.get(collection_id, False) or collection_was_new
            prior_members = catalog.component_collection_member_ids(collection_id)
            result = catalog.add_components_to_collections(file_component_ids, [collection_id])
            memberships += int(result.get("memberships_added") or 0)
            for component_id in set(file_component_ids) - prior_members:
                batch_memberships.add((component_id, collection_id))
    if not files:
        raise ValueError("None of the selected log files could be imported")
    batch = catalog.record_component_import_batch(
        kind=category,
        source_paths=imported_paths,
        collection_mode=mode,
        items=list(component_created.items()),
        memberships=list(batch_memberships),
        collections=list(batch_collections.items()),
    )
    _safe_sync_recipe_prompt_logs()
    return {
        "files": files,
        "values": len(unique_values),
        "unique_values": len(unique_values),
        "new_values": int(batch.get("new_count") or 0),
        "existing_values": int(batch.get("matched_count") or 0),
        "collections": len(created_collection_ids),
        "memberships_added": memberships,
        "batch_id": str(batch.get("batch_id") or ""),
    }


def _import_component_text_log(
    category: str,
    raw_text: str,
    parent: str,
    subcategory: str,
    log_name: str,
    *,
    collection_id: str = "",
    collection_name: str = "",
) -> dict[str, Any]:
    """Import a pasted/local component log into one structural home.

    The selected local file is read by the browser; this backend receives only
    its text and saves a managed copy. Exact values are reused, while the
    Category → optional Subcategory home and optional shareable collection are
    tracked in the reversible import batch.
    """

    kind = str(category or "").strip().casefold()
    if kind not in {"outfit", "scene"}:
        raise ValueError("Log kind must be outfit or scene")
    clean_parent = _single_line_recipe_prompt(parent)
    clean_subcategory = _single_line_recipe_prompt(subcategory)
    clean_log_name = _single_line_recipe_prompt(log_name)
    if not clean_parent:
        raise ValueError("Choose a Category")
    if not clean_log_name:
        raise ValueError("Add a Log name")
    if len(clean_parent) > 80 or len(clean_subcategory) > 80:
        raise ValueError("Category and Subcategory names are limited to 80 characters")
    clean_collection_id = str(collection_id or "").strip()
    clean_collection_name = _single_line_recipe_prompt(collection_name)
    if len(clean_collection_name) > 80:
        raise ValueError("Shareable Collection names are limited to 80 characters")
    raw_lines = str(raw_text or "").splitlines()
    if len(raw_lines) > PROMPT_IMPORT_LIMIT:
        raise ValueError(f"One import is limited to {PROMPT_IMPORT_LIMIT:,} lines")
    values: list[str] = []
    seen: set[str] = set()
    blank = input_duplicates = 0
    for raw in raw_lines:
        value = _single_line_recipe_prompt(raw)
        if not value:
            blank += 1
            continue
        key = value.casefold()
        if key in seen:
            input_duplicates += 1
            continue
        seen.add(key)
        values.append(value)
    if not values:
        raise ValueError(f"No {kind.title()} values remained after cleanup")

    source_path, saved_target = _save_imported_component_log(
        raw_text, kind, clean_parent, clean_subcategory, clean_log_name,
    )
    catalog = get_catalog()
    try:
        available_shareable = catalog.library_collections(kind)
        shareable: dict[str, Any] | None = None
        if clean_collection_id:
            shareable = next(
                (row for row in available_shareable if str(row.get("collection_id") or "") == clean_collection_id),
                None,
            )
            if shareable is None:
                raise ValueError("The selected shareable collection no longer exists")
        structural = catalog.component_collections(kind)
        same_parent_name = [
            row for row in structural
            if str(row.get("name") or "").casefold() == clean_parent.casefold()
        ]
        parent_row = next((row for row in same_parent_name if not str(row.get("parent_id") or "")), None)
        if parent_row is None and same_parent_name:
            raise ValueError(f"A subcategory named ‘{clean_parent}’ already exists; choose another Category name")
        parent_created = parent_row is None
        if parent_row is None:
            parent_row = catalog.create_component_collection(kind, clean_parent)
        parent_id = str(parent_row.get("collection_id") or "")
        if not parent_id:
            raise ValueError("Could not create the selected Category")

        leaf_row = parent_row
        leaf_created = parent_created
        if clean_subcategory:
            structural = catalog.component_collections(kind)
            same_child_name = [
                row for row in structural
                if str(row.get("name") or "").casefold() == clean_subcategory.casefold()
            ]
            leaf_row = next(
                (row for row in same_child_name if str(row.get("parent_id") or "") == parent_id),
                None,
            )
            if leaf_row is None and same_child_name:
                raise ValueError(f"A folder named ‘{clean_subcategory}’ already exists in another Category")
            leaf_created = leaf_row is None
            if leaf_row is None:
                leaf_row = catalog.create_component_collection(kind, clean_subcategory, parent_id=parent_id)
        leaf_id = str(leaf_row.get("collection_id") or "")

        existing_components = {
            str(item.get("value") or "").casefold(): str(item.get("component_id") or "")
            for item in catalog.recipe_components(kind)
        }
        component_created: dict[str, bool] = {}
        component_ids: list[str] = []
        for value in values:
            existed = value.casefold() in existing_components
            component = catalog.upsert_recipe_component(kind, value, manual=True)
            component_id_value = str(component.get("component_id") or "")
            if not component_id_value:
                continue
            component_ids.append(component_id_value)
            component_created[component_id_value] = component_created.get(component_id_value, False) or not existed
            existing_components.setdefault(value.casefold(), component_id_value)

        batch_memberships: set[tuple[str, str]] = set()
        prior_members = catalog.component_collection_member_ids(leaf_id)
        previous_homes = {
            str(row["component_id"]): [str(home["collection_id"]) for home in row.get("collections") or []]
            for row in catalog.recipe_components(kind) if str(row["component_id"]) in component_ids
        }
        structural_result = catalog.move_components_home(component_ids, leaf_id)
        for component_id_value in set(component_ids) - prior_members:
            batch_memberships.add((component_id_value, leaf_id))

        batch_collections: dict[str, bool] = {parent_id: parent_created}
        if leaf_id != parent_id:
            batch_collections[leaf_id] = leaf_created

        shareable_created = False
        shareable_memberships = 0
        if not clean_collection_id and clean_collection_name:
            shareable = next(
                (row for row in available_shareable if str(row.get("name") or "").casefold() == clean_collection_name.casefold()),
                None,
            )
            if shareable is None:
                shareable_created = True
                shareable = catalog.create_library_collection(kind, clean_collection_name)
        if shareable is not None:
            shareable_id = str(shareable.get("collection_id") or "")
            prior_shareable = set(str(value) for value in shareable.get("asset_ids") or [])
            shareable_result = catalog.add_library_assets_to_collections(kind, component_ids, [shareable_id])
            shareable_memberships = int(shareable_result.get("memberships_added") or 0)
            for component_id_value in set(component_ids) - prior_shareable:
                batch_memberships.add((component_id_value, shareable_id))
            batch_collections[shareable_id] = shareable_created

        batch = catalog.record_component_import_batch(
            kind=kind,
            source_paths=[source_path],
            collection_mode="managed-log",
            items=list(component_created.items()),
            memberships=list(batch_memberships),
            collections=list(batch_collections.items()),
        )
        catalog.set_schema_meta_json(f"component_import_previous_homes:{batch['batch_id']}", {
            "target": leaf_id, "homes": previous_homes,
        })
        _safe_sync_recipe_prompt_logs()
        return {
            "files": 1,
            "values": len(component_created),
            "new_values": int(batch.get("new_count") or 0),
            "existing_values": int(batch.get("matched_count") or 0),
            "blank": blank,
            "input_duplicates": input_duplicates,
            "parent": clean_parent,
            "subcategory": clean_subcategory,
            "folder_id": leaf_id,
            "log_name": clean_log_name,
            "source_path": source_path,
            "saved_copy": saved_target.name,
            "collection": shareable,
            "memberships_added": int(structural_result.get("memberships_added") or 0) + shareable_memberships,
            "batch_id": str(batch.get("batch_id") or ""),
        }
    except Exception:
        try:
            saved_target.unlink(missing_ok=True)
            _prune_empty_component_import_folders(kind)
        except OSError:
            pass
        raise


def _component_from_log_reference(relative_path: str, index_value: Any, category: str) -> str:
    value = canonical_log_reference(relative_path, category)
    expected = "outfits" if category == "outfit" else "scenes"
    if not value or value in {"[None]", "None"}:
        return ""
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != expected:
        return ""
    try:
        import folder_paths
        root = (Path(folder_paths.get_input_directory()) / "SickOllieLogs").resolve()
    except Exception:
        return ""
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return ""
    if not candidate.is_file():
        return ""
    text = ""
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            text = candidate.read_text(encoding=encoding)
            break
        except Exception:
            continue
    lines = [_single_line_recipe_prompt(line) for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    try:
        index = int(index_value) % len(lines)
    except Exception:
        index = 0
    return lines[index]


def _recipe_resolved_component_values(recipe: dict[str, Any], category: str) -> list[str]:
    """Return concrete outfit/scene values represented by a saved recipe.

    New Studio outputs embed the exact resolved component lines in the recipe
    summary. Older prompt recipes can still be recovered from their fixed log
    file + index when that source log remains available.
    """
    payload = recipe.get("payload") if isinstance(recipe, dict) else None
    if not isinstance(payload, dict) or category not in {"outfit", "scene"}:
        return []

    collected: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        line = _single_line_recipe_prompt(value)
        folded = line.casefold()
        if line and folded not in seen:
            seen.add(folded)
            collected.append(line)

    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    placeholders = summary.get("placeholders") if isinstance(summary.get("placeholders"), list) else []
    for item in placeholders:
        if not isinstance(item, dict):
            continue
        widget_name = str(item.get("widget") or "")
        token = str(item.get("token") or "").upper()
        if category == "outfit":
            is_match = widget_name.startswith("outfit_log_file_") or token == "OUTFIT" or token.startswith("OUTFIT_")
        else:
            is_match = widget_name == "scene_log_file" or token == "SCENE"
        if is_match:
            add(item.get("value"))

    # Schema-4 Creative Library captures and structured image imports store only
    # components that actually participated in the resolved prompt inside
    # summary.placeholders.  Treat that list as authoritative.  Falling back to
    # the configured log widget for these modern records can incorrectly attach
    # a selected-but-unused SCENE/OUTFIT to a Recipe.
    schema = int(payload.get("schema") or 0) if str(payload.get("schema") or "").isdigit() else 0
    placeholders_are_authoritative = bool(payload.get("structured_metadata")) or (schema >= 4 and isinstance(summary.get("placeholders"), list))
    if placeholders_are_authoritative:
        return collected

    # Legacy compatibility: older Recipes did not record reliable component-use
    # state, so recover their fixed log selection when the source log still
    # exists.  This path is deliberately skipped for modern Recipes above.
    values = _recipe_node_values(payload, STUDIO_PROMPT, include_optional=True)
    if category == "outfit":
        for letter in "ABC":
            add(_component_from_log_reference(
                values.get(f"outfit_log_file_{letter}", ""),
                values.get(f"outfit_index_{letter}", 0),
                "outfit",
            ))
    else:
        add(_component_from_log_reference(values.get("scene_log_file", ""), values.get("scene_index", 0), "scene"))
    return collected


def _recipe_component_assets(
    recipes: list[dict[str, Any]],
    category: str,
    stored_components: list[dict[str, Any]] | None = None,
    tombstoned_values: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Build stable visual assets from recipes plus persistent manual/catalog state."""
    ordered = sorted(recipes, key=lambda item: (str(item.get("created_at") or ""), str(item.get("recipe_id") or "")))
    stored_rows = list(stored_components or [])
    tombstoned = {str(value or "").casefold() for value in (tombstoned_values or set()) if str(value or "")}
    stored_by_value = {str(item.get("value") or "").casefold(): item for item in stored_rows if str(item.get("kind") or category) == category}
    by_value: dict[str, dict[str, Any]] = {}
    for recipe in ordered:
        for value in _recipe_resolved_component_values(recipe, category):
            key = value.casefold()
            if key in tombstoned:
                continue
            existing = by_value.get(key)
            if existing is not None:
                existing["uses"] += 1
                continue
            stored = stored_by_value.get(key) or {}
            catalog_preview = str(stored.get("preview_ref") or "")
            source_preview = str(recipe.get("preview_ref") or "")
            by_value[key] = {
                "component_id": str(stored.get("component_id") or ""),
                "kind": category,
                "value": value,
                "uses": 1,
                "manual": bool(stored.get("manual")),
                "recipe_id": str(recipe.get("recipe_id") or ""),
                "recipe_name": str(recipe.get("name") or "Recipe"),
                # Recipe previews remain provenance only.  Outfit/Scene cards
                # display their own Catalog thumbnail or a true missing state,
                # never an unrelated generation image.
                "source_preview_ref": source_preview,
                "catalog_preview_ref": catalog_preview,
                "preview_ref": catalog_preview,
                "preview_source": str(stored.get("preview_source") or "") if catalog_preview else "",
                "preview_updated_at": str(stored.get("preview_updated_at") or stored.get("updated_at") or "") if catalog_preview else "",
                "collections": list(stored.get("collections") or []),
                "pack_collections": list(stored.get("pack_collections") or []),
                "rating": max(0, min(5, int(stored.get("rating") or 0))),
                "created_at": str(recipe.get("created_at") or stored.get("created_at") or ""),
                "updated_at": str(stored.get("updated_at") or recipe.get("updated_at") or recipe.get("created_at") or ""),
            }

    # Manual assets are a bootstrap path for users who have no existing Outfit/
    # Scene logs yet. They participate in master logs immediately and later merge
    # naturally with the same text if a recipe uses them.
    for stored in stored_rows:
        if str(stored.get("kind") or "") != category or not bool(stored.get("manual")):
            continue
        value = _single_line_recipe_prompt(stored.get("value"))
        key = value.casefold()
        if key in tombstoned:
            continue
        if not value or key in by_value:
            if key in by_value:
                by_value[key]["manual"] = True
                if not by_value[key].get("component_id"):
                    by_value[key]["component_id"] = str(stored.get("component_id") or "")
                if stored.get("collections"):
                    by_value[key]["collections"] = list(stored.get("collections") or [])
                by_value[key]["rating"] = max(0, min(5, int(stored.get("rating") or by_value[key].get("rating") or 0)))
            continue
        catalog_preview = str(stored.get("preview_ref") or "")
        by_value[key] = {
            "component_id": str(stored.get("component_id") or ""),
            "kind": category,
            "value": value,
            "uses": 0,
            "manual": True,
            "recipe_id": "",
            "recipe_name": "Manual Library asset",
            "source_preview_ref": "",
            "catalog_preview_ref": catalog_preview,
            "preview_ref": catalog_preview,
            "preview_source": str(stored.get("preview_source") or "") if catalog_preview else "",
            "preview_updated_at": str(stored.get("preview_updated_at") or stored.get("updated_at") or "") if catalog_preview else "",
            "collections": list(stored.get("collections") or []),
                "pack_collections": list(stored.get("pack_collections") or []),
            "rating": max(0, min(5, int(stored.get("rating") or 0))),
            "created_at": str(stored.get("created_at") or ""),
            "updated_at": str(stored.get("updated_at") or stored.get("created_at") or ""),
        }

    assets = list(by_value.values())
    for index, asset in enumerate(assets):
        asset["index"] = index
    return assets


def _sync_one_component_log_family(
    category: str,
    root: Path,
    recipes: list[dict[str, Any]],
    component_collections: list[dict[str, Any]],
    stored_components: list[dict[str, Any]] | None = None,
    tombstoned_values: set[str] | None = None,
) -> dict[str, Any]:
    master_file = RECIPE_OUTFIT_MASTER_FILE if category == "outfit" else RECIPE_SCENE_MASTER_FILE
    assets = _recipe_component_assets(recipes, category, stored_components, tombstoned_values)
    root.mkdir(parents=True, exist_ok=True)
    collection_root = root / RECIPE_COMPONENT_COLLECTION_FOLDER
    if category == "outfit":
        collection_root.mkdir(parents=True, exist_ok=True)
    changed = 0

    master_content = "\n".join(item["value"] for item in assets) + ("\n" if assets else "")
    if _write_text_if_changed(root / master_file, master_content):
        changed += 1

    desired_files: set[str] = set()
    used_names: set[str] = set()
    # Scene taxonomy is persistent database/UI organization. It intentionally
    # does not create another forest of TXT "homes". Prompt Core needs only the
    # one canonical de-duplicated master log for exact value loading.
    export_collections = component_collections if category == "outfit" else []
    for collection in sorted(export_collections, key=lambda item: str(item.get("name") or "").casefold()):
        collection_id = str(collection.get("collection_id") or "")
        base = _safe_recipe_log_component(str(collection.get("name") or "Collection"))
        filename = f"{base}.txt"
        folded = filename.casefold()
        if folded in used_names:
            suffix = re.sub(r"[^a-fA-F0-9]", "", collection_id)[-6:] or "copy"
            filename = f"{base} - {suffix}.txt"
            folded = filename.casefold()
        used_names.add(folded)
        desired_files.add(folded)
        member_assets = [
            asset for asset in assets
            if any(str((entry or {}).get("collection_id") or "") == collection_id for entry in (asset.get("collections") or []))
        ]
        content = "\n".join(item["value"] for item in member_assets) + ("\n" if member_assets else "")
        if _write_text_if_changed(collection_root / filename, content):
            changed += 1

    removed = 0
    for path in collection_root.glob("*.txt"):
        if path.name.casefold() not in desired_files:
            path.unlink(missing_ok=True)
            removed += 1
    if category == "scene" and collection_root.is_dir():
        # The old Scene collection-log folder was a competing second "home".
        # Once its stale TXT files are removed, drop the directory too when empty.
        try:
            collection_root.rmdir()
        except OSError:
            pass

    folder = "outfits" if category == "outfit" else "scenes"
    retired = {"removed_files": 0, "removed_folders": 0, "retired": False}
    if root.name.casefold() != LEGACY_RECIPE_LIBRARY_LOG_FOLDER.casefold():
        try:
            retired = retire_legacy_generated_logs(root.parent, category)
        except OSError:
            pass
    return {
        "ok": True,
        "category": category,
        "master_file": f"{folder}/{RECIPE_COMPONENT_LOG_FOLDER}/{master_file}",
        "count": len(assets),
        "collection_count": len(component_collections),
        "collection_files": len(export_collections),
        "changed_files": changed,
        "removed_files": removed + int(retired.get("removed_files") or 0),
        "legacy_folders_removed": int(retired.get("removed_folders") or 0),
    }


def _sync_recipe_component_logs(
    outfit_root: Path | str | None = None,
    scene_root: Path | str | None = None,
    recipes: list[dict[str, Any]] | None = None,
    collections: list[dict[str, Any]] | None = None,
    components_by_kind: dict[str, list[dict[str, Any]]] | None = None,
    component_collections_by_kind: dict[str, list[dict[str, Any]]] | None = None,
    tombstones_by_kind: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    # `collections` is retained for call compatibility with older internal/tests,
    # but component log families are now driven only by Outfit/Scene collections.
    catalog = get_catalog() if recipes is None or components_by_kind is None else None
    recipe_rows = list(recipes if recipes is not None else catalog.recipes())
    if components_by_kind is None:
        if catalog is None:
            component_rows = {"outfit": [], "scene": []}
        else:
            component_rows = {kind: catalog.recipe_components(kind) for kind in ("outfit", "scene")}
    else:
        component_rows = components_by_kind

    if tombstones_by_kind is None:
        if catalog is not None:
            tombstone_rows = {
                kind: {str(row.get("value") or "").casefold() for row in catalog.component_tombstones(kind)}
                for kind in ("outfit", "scene")
            }
        else:
            tombstone_rows = {"outfit": set(), "scene": set()}
    else:
        tombstone_rows = tombstones_by_kind

    if component_collections_by_kind is None:
        if catalog is not None:
            component_collection_rows = {kind: catalog.component_collections(kind) for kind in ("outfit", "scene")}
        else:
            component_collection_rows = {}
            for kind in ("outfit", "scene"):
                seen: dict[str, dict[str, Any]] = {}
                for component in component_rows.get(kind) or []:
                    for collection in component.get("collections") or []:
                        collection_id = str((collection or {}).get("collection_id") or "")
                        if collection_id:
                            seen.setdefault(collection_id, dict(collection))
                component_collection_rows[kind] = list(seen.values())
    else:
        component_collection_rows = component_collections_by_kind

    results: dict[str, Any] = {"ok": True}
    for category, override in (("outfit", outfit_root), ("scene", scene_root)):
        root = _recipe_component_log_root(category, override)
        if root is None:
            results[category] = {"ok": False, "reason": "ComfyUI input directory is unavailable"}
            results["ok"] = False
            continue
        results[category] = _sync_one_component_log_family(
            category,
            root,
            recipe_rows,
            list(component_collection_rows.get(category) or []),
            list(component_rows.get(category) or []),
            set(tombstone_rows.get(category) or set()),
        )
    return results


def _ensure_derived_component_records(recipes: list[dict[str, Any]]) -> None:
    catalog = get_catalog()
    _ensure_scene_taxonomy(catalog)
    for category in ("outfit", "scene"):
        for recipe in recipes:
            for value in _recipe_resolved_component_values(recipe, category):
                component = catalog.upsert_recipe_component(category, value, manual=False)
                if category == "scene" and not bool(component.get("tombstoned")):
                    _classify_scene_component_into_existing_taxonomy(catalog, component)


def _safe_sync_recipe_component_logs(**kwargs) -> dict[str, Any]:
    """Refresh Outfit/Scene compatibility logs without turning a successful catalog mutation into a 500."""
    try:
        return _sync_recipe_component_logs(**kwargs)
    except Exception as error:
        print(f"[Sick Ollie Creative Library] Could not refresh generated Outfit/Scene logs: {error}")
        return {"ok": False, "error": str(error)}


def _safe_sync_recipe_prompt_logs(**kwargs) -> dict[str, Any]:
    try:
        prompt_result = _sync_recipe_prompt_logs(**kwargs)
        catalog = get_catalog()
        recipe_rows = list(kwargs.get("recipes") if kwargs.get("recipes") is not None else catalog.recipes())
        collection_rows = list(kwargs.get("collections") if kwargs.get("collections") is not None else catalog.recipe_collections())
        creative_prompt_result = _sync_creative_prompt_asset_logs(
            recipes=recipe_rows,
            collections=catalog.prompt_showcase_collections("prompt"),
        )
        _ensure_derived_component_records(recipe_rows)
        component_result = _sync_recipe_component_logs(
            recipes=recipe_rows,
            collections=collection_rows,
            components_by_kind={kind: catalog.recipe_components(kind) for kind in ("outfit", "scene")},
            component_collections_by_kind={kind: catalog.component_collections(kind) for kind in ("outfit", "scene")},
            tombstones_by_kind={
                kind: {str(row.get("value") or "").casefold() for row in catalog.component_tombstones(kind)}
                for kind in ("outfit", "scene")
            },
        )
        return {**prompt_result, "ready_prompts": creative_prompt_result, "components": component_result}
    except Exception as error:
        print(f"[Sick Ollie Creative Library] Could not refresh generated Creative Library logs: {error}")
        return {"ok": False, "error": str(error)}


_LIBRARY_SYNC_CACHE: dict[str, Any] = {"key": None, "value": None}
_DERIVED_VALUE_CACHE: dict[str, Any] = {"key": None, "value": None}


def _sync_library_if_stale(
    recipes: list[dict[str, Any]] | None = None,
    collections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Refresh generated compatibility logs once per canonical recipe revision."""
    catalog = get_catalog()
    key = (str(catalog.path), catalog.recipe_revision(), catalog.prompt_revision())
    if _LIBRARY_SYNC_CACHE.get("key") == key and isinstance(_LIBRARY_SYNC_CACHE.get("value"), dict):
        return _LIBRARY_SYNC_CACHE["value"]
    recipe_rows = list(recipes if recipes is not None else catalog.recipes())
    collection_rows = list(collections if collections is not None else catalog.recipe_collections())
    result = _safe_sync_recipe_prompt_logs(recipes=recipe_rows, collections=collection_rows)
    _LIBRARY_SYNC_CACHE.update({"key": (str(catalog.path), catalog.recipe_revision(), catalog.prompt_revision()), "value": result})
    return result


def _derived_value_snapshot(kind: str = "", *, sync_logs: bool = True) -> dict[str, Any]:
    catalog = get_catalog()
    clean_kind = str(kind or "").strip().casefold()
    if clean_kind not in {"outfit", "scene"}:
        clean_kind = ""
    if clean_kind in {"", "scene"}:
        _ensure_scene_taxonomy(catalog)
    key = (str(catalog.path), catalog.recipe_revision(), catalog.component_revision(), clean_kind, bool(sync_logs))
    if _DERIVED_VALUE_CACHE.get("key") == key and isinstance(_DERIVED_VALUE_CACHE.get("value"), dict):
        return _DERIVED_VALUE_CACHE["value"]
    recipes = catalog.recipes()
    sync = _sync_library_if_stale(recipes=recipes, collections=catalog.recipe_collections()) if sync_logs else {}
    key = (str(catalog.path), catalog.recipe_revision(), catalog.component_revision(), clean_kind, bool(sync_logs))
    kinds = (clean_kind,) if clean_kind else ("outfit", "scene")
    stored = {value_kind: catalog.recipe_components(value_kind) for value_kind in kinds}
    tombstones = {
        value_kind: {str(row.get("value") or "").casefold() for row in catalog.component_tombstones(value_kind)}
        for value_kind in kinds
    }
    component_sync = sync.get("components") if isinstance(sync, dict) else {}
    outfit_sync = component_sync.get("outfit") if isinstance(component_sync, dict) else {}
    scene_sync = component_sync.get("scene") if isinstance(component_sync, dict) else {}
    result = {
        "ok": True,
        "logs": {
            "outfit": str((outfit_sync or {}).get("master_file") or f"outfits/{RECIPE_COMPONENT_LOG_FOLDER}/{RECIPE_OUTFIT_MASTER_FILE}"),
            "scene": str((scene_sync or {}).get("master_file") or f"scenes/{RECIPE_COMPONENT_LOG_FOLDER}/{RECIPE_SCENE_MASTER_FILE}"),
        },
    }
    if "outfit" in stored:
        result["outfits"] = _recipe_component_assets(recipes, "outfit", stored["outfit"], tombstones.get("outfit", set()))
    if "scene" in stored:
        result["scenes"] = _recipe_component_assets(recipes, "scene", stored["scene"], tombstones.get("scene", set()))
    _DERIVED_VALUE_CACHE.update({"key": key, "value": result})
    return result


def _recipe_tokens(payload: dict[str, Any]) -> list[str]:
    prompt_texts: list[str] = []
    for node in payload.get("nodes", []):
        if not isinstance(node, dict) or str(node.get("type", "")) != STUDIO_PROMPT:
            continue
        widgets = node.get("widgets")
        if isinstance(widgets, list):
            for widget in widgets:
                if isinstance(widget, dict) and widget.get("name") in {"manual_prompt", "saved_prompt", "prefix_text", "suffix_text"}:
                    prompt_texts.append(str(widget.get("value") or ""))
    text = "\n".join(prompt_texts)
    tokens = set(TOKEN_PATTERN.findall(text))
    if "ITEM" in tokens:
        tokens.add("BRAND")
    if any(token == "OUTFIT" or token.startswith("OUTFIT_") for token in tokens):
        tokens.add("OUTFIT")
    return sorted(tokens)


LIBRARY_PREVIEW_MAX_EDGE = 2048
LIBRARY_PREVIEW_MAX_BYTES = 512 * 1024


def _encode_library_preview(image: Image.Image) -> bytes:
    """Preserve aspect/detail without upscaling; cap high-entropy files too."""
    preview = ImageOps.exif_transpose(image).convert("RGB")
    preview.thumbnail((LIBRARY_PREVIEW_MAX_EDGE, LIBRARY_PREVIEW_MAX_EDGE), Image.Resampling.LANCZOS)
    while True:
        for quality in (82, 76, 70):
            buffer = BytesIO()
            preview.save(buffer, "WEBP", quality=quality, method=6)
            encoded = buffer.getvalue()
            if len(encoded) <= LIBRARY_PREVIEW_MAX_BYTES:
                return encoded
        # Grain/noise may defeat quality-only compression. Reduce dimensions
        # gently instead of crushing the image with extremely low quality.
        size = (max(1, round(preview.width * .85)), max(1, round(preview.height * .85)))
        if size == preview.size:
            raise ValueError("Could not encode preview within the file-size budget")
        preview = preview.resize(size, Image.Resampling.LANCZOS)


def _write_library_preview(image: Image.Image, target: Path) -> None:
    encoded = _encode_library_preview(image)
    # A failed encode/write must not destroy a previously working preview.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".preview-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _save_preview(image: Image.Image, preview_name: str) -> str:
    filename = f"{preview_name}.webp"
    _write_library_preview(image, _preview_directory() / filename)
    return filename


_CLEANUP_JOIN_WORDS = {
    "a", "an", "the", "and", "with", "plus", "paired", "pair", "worn", "wearing", "featuring",
    "including", "include", "includes", "together", "complete", "outfit", "look",
}
_CLEANUP_PROMPT_MARKERS = {
    "camera", "lens", "flash", "lighting", "photograph", "photo", "portrait", "framing", "composition",
    "background", "seamless", "bokeh", "depth", "gaze", "expression", "looking", "standing", "sitting",
    "kneeling", "closeup", "close-up", "cinematic", "editorial", "shot",
}


def _cleanup_tokens(value: str) -> list[str]:
    text = str(value or "").casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [token for token in text.split() if token and token not in _CLEANUP_JOIN_WORDS]


def _cleanup_component_report(assets: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    """Return deterministic cleanup candidates without mutating the library."""
    rows = [item for item in assets if str(item.get("component_id") or "")]
    short: list[dict[str, Any]] = []
    long_rows: list[dict[str, Any]] = []
    prompt_like: list[dict[str, Any]] = []
    sequence_groups: dict[str, list[dict[str, Any]]] = {}
    bag_groups: dict[str, list[dict[str, Any]]] = {}
    token_rows: list[tuple[dict[str, Any], tuple[str, ...]]] = []

    for item in rows:
        value = _single_line_recipe_prompt(item.get("value"))
        words = value.split()
        compact = {"component_id": str(item.get("component_id") or ""), "value": value, "manual": bool(item.get("manual")), "uses": int(item.get("uses") or 0), "rating": max(0, min(5, int(item.get("rating") or 0)))}
        if len(words) <= 2 or len(value) < 14:
            short.append(compact)
        if len(words) >= 48 or len(value) >= 280:
            long_rows.append(compact)
        raw_tokens = set(re.findall(r"[A-Za-z0-9-]+", value.casefold()))
        marker_hits = sorted(raw_tokens & _CLEANUP_PROMPT_MARKERS)
        if len(marker_hits) >= 2:
            prompt_like.append({**compact, "markers": marker_hits[:6]})

        tokens = _cleanup_tokens(value)
        unique_tokens = tuple(sorted(set(tokens)))
        if len(unique_tokens) >= 3:
            token_rows.append((compact, unique_tokens))
        if len(tokens) >= 3:
            sequence_key = " ".join(tokens)
            bag_key = " ".join(sorted(tokens))
            sequence_groups.setdefault(sequence_key, []).append(compact)
            bag_groups.setdefault(bag_key, []).append(compact)

    groups: list[dict[str, Any]] = []
    seen_sets: set[tuple[str, ...]] = set()
    for mode, source in (("normalized wording", sequence_groups), ("same word set", bag_groups)):
        for members in source.values():
            if len(members) < 2:
                continue
            ids = tuple(sorted(str(item["component_id"]) for item in members))
            if ids in seen_sets:
                continue
            seen_sets.add(ids)
            groups.append({"mode": mode, "items": members})
    # High-overlap deterministic matching catches the common case where two
    # outfits differ by one modifier (for example ``white socks`` vs
    # ``white ankle socks``) without doing an O(n^2) comparison over a 7k+
    # library.  Each value contributes its full token set plus one-token-drop
    # signatures. Shared signatures become review candidates, then a strict
    # Jaccard threshold keeps loose wardrobe families out of the dupe bucket.
    signature_groups: dict[tuple[str, ...], list[tuple[dict[str, Any], tuple[str, ...]]]] = {}
    for compact, token_set in token_rows:
        if len(token_set) < 5 or len(token_set) > 24:
            continue
        signature_groups.setdefault(token_set, []).append((compact, token_set))
        for index in range(len(token_set)):
            signature = token_set[:index] + token_set[index + 1:]
            if len(signature) >= 4:
                signature_groups.setdefault(signature, []).append((compact, token_set))
        if len(token_set) <= 12:
            for first in range(len(token_set) - 1):
                for second in range(first + 1, len(token_set)):
                    signature = tuple(token for idx, token in enumerate(token_set) if idx not in {first, second})
                    if len(signature) >= 4:
                        signature_groups.setdefault(signature, []).append((compact, token_set))

    for signature, entries in signature_groups.items():
        by_component: dict[str, tuple[dict[str, Any], tuple[str, ...]]] = {}
        for compact, token_set in entries:
            by_component[str(compact["component_id"])] = (compact, token_set)
        if len(by_component) < 2 or len(by_component) > 12:
            continue
        values = list(by_component.values())
        accepted: list[dict[str, Any]] = []
        base_tokens = set(values[0][1])
        for compact, token_set in values:
            current = set(token_set)
            union = base_tokens | current
            overlap = len(base_tokens & current) / max(1, len(union))
            if overlap >= 0.72:
                accepted.append(compact)
        if len(accepted) < 2:
            continue
        ids = tuple(sorted(str(item["component_id"]) for item in accepted))
        if ids in seen_sets:
            continue
        seen_sets.add(ids)
        groups.append({"mode": "high-overlap wording", "items": accepted, "core": " ".join(signature)})

    groups.sort(key=lambda group: ({"same word set": 0, "normalized wording": 1, "high-overlap wording": 2}.get(str(group.get("mode") or ""), 3), -len(group.get("items") or []), str((group.get("items") or [{}])[0].get("value") or "").casefold()))

    return {
        "ok": True,
        "kind": kind,
        "total": len(rows),
        "short": short,
        "very_long": long_rows,
        "prompt_like": prompt_like,
        "near_duplicate_groups": groups[:250],
        "near_duplicate_group_count": len(groups),
    }



WARDROBE_PARSER_VERSION = "wardrobe-v6"
_WARDROBE_HEADS: list[tuple[str, str, str]] = [
    # Coordinated sets must be recognized before their component nouns.
    (r"(?:matching |coordinated |lace |satin |mesh |sheer |balconette |bra |lingerie |pajama |sleepwear |bikini |swim |two[- ]piece )*(?:lingerie|bra|balconette|pajama|sleepwear|bikini|swim|two[- ]piece) sets?", "Matching Sets", "Coordinated Sets"),
    (r"(?:matching |coordinated |soft |cotton |flannel |printed |pink |blue |lavender )*pajamas\b", "Matching Sets", "Sleepwear Sets"),
    (r"corset tops?", "Tops", "Tanks & Camis"),
    (r"bra tops?", "Tops", "Tanks & Camis"),
    (r"bandeau(?: tops?)?", "Tops", "Tanks & Camis"),
    (r"rash tops?", "Tops", "Tees"),
    (r"bralette tops?", "Tops", "Tanks & Camis"),
    (r"bikini tops?", "Tops", "Tanks & Camis"),
    (r"turtlenecks?", "Tops", "Sweaters"),
    (r"mary janes?", "Footwear", "Flats & Mary Janes"),
    (r"(?:platform |low-top |high-top |canvas |reflective )?sneakers?", "Footwear", "Sneakers"),
    (r"(?:combat |cowboy |rain |platform |knee-high |thigh-high |ankle )?boots?", "Footwear", "Boots"),
    (r"(?:kitten |stiletto |platform |ankle-strap |wrap |patent |clear |chrome |strappy )?heels?", "Footwear", "Heels"),
    (r"stilettos?", "Footwear", "Heels"),
    (r"loafers?", "Footwear", "Flats & Mary Janes"),
    (r"(?:ballet )?flats?", "Footwear", "Flats & Mary Janes"),
    (r"(?:house |fuzzy )?slippers?", "Footwear", "Slippers"),
    (r"(?:platform |strappy |leather |clear )?sandals?", "Footwear", "Sandals"),
    (r"flip[- ]?flops?", "Footwear", "Sandals"),
    (r"(?:platform |heeled |feathered |patent |velvet )?mules?", "Footwear", "Heels"),
    (r"pumps?", "Footwear", "Heels"),
    (r"(?:buckle |platform |canvas |patent )?shoes?", "Footwear", "Flats & Mary Janes"),
    (r"(?:ankle|crew|knee-high|knee|thigh-high|tube|athletic|ruffle|lace|slouchy|striped|scrunched)?\s*socks?", "Legwear", ""),
    (r"(?:thigh-high |thigh high |seamed |sheer |fishnet |garter |nylon |lace |white |black )?stockings?", "Legwear", "Stockings"),
    (r"thigh[- ]highs?", "Legwear", "Thigh-Highs"),
    (r"pantyhose", "Legwear", "Tights"),
    (r"(?:sheer |fishnet |black |white )?tights?", "Legwear", "Tights"),
    (r"(?:black |white |ribbed |cotton |sheer |mesh |lace )?leggings?", "Legwear", "Tights"),
    (r"leg warmers?", "Legwear", "Leg Warmers"),
    (r"fishnets?", "Legwear", "Tights"),
    (r"(?:denim |bike |micro |boy|boxer|sleep|pajama|running|athletic|high-waisted|low-rise|cotton|lace|latex|vinyl|fitted|tiny|soft|cutoff|cut-offs? )*shorts", "Bottoms", "Shorts"),
    (r"(?:denim )?cutoffs?", "Bottoms", "Shorts"),
    (r"skorts?", "Bottoms", "Shorts"),
    (r"(?:skirted )?swim bottoms?", "Bottoms", "Underwear Bottoms"),
    (r"(?:mini |micro |pleated |denim |wrap |tulle |pencil |tennis |skater |satin |latex |plaid )?skirts?", "Bottoms", "Skirts"),
    (r"jeans?", "Bottoms", "Jeans"),
    (r"(?:cargo |yoga |track |sweat|wide-leg |leather |latex |cotton )*pants?", "Bottoms", "Pants"),
    (r"(?:bikini |retro |high-waisted |high-rise |cotton |lace |latex |satin |simple |tiny |black |white |red |pink |navy |color block |ribbed )*(?:briefs?|panties|thongs?|boyshorts?|bloomers?)", "Bottoms", "Underwear Bottoms"),
    (r"(?:bikini |swim |high-waisted |low-rise |micro |matching )?bottoms?", "Bottoms", "Underwear Bottoms"),
    (r"(?:sheer |mesh |wrap |beach )?sarongs?", "Bottoms", "Skirts"),
    (r"(?:mini |slip |babydoll |sweater |halter |shirt |corset |bandage |wrap |skater |bodycon |mesh |satin |lace |knit |tulle |cocktail |tank |tee |picnic |sun|sundress |off-shoulder |overall )*dress(?:es)?", "Dresses & One-Pieces", "Dresses"),
    (r"(?:gingham |cotton |soft |frilled |lace |satin )*nightdress(?:es)?", "Dresses & One-Pieces", "Dresses"),
    (r"(?:mini |mesh |satin |lace |sheer |evening |ball |slip )*gowns?", "Dresses & One-Pieces", "Dresses"),
    (r"(?:soft |frilled |lace |satin |silk |sheer |yellow |pink |blue )*nightgowns?", "Dresses & One-Pieces", "Dresses"),
    (r"(?:soft |frilled |lace |satin |silk |sheer |yellow |pink |blue )*nighties?", "Dresses & One-Pieces", "Dresses"),
    (r"rompers?", "Dresses & One-Pieces", "Rompers"),
    (r"(?:pin-up |retro |satin |cotton |denim )*playsuits?", "Dresses & One-Pieces", "Rompers"),
    (r"jumpsuits?", "Dresses & One-Pieces", "Jumpsuits"),
    (r"(?:denim |corduroy |bib |short |striped |paint-splattered )*overalls?", "Dresses & One-Pieces", "Jumpsuits"),
    (r"bodysuits?", "Bodywear", "Bodysuits"),
    (r"leotards?", "Bodywear", "Leotards"),
    (r"tedd(?:y|ies)", "Bodywear", "Teddies"),
    (r"catsuits?", "Bodywear", "Catsuits"),
    (r"corsets?", "Bodywear", "Corsets & Bustiers"),
    (r"bustiers?", "Bodywear", "Corsets & Bustiers"),
    (r"balconettes?", "Bodywear", "Corsets & Bustiers"),
    (r"bralettes?", "Bodywear", "Corsets & Bustiers"),
    (r"bras?", "Bodywear", "Corsets & Bustiers"),
    (r"(?:triangle |string |micro |iridescent )?bikinis?", "Bodywear", "Bodysuits"),
    (r"(?:one-piece )?swimsuits?", "Bodywear", "Bodysuits"),
    (r"babydolls?", "Bodywear", "Teddies"),
    (r"(?:slip |satin |lace |mesh )?chemises?", "Bodywear", "Chemises & Slips"),
    (r"(?:satin |silk |lace |mesh |sheer |black |white |pink |mini )?slips?", "Bodywear", "Chemises & Slips"),
    (r"(?:crop |cropped |tank |halter |tube |mesh |knit |baby |ribbed |fitted |graphic |vinyl |latex |long-sleeve |sleeveless )*tops?", "Tops", ""),
    (r"(?:baby |ringer |graphic |ribbed |cropped |oversized |fitted |band |sailor-collar )*tees?", "Tops", "Tees"),
    (r"(?:short-sleeve |long-sleeve |soft |sleep |pajama |fitted |ribbed )*henleys?", "Tops", "Tees"),
    (r"(?:cropped |crop |fitted |short-sleeve |long-sleeve |baby )*polos?(?:\s+crop)?", "Tops", "Tees"),
    (r"(?:pajama |sleep |relaxed |oversized |soft )*button[- ]ups?(?!\s+shirts?\b)", "Tops", "Shirts & Blouses"),
    (r"(?:tank tops?|tanks?|camisoles?|camis?|camisole)", "Tops", "Tanks & Camis"),
    (r"blouses?", "Tops", "Shirts & Blouses"),
    (r"(?:button-up |button-down |flannel |oversized |dress |sheer )*shirts?", "Tops", "Shirts & Blouses"),
    (r"(?:oversized |soft |plaid )?flannels?", "Tops", "Shirts & Blouses"),
    (r"(?:mesh |sports? |oversized |loose )?jerseys?", "Tops", "Tees"),
    (r"sweaters?", "Tops", "Sweaters"),
    (r"hoodies?", "Layers", "Hoodies & Sweatshirts"),
    (r"sweatshirts?", "Layers", "Hoodies & Sweatshirts"),
    (r"pullovers?", "Layers", "Hoodies & Sweatshirts"),
    (r"cardigans?", "Layers", "Cardigans"),
    (r"shrugs?", "Layers", "Cardigans"),
    (r"jackets?", "Layers", "Jackets"),
    (r"blazers?", "Layers", "Jackets"),
    (r"windbreakers?", "Layers", "Jackets"),
    (r"raincoats?|coats?", "Layers", "Coats"),
    (r"robes?", "Layers", "Robes"),
    (r"capelets?|capes?", "Layers", "Jackets"),
    (r"vests?", "Layers", "Jackets"),
    (r"(?:body|hip|waist) chains?", "Accessories", "Body Chains"),
    (r"collar chokers?", "Accessories", "Chokers & Collars"),
    (r"chokers?", "Accessories", "Chokers & Collars"),
    (r"(?:leather |lace |metal |velvet |jeweled |black |white )?collars?", "Accessories", "Chokers & Collars"),
    (r"necklaces?|anklets?|bracelets?|earrings?", "Accessories", "Jewelry"),
    (r"harness(?:es)?", "Accessories", "Harnesses"),
    (r"gloves?", "Accessories", "Gloves"),
    (r"arm warmers?", "Accessories", "Arm Warmers"),
    (r"(?:garter |waist |leather |chain )*belts?", "Accessories", "Belts"),
    (r"suspenders?", "Accessories", "Belts"),
    (r"hair ribbons?|hair bows?|headbands?|sunhats?|caps?|hats?", "Accessories", "Headwear"),
    (r"(?:cat[- ]?ear )?headsets?", "Accessories", "Headwear"),
    (r"(?:ankle chains?|toe rings?)", "Accessories", "Jewelry"),
    (r"aprons?", "Layers", "Aprons"),
    (r"scar(?:f|ves)|sunglasses|wristbands?", "Accessories", "Jewelry"),
    # Singular 'garter' and generic 'cuffs' are often construction details of the previous garment.
    (r"garters(?!\s+straps?)|garter belts?", "Accessories", "Harnesses"),
    (r"(?:wrist|leather|metal|lace) cuffs?", "Accessories", "Harnesses"),
]
_WARDROBE_HEAD_RE = re.compile("|".join(f"(?P<h{index}>(?<![A-Za-z])(?:{pattern})(?![A-Za-z]))" for index, (pattern, _, __) in enumerate(_WARDROBE_HEADS)), re.IGNORECASE)
_WARDROBE_FINISHERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bcompletely (?:naked|bare) everywhere else\b", re.IGNORECASE), "completely naked everywhere else"),
    (re.compile(r"\bbare everywhere else\b", re.IGNORECASE), "bare everywhere else"),
    (re.compile(r"\botherwise (?:completely )?(?:naked|bare)\b", re.IGNORECASE), "otherwise bare"),
    (re.compile(r"\bbare legs\b", re.IGNORECASE), "bare legs"),
    (re.compile(r"\bwhile barefoot\b|\bbarefoot\b|\bbare feet\b|\bno shoes\b", re.IGNORECASE), "barefoot"),
]
_WARDROBE_SEPARATORS = [
    " layered over ", " worn over ", " paired with ", " finished with ", " tucked into ", " alongside ", " over ", " under ",
    ", and ", " and ", ", ", " with ",
]
_WARDROBE_SET_CATEGORIES = {"Tops", "Bottoms", "Bodywear"}
_WARDROBE_GENERIC_VALUES = {
    "top", "tank", "tank top", "tee", "t-shirt", "shirt", "blouse", "sweater", "hoodie", "sweatshirt", "cardigan",
    "jacket", "coat", "robe", "vest", "shorts", "skirt", "pants", "jeans", "briefs", "panties", "thong", "underwear",
    "dress", "romper", "jumpsuit", "bodysuit", "leotard", "teddy", "catsuit", "corset", "bustier", "bralette", "bra",
    "balconette", "bikini", "swimsuit", "chemise", "socks", "stockings", "tights", "leggings", "leg warmers", "shoes",
    "sneakers", "boots", "heels", "stilettos", "flats", "slippers", "sandals", "pumps", "gloves", "choker", "necklace",
    "bracelet", "earrings", "body chain", "harness", "belt", "hat", "headband", "garters",
}


def _wardrobe_head_class(match: re.Match[str]) -> tuple[str, str]:
    index = int(str(match.lastgroup or "h0")[1:])
    _, category, subtype = _WARDROBE_HEADS[index]
    token = match.group(0).casefold()
    if category == "Legwear" and not subtype:
        if "thigh" in token:
            return category, "Thigh-Highs"
        if "knee" in token:
            return category, "Knee Socks"
        if "ankle" in token:
            return category, "Ankle Socks"
        if "crew" in token:
            return category, "Crew Socks"
        return category, "Crew Socks"
    if category == "Tops" and not subtype:
        if any(word in token for word in ("tank", "cami")):
            return category, "Tanks & Camis"
        return category, "Tees"
    if category == "Matching Sets":
        if any(word in token for word in ("lingerie", "bra", "balconette")):
            return category, "Lingerie Sets"
        if any(word in token for word in ("pajama", "sleepwear")):
            return category, "Sleepwear Sets"
        return category, "Coordinated Sets"
    return category, subtype or "Uncategorized"


def _wardrobe_clean_phrase(value: str) -> str:
    text = str(value or "").strip(" ,.;")
    text = re.sub(r"^(?:and|with|paired with|finished with)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?:,\s*)?(?:and\s*)?$", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip(" ,.;")


def _wardrobe_value_key(value: str) -> str:
    text = _wardrobe_clean_phrase(value).casefold()
    text = re.sub(r"^(?:a|an|the)\s+", "", text)
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _wardrobe_specificity(value: str, item_type: str = "piece") -> dict[str, Any]:
    if item_type in {"finisher", "set", "styling"}:
        return {"visual_ready": True, "specificity": 1.0, "reason": ""}
    key = _wardrobe_value_key(value)
    words = key.split()
    if key in _WARDROBE_GENERIC_VALUES:
        return {"visual_ready": False, "specificity": 0.15, "reason": "generic garment name"}
    if len(words) <= 1:
        return {"visual_ready": False, "specificity": 0.2, "reason": "too generic for a stable thumbnail"}
    # A modifier + garment head is already useful: 'black tights', 'pink hoodie', 'lace gloves'.
    return {"visual_ready": True, "specificity": min(1.0, 0.55 + 0.08 * min(5, len(words))), "reason": ""}


def _wardrobe_filtered_heads(text: str) -> list[re.Match[str]]:
    matches = list(_WARDROBE_HEAD_RE.finditer(text))
    accepted: list[re.Match[str]] = []
    last_end = 0
    for match in matches:
        if accepted and match.start() < last_end:
            continue
        before = text[max(0, match.start() - 28):match.start()].casefold()
        after = text[match.end():match.end() + 20].casefold()
        if accepted and re.search(r"\bworn as a\s+$|\bused as a\s+$", before):
            continue
        # 'cuffs'/'garter straps' and similar details inside a preceding garment are not separate wardrobe items.
        token = match.group(0).casefold()
        # Do not treat a garment word used as a compound adjective as its own Piece:
        # "swimsuit-cut bodysuit" should resolve to one bodysuit.
        if match.end() < len(text) and text[match.end()] == "-" and match.end() + 1 < len(text) and text[match.end() + 1].isalpha():
            continue
        # "dress shirt" is a shirt, not a Dress + generic shirt.
        if token.endswith("dress") and re.match(r"\s+shirts?\b", after):
            continue
        if token.endswith("collar") and re.match(r"\s+chokers?\b", after):
            continue
        if accepted and token in {"collar", "collars"} and re.search(r"\b(?:with|featuring|with a|with an)\s+(?:a\s+|an\s+)?(?:relaxed|spread|pointed|rounded|wide|soft|open|notched|peter[- ]pan|shirt)\s+$", before):
            continue
        # Garment-part descriptions such as "embroidery across the sleeves and skirt"
        # belong to the preceding garment rather than becoming a new skirt Piece.
        if accepted and re.search(r"\b(?:sleeves?|bodice|hem|hood|cuffs?|neckline|collar|waist|hips?)\s+(?:and|or)\s+$", before):
            continue
        if accepted and token in {"cuffs", "cuff"} and re.search(r"\bwith\s+(?:[^,]{0,32})$", before):
            continue
        if token.startswith("garter") and after.startswith(" straps"):
            continue
        accepted.append(match)
        last_end = match.end()
    return accepted


def _wardrobe_separator_between(text: str, left_end: int, right_start: int) -> tuple[int, int, str] | None:
    middle = text[left_end:right_start]
    lowered = middle.casefold()
    candidates: list[tuple[int, int, str]] = []
    for separator in _WARDROBE_SEPARATORS:
        position = lowered.rfind(separator)
        if position >= 0:
            absolute = left_end + position
            candidates.append((absolute, absolute + len(separator), separator.strip()))
    if not candidates:
        return None
    return sorted(candidates, key=lambda value: (value[1], value[1] - value[0]), reverse=True)[0]


_WARDROBE_BODY_STYLING_RE = re.compile(
    r"(?:\bbody\s+paint\b|\bskin\s+(?:finish|gloss|sheen|treatment|glow)\b|\bbody\s+(?:gloss|finish|sheen)\b|"
    r"\b(?:tracing|across|over|around)\s+the\s+body\b)",
    re.IGNORECASE,
)
_WARDROBE_BODY_CONTEXT_RE = re.compile(r"\b(?:body|skin|torso|collarbones?|hips?|shoulders?|waist|chest|upper body|thighs?)\b", re.IGNORECASE)
_WARDROBE_BODY_STYLE_TERM_RE = re.compile(
    r"\b(?:paint|painted|markings?|sheen|gloss|glow|glowing|shimmer|glitter|iridescent|pearlescent|prismatic|radiance|"
    r"luminous|luminescent|chrome|metallic|reflective|projection|projected|laser|starfield|rhinestone|crystal|holographic|"
    r"bioluminescent|neon|uv|ultraviolet|oil-slick|mercury|foil)\b",
    re.IGNORECASE,
)


def _wardrobe_body_styling_item(value: str) -> dict[str, Any] | None:
    text = _wardrobe_clean_phrase(value)
    if not text:
        return None
    # If a concrete garment/accessory head is present, let normal wardrobe decomposition handle it.
    if _wardrobe_filtered_heads(text):
        return None
    strong = bool(_WARDROBE_BODY_STYLING_RE.search(text))
    context = bool(_WARDROBE_BODY_CONTEXT_RE.search(text))
    style_terms = len(_WARDROBE_BODY_STYLE_TERM_RE.findall(text))
    if not strong and not (context and style_terms >= 2):
        return None
    lower = text.casefold()
    if re.search(r"\b(?:body\s+paint|painted|paint|runes?|markings?|stripes?|splatter|graffiti)\b", lower):
        subtype = "Body Paint & Markings"
    elif re.search(r"\b(?:chrome|metallic|copper|silver|mirror|molten|foil|mercury)\b", lower):
        subtype = "Metallic & Chrome"
    elif re.search(r"\b(?:glitter|shimmer|iridescent|pearlescent|prismatic|crystal|luminous|luminescent|glowing|glow|radiance|laser|projected|projection|starfield)\b", lower):
        subtype = "Glow, Glitter & Shimmer"
    else:
        subtype = "Skin Finish"
    return {
        "item_type": "styling",
        "category": "Body Styling",
        "subtype": subtype,
        "value": text,
        "relation": "",
        "visual_ready": True,
        "specificity": 1.0,
    }


def _wardrobe_piece_has_multiple_independent_heads(value: str) -> bool:
    text = _wardrobe_clean_phrase(value)
    matches = _wardrobe_filtered_heads(text)
    if len(matches) < 2:
        return False
    for left, right in zip(matches, matches[1:]):
        before = text[max(0, right.start() - 24):right.start()].casefold()
        if re.search(r"\b(?:built[- ]in|attached|integrated|embroidered|printed|trimmed|edged)\s+$", before):
            continue
        if _wardrobe_separator_between(text, left.end(), right.start()):
            return True
    return False


def _decompose_outfit_look(value: str) -> dict[str, Any]:
    original = _single_line_recipe_prompt(value)
    if not original:
        return {"status": "unresolved", "confidence": 0.0, "items": [], "issues": ["unresolved"], "parser_version": WARDROBE_PARSER_VERSION}

    styling = _wardrobe_body_styling_item(original)
    if styling is not None:
        return {"status": "ready", "confidence": 0.98, "items": [styling], "issues": ["styling"], "parser_version": WARDROBE_PARSER_VERSION}

    work = original
    finishers: list[dict[str, Any]] = []
    seen_finishers: set[str] = set()
    for pattern, canonical in _WARDROBE_FINISHERS:
        if pattern.search(work):
            if canonical not in seen_finishers:
                finishers.append({"item_type": "finisher", "category": "Other", "subtype": "Uncategorized", "value": canonical, "relation": "", "visual_ready": True, "specificity": 1.0})
                seen_finishers.add(canonical)
            work = pattern.sub("", work)
    work = re.sub(r"\s+,", ",", work)
    work = re.sub(r",\s*(?:and\s*)?$", "", work, flags=re.IGNORECASE)
    work = re.sub(r"\s+", " ", work).strip(" ,")

    matches = _wardrobe_filtered_heads(work)
    if not matches:
        status = "review" if finishers else "unresolved"
        return {"status": status, "confidence": 0.35 if finishers else 0.0, "items": finishers, "issues": ["unresolved"] if not finishers else [], "parser_version": WARDROBE_PARSER_VERSION}

    boundaries: list[tuple[int, int, str] | None] = []
    for index in range(len(matches) - 1):
        boundaries.append(_wardrobe_separator_between(work, matches[index].end(), matches[index + 1].start()))

    starts = [0]
    for boundary in boundaries:
        starts.append(boundary[1] if boundary else -1)
    ends: list[int] = []
    for index, match in enumerate(matches):
        if index < len(boundaries):
            boundary = boundaries[index]
            ends.append(boundary[0] if boundary else matches[index + 1].start())
        else:
            ends.append(len(work))

    pieces: list[dict[str, Any]] = []
    missing_boundaries = 0
    for index, match in enumerate(matches):
        start = starts[index]
        if start < 0:
            start = match.start()
            missing_boundaries += 1
        source_phrase = _wardrobe_clean_phrase(work[start:ends[index]])
        if not source_phrase:
            continue
        category, subtype = _wardrobe_head_class(match)
        relation = ""
        if index > 0 and boundaries[index - 1]:
            relation = str(boundaries[index - 1][2] or "")
        item_type = "set" if category == "Matching Sets" else "piece"
        specificity = _wardrobe_specificity(source_phrase, item_type)
        phrase = canonicalize_wardrobe_value(source_phrase, item_type)
        pieces.append({"item_type": item_type, "category": category, "subtype": subtype, "value": phrase, "relation": relation, **specificity})

    # Merge constructions where 'matching' belongs to a second independent garment.
    merged: list[dict[str, Any]] = []
    index = 0
    while index < len(pieces):
        current = pieces[index]
        following = pieces[index + 1] if index + 1 < len(pieces) else None
        if (
            following
            and re.match(r"^matching\b", str(following.get("value") or ""), re.IGNORECASE)
            and str(current.get("category")) in _WARDROBE_SET_CATEGORIES
            and str(following.get("category")) in _WARDROBE_SET_CATEGORIES
        ):
            value_text = _wardrobe_clean_phrase(f"{current['value']} and {following['value']}")
            merged.append({
                "item_type": "set", "category": "Matching Sets", "subtype": "Coordinated Sets",
                "value": value_text, "relation": str(current.get("relation") or ""), "visual_ready": True, "specificity": 1.0,
            })
            index += 2
            continue
        merged.append(current)
        index += 1

    items = merged + finishers
    generic_count = sum(1 for item in items if item.get("visual_ready") is False)
    confidence = 0.98 if len(pieces) == 1 and not finishers else 0.95
    confidence -= min(0.32, missing_boundaries * 0.14)
    if len(items) > 7:
        confidence -= 0.12
    if generic_count:
        confidence -= min(0.28, generic_count * 0.10)
    if any(re.search(r"\b(?:camera|lens|lighting|portrait|photograph|background|pose|gaze)\b", str(item.get("value") or ""), re.IGNORECASE) for item in items):
        confidence -= 0.2
    confidence = max(0.0, min(0.99, confidence))

    issues: list[str] = []
    if generic_count:
        issues.append("generic")
    if any(item.get("item_type") == "set" for item in items):
        issues.append("set")
    if len(items) >= 4:
        issues.append("complex")
    if missing_boundaries:
        issues.append("boundary")
    compound_count = sum(1 for item in items if item.get("item_type") == "piece" and _wardrobe_piece_has_multiple_independent_heads(str(item.get("value") or "")))
    if compound_count:
        issues.append("compound")
        confidence = max(0.0, confidence - min(0.24, 0.12 * compound_count))
    if not items:
        issues.append("unresolved")
    status = "ready" if confidence >= 0.9 and items and not generic_count and not missing_boundaries and not compound_count else "review" if items else "unresolved"
    if status == "unresolved" and "unresolved" not in issues:
        issues.append("unresolved")
    return {"status": status, "confidence": round(confidence, 3), "items": items, "issues": issues, "parser_version": WARDROBE_PARSER_VERSION}


def _wardrobe_migration_status() -> dict[str, Any]:
    catalog = get_catalog()
    looks = catalog.recipe_components("outfit")
    states = catalog.wardrobe_migration_states()
    accepted = ignored = pending = unseen = 0
    for look in looks:
        look_id = str(look.get("component_id") or "")
        state = states.get(look_id)
        if not state:
            unseen += 1
            continue
        status = str(state.get("status") or "")
        if status == "accepted":
            accepted += 1
        elif status == "ignored":
            ignored += 1
        else:
            pending += 1
    return {"ok": True, "total": len(looks), "accepted": accepted, "ignored": ignored, "pending": pending, "new": unseen, "parser_version": WARDROBE_PARSER_VERSION}


def _analyze_wardrobe_migration(
    *,
    refresh: bool = False,
    sample_limit: int = 80,
    sample_offset: int = 0,
    status_filter: str = "",
    query: str = "",
    issue_filter: str = "",
    new_only: bool = False,
) -> dict[str, Any]:
    catalog = get_catalog()
    looks = catalog.recipe_components("outfit")
    states = catalog.wardrobe_migration_states()
    summary = {
        "total": len(looks), "ready": 0, "review": 0, "unresolved": 0, "accepted": 0, "ignored": 0,
        "detected_uses": 0, "unique_candidates": 0, "reused_occurrences": 0, "generic_candidates": 0, "new": 0,
    }
    candidates: list[dict[str, Any]] = []
    state_updates: list[dict[str, Any]] = []
    unique_keys: set[tuple[str, str]] = set()
    for look in looks:
        look_id = str(look.get("component_id") or "")
        prior = states.get(look_id)
        prior_status = str(prior.get("status") or "") if prior else ""
        # Explicit human decisions survive parser upgrades. Bulk auto-migrations can be re-audited
        # when the user explicitly chooses RE-ANALYZE so parser improvements can repair old splits.
        prior_proposal = dict(prior.get("proposal") or {}) if prior else {}
        manually_reviewed = bool(prior_proposal.get("manually_reviewed"))
        if prior and prior_status == "ignored":
            proposal = prior_proposal
            status = prior_status
            confidence = float(prior.get("confidence") or proposal.get("confidence") or 0)
            proposal.setdefault("items", [])
            proposal.setdefault("issues", [])
            is_new = bool(proposal.get("is_new", False))
        elif prior and prior_status == "accepted" and (not refresh or manually_reviewed):
            proposal = prior_proposal
            status = prior_status
            confidence = float(prior.get("confidence") or proposal.get("confidence") or 0)
            proposal.setdefault("items", [])
            proposal.setdefault("issues", [])
            is_new = bool(proposal.get("is_new", False))
        elif prior and not refresh and str(prior.get("parser_version") or "") == WARDROBE_PARSER_VERSION:
            proposal = dict(prior.get("proposal") or {})
            status = str(prior.get("status") or proposal.get("status") or "review")
            confidence = float(prior.get("confidence") or proposal.get("confidence") or 0)
            proposal.setdefault("items", [])
            proposal.setdefault("issues", [])
            is_new = bool(proposal.get("is_new", False))
        else:
            proposal = _decompose_outfit_look(str(look.get("value") or ""))
            status = str(proposal.get("status") or "unresolved")
            confidence = float(proposal.get("confidence") or 0)
            is_new = prior is None
            proposal["is_new"] = is_new
            state_updates.append({"look_component_id": look_id, "parser_version": WARDROBE_PARSER_VERSION, "status": status, "confidence": confidence, "proposal": proposal})
        summary[status if status in summary else "review"] += 1
        if status not in {"accepted", "ignored"} and is_new:
            summary["new"] += 1
        items = proposal.get("items") or []
        summary["detected_uses"] += len(items)
        for item in items:
            if not isinstance(item, dict):
                continue
            key = (str(item.get("item_type") or "piece"), _wardrobe_value_key(str(item.get("value") or "")))
            if key[1]:
                unique_keys.add(key)
            if item.get("visual_ready") is False:
                summary["generic_candidates"] += 1
        if status not in {"accepted", "ignored"}:
            candidates.append({
                "component_id": look_id, "value": str(look.get("value") or ""), "status": status,
                "confidence": confidence, "items": items, "issues": proposal.get("issues") or [],
                "is_new": is_new, "rating": int(look.get("rating") or 0),
            })
    if state_updates:
        catalog.set_wardrobe_migration_states_bulk(state_updates)
    summary["unique_candidates"] = len(unique_keys)
    summary["reused_occurrences"] = max(0, summary["detected_uses"] - summary["unique_candidates"])
    priority = {"review": 0, "unresolved": 1, "ready": 2}
    candidates.sort(key=lambda row: (priority.get(str(row.get("status") or ""), 3), -int(bool(row.get("is_new"))), -int(row.get("rating") or 0), -float(row.get("confidence") or 0), str(row.get("value") or "").casefold()))
    clean_status = str(status_filter or "").strip().lower()
    if clean_status in {"review", "unresolved", "ready"}:
        filtered = [row for row in candidates if str(row.get("status") or "") == clean_status]
    else:
        filtered = candidates
    if new_only:
        filtered = [row for row in filtered if bool(row.get("is_new"))]
    clean_issue = str(issue_filter or "").strip().lower()
    if clean_issue in {"generic", "set", "complex", "boundary", "compound", "styling", "unresolved"}:
        filtered = [row for row in filtered if clean_issue in set(str(value) for value in row.get("issues") or [])]
    clean_query = str(query or "").strip().casefold()
    if clean_query:
        filtered = [row for row in filtered if clean_query in str(row.get("value") or "").casefold() or any(clean_query in str(item.get("value") or "").casefold() for item in row.get("items") or [])]
    limit = max(0, int(sample_limit))
    offset = max(0, int(sample_offset))
    rows = filtered[offset:offset + limit] if limit else []
    return {
        "ok": True, "parser_version": WARDROBE_PARSER_VERSION, "summary": summary, "rows": rows,
        "queue_total": len(filtered), "queue_offset": offset, "queue_limit": limit,
        "status_filter": clean_status if clean_status in {"review", "unresolved", "ready"} else "all",
        "issue_filter": clean_issue, "new_only": bool(new_only), "query": str(query or "").strip(),
    }


def _accept_wardrobe_migration(look_ids: list[str] | None = None, *, high_confidence_only: bool = False, manually_reviewed: bool = False) -> dict[str, Any]:
    catalog = get_catalog()
    looks = {str(item.get("component_id") or ""): item for item in catalog.recipe_components("outfit")}
    states = catalog.wardrobe_migration_states()
    requested = set(str(value) for value in (look_ids or []) if str(value))
    entries: list[dict[str, Any]] = []
    skipped = 0
    state_updates: list[dict[str, Any]] = []
    for look_id, look in looks.items():
        if requested and look_id not in requested:
            continue
        state = states.get(look_id)
        if not state or str(state.get("parser_version") or "") != WARDROBE_PARSER_VERSION:
            # Never overwrite an explicit human decision from an older parser.
            if state and str(state.get("status") or "") in {"accepted", "ignored"}:
                skipped += 1
                continue
            proposal = _decompose_outfit_look(str(look.get("value") or ""))
            status = str(proposal.get("status") or "unresolved")
            confidence = float(proposal.get("confidence") or 0)
            state_updates.append({"look_component_id": look_id, "parser_version": WARDROBE_PARSER_VERSION, "status": status, "confidence": confidence, "proposal": proposal})
        else:
            proposal = dict(state.get("proposal") or {})
            status = str(state.get("status") or proposal.get("status") or "unresolved")
            confidence = float(state.get("confidence") or proposal.get("confidence") or 0)
        if status in {"accepted", "ignored"}:
            skipped += 1
            continue
        if high_confidence_only and not (status == "ready" and confidence >= 0.9):
            skipped += 1
            continue
        eligible_items = [item for item in (proposal.get("items") or []) if isinstance(item, dict) and item.get("visual_ready") is not False]
        if not eligible_items:
            skipped += 1
            continue
        proposal = dict(proposal); proposal["items"] = eligible_items
        if manually_reviewed:
            proposal["manually_reviewed"] = True
        entries.append({"look_component_id": look_id, "proposal": proposal, "confidence": confidence})
    if state_updates:
        catalog.set_wardrobe_migration_states_bulk(state_updates)
    result = catalog.apply_wardrobe_migration_batch(entries, parser_version=WARDROBE_PARSER_VERSION)
    return {"ok": True, **result, "skipped": skipped}

def _accept_filtered_wardrobe_migration(*, status_filter: str = "", issue_filter: str = "", query: str = "", new_only: bool = False) -> dict[str, Any]:
    analysis = _analyze_wardrobe_migration(
        refresh=False, sample_limit=100000, sample_offset=0, status_filter=status_filter,
        issue_filter=issue_filter, query=query, new_only=new_only,
    )
    look_ids = [str(row.get("component_id") or "") for row in analysis.get("rows") or [] if str(row.get("component_id") or "")]
    result = _accept_wardrobe_migration(look_ids, high_confidence_only=False, manually_reviewed=False)
    return {"ok": True, "matched_view": len(look_ids), **result}


def _ignore_filtered_wardrobe_migration(*, status_filter: str = "", issue_filter: str = "", query: str = "", new_only: bool = False) -> dict[str, Any]:
    analysis = _analyze_wardrobe_migration(
        refresh=False, sample_limit=100000, sample_offset=0, status_filter=status_filter,
        issue_filter=issue_filter, query=query, new_only=new_only,
    )
    catalog = get_catalog()
    states = catalog.wardrobe_migration_states()
    changed = 0
    for row in analysis.get("rows") or []:
        look_id = str(row.get("component_id") or "")
        if not look_id:
            continue
        state = states.get(look_id) or {}
        proposal = dict(state.get("proposal") or {})
        if not proposal:
            proposal = {"status": str(row.get("status") or "unresolved"), "confidence": float(row.get("confidence") or 0), "items": row.get("items") or [], "issues": row.get("issues") or [], "parser_version": WARDROBE_PARSER_VERSION}
        proposal["manually_reviewed"] = True
        catalog.set_wardrobe_migration_state(look_id, parser_version=WARDROBE_PARSER_VERSION, status="ignored", confidence=float(row.get("confidence") or 0), proposal=proposal)
        changed += 1
    return {"ok": True, "matched_view": int(analysis.get("queue_total") or 0), "ignored": changed}


_CREATIVE_LIBRARY_KEYS = ("templates", "prompts", "recipes", "outfits", "scenes", "wardrobe", "fragments", "boards")


def _normalize_pack_selection(raw: Any, *, mode: str = "starter") -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    raw_libraries = source.get("libraries")
    if isinstance(raw_libraries, dict):
        libraries = {str(key).strip().lower() for key, enabled in raw_libraries.items() if enabled}
    elif isinstance(raw_libraries, list):
        libraries = {str(value).strip().lower() for value in raw_libraries if str(value).strip()}
    else:
        libraries = set(_CREATIVE_LIBRARY_KEYS)
    libraries &= set(_CREATIVE_LIBRARY_KEYS)
    if str(mode or "starter").strip().lower() != "backup":
        libraries.discard("boards")
    return {
        "libraries": sorted(libraries),
        "prompt_scopes": source.get("prompt_scopes") if isinstance(source.get("prompt_scopes"), dict) else {},
        "recipe_scope": source.get("recipe_scope") if isinstance(source.get("recipe_scope"), dict) else {},
        "component_scopes": source.get("component_scopes") if isinstance(source.get("component_scopes"), dict) else {},
        "wardrobe_scope": source.get("wardrobe_scope") if isinstance(source.get("wardrobe_scope"), dict) else {},
        "include_thumbnails": bool(source.get("include_thumbnails", True)),
        "include_taxonomy": bool(source.get("include_taxonomy", True)),
        "include_dependencies": bool(source.get("include_dependencies", True)),
    }


def _folded_values(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value).strip().casefold() for value in values if str(value).strip()}


def _scoped_subcategories(values: Any) -> set[tuple[str, str]]:
    output: set[tuple[str, str]] = set()
    if not isinstance(values, list):
        return output
    for value in values:
        if isinstance(value, dict):
            parent = str(value.get("parent") or value.get("parent_name") or "").strip().casefold()
            name = str(value.get("name") or value.get("subcategory") or "").strip().casefold()
        else:
            text = str(value or "").strip()
            if "/" in text:
                parent, name = (part.strip().casefold() for part in text.split("/", 1))
            else:
                parent, name = "", text.casefold()
        if name:
            output.add((parent, name))
    return output


def _scoped_component_collections(values: Any) -> set[tuple[str, str]]:
    output: set[tuple[str, str]] = set()
    if not isinstance(values, list):
        return output
    for value in values:
        if isinstance(value, dict):
            parent = str(value.get("parent_name") or value.get("parent") or "").strip().casefold()
            name = str(value.get("name") or "").strip().casefold()
        else:
            text = str(value or "").strip()
            if "/" in text:
                parent, name = (part.strip().casefold() for part in text.split("/", 1))
            else:
                parent, name = "", text.casefold()
        if name:
            output.add((parent, name))
    return output


def _prompt_matches_export_scope(entry: dict[str, Any], scope: Any) -> bool:
    if not isinstance(scope, dict):
        return True
    ids = _folded_values(scope.get("ids")) | _folded_values(scope.get("current_scope_ids"))
    parents = _folded_values(scope.get("parents"))
    subcategories = _scoped_subcategories(scope.get("subcategories"))
    collections = _folded_values(scope.get("collections"))
    source_paths = _folded_values(scope.get("source_paths"))
    if not any((ids, parents, subcategories, collections, source_paths)):
        return True
    prompt_id = str(entry.get("source_prompt_id") or "").strip().casefold()
    parent = str(entry.get("primary_parent") or "").strip().casefold()
    subcategory = str(entry.get("primary_subcategory") or "").strip().casefold()
    member_names = {str(row.get("name") or "").strip().casefold() for row in entry.get("collections") or [] if isinstance(row, dict)}
    entry_source_paths = {str(row.get("source_path") or "").replace("\\", "/").strip().casefold() for row in entry.get("sources") or [] if isinstance(row, dict) and str(row.get("source_path") or "").strip()}
    return (
        (bool(ids) and prompt_id in ids)
        or (bool(parents) and parent in parents)
        or (bool(subcategories) and ((parent, subcategory) in subcategories or ("", subcategory) in subcategories))
        or (bool(collections) and bool(member_names & collections))
        or (bool(source_paths) and bool(entry_source_paths & source_paths))
    )


def _recipe_matches_export_scope(entry: dict[str, Any], scope: Any) -> bool:
    if not isinstance(scope, dict):
        return True
    ids = _folded_values(scope.get("ids")) | _folded_values(scope.get("current_scope_ids"))
    collections = _folded_values(scope.get("collections"))
    if not any((ids, collections)):
        return True
    recipe_id = str(entry.get("source_recipe_id") or "").strip().casefold()
    member_names = {str(row.get("name") or "").strip().casefold() for row in entry.get("collections") or [] if isinstance(row, dict)}
    return (bool(ids) and recipe_id in ids) or (bool(collections) and bool(member_names & collections))


def _component_matches_export_scope(entry: dict[str, Any], scope: Any) -> bool:
    if not isinstance(scope, dict):
        return True
    ids = _folded_values(scope.get("ids")) | _folded_values(scope.get("current_scope_ids"))
    collections = _scoped_component_collections(scope.get("collections"))
    pack_collections = _folded_values(scope.get("pack_collections"))
    if not any((ids, collections, pack_collections)):
        return True
    component_id = str(entry.get("source_component_id") or "").strip().casefold()
    if ids and component_id in ids:
        return True
    for row in entry.get("collections") or []:
        if not isinstance(row, dict):
            continue
        parent = str(row.get("parent_name") or "").strip().casefold()
        name = str(row.get("name") or "").strip().casefold()
        if (parent, name) in collections or ("", name) in collections or ("", parent) in collections:
            return True
    member_pack_names = {str(row.get("name") or "").strip().casefold() for row in entry.get("pack_collections") or [] if isinstance(row, dict)}
    if pack_collections and member_pack_names & pack_collections:
        return True
    return False


def _wardrobe_matches_export_scope(entry: dict[str, Any], scope: Any) -> bool:
    if not isinstance(scope, dict):
        return True
    ids = _folded_values(scope.get("ids")) | _folded_values(scope.get("current_scope_ids"))
    categories = _folded_values(scope.get("categories"))
    subtypes = _folded_values(scope.get("subtypes"))
    category_subtypes = _scoped_subcategories(scope.get("category_subtypes"))
    pack_collections = _folded_values(scope.get("pack_collections"))
    if not any((ids, categories, subtypes, category_subtypes, pack_collections)):
        return True
    wardrobe_id = str(entry.get("source_wardrobe_id") or "").strip().casefold()
    category = str(entry.get("category") or "").strip().casefold()
    subtype = str(entry.get("subtype") or "").strip().casefold()
    return (
        (bool(ids) and wardrobe_id in ids)
        or (bool(categories) and category in categories)
        or (bool(subtypes) and subtype in subtypes)
        or (bool(category_subtypes) and ((category, subtype) in category_subtypes or ("", subtype) in category_subtypes))
        or (bool(pack_collections) and bool({str(row.get("name") or "").strip().casefold() for row in entry.get("pack_collections") or [] if isinstance(row, dict)} & pack_collections))
    )


def _scope_creative_library_snapshot(snapshot: dict[str, Any], raw_selection: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Filter a canonical pack snapshot and add only the dependencies needed by selected records."""
    mode = str(snapshot.get("mode") or "starter")
    selection = _normalize_pack_selection(raw_selection, mode=mode)
    libraries = set(selection["libraries"])
    prompt_scopes = selection["prompt_scopes"]
    component_scopes = selection["component_scopes"]

    full_prompts = [copy.deepcopy(row) for row in snapshot.get("prompts") or [] if isinstance(row, dict)]
    selected_prompts: list[dict[str, Any]] = []
    for row in full_prompts:
        kind = "template" if str(row.get("kind") or "").casefold() == "template" else "prompt"
        library_key = "templates" if kind == "template" else "prompts"
        if library_key not in libraries:
            continue
        if _prompt_matches_export_scope(row, prompt_scopes.get(kind)):
            selected_prompts.append(row)

    selected_recipes = [
        copy.deepcopy(row) for row in snapshot.get("recipes") or []
        if isinstance(row, dict) and "recipes" in libraries and _recipe_matches_export_scope(row, selection["recipe_scope"])
    ]

    full_components = [copy.deepcopy(row) for row in snapshot.get("components") or [] if isinstance(row, dict)]
    selected_components: list[dict[str, Any]] = []
    for row in full_components:
        kind = str(row.get("kind") or "").strip().lower()
        library_key = "outfits" if kind == "outfit" else "scenes" if kind == "scene" else ""
        if not library_key or library_key not in libraries:
            continue
        if _component_matches_export_scope(row, component_scopes.get(kind)):
            selected_components.append(row)

    selected_wardrobe = [
        copy.deepcopy(row) for row in snapshot.get("wardrobe_items") or []
        if isinstance(row, dict) and "wardrobe" in libraries and _wardrobe_matches_export_scope(row, selection["wardrobe_scope"])
    ]
    selected_fragments = [copy.deepcopy(row) for row in snapshot.get("fragments") or [] if isinstance(row, dict) and "fragments" in libraries]
    selected_boards = [copy.deepcopy(row) for row in snapshot.get("boards") or [] if isinstance(row, dict) and "boards" in libraries]

    # Dependency expansion is intentionally value-based. Recipes are portable even
    # when record IDs differ between machines, so concrete prompt/component values
    # are the stable join key.
    if selection["include_dependencies"] and selected_recipes:
        prompt_by_value = {str(row.get("value") or "").casefold(): row for row in full_prompts}
        component_by_key = {(str(row.get("kind") or ""), str(row.get("value") or "").casefold()): row for row in full_components}
        prompt_ids = {str(row.get("source_prompt_id") or "") for row in selected_prompts}
        component_ids = {str(row.get("source_component_id") or "") for row in selected_components}
        for recipe in selected_recipes:
            source_prompt = _recipe_prompt_text(recipe)
            dependency_prompt = prompt_by_value.get(source_prompt.casefold()) if source_prompt else None
            if dependency_prompt and str(dependency_prompt.get("source_prompt_id") or "") not in prompt_ids:
                selected_prompts.append(copy.deepcopy(dependency_prompt))
                prompt_ids.add(str(dependency_prompt.get("source_prompt_id") or ""))
                libraries.add("templates" if str(dependency_prompt.get("kind") or "").casefold() == "template" else "prompts")
            for kind in ("outfit", "scene"):
                for value in _recipe_resolved_component_values(recipe, kind):
                    dependency_component = component_by_key.get((kind, value.casefold()))
                    dependency_id = str((dependency_component or {}).get("source_component_id") or "")
                    if dependency_component and dependency_id not in component_ids:
                        selected_components.append(copy.deepcopy(dependency_component))
                        component_ids.add(dependency_id)
                        libraries.add("outfits" if kind == "outfit" else "scenes")

    # A partially checked export tree also controls which optional navigation
    # memberships/provenance travel with records selected through another path.
    # This keeps an unchecked Collection or source Log from sneaking back
    # into a pack merely because the same record was selected by its taxonomy home.
    for row in selected_prompts:
        kind = "template" if str(row.get("kind") or "").casefold() == "template" else "prompt"
        scope = prompt_scopes.get(kind) if isinstance(prompt_scopes, dict) else {}
        if not isinstance(scope, dict):
            continue
        if bool(scope.get("filter_collections")):
            allowed_collections = _folded_values(scope.get("included_collections"))
            row["collections"] = [
                group for group in row.get("collections") or []
                if isinstance(group, dict) and str(group.get("name") or "").strip().casefold() in allowed_collections
            ]
        if bool(scope.get("filter_sources")):
            allowed_sources = _folded_values(scope.get("included_source_paths"))
            row["sources"] = [
                source for source in row.get("sources") or []
                if isinstance(source, dict)
                and str(source.get("source_path") or "").replace("\\", "/").strip().casefold() in allowed_sources
            ]

    recipe_scope = selection.get("recipe_scope") if isinstance(selection.get("recipe_scope"), dict) else {}
    if bool(recipe_scope.get("filter_collections")):
        allowed_recipe_collections = _folded_values(recipe_scope.get("included_collections"))
        for row in selected_recipes:
            row["collections"] = [
                group for group in row.get("collections") or []
                if isinstance(group, dict) and str(group.get("name") or "").strip().casefold() in allowed_recipe_collections
            ]

    for row in selected_components:
        kind = str(row.get("kind") or "").strip().lower()
        scope = component_scopes.get(kind) if isinstance(component_scopes, dict) else {}
        if not isinstance(scope, dict):
            continue
        if bool(scope.get("filter_collections")):
            allowed_component_collections = _scoped_component_collections(scope.get("included_collections"))
            kept = []
            for group in row.get("collections") or []:
                if not isinstance(group, dict):
                    continue
                parent = str(group.get("parent_name") or "").strip().casefold()
                name = str(group.get("name") or "").strip().casefold()
                if (parent, name) in allowed_component_collections or ("", name) in allowed_component_collections or ("", parent) in allowed_component_collections:
                    kept.append(group)
            row["collections"] = kept
        if bool(scope.get("filter_pack_collections")):
            allowed_pack_collections = _folded_values(scope.get("included_pack_collections"))
            row["pack_collections"] = [
                group for group in row.get("pack_collections") or []
                if isinstance(group, dict) and str(group.get("name") or "").strip().casefold() in allowed_pack_collections
            ]

    wardrobe_scope = selection.get("wardrobe_scope") if isinstance(selection.get("wardrobe_scope"), dict) else {}
    if bool(wardrobe_scope.get("filter_pack_collections")):
        allowed_wardrobe_pack_collections = _folded_values(wardrobe_scope.get("included_pack_collections"))
        for row in selected_wardrobe:
            row["pack_collections"] = [
                group for group in row.get("pack_collections") or []
                if isinstance(group, dict) and str(group.get("name") or "").strip().casefold() in allowed_wardrobe_pack_collections
            ]

    # Outfit Looks are only fully useful when their harvested Wardrobe pieces travel
    # with them. Include exactly the linked items, not the entire Wardrobe catalog.
    full_relations = [copy.deepcopy(row) for row in snapshot.get("wardrobe_relations") or [] if isinstance(row, dict)]
    selected_outfit_values = {str(row.get("value") or "").casefold() for row in selected_components if str(row.get("kind") or "") == "outfit"}
    wardrobe_by_key = {(str(row.get("item_type") or ""), str(row.get("value") or "").casefold()): row for row in snapshot.get("wardrobe_items") or [] if isinstance(row, dict)}
    wardrobe_keys = {(str(row.get("item_type") or ""), str(row.get("value") or "").casefold()) for row in selected_wardrobe}
    if selection["include_dependencies"] and selected_outfit_values:
        for relation in full_relations:
            if str(relation.get("look_value") or "").casefold() not in selected_outfit_values:
                continue
            key = (str(relation.get("item_type") or ""), str(relation.get("item_value") or "").casefold())
            dependency = wardrobe_by_key.get(key)
            if dependency and key not in wardrobe_keys:
                selected_wardrobe.append(copy.deepcopy(dependency))
                wardrobe_keys.add(key)
                libraries.add("wardrobe")

    selected_relations = [
        row for row in full_relations
        if str(row.get("look_value") or "").casefold() in selected_outfit_values
        and (str(row.get("item_type") or ""), str(row.get("item_value") or "").casefold()) in wardrobe_keys
    ]

    if not selection["include_taxonomy"]:
        for row in selected_prompts + selected_recipes + selected_components:
            row["collections"] = []

    recipe_collection_names = {
        str(group.get("name") or "").casefold()
        for row in selected_recipes
        for group in row.get("collections") or [] if isinstance(group, dict)
    }
    recipe_collections = [
        copy.deepcopy(row) for row in snapshot.get("recipe_collections") or []
        if selection["include_taxonomy"] and isinstance(row, dict) and str(row.get("name") or "").casefold() in recipe_collection_names
    ]
    prompt_showcase_keys = {
        (
            "template" if str(row.get("kind") or "").casefold() == "template" else "prompt",
            str(group.get("name") or "").casefold(),
        )
        for row in selected_prompts
        for group in row.get("collections") or [] if isinstance(group, dict)
    }
    for kind, library_key in (("prompt", "prompts"), ("template", "templates")):
        scope = prompt_scopes.get(kind) if isinstance(prompt_scopes, dict) else {}
        full_scope = not isinstance(scope, dict) or not any(
            scope.get(key) for key in ("ids", "current_scope_ids", "parents", "subcategories", "collections", "source_paths")
        )
        if library_key in libraries and full_scope:
            prompt_showcase_keys.update(
                (kind, str(row.get("name") or "").casefold())
                for row in snapshot.get("prompt_showcase_collections") or []
                if isinstance(row, dict) and str(row.get("kind") or "prompt") == kind
            )
    prompt_showcase_collections = [
        copy.deepcopy(row) for row in snapshot.get("prompt_showcase_collections") or []
        if selection["include_taxonomy"] and isinstance(row, dict)
        and (str(row.get("kind") or "prompt"), str(row.get("name") or "").casefold()) in prompt_showcase_keys
    ]
    component_collection_keys = {
        (str(row.get("kind") or ""), str(group.get("parent_name") or "").casefold(), str(group.get("name") or "").casefold())
        for row in selected_components for group in row.get("collections") or [] if isinstance(group, dict)
    }
    component_collection_names = {(kind, name) for kind, _parent, name in component_collection_keys} | {(kind, parent) for kind, parent, _name in component_collection_keys if parent}
    component_collections = [
        copy.deepcopy(row) for row in snapshot.get("component_collections") or []
        if selection["include_taxonomy"] and isinstance(row, dict)
        and (str(row.get("kind") or ""), str(row.get("name") or "").casefold()) in component_collection_names
    ]

    selected_prompt_ids = {str(row.get("source_prompt_id") or "") for row in selected_prompts}
    selected_wardrobe_ids = {str(row.get("source_wardrobe_id") or "") for row in selected_wardrobe}
    selected_fragment_ids = {str(row.get("source_fragment_id") or "") for row in selected_fragments}
    extras = snapshot.get("backup_extras") if isinstance(snapshot.get("backup_extras"), dict) else {}
    scoped_extras = {}
    if mode == "backup":
        selected_source_ids = {
            str(row.get("source_id") or "")
            for row in extras.get("wardrobe_item_sources") or [] if isinstance(row, dict)
            and str(row.get("wardrobe_id") or "") in selected_wardrobe_ids
        }
        scoped_extras = {
            "wardrobe_item_sources": [copy.deepcopy(row) for row in extras.get("wardrobe_item_sources") or [] if isinstance(row, dict) and str(row.get("wardrobe_id") or "") in selected_wardrobe_ids],
            "wardrobe_sources": [copy.deepcopy(row) for row in extras.get("wardrobe_sources") or [] if isinstance(row, dict) and str(row.get("source_id") or "") in selected_source_ids],
            "fragment_memberships": [copy.deepcopy(row) for row in extras.get("fragment_memberships") or [] if isinstance(row, dict) and str(row.get("fragment_id") or "") in selected_fragment_ids and str(row.get("prompt_id") or "") in selected_prompt_ids],
            "fragment_sources": [copy.deepcopy(row) for row in extras.get("fragment_sources") or [] if isinstance(row, dict) and str(row.get("fragment_id") or "") in selected_fragment_ids],
        }

    structure_order: dict[str, Any] = {}
    if selection["include_taxonomy"]:
        full_order = snapshot.get("structure_order") if isinstance(snapshot.get("structure_order"), dict) else {}

        def prompt_scope_is_full(scope: Any) -> bool:
            if not isinstance(scope, dict):
                return True
            return not any(scope.get(key) for key in ("ids", "current_scope_ids", "parents", "subcategories", "collections", "source_paths"))

        for kind, library_key in (("prompt", "prompts"), ("template", "templates")):
            if library_key not in libraries:
                continue
            raw = copy.deepcopy(full_order.get(kind) if isinstance(full_order.get(kind), dict) else {})
            if prompt_scope_is_full(prompt_scopes.get(kind)):
                structure_order[kind] = raw
                continue
            rows = [row for row in selected_prompts if ("template" if str(row.get("kind") or "").casefold() == "template" else "prompt") == kind]
            allowed_parents = {str(row.get("primary_parent") or "") for row in rows}
            allowed_subs: dict[str, set[str]] = {}
            allowed_paths: dict[str, dict[str, set[str]]] = {}
            for row in rows:
                parent = str(row.get("primary_parent") or "")
                sub = str(row.get("primary_subcategory") or "")
                allowed_subs.setdefault(parent, set()).add(sub)
                for source in row.get("sources") or []:
                    if isinstance(source, dict) and str(source.get("source_path") or ""):
                        allowed_paths.setdefault(parent, {}).setdefault(sub, set()).add(str(source.get("source_path") or "").replace("\\", "/"))
            parents = [value for value in raw.get("parents") or [] if str(value) in allowed_parents]
            parents.extend(sorted((value for value in allowed_parents if value and value not in parents), key=str.casefold))
            subs = {}
            logs = {}
            raw_subs = raw.get("subcategories") if isinstance(raw.get("subcategories"), dict) else {}
            raw_logs = raw.get("logs") if isinstance(raw.get("logs"), dict) else {}
            for parent in parents:
                wanted_subs = allowed_subs.get(parent, set())
                child_order = [value for value in raw_subs.get(parent, []) if str(value) in wanted_subs]
                child_order.extend(sorted((value for value in wanted_subs if value and value not in child_order), key=str.casefold))
                subs[parent] = child_order
                parent_logs = {}
                for sub in child_order:
                    paths = allowed_paths.get(parent, {}).get(sub, set())
                    existing = raw_logs.get(parent, {}).get(sub, []) if isinstance(raw_logs.get(parent), dict) else []
                    ordered = [value for value in existing if str(value).replace("\\", "/") in paths]
                    ordered.extend(sorted((value for value in paths if value not in ordered), key=str.casefold))
                    if ordered:
                        parent_logs[sub] = ordered
                if parent_logs:
                    logs[parent] = parent_logs
            showcase_names = {
                str(group.get("name") or "") for row in rows
                for group in row.get("collections") or [] if isinstance(group, dict) and str(group.get("name") or "")
            }
            raw_showcases = raw.get("showcase_collections", []) if isinstance(raw.get("showcase_collections"), list) else []
            ordered_showcases = [name for name in raw_showcases if str(name) in showcase_names]
            ordered_showcases.extend(sorted((name for name in showcase_names if name not in ordered_showcases), key=str.casefold))
            structure_order[kind] = {
                "parents": parents, "subcategories": subs, "logs": logs,
                "showcase_collections": ordered_showcases,
            }

        recipe_names = {str(row.get("name") or "") for row in recipe_collections}
        if "recipes" in libraries or "prompts" in libraries:
            raw_names = (full_order.get("recipe") or {}).get("collections", []) if isinstance(full_order.get("recipe"), dict) else []
            ordered_names = [name for name in raw_names if str(name) in recipe_names]
            ordered_names.extend(sorted((name for name in recipe_names if name and name not in ordered_names), key=str.casefold))
            structure_order["recipe"] = {"collections": ordered_names}

        outfit_names = {str(row.get("name") or "") for row in component_collections if str(row.get("kind") or "") == "outfit"}
        if "outfits" in libraries:
            raw_names = (full_order.get("outfit") or {}).get("collections", []) if isinstance(full_order.get("outfit"), dict) else []
            ordered_names = [name for name in raw_names if str(name) in outfit_names]
            ordered_names.extend(sorted((name for name in outfit_names if name and name not in ordered_names), key=str.casefold))
            structure_order["outfit"] = {"collections": ordered_names}

        if "scenes" in libraries:
            scene_rows = [row for row in component_collections if str(row.get("kind") or "") == "scene"]
            parent_names = {str(row.get("name") or "") for row in scene_rows if not str(row.get("parent_name") or "")}
            child_names: dict[str, set[str]] = {}
            for row in scene_rows:
                parent_name = str(row.get("parent_name") or "")
                if parent_name:
                    child_names.setdefault(parent_name, set()).add(str(row.get("name") or ""))
            raw_scene = full_order.get("scene") if isinstance(full_order.get("scene"), dict) else {}
            parents = [name for name in raw_scene.get("parents") or [] if str(name) in parent_names]
            parents.extend(sorted((name for name in parent_names if name and name not in parents), key=str.casefold))
            raw_subs = raw_scene.get("subcategories") if isinstance(raw_scene.get("subcategories"), dict) else {}
            subs = {}
            for parent in parents:
                available = child_names.get(parent, set())
                ordered = [name for name in raw_subs.get(parent, []) if str(name) in available]
                ordered.extend(sorted((name for name in available if name and name not in ordered), key=str.casefold))
                subs[parent] = ordered
            structure_order["scene"] = {"parents": parents, "subcategories": subs}

    selected_pack_collection_names = {
        (str(row.get("kind") or ""), str(group.get("name") or "").casefold())
        for row in selected_components for group in row.get("pack_collections") or [] if isinstance(group, dict)
    } | {
        ("wardrobe", str(group.get("name") or "").casefold())
        for row in selected_wardrobe for group in row.get("pack_collections") or [] if isinstance(group, dict)
    }
    library_collections = [
        copy.deepcopy(row) for row in snapshot.get("library_collections") or [] if isinstance(row, dict)
        and (str(row.get("kind") or ""), str(row.get("name") or "").casefold()) in selected_pack_collection_names
    ]

    scoped = {
        "mode": mode,
        "structure_order": structure_order,
        "recipe_collections": recipe_collections,
        "prompt_showcase_collections": prompt_showcase_collections,
        "prompts": selected_prompts,
        "recipes": selected_recipes,
        "component_collections": component_collections,
        "library_collections": library_collections,
        "components": selected_components,
        "wardrobe_items": selected_wardrobe,
        "wardrobe_relations": selected_relations,
        "fragments": selected_fragments,
        "boards": selected_boards,
        "tombstones": [
            copy.deepcopy(row) for row in snapshot.get("tombstones") or [] if isinstance(row, dict)
            and ((str(row.get("kind") or "") == "outfit" and "outfits" in libraries) or (str(row.get("kind") or "") == "scene" and "scenes" in libraries))
        ] if mode == "backup" else [],
        "backup_extras": scoped_extras,
    }
    effective_selection = {**selection, "libraries": [key for key in _CREATIVE_LIBRARY_KEYS if key in libraries]}
    return scoped, effective_selection


def _creative_library_pack_snapshot(mode: str = "starter") -> dict[str, Any]:
    """Return the portable snapshot for the *visible* Creative Library.

    The catalog-level snapshot only knows persisted ``prompt_assets``.  Saved
    Recipes and imported images also project fully usable Prompt/Template cards
    into the Library, and users can move those cards into Homes/Collections.
    Packs must therefore export the same prompt universe the gallery exposes,
    rather than silently dropping recipe-derived cards.
    """
    clean_mode = str(mode or "starter").strip().lower()
    if clean_mode not in {"starter", "backup"}:
        clean_mode = "starter"
    snapshot = get_catalog().creative_library_pack_snapshot(clean_mode)
    visible = _prompt_asset_snapshot(ensure_corpus=False)
    prompt_rows: list[dict[str, Any]] = []
    for asset in visible.get("records") or []:
        if not isinstance(asset, dict):
            continue
        if clean_mode != "backup" and bool(asset.get("archived")):
            continue
        kind = "template" if str(asset.get("kind") or "").casefold() == "template" else "prompt"
        prompt_rows.append({
            "source_prompt_id": str(asset.get("prompt_id") or ""),
            "kind": kind,
            "value": str(asset.get("value") or ""),
            "placeholder_signature": str(asset.get("placeholder_signature") or ""),
            "primary_parent": str(asset.get("primary_parent") or "Other"),
            "primary_subcategory": str(asset.get("primary_subcategory") or ""),
            "facets": copy.deepcopy(asset.get("facets") if isinstance(asset.get("facets"), dict) else {}),
            "rating": int(asset.get("rating") or 0),
            "note": str(asset.get("note") or ""),
            "preview_ref": str(asset.get("preview_ref") or ""),
            "preview_source": str(asset.get("preview_source") or ""),
            "resolved_seed": int(asset.get("resolved_seed")) if asset.get("resolved_seed") is not None else -1,
            "resolved_seed_source": str(asset.get("resolved_seed_source") or ""),
            "source_prompt_snapshot": str(asset.get("source_value") or ""),
            "resolved_prompt_snapshot": str(asset.get("resolved_value") or ""),
            "preview_metadata": copy.deepcopy(asset.get("preview_metadata") if isinstance(asset.get("preview_metadata"), dict) else {}),
            "collections": [
                {
                    "kind": kind,
                    "name": str(group.get("name") or ""),
                    "color": str(group.get("color") or "#b89aff"),
                }
                for group in asset.get("collections") or []
                if isinstance(group, dict) and str(group.get("name") or "")
            ],
            "sources": [copy.deepcopy(source) for source in asset.get("sources") or [] if isinstance(source, dict)],
            **({"archived": bool(asset.get("archived")), "is_custom": bool(asset.get("indexed"))} if clean_mode == "backup" else {}),
        })
    snapshot["prompts"] = prompt_rows
    return snapshot


def _creative_library_pack_contents(data: dict[str, Any]) -> dict[str, Any]:
    prompts = [row for row in data.get("prompts") or [] if isinstance(row, dict)]
    components = [row for row in data.get("components") or [] if isinstance(row, dict)]
    prompt_homes: dict[str, dict[str, dict[str, int]]] = {"template": {}, "prompt": {}}
    prompt_logs: dict[str, dict[str, dict[str, dict[str, dict[str, Any]]]]] = {"template": {}, "prompt": {}}
    for row in prompts:
        kind = "template" if str(row.get("kind") or "").casefold() == "template" else "prompt"
        parent = str(row.get("primary_parent") or "Imported")
        sub = str(row.get("primary_subcategory") or "Library Pack")
        prompt_homes[kind].setdefault(parent, {})[sub] = prompt_homes[kind].setdefault(parent, {}).get(sub, 0) + 1
        seen_paths: set[str] = set()
        for source in row.get("sources") or []:
            if not isinstance(source, dict):
                continue
            source_path = str(source.get("source_path") or "").replace("\\", "/").strip()
            if not source_path or source_path in seen_paths:
                continue
            seen_paths.add(source_path)
            label = _single_line_recipe_prompt(source.get("source_label")) or Path(source_path).stem
            bucket = prompt_logs[kind].setdefault(parent, {}).setdefault(sub, {})
            item = bucket.setdefault(source_path, {"label": label, "count": 0})
            item["count"] = int(item.get("count") or 0) + 1
    component_taxonomy: dict[str, dict[str, dict[str, int]]] = {"outfit": {}, "scene": {}}
    for row in components:
        kind = str(row.get("kind") or "")
        if kind not in component_taxonomy:
            continue
        groups = [group for group in row.get("collections") or [] if isinstance(group, dict)]
        if not groups:
            component_taxonomy[kind].setdefault("Unsorted", {})["Unsorted"] = component_taxonomy[kind].setdefault("Unsorted", {}).get("Unsorted", 0) + 1
        for group in groups:
            parent = str(group.get("parent_name") or "")
            name = str(group.get("name") or "Unsorted")
            category = parent or name
            sub = name if parent else ""
            component_taxonomy[kind].setdefault(category, {})[sub] = component_taxonomy[kind].setdefault(category, {}).get(sub, 0) + 1
    recipe_collections = sorted({str(group.get("name") or "") for row in data.get("recipes") or [] for group in row.get("collections") or [] if isinstance(group, dict) and str(group.get("name") or "")}, key=str.casefold)
    showcase_collections = {
        kind: sorted({
            str(group.get("name") or "")
            for row in prompts
            if ("template" if str(row.get("kind") or "").casefold() == "template" else "prompt") == kind
            for group in row.get("collections") or []
            if isinstance(group, dict) and str(group.get("name") or "")
        }, key=str.casefold)
        for kind in ("prompt", "template")
    }
    wardrobe_categories: dict[str, dict[str, int]] = {}
    shareable_collections: dict[str, dict[str, int]] = {"outfit": {}, "scene": {}, "wardrobe": {}}
    for row in components:
        kind = str(row.get("kind") or "")
        if kind not in shareable_collections: continue
        for group in row.get("pack_collections") or []:
            if isinstance(group, dict) and str(group.get("name") or ""):
                name = str(group.get("name") or ""); shareable_collections[kind][name] = shareable_collections[kind].get(name, 0) + 1
    for row in data.get("wardrobe_items") or []:
        if not isinstance(row, dict):
            continue
        category = str(row.get("category") or "Uncategorized")
        subtype = str(row.get("subtype") or "")
        wardrobe_categories.setdefault(category, {})[subtype] = wardrobe_categories.setdefault(category, {}).get(subtype, 0) + 1
        for group in row.get("pack_collections") or []:
            if isinstance(group, dict) and str(group.get("name") or ""):
                name = str(group.get("name") or ""); shareable_collections["wardrobe"][name] = shareable_collections["wardrobe"].get(name, 0) + 1
    return {
        "counts": {
            "templates": sum(1 for row in prompts if str(row.get("kind") or "").casefold() == "template"),
            "prompts": sum(1 for row in prompts if str(row.get("kind") or "").casefold() != "template"),
            "recipes": len(data.get("recipes") or []),
            "outfits": sum(1 for row in components if str(row.get("kind") or "") == "outfit"),
            "scenes": sum(1 for row in components if str(row.get("kind") or "") == "scene"),
            "wardrobe": len(data.get("wardrobe_items") or []),
            "fragments": len(data.get("fragments") or []),
            "boards": len(data.get("boards") or []),
        },
        "prompt_homes": prompt_homes,
        "prompt_logs": prompt_logs,
        "prompt_collections": showcase_collections["prompt"],
        "showcase_collections": showcase_collections,
        "recipe_collections": recipe_collections,
        "component_taxonomy": component_taxonomy,
        "wardrobe_categories": wardrobe_categories,
        "shareable_collections": shareable_collections,
    }

def _library_pack_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _creative_library_pack_export(payload: dict[str, Any]) -> tuple[bytes, str, dict[str, Any]]:
    catalog = get_catalog()
    mode = str(payload.get("mode") or "starter").strip().lower()
    if mode not in {"starter", "backup"}:
        mode = "starter"
    name = _single_line_recipe_prompt(payload.get("name") or ("Sick Ollie Library Pack" if mode == "starter" else "Sick Ollie Creative Library Backup"))
    name = name or ("Sick Ollie Library Pack" if mode == "starter" else "Sick Ollie Creative Library Backup")
    creator = _single_line_recipe_prompt(payload.get("creator") or "")
    version = _single_line_recipe_prompt(payload.get("version") or "1.0") or "1.0"
    description = str(payload.get("description") or "").strip()
    supplied_pack_id = str(payload.get("pack_id") or "").strip()
    if supplied_pack_id:
        pack_id = supplied_pack_id
    else:
        identity = f"{creator.casefold()}\0{name.casefold()}"
        pack_id = f"soslibrary:{hashlib.sha1(identity.encode('utf-8')).hexdigest()}"

    full_snapshot = _creative_library_pack_snapshot(mode)
    snapshot, selection = _scope_creative_library_snapshot(full_snapshot, payload.get("selection"))
    previous_component_memberships = catalog.creative_library_pack_component_membership_snapshot(pack_id)
    selected_component_keys = {
        (str(row.get("kind") or ""), str(row.get("value") or "").casefold())
        for row in snapshot.get("components") or [] if isinstance(row, dict)
    }
    previous_component_memberships = [
        row for row in previous_component_memberships
        if isinstance(row, dict) and (str(row.get("kind") or ""), str(row.get("value") or "").casefold()) in selected_component_keys
    ]
    contents = _creative_library_pack_contents(snapshot)
    counts = {
        "templates": contents["counts"]["templates"],
        "prompts": contents["counts"]["prompts"],
        "recipes": contents["counts"]["recipes"],
        "outfits": contents["counts"]["outfits"],
        "scenes": contents["counts"]["scenes"],
        "wardrobe_items": contents["counts"]["wardrobe"],
        "workshop_fragments": contents["counts"]["fragments"],
        "boards": contents["counts"]["boards"],
    }
    manifest = {
        "format": "sickollie-creative-library-pack",
        "schema_version": 3,
        "export_mode": mode,
        "pack_id": pack_id,
        "name": name,
        "creator": creator,
        "version": version,
        "description": description,
        "created_at": _library_pack_timestamp(),
        "counts": counts,
        "contents": contents,
        "selection": selection,
        "capabilities": ["scoped-export", "manifest-preview", "selective-import", "optional-thumbnails", "dependency-aware", "structure-order", "collections", "prompt-variants"],
        "merge_policy": "preserve-local-reconcile-pack-memberships",
    }
    file_map = {
        "library/structure-order.json": snapshot.get("structure_order") or {},
        "library/recipe-collections.json": snapshot.get("recipe_collections") or [],
        "library/prompt-showcase-collections.json": snapshot.get("prompt_showcase_collections") or [],
        "library/prompts.json": snapshot.get("prompts") or [],
        "library/recipes.json": snapshot.get("recipes") or [],
        "library/component-collections.json": snapshot.get("component_collections") or [],
        "library/shareable-collections.json": snapshot.get("library_collections") or [],
        "library/components.json": snapshot.get("components") or [],
        "library/wardrobe-items.json": snapshot.get("wardrobe_items") or [],
        "library/wardrobe-relations.json": snapshot.get("wardrobe_relations") or [],
        "library/fragments.json": snapshot.get("fragments") or [],
    }
    if previous_component_memberships:
        file_map["library/previous-component-memberships.json"] = previous_component_memberships
        manifest["membership_baseline"] = "installed-pack-state"
    if mode == "backup":
        file_map["library/boards.json"] = snapshot.get("boards") or []
        file_map["library/tombstones.json"] = snapshot.get("tombstones") or []
        file_map["library/backup-extras.json"] = snapshot.get("backup_extras") or {}

    buffer = BytesIO()
    thumbnail_count = 0
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for member, value in file_map.items():
            archive.writestr(member, json.dumps(value, ensure_ascii=False, indent=2))
        added_preview_members: set[str] = set()
        if selection["include_thumbnails"]:
            preview_sets = (
                ("prompts", snapshot.get("prompts") or [], _preview_directory()),
                ("recipes", snapshot.get("recipes") or [], _preview_directory()),
                ("components", snapshot.get("components") or [], _component_preview_directory()),
                ("wardrobe", snapshot.get("wardrobe_items") or [], _component_preview_directory()),
            )
            for preview_kind, rows, directory in preview_sets:
                for entry in rows:
                    filename = Path(str(entry.get("preview_ref") or "")).name
                    source = directory / filename if filename else None
                    if source and source.is_file():
                        member = f"previews/{preview_kind}/{filename}"
                        if member not in added_preview_members:
                            archive.write(source, member)
                            added_preview_members.add(member)
                            thumbnail_count += 1
    manifest["counts"]["thumbnails"] = thumbnail_count
    raw = buffer.getvalue()
    rebuilt = BytesIO()
    with zipfile.ZipFile(BytesIO(raw), "r") as source_zip, zipfile.ZipFile(rebuilt, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as out:
        for info in source_zip.infolist():
            if info.filename == "manifest.json":
                out.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            else:
                out.writestr(info, source_zip.read(info.filename))
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-._") or "sick-ollie-library"
    suffix = "backup" if mode == "backup" else "pack"
    return rebuilt.getvalue(), f"{safe_name}-{suffix}-v{version}.soslibrary", manifest


def _read_library_pack_json(archive: zipfile.ZipFile, member: str, default: Any) -> Any:
    if member not in archive.namelist():
        return default
    raw = archive.read(member)
    if len(raw) > 256 * 1024 * 1024:
        raise ValueError(f"Library Pack member is too large: {member}")
    return json.loads(raw.decode("utf-8"))


def _safe_pack_preview_bytes(archive: zipfile.ZipFile, member: str) -> tuple[bytes, str] | None:
    clean = str(member or "").replace("\\", "/")
    if not clean or clean.startswith("/") or ".." in Path(clean).parts or clean not in archive.namelist():
        return None
    suffix = Path(clean).suffix.casefold()
    if suffix not in {".webp", ".png", ".jpg", ".jpeg"}:
        return None
    info = archive.getinfo(clean)
    if info.file_size <= 0 or info.file_size > 50 * 1024 * 1024:
        return None
    raw = archive.read(clean)
    try:
        with Image.open(BytesIO(raw)) as image:
            image.verify()
    except Exception:
        return None
    return raw, suffix


def _load_creative_library_pack_data(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with zipfile.ZipFile(path, "r") as archive:
        if "manifest.json" not in archive.namelist():
            raise ValueError("This is not a valid Sick Ollie Creative Library Pack")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        schema_version = int(manifest.get("schema_version") or 0)
        if manifest.get("format") != "sickollie-creative-library-pack" or schema_version not in {1, 2, 3}:
            raise ValueError("Unsupported Creative Library Pack format/version")
        data = {
            "mode": str(manifest.get("export_mode") or "starter"),
            "structure_order": _read_library_pack_json(archive, "library/structure-order.json", {}),
            "recipe_collections": _read_library_pack_json(archive, "library/recipe-collections.json", []),
            "prompt_showcase_collections": _read_library_pack_json(archive, "library/prompt-showcase-collections.json", []),
            "prompts": _read_library_pack_json(archive, "library/prompts.json", []),
            "recipes": _read_library_pack_json(archive, "library/recipes.json", []),
            "component_collections": _read_library_pack_json(archive, "library/component-collections.json", []),
            "library_collections": _read_library_pack_json(archive, "library/shareable-collections.json", []),
            "components": _read_library_pack_json(archive, "library/components.json", []),
            "wardrobe_items": _read_library_pack_json(archive, "library/wardrobe-items.json", []),
            "wardrobe_relations": _read_library_pack_json(archive, "library/wardrobe-relations.json", []),
            "fragments": _read_library_pack_json(archive, "library/fragments.json", []),
            "boards": _read_library_pack_json(archive, "library/boards.json", []),
            "tombstones": _read_library_pack_json(archive, "library/tombstones.json", []),
            "backup_extras": _read_library_pack_json(archive, "library/backup-extras.json", {}),
            "previous_component_memberships": _read_library_pack_json(archive, "library/previous-component-memberships.json", []),
        }
    limits = {"prompts": 250000, "recipes": 50000, "prompt_showcase_collections": 10000, "library_collections": 10000, "components": 250000, "wardrobe_items": 250000, "wardrobe_relations": 1000000, "fragments": 500000, "boards": 50000, "previous_component_memberships": 250000}
    for key, maximum in limits.items():
        value = data.get(key)
        if not isinstance(value, list):
            raise ValueError(f"Creative Library Pack {key} data is malformed")
        if len(value) > maximum:
            raise ValueError(f"Creative Library Pack contains too many {key.replace('_', ' ')}")
    if not isinstance(data.get("structure_order"), dict):
        raise ValueError("Creative Library Pack structure order data is malformed")
    return manifest, data


def _creative_library_pack_inspect(path: Path) -> dict[str, Any]:
    manifest, data = _load_creative_library_pack_data(path)
    contents = _creative_library_pack_contents(data)
    return {
        "ok": True,
        "manifest": {
            "name": str(manifest.get("name") or "Creative Library Pack"),
            "creator": str(manifest.get("creator") or ""),
            "version": str(manifest.get("version") or ""),
            "description": str(manifest.get("description") or ""),
            "export_mode": str(manifest.get("export_mode") or "starter"),
            "schema_version": int(manifest.get("schema_version") or 1),
            "pack_id": str(manifest.get("pack_id") or ""),
            "counts": manifest.get("counts") if isinstance(manifest.get("counts"), dict) else contents["counts"],
        },
        "contents": contents,
    }


def _creative_library_pack_import(path: Path, raw_selection: Any = None) -> dict[str, Any]:
    catalog = get_catalog()
    manifest, data = _load_creative_library_pack_data(path)
    selection = _normalize_pack_selection(raw_selection, mode=str(manifest.get("export_mode") or "starter"))
    scoped_data, effective_selection = _scope_creative_library_snapshot(data, selection)
    selected_component_keys = {
        (str(row.get("kind") or ""), str(row.get("value") or "").casefold())
        for row in scoped_data.get("components") or [] if isinstance(row, dict)
    }
    scoped_data["previous_component_memberships"] = [
        copy.deepcopy(row) for row in data.get("previous_component_memberships") or []
        if isinstance(row, dict) and (str(row.get("kind") or ""), str(row.get("value") or "").casefold()) in selected_component_keys
    ]
    partial = (
        any(len(scoped_data.get(key) or []) != len(data.get(key) or []) for key in ("prompts", "recipes", "components", "wardrobe_items", "wardrobe_relations", "fragments", "boards"))
        or not effective_selection["include_taxonomy"]
    )
    merge_manifest = copy.deepcopy(manifest)
    merge_manifest["selective_import"] = bool(partial)
    merge_manifest["import_taxonomy"] = bool(effective_selection["include_taxonomy"])
    merge_manifest["import_selection"] = effective_selection

    with zipfile.ZipFile(path, "r") as archive:
        merge = catalog.merge_creative_library_pack_records(merge_manifest, scoped_data)
        pack_id = str(merge.get("pack_id") or manifest.get("pack_id") or "")
        preview_queue = merge.pop("preview_queue", {}) if isinstance(merge.get("preview_queue"), dict) else {}
        source = f"creative-library-pack:{pack_id}"
        saved: dict[str, list[dict[str, str]]] = {"prompts": [], "recipes": [], "components": [], "wardrobe": []}
        destinations = {
            "prompts": _preview_directory(), "recipes": _preview_directory(),
            "components": _component_preview_directory(), "wardrobe": _component_preview_directory(),
        }
        previews_added = 0
        if effective_selection["include_thumbnails"]:
            for kind in saved:
                for entry in preview_queue.get(kind) or []:
                    if not isinstance(entry, dict):
                        continue
                    target_id = str(entry.get("id") or "").strip()
                    member = str(entry.get("member") or "").strip()
                    current_ref = str(entry.get("current_ref") or "")
                    current_filename = Path(current_ref).name
                    if current_filename and (destinations[kind] / current_filename).is_file():
                        continue
                    checked = _safe_pack_preview_bytes(archive, member)
                    if not target_id or not checked:
                        continue
                    raw, suffix = checked
                    digest = hashlib.sha1(f"{kind}\0{target_id}".encode("utf-8")).hexdigest()
                    filename = f"library_pack_{kind}_{digest}{suffix}"
                    destinations[kind].mkdir(parents=True, exist_ok=True)
                    target = destinations[kind] / filename
                    if not target.exists():
                        target.write_bytes(raw)
                    saved[kind].append({"id": target_id, "filename": filename, "replace_ref": current_ref})
                    previews_added += 1
        catalog.set_creative_library_pack_previews_bulk(
            prompts=saved["prompts"], recipes=saved["recipes"], components=saved["components"], wardrobe=saved["wardrobe"], source=source,
        )

    _safe_sync_recipe_prompt_logs()
    return {
        "ok": True, **merge, "previews_added": previews_added, "selective": partial,
        "selection": effective_selection,
        "manifest": {"name": manifest.get("name"), "version": manifest.get("version"), "export_mode": manifest.get("export_mode"), "counts": manifest.get("counts")},
    }


def _creative_library_orphan_previews(*, delete: bool = False) -> dict[str, Any]:
    catalog = get_catalog()
    with catalog._connection() as db:  # same local catalog; read-only reference scan
        referenced = {
            Path(str(row[0] or "")).name
            for query in (
                "SELECT preview_ref FROM prompt_assets WHERE preview_ref<>''",
                "SELECT preview_ref FROM recipes WHERE preview_ref<>''",
                "SELECT preview_ref FROM recipe_components WHERE preview_ref<>''",
                "SELECT preview_ref FROM wardrobe_items WHERE preview_ref<>''",
            )
            for row in db.execute(query).fetchall() if Path(str(row[0] or "")).name
        }
    groups = (("creative-library", _preview_directory(), referenced),)
    orphan_rows: list[dict[str, Any]] = []
    total_bytes = 0
    deleted = 0
    deleted_bytes = 0
    for group, directory, referenced in groups:
        for target in directory.iterdir():
            if not target.is_file() or target.name in referenced:
                continue
            if target.suffix.casefold() not in {".webp", ".png", ".jpg", ".jpeg"}:
                continue
            try:
                size = int(target.stat().st_size)
            except OSError:
                size = 0
            orphan_rows.append({"group": group, "name": target.name, "bytes": size})
            total_bytes += size
            if delete:
                try:
                    target.unlink()
                    deleted += 1
                    deleted_bytes += size
                except OSError:
                    pass
    orphan_rows.sort(key=lambda row: (str(row["group"]), str(row["name"]).casefold()))
    return {
        "ok": True,
        "dry_run": not delete,
        "orphans": len(orphan_rows),
        "bytes": total_bytes,
        "deleted": deleted,
        "deleted_bytes": deleted_bytes,
        "files": orphan_rows[:500],
        "truncated": len(orphan_rows) > 500,
    }

def _save_component_preview(image: Image.Image, kind: str, value: str) -> str:
    component_id = get_catalog().recipe_component_id(kind, value).replace(":", "_")
    filename = f"{component_id}.webp"
    _write_library_preview(image, _component_preview_directory() / filename)
    return filename


def _save_wardrobe_preview(image: Image.Image, item_type: str, value: str) -> str:
    wardrobe_id = get_catalog().wardrobe_item_id(item_type, value).replace(":", "_")
    filename = f"{wardrobe_id}.webp"
    _write_library_preview(image, _component_preview_directory() / filename)
    return filename

def _purge_wardrobe() -> dict[str, Any]:
    """Purge only the derived Wardrobe layer and its cached thumbnails."""
    result = get_catalog().purge_wardrobe()
    deleted_previews = 0
    preview_dir = _component_preview_directory()
    for preview_ref in result.pop("preview_refs", []):
        filename = Path(str(preview_ref or "")).name
        if not filename:
            continue
        path = preview_dir / filename
        existed = path.is_file()
        path.unlink(missing_ok=True)
        if existed:
            deleted_previews += 1
    result["previews_deleted"] = deleted_previews
    return result

PREVIEW_VERIFY_PROMPT_FIELDS = {
    "manual_prompt", "prompt_log_file", "prompt_index",
    *(name for letter in "ABC" for name in (
        f"outfit_token_{letter}", f"outfit_placement_{letter}", f"outfit_log_file_{letter}", f"outfit_index_{letter}",
    )),
    "scene_token", "scene_placement", "scene_log_file", "scene_index",
    "name_token", "name_value", "item_token", "item_value",
    "prefix_enabled", "prefix_text", "suffix_enabled", "suffix_text",
}
PREVIEW_VERIFY_GENERATION_FIELDS = {
    "custom_width", "custom_height", "seed_value", "clip_name", "clip_type", "clip_device", "vae_name",
}
PREVIEW_VERIFY_LOADER_FIELDS = {
    "diffusion_model", "weight_dtype", "main_lora", "main_strength",
    *(f"secondary_lora_{index}" for index in range(1, 11)),
}


def _recipe_verification_values(payload: dict[str, Any]) -> dict[str, Any]:
    curated = _curate_prompt_catalog_recipe(dict(payload or {}))
    values: dict[str, Any] = {}
    prompt = _recipe_node_values(curated, STUDIO_PROMPT)
    generation = _recipe_node_values(curated, STUDIO_GENERATION, include_optional=True)
    loader = _recipe_node_values(curated, STUDIO_LOADER, include_optional=True)
    for name in PREVIEW_VERIFY_PROMPT_FIELDS:
        if name in prompt:
            values[f"prompt.{name}"] = prompt[name]
    for name in PREVIEW_VERIFY_GENERATION_FIELDS:
        if name in generation:
            values[f"generation.{name}"] = generation[name]
    for name in PREVIEW_VERIFY_LOADER_FIELDS:
        if name in loader:
            values[f"loader.{name}"] = loader[name]
    return values


def _preview_recipe_matches(saved_payload: dict[str, Any], image_payload: dict[str, Any]) -> tuple[bool, str]:
    saved = _recipe_verification_values(saved_payload)
    image = _recipe_verification_values(image_payload)
    if not saved:
        return False, "The saved recipe had no prompt, dimensions, or resolved seed fields that could be verified."
    missing = [key for key in saved if key not in image]
    if missing:
        return False, f"The Preview image metadata was missing {missing[0]}."
    for key, value in saved.items():
        if json.dumps(value, sort_keys=True, default=str) != json.dumps(image.get(key), sort_keys=True, default=str):
            return False, f"The Preview image did not match the saved recipe at {key}."
    return True, "Verified against embedded Preview metadata."


def _preview_authoritative_recipe(current_payload: dict[str, Any], image_payload: dict[str, Any]) -> dict[str, Any]:
    """Use the displayed Preview image as the source of truth for a quick-save.

    Prompt/log indices can advance immediately after queueing, so the live node
    widgets may already describe the *next* image. The Preview PNG contains the
    resolved metadata for the image actually on screen and is therefore the
    only safe source for both recipe values and its thumbnail.
    """
    recipe = _curate_prompt_catalog_recipe(dict(image_payload or {}))
    if not recipe.get("nodes"):
        raise ValueError("The Preview image metadata did not contain a usable prompt, dimensions, or resolved seed")
    recipe.pop("imported_from_image", None)
    recipe.pop("migration", None)
    recipe["captured_from_preview"] = True
    if isinstance(current_payload, dict) and current_payload.get("captured_at"):
        recipe["captured_at"] = current_payload["captured_at"]
    recipe["tokens"] = _recipe_tokens(recipe)
    return recipe


def _runtime_structured_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """Recover resolved runtime metadata from Studio *and* Classic PNGs.

    Modern Output Core writes one consolidated ``so_image_metadata`` block.
    Older Classic nodes predate that block but already embedded extremely useful
    flat fields such as ``source_prompt``, ``resolved_prompt``,
    ``outfit_log_line`` and ``scene_log_line``.  Treat those fields as a real
    compatibility source rather than falling back to the flattened A1111-style
    parameters string, otherwise a Classic template that contained OUTFIT is
    misclassified as a ready Prompt instead of a reusable Recipe.
    """
    def runtime_value(key: str, fallback: Any = None) -> Any:
        raw = metadata.get(key, fallback)
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except (TypeError, ValueError):
                return raw
        return raw

    structured = _json_value(metadata.get("so_image_metadata"), {})
    if isinstance(structured, dict) and structured:
        return structured

    resolved = _json_value(metadata.get("so_prompt_core_resolved"), {})
    if not isinstance(resolved, dict):
        resolved = {}

    # Sick Ollie Classic compatibility.  These fields were already embedded by
    # Classic Output Core and are more semantically useful than the generic
    # Comfy API graph because they preserve the unresolved OUTFIT/SCENE template
    # alongside the exact line that was substituted into the rendered image.
    source_prompt = str(runtime_value("source_prompt", "") or "").strip()
    prompt_log_line = str(runtime_value("prompt_log_line", "") or "").strip()
    final_prompt = str(runtime_value("resolved_prompt", "") or "").strip()
    outfit_line = str(runtime_value("outfit_log_line", "") or "").strip()
    scene_line = str(runtime_value("scene_log_line", "") or "").strip()
    if source_prompt or prompt_log_line or final_prompt or outfit_line or scene_line:
        if source_prompt:
            resolved.setdefault("source_prompt", source_prompt)
        elif prompt_log_line:
            resolved.setdefault("source_prompt", prompt_log_line)
        if final_prompt:
            resolved.setdefault("final_prompt", final_prompt)
        prompt_meta = resolved.get("prompt") if isinstance(resolved.get("prompt"), dict) else {}
        if prompt_log_line or source_prompt:
            prompt_meta.setdefault("line", prompt_log_line or source_prompt)
        if prompt_meta:
            resolved["prompt"] = prompt_meta
        if outfit_line:
            outfit = resolved.get("outfit_a") if isinstance(resolved.get("outfit_a"), dict) else {}
            outfit.update({"used": True, "token": str(runtime_value("outfit_token", "OUTFIT") or "OUTFIT"), "line": outfit_line})
            resolved["outfit_a"] = outfit
        if scene_line:
            scene = resolved.get("scene") if isinstance(resolved.get("scene"), dict) else {}
            scene.update({"used": True, "token": str(runtime_value("scene_token", "SCENE") or "SCENE"), "line": scene_line})
            resolved["scene"] = scene

        # Recover source-log provenance from the Classic API graph when it is
        # present.  The exact line remains the authority; file/index are useful
        # only as provenance and for Recipe reconstruction.
        api_graph = _json_value(metadata.get("prompt"), {})
        if isinstance(api_graph, dict):
            for raw_node in api_graph.values():
                if not isinstance(raw_node, dict) or str(raw_node.get("class_type") or "") != "SOPromptLogEngine":
                    continue
                inputs = raw_node.get("inputs") if isinstance(raw_node.get("inputs"), dict) else {}
                prompt_meta = resolved.get("prompt") if isinstance(resolved.get("prompt"), dict) else {}
                if inputs.get("prompt_log_file"):
                    prompt_meta.setdefault("file", inputs.get("prompt_log_file"))
                if inputs.get("prompt_index") is not None:
                    prompt_meta.setdefault("index", inputs.get("prompt_index"))
                if prompt_meta:
                    resolved["prompt"] = prompt_meta
                if outfit_line:
                    outfit = resolved.get("outfit_a") if isinstance(resolved.get("outfit_a"), dict) else {}
                    outfit_file = inputs.get("outfit_log_file") or inputs.get("outfit_log_file_A")
                    outfit_index = inputs.get("outfit_index") if inputs.get("outfit_index") is not None else inputs.get("outfit_index_A")
                    if outfit_file:
                        outfit.setdefault("file", outfit_file)
                    if outfit_index is not None:
                        outfit.setdefault("index", outfit_index)
                    resolved["outfit_a"] = outfit
                if scene_line:
                    scene = resolved.get("scene") if isinstance(resolved.get("scene"), dict) else {}
                    if inputs.get("scene_log_file"):
                        scene.setdefault("file", inputs.get("scene_log_file"))
                    if inputs.get("scene_index") is not None:
                        scene.setdefault("index", inputs.get("scene_index"))
                    resolved["scene"] = scene
                break

    generation = _json_value(metadata.get("so_generation_info"), {})
    if not isinstance(generation, dict):
        generation = {}
    for target, source in (
        ("seed_used", "so_generation_seed_used"),
        ("width", "so_generation_width"),
        ("height", "so_generation_height"),
        ("shift", "so_generation_shift"),
        ("clip_name", "so_generation_clip_name"),
        ("vae_name", "so_generation_vae_name"),
    ):
        value = runtime_value(source, None)
        if value not in (None, ""):
            generation.setdefault(target, value)

    models: dict[str, Any] = {}
    diffusion_model = str(runtime_value("so_loader_core_diffusion_model", "") or "")
    weight_dtype = str(runtime_value("so_loader_core_weight_dtype", "") or "")
    if diffusion_model:
        models["diffusion_model"] = diffusion_model
    if weight_dtype:
        models["weight_dtype"] = weight_dtype

    main_active = bool(runtime_value("so_loader_core_main_active", False))
    main_file = str(runtime_value("so_loader_core_main_file", "") or "")
    if main_active and main_file:
        models["main_lora"] = {
            "file": main_file,
            "strength": runtime_value("so_loader_core_main_strength", 1.0),
        }

    secondary = runtime_value("so_loader_core_secondary_loras", [])
    if isinstance(secondary, list):
        cleaned = [dict(item) for item in secondary if isinstance(item, dict) and item.get("file")]
        if cleaned:
            models["secondary_loras"] = cleaned

    # Classic Loader Core stored the actual applied LoRA paths as a compact
    # ``path@strength`` list.  Recover it when modern main/secondary fields do
    # not exist so old outputs keep substantially better Loader provenance.
    classic_loras = runtime_value("so_loader_core_applied_loras", [])
    if isinstance(classic_loras, list) and classic_loras and not models.get("main_lora"):
        parsed_loras: list[dict[str, Any]] = []
        for raw in classic_loras:
            text = str(raw or "").strip()
            if not text:
                continue
            file_name, strength = text, 1.0
            if "@" in text:
                file_name, strength_text = text.rsplit("@", 1)
                try:
                    strength = float(strength_text)
                except ValueError:
                    strength = 1.0
            parsed_loras.append({"file": file_name, "strength": strength})
        if parsed_loras:
            models["main_lora"] = parsed_loras[0]
            if len(parsed_loras) > 1:
                models["secondary_loras"] = parsed_loras[1:]

    if not resolved and not generation and not models:
        return None
    return {
        "schema_version": 1,
        "format": "Sick Ollie Runtime / Classic Metadata",
        "resolved": resolved,
        "generation": generation,
        "models": models,
    }


def _recipe_from_image_bytes(raw: bytes) -> tuple[dict[str, Any], Image.Image]:
    with Image.open(BytesIO(raw)) as image:
        metadata = dict(image.info)
        # PNG text chunks live in ``image.info``. JPG/WEBP outputs commonly put
        # the same metadata dictionary in EXIF UserComment, including Sick
        # Ollie Output Core. Merge it here so image import is format-agnostic.
        try:
            exif = image.getexif()
            comment = exif.get(0x9286) if exif else None
            if isinstance(comment, bytes):
                for prefix in (b"ASCII\x00\x00\x00", b"UNICODE\x00", b"JIS\x00\x00\x00\x00\x00"):
                    if comment.startswith(prefix):
                        comment = comment[len(prefix):]
                        break
                comment = comment.decode("utf-8", errors="replace")
            if isinstance(comment, str) and comment.strip():
                decoded_comment = _json_value(comment, {})
                if isinstance(decoded_comment, dict):
                    for key, value in decoded_comment.items():
                        metadata.setdefault(str(key), value)
        except Exception:
            pass
        image_size = image.size
        preview_image = image.copy()
    api_graph = _json_value(metadata.get("prompt"), {})
    workflow = _json_value(metadata.get("workflow"), {})
    parameters = str(metadata.get("parameters") or "")
    structured = _runtime_structured_metadata(metadata)
    if not structured:
        generic = generic_top_level_metadata(metadata)
        if generic:
            resolved: dict[str, Any] = {}
            prompt = str(generic.get("prompt") or "").strip()
            if prompt:
                resolved = {"source_prompt": prompt, "final_prompt": prompt}
            generation = {
                target: generic[source]
                for target, source in (
                    ("seed_used", "seed_value"), ("steps", "steps"), ("cfg", "cfg"),
                    ("sampler_name", "sampler_name"), ("scheduler", "scheduler"),
                    ("width", "custom_width"), ("height", "custom_height"),
                )
                if generic.get(source) is not None
            }
            if generic.get("negative_prompt"):
                generation["negative_prompt"] = generic["negative_prompt"]
            models: dict[str, Any] = {}
            if generic.get("diffusion_model"):
                models["diffusion_model"] = generic["diffusion_model"]
            if generic.get("diffusion_model_hash"):
                models["diffusion_model_hash"] = generic["diffusion_model_hash"]
            if generic.get("vae_name"):
                models["vae"] = generic["vae_name"]
            if generic.get("vae_hash"):
                models["vae_hash"] = generic["vae_hash"]
            loras = generic.get("loras") if isinstance(generic.get("loras"), list) else []
            if loras:
                first = loras[0] if isinstance(loras[0], dict) else {}
                if first.get("file"):
                    models["main_lora"] = {"file": first.get("file"), "strength": first.get("strength", 1.0)}
                secondary = [dict(item) for item in loras[1:] if isinstance(item, dict) and item.get("file")]
                if secondary:
                    models["secondary_loras"] = secondary
            structured = {
                "schema_version": 1,
                "format": "Generic image generation metadata",
                "resolved": resolved,
                "generation": generation,
                "models": models,
            }

    payload: dict[str, Any]
    if isinstance(api_graph, dict) and api_graph:
        payload = _api_to_studio_recipe(api_graph, parameters)
    elif parameters:
        payload = _api_to_studio_recipe({}, parameters)
    elif isinstance(workflow, dict) and workflow:
        payload = _legacy_to_studio_recipe(workflow)
    elif structured:
        payload = {"schema": 3, "imported_from_image": True, "nodes": []}
    else:
        raise ValueError("This image contains no embedded ComfyUI, A1111/Civitai, or Sick Ollie generation metadata.")

    payload = _structured_metadata_overlay(payload, structured)
    if not payload.get("nodes"):
        raise ValueError("The embedded metadata did not contain prompt, generation, model, LoRA, VAE, or output settings that can be migrated")
    payload = _apply_resolved_dimensions(payload, structured, image_size)
    payload = _curate_prompt_catalog_recipe(payload)
    if not payload.get("nodes"):
        raise ValueError("The embedded metadata did not contain a usable prompt, resolved dimensions, or resolved seed")
    payload["metadata_sources"] = [key for key in (
        "so_image_metadata", "so_prompt_core_resolved", "so_generation_info",
        "so_generation_seed_used", "so_loader_core_main_file", "prompt", "workflow", "parameters",
    ) if metadata.get(key) not in (None, "", [], {})]
    payload["tokens"] = _recipe_tokens(payload)
    return payload, preview_image


def _workflow_node_values(node: dict[str, Any]) -> dict[str, Any]:
    """Normalize Comfy workflow and API-prompt nodes into named values."""
    values = node.get("inputs")
    if isinstance(values, dict):
        return values
    widgets = list(node.get("widgets_values") or [])
    node_type = str(node.get("type") or node.get("class_type") or "")
    positional = {
        "CLIPTextEncode": ("text",),
        "KSampler": ("seed", "steps", "cfg", "sampler_name", "scheduler", "denoise"),
        "KSamplerAdvanced": ("add_noise", "noise_seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "start_at_step", "end_at_step", "return_with_leftover_noise"),
        "EmptyLatentImage": ("width", "height", "batch_size"),
        "UNETLoader": ("unet_name", "weight_dtype"),
        "CheckpointLoaderSimple": ("ckpt_name",),
        "LoraLoader": ("lora_name", "strength_model", "strength_clip"),
        "VAELoader": ("vae_name",),
        "SaveImage": ("filename_prefix",),
        # Sick Ollie Classic — these are deliberately named here rather than
        # inferred from generic widgets, so classic output becomes a first-class
        # Studio migration path.
        "SOPromptLogEngine": (
            "prompt_source", "manual_prompt", "prompt_log_file", "prompt_mode", "prompt_index",
            "outfit_token_A", "outfit_log_file_A", "outfit_mode_A", "outfit_index_A",
            "outfit_token_B", "outfit_log_file_B", "outfit_mode_B", "outfit_index_B",
            "outfit_token_C", "outfit_log_file_C", "outfit_mode_C", "outfit_index_C",
            "scene_token", "scene_log_file", "scene_mode", "scene_index", "name_token", "name_value",
            "item_token", "item_value", "prefix_enabled", "prefix_text", "suffix_enabled", "suffix_text",
        ),
        "SOGenerationPipeline": (
            "clip_name", "clip_type", "clip_device", "vae_name", "resolution_mode", "custom_width",
            "custom_height", "aspect_preset", "megapixels", "batch_size", "steps", "cfg", "sampler_name",
            "scheduler", "denoise", "shift", "seed_value",
        ),
        "SOLoaderCoreEngine": (
            "diffusion_model", "weight_dtype", "folder_name", "epoch_filter", "main_enabled", "main_lora",
            "main_strength", "include_subfolders", "loop_folder", "control_after_generate",
        ),
        "SOOutputBuilderSave": (
            "output_root", "subfolder_literal", "subfolder_var_1", "subfolder_var_2", "subfolder_var_3",
            "subfolder_var_4", "subfolder_delimiter", "filename_literal", "filename_var_1", "filename_var_2",
            "filename_var_3", "filename_var_4", "filename_var_5", "filename_var_6", "filename_delimiter",
            "extension", "quality", "counter_digits", "save_prompt_json", "save_workflow_json", "save_civitai_parameters",
        ),
    }.get(node_type, ())
    return {key: widgets[index] for index, key in enumerate(positional) if index < len(widgets)}


def _scalar(value: Any) -> Any:
    """Drop Comfy links; only literal values are safe to migrate into widgets."""
    return value if not isinstance(value, (list, dict)) else None


def _json_value(value: Any, fallback: Any = None) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return value if value is not None else fallback


def _api_nodes(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(key): value for key, value in graph.items() if isinstance(value, dict) and value.get("class_type")}


def _resolve_api_value(value: Any, nodes: dict[str, dict[str, Any]], seen: set[str] | None = None) -> Any:
    if not (isinstance(value, list) and len(value) >= 2):
        return value
    node_id = str(value[0])
    seen = set(seen or ())
    if node_id in seen or node_id not in nodes:
        return None
    seen.add(node_id)
    node = nodes[node_id]
    kind = str(node.get("class_type") or "")
    inputs = node.get("inputs") or {}
    resolve = lambda item: _resolve_api_value(item, nodes, seen)
    if kind in {"PrimitiveString", "PrimitiveStringMultiline", "Text Prompt (JPS)"}:
        return resolve(inputs.get("value", inputs.get("text", "")))
    if kind in {"PrimitiveBoolean"}:
        return bool(resolve(inputs.get("value")))
    if kind in {"Seed (rgthree)", "Seed"}:
        return resolve(inputs.get("seed", inputs.get("value")))
    if kind in {"StringConcatenate", "Text Concatenate"}:
        delimiter = str(resolve(inputs.get("delimiter")) or "")
        keys = ("string_a", "string_b") if kind == "StringConcatenate" else ("text_a", "text_b", "text_c")
        return delimiter.join(str(resolve(inputs.get(key)) or "") for key in keys)
    if kind == "ComfySwitchNode":
        switch = bool(resolve(inputs.get("switch")))
        return resolve(inputs.get("on_true" if switch else "on_false"))
    if kind in {"PreviewAny", "Display Any (rgthree)"}:
        return resolve(inputs.get("source", inputs.get("output")))
    if kind == "RegexReplace":
        source = str(resolve(inputs.get("string")) or "")
        pattern = str(resolve(inputs.get("regex_pattern")) or "")
        replacement = str(resolve(inputs.get("replace")) or "")
        try:
            flags = re.IGNORECASE if bool(resolve(inputs.get("case_insensitive"))) else 0
            return re.sub(pattern, replacement, source, count=int(resolve(inputs.get("count")) or 0), flags=flags)
        except (re.error, ValueError):
            return source
    for key in ("value", "text", "source", "output"):
        if key in inputs:
            return resolve(inputs[key])
    return None


def _named_node(node_type: str, title: str, values: dict[str, Any]) -> dict[str, Any]:
    return {"type": node_type, "title": title, "widgets": [{"name": key, "value": value} for key, value in values.items() if value is not None]}


def _merge_recipe_nodes(payload: dict[str, Any], node_type: str, title: str, values: dict[str, Any]) -> None:
    target = next((node for node in payload.setdefault("nodes", []) if node.get("type") == node_type), None)
    if target is None:
        payload["nodes"].append(_named_node(node_type, title, values))
        return
    widgets = target.setdefault("widgets", [])
    by_name = {str(widget.get("name")): widget for widget in widgets if isinstance(widget, dict)}
    for name, value in values.items():
        if value is None:
            continue
        if name in by_name:
            by_name[name]["value"] = value
        else:
            widgets.append({"name": name, "value": value})


def _remove_recipe_widget_names(payload: dict[str, Any], node_type: str, names: set[str]) -> None:
    for node in payload.get("nodes", []):
        if isinstance(node, dict) and str(node.get("type") or "") == node_type:
            node["widgets"] = [widget for widget in node.get("widgets", []) if not isinstance(widget, dict) or str(widget.get("name") or "") not in names]


def _recipe_node_values(payload: dict[str, Any], node_type: str, *, include_optional: bool = False) -> dict[str, Any]:
    values: dict[str, Any] = {}
    source_nodes = list(payload.get("nodes", []))
    if include_optional:
        source_nodes.extend(payload.get("optional_nodes", []))
    for node in source_nodes:
        if not isinstance(node, dict) or str(node.get("type") or "") != node_type:
            continue
        for widget in node.get("widgets", []):
            if isinstance(widget, dict) and widget.get("name"):
                values[str(widget["name"])] = widget.get("value")
    return values


def _canonicalize_recipe_log_references(payload: dict[str, Any]) -> dict[str, Any]:
    """Upgrade generated log paths while preserving every other Recipe field."""
    for node in [*list(payload.get("nodes") or []), *list(payload.get("optional_nodes") or [])]:
        if not isinstance(node, dict):
            continue
        for widget in node.get("widgets") or []:
            if not isinstance(widget, dict):
                continue
            name = str(widget.get("name") or "")
            if name == "prompt_log_file":
                widget["value"] = canonical_log_reference(widget.get("value"), "prompt")
            elif name.startswith("outfit_log_file_"):
                widget["value"] = canonical_log_reference(widget.get("value"), "outfit")
            elif name == "scene_log_file":
                widget["value"] = canonical_log_reference(widget.get("value"), "scene")
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for item in summary.get("placeholders") or []:
        if not isinstance(item, dict) or not item.get("source"):
            continue
        widget_name = str(item.get("widget") or "")
        category = "outfit" if widget_name.startswith("outfit_log_file_") else "scene" if widget_name == "scene_log_file" else "prompt"
        item["source"] = canonical_log_reference(item.get("source"), category)
    return payload


def _present_lora_value(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("on") is not False and value.get("lora") and str(value.get("lora")).lower() not in {"none", "[none]", "no_lora"})
    return bool(value and str(value).lower() not in {"none", "[none]", "no_lora"})


def _curate_prompt_catalog_recipe(payload: dict[str, Any]) -> dict[str, Any]:
    """Reduce a broad metadata conversion to the prompt-first Studio contract."""
    payload = _canonicalize_recipe_log_references(payload)
    prompt_source = _recipe_node_values(payload, STUDIO_PROMPT)
    generation_source = _recipe_node_values(payload, STUDIO_GENERATION, include_optional=True)
    loader_source = _recipe_node_values(payload, STUDIO_LOADER, include_optional=True)

    prompt = {name: prompt_source[name] for name in PROMPT_RECIPE_FIELDS if name in prompt_source}
    used_prompt = str(prompt.get("manual_prompt") or "").strip()
    if used_prompt:
        prompt["prompt_source"] = "manual"
    else:
        prompt.pop("manual_prompt", None)
        prompt.pop("prompt_source", None)

    if prompt.get("prompt_log_file") not in (None, "", "[None]"):
        prompt["prompt_mode"] = "fixed"
    else:
        for name in ("prompt_log_file", "prompt_mode", "prompt_index"):
            prompt.pop(name, None)

    for letter in "ABC":
        file_key = f"outfit_log_file_{letter}"
        mode_key = f"outfit_mode_{letter}"
        index_key = f"outfit_index_{letter}"
        if prompt.get(file_key) not in (None, "", "[None]"):
            prompt[mode_key] = "fixed"
        else:
            for name in (file_key, mode_key, index_key, f"outfit_token_{letter}", f"outfit_placement_{letter}"):
                prompt.pop(name, None)
    if prompt.get("scene_log_file") not in (None, "", "[None]"):
        prompt["scene_mode"] = "fixed"
    else:
        for name in ("scene_log_file", "scene_mode", "scene_index", "scene_token", "scene_placement"):
            prompt.pop(name, None)

    for enabled, text in (("prefix_enabled", "prefix_text"), ("suffix_enabled", "suffix_text")):
        if not prompt.get(enabled) or not str(prompt.get(text) or "").strip():
            prompt.pop(enabled, None)
            prompt.pop(text, None)

    generation: dict[str, Any] = {}
    width = generation_source.get("custom_width")
    height = generation_source.get("custom_height")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
        generation.update({"resolution_mode": "custom", "custom_width": int(width), "custom_height": int(height)})
    seed = generation_source.get("seed_value")
    try:
        seed_number = int(seed)
    except (TypeError, ValueError):
        seed_number = -1
    if seed_number >= 0:
        generation["seed_value"] = seed_number

    optional_nodes: list[dict[str, Any]] = []
    loader_resources = {
        name: value for name, value in loader_source.items()
        if name in LOADER_RESOURCE_FIELDS
        and (not name.startswith("secondary_lora_") or _present_lora_value(value))
        and value not in (None, "", "[None]", "None", "no_lora")
    }
    if not _present_lora_value(loader_resources.get("main_lora")):
        for name in ("main_lora", "main_enabled", "main_strength", "folder_name"):
            loader_resources.pop(name, None)
    if loader_resources:
        optional_nodes.append(_named_node(STUDIO_LOADER, "Optional model & LoRA resources", loader_resources))
    generation_resources = {name: generation_source[name] for name in GENERATION_RESOURCE_FIELDS if generation_source.get(name) not in (None, "", "[None]")}
    if generation_resources:
        optional_nodes.append(_named_node(STUDIO_GENERATION, "Optional encoder & VAE resources", generation_resources))

    nodes: list[dict[str, Any]] = []
    if prompt:
        nodes.append(_named_node(STUDIO_PROMPT, "Prompt used", prompt))
    if generation:
        nodes.append(_named_node(STUDIO_GENERATION, "Dimensions & resolved seed", generation))
    payload["nodes"] = nodes
    payload["optional_nodes"] = optional_nodes
    payload["schema"] = 4
    payload["catalog_focus"] = "prompt"
    return payload


def _apply_resolved_dimensions(payload: dict[str, Any], structured_raw: Any, image_size: tuple[int, int]) -> dict[str, Any]:
    structured_value = _json_value(structured_raw, {})
    structured_generation = structured_value.get("generation") if isinstance(structured_value, dict) and isinstance(structured_value.get("generation"), dict) else {}
    has_runtime_size = bool(structured_generation.get("width") and structured_generation.get("height"))
    generation_node = next((node for node in payload.get("nodes", []) if node.get("type") == STUDIO_GENERATION), None)
    generation_names = {str(item.get("name")) for item in (generation_node or {}).get("widgets", []) if isinstance(item, dict)}
    dimensions: dict[str, Any] = {}
    if not has_runtime_size or "custom_width" not in generation_names:
        dimensions["custom_width"] = int(image_size[0])
    if not has_runtime_size or "custom_height" not in generation_names:
        dimensions["custom_height"] = int(image_size[1])
    if dimensions:
        dimensions["resolution_mode"] = "custom"
        _merge_recipe_nodes(payload, STUDIO_GENERATION, "Imported image dimensions", dimensions)
    return payload


def _parse_parameters(text: str) -> dict[str, Any]:
    json_values = parse_json_parameters(text)
    if json_values:
        return json_values

    source = str(text or "")
    values: dict[str, Any] = {}
    for key, output in (("Steps", "steps"), ("Sampler", "sampler_name"), ("CFG scale", "cfg"), ("Seed", "seed_value"), ("Model", "diffusion_model"), ("VAE", "vae_name")):
        match = re.search(rf"(?:^|,\s|\n){re.escape(key)}:\s*([^,\n]+)", source)
        if match:
            raw = match.group(1).strip()
            if output in {"steps", "seed_value"}:
                try: raw = int(raw)
                except ValueError: pass
            elif output == "cfg":
                try: raw = float(raw)
                except ValueError: pass
            values[output] = raw
    size = re.search(r"(?:^|,\s|\n)Size:\s*(\d+)x(\d+)", source)
    if size:
        values.update({"custom_width": int(size.group(1)), "custom_height": int(size.group(2)), "resolution_mode": "custom"})
    prompt_end = re.search(r"\nNegative prompt:|\nSteps:\s*", source)
    if prompt_end:
        values["prompt"] = re.sub(r"\s*<lora:[^:>]+:[^>]+>\s*", " ", source[:prompt_end.start()], flags=re.IGNORECASE).strip()
    lora_hashes = {name.strip().lower(): hash_value.lower() for name, hash_value in re.findall(r'([\w .-]+):\s*([0-9a-fA-F]{10,64})', str(re.search(r'Lora hashes:\s*"?([^\n]+)', source).group(1) if re.search(r'Lora hashes:\s*"?([^\n]+)', source) else ""))}
    loras = []
    for name, strength in re.findall(r"<lora:([^:>]+):([^>]+)>", source, re.IGNORECASE):
        try: strength_value: Any = float(strength)
        except ValueError: strength_value = strength
        loras.append({"name": name, "strength": strength_value, "hash": lora_hashes.get(name.lower(), "")})
    values["loras"] = loras
    return values


def _literal_widget(value: Any) -> Any:
    """Keep JSON widget values while excluding Comfy graph links."""
    if isinstance(value, list) and len(value) >= 2 and isinstance(value[0], (str, int)) and isinstance(value[1], int):
        return None
    return value


def _extract_loras(api_nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for node in api_nodes.values():
        kind = str(node.get("class_type") or "")
        inputs = node.get("inputs") or {}
        if kind in {"LoraLoader", "LoraLoaderModelOnly"}:
            name = _literal_widget(inputs.get("lora_name"))
            if name:
                found.append({"name": str(name), "file": str(name), "strength": _literal_widget(inputs.get("strength_model", 1.0))})
        elif "Power Lora Loader" in kind:
            for value in inputs.values():
                if isinstance(value, dict) and value.get("on") and value.get("lora"):
                    found.append({"name": Path(str(value["lora"])).stem, "file": str(value["lora"]), "strength": value.get("strength", 1.0)})
    unique: dict[str, dict[str, Any]] = {}
    for item in found:
        unique[str(item.get("file") or item.get("name")).replace("/", "\\").lower()] = item
    return list(unique.values())


def _best_generic_prompt(api_nodes: dict[str, dict[str, Any]]) -> str:
    positive: list[str] = []
    primitives: list[str] = []
    for node in api_nodes.values():
        kind = str(node.get("class_type") or "")
        inputs = node.get("inputs") or {}
        if kind == "CLIPTextEncode":
            value = _resolve_api_value(inputs.get("text"), api_nodes)
            if isinstance(value, str) and value.strip():
                positive.append(value.strip())
        elif kind in {"PrimitiveString", "PrimitiveStringMultiline"}:
            value = _resolve_api_value(inputs.get("value"), api_nodes)
            if isinstance(value, str) and len(value.strip()) >= 12:
                primitives.append(value.strip())
    if positive:
        return max(positive, key=len)
    useful = [value for value in primitives if "expert prompt engineer" not in value.lower() and "follow these rules" not in value.lower()]
    return min(useful, key=len) if useful else ""


def _api_to_studio_recipe(api_graph: dict[str, Any], parameters: str = "") -> dict[str, Any]:
    """Convert named API-prompt inputs, including expanded subgraphs, into Studio sections."""
    api_nodes = _api_nodes(api_graph)
    payload: dict[str, Any] = {
        "schema": 3,
        "imported_from_image": True,
        "migration": {"mode": "metadata_merge", "notes": [], "loras": [], "source_node_count": len(api_nodes)},
        "nodes": [],
    }

    # Current Studio API prompts already contain named inputs. Curating these
    # avoids stale connected display widgets from Output Core entering recipes.
    for node in api_nodes.values():
        node_type = str(node.get("class_type") or "")
        if node_type not in STUDIO_WIDGETS:
            continue
        inputs = node.get("inputs") or {}
        values = {name: _literal_widget(inputs.get(name)) for name in STUDIO_WIDGETS[node_type] if name in inputs}
        _merge_recipe_nodes(payload, node_type, str((node.get("_meta") or {}).get("title") or node_type), values)

    parsed = _parse_parameters(parameters)
    prompt = str(parsed.get("prompt") or _best_generic_prompt(api_nodes) or "").strip()
    if prompt:
        _merge_recipe_nodes(payload, STUDIO_PROMPT, "Imported prompt", {"prompt_source": "manual", "manual_prompt": prompt})

    generation: dict[str, Any] = {key: parsed.get(key) for key in (
        "steps", "cfg", "sampler_name", "seed_value", "custom_width", "custom_height", "resolution_mode", "vae_name"
    ) if parsed.get(key) is not None}
    for node in api_nodes.values():
        kind = str(node.get("class_type") or "")
        inputs = node.get("inputs") or {}
        if kind in {"KSampler", "KSamplerAdvanced"}:
            for target, source in (("seed_value", "seed"), ("seed_value", "noise_seed"), ("steps", "steps"), ("cfg", "cfg"), ("sampler_name", "sampler_name"), ("scheduler", "scheduler"), ("denoise", "denoise")):
                value = _resolve_api_value(inputs.get(source), api_nodes)
                if value is not None:
                    generation[target] = value
        elif kind in {"EmptyLatentImage", "EmptySD3LatentImage"}:
            for target, source in (("custom_width", "width"), ("custom_height", "height"), ("batch_size", "batch_size")):
                value = _resolve_api_value(inputs.get(source), api_nodes)
                if value is not None:
                    generation[target] = value
            generation["resolution_mode"] = "custom"
        elif kind == "CLIPLoader" and _literal_widget(inputs.get("clip_name")):
            generation.update({"clip_name": inputs.get("clip_name"), "clip_type": inputs.get("type"), "clip_device": inputs.get("device")})
        elif kind == "VAELoader" and _literal_widget(inputs.get("vae_name")):
            generation["vae_name"] = inputs.get("vae_name")
    if generation:
        _merge_recipe_nodes(payload, STUDIO_GENERATION, "Imported generation", generation)

    loader: dict[str, Any] = {}
    for node in api_nodes.values():
        kind = str(node.get("class_type") or "")
        inputs = node.get("inputs") or {}
        if kind == "UNETLoader" and _literal_widget(inputs.get("unet_name")):
            loader.update({"diffusion_model": inputs.get("unet_name"), "weight_dtype": inputs.get("weight_dtype", "default")})
        elif kind == "CheckpointLoaderSimple" and _literal_widget(inputs.get("ckpt_name")):
            loader["diffusion_model"] = inputs.get("ckpt_name")
    if parsed.get("diffusion_model") and not loader.get("diffusion_model"):
        loader["diffusion_model"] = parsed["diffusion_model"]
    loras = _extract_loras(api_nodes) or list(parsed.get("loras") or [])
    parameter_loras = {str(item.get("name", "")).lower(): item for item in parsed.get("loras") or []}
    for item in loras:
        key = Path(str(item.get("file") or item.get("name") or "").replace("\\", "/")).stem.lower()
        if key in parameter_loras and parameter_loras[key].get("hash"):
            item["hash"] = parameter_loras[key]["hash"]
    if loras:
        first = loras[0]
        file_name = str(first.get("file") or first.get("name") or "")
        loader.update({
            "main_enabled": True,
            "main_lora": file_name,
            "folder_name": str(Path(file_name.replace("\\", "/")).parent).replace(".", "[LoRA Root]"),
            "main_strength": first.get("strength", 1.0),
        })
        payload["migration"]["loras"] = loras
    if loader:
        _merge_recipe_nodes(payload, STUDIO_LOADER, "Imported Loader", loader)

    if not payload["nodes"]:
        raise ValueError("The image has no embedded generation metadata that can be converted into a Studio recipe")
    return payload


def _structured_metadata_overlay(payload: dict[str, Any], structured_raw: Any) -> dict[str, Any]:
    structured = _json_value(structured_raw, {})
    if not isinstance(structured, dict):
        return payload
    resolved = structured.get("resolved") if isinstance(structured.get("resolved"), dict) else {}
    generation = structured.get("generation") if isinstance(structured.get("generation"), dict) else {}
    models = structured.get("models") if isinstance(structured.get("models"), dict) else {}

    prompt_values: dict[str, Any] = {}
    source_prompt = str(resolved.get("source_prompt") or (resolved.get("prompt") or {}).get("line") or "")
    if source_prompt:
        prompt_values.update({"prompt_source": "manual", "manual_prompt": source_prompt})
    prompt_meta = resolved.get("prompt") if isinstance(resolved.get("prompt"), dict) else {}
    if prompt_meta.get("file"):
        prompt_values.update({"prompt_log_file": prompt_meta["file"], "prompt_mode": "fixed"})
    if prompt_meta.get("index") is not None:
        prompt_values["prompt_index"] = prompt_meta["index"]
    placeholder_values: list[dict[str, Any]] = []
    for key, token_name, value_name in (("name", "name_token", "name_value"), ("item", "item_token", "item_value")):
        item = resolved.get(key) if isinstance(resolved.get(key), dict) else {}
        if item.get("token"):
            prompt_values[token_name] = item["token"]
        if item.get("value") not in (None, ""):
            prompt_values[value_name] = item["value"]
            placeholder_values.append({"token": item.get("token", key.upper()), "value": item["value"], "widget": value_name})
    for key, letter in (("outfit_a", "A"), ("outfit_b", "B"), ("outfit_c", "C")):
        item = resolved.get(key) if isinstance(resolved.get(key), dict) else {}
        if not item.get("used"):
            _remove_recipe_widget_names(payload, STUDIO_PROMPT, {
                f"outfit_token_{letter}", f"outfit_placement_{letter}", f"outfit_log_file_{letter}",
                f"outfit_mode_{letter}", f"outfit_index_{letter}",
            })
            continue
        if item.get("token"):
            prompt_values[f"outfit_token_{letter}"] = item["token"]
        if item.get("placement"):
            prompt_values[f"outfit_placement_{letter}"] = item["placement"]
        if item.get("file"):
            prompt_values[f"outfit_log_file_{letter}"] = item["file"]
            prompt_values[f"outfit_mode_{letter}"] = "fixed"
        if item.get("index") is not None:
            prompt_values[f"outfit_index_{letter}"] = item["index"]
        if item.get("line"):
            placeholder_values.append({"token": item.get("token", f"OUTFIT_{letter}"), "value": item["line"], "widget": f"outfit_log_file_{letter}", "source": item.get("file", "")})
    scene = resolved.get("scene") if isinstance(resolved.get("scene"), dict) else {}
    if scene.get("used"):
        if scene.get("token"):
            prompt_values["scene_token"] = scene["token"]
        if scene.get("placement"):
            prompt_values["scene_placement"] = scene["placement"]
        if scene.get("file"):
            prompt_values.update({"scene_log_file": scene["file"], "scene_mode": "fixed"})
        if scene.get("index") is not None:
            prompt_values["scene_index"] = scene["index"]
        if scene.get("line"):
            placeholder_values.append({"token": scene.get("token", "SCENE"), "value": scene["line"], "widget": "scene_log_file", "source": scene.get("file", "")})
    else:
        _remove_recipe_widget_names(payload, STUDIO_PROMPT, {"scene_token", "scene_placement", "scene_log_file", "scene_mode", "scene_index"})
    for key in ("prefix", "suffix"):
        item = resolved.get(key) if isinstance(resolved.get(key), dict) else {}
        text = str(item.get("text") or "").strip()
        if item.get("enabled") and text:
            prompt_values[f"{key}_enabled"] = True
            prompt_values[f"{key}_text"] = text
    if prompt_values:
        _merge_recipe_nodes(payload, STUDIO_PROMPT, "Reusable source prompt", prompt_values)

    generation_values = {
        target: generation.get(source)
        for target, source in (
            ("seed_value", "seed_used"), ("steps", "steps"), ("cfg", "cfg"),
            ("sampler_name", "sampler_name"), ("scheduler", "scheduler"), ("denoise", "denoise"),
            ("shift", "shift"), ("custom_width", "width"), ("custom_height", "height"),
            ("batch_size", "batch_size"), ("clip_name", "clip_name"), ("vae_name", "vae_name"),
        ) if generation.get(source) is not None
    }
    if generation_values.get("custom_width") and generation_values.get("custom_height"):
        generation_values["resolution_mode"] = "custom"
    if generation_values:
        _merge_recipe_nodes(payload, STUDIO_GENERATION, "Resolved generation", generation_values)

    loader_values: dict[str, Any] = {}
    if models.get("diffusion_model"):
        loader_values["diffusion_model"] = models["diffusion_model"]
    if models.get("weight_dtype"):
        loader_values["weight_dtype"] = models["weight_dtype"]
    main_lora = models.get("main_lora") if isinstance(models.get("main_lora"), dict) else {}
    if main_lora.get("file"):
        file_name = str(main_lora["file"])
        loader_values.update({
            "folder_name": str(Path(file_name.replace("\\", "/")).parent).replace(".", "[LoRA Root]"),
            "main_lora": file_name,
            "main_enabled": True,
            "main_strength": main_lora.get("strength", 1.0),
        })
    secondary_loras = models.get("secondary_loras") if isinstance(models.get("secondary_loras"), list) else []
    for index, item in enumerate((entry for entry in secondary_loras if isinstance(entry, dict) and entry.get("file")), start=1):
        if index > 10:
            break
        loader_values[f"secondary_lora_{index}"] = {
            "on": True,
            "lora": str(item.get("file") or ""),
            "strength": item.get("strength", 1.0),
        }
    if loader_values:
        _merge_recipe_nodes(payload, STUDIO_LOADER, "Resolved Loader", loader_values)

    payload["summary"] = {
        "prompt_template": source_prompt,
        "resolved_prompt": str(resolved.get("final_prompt") or ""),
        "placeholders": placeholder_values,
        "generation": generation,
        "models": models,
    }
    payload["structured_metadata"] = True
    return payload


def _legacy_to_studio_recipe(workflow: dict[str, Any]) -> dict[str, Any]:
    """Best-effort, deliberately conservative migration from common Comfy nodes.

    It preserves every detected legacy source in the recipe record while only
    applying literal settings that have an unambiguous Studio destination.
    """
    source_nodes = list(workflow.get("nodes") or [])
    if not source_nodes and isinstance(workflow, dict):
        source_nodes = [dict(value, class_type=value.get("class_type", key)) for key, value in workflow.items() if isinstance(value, dict) and value.get("class_type")]
    found: dict[str, Any] = {}
    loras: list[dict[str, Any]] = []
    notes: list[str] = []
    for raw in source_nodes:
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("type") or raw.get("class_type") or "")
        values = _workflow_node_values(raw)
        if kind in {"SOPromptLogEngine", "SOPromptLogEngineStudio"}:
            prompt = _scalar(values.get("manual_prompt"))
            if prompt:
                found["prompt"] = str(prompt)
            found["prompt_source"] = str(_scalar(values.get("prompt_source")) or "manual")
            for key in ("prompt_log_file", "prompt_mode", "prompt_index", "outfit_token_A", "outfit_log_file_A", "outfit_mode_A", "outfit_index_A", "outfit_token_B", "outfit_log_file_B", "outfit_mode_B", "outfit_index_B", "outfit_token_C", "outfit_log_file_C", "outfit_mode_C", "outfit_index_C", "scene_token", "scene_log_file", "scene_mode", "scene_index", "name_token", "name_value", "item_token", "item_value", "prefix_enabled", "prefix_text", "suffix_enabled", "suffix_text"):
                literal = _scalar(values.get(key))
                if literal is not None:
                    found[key] = literal
        elif kind == "CLIPTextEncode" and _scalar(values.get("text")):
            found.setdefault("prompt", str(values["text"]))
        elif kind == "SOGenerationPipeline":
            for key in ("clip_name", "clip_type", "clip_device", "vae_name", "resolution_mode", "custom_width", "custom_height", "aspect_preset", "megapixels", "batch_size", "steps", "cfg", "sampler_name", "scheduler", "denoise", "shift", "seed_value"):
                literal = _scalar(values.get(key))
                if literal is not None:
                    found[key] = literal
        elif kind in {"KSampler", "KSamplerAdvanced"}:
            seed = values.get("seed", values.get("noise_seed"))
            for key, source in (("seed_value", seed), ("steps", values.get("steps")), ("cfg", values.get("cfg")), ("sampler_name", values.get("sampler_name")), ("scheduler", values.get("scheduler")), ("denoise", values.get("denoise"))):
                literal = _scalar(source)
                if literal is not None:
                    found[key] = literal
        elif kind == "EmptyLatentImage":
            for key in ("width", "height", "batch_size"):
                literal = _scalar(values.get(key))
                if literal is not None:
                    found[{"width": "custom_width", "height": "custom_height", "batch_size": "batch_size"}[key]] = literal
        elif kind == "VAELoader" and _scalar(values.get("vae_name")):
            found["vae_name"] = values["vae_name"]
        elif kind == "SOLoaderCoreEngine":
            model = _scalar(values.get("diffusion_model"))
            if model:
                found["model_candidate"] = str(model)
            main_lora = _scalar(values.get("main_lora"))
            if main_lora and str(main_lora).lower() not in {"no_lora", "[none]"}:
                loras.append({"name": str(main_lora), "strength": _scalar(values.get("main_strength")), "folder": _scalar(values.get("folder_name"))})
        elif kind in {"UNETLoader", "CheckpointLoaderSimple"}:
            model = _scalar(values.get("unet_name", values.get("ckpt_name")))
            if model:
                found["model_candidate"] = str(model)
                notes.append("Model kept as a candidate for review; checkpoint and diffusion-model folders are not interchangeable.")
        elif kind == "LoraLoader":
            name = _scalar(values.get("lora_name"))
            if name:
                loras.append({"name": str(name), "strength": _scalar(values.get("strength_model"))})
        elif kind == "SOOutputBuilderSave":
            for key in ("output_root", "subfolder_literal", "subfolder_var_1", "subfolder_var_2", "subfolder_var_3", "subfolder_var_4", "subfolder_delimiter", "filename_literal", "filename_var_1", "filename_var_2", "filename_var_3", "filename_var_4", "filename_var_5", "filename_var_6", "filename_delimiter", "extension", "quality", "counter_digits", "save_prompt_json", "save_workflow_json", "save_civitai_parameters"):
                literal = _scalar(values.get(key))
                if literal is not None:
                    found[key] = literal
        elif kind == "SaveImage" and _scalar(values.get("filename_prefix")):
            found["filename_prefix"] = str(values["filename_prefix"])

    nodes: list[dict[str, Any]] = []
    if found.get("model_candidate"):
        nodes.append({"type": STUDIO_LOADER, "title": "Migrated Loader candidate", "widgets": [{"name": "diffusion_model", "value": found["model_candidate"]}]})
    if found.get("prompt"):
        prompt_keys = ("prompt_source", "manual_prompt", "prompt_log_file", "prompt_mode", "prompt_index", "outfit_token_A", "outfit_log_file_A", "outfit_mode_A", "outfit_index_A", "outfit_token_B", "outfit_log_file_B", "outfit_mode_B", "outfit_index_B", "outfit_token_C", "outfit_log_file_C", "outfit_mode_C", "outfit_index_C", "scene_token", "scene_log_file", "scene_mode", "scene_index", "name_token", "name_value", "item_token", "item_value", "prefix_enabled", "prefix_text", "suffix_enabled", "suffix_text")
        prompt = [{"name": key, "value": found["prompt"] if key == "manual_prompt" else found[key]} for key in prompt_keys if key == "manual_prompt" or key in found]
        if not any(item["name"] == "prompt_source" for item in prompt): prompt.insert(0, {"name": "prompt_source", "value": "manual"})
        nodes.append({"type": STUDIO_PROMPT, "title": "Migrated prompt", "widgets": prompt})
    generation_keys = ("clip_name", "clip_type", "clip_device", "vae_name", "resolution_mode", "custom_width", "custom_height", "aspect_preset", "megapixels", "batch_size", "steps", "cfg", "sampler_name", "scheduler", "denoise", "shift", "seed_value")
    generation = [{"name": key, "value": found[key]} for key in generation_keys if key in found]
    if generation:
        if not any(item["name"] == "resolution_mode" for item in generation): generation.insert(0, {"name": "resolution_mode", "value": "custom"})
        nodes.append({"type": STUDIO_GENERATION, "title": "Migrated generation", "widgets": generation})
    output_keys = ("output_root", "subfolder_literal", "subfolder_var_1", "subfolder_var_2", "subfolder_var_3", "subfolder_var_4", "subfolder_delimiter", "filename_literal", "filename_var_1", "filename_var_2", "filename_var_3", "filename_var_4", "filename_var_5", "filename_var_6", "filename_delimiter", "extension", "quality", "counter_digits", "save_prompt_json", "save_workflow_json", "save_civitai_parameters")
    output = [{"name": key, "value": found[key]} for key in output_keys if key in found]
    if found.get("filename_prefix") and not output: output = [{"name": "filename_literal", "value": found["filename_prefix"]}]
    if output: nodes.append({"type": STUDIO_OUTPUT, "title": "Migrated output", "widgets": output})
    if loras:
        notes.append(f"{len(loras)} legacy LoRA(s) recorded for review. Choose their Studio folder scope before applying them.")
    if not nodes:
        raise ValueError("The embedded workflow did not contain common prompt, sampler, latent, model, LoRA, VAE, or output settings to migrate")
    return {"schema": 2, "imported_from_image": True, "migration": {"mode": "best_effort_legacy", "loras": loras, "notes": notes, "source_node_count": len(source_nodes)}, "nodes": nodes}


PROMPT_HARVEST_VERSION = "prompt-outfit-v1"
_PROMPT_HARVEST_ANCHOR_RE = re.compile(
    r"\b(?:wearing|wears|dressed\s+in|clad\s+in|outfitted\s+in)\b\s*",
    re.IGNORECASE,
)
_PROMPT_HARVEST_STOP_RE = re.compile(
    r",\s*(?=(?:standing|sitting|seated|kneeling|lying|leaning|walking|running|posed?|posing|"
    r"photographed|captured|shot|framed|viewed|against|inside|outside|beside|near|behind|beneath|"
    r"in\s+front|while|her\b|she\b|looking|gazing|expression|harsh\b|soft\b|direct\s+(?:flash|light)|"
    r"lit\b|lighting|background|camera|lens|composition|torso|body|head|face|hair\b|messy\b|giving\b|"
    r"smiling|smile\b|gaze\b|eyes\b|mood\b|relaxed\b|playful\b|calm\b|one\s+hand|both\s+hands)\b)",
    re.IGNORECASE,
)


def _prompt_harvest_exact_outfit(recipe: dict[str, Any] | None) -> str:
    """Return exact OUTFIT text when structured generation metadata provides it."""
    payload = recipe.get("payload") if isinstance(recipe, dict) else None
    if not isinstance(payload, dict):
        return ""
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    placeholders = summary.get("placeholders") if isinstance(summary.get("placeholders"), list) else []
    values: list[str] = []
    for item in placeholders:
        if not isinstance(item, dict):
            continue
        token = str(item.get("token") or "").strip().upper()
        widget = str(item.get("widget") or "")
        if not (token.startswith("OUTFIT") or widget.startswith("outfit_")):
            continue
        value = _single_line_recipe_prompt(item.get("value"))
        if value and value.casefold() not in {existing.casefold() for existing in values}:
            values.append(value)
    if not values:
        return ""
    # Multiple Outfit A/B/C slots are ingredients of the same rendered look.
    # Preserve their authored order as a single Look candidate.
    return _single_line_recipe_prompt(", ".join(values))


def _prompt_harvest_outfit_from_text(text: str) -> dict[str, Any]:
    """Deterministically find the clothing clause in a flattened prompt.

    This deliberately starts from explicit linguistic anchors such as
    ``wearing`` / ``dressed in``.  It is a bootstrap parser, not an LLM: when a
    prompt does not expose a trustworthy clothing clause we leave it for review
    instead of inventing one.
    """
    source = _single_line_recipe_prompt(text)
    if not source:
        return {"candidate": "", "confidence": 0.0, "status": "unresolved", "source": "none", "issues": ["no-prompt"]}

    best: dict[str, Any] | None = None
    for anchor in _PROMPT_HARVEST_ANCHOR_RE.finditer(source):
        tail = source[anchor.end():]
        if not tail:
            continue
        end = len(tail)
        stop = _PROMPT_HARVEST_STOP_RE.search(tail)
        if stop:
            end = min(end, stop.start())
        sentence = re.search(r"[.;]\s+(?=[A-Z])", tail)
        if sentence:
            end = min(end, sentence.start())
        candidate = _wardrobe_clean_phrase(tail[:end][:900])
        candidate = re.sub(r"\s+(?:and|with)$", "", candidate, flags=re.IGNORECASE).strip(" ,;.")
        if not candidate:
            continue
        decomposition = _decompose_outfit_look(candidate)
        items = list(decomposition.get("items") or [])
        if not items:
            continue
        decomp_status = str(decomposition.get("status") or "unresolved")
        confidence = 0.92 if decomp_status == "ready" else 0.78 if decomp_status == "review" else 0.55
        # A candidate that still contains obvious photographic clauses should
        # stay in review even if garment heads were found inside it.
        if re.search(r"\b(?:camera|lens|photograph|lighting|background|pose|expression)\b", candidate, re.IGNORECASE):
            confidence = min(confidence, 0.62)
        row = {
            "candidate": _single_line_recipe_prompt(candidate),
            "confidence": round(confidence, 3),
            "status": "ready" if confidence >= 0.85 else "review",
            "source": "prompt-text",
            "issues": list(decomposition.get("issues") or []),
            "decomposition": decomposition,
        }
        if best is None or float(row["confidence"]) > float(best.get("confidence") or 0):
            best = row
    return best or {"candidate": "", "confidence": 0.0, "status": "unresolved", "source": "none", "issues": ["no-outfit-clause"]}


def _prompt_harvest_analysis(*, status_filter: str = "", query: str = "", sample_limit: int = 100, sample_offset: int = 0) -> dict[str, Any]:
    catalog = get_catalog()
    recipes = catalog.recipes()
    by_recipe = {str(row.get("recipe_id") or ""): row for row in recipes}
    assets = _recipe_prompt_assets(recipes)
    existing_looks = {str(row.get("value") or "").casefold(): row for row in catalog.recipe_components("outfit")}
    rows: list[dict[str, Any]] = []
    summary = {"total": len(assets), "exact": 0, "ready": 0, "review": 0, "unresolved": 0, "existing": 0}
    for asset in assets:
        recipe = by_recipe.get(str(asset.get("recipe_id") or ""))
        exact = _prompt_harvest_exact_outfit(recipe)
        if exact:
            result = {
                "candidate": exact, "confidence": 1.0, "status": "ready", "source": "structured-metadata",
                "issues": [], "decomposition": _decompose_outfit_look(exact),
            }
            summary["exact"] += 1
        else:
            result = _prompt_harvest_outfit_from_text(str(asset.get("value") or ""))
        candidate = str(result.get("candidate") or "").strip()
        exists = bool(candidate and candidate.casefold() in existing_looks)
        status = "existing" if exists else str(result.get("status") or "unresolved")
        if status in summary:
            summary[status] += 1
        row = {
            "prompt_id": str(asset.get("prompt_id") or ""),
            "recipe_id": str(asset.get("recipe_id") or ""),
            "name": str(asset.get("name") or "Prompt"),
            "prompt": str(asset.get("value") or ""),
            "preview_ref": str(asset.get("preview_ref") or ""),
            "from_recipe": bool(asset.get("from_recipe")),
            "candidate": candidate,
            "confidence": float(result.get("confidence") or 0),
            "status": status,
            "source": str(result.get("source") or "none"),
            "issues": list(result.get("issues") or []),
            "decomposition": result.get("decomposition") or {},
        }
        rows.append(row)

    clean_status = str(status_filter or "").strip().lower()
    if clean_status in {"ready", "review", "unresolved", "existing"}:
        filtered = [row for row in rows if row["status"] == clean_status]
    else:
        filtered = rows
    clean_query = str(query or "").strip().casefold()
    if clean_query:
        filtered = [row for row in filtered if clean_query in row["prompt"].casefold() or clean_query in row["candidate"].casefold() or clean_query in row["name"].casefold()]
    priority = {"review": 0, "ready": 1, "unresolved": 2, "existing": 3}
    filtered.sort(key=lambda row: (priority.get(row["status"], 4), -float(row.get("confidence") or 0), row["name"].casefold()))
    limit = max(0, int(sample_limit))
    offset = max(0, int(sample_offset))
    page = filtered[offset:offset + limit] if limit else []
    return {
        "ok": True, "version": PROMPT_HARVEST_VERSION, "summary": summary, "rows": page,
        "queue_total": len(filtered), "queue_offset": offset, "queue_limit": limit,
        "status_filter": clean_status if clean_status in {"ready", "review", "unresolved", "existing"} else "all",
        "query": str(query or "").strip(),
    }


def _accept_prompt_harvest(prompt_id: str, outfit_value: str = "") -> dict[str, Any]:
    analysis = _prompt_harvest_analysis(sample_limit=100000, sample_offset=0)
    row = next((item for item in analysis.get("rows") or [] if str(item.get("prompt_id") or "") == str(prompt_id or "")), None)
    if row is None:
        raise ValueError("Prompt asset no longer exists")
    value = _single_line_recipe_prompt(outfit_value or row.get("candidate"))
    if not value:
        raise ValueError("No Outfit value was detected. Enter an Outfit value before accepting this prompt.")
    component = get_catalog().upsert_recipe_component("outfit", value, manual=True)
    _safe_sync_recipe_component_logs()
    return {
        "ok": True, "prompt_id": str(prompt_id), "component": component,
        "candidate": value, "decomposition": _decompose_outfit_look(value),
    }


def _accept_filtered_prompt_harvest(*, status_filter: str = "ready", query: str = "") -> dict[str, Any]:
    analysis = _prompt_harvest_analysis(status_filter=status_filter, query=query, sample_limit=100000, sample_offset=0)
    created = matched = skipped = 0
    catalog = get_catalog()
    for row in analysis.get("rows") or []:
        candidate = _single_line_recipe_prompt(row.get("candidate"))
        if not candidate or str(row.get("status") or "") in {"unresolved", "existing"}:
            skipped += 1
            continue
        before = catalog.recipe_component_by_value("outfit", candidate)
        catalog.upsert_recipe_component("outfit", candidate, manual=True)
        if before:
            matched += 1
        else:
            created += 1
    if created or matched:
        _safe_sync_recipe_component_logs()
    return {"ok": True, "matched_view": int(analysis.get("queue_total") or 0), "created": created, "matched": matched, "skipped": skipped}


CREATIVE_LIBRARY_API_PREFIX = "/sickollie/creative-library"
LEGACY_RECIPE_CATALOG_API_PREFIX = "/sickollie/recipe-catalog"


def _creative_library_state_payload() -> dict[str, Any]:
    """Return explicit visible, stored, and recipe-derived library counts."""
    catalog = get_catalog()
    stored_counts = catalog.creative_library_counts()
    snapshot = _prompt_asset_snapshot()
    visible_counts = {**stored_counts, "prompts": len(snapshot["prompts"]), "templates": len(snapshot["templates"])}
    return {
        "ok": True,
        "revisions": catalog.creative_library_revisions(),
        "counts": visible_counts,
        "stored_counts": stored_counts,
        "derived_counts": {
            "prompts": max(0, visible_counts["prompts"] - stored_counts["prompts"]),
            "templates": max(0, visible_counts["templates"] - stored_counts["templates"]),
        },
        "count_contract": "counts are browsable assets; stored_counts exclude recipe-derived projections",
    }


def _creative_library_route(method: str, path: str):
    """Register the canonical API plus a cache-safe alias for older frontends."""
    def decorator(handler):
        registrar = getattr(PromptServer.instance.routes, method)
        registrar(f"{CREATIVE_LIBRARY_API_PREFIX}{path}")(handler)
        registrar(f"{LEGACY_RECIPE_CATALOG_API_PREFIX}{path}")(handler)
        return handler
    return decorator


if PromptServer is not None and web is not None:

    @_creative_library_route("get", "/state")
    async def solo_recipe_catalog_state(request):
        return web.json_response(_creative_library_state_payload())

    @_creative_library_route("get", "/structure-order")
    async def solo_creative_structure_order(request):
        scope = str(request.query.get("scope") or "").strip().lower()
        try:
            order = get_catalog().creative_structure_order(scope)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "scope": scope, "order": order})

    @_creative_library_route("put", "/structure-order")
    async def solo_creative_structure_order_update(request):
        try:
            payload = await request.json()
            scope = str(payload.get("scope") or "").strip().lower()
            order = payload.get("order") if isinstance(payload.get("order"), dict) else {}
            saved = get_catalog().set_creative_structure_order(scope, order)
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            return web.json_response({"ok": True, "scope": scope, "order": saved, "revisions": get_catalog().creative_library_revisions()})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("patch", "/prompt-logs/rename")
    async def solo_prompt_log_rename(request):
        try:
            payload = await request.json()
            source_path = str(payload.get("source_path") or "")
            label = str(payload.get("label") or "")
            result = _rename_prompt_source_file(source_path, label)
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            sync = _sync_library_if_stale()
            mirror_deleted = int(((sync.get("ready_prompts") or {}).get("removed_catalog_files") or 0)) if isinstance(sync, dict) else 0
            return web.json_response({"ok": True, **result, "mirror_txt_files_deleted": mirror_deleted})
        except (TypeError, ValueError, OSError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("delete", "/prompt-logs")
    async def solo_prompt_log_remove(request):
        try:
            source_path = str(request.query.get("source_path") or "")
            result = _delete_prompt_source_file(source_path)
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            _ensure_fragment_index(force=True)
            sync = _sync_library_if_stale()
            mirror_deleted = int(((sync.get("ready_prompts") or {}).get("removed_catalog_files") or 0)) if isinstance(sync, dict) else 0
            return web.json_response({"ok": True, **result, "mirror_txt_files_deleted": mirror_deleted})
        except (TypeError, ValueError, OSError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("delete", "/prompt-structure")
    async def solo_prompt_structure_delete(request):
        try:
            payload = await request.json()
            kind = "template" if str(payload.get("kind") or "").casefold() == "template" else "prompt"
            parent = str(payload.get("parent") or "")
            subcategory = str(payload.get("subcategory") or "") if "subcategory" in payload else None
            result = _delete_prompt_structure_scope(kind, parent, subcategory)
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            _ensure_fragment_index(force=True)
            sync = _sync_library_if_stale()
            mirror_deleted = int(((sync.get("ready_prompts") or {}).get("removed_catalog_files") or 0)) if isinstance(sync, dict) else 0
            return web.json_response({"ok": True, "kind": kind, "parent": parent, "subcategory": subcategory, **result, "mirror_txt_files_deleted": mirror_deleted})
        except (TypeError, ValueError, OSError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("get", "/recipes")
    async def solo_recipe_list(request):
        if str(request.query.get("scope") or "").strip().casefold() == "templates":
            return web.json_response(_prompt_asset_snapshot()["recipe_templates"])
        recipes = get_catalog().recipes()
        if str(request.query.get("sync") or "1").strip().casefold() not in {"0", "false", "no"}:
            _sync_library_if_stale(recipes=recipes, collections=get_catalog().recipe_collections())
        for recipe in recipes:
            payload = recipe.get("payload")
            if isinstance(payload, dict):
                recipe["payload"] = _curate_prompt_catalog_recipe(payload)
                recipe["payload"]["tokens"] = _recipe_tokens(recipe["payload"])
        return web.json_response(recipes)

    @_creative_library_route("get", "/prompt-assets")
    async def solo_recipe_prompt_assets(request):
        snapshot = _prompt_asset_snapshot()
        kind = "template" if str(request.query.get("kind") or "").strip().casefold() == "template" else "prompt"
        include_all = str(request.query.get("include_all") or "").strip().casefold() in {"1", "true", "yes"}
        try:
            limit = max(0, min(200, int(request.query.get("limit") or 0)))
            offset = max(0, int(request.query.get("offset") or 0))
            max_results = max(0, min(401, int(request.query.get("max_results") or 0)))
        except (TypeError, ValueError):
            limit, offset, max_results = 0, 0, 0
        filters = dict(
            query=str(request.query.get("q") or ""), source=str(request.query.get("source") or ""),
            collection=str(request.query.get("collection") or ""),
            facets={axis: str(request.query.get(axis) or "") for axis in PROMPT_DISCOVERY_FILTER_AXES},
            sort=str(request.query.get("sort") or "preview_newest"),
            blueprint_only=str(request.query.get("blueprint") or "").strip().casefold() in {"1", "true", "yes"},
            signature=str(request.query.get("signature") or ""),
            placeholders=[
                token for value in request.query.getall("placeholder", [])
                for token in str(value or "").split(",") if token.strip()
            ],
            parent=str(request.query.get("parent") or ""),
            subcategory=str(request.query.get("subcategory") or ""),
            log_path=str(request.query.get("log") or ""),
            rating=str(request.query.get("rating") or ""),
            include_archived=str(request.query.get("include_archived") or "").strip().casefold() in {"1", "true", "yes"},
        )
        kind_assets = snapshot["templates" if kind == "template" else "prompts"]
        metadata = _cached_prompt_filter_metadata(snapshot, kind, kind_assets, filters)
        prompts = metadata["visible"]
        # Catalog views stay paginated, while a Yearbook run deliberately asks for
        # the complete active filter scope.  Keeping this opt-in prevents the
        # gallery from accidentally rendering thousands of cards at once.
        page = (prompts[:max_results] if max_results else prompts) if include_all else (prompts[offset:offset + limit] if limit else [])
        return web.json_response({
            "ok": True,
            "kind": kind,
            "prompts": page,
            "total": len(prompts),
            "total_assets": len(kind_assets),
            "corpus_totals": {
                "prompt": len(snapshot["prompts"]),
                "template": len(snapshot["templates"]),
                "all": len(snapshot["records"]),
            },
            "offset": offset,
            "limit": len(page) if include_all else limit,
            "facet_counts": metadata["facet_counts"],
            "facet_universe": snapshot["facet_counts"][kind],
            "home_counts": metadata["home_counts"],
            "home_universe": snapshot["home_counts"][kind],
            "placeholder_counts": snapshot["placeholder_counts"] if kind == "template" else {},
            "placeholder_available_counts": metadata["placeholder_available_counts"] if kind == "template" else {},
            "collection_counts": snapshot.get("collection_counts_by_kind", {}).get(
                kind,
                snapshot["collection_counts"] if kind == "prompt" else {},
            ),
            "blueprints": snapshot["blueprints"],
            "facet_covers": snapshot["facet_covers"][kind],
        })

    @_creative_library_route("post", "/prompt-assets/import")
    async def solo_prompt_assets_import(request):
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Prompt import payload must be an object")
            if isinstance(payload.get("values"), list):
                raw_values = list(payload.get("values") or [])
            else:
                raw_values = str(payload.get("text") or "").splitlines()
            prepared = _prepare_prompt_import(
                raw_values,
                str(payload.get("parent") or ""),
                str(payload.get("subcategory") or ""),
            )
            if not prepared["items"]:
                raise ValueError("No Prompt or Template lines remained after cleanup")

            catalog = get_catalog()
            selected_kind = "template" if str(payload.get("kind") or "").strip().casefold() == "template" else "prompt"
            collection_id = str(payload.get("collection_id") or "").strip()
            collection_name = _single_line_recipe_prompt(payload.get("collection_name"))
            selected_collection: dict[str, Any] | None = None
            if collection_id:
                selected_collection = next(
                    (row for row in catalog.prompt_showcase_collections(selected_kind) if str(row.get("collection_id") or "") == collection_id),
                    None,
                )
                if selected_collection is None:
                    raise ValueError("The selected Collection no longer exists")
            elif collection_name:
                selected_collection = next(
                    (row for row in catalog.prompt_showcase_collections(selected_kind) if str(row.get("name") or "").casefold() == collection_name.casefold()),
                    None,
                )
                if selected_collection is None:
                    selected_collection = catalog.create_prompt_showcase_collection(selected_kind, collection_name)
                collection_id = str(selected_collection.get("collection_id") or "")

            log_name = _single_line_recipe_prompt(payload.get("log_name"))
            source_path = ""
            saved_target: Path | None = None
            if log_name:
                source_path, saved_target = _save_imported_prompt_log(
                    str(payload.get("text") or ""),
                    prepared["parent"],
                    prepared["subcategory"],
                    log_name,
                )
            try:
                by_kind: dict[str, dict[str, Any]] = {}
                for kind, items in (("prompt", prepared["prompt_items"]), ("template", prepared["template_items"])):
                    if not items:
                        continue
                    by_kind[kind] = catalog.import_prompt_assets(
                        items,
                        parent=prepared["parent"],
                        subcategory=prepared["subcategory"],
                        kind=kind,
                        collection_ids=[collection_id] if collection_id and kind == selected_kind else [],
                        source_path=source_path,
                        source_label=log_name,
                    )
            except Exception:
                if saved_target is not None:
                    try:
                        saved_target.unlink(missing_ok=True)
                    except OSError:
                        pass
                raise
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            imported_ids = [
                prompt_id for result in by_kind.values() for prompt_id in result.get("prompt_ids") or []
            ]
            catalog.set_last_prompt_import(imported_ids)
            _sync_library_if_stale()
            default_kind = selected_kind if by_kind.get(selected_kind) else ("template" if by_kind.get("template") else "prompt")
            created = sum(int(result.get("created") or 0) for result in by_kind.values())
            matched = sum(int(result.get("matched") or 0) for result in by_kind.values())
            return web.json_response({
                "ok": True,
                "created": created,
                "matched": matched,
                "prompt_ids": imported_ids,
                "by_kind": by_kind,
                "prompts": len(prepared["prompt_items"]),
                "templates": len(prepared["template_items"]),
                "default_kind": default_kind,
                "submitted": prepared["submitted"],
                "input_duplicates": prepared["input_duplicates"],
                "blank": prepared["blank"],
                "safety_excluded": prepared["safety_excluded"],
                "template_routed": prepared["template_routed"],
                "prompt_routed": prepared["prompt_routed"],
                "parent": prepared["parent"],
                "subcategory": prepared["subcategory"],
                "log_name": log_name,
                "source_path": source_path,
                "saved_copy": source_path,
                "collection": selected_collection,
                "revisions": catalog.creative_library_revisions(),
            })
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("put", "/prompt-assets/{prompt_id}")
    async def solo_prompt_asset_edit(request):
        prompt_id = str(request.match_info.get("prompt_id") or "")
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Prompt edit payload must be an object")
            value = _single_line_recipe_prompt(payload.get("value"))
            if not value:
                raise ValueError("Prompt text is required")
            mode = str(payload.get("mode") or "save").strip().casefold()
            copy_only = mode == "copy"
            recipe_id = str(payload.get("recipe_id") or "").strip()
            kind = "template" if str(payload.get("kind") or "").strip().casefold() == "template" else "prompt"
            catalog = get_catalog()
            if recipe_id:
                recipe = next((item for item in catalog.recipes() if str(item.get("recipe_id") or "") == recipe_id), None)
                if recipe is None:
                    raise ValueError("The saved Recipe for this card no longer exists")
                if copy_only:
                    parent = _single_line_recipe_prompt(payload.get("parent")) or "Saved & Imported"
                    subcategory = _single_line_recipe_prompt(payload.get("subcategory")) or ("Saved Templates" if kind == "template" else "Saved Prompts")
                    facets = _prompt_facets(value)
                    facets["parent"] = [parent]
                    facets["subcategory"] = [subcategory]
                    result = catalog.import_prompt_assets(
                        [{"value": value, "facets": facets, "source_line": 1}],
                        parent=parent,
                        subcategory=subcategory,
                        kind=kind,
                        collection_ids=[],
                    )
                    catalog.set_last_prompt_import(result.get("prompt_ids") or [])
                    edited = {"prompt_id": (result.get("prompt_ids") or [""])[0], "value": value, "created_copy": True}
                else:
                    updated_recipe = _set_recipe_prompt_text(recipe, kind, value)
                    catalog.save_recipe(recipe_id, str(recipe.get("name") or kind.title()), updated_recipe.get("payload") or {}, str(recipe.get("preview_ref") or ""))
                    catalog.set_last_recipe_import([recipe_id])
                    edited = {"prompt_id": prompt_id, "recipe_id": recipe_id, "value": value, "created_copy": False}
            else:
                edited = catalog.edit_prompt_asset_text(prompt_id, value, copy_only=copy_only)
                catalog.set_last_prompt_import([str(edited.get("prompt_id") or prompt_id)])
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            _sync_library_if_stale()
            return web.json_response({"ok": True, **edited, "revisions": catalog.creative_library_revisions()})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/prompt-assets/purge")
    async def solo_prompt_assets_purge(request):
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Library reset payload must be an object")
            kind = "template" if str(payload.get("kind") or "").strip().casefold() == "template" else "prompt"
            expected = f"PURGE {kind.upper()}S"
            if str(payload.get("confirm") or "").strip().upper() != expected:
                raise ValueError(f"Type {expected} to confirm this reset")
            catalog = get_catalog()
            result = catalog.purge_prompt_library(kind)
            result.pop("prompt_ids", None)
            preview_refs = result.pop("preview_refs", [])
            previews_deleted = 0
            preview_root = _preview_directory()
            for preview_ref in preview_refs:
                target = preview_root / Path(str(preview_ref or "")).name
                if not target.is_file():
                    continue
                target.unlink(missing_ok=True)
                previews_deleted += 1
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            _ensure_fragment_index(force=True)
            _sync_library_if_stale()
            return web.json_response({
                "ok": True,
                **result,
                "previews_deleted": previews_deleted,
                "revisions": catalog.creative_library_revisions(),
            })
        except (TypeError, ValueError, OSError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/prompt-assets/{prompt_id}/rating")
    async def solo_prompt_asset_rating(request):
        prompt_id = str(request.match_info.get("prompt_id") or "")
        try:
            payload = await request.json()
            result = get_catalog().set_prompt_rating(
                prompt_id,
                int(payload.get("rating") or 0),
                str(payload.get("note")) if "note" in payload else None,
            )
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
        return web.json_response({"ok": True, **result})

    @_creative_library_route("post", "/prompt-assets/bulk")
    async def solo_prompt_assets_bulk(request):
        try:
            payload = await request.json()
            ids = [str(value) for value in payload.get("prompt_ids") or []]
            snapshot = _prompt_asset_snapshot()
            kind = "template" if str(payload.get("kind") or "").casefold() == "template" else "prompt"
            if payload.get("all_filtered"):
                filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
                ids = [str(item.get("prompt_id") or "") for item in _filter_prompt_assets(
                    snapshot["templates" if kind == "template" else "prompts"], query=str(filters.get("q") or ""),
                    collection=str(filters.get("collection") or ""), source=str(filters.get("source") or ""),
                    parent=str(filters.get("parent") or ""), subcategory=str(filters.get("subcategory") or ""), log_path=str(filters.get("log") or ""),
                    facets=filters.get("facets") if isinstance(filters.get("facets"), dict) else {},
                    placeholders=list(filters.get("placeholders") or []), sort=str(filters.get("sort") or "preview_newest"),
                    rating=str(filters.get("rating") or ""),
                )]
            catalog = get_catalog(); operation = str(payload.get("operation") or "").casefold()
            response_extra: dict[str, Any] = {}
            if operation == "move": changed = catalog.set_prompt_home(ids, str(payload.get("parent") or ""), str(payload.get("subcategory") or ""))
            elif operation == "auto_home": changed = catalog.clear_prompt_home(ids)
            elif operation == "archive": changed = catalog.set_prompt_archived(ids, True)
            elif operation == "restore": changed = catalog.set_prompt_archived(ids, False)
            elif operation == "delete":
                result = catalog.delete_prompt_assets(ids); changed = int(result["deleted"]) + int(result["archived"])
            elif operation == "delete_previews":
                cleared = catalog.clear_prompt_previews(ids)
                deleted_files = 0
                for row in cleared:
                    preview_ref = str(row.get("removed_preview_ref") or "")
                    if not preview_ref:
                        continue
                    target = _preview_directory() / Path(preview_ref).name
                    if target.is_file():
                        target.unlink(missing_ok=True); deleted_files += 1
                changed = len(cleared)
                response_extra = {"previews_deleted": deleted_files, "previews_cleared": changed}
            else: raise ValueError("Unknown prompt bulk operation")
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None}); _sync_library_if_stale()
            return web.json_response({"ok": True, "changed": changed, **response_extra})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/prompt-assets/bulk/collections/remove")
    async def solo_prompt_assets_bulk_remove_collections(request):
        try:
            payload = await request.json()
            prompt_ids = payload.get("prompt_ids")
            collection_ids = payload.get("collection_ids")
            if not isinstance(prompt_ids, list) or not isinstance(collection_ids, list):
                raise ValueError("Prompt IDs and folder IDs must be lists")
            result = get_catalog().remove_prompts_from_collections(
                [str(value) for value in prompt_ids], [str(value) for value in collection_ids],
                str(payload.get("kind") or "prompt"),
            )
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None}); _sync_library_if_stale()
            return web.json_response({"ok": True, **result})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("put", "/prompt-assets/{prompt_id}/collections")
    async def solo_prompt_asset_set_collections(request):
        prompt_id = str(request.match_info.get("prompt_id") or "")
        try:
            payload = await request.json()
            collection_ids = payload.get("collection_ids")
            if not isinstance(collection_ids, list):
                raise ValueError("Folder IDs must be a list")
            rows = get_catalog().set_prompt_collections(
                prompt_id, collection_ids, str(payload.get("kind") or "prompt"),
            )
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None}); _sync_library_if_stale()
            return web.json_response({"ok": True, "collections": rows})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/prompt-assets/bulk/collections")
    async def solo_prompt_assets_bulk_collections(request):
        try:
            payload = await request.json()
            ids = [str(value) for value in payload.get("prompt_ids") or []]
            collection_ids = payload.get("collection_ids")
            if not isinstance(collection_ids, list):
                raise ValueError("Folder IDs must be a list")
            kind = "template" if str(payload.get("kind") or "").casefold() == "template" else "prompt"
            if payload.get("all_filtered"):
                filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
                snapshot = _prompt_asset_snapshot()
                ids = [str(item.get("prompt_id") or "") for item in _filter_prompt_assets(
                    snapshot["templates" if kind == "template" else "prompts"],
                    query=str(filters.get("q") or ""), collection=str(filters.get("collection") or ""),
                    source=str(filters.get("source") or ""), parent=str(filters.get("parent") or ""),
                    subcategory=str(filters.get("subcategory") or ""), log_path=str(filters.get("log") or ""),
                    facets=filters.get("facets") if isinstance(filters.get("facets"), dict) else {},
                    placeholders=list(filters.get("placeholders") or []), sort=str(filters.get("sort") or "preview_newest"),
                    rating=str(filters.get("rating") or ""),
                )]
            result = get_catalog().add_prompts_to_collections(
                ids, [str(value) for value in collection_ids], kind,
            )
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None}); _sync_library_if_stale()
            return web.json_response({"ok": True, **result})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/prompt-assets/{prompt_id}/preview")
    async def solo_prompt_asset_preview(request):
        prompt_id = str(request.match_info.get("prompt_id") or "")
        raw = bytearray()
        seed_source = "preview-image"
        canonical_source = ""
        identity_placeholders = []
        try:
            reader = await request.multipart()
            while True:
                field = await reader.next()
                if field is None:
                    break
                if field.name == "source_prompt_snapshot":
                    canonical_source = _single_line_recipe_prompt(await field.text())
                    if len(canonical_source) > 100000:
                        raise ValueError("Source prompt is too long")
                    continue
                if field.name == "identity_placeholders":
                    identities = json.loads(await field.text())
                    if not isinstance(identities, list) or len(identities) > 3:
                        raise ValueError("Invalid Yearbook identity metadata")
                    for row in identities:
                        if not isinstance(row, dict) or row.get("token") not in {"NAME", "BRAND", "ITEM"}:
                            raise ValueError("Invalid Yearbook identity placeholder")
                        identity_placeholders.append({"token": row["token"], "value": str(row.get("value") or "")})
                    continue
                if field.name == "seed_source":
                    candidate_source = str(await field.text() or "").strip().lower()
                    seed_source = candidate_source if candidate_source in {"preview-image", "catalog-run"} else "preview-image"
                    continue
                if field.name != "file":
                    continue
                while True:
                    chunk = await field.read_chunk(1024 * 1024)
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > 40 * 1024 * 1024:
                        return web.json_response({"ok": False, "error": "Prompt preview import is limited to 40 MB"}, status=413)
            if not raw:
                raise ValueError("Choose a Preview image first")
            raw_bytes = bytes(raw)
            resolved_seed = None
            preview_image = None
            source_prompt_snapshot = ""
            resolved_prompt_snapshot = ""
            preview_metadata: dict[str, str] = {}
            current_asset = next(
                (item for item in _prompt_asset_snapshot().get("records", []) if str(item.get("prompt_id") or "") == prompt_id),
                None,
            )
            fallback_source = _single_line_recipe_prompt((current_asset or {}).get("value"))
            if seed_source == "catalog-run":
                canonical_source = canonical_source or fallback_source
                source_prompt_snapshot = canonical_source
            else:
                canonical_source = ""
            try:
                recipe_payload, parsed_preview = _recipe_from_image_bytes(raw_bytes)
                preview_image = parsed_preview
                generation_values = _recipe_node_values(recipe_payload, STUDIO_GENERATION, include_optional=True)
                resolved_seed = _valid_resolved_seed(generation_values.get("seed_value"))
                source_prompt_snapshot, resolved_prompt_snapshot = _payload_prompt_variants(
                    recipe_payload, fallback_source, canonical_source=canonical_source,
                    identity_placeholders=identity_placeholders,
                )
                preview_metadata = _payload_prompt_preview_metadata(recipe_payload)
            except Exception:
                # A thumbnail can still be useful even if the image did not carry
                # readable generation metadata. In that case preserve any seed
                # already attached to the Prompt instead of clearing it.
                with Image.open(BytesIO(raw_bytes)) as image:
                    preview_image = image.copy()
            filename = _save_preview(preview_image, f"prompt-{hashlib.sha256(prompt_id.encode('utf-8')).hexdigest()[:24]}")
            result = get_catalog().set_prompt_preview(
                prompt_id, filename, "generated:catalog",
                resolved_seed=resolved_seed,
                resolved_seed_source=seed_source if resolved_seed is not None else "",
                source_prompt_snapshot=source_prompt_snapshot,
                resolved_prompt_snapshot=resolved_prompt_snapshot,
                preview_metadata=preview_metadata,
                replace_prompt_snapshots=seed_source == "catalog-run",
            )
        except (TypeError, ValueError, OSError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
        return web.json_response({"ok": True, **result})

    @_creative_library_route("delete", "/prompt-assets/{prompt_id}/preview")
    async def solo_prompt_asset_preview_delete(request):
        prompt_id = str(request.match_info.get("prompt_id") or "")
        row = get_catalog().clear_prompt_preview(prompt_id)
        if row is None:
            return web.json_response({"ok": False, "error": "Prompt record was not found"}, status=404)
        preview_ref = str(row.get("removed_preview_ref") or "")
        if preview_ref:
            (_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
        _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
        return web.json_response({"ok": True, "cleared": True, "prompt_id": prompt_id})

    @_creative_library_route("get", "/fragments")
    async def solo_fragment_assets(request):
        _ensure_fragment_index()
        try:
            limit = max(0, min(500, int(request.query.get("limit") or 96)))
            offset = max(0, int(request.query.get("offset") or 0))
        except (TypeError, ValueError):
            limit, offset = 96, 0
        catalog = get_catalog()
        result = catalog.fragments(
            query=str(request.query.get("q") or ""),
            role=str(request.query.get("role") or ""),
            state=str(request.query.get("state") or "active"),
            sort=str(request.query.get("sort") or "rank"),
            limit=limit,
            offset=offset,
        )
        return web.json_response({"ok": True, **result, "summary": catalog.fragment_summary()})

    @_creative_library_route("post", "/fragments/rebuild")
    async def solo_fragment_rebuild(request):
        fragment_result = _ensure_fragment_index(force=True)
        return web.json_response({"ok": True, "fragment_index": fragment_result})

    @_creative_library_route("post", "/fragments/bulk")
    async def solo_fragment_bulk_update(request):
        _ensure_fragment_index()
        payload = await request.json()
        filters = payload.get("filters") if isinstance(payload.get("filters"), dict) else {}
        try:
            result = get_catalog().bulk_update_fragments(
                fragment_ids=list(payload.get("fragment_ids") or []),
                all_filtered=bool(payload.get("all_filtered")),
                query=str(filters.get("q") or ""),
                role=str(filters.get("role") or ""),
                state_filter=str(filters.get("state") or "active"),
                review_state=payload.get("state") if "state" in payload else None,
                new_role=payload.get("role") if "role" in payload else None,
                reset_role=bool(payload.get("reset_role")),
                rating=payload.get("rating") if "rating" in payload else None,
            )
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, **result, "summary": get_catalog().fragment_summary()})

    @_creative_library_route("get", "/fragments/for-prompt/{prompt_id}")
    async def solo_fragments_for_prompt(request):
        _ensure_fragment_index()
        prompt_id = str(request.match_info.get("prompt_id") or "")
        return web.json_response({"ok": True, "prompt_id": prompt_id, "fragments": get_catalog().fragments_for_prompt(prompt_id)})

    @_creative_library_route("get", "/fragments/decompose/{prompt_id}")
    async def solo_fragment_decompose_prompt(request):
        _ensure_fragment_index()
        try:
            result = _decompose_prompt_for_builder(str(request.match_info.get("prompt_id") or ""))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=404)
        return web.json_response(result)

    @_creative_library_route("patch", "/fragments/{fragment_id}/review")
    async def solo_fragment_review(request):
        payload = await request.json()
        try:
            fragment = get_catalog().set_fragment_review(
                str(request.match_info.get("fragment_id") or ""),
                str(payload.get("state") or ""),
                payload.get("rating"),
            )
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        if fragment is None:
            return web.json_response({"ok": False, "error": "Fragment no longer exists"}, status=404)
        return web.json_response({"ok": True, "fragment": fragment})

    @_creative_library_route("get", "/boards")
    async def solo_creative_boards(request):
        return web.json_response({"ok": True, "boards": get_catalog().creative_boards()})

    @_creative_library_route("post", "/boards")
    async def solo_creative_board_save(request):
        payload = await request.json()
        board_payload = payload.get("payload")
        if not isinstance(board_payload, dict):
            return web.json_response({"ok": False, "error": "Board payload must be an object"}, status=400)
        try:
            board = get_catalog().save_creative_board(
                str(payload.get("board_id") or ""),
                str(payload.get("name") or ""),
                board_payload,
            )
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "board": board})

    @_creative_library_route("delete", "/boards/{board_id}")
    async def solo_creative_board_delete(request):
        board_id = str(request.match_info.get("board_id") or "")
        if not get_catalog().delete_creative_board(board_id):
            return web.json_response({"ok": False, "error": "Board no longer exists"}, status=404)
        return web.json_response({"ok": True, "deleted": True, "board_id": board_id})

    @_creative_library_route("get", "/prompt-harvest/analyze")
    async def solo_prompt_harvest_analyze(request):
        try:
            limit = int(request.query.get("limit") or 100)
            offset = int(request.query.get("offset") or 0)
        except (TypeError, ValueError):
            limit, offset = 100, 0
        result = _prompt_harvest_analysis(
            status_filter=str(request.query.get("status") or ""),
            query=str(request.query.get("query") or ""),
            sample_limit=max(0, min(500, limit)),
            sample_offset=max(0, offset),
        )
        return web.json_response(result)

    @_creative_library_route("post", "/prompt-harvest/accept")
    async def solo_prompt_harvest_accept(request):
        payload = await request.json()
        try:
            result = _accept_prompt_harvest(str(payload.get("prompt_id") or ""), str(payload.get("outfit_value") or ""))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response(result)

    @_creative_library_route("post", "/prompt-harvest/accept-filtered")
    async def solo_prompt_harvest_accept_filtered(request):
        payload = await request.json()
        result = _accept_filtered_prompt_harvest(
            status_filter=str(payload.get("status") or "ready"),
            query=str(payload.get("query") or ""),
        )
        return web.json_response(result)

    @_creative_library_route("get", "/log-sources")
    async def solo_recipe_log_sources(request):
        kind = str(request.query.get("kind") or "").strip().lower()
        if kind not in {"outfit", "scene"}:
            return web.json_response({"ok": False, "error": "Log kind must be outfit or scene"}, status=400)
        return web.json_response({"ok": True, "kind": kind, "logs": _scan_component_source_logs(kind)})

    @_creative_library_route("post", "/log-import")
    async def solo_recipe_log_import(request):
        payload = await request.json()
        kind = str(payload.get("kind") or "").strip().lower()
        paths = payload.get("paths")
        if kind not in {"outfit", "scene"}:
            return web.json_response({"ok": False, "error": "Log kind must be outfit or scene"}, status=400)
        if not isinstance(paths, list):
            return web.json_response({"ok": False, "error": "Choose one or more log files"}, status=400)
        try:
            result = _import_component_source_logs(kind, paths, str(payload.get("collection_mode") or "none"))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "kind": kind, **result})

    @_creative_library_route("post", "/component-assets/import")
    async def solo_component_assets_import(request):
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                raise ValueError("Log import payload must be an object")
            kind = str(payload.get("kind") or "outfit").strip().casefold()
            if kind not in {"outfit", "scene"}:
                raise ValueError("Log kind must be outfit or scene")
            result = _import_component_text_log(
                kind,
                str(payload.get("text") or ""),
                str(payload.get("parent") or ""),
                str(payload.get("subcategory") or ""),
                str(payload.get("log_name") or ""),
                collection_id=str(payload.get("collection_id") or ""),
                collection_name=str(payload.get("collection_name") or ""),
            )
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "kind": kind, **result})

    @_creative_library_route("get", "/import-batches")
    async def solo_recipe_import_batches(request):
        kind = str(request.query.get("kind") or "").strip().lower()
        if kind and kind not in {"outfit", "scene"}:
            return web.json_response({"ok": False, "error": "Import history kind must be outfit or scene"}, status=400)
        try:
            limit = int(request.query.get("limit") or 20)
            rows = get_catalog().component_import_batches(kind, limit)
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "kind": kind, "batches": rows})

    @_creative_library_route("post", "/import-batches/{batch_id}/undo")
    async def solo_recipe_undo_import_batch(request):
        batch_id = str(request.match_info.get("batch_id") or "")
        catalog = get_catalog()
        try:
            result = catalog.undo_component_import_batch(batch_id)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=404)
        _safe_sync_recipe_prompt_logs()
        remaining_ids = {str(item.get("component_id") or "") for item in catalog.recipe_components(str(result.get("kind") or ""))}
        for removed in result.get("removed") or []:
            component_id = str((removed or {}).get("component_id") or "")
            preview_ref = str((removed or {}).get("preview_ref") or "")
            if preview_ref and component_id not in remaining_ids:
                (_component_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
        if str(result.get("collection_mode") or "") == "managed-log":
            for source_path in result.get("source_paths") or []:
                managed_log = _resolve_imported_component_log(str(result.get("kind") or ""), str(source_path or ""))
                if managed_log is not None and managed_log.is_file():
                    managed_log.unlink(missing_ok=True)
            _prune_empty_component_import_folders(str(result.get("kind") or ""))
        return web.json_response({
            "ok": True,
            "batch_id": batch_id,
            "deleted": int(result.get("deleted") or 0),
            "retained": int(result.get("retained") or 0),
            "memberships_removed": int(result.get("memberships_removed") or 0),
            "collections_removed": int(result.get("collections_removed") or 0),
        })

    @_creative_library_route("get", "/derived-values")
    async def solo_recipe_derived_values(request):
        sync_logs = str(request.query.get("sync") or "1").strip().casefold() not in {"0", "false", "no"}
        return web.json_response(_derived_value_snapshot(str(request.query.get("kind") or ""), sync_logs=sync_logs))

    @_creative_library_route("post", "/derived-values")
    async def solo_recipe_create_derived_value(request):
        payload = await request.json()
        kind = str(payload.get("kind") or "").strip().lower()
        raw_values = payload.get("values") if isinstance(payload.get("values"), list) else [payload.get("value")]
        values = list(dict.fromkeys(_single_line_recipe_prompt(value) for value in raw_values if _single_line_recipe_prompt(value)))
        if not values:
            return web.json_response({"ok": False, "error": "Add at least one outfit or scene value"}, status=400)
        try:
            catalog = get_catalog()
            if kind == "scene":
                _ensure_scene_taxonomy(catalog)
            components = [catalog.upsert_recipe_component(kind, value, manual=True) for value in values]
            if kind == "scene":
                for component in components:
                    _classify_scene_component_into_existing_taxonomy(catalog, component)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "component": components[0], "components": components, "added": len(components)})

    @_creative_library_route("get", "/cleanup")
    async def solo_recipe_cleanup_report(request):
        kind = str(request.query.get("kind") or "").strip().lower()
        if kind not in {"outfit", "scene"}:
            return web.json_response({"ok": False, "error": "Cleanup kind must be outfit or scene"}, status=400)
        catalog = get_catalog()
        recipes = catalog.recipes()
        _ensure_derived_component_records(recipes)
        tombstones = {str(row.get("value") or "").casefold() for row in catalog.component_tombstones(kind)}
        assets = _recipe_component_assets(recipes, kind, catalog.recipe_components(kind), tombstones)
        return web.json_response(_cleanup_component_report(assets, kind))

    @_creative_library_route("post", "/cleanup")
    async def solo_recipe_cleanup_report_scoped(request):
        payload = await request.json()
        kind = str(payload.get("kind") or "").strip().lower()
        if kind not in {"outfit", "scene"}:
            return web.json_response({"ok": False, "error": "Cleanup kind must be outfit or scene"}, status=400)
        component_ids = payload.get("component_ids")
        if component_ids is not None and not isinstance(component_ids, list):
            return web.json_response({"ok": False, "error": "Cleanup asset IDs must be a list"}, status=400)
        catalog = get_catalog()
        recipes = catalog.recipes()
        _ensure_derived_component_records(recipes)
        tombstones = {str(row.get("value") or "").casefold() for row in catalog.component_tombstones(kind)}
        assets = _recipe_component_assets(recipes, kind, catalog.recipe_components(kind), tombstones)
        if isinstance(component_ids, list):
            wanted = {str(value) for value in component_ids if str(value)}
            assets = [item for item in assets if str(item.get("component_id") or "") in wanted]
        return web.json_response(_cleanup_component_report(assets, kind))

    @_creative_library_route("patch", "/derived-values/{component_id}")
    async def solo_component_edit_value(request):
        try:
            payload = await request.json()
            result = get_catalog().update_recipe_component_value(str(request.match_info.get("component_id") or ""), str(payload.get("value") or ""))
            _safe_sync_recipe_prompt_logs()
            return web.json_response({"ok": True, "item": result})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/derived-values/{component_id}/rating")
    async def solo_component_rating(request):
        component_id = str(request.match_info.get("component_id") or "")
        payload = await request.json()
        try:
            result = get_catalog().set_component_rating(component_id, payload.get("rating", 0))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, **result})

    @_creative_library_route("post", "/derived-values/bulk/collections")
    async def solo_component_bulk_add_collections(request):
        payload = await request.json()
        component_ids = payload.get("component_ids")
        collection_ids = payload.get("collection_ids")
        if not isinstance(component_ids, list) or not isinstance(collection_ids, list):
            return web.json_response({"ok": False, "error": "Asset IDs and collection IDs must be lists"}, status=400)
        try:
            if payload.get("replace_home"):
                if len(collection_ids) != 1:
                    raise ValueError("Choose exactly one Home")
                result = get_catalog().move_components_home(component_ids, collection_ids[0])
            else:
                result = get_catalog().add_components_to_collections(component_ids, collection_ids)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, **result})

    @_creative_library_route("post", "/derived-values/bulk/collections/remove")
    async def solo_component_bulk_remove_collections(request):
        payload = await request.json()
        component_ids = payload.get("component_ids")
        collection_ids = payload.get("collection_ids")
        if not isinstance(component_ids, list) or not isinstance(collection_ids, list):
            return web.json_response({"ok": False, "error": "Asset IDs and collection IDs must be lists"}, status=400)
        result = get_catalog().remove_components_from_collections(component_ids, collection_ids)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, **result})

    @_creative_library_route("post", "/derived-values/bulk/delete")
    async def solo_component_bulk_delete(request):
        payload = await request.json()
        component_ids = payload.get("component_ids")
        if not isinstance(component_ids, list):
            return web.json_response({"ok": False, "error": "Asset IDs must be a list"}, status=400)
        catalog = get_catalog()
        everywhere = bool(payload.get("everywhere"))
        result = catalog.delete_recipe_components(component_ids, everywhere=everywhere)
        _safe_sync_recipe_prompt_logs()
        remaining_ids = {str(item.get("component_id") or "") for item in catalog.recipe_components()}
        for removed in result.get("removed") or []:
            component_id = str((removed or {}).get("component_id") or "")
            preview_ref = str((removed or {}).get("preview_ref") or "")
            if preview_ref and component_id not in remaining_ids:
                (_component_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
        surviving = len(set(str(value) for value in component_ids if str(value)) & remaining_ids)
        return web.json_response({
            "ok": True,
            "deleted": int(result.get("deleted") or 0),
            "protected": int(result.get("protected") or 0),
            "tombstoned": int(result.get("tombstoned") or 0),
            "remaining_from_recipes": surviving,
        })

    @_creative_library_route("delete", "/derived-values/{component_id}")
    async def solo_recipe_delete_derived_value(request):
        component_id = str(request.match_info.get("component_id") or "")
        catalog = get_catalog()
        existing = next((item for item in catalog.recipe_components() if str(item.get("component_id") or "") == component_id), None)
        if existing is None:
            return web.json_response({"ok": False, "error": "Library asset was not found"}, status=404)
        if not bool(existing.get("manual")):
            return web.json_response({"ok": False, "error": "Automatically derived assets are removed by deleting their source recipes"}, status=400)
        removed = catalog.delete_recipe_component(component_id)
        preview_ref = str((removed or {}).get("preview_ref") or "")
        if preview_ref:
            (_component_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "deleted": True, "component_id": component_id})

    @_creative_library_route("get", "/component-collections")
    async def solo_component_collections(request):
        kind = str(request.query.get("kind") or "").strip().lower()
        if kind not in {"outfit", "scene"}:
            return web.json_response({"ok": False, "error": "Collection kind must be outfit or scene"}, status=400)
        catalog = get_catalog()
        migration = _ensure_scene_taxonomy(catalog) if kind == "scene" else {"migrated": False}
        return web.json_response({"ok": True, "kind": kind, "collections": catalog.component_collections(kind), "taxonomy": migration})

    @_creative_library_route("post", "/component-collections")
    async def solo_component_create_collection(request):
        payload = await request.json()
        kind = str(payload.get("kind") or "").strip().lower()
        try:
            collection = get_catalog().create_component_collection(kind, str(payload.get("name") or ""), str(payload.get("parent_id") or ""))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "collection": collection})

    @_creative_library_route("patch", "/component-collections/{collection_id}")
    async def solo_component_update_collection(request):
        collection_id = str(request.match_info.get("collection_id") or "")
        payload = await request.json()
        try:
            collection = get_catalog().update_component_collection(
                collection_id,
                name=payload.get("name") if "name" in payload else None,
                parent_id=payload.get("parent_id") if "parent_id" in payload else None,
            )
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "collection": collection})

    @_creative_library_route("delete", "/component-collections/{collection_id}")
    async def solo_component_delete_collection(request):
        collection_id = str(request.match_info.get("collection_id") or "")
        if not get_catalog().delete_component_collection(collection_id):
            return web.json_response({"ok": False, "error": "Collection no longer exists"}, status=404)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True})

    @_creative_library_route("put", "/derived-values/{component_id}/collections")
    async def solo_component_set_collections(request):
        component_id = str(request.match_info.get("component_id") or "")
        payload = await request.json()
        collection_ids = payload.get("collection_ids")
        if not isinstance(collection_ids, list):
            return web.json_response({"ok": False, "error": "Collection IDs must be a list"}, status=400)
        try:
            rows = get_catalog().set_component_collections(component_id, collection_ids)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "collections": rows})

    @_creative_library_route("get", "/library-collections")
    async def solo_library_collections(request):
        kind = str(request.query.get("kind") or "").strip().lower()
        try:
            rows = get_catalog().library_collections(kind)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "kind": kind, "collections": rows})

    @_creative_library_route("post", "/library-collections")
    async def solo_library_collection_create(request):
        try:
            payload = await request.json()
            row = get_catalog().create_library_collection(str(payload.get("kind") or ""), str(payload.get("name") or ""), str(payload.get("color") or ""))
            return web.json_response({"ok": True, "collection": row})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("patch", "/library-collections/{collection_id}")
    async def solo_library_collection_update(request):
        try:
            payload = await request.json()
            row = get_catalog().update_library_collection(str(request.match_info.get("collection_id") or ""), str(payload.get("name") or ""))
            return web.json_response({"ok": True, "collection": row})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("delete", "/library-collections/{collection_id}")
    async def solo_library_collection_delete(request):
        if not get_catalog().delete_library_collection(str(request.match_info.get("collection_id") or "")):
            return web.json_response({"ok": False, "error": "Collection no longer exists"}, status=404)
        return web.json_response({"ok": True})

    @_creative_library_route("put", "/library-collections/{kind}/{asset_id}")
    async def solo_library_asset_collections(request):
        try:
            payload = await request.json(); collection_ids = payload.get("collection_ids")
            if not isinstance(collection_ids, list): raise ValueError("Collection IDs must be a list")
            rows = get_catalog().set_library_asset_collections(str(request.match_info.get("kind") or ""), str(request.match_info.get("asset_id") or ""), [str(value) for value in collection_ids])
            return web.json_response({"ok": True, "collections": rows})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/library-collections/bulk/remove")
    async def solo_library_asset_collections_remove(request):
        try:
            payload = await request.json()
            if not isinstance(payload.get("asset_ids"), list):
                raise ValueError("Asset IDs must be a list")
            result = get_catalog().remove_library_assets_from_collection(str(payload.get("kind") or ""), payload["asset_ids"], str(payload.get("collection_id") or ""))
            return web.json_response({"ok": True, **result})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/library-collections/bulk")
    async def solo_library_asset_collections_bulk(request):
        try:
            payload = await request.json(); asset_ids = payload.get("asset_ids"); collection_ids = payload.get("collection_ids")
            if not isinstance(asset_ids, list) or not isinstance(collection_ids, list): raise ValueError("Asset IDs and Collection IDs must be lists")
            result = get_catalog().add_library_assets_to_collections(str(payload.get("kind") or ""), [str(value) for value in asset_ids], [str(value) for value in collection_ids])
            return web.json_response({"ok": True, **result})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("get", "/showcase-collections")
    async def solo_prompt_showcase_collections(request):
        kind = "template" if str(request.query.get("kind") or "").casefold() == "template" else "prompt"
        return web.json_response({"ok": True, "kind": kind, "collections": get_catalog().prompt_showcase_collections(kind)})

    @_creative_library_route("post", "/showcase-collections")
    async def solo_prompt_showcase_collection_create(request):
        try:
            payload = await request.json()
            collection = get_catalog().create_prompt_showcase_collection(
                str(payload.get("kind") or "prompt"), str(payload.get("name") or ""),
            )
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            return web.json_response({"ok": True, "collection": collection})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("patch", "/showcase-collections/{collection_id}")
    async def solo_prompt_showcase_collection_update(request):
        try:
            payload = await request.json()
            collection = get_catalog().update_prompt_showcase_collection(
                str(request.match_info.get("collection_id") or ""), name=str(payload.get("name") or ""),
            )
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            return web.json_response({"ok": True, "collection": collection})
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("delete", "/showcase-collections/{collection_id}")
    async def solo_prompt_showcase_collection_delete(request):
        collection_id = str(request.match_info.get("collection_id") or "")
        if not get_catalog().delete_prompt_showcase_collection(collection_id):
            return web.json_response({"ok": False, "error": "Collection no longer exists"}, status=404)
        _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
        return web.json_response({"ok": True})

    @_creative_library_route("get", "/collections")
    async def solo_recipe_collections(request):
        return web.json_response(get_catalog().recipe_collections())

    @_creative_library_route("post", "/collections")
    async def solo_recipe_create_collection(request):
        payload = await request.json()
        try:
            collection = get_catalog().create_recipe_collection(str(payload.get("name") or ""))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "collection": collection})

    @_creative_library_route("patch", "/collections/{collection_id}")
    async def solo_recipe_update_collection(request):
        collection_id = str(request.match_info.get("collection_id") or "")
        try:
            payload = await request.json()
            collection = get_catalog().update_recipe_collection(collection_id, name=str(payload.get("name") or ""))
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "collection": collection})

    @_creative_library_route("delete", "/collections/{collection_id}")
    async def solo_recipe_delete_collection(request):
        collection_id = str(request.match_info.get("collection_id") or "")
        if not get_catalog().delete_recipe_collection(collection_id):
            return web.json_response({"ok": False, "error": "Collection no longer exists"}, status=404)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True})

    @_creative_library_route("post", "/recipes")
    async def solo_recipe_save(request):
        payload = await request.json()
        recipe_id = str(payload.get("recipe_id") or f"recipe:{uuid.uuid4().hex}")
        recipe = payload.get("payload")
        if not isinstance(recipe, dict):
            return web.json_response({"ok": False, "error": "Recipe payload must be an object"}, status=400)
        recipe = _curate_prompt_catalog_recipe(recipe)
        recipe["tokens"] = _recipe_tokens(recipe)
        try:
            get_catalog().save_recipe(recipe_id, str(payload.get("name", "")), recipe, str(payload.get("preview_ref", "")))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "recipe_id": recipe_id})

    @_creative_library_route("delete", "/recipes/{recipe_id}")
    async def solo_recipe_delete(request):
        recipe_id = str(request.match_info.get("recipe_id", ""))
        recipe = next((item for item in get_catalog().recipes() if item.get("recipe_id") == recipe_id), None)
        get_catalog().delete_recipe(recipe_id)
        preview_ref = str((recipe or {}).get("preview_ref") or "")
        preview_path = _preview_directory() / Path(preview_ref).name
        if preview_ref and preview_path.is_file():
            preview_path.unlink(missing_ok=True)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True})

    @_creative_library_route("put", "/recipes/{recipe_id}/collections")
    async def solo_recipe_set_collections(request):
        recipe_id = str(request.match_info.get("recipe_id") or "")
        payload = await request.json()
        collection_ids = payload.get("collection_ids")
        if not isinstance(collection_ids, list):
            return web.json_response({"ok": False, "error": "Collection IDs must be a list"}, status=400)
        try:
            collections = get_catalog().set_recipe_collections(recipe_id, collection_ids)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "collections": collections})

    @_creative_library_route("post", "/recipes/bulk/collections")
    async def solo_recipe_bulk_add_collections(request):
        payload = await request.json()
        recipe_ids = payload.get("recipe_ids")
        collection_ids = payload.get("collection_ids")
        if not isinstance(recipe_ids, list) or not isinstance(collection_ids, list):
            return web.json_response({"ok": False, "error": "Recipe IDs and collection IDs must be lists"}, status=400)
        try:
            result = get_catalog().add_recipes_to_collections(recipe_ids, collection_ids)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, **result})

    @_creative_library_route("post", "/recipes/bulk/delete")
    async def solo_recipe_bulk_delete(request):
        payload = await request.json()
        recipe_ids = payload.get("recipe_ids")
        if not isinstance(recipe_ids, list):
            return web.json_response({"ok": False, "error": "Recipe IDs must be a list"}, status=400)
        requested = list(dict.fromkeys(str(value) for value in recipe_ids if str(value)))
        selected = {
            str(item.get("recipe_id")): str(item.get("preview_ref") or "")
            for item in get_catalog().recipes()
            if str(item.get("recipe_id")) in requested
        }
        deleted = get_catalog().delete_recipes(requested)
        for preview_ref in selected.values():
            preview_path = _preview_directory() / Path(preview_ref).name
            if preview_ref and preview_path.is_file():
                preview_path.unlink(missing_ok=True)
        _safe_sync_recipe_prompt_logs()
        return web.json_response({"ok": True, "deleted": deleted})

    @_creative_library_route("get", "/preview/{filename}")
    async def solo_recipe_preview(request):
        filename = str(request.match_info.get("filename", ""))
        if not filename or Path(filename).name != filename:
            raise web.HTTPNotFound()
        path = _preview_directory() / filename
        if not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    @_creative_library_route("get", "/wardrobe-migration/analyze")
    async def solo_wardrobe_migration_analyze(request):
        refresh = str(request.query.get("refresh") or "").strip().lower() in {"1", "true", "yes"}
        try:
            limit = max(0, min(250, int(request.query.get("limit") or 80)))
        except (TypeError, ValueError):
            limit = 80
        try:
            offset = max(0, int(request.query.get("offset") or 0))
        except (TypeError, ValueError):
            offset = 0
        status_filter = str(request.query.get("status") or "").strip().lower()
        issue_filter = str(request.query.get("issue") or "").strip().lower()
        new_only = str(request.query.get("new") or "").strip().lower() in {"1", "true", "yes"}
        query = str(request.query.get("q") or "").strip()[:240]
        try:
            result = _analyze_wardrobe_migration(
                refresh=refresh, sample_limit=limit, sample_offset=offset,
                status_filter=status_filter, query=query, issue_filter=issue_filter, new_only=new_only,
            )
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response(result)

    @_creative_library_route("get", "/wardrobe-migration/status")
    async def solo_wardrobe_migration_status(request):
        return web.json_response(_wardrobe_migration_status())

    @_creative_library_route("post", "/wardrobe-migration/accept")
    async def solo_wardrobe_migration_accept(request):
        payload = await request.json()
        look_ids = payload.get("look_ids") if isinstance(payload.get("look_ids"), list) else []
        high_confidence_only = bool(payload.get("high_confidence_only"))
        manually_reviewed = bool(payload.get("manually_reviewed"))
        try:
            result = _accept_wardrobe_migration(look_ids, high_confidence_only=high_confidence_only, manually_reviewed=manually_reviewed)
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response(result)


    @_creative_library_route("post", "/wardrobe-migration/accept-filtered")
    async def solo_wardrobe_migration_accept_filtered(request):
        payload = await request.json()
        try:
            result = _accept_filtered_wardrobe_migration(
                status_filter=str(payload.get("status") or "").strip().lower(),
                issue_filter=str(payload.get("issue") or "").strip().lower(),
                query=str(payload.get("q") or "").strip()[:240],
                new_only=bool(payload.get("new_only")),
            )
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response(result)

    @_creative_library_route("post", "/wardrobe-migration/ignore-filtered")
    async def solo_wardrobe_migration_ignore_filtered(request):
        payload = await request.json()
        try:
            result = _ignore_filtered_wardrobe_migration(
                status_filter=str(payload.get("status") or "").strip().lower(),
                issue_filter=str(payload.get("issue") or "").strip().lower(),
                query=str(payload.get("q") or "").strip()[:240],
                new_only=bool(payload.get("new_only")),
            )
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response(result)

    @_creative_library_route("post", "/wardrobe-migration/accept-custom")
    async def solo_wardrobe_migration_accept_custom(request):
        payload = await request.json()
        look_id = str(payload.get("look_id") or "").strip()
        raw_items = payload.get("items") if isinstance(payload.get("items"), list) else []
        look = next((row for row in get_catalog().recipe_components("outfit") if str(row.get("component_id") or "") == look_id), None)
        if not look:
            return web.json_response({"ok": False, "error": "Outfit Look was not found"}, status=404)
        items: list[dict[str, Any]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            item_type = str(raw_item.get("item_type") or "piece").strip().lower()
            value = _single_line_recipe_prompt(raw_item.get("value"))
            if item_type not in {"piece", "set", "finisher", "styling"} or not value:
                continue
            items.append({
                "item_type": item_type,
                "category": _single_line_recipe_prompt(raw_item.get("category") or "Uncategorized") or "Uncategorized",
                "subtype": _single_line_recipe_prompt(raw_item.get("subtype") or ""),
                "value": value,
                "relation": _single_line_recipe_prompt(raw_item.get("relation") or ""),
            })
        if not items:
            return web.json_response({"ok": False, "error": "Add at least one accepted Piece, Set, Finisher, or Styling token"}, status=400)
        proposal = {"status": "ready", "confidence": 1.0, "items": items, "parser_version": WARDROBE_PARSER_VERSION, "manually_reviewed": True}
        get_catalog().set_wardrobe_migration_state(look_id, parser_version=WARDROBE_PARSER_VERSION, status="ready", confidence=1.0, proposal=proposal)
        result = _accept_wardrobe_migration([look_id], high_confidence_only=False)
        return web.json_response(result)

    @_creative_library_route("post", "/wardrobe-migration/ignore")
    async def solo_wardrobe_migration_ignore(request):
        payload = await request.json()
        look_id = str(payload.get("look_id") or "").strip()
        state = get_catalog().wardrobe_migration_states().get(look_id)
        if not state:
            proposal = _decompose_outfit_look(str(payload.get("value") or ""))
            confidence = float(proposal.get("confidence") or 0)
        else:
            proposal = dict(state.get("proposal") or {})
            confidence = float(state.get("confidence") or 0)
        proposal = dict(proposal); proposal["manually_reviewed"] = True
        try:
            get_catalog().set_wardrobe_migration_state(look_id, parser_version=WARDROBE_PARSER_VERSION, status="ignored", confidence=confidence, proposal=proposal)
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "look_id": look_id, "status": "ignored"})

    @_creative_library_route("get", "/library-pack/options")
    async def solo_creative_library_pack_options(request):
        mode = str(request.query.get("mode") or "starter").strip().lower()
        if mode not in {"starter", "backup"}:
            mode = "starter"
        try:
            snapshot = _creative_library_pack_snapshot(mode)
            return web.json_response({"ok": True, "mode": mode, "contents": _creative_library_pack_contents(snapshot)})
        except Exception as error:
            return web.json_response({"ok": False, "error": f"Could not read Creative Library export options: {error}"}, status=400)

    @_creative_library_route("post", "/library-pack/export")
    async def solo_creative_library_pack_export(request):
        payload = await request.json()
        try:
            raw, filename, manifest = _creative_library_pack_export(payload)
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-SickOllie-Library-Pack": json.dumps({"name": manifest.get("name"), "version": manifest.get("version"), "mode": manifest.get("export_mode"), "counts": manifest.get("counts")}),
        }
        return web.Response(body=raw, content_type="application/zip", headers=headers)

    @_creative_library_route("post", "/library-pack/inspect")
    async def solo_creative_library_pack_inspect(request):
        reader = await request.multipart()
        try:
            with tempfile.TemporaryDirectory(prefix="sickollie-library-pack-inspect-") as directory:
                upload_path = Path(directory) / "inspect.soslibrary"
                total = 0
                found = False
                while True:
                    field = await reader.next()
                    if field is None:
                        break
                    if field.name != "file":
                        continue
                    found = True
                    with upload_path.open("wb") as stream:
                        while True:
                            chunk = await field.read_chunk(1024 * 1024)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > 4 * 1024 * 1024 * 1024:
                                return web.json_response({"ok": False, "error": "Creative Library Packs are limited to 4 GB"}, status=413)
                            stream.write(chunk)
                if not found or not upload_path.is_file():
                    return web.json_response({"ok": False, "error": "Choose a .soslibrary file to inspect"}, status=400)
                return web.json_response(_creative_library_pack_inspect(upload_path))
        except (zipfile.BadZipFile, json.JSONDecodeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            return web.json_response({"ok": False, "error": f"Could not inspect Creative Library Pack: {error}"}, status=400)

    @_creative_library_route("post", "/library-pack/import")
    async def solo_creative_library_pack_import(request):
        reader = await request.multipart()
        try:
            with tempfile.TemporaryDirectory(prefix="sickollie-library-pack-") as directory:
                upload_path = Path(directory) / "import.soslibrary"
                total = 0
                found = False
                selection: dict[str, Any] | None = None
                while True:
                    field = await reader.next()
                    if field is None:
                        break
                    if field.name == "selection":
                        raw_selection = (await field.text()).strip()
                        if raw_selection:
                            parsed = json.loads(raw_selection)
                            if not isinstance(parsed, dict):
                                raise ValueError("Import selection must be an object")
                            selection = parsed
                        continue
                    if field.name != "file":
                        continue
                    found = True
                    with upload_path.open("wb") as stream:
                        while True:
                            chunk = await field.read_chunk(1024 * 1024)
                            if not chunk:
                                break
                            total += len(chunk)
                            if total > 4 * 1024 * 1024 * 1024:
                                return web.json_response({"ok": False, "error": "Creative Library Packs are limited to 4 GB"}, status=413)
                            stream.write(chunk)
                if not found or not upload_path.is_file():
                    return web.json_response({"ok": False, "error": "Choose a .soslibrary file to import"}, status=400)
                return web.json_response(_creative_library_pack_import(upload_path, selection))
        except (zipfile.BadZipFile, json.JSONDecodeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            return web.json_response({"ok": False, "error": f"Could not import Creative Library Pack: {error}"}, status=400)

    @_creative_library_route("get", "/library-packs")
    async def solo_creative_library_packs(request):
        return web.json_response({"ok": True, "packs": get_catalog().creative_library_packs()})

    @_creative_library_route("post", "/maintenance/purge")
    async def solo_creative_library_purge(request):
        try:
            payload = await request.json()
            if not isinstance(payload, dict): raise ValueError("Purge payload must be an object")
            allowed = ("templates", "prompts", "saved_recipes", "outfit_looks", "wardrobe", "scenes", "workshop")
            scopes = [str(value) for value in payload.get("scopes") or [] if str(value) in allowed]
            scopes = list(dict.fromkeys(scopes))
            if not scopes: raise ValueError("Choose at least one Creative Library area to purge")
            total = set(scopes) == set(allowed)
            expected = "PURGE EVERYTHING" if total else "PURGE SELECTED"
            if str(payload.get("confirm") or "").strip().upper() != expected:
                raise ValueError(f"Type {expected} to confirm this purge")
            catalog = get_catalog(); results: dict[str, Any] = {}; preview_deleted = 0
            def remove_previews(refs: list[str], directory: Path) -> int:
                deleted = 0
                for ref in refs:
                    filename = Path(str(ref or "")).name
                    if not filename: continue
                    target = directory / filename; existed = target.is_file(); target.unlink(missing_ok=True)
                    if existed: deleted += 1
                return deleted
            if "templates" in scopes:
                row = catalog.purge_prompt_library("template"); preview_deleted += remove_previews(row.pop("preview_refs", []), _preview_directory()); row.pop("prompt_ids", None); results["templates"] = row
            if "prompts" in scopes:
                row = catalog.purge_prompt_library("prompt"); preview_deleted += remove_previews(row.pop("preview_refs", []), _preview_directory()); row.pop("prompt_ids", None); results["prompts"] = row
            # Preserve source TXT files. Mark their current filesystem signature as already indexed
            # so a purge remains empty instead of immediately resurrecting the same corpus.
            if "templates" in scopes or "prompts" in scopes:
                root = _prompt_corpus_root()
                if root is not None and root.is_dir():
                    files = _prompt_source_files(root)
                    if files: catalog.set_metadata_value("prompt_index_signature", _file_set_signature(root, files, PROMPT_INDEX_VERSION))
                _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None}); _PROMPT_FILTER_METADATA_CACHE.clear()
            if "saved_recipes" in scopes:
                row = catalog.purge_saved_recipes(); preview_deleted += remove_previews(row.pop("preview_refs", []), _preview_directory()); results["saved_recipes"] = row
            if "outfit_looks" in scopes:
                row = catalog.purge_components("outfit"); preview_deleted += remove_previews(row.pop("preview_refs", []), _component_preview_directory()); results["outfit_looks"] = row
            if "scenes" in scopes:
                row = catalog.purge_components("scene"); preview_deleted += remove_previews(row.pop("preview_refs", []), _component_preview_directory()); results["scenes"] = row
            if "wardrobe" in scopes:
                row = _purge_wardrobe(); preview_deleted += int(row.pop("previews_deleted", 0)); results["wardrobe"] = row
            if "workshop" in scopes:
                results["workshop"] = catalog.purge_workshop_data()
            if total:
                results["pack_registry"] = catalog.purge_pack_registry()
            _LIBRARY_SYNC_CACHE.update({"key": None, "value": None}); _DERIVED_VALUE_CACHE.update({"key": None, "value": None})
            return web.json_response({"ok": True, "scopes": scopes, "total": total, "results": results, "previews_deleted": preview_deleted, "counts": catalog.creative_library_counts(), "revisions": catalog.creative_library_revisions()})
        except (TypeError, ValueError, OSError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("get", "/maintenance/orphan-previews")
    async def solo_creative_library_orphan_previews(request):
        try:
            return web.json_response(_creative_library_orphan_previews(delete=False))
        except Exception as error:
            return web.json_response({"ok": False, "error": f"Could not scan Creative Library thumbnails: {error}"}, status=400)

    @_creative_library_route("post", "/maintenance/orphan-previews/clean")
    async def solo_creative_library_orphan_previews_clean(request):
        try:
            payload = await request.json()
            if str(payload.get("confirm") or "").strip().upper() != "CLEAN ORPHAN THUMBNAILS":
                raise ValueError("Type CLEAN ORPHAN THUMBNAILS to confirm")
            return web.json_response(_creative_library_orphan_previews(delete=True))
        except (TypeError, ValueError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        except Exception as error:
            return web.json_response({"ok": False, "error": f"Could not clean Creative Library thumbnails: {error}"}, status=400)

    @_creative_library_route("post", "/wardrobe-items/purge")
    async def solo_wardrobe_purge(request):
        payload = await request.json()
        if str(payload.get("confirm") or "").strip().upper() != "PURGE":
            return web.json_response({"ok": False, "error": "Type PURGE to confirm the Wardrobe reset."}, status=400)
        try:
            result = _purge_wardrobe()
            _safe_sync_recipe_prompt_logs(kind="outfit")
            return web.json_response({"ok": True, **result})
        except Exception as error:
            return web.json_response({"ok": False, "error": f"Could not purge Wardrobe: {error}"}, status=400)

    @_creative_library_route("get", "/wardrobe-items")
    async def solo_wardrobe_items(request):
        item_type = str(request.query.get("item_type") or "").strip().lower()
        try:
            rows = get_catalog().wardrobe_items(item_type)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        for item in rows:
            item["kind"] = "piece"
            item["catalog_preview_ref"] = str(item.get("preview_ref") or "") if str(item.get("preview_source") or "").startswith("generated:catalog") else ""
            item["preview_updated_at"] = item.get("preview_updated_at") or item.get("updated_at") or item.get("created_at") or ""
            flags: list[str] = []
            if str(item.get("item_type") or "piece") == "piece":
                specificity = _wardrobe_specificity(str(item.get("value") or ""), "piece")
                if specificity.get("visual_ready") is False:
                    flags.append("generic")
                if _wardrobe_piece_has_multiple_independent_heads(str(item.get("value") or "")):
                    flags.append("compound")
            item["review_flags"] = flags
        return web.json_response({"ok": True, "items": rows})

    @_creative_library_route("post", "/wardrobe-items")
    async def solo_wardrobe_create_item(request):
        payload = await request.json()
        raw_values = payload.get("values") if isinstance(payload.get("values"), list) else [payload.get("value")]
        values = list(dict.fromkeys(_single_line_recipe_prompt(value) for value in raw_values if _single_line_recipe_prompt(value)))
        if not values:
            return web.json_response({"ok": False, "error": "Add at least one wardrobe value"}, status=400)
        item_type = str(payload.get("item_type") or "piece").strip().lower()
        category = _single_line_recipe_prompt(payload.get("category") or "Uncategorized") or "Uncategorized"
        subtype = _single_line_recipe_prompt(payload.get("subtype") or "")
        try:
            items = [get_catalog().upsert_wardrobe_item(item_type, value, category=category, subtype=subtype, manual=True) for value in values]
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, "item": items[0], "items": items, "added": len(items)})

    @_creative_library_route("patch", "/wardrobe-items/{wardrobe_id}")
    async def solo_wardrobe_update_item(request):
        wardrobe_id = str(request.match_info.get("wardrobe_id") or "")
        payload = await request.json()
        item_type = str(payload.get("item_type") or "piece").strip().lower()
        value = _single_line_recipe_prompt(payload.get("value") or "")
        category = _single_line_recipe_prompt(payload.get("category") or "Uncategorized") or "Uncategorized"
        subtype = _single_line_recipe_prompt(payload.get("subtype") or "")
        try:
            item = get_catalog().update_wardrobe_item(wardrobe_id, item_type, value, category=category, subtype=subtype)
        except ValueError as error:
            message = str(error)
            status = 404 if "no longer exists" in message else 400
            return web.json_response({"ok": False, "error": message}, status=status)
        item["kind"] = "piece"
        flags: list[str] = []
        if str(item.get("item_type") or "piece") == "piece":
            specificity = _wardrobe_specificity(str(item.get("value") or ""), "piece")
            if specificity.get("visual_ready") is False:
                flags.append("generic")
            if _wardrobe_piece_has_multiple_independent_heads(str(item.get("value") or "")):
                flags.append("compound")
        item["review_flags"] = flags
        return web.json_response({"ok": True, "item": item, "merged": bool(item.get("merged"))})

    @_creative_library_route("post", "/wardrobe-items/{wardrobe_id}/rating")
    async def solo_wardrobe_rating(request):
        wardrobe_id = str(request.match_info.get("wardrobe_id") or "")
        payload = await request.json()
        try:
            result = get_catalog().set_wardrobe_rating(wardrobe_id, payload.get("rating", 0))
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        return web.json_response({"ok": True, **result})

    @_creative_library_route("post", "/wardrobe-items/bulk")
    async def solo_wardrobe_bulk(request):
        payload = await request.json()
        operation = str(payload.get("operation") or "").strip().lower()
        ids = list(dict.fromkeys(
            str(value or "").strip() for value in (payload.get("wardrobe_ids") or payload.get("ids") or [])
            if str(value or "").strip()
        ))
        if not ids:
            return web.json_response({"ok": False, "error": "Select at least one Wardrobe item"}, status=400)
        if operation not in {"delete", "delete_previews"}:
            return web.json_response({"ok": False, "error": "Unsupported Wardrobe bulk operation"}, status=400)
        catalog = get_catalog()
        changed = 0
        missing = 0
        removed_previews = 0
        for wardrobe_id in ids:
            row = catalog.delete_wardrobe_item(wardrobe_id) if operation == "delete" else catalog.clear_wardrobe_preview(wardrobe_id)
            if row is None:
                missing += 1
                continue
            changed += 1
            preview_ref = str(row.get("preview_ref") or row.get("removed_preview_ref") or "")
            if preview_ref:
                (_component_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
                removed_previews += 1
        return web.json_response({
            "ok": True,
            "operation": operation,
            "changed": changed,
            "deleted": changed if operation == "delete" else 0,
            "previews_deleted": removed_previews if operation == "delete_previews" else 0,
            "missing": missing,
            "removed_previews": removed_previews,
        })

    @_creative_library_route("delete", "/wardrobe-items/{wardrobe_id}/preview")
    async def solo_wardrobe_delete_preview(request):
        wardrobe_id = str(request.match_info.get("wardrobe_id") or "")
        row = get_catalog().clear_wardrobe_preview(wardrobe_id)
        if row is None:
            return web.json_response({"ok": False, "error": "Wardrobe item was not found"}, status=404)
        preview_ref = str(row.get("removed_preview_ref") or "")
        if preview_ref:
            (_component_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
        return web.json_response({"ok": True, "cleared": True, "wardrobe_id": wardrobe_id})

    @_creative_library_route("delete", "/wardrobe-items/{wardrobe_id}")
    async def solo_wardrobe_delete_item(request):
        wardrobe_id = str(request.match_info.get("wardrobe_id") or "")
        row = get_catalog().delete_wardrobe_item(wardrobe_id)
        if row is None:
            return web.json_response({"ok": False, "error": "Wardrobe item was not found"}, status=404)
        preview_ref = str(row.get("preview_ref") or "")
        if preview_ref:
            (_component_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
        return web.json_response({"ok": True, "deleted": True, "wardrobe_id": wardrobe_id})

    @_creative_library_route("get", "/component-preview/{filename}")
    async def solo_recipe_component_preview(request):
        filename = str(request.match_info.get("filename", ""))
        if not filename or Path(filename).name != filename:
            raise web.HTTPNotFound()
        path = _component_preview_directory() / filename
        if not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    @_creative_library_route("delete", "/derived-values/{component_id}/preview")
    async def solo_recipe_component_preview_delete(request):
        component_id = str(request.match_info.get("component_id") or "")
        row = get_catalog().clear_recipe_component_preview(component_id)
        if row is None:
            return web.json_response({"ok": False, "error": "Outfit / Scene asset was not found"}, status=404)
        preview_ref = str(row.get("removed_preview_ref") or "")
        if preview_ref:
            (_component_preview_directory() / Path(preview_ref).name).unlink(missing_ok=True)
        return web.json_response({"ok": True, "cleared": True, "component_id": component_id})

    @_creative_library_route("post", "/derived-values/bulk/previews/delete")
    async def solo_recipe_component_previews_bulk_delete(request):
        try:
            payload = await request.json()
            component_ids = [str(value or "") for value in payload.get("component_ids") or []]
            rows = get_catalog().clear_recipe_component_previews(component_ids)
            deleted_files = 0
            for row in rows:
                preview_ref = str(row.get("removed_preview_ref") or "")
                if not preview_ref:
                    continue
                target = _component_preview_directory() / Path(preview_ref).name
                if target.is_file():
                    target.unlink(missing_ok=True); deleted_files += 1
            return web.json_response({"ok": True, "changed": len(rows), "previews_deleted": deleted_files})
        except (TypeError, ValueError, OSError) as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/derived-values/preview")
    async def solo_recipe_save_derived_preview(request):
        reader = await request.multipart()
        kind = ""
        value = ""
        item_type = "piece"
        category = "Uncategorized"
        subtype = ""
        raw = bytearray()
        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "kind":
                kind = (await field.text()).strip().lower()
            elif field.name == "value":
                value = _single_line_recipe_prompt(await field.text())
            elif field.name == "item_type":
                item_type = (await field.text()).strip().lower() or "piece"
            elif field.name == "category":
                category = _single_line_recipe_prompt(await field.text()) or "Uncategorized"
            elif field.name == "subtype":
                subtype = _single_line_recipe_prompt(await field.text())
            elif field.name == "file":
                while True:
                    chunk = await field.read_chunk(1024 * 1024)
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > 40 * 1024 * 1024:
                        return web.json_response({"ok": False, "error": "Catalog preview import is limited to 40 MB"}, status=413)
        if kind not in {"outfit", "scene", "piece"} or not value or not raw:
            return web.json_response({"ok": False, "error": "Catalog preview requires a kind, value, and image"}, status=400)
        try:
            with Image.open(BytesIO(bytes(raw))) as image:
                if kind == "piece":
                    if item_type not in {"piece", "set"}:
                        item_type = "piece"
                    filename = _save_wardrobe_preview(image.copy(), item_type, value)
                    component = get_catalog().set_wardrobe_preview(item_type, value, filename, "generated:catalog", category=category, subtype=subtype)
                else:
                    filename = _save_component_preview(image.copy(), kind, value)
                    component = get_catalog().set_recipe_component_preview(kind, value, filename, "generated:catalog")
            return web.json_response({"ok": True, "preview_ref": filename, "component": component})
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/save-with-preview")
    async def solo_recipe_save_with_preview(request):
        reader = await request.multipart()
        name = ""
        payload_text = ""
        raw = bytearray()
        filename = "preview.png"
        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "name":
                name = await field.text()
            elif field.name == "payload":
                payload_text = await field.text()
            elif field.name == "file":
                filename = str(field.filename or filename)
                while True:
                    chunk = await field.read_chunk(1024 * 1024)
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > 40 * 1024 * 1024:
                        return web.json_response({"ok": False, "error": "Preview thumbnail verification is limited to 40 MB"}, status=413)
        try:
            recipe = json.loads(payload_text or "{}")
        except json.JSONDecodeError:
            return web.json_response({"ok": False, "error": "Recipe payload was not valid JSON"}, status=400)
        if not isinstance(recipe, dict):
            return web.json_response({"ok": False, "error": "Recipe payload must be an object"}, status=400)
        recipe = _curate_prompt_catalog_recipe(recipe)
        recipe["tokens"] = _recipe_tokens(recipe)
        if not recipe.get("nodes"):
            return web.json_response({"ok": False, "error": "The current Studio recipe had no reusable prompt or generation values"}, status=400)

        preview_ref = ""
        preview_matched = False
        preview_reason = "No Preview image was available; saved from the current Studio node state."
        if raw:
            try:
                image_recipe, preview_image = _recipe_from_image_bytes(bytes(raw))
                recipe = _preview_authoritative_recipe(recipe, image_recipe)
                recipe["_sickollie_seed_source"] = "preview-image"
                preview_ref = _save_preview(preview_image, uuid.uuid4().hex)
                preview_matched = True
                preview_reason = "Recipe values and thumbnail were captured from the displayed Preview image metadata."
            except Exception as error:
                preview_reason = f"Could not read resolved metadata from {filename}: {error}"

        recipe_id = f"recipe:{uuid.uuid4().hex}"
        try:
            get_catalog().save_recipe(recipe_id, name, recipe, preview_ref)
        except Exception:
            if preview_ref:
                (_preview_directory() / preview_ref).unlink(missing_ok=True)
            raise
        get_catalog().set_last_recipe_import([recipe_id])
        _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
        _PROMPT_FILTER_METADATA_CACHE.clear()
        _safe_sync_recipe_prompt_logs()
        return web.json_response({
            "ok": True,
            "recipe_id": recipe_id,
            "preview_ref": preview_ref,
            "preview_matched": preview_matched,
            "preview_reason": preview_reason,
        })

    @_creative_library_route("post", "/recipes/last-import")
    async def solo_recipe_last_import(request):
        try:
            payload = await request.json()
            recipe_ids = payload.get("recipe_ids") if isinstance(payload, dict) else []
            ids = get_catalog().set_last_recipe_import(recipe_ids if isinstance(recipe_ids, list) else [])
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            return web.json_response({"ok": True, "recipe_ids": ids})
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)

    @_creative_library_route("post", "/import-metadata")
    async def solo_recipe_import_metadata(request):
        reader = await request.multipart()
        metadata_text = ""
        raw = bytearray()
        preview_filename = "metadata-preview.png"
        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "metadata_json":
                metadata_text = await field.text()
            elif field.name == "file":
                preview_filename = str(field.filename or preview_filename)
                while True:
                    chunk = await field.read_chunk(1024 * 1024)
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > 40 * 1024 * 1024:
                        return web.json_response({"ok": False, "error": "Metadata Core Recipe thumbnail is limited to 40 MB"}, status=413)
        try:
            normalized = json.loads(metadata_text or "{}")
        except json.JSONDecodeError:
            return web.json_response({"ok": False, "error": "Image Metadata Core payload was not valid JSON"}, status=400)
        if not isinstance(normalized, dict):
            return web.json_response({"ok": False, "error": "Image Metadata Core payload must be an object"}, status=400)

        resolved = normalized.get("resolved") if isinstance(normalized.get("resolved"), dict) else {}
        generation = normalized.get("generation") if isinstance(normalized.get("generation"), dict) else {}
        models = normalized.get("models") if isinstance(normalized.get("models"), dict) else {}
        source_prompt = str(normalized.get("source_prompt") or "").strip()
        final_prompt = str(normalized.get("final_prompt") or "").strip()
        if source_prompt and not resolved.get("source_prompt"):
            resolved = {**resolved, "source_prompt": source_prompt}
        if final_prompt and not resolved.get("final_prompt"):
            resolved = {**resolved, "final_prompt": final_prompt}
        structured = {
            "format": "Sick Ollie Image Metadata Core",
            "resolved": resolved,
            "generation": generation,
            "models": models,
        }

        recipe = {"schema": 4, "imported_from_image": True, "nodes": []}
        recipe = _structured_metadata_overlay(recipe, structured)
        image_info = normalized.get("image") if isinstance(normalized.get("image"), dict) else {}
        try:
            image_size = (max(1, int(image_info.get("width") or generation.get("width") or 1)), max(1, int(image_info.get("height") or generation.get("height") or 1)))
        except Exception:
            image_size = (1, 1)
        recipe = _apply_resolved_dimensions(recipe, structured, image_size)
        recipe = _curate_prompt_catalog_recipe(recipe)
        if not recipe.get("nodes"):
            return web.json_response({"ok": False, "error": "This image did not contain enough reusable prompt or generation metadata to save as a Recipe"}, status=400)
        recipe["_sickollie_seed_source"] = "imported-image"
        recipe["metadata_sources"] = ["image-metadata-core"]
        recipe["tokens"] = _recipe_tokens(recipe)

        preview_ref = ""
        if raw:
            try:
                with Image.open(BytesIO(bytes(raw))) as image:
                    preview_ref = _save_preview(image.copy(), uuid.uuid4().hex)
            except Exception as error:
                return web.json_response({"ok": False, "error": f"Could not read the loaded image thumbnail: {error}"}, status=400)

        source_name = Path(str(normalized.get("source_file") or preview_filename or "Metadata Recipe")).stem or "Metadata Recipe"
        recipe_id = f"recipe:{uuid.uuid4().hex}"
        try:
            get_catalog().save_recipe(recipe_id, source_name, recipe, preview_ref)
        except Exception:
            if preview_ref:
                (_preview_directory() / preview_ref).unlink(missing_ok=True)
            raise
        get_catalog().set_last_recipe_import([recipe_id])
        _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
        _PROMPT_FILTER_METADATA_CACHE.clear()
        _safe_sync_recipe_prompt_logs()
        return web.json_response({
            "ok": True,
            "saved": True,
            "recipe_id": recipe_id,
            "name": source_name,
            "preview_ref": preview_ref,
            "tokens": recipe["tokens"],
        })

    @_creative_library_route("post", "/import-image")
    async def solo_recipe_import_image(request):
        reader = await request.multipart()
        field = await reader.next()
        if field is None or field.name != "file" or not field.filename:
            return web.json_response({"ok": False, "error": "Choose a PNG, JPG, or WEBP output image"}, status=400)
        raw = bytearray()
        while True:
            chunk = await field.read_chunk(1024 * 1024)
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > 40 * 1024 * 1024:
                return web.json_response({"ok": False, "error": "Image metadata import is limited to 40 MB"}, status=413)
        try:
            payload, preview_image = _recipe_from_image_bytes(bytes(raw))
            payload["_sickollie_seed_source"] = "imported-image"
            recipe_id = f"recipe:{uuid.uuid4().hex}"
            name = Path(field.filename).stem
            preview_ref = _save_preview(preview_image, uuid.uuid4().hex)
            try:
                get_catalog().save_recipe(recipe_id, name, payload, preview_ref)
            except Exception:
                (_preview_directory() / preview_ref).unlink(missing_ok=True)
                raise
            get_catalog().set_last_recipe_import([recipe_id])
            _PROMPT_SNAPSHOT_CACHE.update({"key": None, "value": None})
            _PROMPT_FILTER_METADATA_CACHE.clear()
            _safe_sync_recipe_prompt_logs()
            return web.json_response({"ok": True, "saved": True, "recipe_id": recipe_id, "name": name, "preview_ref": preview_ref, "tokens": payload["tokens"]})
        except Exception as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
