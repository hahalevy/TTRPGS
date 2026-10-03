"""The one undo command for every field edit, on any kind of model object.
Subclasses only say how to find the object again and what to refresh."""
from __future__ import annotations

import copy

from PySide6.QtGui import QUndoCommand


class SetFieldsCommand(QUndoCommand):
    """Sets fields on a model object; values are deep-copied so later edits
    can never mutate an undo snapshot."""

    def __init__(self, scene, key, old_values: dict, new_values: dict, text: str = "Edit"):
        super().__init__(text)
        self.scene = scene
        self.key = key
        self.old_values = copy.deepcopy(old_values)
        self.new_values = copy.deepcopy(new_values)

    @classmethod
    def changing(cls, scene, target, new_values: dict, text: str = "Edit"):
        """Builds the command from the target's current values, or None if
        nothing would change."""
        old_values = {key: getattr(target, key) for key in new_values}
        if old_values == new_values:
            return None
        return cls(scene, cls.key_of(target), old_values, new_values, text)

    @staticmethod
    def key_of(target):
        return target.id

    def target(self):
        raise NotImplementedError

    def refresh(self) -> None:
        raise NotImplementedError

    def _apply(self, values: dict) -> None:
        target = self.target()
        if target is None:
            return
        for key, value in copy.deepcopy(values).items():
            setattr(target, key, value)
        self.refresh()

    def redo(self) -> None:
        self._apply(self.new_values)

    def undo(self) -> None:
        self._apply(self.old_values)


class SetElementFieldsCommand(SetFieldsCommand):
    def target(self):
        return self.scene.element_for_id(self.key)

    def refresh(self) -> None:
        self.scene.refresh_element(self.key)


class SetLayerFieldsCommand(SetFieldsCommand):
    def target(self):
        return self.scene.project.find_layer(self.key)

    def refresh(self) -> None:
        self.scene.refresh_layer_effects(self.key)


class SetProjectFieldsCommand(SetFieldsCommand):
    @staticmethod
    def key_of(target):
        return None

    def target(self):
        return self.scene.project

    def refresh(self) -> None:
        self.scene.refresh_project()
