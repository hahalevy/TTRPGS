import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hexcrawl.models.elements import (
    StrokeElement, ShapeElement, LabelElement, AssetElement, FogMaskElement, DecorationStyle,
)
from hexcrawl.models.layer import Layer
from hexcrawl.models.effects import OpacityEffect, FogOfWarEffect
from hexcrawl.models.project import Project
from hexcrawl.io.project_serializer import project_to_json, project_from_json


def build_sample_project() -> Project:
    fog_mask = FogMaskElement(
        id="e010", name="Fog Mask", regions=[{"rect": [800, 600, 400, 300], "mode": "hide"}],
    )
    fog_layer = Layer(
        id="f9f9f9", name="Fog of War",
        elements=[fog_mask],
        effects=[FogOfWarEffect(mask_element_id=fog_mask.id)],
    )

    terrain_layer = Layer(
        id="a1b2c3", name="Terrain Notes",
        effects=[OpacityEffect(value=0.85)],
        elements=[
            StrokeElement(id="e001", name="Stroke 1", points=[(120.0, 340.0), (128.5, 345.0)], color="#1E90FF", width=4.0),
            ShapeElement(id="e002", name="Rect 1", shape_type="rectangle", p1=(10, 10), p2=(50, 50), line_style="dashed"),
            LabelElement(
                id="e003", name="Label: Ruins of Kael", text="Ruins of Kael", pos=(512.0, 300.0),
                font_color="#B00000", border=DecorationStyle(enabled=True, color="#FFFFFF", width=2.0),
                outline=DecorationStyle(enabled=True, color="#000000", width=1.5),
            ),
            AssetElement(id="e004", name="Asset: ruin", asset_path="Settlements/ruin.png", pos=(400, 400), rotation=15.0),
        ],
    )

    return Project(
        name="Erillion Campaign",
        base_map_path="../../resources/maps/Echoes03_Erillion_GM.png",
        base_map_size=(4096, 3072),
        background_color="#f0e6d2",
        layers=[terrain_layer, fog_layer],
    )


def test_roundtrip_equal():
    project = build_sample_project()
    text = project_to_json(project)
    restored = project_from_json(text)
    assert restored == project


def test_roundtrip_preserves_element_kinds():
    project = build_sample_project()
    restored = project_from_json(project_to_json(project))
    kinds = [e.kind for e in restored.layers[0].elements]
    assert kinds == ["stroke", "shape", "label", "asset"]
    assert restored.layers[1].elements[0].kind == "fog"



def test_cloned_is_independent_moved_copy():
    from hexcrawl.models.elements import StrokeElement

    original = StrokeElement(points=[(0, 0), (10, 5)], color="#ff0000")
    copy = original.cloned(3, 4)
    assert copy.id != original.id and copy.color == "#ff0000"
    assert copy.points == [(3, 4), (13, 9)] and original.points == [(0, 0), (10, 5)]
