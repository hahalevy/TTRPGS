"""The Notes pane: a preview card for every note (title, what it is attached to
or "Detached", and the first lines of text). Double-click a card to edit it."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QTextDocumentFragment
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDockWidget, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QMenu,
    QPushButton, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from ...models.targets import target_label
from ..widgets import choice_combo
from .actions import NoteActions, fill_template_menu
from .icons import DETACHED_COLOR, link_icon

ID_ROLE = Qt.ItemDataRole.UserRole
WHERE_ROLE = Qt.ItemDataRole.UserRole + 1
SNIPPET_ROLE = Qt.ItemDataRole.UserRole + 2
ATTACHED_ROLE = Qt.ItemDataRole.UserRole + 3
SNIPPET_CHARS = 160
CARD_HEIGHT = 84
FILTERS = [("All notes", "all"), ("Selected element / layer", "selected"), ("Detached", "detached")]


class NoteCardDelegate(QStyledItemDelegate):
    """Draws a note as a three-part card: icon + bold title, where it is attached, text preview."""

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), CARD_HEIGHT)

    def paint(self, painter, option, index) -> None:
        painter.save()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        if selected:
            painter.fillRect(option.rect, palette.highlight())
        painter.setPen(palette.color(palette.ColorRole.Mid))
        painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
        area = option.rect.adjusted(8, 6, -8, -6)
        attached = index.data(ATTACHED_ROLE)
        link_icon(attached).paint(painter, QRect(area.left(), area.top(), 16, 16))
        text_color = palette.highlightedText().color() if selected else palette.text().color()

        title_font = QFont(option.font)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(text_color)
        line = painter.fontMetrics().height()
        painter.drawText(QRect(area.left() + 22, area.top() - 1, area.width() - 22, line),
                         Qt.AlignmentFlag.AlignVCenter, painter.fontMetrics().elidedText(
                             index.data(Qt.ItemDataRole.DisplayRole), Qt.TextElideMode.ElideRight, area.width() - 22))
        painter.setFont(option.font)
        where = index.data(WHERE_ROLE)
        painter.setPen(text_color if selected else QColor("#666666") if attached else QColor(DETACHED_COLOR))
        painter.drawText(QRect(area.left(), area.top() + line + 2, area.width(), line), Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(where if attached else "⚠ Detached",
                                                          Qt.TextElideMode.ElideRight, area.width()))
        painter.setPen(text_color)
        top = area.top() + 2 * line + 6
        painter.drawText(QRect(area.left(), top, area.width(), area.bottom() - top),
                         Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap, index.data(SNIPPET_ROLE))
        painter.restore()


class NotesOverview(QDockWidget):
    openRequested = Signal(str)  # a note was chosen for editing
    noteCreated = Signal(str)  # a new note, to be opened with its title ready to type

    def __init__(self, scene, actions: NoteActions, parent=None):
        super().__init__("Notes", parent)
        self.scene = scene
        self.actions = actions
        self.selected_id = ""  # the layer / element selected in the app
        self._snippets: dict[str, tuple[str, str]] = {}  # note id -> (html, preview text)
        self._refreshing = False
        self._refresh_pending = False

        container = QWidget()
        layout = QVBoxLayout(container)
        buttons = QHBoxLayout()
        self.new_button = self._menu_button("New note", lambda t: self.create_note(t, attach=False))
        self.new_here_button = self._menu_button("Note for selection", lambda t: self.create_note(t, attach=True))
        for button in (self.new_button, self.new_here_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.filter = choice_combo(FILTERS)
        self.filter.currentIndexChanged.connect(lambda _: self.refresh())
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search titles and text")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh())
        layout.addWidget(self.filter)
        layout.addWidget(self.search)

        self.list = QListWidget()
        self.list.setItemDelegate(NoteCardDelegate(self.list))
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._context_menu)
        self.list.itemActivated.connect(lambda item: self.openRequested.emit(item.data(ID_ROLE)))
        layout.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_selected)
        self.export_button = QPushButton("Export...")
        self.export_button.clicked.connect(lambda: self.actions.export(self, set(self.selected_note_ids())))
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.export_button)
        layout.addLayout(buttons)
        self.setWidget(container)
        self.scene.notes_changed.connect(self.request_refresh)
        self.refresh()

    def _menu_button(self, text: str, on_pick) -> QPushButton:
        button = QPushButton(text)
        menu = QMenu(button)
        fill_template_menu(menu, on_pick)
        button.setMenu(menu)
        return button

    @property
    def project(self):
        return self.scene.project

    # --- listing ---
    def request_refresh(self) -> None:
        """Deferred: model changes often arrive while a widget of this pane is mid-event."""
        if not self._refresh_pending:
            self._refresh_pending = True
            QTimer.singleShot(0, self._do_deferred_refresh)

    def _do_deferred_refresh(self) -> None:
        self._refresh_pending = False
        self.refresh()

    def _snippet(self, note) -> str:
        cached = self._snippets.get(note.id)
        if cached is None or cached[0] != note.html:
            text = " ".join(QTextDocumentFragment.fromHtml(note.html).toPlainText().split())
            cached = self._snippets[note.id] = (note.html, text[:SNIPPET_CHARS])
        return cached[1]

    def _visible_notes(self) -> list:
        mode, text = self.filter.currentData(), self.search.text().strip().lower()
        if mode == "selected":
            notes = self.project.notes_for(self.selected_id)
        elif mode == "detached":
            notes = [n for n in self.project.notes if not self.project.is_attached(n)]
        else:
            notes = list(self.project.notes)
        return [n for n in notes if text in n.title.lower() or text in self._snippet(n).lower()] if text else notes

    def refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            keep = set(self.selected_note_ids())
            detached = sum(1 for n in self.project.notes if not self.project.is_attached(n))
            self.filter.setItemText(self.filter.findData("detached"), f"Detached ({detached})" if detached else "Detached")
            self.list.clear()
            notes = self._visible_notes()
            for note in notes:
                attached = self.project.is_attached(note)
                item = QListWidgetItem(note.title)
                item.setData(ID_ROLE, note.id)
                item.setData(ATTACHED_ROLE, attached)
                item.setData(WHERE_ROLE, target_label(self.project, note.target_id))
                item.setData(SNIPPET_ROLE, self._snippet(note))
                item.setToolTip(note.title)
                self.list.addItem(item)
                if note.id in keep:
                    item.setSelected(True)
            if not notes:
                hint = QListWidgetItem("No notes to show here yet.")
                hint.setFlags(Qt.ItemFlag.NoItemFlags)
                hint.setData(ATTACHED_ROLE, True)
                hint.setData(WHERE_ROLE, "Use New note, or Note for selection.")
                hint.setData(SNIPPET_ROLE, "")
                self.list.addItem(hint)
            self.new_here_button.setEnabled(bool(target_label(self.project, self.selected_id)))
            self.delete_button.setEnabled(bool(notes))
        finally:
            self._refreshing = False

    def show_target(self, target_id: str) -> None:
        """The app's selected layer/element changed: its notes are highlighted (or listed, with that filter)."""
        self.selected_id = target_id
        if self.filter.currentData() == "selected":
            self.refresh()
        self.new_here_button.setEnabled(bool(target_label(self.project, target_id)))
        mine = {n.id for n in self.project.notes_for(target_id)}
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setSelected(item.data(ID_ROLE) in mine)
            if item.isSelected():
                self.list.scrollToItem(item)

    def selected_note_ids(self) -> list[str]:
        return [i.data(ID_ROLE) for i in self.list.selectedItems() if i.data(ID_ROLE)]

    # --- actions ---
    def create_note(self, template: dict | None, attach: bool) -> None:
        note = self.actions.create(template, self.selected_id if attach else "")
        if note not in self._visible_notes():
            self.filter.setCurrentIndex(self.filter.findData("all"))
            self.search.clear()
        self.refresh()
        self.noteCreated.emit(note.id)

    def delete_selected(self) -> None:
        for note_id in self.selected_note_ids():
            note = self.project.find_note(note_id)
            if note is not None and not self.actions.delete(self, note):
                break  # "No" stops the rest too

    def _context_menu(self, pos) -> None:
        item = self.list.itemAt(pos)
        note = self.project.find_note(item.data(ID_ROLE)) if item and item.data(ID_ROLE) else None
        if note is None:
            return
        menu = QMenu(self)
        menu.addAction("Edit", lambda: self.openRequested.emit(note.id))
        attached = self.project.is_attached(note)
        menu.addAction("Change attachment..." if attached else "Attach...",
                       lambda: self.actions.attach(self, note, self.selected_id))
        if attached:
            menu.addAction("Detach", lambda: self.actions.detach(note))
        menu.addSeparator()
        menu.addAction("Export...", lambda: self.actions.export(self, set(self.selected_note_ids()) | {note.id}))
        menu.addAction("Delete...", lambda: self.actions.delete(self, note))
        menu.exec(self.list.viewport().mapToGlobal(pos))
