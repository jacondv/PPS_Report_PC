"""
Maps a Layer's thickness values to RGB colors and keeps a pyvista actor per
layer in sync with the Document.

Color thresholds replicate PointCloudViewer.assign_colors() from the old
gui/viewer_3d.py exactly (including the fact that the "above max" and "far"
buckets are both blue) — this must not change without an explicit decision,
since it affects report screenshots.
"""

from typing import Dict, Optional, Tuple

import numpy as np
import pyvista as pv

from pps.core.layers import Layer

FAR_THRESHOLD_MM = 150.0

ColorRGB = Tuple[float, float, float]

DEFAULT_COLOR_BELOW: ColorRGB = (1.0, 0.0, 0.0)
DEFAULT_COLOR_WITHIN: ColorRGB = (0.0, 1.0, 0.0)
DEFAULT_COLOR_ABOVE: ColorRGB = (0.0, 0.0, 1.0)
DEFAULT_COLOR_FAR: ColorRGB = (0.0, 0.0, 1.0)


def threshold_colors(
    distances: np.ndarray,
    target_min: float,
    target_max: float,
    color_below: ColorRGB = DEFAULT_COLOR_BELOW,
    color_within: ColorRGB = DEFAULT_COLOR_WITHIN,
    color_above: ColorRGB = DEFAULT_COLOR_ABOVE,
    color_far: ColorRGB = DEFAULT_COLOR_FAR,
) -> np.ndarray:
    colors = np.zeros((len(distances), 3), dtype=np.float32)
    colors[distances < target_min] = color_below
    colors[(distances >= target_min) & (distances <= target_max)] = color_within
    colors[(distances > target_max) & (distances < FAR_THRESHOLD_MM)] = color_above
    colors[distances >= FAR_THRESHOLD_MM] = color_far
    return colors


class LayerRenderer:
    """Owns the pyvista actor for each visible Layer inside one plotter."""

    def __init__(self, plotter):
        self._plotter = plotter
        self._actors: Dict[str, object] = {}

    def sync(
        self,
        layer: Layer,
        target_min: float,
        target_max: float,
        point_size: int = 3,
    ):
        """(Re)build the actor for `layer` from scratch and return it."""
        self.remove(layer.name)

        cloud = pv.PolyData(layer.points)
        cloud["thickness"] = layer.distances
        if layer.color is None:
            cloud["colors"] = threshold_colors(layer.distances, target_min, target_max)
        else:
            cloud["colors"] = np.tile(
                np.asarray(layer.color, dtype=np.float32), (layer.num_points, 1)
            )

        actor = self._plotter.add_mesh(
            cloud,
            scalars="colors",
            rgb=True,
            point_size=point_size,
            render_points_as_spheres=True,
            show_scalar_bar=False,
            name=f"layer_{layer.name}",
        )
        actor.SetVisibility(layer.visible)
        self._actors[layer.name] = actor
        return actor

    def set_visible(self, layer_name: str, visible: bool) -> None:
        actor = self._actors.get(layer_name)
        if actor is not None:
            actor.SetVisibility(visible)

    def remove(self, layer_name: str) -> None:
        actor = self._actors.pop(layer_name, None)
        if actor is not None:
            try:
                self._plotter.remove_actor(actor)
            except Exception:
                pass

    def clear(self) -> None:
        for layer_name in list(self._actors):
            self.remove(layer_name)

    def get(self, layer_name: str) -> Optional[object]:
        return self._actors.get(layer_name)
