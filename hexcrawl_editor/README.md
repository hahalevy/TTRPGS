# Hexcrawl Editor

A desktop tool for annotating hexcrawl maps: start from any base map image, draw
roads/rivers and shapes, place settlement/ruin/terrain icons, add labels, and manage a
fog-of-war layer with per-layer and per-element visibility - then export a full "DM"
version or a redacted "player" version just by toggling what's visible before exporting.

## Setup

Requires Python 3.11+ (tested on 3.14) and PySide6.

```
pip install -r requirements.txt
# for running the test suite too:
pip install -r requirements-dev.txt
```

If `pip install PySide6` fails because your Python version is too new for the
current PySide6 wheels, create a separate virtual environment pinned to the
newest CPython version PySide6 actually publishes wheels for (check with
`pip index versions PySide6`), and install there instead.

## Running

```
python main.py
```

## Project layout

```
hexcrawl_editor/
├── main.py                  # entry point (asks for a base map at launch)
├── hexcrawl/
│   ├── models/               # pure data model (layers, elements, effects, project) - no Qt
│   ├── io/                   # JSON serialization, .hexproj zip save/load, PNG export
│   ├── commands/             # undo commands; every field edit goes through one generic command
│   ├── canvas/               # scene/view, canvas items + shared handles, tools, image loader
│   └── ui/                   # main window and panels, all bound to elements via FieldBinder
├── resources/
│   ├── maps/                 # your base map images (git-ignored: usually someone else's art)
│   ├── defaults.json         # factory defaults for every tool (the config file)
│   ├── fonts/                # bundled open-license fonts, one folder per family (+ its OFL.txt)
│   └── assets/               # icon library; one subfolder per category (Structures/, Terrain/)
├── projects/                 # suggested place for your .hexproj files (contents are git-ignored)
├── scripts/                  # fetch_icons.py / fetch_fonts.py: (re)download the bundled libraries
└── tests/                    # model tests + offscreen GUI tests driving real mouse events
```

## Basic usage

1. **New project**: at launch (and **File > New Project...**) choose the base map image -
   any project can use any map. It becomes the bottom **Base Map** layer, so it can be
   hidden, renamed, or given effects. **Map > Base Map Settings...** fades the map
   (opacity) and sets the **background color** behind it (default white) - a faded map
   shows that color through it, on screen and in exports; other layers are unaffected.
   **Map > Replace Base Map...** swaps the image and keeps its settings.
2. **Layers** panel: add/delete/rename layers and elements (double-click a name). Click a
   row to make its layer active - new elements go there. The eye column shows/hides; the
   name checkbox marks rows for **Delete Checked**.
3. **Mouse:** left button = the current tool, right button = select (click, or drag a
   box) and move (drag an element), middle button = pan, wheel = zoom.
4. **Side panels** (Layers plus the tool tabs) can be dragged to rearrange but not
   closed or floated, so they can't get lost.
5. **Tools are picked from the side tabs** - choosing a tab or section *is* choosing the
   tool: **Draw** (Line / Shapes sections), **Fog**, **Assets**, **Labels**.
6. **Fog**: drag a rectangle; the Fog tab's Mode decides whether it hides or reveals.
7. **Labels/Assets**: set text/font or pick a thumbnail, then left-click to place. Both
   tabs keep the last 5 used, and the label font is remembered per project.
8. **Editing**: right-click any element to select it - its tab opens showing its values,
   and changing them edits it (same for lines, shapes, labels and assets). Handles:
   corner = resize, top = rotate, edges = stretch, red = delete; Delete key also works.
   **Ctrl+right-click** toggles visibility. **Ctrl+C / Ctrl+V** copy and paste the
   selected elements (any number, any kind) into the active layer - centered on the mouse
   if it is over the map. Everything is undoable (Ctrl+Z / Ctrl+Y).
9. **File > Export PNG...** lets you choose "Full map" or "Current view" as the
   export region, and either the original resolution or a custom one. Export
   flattens whatever is currently visible — there's no separate DM/player mode;
   toggle what you want hidden, export the player version, toggle back, export
   the DM version.
10. **File > Save/Save As** writes a `.hexproj` file (a zip containing the full
   editable project, including base map settings and background color). The base map
   is referenced by a path relative to the project file, so move the project and the
   map together; if the map can't be found on open, you're asked to locate it. The
   `projects/` folder is a convenient place to keep them - its contents are ignored by
   git, so personal campaigns never get committed.
   Closing the app (or starting/opening another project) with unsaved changes asks
   whether to **Save**, **Discard** or **Cancel**; Save opens the Save As dialog for a
   project that has no file yet.

## Defaults and remembered settings

- **`resources/defaults.json`** is the config file: the factory defaults for every tool -
  label font (EB Garamond Medium, size 30), colors (black everywhere), widths, line
  style, borders (off), outlines (white, 2 wide, labels only), fog, asset size, canvas
  background and layer names. Edit it and restart to change what new projects start with.
- **Last-used values belong to the project.** Every panel (line, shape, fog, labels,
  assets: fonts, colors, widths, borders, outlines, the chosen icon, and the "recently
  used" strips) remembers your last choices *inside the `.hexproj`*. Open a saved project
  and its values come back; a **New project** starts from the defaults again. Label
  *text* is not remembered. (Changing a value alone doesn't count as an unsaved change.)
- Elements already placed keep their own settings; defaults only affect new ones.

## Assets and fonts

- A starter library ships in `resources/assets/`: **Structures** (37) and **Terrain**
  (28) - black-on-transparent SVG icons from [game-icons.net](https://game-icons.net),
  CC BY 3.0 (credits in `resources/assets/ATTRIBUTION.md`; keep that file if you
  distribute maps or the app). `scripts/fetch_icons.py` lists them and re-downloads
  them; add a line there to fetch more.
- Add your own: drop images into subfolders of `resources/assets/` - each subfolder is a
  category tab (click **Refresh**). Any format Qt reads works without conversion (SVG,
  PNG, JPG, WebP, ...). Vector icons render crisp at any zoom, and every asset is placed
  at the same small default size (resize with its handles).
- **Fonts:** 20 open-license (SIL OFL 1.1) families from Google Fonts ship in
  `resources/fonts/` - clean (Open Sans), classical serif (EB Garamond, IM Fell...),
  inscriptional (Cinzel...), medieval/fantasy (MedievalSharp, Uncial Antiqua...),
  blackletter (Pirata One, Grenze Gotisch) and handwritten/display. Each family keeps
  its `OFL.txt` beside the font (required by the license; credits in
  `resources/fonts/ATTRIBUTION.md`). `scripts/fetch_fonts.py` lists and re-downloads
  them; add a line there for more.
- Add your own: put `.ttf`/`.otf` files (in any subfolder) in `resources/fonts/` - they
  load at startup and appear in the Labels font list - or use **Import Font...** in the
  Labels panel for a one-off (not copied into the project). Only bundled and imported
  fonts are listed, not every font installed on your system.
- Fonts with several weights (EB Garamond, Cinzel...) show each named weight as its own
  entry in the font list on Windows (e.g. "EB Garamond Medium"); there is no separate
  weight control. The default label font is EB Garamond Medium.

## Tests

```
pytest tests/
```

Covers the data model, project files and asset scanning, plus offscreen GUI tests
that drive the real window with real mouse events (drawing, selecting, moving,
handles, panels, layer table, export). Any exception raised inside a Qt signal
handler fails the test. The color dialog itself is not automated.

## Design: one mechanism per job

- **FieldBinder** (`ui/field_binder.py`) binds panel widgets to element fields. Every
  tab uses it the same way: its values are the settings for new elements, the
  same binder loads and edits the selected element, and given a `key` it also starts
  from `defaults.json` + the project's remembered values and saves them on every edit.
- **SetFieldsCommand** (`commands/fields.py`) handles every edit - move, style,
  transform, rename, visibility, fog regions, layer effects, map settings - on
  elements, layers and the project alike, via `edit_element` / `edit_layer` /
  `edit_project`. Element copies (paste) come from the model's own `cloned()`.
- **TransformHandleMixin** (`canvas/items/handles.py`) provides the selection handles
  for every element type.
- **Export** renders the scene itself, so exports always match the canvas.
- **Images** (`canvas/images.py`): one loader for the map, assets and thumbnails - any
  format Qt reads, vector images rasterized at high resolution.
