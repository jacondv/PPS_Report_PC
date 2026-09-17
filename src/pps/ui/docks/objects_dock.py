"""
Objects dock: every note and measurement in one list — select, toggle
visibility, delete (undoable).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDockWidget,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pps.scene.commands import DeleteMeasurementCommand, DeleteNoteCommand
from pps.scene.measurements import DistanceMeasurement
from pps.ui.icons import load_icon

_KIND_NOTE = "note"
_KIND_DISTANCE = "distance"
_KIND_AREA = "area"


class ObjectsDock(QDockWidget):
    def __init__(self, document, parent=None):
        super().__init__("Objects", parent)
        self.setObjectName("dock_objects")
        self.document = document

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(6, 6, 6, 6)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumWidth(180)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        self.btn_toggle = QPushButton("Show/Hide")
        self.btn_toggle.clicked.connect(self._on_toggle_visible)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._on_delete)
        button_row.addWidget(self.btn_toggle)
        button_row.addWidget(self.btn_delete)
        layout.addLayout(button_row)

        self.setWidget(content)

        for signal in (
            document.annotation_added, document.annotation_changed, document.annotation_removed,
            document.measurement_added, document.measurement_changed, document.measurement_removed,
            document.reset,
        ):
            signal.connect(self.refresh)

        self.refresh()

    def refresh(self, *_args) -> None:
        self.list_widget.clear()
        for note in self.document.annotations:
            item = QListWidgetItem(f"📝 {note.text[:40]}")
            item.setData(Qt.ItemDataRole.UserRole, (_KIND_NOTE, note.id))
            self.list_widget.addItem(item)
        for measurement in self.document.measurements:
            if isinstance(measurement, DistanceMeasurement):
                text = f"📏 {measurement.distance_m:.3f} m"
                kind = _KIND_DISTANCE
            else:
                area_text = "…" if measurement.area_m2 is None else f"{measurement.area_m2:.2f} m²"
                text = f"⬛ {area_text}"
                kind = _KIND_AREA
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (kind, measurement.id))
            self.list_widget.addItem(item)

    def set_icon_color(self, color: str) -> None:
        self.btn_toggle.setIcon(load_icon("eye", color))
        self.btn_delete.setIcon(load_icon("delete", color))

    def _selected(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.list_widget.selectedItems()]

    def _on_toggle_visible(self) -> None:
        selected = self._selected()
        if not selected:
            return
        for kind, object_id in selected:
            if kind == _KIND_NOTE:
                note = self.document._find_note(object_id)
                if note is not None:
                    self.document.set_note_visible(object_id, not note.visible)
            else:
                measurement = self.document._find_measurement(object_id)
                if measurement is not None:
                    self.document.set_measurement_visible(object_id, not measurement.visible)

    def _on_delete(self) -> None:
        selected = self._selected()
        if not selected:
            return
        if len(selected) > 1:
            self.document.undo_stack.beginMacro(f"Delete {len(selected)} objects")
        for kind, object_id in selected:
            if kind == _KIND_NOTE:
                self.document.undo_stack.push(DeleteNoteCommand(self.document, object_id))
            else:
                self.document.undo_stack.push(DeleteMeasurementCommand(self.document, object_id))
        if len(selected) > 1:
            self.document.undo_stack.endMacro()
