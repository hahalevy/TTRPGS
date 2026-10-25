"""Small widget factories shared by all panels, so each control type is
configured in exactly one place."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QMessageBox, QSlider


def combo(items: list[str]) -> QComboBox:
    widget = QComboBox()
    widget.addItems(items)
    return widget


def choice_combo(choices: list[tuple[str, object]]) -> QComboBox:
    """Shows labels, stores values (read back via FieldBinder as the value)."""
    widget = QComboBox()
    for label, value in choices:
        widget.addItem(label, value)
    return widget


def width_spin(value: float = 3.0) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(0.5, 50.0)
    widget.setSingleStep(0.5)
    widget.setValue(value)
    return widget


def opacity_slider() -> tuple[QSlider, float]:
    """A 0-100 slider plus the scale that maps it to a 0-1 field (FieldBinder spec)."""
    widget = QSlider(Qt.Orientation.Horizontal)
    widget.setRange(0, 100)
    widget.setValue(100)
    return widget, 0.01


def confirm(parent, title: str, text: str) -> bool:
    """Yes/No question; every delete-type action asks through here."""
    buttons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    answer = QMessageBox.question(parent, title, f"{text} (Ctrl+Z to undo)", buttons, QMessageBox.StandardButton.No)
    return answer == QMessageBox.StandardButton.Yes
