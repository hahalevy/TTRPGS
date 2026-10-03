"""`.hexproj` = a zip holding project.json. In memory `project.base_map_path`
is always absolute; on disk it is stored relative to the project file so a
project folder can be moved as a whole.
"""
from __future__ import annotations

import os
import zipfile
from dataclasses import replace
from pathlib import Path, PurePosixPath

from ..models.project import Project
from .project_serializer import project_from_json, project_to_json

PROJECT_ENTRY_NAME = "project.json"


def save_project(project: Project, path: Path) -> None:
    on_disk = project
    if project.base_map_path:
        relative = os.path.relpath(project.base_map_path, path.parent).replace("\\", "/")
        on_disk = replace(project, base_map_path=str(PurePosixPath(relative)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(PROJECT_ENTRY_NAME, project_to_json(on_disk))


def load_project(path: Path) -> Project:
    """The caller should prompt for the base map if base_map_path doesn't exist."""
    with zipfile.ZipFile(path, "r") as zf:
        project = project_from_json(zf.read(PROJECT_ENTRY_NAME).decode("utf-8"))
    if project.base_map_path:
        project.base_map_path = str((path.parent / project.base_map_path).resolve())
    return project
