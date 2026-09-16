"""
Run the area/volume/distribution calculation pipeline.

This replicates CalculationWorker.run() from the old gui/main_window.py
exactly: `calculate_area_and_volume()` mutates `distances` in place (clips
|d|<12 and |d|>500 to 0), and `calculate_thickness_distribution()` is then
called on that SAME mutated array. The order and the shared array are load
bearing for the reported Below/Within/Above counts — do not "fix" this by
passing a copy.
"""

from typing import Tuple

import numpy as np

from pps.core.calculator import (
    CalculationResult,
    ThicknessDistribution,
    calculate_area_and_volume,
    calculate_thickness_distribution,
)
from pps.core.surface_area import surface_area

# Same radii as calculate_area_and_volume() uses for the report's surface
# area — the Measure Area tool must stay consistent with the report number.
AREA_MEASUREMENT_RADII = (0.05, 0.1)


def run_analysis(
    points: np.ndarray,
    distances: np.ndarray,
    target_min: float,
    target_max: float,
) -> Tuple[CalculationResult, ThicknessDistribution]:
    calc = calculate_area_and_volume(points, distances, target_min=target_min)
    dist = calculate_thickness_distribution(distances, target_min, target_max)
    return calc, dist


def compute_area_m2(points: np.ndarray, radii: Tuple[float, float] = AREA_MEASUREMENT_RADII) -> float:
    """Surface area (m²) of a raw point set via the same BPA method/radii
    used for the report's surface area — used by the Measure Area tool."""
    import open3d as o3d

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    return surface_area(pcd, radii=radii)
