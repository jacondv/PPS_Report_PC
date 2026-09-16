"""
Screen-space projection and hit-testing.

`project_to_screen` mirrors PointCloudViewer._project_to_screen() from the
old code exactly (same matrix math), so polygon/rectangle/lasso selection
behaves identically to before.
"""

from typing import List, Optional, Tuple

import numpy as np
from matplotlib.path import Path


def project_to_screen(points: np.ndarray, plotter) -> Optional[np.ndarray]:
    """Project 3D world points to 2D screen pixels (VTK convention: origin
    bottom-left), using the plotter's current camera. Returns None on any
    VTK/camera error (e.g. degenerate view) instead of raising, matching
    the old code's tolerance for a bad frame.
    """
    try:
        renderer = plotter.renderer
        camera = renderer.GetActiveCamera()
        aspect = renderer.GetTiledAspectRatio()

        def to_np(matrix):
            return np.array(
                [[matrix.GetElement(i, j) for j in range(4)] for i in range(4)],
                dtype=np.float64,
            )

        view = to_np(camera.GetViewTransformMatrix())
        proj = to_np(camera.GetProjectionTransformMatrix(aspect, -1, 1))

        n = len(points)
        homogeneous = np.ones((n, 4), dtype=np.float64)
        homogeneous[:, :3] = points

        clip = homogeneous @ view.T @ proj.T
        w = clip[:, 3:4]
        w = np.where(np.abs(w) < 1e-10, 1e-10, w)
        ndc = clip[:, :2] / w

        width, height = plotter.ren_win.GetSize()
        sx = (ndc[:, 0] + 1.0) * 0.5 * width
        sy = (ndc[:, 1] + 1.0) * 0.5 * height

        return np.column_stack([sx, sy])
    except Exception:
        return None


def points_in_polygon(points_2d: np.ndarray, polygon_2d: List[Tuple[float, float]]) -> np.ndarray:
    """Boolean mask of which `points_2d` fall inside the (screen-space)
    polygon. Works for any simple polygon, including a rectangle or a
    freehand lasso path — they're all just a list of vertices here."""
    if len(polygon_2d) < 3 or len(points_2d) == 0:
        return np.zeros(len(points_2d), dtype=bool)
    return Path(polygon_2d).contains_points(points_2d)


def rectangle_to_polygon(p0: Tuple[float, float], p1: Tuple[float, float]) -> List[Tuple[float, float]]:
    """Turn two opposite corners into a 4-vertex polygon for points_in_polygon."""
    x0, y0 = p0
    x1, y1 = p1
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
