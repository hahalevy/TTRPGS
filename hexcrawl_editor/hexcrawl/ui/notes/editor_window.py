"""The note editing window: one note at a time - title, what it is attached to
(or a bar to attach it), and the rich-text editor. Closing it just leaves the
note in the overview pane, attached or detached as you left it."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QDockWidget, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QToolButton, QVBoxLayout, QWidget

from ...commands import edit_note
from ...models.notes import Note
from ...models.targets import target_label
from .actions import NoteActions
from .editor import NoteEditor
from .format_toolbar import FormatToolbar
from .icons import DETACHED_COLOR
from .link_dialog import follow_link
from .preview import NotePreviewDialog

BODY_COMMIT_DELAY_MS = 500
BAR_STYLE = "text-align: left; padding: 3px;"


class NoteEditorWindow(QDockWidget):
    bodyEdited = Signal()  # the text changed (not an undo-stack edit: the project is now unsaved)
    targetRequested = Signal(str)  # "show me what this note is attached to"

    def __init__(self, scene, undo_stack, actions: NoteActions, parent=None):
        super().__init__("Note", parent)
        self.scene = scene
        self.undo_stack = undo_stack
        self.actions = actions
        self._current_id: str | None = None  # the note shown
        self._baseline = ""  # editor html right after loading, to tell real edits from normalization
        self._loading = False
        self._refresh_pending = False
        self.selected_id = ""  # layer / element selected in the app: where "Attach" starts

        container = QWidget()
        layout = QVBoxLayout(container)
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Title")
        font = self.title_edit.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.title_edit.setFont(font)
        self.title_edit.editingFinished.connect(self._commit_title)
        layout.addWidget(self.title_edit)

        bar = QHBoxLayout()
        self.attach_button = QPushButton()
        self.attach_button.setFlat(True)
        self.attach_button.clicked.connect(lambda: self.actions.attach(self, self._note(), self.selected_id))
        self.detach_button = QToolButton()
        self.detach_button.setText("Detach")
        self.detach_button.setToolTip("Keep the note but disconnect it from its layer / element")
        self.detach_button.clicked.connect(lambda: self.actions.detach(self._note()))
        self.goto_button = QToolButton()
        self.goto_button.setText("Show")
        self.goto_button.setToolTip("Select the attached element or layer")
        self.goto_button.clicked.connect(lambda: self.targetRequested.emit(self._note().target_id))
        bar.addWidget(self.attach_button, 1)
        bar.addWidget(self.goto_button)
        bar.addWidget(self.detach_button)
        layout.addLayout(bar)

        self.editor = NoteEditor()
        self.format_toolbar = FormatToolbar(self.editor, self._link_candidates)
        layout.addWidget(self.format_toolbar)
        layout.addWidget(self.editor, 1)

        buttons = QHBoxLayout()
        self.delete_button = QPushButton("Delete note")
        self.delete_button.clicked.connect(self.delete_current)
        export_button = QPushButton("Export...")
        export_button.clicked.connect(lambda: self.actions.export(self, {self._current_id} if self._current_id else set()))
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(export_button)
        layout.addLayout(buttons)
        self.setWidget(container)

        self._body_timer = QTimer(self)
        self._body_timer.setSingleShot(True)
        self._body_timer.setInterval(BODY_COMMIT_DELAY_MS)
        self._body_timer.timeout.connect(self._commit_body)
        self.editor.textChanged.connect(lambda: None if self._loading else self._body_timer.start())
        self.editor.linkActivated.connect(lambda href: follow_link(href, self.preview_note))
        self.visibilityChanged.connect(lambda visible: None if visible else self.flush())
        self.scene.notes_changed.connect(self.request_refresh)
        self._show(None)

    # --- model access ---
    @property
    def project(self):
        return self.scene.project

    def _note(self) -> Note | None:
        return self.project.find_note(self._current_id) if self._current_id else None

    def _link_candidates(self) -> list[tuple[str, str]]:
        return [(n.title, n.id) for n in self.project.notes if n.id != self._current_id]

    # --- showing a note ---
    def open_note(self, note_id: str, focus_title: bool = False) -> None:
        if self.project.find_note(note_id) is None:
            return
        if note_id != self._current_id:
            self._show(note_id)
        self.show()
        self.raise_()
        if focus_title:
            self.title_edit.setFocus()
            self.title_edit.selectAll()

    def _show(self, note_id: str | None) -> None:
        self.flush()
        self._current_id = note_id
        note = self._note()
        self._loading = True
        self.editor.load(note.html if note else "", note.images if note else {})
        self._baseline = self.editor.dump()[0]
        self._loading = False
        self.title_edit.setText(note.title if note else "")
        self.setEnabled(note is not None)
        self.setWindowTitle(f"Note - {note.title}" if note else "Note")
        self._sync_header()

    def request_refresh(self) -> None:
        """Deferred: model changes often arrive while one of this window's widgets is mid-event."""
        if not self._refresh_pending:
            self._refresh_pending = True
            QTimer.singleShot(0, self._refresh)

    def _refresh(self) -> None:
        self._refresh_pending = False
        if self._current_id and self._note() is None:  # deleted (or its creation undone)
            self._show(None)
            self.hide()
            return
        note = self._note()
        if note is not None and not self.title_edit.hasFocus():
            self.title_edit.setText(note.title)
        self._sync_header()

    def _sync_header(self) -> None:
        note = self._note()
        if note is None:
            self.attach_button.setText("")
            self.goto_button.hide()
            self.detach_button.hide()
            return
        self.setWindowTitle(f"Note - {note.title}")
        attached = self.project.is_attached(note)
        if attached:
            self.attach_button.setText(f"Attached to: {target_label(self.project, note.target_id)}  (click to change)")
            self.attach_button.setStyleSheet(BAR_STYLE)
        else:
            reason = "its element was deleted" if note.target_id else "not attached to anything"
            self.attach_button.setText(f"⚠ Detached ({reason}) - click to attach")
            self.attach_button.setStyleSheet(f"{BAR_STYLE} font-weight: bold; color: {DETACHED_COLOR};")
        self.goto_button.setVisible(attached)
        self.detach_button.setVisible(attached)

    def reset(self) -> None:
        """A different project was loaded."""
        self._body_timer.stop()
        self.selected_id = ""
        self._show(None)
        self.hide()

    # --- editing ---
    def flush(self) -> None:
        """Commits anything typed but not yet stored (call before saving, switching or exporting)."""
        self._body_timer.stop()
        self._commit_body()
        self._commit_title()

    def _commit_body(self) -> None:
        note = self._note()
        if note is None:
            return
        html, images = self.editor.dump()
        if html != self._baseline:
            self._baseline = html
            note.html, note.images = html, images
            self.bodyEdited.emit()

    def _commit_title(self) -> None:
        note = self._note()
        text = self.title_edit.text().strip()
        if note is None:
            return
        if text and text != note.title:
            edit_note(self.undo_stack, self.scene, note, {"title": text}, "Rename note")
        elif not text:
            self.title_edit.setText(note.title)

    def delete_current(self) -> None:
        note = self._note()
        if note is not None:
            self.actions.delete(self, note)  # the refresh that follows closes this window

    def preview_note(self, note_id: str) -> None:
        if self.project.find_note(note_id) is None:
            QMessageBox.information(self, "Missing note", "That note no longer exists.")
            return
        preview = NotePreviewDialog(self.project, note_id, self.window())
        preview.openRequested.connect(self.open_note)
        preview.show()
