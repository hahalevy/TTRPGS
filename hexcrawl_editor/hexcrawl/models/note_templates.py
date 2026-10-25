"""Note templates, read from resources/note_templates.json and turned into
the same HTML the editor stores, so a template is just ordinary note text."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

TEMPLATES_FILE = Path(__file__).resolve().parent.parent.parent / "resources" / "note_templates.json"

# Qt's own markers for an empty paragraph / list item; without them the HTML
# importer drops them (or fills them with a line-separator character).
_EMPTY = ' style="-qt-paragraph-type:empty;"'
_LISTS = {"numbered": "ol", "bullets": "ul"}


def load_templates(path: Path = TEMPLATES_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["templates"]


def render_template(template: dict) -> str:
    parts = []
    for section in template["sections"]:
        if section.get("heading"):
            parts.append(f"<h2>{escape(section['heading'])}</h2>")
        for label in section.get("fields", []):
            parts.append(f"<p><b>{escape(label)}:</b> </p>")
        tag = _LISTS.get(section.get("kind", "text"))
        if tag:
            parts.append(f"<{tag}><li{_EMPTY}><br /></li></{tag}>")
        elif not section.get("fields"):
            parts.append(f"<p{_EMPTY}><br /></p>")
    return "\n".join(parts)
