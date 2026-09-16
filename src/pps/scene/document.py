"""
Document: the single source of truth for one open project.

Owns layers, selection, annotations, measurements and the undo stack.
Renderers/UI never mutate this state directly — they call Document methods
(or push a QUndoCommand from scene/commands.py) and react to its signals.
"""

import os
from typing import List, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoStack

from pps.core.filename_parser import ProjectInfo
from pps.core.layers import Layer, LayerManager
from pps.scene.annotations import NoteAnnotation
from pps.scene.measurements import AreaMeasurement, DistanceMeasurement
from pps.scene.selection import Selection

Measurement = "DistanceMeasurement | AreaMeasurement"


class Document(QObject):
    reset = Signal()  # whole document replaced (new file loaded / new project)

    layer_added = Signal(str)
    layer_removed = Signal(str)
    layer_changed = Signal(str)  # rename / visibility / color

    selection_changed = Signal()

    annotation_added = Signal(str)
    annotation_changed = Signal(str)
    annotation_removed = Signal(str)

    measurement_added = Signal(str)
    measurement_changed = Signal(str)
    measurement_removed = Signal(str)

    targets_changed = Signal(float, float)
    dirty_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.layer_manager = LayerManager()
        self.selection = Selection(self.layer_manager)
        self.annotations: List[NoteAnnotation] = []
        self.measurements: List[object] = []  # DistanceMeasurement | AreaMeasurement

        self.project_info: Optional[ProjectInfo] = None
        self.source_path: Optional[str] = None
        self.distance_field: str = "distances"
        self.target_min: float = 40.0
        self.target_max: float = 60.0

        self.undo_stack = QUndoStack(self)

        self._dirty = False

    # ------------------------------------------------------------------ dirty
    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self.dirty_changed.emit(True)

    def mark_clean(self) -> None:
        if self._dirty:
            self._dirty = False
            self.dirty_changed.emit(False)

    # ------------------------------------------------------------------ whole-document lifecycle
    def _clear_state(self) -> None:
        self.layer_manager.clear()
        self.selection.clear()
        self.annotations.clear()
        self.measurements.clear()
        self.undo_stack.clear()
        self.project_info = None
        self.source_path = None
        self._dirty = False

    def new_document(self) -> None:
        self._clear_state()
        self.reset.emit()

    def load_point_cloud(
        self,
        source_path: str,
        project_info: ProjectInfo,
        points,
        distances,
        distance_field: str,
        target_min: float,
        target_max: float,
    ) -> Layer:
        self._clear_state()
        self.source_path = source_path
        self.project_info = project_info
        self.distance_field = distance_field
        self.target_min = target_min
        self.target_max = target_max
        layer = self.layer_manager.set_original(
            name=os.path.basename(source_path), points=points, distances=distances
        )
        self.reset.emit()
        return layer

    def set_targets(self, target_min: float, target_max: float) -> None:
        self.target_min = target_min
        self.target_max = target_max
        self.mark_dirty()
        self.targets_changed.emit(target_min, target_max)

    def set_layer_visible(self, layer_id: str, visible: bool) -> None:
        layer = self.layer_manager.get_by_id(layer_id)
        if layer is None or layer.visible == visible:
            return
        layer.visible = visible
        self.mark_dirty()
        self.layer_changed.emit(layer_id)

    # ------------------------------------------------------------------ low-level mutators
    # These are called by scene/commands.py (for undo/redo) as well as
    # directly for non-undoable bookkeeping. They always emit the matching
    # signal and mark the document dirty.

    def _insert_layer(self, layer: Layer, index: Optional[int] = None) -> None:
        if index is None:
            self.layer_manager.add_layer(layer)
        else:
            self.layer_manager.insert_at(index, layer)
        self.mark_dirty()
        self.layer_added.emit(layer.id)

    def _remove_layer(self, layer_id: str):
        index = self.layer_manager.index_of(layer_id)
        layer = self.layer_manager.get_by_id(layer_id)
        self.layer_manager.remove_by_id(layer_id)
        self.mark_dirty()
        self.layer_removed.emit(layer_id)
        return layer, index

    def _rename_layer(self, layer_id: str, new_name: str) -> str:
        layer = self.layer_manager.get_by_id(layer_id)
        old_name = layer.name
        layer.name = new_name
        self.mark_dirty()
        self.layer_changed.emit(layer_id)
        return old_name

    def _find_note(self, note_id: str) -> Optional[NoteAnnotation]:
        return next((a for a in self.annotations if a.id == note_id), None)

    def _insert_note(self, note: NoteAnnotation, index: Optional[int] = None) -> None:
        if index is None:
            self.annotations.append(note)
        else:
            self.annotations.insert(index, note)
        self.mark_dirty()
        self.annotation_added.emit(note.id)

    def _remove_note(self, note_id: str):
        index = next(i for i, a in enumerate(self.annotations) if a.id == note_id)
        note = self.annotations.pop(index)
        self.mark_dirty()
        self.annotation_removed.emit(note_id)
        return note, index

    def _update_note(self, note_id: str, **fields) -> dict:
        note = self._find_note(note_id)
        old_values = {k: getattr(note, k) for k in fields}
        for k, v in fields.items():
            setattr(note, k, v)
        self.mark_dirty()
        self.annotation_changed.emit(note_id)
        return old_values

    def _find_measurement(self, measurement_id: str):
        return next((m for m in self.measurements if m.id == measurement_id), None)

    def _insert_measurement(self, measurement, index: Optional[int] = None) -> None:
        if index is None:
            self.measurements.append(measurement)
        else:
            self.measurements.insert(index, measurement)
        self.mark_dirty()
        self.measurement_added.emit(measurement.id)

    def _remove_measurement(self, measurement_id: str):
        index = next(i for i, m in enumerate(self.measurements) if m.id == measurement_id)
        measurement = self.measurements.pop(index)
        self.mark_dirty()
        self.measurement_removed.emit(measurement_id)
        return measurement, index

    def _update_measurement(self, measurement_id: str, **fields) -> dict:
        measurement = self._find_measurement(measurement_id)
        old_values = {k: getattr(measurement, k) for k in fields}
        for k, v in fields.items():
            setattr(measurement, k, v)
        self.mark_dirty()
        self.measurement_changed.emit(measurement_id)
        return old_values
