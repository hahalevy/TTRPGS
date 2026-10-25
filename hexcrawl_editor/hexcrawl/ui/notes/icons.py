from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

ATTACHED_COLOR, DETACHED_COLOR = "#2e7d32", "#d97706"


def link_icon(attached: bool) -> QIcon:
    """Two chain links when the note is attached; broken apart and orange when it is detached."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(ATTACHED_COLOR if attached else DETACHED_COLOR), 1.8))
    gap = 0 if attached else 1.5
    painter.drawRoundedRect(QRectF(1, 5, 8 - gap, 6), 3, 3)
    painter.drawRoundedRect(QRectF(7 + gap, 5, 8 - gap, 6), 3, 3)
    if not attached:
        painter.drawLine(2, 14, 14, 2)
    painter.end()
    return QIcon(pixmap)
