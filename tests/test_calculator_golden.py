"""
Verifies the moved/restructured code reproduces the exact numbers frozen in
tests/golden/sample_baseline.json (generated from the pre-refactor code).
Any diff here means a behavior change slipped in — fix the new code, never
the baseline, unless the user explicitly approves a numeric change.
"""

import hashlib
import json
import os

import numpy as np
import pytest

from pps.core.ply_loader import load_ply
from pps.core.analysis import run_analysis

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "golden", "sample_baseline.json")


def array_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


@pytest.fixture(scope="module")
def baseline():
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def cloud(sample_ply_path):
    return load_ply(sample_ply_path, "distances")


def test_load_matches_baseline(baseline, cloud):
    assert cloud.num_points == baseline["num_points"]
    assert array_hash(cloud.points) == baseline["points_hash"]
    assert array_hash(cloud.distances) == baseline["distances_hash_raw"]


@pytest.mark.parametrize("case_index", [0, 1])
def test_analysis_matches_baseline(baseline, cloud, case_index):
    case = baseline["cases"][case_index]
    points = cloud.points.copy()
    distances = cloud.distances.copy()

    calc, dist = run_analysis(points, distances, case["target_min"], case["target_max"])

    expected_calc = case["calculation_result"]
    for field, expected in expected_calc.items():
        actual = getattr(calc, field)
        assert actual == pytest.approx(expected, rel=1e-9), field

    expected_dist = case["thickness_distribution"]
    assert dist.below_target == expected_dist["below_target"]
    assert dist.within_target == expected_dist["within_target"]
    assert dist.above_target == expected_dist["above_target"]
    assert dist.below_target_percent == pytest.approx(expected_dist["below_target_percent"])
    assert dist.within_target_percent == pytest.approx(expected_dist["within_target_percent"])
    assert dist.above_target_percent == pytest.approx(expected_dist["above_target_percent"])
    assert list(dist.histogram_counts) == expected_dist["histogram_counts"]

    # the in-place mutation of `distances` must still happen (§7 of the plan)
    assert array_hash(distances) == case["distances_hash_after_mutation"]


def test_distance_range_segment_matches_baseline(baseline, cloud):
    seg = baseline["distance_range_segment"]
    lo, hi = seg["range"]
    mask = (cloud.distances >= lo) & (cloud.distances <= hi)

    assert int(mask.sum()) == seg["num_points"]
    assert array_hash(cloud.points[mask]) == seg["points_hash"]
    assert array_hash(cloud.distances[mask]) == seg["distances_hash"]
