"""Every model edit goes through an undo command. Field edits (the vast
majority) use the edit_* helpers below so call sites never hand-build old/new
dicts or push no-op commands.
"""
from .element_commands import DeleteElementCommand
from .fields import SetElementFieldsCommand, SetLayerFieldsCommand, SetProjectFieldsCommand
from .layer_commands import DeleteLayerCommand


def _edit(command_class, undo_stack, scene, target, new_values: dict, text: str) -> None:
    command = command_class.changing(scene, target, new_values, text)
    if command is not None:
        undo_stack.push(command)


def edit_element(undo_stack, scene, element, new_values: dict, text: str = "Edit element") -> None:
    _edit(SetElementFieldsCommand, undo_stack, scene, element, new_values, text)


def edit_layer(undo_stack, scene, layer, new_values: dict, text: str = "Edit layer") -> None:
    _edit(SetLayerFieldsCommand, undo_stack, scene, layer, new_values, text)


def edit_project(undo_stack, scene, new_values: dict, text: str = "Edit map settings") -> None:
    _edit(SetProjectFieldsCommand, undo_stack, scene, scene.project, new_values, text)


def push_as_one(undo_stack, commands: list, text: str) -> None:
    """Pushes commands as a single undo step (a macro only when needed)."""
    if len(commands) == 1:
        undo_stack.push(commands[0])
    elif commands:
        undo_stack.beginMacro(text)
        for command in commands:
            undo_stack.push(command)
        undo_stack.endMacro()


def delete_items(undo_stack, scene, element_ids=(), layer_ids=()) -> None:
    """Deletes elements and whole layers as one undo step."""
    commands = [DeleteElementCommand(scene, eid) for eid in element_ids]
    commands += [DeleteLayerCommand(scene, lid) for lid in layer_ids]
    push_as_one(undo_stack, commands, f"Delete {len(commands)} item(s)")
