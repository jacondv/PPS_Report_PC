"""
Core modules for tunnel analysis.
"""

from .ply_loader import load_ply, PointCloudData, get_ply_fields, filter_by_distance
from .filename_parser import parse_filename, ProjectInfo
from .calculator import (
    calculate_area_and_volume, 
    calculate_thickness_distribution,
    CalculationResult,
    ThicknessDistribution
)
from .segmentation import SegmentationState, Segment, SelectionMode
from .layer_manager import Layer, LayerManager

__all__ = [
    'load_ply',
    'PointCloudData',
    'get_ply_fields',
    'filter_by_distance',
    'parse_filename',
    'ProjectInfo',
    'calculate_area_and_volume',
    'calculate_thickness_distribution',
    'CalculationResult',
    'ThicknessDistribution',
    'SegmentationState',
    'Segment',
    'SelectionMode',
    'Layer',
    'LayerManager',
]
