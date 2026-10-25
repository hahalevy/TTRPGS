"""The formatting buttons above the note editor. They only call NoteEditor
methods and mirror `NoteEditor.state()`; each button is one row of a table."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QImage, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QInputDialog, QMenu, QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from ...canvas.images import image_extensions
from ...models.note_templates import load_templates, render_template
from ..color_picker_button import ColorPickerButton
from ..widgets import choice_combo
from .editor import TABLE_OPS, NoteEditor
from .link_dialog import LinkDialog

TABLE_LABELS = {
    "row_above": "Insert row above", "row_below": "Insert row below", "col_left": "Insert column left",
    "col_right": "Insert column right", "delete_row": "Delete row", "delete_col": "Delete column",
    "merge": "Merge selected cells", "split": "Split cell", "delete_table": "Delete table",
}


class FormatToolbar(QWidget):
    def __init__(self, editor: NoteEditor, link_candidates: Callable[[], list[tuple[str, str]]], parent=None):
        """link_candidates() -> (title, id) of the notes a hyperlink can point to."""
        super().__init__(parent)
        self.editor = editor
        self._link_candidates = link_candidates
        self._checkable: dict[str, QAction] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        text_bar, paragraph_bar, insert_bar = (self._new_bar(layout) for _ in range(3))

        self.heading = choice_combo([("Normal text", 0)] + [(f"Heading {n}", n) for n in range(1, 7)])
        self.heading.setToolTip("Title / subsection level")
        self.heading.activated.connect(lambda _: self._run(lambda: editor.set_heading(self.heading.currentData())))
        text_bar.addWidget(self.heading)
        for key, text, tip, shortcut in (
            ("bold", "B", "Bold", "Ctrl+B"), ("italic", "I", "Italic", "Ctrl+I"),
            ("underline", "U", "Underline", "Ctrl+U"), ("strike", "S", "Strikethrough", None),
        ):
            action = self._add(text_bar, text, tip, lambda k=key: editor.toggle_char(k), shortcut, key)
            button = text_bar.widgetForAction(action)
            font = button.font()
            font.setBold(key == "bold")
            font.setItalic(key == "italic")
            font.setUnderline(key == "underline")
            font.setStrikeOut(key == "strike")
            button.setFont(font)
        for tip, background, initial in (("Text color", False, "#c00000"), ("Highlight color", True, "#ffff00")):
            swatch = ColorPickerButton(initial)
            swatch.setFixedWidth(26)
            swatch.setToolTip(tip)
            swatch.colorChanged.connect(lambda color, b=background: self._run(lambda: editor.set_color(color, b)))
            text_bar.addWidget(swatch)

        for key, text, tip, shortcut in (
            ("numbered", "1.", "Numbered list: 1, 2, 3 -> a, b, c -> i, ii, iii (Tab nests, Shift+Tab un-nests)",
             "Ctrl+Shift+N"),
            ("bullets", "•", "Bulleted list with sub-bullets (Tab nests, Shift+Tab un-nests)", "Ctrl+Shift+B"),
        ):
            self._add(paragraph_bar, text, tip, lambda k=key: editor.toggle_list(k), shortcut, key)
        self._add(paragraph_bar, "«", "Decrease indent / un-nest", lambda: editor.change_indent(-1))
        self._add(paragraph_bar, "»", "Increase indent / nest", lambda: editor.change_indent(1))
        paragraph_bar.addSeparator()
        for name, text, shortcut in (("left", "L", "Ctrl+L"), ("center", "C", "Ctrl+E"),
                                     ("right", "R", "Ctrl+R"), ("justify", "J", "Ctrl+J")):
            self._add(paragraph_bar, text, f"Align {name}", lambda n=name: editor.set_alignment_name(n), shortcut)
        paragraph_bar.addSeparator()
        self._add(paragraph_bar, "LTR", "Left-to-right paragraph (English)", lambda: editor.set_direction(False),
                  "Ctrl+Alt+L")
        self._add(paragraph_bar, "RTL", "Right-to-left paragraph (Hebrew)", lambda: editor.set_direction(True),
                  "Ctrl+Alt+R", "rtl")
        paragraph_bar.addSeparator()
        self._add(insert_bar, "Link", "Insert / edit hyperlink or link to another note", self.edit_link, "Ctrl+K")
        self._add(insert_bar, "Image", "Insert image (you can also paste or drop one)", self.insert_image_from_file)
        self._menu_button(insert_bar, "Table", "Tables", self._fill_table_menu)
        self._menu_button(insert_bar, "Template", "Insert a template at the cursor", self._fill_template_menu)
        self._add(insert_bar, "Clear", "Remove character formatting", editor.clear_formatting)

        editor.cursorPositionChanged.connect(self.sync)
        editor.currentCharFormatChanged.connect(lambda _: self.sync())
        self.sync()

    # --- building ---
    def _new_bar(self, layout) -> QToolBar:
        bar = QToolBar()
        bar.setMovable(False)
        layout.addWidget(bar)
        return bar

    def _add(self, bar: QToolBar, text: str, tip: str, handler, shortcut: str | None = None,
             check_key: str | None = None) -> QAction:
        action = QAction(text, self)
        action.setToolTip(f"{tip} ({shortcut})" if shortcut else tip)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        if check_key:
            action.setCheckable(True)
            self._checkable[check_key] = action
        action.triggered.connect(lambda _=False: self._run(handler))
        bar.addAction(action)
        return action

    def _menu_button(self, bar: QToolBar, text: str, tip: str, fill_menu) -> None:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tip)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        fill_menu(menu)
        button.setMenu(menu)
        bar.addWidget(button)

    def _fill_table_menu(self, menu: QMenu) -> None:
        menu.addAction("Insert table...", lambda: self._run(self.insert_table))
        menu.addSeparator()
        for op in TABLE_OPS:
            menu.addAction(TABLE_LABELS[op], lambda o=op: self._run(lambda: self.editor.table_op(o)))

    def _fill_template_menu(self, menu: QMenu) -> None:
        for template in load_templates():
            html = render_template(template)
            menu.addAction(template["name"], lambda h=html: self._run(lambda: self.editor.insert_html(h)))

    # --- behavior ---
    def _run(self, handler) -> None:
        """Runs an editor command and hands the keyboard back to the editor."""
        handler()
        self.editor.setFocus()
        self.sync()

    def sync(self) -> None:
        state = self.editor.state()
        for key, action in self._checkable.items():
            action.setChecked(state["list"] == key if key in ("numbered", "bullets") else bool(state.get(key)))
        self.heading.setCurrentIndex(self.heading.findData(state["heading"]))

    def edit_link(self) -> None:
        text, href = self.editor.current_link()
        dialog = LinkDialog(text, href, self._link_candidates(), self)
        if dialog.exec():
            new_text, new_href = dialog.link()
            self.editor.set_link(new_text, new_href)

    def insert_image_from_file(self) -> None:
        filters = "Images (" + " ".join(f"*{ext}" for ext in sorted(image_extensions())) + ")"
        path, _ = QFileDialog.getOpenFileName(self, "Insert image", "", filters)
        if path:
            self.editor.insert_image(QImage(path))

    def insert_table(self) -> None:
        rows, ok = QInputDialog.getInt(self, "Insert table", "Rows:", 3, 1, 100)
        if ok:
            columns, ok = QInputDialog.getInt(self, "Insert table", "Columns:", 2, 1, 20)
            if ok:
                self.editor.insert_table(rows, columns)
