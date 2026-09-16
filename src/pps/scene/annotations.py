"""Note annotation model — anchored to a 3D point on the cloud."""

import uuid
from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class NoteAnnotation:
    anchor: Tuple[float, float, float]
    text: str
    layer_id: str = None
    label_offset_px: Tuple[int, int] = (40, 40)
    color: str = "#ffd166"
    font_size: int = 14
    line_width: int = 2
    visible: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
