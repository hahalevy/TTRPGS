from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF


def export_png(scene, output_path: Path, scope_rect: QRectF | None, resolution: tuple[int, int] | None) -> None:
    """Flattens what is currently visible to a PNG, using the scene's own
    rendering - so the export always matches the canvas exactly.

    scope_rect: None = the whole base map; otherwise a scene-space crop.
    resolution: None = native pixel density of the scope; otherwise (w, h).
    """
    source = scope_rect if scope_rect is not None else scene.map_bounds()
    width, height = resolution or (max(1, round(source.width())), max(1, round(source.height())))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    scene.render_image(source, width, height).save(str(output_path), "PNG")
