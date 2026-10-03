from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QFormLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from ..app_config import DEFAULT_FONT_COLOR, DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE, get_settings
from .color_picker_button import ColorPickerButton
from .decoration_controls import DecorationControls
from .field_binder import FieldBinder
from .font_manager import FontManager
from .recent_items import RecentStrip
from .widgets import combo, opacity_slider

# Font settings remembered across app restarts (QSettings key -> default).
REMEMBERED_FONT_FIELDS = {
    "font_family": DEFAULT_FONT_FAMILY,
    "font_size": DEFAULT_FONT_SIZE,
    "font_color": DEFAULT_FONT_COLOR,
}


class LabelPanel(QDockWidget):
    def __init__(self, font_manager: FontManager, parent=None):
        super().__init__("Labels", parent)
        self.font_manager = font_manager
        self.settings = get_settings()

        container = QWidget()
        layout = QVBoxLayout(container)
        form = QFormLayout()
        size = QSpinBox()
        size.setRange(4, 200)
        self.font_combo = combo(self.font_manager.available_families())
        fields = {
            "text": QLineEdit(), "font_family": self.font_combo, "font_size": size,
            "font_color": ColorPickerButton(), "opacity": opacity_slider(),
        }
        for label, key in (("Text", "text"), ("Font", "font_family"), ("Size", "font_size"),
                           ("Color", "font_color"), ("Opacity", "opacity")):
            form.addRow(label, fields[key][0] if isinstance(fields[key], tuple) else fields[key])
        layout.addLayout(form)

        import_btn = QPushButton("Import Font...")
        import_btn.clicked.connect(self._import_font)
        layout.addWidget(import_btn)

        fields["border"], fields["outline"] = DecorationControls("Border"), DecorationControls("Outline")
        layout.addWidget(fields["border"])
        layout.addWidget(fields["outline"])
        self.binder = FieldBinder(fields, self)

        layout.addWidget(QLabel("Recently Used"))
        self.recent = RecentStrip(
            describe=lambda s: (None, s["text"]), key=lambda s: (s["text"], s["font_family"])
        )
        self.recent.picked.connect(self.binder.load)
        layout.addWidget(self.recent)
        self.setWidget(container)

        self.binder.load({k: self.settings.value(f"label/{k}", d, type=type(d)) for k, d in REMEMBERED_FONT_FIELDS.items()})
        self.binder.edited.connect(self._remember_font)

    def _remember_font(self) -> None:
        values = self.binder.values()
        for key in REMEMBERED_FONT_FIELDS:
            self.settings.setValue(f"label/{key}", values[key])

    def _import_font(self) -> None:
        for family in self.font_manager.import_font_file(self):
            self.binder.load({"font_family": family})
            self._remember_font()

    def current_settings(self) -> dict:
        return self.binder.values()

    def notify_label_placed(self, settings: dict) -> None:
        self.recent.push({k: settings[k] for k in ("text", "font_family", "font_size", "font_color")})
