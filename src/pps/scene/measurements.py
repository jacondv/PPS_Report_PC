"""Measurement models — distance between two 3D points, area of a region."""

import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from pps.core.layers import SourceRef

Point3D = Tuple[float, float, float]


@dataclass
class DistanceMeasurement:
    p1: Point3D
    p2: Point3D
    label_offset_px: Tuple[int, int] = (20, 20)
    color: str = "#4cc9f0"
    visible: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)

    @property
    def distance_m(self) -> float:
        return float(np.linalg.norm(np.asarray(self.p2) - np.asarray(self.p1)))

    @property
    def delta_xyz(self) -> Point3D:
        d = np.asarray(self.p2) - np.asarray(self.p1)
        return (float(d[0]), float(d[1]), float(d[2]))


@dataclass
class AreaMeasurement:
    boundary_px_at_creation: List[Tuple[float, float]]
    sources: List[SourceRef]
    centroid: Point3D
    area_m2: Optional[float] = None  # None while a background calc is running
    label_offset_px: Tuple[int, int] = (20, 20)
    color: str = "#4cc9f0"
    visible: bool = True
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
