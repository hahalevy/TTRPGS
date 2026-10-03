from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from ...models.elements import FogMaskElement
from ..fog_paint import fog_path, paint_fog


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
