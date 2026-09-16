import numpy as np

from pps.core.layers import SourceRef
from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import (
    AddMeasurementCommand,
    AddNoteCommand,
    AddSegmentCommand,
    DeleteMeasurementCommand,
    DeleteNoteCommand,
    EditNoteCommand,
    MoveNoteCommand,
    RemoveLayerCommand,
    RenameLayerCommand,
)
from pps.scene.document import Document
from pps.scene.measurements import DistanceMeasurement


def make_document_with_original(qtbot):
    doc = Document()
    points = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])
    distances = np.array([10.0, 50.0, 200.0])
    doc.load_point_cloud(
        source_path="C:/data/sample.ply",
        project_info=None,
        points=points,
        distances=distances,
        distance_field="distances",
        target_min=40.0,
        target_max=60.0,
    )
    doc.mark_clean()
    return doc


def test_add_segment_command_undo_redo(qtbot):
    doc = make_document_with_original(qtbot)
    original_id = doc.layer_manager.original.id

    source_ref = SourceRef(layer_id=original_id, indices=np.array([0, 1], dtype=np.uint32))
    points = doc.layer_manager.original.points[[0, 1]]
    distances = doc.layer_manager.original.distances[[0, 1]]

    cmd = AddSegmentCommand(doc, points, distances, [source_ref], name="Segment_1")
    doc.undo_stack.push(cmd)

    assert len(doc.layer_manager.layers) == 2
    seg = doc.layer_manager.get("Segment_1")
    assert seg is not None
    assert seg.num_points == 2
    assert doc.dirty is True

    doc.undo_stack.undo()
    assert len(doc.layer_manager.layers) == 1
    assert doc.layer_manager.get("Segment_1") is None

    doc.undo_stack.redo()
    assert len(doc.layer_manager.layers) == 2
    seg2 = doc.layer_manager.get("Segment_1")
    assert seg2 is not None
    # redo must reuse the SAME layer object/id, not rebuild a new one
    assert seg2.id == seg.id


def test_remove_layer_command_restores_index(qtbot):
    doc = make_document_with_original(qtbot)
    original_id = doc.layer_manager.original.id
    seg_ref = SourceRef(layer_id=original_id, indices=np.array([0], dtype=np.uint32))
    doc.undo_stack.push(
        AddSegmentCommand(
            doc,
            doc.layer_manager.original.points[[0]],
            doc.layer_manager.original.distances[[0]],
            [seg_ref],
        )
    )
    seg_id = doc.layer_manager.layers[-1].id

    doc.undo_stack.push(RemoveLayerCommand(doc, seg_id))
    assert doc.layer_manager.get_by_id(seg_id) is None

    doc.undo_stack.undo()
    assert doc.layer_manager.get_by_id(seg_id) is not None
    # restored at the same position (index 1, after the original)
    assert doc.layer_manager.layers[1].id == seg_id


def test_rename_layer_command_undo(qtbot):
    doc = make_document_with_original(qtbot)
    layer_id = doc.layer_manager.original.id

    doc.undo_stack.push(RenameLayerCommand(doc, layer_id, "Renamed"))
    assert doc.layer_manager.get_by_id(layer_id).name == "Renamed"

    doc.undo_stack.undo()
    assert doc.layer_manager.get_by_id(layer_id).name != "Renamed"


def test_note_commands_add_edit_move_delete(qtbot):
    doc = make_document_with_original(qtbot)
    note = NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="hello")

    doc.undo_stack.push(AddNoteCommand(doc, note))
    assert len(doc.annotations) == 1

    doc.undo_stack.push(EditNoteCommand(doc, note.id, text="edited"))
    assert doc._find_note(note.id).text == "edited"

    doc.undo_stack.push(MoveNoteCommand(doc, note.id, (99, 99)))
    assert doc._find_note(note.id).label_offset_px == (99, 99)

    doc.undo_stack.undo()  # undo move
    assert doc._find_note(note.id).label_offset_px != (99, 99)

    doc.undo_stack.undo()  # undo edit
    assert doc._find_note(note.id).text == "hello"

    doc.undo_stack.push(DeleteNoteCommand(doc, note.id))
    assert len(doc.annotations) == 0

    doc.undo_stack.undo()
    assert len(doc.annotations) == 1
    assert doc.annotations[0].text == "hello"


def test_measurement_commands_add_delete(qtbot):
    doc = make_document_with_original(qtbot)
    measurement = DistanceMeasurement(p1=(0.0, 0.0, 0.0), p2=(3.0, 4.0, 0.0))

    doc.undo_stack.push(AddMeasurementCommand(doc, measurement))
    assert len(doc.measurements) == 1
    assert doc.measurements[0].distance_m == 5.0

    doc.undo_stack.push(DeleteMeasurementCommand(doc, measurement.id))
    assert len(doc.measurements) == 0

    doc.undo_stack.undo()
    assert len(doc.measurements) == 1
    assert doc.measurements[0].id == measurement.id
