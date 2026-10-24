from __future__ import annotations

from dataclasses import dataclass, field

from ..defaults import DEFAULTS
from .layer import Layer

SCHEMA_VERSION = 1


@dataclass
class Project:
    schema_version: int = SCHEMA_VERSION
    name: str = "Untitled Hexcrawl"
    base_map_path: str = ""
    base_map_size: tuple[int, int] = (0, 0)
    background_color: str = DEFAULTS["project"]["background_color"]  # canvas color shown behind (and through a faded) base map
    layers: list[Layer] = field(default_factory=list)
    # Last-used tool values (colors, fonts, widths, recent items), saved with the project.
    preferences: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "base_map_path": self.base_map_path,
            "base_map_size": list(self.base_map_size),
            "background_color": self.background_color,
            "layers": [layer.to_dict() for layer in self.layers],
            "preferences": self.preferences,
        }

    @staticmethod
    def from_dict(data: dict) -> "Project":
        return Project(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            name=data.get("name", "Untitled Hexcrawl"),
            base_map_path=data.get("base_map_path", ""),
            base_map_size=tuple(data.get("base_map_size", (0, 0))),
            background_color=data.get("background_color", DEFAULTS["project"]["background_color"]),
            layers=[Layer.from_dict(l) for l in data.get("layers", [])],
            preferences=dict(data.get("preferences", {})),
        )

    def find_layer(self, layer_id: str) -> Layer | None:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None
