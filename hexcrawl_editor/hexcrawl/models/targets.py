"""Human-readable names for layers and elements (shared by the layer panel and notes)."""
from __future__ import annotations

from .project import Project

KIND_LABELS = {
    "stroke": "Line",
    "shape": "Shape",
    "label": "Label",
    "asset": "Asset",
    "fog": "Effect",
}


def element_title(element) -> str:
    if element.name:
        return element.name
    if element.kind == "label" and element.text:
        return f'Label "{element.text}"'
    return KIND_LABELS.get(element.kind, element.kind)


def target_label(project: Project, target_id: str) -> str:
    """"Layer > Element" for an element, the layer's name for a layer, "" if it no longer exists."""
    layer = project.find_layer(target_id)
    if layer is not None:
        return layer.name
    for layer in project.layers:
        element = layer.find_element(target_id)
        if element is not None:
            return f"{layer.name} > {element_title(element)}"
    return ""
