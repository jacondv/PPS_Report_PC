"""
NavigateTool: the default tool. Orbit/pan/zoom (VTK's own camera style)
handles anything this tool doesn't consume — clicking empty space, or
dragging when nothing was hit.

On top of that, this is also where selecting, highlighting, dragging
(moving), and right-click editing/deleting existing notes/annotations/
measurements lives — the Note and Annotation tools are creation-only;
manipulating what's already placed happens here, while Navigate is active,
so left-drag can mean "rotate" almost everywhere but "move this label"
exactly when you've grabbed one.
"""

from typing import Callable, Optional, Tuple

from pps.render.labels import compute_label_bbox, compute_screen_note_bbox
from pps.scene.commands import DeleteMeasurementCommand, DeleteNoteCommand, EditNoteCommand, MoveNoteCommand
from pps.scene.measurements import DistanceMeasurement
from pps.tools.base import MouseButton, PointerEvent, PointerEventType, Tool

NoteEditor = Callable[[Optional[object], Tuple[float, float]], Optional[dict]]
ObjectMenu = Callable[[str, str], Optional[str]]  # (kind, object_id) -> "edit" | "delete" | None

DRAG_THRESHOLD_PX = 3
_MEASUREMENT_LABEL_FONT_SIZE = 14  # matches the default MeasurementRenderer builds labels with


def _midpoint(p1, p2) -> Tuple[float, float, float]:
    return tuple((a + b) / 2.0 for a, b in zip(p1, p2))


def _measurement_display(measurement) -> Tuple[str, Tuple[float, float, float], str]:
    """(kind, anchor, display_text) for hit-testing a measurement's label."""
    if isinstance(measurement, DistanceMeasurement):
        return "distance", _midpoint(measurement.p1, measurement.p2), f"{measurement.distance_m:.3f} m"
    text = "…" if measurement.area_m2 is None else f"{measurement.area_m2:.2f} m²"
    return "area", measurement.centroid, text


def _contains(bbox, x: float, y: float) -> bool:
    x0, y0, x1, y1 = bbox
    return x0 <= x <= x1 and y0 <= y <= y1


class NavigateTool(Tool):
    # Empty id: this is the "no tool" / default sentinel ToolManager already
    # used for Navigate (None/"" tool_id everywhere — Escape, document
    # reset, the Navigate toolbar button); ToolManager.register() maps that
    # to the same internal key so this instance is the one that actually
    # runs instead of no tool at all.
    id = ""
    label = "Navigate"
    shortcut = "V"
    cursor = None

    def __init__(self, note_editor: NoteEditor = None, object_menu: ObjectMenu = None):
        super().__init__()
        self.note_editor = note_editor
        self.object_menu = object_menu
        self._selected: Optional[Tuple[str, str]] = None  # (kind, object_id)
        self._dragging = False
        self._drag_start_pos: Optional[Tuple[float, float]] = None
        self._drag_start_value = None  # offset_px (anchored note) or pos_frac (screen note)
        self._pending_value = None

    # ------------------------------------------------------------------ lifecycle
    def on_activate(self) -> None:
        self._reset_drag()

    def on_deactivate(self) -> None:
        self._reset_drag()
        self._clear_selection()

    def cancel(self) -> None:
        self._reset_drag()

    def is_idle(self) -> bool:
        return not self._dragging

    def status_hint(self) -> str:
        base = "Left-drag: rotate  |  Right-drag/wheel: zoom  |  Middle-drag: pan"
        if self._selected is not None:
            base += "  |  Drag: move  |  Right-click: edit/delete  |  Delete: remove"
        return base

    # ------------------------------------------------------------------ selection (also used externally, e.g. Project dock's "Move")
    def select(self, kind: Optional[str], object_id: Optional[str]) -> None:
        self._selected = (kind, object_id) if kind and object_id else None
        self.ctx.set_highlighted(kind, object_id)

    def _clear_selection(self) -> None:
        self.select(None, None)

    # ------------------------------------------------------------------ events
    def handle_pointer(self, event: PointerEvent) -> bool:
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.LEFT:
            return self._on_left_press(event)
        if event.kind == PointerEventType.PRESS and event.button == MouseButton.RIGHT:
            return self._on_right_press(event)
        if event.kind == PointerEventType.MOVE and self._dragging:
            self._on_drag_move(event)
            return True
        if event.kind == PointerEventType.RELEASE and event.button == MouseButton.LEFT and self._dragging:
            self._on_drag_release()
            return True
        return False

    def handle_key(self, event) -> bool:
        if event.key == "Delete" and self._selected is not None:
            kind, object_id = self._selected
            self._delete(kind, object_id)
            self._clear_selection()
            return True
        return False

    def _delete(self, kind: str, object_id: str) -> None:
        if kind == "note":
            self.ctx.undo_stack.push(DeleteNoteCommand(self.ctx.document, object_id))
        else:
            self.ctx.undo_stack.push(DeleteMeasurementCommand(self.ctx.document, object_id))

    # ------------------------------------------------------------------ press
    def _on_left_press(self, event: PointerEvent) -> bool:
        hit = self._hit_test(event.x, event.y)
        if hit is None:
            self._clear_selection()
            return False  # let VTK orbit/pan as normal

        kind, object_id, draggable = hit
        self.select(kind, object_id)
        if draggable:
            self._dragging = True
            self._drag_start_pos = (event.x, event.y)
            self._drag_start_value = self._current_value(object_id)
            self._pending_value = self._drag_start_value
        return True  # consume: don't let this click also start an orbit

    def _on_right_press(self, event: PointerEvent) -> bool:
        hit = self._hit_test(event.x, event.y)
        if hit is None:
            return False
        kind, object_id, _draggable = hit
        self.select(kind, object_id)
        if self.object_menu is None:
            return True

        action = self.object_menu(kind, object_id)
        if action == "edit" and kind == "note" and self.note_editor is not None:
            note = self.ctx.document._find_note(object_id)
            if note is not None:
                result = self.note_editor(note, (event.x, event.y))
                if result is not None:
                    self.ctx.undo_stack.push(EditNoteCommand(self.ctx.document, note.id, **result))
        elif action == "delete":
            self._delete(kind, object_id)
            self._clear_selection()
        return True

    # ------------------------------------------------------------------ drag
    def _current_value(self, note_id: str):
        note = self.ctx.document._find_note(note_id)
        return note.screen_pos_frac if note.is_screen_note else note.label_offset_px

    def _on_drag_move(self, event: PointerEvent) -> None:
        kind, object_id = self._selected
        note = self.ctx.document._find_note(object_id) if kind == "note" else None
        if note is None:
            self._reset_drag()
            return

        dx = event.x - self._drag_start_pos[0]
        dy = event.y - self._drag_start_pos[1]
        if note.is_screen_note:
            width, height = self._viewport_size()
            self._pending_value = (
                self._drag_start_value[0] + (dx / width if width else 0.0),
                self._drag_start_value[1] + (dy / height if height else 0.0),
            )
            self.ctx.move_object_preview(kind, object_id, pos_frac=self._pending_value)
        else:
            self._pending_value = (
                int(self._drag_start_value[0] + dx),
                int(self._drag_start_value[1] + dy),
            )
            self.ctx.move_object_preview(kind, object_id, offset_px=self._pending_value)
        self.ctx.request_render()

    def _on_drag_release(self) -> None:
        kind, object_id = self._selected
        start_value = self._drag_start_value
        pending_value = self._pending_value
        self._dragging = False

        note = self.ctx.document._find_note(object_id) if kind == "note" else None
        if note is not None and pending_value is not None:
            width, height = self._viewport_size()
            if note.is_screen_note:
                field = "screen_pos_frac"
                moved = (
                    abs((pending_value[0] - start_value[0]) * width) >= DRAG_THRESHOLD_PX
                    or abs((pending_value[1] - start_value[1]) * height) >= DRAG_THRESHOLD_PX
                )
            else:
                field = "label_offset_px"
                moved = (
                    abs(pending_value[0] - start_value[0]) >= DRAG_THRESHOLD_PX
                    or abs(pending_value[1] - start_value[1]) >= DRAG_THRESHOLD_PX
                )
            if moved:
                self.ctx.undo_stack.push(
                    MoveNoteCommand(self.ctx.document, object_id, field=field, new_value=pending_value)
                )
            else:
                # Below the drag threshold: snap the live preview back so it
                # doesn't sit at a not-quite-committed position.
                key = "pos_frac" if note.is_screen_note else "offset_px"
                self.ctx.move_object_preview(kind, object_id, **{key: start_value})
        self.ctx.request_render()

    def _reset_drag(self) -> None:
        if self._dragging and self._selected is not None and self.ctx is not None:
            kind, object_id = self._selected
            note = self.ctx.document._find_note(object_id) if kind == "note" else None
            if note is not None and self._drag_start_value is not None:
                key = "pos_frac" if note.is_screen_note else "offset_px"
                self.ctx.move_object_preview(kind, object_id, **{key: self._drag_start_value})
        self._dragging = False
        self._drag_start_pos = None
        self._drag_start_value = None
        self._pending_value = None
        if self.ctx is not None:
            self.ctx.request_render()

    # ------------------------------------------------------------------ helpers
    def _viewport_size(self) -> Tuple[int, int]:
        try:
            return tuple(self.ctx.viewport.plotter.ren_win.GetSize())
        except Exception:
            return (1, 1)

    # ------------------------------------------------------------------ hit-testing
    def _hit_test(self, x: float, y: float) -> Optional[Tuple[str, str, bool]]:
        """(kind, object_id, draggable) for whatever's under (x, y), most
        recently added first, or None. Measurements are selectable/
        deletable but not (yet) draggable."""
        viewport_size = self._viewport_size()
        plotter = self.ctx.viewport.plotter

        for note in reversed(self.ctx.document.annotations):
            if note.is_screen_note:
                bbox = compute_screen_note_bbox(note.screen_pos_frac, note.text, note.font_size, viewport_size)
            else:
                bbox = compute_label_bbox(note.anchor, note.label_offset_px, note.text, note.font_size, plotter)
            if bbox is not None and _contains(bbox, x, y):
                return ("note", note.id, True)

        for measurement in reversed(self.ctx.document.measurements):
            kind, anchor, text = _measurement_display(measurement)
            bbox = compute_label_bbox(anchor, measurement.label_offset_px, text, _MEASUREMENT_LABEL_FONT_SIZE, plotter)
            if bbox is not None and _contains(bbox, x, y):
                return (kind, measurement.id, False)

        return None
