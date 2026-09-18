"""
AnnotationTool: click a point on the cloud to place a 3D-anchored text
annotation (opens an inline editor at the click) — one end on the cloud,
the other end draggable text connected by a leader line.

Creation only: selecting, dragging (moving), editing, and deleting an
existing note/annotation all happen with the Navigate tool active instead
(tools/navigate.py) — while Annotation is active, every click on the cloud
just places a new one.
"""

from typing import Callable, Optional, Tuple

from pps.render.picking import pick_nearest_point_3d
from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import AddNoteCommand
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, Tool

NoteEditor = Callable[[Optional[NoteAnnotation], Tuple[float, float]], Optional[dict]]


def _default_note_editor(existing: Optional[NoteAnnotation], screen_pos: Tuple[float, float]) -> Optional[dict]:
    from pps.app.dialogs import open_note_editor

    return open_note_editor(existing)


class AnnotationTool(Tool):
    id = "annotation"
    label = "Annotation"
    shortcut = "G"
    cursor = "ibeam"

    def __init__(self, note_editor: NoteEditor = None):
        super().__init__()
        self.note_editor = note_editor or _default_note_editor

    def status_hint(self) -> str:
        return "Click cloud: place annotation here  |  Esc: cancel"

    def handle_pointer(self, event: PointerEvent) -> bool:
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.LEFT:
            picked = pick_nearest_point_3d(event.x, event.y, self.ctx.viewport.plotter)
            if picked is not None:
                self._create_note(picked, (event.x, event.y))
            return True
        return False

    def _create_note(self, anchor, screen_pos: Tuple[float, float]) -> None:
        result = self.note_editor(None, screen_pos)
        if result is None:
            return
        document = self.ctx.document
        note = NoteAnnotation(
            anchor=tuple(anchor),
            text=result["text"],
            layer_id=document.layer_manager.nearest_layer_id(anchor),
            color=result.get("color", "#ffd166"),
            font_size=result.get("font_size", 14),
        )
        self.ctx.undo_stack.push(AddNoteCommand(document, note))
        self.ctx.finish_command()
