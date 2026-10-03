"""Left-button canvas tools. Every tool is built the same way:

    Tool(view, get_layer_id, get_settings, on_placed=None)

where get_settings() returns the tool's panel binder values - the same
dict-of-fields the panel uses to edit a selected element. Two shared
behaviors cover all tools: click-to-place (Label, Asset) and drag-to-draw
with a live preview (Line, Shape, Fog).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsRectItem

from ..commands import edit_element, edit_layer
from ..commands.element_commands import AddElementCommand
from ..models.effects import FogOfWarEffect
from ..models.elements import AssetElement, FogMaskElement, LabelElement, ShapeElement, StrokeElement
from .items.path_items import ShapeItem, StrokeItem

PREVIEW_Z = 2000


class CanvasTool:
    name = "tool"

    def __init__(self, view, get_layer_id, get_settings, on_placed=None):
        self.view = view
        self.get_layer_id = get_layer_id
        self.get_settings = get_settings
        self.on_placed = on_placed

    def _add(self, element, text: str, settings: dict) -> None:
        layer_id = self.get_layer_id()
        if layer_id:
            self.view.undo_stack.push(AddElementCommand(self.view.scene(), layer_id, element, text))
            if callable(self.on_placed):
                self.on_placed(settings)

    def mouse_press(self, pos, event) -> bool:
        return False

    def mouse_move(self, pos, event) -> bool:
        return False

    def mouse_release(self, pos, event) -> bool:
        return False

    def deactivate(self) -> None:
        pass


class ClickPlaceTool(CanvasTool):
    """Subclasses implement make_element(pos, settings) -> element or None."""

    def mouse_press(self, pos, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        settings = self.get_settings()
        element = self.make_element((pos.x(), pos.y()), settings)
        if element is not None:
            self._add(element, f"Place {self.name}", settings)
        return True


class LabelTool(ClickPlaceTool):
    name = "label"

    def make_element(self, pos, settings):
        if not settings.get("text"):
            return None
        return LabelElement(pos=pos, name=f"Label: {settings['text']}", **settings)


class AssetTool(ClickPlaceTool):
    name = "asset"

    def make_element(self, pos, settings):
        if not settings.get("asset_path"):
            return None
        return AssetElement(pos=pos, name=Path(settings["asset_path"]).stem, **settings)


class DragTool(CanvasTool):
    """Press starts a preview, move updates it, release commits. Subclasses
    implement start(pos, settings) -> preview item, update(pos), finish()."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._preview = None

    def mouse_press(self, pos, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        self._settings = self.get_settings()
        self._start = (pos.x(), pos.y())
        self._preview = self.start(self._start, self._settings)
        self._preview.setZValue(PREVIEW_Z)
        self.view.scene().addItem(self._preview)
        return True

    def mouse_move(self, pos, event) -> bool:
        if self._preview is None:
            return False
        self.update((pos.x(), pos.y()))
        return True

    def mouse_release(self, pos, event) -> bool:
        if self._preview is None:
            return False
        self.update((pos.x(), pos.y()))
        self.deactivate()
        self.finish()
        return True

    def deactivate(self) -> None:
        if self._preview is not None:
            self.view.scene().removeItem(self._preview)
            self._preview = None


class ElementDragTool(DragTool):
    """Preview is the real canvas item for the element being drawn, so the
    preview always looks exactly like the result."""

    def start(self, pos, settings):
        self._element = self.new_element(pos, settings)
        return self.item_class(self._element)

    def update(self, pos) -> None:
        self.extend(self._element, pos)
        self._preview.sync_from_element(self._element)

    def finish(self) -> None:
        if self.is_valid(self._element):
            self._add(self._element, f"Draw {self.name}", self._settings)


class LineTool(ElementDragTool):
    name = "line"
    item_class = StrokeItem

    def new_element(self, pos, settings):
        return StrokeElement(points=[pos], name="Line", **settings)

    def extend(self, element, pos) -> None:
        if element.points[-1] != pos:
            element.points.append(pos)

    def is_valid(self, element) -> bool:
        return len(element.points) >= 2


class ShapeTool(ElementDragTool):
    name = "shape"
    item_class = ShapeItem

    def new_element(self, pos, settings):
        return ShapeElement(p1=pos, p2=pos, name=settings["shape_type"].capitalize(), **settings)

    def extend(self, element, pos) -> None:
        element.p2 = pos

    def is_valid(self, element) -> bool:
        return element.p1 != element.p2


class FogTool(DragTool):
    """Drag a rectangle to hide or reveal (per the Fog panel's mode)."""

    name = "fog"

    def start(self, pos, settings):
        preview = QGraphicsRectItem()
        preview.setBrush(QColor(settings["color"] if settings["mode"] == "hide" else "#30c0ff"))
        preview.setOpacity(0.5)
        return preview

    def update(self, pos) -> None:
        (x1, y1), (x2, y2) = self._start, pos
        self._rect = (min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))
        self._preview.setRect(QRectF(*self._rect))

    def finish(self) -> None:
        layer_id = self.get_layer_id()
        if not layer_id or self._rect[2] < 1 or self._rect[3] < 1:
            return
        mask = self._fog_mask(layer_id)
        region = {"rect": list(self._rect), "mode": self._settings["mode"]}
        edit_element(self.view.undo_stack, self.view.scene(), mask, {"regions": mask.regions + [region]},
                     "Hide fog" if region["mode"] == "hide" else "Reveal fog")

    def _fog_mask(self, layer_id: str) -> FogMaskElement:
        scene = self.view.scene()
        layer = scene.project.find_layer(layer_id)
        mask = next((e for e in layer.elements if isinstance(e, FogMaskElement)), None)
        if mask is None:
            mask = FogMaskElement(name="Fog Mask", color=self._settings["color"])
            self.view.undo_stack.push(AddElementCommand(scene, layer_id, mask, "Add fog mask"))
            if not any(isinstance(e, FogOfWarEffect) for e in layer.effects):
                edit_layer(self.view.undo_stack, scene, layer,
                           {"effects": layer.effects + [FogOfWarEffect(mask_element_id=mask.id)]}, "Enable fog")
        return mask
