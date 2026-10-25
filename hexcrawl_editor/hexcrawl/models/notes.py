"""Notes: rich-text documents that live on the project, not on the map.

A note may point at a layer or an element through `target_id` (ids are unique
across both). The note never depends on its target: if the target is deleted
the note simply stays, and `Project.is_attached` says it is dangling.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

from .elements import new_id

NOTE_LINK_PREFIX = "note:"  # href scheme of a hyperlink to another note


@dataclass
class Note:
    id: str = field(default_factory=new_id)
    title: str = "Untitled note"
    target_id: str = ""  # layer or element id; "" = not attached
    html: str = ""  # body, as written by QTextDocument.toHtml()
    images: dict = field(default_factory=dict)  # name used in `html` -> base64 PNG

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Note":
        known = {f.name for f in fields(Note)}
        return Note(**{k: v for k, v in data.items() if k in known})
