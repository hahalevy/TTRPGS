from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsPixmapItem, QStyleOptionGraphicsItem, QWidget

from ...models.elements import AssetElement, DecorationStyle
from ..decoration_paint import build_asset_outline_pixmap, paint_border
from ..images import ASSET_SIZE, load_image
from .handles import PlacedItemMixin


@lru_cache(maxsize=256)
def _outline_for(abs_path: str, width: float, color: str):
    return build_asset_outline_pixmap(load_image(abs_path), DecorationStyle(True, color, width))


class AssetItem(PlacedItemMixin, QGraphicsPixmapItem):
    """The image is kept at full resolution; a base factor folded into the
    transform makes every asset start at the same small size (ASSET_SIZE)
    regardless of its source resolution. scale_x/scale_y are relative to that.
    """

    def __init__(self, element: AssetElement, assets_dir: Path):
        super().__init__()
        self._assets_dir = assets_dir
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self._init_placed(element)
        self.sync_from_element(element)

    def sync_from_element(self, element: AssetElement) -> None:
        self.abs_path = str(self._assets_dir / element.asset_path)
        pixmap = load_image(self.abs_path)
        self.setPixmap(pixmap)
        # Centered on the item origin: an asset's pos is its center, so it lands
        # where you click and scales/rotates in place.
        self.setOffset(-pixmap.width() / 2, -pixmap.height() / 2)
        self._base_factor = ASSET_SIZE / max(pixmap.width(), pixmap.height(), 1)
        self._sync_placed(element)

    def _matrix_scale(self) -> tuple[float, float]:
        return self._scale_x * self._base_factor, self._scale_y * self._base_factor

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        # Decoration widths are in map units; the image is drawn in source
        # pixels, so convert by the base factor.
        if self._outline.enabled:
            result = _outline_for(self.abs_path, round(self._outline.width / self._base_factor, 1), self._outline.color)
            if result is not None:
                outline_pixmap, pad = result
                painter.drawPixmap(self.offset() - QPointF(pad, pad), outline_pixmap)
        super().paint(painter, option, widget)
        paint_border(painter, self.boundingRect(), replace(self._border, width=self._border.width / self._base_factor))
