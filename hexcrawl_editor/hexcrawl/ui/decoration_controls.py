from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QHBoxLayout

from ..models.elements import DecorationStyle
from .color_picker_button import ColorPickerButton
from .field_binder import FieldBinder
from .widgets import width_spin


class DecorationControls(QGroupBox):
    """Checkable Border/Outline group whose value is a DecorationStyle:
    enabled = the group's checkbox, color/width via a FieldBinder."""

    changed = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)
        color, width = ColorPickerButton(), width_spin(2.0)
        layout = QHBoxLayout(self)
        layout.addWidget(color)
        layout.addWidget(width)
        self._binder = FieldBinder({"color": color, "width": width}, self)
        self._binder.edited.connect(self.changed.emit)
        self.toggled.connect(lambda _checked: self.changed.emit())

    def value(self) -> DecorationStyle:
        return DecorationStyle(enabled=self.isChecked(), **self._binder.values())

    def set_value(self, style: DecorationStyle) -> None:
        blocked = self.blockSignals(True)
        self.setChecked(style.enabled)
        self.blockSignals(blocked)
        self._binder.load(style)
