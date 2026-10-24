from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from ...models.elements import FogMaskElement


# Fog model: `element.regions` is a list of {"rect": [x,y,w,h], "mode": "hide"|"reveal"}
# rectangles in drawing order. The covered area is the union of all "hide" rectangles
# minus the union of all "reveal" rectangles, so a reveal punches a true partial hole
# whichever hide rectangles it overlaps. With no regions nothing is covered.
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


class FogMaskItem(QGraphicsItem):
    """Never interactive on the canvas: it spans the whole map, so letting it
    take clicks would block every element beneath it. Fog is edited with the
    Fog tool and managed from the layer panel / Effects dialog instead.
    """

    def __init__(self, element: FogMaskElement, get_bounds):
        super().__init__()
        self.element_id = element.id
        self.setData(0, element.id)
        self._get_bounds = get_bounds  # map bounds can change (new base map)
        self._bounds = QRectF(get_bounds())
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.setZValue(500)
        self.sync_from_element(element)

    def boundingRect(self) -> QRectF:
        return self._bounds

    def shape(self) -> QPainterPath:
        return fog_path(self._element, self._bounds)

    def sync_from_element(self, element: FogMaskElement) -> None:
        self.prepareGeometryChange()
        self._element = element
        self._bounds = QRectF(self._get_bounds())
        self.setVisible(element.visible)
        self.update()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        paint_fog(painter, self._element, self._bounds)
