from __future__ import annotations

from PySide6.QtGui import QUndoCommand

from ..models.elements import Element


class AddElementCommand(QUndoCommand):
    def __init__(self, scene, layer_id: str, element: Element, text: str = "Add element"):
        super().__init__(text)
        self.scene = scene
        self.layer_id = layer_id
        self.element = element

    def redo(self) -> None:
        self.scene.add_element(self.layer_id, self.element)

    def undo(self) -> None:
        self.scene.remove_element(self.element.id)


class DeleteElementCommand(QUndoCommand):
    def __init__(self, scene, element_id: str, text: str = "Delete element"):
        super().__init__(text)
        self.scene = scene
        self.element_id = element_id
        self.layer_id = None
        self.element = None
        self.index = 0

    def redo(self) -> None:
        layer = self.scene.layer_for_element(self.element_id)
        self.layer_id = layer.id
        self.element = self.scene.element_for_id(self.element_id)
        self.index = layer.elements.index(self.element)
        self.scene.remove_element(self.element_id)

    def undo(self) -> None:
        if self.layer_id and self.element is not None:
            self.scene.insert_element(self.layer_id, self.element, self.index)
