"""
ProjectDock tree: segments are top-level rows, their notes/annotations and
measurements are nested children (replacing the separate Objects dock).
Visibility cascades from a segment to its children, selecting a child emits
object_selected (for highlighting in the 3D view), and "Move" emits
move_requested instead of trying to drag anything itself (dragging only
makes sense in the 3D view).
"""

import numpy as np
import pytest

from pps.core.layers import SourceRef
from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import AddNoteCommand, AddSegmentCommand
from pps.scene.document import Document
from pps.scene.measurements import DistanceMeasurement
from pps.ui.docks.project_dock import ProjectDock


@pytest.fixture
def document(qtbot):
    doc = Document()
    doc.load_point_cloud(
        source_path="C:/data/sample.ply",
        project_info=None,
        points=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]),
        distances=np.array([10.0, 20.0]),
        distance_field="distances",
        target_min=0.0,
        target_max=100.0,
    )
    return doc


def test_layer_is_top_level_with_notes_and_measurements_nested_under_it(document, qtbot):
    original = document.layer_manager.original
    note = NoteAnnotation(text="hi", screen_pos_frac=(0.5, 0.5), layer_id=original.id)
    document.undo_stack.push(AddNoteCommand(document, note))
    document.measurements.append(
        DistanceMeasurement(p1=(0.0, 0.0, 0.0), p2=(1.0, 0.0, 0.0), layer_id=original.id)
    )
    document.measurement_added.emit("ignored")  # trigger a refresh

    dock = ProjectDock(document)
    qtbot.addWidget(dock)

    assert dock.list_widget.topLevelItemCount() == 1
    layer_item = dock.list_widget.topLevelItem(0)
    assert dock.item_id(layer_item) == original.id
    assert layer_item.childCount() == 2
    child_kinds = {dock.item_kind(layer_item.child(i)) for i in range(layer_item.childCount())}
    assert child_kinds == {"note", "distance"}


def test_hiding_segment_disables_its_children_checkboxes(document, qtbot):
    original = document.layer_manager.original
    note = NoteAnnotation(text="hi", screen_pos_frac=(0.5, 0.5), layer_id=original.id)
    document.undo_stack.push(AddNoteCommand(document, note))

    dock = ProjectDock(document)
    qtbot.addWidget(dock)

    document.set_layer_visible(original.id, False)

    layer_item = dock.list_widget.topLevelItem(0)
    from PySide6.QtCore import Qt

    child = layer_item.child(0)
    assert not (child.flags() & Qt.ItemFlag.ItemIsEnabled)


def test_selecting_note_child_emits_object_selected(document, qtbot):
    original = document.layer_manager.original
    note = NoteAnnotation(text="hi", screen_pos_frac=(0.5, 0.5), layer_id=original.id)
    document.undo_stack.push(AddNoteCommand(document, note))

    dock = ProjectDock(document)
    qtbot.addWidget(dock)

    calls = []
    dock.object_selected.connect(lambda kind, oid: calls.append((kind, oid)))

    layer_item = dock.list_widget.topLevelItem(0)
    dock.list_widget.setCurrentItem(layer_item.child(0))

    assert calls == [("note", note.id)]


def test_move_context_action_emits_move_requested_for_notes(document, qtbot, monkeypatch):
    original = document.layer_manager.original
    note = NoteAnnotation(text="hi", screen_pos_frac=(0.5, 0.5), layer_id=original.id)
    document.undo_stack.push(AddNoteCommand(document, note))

    dock = ProjectDock(document)
    qtbot.addWidget(dock)

    layer_item = dock.list_widget.topLevelItem(0)
    note_item = layer_item.child(0)
    dock.list_widget.setCurrentItem(note_item)

    calls = []
    dock.move_requested.connect(lambda kind, oid: calls.append((kind, oid)))

    # Simulate choosing "Move" from the context menu without a real QMenu popup.
    from pps.ui.docks import project_dock as pd_module

    class _FakeMenu:
        def __init__(self, *a, **k):
            self.actions = []

        def addAction(self, *args):
            text = args[-1]  # accepts either addAction(text) or addAction(icon, text)
            action = object()
            self.actions.append((text, action))
            return action

        def addSeparator(self):
            pass

        def exec(self, *a, **k):
            return dict(self.actions)["Move"]

    monkeypatch.setattr(pd_module, "QMenu", _FakeMenu)
    dock._show_object_menu(dock.list_widget.visualItemRect(note_item).center(), note_item)

    assert calls == [("note", note.id)]


def test_bulk_delete_multiple_notes_in_one_undo_step(document, qtbot):
    original = document.layer_manager.original
    n1 = NoteAnnotation(text="a", screen_pos_frac=(0.3, 0.3), layer_id=original.id)
    n2 = NoteAnnotation(text="b", screen_pos_frac=(0.6, 0.6), layer_id=original.id)
    document.undo_stack.push(AddNoteCommand(document, n1))
    document.undo_stack.push(AddNoteCommand(document, n2))

    dock = ProjectDock(document)
    qtbot.addWidget(dock)

    layer_item = dock.list_widget.topLevelItem(0)
    items = [layer_item.child(i) for i in range(layer_item.childCount())]
    pairs = [(dock.item_kind(i), dock.item_id(i)) for i in items]

    dock._delete_objects(pairs)

    assert len(document.annotations) == 0

    document.undo_stack.undo()
    assert len(document.annotations) == 2


def test_unassigned_notes_appear_under_their_own_group(document, qtbot):
    note = NoteAnnotation(text="orphan", screen_pos_frac=(0.5, 0.5), layer_id=None)
    document.undo_stack.push(AddNoteCommand(document, note))

    dock = ProjectDock(document)
    qtbot.addWidget(dock)

    # 1 real layer + 1 "(Unassigned)" group
    assert dock.list_widget.topLevelItemCount() == 2
    group_item = dock.list_widget.topLevelItem(1)
    assert group_item.childCount() == 1
    assert dock.item_id(group_item.child(0)) == note.id
