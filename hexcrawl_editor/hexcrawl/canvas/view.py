from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsView, QRubberBand

from ..commands import edit_element

MIN_SCALE = 0.05
MAX_SCALE = 16.0
DRAG_THRESHOLD = 4


class HexcrawlView(QGraphicsView):
    """Left mouse button always performs whatever tool is currently active
    (Line/Shapes/Fog/Label/Asset, picked directly from its sidebar section -
    there's no separate "select tool" step). Right mouse button always
    selects and manipulates: click selects one element, drag either moves a
    clicked label/asset or rubber-bands a multi-selection over empty space,
    and also drives any resize/rotate/stretch/delete handle on an
    already-selected element - regardless of whichever tool is active for
    the left button. Middle mouse button always pans.
    """

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        self._cumulative_scale = 1.0
        self._tools: dict[str, object] = {}
        self.current_tool = None
        self.on_delete_key = None  # () -> None, set by main_window
        self.on_items_moved = None  # (list of (element_id, dx, dy)) -> None, set by main_window
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._middle_panning = False
        self._last_pan_point: QPointF | None = None

        self._rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._right_press_viewport_pos: QPointF | None = None
        self._right_dragging = False
        self._right_press_on_handle = False
        self._right_move_item = None
        self._right_move_start_pos: QPointF | None = None
        self._right_move_starts: dict = {}

    # --- tool management ---
    def register_tool(self, name: str, tool) -> None:
        self._tools[name] = tool

    def set_tool(self, name: str) -> None:
        if self.current_tool is not None:
            self.current_tool.deactivate()
        self.current_tool = self._tools.get(name)
        if self.current_tool is not None and hasattr(self.current_tool, "activate"):
            self.current_tool.activate()

    # --- zoom ---
    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_scale = self._cumulative_scale * factor
        if new_scale < MIN_SCALE or new_scale > MAX_SCALE:
            return
        self._cumulative_scale = new_scale
        self.scale(factor, factor)

    def zoom_in(self) -> None:
        factor = 1.25
        if self._cumulative_scale * factor <= MAX_SCALE:
            self._cumulative_scale *= factor
            self.scale(factor, factor)

    def zoom_out(self) -> None:
        factor = 1 / 1.25
        if self._cumulative_scale * factor >= MIN_SCALE:
            self._cumulative_scale *= factor
            self.scale(factor, factor)

    def zoom_reset(self) -> None:
        self.resetTransform()
        self._cumulative_scale = 1.0

    # --- mouse dispatch ---
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_panning = True
            self._last_pan_point = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self._handle_right_press(event)
            event.accept()
            return

        if self.current_tool is not None:
            handled = self.current_tool.mouse_press(self.mapToScene(event.position().toPoint()), event)
            if handled:
                event.accept()
                return
        # No active tool: absorb the click rather than falling back to Qt's
        # default item-click-selection/drag on the left button - selection
        # and moving only ever happen via the right button.
        event.accept()

    def _interactive_item_at(self, viewport_pos):
        """Topmost visible handle or selectable element under the cursor,
        skipping everything else (base map, layer groups, fog mask, previews)
        so a large non-interactive item can never swallow the click.
        Uses the view's own hit-testing so transform-ignoring handles are
        hit correctly at any zoom/scroll position.
        """
        for item in self.items(viewport_pos):
            if not item.isVisible():
                continue
            if getattr(item, "is_handle", False):
                return item
            if item.data(0) and (item.flags() & item.GraphicsItemFlag.ItemIsSelectable):
                return item
        return None

    def _handle_right_press(self, event: QMouseEvent) -> None:
        self._right_press_viewport_pos = event.position().toPoint()
        self._right_dragging = False
        self._right_move_item = None
        self._right_move_start_pos = None
        self._right_move_starts = {}

        item = self._interactive_item_at(self._right_press_viewport_pos)

        if item is not None and getattr(item, "is_handle", False):
            self._right_press_on_handle = True
            super().mousePressEvent(event)
            return
        self._right_press_on_handle = False

        ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if ctrl_held or item is None:
            return  # ctrl: toggles visibility on release; empty space: rubber band

        if not item.isSelected():
            self.scene().clearSelection()
            item.setSelected(True)
        # Pressing on any selected element arms a move of the whole selection.
        self._right_move_item = item
        self._right_move_start_pos = item.pos()
        self._right_move_starts = {sel: sel.pos() for sel in self.scene().selectedItems() if sel.data(0)}

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._middle_panning and self._last_pan_point is not None:
            delta = event.position() - self._last_pan_point
            self._last_pan_point = event.position()
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - int(delta.x()))
            v_bar.setValue(v_bar.value() - int(delta.y()))
            event.accept()
            return

        if event.buttons() & Qt.MouseButton.RightButton:
            self._handle_right_move(event)
            event.accept()
            return

        if self.current_tool is not None:
            handled = self.current_tool.mouse_move(self.mapToScene(event.position().toPoint()), event)
            if handled:
                event.accept()
                return
        super().mouseMoveEvent(event)

    def _handle_right_move(self, event: QMouseEvent) -> None:
        if self._right_press_on_handle:
            super().mouseMoveEvent(event)
            return
        if self._right_move_item is not None and self._right_move_starts:
            current = event.position().toPoint()
            if not self._right_dragging and (current - self._right_press_viewport_pos).manhattanLength() <= DRAG_THRESHOLD:
                return
            scene_pos = self.mapToScene(current)
            press_scene_pos = self.mapToScene(self._right_press_viewport_pos)
            delta = scene_pos - press_scene_pos
            for sel, start in self._right_move_starts.items():
                sel.setPos(start + delta)
            self._right_dragging = True
            return
        if self._right_press_viewport_pos is not None:
            current = event.position().toPoint()
            moved = (current - self._right_press_viewport_pos).manhattanLength()
            if moved > DRAG_THRESHOLD:
                self._right_dragging = True
                rect = QRect(self._right_press_viewport_pos, current).normalized()
                self._rubber_band.setGeometry(rect)
                self._rubber_band.show()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._middle_panning:
            self._middle_panning = False
            self._last_pan_point = None
            self.unsetCursor()
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self._handle_right_release(event)
            event.accept()
            return

        if self.current_tool is not None:
            handled = self.current_tool.mouse_release(self.mapToScene(event.position().toPoint()), event)
            if handled:
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def _handle_right_release(self, event: QMouseEvent) -> None:
        if self._right_press_on_handle:
            super().mouseReleaseEvent(event)
        elif self._right_move_item is not None:
            if self._right_dragging:
                delta = self._right_move_item.pos() - self._right_move_start_pos
                moves = [(sel.data(0), delta.x(), delta.y()) for sel in self._right_move_starts]
                if delta.manhattanLength() > 0.01 and callable(self.on_items_moved):
                    self.on_items_moved(moves)
            # else: plain click already selected it in _handle_right_press
        elif self._right_dragging:
            self._rubber_band.hide()
            rect_viewport = self._rubber_band.geometry()
            scene_rect = self.mapToScene(rect_viewport).boundingRect()
            self._select_items_in_rect(scene_rect, event)
        else:
            self._select_or_toggle_item_at(self._right_press_viewport_pos, event)

        self._right_press_viewport_pos = None
        self._right_dragging = False
        self._right_press_on_handle = False
        self._right_move_item = None
        self._right_move_start_pos = None
        self._right_move_starts = {}

    def _select_or_toggle_item_at(self, viewport_pos, event: QMouseEvent) -> None:
        if viewport_pos is None:
            return
        item = self._interactive_item_at(viewport_pos)
        if item is not None and getattr(item, "is_handle", False):
            item = None
        element_id = item.data(0) if item is not None else None
        ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)

        if ctrl_held and element_id:
            element = self.scene().element_for_id(element_id)
            if element is not None:
                edit_element(self.undo_stack, self.scene(), element, {"visible": not element.visible}, "Toggle visibility")
            return

        selectable = item is not None and bool(item.flags() & item.GraphicsItemFlag.ItemIsSelectable)
        if not ctrl_held:
            self.scene().clearSelection()
        if selectable:
            item.setSelected(True)

    def _select_items_in_rect(self, scene_rect, event: QMouseEvent) -> None:
        ctrl_held = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if not ctrl_held:
            self.scene().clearSelection()
        items = self.scene().items(scene_rect, Qt.ItemSelectionMode.IntersectsItemShape)
        for item in items:
            if item.flags() & item.GraphicsItemFlag.ItemIsSelectable:
                item.setSelected(True)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if callable(self.on_delete_key):
                self.on_delete_key()
                event.accept()
                return
        super().keyPressEvent(event)
