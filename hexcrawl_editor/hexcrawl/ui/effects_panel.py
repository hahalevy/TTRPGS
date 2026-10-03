from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QPushButton

from ..commands import edit_element, edit_layer, edit_project
from ..models.effects import FogOfWarEffect, OpacityEffect
from .color_picker_button import ColorPickerButton
from .field_binder import FieldBinder
from .fog_panel import FOG_COLOR_CHOICES
from .widgets import choice_combo, opacity_slider


class EffectsDialog(QDialog):
    """Effects for one layer. For the Base Map layer - or `layer_id=None` when
    the project has no base map - it also edits the project background, the
    color seen behind (and through) a faded base map."""

    def __init__(self, scene, undo_stack, layer_id: str | None, parent=None):
        super().__init__(parent)
        self.scene, self.undo_stack = scene, undo_stack
        self.layer = scene.project.find_layer(layer_id) if layer_id else None
        is_map = self.layer is None or self.layer.base_map
        self.setWindowTitle("Base Map Settings" if is_map else f"Effects: {self.layer.name}")
        form = QFormLayout(self)

        if self.layer is not None:
            opacity = opacity_slider()
            form.addRow("Map opacity" if is_map else "Opacity", opacity[0])
            self.opacity = FieldBinder({"value": opacity}, self)
            self.opacity.load(self._opacity_effect() or OpacityEffect())
            self.opacity.edited.connect(self._apply_opacity)

        if is_map:
            background = ColorPickerButton()
            form.addRow("Background", background)
            self.background = FieldBinder({"background_color": background}, self)
            self.background.load(scene.project)
            self.background.edited.connect(
                lambda: edit_project(self.undo_stack, self.scene, self.background.values(), "Change background")
            )

        fog = next((e for e in self.layer.effects if isinstance(e, FogOfWarEffect)), None) if self.layer else None
        self.mask = self.layer.find_element(fog.mask_element_id) if fog else None
        if self.mask is not None:
            form.addRow(QLabel(f"Fog of War: {len(self.mask.regions)} drawn region(s)"))
            color = choice_combo(FOG_COLOR_CHOICES)
            form.addRow("Fog color", color)
            self.fog = FieldBinder({"color": color}, self)
            self.fog.load(self.mask)
            self.fog.edited.connect(
                lambda: edit_element(self.undo_stack, self.scene, self.mask, self.fog.values(), "Change fog color")
            )
            clear = QPushButton("Clear All Fog")
            clear.clicked.connect(self._clear_fog)
            form.addRow(clear)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        form.addRow(close)

    def _opacity_effect(self):
        return next((e for e in self.layer.effects if isinstance(e, OpacityEffect)), None)

    def _apply_opacity(self) -> None:
        others = [e for e in self.layer.effects if not isinstance(e, OpacityEffect)]
        edit_layer(self.undo_stack, self.scene, self.layer,
                   {"effects": others + [OpacityEffect(**self.opacity.values())]}, "Change opacity")

    def _clear_fog(self) -> None:
        edit_element(self.undo_stack, self.scene, self.mask, {"regions": []}, "Clear all fog")
        self.accept()
