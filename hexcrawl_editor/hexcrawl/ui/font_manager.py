from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFileDialog, QWidget

from ..app_config import FONTS_DIR

FALLBACK_FAMILIES = ["Arial", "Sans Serif"]
FONT_EXTENSIONS = {".ttf", ".otf"}


class FontManager:
    def __init__(self):
        self._loaded_families: list[str] = []
        self.load_bundled_fonts()

    def load_bundled_fonts(self) -> None:
        if not FONTS_DIR.exists():
            return
        # One subfolder per family (each keeps its license); loose files work too.
        for font_file in sorted(p for p in FONTS_DIR.rglob("*") if p.suffix.lower() in FONT_EXTENSIONS):
            self._register_font_file(font_file)

    def _register_font_file(self, path: Path) -> list[str]:
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            return []
        families = QFontDatabase.applicationFontFamilies(font_id)
        for family in families:
            if family not in self._loaded_families:
                self._loaded_families.append(family)
        return families

    def available_families(self) -> list[str]:
        if self._loaded_families:
            return sorted(self._loaded_families, key=str.casefold)
        return FALLBACK_FAMILIES

    def import_font_file(self, parent: QWidget | None = None) -> list[str]:
        path_str, _ = QFileDialog.getOpenFileName(parent, "Import Font", "", "Fonts (" + " ".join(f"*{e}" for e in sorted(FONT_EXTENSIONS)) + ")")
        if not path_str:
            return []
        return self._register_font_file(Path(path_str))
