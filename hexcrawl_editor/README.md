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
│   ├── fonts/                # extra .ttf/.otf fonts, auto-loaded at startup
│   └── assets/               # icon library; one subfolder per category (Structures/, Terrain/)
├── projects/                 # suggested place for your .hexproj files (contents are git-ignored)
├── scripts/fetch_icons.py    # (re)downloads the starter icon library
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
4. **Tools are picked from the side tabs** - choosing a tab or section *is* choosing the
   tool: **Draw** (Line / Shapes sections), **Fog**, **Assets**, **Labels**.
5. **Fog**: drag a rectangle; the Fog tab's Mode decides whether it hides or reveals.
6. **Labels/Assets**: set text/font or pick a thumbnail, then left-click to place. Both
   tabs keep the last 5 used, and the label font is remembered across restarts.
7. **Editing**: right-click any element to select it - its tab opens showing its values,
   and changing them edits it (same for lines, shapes, labels and assets). Handles:
   corner = resize, top = rotate, edges = stretch, red = delete; Delete key also works.
   **Ctrl+right-click** toggles visibility. **Ctrl+C / Ctrl+V** copy and paste the
   selected elements (any number, any kind) into the active layer - centered on the mouse
   if it is over the map. Everything is undoable (Ctrl+Z / Ctrl+Y).
8. **File > Export PNG...** lets you choose "Full map" or "Current view" as the
   export region, and either the original resolution or a custom one. Export
   flattens whatever is currently visible — there's no separate DM/player mode;
   toggle what you want hidden, export the player version, toggle back, export
   the DM version.
9. **File > Save/Save As** writes a `.hexproj` file (a zip containing the full
   editable project, including base map settings and background color). The base map
   is referenced by a path relative to the project file, so move the project and the
   map together; if the map can't be found on open, you're asked to locate it. The
   `projects/` folder is a convenient place to keep them - its contents are ignored by
   git, so personal campaigns never get committed.

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
- Drop `.ttf`/`.otf` font files into `resources/fonts/` to have them auto-loaded at
  startup, or use **Import Font...** in the Labels panel to load one at runtime
  (not copied into the project).

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
  tab uses it the same way: its values are the settings for new elements, and the
  same binder loads and edits the selected element.
- **SetFieldsCommand** (`commands/fields.py`) handles every edit - move, style,
  transform, rename, visibility, fog regions, layer effects, map settings - on
  elements, layers and the project alike, via `edit_element` / `edit_layer` /
  `edit_project`. Element copies (paste) come from the model's own `cloned()`.
- **TransformHandleMixin** (`canvas/items/handles.py`) provides the selection handles
  for every element type.
- **Export** renders the scene itself, so exports always match the canvas.
- **Images** (`canvas/images.py`): one loader for the map, assets and thumbnails - any
  format Qt reads, vector images rasterized at high resolution.
