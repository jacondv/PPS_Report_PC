import vtk

from pps.render.note_renderer import NoteRenderer
from pps.render.overlay import Overlay
from pps.scene.annotations import NoteAnnotation


class FakePlotter:
    def __init__(self):
        self.renderer = vtk.vtkRenderer()
        self.ren_win = vtk.vtkRenderWindow()
        self.ren_win.SetOffScreenRendering(1)
        self.ren_win.AddRenderer(self.renderer)
        self.ren_win.SetSize(400, 300)


def make_renderer():
    plotter = FakePlotter()
    overlay = Overlay(vtk.vtkRenderer())
    return NoteRenderer(plotter, overlay)


def test_sync_one_creates_label():
    renderer = make_renderer()
    note = NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="hello")

    renderer.sync_one(note)

    assert note.id in renderer._labels
    assert renderer._labels[note.id].text == "hello"


def test_sync_all_removes_stale_entries():
    renderer = make_renderer()
    n1 = NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="a")
    n2 = NoteAnnotation(anchor=(1.0, 0.0, 0.0), text="b")

    renderer.sync_all([n1, n2])
    assert set(renderer._labels) == {n1.id, n2.id}

    renderer.sync_all([n2])
    assert set(renderer._labels) == {n2.id}


def test_remove_and_clear():
    renderer = make_renderer()
    note = NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="a")
    renderer.sync_one(note)

    renderer.remove(note.id)
    assert note.id not in renderer._labels

    renderer.sync_one(note)
    renderer.clear()
    assert renderer._labels == {}


def test_sync_one_rebuilds_on_text_change():
    renderer = make_renderer()
    note = NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="a")
    renderer.sync_one(note)
    first = renderer._labels[note.id]

    note.text = "b"
    renderer.sync_one(note)

    assert renderer._labels[note.id] is not first
    assert renderer._labels[note.id].text == "b"


def test_sync_one_builds_a_screen_label_for_a_note_with_no_anchor():
    from pps.render.labels import ScreenLabel

    renderer = make_renderer()
    note = NoteAnnotation(text="free text", screen_pos_frac=(0.3, 0.7))

    renderer.sync_one(note)

    label = renderer._labels[note.id]
    assert isinstance(label, ScreenLabel)
    assert label.text == "free text"
    assert label.pos_frac == (0.3, 0.7)


def test_sync_all_handles_a_mix_of_anchored_and_screen_notes():
    renderer = make_renderer()
    anchored = NoteAnnotation(anchor=(0.0, 0.0, 0.0), text="anchored")
    screen = NoteAnnotation(text="screen", screen_pos_frac=(0.1, 0.1))

    renderer.sync_all([anchored, screen])

    assert set(renderer._labels) == {anchored.id, screen.id}
