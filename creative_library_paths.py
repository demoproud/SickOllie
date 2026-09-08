from __future__ import annotations

"""Canonical filesystem contracts for the Sick Ollie Creative Library.

The public Library grew out of the older Recipe Library.  Keep migration names
here—at one compatibility boundary—so every live writer, reader, and UI surface
uses the same paths instead of re-implementing legacy detection independently.
"""

from pathlib import Path


LOG_ROOT_NAME = "SickOllieLogs"
CREATIVE_LIBRARY_LOG_FOLDER = "Creative Library"
LEGACY_RECIPE_LIBRARY_LOG_FOLDER = "Recipe Library"

CREATIVE_LIBRARY_PREVIEW_FOLDER = "creative_library_previews"
LEGACY_PREVIEW_FOLDERS = ("recipe_previews", "recipe_component_previews")
PREVIEW_SUFFIXES = {".webp", ".png", ".jpg", ".jpeg"}

SAVED_RECIPE_MASTER_FILE = "MASTER - Saved Recipe Prompts.txt"
SAVED_RECIPE_COLLECTION_FOLDER = "Saved Recipe Collections"
OUTFIT_MASTER_FILE = "MASTER - Outfit Looks.txt"
SCENE_MASTER_FILE = "MASTER - Scenes.txt"

LEGACY_SAVED_RECIPE_MASTER_FILE = "MASTER - All Recipe Prompts.txt"
LEGACY_COMPONENT_MASTER_FILES = {
    "outfit": "MASTER - Resolved Recipe Outfits.txt",
    "scene": "MASTER - Resolved Recipe Scenes.txt",
}


def canonical_log_reference(value: str, category: str = "") -> str:
    """Map one generated Recipe Library reference onto its Creative Library home."""
    clean = str(value or "").strip().replace("\\", "/")
    if not clean or clean == "[None]":
        return clean
    relative = Path(clean)
    if relative.is_absolute() or ".." in relative.parts or len(relative.parts) < 2:
        return clean
    inferred = {"prompts": "prompt", "outfits": "outfit", "scenes": "scene"}.get(relative.parts[0].casefold(), "")
    clean_category = str(category or inferred).strip().casefold()
    if clean_category not in {"prompt", "outfit", "scene"}:
        return clean
    parts = list(relative.parts)
    if parts[1].casefold() != LEGACY_RECIPE_LIBRARY_LOG_FOLDER.casefold():
        return relative.as_posix()
    parts[1] = CREATIVE_LIBRARY_LOG_FOLDER
    if clean_category == "prompt" and len(parts) >= 3:
        if parts[2].casefold() == LEGACY_SAVED_RECIPE_MASTER_FILE.casefold():
            parts[2] = SAVED_RECIPE_MASTER_FILE
        elif parts[2].casefold() == "collections":
            parts[2] = SAVED_RECIPE_COLLECTION_FOLDER
    elif clean_category in {"outfit", "scene"} and len(parts) >= 3:
        if parts[2].casefold() == LEGACY_COMPONENT_MASTER_FILES[clean_category].casefold():
            parts[2] = OUTFIT_MASTER_FILE if clean_category == "outfit" else SCENE_MASTER_FILE
    return Path(*parts).as_posix()


def creative_library_preview_directory(catalog_parent: Path | str) -> Path:
    """Return the one preview root, migrating both legacy stores without copying."""
    parent = Path(catalog_parent)
    destination = parent / CREATIVE_LIBRARY_PREVIEW_FOLDER
    destination.mkdir(parents=True, exist_ok=True)
    for legacy_name in LEGACY_PREVIEW_FOLDERS:
        legacy = parent / legacy_name
        if not legacy.is_dir() or legacy.resolve(strict=False) == destination.resolve(strict=False):
            continue
        for source in legacy.iterdir():
            if not source.is_file() or source.suffix.casefold() not in PREVIEW_SUFFIXES:
                continue
            target = destination / source.name
            if not target.exists():
                source.replace(target)
        try:
            legacy.rmdir()
        except OSError:
            # Unknown or conflicting files are deliberately preserved.  The
            # app only retires a legacy directory after every managed image moved.
            pass
    return destination


def retire_legacy_generated_logs(category_root: Path | str, category: str) -> dict[str, int | bool]:
    """Remove only known generated files from one obsolete Recipe Library root."""
    clean_category = str(category or "").strip().casefold()
    if clean_category not in {"prompt", "outfit", "scene"}:
        return {"removed_files": 0, "removed_folders": 0, "retired": False}
    legacy = Path(category_root) / LEGACY_RECIPE_LIBRARY_LOG_FOLDER
    if not legacy.is_dir():
        return {"removed_files": 0, "removed_folders": 0, "retired": False}
    masters = (
        {LEGACY_SAVED_RECIPE_MASTER_FILE}
        if clean_category == "prompt"
        else {LEGACY_COMPONENT_MASTER_FILES[clean_category]}
    )
    removed_files = 0
    removed_folders = 0
    for name in masters:
        target = legacy / name
        if target.is_file():
            target.unlink(missing_ok=True)
            removed_files += 1
    collection_root = legacy / "Collections"
    if collection_root.is_dir():
        for target in collection_root.glob("*.txt"):
            if target.is_file():
                target.unlink(missing_ok=True)
                removed_files += 1
        try:
            collection_root.rmdir()
            removed_folders += 1
        except OSError:
            pass
    try:
        legacy.rmdir()
        removed_folders += 1
    except OSError:
        pass
    return {"removed_files": removed_files, "removed_folders": removed_folders, "retired": not legacy.exists()}
