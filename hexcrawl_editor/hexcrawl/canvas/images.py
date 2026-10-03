"""The one image loader for canvas assets and panel thumbnails. Any format Qt
reads natively works as-is (PNG, JPG, WebP, BMP, GIF, SVG...). Vector images
are rasterized at HI_RES so they stay crisp when enlarged on the map.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImageReader, QPixmap

HI_RES = 512  # longest side, in pixels, that vector images are rendered at
ASSET_SIZE = 48.0  # default on-map size (longest side, scene units) of every placed asset


def image_extensions() -> set[str]:
    return {"." + bytes(fmt).decode() for fmt in QImageReader.supportedImageFormats()}


@lru_cache(maxsize=None)
def _load(path: str, mtime: float) -> QPixmap:
    reader = QImageReader(path)
    size = reader.size()
    if bytes(reader.format()) in (b"svg", b"svgz") and size.isValid():
        reader.setScaledSize(size.scaled(HI_RES, HI_RES, Qt.AspectRatioMode.KeepAspectRatio))
    return QPixmap.fromImage(reader.read())


def load_image(path: Path | str) -> QPixmap:
    """Cached per file version, so an edited file is picked up again."""
    path = Path(path)
    return _load(str(path), path.stat().st_mtime) if path.exists() else QPixmap()
