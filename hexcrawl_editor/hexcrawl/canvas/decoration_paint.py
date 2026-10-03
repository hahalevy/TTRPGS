"""Border/outline rendering shared by LabelItem and AssetItem.

Border = a plain rect stroked around the element's bounding box.
Outline = traces the actual non-transparent content:
  - vector content (text glyphs): stroke the content path itself.
  - raster assets: alpha-mask "poor man's dilation" via ring-offset stamping,
    cached per (asset_path, outline width) by the caller.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

from ..models.elements import DecorationStyle


def _stroke(painter: QPainter, style: DecorationStyle, draw) -> None:
    if not style.enabled:
        return
    painter.save()
    pen = QPen(QColor(style.color))
    pen.setWidthF(max(style.width, 0.1))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    draw()
    painter.restore()


def paint_border(painter: QPainter, bounding_rect: QRectF, border: DecorationStyle) -> None:
    _stroke(painter, border, lambda: painter.drawRect(bounding_rect))


def paint_path_outline(painter: QPainter, path: QPainterPath, outline: DecorationStyle) -> None:
    _stroke(painter, outline, lambda: painter.drawPath(path))


def build_asset_outline_pixmap(pixmap: QPixmap, outline: DecorationStyle) -> tuple[QPixmap, int] | None:
    """Returns (outline_pixmap, padding) where outline_pixmap is sized
    pixmap.size() + 2*padding and should be drawn offset by (-padding, -padding)
    relative to where the base pixmap is drawn, so the ring sits just outside it.
    """
    if not outline.enabled or pixmap.isNull():
        return None

    width = max(outline.width, 0.5)
    pad = int(math.ceil(width)) + 1
    base_alpha = pixmap.toImage().convertToFormat(QImage.Format.Format_Alpha8)
    w, h = base_alpha.width(), base_alpha.height()

    padded = QImage(w + 2 * pad, h + 2 * pad, QImage.Format.Format_Alpha8)
    padded.fill(0)
    p = QPainter(padded)
    p.drawImage(pad, pad, base_alpha)
    p.end()

    dilated = QImage(padded.size(), QImage.Format.Format_Alpha8)
    dilated.fill(0)
    p = QPainter(dilated)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Lighten)
    steps = max(8, int(width * 4))
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        ox = width * math.cos(angle)
        oy = width * math.sin(angle)
        p.drawImage(ox, oy, padded)
    p.end()

    ring = QImage(dilated)
    p = QPainter(ring)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationOut)
    p.drawImage(0, 0, padded)
    p.end()

    colored = QImage(ring.size(), QImage.Format.Format_ARGB32_Premultiplied)
    colored.fill(Qt.GlobalColor.transparent)
    p = QPainter(colored)
    p.fillRect(colored.rect(), QColor(outline.color))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    p.drawImage(0, 0, ring)
    p.end()

    return QPixmap.fromImage(colored), pad
