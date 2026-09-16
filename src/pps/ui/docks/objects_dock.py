"""
Objects dock: every note and measurement in one list — select, toggle
visibility, delete (undoable).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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
        layout.addWidget(self.list_widget)

        button_row = QHBoxLayout()
        btn_toggle = QPushButton("Show/Hide")
        btn_toggle.clicked.connect(self._on_toggle_visible)
        btn_delete = QPushButton("Delete")
        btn_delete.clicked.connect(self._on_delete)
        button_row.addWidget(btn_toggle)
        button_row.addWidget(btn_delete)
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

    def _current(self):
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_toggle_visible(self) -> None:
        current = self._current()
        if current is None:
            return
        kind, object_id = current
        if kind == _KIND_NOTE:
            note = self.document._find_note(object_id)
            if note is not None:
                self.document.set_note_visible(object_id, not note.visible)
        else:
            measurement = self.document._find_measurement(object_id)
            if measurement is not None:
                self.document.set_measurement_visible(object_id, not measurement.visible)

    def _on_delete(self) -> None:
        current = self._current()
        if current is None:
            return
        kind, object_id = current
        if kind == _KIND_NOTE:
            self.document.undo_stack.push(DeleteNoteCommand(self.document, object_id))
        else:
            self.document.undo_stack.push(DeleteMeasurementCommand(self.document, object_id))
