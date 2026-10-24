"""One generic two-way binding between panel widgets and element fields,
used identically by every tab (Draw line/shapes, Labels, Assets, Fog):

    binder = FieldBinder({"color": color_button, "width": spin, "opacity": (slider, 0.01)})
    binder.values()      -> {"color": ..., "width": ..., "opacity": ...}   (new-element settings)
    binder.load(element) -> show an element's (or dict's) values without emitting edits
    binder.edited        -> emitted on any user change; the app applies values() to the selection

A spec may be (widget, scale) to convert units, e.g. a 0-100 slider for a 0-1 field.

With `key`, the panel starts from the factory defaults (resources/defaults.json
section of that name) overlaid with the current project's last-used values, saves
its values on every user edit, and reloads when another project is opened. `skip` lists fields not worth remembering (e.g. text).
"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, QSlider, QSpinBox

from ..app_config import preferences, remember, remembered
from ..defaults import DEFAULTS
from ..models.elements import to_json
from .color_picker_button import ColorPickerButton


def _combo_get(combo: QComboBox):
    data = combo.currentData()
    return data if data is not None else combo.currentText()


def _combo_set(combo: QComboBox, value) -> None:
    index = combo.findData(value)
    if index < 0:
        index = combo.findText(str(value))
    if index < 0:
        combo.addItem(str(value))
        index = combo.count() - 1
    combo.setCurrentIndex(index)


def _accessors(widget):
    """(getter, setter, change_signal) for each supported widget type."""
    # Composite widgets (e.g. DecorationControls) expose value/set_value/changed.
    # Checked first: they may subclass a basic widget (DecorationControls is a QGroupBox).
    if hasattr(widget, "set_value"):
        return widget.value, widget.set_value, widget.changed
    if isinstance(widget, ColorPickerButton):
        return widget.color, widget.setColor, widget.colorChanged
    if isinstance(widget, QLineEdit):
        return widget.text, widget.setText, widget.textChanged
    if isinstance(widget, QComboBox):
        return (lambda: _combo_get(widget)), (lambda v: _combo_set(widget, v)), widget.currentIndexChanged
    if isinstance(widget, QCheckBox):
        return widget.isChecked, widget.setChecked, widget.toggled
    if isinstance(widget, (QSpinBox, QDoubleSpinBox, QSlider)):
        return widget.value, widget.setValue, widget.valueChanged
    raise TypeError(f"FieldBinder doesn't support {type(widget).__name__}")


class FieldBinder(QObject):
    edited = Signal()

    def __init__(self, specs: dict, parent=None, key: str | None = None, skip: tuple = ()):
        super().__init__(parent)
        self._key, self._skip = key, skip
        self._fields = {}
        for name, spec in specs.items():
            widget, scale = spec if isinstance(spec, tuple) else (spec, None)
            getter, setter, signal = _accessors(widget)
            self._fields[name] = (widget, getter, setter, scale)
            signal.connect(self._on_widget_changed)
        self._loading = False
        if key:
            self.reload()
            self.edited.connect(self.save)
            preferences.loaded.connect(self.reload)

    def reload(self) -> None:
        self.load(DEFAULTS[self._key])
        self.load(remembered(self._key, {}))

    def save(self) -> None:
        """Stores the current values as the project's last-used ones (when `key` is set)."""
        if self._key:
            remember(self._key, {k: to_json(v) for k, v in self.values().items() if k not in self._skip})

    def _on_widget_changed(self, *_args) -> None:
        if not self._loading:
            self.edited.emit()

    def values(self) -> dict:
        result = {}
        for name, (_widget, getter, _setter, scale) in self._fields.items():
            value = getter()
            result[name] = value * scale if scale else value
        return result

    def load(self, source) -> None:
        """Shows values from an element or dict; fields the source lacks are left as they are."""
        self._loading = True
        try:
            for name, (widget, _getter, setter, scale) in self._fields.items():
                value = source.get(name) if isinstance(source, dict) else getattr(source, name, None)
                if value is None:
                    continue
                widget.blockSignals(True)
                try:
                    setter(round(value / scale) if scale else value)
                finally:
                    widget.blockSignals(False)
        finally:
            self._loading = False
