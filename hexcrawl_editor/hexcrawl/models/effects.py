"""Per-layer effects. Pure dataclasses, no Qt imports; serialization is
generic, so a new effect type is just a new dataclass + registry entry."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class LayerEffect:
    kind: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "LayerEffect":
        return _EFFECT_KINDS.get(data.get("kind"), LayerEffect)(**data)


@dataclass
class OpacityEffect(LayerEffect):
    kind: str = "opacity"
    value: float = 1.0


@dataclass
class FogOfWarEffect(LayerEffect):
    kind: str = "fog_of_war"
    mask_element_id: str | None = None


_EFFECT_KINDS: dict[str, type[LayerEffect]] = {cls.kind: cls for cls in (OpacityEffect, FogOfWarEffect)}
