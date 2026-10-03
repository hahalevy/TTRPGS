from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDockWidget, QFormLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..app_config import ASSETS_DIR
from ..canvas.images import image_extensions, load_image
from .asset_scanner import scan_assets
from .decoration_controls import DecorationControls
from .field_binder import FieldBinder
from .recent_items import RecentStrip
from .widgets import opacity_slider

THUMB_SIZE = 64


def thumbnail(path: Path) -> QIcon:
    return QIcon(load_image(path))  # QIcon scales it down to the list's icon size


class AssetPanel(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Assets", parent)
        self._current_asset: str | None = None

        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("Recently Used"))
        self.recent = RecentStrip(
            describe=lambda rel: (thumbnail(ASSETS_DIR / rel), Path(rel).stem), icon_size=THUMB_SIZE
        )
        self.recent.picked.connect(self._select_asset)
        layout.addWidget(self.recent)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(refresh_btn)

        self.tabs = QTabWidget()
        self.empty_label = QLabel("No asset categories found yet.\nAdd subfolders under resources/assets/.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.tabs)
        layout.addWidget(self.empty_label)

        form = QFormLayout()
        opacity = opacity_slider()
        form.addRow("Opacity", opacity[0])
        layout.addLayout(form)
        fields = {"opacity": opacity, "border": DecorationControls("Border"), "outline": DecorationControls("Outline")}
        layout.addWidget(fields["border"])
        layout.addWidget(fields["outline"])
        self.binder = FieldBinder(fields, self)

        self.setWidget(container)
        self.refresh()

    def refresh(self) -> None:
        self.tabs.clear()
        categories = scan_assets(ASSETS_DIR, image_extensions())
        self.empty_label.setVisible(not categories)
        self.tabs.setVisible(bool(categories))
        for category, entries in categories.items():
            grid = QListWidget()
            grid.setViewMode(QListWidget.ViewMode.IconMode)
            grid.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
            for entry in entries:
                row = QListWidgetItem(thumbnail(entry.abs_path), entry.name)
                row.setData(Qt.ItemDataRole.UserRole, entry.relative_path)
                grid.addItem(row)
            grid.itemClicked.connect(lambda row: self._select_asset(row.data(Qt.ItemDataRole.UserRole)))
            self.tabs.addTab(grid, category)

    def _select_asset(self, relative_path: str) -> None:
        self._current_asset = relative_path

    def current_settings(self) -> dict:
        return {**self.binder.values(), "asset_path": self._current_asset}

    def notify_asset_placed(self, relative_path: str) -> None:
        self.recent.push(relative_path)
