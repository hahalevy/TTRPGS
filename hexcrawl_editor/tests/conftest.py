import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def fail_on_slot_exceptions():
    """Qt only prints exceptions raised inside signal handlers and carries
    on, so a broken handler would otherwise pass silently."""
    errors = []
    previous = sys.excepthook
    sys.excepthook = lambda *exc: errors.append(exc)
    yield
    sys.excepthook = previous
    assert not errors, "exception in a Qt handler: " + "".join(
        __import__("traceback").format_exception(*errors[0])
    )
