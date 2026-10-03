from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".bmp", ".gif"}


@dataclass
class AssetEntry:
    category: str
    name: str
    abs_path: Path
    relative_path: str  # relative to assets root, e.g. "Settlements/town.png"


def scan_assets(root: Path, extensions: set[str] = DEFAULT_EXTENSIONS) -> dict[str, list[AssetEntry]]:
    """Walk immediate subdirectories of `root` (category = subfolder name, one
    level deep, no hardcoded category list). Returns {} gracefully if root is
    missing or empty. The app passes every format Qt can read.
    """
    categories: dict[str, list[AssetEntry]] = {}
    if not root.exists():
        return categories
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        entries = []
        for file in sorted(sub.iterdir()):
            if file.is_file() and file.suffix.lower() in extensions:
                entries.append(
                    AssetEntry(
                        category=sub.name,
                        name=file.stem,
                        abs_path=file,
                        relative_path=f"{sub.name}/{file.name}",
                    )
                )
        if entries:
            categories[sub.name] = entries
    return categories
