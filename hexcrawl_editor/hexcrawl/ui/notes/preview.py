from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from ...io.note_document import note_document
from ...models.targets import target_label
from .link_dialog import follow_link


class NotePreviewDialog(QDialog):
    """The pop-up shown when a link to another note is followed. Links inside it
    navigate within the pop-up (Back returns); "Open in Notes" edits the note."""

    openRequested = Signal(str)

    def __init__(self, project, note_id: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.resize(480, 560)
        self.project = project
        self.history: list[str] = []
        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.title.setWordWrap(True)
        self.where = QLabel()
        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(lambda url: follow_link(url.toString(), self.show_note))
        buttons = QHBoxLayout()
        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self._back)
        self.open_button = QPushButton("Open in Notes")
        self.open_button.clicked.connect(lambda: self.openRequested.emit(self.history[-1]))
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        buttons.addWidget(self.back_button)
        buttons.addStretch()
        buttons.addWidget(self.open_button)
        buttons.addWidget(close)
        for widget in (self.title, self.where, self.browser):
            layout.addWidget(widget)
        layout.addLayout(buttons)
        self.show_note(note_id)

    def show_note(self, note_id: str) -> None:
        self.history.append(note_id)
        self._display()

    def _back(self) -> None:
        self.history.pop()
        self._display()

    def _display(self) -> None:
        note = self.project.find_note(self.history[-1])
        self.back_button.setEnabled(len(self.history) > 1)
        self.open_button.setEnabled(note is not None)
        if note is None:
            self.title.setText("Missing note")
            self.where.setText("")
            self.browser.setPlainText("That note no longer exists.")
            return
        where = target_label(self.project, note.target_id)
        self.setWindowTitle(note.title)
        self.title.setText(note.title)
        self.where.setText(f"Attached to: {where}" if where else "Not attached to anything")
        self.browser.setDocument(note_document(note.html, note.images, self.browser))
