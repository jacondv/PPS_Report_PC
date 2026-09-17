"""
Note annotation model, covering two kinds of user-placed text (the "Note"
and "Annotation" tools):

- Anchored (`anchor` set): one end is a 3D point on the cloud, the other is
  draggable text connected to it by a leader line — what the Annotation
  tool creates.
- Screen-space (`anchor` is None, `screen_pos_frac` set instead): plain 2D
  text placed and dragged freely on top of the view, with no relation to
  the cloud at all — what the Note tool creates. `screen_pos_frac` is a
  normalized-viewport fraction (0..1, VTK convention: origin bottom-left)
  so the text stays in the same relative spot across window resizes.
"""

import uuid
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class NoteAnnotation:
    text: str
    anchor: Optional[Tuple[float, float, float]] = None
    screen_pos_frac: Optional[Tuple[float, float]] = None
    layer_id: Optional[str] = None
    label_offset_px: Tuple[int, int] = (40, 40)
    color: str = "#ffd166"
    font_size: int = 14
    line_width: int = 2
    visible: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def is_screen_note(self) -> bool:
        return self.anchor is None
