from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFileDialog, QWidget

from ..app_config import FONTS_DIR

FALLBACK_FAMILIES = ["Arial", "Sans Serif"]


class FontManager:
    def __init__(self):
        self._loaded_families: list[str] = []
        self.load_bundled_fonts()

    def load_bundled_fonts(self) -> None:
        if not FONTS_DIR.exists():
            return
        for font_file in sorted(FONTS_DIR.glob("*.[to]tf")):
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
            return list(self._loaded_families)
        return FALLBACK_FAMILIES

    def import_font_file(self, parent: QWidget | None = None) -> list[str]:
        path_str, _ = QFileDialog.getOpenFileName(parent, "Import Font", "", "Fonts (*.ttf *.otf)")
        if not path_str:
            return []
        return self._register_font_file(Path(path_str))
