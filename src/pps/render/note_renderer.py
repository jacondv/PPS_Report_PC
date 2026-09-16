"""
Syncs Document.annotations (NoteAnnotation) to AnchoredLabel visuals. Same
"data -> actors" mapper shape as LayerRenderer/MeasurementRenderer —
MainWindow (Phase 6) calls this from Document's annotation_added/changed/
removed/reset signal handlers.
"""

from typing import Dict, Iterable

from pps.render.labels import AnchoredLabel
from pps.scene.annotations import NoteAnnotation


class NoteRenderer:
    def __init__(self, plotter, overlay):
        self._plotter = plotter
        self._overlay = overlay
        self._labels: Dict[str, AnchoredLabel] = {}

    def sync_all(self, notes: Iterable[NoteAnnotation]) -> None:
        notes = list(notes)
        wanted_ids = {n.id for n in notes}
        for stale_id in set(self._labels) - wanted_ids:
            self.remove(stale_id)
        for note in notes:
            self.sync_one(note)

    def sync_one(self, note: NoteAnnotation) -> None:
        self.remove(note.id)  # rebuild from scratch: simplest correct approach
        label = AnchoredLabel(
            self._plotter,
            self._overlay,
            anchor=note.anchor,
            text=note.text,
            offset_px=note.label_offset_px,
            color=note.color,
            font_size=note.font_size,
            line_width=note.line_width,
        )
        label.set_visible(note.visible)
        self._labels[note.id] = label

    def remove(self, note_id: str) -> None:
        label = self._labels.pop(note_id, None)
        if label is not None:
            label.remove()

    def clear(self) -> None:
        for note_id in list(self._labels):
            self.remove(note_id)
