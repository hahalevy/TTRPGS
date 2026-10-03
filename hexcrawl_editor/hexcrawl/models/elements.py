"""Element model: strokes, shapes, labels, assets, fog masks.

Pure dataclasses, zero Qt imports, so the model can be unit tested headlessly.
Serialization is generic (driven by the dataclass fields), so adding a field
to an element type needs no extra (de)serialization code.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, fields


def new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class DecorationStyle:
    """Shared border/outline style used by LabelElement and AssetElement."""

    enabled: bool = False
    color: str = "#000000"
    width: float = 2.0

    def to_dict(self) -> dict:
        return {"enabled": self.enabled, "color": self.color, "width": self.width}

    @staticmethod
    def from_dict(data: dict | None) -> "DecorationStyle":
        return DecorationStyle(**(data or {}))


Point = tuple[float, float]

# Converters from JSON values back to model values, keyed by field annotation.
_FROM_JSON = {
    "DecorationStyle": DecorationStyle.from_dict,
    "Point": tuple,
    "list[Point]": lambda pts: [tuple(p) for p in pts],
    "list[dict]": lambda items: [dict(i) for i in items],
}


def _to_json(value):
    if isinstance(value, DecorationStyle):
        return value.to_dict()
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return [_to_json(v) for v in value]
    if isinstance(value, dict):
        return dict(value)
    return value


@dataclass
class Element:
    kind: str = ""
    id: str = field(default_factory=new_id)
    visible: bool = True
    name: str = ""
    z: int = 0

    def to_dict(self) -> dict:
        return {f.name: _to_json(getattr(self, f.name)) for f in fields(self)}

    @staticmethod
    def from_dict(data: dict) -> "Element":
        cls = _ELEMENT_KINDS.get(data.get("kind"))
        if cls is None:
            raise ValueError(f"Unknown element kind: {data.get('kind')!r}")
        kwargs = {}
        for f in fields(cls):
            if f.name in data:
                convert = _FROM_JSON.get(f.type)
                kwargs[f.name] = convert(data[f.name]) if convert else data[f.name]
        return cls(**kwargs)

    def translated(self, dx: float, dy: float) -> dict:
        """Field values that move this element by (dx, dy); {} if immovable."""
        return {}

    def cloned(self, dx: float = 0.0, dy: float = 0.0) -> "Element":
        """An independent copy with a new id, moved by (dx, dy)."""
        copy = Element.from_dict({**self.to_dict(), "id": new_id()})
        for key, value in copy.translated(dx, dy).items():
            setattr(copy, key, value)
        return copy


@dataclass
class StrokeElement(Element):
    kind: str = "stroke"
    points: list[Point] = field(default_factory=list)
    color: str = "#000000"
    width: float = 3.0
    line_style: str = "solid"  # "solid" | "dashed" | "dotted"
    rotation: float = 0.0

    def translated(self, dx: float, dy: float) -> dict:
        return {"points": [(x + dx, y + dy) for x, y in self.points]}


@dataclass
class ShapeElement(Element):
    kind: str = "shape"
    shape_type: str = "line"  # "line" | "rectangle" | "ellipse" | "triangle"
    p1: Point = (0.0, 0.0)
    p2: Point = (0.0, 0.0)
    color: str = "#000000"
    width: float = 3.0
    line_style: str = "solid"
    filled: bool = False
    fill_color: str | None = None
    rotation: float = 0.0

    def translated(self, dx: float, dy: float) -> dict:
        return {
            "p1": (self.p1[0] + dx, self.p1[1] + dy),
            "p2": (self.p2[0] + dx, self.p2[1] + dy),
        }


@dataclass
class LabelElement(Element):
    kind: str = "label"
    text: str = ""
    pos: Point = (0.0, 0.0)
    font_family: str = "Open Sans"
    font_size: int = 14
    font_color: str = "#000000"
    opacity: float = 1.0
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    border: DecorationStyle = field(default_factory=DecorationStyle)
    outline: DecorationStyle = field(default_factory=DecorationStyle)

    def translated(self, dx: float, dy: float) -> dict:
        return {"pos": (self.pos[0] + dx, self.pos[1] + dy)}


@dataclass
class AssetElement(Element):
    kind: str = "asset"
    asset_path: str = ""  # relative to resources/assets
    pos: Point = (0.0, 0.0)
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    border: DecorationStyle = field(default_factory=DecorationStyle)
    outline: DecorationStyle = field(default_factory=DecorationStyle)

    def translated(self, dx: float, dy: float) -> dict:
        return {"pos": (self.pos[0] + dx, self.pos[1] + dy)}


@dataclass
class FogMaskElement(Element):
    """One per fog layer: an ordered list of rectangles, each "hide" or
    "reveal" (see canvas/fog_paint.py for how they combine).
    """

    kind: str = "fog"
    regions: list[dict] = field(default_factory=list)  # [{"rect": [x,y,w,h], "mode": "hide"|"reveal"}]
    color: str = "#000000"
    base_opacity: float = 1.0


_ELEMENT_KINDS: dict[str, type[Element]] = {
    cls.kind: cls for cls in (StrokeElement, ShapeElement, LabelElement, AssetElement, FogMaskElement)
}
