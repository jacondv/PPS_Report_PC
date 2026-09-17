"""
QUndoCommand subclasses. Every mutation that should be undoable goes through
one of these; they only ever call Document's `_`-prefixed low-level
mutators (never touch layer_manager/annotations/measurements directly), so
Document stays the single place that emits signals and marks dirty.
"""

from PySide6.QtGui import QUndoCommand


class AddSegmentCommand(QUndoCommand):
    """Create a new segment layer from a selection (or any point/distance
    arrays + their SourceRef provenance)."""

    def __init__(self, document, points, distances, sources, name=None):
        super().__init__("Add segment")
        self.document = document
        self._points = points
        self._distances = distances
        self._sources = sources
        self._name = name
        self._layer = None  # built once, on first redo

    @property
    def layer(self):
        return self._layer

    def redo(self):
        if self._layer is None:
            self._layer = self.document.layer_manager.build_segment(
                points=self._points,
                distances=self._distances,
                name=self._name,
                sources=self._sources,
            )
            self.setText(f"Add segment '{self._layer.name}'")
        self.document._insert_layer(self._layer)

    def undo(self):
        self.document._remove_layer(self._layer.id)


class RemoveLayerCommand(QUndoCommand):
    def __init__(self, document, layer_id):
        layer = document.layer_manager.get_by_id(layer_id)
        label = f"Remove layer '{layer.name}'" if layer else "Remove layer"
        super().__init__(label)
        self.document = document
        self._layer_id = layer_id
        self._layer = None
        self._index = None

    def redo(self):
        self._layer, self._index = self.document._remove_layer(self._layer_id)

    def undo(self):
        self.document._insert_layer(self._layer, self._index)


class RenameLayerCommand(QUndoCommand):
    def __init__(self, document, layer_id, new_name):
        super().__init__("Rename layer")
        self.document = document
        self._layer_id = layer_id
        self._new_name = new_name
        self._old_name = None

    def redo(self):
        self._old_name = self.document._rename_layer(self._layer_id, self._new_name)

    def undo(self):
        self.document._rename_layer(self._layer_id, self._old_name)


class AddNoteCommand(QUndoCommand):
    def __init__(self, document, note):
        super().__init__("Add note")
        self.document = document
        self._note = note
        self._index = None

    def redo(self):
        self.document._insert_note(self._note, self._index)

    def undo(self):
        _, self._index = self.document._remove_note(self._note.id)


class DeleteNoteCommand(QUndoCommand):
    def __init__(self, document, note_id):
        super().__init__("Delete note")
        self.document = document
        self._note_id = note_id
        self._note = None
        self._index = None

    def redo(self):
        self._note, self._index = self.document._remove_note(self._note_id)

    def undo(self):
        self.document._insert_note(self._note, self._index)


class MoveNoteCommand(QUndoCommand):
    """Drag a note: for an anchored note (Annotation tool) this updates
    `label_offset_px` (screen-space offset from its 3D anchor); for a
    screen note (Note tool, no anchor) this updates `screen_pos_frac`
    (its absolute normalized-viewport position) instead."""

    def __init__(self, document, note_id, new_offset_px=None, field="label_offset_px", new_value=None):
        super().__init__("Move note")
        self.document = document
        self._note_id = note_id
        self._field = field
        self._new_value = new_value if new_value is not None else new_offset_px
        self._old_value = None

    def redo(self):
        old = self.document._update_note(self._note_id, **{self._field: self._new_value})
        self._old_value = old[self._field]

    def undo(self):
        self.document._update_note(self._note_id, **{self._field: self._old_value})


class EditNoteCommand(QUndoCommand):
    """Edit arbitrary note fields (text, color, font_size, ...)."""

    def __init__(self, document, note_id, **new_fields):
        super().__init__("Edit note")
        self.document = document
        self._note_id = note_id
        self._new_fields = new_fields
        self._old_fields = None

    def redo(self):
        self._old_fields = self.document._update_note(self._note_id, **self._new_fields)

    def undo(self):
        self.document._update_note(self._note_id, **self._old_fields)


class AddMeasurementCommand(QUndoCommand):
    def __init__(self, document, measurement):
        super().__init__("Add measurement")
        self.document = document
        self._measurement = measurement
        self._index = None

    def redo(self):
        self.document._insert_measurement(self._measurement, self._index)

    def undo(self):
        _, self._index = self.document._remove_measurement(self._measurement.id)


class DeleteMeasurementCommand(QUndoCommand):
    def __init__(self, document, measurement_id):
        super().__init__("Delete measurement")
        self.document = document
        self._measurement_id = measurement_id
        self._measurement = None
        self._index = None

    def redo(self):
        self._measurement, self._index = self.document._remove_measurement(self._measurement_id)

    def undo(self):
        self.document._insert_measurement(self._measurement, self._index)


class UpdateMeasurementCommand(QUndoCommand):
    """Edit arbitrary measurement fields (label offset, color, ...)."""

    def __init__(self, document, measurement_id, **new_fields):
        super().__init__("Update measurement")
        self.document = document
        self._measurement_id = measurement_id
        self._new_fields = new_fields
        self._old_fields = None

    def redo(self):
        self._old_fields = self.document._update_measurement(
            self._measurement_id, **self._new_fields
        )

    def undo(self):
        self.document._update_measurement(self._measurement_id, **self._old_fields)
