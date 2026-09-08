from __future__ import annotations

"""Small compatibility helpers for third-party image generation metadata.

The Studio has its own rich metadata schema, but image libraries often contain
outputs from SwarmUI/StableSwarmUI, A1111-style tools, or other generators that
store a compact JSON object under a generic ``parameters`` field.  This module
normalizes the common JSON shapes without making any assumptions about Studio
nodes or catalog state.
"""

import json
import re
from pathlib import Path
from typing import Any


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    text = value.strip()
    if not text or not text.startswith("{"):
        return {}
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _key_map(data: dict[str, Any]) -> dict[str, Any]:
    """Case/spacing-insensitive view over one metadata dictionary."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if normalized and normalized not in result:
            result[normalized] = value
    return result


def _pick(data: dict[str, Any], *aliases: str) -> Any:
    keys = _key_map(data)
    for alias in aliases:
        normalized = re.sub(r"[^a-z0-9]", "", alias.lower())
        if normalized in keys:
            return keys[normalized]
    return None


def _number(value: Any, integer: bool = False) -> Any:
    if value is None or value == "":
        return None
    if integer:
        try:
            # Keep large seeds exact. Most generators serialize them as integer
            # strings or JSON integers; only fall back through float for values
            # such as "42.0".
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _size_from_value(value: Any) -> tuple[int | None, int | None]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            return int(value[0]), int(value[1])
        except (TypeError, ValueError):
            return None, None
    match = re.search(r"(\d+)\s*[xX×]\s*(\d+)", _text(value))
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def _model_entries(root: dict[str, Any]) -> list[dict[str, Any]]:
    raw = root.get("sui_models")
    if not isinstance(raw, list):
        raw = root.get("models") if isinstance(root.get("models"), list) else []
    return [item for item in raw if isinstance(item, dict)]


def _matching_model(entries: list[dict[str, Any]], param: str, name: str = "") -> dict[str, Any]:
    wanted_param = param.casefold()
    wanted_name = Path(name.replace("\\", "/")).stem.casefold() if name else ""
    for item in entries:
        if _text(item.get("param")).casefold() != wanted_param:
            continue
        item_name = _text(item.get("name"))
        if not wanted_name or Path(item_name.replace("\\", "/")).stem.casefold() == wanted_name:
            return item
    return {}


def parse_json_parameters(value: Any) -> dict[str, Any]:
    """Normalize a JSON-style generation ``parameters`` payload.

    Returns an empty dict for ordinary A1111/Civitai text so callers can retain
    their existing text parser as a fallback.
    """
    root = _json_object(value)
    if not root:
        return {}

    # SwarmUI/StableSwarmUI stores the real generation values here.  For other
    # JSON emitters, accept a few common nested names or the root object itself.
    candidates = [
        root.get("sui_image_params"),
        root.get("image_params"),
        root.get("generation"),
        root.get("parameters"),
        root,
    ]
    params = next((item for item in candidates if isinstance(item, dict) and item), {})
    if not params:
        return {}

    prompt = _text(_pick(params, "prompt", "positive_prompt", "positiveprompt", "positive"))
    negative = _text(_pick(params, "negative_prompt", "negativeprompt", "negative"))
    seed = _number(_pick(params, "seed", "seed_used", "noiseseed", "noise_seed"), integer=True)
    steps = _number(_pick(params, "steps"), integer=True)
    cfg = _number(_pick(params, "cfg", "cfgscale", "cfg_scale", "guidance", "guidance_scale"))
    sampler = _text(_pick(params, "sampler", "sampler_name"))
    scheduler = _text(_pick(params, "scheduler", "schedule", "schedule_type", "scheduletype"))
    width = _number(_pick(params, "width"), integer=True)
    height = _number(_pick(params, "height"), integer=True)
    if not width or not height:
        parsed_width, parsed_height = _size_from_value(_pick(params, "size", "resolution"))
        width = width or parsed_width
        height = height or parsed_height

    model = _text(_pick(params, "model", "model_name", "checkpoint", "ckpt_name", "diffusion_model", "unet_name"))
    model_hash = _text(_pick(params, "model_hash", "modelhash", "checkpoint_hash"))
    vae = _text(_pick(params, "vae", "vae_name"))
    vae_hash = _text(_pick(params, "vae_hash", "vaehash"))

    entries = _model_entries(root)
    if model:
        model_entry = _matching_model(entries, "model", model)
        if model_entry:
            model = _text(model_entry.get("name")) or model
            model_hash = _text(model_entry.get("hash")) or model_hash
    elif entries:
        model_entry = _matching_model(entries, "model")
        if model_entry:
            model = _text(model_entry.get("name"))
            model_hash = _text(model_entry.get("hash"))

    loras_raw = _pick(params, "loras", "lora_models", "loramodels")
    weights_raw = _pick(params, "loraweights", "lora_weights", "lorastrengths", "lora_strengths")
    if isinstance(loras_raw, str):
        loras_raw = [part.strip() for part in loras_raw.split(",") if part.strip()]
    if isinstance(weights_raw, str):
        weights_raw = [part.strip() for part in weights_raw.split(",") if part.strip()]
    lora_names = list(loras_raw) if isinstance(loras_raw, (list, tuple)) else []
    lora_weights = list(weights_raw) if isinstance(weights_raw, (list, tuple)) else []
    loras: list[dict[str, Any]] = []
    for index, raw_name in enumerate(lora_names):
        name = _text(raw_name)
        if not name:
            continue
        weight = _number(lora_weights[index] if index < len(lora_weights) else 1.0)
        model_entry = _matching_model(entries, "loras", name)
        file_name = _text(model_entry.get("name")) or name
        loras.append({
            "name": Path(file_name.replace("\\", "/")).stem,
            "file": file_name,
            "strength": 1.0 if weight in (None, "") else weight,
            "hash": _text(model_entry.get("hash")),
        })

    # Some JSON generators store LoRAs as objects instead of parallel arrays.
    if not loras and isinstance(loras_raw, list):
        for item in loras_raw:
            if not isinstance(item, dict):
                continue
            file_name = _text(_pick(item, "file", "name", "lora", "model"))
            if not file_name:
                continue
            loras.append({
                "name": Path(file_name.replace("\\", "/")).stem,
                "file": file_name,
                "strength": _number(_pick(item, "strength", "weight", "model_strength")) or 1.0,
                "hash": _text(_pick(item, "hash", "model_hash")),
            })

    # Requiring at least one recognizably generative field prevents unrelated
    # JSON comments from being mistaken for image-generation metadata.
    if not any((prompt, negative, seed is not None, steps is not None, model, width, height, loras)):
        return {}

    result: dict[str, Any] = {"format": "json-parameters"}
    if prompt:
        result["prompt"] = prompt
    if negative:
        result["negative_prompt"] = negative
    if seed is not None:
        result["seed_value"] = seed
    if steps is not None:
        result["steps"] = steps
    if cfg is not None:
        result["cfg"] = cfg
    if sampler:
        result["sampler_name"] = sampler
    if scheduler:
        result["scheduler"] = scheduler
    if width:
        result["custom_width"] = int(width)
    if height:
        result["custom_height"] = int(height)
    if width and height:
        result["resolution_mode"] = "custom"
    if model:
        result["diffusion_model"] = model
    if model_hash:
        result["diffusion_model_hash"] = model_hash
    if vae:
        result["vae_name"] = vae
    if vae_hash:
        result["vae_hash"] = vae_hash
    if loras:
        result["loras"] = loras
    return result


def generic_top_level_metadata(info: dict[str, Any]) -> dict[str, Any]:
    """Normalize loose top-level prompt/seed/model fields used by image tools."""
    if not isinstance(info, dict):
        return {}
    keys = _key_map(info)

    def pick(*aliases: str) -> Any:
        for alias in aliases:
            normalized = re.sub(r"[^a-z0-9]", "", alias.lower())
            if normalized in keys:
                return keys[normalized]
        return None

    result: dict[str, Any] = {}
    prompt = _text(pick("Positive prompt", "positive_prompt", "positiveprompt"))
    negative = _text(pick("Negative prompt", "negative_prompt", "negativeprompt"))
    seed = _number(pick("Seed", "seed_used"), integer=True)
    steps = _number(pick("Steps"), integer=True)
    cfg = _number(pick("CFG scale", "cfg", "cfgscale"))
    sampler = _text(pick("Sampler", "sampler_name"))
    scheduler = _text(pick("Scheduler", "Schedule type", "schedule_type"))
    model = _text(pick("Model", "model_name", "diffusion_model"))
    model_hash = _text(pick("Model hash", "model_hash"))
    vae = _text(pick("VAE", "vae_name"))
    vae_hash = _text(pick("VAE hash", "vae_hash"))
    width, height = _size_from_value(pick("Size", "resolution"))

    if prompt:
        result["prompt"] = prompt
    if negative:
        result["negative_prompt"] = negative
    if seed is not None:
        result["seed_value"] = seed
    if steps is not None:
        result["steps"] = steps
    if cfg is not None:
        result["cfg"] = cfg
    if sampler:
        result["sampler_name"] = sampler
    if scheduler:
        result["scheduler"] = scheduler
    if model:
        result["diffusion_model"] = model
    if model_hash:
        result["diffusion_model_hash"] = model_hash
    if vae:
        result["vae_name"] = vae
    if vae_hash:
        result["vae_hash"] = vae_hash
    if width and height:
        result.update({"custom_width": width, "custom_height": height, "resolution_mode": "custom"})
    return result
