from __future__ import annotations

"""Durable, local catalog shared by Sick Ollie Studio tools.

The catalog is intentionally an index, never a second LoRA library: files stay
where the user put them and the SQLite data can be rebuilt from paths/hashes.
It supplies stable identity, history, trigger choices, tokens, and review
state to later Studio, Review, and Recipe surfaces.
"""

import json
import os
import sqlite3
import threading
import hashlib
import uuid
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse


SCHEMA_VERSION = 28
_LOCK = threading.RLock()
RECIPE_COLLECTION_COLORS = ("#ff4ab8", "#35d7ff", "#f6e65a", "#6ee7a2", "#b89aff", "#ff9b5f")

_CREATIVE_LIBRARY_PLACEHOLDERS = (
    "NAME", "OUTFIT", "OUTFIT_A", "OUTFIT_B", "OUTFIT_C", "BRAND", "ITEM", "SCENE",
    "LOCATION", "RARE_EVENT", "LIGHT_SOURCE", "ANALOG_CAPTURE_STYLE", "PRACTICAL_OUTER_LAYER",
    "SMALL_STYLING_DETAILS", "NATURAL_SURFACE", "TRIGGER",
)
_CREATIVE_LIBRARY_PLACEHOLDER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(
        re.escape(token) for token in sorted(_CREATIVE_LIBRARY_PLACEHOLDERS, key=len, reverse=True)
    ) + r")(?![A-Za-z0-9_]|\s*:)",
)


def _creative_prompt_signature(value: Any) -> str:
    present = {str(token).upper() for token in _CREATIVE_LIBRARY_PLACEHOLDER_PATTERN.findall(str(value or ""))}
    if "OUTFIT_A" in present:
        present.discard("OUTFIT_A")
        present.add("OUTFIT")
    order = tuple(dict.fromkeys("OUTFIT" if token == "OUTFIT_A" else token for token in _CREATIVE_LIBRARY_PLACEHOLDERS))
    return "+".join(token for token in order if token in present)

_SUPPORTED_CIVITAI_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _supported_remote_images(remote: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in remote.get("images") or []:
        url = str(item or "").strip()
        if not url:
            continue
        try:
            parsed = urlparse(url)
        except ValueError:
            continue
        if Path(parsed.path).suffix.casefold() not in _SUPPORTED_CIVITAI_IMAGE_SUFFIXES:
            continue
        values.append(url)
    return list(dict.fromkeys(values))



def repair_yearbook_prompt_snapshots(record: dict[str, Any]) -> tuple[str, str]:
    """Recover reusable Yearbook text from its canonical asset and captured components."""
    source = str(record.get("source_prompt_snapshot") or "")
    resolved = str(record.get("resolved_prompt_snapshot") or "")
    canonical = str(record.get("value") or "")
    if str(record.get("resolved_seed_source") or "") != "catalog-run" or not canonical or not source or source == canonical:
        return source, resolved
    # The run's manual prompt was temporary. Its asset value is the original
    # reusable source, including identity hooks and ordinary words.
    if not resolved:
        return canonical, ""
    metadata = record.get("preview_metadata")
    if not isinstance(metadata, dict):
        try:
            metadata = json.loads(str(record.get("preview_metadata_json") or "{}"))
        except (TypeError, ValueError):
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    components = {"OUTFIT": "outfit_a", "OUTFIT_A": "outfit_a", "OUTFIT_B": "outfit_b", "OUTFIT_C": "outfit_c", "SCENE": "scene"}
    missing = False
    def replace(match):
        nonlocal missing
        value = str(metadata.get(components[match.group(1)]) or "")
        if not value:
            missing = True
        return value or match.group(0)
    portable = re.sub(r"(?<![A-Za-z0-9_])(?:\{)?(OUTFIT(?:_[ABC])?|SCENE)(?:\})?(?![A-Za-z0-9_])", replace, canonical)
    # Do not invent component choices when older previews omitted metadata.
    return canonical, "" if missing or portable == canonical else portable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _wardrobe_alias_key(value: str) -> str:
    text = " ".join(str(value or "").split()).casefold().strip(" ,.;")
    text = re.sub(r"^(?:a|an|the)\s+", "", text)
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"[-_/]+", " ", text)
    text = re.sub(r"[^a-z0-9\s]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def default_catalog_path() -> Path:
    try:
        import folder_paths

        user_dir = getattr(folder_paths, "get_user_directory", lambda: "")()
    except Exception:
        user_dir = ""
    root = Path(user_dir) if user_dir else Path(__file__).resolve().parent / "data"
    return root / "SickOllie" / "solo_catalog.sqlite3"


class SoloCatalog:
    def __init__(self, database_path: str | os.PathLike[str] | None = None):
        self.path = Path(database_path or default_catalog_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with _LOCK, self._connection() as db:
            db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS assets (
                    asset_id TEXT PRIMARY KEY,
                    sha256 TEXT UNIQUE,
                    size INTEGER NOT NULL DEFAULT 0,
                    current_path TEXT NOT NULL,
                    model_name TEXT NOT NULL DEFAULT '',
                    civitai_model_id TEXT NOT NULL DEFAULT '',
                    civitai_version_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_paths (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
                    path TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT 'scan',
                    UNIQUE(asset_id, path)
                );
                CREATE TABLE IF NOT EXISTS trigger_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
                    raw_text TEXT NOT NULL,
                    clean_text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0,
                    flags_json TEXT NOT NULL DEFAULT '[]',
                    pinned INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(asset_id, raw_text, source)
                );
                CREATE TABLE IF NOT EXISTS trigger_family_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder_key TEXT NOT NULL,
                    family_key TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'user.family_override',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(folder_key, family_key)
                );
                CREATE TABLE IF NOT EXISTS token_registry (
                    token TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    color TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_reviews (
                    asset_id TEXT PRIMARY KEY REFERENCES assets(asset_id),
                    state TEXT NOT NULL DEFAULT 'untested',
                    rating INTEGER,
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_usage (
                    asset_id TEXT PRIMARY KEY REFERENCES assets(asset_id),
                    use_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT NOT NULL DEFAULT '',
                    last_output TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS asset_usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
                    used_at TEXT NOT NULL,
                    output_path TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS asset_usage_events_asset_time
                    ON asset_usage_events(asset_id, used_at DESC);
                CREATE TABLE IF NOT EXISTS asset_thumbnails (
                    asset_id TEXT PRIMARY KEY REFERENCES assets(asset_id),
                    filename TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    source_url TEXT NOT NULL DEFAULT '',
                    width INTEGER NOT NULL DEFAULT 0,
                    height INTEGER NOT NULL DEFAULT 0,
                    byte_size INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS asset_remote_metadata (
                    asset_id TEXT PRIMARY KEY REFERENCES assets(asset_id),
                    source TEXT NOT NULL DEFAULT '',
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    fetched_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS relocation_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
                    old_path TEXT NOT NULL,
                    new_path TEXT NOT NULL,
                    manifest_path TEXT NOT NULL DEFAULT '',
                    recorded_at TEXT NOT NULL,
                    UNIQUE(asset_id, old_path, new_path)
                );
                CREATE TABLE IF NOT EXISTS saved_filters (
                    name TEXT PRIMARY KEY,
                    query_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lora_collections (
                    collection_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    color TEXT NOT NULL DEFAULT '#b89aff',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lora_collection_memberships (
                    asset_id TEXT NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
                    collection_id TEXT NOT NULL REFERENCES lora_collections(collection_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(asset_id, collection_id)
                );
                CREATE INDEX IF NOT EXISTS lora_collection_memberships_collection_asset
                    ON lora_collection_memberships(collection_id, asset_id);
                CREATE TABLE IF NOT EXISTS recipes (
                    recipe_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    preview_ref TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recipe_collections (
                    collection_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    color TEXT NOT NULL DEFAULT '#ff4ab8',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recipe_collection_memberships (
                    recipe_id TEXT NOT NULL REFERENCES recipes(recipe_id) ON DELETE CASCADE,
                    collection_id TEXT NOT NULL REFERENCES recipe_collections(collection_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(recipe_id, collection_id)
                );
                CREATE INDEX IF NOT EXISTS recipe_collection_memberships_collection_recipe
                    ON recipe_collection_memberships(collection_id, recipe_id);
                CREATE TABLE IF NOT EXISTS prompt_collection_memberships (
                    prompt_id TEXT NOT NULL,
                    collection_id TEXT NOT NULL REFERENCES recipe_collections(collection_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(prompt_id, collection_id)
                );
                CREATE INDEX IF NOT EXISTS prompt_collection_memberships_collection_prompt
                    ON prompt_collection_memberships(collection_id, prompt_id);
                CREATE TABLE IF NOT EXISTS prompt_showcase_collections (
                    collection_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL CHECK(kind IN ('prompt','template')),
                    name TEXT NOT NULL COLLATE NOCASE,
                    color TEXT NOT NULL DEFAULT '#b89aff',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(kind, name)
                );
                CREATE INDEX IF NOT EXISTS prompt_showcase_collections_kind_name
                    ON prompt_showcase_collections(kind, name COLLATE NOCASE);
                CREATE TABLE IF NOT EXISTS prompt_showcase_memberships (
                    prompt_id TEXT NOT NULL,
                    collection_id TEXT NOT NULL REFERENCES prompt_showcase_collections(collection_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(prompt_id, collection_id)
                );
                CREATE INDEX IF NOT EXISTS prompt_showcase_memberships_collection_prompt
                    ON prompt_showcase_memberships(collection_id, prompt_id);
                CREATE TABLE IF NOT EXISTS creative_boards (
                    board_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS creative_boards_updated
                    ON creative_boards(updated_at DESC, board_id);
                CREATE TABLE IF NOT EXISTS prompt_assets (
                    prompt_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL DEFAULT 'prompt',
                    value TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    placeholder_signature TEXT NOT NULL DEFAULT '',
                    primary_parent TEXT NOT NULL DEFAULT 'Other',
                    primary_subcategory TEXT NOT NULL DEFAULT 'General',
                    facets_json TEXT NOT NULL DEFAULT '{}',
                    quality_score REAL NOT NULL DEFAULT 0,
                    exact_source_occurrences INTEGER NOT NULL DEFAULT 0,
                    near_cluster_id TEXT NOT NULL DEFAULT '',
                    preview_ref TEXT NOT NULL DEFAULT '',
                    preview_source TEXT NOT NULL DEFAULT '',
                    preview_updated_at TEXT NOT NULL DEFAULT '',
                    resolved_seed INTEGER NOT NULL DEFAULT -1,
                    resolved_seed_source TEXT NOT NULL DEFAULT '',
                    preview_metadata_json TEXT NOT NULL DEFAULT '{}',
                    is_custom INTEGER NOT NULL DEFAULT 0,
                    source_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS prompt_assets_source_count
                    ON prompt_assets(source_count DESC, prompt_id);
                CREATE TABLE IF NOT EXISTS prompt_reviews (
                    prompt_id TEXT PRIMARY KEY REFERENCES prompt_assets(prompt_id) ON DELETE CASCADE,
                    rating INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS prompt_reviews_rating
                    ON prompt_reviews(rating, prompt_id);
                CREATE TABLE IF NOT EXISTS prompt_overrides (
                    prompt_id TEXT PRIMARY KEY,
                    primary_parent TEXT NOT NULL DEFAULT '',
                    primary_subcategory TEXT NOT NULL DEFAULT '',
                    home_override INTEGER NOT NULL DEFAULT 0,
                    archived INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS prompt_overrides_archived
                    ON prompt_overrides(archived, updated_at DESC);
                CREATE TABLE IF NOT EXISTS prompt_sources (
                    prompt_id TEXT NOT NULL REFERENCES prompt_assets(prompt_id) ON DELETE CASCADE,
                    source_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL DEFAULT 0,
                    source_label TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(prompt_id, source_path, line_number)
                );
                CREATE INDEX IF NOT EXISTS prompt_sources_path_prompt
                    ON prompt_sources(source_path, prompt_id);
                CREATE TABLE IF NOT EXISTS prompt_index_files (
                    source_path TEXT PRIMARY KEY,
                    byte_size INTEGER NOT NULL DEFAULT 0,
                    modified_ns INTEGER NOT NULL DEFAULT 0,
                    line_count INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fragment_assets (
                    fragment_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    mined_role TEXT NOT NULL DEFAULT '',
                    role_override TEXT NOT NULL DEFAULT '',
                    value TEXT NOT NULL COLLATE NOCASE,
                    family_id TEXT NOT NULL DEFAULT '',
                    join_mode TEXT NOT NULL DEFAULT 'sentence',
                    preferred_position INTEGER NOT NULL DEFAULT 50,
                    placeholder_signature TEXT NOT NULL DEFAULT '',
                    confidence REAL NOT NULL DEFAULT 0,
                    review_state TEXT NOT NULL DEFAULT 'suggested',
                    rating INTEGER NOT NULL DEFAULT 0,
                    source_kind TEXT NOT NULL DEFAULT 'mined',
                    prompt_count INTEGER NOT NULL DEFAULT 0,
                    source_count INTEGER NOT NULL DEFAULT 0,
                    multiple_allowed INTEGER NOT NULL DEFAULT 1,
                    conflict_tags_json TEXT NOT NULL DEFAULT '[]',
                    manual INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(role, value)
                );
                CREATE INDEX IF NOT EXISTS fragment_assets_role_rank
                    ON fragment_assets(role, review_state, source_count DESC, prompt_count DESC, confidence DESC);
                CREATE INDEX IF NOT EXISTS fragment_assets_family
                    ON fragment_assets(family_id, role, fragment_id);
                CREATE TABLE IF NOT EXISTS fragment_prompt_memberships (
                    fragment_id TEXT NOT NULL REFERENCES fragment_assets(fragment_id) ON DELETE CASCADE,
                    prompt_id TEXT NOT NULL,
                    occurrence_count INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(fragment_id, prompt_id)
                );
                CREATE INDEX IF NOT EXISTS fragment_prompt_memberships_prompt
                    ON fragment_prompt_memberships(prompt_id, fragment_id);
                CREATE TABLE IF NOT EXISTS fragment_file_sources (
                    fragment_id TEXT NOT NULL REFERENCES fragment_assets(fragment_id) ON DELETE CASCADE,
                    source_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL DEFAULT 0,
                    source_type TEXT NOT NULL DEFAULT 'prompt-log',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(fragment_id, source_path, line_number, source_type)
                );
                CREATE INDEX IF NOT EXISTS fragment_file_sources_path
                    ON fragment_file_sources(source_path, fragment_id);
                CREATE TABLE IF NOT EXISTS recipe_components (
                    component_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    value TEXT NOT NULL COLLATE NOCASE,
                    manual INTEGER NOT NULL DEFAULT 0,
                    preview_ref TEXT NOT NULL DEFAULT '',
                    preview_source TEXT NOT NULL DEFAULT '',
                    preview_updated_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(kind, value)
                );
                CREATE INDEX IF NOT EXISTS recipe_components_kind_created
                    ON recipe_components(kind, created_at, component_id);
                CREATE TABLE IF NOT EXISTS component_reviews (
                    component_id TEXT PRIMARY KEY REFERENCES recipe_components(component_id) ON DELETE CASCADE,
                    rating INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS component_reviews_rating
                    ON component_reviews(rating, component_id);
                CREATE TABLE IF NOT EXISTS component_collections (
                    collection_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL COLLATE NOCASE,
                    parent_id TEXT NOT NULL DEFAULT '',
                    color TEXT NOT NULL DEFAULT '#ff4ab8',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(kind, name)
                );
                CREATE INDEX IF NOT EXISTS component_collections_kind_name
                    ON component_collections(kind, name);
                -- Do not create the parent_id index here. On an existing v3.3.16
                -- database the component_collections table already exists without
                -- parent_id, so referencing it before the ALTER TABLE migration
                -- below aborts initialization with "no such column: parent_id".
                CREATE TABLE IF NOT EXISTS component_collection_memberships (
                    component_id TEXT NOT NULL REFERENCES recipe_components(component_id) ON DELETE CASCADE,
                    collection_id TEXT NOT NULL REFERENCES component_collections(collection_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(component_id, collection_id)
                );
                CREATE INDEX IF NOT EXISTS component_collection_memberships_collection_component
                    ON component_collection_memberships(collection_id, component_id);
                CREATE TABLE IF NOT EXISTS component_tombstones (
                    component_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    value TEXT NOT NULL COLLATE NOCASE,
                    deleted_at TEXT NOT NULL,
                    UNIQUE(kind, value)
                );
                CREATE INDEX IF NOT EXISTS component_tombstones_kind_value
                    ON component_tombstones(kind, value);
                CREATE TABLE IF NOT EXISTS component_import_batches (
                    batch_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    file_count INTEGER NOT NULL DEFAULT 0,
                    new_count INTEGER NOT NULL DEFAULT 0,
                    matched_count INTEGER NOT NULL DEFAULT 0,
                    membership_count INTEGER NOT NULL DEFAULT 0,
                    source_paths_json TEXT NOT NULL DEFAULT '[]',
                    collection_mode TEXT NOT NULL DEFAULT 'none',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS component_import_batches_kind_time
                    ON component_import_batches(kind, created_at DESC);
                CREATE TABLE IF NOT EXISTS component_import_items (
                    batch_id TEXT NOT NULL REFERENCES component_import_batches(batch_id) ON DELETE CASCADE,
                    component_id TEXT NOT NULL,
                    created_component INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(batch_id, component_id)
                );
                CREATE INDEX IF NOT EXISTS component_import_items_component
                    ON component_import_items(component_id, batch_id);
                CREATE TABLE IF NOT EXISTS component_import_memberships (
                    batch_id TEXT NOT NULL REFERENCES component_import_batches(batch_id) ON DELETE CASCADE,
                    component_id TEXT NOT NULL,
                    collection_id TEXT NOT NULL,
                    PRIMARY KEY(batch_id, component_id, collection_id)
                );
                CREATE TABLE IF NOT EXISTS component_import_collections (
                    batch_id TEXT NOT NULL REFERENCES component_import_batches(batch_id) ON DELETE CASCADE,
                    collection_id TEXT NOT NULL,
                    created_collection INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(batch_id, collection_id)
                );
                CREATE TABLE IF NOT EXISTS wardrobe_items (
                    wardrobe_id TEXT PRIMARY KEY,
                    item_type TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'Uncategorized',
                    subtype TEXT NOT NULL DEFAULT '',
                    value TEXT NOT NULL COLLATE NOCASE,
                    manual INTEGER NOT NULL DEFAULT 1,
                    preview_ref TEXT NOT NULL DEFAULT '',
                    preview_source TEXT NOT NULL DEFAULT '',
                    preview_updated_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(item_type, value)
                );
                CREATE INDEX IF NOT EXISTS wardrobe_items_category_subtype
                    ON wardrobe_items(item_type, category, subtype, value);
                CREATE INDEX IF NOT EXISTS wardrobe_items_created
                    ON wardrobe_items(item_type, created_at, wardrobe_id);
                CREATE TABLE IF NOT EXISTS wardrobe_reviews (
                    wardrobe_id TEXT PRIMARY KEY REFERENCES wardrobe_items(wardrobe_id) ON DELETE CASCADE,
                    rating INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS wardrobe_reviews_rating
                    ON wardrobe_reviews(rating, wardrobe_id);
                CREATE TABLE IF NOT EXISTS library_collections (
                    collection_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    name TEXT NOT NULL COLLATE NOCASE,
                    color TEXT NOT NULL DEFAULT '#b89aff',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(kind, name)
                );
                CREATE INDEX IF NOT EXISTS library_collections_kind_name
                    ON library_collections(kind, name);
                CREATE TABLE IF NOT EXISTS library_collection_memberships (
                    collection_id TEXT NOT NULL REFERENCES library_collections(collection_id) ON DELETE CASCADE,
                    asset_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(collection_id, asset_id)
                );
                CREATE INDEX IF NOT EXISTS library_collection_memberships_asset
                    ON library_collection_memberships(asset_id, collection_id);
                CREATE TABLE IF NOT EXISTS wardrobe_sources (
                    source_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    label TEXT NOT NULL DEFAULT '',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source_type, source_key)
                );
                CREATE INDEX IF NOT EXISTS wardrobe_sources_type_key
                    ON wardrobe_sources(source_type, source_key);
                CREATE TABLE IF NOT EXISTS wardrobe_item_sources (
                    wardrobe_id TEXT NOT NULL REFERENCES wardrobe_items(wardrobe_id) ON DELETE CASCADE,
                    source_id TEXT NOT NULL REFERENCES wardrobe_sources(source_id) ON DELETE CASCADE,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(wardrobe_id, source_id)
                );
                CREATE INDEX IF NOT EXISTS wardrobe_item_sources_source
                    ON wardrobe_item_sources(source_id, wardrobe_id);
                CREATE TABLE IF NOT EXISTS wardrobe_look_parts (
                    look_component_id TEXT NOT NULL REFERENCES recipe_components(component_id) ON DELETE CASCADE,
                    wardrobe_id TEXT NOT NULL REFERENCES wardrobe_items(wardrobe_id) ON DELETE CASCADE,
                    position INTEGER NOT NULL DEFAULT 0,
                    relation TEXT NOT NULL DEFAULT '',
                    source_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(look_component_id, wardrobe_id, position)
                );
                CREATE INDEX IF NOT EXISTS wardrobe_look_parts_look
                    ON wardrobe_look_parts(look_component_id, position);
                CREATE INDEX IF NOT EXISTS wardrobe_look_parts_item
                    ON wardrobe_look_parts(wardrobe_id, look_component_id);
                CREATE TABLE IF NOT EXISTS wardrobe_migration_state (
                    look_component_id TEXT PRIMARY KEY REFERENCES recipe_components(component_id) ON DELETE CASCADE,
                    parser_version TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'unreviewed',
                    confidence REAL NOT NULL DEFAULT 0,
                    proposal_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS wardrobe_migration_status
                    ON wardrobe_migration_state(status, confidence DESC, look_component_id);
                CREATE TABLE IF NOT EXISTS wardrobe_packs (
                    pack_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    creator TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    manifest_json TEXT NOT NULL DEFAULT '{}',
                    installed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wardrobe_pack_looks (
                    pack_id TEXT NOT NULL REFERENCES wardrobe_packs(pack_id) ON DELETE CASCADE,
                    component_id TEXT NOT NULL REFERENCES recipe_components(component_id) ON DELETE CASCADE,
                    created_component INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(pack_id, component_id)
                );
                CREATE TABLE IF NOT EXISTS creative_library_packs (
                    pack_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    creator TEXT NOT NULL DEFAULT '',
                    version TEXT NOT NULL DEFAULT '',
                    export_mode TEXT NOT NULL DEFAULT 'starter',
                    description TEXT NOT NULL DEFAULT '',
                    manifest_json TEXT NOT NULL DEFAULT '{}',
                    installed_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS creative_library_pack_component_memberships (
                    pack_id TEXT NOT NULL REFERENCES creative_library_packs(pack_id) ON DELETE CASCADE,
                    component_id TEXT NOT NULL REFERENCES recipe_components(component_id) ON DELETE CASCADE,
                    collection_id TEXT NOT NULL REFERENCES component_collections(collection_id) ON DELETE CASCADE,
                    PRIMARY KEY(pack_id, component_id, collection_id)
                );
                CREATE INDEX IF NOT EXISTS creative_library_pack_component_memberships_component
                    ON creative_library_pack_component_memberships(component_id, collection_id, pack_id);
                """
            )
            prompt_columns = {str(row[1]) for row in db.execute("PRAGMA table_info(prompt_assets)")}
            prompt_migrations = {
                "kind": "TEXT NOT NULL DEFAULT 'prompt'",
                "primary_parent": "TEXT NOT NULL DEFAULT 'Other'",
                "primary_subcategory": "TEXT NOT NULL DEFAULT 'General'",
                "facets_json": "TEXT NOT NULL DEFAULT '{}'",
                "quality_score": "REAL NOT NULL DEFAULT 0",
                "exact_source_occurrences": "INTEGER NOT NULL DEFAULT 0",
                "near_cluster_id": "TEXT NOT NULL DEFAULT ''",
                "preview_ref": "TEXT NOT NULL DEFAULT ''",
                "preview_source": "TEXT NOT NULL DEFAULT ''",
                "preview_updated_at": "TEXT NOT NULL DEFAULT ''",
                "resolved_seed": "INTEGER NOT NULL DEFAULT -1",
                "resolved_seed_source": "TEXT NOT NULL DEFAULT ''",
                "source_prompt_snapshot": "TEXT NOT NULL DEFAULT ''",
                "resolved_prompt_snapshot": "TEXT NOT NULL DEFAULT ''",
                "preview_metadata_json": "TEXT NOT NULL DEFAULT '{}'",
                "is_custom": "INTEGER NOT NULL DEFAULT 0",
            }
            for column, declaration in prompt_migrations.items():
                if column not in prompt_columns:
                    db.execute(f"ALTER TABLE prompt_assets ADD COLUMN {column} {declaration}")
            override_columns = {str(row[1]) for row in db.execute("PRAGMA table_info(prompt_overrides)")}
            if "home_override" not in override_columns:
                db.execute("ALTER TABLE prompt_overrides ADD COLUMN home_override INTEGER NOT NULL DEFAULT 0")
                db.execute(
                    "UPDATE prompt_overrides SET home_override=1 WHERE primary_parent<>'' OR primary_subcategory<>''"
                )
            showcase_split = db.execute(
                "SELECT value FROM schema_meta WHERE key='prompt_showcase_split_v1'"
            ).fetchone()
            if showcase_split is None:
                legacy_folders = db.execute(
                    """SELECT c.collection_id, c.name, c.color, c.created_at, c.updated_at
                    FROM recipe_collections c
                    WHERE EXISTS (
                        SELECT 1 FROM prompt_collection_memberships m
                        WHERE m.collection_id=c.collection_id
                    )
                    ORDER BY c.created_at, c.collection_id"""
                ).fetchall()
                for folder in legacy_folders:
                    legacy_id = str(folder["collection_id"])
                    suffix = hashlib.sha1(legacy_id.encode("utf-8")).hexdigest()[:24]
                    legacy_members = db.execute(
                        """SELECT m.prompt_id, m.created_at, p.kind AS asset_kind
                        FROM prompt_collection_memberships m
                        LEFT JOIN prompt_assets p ON p.prompt_id=m.prompt_id
                        WHERE m.collection_id=?""",
                        (legacy_id,),
                    ).fetchall()
                    for kind in ("prompt", "template"):
                        collection_id = f"prompt-showcase:{kind}:{suffix}"
                        db.execute(
                            """INSERT OR IGNORE INTO prompt_showcase_collections(
                            collection_id, kind, name, color, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                collection_id, kind, str(folder["name"]), str(folder["color"]),
                                str(folder["created_at"]), str(folder["updated_at"]),
                            ),
                        )
                        db.executemany(
                            """INSERT OR IGNORE INTO prompt_showcase_memberships(
                            prompt_id, collection_id, created_at
                            ) VALUES (?, ?, ?)""",
                            [
                                (str(member["prompt_id"]), collection_id, str(member["created_at"]))
                                for member in legacy_members
                                if (
                                    str(member["asset_kind"] or "") == kind
                                    or (
                                        not str(member["asset_kind"] or "")
                                        and (("template" in str(member["prompt_id"]).casefold()) == (kind == "template"))
                                    )
                                )
                            ],
                        )
                db.execute(
                    "INSERT INTO schema_meta(key, value) VALUES('prompt_showcase_split_v1', '1')"
                )
            placeholder_split = db.execute(
                "SELECT value FROM schema_meta WHERE key='prompt_placeholder_tabs_v2'"
            ).fetchone()
            if placeholder_split is None:
                reclassified = False
                rows = db.execute(
                    "SELECT prompt_id, kind, value, placeholder_signature FROM prompt_assets"
                ).fetchall()
                for row in rows:
                    prompt_id = str(row["prompt_id"])
                    old_kind = "template" if str(row["kind"] or "").casefold() == "template" else "prompt"
                    signature = _creative_prompt_signature(row["value"])
                    new_kind = "template" if signature else "prompt"
                    if old_kind != new_kind:
                        memberships = db.execute(
                            """SELECT c.collection_id, c.name, c.color, c.created_at, c.updated_at
                            FROM prompt_showcase_memberships m
                            JOIN prompt_showcase_collections c ON c.collection_id=m.collection_id
                            WHERE m.prompt_id=? AND c.kind=?""",
                            (prompt_id, old_kind),
                        ).fetchall()
                        for folder in memberships:
                            target = db.execute(
                                "SELECT collection_id FROM prompt_showcase_collections WHERE kind=? AND name=? COLLATE NOCASE",
                                (new_kind, str(folder["name"])),
                            ).fetchone()
                            if target is None:
                                suffix = hashlib.sha1(
                                    f"{new_kind}\0{str(folder['name']).casefold()}".encode("utf-8")
                                ).hexdigest()[:24]
                                target_id = f"prompt-showcase:{new_kind}:reclassified:{suffix}"
                                db.execute(
                                    """INSERT OR IGNORE INTO prompt_showcase_collections(
                                    collection_id, kind, name, color, created_at, updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                                    (
                                        target_id, new_kind, str(folder["name"]), str(folder["color"]),
                                        str(folder["created_at"]), str(folder["updated_at"]),
                                    ),
                                )
                            else:
                                target_id = str(target["collection_id"])
                            db.execute(
                                "INSERT OR IGNORE INTO prompt_showcase_memberships(prompt_id, collection_id, created_at) VALUES (?, ?, ?)",
                                (prompt_id, target_id, _now()),
                            )
                            db.execute(
                                "DELETE FROM prompt_showcase_memberships WHERE prompt_id=? AND collection_id=?",
                                (prompt_id, str(folder["collection_id"])),
                            )
                        reclassified = True
                    if old_kind != new_kind or str(row["placeholder_signature"] or "") != signature:
                        db.execute(
                            "UPDATE prompt_assets SET kind=?, placeholder_signature=?, updated_at=? WHERE prompt_id=?",
                            (new_kind, signature, _now(), prompt_id),
                        )
                        reclassified = True
                db.execute(
                    "INSERT INTO schema_meta(key, value) VALUES('prompt_placeholder_tabs_v2', '1')"
                )
                if reclassified:
                    db.execute(
                        """INSERT INTO schema_meta(key, value) VALUES('prompt_revision', '1')
                        ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
                    )
            component_columns = {str(row[1]) for row in db.execute("PRAGMA table_info(recipe_components)")}
            if "preview_updated_at" not in component_columns:
                db.execute("ALTER TABLE recipe_components ADD COLUMN preview_updated_at TEXT NOT NULL DEFAULT ''")
            collection_columns = {str(row[1]) for row in db.execute("PRAGMA table_info(component_collections)")}
            if "parent_id" not in collection_columns:
                db.execute("ALTER TABLE component_collections ADD COLUMN parent_id TEXT NOT NULL DEFAULT ''")
            db.execute(
                "CREATE INDEX IF NOT EXISTS component_collections_kind_parent ON component_collections(kind, parent_id, name)"
            )
            wardrobe_columns = {str(row[1]) for row in db.execute("PRAGMA table_info(wardrobe_items)")}
            if "preview_updated_at" not in wardrobe_columns:
                db.execute("ALTER TABLE wardrobe_items ADD COLUMN preview_updated_at TEXT NOT NULL DEFAULT ''")
            db.execute(
                "CREATE INDEX IF NOT EXISTS prompt_assets_home ON prompt_assets(kind, primary_parent, primary_subcategory, prompt_id)"
            )
            fragment_columns = {str(row[1]) for row in db.execute("PRAGMA table_info(fragment_assets)")}
            if "mined_role" not in fragment_columns:
                db.execute("ALTER TABLE fragment_assets ADD COLUMN mined_role TEXT NOT NULL DEFAULT ''")
            if "role_override" not in fragment_columns:
                db.execute("ALTER TABLE fragment_assets ADD COLUMN role_override TEXT NOT NULL DEFAULT ''")
            db.execute("UPDATE fragment_assets SET mined_role=role WHERE mined_role='' OR mined_role IS NULL")
            revision_tables = {
                "recipe_revision": ("recipes", "recipe_collections", "recipe_collection_memberships"),
                "component_revision": ("recipe_components", "component_reviews", "component_collections", "component_collection_memberships", "component_tombstones", "library_collections", "library_collection_memberships"),
            }
            for revision_key, tables in revision_tables.items():
                db.execute("INSERT OR IGNORE INTO schema_meta(key, value) VALUES(?, '0')", (revision_key,))
                for table in tables:
                    for event in ("INSERT", "UPDATE", "DELETE"):
                        trigger = f"solo_{revision_key}_{table}_{event.lower()}"
                        db.execute(
                            f"""CREATE TRIGGER IF NOT EXISTS {trigger} AFTER {event} ON {table}
                            BEGIN
                                INSERT INTO schema_meta(key, value) VALUES('{revision_key}', '1')
                                ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1;
                            END"""
                        )
            for revision_key in ("prompt_revision", "fragment_revision"):
                db.execute("INSERT OR IGNORE INTO schema_meta(key, value) VALUES(?, '0')", (revision_key,))
            db.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)", (str(SCHEMA_VERSION),))
        self.repair_yearbook_prompt_sources()
        self.ensure_default_tokens()

    def repair_yearbook_prompt_sources(self) -> int:
        """Repair legacy Yearbook snapshots without changing assets or previews."""
        with _LOCK, self._connection() as db:
            rows = db.execute("SELECT prompt_id,value,source_prompt_snapshot,resolved_prompt_snapshot,resolved_seed_source,preview_metadata_json FROM prompt_assets WHERE resolved_seed_source='catalog-run' AND source_prompt_snapshot<>'' AND source_prompt_snapshot<>value").fetchall()
            changed = 0
            for row in rows:
                source, resolved = repair_yearbook_prompt_snapshots(dict(row))
                if (source, resolved) == (row["source_prompt_snapshot"], row["resolved_prompt_snapshot"]):
                    continue
                db.execute("UPDATE prompt_assets SET source_prompt_snapshot=?,resolved_prompt_snapshot=? WHERE prompt_id=?", (source, resolved, row["prompt_id"]))
                changed += 1
            if changed:
                db.execute("INSERT INTO schema_meta(key,value) VALUES('prompt_revision','1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1")
        return changed

    def ensure_default_tokens(self) -> None:
        defaults = {
            "NAME": ("identity", "#f2df55", "Linked Loader clean name"),
            "OUTFIT": ("outfit", "#ff4dc4", "Primary outfit insertion"),
            "OUTFIT_A": ("outfit", "#ff4dc4", "Outfit A insertion"),
            "OUTFIT_B": ("outfit", "#f2df55", "Outfit B insertion"),
            "OUTFIT_C": ("outfit", "#28d8ff", "Outfit C insertion"),
            "SCENE": ("scene", "#63e6a4", "Scene insertion"),
            "ITEM": ("item", "#28d8ff", "Dynamic item / brand insertion"),
            "TRIGGER": ("trigger", "#a98cff", "Selected LoRA activation phrase"),
            "BRAND": ("item", "#28d8ff", "Brand or graphic text insertion"),
            "LOCATION": ("scene", "#63e6a4", "Portable location insertion"),
            "RARE_EVENT": ("concept", "#ff9b5f", "Rare event or story beat insertion"),
            "LIGHT_SOURCE": ("lighting", "#f2df55", "Lighting-source insertion"),
            "ANALOG_CAPTURE_STYLE": ("camera", "#35d7ff", "Analog capture treatment insertion"),
            "PRACTICAL_OUTER_LAYER": ("outfit", "#ff4dc4", "Practical outer-layer insertion"),
            "SMALL_STYLING_DETAILS": ("styling", "#ff9b5f", "Small styling-detail insertion"),
            "NATURAL_SURFACE": ("scene", "#63e6a4", "Natural surface insertion"),
        }
        now = _now()
        with _LOCK, self._connection() as db:
            for token, (kind, color, description) in defaults.items():
                db.execute(
                    "INSERT OR IGNORE INTO token_registry(token, kind, color, description, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (token, kind, color, description, now),
                )

    def upsert_asset(self, *, asset_id: str, path: str, sha256: str = "", size: int = 0, model_name: str = "", civitai_model_id: str = "", civitai_version_id: str = "", reason: str = "scan") -> None:
        now = _now()
        full_path = os.path.abspath(path)
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO assets(asset_id, sha256, size, current_path, model_name, civitai_model_id, civitai_version_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET sha256=COALESCE(excluded.sha256, assets.sha256), size=excluded.size, current_path=excluded.current_path,
                    model_name=excluded.model_name,
                    civitai_model_id=CASE WHEN excluded.civitai_model_id<>'' THEN excluded.civitai_model_id ELSE assets.civitai_model_id END,
                    civitai_version_id=CASE WHEN excluded.civitai_version_id<>'' THEN excluded.civitai_version_id ELSE assets.civitai_version_id END,
                    updated_at=excluded.updated_at""",
                (asset_id, sha256 or None, int(size or 0), full_path, model_name, civitai_model_id, civitai_version_id, now, now),
            )
            db.execute("INSERT OR REPLACE INTO asset_paths(asset_id, path, seen_at, reason) VALUES (?, ?, ?, ?)", (asset_id, full_path, now, reason))

    @staticmethod
    def path_asset_id(path: str | os.PathLike[str]) -> str:
        return "path:" + hashlib.sha1(os.path.abspath(os.fspath(path)).encode("utf-8")).hexdigest()

    def ensure_path_asset(self, path: str | os.PathLike[str], reason: str = "runtime") -> str:
        full_path = os.path.abspath(os.fspath(path))
        asset_id = self.path_asset_id(full_path)
        try:
            size = os.path.getsize(full_path)
        except OSError:
            size = 0
        self.upsert_asset(asset_id=asset_id, path=full_path, size=size, model_name=Path(full_path).stem, reason=reason)
        return asset_id

    def asset_id_for_path(self, path: str | os.PathLike[str]) -> str | None:
        """Return the existing catalog asset for a model path without creating one."""
        full_path = os.path.abspath(os.fspath(path))
        with _LOCK, self._connection() as db:
            row = db.execute(
                """SELECT asset_id FROM assets WHERE current_path=?
                ORDER BY CASE WHEN asset_id LIKE 'sha256:%' THEN 0 ELSE 1 END, updated_at DESC LIMIT 1""",
                (full_path,),
            ).fetchone()
            if row:
                return str(row[0])
            row = db.execute(
                """SELECT a.asset_id FROM assets a JOIN asset_paths p ON p.asset_id=a.asset_id
                WHERE p.path=?
                ORDER BY CASE WHEN a.asset_id LIKE 'sha256:%' THEN 0 ELSE 1 END, p.seen_at DESC LIMIT 1""",
                (full_path,),
            ).fetchone()
            return str(row[0]) if row else None

    def pinned_trigger(self, asset_id: str) -> dict[str, Any] | None:
        with _LOCK, self._connection() as db:
            row = db.execute(
                """SELECT raw_text, clean_text, source, confidence, flags_json, pinned
                FROM trigger_candidates WHERE asset_id=? AND pinned=1
                ORDER BY updated_at DESC LIMIT 1""",
                (str(asset_id),),
            ).fetchone()
        if not row:
            return None
        value = dict(row)
        value["flags"] = json.loads(value.pop("flags_json") or "[]")
        return value

    def clear_pinned_trigger(self, asset_id: str) -> None:
        with _LOCK, self._connection() as db:
            db.execute("DELETE FROM trigger_candidates WHERE asset_id=? AND pinned=1", (str(asset_id),))

    def trigger_family_override(self, folder_key: str, family_key: str) -> dict[str, Any] | None:
        with _LOCK, self._connection() as db:
            row = db.execute(
                """SELECT folder_key, family_key, raw_text, source, created_at, updated_at
                FROM trigger_family_overrides
                WHERE folder_key=? AND family_key=?
                LIMIT 1""",
                (str(folder_key or "").casefold(), str(family_key or "").casefold()),
            ).fetchone()
        return dict(row) if row else None

    def pin_trigger_family(
        self,
        folder_key: str,
        family_key: str,
        raw_text: str,
        source: str = "user.family_override",
    ) -> None:
        folder = str(folder_key or "").casefold()
        family = str(family_key or "").casefold()
        raw = str(raw_text or "").strip()
        if not family:
            raise ValueError("Trigger family key cannot be empty")
        if not raw:
            raise ValueError("Trigger family text cannot be empty")
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO trigger_family_overrides(
                    folder_key, family_key, raw_text, source, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(folder_key, family_key) DO UPDATE SET
                    raw_text=excluded.raw_text,
                    source=excluded.source,
                    updated_at=excluded.updated_at""",
                (folder, family, raw, str(source or "user.family_override"), now, now),
            )

    def clear_trigger_family(self, folder_key: str, family_key: str) -> bool:
        with _LOCK, self._connection() as db:
            cursor = db.execute(
                "DELETE FROM trigger_family_overrides WHERE folder_key=? AND family_key=?",
                (str(folder_key or "").casefold(), str(family_key or "").casefold()),
            )
            return bool(cursor.rowcount)

    def record_usage(self, path: str | os.PathLike[str], last_output: str = "") -> dict[str, Any]:
        """Record durable tested history without changing the user's rating.

        Review state and tested history are deliberately independent.  A run
        proves that an asset was tested; it must not silently turn that asset
        into a green Keep rating or erase a Retest/Favorite/Reject choice.
        """
        asset_id = self.ensure_path_asset(path, "completed generation")
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO asset_usage(asset_id, use_count, last_used_at, last_output) VALUES (?, 1, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET use_count=asset_usage.use_count+1,
                last_used_at=excluded.last_used_at, last_output=excluded.last_output""",
                (asset_id, now, str(last_output or "")),
            )
            db.execute(
                "INSERT INTO asset_usage_events(asset_id, used_at, output_path) VALUES (?, ?, ?)",
                (asset_id, now, str(last_output or "")),
            )
        return {"asset_id": asset_id, "tested": True, "last_used_at": now}

    def record_relocation(self, asset_id: str, old_path: str, new_path: str, manifest_path: str = "") -> None:
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute("INSERT OR IGNORE INTO relocation_ledger(asset_id, old_path, new_path, manifest_path, recorded_at) VALUES (?, ?, ?, ?, ?)", (asset_id, os.path.abspath(old_path), os.path.abspath(new_path), manifest_path, now))
            db.execute("UPDATE assets SET current_path=?, updated_at=? WHERE asset_id=?", (os.path.abspath(new_path), now, asset_id))
            db.execute("INSERT OR REPLACE INTO asset_paths(asset_id, path, seen_at, reason) VALUES (?, ?, ?, 'relocation')", (asset_id, os.path.abspath(new_path), now))

    def replace_trigger_candidates(self, asset_id: str, candidates: list[dict[str, Any]]) -> None:
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute("DELETE FROM trigger_candidates WHERE asset_id=? AND pinned=0", (asset_id,))
            for item in candidates:
                raw = str(item.get("raw", "")).strip()
                if not raw:
                    continue
                db.execute(
                    """INSERT INTO trigger_candidates(asset_id, raw_text, clean_text, source, confidence, flags_json, pinned, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                    ON CONFLICT(asset_id, raw_text, source) DO UPDATE SET clean_text=excluded.clean_text, confidence=excluded.confidence, flags_json=excluded.flags_json, updated_at=excluded.updated_at""",
                    (asset_id, raw, str(item.get("clean", raw)), str(item.get("source", "")), float(item.get("confidence", 0)), json.dumps(item.get("flags", [])), now, now),
                )

    def pin_trigger(self, asset_id: str, raw_text: str, source: str = "user.pinned") -> None:
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute("UPDATE trigger_candidates SET pinned=0 WHERE asset_id=?", (asset_id,))
            db.execute(
                "INSERT OR REPLACE INTO trigger_candidates(asset_id, raw_text, clean_text, source, confidence, flags_json, pinned, created_at, updated_at) VALUES (?, ?, ?, ?, 1, '[]', 1, ?, ?)",
                (asset_id, raw_text, raw_text, source, now, now),
            )

    def set_review(self, asset_id: str, state: str, rating: int | None = None, note: str = "") -> None:
        normalized = str(state or "none").strip().lower()
        if normalized not in {"none", "untested", "generated", "unreviewed", "rated", "keep", "favorite", "reject", "retest"}:
            raise ValueError("Unknown review state")
        with _LOCK, self._connection() as db:
            if normalized in {"none", "untested", "generated", "unreviewed"}:
                db.execute("DELETE FROM asset_reviews WHERE asset_id=?", (asset_id,))
                return
            implied_rating = 4 if normalized == "favorite" else 3 if normalized == "keep" else rating
            db.execute(
                "INSERT OR REPLACE INTO asset_reviews(asset_id, state, rating, note, updated_at) VALUES (?, ?, ?, ?, ?)",
                (asset_id, normalized, implied_rating, note, _now()),
            )

    def reset_status(self, asset_id: str, *, include_testing: bool = False) -> None:
        """Clear deliberate status, optionally erasing tested/use history too."""
        with _LOCK, self._connection() as db:
            db.execute("DELETE FROM asset_reviews WHERE asset_id=?", (asset_id,))
            if include_testing:
                db.execute("DELETE FROM asset_usage WHERE asset_id=?", (asset_id,))
                db.execute("DELETE FROM asset_usage_events WHERE asset_id=?", (asset_id,))

    @staticmethod
    def _clean_asset_ids(asset_ids: list[str] | tuple[str, ...] | set[str]) -> list[str]:
        return list(dict.fromkeys(str(asset_id or "").strip() for asset_id in asset_ids if str(asset_id or "").strip()))

    def clear_thumbnails(self, asset_ids: list[str] | tuple[str, ...] | set[str]) -> list[dict[str, Any]]:
        """Remove thumbnail records for selected assets and return the removed rows.

        The caller owns deletion of the corresponding cache files. Keeping file
        mutation outside the catalog makes this method safe for tests and other
        catalog consumers.
        """
        ids = self._clean_asset_ids(asset_ids)
        if not ids:
            return []
        with _LOCK, self._connection() as db:
            removed: list[dict[str, Any]] = []
            for asset_id in ids:
                row = db.execute("SELECT * FROM asset_thumbnails WHERE asset_id=?", (asset_id,)).fetchone()
                if row:
                    removed.append(dict(row))
            db.executemany("DELETE FROM asset_thumbnails WHERE asset_id=?", [(asset_id,) for asset_id in ids])
        return removed

    def purge_assets(self, asset_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, Any]:
        """Remove selected LoRA catalog records without touching model files.

        Recipes, saved filters, and the shared token registry intentionally live
        outside the purge boundary. This is the safe equivalent of rebuilding a
        portion of the LoRA Library rather than deleting the shared SQLite file.
        """
        ids = self._clean_asset_ids(asset_ids)
        if not ids:
            return {"purged": 0, "thumbnails": []}
        child_tables = (
            "asset_paths", "trigger_candidates", "asset_reviews", "asset_usage",
            "asset_usage_events", "asset_thumbnails", "asset_remote_metadata",
            "relocation_ledger", "lora_collection_memberships",
        )
        with _LOCK, self._connection() as db:
            existing_ids: list[str] = []
            thumbnails: list[dict[str, Any]] = []
            for asset_id in ids:
                row = db.execute("SELECT asset_id FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
                if not row:
                    continue
                existing_ids.append(asset_id)
                thumb = db.execute("SELECT * FROM asset_thumbnails WHERE asset_id=?", (asset_id,)).fetchone()
                if thumb:
                    thumbnails.append(dict(thumb))
            if not existing_ids:
                return {"purged": 0, "thumbnails": []}
            rows = [(asset_id,) for asset_id in existing_ids]
            for table in child_tables:
                db.executemany(f"DELETE FROM {table} WHERE asset_id=?", rows)
            db.executemany("DELETE FROM assets WHERE asset_id=?", rows)
        return {"purged": len(existing_ids), "thumbnails": thumbnails}

    def asset(self, asset_id: str) -> dict[str, Any] | None:
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone()
            if row is None:
                return None
            value = dict(row)
            value["paths"] = [entry[0] for entry in db.execute("SELECT path FROM asset_paths WHERE asset_id=? ORDER BY seen_at DESC", (asset_id,))]
            value["triggers"] = [dict(entry) | {"flags": json.loads(entry["flags_json"])} for entry in db.execute("SELECT * FROM trigger_candidates WHERE asset_id=? ORDER BY pinned DESC, confidence DESC", (asset_id,))]
            review = db.execute("SELECT * FROM asset_reviews WHERE asset_id=?", (asset_id,)).fetchone()
            value["review"] = dict(review) if review else {"state": "untested"}
            usage = db.execute("SELECT * FROM asset_usage WHERE asset_id=?", (asset_id,)).fetchone()
            value["usage"] = dict(usage) if usage else {"use_count": 0, "last_used_at": "", "last_output": ""}
            value["usage_events"] = [
                dict(entry) for entry in db.execute(
                    "SELECT used_at, output_path FROM asset_usage_events WHERE asset_id=? ORDER BY used_at DESC LIMIT 24",
                    (asset_id,),
                )
            ]
            first_use = db.execute("SELECT MIN(used_at) FROM asset_usage_events WHERE asset_id=?", (asset_id,)).fetchone()
            value["first_used_at"] = str(first_use[0] or "") if first_use else ""
            thumbnail = db.execute("SELECT * FROM asset_thumbnails WHERE asset_id=?", (asset_id,)).fetchone()
            value["thumbnail"] = dict(thumbnail) if thumbnail else None
            remote = db.execute("SELECT * FROM asset_remote_metadata WHERE asset_id=?", (asset_id,)).fetchone()
            value["remote_metadata"] = json.loads(remote["payload_json"]) if remote else {}
            if remote:
                value["remote_metadata_source"] = remote["source"]
                value["remote_metadata_fetched_at"] = remote["fetched_at"]
            return value

    def thumbnail(self, asset_id: str) -> dict[str, Any] | None:
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT * FROM asset_thumbnails WHERE asset_id=?", (asset_id,)).fetchone()
        return dict(row) if row else None

    def set_thumbnail(
        self, asset_id: str, filename: str, source: str, *, source_url: str = "",
        width: int = 0, height: int = 0, byte_size: int = 0,
    ) -> None:
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO asset_thumbnails(asset_id, filename, source, source_url, width, height, byte_size, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET filename=excluded.filename, source=excluded.source,
                source_url=excluded.source_url, width=excluded.width, height=excluded.height,
                byte_size=excluded.byte_size, updated_at=excluded.updated_at""",
                (asset_id, filename, source, source_url, int(width), int(height), int(byte_size), now, now),
            )

    def clear_thumbnail(self, asset_id: str) -> dict[str, Any] | None:
        existing = self.thumbnail(asset_id)
        with _LOCK, self._connection() as db:
            db.execute("DELETE FROM asset_thumbnails WHERE asset_id=?", (asset_id,))
        return existing

    def set_remote_metadata(self, asset_id: str, payload: dict[str, Any], source: str) -> None:
        clean = dict(payload or {})
        model_id = str(clean.get("model_id") or "")
        version_id = str(clean.get("version_id") or "")
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO asset_remote_metadata(asset_id, source, payload_json, fetched_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET source=excluded.source, payload_json=excluded.payload_json, fetched_at=excluded.fetched_at""",
                (asset_id, str(source or ""), json.dumps(clean, sort_keys=True), now),
            )
            if model_id or version_id:
                db.execute(
                    """UPDATE assets SET
                    civitai_model_id=CASE WHEN ?<>'' THEN ? ELSE civitai_model_id END,
                    civitai_version_id=CASE WHEN ?<>'' THEN ? ELSE civitai_version_id END,
                    updated_at=? WHERE asset_id=?""",
                    (model_id, model_id, version_id, version_id, now, asset_id),
                )

    @staticmethod
    def _decode_remote(value: Any) -> dict[str, Any]:
        try:
            return json.loads(str(value or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def exact_repair_target(self, *, sha256: str = "", old_path: str = "") -> str | None:
        """Return an automatic repair only when identity is exact and unique.

        Filename similarity is intentionally excluded: a wrong LoRA route is
        more harmful than leaving a broken reference visible for review.
        """

        with _LOCK, self._connection() as db:
            if sha256:
                rows = db.execute("SELECT current_path FROM assets WHERE sha256=?", (sha256,)).fetchall()
            elif old_path:
                rows = db.execute("SELECT a.current_path FROM assets a JOIN asset_paths p ON p.asset_id=a.asset_id WHERE p.path=?", (os.path.abspath(old_path),)).fetchall()
            else:
                return None
        paths = {str(row[0]) for row in rows if row[0]}
        return next(iter(paths)) if len(paths) == 1 else None

    def list_assets(self, state: str = "", query: str = "", sort: str = "recent") -> list[dict[str, Any]]:
        terms: list[str] = []
        clauses: list[str] = []
        params: list[Any] = []
        normalized_state = str(state or "").strip().lower()
        if normalized_state == "tested":
            clauses.append("COALESCE(u.use_count, 0)>0")
        elif normalized_state == "untested":
            clauses.append("COALESCE(u.use_count, 0)=0")
        elif normalized_state in {"keep", "favorite", "retest", "reject"}:
            clauses.append("r.state=?")
            params.append(normalized_state)
        if query.strip():
            clauses.append("(a.current_path LIKE ? OR a.model_name LIKE ?)")
            needle = f"%{query.strip()}%"
            params.extend([needle, needle])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = {
            "most_used": "COALESCE(u.use_count, 0) DESC, a.model_name COLLATE NOCASE ASC",
            "least_used": "COALESCE(u.use_count, 0) ASC, a.model_name COLLATE NOCASE ASC",
            "name": "a.model_name COLLATE NOCASE ASC",
            "last_used": "COALESCE(u.last_used_at, '') DESC, a.model_name COLLATE NOCASE ASC",
        }.get(str(sort or "recent"), "a.updated_at DESC")
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"""SELECT a.*,
                CASE WHEN r.state IN ('rated', 'keep', 'favorite', 'retest', 'reject') THEN r.state ELSE 'none' END AS review_state,
                COALESCE(r.rating, 0) AS rating, COALESCE(r.note, '') AS note,
                COALESCE(u.use_count, 0) AS use_count, COALESCE(u.last_used_at, '') AS last_used_at,
                COALESCE(u.last_output, '') AS last_output,
                COALESCE(t.filename, '') AS thumbnail_ref, COALESCE(t.source, '') AS thumbnail_source,
                COALESCE(t.width, 0) AS thumbnail_width, COALESCE(t.height, 0) AS thumbnail_height,
                COALESCE(t.byte_size, 0) AS thumbnail_bytes, COALESCE(t.updated_at, '') AS thumbnail_updated_at,
                COALESCE(m.payload_json, '{{}}') AS remote_json,
                CASE WHEN COALESCE(u.use_count, 0)>0 THEN 1 ELSE 0 END AS tested
                FROM assets a LEFT JOIN asset_reviews r ON r.asset_id=a.asset_id
                LEFT JOIN asset_usage u ON u.asset_id=a.asset_id
                LEFT JOIN asset_thumbnails t ON t.asset_id=a.asset_id
                LEFT JOIN asset_remote_metadata m ON m.asset_id=a.asset_id
                {where}
                ORDER BY {order}""",
                params,
            ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            value = dict(row)
            remote = self._decode_remote(value.pop("remote_json", "{}"))
            remote_images = _supported_remote_images(remote)
            value["civitai_preview"] = remote_images[0] if remote_images else ""
            value["civitai_image_count"] = len(remote_images)
            value["civitai_creator"] = str(remote.get("creator") or "")
            value["base_model"] = str(remote.get("base_model") or "")
            values.append(value)
        return values

    def save_filter(self, name: str, query: dict[str, Any]) -> None:
        clean = str(name).strip()
        if not clean:
            raise ValueError("Filter name is required")
        with _LOCK, self._connection() as db:
            db.execute("INSERT OR REPLACE INTO saved_filters(name, query_json, updated_at) VALUES (?, ?, ?)", (clean, json.dumps(query, sort_keys=True), _now()))

    def filters(self) -> list[dict[str, Any]]:
        with _LOCK, self._connection() as db:
            rows = db.execute("SELECT name, query_json, updated_at FROM saved_filters ORDER BY name COLLATE NOCASE").fetchall()
        return [{"name": row["name"], "query": json.loads(row["query_json"]), "updated_at": row["updated_at"]} for row in rows]

    def lora_collections(self) -> list[dict[str, Any]]:
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT c.collection_id, c.name, c.color, c.created_at, c.updated_at,
                COUNT(m.asset_id) AS asset_count
                FROM lora_collections c
                LEFT JOIN lora_collection_memberships m ON m.collection_id=c.collection_id
                GROUP BY c.collection_id
                ORDER BY c.name COLLATE NOCASE"""
            ).fetchall()
            memberships = db.execute(
                "SELECT collection_id, asset_id FROM lora_collection_memberships ORDER BY created_at, asset_id"
            ).fetchall()
        grouped: dict[str, list[str]] = {}
        for row in memberships:
            grouped.setdefault(str(row["collection_id"]), []).append(str(row["asset_id"]))
        return [dict(row) | {"asset_ids": grouped.get(str(row["collection_id"]), [])} for row in rows]

    def create_lora_collection(self, name: str, color: str = "") -> dict[str, Any]:
        clean = " ".join(str(name or "").split())
        if not clean:
            raise ValueError("Collection name is required")
        if len(clean) > 120:
            raise ValueError("Collection names are limited to 120 characters")
        now = _now()
        with _LOCK, self._connection() as db:
            existing = db.execute("SELECT * FROM lora_collections WHERE name=? COLLATE NOCASE", (clean,)).fetchone()
            if existing:
                return dict(existing) | {"asset_count": int(db.execute("SELECT COUNT(*) FROM lora_collection_memberships WHERE collection_id=?", (existing["collection_id"],)).fetchone()[0]), "asset_ids": []}
            use_color = str(color or "").strip()
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", use_color):
                count = int(db.execute("SELECT COUNT(*) FROM lora_collections").fetchone()[0])
                use_color = RECIPE_COLLECTION_COLORS[count % len(RECIPE_COLLECTION_COLORS)]
            collection_id = "lora-collection:" + uuid.uuid4().hex
            db.execute(
                "INSERT INTO lora_collections(collection_id,name,color,created_at,updated_at) VALUES(?,?,?,?,?)",
                (collection_id, clean, use_color, now, now),
            )
        return {"collection_id": collection_id, "name": clean, "color": use_color, "created_at": now, "updated_at": now, "asset_count": 0, "asset_ids": []}

    def delete_lora_collection(self, collection_id: str) -> bool:
        with _LOCK, self._connection() as db:
            result = db.execute("DELETE FROM lora_collections WHERE collection_id=?", (str(collection_id),))
        return bool(result.rowcount)

    def update_lora_collection_members(self, collection_id: str, asset_ids: list[str], *, remove: bool = False) -> dict[str, int]:
        result = self.update_lora_collections_members([collection_id], asset_ids, remove=remove)
        return {
            "assets": int(result.get("assets") or 0),
            "memberships_changed": int(result.get("memberships_changed") or 0),
        }

    def update_lora_collections_members(
        self,
        collection_ids: list[str],
        asset_ids: list[str],
        *,
        remove: bool = False,
    ) -> dict[str, int]:
        clean_collections = list(dict.fromkeys(
            str(collection_id or "").strip()
            for collection_id in collection_ids
            if str(collection_id or "").strip()
        ))
        clean_assets = self._clean_asset_ids(asset_ids)
        if not clean_collections:
            raise ValueError("Select at least one LoRA collection")
        with _LOCK, self._connection() as db:
            placeholders = ",".join("?" for _ in clean_collections)
            found_collections = {
                str(row[0]) for row in db.execute(
                    f"SELECT collection_id FROM lora_collections WHERE collection_id IN ({placeholders})",
                    clean_collections,
                )
            }
            if found_collections != set(clean_collections):
                raise ValueError("One or more selected LoRA collections no longer exist")
            if not clean_assets:
                return {"assets": 0, "collections": len(clean_collections), "memberships_changed": 0}
            valid: set[str] = set()
            for offset in range(0, len(clean_assets), 500):
                chunk = clean_assets[offset:offset + 500]
                asset_placeholders = ",".join("?" for _ in chunk)
                valid.update(str(row[0]) for row in db.execute(f"SELECT asset_id FROM assets WHERE asset_id IN ({asset_placeholders})", chunk))
            pairs = [
                (asset_id, collection_id)
                for collection_id in clean_collections
                for asset_id in valid
            ]
            if remove:
                before = db.total_changes
                db.executemany(
                    "DELETE FROM lora_collection_memberships WHERE asset_id=? AND collection_id=?",
                    pairs,
                )
                changed = db.total_changes - before
            else:
                before = db.total_changes
                now = _now()
                db.executemany(
                    "INSERT OR IGNORE INTO lora_collection_memberships(asset_id,collection_id,created_at) VALUES(?,?,?)",
                    [(asset_id, collection_id, now) for asset_id, collection_id in pairs],
                )
                changed = db.total_changes - before
            updated_at = _now()
            db.executemany(
                "UPDATE lora_collections SET updated_at=? WHERE collection_id=?",
                [(updated_at, collection_id) for collection_id in clean_collections],
            )
        return {
            "assets": len(valid),
            "collections": len(clean_collections),
            "memberships_changed": max(0, int(changed)),
        }

    def save_recipe(self, recipe_id: str, name: str, payload: dict[str, Any], preview_ref: str = "") -> None:
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("Recipe name is required")
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO recipes(recipe_id, name, payload_json, preview_ref, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(recipe_id) DO UPDATE SET name=excluded.name, payload_json=excluded.payload_json, preview_ref=excluded.preview_ref, updated_at=excluded.updated_at""",
                (recipe_id, clean_name, json.dumps(payload, sort_keys=True), str(preview_ref or ""), now, now),
            )

    def recipes(self) -> list[dict[str, Any]]:
        with _LOCK, self._connection() as db:
            rows = db.execute("SELECT * FROM recipes ORDER BY updated_at DESC").fetchall()
            memberships = db.execute(
                """SELECT m.recipe_id, c.collection_id, c.name, c.color
                FROM recipe_collection_memberships m
                JOIN recipe_collections c ON c.collection_id=m.collection_id
                ORDER BY c.name COLLATE NOCASE"""
            ).fetchall()
        grouped: dict[str, list[dict[str, str]]] = {}
        for membership in memberships:
            grouped.setdefault(str(membership["recipe_id"]), []).append({
                "collection_id": str(membership["collection_id"]),
                "name": str(membership["name"]),
                "color": str(membership["color"]),
            })
        return [dict(row) | {
            "payload": json.loads(row["payload_json"]),
            "collections": grouped.get(str(row["recipe_id"]), []),
        } for row in rows]

    def recipe_revision(self) -> str:
        """Cheap cache signature for large Creative Library prompt snapshots."""
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT value FROM schema_meta WHERE key='recipe_revision'").fetchone()
        return str(row["value"] if row else "0")

    def component_revision(self) -> str:
        """Cheap cache signature for Creative Library Outfit/Scene views."""
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT value FROM schema_meta WHERE key='component_revision'").fetchone()
        return str(row["value"] if row else "0")

    def prompt_revision(self) -> str:
        """Cheap cache signature for the canonical prompt/source index."""
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT value FROM schema_meta WHERE key='prompt_revision'").fetchone()
        return str(row["value"] if row else "0")

    def fragment_revision(self) -> str:
        """Cheap cache signature for mined and curated Prompt Builder fragments."""
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT value FROM schema_meta WHERE key='fragment_revision'").fetchone()
        return str(row["value"] if row else "0")

    def creative_library_revisions(self) -> dict[str, str]:
        """Return every Creative Library cache token in one tiny query.

        The browser uses this before reopening the Library so an unchanged
        catalog can be painted from its already-loaded page instead of
        downloading and rebuilding every tab again.
        """
        keys = ("recipe_revision", "prompt_revision", "fragment_revision", "component_revision")
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"SELECT key, value FROM schema_meta WHERE key IN ({','.join('?' for _ in keys)})",
                keys,
            ).fetchall()
        values = {str(row["key"]): str(row["value"]) for row in rows}
        return {
            "recipes": values.get("recipe_revision", "0"),
            "prompts": values.get("prompt_revision", "0"),
            "fragments": values.get("fragment_revision", "0"),
            "components": values.get("component_revision", "0"),
        }

    def creative_library_counts(self) -> dict[str, int]:
        """Return lightweight tab counts without materializing catalog rows."""
        with _LOCK, self._connection() as db:
            prompt_rows = db.execute(
                """SELECT p.kind, COUNT(*) AS amount
                FROM prompt_assets p
                LEFT JOIN prompt_overrides o ON o.prompt_id=p.prompt_id
                WHERE COALESCE(o.archived, 0)=0
                GROUP BY p.kind"""
            ).fetchall()
            component_rows = db.execute(
                "SELECT kind, COUNT(*) AS amount FROM recipe_components GROUP BY kind"
            ).fetchall()
            fragment_rows = db.execute(
                "SELECT review_state, COUNT(*) AS amount FROM fragment_assets GROUP BY review_state"
            ).fetchall()
            recipe_count = int(db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0])
            wardrobe_count = int(db.execute("SELECT COUNT(*) FROM wardrobe_items").fetchone()[0])
            board_count = int(db.execute("SELECT COUNT(*) FROM creative_boards").fetchone()[0])
        prompts = {str(row["kind"]): int(row["amount"] or 0) for row in prompt_rows}
        components = {str(row["kind"]): int(row["amount"] or 0) for row in component_rows}
        fragments = {str(row["review_state"]): int(row["amount"] or 0) for row in fragment_rows}
        return {
            "templates": prompts.get("template", 0),
            "prompts": prompts.get("prompt", 0),
            "outfits": components.get("outfit", 0),
            "scenes": components.get("scene", 0),
            "wardrobe": wardrobe_count,
            "fragments": fragments.get("approved", 0) + fragments.get("suggested", 0),
            "recipes": recipe_count,
            "boards": board_count,
        }

    def metadata_value(self, key: str, default: str = "") -> str:
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT value FROM schema_meta WHERE key=?", (str(key or ""),)).fetchone()
        return str(row["value"] if row else default)

    def set_metadata_value(self, key: str, value: str) -> None:
        clean_key = str(key or "").strip()
        if not clean_key:
            raise ValueError("Metadata key is required")
        with _LOCK, self._connection() as db:
            db.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES(?, ?)", (clean_key, str(value or "")))

    @staticmethod
    def _structure_order_key(scope: str) -> str:
        clean_scope = str(scope or "").strip().lower()
        if clean_scope not in {"prompt", "template", "recipe", "outfit", "scene"}:
            raise ValueError("Unknown Creative Library structure scope")
        return f"creative_structure_order_v1:{clean_scope}"

    @staticmethod
    def _clean_structure_order_value(value: Any) -> Any:
        if isinstance(value, list):
            output = []
            seen = set()
            for item in value:
                clean = str(item or "").strip()
                if not clean or clean in seen:
                    continue
                seen.add(clean); output.append(clean)
            return output
        if isinstance(value, dict):
            output = {}
            for key, item in value.items():
                clean_key = str(key or "").strip()
                if not clean_key:
                    continue
                cleaned = SoloCatalog._clean_structure_order_value(item)
                if isinstance(cleaned, (list, dict)):
                    output[clean_key] = cleaned
            return output
        return []

    def creative_structure_order(self, scope: str) -> dict[str, Any]:
        key = self._structure_order_key(scope)
        clean_scope = str(scope or "").strip().lower()
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT value FROM schema_meta WHERE key=?", (key,)).fetchone()
        if row is None:
            return {}
        try:
            parsed = json.loads(str(row["value"] or "{}"))
        except Exception:
            return {}
        cleaned = self._clean_structure_order_value(parsed)
        if not isinstance(cleaned, dict):
            return {}
        if clean_scope in {"prompt", "template"}:
            children = cleaned.get("subcategories") if isinstance(cleaned.get("subcategories"), dict) else {}
            if isinstance(children.get("Saved & Imported"), list):
                children["Saved & Imported"] = [value for value in children["Saved & Imported"] if value != "Last Import"]
            logs = cleaned.get("logs") if isinstance(cleaned.get("logs"), dict) else {}
            if isinstance(logs.get("Saved & Imported"), dict):
                logs["Saved & Imported"].pop("Last Import", None)
        return cleaned

    def set_creative_structure_order(self, scope: str, order: dict[str, Any]) -> dict[str, Any]:
        key = self._structure_order_key(scope)
        cleaned = self._clean_structure_order_value(order if isinstance(order, dict) else {})
        if not isinstance(cleaned, dict):
            cleaned = {}
        clean_scope = str(scope or "").strip().lower()
        revision_key = "prompt_revision" if clean_scope in {"prompt", "template"} else "recipe_revision" if clean_scope == "recipe" else "component_revision"
        with _LOCK, self._connection() as db:
            db.execute(
                "INSERT INTO schema_meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, json.dumps(cleaned, ensure_ascii=False, sort_keys=True)),
            )
            db.execute(
                f"INSERT INTO schema_meta(key, value) VALUES('{revision_key}', '1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"
            )
        return cleaned

    def replace_prompt_index(
        self,
        assets: list[dict[str, Any]],
        files: list[dict[str, Any]],
        *,
        signature: str,
    ) -> dict[str, int]:
        """Atomically replace the derived prompt/source index.

        Source text files remain canonical. Stable content-addressed prompt IDs
        make a rebuild reversible and allow the index to be discarded safely.
        """
        now = _now()
        clean_assets: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for item in assets:
            prompt_id = str(item.get("prompt_id") or "").strip()
            value = " ".join(str(item.get("value") or "").split())
            if not prompt_id or not value or prompt_id in seen_ids:
                continue
            seen_ids.add(prompt_id)
            sources = []
            source_seen: set[tuple[str, int]] = set()
            for source in item.get("sources") or []:
                if not isinstance(source, dict):
                    continue
                source_path = str(source.get("source_path") or source.get("path") or "").replace("\\", "/").strip()
                try:
                    line_number = max(0, int(source.get("line_number") or 0))
                except (TypeError, ValueError):
                    line_number = 0
                key = (source_path, line_number)
                if not source_path or key in source_seen:
                    continue
                source_seen.add(key)
                sources.append({
                    "source_path": source_path,
                    "line_number": line_number,
                    "source_label": " ".join(str(source.get("source_label") or source.get("label") or Path(source_path).stem).split()),
                })
            signature = _creative_prompt_signature(value)
            if "primary_subcategory" in item:
                clean_subcategory = " ".join(str(item.get("primary_subcategory") or "").split())
            else:
                clean_subcategory = "General"
            clean_assets.append({
                "prompt_id": prompt_id,
                "kind": "template" if signature else "prompt",
                "value": value,
                "placeholder_signature": signature,
                "primary_parent": " ".join(str(item.get("primary_parent") or "Other").split()) or "Other",
                "primary_subcategory": clean_subcategory,
                "facets_json": json.dumps(item.get("facets") if isinstance(item.get("facets"), dict) else {}, ensure_ascii=False, sort_keys=True),
                "quality_score": float(item.get("quality_score") or 0),
                "exact_source_occurrences": max(0, int(item.get("exact_source_occurrences") or 0)),
                "near_cluster_id": str(item.get("near_cluster_id") or ""),
                "preview_ref": str(item.get("preview_ref") or ""),
                "preview_source": str(item.get("preview_source") or ""),
                "preview_updated_at": str(item.get("preview_updated_at") or ""),
                "resolved_seed": int(item.get("resolved_seed")) if item.get("resolved_seed") is not None and str(item.get("resolved_seed")).lstrip("-").isdigit() else -1,
                "resolved_seed_source": str(item.get("resolved_seed_source") or ""),
                "source_count": max(0, int(item.get("source_count") or len(sources))),
                "sources": sources,
            })

        with _LOCK, self._connection() as db:
            existing_state = {}
            for row in db.execute(
                """SELECT p.value, p.created_at, p.preview_ref, p.preview_source, p.preview_updated_at, p.resolved_seed, p.resolved_seed_source,
                COALESCE(r.rating, 0) AS rating, COALESCE(r.note, '') AS note
                FROM prompt_assets p LEFT JOIN prompt_reviews r ON r.prompt_id=p.prompt_id"""
            ):
                existing_state[str(row["value"] or "").casefold()] = dict(row)
            db.execute("DELETE FROM prompt_sources")
            db.execute("DELETE FROM prompt_assets WHERE is_custom=0")
            db.execute("DELETE FROM prompt_index_files")
            db.executemany(
                """INSERT INTO prompt_assets(
                    prompt_id, kind, value, placeholder_signature, primary_parent, primary_subcategory,
                    facets_json, quality_score, exact_source_occurrences, near_cluster_id,
                    preview_ref, preview_source, preview_updated_at, resolved_seed, resolved_seed_source, is_custom, source_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        item["prompt_id"], item["kind"], item["value"], item["placeholder_signature"],
                        item["primary_parent"], item["primary_subcategory"], item["facets_json"],
                        item["quality_score"], item["exact_source_occurrences"], item["near_cluster_id"],
                        item["preview_ref"] or str(existing_state.get(item["value"].casefold(), {}).get("preview_ref") or ""),
                        item["preview_source"] or str(existing_state.get(item["value"].casefold(), {}).get("preview_source") or ""),
                        item["preview_updated_at"] or str(existing_state.get(item["value"].casefold(), {}).get("preview_updated_at") or ""),
                        int(item.get("resolved_seed") if str(item.get("resolved_seed_source") or "") else (existing_state.get(item["value"].casefold(), {}).get("resolved_seed") if existing_state.get(item["value"].casefold(), {}).get("resolved_seed") is not None else -1)),
                        str(item.get("resolved_seed_source") or existing_state.get(item["value"].casefold(), {}).get("resolved_seed_source") or ""),
                        0,
                        item["source_count"],
                        str(existing_state.get(item["value"].casefold(), {}).get("created_at") or now), now,
                    )
                    for item in clean_assets
                ],
            )
            review_rows = []
            for item in clean_assets:
                state = existing_state.get(item["value"].casefold()) or {}
                rating = max(0, min(5, int(state.get("rating") or 0)))
                note = str(state.get("note") or "")
                if rating or note:
                    review_rows.append((item["prompt_id"], rating, note, now))
            if review_rows:
                db.executemany(
                    "INSERT INTO prompt_reviews(prompt_id, rating, note, updated_at) VALUES (?, ?, ?, ?)",
                    review_rows,
                )
            source_rows = [
                (
                    item["prompt_id"], source["source_path"], source["line_number"], source["source_label"], now,
                )
                for item in clean_assets
                for source in item["sources"]
            ]
            if source_rows:
                db.executemany(
                    """INSERT INTO prompt_sources(prompt_id, source_path, line_number, source_label, created_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    source_rows,
                )
            clean_files = []
            for item in files:
                source_path = str(item.get("source_path") or item.get("path") or "").replace("\\", "/").strip()
                if not source_path:
                    continue
                try:
                    byte_size = max(0, int(item.get("byte_size") or item.get("size") or 0))
                    modified_ns = max(0, int(item.get("modified_ns") or item.get("mtime_ns") or 0))
                    line_count = max(0, int(item.get("line_count") or 0))
                except (TypeError, ValueError):
                    continue
                clean_files.append((source_path, byte_size, modified_ns, line_count, now))
            if clean_files:
                db.executemany(
                    """INSERT INTO prompt_index_files(source_path, byte_size, modified_ns, line_count, updated_at)
                    VALUES (?, ?, ?, ?, ?)""",
                    clean_files,
                )
            db.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES('prompt_index_signature', ?)", (str(signature or ""),))
            db.execute(
                """INSERT INTO schema_meta(key, value) VALUES('prompt_revision', '1')
                ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
            )
        return {"prompts": len(clean_assets), "sources": len(source_rows), "files": len(clean_files)}

    def indexed_prompt_assets(self) -> list[dict[str, Any]]:
        """Return canonical prompt text with complete source-log provenance."""
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT p.prompt_id, p.kind, p.value, p.placeholder_signature,
                CASE WHEN COALESCE(o.home_override, 0)=1 THEN o.primary_parent ELSE p.primary_parent END AS primary_parent,
                CASE WHEN COALESCE(o.home_override, 0)=1 THEN o.primary_subcategory ELSE p.primary_subcategory END AS primary_subcategory,
                p.facets_json, p.quality_score,
                p.exact_source_occurrences, p.near_cluster_id, p.preview_ref, p.preview_source, p.preview_updated_at,
                p.resolved_seed, p.resolved_seed_source, p.source_prompt_snapshot, p.resolved_prompt_snapshot,
                p.preview_metadata_json,
                p.is_custom, COALESCE(o.archived, 0) AS archived,
                p.source_count, p.created_at, p.updated_at,
                COALESCE(r.rating, 0) AS rating, COALESCE(r.note, '') AS note
                FROM prompt_assets p
                LEFT JOIN prompt_reviews r ON r.prompt_id=p.prompt_id
                LEFT JOIN prompt_overrides o ON o.prompt_id=p.prompt_id
                ORDER BY p.prompt_id"""
            ).fetchall()
            sources = db.execute(
                """SELECT prompt_id, source_path, line_number, source_label
                FROM prompt_sources ORDER BY prompt_id, source_path COLLATE NOCASE, line_number"""
            ).fetchall()
            collection_rows = db.execute(
                """SELECT m.prompt_id, c.collection_id, c.kind, c.name, c.color
                FROM prompt_showcase_memberships m
                JOIN prompt_showcase_collections c ON c.collection_id=m.collection_id
                JOIN prompt_assets p ON p.prompt_id=m.prompt_id AND p.kind=c.kind
                ORDER BY m.prompt_id, c.name COLLATE NOCASE"""
            ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = {}
        for source in sources:
            grouped.setdefault(str(source["prompt_id"]), []).append({
                "source_path": str(source["source_path"]),
                "line_number": int(source["line_number"] or 0),
                "source_label": str(source["source_label"] or ""),
            })
        grouped_collections: dict[str, list[dict[str, str]]] = {}
        for collection in collection_rows:
            grouped_collections.setdefault(str(collection["prompt_id"]), []).append({
                "collection_id": str(collection["collection_id"]),
                "kind": str(collection["kind"]),
                "name": str(collection["name"]),
                "color": str(collection["color"]),
            })
        output = []
        for row in rows:
            item = dict(row)
            try:
                item["facets"] = json.loads(str(item.pop("facets_json", "{}") or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                item["facets"] = {}
            item["sources"] = grouped.get(str(row["prompt_id"]), [])
            item["collections"] = grouped_collections.get(str(row["prompt_id"]), [])
            try:
                item["preview_metadata"] = json.loads(str(item.pop("preview_metadata_json", "{}") or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                item["preview_metadata"] = {}
            output.append(item)
        return output

    def prompt_collection_map(self, prompt_ids: list[str] | None = None) -> dict[str, list[dict[str, str]]]:
        requested = self._clean_prompt_ids(prompt_ids or [])
        with _LOCK, self._connection() as db:
            query = """SELECT m.prompt_id, c.collection_id, c.kind, c.name, c.color
                FROM prompt_showcase_memberships m
                JOIN prompt_showcase_collections c ON c.collection_id=m.collection_id"""
            params: list[str] = []
            if requested:
                query += f" WHERE m.prompt_id IN ({','.join('?' for _ in requested)})"
                params.extend(requested)
            query += " ORDER BY m.prompt_id, c.name COLLATE NOCASE"
            rows = db.execute(query, params).fetchall()
        output: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            output.setdefault(str(row["prompt_id"]), []).append({
                "collection_id": str(row["collection_id"]), "kind": str(row["kind"]),
                "name": str(row["name"]), "color": str(row["color"]),
            })
        return output

    def set_prompt_collections(self, prompt_id: str, collection_ids: list[str], kind: str = "prompt") -> list[dict[str, str]]:
        clean_id = str(prompt_id or "").strip()
        if not clean_id:
            raise ValueError("Prompt record is required")
        requested = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        clean_kind = self._clean_prompt_showcase_kind(kind)
        with _LOCK, self._connection() as db:
            rows = self._validate_prompt_showcase_collection_ids(db, requested, clean_kind)
            db.execute(
                """DELETE FROM prompt_showcase_memberships WHERE prompt_id=? AND collection_id IN (
                SELECT collection_id FROM prompt_showcase_collections WHERE kind=?
                )""",
                (clean_id, clean_kind),
            )
            now = _now()
            db.executemany(
                "INSERT INTO prompt_showcase_memberships(prompt_id, collection_id, created_at) VALUES (?, ?, ?)",
                [(clean_id, collection_id, now) for collection_id in requested],
            )
            self._bump_prompt_revision(db)
        selected = {str(row["collection_id"]): row for row in rows}
        return [{"collection_id": value, "name": str(selected[value]["name"]), "color": str(selected[value]["color"])} for value in requested]

    @staticmethod
    def _clean_prompt_showcase_kind(kind: str) -> str:
        return "template" if str(kind or "").strip().casefold() == "template" else "prompt"

    @classmethod
    def _validate_prompt_showcase_collection_ids(
        cls, db: sqlite3.Connection, collection_ids: list[str], kind: str,
    ) -> list[sqlite3.Row]:
        if not collection_ids:
            return []
        clean_kind = cls._clean_prompt_showcase_kind(kind)
        placeholders = ",".join("?" for _ in collection_ids)
        rows = db.execute(
            f"""SELECT collection_id, name, color FROM prompt_showcase_collections
            WHERE kind=? AND collection_id IN ({placeholders})""",
            [clean_kind, *collection_ids],
        ).fetchall()
        if {str(row["collection_id"]) for row in rows} != set(collection_ids):
            raise ValueError("One or more selected folders no longer exist")
        return rows

    def add_prompts_to_collections(
        self, prompt_ids: list[str], collection_ids: list[str], kind: str = "prompt",
    ) -> dict[str, int]:
        requested_prompts = self._clean_prompt_ids(prompt_ids)
        requested_collections = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        if not requested_prompts:
            raise ValueError("Select at least one Prompt")
        if not requested_collections:
            raise ValueError("Select at least one folder")
        clean_kind = self._clean_prompt_showcase_kind(kind)
        with _LOCK, self._connection() as db:
            self._validate_prompt_showcase_collection_ids(db, requested_collections, clean_kind)
            now = _now()
            cursor = db.executemany(
                "INSERT OR IGNORE INTO prompt_showcase_memberships(prompt_id, collection_id, created_at) VALUES (?, ?, ?)",
                [(prompt_id, collection_id, now) for prompt_id in requested_prompts for collection_id in requested_collections],
            )
            self._bump_prompt_revision(db)
            added = max(0, int(cursor.rowcount or 0))
        return {"prompts": len(requested_prompts), "collections": len(requested_collections), "memberships_added": added}

    def remove_prompts_from_collections(
        self, prompt_ids: list[str], collection_ids: list[str], kind: str = "prompt",
    ) -> dict[str, int]:
        requested_prompts = self._clean_prompt_ids(prompt_ids)
        requested_collections = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        if not requested_prompts or not requested_collections:
            return {"prompts": len(requested_prompts), "collections": len(requested_collections), "memberships_removed": 0}
        clean_kind = self._clean_prompt_showcase_kind(kind)
        with _LOCK, self._connection() as db:
            self._validate_prompt_showcase_collection_ids(db, requested_collections, clean_kind)
            removed = 0
            for collection_id in requested_collections:
                for prompt_id in requested_prompts:
                    result = db.execute(
                        "DELETE FROM prompt_showcase_memberships WHERE prompt_id=? AND collection_id=?",
                        (prompt_id, collection_id),
                    )
                    removed += max(0, int(result.rowcount or 0))
            if removed:
                self._bump_prompt_revision(db)
        return {"prompts": len(requested_prompts), "collections": len(requested_collections), "memberships_removed": removed}

    def rename_prompt_source_log(self, source_path: str, label: str) -> int:
        clean_path = str(source_path or "").replace("\\", "/").strip()
        clean_label = " ".join(str(label or "").split())
        if not clean_path:
            raise ValueError("Source Log path is required")
        if not clean_label:
            raise ValueError("Source Log name is required")
        if len(clean_label) > 120:
            raise ValueError("Source Log names are limited to 120 characters")
        with _LOCK, self._connection() as db:
            result = db.execute(
                "UPDATE prompt_sources SET source_label=? WHERE REPLACE(source_path, '\\', '/')=?",
                (clean_label, clean_path),
            )
            if result.rowcount:
                self._bump_prompt_revision(db)
        return max(0, int(result.rowcount or 0))

    def move_prompt_source_log(self, source_path: str, next_source_path: str, label: str) -> int:
        """Move one canonical Prompt Log reference without creating a second source.

        The caller owns the corresponding filesystem rename.  This database
        half is intentionally strict: an existing destination is a conflict,
        never an invitation to merge or duplicate source rows.
        """
        clean_path = str(source_path or "").replace("\\", "/").strip()
        clean_next = str(next_source_path or "").replace("\\", "/").strip()
        clean_label = " ".join(str(label or "").split())
        if not clean_path or not clean_next:
            raise ValueError("Source Log paths are required")
        if not clean_label:
            raise ValueError("Source Log name is required")
        if len(clean_label) > 120:
            raise ValueError("Source Log names are limited to 120 characters")
        with _LOCK, self._connection() as db:
            if clean_next.casefold() != clean_path.casefold():
                if db.execute(
                    "SELECT 1 FROM prompt_sources WHERE LOWER(REPLACE(source_path, '\\', '/'))=LOWER(?) LIMIT 1",
                    (clean_next,),
                ).fetchone() or db.execute(
                    "SELECT 1 FROM prompt_index_files WHERE LOWER(REPLACE(source_path, '\\', '/'))=LOWER(?) LIMIT 1",
                    (clean_next,),
                ).fetchone():
                    raise ValueError("A Prompt Log with that filename already exists")
            result = db.execute(
                "UPDATE prompt_sources SET source_path=?, source_label=? WHERE REPLACE(source_path, '\\', '/')=?",
                (clean_next, clean_label, clean_path),
            )
            db.execute(
                "UPDATE prompt_index_files SET source_path=? WHERE REPLACE(source_path, '\\', '/')=?",
                (clean_next, clean_path),
            )
            for scope in ("prompt", "template"):
                key = self._structure_order_key(scope)
                row = db.execute("SELECT value FROM schema_meta WHERE key=?", (key,)).fetchone()
                if row is None:
                    continue
                try:
                    order = json.loads(str(row["value"] or "{}"))
                except (TypeError, json.JSONDecodeError):
                    continue
                logs = order.get("logs") if isinstance(order, dict) else None
                changed_order = False
                if isinstance(logs, dict):
                    for parent_logs in logs.values():
                        if not isinstance(parent_logs, dict):
                            continue
                        for subcategory, paths in parent_logs.items():
                            if not isinstance(paths, list):
                                continue
                            replaced = [clean_next if str(value).replace("\\", "/") == clean_path else value for value in paths]
                            if replaced != paths:
                                parent_logs[subcategory] = list(dict.fromkeys(replaced))
                                changed_order = True
                if changed_order:
                    db.execute("UPDATE schema_meta SET value=? WHERE key=?", (json.dumps(order, ensure_ascii=False, sort_keys=True), key))
            if result.rowcount:
                self._bump_prompt_revision(db)
        return max(0, int(result.rowcount or 0))

    def remove_prompt_source_log(self, source_path: str) -> int:
        clean_path = str(source_path or "").replace("\\", "/").strip()
        if not clean_path:
            raise ValueError("Source Log path is required")
        with _LOCK, self._connection() as db:
            affected_prompt_ids = [str(row["prompt_id"]) for row in db.execute(
                "SELECT DISTINCT prompt_id FROM prompt_sources WHERE REPLACE(source_path, '\\', '/')=?",
                (clean_path,),
            ).fetchall()]
            result = db.execute(
                "DELETE FROM prompt_sources WHERE REPLACE(source_path, '\\', '/')=?",
                (clean_path,),
            )
            for prompt_id in affected_prompt_ids:
                db.execute(
                    "UPDATE prompt_assets SET source_count=(SELECT COUNT(*) FROM prompt_sources WHERE prompt_id=?), exact_source_occurrences=(SELECT COUNT(*) FROM prompt_sources WHERE prompt_id=?), updated_at=? WHERE prompt_id=?",
                    (prompt_id, prompt_id, _now(), prompt_id),
                )
            if result.rowcount:
                self._bump_prompt_revision(db)
        return max(0, int(result.rowcount or 0))

    def hard_delete_prompt_assets(self, prompt_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, Any]:
        """Permanently delete catalog records and every dependent UI record."""
        ids = self._clean_prompt_ids(prompt_ids)
        if not ids:
            return {"deleted": 0, "preview_refs": []}
        placeholders = ",".join("?" for _ in ids)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"SELECT prompt_id, preview_ref FROM prompt_assets WHERE prompt_id IN ({placeholders})", ids,
            ).fetchall()
            existing = [str(row["prompt_id"]) for row in rows]
            preview_refs = list(dict.fromkeys(str(row["preview_ref"] or "") for row in rows if str(row["preview_ref"] or "")))
            if not existing:
                return {"deleted": 0, "preview_refs": []}
            values = [(prompt_id,) for prompt_id in existing]
            db.executemany("DELETE FROM prompt_showcase_memberships WHERE prompt_id=?", values)
            db.executemany("DELETE FROM prompt_collection_memberships WHERE prompt_id=?", values)
            db.executemany("DELETE FROM fragment_prompt_memberships WHERE prompt_id=?", values)
            db.executemany("DELETE FROM prompt_overrides WHERE prompt_id=?", values)
            db.executemany("DELETE FROM prompt_assets WHERE prompt_id=?", values)
            self._bump_prompt_revision(db)
        return {"deleted": len(existing), "preview_refs": preview_refs}

    def set_prompt_rating(self, prompt_id: str, rating: int, note: str | None = None) -> dict[str, Any]:
        clean_id = str(prompt_id or "").strip()
        clean_rating = max(0, min(5, int(rating or 0)))
        now = _now()
        with _LOCK, self._connection() as db:
            if not db.execute("SELECT 1 FROM prompt_assets WHERE prompt_id=?", (clean_id,)).fetchone():
                raise ValueError("Prompt record no longer exists")
            existing = db.execute("SELECT note FROM prompt_reviews WHERE prompt_id=?", (clean_id,)).fetchone()
            clean_note = str(note if note is not None else (existing["note"] if existing else ""))
            if clean_rating or clean_note:
                db.execute(
                    """INSERT INTO prompt_reviews(prompt_id, rating, note, updated_at) VALUES (?, ?, ?, ?)
                    ON CONFLICT(prompt_id) DO UPDATE SET rating=excluded.rating, note=excluded.note, updated_at=excluded.updated_at""",
                    (clean_id, clean_rating, clean_note, now),
                )
            else:
                db.execute("DELETE FROM prompt_reviews WHERE prompt_id=?", (clean_id,))
            db.execute(
                """INSERT INTO schema_meta(key, value) VALUES('prompt_revision', '1')
                ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
            )
        return {"prompt_id": clean_id, "rating": clean_rating, "note": clean_note, "updated_at": now}

    def set_prompt_preview(
        self, prompt_id: str, filename: str, source: str = "generated:catalog",
        resolved_seed: int | None = None, resolved_seed_source: str = "",
        source_prompt_snapshot: str = "", resolved_prompt_snapshot: str = "",
        preview_metadata: dict[str, Any] | None = None,
        replace_prompt_snapshots: bool = False,
    ) -> dict[str, Any]:
        clean_id = str(prompt_id or "").strip()
        clean_filename = Path(str(filename or "")).name
        if not clean_id or not clean_filename:
            raise ValueError("Prompt preview requires a prompt ID and filename")
        seed_value: int | None = None
        if resolved_seed is not None:
            try:
                candidate = int(resolved_seed)
            except (TypeError, ValueError):
                candidate = -1
            if 0 <= candidate <= 1125899906842624:
                seed_value = candidate
        now = _now()
        clean_source_prompt = " ".join(str(source_prompt_snapshot or "").split())
        clean_resolved_prompt = " ".join(str(resolved_prompt_snapshot or "").split())
        clean_preview_metadata = {
            str(key): " ".join(str(value or "").split())
            for key, value in (preview_metadata or {}).items()
            if str(key) in {"outfit_a", "outfit_b", "outfit_c", "scene"} and str(value or "").strip()
        }
        preview_metadata_json = json.dumps(clean_preview_metadata, ensure_ascii=False, sort_keys=True)
        with _LOCK, self._connection() as db:
            if seed_value is None:
                cursor = db.execute(
                    """UPDATE prompt_assets SET preview_ref=?, preview_source=?, preview_updated_at=?,
                    source_prompt_snapshot=CASE WHEN ?<>'' THEN ? ELSE source_prompt_snapshot END,
                    resolved_prompt_snapshot=CASE WHEN ?<>'' THEN ? ELSE resolved_prompt_snapshot END,
                    preview_metadata_json=CASE WHEN ?<>'{}' THEN ? ELSE preview_metadata_json END,
                    updated_at=? WHERE prompt_id=?""",
                    (
                        clean_filename, str(source or ""), now,
                        clean_source_prompt, clean_source_prompt,
                        clean_resolved_prompt, clean_resolved_prompt,
                        preview_metadata_json, preview_metadata_json,
                        now, clean_id,
                    ),
                )
            else:
                cursor = db.execute(
                    """UPDATE prompt_assets SET preview_ref=?, preview_source=?, preview_updated_at=?,
                    resolved_seed=?, resolved_seed_source=?,
                    source_prompt_snapshot=CASE WHEN ?<>'' THEN ? ELSE source_prompt_snapshot END,
                    resolved_prompt_snapshot=CASE WHEN ?<>'' THEN ? ELSE resolved_prompt_snapshot END,
                    preview_metadata_json=CASE WHEN ?<>'{}' THEN ? ELSE preview_metadata_json END,
                    updated_at=? WHERE prompt_id=?""",
                    (
                        clean_filename, str(source or ""), now, seed_value, str(resolved_seed_source or ""),
                        clean_source_prompt, clean_source_prompt,
                        clean_resolved_prompt, clean_resolved_prompt,
                        preview_metadata_json, preview_metadata_json,
                        now, clean_id,
                    ),
                )
            if replace_prompt_snapshots:
                db.execute("UPDATE prompt_assets SET source_prompt_snapshot=?,resolved_prompt_snapshot=?,preview_metadata_json=? WHERE prompt_id=?", (clean_source_prompt, clean_resolved_prompt, preview_metadata_json, clean_id))
            if not cursor.rowcount:
                raise ValueError("Prompt record no longer exists")
            db.execute(
                """INSERT INTO schema_meta(key, value) VALUES('prompt_revision', '1')
                ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
            )
            row = db.execute(
                """SELECT prompt_id, preview_ref, preview_source, preview_updated_at,
                resolved_seed, resolved_seed_source, source_prompt_snapshot,
                resolved_prompt_snapshot, preview_metadata_json, updated_at FROM prompt_assets WHERE prompt_id=?""",
                (clean_id,),
            ).fetchone()
        output = dict(row)
        try:
            output["preview_metadata"] = json.loads(str(output.pop("preview_metadata_json", "{}") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            output["preview_metadata"] = {}
        return output

    def clear_prompt_previews(self, prompt_ids: list[str]) -> list[dict[str, Any]]:
        ids = list(dict.fromkeys(str(value or "").strip() for value in prompt_ids if str(value or "").strip()))
        if not ids:
            return []
        now = _now()
        placeholders = ",".join("?" for _ in ids)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"SELECT prompt_id, preview_ref FROM prompt_assets WHERE prompt_id IN ({placeholders})",
                ids,
            ).fetchall()
            if rows:
                db.executemany(
                    "UPDATE prompt_assets SET preview_ref='', preview_source='', preview_updated_at='', preview_metadata_json='{}', updated_at=? WHERE prompt_id=?",
                    [(now, str(row["prompt_id"])) for row in rows],
                )
                self._bump_prompt_revision(db)
        return [{"prompt_id": str(row["prompt_id"]), "removed_preview_ref": str(row["preview_ref"] or "")} for row in rows]

    def clear_prompt_preview(self, prompt_id: str) -> dict[str, Any] | None:
        rows = self.clear_prompt_previews([prompt_id])
        return rows[0] if rows else None

    def edit_prompt_asset_text(self, prompt_id: str, value: str, *, copy_only: bool = False) -> dict[str, Any]:
        clean_id = str(prompt_id or "").strip()
        clean_value = " ".join(str(value or "").split())
        if not clean_id:
            raise ValueError("Prompt ID is required")
        if not clean_value:
            raise ValueError("Prompt text is required")
        now = _now()
        with _LOCK, self._connection() as db:
            row = db.execute(
                "SELECT * FROM prompt_assets WHERE prompt_id=?",
                (clean_id,),
            ).fetchone()
            if row is None:
                raise ValueError("Prompt record no longer exists")
            duplicate = db.execute(
                "SELECT prompt_id FROM prompt_assets WHERE value=? COLLATE NOCASE AND prompt_id<>?",
                (clean_value, clean_id),
            ).fetchone()
            if duplicate is not None:
                raise ValueError("Another saved Prompt already uses that exact text")
            current = dict(row)
            facets_json = current.get("facets_json") or "{}"
            if copy_only:
                new_id = f"imported:{uuid.uuid4().hex}"
                db.execute(
                    """INSERT INTO prompt_assets(
                    prompt_id, kind, value, placeholder_signature, primary_parent, primary_subcategory,
                    facets_json, quality_score, exact_source_occurrences, near_cluster_id, preview_ref,
                    preview_source, preview_updated_at, resolved_seed, resolved_seed_source,
                    source_prompt_snapshot, resolved_prompt_snapshot, is_custom,
                    source_count, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)""",
                    (
                        new_id, str(current.get("kind") or "prompt"), clean_value, str(current.get("placeholder_signature") or ""),
                        str(current.get("primary_parent") or "Other"), str(current.get("primary_subcategory") or "General"),
                        str(facets_json), float(current.get("quality_score") or 0), int(current.get("exact_source_occurrences") or 0),
                        str(current.get("near_cluster_id") or ""), str(current.get("preview_ref") or ""), str(current.get("preview_source") or ""),
                        str(current.get("preview_updated_at") or ""), int(current.get("resolved_seed") or -1), str(current.get("resolved_seed_source") or ""),
                        str(current.get("source_prompt_snapshot") or ""), str(current.get("resolved_prompt_snapshot") or ""),
                        int(current.get("source_count") or 0), now, now,
                    ),
                )
                sources = db.execute(
                    "SELECT source_path, line_number, source_label FROM prompt_sources WHERE prompt_id=?",
                    (clean_id,),
                ).fetchall()
                if sources:
                    db.executemany(
                        "INSERT OR IGNORE INTO prompt_sources(prompt_id, source_path, line_number, source_label, created_at) VALUES (?, ?, ?, ?, ?)",
                        [(new_id, str(src["source_path"]), int(src["line_number"] or 0), str(src["source_label"] or ""), now) for src in sources],
                    )
                memberships = db.execute(
                    "SELECT collection_id FROM prompt_showcase_memberships WHERE prompt_id=?",
                    (clean_id,),
                ).fetchall()
                if memberships:
                    db.executemany(
                        "INSERT OR IGNORE INTO prompt_showcase_memberships(prompt_id, collection_id, created_at) VALUES (?, ?, ?)",
                        [(new_id, str(item["collection_id"]), now) for item in memberships],
                    )
                review = db.execute(
                    "SELECT rating, note FROM prompt_reviews WHERE prompt_id=?",
                    (clean_id,),
                ).fetchone()
                if review and (int(review["rating"] or 0) or str(review["note"] or "")):
                    db.execute(
                        "INSERT INTO prompt_reviews(prompt_id, rating, note, updated_at) VALUES (?, ?, ?, ?)",
                        (new_id, int(review["rating"] or 0), str(review["note"] or ""), now),
                    )
                target_id = new_id
            else:
                db.execute(
                    "UPDATE prompt_assets SET value=?, updated_at=?, is_custom=1 WHERE prompt_id=?",
                    (clean_value, now, clean_id),
                )
                target_id = clean_id
            self._bump_prompt_revision(db)
            row = db.execute(
                "SELECT prompt_id, kind, value, primary_parent, primary_subcategory, updated_at FROM prompt_assets WHERE prompt_id=?",
                (target_id,),
            ).fetchone()
        return dict(row) | {"created_copy": bool(copy_only)}

    @staticmethod
    def _clean_prompt_ids(prompt_ids: list[str] | tuple[str, ...] | set[str]) -> list[str]:
        return list(dict.fromkeys(str(value or "").strip() for value in prompt_ids if str(value or "").strip()))

    def prompt_override_map(self, prompt_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, dict[str, Any]]:
        """Return UI overrides for persisted or recipe-derived prompt IDs."""
        ids = self._clean_prompt_ids(prompt_ids)
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"SELECT prompt_id, primary_parent, primary_subcategory, home_override, archived, updated_at FROM prompt_overrides WHERE prompt_id IN ({placeholders})",
                ids,
            ).fetchall()
        return {str(row["prompt_id"]): dict(row) for row in rows}

    def set_prompt_home(self, prompt_ids: list[str] | tuple[str, ...] | set[str], parent: str, subcategory: str) -> int:
        ids = self._clean_prompt_ids(prompt_ids)
        clean_parent = " ".join(str(parent or "").split())
        clean_subcategory = " ".join(str(subcategory or "").split())
        if not ids or not clean_parent:
            raise ValueError("Choose at least one Prompt and a Category")
        now = _now()
        rows = [(prompt_id, clean_parent, clean_subcategory, 1, 0, now) for prompt_id in ids]
        with _LOCK, self._connection() as db:
            db.executemany(
                """INSERT INTO prompt_overrides(prompt_id, primary_parent, primary_subcategory, home_override, archived, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(prompt_id) DO UPDATE SET primary_parent=excluded.primary_parent,
                primary_subcategory=excluded.primary_subcategory, home_override=1, updated_at=excluded.updated_at""",
                rows,
            )
            self._bump_prompt_revision(db)
        return len(rows)

    def clear_prompt_home(self, prompt_ids: list[str] | tuple[str, ...] | set[str]) -> int:
        ids = self._clean_prompt_ids(prompt_ids)
        if not ids:
            return 0
        now = _now()
        rows = [(prompt_id, "", "", 0, 0, now) for prompt_id in ids]
        with _LOCK, self._connection() as db:
            db.executemany(
                """INSERT INTO prompt_overrides(prompt_id, primary_parent, primary_subcategory, home_override, archived, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(prompt_id) DO UPDATE SET primary_parent='', primary_subcategory='',
                home_override=0, updated_at=excluded.updated_at""",
                rows,
            )
            self._bump_prompt_revision(db)
        return len(rows)

    def set_prompt_archived(self, prompt_ids: list[str] | tuple[str, ...] | set[str], archived: bool = True) -> int:
        ids = self._clean_prompt_ids(prompt_ids)
        if not ids:
            return 0
        now = _now()
        rows = [(prompt_id, "", "", 0, int(bool(archived)), now) for prompt_id in ids]
        with _LOCK, self._connection() as db:
            db.executemany(
                """INSERT INTO prompt_overrides(prompt_id, primary_parent, primary_subcategory, home_override, archived, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(prompt_id) DO UPDATE SET archived=excluded.archived, updated_at=excluded.updated_at""",
                rows,
            )
            self._bump_prompt_revision(db)
        return len(rows)

    def delete_prompt_assets(self, prompt_ids: list[str] | tuple[str, ...] | set[str]) -> dict[str, int]:
        """Hard-delete custom rows and archive canonical or recipe-derived records."""
        ids = self._clean_prompt_ids(prompt_ids)
        if not ids:
            return {"deleted": 0, "archived": 0}
        placeholders = ",".join("?" for _ in ids)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"SELECT prompt_id, is_custom FROM prompt_assets WHERE prompt_id IN ({placeholders})", ids
            ).fetchall()
            found = {str(row["prompt_id"]): bool(row["is_custom"]) for row in rows}
            custom = [prompt_id for prompt_id in ids if found.get(prompt_id) is True]
            canonical = [prompt_id for prompt_id in ids if prompt_id in found and not found[prompt_id]]
            synthetic = [prompt_id for prompt_id in ids if prompt_id not in found]
            if custom:
                values = [(prompt_id,) for prompt_id in custom]
                db.executemany("DELETE FROM prompt_showcase_memberships WHERE prompt_id=?", values)
                db.executemany("DELETE FROM prompt_collection_memberships WHERE prompt_id=?", values)
                db.executemany("DELETE FROM fragment_prompt_memberships WHERE prompt_id=?", values)
                db.executemany("DELETE FROM prompt_overrides WHERE prompt_id=?", values)
                db.executemany("DELETE FROM prompt_assets WHERE prompt_id=?", values)
            archive_ids = canonical + synthetic
            if archive_ids:
                now = _now()
                db.executemany(
                    """INSERT INTO prompt_overrides(prompt_id, primary_parent, primary_subcategory, home_override, archived, updated_at)
                    VALUES (?, '', '', 0, 1, ?)
                    ON CONFLICT(prompt_id) DO UPDATE SET archived=1, updated_at=excluded.updated_at""",
                    [(prompt_id, now) for prompt_id in archive_ids],
                )
            if custom or archive_ids:
                self._bump_prompt_revision(db)
        return {"deleted": len(custom), "archived": len(archive_ids)}

    def purge_prompt_library(self, kind: str) -> dict[str, Any]:
        """Hard-reset one Prompt/Template gallery without touching other tabs."""
        clean_kind = str(kind or "").strip().casefold()
        if clean_kind not in {"prompt", "template"}:
            raise ValueError("Library kind must be prompt or template")
        with _LOCK, self._connection() as db:
            rows = db.execute(
                "SELECT prompt_id, preview_ref FROM prompt_assets WHERE kind=?",
                (clean_kind,),
            ).fetchall()
            prompt_ids = [str(row["prompt_id"]) for row in rows]
            preview_refs = list(dict.fromkeys(
                Path(str(row["preview_ref"] or "")).name
                for row in rows if Path(str(row["preview_ref"] or "")).name
            ))
            collections_deleted = 0
            removable = [str(row[0]) for row in db.execute(
                "SELECT collection_id FROM prompt_showcase_collections WHERE kind=?", (clean_kind,),
            ).fetchall()]
            if removable:
                db.executemany(
                    "DELETE FROM prompt_showcase_collections WHERE collection_id=?",
                    [(value,) for value in removable],
                )
                collections_deleted = len(removable)
            db.execute(
                "DELETE FROM prompt_overrides WHERE prompt_id IN (SELECT prompt_id FROM prompt_assets WHERE kind=?)",
                (clean_kind,),
            )
            deleted = int(db.execute("DELETE FROM prompt_assets WHERE kind=?", (clean_kind,)).rowcount or 0)
            db.execute("DELETE FROM prompt_index_files")
            db.execute("DELETE FROM schema_meta WHERE key IN ('prompt_index_signature','fragment_index_signature')")
            db.execute("DELETE FROM schema_meta WHERE key=?", (self._structure_order_key(clean_kind),))
            self._bump_prompt_revision(db)
        return {
            "kind": clean_kind,
            "assets": deleted,
            "prompt_ids": prompt_ids,
            "preview_refs": preview_refs,
            "collections_deleted": collections_deleted,
        }

    def import_prompt_asset(self, item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        value = " ".join(str(item.get("value") or "").split())
        if not value:
            raise ValueError("Imported Prompt text is required")
        signature = _creative_prompt_signature(value)
        kind = "template" if signature else "prompt"
        parent = " ".join(str(item.get("primary_parent") or item.get("parent") or "Imported").split()) or "Imported"
        if "primary_subcategory" in item or "subcategory" in item:
            subcategory = " ".join(str(item.get("primary_subcategory") if "primary_subcategory" in item else item.get("subcategory") or "").split())
        else:
            subcategory = "Imported Catalog"
        facets = item.get("facets") if isinstance(item.get("facets"), dict) else {}
        now = _now()
        with _LOCK, self._connection() as db:
            existing = db.execute("SELECT prompt_id FROM prompt_assets WHERE value=? COLLATE NOCASE", (value,)).fetchone()
            if existing is not None:
                return {"prompt_id": str(existing["prompt_id"]), "value": value}, False
            prompt_id = f"imported:{uuid.uuid4().hex}"
            db.execute(
                """INSERT INTO prompt_assets(prompt_id, kind, value, placeholder_signature, primary_parent, primary_subcategory,
                facets_json, quality_score, exact_source_occurrences, near_cluster_id, preview_ref, preview_source,
                preview_updated_at, is_custom, source_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, '', '', 'imported:catalog', '', 1, 0, ?, ?)""",
                (prompt_id, kind, value, signature, parent, subcategory, json.dumps(facets, ensure_ascii=False, sort_keys=True), now, now),
            )
            self._bump_prompt_revision(db)
        return {"prompt_id": prompt_id, "value": value}, True

    def import_prompt_assets(
        self,
        items: list[dict[str, Any]],
        *,
        parent: str,
        subcategory: str,
        kind: str = "prompt",
        collection_ids: list[str] | None = None,
        source_path: str = "",
        source_label: str = "",
    ) -> dict[str, Any]:
        """Atomically import or re-home a curated Prompt or Template batch.

        Exact text matches reuse the existing canonical record.  The selected
        catalog home is written as a durable manual override for both matched
        and newly created rows, while Collection membership remains an
        independent many-to-many layer.
        """
        clean_parent = " ".join(str(parent or "").split())
        clean_subcategory = " ".join(str(subcategory or "").split())
        clean_kind = self._clean_prompt_showcase_kind(kind)
        if not clean_parent:
            raise ValueError("Choose a Category")
        requested_collections = list(dict.fromkeys(
            str(value or "").strip() for value in collection_ids or [] if str(value or "").strip()
        ))
        clean_source_path = str(source_path or "").replace("\\", "/").strip()
        clean_source_label = " ".join(str(source_label or "").split()) or (Path(clean_source_path).stem if clean_source_path else "")
        prepared: list[dict[str, Any]] = []
        inferred_kinds: set[str] = set()
        seen_values: set[str] = set()
        input_duplicates = 0
        for item in items or []:
            value = " ".join(str((item or {}).get("value") or "").split())
            key = value.casefold()
            if not value:
                continue
            if key in seen_values:
                input_duplicates += 1
                continue
            seen_values.add(key)
            try:
                source_line = max(0, int((item or {}).get("source_line") or 0))
            except (TypeError, ValueError):
                source_line = 0
            signature = _creative_prompt_signature(value)
            inferred_kind = "template" if signature else "prompt"
            inferred_kinds.add(inferred_kind)
            prepared.append({
                "value": value,
                "source_line": source_line,
                "placeholder_signature": signature,
                "facets_json": json.dumps(
                    (item or {}).get("facets") if isinstance((item or {}).get("facets"), dict) else {},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            })
        if not prepared:
            raise ValueError(f"Add at least one unique {clean_kind.title()} line")
        if len(inferred_kinds) != 1:
            raise ValueError("Split mixed Prompt / Template values into separate import batches")
        clean_kind = next(iter(inferred_kinds))

        now = _now()
        created: list[str] = []
        matched: list[str] = []
        touched: list[str] = []
        source_rows: list[tuple[str, int]] = []
        with _LOCK, self._connection() as db:
            self._validate_prompt_showcase_collection_ids(db, requested_collections, clean_kind)
            existing = {
                str(row["value"] or "").casefold(): str(row["prompt_id"])
                for row in db.execute("SELECT prompt_id, value FROM prompt_assets")
            }
            for item in prepared:
                prompt_id = existing.get(item["value"].casefold())
                if prompt_id:
                    matched.append(prompt_id)
                    db.execute(
                        "UPDATE prompt_assets SET kind=?, placeholder_signature=?, updated_at=? WHERE prompt_id=?",
                        (clean_kind, item["placeholder_signature"], now, prompt_id),
                    )
                else:
                    prompt_id = f"imported:{uuid.uuid4().hex}"
                    db.execute(
                        """INSERT INTO prompt_assets(
                        prompt_id, kind, value, placeholder_signature, primary_parent, primary_subcategory,
                        facets_json, quality_score, exact_source_occurrences, near_cluster_id, preview_ref,
                        preview_source, preview_updated_at, is_custom, source_count, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, '', '', 'imported:catalog', '', 1, 0, ?, ?)""",
                        (
                            prompt_id, clean_kind, item["value"], item["placeholder_signature"], clean_parent, clean_subcategory,
                            item["facets_json"], now, now,
                        ),
                    )
                    existing[item["value"].casefold()] = prompt_id
                    created.append(prompt_id)
                touched.append(prompt_id)
                if clean_source_path and int(item.get("source_line") or 0) > 0:
                    source_rows.append((prompt_id, int(item.get("source_line") or 0)))

            db.executemany(
                """INSERT INTO prompt_overrides(prompt_id, primary_parent, primary_subcategory, home_override, archived, updated_at)
                VALUES (?, ?, ?, 1, 0, ?)
                ON CONFLICT(prompt_id) DO UPDATE SET primary_parent=excluded.primary_parent,
                primary_subcategory=excluded.primary_subcategory, home_override=1, archived=0, updated_at=excluded.updated_at""",
                [(prompt_id, clean_parent, clean_subcategory, now) for prompt_id in touched],
            )
            memberships_added = 0
            if requested_collections:
                cursor = db.executemany(
                    "INSERT OR IGNORE INTO prompt_showcase_memberships(prompt_id, collection_id, created_at) VALUES (?, ?, ?)",
                    [
                        (prompt_id, collection_id, now)
                        for prompt_id in touched
                        for collection_id in requested_collections
                    ],
                )
                memberships_added = max(0, int(cursor.rowcount or 0))
            source_links_added = 0
            if clean_source_path and source_rows:
                cursor = db.executemany(
                    "INSERT OR IGNORE INTO prompt_sources(prompt_id, source_path, line_number, source_label, created_at) VALUES (?, ?, ?, ?, ?)",
                    [(prompt_id, clean_source_path, line_number, clean_source_label, now) for prompt_id, line_number in source_rows],
                )
                source_links_added = max(0, int(cursor.rowcount or 0))
                db.executemany(
                    "UPDATE prompt_assets SET source_count=(SELECT COUNT(*) FROM prompt_sources WHERE prompt_id=?), exact_source_occurrences=(SELECT COUNT(*) FROM prompt_sources WHERE prompt_id=?), updated_at=? WHERE prompt_id=?",
                    [(prompt_id, prompt_id, now, prompt_id) for prompt_id in dict.fromkeys(prompt_id for prompt_id, _ in source_rows)],
                )
            self._bump_prompt_revision(db)
        return {
            "submitted": len(items or []),
            "unique": len(prepared),
            "created": len(created),
            "matched": len(matched),
            "input_duplicates": input_duplicates,
            "homes_updated": len(touched),
            "collections": len(requested_collections),
            "memberships_added": memberships_added,
            "source_links_added": source_links_added,
            "source_path": clean_source_path,
            "source_label": clean_source_label,
            "kind": clean_kind,
            "prompt_ids": touched,
        }

    @staticmethod
    def _bump_prompt_revision(db: sqlite3.Connection) -> None:
        db.execute(
            """INSERT INTO schema_meta(key, value) VALUES('prompt_revision', '1')
            ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
        )

    @staticmethod
    def _bump_recipe_revision(db: sqlite3.Connection) -> None:
        db.execute(
            """INSERT INTO schema_meta(key, value) VALUES('recipe_revision', '1')
            ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
        )

    @staticmethod
    def _bump_fragment_revision(db: sqlite3.Connection) -> None:
        db.execute(
            """INSERT INTO schema_meta(key, value) VALUES('fragment_revision', '1')
            ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
        )

    @staticmethod
    def _bump_component_revision(db: sqlite3.Connection) -> None:
        db.execute(
            """INSERT INTO schema_meta(key, value) VALUES('component_revision', '1')
            ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
        )

    def prompt_showcase_collections(self, kind: str) -> list[dict[str, Any]]:
        clean_kind = self._clean_prompt_showcase_kind(kind)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT c.collection_id, c.kind, c.name, c.color, c.created_at, c.updated_at,
                COUNT(m.prompt_id) AS prompt_count
                FROM prompt_showcase_collections c
                LEFT JOIN prompt_showcase_memberships m ON m.collection_id=c.collection_id
                WHERE c.kind=?
                GROUP BY c.collection_id
                ORDER BY c.name COLLATE NOCASE""",
                (clean_kind,),
            ).fetchall()
        output = [dict(row) for row in rows]
        order = self.creative_structure_order(clean_kind).get("showcase_collections", [])
        order_index = {str(value): index for index, value in enumerate(order if isinstance(order, list) else [])}
        output.sort(key=lambda row: (
            order_index.get(str(row.get("collection_id") or ""), 10**9),
            str(row.get("name") or "").casefold(),
        ))
        return output

    def create_prompt_showcase_collection(self, kind: str, name: str) -> dict[str, Any]:
        clean_kind = self._clean_prompt_showcase_kind(kind)
        clean_name = " ".join(str(name or "").split())
        if not clean_name:
            raise ValueError("Collection name is required")
        if len(clean_name) > 80:
            raise ValueError("Collection names are limited to 80 characters")
        now = _now()
        collection_id = f"prompt-showcase:{clean_kind}:{uuid.uuid4().hex}"
        with _LOCK, self._connection() as db:
            color = RECIPE_COLLECTION_COLORS[
                int(db.execute(
                    "SELECT COUNT(*) FROM prompt_showcase_collections WHERE kind=?", (clean_kind,),
                ).fetchone()[0]) % len(RECIPE_COLLECTION_COLORS)
            ]
            try:
                db.execute(
                    """INSERT INTO prompt_showcase_collections(
                    collection_id, kind, name, color, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)""",
                    (collection_id, clean_kind, clean_name, color, now, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"A {clean_kind} Collection named '{clean_name}' already exists") from error
            self._bump_prompt_revision(db)
        return {
            "collection_id": collection_id, "kind": clean_kind, "name": clean_name,
            "color": color, "created_at": now, "updated_at": now, "prompt_count": 0,
        }

    def update_prompt_showcase_collection(self, collection_id: str, *, name: str) -> dict[str, Any]:
        clean_id = str(collection_id or "").strip()
        clean_name = " ".join(str(name or "").split())
        if not clean_id or not clean_name:
            raise ValueError("Collection and name are required")
        if len(clean_name) > 80:
            raise ValueError("Collection names are limited to 80 characters")
        with _LOCK, self._connection() as db:
            current = db.execute(
                "SELECT * FROM prompt_showcase_collections WHERE collection_id=?", (clean_id,),
            ).fetchone()
            if current is None:
                raise ValueError("Collection no longer exists")
            try:
                db.execute(
                    "UPDATE prompt_showcase_collections SET name=?, updated_at=? WHERE collection_id=?",
                    (clean_name, _now(), clean_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"A {current['kind']} Collection named '{clean_name}' already exists") from error
            self._bump_prompt_revision(db)
            row = db.execute(
                """SELECT c.collection_id, c.kind, c.name, c.color, c.created_at, c.updated_at,
                COUNT(m.prompt_id) AS prompt_count
                FROM prompt_showcase_collections c
                LEFT JOIN prompt_showcase_memberships m ON m.collection_id=c.collection_id
                WHERE c.collection_id=? GROUP BY c.collection_id""",
                (clean_id,),
            ).fetchone()
        return dict(row)

    def delete_prompt_showcase_collection(self, collection_id: str) -> bool:
        with _LOCK, self._connection() as db:
            result = db.execute(
                "DELETE FROM prompt_showcase_collections WHERE collection_id=?", (str(collection_id),),
            )
            if result.rowcount:
                self._bump_prompt_revision(db)
        return result.rowcount > 0

    def recipe_collections(self) -> list[dict[str, Any]]:
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT c.collection_id, c.name, c.color, c.created_at, c.updated_at,
                COUNT(m.recipe_id) AS recipe_count,
                (SELECT COUNT(*) FROM prompt_collection_memberships p WHERE p.collection_id=c.collection_id) AS prompt_count
                FROM recipe_collections c
                LEFT JOIN recipe_collection_memberships m ON m.collection_id=c.collection_id
                GROUP BY c.collection_id
                ORDER BY c.name COLLATE NOCASE"""
            ).fetchall()
        output = [dict(row) for row in rows]
        order = self.creative_structure_order("recipe").get("collections", [])
        order_index = {str(value): index for index, value in enumerate(order if isinstance(order, list) else [])}
        output.sort(key=lambda row: (order_index.get(str(row.get("collection_id") or ""), 10**9), str(row.get("name") or "").casefold()))
        return output

    def create_recipe_collection(self, name: str) -> dict[str, Any]:
        clean_name = " ".join(str(name or "").split())
        if not clean_name:
            raise ValueError("Collection name is required")
        if len(clean_name) > 80:
            raise ValueError("Collection names are limited to 80 characters")
        now = _now()
        collection_id = f"recipe-collection:{uuid.uuid4().hex}"
        with _LOCK, self._connection() as db:
            color = RECIPE_COLLECTION_COLORS[
                int(db.execute("SELECT COUNT(*) FROM recipe_collections").fetchone()[0]) % len(RECIPE_COLLECTION_COLORS)
            ]
            try:
                db.execute(
                    "INSERT INTO recipe_collections(collection_id, name, color, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (collection_id, clean_name, color, now, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"A collection named '{clean_name}' already exists") from error
            self._bump_prompt_revision(db)
            self._bump_recipe_revision(db)
        return {"collection_id": collection_id, "name": clean_name, "color": color, "created_at": now, "updated_at": now, "recipe_count": 0}

    def update_recipe_collection(self, collection_id: str, *, name: str) -> dict[str, Any]:
        clean_id = str(collection_id or "").strip()
        clean_name = " ".join(str(name or "").split())
        if not clean_id:
            raise ValueError("Collection ID is required")
        if not clean_name:
            raise ValueError("Collection name is required")
        if len(clean_name) > 80:
            raise ValueError("Collection names are limited to 80 characters")
        with _LOCK, self._connection() as db:
            current = db.execute("SELECT * FROM recipe_collections WHERE collection_id=?", (clean_id,)).fetchone()
            if current is None:
                raise ValueError("Collection no longer exists")
            try:
                db.execute("UPDATE recipe_collections SET name=?, updated_at=? WHERE collection_id=?", (clean_name, _now(), clean_id))
            except sqlite3.IntegrityError as error:
                raise ValueError(f"A collection named '{clean_name}' already exists") from error
            self._bump_prompt_revision(db)
            self._bump_recipe_revision(db)
            row = db.execute(
                """SELECT c.collection_id, c.name, c.color, c.created_at, c.updated_at,
                (SELECT COUNT(*) FROM recipe_collection_memberships m WHERE m.collection_id=c.collection_id) AS recipe_count,
                (SELECT COUNT(*) FROM prompt_collection_memberships p WHERE p.collection_id=c.collection_id) AS prompt_count
                FROM recipe_collections c WHERE c.collection_id=?""",
                (clean_id,),
            ).fetchone()
        return dict(row) if row else {"collection_id": clean_id, "name": clean_name}

    def delete_recipe_collection(self, collection_id: str) -> bool:
        with _LOCK, self._connection() as db:
            result = db.execute("DELETE FROM recipe_collections WHERE collection_id=?", (str(collection_id),))
            if result.rowcount:
                self._bump_prompt_revision(db)
                self._bump_recipe_revision(db)
        return result.rowcount > 0

    def set_recipe_collections(self, recipe_id: str, collection_ids: list[str]) -> list[dict[str, str]]:
        requested = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        with _LOCK, self._connection() as db:
            exists = db.execute("SELECT 1 FROM recipes WHERE recipe_id=?", (str(recipe_id),)).fetchone()
            if exists is None:
                raise ValueError("Recipe no longer exists")
            if requested:
                placeholders = ",".join("?" for _ in requested)
                rows = db.execute(
                    f"SELECT collection_id, name, color FROM recipe_collections WHERE collection_id IN ({placeholders})",
                    requested,
                ).fetchall()
                found = {str(row["collection_id"]) for row in rows}
                missing = [value for value in requested if value not in found]
                if missing:
                    raise ValueError("One or more selected collections no longer exist")
            else:
                rows = []
            db.execute("DELETE FROM recipe_collection_memberships WHERE recipe_id=?", (str(recipe_id),))
            now = _now()
            db.executemany(
                "INSERT INTO recipe_collection_memberships(recipe_id, collection_id, created_at) VALUES (?, ?, ?)",
                [(str(recipe_id), collection_id, now) for collection_id in requested],
            )
        selected = {str(row["collection_id"]): row for row in rows}
        return [
            {"collection_id": value, "name": str(selected[value]["name"]), "color": str(selected[value]["color"])}
            for value in requested
        ]

    def add_recipes_to_collections(self, recipe_ids: list[str], collection_ids: list[str]) -> dict[str, int]:
        requested_recipes = list(dict.fromkeys(str(value) for value in recipe_ids if str(value)))
        requested_collections = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        if not requested_recipes:
            raise ValueError("Select at least one recipe")
        if not requested_collections:
            raise ValueError("Select at least one collection")

        with _LOCK, self._connection() as db:
            recipe_placeholders = ",".join("?" for _ in requested_recipes)
            existing_recipes = {
                str(row[0])
                for row in db.execute(
                    f"SELECT recipe_id FROM recipes WHERE recipe_id IN ({recipe_placeholders})",
                    requested_recipes,
                ).fetchall()
            }
            missing_recipes = [value for value in requested_recipes if value not in existing_recipes]
            if missing_recipes:
                raise ValueError("One or more selected recipes no longer exist")

            collection_placeholders = ",".join("?" for _ in requested_collections)
            existing_collections = {
                str(row[0])
                for row in db.execute(
                    f"SELECT collection_id FROM recipe_collections WHERE collection_id IN ({collection_placeholders})",
                    requested_collections,
                ).fetchall()
            }
            missing_collections = [value for value in requested_collections if value not in existing_collections]
            if missing_collections:
                raise ValueError("One or more selected collections no longer exist")

            now = _now()
            cursor = db.executemany(
                "INSERT OR IGNORE INTO recipe_collection_memberships(recipe_id, collection_id, created_at) VALUES (?, ?, ?)",
                [
                    (recipe_id, collection_id, now)
                    for recipe_id in requested_recipes
                    for collection_id in requested_collections
                ],
            )
            added = max(0, int(cursor.rowcount or 0))

        return {
            "recipes": len(requested_recipes),
            "collections": len(requested_collections),
            "memberships_added": int(added),
        }

    def delete_recipes(self, recipe_ids: list[str]) -> int:
        requested = list(dict.fromkeys(str(value) for value in recipe_ids if str(value)))
        if not requested:
            return 0
        placeholders = ",".join("?" for _ in requested)
        with _LOCK, self._connection() as db:
            existing = int(
                db.execute(
                    f"SELECT COUNT(*) FROM recipes WHERE recipe_id IN ({placeholders})",
                    requested,
                ).fetchone()[0]
            )
            db.execute(
                f"DELETE FROM recipe_collection_memberships WHERE recipe_id IN ({placeholders})",
                requested,
            )
            db.execute(
                f"DELETE FROM recipes WHERE recipe_id IN ({placeholders})",
                requested,
            )
        return existing

    def creative_boards(self) -> list[dict[str, Any]]:
        """Return reusable Prompt Builder workspaces, newest first."""
        with _LOCK, self._connection() as db:
            rows = db.execute(
                "SELECT board_id, name, payload_json, created_at, updated_at FROM creative_boards ORDER BY updated_at DESC, board_id"
            ).fetchall()
        output: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row["payload_json"] or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
            output.append({
                "board_id": str(row["board_id"]),
                "name": str(row["name"]),
                "payload": payload if isinstance(payload, dict) else {},
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
            })
        return output

    def save_creative_board(self, board_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean_name = " ".join(str(name or "").split())
        if not clean_name:
            raise ValueError("Board name is required")
        if len(clean_name) > 100:
            raise ValueError("Board names are limited to 100 characters")
        if not isinstance(payload, dict):
            raise ValueError("Board payload must be an object")
        encoded = json.dumps(payload, sort_keys=True)
        if len(encoded.encode("utf-8")) > 256 * 1024:
            raise ValueError("Board payload is limited to 256 KB")
        clean_id = str(board_id or "").strip() or f"creative-board:{uuid.uuid4().hex}"
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO creative_boards(board_id, name, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(board_id) DO UPDATE SET
                    name=excluded.name,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at""",
                (clean_id, clean_name, encoded, now, now),
            )
            row = db.execute(
                "SELECT board_id, name, payload_json, created_at, updated_at FROM creative_boards WHERE board_id=?",
                (clean_id,),
            ).fetchone()
        return {
            "board_id": str(row["board_id"]),
            "name": str(row["name"]),
            "payload": json.loads(str(row["payload_json"] or "{}")),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }

    def delete_creative_board(self, board_id: str) -> bool:
        with _LOCK, self._connection() as db:
            result = db.execute("DELETE FROM creative_boards WHERE board_id=?", (str(board_id or ""),))
        return result.rowcount > 0

    @staticmethod
    def fragment_id(role: str, value: str) -> str:
        clean_role = str(role or "").strip().lower()
        clean_value = " ".join(str(value or "").split()).casefold()
        digest = hashlib.sha1(f"{clean_role}\0{clean_value}".encode("utf-8")).hexdigest()
        return f"fragment:{clean_role}:{digest}"

    def replace_mined_fragments(self, assets: list[dict[str, Any]], *, signature: str) -> dict[str, int]:
        """Atomically refresh mined fragments while preserving human review.

        Mined rows are a disposable index over canonical prompts. Review state,
        ratings, and manually created rows survive every miner revision.
        """
        now = _now()
        clean_assets: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for item in assets:
            role = str(item.get("role") or "").strip().lower()
            value = " ".join(str(item.get("value") or "").split())
            if not role or not value:
                continue
            fragment_id = str(item.get("fragment_id") or self.fragment_id(role, value)).strip()
            if not fragment_id or fragment_id in seen_ids:
                continue
            seen_ids.add(fragment_id)
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence") or 0)))
                preferred_position = int(item.get("preferred_position") or 50)
            except (TypeError, ValueError):
                confidence, preferred_position = 0.0, 50
            review_state = str(item.get("review_state") or "suggested").strip().lower()
            if review_state not in {"approved", "suggested", "review", "rejected"}:
                review_state = "review"
            prompt_ids = list(dict.fromkeys(str(value or "").strip() for value in item.get("source_prompt_ids") or [] if str(value or "").strip()))
            source_files: list[dict[str, Any]] = []
            file_seen: set[tuple[str, int, str]] = set()
            for source in item.get("source_files") or []:
                if isinstance(source, str):
                    source = {"source_path": source}
                if not isinstance(source, dict):
                    continue
                source_path = str(source.get("source_path") or source.get("path") or "").replace("\\", "/").strip()
                try:
                    line_number = max(0, int(source.get("line_number") or 0))
                except (TypeError, ValueError):
                    line_number = 0
                source_type = str(source.get("source_type") or "prompt-log").strip().lower() or "prompt-log"
                key = (source_path, line_number, source_type)
                if not source_path or key in file_seen:
                    continue
                file_seen.add(key)
                source_files.append({"source_path": source_path, "line_number": line_number, "source_type": source_type})
            conflicts = list(dict.fromkeys(str(value or "").strip() for value in item.get("conflict_tags") or [] if str(value or "").strip()))
            clean_assets.append({
                "fragment_id": fragment_id,
                "role": role,
                "mined_role": role,
                "value": value,
                "family_id": str(item.get("family_id") or ""),
                "join_mode": str(item.get("join_mode") or "sentence"),
                "preferred_position": preferred_position,
                "placeholder_signature": str(item.get("placeholder_signature") or ""),
                "confidence": confidence,
                "review_state": review_state,
                "source_kind": str(item.get("source_kind") or "mined"),
                "prompt_ids": prompt_ids,
                "source_files": source_files,
                "multiple_allowed": 1 if item.get("multiple_allowed", True) else 0,
                "conflict_tags_json": json.dumps(conflicts, ensure_ascii=False),
            })

        with _LOCK, self._connection() as db:
            db.execute("CREATE TEMP TABLE IF NOT EXISTS solo_fragment_seen(fragment_id TEXT PRIMARY KEY)")
            db.execute("DELETE FROM solo_fragment_seen")
            if clean_assets:
                db.executemany(
                    "INSERT OR IGNORE INTO solo_fragment_seen(fragment_id) VALUES(?)",
                    [(item["fragment_id"],) for item in clean_assets],
                )
            db.execute("DELETE FROM fragment_prompt_memberships")
            db.execute("DELETE FROM fragment_file_sources")
            for item in clean_assets:
                db.execute(
                    """INSERT INTO fragment_assets(
                        fragment_id, role, mined_role, role_override, value, family_id, join_mode, preferred_position,
                        placeholder_signature, confidence, review_state, rating, source_kind,
                        prompt_count, source_count, multiple_allowed, conflict_tags_json,
                        manual, created_at, updated_at
                    ) VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 0, ?, ?)
                    ON CONFLICT(fragment_id) DO UPDATE SET
                        mined_role=excluded.mined_role,
                        role=CASE WHEN fragment_assets.role_override<>'' THEN fragment_assets.role_override ELSE excluded.role END,
                        role_override=fragment_assets.role_override,
                        value=excluded.value,
                        family_id=excluded.family_id,
                        join_mode=excluded.join_mode,
                        preferred_position=excluded.preferred_position,
                        placeholder_signature=excluded.placeholder_signature,
                        confidence=excluded.confidence,
                        review_state=fragment_assets.review_state,
                        rating=fragment_assets.rating,
                        source_kind=CASE WHEN fragment_assets.manual=1 THEN fragment_assets.source_kind ELSE excluded.source_kind END,
                        prompt_count=excluded.prompt_count,
                        source_count=excluded.source_count,
                        multiple_allowed=excluded.multiple_allowed,
                        conflict_tags_json=excluded.conflict_tags_json,
                        manual=fragment_assets.manual,
                        updated_at=excluded.updated_at""",
                    (
                        item["fragment_id"], item["role"], item["mined_role"], item["value"], item["family_id"], item["join_mode"],
                        item["preferred_position"], item["placeholder_signature"], item["confidence"], item["review_state"],
                        item["source_kind"], len(item["prompt_ids"]), len({source["source_path"] for source in item["source_files"]}),
                        item["multiple_allowed"], item["conflict_tags_json"], now, now,
                    ),
                )
            db.execute(
                """DELETE FROM fragment_assets
                WHERE manual=0 AND NOT EXISTS (
                    SELECT 1 FROM solo_fragment_seen seen WHERE seen.fragment_id=fragment_assets.fragment_id
                )"""
            )
            membership_rows = [
                (item["fragment_id"], prompt_id, 1, now)
                for item in clean_assets for prompt_id in item["prompt_ids"]
            ]
            if membership_rows:
                db.executemany(
                    """INSERT OR REPLACE INTO fragment_prompt_memberships(
                        fragment_id, prompt_id, occurrence_count, created_at
                    ) VALUES (?, ?, ?, ?)""",
                    membership_rows,
                )
            file_rows = [
                (item["fragment_id"], source["source_path"], source["line_number"], source["source_type"], now)
                for item in clean_assets for source in item["source_files"]
            ]
            if file_rows:
                db.executemany(
                    """INSERT OR REPLACE INTO fragment_file_sources(
                        fragment_id, source_path, line_number, source_type, created_at
                    ) VALUES (?, ?, ?, ?, ?)""",
                    file_rows,
                )
            db.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES('fragment_index_signature', ?)", (str(signature or ""),))
            db.execute(
                """INSERT INTO schema_meta(key, value) VALUES('fragment_revision', '1')
                ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
            )
        return {"fragments": len(clean_assets), "memberships": len(membership_rows), "sources": len(file_rows)}

    @staticmethod
    def _fragment_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        value = dict(row)
        try:
            value["conflict_tags"] = json.loads(str(value.pop("conflict_tags_json", "[]") or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            value["conflict_tags"] = []
        for key in ("preferred_position", "rating", "prompt_count", "source_count", "multiple_allowed", "manual"):
            if key in value:
                value[key] = int(value[key] or 0)
        if "confidence" in value:
            value["confidence"] = float(value["confidence"] or 0)
        return value

    def fragment_summary(self) -> dict[str, Any]:
        with _LOCK, self._connection() as db:
            total = int(db.execute("SELECT COUNT(*) FROM fragment_assets WHERE review_state<>'rejected'").fetchone()[0])
            role_rows = db.execute(
                """SELECT role, COUNT(*) AS count FROM fragment_assets
                WHERE review_state<>'rejected' GROUP BY role ORDER BY count DESC, role"""
            ).fetchall()
            state_rows = db.execute(
                "SELECT review_state, COUNT(*) AS count FROM fragment_assets GROUP BY review_state ORDER BY review_state"
            ).fetchall()
            source_rows = db.execute(
                """SELECT source_kind, COUNT(*) AS count FROM fragment_assets
                WHERE review_state<>'rejected' GROUP BY source_kind ORDER BY count DESC, source_kind"""
            ).fetchall()
        return {
            "total": total,
            "roles": {str(row["role"]): int(row["count"] or 0) for row in role_rows},
            "states": {str(row["review_state"]): int(row["count"] or 0) for row in state_rows},
            "sources": {str(row["source_kind"]): int(row["count"] or 0) for row in source_rows},
        }

    def fragments(
        self,
        *,
        query: str = "",
        role: str = "",
        state: str = "active",
        sort: str = "rank",
        limit: int = 96,
        offset: int = 0,
    ) -> dict[str, Any]:
        where: list[str] = []
        values: list[Any] = []
        clean_role = str(role or "").strip().lower()
        clean_state = str(state or "active").strip().lower()
        clean_query = " ".join(str(query or "").split()).casefold()
        if clean_role:
            where.append("role=?")
            values.append(clean_role)
        if clean_state == "active":
            where.append("review_state<>'rejected'")
        elif clean_state == "ready":
            where.append("review_state IN ('approved', 'suggested')")
        elif clean_state in {"approved", "suggested", "review", "rejected"}:
            where.append("review_state=?")
            values.append(clean_state)
        if clean_query:
            where.append("(LOWER(value) LIKE ? OR LOWER(role) LIKE ? OR LOWER(family_id) LIKE ?)")
            needle = f"%{clean_query}%"
            values.extend((needle, needle, needle))
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        order = {
            "name": "value COLLATE NOCASE, fragment_id",
            "newest": "updated_at DESC, fragment_id",
            "confidence": "confidence DESC, source_count DESC, prompt_count DESC, value COLLATE NOCASE",
            "role": "preferred_position, role, source_count DESC, prompt_count DESC, value COLLATE NOCASE",
        }.get(str(sort or "").strip().lower(), "source_count DESC, prompt_count DESC, confidence DESC, value COLLATE NOCASE")
        clean_limit = max(0, min(500, int(limit or 0)))
        clean_offset = max(0, int(offset or 0))
        with _LOCK, self._connection() as db:
            total = int(db.execute(f"SELECT COUNT(*) FROM fragment_assets {clause}", values).fetchone()[0])
            if clean_limit:
                rows = db.execute(
                    f"""SELECT * FROM fragment_assets {clause}
                    ORDER BY {order} LIMIT ? OFFSET ?""",
                    [*values, clean_limit, clean_offset],
                ).fetchall()
            else:
                rows = []
            ids = [str(row["fragment_id"]) for row in rows]
            file_sources: dict[str, list[dict[str, Any]]] = {}
            if ids:
                placeholders = ",".join("?" for _ in ids)
                source_rows = db.execute(
                    f"""SELECT fragment_id, source_path, line_number, source_type
                    FROM fragment_file_sources WHERE fragment_id IN ({placeholders})
                    ORDER BY source_path COLLATE NOCASE, line_number""",
                    ids,
                ).fetchall()
                for source in source_rows:
                    bucket = file_sources.setdefault(str(source["fragment_id"]), [])
                    if len(bucket) < 8:
                        bucket.append({
                            "source_path": str(source["source_path"]),
                            "line_number": int(source["line_number"] or 0),
                            "source_type": str(source["source_type"] or ""),
                        })
        output = []
        for row in rows:
            item = self._fragment_row(row)
            item["source_files"] = file_sources.get(str(item.get("fragment_id") or ""), [])
            output.append(item)
        return {"fragments": output, "total": total, "offset": clean_offset, "limit": clean_limit}

    def fragments_for_prompt(self, prompt_id: str, limit: int = 60) -> list[dict[str, Any]]:
        clean_id = str(prompt_id or "").strip()
        if not clean_id:
            return []
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT f.* FROM fragment_prompt_memberships m
                JOIN fragment_assets f ON f.fragment_id=m.fragment_id
                WHERE m.prompt_id=? AND f.review_state<>'rejected'
                ORDER BY f.preferred_position, f.source_count DESC, f.confidence DESC, f.fragment_id
                LIMIT ?""",
                (clean_id, max(1, min(200, int(limit or 60)))),
            ).fetchall()
        return [self._fragment_row(row) for row in rows]

    def set_fragment_review(self, fragment_id: str, state: str, rating: int | None = None) -> dict[str, Any] | None:
        clean_state = str(state or "").strip().lower()
        if clean_state not in {"approved", "suggested", "review", "rejected"}:
            raise ValueError("Fragment state must be approved, suggested, review, or rejected")
        try:
            clean_rating = max(0, min(5, int(rating or 0)))
        except (TypeError, ValueError):
            clean_rating = 0
        with _LOCK, self._connection() as db:
            result = db.execute(
                "UPDATE fragment_assets SET review_state=?, rating=?, updated_at=? WHERE fragment_id=?",
                (clean_state, clean_rating, _now(), str(fragment_id or "")),
            )
            if result.rowcount <= 0:
                return None
            db.execute(
                """INSERT INTO schema_meta(key, value) VALUES('fragment_revision', '1')
                ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
            )
            row = db.execute("SELECT * FROM fragment_assets WHERE fragment_id=?", (str(fragment_id or ""),)).fetchone()
        return self._fragment_row(row) if row else None

    @staticmethod
    def _valid_fragment_role(role: str) -> str:
        clean_role = str(role or "").strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", clean_role):
            raise ValueError("Fragment role must be a supported ingredient category")
        return clean_role

    def bulk_update_fragments(
        self,
        *,
        fragment_ids: list[str] | None = None,
        all_filtered: bool = False,
        query: str = "",
        role: str = "",
        state_filter: str = "active",
        review_state: str | None = None,
        new_role: str | None = None,
        reset_role: bool = False,
        rating: int | None = None,
    ) -> dict[str, int]:
        """Bulk review/reclassify a page or an entire filtered ingredient view.

        Human role corrections are stored separately from the miner role, so a
        deterministic rebuild can refresh provenance without erasing review.
        Reclassification merges an exact value already present in the target
        role instead of failing the whole batch on the `(role, value)` key.
        """
        clean_ids = list(dict.fromkeys(str(value or "").strip() for value in fragment_ids or [] if str(value or "").strip()))
        clean_review = None if review_state is None else str(review_state or "").strip().lower()
        if clean_review is not None and clean_review not in {"approved", "suggested", "review", "rejected"}:
            raise ValueError("Fragment state must be approved, suggested, review, or rejected")
        clean_new_role = self._valid_fragment_role(new_role) if new_role is not None and not reset_role else None
        try:
            clean_rating = None if rating is None else max(0, min(5, int(rating)))
        except (TypeError, ValueError):
            raise ValueError("Fragment rating must be between 0 and 5") from None
        if not clean_ids and not all_filtered:
            raise ValueError("Select at least one Fragment or the current filtered view")
        if clean_review is None and clean_new_role is None and not reset_role and clean_rating is None:
            raise ValueError("Choose a review or category change")

        where: list[str] = []
        values: list[Any] = []
        clean_filter_role = str(role or "").strip().lower()
        clean_state = str(state_filter or "active").strip().lower()
        clean_query = " ".join(str(query or "").split()).casefold()
        if clean_filter_role:
            where.append("role=?")
            values.append(clean_filter_role)
        if clean_state == "active":
            where.append("review_state<>'rejected'")
        elif clean_state == "ready":
            where.append("review_state IN ('approved', 'suggested')")
        elif clean_state in {"approved", "suggested", "review", "rejected"}:
            where.append("review_state=?")
            values.append(clean_state)
        if clean_query:
            where.append("(LOWER(value) LIKE ? OR LOWER(role) LIKE ? OR LOWER(family_id) LIKE ?)")
            needle = f"%{clean_query}%"
            values.extend((needle, needle, needle))
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        changed = merged = 0
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute("CREATE TEMP TABLE IF NOT EXISTS solo_fragment_bulk(fragment_id TEXT PRIMARY KEY)")
            db.execute("DELETE FROM solo_fragment_bulk")
            if clean_ids:
                db.executemany(
                    "INSERT OR IGNORE INTO solo_fragment_bulk(fragment_id) VALUES(?)",
                    [(fragment_id,) for fragment_id in clean_ids],
                )
            if all_filtered:
                db.execute(
                    f"INSERT OR IGNORE INTO solo_fragment_bulk(fragment_id) SELECT fragment_id FROM fragment_assets {clause}",
                    values,
                )
            selected_rows = db.execute(
                """SELECT f.* FROM fragment_assets f
                JOIN solo_fragment_bulk selected ON selected.fragment_id=f.fragment_id
                ORDER BY f.fragment_id"""
            ).fetchall()

            effective_ids: set[str] = set()
            for selected in selected_rows:
                fragment_id = str(selected["fragment_id"])
                target_role = str(selected["mined_role"] or selected["role"]) if reset_role else (clean_new_role or str(selected["role"]))
                target_override = "" if reset_role else (clean_new_role if clean_new_role is not None else str(selected["role_override"] or ""))
                target = None
                if target_role != str(selected["role"]):
                    target = db.execute(
                        "SELECT fragment_id FROM fragment_assets WHERE role=? AND value=? COLLATE NOCASE AND fragment_id<>?",
                        (target_role, str(selected["value"]), fragment_id),
                    ).fetchone()
                if target is not None:
                    target_id = str(target["fragment_id"])
                    db.execute(
                        """INSERT OR IGNORE INTO fragment_prompt_memberships(fragment_id, prompt_id, occurrence_count, created_at)
                        SELECT ?, prompt_id, occurrence_count, created_at FROM fragment_prompt_memberships WHERE fragment_id=?""",
                        (target_id, fragment_id),
                    )
                    db.execute(
                        """INSERT OR IGNORE INTO fragment_file_sources(fragment_id, source_path, line_number, source_type, created_at)
                        SELECT ?, source_path, line_number, source_type, created_at FROM fragment_file_sources WHERE fragment_id=?""",
                        (target_id, fragment_id),
                    )
                    db.execute("DELETE FROM fragment_assets WHERE fragment_id=?", (fragment_id,))
                    effective_ids.add(target_id)
                    merged += 1
                    continue
                if target_role != str(selected["role"]) or target_override != str(selected["role_override"] or ""):
                    db.execute(
                        "UPDATE fragment_assets SET role=?, role_override=?, updated_at=? WHERE fragment_id=?",
                        (target_role, target_override, now, fragment_id),
                    )
                effective_ids.add(fragment_id)

            if effective_ids:
                db.execute("DELETE FROM solo_fragment_bulk")
                db.executemany(
                    "INSERT OR IGNORE INTO solo_fragment_bulk(fragment_id) VALUES(?)",
                    [(fragment_id,) for fragment_id in sorted(effective_ids)],
                )
                assignments: list[str] = ["updated_at=?"]
                update_values: list[Any] = [now]
                if clean_review is not None:
                    assignments.append("review_state=?")
                    update_values.append(clean_review)
                if clean_rating is not None:
                    assignments.append("rating=?")
                    update_values.append(clean_rating)
                result = db.execute(
                    f"""UPDATE fragment_assets SET {', '.join(assignments)}
                    WHERE fragment_id IN (SELECT fragment_id FROM solo_fragment_bulk)""",
                    update_values,
                )
                changed = max(0, int(result.rowcount or 0))
                db.execute(
                    """INSERT INTO schema_meta(key, value) VALUES('fragment_revision', '1')
                    ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER) + 1"""
                )
        return {"selected": len(selected_rows), "changed": changed, "merged": merged}

    @staticmethod
    def recipe_component_id(kind: str, value: str) -> str:
        clean_kind = str(kind or "").strip().lower()
        clean_value = " ".join(str(value or "").split())
        digest = hashlib.sha1(f"{clean_kind}\0{clean_value.casefold()}".encode("utf-8")).hexdigest()
        return f"recipe-component:{clean_kind}:{digest}"

    def upsert_recipe_component(self, kind: str, value: str, *, manual: bool = False) -> dict[str, Any]:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind not in {"outfit", "scene"}:
            raise ValueError("Recipe component kind must be outfit or scene")
        clean_value = " ".join(str(value or "").split())
        if not clean_value:
            raise ValueError("Recipe component text is required")
        if len(clean_value) > 8000:
            raise ValueError("Recipe component text is limited to 8000 characters")
        component_id = self.recipe_component_id(clean_kind, clean_value)
        now = _now()
        with _LOCK, self._connection() as db:
            tombstone = db.execute(
                "SELECT component_id FROM component_tombstones WHERE component_id=? OR (kind=? AND value=? COLLATE NOCASE)",
                (component_id, clean_kind, clean_value),
            ).fetchone()
            if tombstone is not None and not manual:
                return {
                    "component_id": component_id,
                    "kind": clean_kind,
                    "value": clean_value,
                    "manual": 0,
                    "tombstoned": True,
                }
            if tombstone is not None and manual:
                # A deliberate manual add/import is the only implicit way to
                # resurrect a value that was previously DELETE EVERYWHERE'd.
                db.execute("DELETE FROM component_tombstones WHERE component_id=?", (component_id,))
            db.execute(
                """INSERT INTO recipe_components(component_id, kind, value, manual, preview_ref, preview_source, created_at, updated_at)
                VALUES (?, ?, ?, ?, '', '', ?, ?)
                ON CONFLICT(kind, value) DO UPDATE SET
                    manual=MAX(recipe_components.manual, excluded.manual),
                    updated_at=excluded.updated_at""",
                (component_id, clean_kind, clean_value, int(bool(manual)), now, now),
            )
            row = db.execute("SELECT * FROM recipe_components WHERE kind=? AND value=? COLLATE NOCASE", (clean_kind, clean_value)).fetchone()
        return dict(row) if row else {"component_id": component_id, "kind": clean_kind, "value": clean_value, "manual": int(bool(manual))}

    def update_recipe_component_value(self, component_id: str, value: str) -> dict[str, Any]:
        clean = " ".join(str(value or "").split())
        if not clean or len(clean) > 8000:
            raise ValueError("Enter a value between 1 and 8000 characters")
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT * FROM recipe_components WHERE component_id=?", (component_id,)).fetchone()
            if row is None:
                raise ValueError("Library asset no longer exists")
            duplicate = db.execute("SELECT component_id FROM recipe_components WHERE kind=? AND value=? COLLATE NOCASE AND component_id<>?", (row["kind"], clean, component_id)).fetchone()
            if duplicate is not None:
                raise ValueError("That value already exists. Choose different text or use the existing asset.")
            new_id = self.recipe_component_id(row["kind"], clean)
            if clean == row["value"]:
                return dict(row)
            db.execute("PRAGMA defer_foreign_keys=ON")
            db.execute("UPDATE recipe_components SET component_id=?,value=?,manual=1,updated_at=? WHERE component_id=?", (new_id, clean, _now(), component_id))
            if new_id != component_id:
                for table, column in (
                    ("component_reviews", "component_id"),
                    ("component_collection_memberships", "component_id"),
                    ("component_import_items", "component_id"),
                    ("component_import_memberships", "component_id"),
                    ("wardrobe_look_parts", "look_component_id"),
                    ("wardrobe_migration_state", "look_component_id"),
                    ("wardrobe_pack_looks", "component_id"),
                    ("creative_library_pack_component_memberships", "component_id"),
                    ("library_collection_memberships", "asset_id"),
                ):
                    db.execute(f"UPDATE {table} SET {column}=? WHERE {column}=?", (new_id, component_id))
                # Keep recipe/source scans from resurrecting the superseded value.
                db.execute("INSERT OR REPLACE INTO component_tombstones(component_id,kind,value,deleted_at) VALUES(?,?,?,?)", (component_id, row["kind"], row["value"], _now()))
                db.execute("DELETE FROM component_tombstones WHERE component_id=?", (new_id,))
            if new_id != component_id:
                for meta in db.execute("SELECT key,value FROM schema_meta WHERE key LIKE 'component_import_previous_homes:%'").fetchall():
                    saved = json.loads(meta["value"])
                    if component_id in saved.get("homes", {}):
                        saved["homes"][new_id] = saved["homes"].pop(component_id)
                        db.execute("UPDATE schema_meta SET value=? WHERE key=?", (json.dumps(saved), meta["key"]))
            self._bump_component_revision(db)
            result = dict(db.execute("SELECT * FROM recipe_components WHERE component_id=?", (new_id,)).fetchone())
        return result

    def component_tombstones(self, kind: str = "") -> list[dict[str, Any]]:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind and clean_kind not in {"outfit", "scene"}:
            raise ValueError("Recipe component kind must be outfit or scene")
        with _LOCK, self._connection() as db:
            if clean_kind:
                rows = db.execute(
                    "SELECT * FROM component_tombstones WHERE kind=? ORDER BY deleted_at DESC",
                    (clean_kind,),
                ).fetchall()
            else:
                rows = db.execute("SELECT * FROM component_tombstones ORDER BY deleted_at DESC").fetchall()
        return [dict(row) for row in rows]

    def is_component_tombstoned(self, kind: str, value: str) -> bool:
        clean_kind = str(kind or "").strip().lower()
        clean_value = " ".join(str(value or "").split())
        if clean_kind not in {"outfit", "scene"} or not clean_value:
            return False
        component_id = self.recipe_component_id(clean_kind, clean_value)
        with _LOCK, self._connection() as db:
            row = db.execute(
                "SELECT 1 FROM component_tombstones WHERE component_id=? OR (kind=? AND value=? COLLATE NOCASE) LIMIT 1",
                (component_id, clean_kind, clean_value),
            ).fetchone()
        return row is not None

    def schema_meta_value(self, key: str, default: str = "") -> str:
        clean_key = str(key or "").strip()
        if not clean_key:
            return str(default or "")
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT value FROM schema_meta WHERE key=?", (clean_key,)).fetchone()
        return str(row["value"] if row is not None else default)

    def set_schema_meta_value(self, key: str, value: str) -> None:
        clean_key = str(key or "").strip()
        if not clean_key:
            raise ValueError("Metadata key is required")
        with _LOCK, self._connection() as db:
            db.execute(
                "INSERT INTO schema_meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (clean_key, str(value or "")),
            )

    def schema_meta_json(self, key: str, default: Any = None) -> Any:
        raw = self.schema_meta_value(key, "")
        if not raw:
            return default
        try:
            return json.loads(raw)
        except Exception:
            return default

    def set_schema_meta_json(self, key: str, value: Any) -> None:
        self.set_schema_meta_value(key, json.dumps(value if value is not None else [], ensure_ascii=False, sort_keys=True))

    def set_last_prompt_import(self, prompt_ids: list[str] | tuple[str, ...] | set[str]) -> list[str]:
        ids = self._clean_prompt_ids(prompt_ids)
        self.set_schema_meta_json("prompt_last_import_ids", ids)
        return ids

    def last_prompt_import_ids(self) -> list[str]:
        data = self.schema_meta_json("prompt_last_import_ids", [])
        return self._clean_prompt_ids(data if isinstance(data, list) else [])

    def set_last_recipe_import(self, recipe_ids: list[str] | tuple[str, ...] | set[str]) -> list[str]:
        ids = self._clean_prompt_ids(recipe_ids)
        self.set_schema_meta_json("recipe_last_import_ids", ids)
        return ids

    def last_recipe_import_ids(self) -> list[str]:
        data = self.schema_meta_json("recipe_last_import_ids", [])
        return self._clean_prompt_ids(data if isinstance(data, list) else [])

    def recipe_component_by_value(self, kind: str, value: str) -> dict[str, Any] | None:
        clean_kind = str(kind or "").strip().lower()
        clean_value = " ".join(str(value or "").split())
        if clean_kind not in {"outfit", "scene"} or not clean_value:
            return None
        with _LOCK, self._connection() as db:
            row = db.execute(
                "SELECT * FROM recipe_components WHERE kind=? AND value=? COLLATE NOCASE",
                (clean_kind, clean_value),
            ).fetchone()
        return dict(row) if row else None

    def recipe_components(self, kind: str = "") -> list[dict[str, Any]]:
        clean_kind = str(kind or "").strip().lower()
        params: list[Any] = []
        where = ""
        if clean_kind:
            if clean_kind not in {"outfit", "scene"}:
                raise ValueError("Recipe component kind must be outfit or scene")
            where = "WHERE kind=?"
            params.append(clean_kind)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"SELECT * FROM recipe_components {where} ORDER BY created_at, component_id",
                params,
            ).fetchall()
            output = [dict(row) for row in rows]
            by_id = {str(item["component_id"]): item for item in output}
            if by_id:
                membership_rows = db.execute(
                    f"""SELECT m.component_id, c.collection_id, c.name, c.parent_id, c.color
                    FROM component_collection_memberships m
                    JOIN component_collections c ON c.collection_id=m.collection_id
                    {'WHERE c.kind=?' if clean_kind else ''}
                    ORDER BY c.name COLLATE NOCASE""",
                    ([clean_kind] if clean_kind else []),
                ).fetchall()
                for entry in membership_rows:
                    item = by_id.get(str(entry["component_id"]))
                    if item is not None:
                        item.setdefault("collections", []).append({
                            "collection_id": str(entry["collection_id"]),
                            "name": str(entry["name"]),
                            "parent_id": str(entry["parent_id"] or ""),
                            "color": str(entry["color"]),
                        })
            if by_id:
                pack_rows = db.execute(
                    f"""SELECT m.asset_id, c.collection_id, c.name, c.color
                    FROM library_collection_memberships m
                    JOIN library_collections c ON c.collection_id=m.collection_id
                    {'WHERE c.kind=?' if clean_kind else "WHERE c.kind IN ('outfit','scene')"}
                    ORDER BY c.name COLLATE NOCASE""",
                    ([clean_kind] if clean_kind else []),
                ).fetchall()
                for entry in pack_rows:
                    item = by_id.get(str(entry["asset_id"]))
                    if item is not None:
                        item.setdefault("pack_collections", []).append({
                            "collection_id": str(entry["collection_id"]),
                            "name": str(entry["name"]),
                            "color": str(entry["color"]),
                        })
            if by_id:
                if clean_kind:
                    rating_rows = db.execute(
                        """SELECT r.component_id, r.rating
                        FROM component_reviews r
                        JOIN recipe_components c ON c.component_id=r.component_id
                        WHERE c.kind=?""",
                        (clean_kind,),
                    ).fetchall()
                else:
                    rating_rows = db.execute("SELECT component_id, rating FROM component_reviews").fetchall()
                ratings = {str(row["component_id"]): int(row["rating"] or 0) for row in rating_rows}
            else:
                ratings = {}
            for item in output:
                item.setdefault("collections", [])
                item.setdefault("pack_collections", [])
                item["rating"] = max(0, min(5, int(ratings.get(str(item.get("component_id") or ""), 0))))
        return output

    def set_component_rating(self, component_id: str, rating: int) -> dict[str, Any]:
        clean_id = str(component_id or "").strip()
        try:
            clean_rating = int(rating)
        except (TypeError, ValueError):
            raise ValueError("Rating must be a number from 0 to 5")
        if clean_rating < 0 or clean_rating > 5:
            raise ValueError("Rating must be between 0 and 5")
        with _LOCK, self._connection() as db:
            component = db.execute("SELECT component_id FROM recipe_components WHERE component_id=?", (clean_id,)).fetchone()
            if component is None:
                raise ValueError("Library asset no longer exists")
            if clean_rating == 0:
                db.execute("DELETE FROM component_reviews WHERE component_id=?", (clean_id,))
            else:
                db.execute(
                    """INSERT INTO component_reviews(component_id, rating, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(component_id) DO UPDATE SET rating=excluded.rating, updated_at=excluded.updated_at""",
                    (clean_id, clean_rating, _now()),
                )
        return {"component_id": clean_id, "rating": clean_rating}

    def component_collections(self, kind: str) -> list[dict[str, Any]]:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind not in {"outfit", "scene"}:
            raise ValueError("Component collection kind must be outfit or scene")
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT c.*, COUNT(m.component_id) AS asset_count
                FROM component_collections c
                LEFT JOIN component_collection_memberships m ON m.collection_id=c.collection_id
                WHERE c.kind=?
                GROUP BY c.collection_id
                ORDER BY CASE WHEN c.parent_id='' THEN 0 ELSE 1 END, c.name COLLATE NOCASE""",
                (clean_kind,),
            ).fetchall()
            membership_rows = db.execute(
                """SELECT m.component_id, m.collection_id
                FROM component_collection_memberships m
                JOIN component_collections c ON c.collection_id=m.collection_id
                WHERE c.kind=?""",
                (clean_kind,),
            ).fetchall()
        output = [dict(row) for row in rows]
        members: dict[str, set[str]] = {}
        for row in membership_rows:
            members.setdefault(str(row["collection_id"]), set()).add(str(row["component_id"]))
        children: dict[str, list[str]] = {}
        for row in output:
            parent_id = str(row.get("parent_id") or "")
            if parent_id:
                children.setdefault(parent_id, []).append(str(row.get("collection_id") or ""))
        for row in output:
            collection_id = str(row.get("collection_id") or "")
            direct = set(members.get(collection_id, set()))
            row["direct_asset_count"] = len(direct)
            if not str(row.get("parent_id") or ""):
                scoped = set(direct)
                for child_id in children.get(collection_id, []):
                    scoped.update(members.get(child_id, set()))
                row["asset_count"] = len(scoped)
            else:
                row["asset_count"] = len(direct)
        order = self.creative_structure_order(clean_kind).get("collections", [])
        order_index = {str(value): index for index, value in enumerate(order if isinstance(order, list) else [])}
        output.sort(key=lambda row: (order_index.get(str(row.get("collection_id") or ""), 10**9), 0 if not str(row.get("parent_id") or "") else 1, str(row.get("name") or "").casefold()))
        return output

    def create_component_collection(self, kind: str, name: str, parent_id: str = "") -> dict[str, Any]:
        clean_kind = str(kind or "").strip().lower()
        clean_name = " ".join(str(name or "").split())
        clean_parent = str(parent_id or "").strip()
        if clean_kind not in {"outfit", "scene"}:
            raise ValueError("Component collection kind must be outfit or scene")
        if not clean_name:
            raise ValueError("Collection name is required")
        if len(clean_name) > 80:
            raise ValueError("Collection name is limited to 80 characters")
        now = _now()
        collection_id = f"component-collection:{clean_kind}:{uuid.uuid4().hex}"
        with _LOCK, self._connection() as db:
            if clean_parent:
                parent = db.execute(
                    "SELECT collection_id, kind, parent_id FROM component_collections WHERE collection_id=?",
                    (clean_parent,),
                ).fetchone()
                if parent is None or str(parent["kind"] or "") != clean_kind:
                    raise ValueError("Parent category no longer exists")
                if str(parent["parent_id"] or ""):
                    raise ValueError("Folder taxonomy supports Category → Subcategory only")
            color = RECIPE_COLLECTION_COLORS[
                int(db.execute("SELECT COUNT(*) FROM component_collections WHERE kind=?", (clean_kind,)).fetchone()[0]) % len(RECIPE_COLLECTION_COLORS)
            ]
            try:
                db.execute(
                    "INSERT INTO component_collections(collection_id, kind, name, parent_id, color, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (collection_id, clean_kind, clean_name, clean_parent, color, now, now),
                )
            except sqlite3.IntegrityError:
                row = db.execute("SELECT * FROM component_collections WHERE kind=? AND name=? COLLATE NOCASE", (clean_kind, clean_name)).fetchone()
                if row is not None:
                    item = dict(row)
                    if clean_parent and str(item.get("parent_id") or "") != clean_parent:
                        raise ValueError(f"A {clean_kind} category/subcategory named “{clean_name}” already exists")
                    item["asset_count"] = int(db.execute("SELECT COUNT(*) FROM component_collection_memberships WHERE collection_id=?", (item["collection_id"],)).fetchone()[0]); return item
                raise
        return {"collection_id": collection_id, "kind": clean_kind, "name": clean_name, "parent_id": clean_parent, "color": color, "created_at": now, "updated_at": now, "asset_count": 0, "direct_asset_count": 0}

    def update_component_collection(self, collection_id: str, *, name: str | None = None, parent_id: str | None = None) -> dict[str, Any]:
        clean_id = str(collection_id or "").strip()
        with _LOCK, self._connection() as db:
            current = db.execute("SELECT * FROM component_collections WHERE collection_id=?", (clean_id,)).fetchone()
            if current is None:
                raise ValueError("Collection no longer exists")
            clean_kind = str(current["kind"] or "")
            next_name = " ".join(str(name if name is not None else current["name"]).split())
            if not next_name:
                raise ValueError("Collection name is required")
            if len(next_name) > 80:
                raise ValueError("Collection name is limited to 80 characters")
            next_parent = str(parent_id if parent_id is not None else current["parent_id"] or "").strip()
            if next_parent == clean_id:
                raise ValueError("A category cannot be its own parent")
            if next_parent:
                parent = db.execute("SELECT kind, parent_id FROM component_collections WHERE collection_id=?", (next_parent,)).fetchone()
                if parent is None or str(parent["kind"] or "") != clean_kind:
                    raise ValueError("Parent category no longer exists")
                if str(parent["parent_id"] or ""):
                    raise ValueError("Folder taxonomy supports Category → Subcategory only")
            child = db.execute("SELECT 1 FROM component_collections WHERE parent_id=? LIMIT 1", (clean_id,)).fetchone()
            if child is not None and next_parent:
                raise ValueError("A category with subcategories cannot become a subcategory")
            try:
                db.execute(
                    "UPDATE component_collections SET name=?, parent_id=?, updated_at=? WHERE collection_id=?",
                    (next_name, next_parent, _now(), clean_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(f"A {clean_kind} category/subcategory named “{next_name}” already exists") from error
            updated = db.execute("SELECT * FROM component_collections WHERE collection_id=?", (clean_id,)).fetchone()
        item = dict(updated) if updated else {}
        item["asset_count"] = len(self.component_collection_member_ids(clean_id, include_children=not bool(item.get("parent_id"))))
        return item

    def delete_component_collection(self, collection_id: str) -> bool:
        with _LOCK, self._connection() as db:
            clean_id = str(collection_id)
            children = db.execute("SELECT collection_id FROM component_collections WHERE parent_id=?", (clean_id,)).fetchall()
            child_ids = [str(row["collection_id"]) for row in children]
            if child_ids:
                placeholders = ",".join("?" for _ in child_ids)
                db.execute(f"DELETE FROM component_collections WHERE collection_id IN ({placeholders})", child_ids)
            result = db.execute("DELETE FROM component_collections WHERE collection_id=?", (clean_id,))
        return result.rowcount > 0

    def clear_component_collections(self, kind: str) -> int:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind not in {"outfit", "scene"}:
            raise ValueError("Component collection kind must be outfit or scene")
        with _LOCK, self._connection() as db:
            count = int(db.execute("SELECT COUNT(*) FROM component_collections WHERE kind=?", (clean_kind,)).fetchone()[0])
            db.execute("DELETE FROM component_collections WHERE kind=?", (clean_kind,))
        return count

    def set_component_collections(self, component_id: str, collection_ids: list[str]) -> list[dict[str, str]]:
        requested = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        with _LOCK, self._connection() as db:
            component = db.execute("SELECT kind FROM recipe_components WHERE component_id=?", (str(component_id),)).fetchone()
            if component is None:
                raise ValueError("Library asset no longer exists")
            kind = str(component["kind"] or "")
            rows = []
            if requested:
                placeholders = ",".join("?" for _ in requested)
                rows = db.execute(
                    f"SELECT collection_id, name, color FROM component_collections WHERE kind=? AND collection_id IN ({placeholders})",
                    [kind, *requested],
                ).fetchall()
                found = {str(row["collection_id"]) for row in rows}
                if any(value not in found for value in requested):
                    raise ValueError("One or more selected collections do not exist for this asset type")
            db.execute("DELETE FROM component_collection_memberships WHERE component_id=?", (str(component_id),))
            now = _now()
            db.executemany(
                "INSERT INTO component_collection_memberships(component_id, collection_id, created_at) VALUES (?, ?, ?)",
                [(str(component_id), collection_id, now) for collection_id in requested],
            )
        selected = {str(row["collection_id"]): row for row in rows}
        return [{"collection_id": value, "name": str(selected[value]["name"]), "color": str(selected[value]["color"])} for value in requested]

    def add_components_to_collections(self, component_ids: list[str], collection_ids: list[str]) -> dict[str, int]:
        requested_components = list(dict.fromkeys(str(value) for value in component_ids if str(value)))
        requested_collections = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        if not requested_components or not requested_collections:
            return {"assets": len(requested_components), "collections": len(requested_collections), "memberships_added": 0}
        with _LOCK, self._connection() as db:
            components: list[sqlite3.Row] = []
            for offset in range(0, len(requested_components), 500):
                chunk = requested_components[offset:offset + 500]
                placeholders = ",".join("?" for _ in chunk)
                components.extend(db.execute(
                    f"SELECT component_id, kind FROM recipe_components WHERE component_id IN ({placeholders})",
                    chunk,
                ).fetchall())
            if len(components) != len(requested_components):
                raise ValueError("One or more selected assets no longer exist")
            kinds = {str(row["kind"]) for row in components}
            if len(kinds) != 1:
                raise ValueError("Selected assets must be the same type")
            kind = next(iter(kinds))
            valid_ids: set[str] = set()
            for offset in range(0, len(requested_collections), 500):
                chunk = requested_collections[offset:offset + 500]
                placeholders = ",".join("?" for _ in chunk)
                valid_ids.update(str(row["collection_id"]) for row in db.execute(
                    f"SELECT collection_id FROM component_collections WHERE kind=? AND collection_id IN ({placeholders})",
                    [kind, *chunk],
                ).fetchall())
            if len(valid_ids) != len(requested_collections):
                raise ValueError("One or more selected collections do not exist for this asset type")
            now = _now()
            cursor = db.executemany(
                "INSERT OR IGNORE INTO component_collection_memberships(component_id, collection_id, created_at) VALUES (?, ?, ?)",
                [(component_id, collection_id, now) for component_id in requested_components for collection_id in requested_collections],
            )
            added = max(0, int(cursor.rowcount or 0))
        return {"assets": len(requested_components), "collections": len(requested_collections), "memberships_added": int(added)}

    def move_components_home(self, component_ids: list[str], collection_id: str) -> dict[str, int]:
        """Move same-kind component assets to one canonical taxonomy Home."""
        requested_components = list(dict.fromkeys(str(value) for value in component_ids if str(value)))
        requested_home = str(collection_id or "").strip()
        if not requested_components or not requested_home:
            return {"assets": len(requested_components), "homes": 0, "memberships_added": 0}
        with _LOCK, self._connection() as db:
            components: list[sqlite3.Row] = []
            for offset in range(0, len(requested_components), 500):
                chunk = requested_components[offset:offset + 500]
                placeholders = ",".join("?" for _ in chunk)
                components.extend(db.execute(
                    f"SELECT component_id, kind FROM recipe_components WHERE component_id IN ({placeholders})",
                    chunk,
                ).fetchall())
            if len(components) != len(requested_components):
                raise ValueError("One or more selected assets no longer exist")
            kinds = {str(row["kind"]) for row in components}
            if len(kinds) != 1:
                raise ValueError("Selected assets must be the same type")
            home = db.execute(
                "SELECT collection_id FROM component_collections WHERE kind=? AND collection_id=?",
                (next(iter(kinds)), requested_home),
            ).fetchone()
            if home is None:
                raise ValueError("The selected Home no longer exists for this asset type")
            for offset in range(0, len(requested_components), 500):
                chunk = requested_components[offset:offset + 500]
                placeholders = ",".join("?" for _ in chunk)
                db.execute(
                    f"DELETE FROM component_collection_memberships WHERE component_id IN ({placeholders})",
                    chunk,
                )
            now = _now()
            db.executemany(
                "INSERT INTO component_collection_memberships(component_id, collection_id, created_at) VALUES (?, ?, ?)",
                [(component_id, requested_home, now) for component_id in requested_components],
            )
        return {"assets": len(requested_components), "homes": 1, "memberships_added": len(requested_components)}

    def component_collection_by_name(self, kind: str, name: str) -> dict[str, Any] | None:
        clean_kind = str(kind or "").strip().lower()
        clean_name = " ".join(str(name or "").split())
        if clean_kind not in {"outfit", "scene"} or not clean_name:
            return None
        with _LOCK, self._connection() as db:
            row = db.execute(
                "SELECT * FROM component_collections WHERE kind=? AND name=? COLLATE NOCASE",
                (clean_kind, clean_name),
            ).fetchone()
        return dict(row) if row else None

    def component_collection_member_ids(self, collection_id: str, include_children: bool = False) -> set[str]:
        clean_id = str(collection_id or "")
        with _LOCK, self._connection() as db:
            ids = [clean_id]
            if include_children:
                ids.extend(str(row["collection_id"]) for row in db.execute(
                    "SELECT collection_id FROM component_collections WHERE parent_id=?",
                    (clean_id,),
                ).fetchall())
            placeholders = ",".join("?" for _ in ids)
            rows = db.execute(
                f"SELECT DISTINCT component_id FROM component_collection_memberships WHERE collection_id IN ({placeholders})",
                ids,
            ).fetchall()
        return {str(row["component_id"]) for row in rows}

    def remove_components_from_collections(self, component_ids: list[str], collection_ids: list[str]) -> dict[str, int]:
        requested_components = list(dict.fromkeys(str(value) for value in component_ids if str(value)))
        requested_collections = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        if not requested_components or not requested_collections:
            return {"assets": len(requested_components), "collections": len(requested_collections), "memberships_removed": 0}
        with _LOCK, self._connection() as db:
            removed = 0
            for collection_id in requested_collections:
                for component_id in requested_components:
                    result = db.execute(
                        "DELETE FROM component_collection_memberships WHERE component_id=? AND collection_id=?",
                        (component_id, collection_id),
                    )
                    removed += max(0, int(result.rowcount or 0))
        return {"assets": len(requested_components), "collections": len(requested_collections), "memberships_removed": removed}

    def delete_recipe_components(self, component_ids: list[str], *, everywhere: bool = False) -> dict[str, Any]:
        requested = list(dict.fromkeys(str(value) for value in component_ids if str(value)))
        if not requested:
            return {"deleted": 0, "protected": 0, "removed": [], "tombstoned": 0}
        removed: list[dict[str, Any]] = []
        protected = 0
        tombstoned = 0
        with _LOCK, self._connection() as db:
            for component_id in requested:
                row = db.execute("SELECT * FROM recipe_components WHERE component_id=?", (component_id,)).fetchone()
                if row is None:
                    continue
                if not everywhere and not bool(row["manual"]):
                    protected += 1
                    continue
                removed.append(dict(row))
                if everywhere:
                    db.execute(
                        """INSERT INTO component_tombstones(component_id, kind, value, deleted_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(component_id) DO UPDATE SET kind=excluded.kind, value=excluded.value, deleted_at=excluded.deleted_at""",
                        (component_id, str(row["kind"] or ""), str(row["value"] or ""), _now()),
                    )
                    tombstoned += 1
                db.execute("DELETE FROM recipe_components WHERE component_id=?", (component_id,))
        return {"deleted": len(removed), "protected": protected, "removed": removed, "tombstoned": tombstoned}

    def record_component_import_batch(
        self, *, kind: str, source_paths: list[str], collection_mode: str,
        items: list[tuple[str, bool]], memberships: list[tuple[str, str]],
        collections: list[tuple[str, bool]],
    ) -> dict[str, Any]:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind not in {"outfit", "scene"}:
            raise ValueError("Import batch kind must be outfit or scene")
        batch_id = f"component-import:{clean_kind}:{uuid.uuid4().hex}"
        now = _now()
        dedup_items: dict[str, bool] = {}
        for component_id, created in items:
            if component_id:
                dedup_items[str(component_id)] = bool(created) or dedup_items.get(str(component_id), False)
        dedup_memberships = list(dict.fromkeys((str(component_id), str(collection_id)) for component_id, collection_id in memberships if component_id and collection_id))
        dedup_collections: dict[str, bool] = {}
        for collection_id, created in collections:
            if collection_id:
                dedup_collections[str(collection_id)] = bool(created) or dedup_collections.get(str(collection_id), False)
        new_count = sum(1 for created in dedup_items.values() if created)
        matched_count = len(dedup_items) - new_count
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO component_import_batches(batch_id, kind, file_count, new_count, matched_count, membership_count, source_paths_json, collection_mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (batch_id, clean_kind, len(source_paths), new_count, matched_count, len(dedup_memberships), json.dumps(list(source_paths)), str(collection_mode or "none"), now),
            )
            db.executemany(
                "INSERT INTO component_import_items(batch_id, component_id, created_component) VALUES (?, ?, ?)",
                [(batch_id, component_id, int(created)) for component_id, created in dedup_items.items()],
            )
            db.executemany(
                "INSERT INTO component_import_memberships(batch_id, component_id, collection_id) VALUES (?, ?, ?)",
                [(batch_id, component_id, collection_id) for component_id, collection_id in dedup_memberships],
            )
            db.executemany(
                "INSERT INTO component_import_collections(batch_id, collection_id, created_collection) VALUES (?, ?, ?)",
                [(batch_id, collection_id, int(created)) for collection_id, created in dedup_collections.items()],
            )
        return {"batch_id": batch_id, "created_at": now, "new_count": new_count, "matched_count": matched_count, "membership_count": len(dedup_memberships)}

    def component_import_batches(self, kind: str = "", limit: int = 20) -> list[dict[str, Any]]:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind and clean_kind not in {"outfit", "scene"}:
            raise ValueError("Import batch kind must be outfit or scene")
        safe_limit = max(1, min(100, int(limit or 20)))
        with _LOCK, self._connection() as db:
            if clean_kind:
                rows = db.execute(
                    "SELECT * FROM component_import_batches WHERE kind=? ORDER BY created_at DESC LIMIT ?",
                    (clean_kind, safe_limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM component_import_batches ORDER BY created_at DESC LIMIT ?",
                    (safe_limit,),
                ).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            try:
                item["source_paths"] = json.loads(str(item.pop("source_paths_json", "[]") or "[]"))
            except Exception:
                item["source_paths"] = []
            output.append(item)
        return output

    def undo_component_import_batch(self, batch_id: str) -> dict[str, Any]:
        clean_batch = str(batch_id or "").strip()
        with _LOCK, self._connection() as db:
            batch = db.execute("SELECT * FROM component_import_batches WHERE batch_id=?", (clean_batch,)).fetchone()
            if batch is None:
                raise ValueError("Import batch no longer exists")
            meta_key = f"component_import_previous_homes:{clean_batch}"
            saved_homes = db.execute("SELECT value FROM schema_meta WHERE key=?", (meta_key,)).fetchone()
            previous = json.loads(saved_homes[0]) if saved_homes else {}
            restore_homes = {}
            for asset_id, home_ids in previous.get("homes", {}).items():
                current_homes = {str(row[0]) for row in db.execute("SELECT collection_id FROM component_collection_memberships WHERE component_id=?", (asset_id,))}
                if current_homes == {previous.get("target")}:
                    restore_homes[asset_id] = home_ids
            membership_rows = db.execute(
                "SELECT component_id, collection_id FROM component_import_memberships WHERE batch_id=?",
                (clean_batch,),
            ).fetchall()
            memberships_removed = 0
            for row in membership_rows:
                collection_id = str(row["collection_id"] or "")
                if collection_id.startswith("library-collection:"):
                    result = db.execute(
                        "DELETE FROM library_collection_memberships WHERE asset_id=? AND collection_id=?",
                        (str(row["component_id"]), collection_id),
                    )
                else:
                    result = db.execute(
                        "DELETE FROM component_collection_memberships WHERE component_id=? AND collection_id=?",
                        (str(row["component_id"]), collection_id),
                    )
                memberships_removed += max(0, int(result.rowcount or 0))

            for asset_id, home_ids in restore_homes.items():
                for home_id in home_ids:
                    db.execute("INSERT OR IGNORE INTO component_collection_memberships(component_id,collection_id,created_at) SELECT ?,collection_id,? FROM component_collections WHERE collection_id=?", (asset_id, _now(), home_id))
            db.execute("DELETE FROM schema_meta WHERE key=?", (meta_key,))
            item_rows = db.execute(
                "SELECT component_id, created_component FROM component_import_items WHERE batch_id=?",
                (clean_batch,),
            ).fetchall()
            removed: list[dict[str, Any]] = []
            retained = 0
            for item in item_rows:
                if not bool(item["created_component"]):
                    continue
                component_id = str(item["component_id"] or "")
                other_batch = db.execute(
                    "SELECT 1 FROM component_import_items WHERE component_id=? AND batch_id<>? LIMIT 1",
                    (component_id, clean_batch),
                ).fetchone()
                remaining_membership = db.execute(
                    """SELECT 1 FROM component_collection_memberships WHERE component_id=?
                    UNION ALL SELECT 1 FROM library_collection_memberships WHERE asset_id=? LIMIT 1""",
                    (component_id, component_id),
                ).fetchone()
                row = db.execute("SELECT * FROM recipe_components WHERE component_id=?", (component_id,)).fetchone()
                if row is None:
                    continue
                if other_batch is not None or remaining_membership is not None or not bool(row["manual"]):
                    retained += 1
                    continue
                removed.append(dict(row))
                db.execute("DELETE FROM recipe_components WHERE component_id=?", (component_id,))

            collection_rows = db.execute(
                "SELECT collection_id, created_collection FROM component_import_collections WHERE batch_id=?",
                (clean_batch,),
            ).fetchall()
            collections_removed = 0
            pending = {
                str(item["collection_id"] or "")
                for item in collection_rows if bool(item["created_collection"]) and str(item["collection_id"] or "")
            }
            while pending:
                changed = False
                for collection_id in list(pending):
                    if collection_id.startswith("library-collection:"):
                        count = int(db.execute(
                            "SELECT COUNT(*) FROM library_collection_memberships WHERE collection_id=?",
                            (collection_id,),
                        ).fetchone()[0])
                        if count:
                            pending.remove(collection_id)
                            continue
                        result = db.execute("DELETE FROM library_collections WHERE collection_id=?", (collection_id,))
                    else:
                        count = int(db.execute(
                            "SELECT COUNT(*) FROM component_collection_memberships WHERE collection_id=?",
                            (collection_id,),
                        ).fetchone()[0])
                        child_count = int(db.execute(
                            "SELECT COUNT(*) FROM component_collections WHERE parent_id=?",
                            (collection_id,),
                        ).fetchone()[0])
                        if count or child_count:
                            continue
                        result = db.execute("DELETE FROM component_collections WHERE collection_id=?", (collection_id,))
                    collections_removed += max(0, int(result.rowcount or 0))
                    pending.remove(collection_id)
                    changed = True
                if not changed:
                    break
            try:
                source_paths = json.loads(str(batch["source_paths_json"] or "[]"))
            except (TypeError, ValueError, json.JSONDecodeError):
                source_paths = []
            collection_mode = str(batch["collection_mode"] or "")
            db.execute("DELETE FROM component_import_batches WHERE batch_id=?", (clean_batch,))
        return {
            "batch_id": clean_batch,
            "kind": str(batch["kind"]),
            "removed": removed,
            "deleted": len(removed),
            "retained": retained,
            "memberships_removed": memberships_removed,
            "collections_removed": collections_removed,
            "source_paths": source_paths if isinstance(source_paths, list) else [],
            "collection_mode": collection_mode,
        }

    def set_recipe_component_preview(self, kind: str, value: str, filename: str, source: str = "generated:catalog") -> dict[str, Any]:
        row = self.upsert_recipe_component(kind, value, manual=False)
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                "UPDATE recipe_components SET preview_ref=?, preview_source=?, preview_updated_at=?, updated_at=? WHERE component_id=?",
                (str(filename or ""), str(source or ""), now, now, str(row["component_id"])),
            )
            updated = db.execute("SELECT * FROM recipe_components WHERE component_id=?", (str(row["component_id"]),)).fetchone()
        return dict(updated) if updated else row

    def clear_recipe_component_previews(self, component_ids: list[str]) -> list[dict[str, Any]]:
        ids = list(dict.fromkeys(str(value or "").strip() for value in component_ids if str(value or "").strip()))
        if not ids:
            return []
        now = _now()
        placeholders = ",".join("?" for _ in ids)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"SELECT component_id, preview_ref FROM recipe_components WHERE component_id IN ({placeholders})",
                ids,
            ).fetchall()
            if rows:
                db.executemany(
                    "UPDATE recipe_components SET preview_ref='', preview_source='', preview_updated_at='', updated_at=? WHERE component_id=?",
                    [(now, str(row["component_id"])) for row in rows],
                )
                self._bump_component_revision(db)
        return [{"component_id": str(row["component_id"]), "removed_preview_ref": str(row["preview_ref"] or "")} for row in rows]

    def clear_recipe_component_preview(self, component_id: str) -> dict[str, Any] | None:
        rows = self.clear_recipe_component_previews([component_id])
        return rows[0] if rows else None

    def delete_recipe_component(self, component_id: str, *, everywhere: bool = False) -> dict[str, Any] | None:
        clean_id = str(component_id or "").strip()
        if not clean_id:
            return None
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT * FROM recipe_components WHERE component_id=?", (clean_id,)).fetchone()
            if row is None:
                return None
            if everywhere:
                db.execute(
                    """INSERT INTO component_tombstones(component_id, kind, value, deleted_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(component_id) DO UPDATE SET kind=excluded.kind, value=excluded.value, deleted_at=excluded.deleted_at""",
                    (clean_id, str(row["kind"] or ""), str(row["value"] or ""), _now()),
                )
            db.execute("DELETE FROM recipe_components WHERE component_id=?", (clean_id,))
        return dict(row)


    def library_collections(self, kind: str) -> list[dict[str, Any]]:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind not in {"outfit", "scene", "wardrobe"}:
            raise ValueError("Collection kind must be outfit, scene, or wardrobe")
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT c.*, COUNT(m.asset_id) AS asset_count
                FROM library_collections c LEFT JOIN library_collection_memberships m ON m.collection_id=c.collection_id
                WHERE c.kind=? GROUP BY c.collection_id ORDER BY c.created_at, c.name COLLATE NOCASE""",
                (clean_kind,),
            ).fetchall()
            memberships = db.execute(
                """SELECT m.collection_id, m.asset_id FROM library_collection_memberships m
                JOIN library_collections c ON c.collection_id=m.collection_id WHERE c.kind=? ORDER BY m.created_at, m.asset_id""",
                (clean_kind,),
            ).fetchall()
        members: dict[str, list[str]] = {}
        for row in memberships:
            members.setdefault(str(row["collection_id"]), []).append(str(row["asset_id"]))
        output = [dict(row) | {"asset_ids": members.get(str(row["collection_id"]), [])} for row in rows]
        if clean_kind in {"outfit", "scene"}:
            order = self.creative_structure_order(clean_kind).get("library_collections", [])
            ranks = {str(value): index for index, value in enumerate(order)}
            output.sort(key=lambda row: ranks.get(str(row["collection_id"]), len(ranks)))
        return output

    def create_library_collection(self, kind: str, name: str, color: str = "") -> dict[str, Any]:
        clean_kind = str(kind or "").strip().lower()
        if clean_kind not in {"outfit", "scene", "wardrobe"}:
            raise ValueError("Collection kind must be outfit, scene, or wardrobe")
        clean_name = " ".join(str(name or "").split())
        if not clean_name:
            raise ValueError("Collection name is required")
        if len(clean_name) > 80:
            raise ValueError("Collection name is limited to 80 characters")
        now = _now(); collection_id = f"library-collection:{clean_kind}:{uuid.uuid4().hex}"
        use_color = str(color or "").strip() or {"outfit":"#f6e65a","scene":"#63e6a4","wardrobe":"#ff9b5f"}[clean_kind]
        with _LOCK, self._connection() as db:
            existing = db.execute("SELECT * FROM library_collections WHERE kind=? AND name=? COLLATE NOCASE", (clean_kind, clean_name)).fetchone()
            if existing is not None:
                row = dict(existing); row["asset_count"] = int(db.execute("SELECT COUNT(*) FROM library_collection_memberships WHERE collection_id=?", (row["collection_id"],)).fetchone()[0]); row["asset_ids"] = []; return row
            db.execute("INSERT INTO library_collections(collection_id,kind,name,color,created_at,updated_at) VALUES(?,?,?,?,?,?)", (collection_id,clean_kind,clean_name,use_color,now,now))
        return {"collection_id":collection_id,"kind":clean_kind,"name":clean_name,"color":use_color,"asset_count":0,"asset_ids":[],"created_at":now,"updated_at":now}

    def update_library_collection(self, collection_id: str, name: str) -> dict[str, Any]:
        clean_id = str(collection_id or "").strip(); clean_name = " ".join(str(name or "").split())
        if not clean_id or not clean_name: raise ValueError("Collection and name are required")
        with _LOCK, self._connection() as db:
            current = db.execute("SELECT kind FROM library_collections WHERE collection_id=?", (clean_id,)).fetchone()
            if current is None: raise ValueError("Collection no longer exists")
            try: db.execute("UPDATE library_collections SET name=?, updated_at=? WHERE collection_id=?", (clean_name,_now(),clean_id))
            except sqlite3.IntegrityError as error: raise ValueError(f"A collection named ‘{clean_name}’ already exists") from error
            row = db.execute("SELECT * FROM library_collections WHERE collection_id=?", (clean_id,)).fetchone()
            count = int(db.execute("SELECT COUNT(*) FROM library_collection_memberships WHERE collection_id=?", (clean_id,)).fetchone()[0])
        return dict(row) | {"asset_count": count, "asset_ids": []}

    def delete_library_collection(self, collection_id: str) -> bool:
        with _LOCK, self._connection() as db:
            result = db.execute("DELETE FROM library_collections WHERE collection_id=?", (str(collection_id or ""),))
        return result.rowcount > 0

    def set_library_asset_collections(self, kind: str, asset_id: str, collection_ids: list[str]) -> list[dict[str, str]]:
        clean_kind = str(kind or "").strip().lower(); clean_asset = str(asset_id or "").strip()
        if clean_kind not in {"outfit","scene","wardrobe"} or not clean_asset: raise ValueError("Asset collection target is invalid")
        requested = list(dict.fromkeys(str(value) for value in collection_ids if str(value)))
        with _LOCK, self._connection() as db:
            if clean_kind in {"outfit","scene"}:
                exists = db.execute("SELECT 1 FROM recipe_components WHERE component_id=? AND kind=?", (clean_asset,clean_kind)).fetchone()
            else:
                exists = db.execute("SELECT 1 FROM wardrobe_items WHERE wardrobe_id=?", (clean_asset,)).fetchone()
            if exists is None: raise ValueError("Library asset no longer exists")
            rows=[]
            if requested:
                placeholders=','.join('?' for _ in requested)
                rows=db.execute(f"SELECT collection_id,name,color FROM library_collections WHERE kind=? AND collection_id IN ({placeholders})", [clean_kind,*requested]).fetchall()
                if len({str(row['collection_id']) for row in rows}) != len(requested): raise ValueError("One or more selected collections no longer exist")
            current = [str(row[0]) for row in db.execute("SELECT collection_id FROM library_collections WHERE kind=?", (clean_kind,)).fetchall()]
            if current:
                placeholders=','.join('?' for _ in current)
                db.execute(f"DELETE FROM library_collection_memberships WHERE asset_id=? AND collection_id IN ({placeholders})", [clean_asset,*current])
            now=_now(); db.executemany("INSERT OR IGNORE INTO library_collection_memberships(collection_id,asset_id,created_at) VALUES(?,?,?)", [(collection_id,clean_asset,now) for collection_id in requested])
        selected={str(row['collection_id']):row for row in rows}
        return [{"collection_id":value,"name":str(selected[value]['name']),"color":str(selected[value]['color'])} for value in requested]

    def add_library_assets_to_collections(self, kind: str, asset_ids: list[str], collection_ids: list[str]) -> dict[str, int]:
        clean_kind=str(kind or "").strip().lower(); ids=list(dict.fromkeys(str(v) for v in asset_ids if str(v))); cols=list(dict.fromkeys(str(v) for v in collection_ids if str(v)))
        if clean_kind not in {"outfit","scene","wardrobe"} or not ids or not cols: raise ValueError("Choose assets and at least one collection")
        with _LOCK, self._connection() as db:
            placeholders=','.join('?' for _ in cols); existing={str(r[0]) for r in db.execute(f"SELECT collection_id FROM library_collections WHERE kind=? AND collection_id IN ({placeholders})", [clean_kind,*cols]).fetchall()}
            if len(existing)!=len(cols): raise ValueError("One or more selected collections no longer exist")
            now=_now(); before=db.total_changes
            db.executemany("INSERT OR IGNORE INTO library_collection_memberships(collection_id,asset_id,created_at) VALUES(?,?,?)", [(c,a,now) for a in ids for c in cols])
            added=db.total_changes-before
        return {"assets":len(ids),"collections":len(cols),"memberships_added":added}

    def remove_library_assets_from_collection(self, kind: str, asset_ids: list[str], collection_id: str) -> dict[str, int]:
        ids = list(dict.fromkeys(str(value) for value in asset_ids if str(value)))
        with _LOCK, self._connection() as db:
            if db.execute("SELECT 1 FROM library_collections WHERE kind=? AND collection_id=?", (kind, collection_id)).fetchone() is None:
                raise ValueError("Collection no longer exists")
            count = 0
            for asset_id in ids:
                count += db.execute("DELETE FROM library_collection_memberships WHERE collection_id=? AND asset_id=?", (collection_id, asset_id)).rowcount
        return {"assets": len(ids), "memberships_removed": count}

    def purge_saved_recipes(self) -> dict[str, Any]:
        with _LOCK, self._connection() as db:
            preview_refs=[str(r[0] or '') for r in db.execute("SELECT preview_ref FROM recipes WHERE preview_ref<>''").fetchall() if str(r[0] or '')]
            count=int(db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]); db.execute("DELETE FROM recipes")
            db.execute("DELETE FROM recipe_collections WHERE NOT EXISTS (SELECT 1 FROM recipe_collection_memberships r WHERE r.collection_id=recipe_collections.collection_id)")
            self._bump_recipe_revision(db)
        return {"recipes":count,"preview_refs":preview_refs}

    def purge_components(self, kind: str) -> dict[str, Any]:
        clean_kind=str(kind or '').strip().lower()
        if clean_kind not in {'outfit','scene'}: raise ValueError('Component kind must be outfit or scene')
        with _LOCK, self._connection() as db:
            rows=db.execute("SELECT component_id,preview_ref FROM recipe_components WHERE kind=?", (clean_kind,)).fetchall(); ids=[str(r['component_id']) for r in rows]
            preview_refs=[str(r['preview_ref'] or '') for r in rows if str(r['preview_ref'] or '')]
            count=len(ids); db.execute("DELETE FROM recipe_components WHERE kind=?", (clean_kind,)); db.execute("DELETE FROM component_collections WHERE kind=?", (clean_kind,)); db.execute("DELETE FROM component_tombstones WHERE kind=?", (clean_kind,)); db.execute("DELETE FROM library_collections WHERE kind=?", (clean_kind,)); db.execute("DELETE FROM schema_meta WHERE key=?", (self._structure_order_key(clean_kind),)); self._bump_component_revision(db)
        return {"kind":clean_kind,"assets":count,"preview_refs":preview_refs}

    def purge_workshop_data(self) -> dict[str, Any]:
        with _LOCK, self._connection() as db:
            fragments=int(db.execute("SELECT COUNT(*) FROM fragment_assets").fetchone()[0]); boards=int(db.execute("SELECT COUNT(*) FROM creative_boards").fetchone()[0]); db.execute("DELETE FROM fragment_assets"); db.execute("DELETE FROM creative_boards"); db.execute("DELETE FROM schema_meta WHERE key IN ('fragment_index_signature')"); self._bump_fragment_revision(db)
        return {"fragments":fragments,"boards":boards}

    def purge_pack_registry(self) -> dict[str, int]:
        with _LOCK, self._connection() as db:
            packs = int(db.execute("SELECT COUNT(*) FROM creative_library_packs").fetchone()[0])
            component_memberships = int(db.execute("SELECT COUNT(*) FROM creative_library_pack_component_memberships").fetchone()[0])
            db.execute("DELETE FROM creative_library_pack_component_memberships")
            db.execute("DELETE FROM creative_library_packs")
            # Structure ordering is user library data too. Clear both the
            # current key namespace and the short-lived legacy namespace so a
            # Total Creative Library Purge really returns navigation to a
            # clean slate.
            db.execute("DELETE FROM schema_meta WHERE key LIKE 'creative_structure_order_v1:%'")
            db.execute("DELETE FROM schema_meta WHERE key LIKE 'creative_structure_order:%'")
        return {"installed_packs": packs, "pack_memberships": component_memberships}

    @staticmethod
    def wardrobe_item_id(item_type: str, value: str) -> str:
        clean_type = str(item_type or "").strip().lower()
        clean_value = " ".join(str(value or "").split())
        digest = hashlib.sha1(f"{clean_type}\0{clean_value.casefold()}".encode("utf-8")).hexdigest()
        return f"wardrobe:{clean_type}:{digest}"

    def upsert_wardrobe_item(self, item_type: str, value: str, *, category: str = "Uncategorized", subtype: str = "", manual: bool = True) -> dict[str, Any]:
        clean_type = str(item_type or "").strip().lower()
        if clean_type not in {"piece", "set", "finisher", "styling"}:
            raise ValueError("Wardrobe item type must be piece, set, finisher, or styling")
        clean_value = " ".join(str(value or "").split())
        if not clean_value:
            raise ValueError("Wardrobe item text is required")
        if len(clean_value) > 8000:
            raise ValueError("Wardrobe item text is limited to 8000 characters")
        clean_category = " ".join(str(category or "Uncategorized").split()) or "Uncategorized"
        clean_subtype = " ".join(str(subtype or "").split())
        wardrobe_id = self.wardrobe_item_id(clean_type, clean_value)
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO wardrobe_items(wardrobe_id, item_type, category, subtype, value, manual, preview_ref, preview_source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?)
                ON CONFLICT(item_type, value) DO UPDATE SET
                    category=CASE WHEN excluded.category!='Uncategorized' THEN excluded.category ELSE wardrobe_items.category END,
                    subtype=CASE WHEN excluded.subtype!='' THEN excluded.subtype ELSE wardrobe_items.subtype END,
                    manual=MAX(wardrobe_items.manual, excluded.manual),
                    updated_at=excluded.updated_at""",
                (wardrobe_id, clean_type, clean_category, clean_subtype, clean_value, int(bool(manual)), now, now),
            )
            row = db.execute("SELECT * FROM wardrobe_items WHERE item_type=? AND value=? COLLATE NOCASE", (clean_type, clean_value)).fetchone()
        return dict(row) if row else {"wardrobe_id": wardrobe_id, "item_type": clean_type, "category": clean_category, "subtype": clean_subtype, "value": clean_value}

    def wardrobe_item_by_value(self, item_type: str, value: str) -> dict[str, Any] | None:
        clean_type = str(item_type or "").strip().lower()
        clean_value = " ".join(str(value or "").split())
        if clean_type not in {"piece", "set", "finisher", "styling"} or not clean_value:
            return None
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT * FROM wardrobe_items WHERE item_type=? AND value=? COLLATE NOCASE", (clean_type, clean_value)).fetchone()
            if row is None:
                return None
            item = dict(row)
            rating = db.execute("SELECT rating FROM wardrobe_reviews WHERE wardrobe_id=?", (str(item["wardrobe_id"]),)).fetchone()
        item["rating"] = max(0, min(5, int(rating["rating"] if rating else 0)))
        return item

    def wardrobe_items(self, item_type: str = "") -> list[dict[str, Any]]:
        clean_type = str(item_type or "").strip().lower()
        params: list[Any] = []
        where = ""
        if clean_type:
            if clean_type not in {"piece", "set", "finisher", "styling"}:
                raise ValueError("Wardrobe item type must be piece, set, finisher, or styling")
            where = "WHERE item_type=?"
            params.append(clean_type)
        with _LOCK, self._connection() as db:
            rows = db.execute(f"SELECT * FROM wardrobe_items {where} ORDER BY created_at, wardrobe_id", params).fetchall()
            output = [dict(row) for row in rows]
            ratings = {str(row["wardrobe_id"]): int(row["rating"] or 0) for row in db.execute("SELECT wardrobe_id, rating FROM wardrobe_reviews").fetchall()}
            by_id = {str(item.get("wardrobe_id") or ""): item for item in output}
            if by_id:
                for row in db.execute("""SELECT m.asset_id, c.collection_id, c.name, c.color
                    FROM library_collection_memberships m JOIN library_collections c ON c.collection_id=m.collection_id
                    WHERE c.kind='wardrobe' ORDER BY c.name COLLATE NOCASE""").fetchall():
                    item = by_id.get(str(row["asset_id"]))
                    if item is not None:
                        item.setdefault("pack_collections", []).append({"collection_id": str(row["collection_id"]), "name": str(row["name"]), "color": str(row["color"])})
        for item in output:
            item.setdefault("pack_collections", [])
            item["rating"] = max(0, min(5, int(ratings.get(str(item.get("wardrobe_id") or ""), 0))))
        return output

    def set_wardrobe_rating(self, wardrobe_id: str, rating: int) -> dict[str, Any]:
        clean_id = str(wardrobe_id or "").strip()
        try:
            clean_rating = int(rating)
        except (TypeError, ValueError):
            raise ValueError("Rating must be a number from 0 to 5")
        if clean_rating < 0 or clean_rating > 5:
            raise ValueError("Rating must be between 0 and 5")
        with _LOCK, self._connection() as db:
            if db.execute("SELECT 1 FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,)).fetchone() is None:
                raise ValueError("Wardrobe item no longer exists")
            if clean_rating == 0:
                db.execute("DELETE FROM wardrobe_reviews WHERE wardrobe_id=?", (clean_id,))
            else:
                db.execute(
                    """INSERT INTO wardrobe_reviews(wardrobe_id, rating, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(wardrobe_id) DO UPDATE SET rating=excluded.rating, updated_at=excluded.updated_at""",
                    (clean_id, clean_rating, _now()),
                )
        return {"wardrobe_id": clean_id, "rating": clean_rating}

    def set_wardrobe_preview(self, item_type: str, value: str, filename: str, source: str = "generated:catalog", *, category: str = "Uncategorized", subtype: str = "") -> dict[str, Any]:
        row = self.upsert_wardrobe_item(item_type, value, category=category, subtype=subtype, manual=False)
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute("UPDATE wardrobe_items SET preview_ref=?, preview_source=?, preview_updated_at=?, updated_at=? WHERE wardrobe_id=?", (str(filename or ""), str(source or ""), now, now, str(row["wardrobe_id"])))
            updated = db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (str(row["wardrobe_id"]),)).fetchone()
        return dict(updated) if updated else row

    def clear_wardrobe_preview(self, wardrobe_id: str) -> dict[str, Any] | None:
        clean_id = str(wardrobe_id or "").strip()
        if not clean_id:
            return None
        now = _now()
        with _LOCK, self._connection() as db:
            previous = db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,)).fetchone()
            if previous is None:
                return None
            previous_data = dict(previous)
            db.execute(
                "UPDATE wardrobe_items SET preview_ref='', preview_source='', preview_updated_at='', updated_at=? WHERE wardrobe_id=?",
                (now, clean_id),
            )
            updated = db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,)).fetchone()
        result = dict(updated) if updated else previous_data
        result["removed_preview_ref"] = str(previous_data.get("preview_ref") or "")
        return result

    def update_wardrobe_item(self, wardrobe_id: str, item_type: str, value: str, *, category: str = "Uncategorized", subtype: str = "") -> dict[str, Any]:
        clean_id = str(wardrobe_id or "").strip()
        clean_type = str(item_type or "").strip().lower()
        if clean_type not in {"piece", "set", "finisher", "styling"}:
            raise ValueError("Wardrobe item type must be piece, set, finisher, or styling")
        clean_value = " ".join(str(value or "").split())
        if not clean_value:
            raise ValueError("Wardrobe item text is required")
        if len(clean_value) > 8000:
            raise ValueError("Wardrobe item text is limited to 8000 characters")
        clean_category = " ".join(str(category or "Uncategorized").split()) or "Uncategorized"
        clean_subtype = " ".join(str(subtype or "").split())
        now = _now()
        with _LOCK, self._connection() as db:
            previous = db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,)).fetchone()
            if previous is None:
                raise ValueError("Wardrobe item no longer exists")
            previous = dict(previous)
            next_id = self.wardrobe_item_id(clean_type, clean_value)
            if next_id == clean_id:
                db.execute(
                    "UPDATE wardrobe_items SET item_type=?, category=?, subtype=?, value=?, updated_at=? WHERE wardrobe_id=?",
                    (clean_type, clean_category, clean_subtype, clean_value, now, clean_id),
                )
                row = db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,)).fetchone()
                rating = db.execute("SELECT rating FROM wardrobe_reviews WHERE wardrobe_id=?", (clean_id,)).fetchone()
                result = dict(row) if row else previous
                result["rating"] = max(0, min(5, int(rating["rating"] if rating else 0)))
                result["merged"] = False
                return result

            target = db.execute(
                "SELECT * FROM wardrobe_items WHERE item_type=? AND value=? COLLATE NOCASE",
                (clean_type, clean_value),
            ).fetchone()
            if target is None:
                db.execute(
                    """INSERT INTO wardrobe_items(wardrobe_id, item_type, category, subtype, value, manual, preview_ref, preview_source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (next_id, clean_type, clean_category, clean_subtype, clean_value, int(previous.get("manual") or 0),
                     str(previous.get("preview_ref") or ""), str(previous.get("preview_source") or ""),
                     str(previous.get("created_at") or now), now),
                )
                target_id = next_id
                merged = False
            else:
                target = dict(target)
                target_id = str(target.get("wardrobe_id") or next_id)
                preview_ref = str(target.get("preview_ref") or previous.get("preview_ref") or "")
                preview_source = str(target.get("preview_source") or (previous.get("preview_source") if not target.get("preview_ref") else "") or "")
                manual = max(int(target.get("manual") or 0), int(previous.get("manual") or 0))
                created_at = min(str(target.get("created_at") or now), str(previous.get("created_at") or now))
                db.execute(
                    """UPDATE wardrobe_items SET category=?, subtype=?, value=?, manual=?, preview_ref=?, preview_source=?, created_at=?, updated_at=?
                    WHERE wardrobe_id=?""",
                    (clean_category, clean_subtype, clean_value, manual, preview_ref, preview_source, created_at, now, target_id),
                )
                merged = True

            db.execute(
                """INSERT OR IGNORE INTO wardrobe_item_sources(wardrobe_id, source_id, created_at)
                SELECT ?, source_id, created_at FROM wardrobe_item_sources WHERE wardrobe_id=?""",
                (target_id, clean_id),
            )
            for part in db.execute(
                "SELECT look_component_id, position, relation, source_text, created_at FROM wardrobe_look_parts WHERE wardrobe_id=?",
                (clean_id,),
            ).fetchall():
                db.execute(
                    """INSERT OR IGNORE INTO wardrobe_look_parts(look_component_id, wardrobe_id, position, relation, source_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (str(part["look_component_id"]), target_id, int(part["position"] or 0), str(part["relation"] or ""),
                     str(part["source_text"] or ""), str(part["created_at"] or now)),
                )
            old_rating = db.execute("SELECT rating FROM wardrobe_reviews WHERE wardrobe_id=?", (clean_id,)).fetchone()
            target_rating = db.execute("SELECT rating FROM wardrobe_reviews WHERE wardrobe_id=?", (target_id,)).fetchone()
            merged_rating = max(int(old_rating["rating"] if old_rating else 0), int(target_rating["rating"] if target_rating else 0))
            if merged_rating:
                db.execute(
                    """INSERT INTO wardrobe_reviews(wardrobe_id, rating, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(wardrobe_id) DO UPDATE SET rating=MAX(wardrobe_reviews.rating, excluded.rating), updated_at=excluded.updated_at""",
                    (target_id, merged_rating, now),
                )
            db.execute("DELETE FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,))
            row = db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (target_id,)).fetchone()
            result = dict(row) if row else {"wardrobe_id": target_id, "item_type": clean_type, "category": clean_category, "subtype": clean_subtype, "value": clean_value}
            result["rating"] = merged_rating
            result["merged"] = merged
            result["previous_wardrobe_id"] = clean_id
            return result

    def delete_wardrobe_item(self, wardrobe_id: str) -> dict[str, Any] | None:
        clean_id = str(wardrobe_id or "").strip()
        if not clean_id:
            return None
        with _LOCK, self._connection() as db:
            row = db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,)).fetchone()
            if row is None:
                return None
            db.execute("DELETE FROM wardrobe_items WHERE wardrobe_id=?", (clean_id,))
        return dict(row)

    def purge_wardrobe(self) -> dict[str, Any]:
        """Reset the derived Wardrobe layer while preserving source Outfit Looks.

        This is intentionally broader than deleting individual Pieces: it clears
        Pieces/Sets/Finishers/Body Styling, ratings, source links, Look-to-item
        relationships, migration decisions, and installed Wardrobe Pack
        provenance.  The underlying recipe_components Outfit Looks and their
        collections/previews remain untouched so migration can be tested again
        from a truly clean Wardrobe state.
        """
        with _LOCK, self._connection() as db:
            preview_refs = [
                str(row["preview_ref"] or "")
                for row in db.execute("SELECT preview_ref FROM wardrobe_items WHERE preview_ref<>''").fetchall()
                if str(row["preview_ref"] or "")
            ]
            counts = {
                "items": int(db.execute("SELECT COUNT(*) FROM wardrobe_items").fetchone()[0]),
                "migration_states": int(db.execute("SELECT COUNT(*) FROM wardrobe_migration_state").fetchone()[0]),
                "sources": int(db.execute("SELECT COUNT(*) FROM wardrobe_sources").fetchone()[0]),
                "packs": int(db.execute("SELECT COUNT(*) FROM wardrobe_packs").fetchone()[0]),
                "relationships": int(db.execute("SELECT COUNT(*) FROM wardrobe_look_parts").fetchone()[0]),
            }
            # Dependent rows cascade from wardrobe_items / wardrobe_packs, but
            # clear explicit state tables too so every Look is eligible for a
            # fresh migration analysis immediately after the purge.
            db.execute("DELETE FROM wardrobe_migration_state")
            db.execute("DELETE FROM wardrobe_items")
            db.execute("DELETE FROM wardrobe_sources")
            db.execute("DELETE FROM wardrobe_packs")
            db.execute("DELETE FROM library_collections WHERE kind='wardrobe'")
        return {**counts, "preview_refs": preview_refs, "previews": len(preview_refs)}

    @staticmethod
    def wardrobe_source_id(source_type: str, source_key: str) -> str:
        clean_type = str(source_type or "").strip().lower() or "unknown"
        clean_key = " ".join(str(source_key or "").split()) or "unknown"
        digest = hashlib.sha1(f"{clean_type}\0{clean_key.casefold()}".encode("utf-8")).hexdigest()
        return f"wardrobe-source:{clean_type}:{digest}"

    def upsert_wardrobe_source(self, source_type: str, source_key: str, *, label: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_type = str(source_type or "").strip().lower() or "unknown"
        clean_key = " ".join(str(source_key or "").split()) or "unknown"
        clean_label = " ".join(str(label or "").split())
        source_id = self.wardrobe_source_id(clean_type, clean_key)
        now = _now()
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO wardrobe_sources(source_id, source_type, source_key, label, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_key) DO UPDATE SET
                    label=CASE WHEN excluded.label<>'' THEN excluded.label ELSE wardrobe_sources.label END,
                    metadata_json=CASE WHEN excluded.metadata_json<>'{}' THEN excluded.metadata_json ELSE wardrobe_sources.metadata_json END,
                    updated_at=excluded.updated_at""",
                (source_id, clean_type, clean_key, clean_label, metadata_json, now, now),
            )
            row = db.execute("SELECT * FROM wardrobe_sources WHERE source_type=? AND source_key=?", (clean_type, clean_key)).fetchone()
        return dict(row) if row else {"source_id": source_id, "source_type": clean_type, "source_key": clean_key, "label": clean_label}

    def link_wardrobe_source(self, wardrobe_id: str, source_id: str) -> None:
        with _LOCK, self._connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO wardrobe_item_sources(wardrobe_id, source_id, created_at) VALUES (?, ?, ?)",
                (str(wardrobe_id), str(source_id), _now()),
            )

    def wardrobe_item_sources(self, wardrobe_id: str = "") -> list[dict[str, Any]]:
        clean_id = str(wardrobe_id or "").strip()
        params: list[Any] = []
        where = ""
        if clean_id:
            where = "WHERE m.wardrobe_id=?"
            params.append(clean_id)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"""SELECT m.wardrobe_id, s.* FROM wardrobe_item_sources m
                JOIN wardrobe_sources s ON s.source_id=m.source_id {where}
                ORDER BY s.source_type, s.label COLLATE NOCASE, s.source_key COLLATE NOCASE""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def set_wardrobe_look_parts(self, look_component_id: str, parts: list[dict[str, Any]]) -> None:
        look_id = str(look_component_id or "").strip()
        if not look_id:
            raise ValueError("Look component ID is required")
        now = _now()
        with _LOCK, self._connection() as db:
            if db.execute("SELECT 1 FROM recipe_components WHERE component_id=? AND kind='outfit'", (look_id,)).fetchone() is None:
                raise ValueError("Outfit Look no longer exists")
            db.execute("DELETE FROM wardrobe_look_parts WHERE look_component_id=?", (look_id,))
            for position, part in enumerate(parts):
                wardrobe_id = str(part.get("wardrobe_id") or "").strip()
                if not wardrobe_id:
                    continue
                db.execute(
                    """INSERT OR IGNORE INTO wardrobe_look_parts(look_component_id, wardrobe_id, position, relation, source_text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (look_id, wardrobe_id, position, str(part.get("relation") or ""), str(part.get("source_text") or ""), now),
                )

    def wardrobe_look_parts(self, look_component_id: str = "") -> list[dict[str, Any]]:
        clean_id = str(look_component_id or "").strip()
        params: list[Any] = []
        where = ""
        if clean_id:
            where = "WHERE p.look_component_id=?"
            params.append(clean_id)
        with _LOCK, self._connection() as db:
            rows = db.execute(
                f"""SELECT p.look_component_id, p.position, p.relation, p.source_text,
                w.wardrobe_id, w.item_type, w.category, w.subtype, w.value, w.preview_ref, w.preview_source
                FROM wardrobe_look_parts p JOIN wardrobe_items w ON w.wardrobe_id=p.wardrobe_id
                {where} ORDER BY p.look_component_id, p.position""",
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def set_wardrobe_migration_state(self, look_component_id: str, *, parser_version: str, status: str, confidence: float, proposal: dict[str, Any]) -> None:
        clean_status = str(status or "unreviewed").strip().lower()
        if clean_status not in {"unreviewed", "ready", "review", "unresolved", "accepted", "ignored"}:
            raise ValueError("Unsupported wardrobe migration status")
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO wardrobe_migration_state(look_component_id, parser_version, status, confidence, proposal_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(look_component_id) DO UPDATE SET parser_version=excluded.parser_version,
                    status=excluded.status, confidence=excluded.confidence, proposal_json=excluded.proposal_json, updated_at=excluded.updated_at""",
                (str(look_component_id), str(parser_version), clean_status, float(confidence or 0), json.dumps(proposal or {}, ensure_ascii=False), _now()),
            )

    def set_wardrobe_migration_states_bulk(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        now = _now()
        with _LOCK, self._connection() as db:
            db.executemany(
                """INSERT INTO wardrobe_migration_state(look_component_id, parser_version, status, confidence, proposal_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(look_component_id) DO UPDATE SET parser_version=excluded.parser_version,
                    status=excluded.status, confidence=excluded.confidence, proposal_json=excluded.proposal_json, updated_at=excluded.updated_at""",
                [(
                    str(row.get("look_component_id") or ""), str(row.get("parser_version") or ""),
                    str(row.get("status") or "unreviewed"), float(row.get("confidence") or 0),
                    json.dumps(row.get("proposal") or {}, ensure_ascii=False), now,
                ) for row in rows if str(row.get("look_component_id") or "")],
            )

    def apply_wardrobe_migration_batch(self, entries: list[dict[str, Any]], *, parser_version: str) -> dict[str, int]:
        if not entries:
            return {"accepted_looks": 0, "created_items": 0, "matched_items": 0, "linked_parts": 0}
        now = _now()
        accepted = created = matched = linked = 0
        with _LOCK, self._connection() as db:
            alias_items: dict[tuple[str, str], dict[str, Any]] = {}
            for row in db.execute("SELECT wardrobe_id, item_type, category, subtype, value FROM wardrobe_items").fetchall():
                alias = _wardrobe_alias_key(str(row["value"] or ""))
                if alias:
                    alias_items.setdefault((str(row["item_type"] or "piece"), alias), dict(row))
            for entry in entries:
                look_id = str(entry.get("look_component_id") or "").strip()
                proposal = entry.get("proposal") if isinstance(entry.get("proposal"), dict) else {}
                confidence = float(entry.get("confidence") or proposal.get("confidence") or 0)
                look = db.execute("SELECT value FROM recipe_components WHERE component_id=? AND kind='outfit'", (look_id,)).fetchone()
                if look is None:
                    continue
                source_id = self.wardrobe_source_id("look", look_id)
                label = str(look["value"] or "")[:160]
                db.execute(
                    """INSERT INTO wardrobe_sources(source_id, source_type, source_key, label, metadata_json, created_at, updated_at)
                    VALUES (?, 'look', ?, ?, ?, ?, ?)
                    ON CONFLICT(source_type, source_key) DO UPDATE SET label=excluded.label, metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
                    (source_id, look_id, label, json.dumps({"parser_version": parser_version}, ensure_ascii=False), now, now),
                )
                previous_item_ids = [str(row["wardrobe_id"]) for row in db.execute("SELECT wardrobe_id FROM wardrobe_look_parts WHERE look_component_id=?", (look_id,)).fetchall()]
                db.execute("DELETE FROM wardrobe_look_parts WHERE look_component_id=?", (look_id,))
                part_count = 0
                current_item_ids: set[str] = set()
                for position, item in enumerate(proposal.get("items") or []):
                    if not isinstance(item, dict):
                        continue
                    item_type = str(item.get("item_type") or "piece").strip().lower()
                    if item_type not in {"piece", "set", "finisher", "styling"}:
                        continue
                    value = " ".join(str(item.get("value") or "").split())
                    if not value:
                        continue
                    category = " ".join(str(item.get("category") or "Uncategorized").split()) or "Uncategorized"
                    subtype = " ".join(str(item.get("subtype") or "").split())
                    alias_key = _wardrobe_alias_key(value)
                    alias_match = alias_items.get((item_type, alias_key)) if alias_key else None
                    if alias_match:
                        wardrobe_id = str(alias_match["wardrobe_id"])
                        existed = True
                        db.execute(
                            """UPDATE wardrobe_items SET
                                category=CASE WHEN category='Uncategorized' AND ?!='Uncategorized' THEN ? ELSE category END,
                                subtype=CASE WHEN subtype='' AND ?!='' THEN ? ELSE subtype END,
                                updated_at=? WHERE wardrobe_id=?""",
                            (category, category, subtype, subtype, now, wardrobe_id),
                        )
                    else:
                        wardrobe_id = self.wardrobe_item_id(item_type, value)
                        existed = db.execute("SELECT 1 FROM wardrobe_items WHERE wardrobe_id=?", (wardrobe_id,)).fetchone() is not None
                        db.execute(
                            """INSERT INTO wardrobe_items(wardrobe_id, item_type, category, subtype, value, manual, preview_ref, preview_source, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, 0, '', '', ?, ?)
                            ON CONFLICT(item_type, value) DO UPDATE SET
                                category=CASE WHEN excluded.category!='Uncategorized' THEN excluded.category ELSE wardrobe_items.category END,
                                subtype=CASE WHEN excluded.subtype!='' THEN excluded.subtype ELSE wardrobe_items.subtype END,
                                updated_at=excluded.updated_at""",
                            (wardrobe_id, item_type, category, subtype, value, now, now),
                        )
                        if alias_key:
                            alias_items[(item_type, alias_key)] = {"wardrobe_id": wardrobe_id, "item_type": item_type, "category": category, "subtype": subtype, "value": value}
                    created += int(not existed); matched += int(existed)
                    db.execute("INSERT OR IGNORE INTO wardrobe_item_sources(wardrobe_id, source_id, created_at) VALUES (?, ?, ?)", (wardrobe_id, source_id, now))
                    db.execute(
                        """INSERT OR IGNORE INTO wardrobe_look_parts(look_component_id, wardrobe_id, position, relation, source_text, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (look_id, wardrobe_id, position, str(item.get("relation") or ""), value, now),
                    )
                    current_item_ids.add(wardrobe_id)
                    part_count += 1; linked += 1
                for previous_id in previous_item_ids:
                    if previous_id in current_item_ids:
                        continue
                    db.execute("DELETE FROM wardrobe_item_sources WHERE wardrobe_id=? AND source_id=?", (previous_id, source_id))
                    old_item = db.execute("SELECT manual FROM wardrobe_items WHERE wardrobe_id=?", (previous_id,)).fetchone()
                    if old_item is not None and not int(old_item["manual"] or 0):
                        still_linked = db.execute("SELECT 1 FROM wardrobe_look_parts WHERE wardrobe_id=? LIMIT 1", (previous_id,)).fetchone()
                        still_sourced = db.execute("SELECT 1 FROM wardrobe_item_sources WHERE wardrobe_id=? LIMIT 1", (previous_id,)).fetchone()
                        if still_linked is None and still_sourced is None:
                            db.execute("DELETE FROM wardrobe_items WHERE wardrobe_id=?", (previous_id,))
                if part_count:
                    proposal = dict(proposal); proposal["accepted_items"] = part_count
                    db.execute(
                        """INSERT INTO wardrobe_migration_state(look_component_id, parser_version, status, confidence, proposal_json, updated_at)
                        VALUES (?, ?, 'accepted', ?, ?, ?)
                        ON CONFLICT(look_component_id) DO UPDATE SET parser_version=excluded.parser_version, status='accepted',
                            confidence=excluded.confidence, proposal_json=excluded.proposal_json, updated_at=excluded.updated_at""",
                        (look_id, parser_version, confidence, json.dumps(proposal, ensure_ascii=False), now),
                    )
                    accepted += 1
        return {"accepted_looks": accepted, "created_items": created, "matched_items": matched, "linked_parts": linked}

    def wardrobe_migration_states(self) -> dict[str, dict[str, Any]]:
        with _LOCK, self._connection() as db:
            rows = db.execute("SELECT * FROM wardrobe_migration_state").fetchall()
        result: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            try:
                item["proposal"] = json.loads(str(item.pop("proposal_json") or "{}"))
            except Exception:
                item["proposal"] = {}
            result[str(item["look_component_id"])] = item
        return result

    def upsert_wardrobe_pack(self, manifest: dict[str, Any]) -> dict[str, Any]:
        pack_id = str(manifest.get("pack_id") or "").strip()
        if not pack_id:
            raise ValueError("Wardrobe pack ID is required")
        name = " ".join(str(manifest.get("name") or "Wardrobe Pack").split()) or "Wardrobe Pack"
        creator = " ".join(str(manifest.get("creator") or "").split())
        version = " ".join(str(manifest.get("version") or "").split())
        description = str(manifest.get("description") or "").strip()
        now = _now()
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO wardrobe_packs(pack_id, name, creator, version, description, manifest_json, installed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pack_id) DO UPDATE SET name=excluded.name, creator=excluded.creator, version=excluded.version,
                    description=excluded.description, manifest_json=excluded.manifest_json, updated_at=excluded.updated_at""",
                (pack_id, name, creator, version, description, json.dumps(manifest, ensure_ascii=False), now, now),
            )
            row = db.execute("SELECT * FROM wardrobe_packs WHERE pack_id=?", (pack_id,)).fetchone()
        return dict(row) if row else {"pack_id": pack_id, "name": name, "creator": creator, "version": version}

    def record_wardrobe_pack_look(self, pack_id: str, component_id: str, *, created_component: bool) -> None:
        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO wardrobe_pack_looks(pack_id, component_id, created_component) VALUES (?, ?, ?)
                ON CONFLICT(pack_id, component_id) DO UPDATE SET created_component=MAX(wardrobe_pack_looks.created_component, excluded.created_component)""",
                (str(pack_id), str(component_id), int(bool(created_component))),
            )

    def wardrobe_packs(self) -> list[dict[str, Any]]:
        with _LOCK, self._connection() as db:
            rows = db.execute("SELECT * FROM wardrobe_packs ORDER BY updated_at DESC, name COLLATE NOCASE").fetchall()
        return [dict(row) for row in rows]

    def merge_wardrobe_pack_records(
        self,
        manifest: dict[str, Any],
        looks: list[dict[str, Any]],
        items: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Merge a portable Wardrobe Pack in one SQLite transaction.

        Preview bytes stay outside the catalog layer. The returned preview queues
        tell the caller which local assets are still missing an image so it can
        validate/save those images and commit their refs in one follow-up write.
        Existing ratings and previews always win over imported values.
        """
        pack_id = str(manifest.get("pack_id") or "").strip()
        if not pack_id:
            raise ValueError("Wardrobe pack ID is required")
        pack_name = " ".join(str(manifest.get("name") or "Wardrobe Pack").split()) or "Wardrobe Pack"
        creator = " ".join(str(manifest.get("creator") or "").split())
        version = " ".join(str(manifest.get("version") or "").split())
        description = str(manifest.get("description") or "").strip()
        backup_mode = str(manifest.get("export_mode") or "pack").strip().lower() == "backup"
        now = _now()
        pack_source_id = self.wardrobe_source_id("pack", pack_id)

        created_looks = matched_looks = created_items = matched_items = collections_added = 0
        look_map: dict[str, dict[str, Any]] = {}
        item_map: dict[tuple[str, str], dict[str, Any]] = {}
        look_preview_queue: list[dict[str, str]] = []
        item_preview_queue: list[dict[str, str]] = []

        with _LOCK, self._connection() as db:
            db.execute(
                """INSERT INTO wardrobe_packs(pack_id, name, creator, version, description, manifest_json, installed_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(pack_id) DO UPDATE SET name=excluded.name, creator=excluded.creator, version=excluded.version,
                    description=excluded.description, manifest_json=excluded.manifest_json, updated_at=excluded.updated_at""",
                (pack_id, pack_name, creator, version, description, json.dumps(manifest, ensure_ascii=False), now, now),
            )
            db.execute(
                """INSERT INTO wardrobe_sources(source_id, source_type, source_key, label, metadata_json, created_at, updated_at)
                VALUES (?, 'pack', ?, ?, ?, ?, ?)
                ON CONFLICT(source_type, source_key) DO UPDATE SET label=excluded.label, metadata_json=excluded.metadata_json, updated_at=excluded.updated_at""",
                (pack_source_id, pack_id, pack_name, json.dumps({"version": version, "creator": creator}, ensure_ascii=False), now, now),
            )

            existing_looks = {str(row["value"] or "").casefold(): dict(row) for row in db.execute("SELECT * FROM recipe_components WHERE kind='outfit'").fetchall()}
            look_ratings = {str(row["component_id"]): int(row["rating"] or 0) for row in db.execute(
                """SELECT c.component_id, COALESCE(r.rating, 0) AS rating FROM recipe_components c
                LEFT JOIN component_reviews r ON r.component_id=c.component_id WHERE c.kind='outfit'"""
            ).fetchall()}
            existing_items = {(str(row["item_type"] or "piece"), str(row["value"] or "").casefold()): dict(row) for row in db.execute("SELECT * FROM wardrobe_items").fetchall()}
            item_ratings = {str(row["wardrobe_id"]): int(row["rating"] or 0) for row in db.execute(
                """SELECT w.wardrobe_id, COALESCE(r.rating, 0) AS rating FROM wardrobe_items w
                LEFT JOIN wardrobe_reviews r ON r.wardrobe_id=w.wardrobe_id"""
            ).fetchall()}
            collections = {str(row["name"] or "").casefold(): dict(row) for row in db.execute("SELECT * FROM component_collections WHERE kind='outfit'").fetchall()}

            for entry in looks:
                value = " ".join(str(entry.get("value") or "").split())
                if not value or len(value) > 8000:
                    continue
                key = value.casefold()
                before = existing_looks.get(key)
                component_id = str(before.get("component_id")) if before else self.recipe_component_id("outfit", value)
                db.execute(
                    """INSERT INTO recipe_components(component_id, kind, value, manual, preview_ref, preview_source, created_at, updated_at)
                    VALUES (?, 'outfit', ?, 1, '', '', ?, ?)
                    ON CONFLICT(kind, value) DO UPDATE SET manual=MAX(recipe_components.manual, 1), updated_at=excluded.updated_at""",
                    (component_id, value, now, now),
                )
                if before is None:
                    created_looks += 1
                else:
                    matched_looks += 1
                current = dict(db.execute("SELECT * FROM recipe_components WHERE component_id=?", (component_id,)).fetchone())
                existing_looks[key] = current
                look_map[key] = current
                db.execute(
                    """INSERT INTO wardrobe_pack_looks(pack_id, component_id, created_component) VALUES (?, ?, ?)
                    ON CONFLICT(pack_id, component_id) DO UPDATE SET created_component=MAX(wardrobe_pack_looks.created_component, excluded.created_component)""",
                    (pack_id, component_id, int(before is None)),
                )
                imported_rating = max(0, min(5, int(entry.get("rating") or 0)))
                if imported_rating and int(look_ratings.get(component_id, 0)) == 0:
                    db.execute(
                        """INSERT INTO component_reviews(component_id, rating, updated_at) VALUES (?, ?, ?)
                        ON CONFLICT(component_id) DO UPDATE SET rating=excluded.rating, updated_at=excluded.updated_at""",
                        (component_id, imported_rating, now),
                    )
                    look_ratings[component_id] = imported_rating
                for group in entry.get("collections") or []:
                    if not isinstance(group, dict):
                        continue
                    group_name = " ".join(str(group.get("name") or "").split())
                    if not group_name or len(group_name) > 80:
                        continue
                    group_key = group_name.casefold()
                    group_row = collections.get(group_key)
                    if group_row is None:
                        raw_color = str(group.get("color") or "").strip()
                        valid_color = len(raw_color) == 7 and raw_color.startswith("#") and all(ch in "0123456789abcdefABCDEF" for ch in raw_color[1:])
                        color = raw_color if valid_color else RECIPE_COLLECTION_COLORS[len(collections) % len(RECIPE_COLLECTION_COLORS)]
                        collection_id = f"component-collection:outfit:{uuid.uuid4().hex}"
                        db.execute(
                            "INSERT INTO component_collections(collection_id, kind, name, color, created_at, updated_at) VALUES (?, 'outfit', ?, ?, ?, ?)",
                            (collection_id, group_name, color, now, now),
                        )
                        group_row = {"collection_id": collection_id, "name": group_name, "color": color}
                        collections[group_key] = group_row
                        collections_added += 1
                    db.execute(
                        "INSERT OR IGNORE INTO component_collection_memberships(component_id, collection_id, created_at) VALUES (?, ?, ?)",
                        (component_id, str(group_row["collection_id"]), now),
                    )
                preview_member = str(entry.get("preview") or "").strip()
                if preview_member and not str(current.get("preview_ref") or ""):
                    look_preview_queue.append({"component_id": component_id, "value": value, "preview": preview_member})

            for entry in items:
                item_type = str(entry.get("item_type") or "piece").strip().lower()
                value = " ".join(str(entry.get("value") or "").split())
                if item_type not in {"piece", "set", "finisher", "styling"} or not value or len(value) > 8000:
                    continue
                category = " ".join(str(entry.get("category") or "Uncategorized").split()) or "Uncategorized"
                subtype = " ".join(str(entry.get("subtype") or "").split())
                key = (item_type, value.casefold())
                before = existing_items.get(key)
                wardrobe_id = str(before.get("wardrobe_id")) if before else self.wardrobe_item_id(item_type, value)
                db.execute(
                    """INSERT INTO wardrobe_items(wardrobe_id, item_type, category, subtype, value, manual, preview_ref, preview_source, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 0, '', '', ?, ?)
                    ON CONFLICT(item_type, value) DO UPDATE SET
                        category=CASE WHEN wardrobe_items.category='Uncategorized' AND excluded.category!='Uncategorized' THEN excluded.category ELSE wardrobe_items.category END,
                        subtype=CASE WHEN wardrobe_items.subtype='' AND excluded.subtype!='' THEN excluded.subtype ELSE wardrobe_items.subtype END,
                        updated_at=excluded.updated_at""",
                    (wardrobe_id, item_type, category, subtype, value, now, now),
                )
                if before is None:
                    created_items += 1
                else:
                    matched_items += 1
                current = dict(db.execute("SELECT * FROM wardrobe_items WHERE wardrobe_id=?", (wardrobe_id,)).fetchone())
                existing_items[key] = current
                item_map[key] = current
                db.execute("INSERT OR IGNORE INTO wardrobe_item_sources(wardrobe_id, source_id, created_at) VALUES (?, ?, ?)", (wardrobe_id, pack_source_id, now))
                if backup_mode:
                    for raw_source in entry.get("sources") or []:
                        if not isinstance(raw_source, dict):
                            continue
                        source_type = str(raw_source.get("source_type") or "").strip().lower()
                        source_key = " ".join(str(raw_source.get("source_key") or "").split())
                        if not source_type or not source_key or source_type == "pack":
                            continue
                        source_id = self.wardrobe_source_id(source_type, source_key)
                        label = " ".join(str(raw_source.get("label") or "").split())
                        try:
                            metadata = json.loads(str(raw_source.get("metadata_json") or "{}"))
                        except Exception:
                            metadata = {}
                        db.execute(
                            """INSERT INTO wardrobe_sources(source_id, source_type, source_key, label, metadata_json, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(source_type, source_key) DO UPDATE SET
                                label=CASE WHEN excluded.label<>'' THEN excluded.label ELSE wardrobe_sources.label END,
                                metadata_json=CASE WHEN excluded.metadata_json<>'{}' THEN excluded.metadata_json ELSE wardrobe_sources.metadata_json END,
                                updated_at=excluded.updated_at""",
                            (source_id, source_type, source_key, label, json.dumps(metadata if isinstance(metadata, dict) else {}, ensure_ascii=False, sort_keys=True), now, now),
                        )
                        db.execute("INSERT OR IGNORE INTO wardrobe_item_sources(wardrobe_id, source_id, created_at) VALUES (?, ?, ?)", (wardrobe_id, source_id, now))
                imported_rating = max(0, min(5, int(entry.get("rating") or 0)))
                if imported_rating and int(item_ratings.get(wardrobe_id, 0)) == 0:
                    db.execute(
                        """INSERT INTO wardrobe_reviews(wardrobe_id, rating, updated_at) VALUES (?, ?, ?)
                        ON CONFLICT(wardrobe_id) DO UPDATE SET rating=excluded.rating, updated_at=excluded.updated_at""",
                        (wardrobe_id, imported_rating, now),
                    )
                    item_ratings[wardrobe_id] = imported_rating
                preview_member = str(entry.get("preview") or "").strip()
                if preview_member and item_type != "finisher" and not str(current.get("preview_ref") or ""):
                    item_preview_queue.append({"wardrobe_id": wardrobe_id, "item_type": item_type, "value": value, "category": category, "subtype": subtype, "preview": preview_member})

            relations_by_look: dict[str, list[tuple[int, str, str, str]]] = {}
            for relation in relationships:
                if not isinstance(relation, dict):
                    continue
                look_value = " ".join(str(relation.get("look_value") or "").split())
                item_type = str(relation.get("item_type") or "piece").strip().lower()
                item_value = " ".join(str(relation.get("item_value") or "").split())
                look = look_map.get(look_value.casefold())
                item = item_map.get((item_type, item_value.casefold()))
                if not look or not item:
                    continue
                look_id = str(look["component_id"]); wardrobe_id = str(item["wardrobe_id"])
                relations_by_look.setdefault(look_id, []).append((
                    int(relation.get("position") or 0), wardrobe_id, str(relation.get("relation") or ""),
                    str(relation.get("source_text") or item_value),
                ))
            for look_id, parts in relations_by_look.items():
                db.execute("DELETE FROM wardrobe_look_parts WHERE look_component_id=?", (look_id,))
                for position, wardrobe_id, relation, source_text in sorted(parts, key=lambda row: row[0]):
                    db.execute(
                        """INSERT OR IGNORE INTO wardrobe_look_parts(look_component_id, wardrobe_id, position, relation, source_text, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (look_id, wardrobe_id, position, relation, source_text, now),
                    )

        return {
            "pack_id": pack_id, "name": pack_name,
            "created_looks": created_looks, "matched_looks": matched_looks,
            "created_items": created_items, "matched_items": matched_items, "collections_added": collections_added,
            "look_previews": look_preview_queue, "item_previews": item_preview_queue,
        }

    def set_wardrobe_pack_previews_bulk(
        self,
        *,
        look_previews: list[dict[str, str]] | None = None,
        item_previews: list[dict[str, str]] | None = None,
        source: str = "",
    ) -> None:
        look_previews = look_previews or []
        item_previews = item_previews or []
        if not look_previews and not item_previews:
            return
        now = _now()
        with _LOCK, self._connection() as db:
            db.executemany(
                "UPDATE recipe_components SET preview_ref=?, preview_source=?, updated_at=? WHERE component_id=? AND preview_ref=''",
                [(str(row.get("filename") or ""), str(source or ""), now, str(row.get("component_id") or "")) for row in look_previews if str(row.get("filename") or "") and str(row.get("component_id") or "")],
            )
            db.executemany(
                "UPDATE wardrobe_items SET preview_ref=?, preview_source=?, updated_at=? WHERE wardrobe_id=? AND preview_ref=''",
                [(str(row.get("filename") or ""), str(source or ""), now, str(row.get("wardrobe_id") or "")) for row in item_previews if str(row.get("filename") or "") and str(row.get("wardrobe_id") or "")],
            )

    def creative_library_pack_snapshot(self, mode: str = "starter") -> dict[str, Any]:
        """Return portable Creative Library records without exposing the SQLite file itself.

        ``starter`` is intended for distribution. It excludes deleted/archived state,
        private import history, and personal Boards, while retaining Prompt source-log
        names and line positions because they are part of catalog navigation. ``backup``
        keeps the remaining provenance needed to reconstruct the user's library state.
        """
        clean_mode = str(mode or "starter").strip().lower()
        if clean_mode not in {"starter", "backup"}:
            clean_mode = "starter"
        backup = clean_mode == "backup"
        with _LOCK, self._connection() as db:
            recipe_collections = [dict(row) for row in db.execute(
                "SELECT collection_id, name, color, created_at, updated_at FROM recipe_collections ORDER BY name COLLATE NOCASE"
            ).fetchall()]
            recipe_memberships = [dict(row) for row in db.execute(
                "SELECT recipe_id, collection_id FROM recipe_collection_memberships ORDER BY recipe_id, collection_id"
            ).fetchall()]
            prompt_showcase_collections = [dict(row) for row in db.execute(
                """SELECT collection_id, kind, name, color, created_at, updated_at
                FROM prompt_showcase_collections ORDER BY kind, name COLLATE NOCASE"""
            ).fetchall()]
            prompt_memberships = [dict(row) for row in db.execute(
                "SELECT prompt_id, collection_id FROM prompt_showcase_memberships ORDER BY prompt_id, collection_id"
            ).fetchall()]
            prompt_query = """SELECT p.*, COALESCE(r.rating,0) AS rating, COALESCE(r.note,'') AS note,
                COALESCE(o.primary_parent,'') AS override_parent, COALESCE(o.primary_subcategory,'') AS override_subcategory,
                COALESCE(o.home_override,0) AS home_override,
                COALESCE(o.archived,0) AS archived
                FROM prompt_assets p
                LEFT JOIN prompt_reviews r ON r.prompt_id=p.prompt_id
                LEFT JOIN prompt_overrides o ON o.prompt_id=p.prompt_id"""
            if not backup:
                prompt_query += " WHERE COALESCE(o.archived,0)=0"
            prompt_query += " ORDER BY p.prompt_id"
            prompt_rows = [dict(row) for row in db.execute(prompt_query).fetchall()]
            prompt_sources: dict[str, list[dict[str, Any]]] = {}
            # Source-log identity and line position are catalog structure, not a
            # machine-local file dependency. Keep them in both shareable packs
            # and backups so Category → Subcategory → Log navigation survives.
            for row in db.execute(
                "SELECT prompt_id, source_path, line_number, source_label FROM prompt_sources ORDER BY prompt_id, source_path, line_number"
            ).fetchall():
                prompt_sources.setdefault(str(row["prompt_id"]), []).append(dict(row))

            recipes = [dict(row) for row in db.execute("SELECT * FROM recipes ORDER BY recipe_id").fetchall()]
            components = [dict(row) for row in db.execute("""SELECT c.*, COALESCE(r.rating,0) AS rating
                FROM recipe_components c LEFT JOIN component_reviews r ON r.component_id=c.component_id
                ORDER BY c.kind, c.component_id""").fetchall()]
            component_collections = [dict(row) for row in db.execute(
                "SELECT collection_id, kind, name, parent_id, color, created_at, updated_at FROM component_collections ORDER BY kind, parent_id, name COLLATE NOCASE"
            ).fetchall()]
            component_memberships = [dict(row) for row in db.execute(
                "SELECT component_id, collection_id FROM component_collection_memberships ORDER BY component_id, collection_id"
            ).fetchall()]
            library_collections = [dict(row) for row in db.execute(
                "SELECT collection_id, kind, name, color, created_at, updated_at FROM library_collections ORDER BY kind, created_at, name COLLATE NOCASE"
            ).fetchall()]
            library_collection_memberships = [dict(row) for row in db.execute(
                "SELECT collection_id, asset_id FROM library_collection_memberships ORDER BY collection_id, created_at, asset_id"
            ).fetchall()]
            wardrobe_items = [dict(row) for row in db.execute("""SELECT w.*, COALESCE(r.rating,0) AS rating
                FROM wardrobe_items w LEFT JOIN wardrobe_reviews r ON r.wardrobe_id=w.wardrobe_id
                ORDER BY w.item_type, w.wardrobe_id""").fetchall()]
            wardrobe_relations = [dict(row) for row in db.execute(
                "SELECT look_component_id, wardrobe_id, position, relation, source_text FROM wardrobe_look_parts ORDER BY look_component_id, position, wardrobe_id"
            ).fetchall()]
            wardrobe_sources: list[dict[str, Any]] = []
            wardrobe_item_sources: list[dict[str, Any]] = []
            if backup:
                wardrobe_sources = [dict(row) for row in db.execute("SELECT * FROM wardrobe_sources ORDER BY source_id").fetchall()]
                wardrobe_item_sources = [dict(row) for row in db.execute(
                    "SELECT wardrobe_id, source_id FROM wardrobe_item_sources ORDER BY wardrobe_id, source_id"
                ).fetchall()]

            fragment_where = "" if backup else "WHERE review_state IN ('approved','suggested')"
            fragments = [dict(row) for row in db.execute(
                f"SELECT * FROM fragment_assets {fragment_where} ORDER BY fragment_id"
            ).fetchall()]
            fragment_memberships: list[dict[str, Any]] = []
            fragment_sources: list[dict[str, Any]] = []
            if backup:
                fragment_memberships = [dict(row) for row in db.execute(
                    "SELECT fragment_id, prompt_id, occurrence_count FROM fragment_prompt_memberships ORDER BY fragment_id, prompt_id"
                ).fetchall()]
                fragment_sources = [dict(row) for row in db.execute(
                    "SELECT fragment_id, source_path, line_number, source_type FROM fragment_file_sources ORDER BY fragment_id, source_path, line_number"
                ).fetchall()]
            boards = [dict(row) for row in db.execute("SELECT * FROM creative_boards ORDER BY board_id").fetchall()] if backup else []
            tombstones = [dict(row) for row in db.execute("SELECT * FROM component_tombstones ORDER BY kind, value").fetchall()] if backup else []

        collection_by_id = {str(row["collection_id"]): row for row in recipe_collections}
        prompt_showcase_by_id = {str(row["collection_id"]): row for row in prompt_showcase_collections}
        component_collection_by_id = {str(row["collection_id"]): row for row in component_collections}

        # Structure order is exported in portable, name-based form. Prompt/Template
        # taxonomy already uses names and source paths; collection-backed libraries
        # use database IDs locally, so translate those IDs before they leave the machine.
        raw_structure_order = {scope: self.creative_structure_order(scope) for scope in ("prompt", "template", "recipe", "outfit", "scene")}
        recipe_order_ids = raw_structure_order.get("recipe", {}).get("collections", [])
        recipe_order_names = [str(collection_by_id[cid].get("name") or "") for cid in recipe_order_ids if cid in collection_by_id]
        recipe_order_names.extend(str(row.get("name") or "") for row in recipe_collections if str(row.get("name") or "") not in recipe_order_names)

        def portable_prompt_order(kind: str) -> dict[str, Any]:
            raw = dict(raw_structure_order.get(kind, {}))
            folder_ids = raw.get("showcase_collections", [])
            names = [
                str(prompt_showcase_by_id[str(cid)].get("name") or "")
                for cid in folder_ids if str(cid) in prompt_showcase_by_id
                and str(prompt_showcase_by_id[str(cid)].get("kind") or "") == kind
            ]
            names.extend(
                str(row.get("name") or "") for row in prompt_showcase_collections
                if str(row.get("kind") or "") == kind and str(row.get("name") or "") not in names
            )
            raw["showcase_collections"] = [name for name in names if name]
            return raw

        def ordered_component_rows(kind: str) -> list[dict[str, Any]]:
            rows = [row for row in component_collections if str(row.get("kind") or "") == kind]
            ids = raw_structure_order.get(kind, {}).get("collections", [])
            order_index = {str(value): index for index, value in enumerate(ids if isinstance(ids, list) else [])}
            rows.sort(key=lambda row: (order_index.get(str(row.get("collection_id") or ""), 10**9), 0 if not str(row.get("parent_id") or "") else 1, str(row.get("name") or "").casefold()))
            return rows

        outfit_rows_ordered = ordered_component_rows("outfit")
        outfit_parent_rows = [row for row in outfit_rows_ordered if not str(row.get("parent_id") or "")]
        scene_rows_ordered = ordered_component_rows("scene")
        scene_parent_rows = [row for row in scene_rows_ordered if not str(row.get("parent_id") or "")]
        scene_parent_name_by_id = {str(row.get("collection_id") or ""): str(row.get("name") or "") for row in scene_parent_rows}
        portable_structure_order = {
            "prompt": portable_prompt_order("prompt"),
            "template": portable_prompt_order("template"),
            "recipe": {"collections": [name for name in recipe_order_names if name]},
            "outfit": {
                "parents": [str(row.get("name") or "") for row in outfit_parent_rows if str(row.get("name") or "")],
                "subcategories": {
                    str(parent.get("name") or ""): [
                        str(row.get("name") or "") for row in outfit_rows_ordered
                        if str(row.get("parent_id") or "") == str(parent.get("collection_id") or "") and str(row.get("name") or "")
                    ]
                    for parent in outfit_parent_rows if str(parent.get("name") or "")
                },
                "collections": [str(row.get("name") or "") for row in outfit_rows_ordered if str(row.get("name") or "")],
            },
            "scene": {
                "parents": [str(row.get("name") or "") for row in scene_parent_rows if str(row.get("name") or "")],
                "subcategories": {
                    str(parent.get("name") or ""): [
                        str(row.get("name") or "") for row in scene_rows_ordered
                        if str(row.get("parent_id") or "") == str(parent.get("collection_id") or "") and str(row.get("name") or "")
                    ]
                    for parent in scene_parent_rows if str(parent.get("name") or "")
                },
            },
        }
        recipe_members_by_id: dict[str, list[str]] = {}
        for row in recipe_memberships:
            recipe_members_by_id.setdefault(str(row["recipe_id"]), []).append(str(row["collection_id"]))
        prompt_members_by_id: dict[str, list[str]] = {}
        for row in prompt_memberships:
            prompt_members_by_id.setdefault(str(row["prompt_id"]), []).append(str(row["collection_id"]))
        component_members_by_id: dict[str, list[str]] = {}
        for row in component_memberships:
            component_members_by_id.setdefault(str(row["component_id"]), []).append(str(row["collection_id"]))
        library_collection_by_id = {str(row["collection_id"]): row for row in library_collections}
        library_members_by_asset: dict[str, list[str]] = {}
        for row in library_collection_memberships:
            library_members_by_asset.setdefault(str(row["asset_id"]), []).append(str(row["collection_id"]))

        prompts_out: list[dict[str, Any]] = []
        for row in prompt_rows:
            try:
                facets = json.loads(str(row.get("facets_json") or "{}"))
            except Exception:
                facets = {}
            home_override = bool(row.get("home_override"))
            parent = str(row.get("override_parent") if home_override else row.get("primary_parent") or "Other")
            subcategory = str(row.get("override_subcategory") if home_override else row.get("primary_subcategory") or "")
            item = {
                "source_prompt_id": str(row.get("prompt_id") or ""),
                "kind": str(row.get("kind") or "prompt"),
                "value": str(row.get("value") or ""),
                "placeholder_signature": str(row.get("placeholder_signature") or ""),
                "primary_parent": parent,
                "primary_subcategory": subcategory,
                "facets": facets if isinstance(facets, dict) else {},
                "rating": int(row.get("rating") or 0),
                "note": str(row.get("note") or ""),
                "preview_ref": str(row.get("preview_ref") or ""),
                "preview_source": str(row.get("preview_source") or ""),
                "resolved_seed": int(row.get("resolved_seed")) if row.get("resolved_seed") is not None else -1,
                "resolved_seed_source": str(row.get("resolved_seed_source") or ""),
                "source_prompt_snapshot": str(row.get("source_prompt_snapshot") or ""),
                "resolved_prompt_snapshot": str(row.get("resolved_prompt_snapshot") or ""),
                "preview_metadata": json.loads(str(row.get("preview_metadata_json") or "{}")),
                "collections": [
                    {
                        "kind": str(prompt_showcase_by_id[cid]["kind"]),
                        "name": str(prompt_showcase_by_id[cid]["name"]),
                        "color": str(prompt_showcase_by_id[cid]["color"]),
                    }
                    for cid in prompt_members_by_id.get(str(row.get("prompt_id") or ""), [])
                    if cid in prompt_showcase_by_id
                    and str(prompt_showcase_by_id[cid].get("kind") or "") == str(row.get("kind") or "prompt")
                ],
                "sources": prompt_sources.get(str(row.get("prompt_id") or ""), []),
            }
            if backup:
                item.update({
                    "archived": bool(row.get("archived")),
                    "is_custom": bool(row.get("is_custom")),
                })
            prompts_out.append(item)

        recipes_out: list[dict[str, Any]] = []
        for row in recipes:
            try:
                payload = json.loads(str(row.get("payload_json") or "{}"))
            except Exception:
                payload = {}
            recipes_out.append({
                "source_recipe_id": str(row.get("recipe_id") or ""),
                "name": str(row.get("name") or "Recipe"),
                "payload": payload if isinstance(payload, dict) else {},
                "preview_ref": str(row.get("preview_ref") or ""),
                "collections": [
                    {"name": str(collection_by_id[cid]["name"]), "color": str(collection_by_id[cid]["color"])}
                    for cid in recipe_members_by_id.get(str(row.get("recipe_id") or ""), []) if cid in collection_by_id
                ],
            })

        component_collections_out = []
        for row in component_collections:
            parent = component_collection_by_id.get(str(row.get("parent_id") or ""))
            component_collections_out.append({
                "source_collection_id": str(row.get("collection_id") or ""),
                "kind": str(row.get("kind") or ""),
                "name": str(row.get("name") or ""),
                "parent_name": str(parent.get("name") or "") if parent else "",
                "color": str(row.get("color") or "#ff4ab8"),
            })
        components_out = []
        for row in components:
            components_out.append({
                "source_component_id": str(row.get("component_id") or ""),
                "kind": str(row.get("kind") or ""),
                "value": str(row.get("value") or ""),
                "manual": bool(row.get("manual")),
                "rating": int(row.get("rating") or 0),
                "preview_ref": str(row.get("preview_ref") or ""),
                "preview_source": str(row.get("preview_source") or ""),
                "resolved_seed": int(row.get("resolved_seed")) if row.get("resolved_seed") is not None else -1,
                "collections": [
                    {
                        "name": str(component_collection_by_id[cid]["name"]),
                        "parent_name": str(component_collection_by_id.get(str(component_collection_by_id[cid].get("parent_id") or ""), {}).get("name") or ""),
                        "color": str(component_collection_by_id[cid].get("color") or "#ff4ab8"),
                    }
                    for cid in component_members_by_id.get(str(row.get("component_id") or ""), []) if cid in component_collection_by_id
                ],
                "pack_collections": [
                    {"name": str(library_collection_by_id[cid].get("name") or ""), "color": str(library_collection_by_id[cid].get("color") or "")}
                    for cid in library_members_by_asset.get(str(row.get("component_id") or ""), [])
                    if cid in library_collection_by_id and str(library_collection_by_id[cid].get("kind") or "") == str(row.get("kind") or "")
                ],
            })

        wardrobe_out = [{
            "source_wardrobe_id": str(row.get("wardrobe_id") or ""),
            "item_type": str(row.get("item_type") or "piece"),
            "category": str(row.get("category") or "Uncategorized"),
            "subtype": str(row.get("subtype") or ""),
            "value": str(row.get("value") or ""),
            "manual": bool(row.get("manual")),
            "rating": int(row.get("rating") or 0),
            "preview_ref": str(row.get("preview_ref") or ""),
            "preview_source": str(row.get("preview_source") or ""),
            "pack_collections": [
                {"name": str(library_collection_by_id[cid].get("name") or ""), "color": str(library_collection_by_id[cid].get("color") or "")}
                for cid in library_members_by_asset.get(str(row.get("wardrobe_id") or ""), [])
                if cid in library_collection_by_id and str(library_collection_by_id[cid].get("kind") or "") == "wardrobe"
            ],
        } for row in wardrobe_items]
        component_by_id = {str(row["component_id"]): row for row in components}
        wardrobe_by_id = {str(row["wardrobe_id"]): row for row in wardrobe_items}
        relations_out = []
        for row in wardrobe_relations:
            look = component_by_id.get(str(row.get("look_component_id") or ""))
            item = wardrobe_by_id.get(str(row.get("wardrobe_id") or ""))
            if not look or not item:
                continue
            relations_out.append({
                "look_value": str(look.get("value") or ""),
                "item_type": str(item.get("item_type") or "piece"),
                "item_value": str(item.get("value") or ""),
                "position": int(row.get("position") or 0),
                "relation": str(row.get("relation") or ""),
                "source_text": str(row.get("source_text") or ""),
            })

        fragments_out = []
        for row in fragments:
            try:
                conflict_tags = json.loads(str(row.get("conflict_tags_json") or "[]"))
            except Exception:
                conflict_tags = []
            fragments_out.append({
                "source_fragment_id": str(row.get("fragment_id") or ""),
                "role": str(row.get("role") or ""), "mined_role": str(row.get("mined_role") or ""),
                "role_override": str(row.get("role_override") or ""), "value": str(row.get("value") or ""),
                "family_id": str(row.get("family_id") or ""), "join_mode": str(row.get("join_mode") or "sentence"),
                "preferred_position": int(row.get("preferred_position") or 50),
                "placeholder_signature": str(row.get("placeholder_signature") or ""),
                "confidence": float(row.get("confidence") or 0), "review_state": str(row.get("review_state") or "suggested"),
                "rating": int(row.get("rating") or 0), "source_kind": str(row.get("source_kind") or "mined"),
                "multiple_allowed": int(row.get("multiple_allowed") or 1),
                "conflict_tags": conflict_tags if isinstance(conflict_tags, list) else [],
                "manual": bool(row.get("manual")),
            })

        boards_out = []
        for row in boards:
            try:
                payload = json.loads(str(row.get("payload_json") or "{}"))
            except Exception:
                payload = {}
            boards_out.append({"board_id": str(row.get("board_id") or ""), "name": str(row.get("name") or "Board"), "payload": payload if isinstance(payload, dict) else {}})

        return {
            "mode": clean_mode,
            "structure_order": portable_structure_order,
            "recipe_collections": [{"name": str(row["name"]), "color": str(row["color"])} for row in recipe_collections],
            "prompt_showcase_collections": [
                {"kind": str(row["kind"]), "name": str(row["name"]), "color": str(row["color"])}
                for row in prompt_showcase_collections
            ],
            "prompts": prompts_out,
            "recipes": recipes_out,
            "component_collections": component_collections_out,
            "library_collections": [{"kind": str(row.get("kind") or ""), "name": str(row.get("name") or ""), "color": str(row.get("color") or "")} for row in library_collections],
            "components": components_out,
            "wardrobe_items": wardrobe_out,
            "wardrobe_relations": relations_out,
            "fragments": fragments_out,
            "boards": boards_out,
            "tombstones": tombstones,
            "backup_extras": {
                "wardrobe_sources": wardrobe_sources,
                "wardrobe_item_sources": wardrobe_item_sources,
                "fragment_memberships": fragment_memberships,
                "fragment_sources": fragment_sources,
            } if backup else {},
        }

    def merge_creative_library_pack_records(self, manifest: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        """Merge a portable Creative Library pack without replacing local user state."""
        mode = str(manifest.get("export_mode") or data.get("mode") or "starter").strip().lower()
        backup_mode = mode == "backup"
        pack_id = str(manifest.get("pack_id") or f"soslibrary:{uuid.uuid4().hex}")
        pack_name = " ".join(str(manifest.get("name") or "Sick Ollie Library").split()) or "Sick Ollie Library"
        now = _now()
        counts = {
            "created_prompts": 0, "matched_prompts": 0, "created_recipes": 0, "matched_recipes": 0,
            "created_components": 0, "matched_components": 0, "created_wardrobe": 0, "matched_wardrobe": 0,
            "created_fragments": 0, "matched_fragments": 0, "collections_added": 0, "memberships_added": 0,
            "memberships_removed": 0,
        }
        preview_queue = {"prompts": [], "recipes": [], "components": [], "wardrobe": []}

        self.repair_yearbook_prompt_sources()
        prompts = []
        for original in data.get("prompts") if isinstance(data.get("prompts"), list) else []:
            if not isinstance(original, dict):
                continue
            entry = dict(original)
            entry["source_prompt_snapshot"], entry["resolved_prompt_snapshot"] = repair_yearbook_prompt_snapshots(entry)
            prompts.append(entry)
        recipes = data.get("recipes") if isinstance(data.get("recipes"), list) else []
        components = data.get("components") if isinstance(data.get("components"), list) else []
        component_collections = data.get("component_collections") if isinstance(data.get("component_collections"), list) else []
        library_collections = data.get("library_collections") if isinstance(data.get("library_collections"), list) else []
        wardrobe_items = data.get("wardrobe_items") if isinstance(data.get("wardrobe_items"), list) else []
        wardrobe_relations = data.get("wardrobe_relations") if isinstance(data.get("wardrobe_relations"), list) else []
        fragments = data.get("fragments") if isinstance(data.get("fragments"), list) else []
        boards = data.get("boards") if isinstance(data.get("boards"), list) else []
        tombstones = data.get("tombstones") if isinstance(data.get("tombstones"), list) else []
        recipe_collections = data.get("recipe_collections") if isinstance(data.get("recipe_collections"), list) else []
        prompt_showcase_collections = data.get("prompt_showcase_collections") if isinstance(data.get("prompt_showcase_collections"), list) else []
        previous_component_memberships = data.get("previous_component_memberships") if isinstance(data.get("previous_component_memberships"), list) else []
        portable_structure_order = data.get("structure_order") if isinstance(data.get("structure_order"), dict) else {}

        with _LOCK, self._connection() as db:
            # Register the pack before provenance rows so foreign keys remain valid.
            # This is part of the same transaction, so a failed import rolls it back.
            db.execute("""INSERT INTO creative_library_packs(pack_id,name,creator,version,export_mode,description,manifest_json,installed_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(pack_id) DO UPDATE SET name=excluded.name,creator=excluded.creator,version=excluded.version,
                export_mode=excluded.export_mode,description=excluded.description,manifest_json=excluded.manifest_json,updated_at=excluded.updated_at""",(
                pack_id,pack_name,str(manifest.get("creator") or ""),str(manifest.get("version") or ""),mode,str(manifest.get("description") or ""),json.dumps(manifest,ensure_ascii=False,sort_keys=True),now,now))
            # Saved Recipe collections are separate from Prompt/Template collections.
            existing_recipe_collections = {str(row["name"]).casefold(): dict(row) for row in db.execute("SELECT * FROM recipe_collections").fetchall()}
            def ensure_recipe_collection(raw: dict[str, Any]) -> str:
                name = " ".join(str(raw.get("name") or "").split())
                if not name:
                    return ""
                key = name.casefold()
                row = existing_recipe_collections.get(key)
                if row:
                    return str(row["collection_id"])
                color = str(raw.get("color") or RECIPE_COLLECTION_COLORS[len(existing_recipe_collections) % len(RECIPE_COLLECTION_COLORS)])
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                    color = RECIPE_COLLECTION_COLORS[len(existing_recipe_collections) % len(RECIPE_COLLECTION_COLORS)]
                cid = f"recipe-collection:{uuid.uuid4().hex}"
                db.execute("INSERT INTO recipe_collections(collection_id,name,color,created_at,updated_at) VALUES(?,?,?,?,?)", (cid, name, color, now, now))
                row = {"collection_id": cid, "name": name, "color": color}
                existing_recipe_collections[key] = row
                counts["collections_added"] += 1
                return cid
            for raw in recipe_collections:
                if isinstance(raw, dict): ensure_recipe_collection(raw)

            existing_showcase_collections = {
                (str(row["kind"]), str(row["name"]).casefold()): dict(row)
                for row in db.execute("SELECT * FROM prompt_showcase_collections").fetchall()
            }
            def ensure_showcase_collection(raw: dict[str, Any], fallback_kind: str) -> str:
                kind = self._clean_prompt_showcase_kind(str(raw.get("kind") or fallback_kind))
                name = " ".join(str(raw.get("name") or "").split())
                if not name:
                    return ""
                key = (kind, name.casefold())
                row = existing_showcase_collections.get(key)
                if row:
                    return str(row["collection_id"])
                color = str(raw.get("color") or RECIPE_COLLECTION_COLORS[len(existing_showcase_collections) % len(RECIPE_COLLECTION_COLORS)])
                if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
                    color = RECIPE_COLLECTION_COLORS[len(existing_showcase_collections) % len(RECIPE_COLLECTION_COLORS)]
                cid = f"prompt-showcase:{kind}:{uuid.uuid4().hex}"
                db.execute(
                    """INSERT INTO prompt_showcase_collections(
                    collection_id,kind,name,color,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?)""",
                    (cid, kind, name, color, now, now),
                )
                row = {"collection_id": cid, "kind": kind, "name": name, "color": color}
                existing_showcase_collections[key] = row
                counts["collections_added"] += 1
                return cid
            for raw in prompt_showcase_collections:
                if isinstance(raw, dict):
                    ensure_showcase_collection(raw, str(raw.get("kind") or "prompt"))

            existing_prompt_by_value = {str(row["value"]).casefold(): dict(row) for row in db.execute("SELECT * FROM prompt_assets").fetchall()}
            prompt_id_map: dict[str, str] = {}
            for entry in prompts:
                if not isinstance(entry, dict): continue
                value = " ".join(str(entry.get("value") or "").split())
                if not value or len(value) > 32000: continue
                existing = existing_prompt_by_value.get(value.casefold())
                signature = _creative_prompt_signature(value)
                classified_kind = "template" if signature else "prompt"
                if existing:
                    prompt_id = str(existing["prompt_id"]); counts["matched_prompts"] += 1
                    db.execute(
                        "UPDATE prompt_assets SET kind=?, placeholder_signature=?, updated_at=? WHERE prompt_id=?",
                        (classified_kind, signature, now, prompt_id),
                    )
                else:
                    kind = classified_kind
                    prompt_id = str(entry.get("source_prompt_id") or "").strip()
                    if not prompt_id or db.execute("SELECT 1 FROM prompt_assets WHERE prompt_id=?", (prompt_id,)).fetchone():
                        prompt_id = f"imported:{uuid.uuid4().hex}"
                    parent = " ".join(str(entry.get("primary_parent") or "Imported").split()) or "Imported"
                    if "primary_subcategory" in entry:
                        sub = " ".join(str(entry.get("primary_subcategory") or "").split())
                    else:
                        sub = "Library Pack"
                    facets = entry.get("facets") if isinstance(entry.get("facets"), dict) else {}
                    try:
                        incoming_seed = int(entry.get("resolved_seed") if entry.get("resolved_seed") is not None else -1)
                    except (TypeError, ValueError):
                        incoming_seed = -1
                    if not 0 <= incoming_seed <= 1125899906842624:
                        incoming_seed = -1
                    incoming_preview_metadata = entry.get("preview_metadata") if isinstance(entry.get("preview_metadata"), dict) else {}
                    db.execute("""INSERT INTO prompt_assets(prompt_id,kind,value,placeholder_signature,primary_parent,primary_subcategory,facets_json,
                        quality_score,exact_source_occurrences,near_cluster_id,preview_ref,preview_source,preview_updated_at,resolved_seed,resolved_seed_source,
                        source_prompt_snapshot,resolved_prompt_snapshot,preview_metadata_json,is_custom,source_count,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,0,0,'','','','',?,?,?,?,?,1,0,?,?)""", (
                        prompt_id, kind, value, signature, parent, sub,
                        json.dumps(facets, ensure_ascii=False, sort_keys=True), incoming_seed, str(entry.get("resolved_seed_source") or ""),
                        str(entry.get("source_prompt_snapshot") or ""), str(entry.get("resolved_prompt_snapshot") or ""),
                        json.dumps(incoming_preview_metadata, ensure_ascii=False, sort_keys=True), now, now,
                    ))
                    existing = dict(db.execute("SELECT * FROM prompt_assets WHERE prompt_id=?", (prompt_id,)).fetchone())
                    existing_prompt_by_value[value.casefold()] = existing
                    counts["created_prompts"] += 1
                try:
                    incoming_seed = int(entry.get("resolved_seed") if entry.get("resolved_seed") is not None else -1)
                except (TypeError, ValueError):
                    incoming_seed = -1
                incoming_seed_source = str(entry.get("resolved_seed_source") or "")
                if 0 <= incoming_seed <= 1125899906842624 and incoming_seed_source:
                    db.execute("UPDATE prompt_assets SET resolved_seed=?, resolved_seed_source=? WHERE prompt_id=? AND (resolved_seed<0 OR resolved_seed_source='')", (incoming_seed, incoming_seed_source, prompt_id))
                incoming_source_snapshot = str(entry.get("source_prompt_snapshot") or "").strip()
                incoming_resolved_snapshot = str(entry.get("resolved_prompt_snapshot") or "").strip()
                incoming_preview_metadata = entry.get("preview_metadata") if isinstance(entry.get("preview_metadata"), dict) else {}
                if incoming_source_snapshot or incoming_resolved_snapshot:
                    db.execute(
                        """UPDATE prompt_assets SET
                        source_prompt_snapshot=CASE WHEN source_prompt_snapshot='' THEN ? ELSE source_prompt_snapshot END,
                        resolved_prompt_snapshot=CASE WHEN resolved_prompt_snapshot='' THEN ? ELSE resolved_prompt_snapshot END
                        WHERE prompt_id=?""",
                        (incoming_source_snapshot, incoming_resolved_snapshot, prompt_id),
                    )
                if incoming_preview_metadata:
                    db.execute(
                        """UPDATE prompt_assets SET preview_metadata_json=CASE WHEN preview_metadata_json='{}' THEN ? ELSE preview_metadata_json END
                        WHERE prompt_id=?""",
                        (json.dumps(incoming_preview_metadata, ensure_ascii=False, sort_keys=True), prompt_id),
                    )
                prompt_id_map[str(entry.get("source_prompt_id") or prompt_id)] = prompt_id
                rating = max(0, min(5, int(entry.get("rating") or 0)))
                review = db.execute("SELECT rating,note FROM prompt_reviews WHERE prompt_id=?", (prompt_id,)).fetchone()
                if rating and (review is None or int(review["rating"] or 0) == 0):
                    note = str(entry.get("note") or "") if review is None or not str(review["note"] or "") else str(review["note"] or "")
                    db.execute("""INSERT INTO prompt_reviews(prompt_id,rating,note,updated_at) VALUES(?,?,?,?)
                        ON CONFLICT(prompt_id) DO UPDATE SET rating=CASE WHEN prompt_reviews.rating=0 THEN excluded.rating ELSE prompt_reviews.rating END,
                        note=CASE WHEN prompt_reviews.note='' THEN excluded.note ELSE prompt_reviews.note END, updated_at=excluded.updated_at""", (prompt_id, rating, note, now))
                for group in entry.get("collections") or []:
                    if not isinstance(group, dict): continue
                    entry_kind = classified_kind
                    cid = ensure_showcase_collection(dict(group) | {"kind": entry_kind}, entry_kind)
                    if cid:
                        cur = db.execute("INSERT OR IGNORE INTO prompt_showcase_memberships(prompt_id,collection_id,created_at) VALUES(?,?,?)", (prompt_id, cid, now))
                        counts["memberships_added"] += max(0, int(cur.rowcount or 0))
                preview = Path(str(entry.get("preview_ref") or "")).name
                current = db.execute("SELECT preview_ref FROM prompt_assets WHERE prompt_id=?", (prompt_id,)).fetchone()
                if preview and current is not None:
                    preview_queue["prompts"].append({
                        "id": prompt_id,
                        "member": f"previews/prompts/{preview}",
                        "current_ref": str(current["preview_ref"] or ""),
                    })
                if backup_mode and bool(entry.get("archived")):
                    db.execute("""INSERT INTO prompt_overrides(prompt_id,primary_parent,primary_subcategory,home_override,archived,updated_at)
                        VALUES(?,?,?,?,?,?) ON CONFLICT(prompt_id) DO UPDATE SET archived=1,updated_at=excluded.updated_at""",
                        (prompt_id, "", "", 0, 1, now))
                for source_row in entry.get("sources") or []:
                    if not isinstance(source_row, dict):
                        continue
                    source_path = str(source_row.get("source_path") or "").replace("\\", "/").strip()
                    if not source_path:
                        continue
                    try:
                        line_number = max(0, int(source_row.get("line_number") or 0))
                    except (TypeError, ValueError):
                        line_number = 0
                    db.execute(
                        "INSERT OR IGNORE INTO prompt_sources(prompt_id,source_path,line_number,source_label,created_at) VALUES(?,?,?,?,?)",
                        (prompt_id, source_path, line_number, str(source_row.get("source_label") or ""), now),
                    )
                db.execute(
                    "UPDATE prompt_assets SET source_count=(SELECT COUNT(*) FROM prompt_sources WHERE prompt_id=?), exact_source_occurrences=(SELECT COUNT(*) FROM prompt_sources WHERE prompt_id=?), updated_at=? WHERE prompt_id=?",
                    (prompt_id, prompt_id, now, prompt_id),
                )

            # Recipes keep their stable source ID when possible so future pack updates match cleanly.
            for entry in recipes:
                if not isinstance(entry, dict): continue
                rid = str(entry.get("source_recipe_id") or "").strip() or f"recipe:{uuid.uuid4().hex}"
                exists = db.execute("SELECT recipe_id,preview_ref FROM recipes WHERE recipe_id=?", (rid,)).fetchone()
                if exists:
                    counts["matched_recipes"] += 1
                else:
                    payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else {}
                    db.execute("INSERT INTO recipes(recipe_id,name,payload_json,preview_ref,created_at,updated_at) VALUES(?,?,?,?,?,?)", (
                        rid, " ".join(str(entry.get("name") or "Imported Recipe").split()) or "Imported Recipe",
                        json.dumps(payload, ensure_ascii=False, sort_keys=True), "", now, now,
                    ))
                    counts["created_recipes"] += 1
                for group in entry.get("collections") or []:
                    if not isinstance(group, dict): continue
                    cid = ensure_recipe_collection(group)
                    if cid:
                        cur = db.execute("INSERT OR IGNORE INTO recipe_collection_memberships(recipe_id,collection_id,created_at) VALUES(?,?,?)", (rid, cid, now))
                        counts["memberships_added"] += max(0, int(cur.rowcount or 0))
                preview = Path(str(entry.get("preview_ref") or "")).name
                current = db.execute("SELECT preview_ref FROM recipes WHERE recipe_id=?", (rid,)).fetchone()
                if preview and current is not None:
                    preview_queue["recipes"].append({
                        "id": rid,
                        "member": f"previews/recipes/{preview}",
                        "current_ref": str(current["preview_ref"] or ""),
                    })

            # Shareable user collections merge independently from structural taxonomy.
            existing_library_collections = {(str(row["kind"]), str(row["name"]).casefold()): dict(row) for row in db.execute("SELECT * FROM library_collections").fetchall()}
            def ensure_library_collection(kind: str, name: str, color: str = "") -> str:
                clean_kind = str(kind or "").strip().lower(); clean_name = " ".join(str(name or "").split())
                if clean_kind not in {"outfit", "scene", "wardrobe"} or not clean_name: return ""
                key = (clean_kind, clean_name.casefold()); row = existing_library_collections.get(key)
                if row: return str(row["collection_id"])
                use_color = color if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(color or "")) else {"outfit":"#f6e65a","scene":"#63e6a4","wardrobe":"#ff9b5f"}[clean_kind]
                cid = f"library-collection:{clean_kind}:{uuid.uuid4().hex}"
                db.execute("INSERT INTO library_collections(collection_id,kind,name,color,created_at,updated_at) VALUES(?,?,?,?,?,?)", (cid, clean_kind, clean_name, use_color, now, now))
                existing_library_collections[key] = {"collection_id":cid,"kind":clean_kind,"name":clean_name,"color":use_color}; counts["collections_added"] += 1
                return cid
            for entry in library_collections:
                if isinstance(entry, dict): ensure_library_collection(str(entry.get("kind") or ""), str(entry.get("name") or ""), str(entry.get("color") or ""))

            # Component taxonomy merges by kind + name. Parents are created before children.
            existing_cc = {(str(row["kind"]), str(row["name"]).casefold()): dict(row) for row in db.execute("SELECT * FROM component_collections").fetchall()}
            def ensure_component_collection(kind: str, name: str, parent_name: str = "", color: str = "") -> str:
                clean_kind = str(kind or "").strip().lower()
                clean_name = " ".join(str(name or "").split())
                if clean_kind not in {"outfit", "scene"} or not clean_name: return ""
                key = (clean_kind, clean_name.casefold())
                row = existing_cc.get(key)
                if row: return str(row["collection_id"])
                parent_id = ""
                if parent_name:
                    parent_id = ensure_component_collection(clean_kind, parent_name, "", color)
                use_color = color if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(color or "")) else RECIPE_COLLECTION_COLORS[len(existing_cc) % len(RECIPE_COLLECTION_COLORS)]
                cid = f"component-collection:{clean_kind}:{uuid.uuid4().hex}"
                db.execute("INSERT INTO component_collections(collection_id,kind,name,parent_id,color,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (cid, clean_kind, clean_name, parent_id, use_color, now, now))
                existing_cc[key] = {"collection_id": cid, "kind": clean_kind, "name": clean_name, "parent_id": parent_id, "color": use_color}
                counts["collections_added"] += 1
                return cid
            for entry in component_collections:
                if isinstance(entry, dict) and not str(entry.get("parent_name") or ""):
                    ensure_component_collection(str(entry.get("kind") or ""), str(entry.get("name") or ""), "", str(entry.get("color") or ""))
            for entry in component_collections:
                if isinstance(entry, dict):
                    ensure_component_collection(str(entry.get("kind") or ""), str(entry.get("name") or ""), str(entry.get("parent_name") or ""), str(entry.get("color") or ""))

            component_map: dict[tuple[str, str], str] = {}
            desired_pack_component_memberships: set[tuple[str, str]] = set()
            for entry in components:
                if not isinstance(entry, dict): continue
                kind = str(entry.get("kind") or "").strip().lower(); value = " ".join(str(entry.get("value") or "").split())
                if kind not in {"outfit", "scene"} or not value or len(value)>8000: continue
                component_id = self.recipe_component_id(kind, value)
                existing = db.execute("SELECT * FROM recipe_components WHERE kind=? AND value=? COLLATE NOCASE", (kind, value)).fetchone()
                if existing:
                    component_id = str(existing["component_id"]); counts["matched_components"] += 1
                else:
                    # A deliberate pack import may resurrect an intentionally deleted starter asset.
                    db.execute("DELETE FROM component_tombstones WHERE component_id=? OR (kind=? AND value=? COLLATE NOCASE)", (component_id, kind, value))
                    db.execute("INSERT INTO recipe_components(component_id,kind,value,manual,preview_ref,preview_source,preview_updated_at,created_at,updated_at) VALUES(?,?,?,1,'','','',?,?)", (component_id, kind, value, now, now))
                    counts["created_components"] += 1
                component_map[(kind, value.casefold())] = component_id
                rating = max(0,min(5,int(entry.get("rating") or 0)))
                current_rating = db.execute("SELECT rating FROM component_reviews WHERE component_id=?", (component_id,)).fetchone()
                if rating and (current_rating is None or int(current_rating["rating"] or 0)==0):
                    db.execute("""INSERT INTO component_reviews(component_id,rating,updated_at) VALUES(?,?,?)
                        ON CONFLICT(component_id) DO UPDATE SET rating=CASE WHEN component_reviews.rating=0 THEN excluded.rating ELSE component_reviews.rating END,updated_at=excluded.updated_at""", (component_id,rating,now))
                for group in entry.get("collections") or []:
                    if not isinstance(group, dict): continue
                    cid = ensure_component_collection(kind, str(group.get("name") or ""), str(group.get("parent_name") or ""), str(group.get("color") or ""))
                    if cid:
                        cur=db.execute("INSERT OR IGNORE INTO component_collection_memberships(component_id,collection_id,created_at) VALUES(?,?,?)", (component_id,cid,now)); counts["memberships_added"]+=max(0,int(cur.rowcount or 0))
                        desired_pack_component_memberships.add((component_id, cid))
                for group in entry.get("pack_collections") or []:
                    if not isinstance(group, dict): continue
                    cid = ensure_library_collection(kind, str(group.get("name") or ""), str(group.get("color") or ""))
                    if cid:
                        cur=db.execute("INSERT OR IGNORE INTO library_collection_memberships(collection_id,asset_id,created_at) VALUES(?,?,?)", (cid,component_id,now)); counts["memberships_added"]+=max(0,int(cur.rowcount or 0))
                preview=Path(str(entry.get("preview_ref") or "")).name
                current=db.execute("SELECT preview_ref FROM recipe_components WHERE component_id=?", (component_id,)).fetchone()
                if preview and current is not None:
                    preview_queue["components"].append({
                        "id":component_id,
                        "member":f"previews/components/{preview}",
                        "current_ref":str(current["preview_ref"] or ""),
                    })

            # Reconcile taxonomy memberships owned by earlier revisions of this same pack.
            # Ordinary local memberships are never part of the removal basis, so they survive.
            selective_import = bool(manifest.get("selective_import"))
            import_taxonomy = bool(manifest.get("import_taxonomy", True))
            touched_component_ids = set(component_map.values())
            prior_owned = {
                (str(row["component_id"]), str(row["collection_id"]))
                for row in db.execute(
                    "SELECT component_id,collection_id FROM creative_library_pack_component_memberships WHERE pack_id=?",
                    (pack_id,),
                ).fetchall()
                if not selective_import or str(row["component_id"]) in touched_component_ids
            }
            reconcile_basis = set(prior_owned)
            # Bootstrap the first reconciled update for a library that originally *created*
            # the starter pack rather than imported it. A pack may include a previous-version
            # membership snapshot; only those known previous memberships are eligible to move.
            if not reconcile_basis and previous_component_memberships:
                for previous in previous_component_memberships:
                    if not isinstance(previous, dict):
                        continue
                    prev_kind = str(previous.get("kind") or "").strip().lower()
                    prev_value = " ".join(str(previous.get("value") or "").split())
                    if prev_kind not in {"outfit", "scene"} or not prev_value:
                        continue
                    component_row = db.execute(
                        "SELECT component_id FROM recipe_components WHERE kind=? AND value=? COLLATE NOCASE",
                        (prev_kind, prev_value),
                    ).fetchone()
                    if component_row is None:
                        continue
                    previous_component_id = str(component_row["component_id"])
                    for group in previous.get("collections") or []:
                        if not isinstance(group, dict):
                            continue
                        group_name = " ".join(str(group.get("name") or "").split())
                        if not group_name:
                            continue
                        collection_row = db.execute(
                            "SELECT collection_id FROM component_collections WHERE kind=? AND name=? COLLATE NOCASE",
                            (prev_kind, group_name),
                        ).fetchone()
                        if collection_row is not None:
                            reconcile_basis.add((previous_component_id, str(collection_row["collection_id"])))

            for old_component_id, old_collection_id in sorted((reconcile_basis - desired_pack_component_memberships) if import_taxonomy else set()):
                # Another installed pack may legitimately share the same membership.
                other_owner = db.execute(
                    """SELECT 1 FROM creative_library_pack_component_memberships
                    WHERE component_id=? AND collection_id=? AND pack_id<>? LIMIT 1""",
                    (old_component_id, old_collection_id, pack_id),
                ).fetchone()
                if other_owner is not None:
                    continue
                result = db.execute(
                    "DELETE FROM component_collection_memberships WHERE component_id=? AND collection_id=?",
                    (old_component_id, old_collection_id),
                )
                counts["memberships_removed"] += max(0, int(result.rowcount or 0))

            if import_taxonomy:
                if selective_import:
                    if touched_component_ids:
                        db.executemany(
                            "DELETE FROM creative_library_pack_component_memberships WHERE pack_id=? AND component_id=?",
                            [(pack_id, component_id) for component_id in sorted(touched_component_ids)],
                        )
                else:
                    db.execute("DELETE FROM creative_library_pack_component_memberships WHERE pack_id=?", (pack_id,))
                if desired_pack_component_memberships:
                    db.executemany(
                        "INSERT OR IGNORE INTO creative_library_pack_component_memberships(pack_id,component_id,collection_id) VALUES(?,?,?)",
                        [(pack_id, component_id, collection_id) for component_id, collection_id in sorted(desired_pack_component_memberships)],
                    )

            wardrobe_map: dict[tuple[str,str],str] = {}
            wardrobe_source_id_map: dict[str, str] = {}
            for entry in wardrobe_items:
                if not isinstance(entry,dict): continue
                item_type=str(entry.get("item_type") or "piece").strip().lower(); value=" ".join(str(entry.get("value") or "").split())
                if item_type not in {"piece","set","finisher","styling"} or not value or len(value)>8000: continue
                existing=db.execute("SELECT * FROM wardrobe_items WHERE item_type=? AND value=? COLLATE NOCASE", (item_type,value)).fetchone()
                if existing:
                    wid=str(existing["wardrobe_id"]); counts["matched_wardrobe"]+=1
                else:
                    wid=self.wardrobe_item_id(item_type,value)
                    db.execute("INSERT INTO wardrobe_items(wardrobe_id,item_type,category,subtype,value,manual,preview_ref,preview_source,preview_updated_at,created_at,updated_at) VALUES(?,?,?,?,?,1,'','','',?,?)", (
                        wid,item_type," ".join(str(entry.get("category") or "Uncategorized").split()) or "Uncategorized"," ".join(str(entry.get("subtype") or "").split()),value,now,now))
                    counts["created_wardrobe"]+=1
                wardrobe_map[(item_type,value.casefold())]=wid
                source_wardrobe_id = str(entry.get("source_wardrobe_id") or "").strip()
                if source_wardrobe_id:
                    wardrobe_source_id_map[source_wardrobe_id] = wid
                rating=max(0,min(5,int(entry.get("rating") or 0))); current_rating=db.execute("SELECT rating FROM wardrobe_reviews WHERE wardrobe_id=?",(wid,)).fetchone()
                if rating and (current_rating is None or int(current_rating["rating"] or 0)==0):
                    db.execute("""INSERT INTO wardrobe_reviews(wardrobe_id,rating,updated_at) VALUES(?,?,?)
                        ON CONFLICT(wardrobe_id) DO UPDATE SET rating=CASE WHEN wardrobe_reviews.rating=0 THEN excluded.rating ELSE wardrobe_reviews.rating END,updated_at=excluded.updated_at""",(wid,rating,now))
                for group in entry.get("pack_collections") or []:
                    if not isinstance(group, dict): continue
                    cid = ensure_library_collection("wardrobe", str(group.get("name") or ""), str(group.get("color") or ""))
                    if cid:
                        cur=db.execute("INSERT OR IGNORE INTO library_collection_memberships(collection_id,asset_id,created_at) VALUES(?,?,?)", (cid,wid,now)); counts["memberships_added"]+=max(0,int(cur.rowcount or 0))
                preview=Path(str(entry.get("preview_ref") or "")).name; current=db.execute("SELECT preview_ref FROM wardrobe_items WHERE wardrobe_id=?",(wid,)).fetchone()
                if preview and item_type != "finisher" and current is not None:
                    preview_queue["wardrobe"].append({
                        "id":wid,
                        "member":f"previews/wardrobe/{preview}",
                        "current_ref":str(current["preview_ref"] or ""),
                    })

            for relation in wardrobe_relations:
                if not isinstance(relation,dict): continue
                look_value=" ".join(str(relation.get("look_value") or "").split()); item_type=str(relation.get("item_type") or "piece").strip().lower(); item_value=" ".join(str(relation.get("item_value") or "").split())
                look_id=component_map.get(("outfit",look_value.casefold()))
                if not look_id:
                    row=db.execute("SELECT component_id FROM recipe_components WHERE kind='outfit' AND value=? COLLATE NOCASE",(look_value,)).fetchone(); look_id=str(row["component_id"]) if row else ""
                wid=wardrobe_map.get((item_type,item_value.casefold()))
                if not wid:
                    row=db.execute("SELECT wardrobe_id FROM wardrobe_items WHERE item_type=? AND value=? COLLATE NOCASE",(item_type,item_value)).fetchone(); wid=str(row["wardrobe_id"]) if row else ""
                if look_id and wid:
                    cur=db.execute("INSERT OR IGNORE INTO wardrobe_look_parts(look_component_id,wardrobe_id,position,relation,source_text,created_at) VALUES(?,?,?,?,?,?)",(
                        look_id,wid,int(relation.get("position") or 0),str(relation.get("relation") or ""),str(relation.get("source_text") or item_value),now))
                    counts["memberships_added"]+=max(0,int(cur.rowcount or 0))

            fragment_id_map: dict[str, str] = {}
            for entry in fragments:
                if not isinstance(entry,dict): continue
                role=str(entry.get("role") or "").strip().lower(); value=" ".join(str(entry.get("value") or "").split())
                if not role or not value or len(value)>8000: continue
                existing=db.execute("SELECT fragment_id,rating,review_state FROM fragment_assets WHERE role=? AND value=? COLLATE NOCASE",(role,value)).fetchone()
                if existing:
                    fid=str(existing["fragment_id"]); counts["matched_fragments"]+=1
                else:
                    fid=self.fragment_id(role,value)
                    review_state=str(entry.get("review_state") or "suggested").strip().lower()
                    if review_state not in {"suggested","approved","review","rejected"}: review_state="suggested"
                    db.execute("""INSERT INTO fragment_assets(fragment_id,role,mined_role,role_override,value,family_id,join_mode,preferred_position,placeholder_signature,confidence,review_state,rating,source_kind,prompt_count,source_count,multiple_allowed,conflict_tags_json,manual,created_at,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?,?,1,?,?)""",(
                        fid,role,str(entry.get("mined_role") or role),str(entry.get("role_override") or ""),value,str(entry.get("family_id") or ""),str(entry.get("join_mode") or "sentence"),int(entry.get("preferred_position") or 50),str(entry.get("placeholder_signature") or ""),float(entry.get("confidence") or 0),review_state,max(0,min(5,int(entry.get("rating") or 0))),"pack",int(entry.get("multiple_allowed") if entry.get("multiple_allowed") is not None else 1),json.dumps(entry.get("conflict_tags") if isinstance(entry.get("conflict_tags"),list) else [],ensure_ascii=False,sort_keys=True),now,now))
                    counts["created_fragments"]+=1
                source_fragment_id = str(entry.get("source_fragment_id") or "").strip()
                if source_fragment_id:
                    fragment_id_map[source_fragment_id] = fid
                if existing and int(existing["rating"] or 0)==0 and int(entry.get("rating") or 0)>0:
                    db.execute("UPDATE fragment_assets SET rating=?,updated_at=? WHERE fragment_id=?",(max(0,min(5,int(entry.get("rating") or 0))),now,fid))

            if backup_mode:
                extras = data.get("backup_extras") if isinstance(data.get("backup_extras"), dict) else {}
                source_id_map: dict[str, str] = {}
                for source_row in extras.get("wardrobe_sources") or []:
                    if not isinstance(source_row, dict):
                        continue
                    source_type = str(source_row.get("source_type") or "").strip().lower()
                    source_key = str(source_row.get("source_key") or "").strip()
                    if not source_type or not source_key:
                        continue
                    existing_source = db.execute(
                        "SELECT source_id FROM wardrobe_sources WHERE source_type=? AND source_key=?",
                        (source_type, source_key),
                    ).fetchone()
                    if existing_source:
                        target_source_id = str(existing_source["source_id"])
                    else:
                        target_source_id = str(source_row.get("source_id") or "").strip() or f"wardrobe-source:{uuid.uuid4().hex}"
                        if db.execute("SELECT 1 FROM wardrobe_sources WHERE source_id=?", (target_source_id,)).fetchone():
                            target_source_id = f"wardrobe-source:{uuid.uuid4().hex}"
                        metadata_json = str(source_row.get("metadata_json") or "{}")
                        try:
                            json.loads(metadata_json)
                        except Exception:
                            metadata_json = "{}"
                        db.execute(
                            "INSERT INTO wardrobe_sources(source_id,source_type,source_key,label,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                            (target_source_id, source_type, source_key, str(source_row.get("label") or ""), metadata_json, now, now),
                        )
                    old_source_id = str(source_row.get("source_id") or "").strip()
                    if old_source_id:
                        source_id_map[old_source_id] = target_source_id
                for link in extras.get("wardrobe_item_sources") or []:
                    if not isinstance(link, dict):
                        continue
                    wid = wardrobe_source_id_map.get(str(link.get("wardrobe_id") or "").strip(), "")
                    sid = source_id_map.get(str(link.get("source_id") or "").strip(), "")
                    if wid and sid:
                        db.execute(
                            "INSERT OR IGNORE INTO wardrobe_item_sources(wardrobe_id,source_id,created_at) VALUES(?,?,?)",
                            (wid, sid, now),
                        )
                for link in extras.get("fragment_memberships") or []:
                    if not isinstance(link, dict):
                        continue
                    fid = fragment_id_map.get(str(link.get("fragment_id") or "").strip(), "")
                    prompt_id = prompt_id_map.get(str(link.get("prompt_id") or "").strip(), "")
                    if not fid or not prompt_id:
                        continue
                    try:
                        occurrence_count = max(1, int(link.get("occurrence_count") or 1))
                    except (TypeError, ValueError):
                        occurrence_count = 1
                    db.execute(
                        "INSERT OR IGNORE INTO fragment_prompt_memberships(fragment_id,prompt_id,occurrence_count,created_at) VALUES(?,?,?,?)",
                        (fid, prompt_id, occurrence_count, now),
                    )
                for source_row in extras.get("fragment_sources") or []:
                    if not isinstance(source_row, dict):
                        continue
                    fid = fragment_id_map.get(str(source_row.get("fragment_id") or "").strip(), "")
                    source_path = str(source_row.get("source_path") or "").replace("\\", "/").strip()
                    if not fid or not source_path:
                        continue
                    try:
                        line_number = max(0, int(source_row.get("line_number") or 0))
                    except (TypeError, ValueError):
                        line_number = 0
                    db.execute(
                        "INSERT OR IGNORE INTO fragment_file_sources(fragment_id,source_path,line_number,source_type,created_at) VALUES(?,?,?,?,?)",
                        (fid, source_path, line_number, str(source_row.get("source_type") or "prompt-log"), now),
                    )
                for fid in set(fragment_id_map.values()):
                    db.execute(
                        """UPDATE fragment_assets SET
                            prompt_count=(SELECT COUNT(*) FROM fragment_prompt_memberships WHERE fragment_id=?),
                            source_count=(SELECT COUNT(*) FROM fragment_file_sources WHERE fragment_id=?),updated_at=?
                            WHERE fragment_id=?""",
                        (fid, fid, now, fid),
                    )
                for entry in boards:
                    if not isinstance(entry,dict): continue
                    bid=str(entry.get("board_id") or "").strip() or f"creative-board:{uuid.uuid4().hex}"
                    if db.execute("SELECT 1 FROM creative_boards WHERE board_id=?",(bid,)).fetchone(): continue
                    payload=entry.get("payload") if isinstance(entry.get("payload"),dict) else {}
                    db.execute("INSERT INTO creative_boards(board_id,name,payload_json,created_at,updated_at) VALUES(?,?,?,?,?)",(bid," ".join(str(entry.get("name") or "Imported Board").split()) or "Imported Board",json.dumps(payload,ensure_ascii=False,sort_keys=True),now,now))
                for entry in tombstones:
                    if not isinstance(entry,dict): continue
                    kind=str(entry.get("kind") or "").strip().lower(); value=" ".join(str(entry.get("value") or "").split())
                    if kind not in {"outfit","scene"} or not value: continue
                    cid=self.recipe_component_id(kind,value)
                    if db.execute("SELECT 1 FROM recipe_components WHERE component_id=?",(cid,)).fetchone(): continue
                    db.execute("INSERT OR IGNORE INTO component_tombstones(component_id,kind,value,deleted_at) VALUES(?,?,?,?)",(cid,kind,value,str(entry.get("deleted_at") or now)))

            # Merge portable manual structure order after taxonomy IDs have been resolved.
            # Existing local order always wins for folders the user already has; new pack
            # folders are appended in the pack's order. On a fresh library this restores
            # the exported order exactly.
            def read_local_structure(scope: str) -> dict[str, Any]:
                key = self._structure_order_key(scope)
                row = db.execute("SELECT value FROM schema_meta WHERE key=?", (key,)).fetchone()
                if row is None:
                    return {}
                try:
                    value = json.loads(str(row["value"] or "{}"))
                except Exception:
                    return {}
                cleaned = self._clean_structure_order_value(value)
                return cleaned if isinstance(cleaned, dict) else {}

            def merge_order_list(local: Any, incoming: Any) -> list[str]:
                output = [str(value) for value in local] if isinstance(local, list) else []
                seen = set(output)
                for value in incoming if isinstance(incoming, list) else []:
                    clean = str(value or "").strip()
                    if clean and clean not in seen:
                        seen.add(clean); output.append(clean)
                return output

            def merge_prompt_structure(local: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
                output = {
                    "parents": merge_order_list(local.get("parents"), incoming.get("parents")),
                    "subcategories": {},
                    "logs": {},
                    "showcase_collections": merge_order_list(
                        local.get("showcase_collections"), incoming.get("showcase_collections")
                    ),
                }
                local_subs = local.get("subcategories") if isinstance(local.get("subcategories"), dict) else {}
                incoming_subs = incoming.get("subcategories") if isinstance(incoming.get("subcategories"), dict) else {}
                local_logs = local.get("logs") if isinstance(local.get("logs"), dict) else {}
                incoming_logs = incoming.get("logs") if isinstance(incoming.get("logs"), dict) else {}
                for parent in output["parents"]:
                    output["subcategories"][parent] = merge_order_list(local_subs.get(parent), incoming_subs.get(parent))
                    parent_logs: dict[str, list[str]] = {}
                    for subcategory in output["subcategories"][parent]:
                        left = local_logs.get(parent, {}).get(subcategory, []) if isinstance(local_logs.get(parent), dict) else []
                        right = incoming_logs.get(parent, {}).get(subcategory, []) if isinstance(incoming_logs.get(parent), dict) else []
                        merged = merge_order_list(left, right)
                        if merged:
                            parent_logs[subcategory] = merged
                    if parent_logs:
                        output["logs"][parent] = parent_logs
                return output

            def write_merged_structure(scope: str, incoming: dict[str, Any]) -> None:
                if not isinstance(incoming, dict) or not incoming:
                    return
                local = read_local_structure(scope)
                merged = merge_prompt_structure(local, incoming) if scope in {"prompt", "template"} else {"collections": merge_order_list(local.get("collections"), incoming.get("collections"))}
                cleaned = self._clean_structure_order_value(merged)
                db.execute(
                    "INSERT INTO schema_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (self._structure_order_key(scope), json.dumps(cleaned, ensure_ascii=False, sort_keys=True)),
                )

            for scope in ("prompt", "template"):
                raw_incoming = portable_structure_order.get(scope) if isinstance(portable_structure_order.get(scope), dict) else {}
                incoming = dict(raw_incoming)
                showcase_ids = []
                for name in raw_incoming.get("showcase_collections", []) if isinstance(raw_incoming.get("showcase_collections"), list) else []:
                    row = existing_showcase_collections.get((scope, str(name or "").strip().casefold()))
                    if row:
                        showcase_ids.append(str(row["collection_id"]))
                incoming["showcase_collections"] = showcase_ids
                write_merged_structure(scope, incoming)

            recipe_names = (portable_structure_order.get("recipe") or {}).get("collections", []) if isinstance(portable_structure_order.get("recipe"), dict) else []
            recipe_ids = []
            for name in recipe_names if isinstance(recipe_names, list) else []:
                row = existing_recipe_collections.get(str(name or "").strip().casefold())
                if row:
                    recipe_ids.append(str(row["collection_id"]))
            write_merged_structure("recipe", {"collections": recipe_ids} if recipe_ids else {})

            outfit_order = portable_structure_order.get("outfit") if isinstance(portable_structure_order.get("outfit"), dict) else {}
            outfit_names = outfit_order.get("collections", [])
            outfit_ids = []
            outfit_subs = outfit_order.get("subcategories") if isinstance(outfit_order.get("subcategories"), dict) else {}
            parent_names = outfit_order.get("parents", []) if isinstance(outfit_order.get("parents"), list) else []
            if parent_names:
                for parent_name in parent_names:
                    parent = existing_cc.get(("outfit", str(parent_name or "").strip().casefold()))
                    if not parent:
                        continue
                    parent_id = str(parent["collection_id"]); outfit_ids.append(parent_id)
                    for child_name in outfit_subs.get(str(parent_name), []) if isinstance(outfit_subs.get(str(parent_name)), list) else []:
                        child = existing_cc.get(("outfit", str(child_name or "").strip().casefold()))
                        if child and str(child.get("parent_id") or "") == parent_id:
                            outfit_ids.append(str(child["collection_id"]))
            else:
                for name in outfit_names if isinstance(outfit_names, list) else []:
                    row = existing_cc.get(("outfit", str(name or "").strip().casefold()))
                    if row:
                        outfit_ids.append(str(row["collection_id"]))
            write_merged_structure("outfit", {"collections": outfit_ids} if outfit_ids else {})

            scene_order = portable_structure_order.get("scene") if isinstance(portable_structure_order.get("scene"), dict) else {}
            scene_ids = []
            scene_subs = scene_order.get("subcategories") if isinstance(scene_order.get("subcategories"), dict) else {}
            for parent_name in scene_order.get("parents", []) if isinstance(scene_order.get("parents"), list) else []:
                parent = existing_cc.get(("scene", str(parent_name or "").strip().casefold()))
                if not parent:
                    continue
                parent_id = str(parent["collection_id"]); scene_ids.append(parent_id)
                for child_name in scene_subs.get(str(parent_name), []) if isinstance(scene_subs.get(str(parent_name)), list) else []:
                    child = existing_cc.get(("scene", str(child_name or "").strip().casefold()))
                    if child and str(child.get("parent_id") or "") == parent_id:
                        scene_ids.append(str(child["collection_id"]))
            write_merged_structure("scene", {"collections": scene_ids} if scene_ids else {})

            db.execute("""INSERT INTO creative_library_packs(pack_id,name,creator,version,export_mode,description,manifest_json,installed_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(pack_id) DO UPDATE SET name=excluded.name,creator=excluded.creator,version=excluded.version,
                export_mode=excluded.export_mode,description=excluded.description,manifest_json=excluded.manifest_json,updated_at=excluded.updated_at""",(
                pack_id,pack_name,str(manifest.get("creator") or ""),str(manifest.get("version") or ""),mode,str(manifest.get("description") or ""),json.dumps(manifest,ensure_ascii=False,sort_keys=True),now,now))
            for key in ("recipe_revision","prompt_revision","fragment_revision","component_revision"):
                db.execute("""INSERT INTO schema_meta(key,value) VALUES(?, '1') ON CONFLICT(key) DO UPDATE SET value=CAST(value AS INTEGER)+1""",(key,))
        return {"pack_id":pack_id,"name":pack_name,"export_mode":mode,**counts,"preview_queue":preview_queue}

    def set_creative_library_pack_previews_bulk(self, *, prompts: list[dict[str,str]] | None=None, recipes: list[dict[str,str]] | None=None, components: list[dict[str,str]] | None=None, wardrobe: list[dict[str,str]] | None=None, source: str="") -> None:
        prompts=prompts or []; recipes=recipes or []; components=components or []; wardrobe=wardrobe or []
        if not any((prompts,recipes,components,wardrobe)): return
        now=_now()
        with _LOCK, self._connection() as db:
            db.executemany("UPDATE prompt_assets SET preview_ref=?,preview_source=?,preview_updated_at=?,updated_at=? WHERE prompt_id=? AND preview_ref=?",[(str(x.get("filename") or ""),source,now,now,str(x.get("id") or ""),str(x.get("replace_ref") or "")) for x in prompts if x.get("filename") and x.get("id")])
            db.executemany("UPDATE recipes SET preview_ref=?,updated_at=? WHERE recipe_id=? AND preview_ref=?",[(str(x.get("filename") or ""),now,str(x.get("id") or ""),str(x.get("replace_ref") or "")) for x in recipes if x.get("filename") and x.get("id")])
            db.executemany("UPDATE recipe_components SET preview_ref=?,preview_source=?,preview_updated_at=?,updated_at=? WHERE component_id=? AND preview_ref=?",[(str(x.get("filename") or ""),source,now,now,str(x.get("id") or ""),str(x.get("replace_ref") or "")) for x in components if x.get("filename") and x.get("id")])
            db.executemany("UPDATE wardrobe_items SET preview_ref=?,preview_source=?,preview_updated_at=?,updated_at=? WHERE wardrobe_id=? AND preview_ref=?",[(str(x.get("filename") or ""),source,now,now,str(x.get("id") or ""),str(x.get("replace_ref") or "")) for x in wardrobe if x.get("filename") and x.get("id")])

    def creative_library_pack_component_membership_snapshot(self, pack_id: str) -> list[dict[str, Any]]:
        """Return the last installed taxonomy state owned by a pack, grouped by component identity."""
        clean_pack_id = str(pack_id or "").strip()
        if not clean_pack_id:
            return []
        with _LOCK, self._connection() as db:
            rows = db.execute(
                """SELECT rc.kind,rc.value,cc.name,COALESCE(parent.name,'') AS parent_name,cc.color
                FROM creative_library_pack_component_memberships pm
                JOIN recipe_components rc ON rc.component_id=pm.component_id
                JOIN component_collections cc ON cc.collection_id=pm.collection_id
                LEFT JOIN component_collections parent ON parent.collection_id=cc.parent_id
                WHERE pm.pack_id=?
                ORDER BY rc.kind,rc.value COLLATE NOCASE,COALESCE(parent.name,''),cc.name COLLATE NOCASE""",
                (clean_pack_id,),
            ).fetchall()
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (str(row["kind"] or ""), str(row["value"] or ""))
            entry = grouped.setdefault(key, {"kind": key[0], "value": key[1], "collections": []})
            entry["collections"].append({
                "name": str(row["name"] or ""),
                "parent_name": str(row["parent_name"] or ""),
                "color": str(row["color"] or ""),
            })
        return list(grouped.values())

    def creative_library_packs(self) -> list[dict[str, Any]]:
        with _LOCK, self._connection() as db:
            rows=db.execute("SELECT pack_id,name,creator,version,export_mode,description,installed_at,updated_at FROM creative_library_packs ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def delete_recipe(self, recipe_id: str) -> None:
        self.delete_recipes([recipe_id])


_CATALOG: SoloCatalog | None = None


def get_catalog() -> SoloCatalog:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = SoloCatalog()
    return _CATALOG
