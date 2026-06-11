"""
PLY file loader with support for custom scalar fields (distances).
"""

import numpy as np
from plyfile import PlyData
from dataclasses import dataclass
from typing import Optional, List, Tuple
import os


@dataclass
class PointCloudData:
    """Point cloud data structure."""
    points: np.ndarray  # (N, 3) array of XYZ coordinates
    distances: np.ndarray  # (N,) array of distance/thickness values in mm
    colors: Optional[np.ndarray] = None  # (N, 3) array of RGB colors
    normals: Optional[np.ndarray] = None  # (N, 3) array of normal vectors
    
    @property
    def num_points(self) -> int:
        return len(self.points)
    
    @property
    def bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Return (min_xyz, max_xyz) bounds."""
        return self.points.min(axis=0), self.points.max(axis=0)
    
    @property
    def center(self) -> np.ndarray:
        """Return center point of the cloud."""
        return self.points.mean(axis=0)
    
    def get_thickness_stats(self) -> dict:
        """Get statistics about thickness/distance values."""
        valid_distances = self.distances[~np.isnan(self.distances)]
        if len(valid_distances) == 0:
            return {
                'min': 0, 'max': 0, 'mean': 0, 'std': 0, 'median': 0
            }
        return {
            'min': float(np.min(valid_distances)),
            'max': float(np.max(valid_distances)),
            'mean': float(np.mean(valid_distances)),
            'std': float(np.std(valid_distances)),
            'median': float(np.median(valid_distances))
        }


def load_ply(filepath: str, distance_field: str = "distances") -> PointCloudData:
    """
    Load a PLY file with custom distance/thickness field.
    
    Args:
        filepath: Path to PLY file
        distance_field: Name of the scalar field containing thickness data
        
    Returns:
        PointCloudData object
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PLY file not found: {filepath}")
    
    plydata = PlyData.read(filepath)
    vertex = plydata['vertex']
    
    # Extract XYZ coordinates
    x = np.array(vertex['x'])
    y = np.array(vertex['y'])
    z = np.array(vertex['z'])
    points = np.column_stack((x, y, z))
    
    # Extract distances/thickness
    distances = None
    
    # Try multiple possible field names
    possible_names = [
        distance_field,
        'distances',
        'distance',
        'thickness',
        'scalar_distances',
        'scalar_Distances',
        'Distances',
        'C2C_absolute_distances',
        'C2C_signed_distances'
    ]
    
    for name in possible_names:
        try:
            distances = np.array(vertex[name], dtype=np.float64)
            mask = (distances > -25) & (distances < 25)
            distances[mask] = np.abs(distances[mask])
            distances = np.where(distances < -25, np.abs(distances), distances)

            print(f"Found distance field: '{name}'")
            break
        except (ValueError, KeyError):
            continue
    
    if distances is None:
        # List available fields for debugging
        available_fields = list(vertex.data.dtype.names)
        print(f"Warning: Distance field not found. Available fields: {available_fields}")
        # Create zero distances as fallback
        distances = np.zeros(len(points))
    
    # Extract colors if available
    colors = None
    try:
        r = np.array(vertex['red'])
        g = np.array(vertex['green'])
        b = np.array(vertex['blue'])
        colors = np.column_stack((r, g, b))
        # Normalize to 0-1 if values are 0-255
        if colors.max() > 1:
            colors = colors / 255.0
    except (ValueError, KeyError):
        pass
    
    # Extract normals if available
    normals = None
    try:
        nx = np.array(vertex['nx'])
        ny = np.array(vertex['ny'])
        nz = np.array(vertex['nz'])
        normals = np.column_stack((nx, ny, nz))
    except (ValueError, KeyError):
        pass
    
    return PointCloudData(
        points=points,
        distances=distances,
        colors=colors,
        normals=normals
    )


def get_ply_fields(filepath: str) -> List[str]:
    """Get list of all scalar fields in a PLY file."""
    plydata = PlyData.read(filepath)
    vertex = plydata['vertex']
    return list(vertex.data.dtype.names)


def filter_by_distance(cloud: PointCloudData, 
                       min_dist: float = None, 
                       max_dist: float = None) -> PointCloudData:
    """
    Filter point cloud by distance values.
    
    Args:
        cloud: Input point cloud
        min_dist: Minimum distance threshold (mm)
        max_dist: Maximum distance threshold (mm)
        
    Returns:
        Filtered PointCloudData
    """
    mask = np.ones(cloud.num_points, dtype=bool)
    
    if min_dist is not None:
        mask &= cloud.distances >= min_dist
    if max_dist is not None:
        mask &= cloud.distances <= max_dist
    
    return PointCloudData(
        points=cloud.points[mask],
        distances=cloud.distances[mask],
        colors=cloud.colors[mask] if cloud.colors is not None else None,
        normals=cloud.normals[mask] if cloud.normals is not None else None
    )
