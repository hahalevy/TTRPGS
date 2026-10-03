from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QGuiApplication, QKeySequence, QUndoStack
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox

from ..app_config import ASSETS_DIR, MAPS_DIR
from ..canvas.images import image_extensions
from ..canvas.scene import HexcrawlScene
from ..canvas.tools import AssetTool, FogTool, LabelTool, LineTool, ShapeTool
from ..canvas.view import HexcrawlView
from ..commands import delete_items, edit_element, push_as_one
from ..commands.element_commands import AddElementCommand
from ..commands.fields import SetElementFieldsCommand
from ..io.exporter import export_png
from ..io.project_file import load_project, save_project
from ..models.elements import Element
from ..models.layer import Layer
from ..models.project import Project
from .asset_panel import AssetPanel
from .draw_panel import DrawPanel
from .effects_panel import EffectsDialog
from .export_dialog import ExportDialog
from .fog_panel import FogPanel
from .font_manager import FontManager
from .label_panel import LabelPanel
from .layer_panel import LayerPanel
from .toolbar import MainToolBar

CLIPBOARD_MIME = "application/x-hexcrawl-elements"
PASTE_OFFSET = 20  # scene units between repeated pastes when the mouse is off the map

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hexcrawl Editor")
        self.resize(1400, 900)

        self.undo_stack = QUndoStack(self)
        self.scene = HexcrawlScene(ASSETS_DIR)
        self.view = HexcrawlView(self.scene)
        self.view.undo_stack = self.undo_stack
        self.setCentralWidget(self.view)
        self._current_project_path: Path | None = None
        self._selected_element_id: str | None = None

        self._setup_toolbar()
        self._setup_docks()
        self._setup_tools()
        self._setup_menus()

        self.scene.rebuild_from_project(self.scene.project)  # blank until a base map is chosen
        self.layer_panel.refresh()

        # Every item edit / delete / move from the canvas funnels through one place.
        self.scene.selectionChanged.connect(self._on_selection_changed)
        self.scene.on_element_edited = lambda eid, old, new, label: self.undo_stack.push(
            SetElementFieldsCommand(self.scene, eid, old, new, label)
        )
        self.scene.on_delete_requested = lambda eid: delete_items(self.undo_stack, self.scene, [eid])
        self.view.on_delete_key = self._delete_selected_elements
        self.view.on_items_moved = self._move_elements
        self.undo_stack.indexChanged.connect(self._on_undo_stack_changed)

        # Tabifying docks fires spurious visibilityChanged events during the
        # first layout; tool activation from tabs starts once that settles.
        self._startup_complete = False
        QTimer.singleShot(0, self._mark_startup_complete)

    # --- setup ---
    def _setup_toolbar(self) -> None:
        self.toolbar = MainToolBar()
        self.addToolBar(self.toolbar)
        self.toolbar.zoom_in_action.triggered.connect(self.view.zoom_in)
        self.toolbar.zoom_out_action.triggered.connect(self.view.zoom_out)
        self.toolbar.zoom_reset_action.triggered.connect(self.view.zoom_reset)

    def _setup_docks(self) -> None:
        self.layer_panel = LayerPanel(self.scene, self.undo_stack)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_panel)
        self.layer_panel.activeLayerChanged.connect(self._set_active_layer)
        self.layer_panel.effectsRequested.connect(
            lambda layer_id: EffectsDialog(self.scene, self.undo_stack, layer_id, self).exec()
        )
        self.layer_panel.elementSelected.connect(self._select_element_on_canvas)

        self.draw_panel = DrawPanel()
        self.fog_panel = FogPanel()
        self.asset_panel = AssetPanel()
        self.label_panel = LabelPanel(FontManager())
        palette = [self.draw_panel, self.fog_panel, self.asset_panel, self.label_panel]
        for dock in palette:
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
        for first, second in zip(palette, palette[1:]):
            self.tabifyDockWidget(first, second)

        # Element kind -> (panel to show, binder that edits it, Draw section).
        # The same binder supplies settings for new elements of that kind.
        self._editors = {
            "stroke": (self.draw_panel, self.draw_panel.line_binder, "line"),
            "shape": (self.draw_panel, self.draw_panel.shape_binder, "shape"),
            "label": (self.label_panel, self.label_panel.binder, None),
            "asset": (self.asset_panel, self.asset_panel.binder, None),
        }
        for kind, (_dock, binder, _section) in self._editors.items():
            binder.edited.connect(lambda k=kind, b=binder: self._apply_panel_to_selection(k, b))

        # Picking a tab (or a Draw section) IS picking the tool.
        self._tool_for_dock = {
            self.draw_panel: self.draw_panel.active_section,
            self.fog_panel: lambda: "fog",
            self.asset_panel: lambda: "asset",
            self.label_panel: lambda: "label",
        }
        for dock, tool_name in self._tool_for_dock.items():
            dock.visibilityChanged.connect(lambda visible, t=tool_name: visible and self._activate_tool(t()))
        self.draw_panel.sectionActivated.connect(self._activate_tool)

    def _setup_tools(self) -> None:
        layer = lambda: self.scene.active_layer_id  # noqa: E731
        for tool in (
            LineTool(self.view, layer, self.draw_panel.line_binder.values),
            ShapeTool(self.view, layer, self.draw_panel.shape_binder.values),
            FogTool(self.view, layer, self.fog_panel.binder.values),
            LabelTool(self.view, layer, self.label_panel.current_settings, self.label_panel.notify_label_placed),
            AssetTool(self.view, layer, self.asset_panel.current_settings,
                      lambda s: self.asset_panel.notify_asset_placed(s["asset_path"])),
        ):
            self.view.register_tool(tool.name, tool)

    def _setup_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        for title, handler in (
            ("New Project...", self.new_project), ("Open Project...", self._open_project),
            ("Save", self._save_project), ("Save As...", self._save_project_as),
            ("Export PNG...", self._export_png),
        ):
            action = QAction(title, self)
            action.triggered.connect(handler)
            file_menu.addAction(action)

        edit_menu = self.menuBar().addMenu("&Edit")
        copy_action, paste_action = QAction("Copy", self), QAction("Paste", self)
        copy_action.triggered.connect(self._copy_selection)
        paste_action.triggered.connect(self._paste)
        # Text fields with focus (e.g. label text) keep their own Ctrl+C/V.
        for action, shortcut in ((self.undo_stack.createUndoAction(self, "Undo"), QKeySequence.StandardKey.Undo),
                                 (self.undo_stack.createRedoAction(self, "Redo"), QKeySequence.StandardKey.Redo),
                                 (copy_action, QKeySequence.StandardKey.Copy),
                                 (paste_action, QKeySequence.StandardKey.Paste)):
            action.setShortcut(shortcut)
            edit_menu.addAction(action)

        view_menu = self.menuBar().addMenu("&View")
        for action in (self.toolbar.zoom_in_action, self.toolbar.zoom_out_action, self.toolbar.zoom_reset_action):
            view_menu.addAction(action)

        map_menu = self.menuBar().addMenu("&Map")
        for title, handler in (("Base Map Settings...", self.open_map_settings),
                               ("Replace Base Map...", self._replace_base_map)):
            action = QAction(title, self)
            action.triggered.connect(handler)
            map_menu.addAction(action)

        layer_menu = self.menuBar().addMenu("&Layer")
        add_layer = QAction("Add Layer", self)
        add_layer.triggered.connect(self.layer_panel._add_layer)
        layer_menu.addAction(add_layer)

    # --- tools ---
    def _mark_startup_complete(self) -> None:
        self._startup_complete = True
        # Start on the Draw tab with its open section's tool actually active.
        self.draw_panel.raise_()
        self._activate_tool(self.draw_panel.active_section())

    def _activate_tool(self, name: str) -> None:
        if self._startup_complete:
            self.view.set_tool(name)

    # --- selection <-> panels ---
    def _set_active_layer(self, layer_id: str) -> None:
        self.scene.set_active_layer(layer_id)
        self.layer_panel.set_active_layer_highlight(layer_id)

    def _on_selection_changed(self) -> None:
        selected = self.scene.selectedItems()
        element = self.scene.element_for_id(selected[0].data(0)) if len(selected) == 1 else None
        self._selected_element_id = element.id if element else None
        if element is None:
            return
        layer = self.scene.layer_for_element(element.id)
        if layer.id != self.scene.active_layer_id:  # selecting engages the element's layer
            self._set_active_layer(layer.id)
        editor = self._editors.get(element.kind)
        if editor is not None:
            dock, binder, section = editor
            binder.load(element)  # shows its values; doesn't emit edits
            if section:
                self.draw_panel.set_active_section(section)
            dock.raise_()

    def _apply_panel_to_selection(self, kind: str, binder) -> None:
        element = self.scene.element_for_id(self._selected_element_id) if self._selected_element_id else None
        if element is None or element.kind != kind:
            return
        values = {k: v for k, v in binder.values().items() if hasattr(element, k)}
        edit_element(self.undo_stack, self.scene, element, values, f"Edit {kind}")

    def _select_element_on_canvas(self, element_id: str) -> None:
        self.scene.set_active_layer(self.scene.layer_for_element(element_id).id)
        self.scene.clearSelection()
        item = self.scene.item_for_element(element_id)
        if item is not None:
            item.setSelected(True)

    # --- canvas edits ---
    def _copy_selection(self) -> None:
        """Copies the selected elements (any mix of kinds) to the system
        clipboard as JSON, plus their combined center for placing the paste."""
        items = [i for i in self.scene.selectedItems() if i.data(0)]
        if not items:
            return
        bounds = items[0].sceneBoundingRect()
        for item in items[1:]:
            bounds = bounds.united(item.sceneBoundingRect())
        payload = {
            "center": [bounds.center().x(), bounds.center().y()],
            "elements": [self.scene.element_for_id(i.data(0)).to_dict() for i in items],
        }
        mime = QMimeData()
        mime.setData(CLIPBOARD_MIME, json.dumps(payload).encode())
        QGuiApplication.clipboard().setMimeData(mime)
        self._paste_count = 0

    def _paste(self) -> None:
        """Pastes into the active layer as one undo step and selects the copies:
        centered on the mouse if it is over the map, otherwise offset from the
        originals (repeated pastes cascade)."""
        mime = QGuiApplication.clipboard().mimeData()
        layer_id = self.scene.active_layer_id
        if mime is None or not mime.hasFormat(CLIPBOARD_MIME) or layer_id is None:
            return
        payload = json.loads(bytes(mime.data(CLIPBOARD_MIME)).decode())
        cursor = self.view.viewport().mapFromGlobal(QCursor.pos())
        if self.view.viewport().rect().contains(cursor):
            target = self.view.mapToScene(cursor)
            dx, dy = target.x() - payload["center"][0], target.y() - payload["center"][1]
        else:
            self._paste_count = getattr(self, "_paste_count", 0) + 1
            dx = dy = PASTE_OFFSET * self._paste_count
        copies = [Element.from_dict(data).cloned(dx, dy) for data in payload["elements"]]
        push_as_one(self.undo_stack, [AddElementCommand(self.scene, layer_id, c, "Paste") for c in copies],
                    f"Paste {len(copies)} element(s)")
        self.scene.clearSelection()
        for copy in copies:
            self.scene.item_for_element(copy.id).setSelected(True)

    def _delete_selected_elements(self) -> None:
        ids = [item.data(0) for item in self.scene.selectedItems() if item.data(0)]
        delete_items(self.undo_stack, self.scene, ids)

    def _move_elements(self, moves: list) -> None:
        commands = []
        for element_id, dx, dy in moves:
            element = self.scene.element_for_id(element_id)
            command = SetElementFieldsCommand.changing(self.scene, element, element.translated(dx, dy), "Move")
            if command is not None:
                commands.append(command)
        push_as_one(self.undo_stack, commands, f"Move {len(commands)} elements")

    def _on_undo_stack_changed(self, _index: int) -> None:
        self.scene.set_active_layer(self.scene.active_layer_id)
        # Deferred: pushes often originate inside the layer tree's own
        # click/edit handling, where a synchronous rebuild would crash.
        self.layer_panel.request_refresh()

    # --- file actions ---
    def _image_filter(self) -> str:
        return "Images (" + " ".join(f"*{ext}" for ext in sorted(image_extensions())) + ")"

    def _ask_for_base_map(self, title: str) -> str:
        path, _ = QFileDialog.getOpenFileName(self, title, str(MAPS_DIR), self._image_filter())
        return path

    def _load(self, project: Project) -> None:
        self.scene.rebuild_from_project(project)
        self.undo_stack.clear()
        self.layer_panel.refresh()
        self.view.zoom_reset()

    def new_project(self) -> bool:
        """Asks for the base map image; the new project starts with it as the
        bottom "Base Map" layer plus an empty drawing layer. Cancel keeps the
        current project."""
        path = self._ask_for_base_map("New project - choose a base map")
        if not path:
            return False
        project = Project(base_map_path=path, layers=[Layer(name="Base Map", base_map=True), Layer(name="Layer 1")])
        self._load(project)
        self._current_project_path = None
        return True

    def _open_project(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "Hexcrawl Project (*.hexproj)")
        if not path_str:
            return
        project = load_project(Path(path_str))
        if project.base_map_path and not Path(project.base_map_path).exists():
            project.base_map_path = self._ask_for_base_map(f"Locate base map: {Path(project.base_map_path).name}")
        self._load(project)
        self._current_project_path = Path(path_str)

    def _save_project(self) -> None:
        if self._current_project_path is None:
            self._save_project_as()
        else:
            save_project(self.scene.project, self._current_project_path)

    def _save_project_as(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "Hexcrawl Project (*.hexproj)")
        if path_str:
            self._current_project_path = Path(path_str).with_suffix(".hexproj")
            save_project(self.scene.project, self._current_project_path)

    def open_map_settings(self) -> None:
        """Base map opacity + background color, regardless of the selected layer."""
        base = self.scene.base_layer()
        EffectsDialog(self.scene, self.undo_stack, base.id if base else None, self).exec()

    def _replace_base_map(self) -> None:
        """Swaps the base map image; the Base Map layer keeps its effects."""
        path = self._ask_for_base_map("Replace base map")
        if path:
            self.scene.set_base_map(path)
            self.layer_panel.refresh()

    def _export_png(self) -> None:
        bounds = self.scene.map_bounds()
        dialog = ExportDialog(int(bounds.width()), int(bounds.height()), self)
        if dialog.exec() != ExportDialog.DialogCode.Accepted:
            return
        scope_rect = None
        if dialog.scope() == "current_view":
            scope_rect = self.view.mapToScene(self.view.viewport().rect()).boundingRect().intersected(bounds)
        output_str, _ = QFileDialog.getSaveFileName(self, "Export PNG", "", "PNG Image (*.png)")
        if not output_str:
            return
        output_path = Path(output_str).with_suffix(".png")
        export_png(self.scene, output_path, scope_rect, dialog.resolution())
        QMessageBox.information(self, "Export complete", f"Exported to {output_path}")
