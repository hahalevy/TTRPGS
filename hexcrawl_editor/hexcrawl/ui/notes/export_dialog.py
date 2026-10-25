from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout,
)

from ...io.note_export import FORMATS, export_notes, print_notes
from ..widgets import choice_combo

PRINT = "print"


class NotesExportDialog(QDialog):
    """Choose which notes to export (all or some) and in which format."""

    def __init__(self, notes: list, preselected: set[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export notes")
        self.resize(380, 460)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        for note in notes:
            item = QListWidgetItem(note.title)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if note.id in preselected else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, note.id)
            self.list.addItem(item)
        layout.addWidget(self.list)
        row = QHBoxLayout()
        for text, state in (("Select all", Qt.CheckState.Checked), ("Select none", Qt.CheckState.Unchecked)):
            button = QPushButton(text)
            button.clicked.connect(lambda _=False, s=state: self._check_all(s))
            row.addWidget(button)
        layout.addLayout(row)

        self.format = choice_combo([(label, key) for key, (label, _) in FORMATS.items()] + [("Print...", PRINT)])
        self.page_breaks = QCheckBox("Start each note on a new page")
        self.page_breaks.setChecked(True)
        self.separate = QCheckBox("One file per note")
        self.format.currentIndexChanged.connect(lambda _: self.separate.setEnabled(self.format.currentData() != PRINT))
        form = QFormLayout()
        form.addRow("Format", self.format)
        form.addRow(self.page_breaks)
        form.addRow(self.separate)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _check_all(self, state: Qt.CheckState) -> None:
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def chosen_ids(self) -> set[str]:
        return {self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked}


def run_export(parent, project, preselected: set[str]) -> None:
    """The whole interactive export: pick notes + format, pick a destination, write."""
    if not project.notes:
        QMessageBox.information(parent, "Export notes", "There are no notes to export yet.")
        return
    dialog = NotesExportDialog(project.notes, preselected, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    chosen = dialog.chosen_ids()
    notes = [n for n in project.notes if n.id in chosen]  # keeps the project's order
    if not notes:
        QMessageBox.information(parent, "Export notes", "Tick at least one note to export.")
        return
    fmt, page_breaks = dialog.format.currentData(), dialog.page_breaks.isChecked()
    if fmt == PRINT:
        printer = QPrinter()
        if QPrintDialog(printer, parent).exec() == QDialog.DialogCode.Accepted:
            print_notes(project, notes, printer, page_breaks)
        return
    label, extension = FORMATS[fmt]
    separate = dialog.separate.isChecked() and len(notes) > 1
    if separate:
        folder = QFileDialog.getExistingDirectory(parent, "Export each note into folder")
        if not folder:
            return
        written = export_notes(project, notes, fmt, Path(folder), True, page_breaks)
    else:
        name, _ = QFileDialog.getSaveFileName(parent, "Export notes", "", f"{label} (*{extension})")
        if not name:
            return
        written = export_notes(project, notes, fmt, Path(name).with_suffix(extension), False, page_breaks)
    where = written[0].parent if separate else written[0]
    QMessageBox.information(parent, "Export complete", f"Exported {len(notes)} note(s) to {where}")
