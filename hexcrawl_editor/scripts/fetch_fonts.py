"""Fetches the bundled fonts from Google Fonts' open repository (all SIL Open Font
License 1.1) into resources/fonts/<Family>/, each with its OFL.txt - the license
requires shipping it with the font - and rewrites resources/fonts/ATTRIBUTION.md.
To add a font: find its folder under https://github.com/google/fonts/tree/main/ofl,
add "Family Name": ("folder", "File.ttf") below, rerun from the hexcrawl_editor
folder:  python scripts/fetch_fonts.py
Variable fonts (names with [axes]) work; their default style is what gets used.
"""
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl"

FONTS = {
    "Clean": {
        "Open Sans": ("opensans", "OpenSans[wdth,wght].ttf"),
    },
    "Classical serif": {
        "EB Garamond": ("ebgaramond", "EBGaramond[wght].ttf"),
        "Caudex": ("caudex", "Caudex-Regular.ttf"),
        "IM Fell English": ("imfellenglish", "IMFeENrm28P.ttf"),
        "IM Fell DW Pica": ("imfelldwpica", "IMFePIrm28P.ttf"),
    },
    "Inscriptional": {
        "Cinzel": ("cinzel", "Cinzel[wght].ttf"),
        "Cinzel Decorative": ("cinzeldecorative", "CinzelDecorative-Regular.ttf"),
        "Metamorphous": ("metamorphous", "Metamorphous-Regular.ttf"),
    },
    "Medieval and fantasy": {
        "MedievalSharp": ("medievalsharp", "MedievalSharp.ttf"),
        "Uncial Antiqua": ("uncialantiqua", "UncialAntiqua-Regular.ttf"),
        "Almendra": ("almendra", "Almendra-Regular.ttf"),
        "Macondo": ("macondo", "Macondo-Regular.ttf"),
        "Lancelot": ("lancelot", "Lancelot-Regular.ttf"),
        "Texturina": ("texturina", "Texturina[opsz,wght].ttf"),
    },
    "Blackletter": {
        "Pirata One": ("pirataone", "PirataOne-Regular.ttf"),
        "Grenze Gotisch": ("grenzegotisch", "GrenzeGotisch[wght].ttf"),
    },
    "Handwritten and display": {
        "Fondamento": ("fondamento", "Fondamento-Regular.ttf"),
        "Jim Nightshade": ("jimnightshade", "JimNightshade-Regular.ttf"),
        "Eagle Lake": ("eaglelake", "EagleLake-Regular.ttf"),
        "Jolly Lodger": ("jollylodger", "JollyLodger-Regular.ttf"),
    },
}


def download(folder: str, filename: str) -> bytes:
    url = f"{BASE}/{folder}/{urllib.parse.quote(filename)}"
    data = urllib.request.urlopen(url, timeout=30).read()
    time.sleep(0.15)  # be polite to the host
    return data


def main() -> None:
    root = Path(__file__).resolve().parent.parent / "resources" / "fonts"
    failed = []
    for group in FONTS.values():
        for family, (folder, filename) in group.items():
            try:
                font, license_text = download(folder, filename), download(folder, "OFL.txt")
                assert font[:4] in (b"\x00\x01\x00\x00", b"OTTO", b"true"), "not a font file"
                assert b"SIL OPEN FONT LICENSE" in license_text.upper()
            except Exception as exc:
                failed.append((family, exc))
                continue
            target = root / family
            target.mkdir(parents=True, exist_ok=True)
            (target / filename).write_bytes(font)
            (target / "OFL.txt").write_bytes(license_text)

    lines = ["# Font attribution", "",
             "Fonts from [Google Fonts](https://github.com/google/fonts), each licensed under the",
             "[SIL Open Font License 1.1](https://openfontlicense.org). Unmodified; each family's own",
             "`OFL.txt` (with its copyright notice) sits in its folder and must stay with the font.", ""]
    for group_name, group in FONTS.items():
        lines += [f"## {group_name}", "", "| Family | Source |", "|---|---|"]
        for family, (folder, _filename) in group.items():
            lines.append(f"| {family} | [{folder}](https://github.com/google/fonts/tree/main/ofl/{folder}) |")
        lines.append("")
    (root / "ATTRIBUTION.md").write_text("\n".join(lines), encoding="utf-8")
    print("fonts:", sum(len(g) for g in FONTS.values()) - len(failed), "failed:", failed)


if __name__ == "__main__":
    main()
