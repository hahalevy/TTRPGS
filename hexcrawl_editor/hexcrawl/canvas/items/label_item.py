from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem, QStyleOptionGraphicsItem, QWidget

from ...models.elements import LabelElement
from ..decoration_paint import paint_border, paint_path_outline
from .handles import PlacedItemMixin


class LabelItem(PlacedItemMixin, QGraphicsTextItem):
    """Renders text as one glyph path (fill and outline share identical
    geometry, so the outline hugs the letters) except while being edited
    (double click), when native QGraphicsTextItem rendering takes over so
    typing/caret work normally.
    """

    def __init__(self, element: LabelElement):
        super().__init__()
        self._editing = False
        self._text_before_edit = ""
        self._init_placed(element)
        self.sync_from_element(element)

    def sync_from_element(self, element: LabelElement) -> None:
        self.setPlainText(element.text)
        self.setFont(QFont(element.font_family, element.font_size))
        self._font_color = QColor(element.font_color)
        self.setDefaultTextColor(self._font_color)
        self._sync_placed(element)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        if self._editing:
            super().paint(painter, option, widget)
        elif self.toPlainText():
            glyphs = QPainterPath()
            glyphs.addText(0.0, QFontMetricsF(self.font()).ascent(), self.font(), self.toPlainText())
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            paint_path_outline(painter, glyphs, self._outline)
            painter.fillPath(glyphs, self._font_color)
            painter.restore()
        paint_border(painter, self.boundingRect(), self._border)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged and not value and self._editing:
            self._stop_editing()
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:
        self._editing = True
        self._text_before_edit = self.toPlainText()
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.update()
        super().mouseDoubleClickEvent(event)

    def _stop_editing(self) -> None:
        self._editing = False
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.update()
        new_text = self.toPlainText()
        if new_text != self._text_before_edit and callable(self.on_edited):
            self.on_edited({"text": self._text_before_edit}, {"text": new_text}, "Edit text")

    def focusOutEvent(self, event) -> None:
        if self._editing:
            self._stop_editing()
        super().focusOutEvent(event)
