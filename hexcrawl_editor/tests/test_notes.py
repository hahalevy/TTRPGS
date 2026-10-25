"""The notes suite: model, commands, the Notes pane inside the real window,
the rich-text editor operations, templates and export."""
import base64

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QTextCursor
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from hexcrawl.commands.element_commands import AddElementCommand, DeleteElementCommand
from hexcrawl.commands.note_commands import AddNoteCommand
from hexcrawl.io.note_document import encode_image
from hexcrawl.io.note_export import export_notes
from hexcrawl.io.project_file import load_project, save_project
from hexcrawl.models.note_templates import load_templates, render_template
from hexcrawl.models.notes import Note
from hexcrawl.models.elements import LabelElement
from hexcrawl.models.project import Project
from hexcrawl.ui.notes.editor import NoteEditor
from hexcrawl.ui.notes.link_dialog import LinkDialog
from hexcrawl.ui.notes.preview import NotePreviewDialog
from hexcrawl.ui.notes.targets import TargetPickerDialog


@pytest.fixture
def editor():
    QApplication.instance() or QApplication([])
    return NoteEditor()


def block(editor, index):
    return editor.document().findBlockByNumber(index)


def put_cursor_in(editor, index):
    editor.setTextCursor(QTextCursor(block(editor, index)))


def add_label(win, text="Forest Road"):
    label = LabelElement(text=text, pos=(200, 200))
    win.undo_stack.push(AddElementCommand(win.scene, win.scene.project.layers[-1].id, label))
    return label


def select(win, element):
    win.scene.clearSelection()
    win.scene.item_for_element(element.id).setSelected(True)


def card_titles(win):
    """Titles of the preview cards in the overview pane."""
    items = [win.notes_overview.list.item(i) for i in range(win.notes_overview.list.count())]
    return [i.text() for i in items if i.data(Qt.ItemDataRole.UserRole)]


def card(win, title):
    return next(win.notes_overview.list.item(i) for i in range(win.notes_overview.list.count())
                if win.notes_overview.list.item(i).text() == title)


def new_note(win, template=None, attach=False):
    """What the New note / Note for selection buttons do."""
    win.notes_overview.create_note(template, attach)
    return win.scene.project.notes[-1]


# --- model ---
def test_notes_survive_save_and_load_and_old_projects_have_none(tmp_path):
    project = Project(notes=[Note(title="Lair", target_id="abc", html="<p>x</p>", images={"i.png": "AAAA"})])
    save_project(project, tmp_path / "p.hexproj")
    assert load_project(tmp_path / "p.hexproj").notes == project.notes
    assert Project.from_dict({"name": "old"}).notes == []


def test_note_is_dangling_when_its_element_or_nothing_is_the_target(win):
    label = add_label(win)
    note = Note(target_id=label.id)
    win.scene.project.notes.append(note)
    assert win.scene.project.is_attached(note)
    win.undo_stack.push(DeleteElementCommand(win.scene, label.id))
    assert not win.scene.project.is_attached(note) and note in win.scene.project.notes
    win.undo_stack.undo()
    assert win.scene.project.is_attached(note)  # undoing the delete re-attaches it
    assert not win.scene.project.is_attached(Note())  # never attached
    assert win.scene.project.is_attached(Note(target_id=win.scene.project.layers[-1].id))  # layers work too


# --- the overview pane and the editing window ---
def test_new_note_can_start_detached_and_cards_preview_it(win):
    note = new_note(win)
    assert note.target_id == "" and win.note_editor.isVisible() and win.note_editor._current_id == note.id
    win.note_editor.editor.insertPlainText("Three trolls guard the bridge over the river")
    win.note_editor.flush()
    QApplication.processEvents()
    item = card(win, "New note")
    assert "Three trolls guard" in item.data(Qt.ItemDataRole.UserRole + 2)
    assert item.data(Qt.ItemDataRole.UserRole + 3) is False  # drawn with the orange "Detached" mark


def test_selecting_an_element_shows_the_overview_and_highlights_its_notes(win):
    label = add_label(win)
    other = add_label(win, "Cave")
    win.scene.project.notes += [Note(title="Road", target_id=label.id), Note(title="Cave note", target_id=other.id)]
    win.notes_overview.hide()
    win.notes_overview.refresh()
    select(win, label)
    assert win.notes_overview.isVisible() and not win.note_editor.isVisible()  # the editor only opens on request
    assert [i.text() for i in win.notes_overview.list.selectedItems()] == ["Road"]
    select(win, other)
    assert [i.text() for i in win.notes_overview.list.selectedItems()] == ["Cave note"]
    win.notes_overview.filter.setCurrentIndex(win.notes_overview.filter.findData("selected"))
    assert card_titles(win) == ["Cave note"]


def test_note_for_selection_attaches_and_needs_a_selection(win):
    label = add_label(win)
    assert not win.notes_overview.new_here_button.isEnabled()
    select(win, label)
    assert win.notes_overview.new_here_button.isEnabled()
    note = new_note(win, attach=True)
    assert note.target_id == label.id and note.title == 'Label "Forest Road"'


def test_detaching_in_the_editor_and_closing_leaves_a_detached_card_to_attach_later(win):
    label = add_label(win)
    select(win, label)
    note = new_note(win, attach=True)
    editor = win.note_editor
    assert editor.detach_button.isVisibleTo(editor) and "Attached to" in editor.attach_button.text()
    editor.detach_button.click()
    QApplication.processEvents()
    assert note.target_id == "" and "Detached" in editor.attach_button.text()
    editor.hide()  # "exit the note"
    QApplication.processEvents()
    overview = win.notes_overview
    assert card(win, note.title).data(Qt.ItemDataRole.UserRole + 3) is False
    overview.filter.setCurrentIndex(overview.filter.findData("detached"))
    assert card_titles(win) == [note.title]
    assert "Detached (1)" in overview.filter.itemText(overview.filter.findData("detached"))
    other = add_label(win, "Another")
    dialog = TargetPickerDialog(win.scene.project, "", other.id)
    assert dialog.chosen_id() == other.id  # starts on whatever is selected on the map
    from hexcrawl.commands import edit_note
    edit_note(win.undo_stack, win.scene, note, {"target_id": dialog.chosen_id()})
    QApplication.processEvents()
    assert win.scene.project.is_attached(note) and card_titles(win) == []  # no longer detached
    win.undo_stack.undo()  # attaching is undoable
    assert not win.scene.project.is_attached(note)


def test_deleting_the_element_keeps_the_note_and_marks_it_detached(win):
    label = add_label(win)
    select(win, label)
    note = new_note(win, attach=True)
    win.undo_stack.push(DeleteElementCommand(win.scene, label.id))
    QApplication.processEvents()
    assert note in win.scene.project.notes
    assert card(win, note.title).data(Qt.ItemDataRole.UserRole + 3) is False
    assert "Detached" in win.note_editor.attach_button.text() and "deleted" in win.note_editor.attach_button.text()
    assert not win.note_editor.goto_button.isVisibleTo(win.note_editor)
    win.undo_stack.undo()  # undoing the delete re-attaches it
    QApplication.processEvents()
    assert win.scene.project.is_attached(note)
    assert win.scene.project.is_attached(Note(target_id=win.scene.project.layers[-1].id))  # layers work too
    assert not win.scene.project.is_attached(Note())


def test_target_picker_can_detach(win):
    dialog = TargetPickerDialog(win.scene.project, win.scene.project.layers[-1].id)
    dialog._detach()
    assert dialog.chosen_id() == ""


def test_delete_warns_first_and_is_undoable_and_closes_the_editor(win, monkeypatch):
    note = new_note(win)
    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(a[1:3]) or QMessageBox.StandardButton.No)
    win.note_editor.delete_current()
    assert asked and note.title in asked[0][1] and win.scene.project.notes == [note]
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    win.notes_overview.list.item(0).setSelected(True)
    win.notes_overview.delete_selected()
    QApplication.processEvents()
    assert win.scene.project.notes == [] and not win.note_editor.isVisible() and card_titles(win) == []
    win.undo_stack.undo()
    assert win.scene.project.notes == [note]


def test_typed_text_is_stored_marks_project_unsaved_and_persists(win, tmp_path):
    note = new_note(win)
    win._unsaved_outside_undo = False
    win.undo_stack.setClean()
    win.note_editor.editor.insertPlainText("Three trolls guard the bridge")
    win.note_editor.flush()
    assert "Three trolls" in note.html and win.has_unsaved_changes()
    win.note_editor.title_edit.setText("Troll Bridge")
    win.note_editor.title_edit.editingFinished.emit()
    assert note.title == "Troll Bridge"
    win.undo_stack.undo()
    assert note.title != "Troll Bridge"  # titles are undoable
    path = tmp_path / "n.hexproj"
    win._current_project_path = path
    win._save_project()
    assert "Three trolls" in load_project(path).notes[0].html


def test_viewing_a_note_does_not_count_as_a_change(win):
    win.scene.project.notes.append(Note(title="Seen", html="<p>hello</p>"))
    win.note_editor.open_note(win.scene.project.notes[0].id)
    win.undo_stack.setClean()
    win._unsaved_outside_undo = False
    win.note_editor.flush()
    assert not win.has_unsaved_changes()


def test_closing_the_editor_window_stores_what_was_typed(win):
    note = new_note(win)
    win.note_editor.editor.insertPlainText("quick idea")
    win.note_editor.hide()
    assert "quick idea" in note.html


def test_search_filters_cards_by_title_and_text_and_loading_a_project_clears_the_panes(win):
    win.scene.project.notes += [Note(title="A", html="<p>dragon hoard</p>"), Note(title="B", html="<p>market day</p>")]
    overview = win.notes_overview
    overview.refresh()
    assert card_titles(win) == ["A", "B"]
    overview.search.setText("dragon")
    assert card_titles(win) == ["A"]
    overview.search.clear()
    win.note_editor.open_note(win.scene.project.notes[0].id)
    win._load(Project())
    assert card_titles(win) == [] and not win.note_editor.isVisible() and win.note_editor.editor.toPlainText() == ""


def test_editor_starts_with_nothing_to_edit(win):
    assert not win.note_editor.isEnabled()


def test_template_note_is_filled_in_and_stays_editable(win):
    note = new_note(win, next(t for t in load_templates() if t["name"] == "Settlement"))
    assert note.title == "Settlement" and "Rumors" in note.html
    win.note_editor.editor.insertPlainText(" edited")
    win.note_editor.flush()
    assert "edited" in note.html


def test_layer_panel_counts_notes(win):
    from hexcrawl.ui.layer_panel import NOTES_COL
    label = add_label(win)
    win.scene.project.notes += [Note(target_id=label.id), Note(target_id=label.id)]
    win.layer_panel.refresh()
    layer_row = win.layer_panel.tree.topLevelItem(win.layer_panel.tree.topLevelItemCount() - 1)
    assert layer_row.child(0).text(NOTES_COL) == "2"


# --- links between notes ---
def test_note_link_pops_up_the_other_note_and_follows_further_links(win):
    target = Note(title="Goblin Cave", html="<p>Ten goblins.</p>")
    other = Note(title="Deep Pit", html="<p>Bottomless.</p>")
    source = Note(title="Rumors", html=f'<p><a href="note:{target.id}">the cave</a></p>')
    win.scene.project.notes += [source, target, other]
    win.note_editor.open_note(source.id)
    win.note_editor.editor.linkActivated.emit(f"note:{target.id}")
    popup = win.findChildren(NotePreviewDialog)[0]
    assert popup.title.text() == "Goblin Cave" and "Ten goblins" in popup.browser.toPlainText()
    popup.show_note(other.id)
    assert popup.title.text() == "Deep Pit" and popup.back_button.isEnabled()
    popup._back()
    assert popup.title.text() == "Goblin Cave"
    opened = []
    popup.openRequested.connect(opened.append)
    popup.open_button.click()
    assert opened == [target.id]
    win.note_editor.open_note(opened[0])
    assert win.note_editor._current_id == target.id


def test_link_dialog_builds_web_and_note_links():
    QApplication.instance() or QApplication([])
    dialog = LinkDialog("x", "", [("Cave", "id1")])
    dialog.url_edit.setText("example.com")
    assert dialog.link() == ("x", "https://example.com")
    dialog.note_radio.setChecked(True)
    assert dialog.link() == ("x", "note:id1")
    assert LinkDialog("x", "note:id1", [("Cave", "id1")]).note_radio.isChecked()


def test_following_a_missing_note_says_so(win, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: shown.append(a[1]))
    win.note_editor.preview_note("nope")
    assert shown == ["Missing note"]


# --- editor ---
def test_headings_and_character_formats(editor):
    editor.insertPlainText("Title")
    editor.set_heading(2)
    assert block(editor, 0).blockFormat().headingLevel() == 2 and editor.state()["heading"] == 2
    editor.selectAll()
    editor.toggle_char("italic")
    editor.toggle_char("underline")
    editor.set_color("#ff0000")
    html, _ = editor.dump()
    assert "<h2" in html and "italic" in html and "underline" in html and "#ff0000" in html
    editor.set_heading(0)
    assert block(editor, 0).blockFormat().headingLevel() == 0


def test_nested_numbered_lists_change_style_per_level_and_keep_counting(editor):
    editor.insertPlainText("one\nsub a\nsub b\nsub sub\ntwo\nthree")
    for index in range(6):
        put_cursor_in(editor, index)
        editor.toggle_list("numbered")
    for index, levels in ((1, 1), (2, 1), (3, 2)):
        put_cursor_in(editor, index)
        for _ in range(levels):
            editor.change_indent(1)
    styles = [(b.textList().format().indent(), b.textList().format().style()) for b in map(lambda i: block(editor, i), range(6))]
    from PySide6.QtGui import QTextListFormat as F
    assert styles == [(1, F.Style.ListDecimal), (2, F.Style.ListLowerAlpha), (2, F.Style.ListLowerAlpha),
                      (3, F.Style.ListLowerRoman), (1, F.Style.ListDecimal), (1, F.Style.ListDecimal)]
    numbers = [block(editor, i).textList().itemNumber(block(editor, i)) for i in range(6)]
    assert numbers == [0, 0, 1, 0, 1, 2]  # "two" is item 2 of the outer list, not a restart
    html, images = editor.dump()
    restored = NoteEditor()
    restored.load(html, images)
    assert [restored.document().findBlockByNumber(i).textList().itemNumber(restored.document().findBlockByNumber(i))
            for i in range(6)] == numbers
    put_cursor_in(editor, 3)
    editor.change_indent(-1)
    assert block(editor, 3).textList().format().style() == F.Style.ListLowerAlpha
    for index in (3,):
        put_cursor_in(editor, index)
        editor.toggle_list("numbered")  # toggling off removes it from the list
    assert block(editor, 3).textList() is None


def test_bullets_use_disc_circle_square(editor):
    from PySide6.QtGui import QTextListFormat as F
    editor.insertPlainText("a\nb\nc")
    for i in range(3):
        put_cursor_in(editor, i)
        editor.toggle_list("bullets")
    put_cursor_in(editor, 1)
    editor.change_indent(1)
    put_cursor_in(editor, 2)
    editor.change_indent(1)
    editor.change_indent(1)
    assert [block(editor, i).textList().format().style() for i in range(3)] == [
        F.Style.ListDisc, F.Style.ListCircle, F.Style.ListSquare]


def test_tab_nests_list_items_and_shift_tab_unnests(editor):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    editor.insertPlainText("a\nb")
    for i in range(2):
        put_cursor_in(editor, i)
        editor.toggle_list("numbered")
    put_cursor_in(editor, 1)
    editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier))
    assert block(editor, 1).textList().format().indent() == 2
    editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier))
    assert block(editor, 1).textList().format().indent() == 1


def test_hebrew_is_right_to_left_automatically_and_direction_switches_and_persists(editor):
    editor.insertPlainText("שלום עולם\nhello")
    assert block(editor, 0).textDirection() == Qt.LayoutDirection.RightToLeft
    assert block(editor, 1).textDirection() == Qt.LayoutDirection.LeftToRight
    put_cursor_in(editor, 1)
    editor.set_direction(True)
    assert editor.state()["rtl"]
    put_cursor_in(editor, 0)
    editor.set_direction(False)
    assert not editor.state()["rtl"]
    restored = NoteEditor()
    restored.load(*editor.dump())
    assert [restored.document().findBlockByNumber(i).textDirection() for i in range(2)] == [
        Qt.LayoutDirection.LeftToRight, Qt.LayoutDirection.RightToLeft]


def test_alignment_buttons_survive_a_reload(editor):
    editor.insertPlainText("abc\nשלום")
    A = Qt.AlignmentFlag
    for name, flag in (("right", A.AlignRight), ("center", A.AlignHCenter), ("justify", A.AlignJustify)):
        put_cursor_in(editor, 0)
        editor.set_alignment_name(name)
        restored = NoteEditor()
        restored.load(*editor.dump())
        assert block(restored, 0).blockFormat().alignment() & flag
    put_cursor_in(editor, 1)
    editor.set_direction(True)
    editor.set_alignment_name("left")  # not storable for Hebrew paragraphs: ignored, so nothing changes on reload
    restored = NoteEditor()
    restored.load(*editor.dump())
    assert block(restored, 1).blockFormat().alignment() == block(editor, 1).blockFormat().alignment()


def test_tables_can_be_built_and_edited_and_survive_a_reload(editor):
    editor.insert_table(2, 2)
    editor.table_op("row_below")
    editor.table_op("col_right")
    table = editor.textCursor().currentTable()
    assert (table.rows(), table.columns()) == (3, 3)
    restored = NoteEditor()
    restored.load(*editor.dump())
    assert "<table" in restored.dump()[0] and "<table" in editor.dump()[0]
    editor.table_op("delete_table")
    assert "<table" not in editor.dump()[0]


def test_links_can_be_made_edited_and_removed(editor):
    editor.insertPlainText("visit the cave today")
    cursor = editor.document().find("the cave")
    editor.setTextCursor(cursor)
    editor.set_link("", "note:abc")
    assert 'href="note:abc"' in editor.dump()[0]
    editor.setTextCursor(editor.document().find("the cave"))
    assert editor.current_link() == ("the cave", "note:abc")
    editor.set_link("the cave", "https://example.com")
    assert 'href="https://example.com"' in editor.dump()[0] and "note:abc" not in editor.dump()[0]
    editor.setTextCursor(editor.document().find("the cave"))
    editor.set_link("", "")
    assert "href" not in editor.dump()[0] and editor.toPlainText() == "visit the cave today"


def test_typing_after_a_link_is_not_part_of_the_link(editor):
    editor.set_link("cave", "note:abc")
    editor.insertPlainText(" and more")
    html, _ = editor.dump()
    assert "</a> and more" in html


def test_images_are_stored_with_the_note_resized_and_unused_ones_dropped(editor):
    image = QImage(2000, 1000, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    editor.insert_image(image)
    html, images = editor.dump()
    (name,) = images
    assert name in html and 'width="480"' in html and 'height="240"' in html
    assert QImage.fromData(base64.b64decode(images[name])).width() == 1600  # stored smaller
    restored = NoteEditor()
    restored.load(html, images)
    assert name in restored.dump()[1]
    editor.selectAll()
    editor.textCursor().removeSelectedText()
    assert editor.dump()[1] == {}  # an image deleted from the text is not kept


def test_pasting_an_image_inserts_it(editor):
    from PySide6.QtCore import QMimeData
    image = QImage(40, 40, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    mime = QMimeData()
    mime.setImageData(image)
    assert editor.canInsertFromMimeData(mime)
    editor.insertFromMimeData(mime)
    assert len(editor.dump()[1]) == 1


def test_text_with_pictures_copied_between_notes_keeps_them(editor):
    image = QImage(30, 30, QImage.Format.Format_RGB32)
    image.fill(QColor("green"))
    editor.insert_image(image)
    editor.selectAll()
    mime = editor.createMimeDataFromSelection()
    other = NoteEditor()
    other.insertFromMimeData(mime)
    assert len(other.dump()[1]) == 1


# --- templates ---
def test_templates_match_the_requested_sections():
    sections = {t["name"]: [s.get("heading") or ", ".join(s.get("fields", [])) for s in t["sections"]]
                for t in load_templates()}
    assert sections["Monster Lair"] == ["Creature, Number appearing, Treasure", "Description", "Map", "Room Key"]
    assert [s for s in sections["Settlement"]] == [
        "Category (village / town / city), Population, Military forces", "Notable NPCs", "Notable Locales", "Map",
        "Rumors", "Hooks & Quests"]
    assert sections["Wilderness Locale"] == ["Description", "Monsters", "Treasure", "Map", "Area Key"]


def test_template_room_key_is_a_ready_numbered_list_that_survives_saving(editor):
    lair = next(t for t in load_templates() if t["name"] == "Monster Lair")
    editor.insert_html(render_template(lair))
    restored = NoteEditor()
    restored.load(*editor.dump())
    lists = [b for i in range(restored.document().blockCount())
             if (b := restored.document().findBlockByNumber(i)).textList() is not None]
    assert len(lists) == 1 and lists[0].text() == "" and lists[0].textList().format().indent() == 1
    assert "Room Key" in restored.toPlainText() and "Creature:" in restored.toPlainText()


# --- export ---
def sample_project():
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor("purple"))
    pic = encode_image(image)
    cave = Note(title="Goblin Cave", html='<h2>Area Key</h2><ol><li>Entrance</li><li>Pit</li></ol>'
                '<p><img src="pic.png" width="20" height="20"></p>', images={"pic.png": pic})
    town = Note(title="Hebrew Town", html='<p dir="rtl">שלום עולם</p><p>See <a href="note:%s">the cave</a>.</p>' % cave.id)
    return Project(notes=[town, cave]), town, cave


def test_export_markdown_html_odt_pdf(tmp_path):
    project, town, cave = sample_project()
    paths = {}
    for fmt, extension in (("markdown", ".md"), ("html", ".html"), ("odt", ".odt"), ("pdf", ".pdf")):
        paths[fmt] = export_notes(project, [town, cave], fmt, tmp_path / f"out{extension}")[0]
        assert paths[fmt].stat().st_size > 100
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "# Hebrew Town" in markdown and "# Goblin Cave" in markdown and "שלום עולם" in markdown
    assert "Entrance" in markdown and "out_files/pic.png" in markdown and (tmp_path / "out_files" / "pic.png").exists()
    html = paths["html"].read_text(encoding="utf-8")
    assert "data:image/png;base64," in html and f'href="#note-{cave.id}"' in html and f'name="note-{cave.id}"' in html
    assert "note:" not in markdown
    assert paths["pdf"].read_bytes().startswith(b"%PDF")


def test_export_part_of_the_notes_and_one_file_per_note(tmp_path):
    project, town, cave = sample_project()
    (only,) = export_notes(project, [cave], "markdown", tmp_path / "one.md")
    text = only.read_text(encoding="utf-8")
    assert "Goblin Cave" in text and "Hebrew Town" not in text
    written = export_notes(project, [town, cave], "html", tmp_path / "folder", separate_files=True)
    assert sorted(p.name for p in written) == ["Goblin Cave.html", "Hebrew Town.html"]
    # a link to a note that is not part of the export becomes plain text
    assert "href" not in written[0].read_text(encoding="utf-8").split("</style>")[1]


def test_export_names_where_a_note_is_attached(win, tmp_path):
    label = add_label(win)
    win.scene.project.notes.append(Note(title="Road", target_id=label.id, html="<p>Muddy.</p>"))
    (path,) = export_notes(win.scene.project, win.scene.project.notes, "markdown", tmp_path / "r.md")
    assert 'Attached to:' in path.read_text(encoding="utf-8") and 'Forest Road' in path.read_text(encoding="utf-8")
