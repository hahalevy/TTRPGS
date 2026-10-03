from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QToolButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """A titled section that behaves like one item in an accordion / tool
    palette: clicking its header both expands it (collapsing siblings, via
    DrawPanel's QButtonGroup) and activates the corresponding tool - standard
    "select a tool" UX (Photoshop/Illustrator-style), not a separate
    show/hide checkbox independent of tool selection.
    """

    activated = Signal()  # emitted when the header is clicked to become the active section

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        self.toggle_button = QToolButton()
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
        self.toggle_button.toggled.connect(self._on_toggled)
        self.toggle_button.pressed.connect(self._on_pressed)
        self.toggle_button.clicked.connect(self._on_clicked)
        self._was_open_at_press = False
        outer.addWidget(self.toggle_button)

        self.content = QWidget()
        outer.addWidget(self.content)

    def _on_toggled(self, checked: bool) -> None:
        self.toggle_button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self.content.setVisible(checked)
        if checked:
            self.activated.emit()

    def _on_pressed(self) -> None:
        self._was_open_at_press = self.toggle_button.isChecked()

    def _on_clicked(self, checked: bool) -> None:
        # Clicking an already-open section in an exclusive group doesn't
        # toggle (so no `activated` above), but it still means "use this
        # tool" - activate it anyway.
        if checked and self._was_open_at_press:
            self.activated.emit()

    def set_expanded(self, expanded: bool) -> None:
        self.toggle_button.setChecked(expanded)

    def is_expanded(self) -> bool:
        return self.toggle_button.isChecked()
