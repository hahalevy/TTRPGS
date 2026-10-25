from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDockWidget, QHBoxLayout, QHeaderView, QMessageBox, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..commands import delete_items, edit_element, edit_layer
from ..commands.layer_commands import AddLayerCommand
from ..models.layer import Layer
from ..models.targets import KIND_LABELS
from .widgets import confirm

LAYER_ROLE = Qt.ItemDataRole.UserRole
ELEMENT_ROLE = Qt.ItemDataRole.UserRole + 1

NAME_COL = 0  # checkbox here = "marked" for bulk actions (not visibility)
VISIBLE_COL = 1  # eye icon, click to show/hide
TYPE_COL = 2
NOTES_COL = 3  # how many notes are attached to the row

def _eye_icon(visible: bool) -> QIcon:
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor("#202020") if visible else QColor("#a0a0a0")
    p.setPen(QPen(color, 1.5))
    eye = QPainterPath()
    eye.moveTo(2, 9)
    eye.quadTo(9, 2, 16, 9)
    eye.quadTo(9, 16, 2, 9)
    p.drawPath(eye)
    if visible:
        p.setBrush(color)
        p.drawEllipse(QPointF(9, 9), 2.5, 2.5)
    else:
        p.drawLine(3, 15, 15, 3)
    p.end()
    return QIcon(pixmap)


class LayerPanel(QDockWidget):
    activeLayerChanged = Signal(str)
    effectsRequested = Signal(str)
    elementSelected = Signal(str)

    def __init__(self, scene, undo_stack, parent=None):
        super().__init__("Layers", parent)
        self.scene = scene
        self.undo_stack = undo_stack
        self._marked_ids: set[str] = set()
        self._refresh_pending = False
        self._eye_on = _eye_icon(True)
        self._eye_off = _eye_icon(False)

        container = QWidget()
        layout = QVBoxLayout(container)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Name", "Visible", "Type", "Notes"])
        header = self.tree.header()
        header.setSectionResizeMode(NAME_COL, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(VISIBLE_COL, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(TYPE_COL, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(NOTES_COL, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(False)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Add Layer")
        del_layer_btn = QPushButton("Delete Layer")
        del_checked_btn = QPushButton("Delete Checked")
        effects_btn = QPushButton("Effects...")
        add_btn.clicked.connect(self._add_layer)
        del_layer_btn.clicked.connect(self._delete_current_layer)
        del_checked_btn.clicked.connect(self._delete_checked)
        effects_btn.clicked.connect(self._open_effects)
        for btn in (add_btn, del_layer_btn, del_checked_btn, effects_btn):
            buttons.addWidget(btn)
        layout.addLayout(buttons)

        self.setWidget(container)
        self._suppress_item_changed = False
        self.refresh()

    # --- refreshing ---
    def request_refresh(self) -> None:
        """Rebuilds the tree on the next event-loop turn. Rebuilding
        synchronously from inside the tree's own click/itemChanged handling
        deletes the very item Qt is still processing (use-after-free crash),
        so every rebuild triggered by an edit goes through here.
        """
        if self._refresh_pending:
            return
        self._refresh_pending = True
        QTimer.singleShot(0, self._do_deferred_refresh)

    def _do_deferred_refresh(self) -> None:
        self._refresh_pending = False
        self.refresh()

    def set_active_layer_highlight(self, layer_id: str) -> None:
        self._suppress_item_changed = True
        try:
            for i in range(self.tree.topLevelItemCount()):
                top = self.tree.topLevelItem(i)
                font = top.font(NAME_COL)
                font.setBold(top.data(NAME_COL, LAYER_ROLE) == layer_id)
                top.setFont(NAME_COL, font)
        finally:
            self._suppress_item_changed = False

    def _make_row(self, item_id: str, name: str, visible: bool, type_label: str, role) -> QTreeWidgetItem:
        notes = len(self.scene.project.notes_for(item_id))
        row = QTreeWidgetItem([name, "", type_label, str(notes) if notes else ""])
        row.setTextAlignment(NOTES_COL, Qt.AlignmentFlag.AlignCenter)
        row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
        row.setCheckState(NAME_COL, Qt.CheckState.Checked if item_id in self._marked_ids else Qt.CheckState.Unchecked)
        row.setIcon(VISIBLE_COL, self._eye_on if visible else self._eye_off)
        row.setToolTip(VISIBLE_COL, "Click to hide" if visible else "Click to show")
        row.setData(NAME_COL, role, item_id)
        return row

    def refresh(self) -> None:
        expanded_ids = {
            self.tree.topLevelItem(i).data(NAME_COL, LAYER_ROLE)
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).isExpanded()
        }
        current = self.tree.currentItem()
        current_id = (current.data(NAME_COL, ELEMENT_ROLE) or current.data(NAME_COL, LAYER_ROLE)) if current else None
        active_layer_id = self.scene.active_layer_id

        existing_ids = {layer.id for layer in self.scene.project.layers}
        existing_ids |= {e.id for layer in self.scene.project.layers for e in layer.elements}
        self._marked_ids &= existing_ids

        self._suppress_item_changed = True
        try:
            self.tree.clear()
            restore = None
            for layer in self.scene.project.layers:
                layer_row = self._make_row(
                    layer.id, layer.name, layer.visible, "Base map" if layer.base_map else "Layer", LAYER_ROLE
                )
                if layer.id == active_layer_id:
                    font = layer_row.font(NAME_COL)
                    font.setBold(True)
                    layer_row.setFont(NAME_COL, font)
                for element in layer.elements:
                    el_row = self._make_row(
                        element.id, element.name or KIND_LABELS.get(element.kind, element.kind),
                        element.visible, KIND_LABELS.get(element.kind, element.kind), ELEMENT_ROLE,
                    )
                    layer_row.addChild(el_row)
                    if element.id == current_id:
                        restore = el_row
                self.tree.addTopLevelItem(layer_row)
                layer_row.setExpanded(layer.id in expanded_ids or layer.id == active_layer_id)
                if layer.id == current_id:
                    restore = layer_row
            if restore is not None:
                self.tree.setCurrentItem(restore)
        finally:
            self._suppress_item_changed = False

    # --- interaction ---
    def _on_item_clicked(self, item: QTreeWidgetItem | None, column: int) -> None:
        if item is None:
            return
        element_id = item.data(NAME_COL, ELEMENT_ROLE)
        layer_id = item.data(NAME_COL, LAYER_ROLE)
        alt_held = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.AltModifier)

        if column == VISIBLE_COL or (alt_held and element_id):
            self._toggle_visibility(element_id, layer_id)
            return
        if element_id:
            # Clicking an element row engages its layer and selects it on canvas.
            parent = item.parent()
            if parent is not None:
                self.activeLayerChanged.emit(parent.data(NAME_COL, LAYER_ROLE))
            self.elementSelected.emit(element_id)
        elif layer_id:
            self.activeLayerChanged.emit(layer_id)

    def _model_for(self, element_id: str | None, layer_id: str | None):
        """(model object, edit function) for a row - layers and elements are
        edited the same way, just through their own command type."""
        if element_id:
            return self.scene.element_for_id(element_id), edit_element
        return self.scene.project.find_layer(layer_id), edit_layer

    def _toggle_visibility(self, element_id: str | None, layer_id: str | None) -> None:
        obj, edit = self._model_for(element_id, layer_id)
        if obj is not None:
            edit(self.undo_stack, self.scene, obj, {"visible": not obj.visible}, "Toggle visibility")

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._suppress_item_changed or column != NAME_COL:
            return
        # Read everything from `item` before pushing anything: a push can
        # schedule a rebuild that invalidates this item.
        marked = item.checkState(NAME_COL) == Qt.CheckState.Checked
        new_name = item.text(NAME_COL)
        element_id = item.data(NAME_COL, ELEMENT_ROLE)
        layer_id = item.data(NAME_COL, LAYER_ROLE)
        obj, edit = self._model_for(element_id, layer_id)
        if obj is None:
            return
        (self._marked_ids.add if marked else self._marked_ids.discard)(obj.id)
        if new_name and new_name != self._display_name(obj):
            edit(self.undo_stack, self.scene, obj, {"name": new_name}, "Rename")

    @staticmethod
    def _display_name(obj) -> str:
        return obj.name or KIND_LABELS.get(getattr(obj, "kind", ""), "")

    def _confirm(self, title: str, text: str) -> bool:
        return confirm(self, title, text)

    # --- buttons ---
    def _add_layer(self) -> None:
        layer = Layer(name=f"Layer {len(self.scene.project.layers) + 1}")
        self.undo_stack.push(AddLayerCommand(self.scene, layer, "Add layer"))
        self.activeLayerChanged.emit(layer.id)

    def _current_layer_id(self) -> str | None:
        item = self.tree.currentItem()
        if item is None:
            return None
        if item.data(NAME_COL, LAYER_ROLE):
            return item.data(NAME_COL, LAYER_ROLE)
        parent = item.parent()
        return parent.data(NAME_COL, LAYER_ROLE) if parent is not None else None

    def _delete_current_layer(self) -> None:
        layer_id = self._current_layer_id() or self.scene.active_layer_id
        layer = self.scene.project.find_layer(layer_id) if layer_id else None
        if layer is not None and self._confirm(
            "Delete layer", f'Delete layer "{layer.name}" and its {len(layer.elements)} element(s)?'
        ):
            delete_items(self.undo_stack, self.scene, layer_ids=[layer.id])

    def _delete_checked(self) -> None:
        layer_ids = {layer.id for layer in self.scene.project.layers if layer.id in self._marked_ids}
        element_ids = {
            e.id
            for layer in self.scene.project.layers
            if layer.id not in layer_ids  # a checked layer already takes its elements with it
            for e in layer.elements
            if e.id in self._marked_ids
        }
        if not layer_ids and not element_ids:
            QMessageBox.information(
                self, "Delete checked",
                "Tick the checkbox next to the layers or elements you want to delete first.",
            )
            return
        if self._confirm(
            "Delete checked", f"Delete {len(layer_ids)} layer(s) (with their elements) and {len(element_ids)} element(s)?"
        ):
            delete_items(self.undo_stack, self.scene, element_ids, layer_ids)
            self._marked_ids -= layer_ids | element_ids

    def _open_effects(self) -> None:
        layer_id = self._current_layer_id() or self.scene.active_layer_id
        if layer_id:
            self.effectsRequested.emit(layer_id)
