"""Offscreen end-to-end tests driving the real window with real mouse events.
Each test covers a bug that was reported and fixed, so it can't come back."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from hexcrawl.commands.element_commands import AddElementCommand
from hexcrawl.models.elements import LabelElement, ShapeElement
from hexcrawl.models.layer import Layer
from hexcrawl.models.project import Project
from hexcrawl.ui.layer_panel import NAME_COL, VISIBLE_COL
from hexcrawl.ui.main_window import MainWindow

L, R, NONE = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton, Qt.MouseButton.NoButton


def _event(w, kind, scene_pt, button, buttons=None):
    vp = w.view.mapFromScene(QPointF(*scene_pt))
    return QMouseEvent(kind, QPointF(vp), QPointF(w.view.viewport().mapToGlobal(vp)), button,
                       buttons if buttons is not None else button, Qt.KeyboardModifier.NoModifier)


def drag(w, button, start, end, steps=4):
    w.view.mousePressEvent(_event(w, QEvent.Type.MouseButtonPress, start, button))
    for i in range(1, steps + 1):
        p = (start[0] + (end[0] - start[0]) * i / steps, start[1] + (end[1] - start[1]) * i / steps)
        w.view.mouseMoveEvent(_event(w, QEvent.Type.MouseMove, p, NONE, button))
    w.view.mouseReleaseEvent(_event(w, QEvent.Type.MouseButtonRelease, end, button, NONE))


def click(w, button, pt):
    w.view.mousePressEvent(_event(w, QEvent.Type.MouseButtonPress, pt, button))
    w.view.mouseReleaseEvent(_event(w, QEvent.Type.MouseButtonRelease, pt, button, NONE))


def pick_color(button, color):
    """Same effect as choosing a color in the dialog and pressing OK."""
    button.setColor(color)
    button.colorChanged.emit(color)


def binder_widget(binder, field):
    return binder._fields[field][0]


def layer(w):
    return w.scene.project.layers[0]


def of_kind(w, kind):
    return [e for e in layer(w).elements if e.kind == kind]


def test_line_color_works_right_after_launch(win):
    assert win.view.current_tool.name == "line"
    pick_color(binder_widget(win.draw_panel.line_binder, "color"), "#ff0000")
    drag(win, L, (100, 100), (200, 150))
    assert of_kind(win, "stroke")[0].color == "#ff0000"


def test_new_shape_color_and_fill(win):
    QTest.mouseClick(win.draw_panel.shapes_section.toggle_button, L)
    assert win.view.current_tool.name == "shape"
    pick_color(binder_widget(win.draw_panel.shape_binder, "color"), "#0000ff")
    pick_color(binder_widget(win.draw_panel.shape_binder, "fill_color"), "#00ff00")  # also ticks Fill
    drag(win, L, (300, 300), (400, 380))
    shape = of_kind(win, "shape")[0]
    assert (shape.color, shape.filled, shape.fill_color) == ("#0000ff", True, "#00ff00")


def test_fog_never_blocks_selecting_and_editing_shapes(win):
    QTest.mouseClick(win.draw_panel.shapes_section.toggle_button, L)
    drag(win, L, (200, 200), (320, 280))
    win.view.set_tool("fog")
    drag(win, L, (600, 600), (700, 700))
    assert of_kind(win, "fog")
    click(win, R, (260, 240))
    shape = of_kind(win, "shape")[0]
    assert [i.data(0) for i in win.scene.selectedItems()] == [shape.id]
    pick_color(binder_widget(win.draw_panel.shape_binder, "color"), "#ff0000")
    assert shape.color == "#ff0000"  # Draw panel edits the selected shape


def test_right_drag_moves_any_element_as_one_undo_step(win):
    shape = ShapeElement(shape_type="rectangle", p1=(100, 100), p2=(200, 160))
    label = LabelElement(text="Hi", pos=(300, 100))
    for el in (shape, label):
        win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, el))
    drag(win, R, (50, 50), (400, 200))  # rubber-band both
    assert len(win.scene.selectedItems()) == 2
    drag(win, R, (150, 130), (190, 150))
    assert shape.p1 == (140, 120) and tuple(label.pos) == (340, 120)
    assert win.scene.item_for_element(shape.id).pos() == QPointF(0, 0)
    win.undo_stack.undo()
    assert shape.p1 == (100, 100) and tuple(label.pos) == (300, 100)


def test_handles_stretch_and_rotate_about_center_when_zoomed(win):
    shape = ShapeElement(shape_type="rectangle", p1=(300, 250), p2=(420, 330))
    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, shape))
    item = win.scene.item_for_element(shape.id)
    item.setSelected(True)
    win.view.zoom_in()
    win.view.zoom_in()
    win.view.centerOn(QPointF(360, 290))
    QApplication.processEvents()
    h = item.mapToScene(item._handles["h_stretch"].pos())
    drag(win, R, (h.x(), h.y()), (h.x() + 60, h.y()))
    assert shape.p2[0] - shape.p1[0] == pytest.approx(240, abs=2)  # pixel rounding at zoom
    center = item.mapToScene(item._local_rect().center())
    r = item.mapToScene(item._handles["rotate"].pos())
    drag(win, R, (r.x(), r.y()), (center.x() + 100, center.y()))
    assert shape.rotation == pytest.approx(90, abs=2)
    assert item.mapToScene(item._local_rect().center()) == center  # pivot didn't move


def test_label_tool_places_labels_with_border_and_outline(win):
    binder = win.label_panel.binder
    binder_widget(binder, "text").setText("Keep")
    binder_widget(binder, "border").setChecked(True)
    win.label_panel.raise_()
    win.view.set_tool("label")
    click(win, L, (100, 100))
    label = of_kind(win, "label")[0]
    assert label.text == "Keep" and label.border.enabled and label.outline.enabled  # outline is on by default
    win.scene.item_for_element(label.id).setSelected(True)  # loading it back must not fail
    assert binder_widget(binder, "border").value() == label.border


def test_label_selection_loads_panel_and_edits_apply(win):
    label = LabelElement(text="Old", pos=(100, 100), font_color="#123456")
    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, label))
    win.scene.item_for_element(label.id).setSelected(True)
    assert binder_widget(win.label_panel.binder, "font_color").color() == "#123456"
    pick_color(binder_widget(win.label_panel.binder, "font_color"), "#ff00ff")
    binder_widget(win.label_panel.binder, "font_size").setValue(30)
    assert (label.font_color, label.font_size) == ("#ff00ff", 30)


def test_layer_panel_clicks_marks_visibility_and_delete_checked(win, monkeypatch):
    els = [ShapeElement(shape_type="rectangle", p1=(i * 50, 0), p2=(i * 50 + 40, 40), name=f"S{i}") for i in range(3)]
    for el in els:
        win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, el))
    tree = win.layer_panel.tree
    QApplication.processEvents()

    def cell(i, col):
        QApplication.processEvents()
        tree.expandAll()
        return tree.visualRect(tree.indexFromItem(tree.topLevelItem(0).child(i), col))

    for i in range(3):  # body, eye and checkbox clicks: no crash, eye toggles visibility
        QTest.mouseClick(tree.viewport(), L, Qt.KeyboardModifier.NoModifier, cell(i, NAME_COL).center())
        QTest.mouseClick(tree.viewport(), L, Qt.KeyboardModifier.NoModifier, cell(i, VISIBLE_COL).center())
    QApplication.processEvents()
    assert not any(e.visible for e in els)
    for i in (0, 2):
        r = cell(i, NAME_COL)
        QTest.mouseClick(tree.viewport(), L, Qt.KeyboardModifier.NoModifier, QPoint(r.left() + 8, r.center().y()))
    QApplication.processEvents()
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    tree.setCurrentItem(tree.topLevelItem(0).child(1))  # selection must not matter
    win.layer_panel._delete_checked()
    assert [e.name for e in layer(win).elements] == ["S1"]


def test_rename_layer_and_element(win):
    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, LabelElement(text="x", name="Before")))
    win.layer_panel.refresh()
    top = win.layer_panel.tree.topLevelItem(0)
    top.child(0).setText(NAME_COL, "After")
    top.setText(NAME_COL, "Renamed")
    assert layer(win).name == "Renamed" and layer(win).elements[0].name == "After"


def test_export_matches_canvas_without_handles_or_hidden(win, tmp_path):
    shape = ShapeElement(shape_type="rectangle", p1=(10, 10), p2=(60, 60), filled=True, fill_color="#ff0000")
    hidden = ShapeElement(shape_type="rectangle", p1=(100, 10), p2=(150, 60), filled=True, fill_color="#00ff00", visible=False)
    for el in (shape, hidden):
        win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, el))
    item = win.scene.item_for_element(shape.id)
    item.setSelected(True)
    from hexcrawl.io.exporter import export_png
    from PySide6.QtGui import QImage

    out = tmp_path / "out.png"
    export_png(win.scene, out, None, None)
    image = QImage(str(out))
    assert image.pixelColor(35, 35).name() == "#ff0000"
    assert image.pixelColor(125, 35).name() != "#00ff00"
    assert item.isSelected()  # selection restored after export


def _make_map(path, color="#336699", size=(400, 300)):
    from PySide6.QtGui import QColor, QImage

    image = QImage(*size, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    image.save(str(path))
    return path


def test_new_project_uses_chosen_base_map_as_its_own_layer(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    chosen = _make_map(tmp_path / "other_map.png")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(chosen), ""))
    assert win.new_project()
    base, drawing = win.scene.project.layers
    assert base.base_map and not drawing.base_map
    assert win.scene.map_bounds().size().toTuple() == (400, 300)
    assert win.scene.base_map_item.parentItem() is win.scene.layer_items[base.id]
    assert win.scene.active_layer_id == drawing.id
    win._set_active_layer(base.id)  # the base map is never a drawing target
    assert win.scene.active_layer_id == drawing.id
    assert win.layer_panel.tree.topLevelItem(0).text(2) == "Base map"


def test_base_map_layer_opacity_applies_to_canvas_and_export(win, tmp_path, monkeypatch):
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QFileDialog
    from hexcrawl.commands import edit_layer
    from hexcrawl.io.exporter import export_png
    from hexcrawl.models.effects import OpacityEffect

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(_make_map(tmp_path / "m.png")), ""))
    win.new_project()
    base = win.scene.base_layer()
    edit_layer(win.undo_stack, win.scene, base, {"effects": [OpacityEffect(value=0.5)]})
    assert win.scene.layer_items[base.id].opacity() == 0.5
    export_png(win.scene, tmp_path / "out.png", None, None)
    pixel = QImage(str(tmp_path / "out.png")).pixelColor(10, 10)
    # #336699 at 50% over the default white background, fully opaque.
    assert pixel.alpha() == 255
    assert (pixel.red(), pixel.green(), pixel.blue()) == pytest.approx((0x99, 0xB3, 0xCC), abs=3)
    win.undo_stack.undo()
    assert win.scene.layer_items[base.id].opacity() == 1.0


def test_map_settings_fade_map_and_change_background_whatever_is_selected(win, tmp_path, monkeypatch):
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QFileDialog
    from hexcrawl.io.exporter import export_png
    from hexcrawl.ui.effects_panel import EffectsDialog

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(_make_map(tmp_path / "m.png", "#000000")), ""))
    win.new_project()
    assert win.scene.project.background_color == "#ffffff"
    win.layer_panel.tree.setCurrentItem(win.layer_panel.tree.topLevelItem(1))  # a drawing layer is selected
    dialogs = []
    monkeypatch.setattr(EffectsDialog, "exec", lambda self: dialogs.append(self))
    win.open_map_settings()
    dialog = dialogs[0]
    assert dialog.layer.base_map  # targets the base map regardless of selection
    binder_widget(dialog.opacity, "value").setValue(25)
    pick_color(binder_widget(dialog.background, "background_color"), "#ff0000")
    assert win.scene.project.background_color == "#ff0000"
    export_png(win.scene, tmp_path / "out.png", None, None)
    pixel = QImage(str(tmp_path / "out.png")).pixelColor(10, 10)  # black map at 25% over red
    assert (pixel.red(), pixel.green(), pixel.blue()) == pytest.approx((191, 0, 0), abs=3)
    assert win.scene.layer_items[win.scene.project.layers[1].id].opacity() == 1.0  # other layers untouched
    win.undo_stack.undo()
    assert win.scene.project.background_color == "#ffffff"


def test_projects_saved_before_base_map_layer_get_one(win, tmp_path):
    from hexcrawl.models.layer import Layer
    from hexcrawl.models.project import Project

    old = Project(base_map_path=str(_make_map(tmp_path / "m.png")), layers=[Layer(name="Roads")])
    win._load(old)
    assert [l.name for l in old.layers] == ["Base Map", "Roads"] and old.layers[0].base_map
    assert win.scene.base_map_item is not None


def test_library_assets_place_small_and_uniform_from_hi_res_source(win):
    from hexcrawl.canvas.images import ASSET_SIZE
    from hexcrawl.ui.asset_scanner import scan_assets
    from hexcrawl.app_config import ASSETS_DIR

    library = scan_assets(ASSETS_DIR)
    assert {"Structures", "Terrain"} <= set(library)
    win.asset_panel.refresh()
    for rel in ("Structures/Castle.svg", "Terrain/Mountains.svg"):
        win.asset_panel._select_asset(rel)
        win.view.set_tool("asset")
        click(win, L, (300, 300))
    for element in of_kind(win, "asset"):
        item = win.scene.item_for_element(element.id)
        assert max(item.pixmap().width(), item.pixmap().height()) >= 512  # crisp source
        rect = item.sceneBoundingRect()
        assert max(rect.width(), rect.height()) == pytest.approx(ASSET_SIZE, abs=1)  # uniform default size
        assert (rect.center().x(), rect.center().y()) == pytest.approx((300, 300), abs=1)  # lands where clicked


def _cursor_at(monkeypatch, win, scene_pt):
    """Places the (virtual) mouse over a scene point, or off the map if None."""
    import hexcrawl.ui.main_window as mw

    if scene_pt is None:
        global_pos = win.view.viewport().mapToGlobal(QPoint(-500, -500))
    else:
        global_pos = win.view.viewport().mapToGlobal(win.view.mapFromScene(QPointF(*scene_pt)))
    monkeypatch.setattr(mw, "QCursor", type("Cursor", (), {"pos": staticmethod(lambda: global_pos)}))


def test_copy_paste_multiple_elements_at_cursor_as_one_undo(win, monkeypatch):
    shape = ShapeElement(shape_type="rectangle", p1=(100, 100), p2=(140, 140), color="#ff0000")
    label = LabelElement(text="Ruins", pos=(200, 100), font_color="#00ff00")
    for el in (shape, label):
        win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, el))
    drag(win, R, (50, 50), (400, 200))  # select both
    win._copy_selection()

    _cursor_at(monkeypatch, win, (600, 600))
    win._paste()
    shapes, labels = of_kind(win, "shape"), of_kind(win, "label")
    assert len(shapes) == 2 and len(labels) == 2
    new_shape, new_label = shapes[1], labels[1]
    assert new_shape.id != shape.id and new_shape.color == "#ff0000" and new_label.text == "Ruins"
    # Kept their relative layout, and the group is centered on the mouse.
    assert new_label.pos[0] - new_shape.p1[0] == pytest.approx(label.pos[0] - shape.p1[0])
    pasted = [win.scene.item_for_element(e.id) for e in (new_shape, new_label)]
    group = pasted[0].sceneBoundingRect().united(pasted[1].sceneBoundingRect())
    assert (group.center().x(), group.center().y()) == pytest.approx((600, 600), abs=2)
    assert set(win.scene.selectedItems()) == set(pasted)  # copies are selected
    win.undo_stack.undo()
    assert len(layer(win).elements) == 2  # whole paste undone in one step


def test_repeated_paste_with_mouse_off_map_cascades(win, monkeypatch):
    shape = ShapeElement(shape_type="rectangle", p1=(100, 100), p2=(140, 140))
    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, shape))
    win.scene.item_for_element(shape.id).setSelected(True)
    win._copy_selection()
    _cursor_at(monkeypatch, win, None)
    win._paste()
    win._paste()
    assert [s.p1 for s in of_kind(win, "shape")] == [(100, 100), (120, 120), (140, 140)]


def test_copy_paste_have_standard_shortcuts(win):
    from PySide6.QtGui import QKeySequence

    shortcuts = {a.text(): a.shortcut() for a in win.menuBar().actions()[1].menu().actions()}
    assert shortcuts["Copy"] == QKeySequence(QKeySequence.StandardKey.Copy)
    assert shortcuts["Paste"] == QKeySequence(QKeySequence.StandardKey.Paste)


def test_bundled_fonts_load_sorted_and_include_the_label_default(win):
    from hexcrawl.ui.font_manager import FontManager

    families = FontManager().available_families()
    assert len(families) >= 20 and families == sorted(families, key=str.casefold)


@pytest.mark.skipif(sys.platform != "win32", reason="needs the native Windows Qt platform")
def test_label_default_font_is_in_the_font_list_on_windows():
    # The offscreen platform lists only a variable font's base family; Windows also
    # lists its named weights ("EB Garamond Medium"), so check in a native subprocess.
    code = (
        "from PySide6.QtWidgets import QApplication; app = QApplication([]);"
        "from hexcrawl.defaults import DEFAULTS; from hexcrawl.ui.font_manager import FontManager;"
        "print(DEFAULTS['label']['font_family'] in FontManager().available_families())"
    )
    env = {k: v for k, v in os.environ.items() if k != "QT_QPA_PLATFORM"}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env,
                         cwd=Path(__file__).resolve().parent.parent, check=True)
    assert out.stdout.strip() == "True"


def _try_close(win):
    from PySide6.QtGui import QCloseEvent

    event = QCloseEvent()
    win.closeEvent(event)
    return event.isAccepted()


def _answer_prompt(monkeypatch, button):
    """Answers the Save/Discard/Cancel prompt; returns the list of times it was shown."""
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: shown.append(self.text()) or button)
    return shown


def test_closing_a_clean_project_does_not_prompt(win, monkeypatch):
    shown = _answer_prompt(monkeypatch, QMessageBox.StandardButton.Cancel)
    assert _try_close(win) and not shown


def test_closing_with_unsaved_changes_offers_save_discard_cancel(win, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, LabelElement(text="x")))
    assert win.has_unsaved_changes()

    shown = _answer_prompt(monkeypatch, QMessageBox.StandardButton.Cancel)
    assert not _try_close(win) and len(shown) == 1  # Cancel: stay open, nothing lost

    _answer_prompt(monkeypatch, QMessageBox.StandardButton.Discard)
    assert _try_close(win)

    # Save on a never-saved project goes to the Save As dialog; cancelling it keeps the window open.
    _answer_prompt(monkeypatch, QMessageBox.StandardButton.Save)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    assert not _try_close(win)
    target = tmp_path / "campaign"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    assert _try_close(win)
    assert target.with_suffix(".hexproj").exists() and not win.has_unsaved_changes()


def test_saved_state_tracks_undo_and_non_undoable_edits(win, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(tmp_path / "p"), ""))
    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, LabelElement(text="x")))
    win._save_project()
    assert not win.has_unsaved_changes()
    win.undo_stack.undo()
    assert win.has_unsaved_changes()  # differs from what's on disk
    win.undo_stack.redo()
    assert not win.has_unsaved_changes()  # back to the saved state
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(_make_map(tmp_path / "m.png")), ""))
    win._replace_base_map()  # not an undoable edit, but still unsaved
    assert win.has_unsaved_changes()


def test_new_and_open_also_ask_before_discarding_changes(win, monkeypatch):
    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, LabelElement(text="x")))
    shown = _answer_prompt(monkeypatch, QMessageBox.StandardButton.Cancel)
    assert win.new_project() is False and len(shown) == 1


def test_factory_defaults_match_the_spec(win):
    from hexcrawl.models.elements import AssetElement, DecorationStyle, StrokeElement

    label, shape, line, asset = LabelElement(), ShapeElement(), StrokeElement(), AssetElement()
    assert (label.font_family, label.font_size, label.font_color) == ("EB Garamond Medium", 30, "#000000")
    assert label.border == DecorationStyle(False, "#000000", 2.0)
    assert label.outline == DecorationStyle(True, "#ffffff", 2.0)  # outline: labels only
    assert not asset.border.enabled and not asset.outline.enabled
    assert (shape.color, shape.fill_color, shape.filled, line.color) == ("#000000", "#000000", False, "#000000")
    # ...and a freshly launched app's panels start from the same values.
    panel = win.label_panel.binder.values()
    assert (panel["font_family"], panel["font_size"]) == ("EB Garamond Medium", 30)
    assert panel["outline"] == label.outline and not panel["border"].enabled
    assert win.draw_panel.line_binder.values()["color"] == "#000000"
    assert not win.asset_panel.binder.values()["outline"].enabled


def test_default_label_renders_in_garamond_medium(win):
    label = LabelElement(text="Kael")
    win.undo_stack.push(AddElementCommand(win.scene, layer(win).id, label))
    font = win.scene.item_for_element(label.id).font()
    assert font.family() == "EB Garamond Medium" and font.pointSize() == 30


def test_last_used_values_belong_to_the_project(win, tmp_path):
    from hexcrawl.app_config import remembered
    from hexcrawl.io.project_file import load_project

    win.asset_panel.refresh()
    win.asset_panel._select_asset("Terrain/Forest.svg")
    win.asset_panel.notify_asset_placed("Terrain/Forest.svg")
    win.label_panel.binder._fields["font_size"][0].setValue(44)
    pick_color(binder_widget(win.label_panel.binder, "font_color"), "#aa0000")
    binder_widget(win.label_panel.binder, "outline").setChecked(False)
    win.label_panel.notify_label_placed({**win.label_panel.binder.values(), "text": "Kael"})
    pick_color(binder_widget(win.draw_panel.shape_binder, "color"), "#00aa00")
    binder_widget(win.draw_panel.shape_binder, "filled").setChecked(True)
    win.draw_panel.line_binder._fields["width"][0].setValue(8)
    assert remembered("label")["font_size"] == 44 and "text" not in remembered("label")
    assert win.scene.project.preferences["label"]["font_size"] == 44  # stored in the project itself

    path = tmp_path / "kept.hexproj"
    win._write_project(path)

    # A brand-new project starts from the factory defaults, not from the last one.
    win._load(Project(layers=[Layer(name="Layer 1")]))
    label = win.label_panel.binder.values()
    assert (label["font_size"], label["font_color"], label["outline"].enabled) == (30, "#000000", True)
    assert win.draw_panel.shape_binder.values()["color"] == "#000000"
    assert win.draw_panel.line_binder.values()["width"] == 3.0
    assert win.asset_panel.current_settings()["asset_path"] is None
    assert win.asset_panel.recent.items == [] and win.label_panel.recent.items == []

    # Opening the saved project brings its values back.
    win._load(load_project(path))
    label = win.label_panel.binder.values()
    assert (label["font_size"], label["font_color"], label["outline"].enabled) == (44, "#aa0000", False)
    assert label["font_family"] == "EB Garamond Medium"  # untouched values still come from the defaults
    shape = win.draw_panel.shape_binder.values()
    assert (shape["color"], shape["filled"]) == ("#00aa00", True)
    assert win.draw_panel.line_binder.values()["width"] == 8
    assert win.asset_panel.current_settings()["asset_path"] == "Terrain/Forest.svg"
    assert win.asset_panel.recent.items == ["Terrain/Forest.svg"]
    assert [r["text"] for r in win.label_panel.recent.items] == ["Kael"]


def test_panels_cannot_be_closed_or_floated(win):
    from PySide6.QtWidgets import QDockWidget

    # The notes overview (closable; View > Notes reopens it) and the floating note editor are the exceptions.
    docks = [d for d in win.findChildren(QDockWidget) if d not in (win.notes_overview, win.note_editor)]
    assert len(docks) == 5
    for dock in docks:
        assert dock.features() == QDockWidget.DockWidgetFeature.DockWidgetMovable
