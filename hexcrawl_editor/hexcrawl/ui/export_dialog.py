from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QRadioButton, QSpinBox, QVBoxLayout,
)


class ExportDialog(QDialog):
    def __init__(self, default_width: int, default_height: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export PNG")
        self._default_width = default_width
        self._default_height = default_height

        layout = QVBoxLayout(self)

        self.scope_full = QRadioButton("Full map")
        self.scope_current = QRadioButton("Current view")
        self.scope_full.setChecked(True)
        layout.addWidget(self.scope_full)
        layout.addWidget(self.scope_current)

        self.custom_resolution_check = QCheckBox("Custom resolution")
        layout.addWidget(self.custom_resolution_check)

        form = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 20000)
        self.width_spin.setValue(default_width)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 20000)
        self.height_spin.setValue(default_height)
        form.addRow("Width", self.width_spin)
        form.addRow("Height", self.height_spin)
        layout.addLayout(form)

        self.custom_resolution_check.toggled.connect(self.width_spin.setEnabled)
        self.custom_resolution_check.toggled.connect(self.height_spin.setEnabled)
        self.width_spin.setEnabled(False)
        self.height_spin.setEnabled(False)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def scope(self) -> str:
        return "current_view" if self.scope_current.isChecked() else "full_map"

    def resolution(self) -> tuple[int, int] | None:
        if self.custom_resolution_check.isChecked():
            return self.width_spin.value(), self.height_spin.value()
        return None
