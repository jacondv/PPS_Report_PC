"""
NoteTool: click anywhere in the 3D view to place plain 2D text directly on
top of it (opens an inline editor at the click) — no cloud point needed at
all, unlike AnnotationTool.

Creation only: selecting, dragging (moving), editing, and deleting an
existing note/annotation all happen with the Navigate tool active instead
(tools/navigate.py) — while Note is active, every click just places a new
one.
"""

from typing import Callable, Optional, Tuple

from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import AddNoteCommand
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, Tool

NoteEditor = Callable[[Optional[NoteAnnotation], Tuple[float, float]], Optional[dict]]


def _default_note_editor(existing: Optional[NoteAnnotation], screen_pos: Tuple[float, float]) -> Optional[dict]:
    from pps.app.dialogs import open_note_editor

    return open_note_editor(existing)


class NoteTool(Tool):
    id = "note"
    label = "Note"
    shortcut = "N"
    cursor = "ibeam"

    def __init__(self, note_editor: NoteEditor = None):
        super().__init__()
        self.note_editor = note_editor or _default_note_editor

    def status_hint(self) -> str:
        return "Click: place note text here  |  Esc: cancel"

    def handle_pointer(self, event: PointerEvent) -> bool:
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.LEFT:
            self._create_note((event.x, event.y))
            return True
        return False

    def _create_note(self, screen_pos: Tuple[float, float]) -> None:
        result = self.note_editor(None, screen_pos)
        if result is None:
            return
        document = self.ctx.document
        width, height = self._viewport_size()
        pos_frac = (screen_pos[0] / width if width else 0.5, screen_pos[1] / height if height else 0.5)
        note = NoteAnnotation(
            text=result["text"],
            screen_pos_frac=pos_frac,
            # A screen note has no 3D anchor to place it "on" a segment, so
            # it attaches to whichever segment is currently active (visible),
            # falling back to the original layer — this is what lets it show
            # up under the right segment in the Project tree and hide along
            # with it.
            layer_id=document.layer_manager.active_layer_id(),
            color=result.get("color", "#ffd166"),
            font_size=result.get("font_size", 14),
        )
        self.ctx.undo_stack.push(AddNoteCommand(document, note))
        self.ctx.finish_command()

    def _viewport_size(self) -> Tuple[int, int]:
        try:
            return tuple(self.ctx.viewport.plotter.ren_win.GetSize())
        except Exception:
            return (1, 1)
