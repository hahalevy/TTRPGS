from __future__ import annotations

from PySide6.QtWidgets import QGraphicsItemGroup

from ..models.effects import OpacityEffect, FogOfWarEffect


class LayerGroupItem(QGraphicsItemGroup):
    """Scene-graph counterpart of a Layer model object. Holds child element items
    and applies the layer's effects (opacity, fog-of-war) to itself/its children.
    """

    def __init__(self, layer_id: str):
        super().__init__()
        self.layer_id = layer_id
        self.setHandlesChildEvents(False)

    def apply_effects(self, effects: list) -> None:
        # Reset to defaults, then apply each effect in order.
        self.setOpacity(1.0)
        for effect in effects:
            if isinstance(effect, OpacityEffect):
                self.setOpacity(effect.value)
            elif isinstance(effect, FogOfWarEffect):
                # Fog rendering itself lives on the FogMaskItem child; nothing to
                # do at the group level beyond ensuring the child exists (handled
                # by the scene when it rebuilds elements).
                pass
