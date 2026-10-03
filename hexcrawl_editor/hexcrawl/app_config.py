from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

APP_ORG = "HahaLevyGames"
APP_NAME = "HexcrawlEditor"

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PACKAGE_ROOT / "resources"
MAPS_DIR = RESOURCES_DIR / "maps"
FONTS_DIR = RESOURCES_DIR / "fonts"
ASSETS_DIR = RESOURCES_DIR / "assets"

DEFAULT_FONT_FAMILY = "Open Sans"
DEFAULT_FONT_SIZE = 14
DEFAULT_FONT_COLOR = "#000000"


def get_settings() -> QSettings:
    return QSettings(APP_ORG, APP_NAME)
