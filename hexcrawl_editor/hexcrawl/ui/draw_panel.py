from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QDockWidget, QFormLayout, QVBoxLayout, QWidget

from .collapsible_section import CollapsibleSection
from .color_picker_button import ColorPickerButton
from .field_binder import FieldBinder
from .widgets import combo, width_spin

LINE_STYLES = ["solid", "dashed", "dotted"]
SHAPE_TYPES = ["line", "rectangle", "ellipse", "triangle"]


class DrawPanel(QDockWidget):
    """Line (freehand) and Shapes sections. Each section's binder supplies
    the settings for new drawings and edits the selected element of its
    kind - exactly like the Labels and Assets tabs.
    """

    sectionActivated = Signal(str)  # "line" | "shape" (also the tool names)

    def __init__(self, parent=None):
        super().__init__("Draw", parent)
        container = QWidget()
        layout = QVBoxLayout(container)
        group = QButtonGroup(self)
        group.setExclusive(True)

        self.line_section = CollapsibleSection("Line")
        form = QFormLayout(self.line_section.content)
        line_widgets = {"color": ColorPickerButton(), "width": width_spin(), "line_style": combo(LINE_STYLES)}
        for label, key in (("Color", "color"), ("Thickness", "width"), ("Style", "line_style")):
            form.addRow(label, line_widgets[key])
        self.line_binder = FieldBinder(line_widgets, self, key="line")

        self.shapes_section = CollapsibleSection("Shapes")
        form = QFormLayout(self.shapes_section.content)
        fill_check = QCheckBox("Fill")
        fill_color = ColorPickerButton()
        # Choosing a fill color means "fill it" (connected before the binder,
        # so the shape gets both changes in one edit).
        fill_color.colorChanged.connect(lambda _c: fill_check.setChecked(True))
        shape_widgets = {
            "shape_type": combo(SHAPE_TYPES), "color": ColorPickerButton(), "width": width_spin(),
            "line_style": combo(LINE_STYLES), "filled": fill_check, "fill_color": fill_color,
        }
        for label, key in (("Shape", "shape_type"), ("Color", "color"), ("Thickness", "width"),
                           ("Style", "line_style"), ("", "filled"), ("Fill color", "fill_color")):
            form.addRow(label, shape_widgets[key])
        self.shape_binder = FieldBinder(shape_widgets, self, key="shape")

        for name, section in (("line", self.line_section), ("shape", self.shapes_section)):
            layout.addWidget(section)
            group.addButton(section.toggle_button)
            section.activated.connect(lambda n=name: self.sectionActivated.emit(n))
        self.line_section.set_expanded(True)
        layout.addStretch(1)
        self.setWidget(container)

    def set_active_section(self, name: str) -> None:
        {"line": self.line_section, "shape": self.shapes_section}[name].set_expanded(True)

    def active_section(self) -> str:
        return "shape" if self.shapes_section.is_expanded() else "line"
