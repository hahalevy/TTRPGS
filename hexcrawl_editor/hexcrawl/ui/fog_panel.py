from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QFormLayout, QWidget

from .field_binder import FieldBinder
from .widgets import choice_combo

FOG_COLOR_CHOICES = [("Black", "#000000"), ("Grey", "#808080"), ("White", "#ffffff")]
FOG_MODES = [("Hide", "hide"), ("Reveal", "reveal")]


class FogPanel(QDockWidget):
    """Its own sidebar tab; switching to it activates the Fog tool."""

    def __init__(self, parent=None):
        super().__init__("Fog", parent)
        container = QWidget()
        form = QFormLayout(container)
        mode, color = choice_combo(FOG_MODES), choice_combo(FOG_COLOR_CHOICES)
        form.addRow("Mode", mode)
        form.addRow("Color", color)
        self.binder = FieldBinder({"mode": mode, "color": color}, self, key="fog")
        self.setWidget(container)
