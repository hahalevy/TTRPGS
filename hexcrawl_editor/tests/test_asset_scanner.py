import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hexcrawl.ui.asset_scanner import scan_assets


def test_scan_empty_folder_does_not_raise(tmp_path):
    result = scan_assets(tmp_path / "does_not_exist")
    assert result == {}


def test_scan_detects_categories_and_counts(tmp_path):
    settlements = tmp_path / "Settlements"
    wilderness = tmp_path / "Wilderness"
    settlements.mkdir()
    wilderness.mkdir()
    (settlements / "town.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (settlements / "ruin.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (wilderness / "lair.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "not_an_image.txt").write_text("ignore me")

    result = scan_assets(tmp_path)

    assert set(result.keys()) == {"Settlements", "Wilderness"}
    assert len(result["Settlements"]) == 2
    assert len(result["Wilderness"]) == 1
    assert result["Settlements"][0].relative_path.startswith("Settlements/")


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        test_scan_empty_folder_does_not_raise(Path(d))
    with tempfile.TemporaryDirectory() as d:
        test_scan_detects_categories_and_counts(Path(d))
    print("OK")
