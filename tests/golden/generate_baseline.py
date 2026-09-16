"""
ONE-OFF script: run against the CURRENT (pre-refactor) code layout to freeze
golden numbers before any restructuring happens. Do not "fix" this script to
match new code — it exists to prove the new code matches the OLD behavior.

Run once from repo root:
    .venv\\Scripts\\python.exe tests\\golden\\generate_baseline.py
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np

from core.ply_loader import load_ply, get_ply_fields
from core.filename_parser import parse_filename
from core.calculator import calculate_area_and_volume, calculate_thickness_distribution
from report.core.html_pdf_generator import HTMLPDFGenerator

SAMPLE = os.path.join(
    ROOT, "sample", "2_thickness_01#20260203_093652#cloud_compared_07.ply"
)


def array_hash(arr: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def calc_result_to_dict(calc):
    return {
        "surface_area_m2": calc.surface_area_m2,
        "volume_m3": calc.volume_m3,
        "mean_thickness_mm": calc.mean_thickness_mm,
        "min_thickness_mm": calc.min_thickness_mm,
        "max_thickness_mm": calc.max_thickness_mm,
        "std_thickness_mm": calc.std_thickness_mm,
        "num_points": calc.num_points,
        "area_reached_target_m2": calc.area_reached_target_m2,
    }


def dist_to_dict(dist):
    return {
        "below_target": dist.below_target,
        "within_target": dist.within_target,
        "above_target": dist.above_target,
        "below_target_percent": dist.below_target_percent,
        "within_target_percent": dist.within_target_percent,
        "above_target_percent": dist.above_target_percent,
        "histogram_bins": list(dist.histogram_bins),
        "histogram_counts": [int(c) for c in dist.histogram_counts],
        "target_min": dist.target_min,
        "target_max": dist.target_max,
    }


def run_case(points, distances, target_min, target_max):
    # IMPORTANT: replicate CalculationWorker.run() exactly — same array object
    # is passed to both calls, in this order. calculate_area_and_volume()
    # mutates `distances` in place (clips |d|<12 and |d|>500 to 0); the
    # distribution below is computed on the POST-mutation array. This is the
    # existing (if surprising) behavior and must not change silently.
    calc = calculate_area_and_volume(points, distances, target_min=target_min)
    dist = calculate_thickness_distribution(distances, target_min, target_max)
    return calc, dist


def main():
    fields = get_ply_fields(SAMPLE)
    cloud = load_ply(SAMPLE, "distances" if "distances" in fields else fields[0])
    project_info = parse_filename(SAMPLE)

    baseline = {
        "sample_file": os.path.basename(SAMPLE),
        "fields": fields,
        "num_points": cloud.num_points,
        "points_hash": array_hash(cloud.points),
        "distances_hash_raw": array_hash(cloud.distances),
        "project_info": {
            "project_name": project_info.project_name,
            "job_number": project_info.job_number,
            "scan_time": project_info.scan_time,
            "segment_name": project_info.segment_name,
            "parse_success": project_info.parse_success,
            "formatted_date": project_info.formatted_date,
            "formatted_time": project_info.formatted_time,
        },
        "cases": [],
    }

    gen = HTMLPDFGenerator("unused.pdf")

    for target_min, target_max in [(40.0, 60.0), (50.0, 150.0)]:
        points = cloud.points.copy()
        distances = cloud.distances.copy()

        calc, dist = run_case(points, distances, target_min, target_max)

        case = {
            "target_min": target_min,
            "target_max": target_max,
            "calculation_result": calc_result_to_dict(calc),
            "thickness_distribution": dist_to_dict(dist),
            "distances_hash_after_mutation": array_hash(distances),
            "project_rows": gen._project_rows(project_info, calc, target_min, target_max, {}),
            "result_main_rows": gen._result_main_rows(calc),
            "result_stats_rows": gen._result_stats_rows(calc),
            "distribution_rows": gen._distribution_rows(dist, target_min, target_max),
        }
        baseline["cases"].append(case)

    # Deterministic "segment" golden: distance-range selection (no camera
    # needed, unlike polygon selection). This locks the exact mask semantics
    # (inclusive bounds) that the new Selection model must reproduce.
    mask = (cloud.distances >= 75) & (cloud.distances <= 125)
    seg_points = cloud.points[mask]
    seg_distances = cloud.distances[mask]
    baseline["distance_range_segment"] = {
        "range": [75, 125],
        "num_points": int(mask.sum()),
        "points_hash": array_hash(seg_points),
        "distances_hash": array_hash(seg_distances),
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_baseline.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
