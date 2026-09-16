import json
import os

from pps.core.job_info import resolve_targets


def test_no_job_info_file_uses_fixed_fallback(tmp_path):
    ply_path = tmp_path / "sample.ply"
    ply_path.write_bytes(b"")
    assert resolve_targets(str(ply_path)) == (40.0, 60.0)


def test_job_info_file_overrides_targets(tmp_path):
    ply_path = tmp_path / "sample.ply"
    ply_path.write_bytes(b"")
    job_info = {
        "name": "JOB20260528",
        "parameters": {"target_thickness": 60, "tolerance": 10},
    }
    (tmp_path / "job_info.json").write_text(json.dumps(job_info), encoding="utf-8")

    assert resolve_targets(str(ply_path)) == (50, 70)


def test_job_info_file_missing_parameters_uses_defaults(tmp_path):
    ply_path = tmp_path / "sample.ply"
    ply_path.write_bytes(b"")
    (tmp_path / "job_info.json").write_text(json.dumps({}), encoding="utf-8")

    # default target_thickness=30, tolerance=10
    assert resolve_targets(str(ply_path)) == (20, 40)
