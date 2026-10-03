from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar


class MainToolBar(QToolBar):
    """Zoom controls only. Every tool (Line, Shapes, Fog, Labels, Assets) is
    activated directly from its sidebar section/tab; there is no separate
    "pick a tool" step in the toolbar. Selecting/moving existing elements is
    always available via the right mouse button (click or drag), regardless
    of whichever draw tool is currently active for the left button.
    """

    def __init__(self, parent=None):
        super().__init__("View", parent)

        zoom_in = QAction("Zoom In", self)
        zoom_out = QAction("Zoom Out", self)
        zoom_reset = QAction("Fit/Reset", self)
        self.addAction(zoom_in)
        self.addAction(zoom_out)
        self.addAction(zoom_reset)
        self.zoom_in_action = zoom_in
        self.zoom_out_action = zoom_out
        self.zoom_reset_action = zoom_reset
