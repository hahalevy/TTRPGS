"""Factory defaults, read from resources/defaults.json. Pure Python (no Qt), so
the data model can use them for its field defaults.

    DEFAULTS["label"]["font_size"]   # -> 30

This module only reads the shipped file; what the user last used is stored
per project (see app_config).
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULTS_FILE = Path(__file__).resolve().parent.parent / "resources" / "defaults.json"

DEFAULTS: dict = {k: v for k, v in json.loads(DEFAULTS_FILE.read_text(encoding="utf-8")).items() if not k.startswith("_")}
