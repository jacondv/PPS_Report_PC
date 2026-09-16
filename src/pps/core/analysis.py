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


def run_analysis(
    points: np.ndarray,
    distances: np.ndarray,
    target_min: float,
    target_max: float,
) -> Tuple[CalculationResult, ThicknessDistribution]:
    calc = calculate_area_and_volume(points, distances, target_min=target_min)
    dist = calculate_thickness_distribution(distances, target_min, target_max)
    return calc, dist
