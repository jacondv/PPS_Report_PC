"""
AnnotationTool: click a point on the cloud to place a 3D-anchored text
annotation (opens an inline editor at the click), drag an existing
annotation's text to reposition it (leader line follows), double-click to
edit, Delete to remove the selected one.

Formerly "NoteTool" — split into two tools: this one needs a cloud point to
anchor to (one end on the cloud, the other end draggable text), while the
Note tool (tools/note.py) is plain free-floating 2D text with no cloud
anchor at all.
"""

from typing import Callable, Optional, Tuple

import numpy as np

from pps.render.actors2d import polyline_actor
from pps.render.labels import compute_label_bbox, hex_to_rgb
from pps.render.picking import pick_nearest_point_3d, project_to_screen
from pps.scene.annotations import NoteAnnotation
from pps.scene.commands import AddNoteCommand, DeleteNoteCommand, EditNoteCommand, MoveNoteCommand
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, Tool

NoteEditor = Callable[[Optional[NoteAnnotation], Tuple[float, float]], Optional[dict]]

DRAG_THRESHOLD_PX = 3


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
        self._selected_note_id: Optional[str] = None
        self._dragging = False
        self._drag_start_pos: Optional[Tuple[float, float]] = None
        self._drag_start_offset: Optional[Tuple[int, int]] = None
        self._pending_offset: Optional[Tuple[int, int]] = None

    def on_activate(self) -> None:
        self._reset_drag()
        self._selected_note_id = None

    def on_deactivate(self) -> None:
        self._reset_drag()
        self._selected_note_id = None

    def cancel(self) -> None:
        self._reset_drag()
        self._selected_note_id = None

    def is_idle(self) -> bool:
        return not self._dragging

    def status_hint(self) -> str:
        return (
            "Click cloud: add annotation  |  Drag text: move  |  Double-click: edit  |  "
            "Delete: remove selected  |  Esc: cancel"
        )

    def select(self, note_id: Optional[str]) -> None:
        """Pre-select an annotation (e.g. from the Project dock's "Move"
        action) so the very next drag in the 3D view moves it, without
        requiring the user to click it first."""
        self._selected_note_id = note_id

    # ------------------------------------------------------------------ events
    def handle_pointer(self, event: PointerEvent) -> bool:
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.LEFT:
            return self._on_press(event)

        if event.kind == PointerEventType.DOUBLE_CLICK and event.button == MouseButton.LEFT:
            return self._on_double_click(event)

        if event.kind == PointerEventType.MOVE and self._dragging:
            self._on_drag_move(event)
            return True

        if event.kind == PointerEventType.RELEASE and event.button == MouseButton.LEFT and self._dragging:
            self._on_drag_release()
            return True

        return False

    def handle_key(self, event) -> bool:
        if event.key == "Delete" and self._selected_note_id is not None:
            self.ctx.undo_stack.push(DeleteNoteCommand(self.ctx.document, self._selected_note_id))
            self._selected_note_id = None
            return True
        return False

    # ------------------------------------------------------------------ press / double-click
    def _on_press(self, event: PointerEvent) -> bool:
        hit = self._hit_test(event.x, event.y)
        if hit is not None:
            self._selected_note_id = hit.id
            self._dragging = True
            self._drag_start_pos = (event.x, event.y)
            self._drag_start_offset = hit.label_offset_px
            self._pending_offset = hit.label_offset_px
            return True

        self._selected_note_id = None
        picked = pick_nearest_point_3d(event.x, event.y, self.ctx.viewport.plotter)
        if picked is not None:
            self._create_note(picked, (event.x, event.y))
        return True

    def _on_double_click(self, event: PointerEvent) -> bool:
        hit = self._hit_test(event.x, event.y)
        if hit is None:
            return False
        self._edit_note(hit, (event.x, event.y))
        return True

    # ------------------------------------------------------------------ drag
    def _on_drag_move(self, event: PointerEvent) -> None:
        note = self.ctx.document._find_note(self._selected_note_id)
        if note is None:
            self._reset_drag()
            return

        dx = event.x - self._drag_start_pos[0]
        dy = event.y - self._drag_start_pos[1]
        self._pending_offset = (
            int(self._drag_start_offset[0] + dx),
            int(self._drag_start_offset[1] + dy),
        )
        self._draw_drag_preview(note)

    def _on_drag_release(self) -> None:
        note_id = self._selected_note_id
        start_offset = self._drag_start_offset
        pending_offset = self._pending_offset
        self._dragging = False
        self.scratch.clear()
        self.ctx.overlay.set_hud_text("")

        moved = pending_offset is not None and (
            abs(pending_offset[0] - start_offset[0]) >= DRAG_THRESHOLD_PX
            or abs(pending_offset[1] - start_offset[1]) >= DRAG_THRESHOLD_PX
        )
        if moved:
            self.ctx.undo_stack.push(MoveNoteCommand(self.ctx.document, note_id, pending_offset))
        self.ctx.request_render()

    def _draw_drag_preview(self, note: NoteAnnotation) -> None:
        self.scratch.clear()
        projected = project_to_screen(np.array([note.anchor]), self.ctx.viewport.plotter)
        if projected is not None:
            ax, ay = float(projected[0][0]), float(projected[0][1])
            lx, ly = ax + self._pending_offset[0], ay + self._pending_offset[1]
            self.scratch.add(
                polyline_actor(
                    [(ax, ay), (lx, ly)], closed=False,
                    rgb=hex_to_rgb(note.color), line_width=1.5, opacity=0.7, stipple=0xF0F0,
                )
            )
        self.ctx.overlay.set_hud_text(f"Moving annotation: {note.text[:40]!r}")
        self.ctx.request_render()

    def _reset_drag(self) -> None:
        self._dragging = False
        self._drag_start_pos = None
        self._drag_start_offset = None
        self._pending_offset = None
        if self.scratch is not None:
            self.scratch.clear()
        if self.ctx is not None:
            self.ctx.overlay.set_hud_text("")
            self.ctx.request_render()

    # ------------------------------------------------------------------ create / edit
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

    def _edit_note(self, note: NoteAnnotation, screen_pos: Tuple[float, float]) -> None:
        result = self.note_editor(note, screen_pos)
        if result is None:
            return
        self.ctx.undo_stack.push(EditNoteCommand(self.ctx.document, note.id, **result))

    # ------------------------------------------------------------------ hit-testing
    def _hit_test(self, x: float, y: float) -> Optional[NoteAnnotation]:
        for note in reversed(self.ctx.document.annotations):
            if note.is_screen_note:
                continue
            bbox = compute_label_bbox(
                note.anchor, note.label_offset_px, note.text, note.font_size, self.ctx.viewport.plotter
            )
            if bbox is None:
                continue
            x0, y0, x1, y1 = bbox
            if x0 <= x <= x1 and y0 <= y <= y1:
                return note
        return None
