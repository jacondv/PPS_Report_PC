"""
Selection dock: region-select mode, thickness filter, extract/crop
segment, invert/clear/select-all — everything that doesn't need a mouse
tool active.
"""

from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pps.scene.commands import AddSegmentCommand
from pps.tools.region_select import RegionMode

_MODE_LABELS = {
    RegionMode.POLYGON: "Polygon",
    RegionMode.RECTANGLE: "Rectangle",
    RegionMode.LASSO: "Lasso",
}


class SelectionDock(QDockWidget):
    def __init__(self, document, region_select_tool, measure_area_tool, parent=None):
        super().__init__("Selection", parent)
        self.setObjectName("dock_selection")
        self.document = document
        self.region_select_tool = region_select_tool
        self.measure_area_tool = measure_area_tool

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumWidth(200)
        layout = QVBoxLayout(content)

        mode_group = QGroupBox("Region Draw Mode")
        mode_form = QFormLayout(mode_group)
        self.mode_combo = QComboBox()
        for mode in RegionMode:
            self.mode_combo.addItem(_MODE_LABELS[mode], mode)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_form.addRow("Shape:", self.mode_combo)
        layout.addWidget(mode_group)

        filter_group = QGroupBox("Filter by Thickness")
        filter_layout = QVBoxLayout(filter_group)
        range_row = QHBoxLayout()
        self.spin_from = QDoubleSpinBox()
        self.spin_from.setRange(-99999, 99999)
        self.spin_from.setValue(75)
        self.spin_to = QDoubleSpinBox()
        self.spin_to.setRange(-99999, 99999)
        self.spin_to.setValue(125)
        range_row.addWidget(QLabel("From:"))
        range_row.addWidget(self.spin_from)
        range_row.addWidget(QLabel("To:"))
        range_row.addWidget(self.spin_to)
        filter_layout.addLayout(range_row)

        self.filter_mode_combo = QComboBox()
        self.filter_mode_combo.addItems(["Replace", "Add", "Subtract"])
        filter_layout.addWidget(self.filter_mode_combo)

        btn_filter = QPushButton("Select by Thickness")
        btn_filter.clicked.connect(self._on_filter_clicked)
        filter_layout.addWidget(btn_filter)
        layout.addWidget(filter_group)

        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)

        self.lbl_selection_count = QLabel("No selection")
        actions_layout.addWidget(self.lbl_selection_count)

        row1 = QHBoxLayout()
        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(self._on_select_all)
        btn_invert = QPushButton("Invert")
        btn_invert.clicked.connect(self._on_invert)
        btn_clear = QPushButton("Clear")
        btn_clear.clicked.connect(self._on_clear)
        row1.addWidget(btn_select_all)
        row1.addWidget(btn_invert)
        row1.addWidget(btn_clear)
        actions_layout.addLayout(row1)

        btn_extract = QPushButton("Extract Segment")
        btn_extract.clicked.connect(self._on_extract_segment)
        actions_layout.addWidget(btn_extract)

        btn_crop = QPushButton("Crop (extract outside selection)")
        btn_crop.clicked.connect(self._on_crop)
        actions_layout.addWidget(btn_crop)

        layout.addWidget(actions_group)
        layout.addStretch()

        scroll.setWidget(content)
        self.setWidget(scroll)

        document.selection_changed.connect(self._refresh_selection_count)
        document.reset.connect(self._refresh_selection_count)

    # ------------------------------------------------------------------ mode
    def _on_mode_changed(self, index: int) -> None:
        mode = self.mode_combo.itemData(index)
        self.region_select_tool.mode = mode
        self.measure_area_tool.mode = mode

    # ------------------------------------------------------------------ filter
    def _filter_mode(self) -> str:
        return self.filter_mode_combo.currentText().lower()

    def _on_filter_clicked(self) -> None:
        self.document.selection.select_by_distance_range(
            self.spin_from.value(), self.spin_to.value(), mode=self._filter_mode()
        )
        self.document.selection_changed.emit()

    # ------------------------------------------------------------------ selection ops
    def _on_select_all(self) -> None:
        self.document.selection.select_all()
        self.document.selection_changed.emit()

    def _on_invert(self) -> None:
        self.document.selection.invert()
        self.document.selection_changed.emit()

    def _on_clear(self) -> None:
        self.document.selection.clear()
        self.document.selection_changed.emit()

    def _on_extract_segment(self) -> None:
        selection = self.document.selection
        if selection.is_empty():
            return
        sources = selection.to_sources()
        points, distances = selection.get_points_and_distances()
        cmd = AddSegmentCommand(self.document, points, distances, sources)
        self.document.undo_stack.push(cmd)
        selection.clear()
        self.document.selection_changed.emit()
        self._show_only(cmd.layer.id)

    def _on_crop(self) -> None:
        selection = self.document.selection
        selection.invert()
        cmd = None
        try:
            if selection.is_empty():
                return
            sources = selection.to_sources()
            points, distances = selection.get_points_and_distances()
            cmd = AddSegmentCommand(self.document, points, distances, sources)
            self.document.undo_stack.push(cmd)
        finally:
            selection.invert()  # restore the selection as the user had it
        selection.clear()
        self.document.selection_changed.emit()
        if cmd is not None:
            self._show_only(cmd.layer.id)

    def _show_only(self, layer_id: str) -> None:
        """After extracting a new segment, show only that segment and hide
        every other layer, so the result of the extraction is immediately
        visible without being buried under the layers it came from."""
        for layer in self.document.layer_manager.layers:
            self.document.set_layer_visible(layer.id, layer.id == layer_id)

    # ------------------------------------------------------------------ display
    def _refresh_selection_count(self) -> None:
        count = self.document.selection.count()
        self.lbl_selection_count.setText(
            "No selection" if count == 0 else f"Selected: {count:,} points"
        )
