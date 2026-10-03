from __future__ import annotations

from dataclasses import dataclass, field

from .elements import Element, new_id
from .effects import LayerEffect


@dataclass
class Layer:
    id: str = field(default_factory=new_id)
    name: str = "New Layer"
    visible: bool = True
    locked: bool = False
    base_map: bool = False  # the bottom layer showing the project's base map image; not drawable
    elements: list[Element] = field(default_factory=list)
    effects: list[LayerEffect] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "visible": self.visible,
            "locked": self.locked,
            "base_map": self.base_map,
            "elements": [e.to_dict() for e in self.elements],
            "effects": [eff.to_dict() for eff in self.effects],
        }

    @staticmethod
    def from_dict(data: dict) -> "Layer":
        return Layer(
            id=data.get("id", new_id()),
            name=data.get("name", "New Layer"),
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            base_map=data.get("base_map", False),
            elements=[Element.from_dict(e) for e in data.get("elements", [])],
            effects=[LayerEffect.from_dict(e) for e in data.get("effects", [])],
        )

    def find_element(self, element_id: str) -> Element | None:
        for e in self.elements:
            if e.id == element_id:
                return e
        return None
