"""JSON (de)serialization for Project. Pure, no Qt, no filesystem I/O."""
from __future__ import annotations

import json

from ..models.project import Project


def project_to_json(project: Project) -> str:
    return json.dumps(project.to_dict(), indent=2)


def project_from_json(text: str) -> Project:
    return Project.from_dict(json.loads(text))
