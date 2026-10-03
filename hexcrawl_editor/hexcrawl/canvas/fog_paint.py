"""Shared fog-of-war paint logic used by FogMaskItem (live canvas) and the
exporter, so on-screen and exported fog state always match.

Model: `element.regions` is a list of {"rect": [x,y,w,h], "mode": "hide"|"reveal"}
rectangles in the order they were drawn. The covered (opaque) area is the union
of all "hide" rectangles minus the union of all "reveal" rectangles - so a
"reveal" drag always punches a hole through fog in that exact area, regardless
of which "hide" rectangle(s) it overlaps (true partial reveal, not just
all-or-nothing per original rectangle). With no regions at all, nothing is
covered - fog is opt-in, not a default full-map overlay.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath

from ..models.elements import FogMaskElement


def _union_path(rects: list) -> QPainterPath:
    path = QPainterPath()
    for rect in rects:
        x, y, w, h = rect["rect"]
        piece = QPainterPath()
        piece.addRect(QRectF(x, y, w, h))
        path = path.united(piece)
    return path


def fog_path(element: FogMaskElement, bounds: QRectF) -> QPainterPath:
    hide_rects = [r for r in element.regions if r.get("mode", "hide") == "hide"]
    reveal_rects = [r for r in element.regions if r.get("mode") == "reveal"]
    covered = _union_path(hide_rects)
    if reveal_rects:
        covered = covered.subtracted(_union_path(reveal_rects))
    return covered.intersected(_bounds_path(bounds))


def _bounds_path(bounds: QRectF) -> QPainterPath:
    path = QPainterPath()
    path.addRect(bounds)
    return path


def paint_fog(painter: QPainter, element: FogMaskElement, bounds: QRectF) -> None:
    painter.save()
    painter.setOpacity(painter.opacity() * element.base_opacity)
    painter.setPen(QColor(0, 0, 0, 0))
    painter.setBrush(QColor(element.color))
    painter.drawPath(fog_path(element, bounds))
    painter.restore()
