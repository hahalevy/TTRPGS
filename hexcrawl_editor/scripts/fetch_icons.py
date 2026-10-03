"""Fetches the starter icon library from game-icons.net (CC BY 3.0) into
resources/assets/<Category>/ and rewrites resources/assets/ATTRIBUTION.md.
To add an icon: find it on game-icons.net, add "Name": "author/icon" below, rerun
from the hexcrawl_editor folder:  python scripts/fetch_icons.py
"""
import time, urllib.request
from pathlib import Path

ICONS = {
    "Structures": {
        "City": "caro-asercion/medieval-village-01", "Castle": "delapouite/castle", "Keep": "delapouite/tower-flag",
        "Village": "delapouite/village", "Hamlet": "delapouite/huts-village", "Manor": "delapouite/family-house",
        "House": "delapouite/house", "Hut": "delapouite/hut", "Farm": "delapouite/barn",
        "Ruins": "delapouite/ancient-ruins", "Castle Ruins": "delapouite/castle-ruins", "Ruined Wall": "delapouite/broken-wall",
        "Temple": "delapouite/greek-temple", "Church": "delapouite/church", "Shrine": "delapouite/shinto-shrine",
        "Pagoda": "delapouite/pagoda", "Pyramid": "delapouite/mayan-pyramid", "Obelisk": "delapouite/obelisk",
        "Standing Stone": "lorc/rune-stone", "Watchtower": "delapouite/watchtower", "Wizard Tower": "delapouite/evil-tower",
        "Fort": "delapouite/military-fort", "Hill Fort": "delapouite/hill-fort", "City Gate": "delapouite/medieval-gate",
        "Lighthouse": "delapouite/lighthouse", "Windmill": "delapouite/windmill", "Watermill": "caro-asercion/water-mill",
        "Tavern": "delapouite/tavern-sign", "Harbor": "delapouite/harbor-dock", "Bridge": "delapouite/stone-bridge",
        "Mine": "delapouite/gold-mine", "Cave": "delapouite/cave-entrance", "Dungeon": "delapouite/dungeon-gate",
        "Crypt": "delapouite/crypt-entrance", "Graveyard": "delapouite/graveyard", "Camp": "delapouite/camping-tent",
        "Well": "delapouite/well",
    },
    "Terrain": {
        "Forest": "delapouite/forest", "Pine Tree": "lorc/pine-tree", "Birch Trees": "caro-asercion/birch-trees",
        "Jungle": "delapouite/jungle", "Palm Tree": "delapouite/palm-tree", "Fungal Forest": "delapouite/mushrooms",
        "Hills": "delapouite/hills", "Mountains": "lorc/peaks", "Mountain Pass": "delapouite/mountain-road",
        "Volcano": "lorc/volcano", "Desert": "delapouite/desert", "Cactus": "delapouite/cactus", "Oasis": "delapouite/oasis",
        "Plains": "delapouite/grass", "Steppe": "delapouite/high-grass", "Farmland": "lorc/wheat",
        "Swamp": "delapouite/swamp", "Marsh Reeds": "delapouite/reed", "Lake": "lorc/waves", "River": "delapouite/river",
        "Sea Waves": "lorc/big-wave", "Island": "delapouite/island", "Sea Cliff": "delapouite/sea-cliff",
        "Rocks": "lorc/rock", "Boulders": "delapouite/stone-pile", "Iceberg": "delapouite/iceberg", "Snowfield": "lorc/snowing",
        "Lava": "sbed/lava",
    },
}

root = Path("resources/assets")
failed = []
for category, icons in ICONS.items():
    (root / category).mkdir(parents=True, exist_ok=True)
    for name, src in icons.items():
        url = f"https://game-icons.net/icons/000000/transparent/1x1/{src}.svg"
        try:
            data = urllib.request.urlopen(url, timeout=20).read()
            assert data.startswith(b"<svg"), data[:60]
            (root / category / f"{name}.svg").write_bytes(data)
        except Exception as exc:
            failed.append((name, src, exc))
        time.sleep(0.15)  # be polite to the site

lines = ["# Asset attribution", "",
         "Icons from [game-icons.net](https://game-icons.net), licensed under",
         "[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Downloaded as black-on-transparent SVG, unmodified.", ""]
for category, icons in ICONS.items():
    lines += [f"## {category}", "", "| Icon | Original | Author |", "|---|---|---|"]
    for name, src in icons.items():
        author, icon = src.split("/")
        lines.append(f"| {name} | [{icon}](https://game-icons.net/1x1/{src}.html) | {author} |")
    lines.append("")
(root / "ATTRIBUTION.md").write_text("\n".join(lines), encoding="utf-8")
print("downloaded", sum(len(v) for v in ICONS.values()) - len(failed), "failed", failed)
