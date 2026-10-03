from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QListWidget, QListWidgetItem

MAX_RECENT = 5


class RecentStrip(QListWidget):
    """Last-5-used strip shared by the Labels and Assets panels. Items are
    any value; `describe(item) -> (icon or None, text)` controls display,
    `key(item)` controls de-duplication. Clicking emits `picked(item)`.
    """

    picked = Signal(object)

    def __init__(self, describe: Callable, key: Callable = lambda item: item, icon_size: int = 0, parent=None):
        super().__init__(parent)
        self._describe = describe
        self._key = key
        self.items: list = []
        if icon_size:
            self.setViewMode(QListWidget.ViewMode.IconMode)
            self.setIconSize(QSize(icon_size, icon_size))
        self.setFixedHeight(96)
        self.itemClicked.connect(lambda row: self.picked.emit(row.data(Qt.ItemDataRole.UserRole)))

    def push(self, item) -> None:
        key = self._key(item)
        self.items = ([item] + [i for i in self.items if self._key(i) != key])[:MAX_RECENT]
        self.clear()
        for entry in self.items:
            icon, text = self._describe(entry)
            row = QListWidgetItem(icon or QIcon(), text)
            row.setData(Qt.ItemDataRole.UserRole, entry)
            self.addItem(row)
