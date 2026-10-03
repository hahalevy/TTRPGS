from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from ..models.layer import Layer


class AddLayerCommand(QUndoCommand):
    def __init__(self, scene, layer: Layer, text: str = "Add layer"):
        super().__init__(text)
        self.scene = scene
        self.layer = layer

    def redo(self) -> None:
        self.scene.insert_layer(self.layer, len(self.scene.project.layers))

    def undo(self) -> None:
        self.scene.remove_layer(self.layer.id)


class DeleteLayerCommand(QUndoCommand):
    def __init__(self, scene, layer_id: str, text: str = "Delete layer"):
        super().__init__(text)
        self.scene = scene
        self.layer_id = layer_id
        self.layer: Layer | None = None
        self.index = 0

    def redo(self) -> None:
        self.layer = self.scene.project.find_layer(self.layer_id)
        self.index = self.scene.project.layers.index(self.layer) if self.layer else 0
        self.scene.remove_layer(self.layer_id)

    def undo(self) -> None:
        if self.layer is not None:
            self.scene.insert_layer(self.layer, self.index)
