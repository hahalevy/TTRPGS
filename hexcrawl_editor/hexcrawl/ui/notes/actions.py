"""Creating, deleting, attaching, detaching and exporting notes. The overview pane
and the editing window both call these, so each action exists once."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMenu

from ...commands import edit_note
from ...commands.note_commands import AddNoteCommand, DeleteNoteCommand
from ...models.note_templates import load_templates, render_template
from ...models.notes import Note
from ...models.targets import target_label
from ..widgets import confirm
from .export_dialog import run_export
from .targets import TargetPickerDialog


def fill_template_menu(menu: QMenu, on_pick: Callable[[dict | None], None]) -> None:
    """A blank note plus one entry per template; on_pick(template or None)."""
    menu.addAction("Blank note", lambda: on_pick(None))
    menu.addSeparator()
    for template in load_templates():
        menu.addAction(template["name"], lambda t=template: on_pick(t))


class NoteActions:
    def __init__(self, scene, undo_stack, flush: Callable[[], None] = lambda: None):
        self.scene = scene
        self.undo_stack = undo_stack
        self.flush = flush  # stores text typed but not yet saved (set to the editor window's flush)

    @property
    def project(self):
        return self.scene.project

    def create(self, template: dict | None = None, target_id: str = "") -> Note:
        """A new note, blank or from a template. With a target it is attached to it (and named after it);
        without, it is detached and can be attached later."""
        self.flush()
        target = target_id if target_label(self.project, target_id) else ""
        title = target_label(self.project, target).split(" > ")[-1] or (template["name"] if template else "New note")
        note = Note(title=title, target_id=target, html=render_template(template) if template else "")
        self.undo_stack.push(AddNoteCommand(self.scene, note))
        return note

    def delete(self, parent, note: Note) -> bool:
        self.flush()
        if not confirm(parent, "Delete note", f'Delete the note "{note.title}" and everything in it?'):
            return False
        self.undo_stack.push(DeleteNoteCommand(self.scene, note.id))
        return True

    def attach(self, parent, note: Note, preselect_id: str = "") -> None:
        """Asks which layer or element the note belongs to (the dialog also offers Detach)."""
        current = note.target_id if self.project.is_attached(note) else ""
        dialog = TargetPickerDialog(self.project, current, preselect_id, parent)
        if dialog.exec():
            chosen = dialog.chosen_id()
            if chosen is not None:
                edit_note(self.undo_stack, self.scene, note, {"target_id": chosen}, "Attach note")

    def detach(self, note: Note) -> None:
        edit_note(self.undo_stack, self.scene, note, {"target_id": ""}, "Detach note")

    def export(self, parent, preselected: set[str]) -> None:
        self.flush()
        run_export(parent, self.project, preselected)
