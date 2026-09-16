"""
Layer model for point cloud management.
Each layer (original cloud or extracted segment) is an independent entity
with its own copy of points and distance data.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict
import numpy as np


@dataclass
class SourceRef:
    """Points a segment layer back to the indices it was carved from.

    `indices` are ascending positions into the source layer's own
    points/distances arrays at the time the segment was created (a project
    file stores these to be able to rebuild the segment after reloading the
    original PLY).
    """
    layer_id: str
    indices: np.ndarray


# Distinct colors for segments
SEGMENT_COLORS: List[Tuple[float, float, float]] = [
    (0.95, 0.25, 0.25),   # red
    (0.25, 0.85, 0.25),   # green
    (0.25, 0.50, 1.00),   # blue
    (1.00, 0.75, 0.20),   # yellow
    (0.85, 0.25, 1.00),   # purple
    (0.20, 0.90, 0.90),   # cyan
    (1.00, 0.50, 0.10),   # orange
    (0.60, 0.20, 0.80),   # violet
]


@dataclass
class Layer:
    """
    An independent point cloud layer.

    Attributes
    ----------
    id           : stable identifier (uuid), independent of the display name
    name         : display name (user-renamable)
    points       : (N, 3) XYZ coordinates
    distances    : (N,)   thickness in mm
    visible      : whether to show in 3D view and include in calculations
    is_original  : True for the PLY file loaded from disk
    color        : None  → use colormap (original only)
                   tuple → solid RGB color in [0, 1] (segments)
    sources      : for a segment, the (layer_id, indices) pairs it was
                   carved from — empty for the original layer
    """
    name: str
    points: np.ndarray
    distances: np.ndarray
    visible: bool = True
    is_original: bool = False
    color: Optional[Tuple[float, float, float]] = None
    annotations: List[Dict[str, object]] = field(default_factory=list)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    sources: List[SourceRef] = field(default_factory=list)

    @property
    def num_points(self) -> int:
        return len(self.points)

    def get_stats(self) -> dict:
        valid = self.distances[
            ~np.isnan(self.distances) & ~np.isinf(self.distances)
        ]
        if len(valid) == 0:
            return {'min': 0, 'max': 0, 'mean': 0, 'std': 0, 'median': 0}
        return {
            'min':    float(np.min(valid)),
            'max':    float(np.max(valid)),
            'mean':   float(np.mean(valid)),
            'std':    float(np.std(valid)),
            'median': float(np.median(valid)),
        }


class LayerManager:
    """
    Manages a list of Layer objects (one original + N segments).
    The original layer is always at index 0 when present.
    """

    def __init__(self):
        self._layers: List[Layer] = []
        self._seg_count: int = 0

    # ------------------------------------------------------------------ add / remove
    def set_original(self, name: str,
                     points: np.ndarray,
                     distances: np.ndarray) -> Layer:
        """Replace the original layer (only one allowed)."""
        self._layers = [l for l in self._layers if not l.is_original]
        layer = Layer(name=name, points=points, distances=distances,
                      visible=True, is_original=True, color=None)
        self._layers.insert(0, layer)
        return layer

    def build_segment(self,
                       points: np.ndarray,
                       distances: np.ndarray,
                       name: Optional[str] = None,
                       sources: Optional[List[SourceRef]] = None) -> Layer:
        """Construct a new segment Layer WITHOUT inserting it into this
        manager (used by undo commands, which control insertion timing)."""
        self._seg_count += 1
        if name is None:
            name = f"Segment_{self._seg_count}"
        color = SEGMENT_COLORS[(self._seg_count - 1) % len(SEGMENT_COLORS)]
        return Layer(name=name, points=points, distances=distances,
                     visible=True, is_original=False, color=color,
                     sources=sources or [])

    def add_segment(self,
                    points: np.ndarray,
                    distances: np.ndarray,
                    name: Optional[str] = None,
                    sources: Optional[List[SourceRef]] = None) -> Layer:
        """Create a new independent segment layer."""
        layer = self.build_segment(points, distances, name, sources)
        self._layers.append(layer)
        return layer

    def add_layer(self, layer: Layer) -> Layer:
        """Insert an already-built Layer (e.g. restored from a project file)."""
        if layer.is_original:
            self._layers = [l for l in self._layers if not l.is_original]
            self._layers.insert(0, layer)
        else:
            self._layers.append(layer)
        return layer

    def remove(self, name: str) -> bool:
        prev = len(self._layers)
        self._layers = [l for l in self._layers if l.name != name]
        return len(self._layers) < prev

    def remove_by_id(self, layer_id: str) -> bool:
        prev = len(self._layers)
        self._layers = [l for l in self._layers if l.id != layer_id]
        return len(self._layers) < prev

    def index_of(self, layer_id: str) -> Optional[int]:
        for i, l in enumerate(self._layers):
            if l.id == layer_id:
                return i
        return None

    def insert_at(self, index: int, layer: Layer) -> None:
        """Re-insert a previously-removed layer at a specific index (undo)."""
        index = max(0, min(index, len(self._layers)))
        self._layers.insert(index, layer)

    def rename(self, old_name: str, new_name: str) -> bool:
        layer = self.get(old_name)
        if layer is None:
            return False
        layer.name = new_name
        return True

    # ------------------------------------------------------------------ query
    def get(self, name: str) -> Optional[Layer]:
        for l in self._layers:
            if l.name == name:
                return l
        return None

    def get_by_id(self, layer_id: str) -> Optional[Layer]:
        for l in self._layers:
            if l.id == layer_id:
                return l
        return None

    @property
    def original(self) -> Optional[Layer]:
        for l in self._layers:
            if l.is_original:
                return l
        return None

    @property
    def layers(self) -> List[Layer]:
        return list(self._layers)

    def visible_layers(self) -> List[Layer]:
        return [l for l in self._layers if l.visible]

    def combined_visible(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Concatenate points + distances of all VISIBLE layers.
        Returns empty arrays if nothing is visible.
        """
        vis = self.visible_layers()
        if not vis:
            return np.empty((0, 3), dtype=np.float64), np.empty(0, dtype=np.float64)
        pts   = np.concatenate([l.points    for l in vis])
        dists = np.concatenate([l.distances for l in vis])
        return pts, dists

    def clear(self):
        self._layers.clear()
        self._seg_count = 0
