from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QRadioButton, QVBoxLayout,
)

from ...models.notes import NOTE_LINK_PREFIX


class LinkDialog(QDialog):
    """A hyperlink to a web address or to another note."""

    def __init__(self, text: str, href: str, notes: list[tuple[str, str]], parent=None):
        """notes: (title, id) of the notes that can be linked to."""
        super().__init__(parent)
        self.setWindowTitle("Hyperlink")
        self.text_edit = QLineEdit(text)
        self.web_radio, self.note_radio = QRadioButton("Web address"), QRadioButton("Another note")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")
        self.note_combo = QComboBox()
        for title, note_id in notes:
            self.note_combo.addItem(title, note_id)
        self.note_radio.setEnabled(bool(notes))
        group = QButtonGroup(self)
        group.addButton(self.web_radio)
        group.addButton(self.note_radio)
        if href.startswith(NOTE_LINK_PREFIX) and self.note_radio.isEnabled():
            self.note_radio.setChecked(True)
            self.note_combo.setCurrentIndex(max(0, self.note_combo.findData(href[len(NOTE_LINK_PREFIX):])))
        else:
            self.web_radio.setChecked(True)
            self.url_edit.setText("" if href.startswith(NOTE_LINK_PREFIX) else href)
        self.url_edit.textEdited.connect(lambda _: self.web_radio.setChecked(True))
        self.note_combo.activated.connect(lambda _: self.note_radio.setChecked(True))

        form = QFormLayout()
        form.addRow("Text to display", self.text_edit)
        form.addRow(self.web_radio, self.url_edit)
        form.addRow(self.note_radio, self.note_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.removed = False
        remove = buttons.addButton("Remove link", QDialogButtonBox.ButtonRole.DestructiveRole)
        remove.setEnabled(bool(href))
        remove.clicked.connect(self._remove)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _remove(self) -> None:
        self.removed = True
        self.accept()

    def link(self) -> tuple[str, str]:
        """(text, href); an empty href means "remove the link"."""
        text = self.text_edit.text()
        if self.removed:
            return text, ""
        if self.note_radio.isChecked():
            return text, NOTE_LINK_PREFIX + self.note_combo.currentData()
        url = self.url_edit.text().strip()
        if url and "://" not in url and not url.startswith(("mailto:", "#")):
            url = "https://" + url
        return text, url


def follow_link(href: str, open_note) -> None:
    """Opens a hyperlink: a link to a note goes to open_note(note_id), anything else to the system."""
    if href.startswith(NOTE_LINK_PREFIX):
        open_note(href[len(NOTE_LINK_PREFIX):])
    else:
        QDesktopServices.openUrl(QUrl(href))
