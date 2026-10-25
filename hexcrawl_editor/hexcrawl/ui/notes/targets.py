"""Picking what a note is attached to (a layer or any element)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from ...models.project import Project
from ...models.targets import KIND_LABELS, element_title

ID_ROLE = Qt.ItemDataRole.UserRole


class TargetPickerDialog(QDialog):
    """Lists every layer and element; choosing one attaches the note to it.
    "Detach" (the Remove button) leaves the note attached to nothing."""

    def __init__(self, project: Project, current_id: str = "", preselect_id: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Attach note to...")
        self.resize(360, 420)
        self.detached = False
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Pick the layer or element this note belongs to:"))
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        layout.addWidget(self.tree)
        wanted = preselect_id or current_id
        for layer in reversed(project.layers):
            layer_row = QTreeWidgetItem([layer.name])
            layer_row.setData(0, ID_ROLE, layer.id)
            self.tree.addTopLevelItem(layer_row)
            for element in layer.elements:
                row = QTreeWidgetItem([f"{element_title(element)}  ({KIND_LABELS.get(element.kind, element.kind)})"])
                row.setData(0, ID_ROLE, element.id)
                layer_row.addChild(row)
                if element.id == wanted:
                    self.tree.setCurrentItem(row)
            layer_row.setExpanded(True)
            if layer.id == wanted:
                self.tree.setCurrentItem(layer_row)
        self.tree.itemDoubleClicked.connect(lambda *_: self.accept())
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        detach = buttons.addButton("Detach", QDialogButtonBox.ButtonRole.DestructiveRole)
        detach.setEnabled(bool(current_id))
        detach.clicked.connect(self._detach)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _detach(self) -> None:
        self.detached = True
        self.accept()

    def chosen_id(self) -> str | None:
        """The picked id, "" for Detach, None if nothing is picked."""
        if self.detached:
            return ""
        item = self.tree.currentItem()
        return item.data(0, ID_ROLE) if item else None
