import json
import zipfile
from pathlib import Path

from hexcrawl.io.project_file import load_project, save_project
from hexcrawl.models.effects import OpacityEffect
from hexcrawl.models.layer import Layer
from hexcrawl.models.project import Project


def test_save_load_roundtrip_with_relative_base_map(tmp_path):
    base_map = tmp_path / "maps" / "sample.png"
    base_map.parent.mkdir()
    base_map.write_bytes(b"\x89PNG\r\n\x1a\n")
    project_path = tmp_path / "projects" / "sub" / "campaign.hexproj"

    base_layer = Layer(name="Base Map", base_map=True, effects=[OpacityEffect(value=0.5)])
    project = Project(name="Test", base_map_path=str(base_map), layers=[base_layer, Layer(name="Layer 1")])
    save_project(project, project_path)

    on_disk = json.loads(zipfile.ZipFile(project_path).read("project.json"))
    assert on_disk["base_map_path"] == "../../maps/sample.png"  # stored relative
    assert project.base_map_path == str(base_map)  # in-memory project untouched

    loaded = load_project(project_path)
    assert Path(loaded.base_map_path) == base_map.resolve()
    assert loaded.layers[0].base_map and loaded.layers[0].effects == [OpacityEffect(value=0.5)]


def test_project_without_base_map(tmp_path):
    path = tmp_path / "p.hexproj"
    save_project(Project(layers=[Layer()]), path)
    assert load_project(path).base_map_path == ""
