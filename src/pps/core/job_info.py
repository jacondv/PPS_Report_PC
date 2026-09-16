"""
Resolve thickness targets from a `job_info.json` file sitting next to a PLY.

Extracted from the old MainWindow._load_file(); default targets and the
target_thickness/tolerance keys must stay exactly as before.
"""

import json
import logging
import os
from typing import Tuple

logger = logging.getLogger(__name__)

DEFAULT_TARGET_MIN_NO_JOB_INFO = 40.0
DEFAULT_TARGET_MAX_NO_JOB_INFO = 60.0
DEFAULT_TARGET_THICKNESS = 30
DEFAULT_TOLERANCE = 10


def resolve_targets(ply_filepath: str) -> Tuple[float, float]:
    """Return (target_min, target_max) for the PLY at `ply_filepath`.

    Looks for a `job_info.json` file in the same directory. If present,
    reads `parameters.target_thickness` / `parameters.tolerance` (default
    30/10) and returns (target_thickness - tolerance, target_thickness +
    tolerance). If absent, returns the fixed fallback (40, 60).
    """
    job_info_path = os.path.join(os.path.dirname(ply_filepath), 'job_info.json')

    if not os.path.exists(job_info_path):
        return DEFAULT_TARGET_MIN_NO_JOB_INFO, DEFAULT_TARGET_MAX_NO_JOB_INFO

    with open(job_info_path, 'r') as f:
        job_info = json.load(f)
    logger.debug("Loaded job info: %s", job_info)

    parameters = job_info.get('parameters', {})
    target_thickness = parameters.get('target_thickness', DEFAULT_TARGET_THICKNESS)
    tolerance = parameters.get('tolerance', DEFAULT_TOLERANCE)

    return target_thickness - tolerance, target_thickness + tolerance
