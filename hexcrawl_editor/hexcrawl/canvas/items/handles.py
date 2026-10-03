"""Selection handles shared by every editable canvas item (labels, assets,
lines, shapes): uniform resize (corner), rotate (top), horizontal/vertical
stretch (edges) and delete ("x"). Handles respond to the right mouse button,
which is the canvas's "select & manipulate" button.

Items mix in TransformHandleMixin and implement four small hooks:
  _local_rect()            untransformed rect used for handles and as pivot
  _edit_fields()           current values of the fields a handle drag changes
  _apply_scale(rx, ry, s)  scale by ratios relative to snapshot `s`
  _matrix_scale()          (sx, sy) baked into the item transform
A finished drag reports on_edited(old_fields, new_fields, label); the app
turns that into a single undo command.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

HANDLE_SIZE = 8.0
ROTATE_HANDLE_OFFSET = 24.0
MIN_RATIO = 0.05

_CURSORS = {
    "corner": Qt.CursorShape.SizeFDiagCursor,
    "rotate": Qt.CursorShape.CrossCursor,
    "h_stretch": Qt.CursorShape.SizeHorCursor,
    "v_stretch": Qt.CursorShape.SizeVerCursor,
    "delete": Qt.CursorShape.PointingHandCursor,
}
_LABELS = {"corner": "Resize", "rotate": "Rotate", "h_stretch": "Stretch", "v_stretch": "Stretch"}


class HandleItem(QGraphicsRectItem):
    is_handle = True  # lets HexcrawlView route right-clicks to handles first

    def __init__(self, owner: "TransformHandleMixin", kind: str):
        super().__init__(-HANDLE_SIZE / 2, -HANDLE_SIZE / 2, HANDLE_SIZE, HANDLE_SIZE, owner)
        self._owner = owner
        self.kind = kind
        self.setBrush(QBrush(QColor("#d03030" if kind == "delete" else "white")))
        self.setPen(QPen(QColor("#2060C0"), 1.0))
        self.setZValue(1000)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setCursor(_CURSORS[kind])
        self.setVisible(False)
        self.setAcceptedMouseButtons(Qt.MouseButton.RightButton)

    def mousePressEvent(self, event):
        if self.kind != "delete":
            self._owner._begin_handle_drag(event.scenePos())
        event.accept()

    def mouseMoveEvent(self, event):
        if self.kind != "delete":
            self._owner._update_handle_drag(self.kind, event.scenePos())
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.kind == "delete":
            if callable(self._owner.on_delete_requested):
                self._owner.on_delete_requested()
        else:
            self._owner._finish_handle_drag(self.kind)
        event.accept()


def _unrotate(v: QPointF, degrees: float) -> QPointF:
    """Expresses a scene-space vector in the item's rotated local axes, so
    stretching follows the item's own x/y even when it is rotated."""
    r = math.radians(-degrees)
    return QPointF(v.x() * math.cos(r) - v.y() * math.sin(r), v.x() * math.sin(r) + v.y() * math.cos(r))


def _ratio(now: float, start: float) -> float:
    if abs(start) < 1e-6:
        return 1.0
    return max(MIN_RATIO, now / start)


class TransformHandleMixin:
    def _init_handles(self) -> None:
        self._handles = {kind: HandleItem(self, kind) for kind in _CURSORS}
        self.on_edited = None  # (old_fields, new_fields, label) -> None, set by the scene
        self.on_delete_requested = None  # () -> None, set by the scene
        self._drag_snapshot: dict | None = None
        if not hasattr(self, "_rotation"):
            self._rotation = 0.0

    # --- hooks (overridden per item type) ---
    def _local_rect(self) -> QRectF:
        return self.boundingRect()

    def _matrix_scale(self) -> tuple[float, float]:
        return 1.0, 1.0

    def _edit_fields(self) -> dict:
        raise NotImplementedError

    def _apply_scale(self, rx: float, ry: float, snapshot: dict) -> None:
        raise NotImplementedError

    # --- shared behavior ---
    def _rebuild_transform(self) -> None:
        # Rotation/scale pivot is baked into the matrix: setTransformOriginPoint
        # only affects Qt's rotation()/scale() properties, not setTransform().
        center = self._local_rect().center()
        sx, sy = self._matrix_scale()
        t = QTransform()
        t.translate(center.x(), center.y())
        t.rotate(self._rotation)
        t.scale(sx, sy)
        t.translate(-center.x(), -center.y())
        self.setTransform(t)
        self._position_handles()

    def _position_handles(self) -> None:
        rect = self._local_rect()
        positions = {
            "corner": (rect.right(), rect.bottom()),
            "rotate": (rect.center().x(), rect.top() - ROTATE_HANDLE_OFFSET),
            "h_stretch": (rect.right(), rect.center().y()),
            "v_stretch": (rect.center().x(), rect.bottom()),
            "delete": (rect.right(), rect.top()),
        }
        for kind, (x, y) in positions.items():
            self._handles[kind].setPos(x, y)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            for handle in self._handles.values():
                handle.setVisible(bool(value))
        return super().itemChange(change, value)

    def _begin_handle_drag(self, scene_pos: QPointF) -> None:
        self._drag_snapshot = self._edit_fields()
        self._drag_start_rotation = self._rotation
        self._drag_center = self.mapToScene(self._local_rect().center())
        self._drag_start_vec = scene_pos - self._drag_center

    def _update_handle_drag(self, kind: str, scene_pos: QPointF) -> None:
        if self._drag_snapshot is None:
            return
        vec = scene_pos - self._drag_center
        if kind == "rotate":
            self._rotation = math.degrees(math.atan2(vec.y(), vec.x())) + 90.0
        elif kind == "corner":
            r = _ratio(math.hypot(vec.x(), vec.y()), math.hypot(self._drag_start_vec.x(), self._drag_start_vec.y()))
            self._apply_scale(r, r, self._drag_snapshot)
        else:
            now = _unrotate(vec, self._drag_start_rotation)
            start = _unrotate(self._drag_start_vec, self._drag_start_rotation)
            if kind == "h_stretch":
                self._apply_scale(_ratio(now.x(), start.x()), 1.0, self._drag_snapshot)
            else:
                self._apply_scale(1.0, _ratio(now.y(), start.y()), self._drag_snapshot)
        self._rebuild_transform()

    def _finish_handle_drag(self, kind: str) -> None:
        old, self._drag_snapshot = self._drag_snapshot, None
        new = self._edit_fields()
        if old is not None and old != new and callable(self.on_edited):
            self.on_edited(old, new, _LABELS[kind])


class PlacedItemMixin(TransformHandleMixin):
    """For elements placed at a `pos` and scaled via the transform matrix
    (labels, assets): shared sync of placement/transform/decoration fields.
    """

    def _init_placed(self, element) -> None:
        self.element_id = element.id
        self.setData(0, element.id)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._init_handles()

    def _sync_placed(self, element) -> None:
        self.setOpacity(element.opacity)
        self.setPos(*element.pos)
        self._rotation = element.rotation
        self._scale_x = element.scale_x
        self._scale_y = element.scale_y
        self._border = element.border
        self._outline = element.outline
        self.setVisible(element.visible)
        self._rebuild_transform()
        self.update()

    def _matrix_scale(self) -> tuple[float, float]:
        return self._scale_x, self._scale_y

    def _edit_fields(self) -> dict:
        return {"rotation": self._rotation, "scale_x": self._scale_x, "scale_y": self._scale_y}

    def _apply_scale(self, rx: float, ry: float, snapshot: dict) -> None:
        self._scale_x = max(MIN_RATIO, snapshot["scale_x"] * rx)
        self._scale_y = max(MIN_RATIO, snapshot["scale_y"] * ry)
