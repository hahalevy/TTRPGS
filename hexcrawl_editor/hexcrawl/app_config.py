from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

APP_ORG = "HahaLevyGames"
APP_NAME = "HexcrawlEditor"

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = PACKAGE_ROOT / "resources"
MAPS_DIR = RESOURCES_DIR / "maps"
FONTS_DIR = RESOURCES_DIR / "fonts"
ASSETS_DIR = RESOURCES_DIR / "assets"


class _Preferences(QObject):
    loaded = Signal()  # a different project's preferences are now in effect


preferences = _Preferences()
_current: dict = {}


def use_preferences(data: dict) -> None:
    """Makes `data` (a project's own preferences dict) the place last-used values
    are read from and written to, and tells every panel to reload. Anything not
    in it falls back to the factory defaults in resources/defaults.json."""
    global _current
    _current = data
    preferences.loaded.emit()


def remembered(key: str, default=None):
    """A last-used value saved in the current project (any JSON-able value), or `default`."""
    return _current.get(key, default)


def remember(key: str, value) -> None:
    _current[key] = value
