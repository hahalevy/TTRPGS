from __future__ import annotations

from PySide6.QtCore import SIGNAL, QObject, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QDialog, QPushButton, QWidget


class ColorPickerButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, initial_color: str = "#000000", parent=None):
        super().__init__(parent)
        self.setObjectName("colorSwatch")
        self._color = initial_color
        self.setFixedWidth(40)
        self.clicked.connect(self._pick_color)
        self._update_swatch()

    def color(self) -> str:
        return self._color

    def setColor(self, color: str) -> None:
        self._color = color
        self._update_swatch()

    def _update_swatch(self) -> None:
        # Selector-scoped so the swatch color can't cascade into child widgets.
        self.setStyleSheet(
            f"QPushButton#colorSwatch {{ background-color: {self._color}; border: 1px solid #888; }}"
        )

    def _pick_color(self) -> None:
        # Parented to the window, not this button, so the dialog never
        # inherits the swatch's stylesheet.
        dialog = QColorDialog(QColor(self._color), self.window())
        dialog.setWindowTitle("Choose color")
        _fix_black_spectrum_trap(dialog, QColor(self._color))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        chosen = dialog.selectedColor()
        if not chosen.isValid():
            chosen = dialog.currentColor()
        if chosen.isValid():
            self._color = chosen.name()
            self._update_swatch()
            self.colorChanged.emit(self._color)


def _fix_black_spectrum_trap(dialog: QColorDialog, initial: QColor) -> None:
    """Qt's big hue/saturation spectrum keeps the current brightness, which
    is zero when starting from black - so every spectrum click still yields
    black (and the dialog doesn't even report a change, since it stores the
    color as RGB and black-with-any-hue is still black). The spectrum widget
    does announce the clicked hue/saturation via its newCol(h, s) signal, so
    when that fires while brightness is zero, lift brightness to full. Picking
    black from a color cell, or with the brightness slider, is unaffected.
    """
    picker = next(
        (w for w in dialog.findChildren(QWidget) if w.metaObject().className() == "QtPrivate::QColorPicker"),
        None,
    )
    if picker is None:  # Qt internals changed; fall back to stock behavior
        return

    def on_spectrum_pick(hue: int, saturation: int) -> None:
        if dialog.currentColor().value() == 0:
            dialog.setCurrentColor(QColor.fromHsv(hue, saturation, 255))

    dialog._spectrum_fix = QObject.connect(picker, SIGNAL("newCol(int,int)"), on_spectrum_pick)
