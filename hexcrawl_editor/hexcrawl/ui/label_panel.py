from __future__ import annotations

from PySide6.QtWidgets import QDockWidget, QFormLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

from .color_picker_button import ColorPickerButton
from .decoration_controls import DecorationControls
from .field_binder import FieldBinder
from .font_manager import FontManager
from .recent_items import RecentStrip
from .widgets import combo, opacity_slider

SNAPSHOT_FIELDS = ("text", "font_family", "font_size", "font_color")


class LabelPanel(QDockWidget):
    def __init__(self, font_manager: FontManager, parent=None):
        super().__init__("Labels", parent)
        self.font_manager = font_manager

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
        self.binder = FieldBinder(fields, self, key="label", skip=("text",))

        layout.addWidget(QLabel("Recently Used"))
        self.recent = RecentStrip(
            describe=lambda s: (None, s["text"]), key=lambda s: (s["text"], s["font_family"]), storage_key="recent_labels"
        )
        self.recent.picked.connect(self.binder.load)
        layout.addWidget(self.recent)
        self.setWidget(container)

    def _import_font(self) -> None:
        for family in self.font_manager.import_font_file(self):
            self.binder.load({"font_family": family})
            self.binder.save()

    def current_settings(self) -> dict:
        return self.binder.values()

    def notify_label_placed(self, settings: dict) -> None:
        self.recent.push({k: settings[k] for k in SNAPSHOT_FIELDS})
