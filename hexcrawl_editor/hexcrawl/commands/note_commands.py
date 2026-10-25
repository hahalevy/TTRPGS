from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from ..models.notes import Note
from .fields import SetFieldsCommand


class AddNoteCommand(QUndoCommand):
    def __init__(self, scene, note: Note, text: str = "Add note"):
        super().__init__(text)
        self.scene = scene
        self.note = note

    def redo(self) -> None:
        self.scene.insert_note(self.note, len(self.scene.project.notes))

    def undo(self) -> None:
        self.scene.remove_note(self.note.id)


class DeleteNoteCommand(QUndoCommand):
    def __init__(self, scene, note_id: str, text: str = "Delete note"):
        super().__init__(text)
        self.scene = scene
        self.note = scene.project.find_note(note_id)
        self.index = scene.project.notes.index(self.note)

    def redo(self) -> None:
        self.scene.remove_note(self.note.id)

    def undo(self) -> None:
        self.scene.insert_note(self.note, self.index)


class SetNoteFieldsCommand(SetFieldsCommand):
    def target(self):
        return self.scene.project.find_note(self.key)

    def refresh(self) -> None:
        self.scene.notes_changed.emit()
