"""
Selection model: a boolean mask per currently-visible layer.

Deliberately kept outside Document's undo stack — selection changes are not
undoable (mirrors CloudCompare); only *acting* on a selection (e.g. turning
it into a segment) goes through scene/commands.py.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np

from pps.core.layers import LayerManager, SourceRef

SelectionMode = str  # "replace" | "add" | "subtract"


class Selection:
    def __init__(self, layer_manager: LayerManager):
        self._layer_manager = layer_manager
        self._masks: Dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------ mutation
    def clear(self) -> None:
        self._masks = {}

    def replace(self, masks: Dict[str, np.ndarray]) -> None:
        self._masks = {lid: m for lid, m in masks.items() if m.any()}

    def add(self, masks: Dict[str, np.ndarray]) -> None:
        for lid, mask in masks.items():
            existing = self._masks.get(lid)
            combined = mask if existing is None else (existing | mask)
            if combined.any():
                self._masks[lid] = combined

    def subtract(self, masks: Dict[str, np.ndarray]) -> None:
        for lid, mask in masks.items():
            existing = self._masks.get(lid)
            if existing is None:
                continue
            combined = existing & ~mask
            if combined.any():
                self._masks[lid] = combined
            else:
                self._masks.pop(lid, None)

    def apply(self, masks: Dict[str, np.ndarray], mode: SelectionMode = "replace") -> None:
        if mode == "replace":
            self.replace(masks)
        elif mode == "add":
            self.add(masks)
        elif mode == "subtract":
            self.subtract(masks)
        else:
            raise ValueError(f"Unknown selection mode: {mode!r}")

    def select_all(self) -> None:
        masks = {
            layer.id: np.ones(layer.num_points, dtype=bool)
            for layer in self._layer_manager.visible_layers()
        }
        self.replace(masks)

    def invert(self) -> None:
        masks = {}
        for layer in self._layer_manager.visible_layers():
            current = self._masks.get(layer.id)
            inverted = np.ones(layer.num_points, dtype=bool) if current is None else ~current
            masks[layer.id] = inverted
        self.replace(masks)

    def select_by_distance_range(
        self, min_d: float, max_d: float, mode: SelectionMode = "replace"
    ) -> None:
        masks = {
            layer.id: (layer.distances >= min_d) & (layer.distances <= max_d)
            for layer in self._layer_manager.visible_layers()
        }
        self.apply(masks, mode)

    # ------------------------------------------------------------------ query
    def is_empty(self) -> bool:
        return not any(mask.any() for mask in self._masks.values())

    def count(self) -> int:
        return sum(int(mask.sum()) for mask in self._masks.values())

    def mask_for(self, layer_id: str) -> Optional[np.ndarray]:
        return self._masks.get(layer_id)

    def to_sources(self) -> List[SourceRef]:
        """(layer_id, ascending indices) pairs, ordered like LayerManager.

        The ordering matters: it reproduces how the old code concatenated
        `[l.points for l in visible_layers]` before masking, so a segment
        built from this selection is byte-identical to the old behavior.
        """
        sources = []
        for layer in self._layer_manager.visible_layers():
            mask = self._masks.get(layer.id)
            if mask is None or not mask.any():
                continue
            indices = np.where(mask)[0].astype(np.uint32)
            sources.append(SourceRef(layer_id=layer.id, indices=indices))
        return sources

    def get_points_and_distances(self) -> Tuple[np.ndarray, np.ndarray]:
        """Concatenated (points, distances) for the current selection."""
        points_list, distances_list = [], []
        for ref in self.to_sources():
            layer = self._layer_manager.get_by_id(ref.layer_id)
            points_list.append(layer.points[ref.indices])
            distances_list.append(layer.distances[ref.indices])
        if not points_list:
            return np.empty((0, 3), dtype=np.float64), np.empty((0,), dtype=np.float64)
        return np.concatenate(points_list), np.concatenate(distances_list)
