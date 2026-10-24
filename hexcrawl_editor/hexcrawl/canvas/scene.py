from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene

from ..defaults import DEFAULTS
from ..models.elements import Element
from ..models.layer import Layer
from ..models.project import Project
from .images import load_image
from .items.asset_item import AssetItem
from .items.fog_item import FogMaskItem
from .items.label_item import LabelItem
from .items.path_items import ShapeItem, StrokeItem
from .layer_item import LayerGroupItem

DEFAULT_CANVAS = QRectF(0, 0, *DEFAULTS["project"]["canvas_size"])  # canvas size when there is no base map
BACKGROUND_Z = -1_000_000  # below every layer


class HexcrawlScene(QGraphicsScene):
    def __init__(self, assets_dir: Path, parent=None):
        super().__init__(parent)
        self.assets_dir = assets_dir
        self.project = Project()
        self.active_layer_id: str | None = None
        self.base_map_item: QGraphicsPixmapItem | None = None
        self._base_pixmap = QPixmap()
        # Project background: below all layers (so layer effects never touch
        # it) and covering the map area; shows through a faded base map.
        self._background = QGraphicsRectItem()
        self._background.setZValue(BACKGROUND_Z)
        self._background.setPen(QPen(Qt.PenStyle.NoPen))
        self._background.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.addItem(self._background)
        self.layer_items: dict[str, LayerGroupItem] = {}
        self._element_items: dict[str, QGraphicsItem] = {}
        # Set by main_window: every item edit and delete request funnels through these.
        self.on_element_edited = None  # (element_id, old_fields, new_fields, label) -> None
        self.on_delete_requested = None  # (element_id) -> None
        self._factories = {
            "stroke": StrokeItem,
            "shape": ShapeItem,
            "label": LabelItem,
            "asset": lambda e: AssetItem(e, self.assets_dir),
            "fog": lambda e: FogMaskItem(e, self.map_bounds),
        }

    # --- base map: an image shown inside the bottom "Base Map" layer, so all
    # layer features (effects such as opacity, visibility, undo) apply to it ---
    def set_base_map(self, path: Path | str) -> None:
        self.project.base_map_path = str(path)
        if self.base_layer() is None:
            self.insert_layer(Layer(name=DEFAULTS["project"]["base_layer_name"], base_map=True), 0)
        self._load_base_pixmap()

    def base_layer(self) -> Layer | None:
        return next((layer for layer in self.project.layers if layer.base_map), None)

    def _load_base_pixmap(self) -> None:
        path = self.project.base_map_path
        self._base_pixmap = load_image(path) if path else QPixmap()
        if not self._base_pixmap.isNull():
            self.project.base_map_size = (self._base_pixmap.width(), self._base_pixmap.height())
        layer = self.base_layer()
        if layer is not None:
            self._attach_base_pixmap(self.layer_items[layer.id])
        self.setSceneRect(self.map_bounds())
        self.refresh_project()

    def refresh_project(self) -> None:
        """Re-sync project-wide settings (currently the background)."""
        self._background.setRect(self.map_bounds())
        self._background.setBrush(QColor(self.project.background_color))

    def _attach_base_pixmap(self, group: LayerGroupItem) -> None:
        for child in group.childItems():
            if child.data(1) == "base_map":
                self.removeItem(child)
        self.base_map_item = None
        if not self._base_pixmap.isNull():
            self.base_map_item = QGraphicsPixmapItem(self._base_pixmap, group)
            self.base_map_item.setData(1, "base_map")
            self.base_map_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

    def map_bounds(self) -> QRectF:
        return QRectF(self._base_pixmap.rect()) if not self._base_pixmap.isNull() else QRectF(DEFAULT_CANVAS)

    # --- export: rendered by the same items that draw the canvas ---
    def render_image(self, source: QRectF, width: int, height: int) -> QImage:
        """Flattens the currently visible content of `source`. Selection is
        cleared during the render so handles/selection outlines never show.
        """
        selected = self.selectedItems()
        self.clearSelection()
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(0)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.render(painter, QRectF(0, 0, width, height), source, Qt.AspectRatioMode.IgnoreAspectRatio)
        painter.end()
        for item in selected:
            item.setSelected(True)
        return image

    # --- project <-> scene ---
    def rebuild_from_project(self, project: Project) -> None:
        self.project = project
        for layer_item in list(self.layer_items.values()):
            self.removeItem(layer_item)
        self.layer_items.clear()
        self._element_items.clear()
        if project.base_map_path and not any(layer.base_map for layer in project.layers):
            # Projects saved before the base map became a layer.
            project.layers.insert(0, Layer(name=DEFAULTS["project"]["base_layer_name"], base_map=True))
        if all(layer.base_map for layer in project.layers):
            # Always start with at least one layer the user can draw into.
            project.layers.append(Layer(name=DEFAULTS["project"]["first_layer_name"]))
        for layer in project.layers:
            self._build_layer_item(layer)
        self._restack_layers()
        self._load_base_pixmap()
        self.active_layer_id = None
        self.set_active_layer(None)

    def set_active_layer(self, layer_id: str | None) -> None:
        """Sets the layer new elements go into. The base map layer is never a
        drawing target: asking for it (or for a layer that no longer exists)
        keeps the current layer, or falls back to the topmost drawable one.
        Only the active layer's elements are clickable on the canvas.
        """
        def drawable(lid):
            layer = self.project.find_layer(lid) if lid else None
            return layer if layer is not None and not layer.base_map else None

        layer = drawable(layer_id) or drawable(self.active_layer_id) or next(
            (l for l in reversed(self.project.layers) if not l.base_map), None
        )
        self.active_layer_id = layer.id if layer else None
        for layer in self.project.layers:
            for element in layer.elements:
                self._apply_selectable(element.id, layer.id)

    def _apply_selectable(self, element_id: str, layer_id: str) -> None:
        item = self._element_items.get(element_id)
        if item is None or isinstance(item, FogMaskItem):  # fog spans the map; never clickable
            return
        is_active = layer_id == self.active_layer_id
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, is_active)
        if not is_active and item.isSelected():
            item.setSelected(False)

    def _build_layer_item(self, layer: Layer) -> None:
        group = LayerGroupItem(layer.id)
        self.addItem(group)
        self.layer_items[layer.id] = group
        if layer.base_map:
            self._attach_base_pixmap(group)
        for element in layer.elements:
            self._materialize_element(layer.id, element)
        self.refresh_layer_effects(layer.id)

    def _restack_layers(self) -> None:
        for index, layer in enumerate(self.project.layers):
            self.layer_items[layer.id].setZValue(index)

    def _materialize_element(self, layer_id: str, element: Element) -> None:
        item = self._factories[element.kind](element)
        item.setParentItem(self.layer_items[layer_id])
        self._element_items[element.id] = item
        eid = element.id
        item.on_edited = lambda old, new, label: self.on_element_edited and self.on_element_edited(eid, old, new, label)
        item.on_delete_requested = lambda: self.on_delete_requested and self.on_delete_requested(eid)
        self._apply_selectable(element.id, layer_id)

    # --- layer / element mutation (called by undo commands) ---
    def insert_layer(self, layer: Layer, index: int) -> None:
        self.project.layers.insert(min(index, len(self.project.layers)), layer)
        self._build_layer_item(layer)
        self._restack_layers()

    def remove_layer(self, layer_id: str) -> None:
        group = self.layer_items.pop(layer_id, None)
        if group is not None:
            self.removeItem(group)
        self.project.layers = [l for l in self.project.layers if l.id != layer_id]
        self._restack_layers()

    def add_element(self, layer_id: str, element: Element) -> None:
        layer = self.project.find_layer(layer_id)
        if layer is not None:
            self.insert_element(layer_id, element, len(layer.elements))

    def insert_element(self, layer_id: str, element: Element, index: int) -> None:
        layer = self.project.find_layer(layer_id)
        if layer is None:
            return
        layer.elements.insert(min(index, len(layer.elements)), element)
        self._materialize_element(layer_id, element)

    def remove_element(self, element_id: str) -> None:
        item = self._element_items.pop(element_id, None)
        if item is not None:
            self.removeItem(item)
        for layer in self.project.layers:
            layer.elements = [e for e in layer.elements if e.id != element_id]

    # --- lookups ---
    def item_for_element(self, element_id: str):
        return self._element_items.get(element_id)

    def element_for_id(self, element_id: str) -> Element | None:
        layer = self.layer_for_element(element_id)
        return layer.find_element(element_id) if layer else None

    def layer_for_element(self, element_id: str) -> Layer | None:
        for layer in self.project.layers:
            if layer.find_element(element_id) is not None:
                return layer
        return None

    # --- re-sync after model edits ---
    def refresh_element(self, element_id: str) -> None:
        element = self.element_for_id(element_id)
        item = self._element_items.get(element_id)
        if element is not None and item is not None:
            item.sync_from_element(element)

    def refresh_layer_effects(self, layer_id: str) -> None:
        layer = self.project.find_layer(layer_id)
        group = self.layer_items.get(layer_id)
        if layer is not None and group is not None:
            group.apply_effects(layer.effects)
            group.setVisible(layer.visible)
