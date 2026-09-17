"""
Syncs Document.annotations (NoteAnnotation) to AnchoredLabel visuals. Same
"data -> actors" mapper shape as LayerRenderer/MeasurementRenderer —
MainWindow (Phase 6) calls this from Document's annotation_added/changed/
removed/reset signal handlers.
"""

from typing import Dict, Iterable, Union

from pps.render.labels import AnchoredLabel, ScreenLabel
from pps.scene.annotations import NoteAnnotation


class NoteRenderer:
    def __init__(self, plotter, overlay):
        self._plotter = plotter
        self._overlay = overlay
        self._labels: Dict[str, Union[AnchoredLabel, ScreenLabel]] = {}

    def sync_all(self, notes: Iterable[NoteAnnotation], layer_manager=None) -> None:
        notes = list(notes)
        wanted_ids = {n.id for n in notes}
        for stale_id in set(self._labels) - wanted_ids:
            self.remove(stale_id)
        for note in notes:
            self.sync_one(note, layer_visible=_layer_visible(layer_manager, note.layer_id))

    def sync_one(self, note: NoteAnnotation, layer_visible: bool = True) -> None:
        self.remove(note.id)  # rebuild from scratch: simplest correct approach
        if note.is_screen_note:
            label = ScreenLabel(
                self._overlay,
                pos_frac=note.screen_pos_frac or (0.5, 0.5),
                text=note.text,
                color=note.color,
                font_size=note.font_size,
            )
        else:
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
        # A note belonging to a hidden segment is hidden too, regardless of
        # its own visible flag — visibility cascades from the segment.
        label.set_visible(note.visible and layer_visible)
        self._labels[note.id] = label

    def remove(self, note_id: str) -> None:
        label = self._labels.pop(note_id, None)
        if label is not None:
            label.remove()

    def clear(self) -> None:
        for note_id in list(self._labels):
            self.remove(note_id)

    def set_highlighted(self, note_id) -> None:
        """Highlight exactly one note (or none), e.g. following selection
        in the Project dock's tree."""
        for oid, label in self._labels.items():
            label.set_highlighted(oid == note_id)


def _layer_visible(layer_manager, layer_id) -> bool:
    if layer_manager is None or layer_id is None:
        return True
    layer = layer_manager.get_by_id(layer_id)
    return True if layer is None else layer.visible
