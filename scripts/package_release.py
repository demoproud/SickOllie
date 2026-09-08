"""Create a clean distributable without local caches or private work files.

Run from the extension root:
    python scripts/package_release.py ../ComfyUI-SickOllie-release.zip
"""
from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".cache", "__pycache__", ".git", ".pytest_cache", "yearbook_repairs", "release-audit", "internal", "node_modules", "Starter Content", "starter_content"}
EXCLUDED_NAMES = {
    "--help",
    "IMPLEMENTATION_LEDGER.md",
    "PRIVATE",
    "PRIVATE DEV NOTES.md",
    "PRIVATE_DEV10_NOTES.md",
    "CLASSIC_STUDIO_DEV48.md",
    "RELEASE_READINESS_AUDIT.md",
    "RELEASE_ANNOUNCEMENT.md",
    "RECOVER_YEARBOOK_20260903.bat",
    "YEARBOOK_RECOVERY_README.txt",
    "recover_mixed_yearbook_20260903.py",
    "repair_mixed_yearbook.py",
    "TUTORIAL_VIDEO_OUTLINE.md",
    "prompt_core.js.bak",
}
ALLOWED_HIDDEN_FILES = {".comfyignore", ".gitignore"}
EXCLUDED_RELATIVE = {
    # The maintained copy lives under docs/. Avoid shipping the same 10 MB PDF twice.
    Path("Sick_Ollie_Classic_Studio_v2_Reference_Guide.pdf"),
}


def include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    # Runtime catalog/settings caches live only at the extension root. Nested
    # engine resources such as solo_log_organizer/data/theme_rules.json ship.
    if relative.parts and relative.parts[0] == "data":
        return False
    if relative in EXCLUDED_RELATIVE:
        return False
    # Atomic catalog rebuilds can leave dot-prefixed sibling files behind if a
    # process is interrupted. They are recovery debris, not canonical release
    # data; keep only the two intentional repository control files.
    if path.name.startswith(".") and path.name not in ALLOWED_HIDDEN_FILES:
        return False
    if path.name.startswith("test-results-") or path.name.startswith("VALIDATION_RECEIPT"):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in {".pyc", ".bak", ".sqlite", ".sqlite3", ".db", ".tmp", ".log"}:
        return False
    return path.is_file()


def main() -> None:
    destination = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "ComfyUI-SickOllie-release.zip"
    ).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(ROOT.rglob("*")):
                # A destination inside the project must never package itself.
                if path.resolve() == destination or path.resolve() == temporary_path:
                    continue
                if include(path):
                    archive.write(path, Path(ROOT.name) / path.relative_to(ROOT))
        temporary_path.replace(destination)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    print(destination)


if __name__ == "__main__":
    main()
