"""Shared style helpers used by canvas items AND the exporter, so on-screen and
exported rendering never drift apart.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen

_LINE_STYLE_MAP = {
    "solid": Qt.PenStyle.SolidLine,
    "dashed": Qt.PenStyle.DashLine,
    "dotted": Qt.PenStyle.DotLine,
}


def pen_from_style(color: str, width: float, line_style: str) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(max(width, 0.1))
    pen.setStyle(_LINE_STYLE_MAP.get(line_style, Qt.PenStyle.SolidLine))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen
