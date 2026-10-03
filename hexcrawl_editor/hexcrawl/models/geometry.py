"""Plain JSON-friendly geometry value types. No Qt imports here."""
from __future__ import annotations

PointTuple = tuple[float, float]
RectTuple = tuple[float, float, float, float]  # x, y, w, h
