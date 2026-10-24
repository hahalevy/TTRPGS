"""Canvas items for point-defined elements: freehand lines and shapes.

Both store their geometry as absolute points in the model, so stretching
remaps those points around the center (pen width stays constant, unlike
scaling a matrix) while rotation is a centered transform. Everything else -
handles, drag math, selection - comes from TransformHandleMixin.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from ...models.elements import Element, ShapeElement, StrokeElement
from .handles import TransformHandleMixin

Point = tuple[float, float]

_LINE_STYLES = {"solid": Qt.PenStyle.SolidLine, "dashed": Qt.PenStyle.DashLine, "dotted": Qt.PenStyle.DotLine}


def pen_from_style(color: str, width: float, line_style: str) -> QPen:
    pen = QPen(QColor(color))
    pen.setWidthF(max(width, 0.1))
    pen.setStyle(_LINE_STYLES.get(line_style, Qt.PenStyle.SolidLine))
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def path_for_shape(shape_type: str, p1: Point, p2: Point) -> QPainterPath:
    path = QPainterPath()
    (x1, y1), (x2, y2) = p1, p2
    left, top, right, bottom = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
    if shape_type == "line":
        path.moveTo(x1, y1)
        path.lineTo(x2, y2)
    elif shape_type == "rectangle":
        path.addRect(left, top, right - left, bottom - top)
    elif shape_type == "ellipse":
        path.addEllipse(left, top, right - left, bottom - top)
    elif shape_type == "triangle":
        path.moveTo((left + right) / 2, top)
        path.lineTo(right, bottom)
        path.lineTo(left, bottom)
        path.closeSubpath()
    return path


def path_for_polyline(points: list[Point]) -> QPainterPath:
    path = QPainterPath()
    if points:
        path.moveTo(*points[0])
        for pt in points[1:]:
            path.lineTo(*pt)
    return path


class PathElementItem(TransformHandleMixin, QGraphicsPathItem):
    """Subclasses define how points map to a path and to model fields."""

    def __init__(self, element: Element):
        super().__init__()
        self.element_id = element.id
        self.setData(0, element.id)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._points: list[Point] = []
        self._init_handles()
        self.sync_from_element(element)

    def _points_of(self, element) -> list[Point]:
        raise NotImplementedError

    def _fields_for(self, points: list[Point]) -> dict:
        raise NotImplementedError

    def _path_for(self, points: list[Point]) -> QPainterPath:
        raise NotImplementedError

    def _style(self, element) -> None:
        self.setPen(pen_from_style(element.color, element.width, element.line_style))

    def sync_from_element(self, element) -> None:
        self._points = [tuple(p) for p in self._points_of(element)]
        self._rotation = element.rotation
        self.setPos(0, 0)  # placement lives in the points; pos is only a transient drag offset
        self.setPath(self._path_for(self._points))
        self._style(element)
        self.setVisible(element.visible)
        self._rebuild_transform()

    # --- TransformHandleMixin hooks ---
    def _local_rect(self) -> QRectF:
        xs = [p[0] for p in self._points] or [0.0]
        ys = [p[1] for p in self._points] or [0.0]
        return QRectF(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    def _edit_fields(self) -> dict:
        return {**self._fields_for(self._points), "rotation": self._rotation}

    def _apply_scale(self, rx: float, ry: float, snapshot: dict) -> None:
        start_points = self._points_of_fields(snapshot)
        xs, ys = [p[0] for p in start_points], [p[1] for p in start_points]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        self._points = [(cx + (x - cx) * rx, cy + (y - cy) * ry) for x, y in start_points]
        self.setPath(self._path_for(self._points))

    def _points_of_fields(self, fields: dict) -> list[Point]:
        raise NotImplementedError


class StrokeItem(PathElementItem):
    def _points_of(self, element: StrokeElement) -> list[Point]:
        return element.points

    def _points_of_fields(self, fields: dict) -> list[Point]:
        return fields["points"]

    def _fields_for(self, points: list[Point]) -> dict:
        return {"points": list(points)}

    def _path_for(self, points: list[Point]) -> QPainterPath:
        return path_for_polyline(points)


class ShapeItem(PathElementItem):
    def _points_of(self, element: ShapeElement) -> list[Point]:
        self._shape_type = element.shape_type
        return [element.p1, element.p2]

    def _points_of_fields(self, fields: dict) -> list[Point]:
        return [fields["p1"], fields["p2"]]

    def _fields_for(self, points: list[Point]) -> dict:
        return {"p1": points[0], "p2": points[1]}

    def _path_for(self, points: list[Point]) -> QPainterPath:
        return path_for_shape(self._shape_type, points[0], points[1])

    def _style(self, element: ShapeElement) -> None:
        super()._style(element)
        self.setBrush(QBrush(QColor(element.fill_color)) if element.filled and element.fill_color else QBrush())
