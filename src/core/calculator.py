"""
Calculate surface area and volume from point cloud data.
Uses surface reconstruction and thickness information.
"""

import numpy as np
from scipy.spatial import Delaunay, ConvexHull
from dataclasses import dataclass
from typing import Tuple, List, Optional
import warnings


@dataclass
class CalculationResult:
    """Results from area and volume calculations."""
    surface_area_m2: float  # Surface area in square meters
    volume_m3: float  # Volume in cubic meters
    mean_thickness_mm: float  # Mean thickness in mm
    min_thickness_mm: float
    max_thickness_mm: float
    std_thickness_mm: float
    num_points: int
    
    @property
    def surface_area_cm2(self) -> float:
        return self.surface_area_m2 * 10000
    
    @property
    def volume_liters(self) -> float:
        return self.volume_m3 * 1000


@dataclass
class ThicknessDistribution:
    """Thickness distribution for histogram."""
    below_target: int  # Points below target thickness
    within_target: int  # Points within target range
    above_target: int  # Points above target thickness
    
    below_target_percent: float
    within_target_percent: float
    above_target_percent: float
    
    histogram_bins: np.ndarray
    histogram_counts: np.ndarray
    
    target_min: float
    target_max: float


def estimate_surface_area_alpha_shape(points: np.ndarray, alpha: float = None) -> float:
    """
    Estimate surface area using alpha shape (2D projection + 3D correction).
    
    For tunnel surfaces, we project to a local 2D plane and compute area,
    then apply a correction factor based on surface curvature.
    
    Args:
        points: (N, 3) array of XYZ coordinates
        alpha: Alpha value for alpha shape (auto-computed if None)
        
    Returns:
        Estimated surface area in square units (same as input units)
    """
    if len(points) < 3:
        return 0.0
    
    try:
        # Use convex hull for robust area estimation
        hull = ConvexHull(points)
        return hull.area
    except Exception as e:
        warnings.warn(f"ConvexHull failed: {e}. Using approximate method.")
        return estimate_surface_area_grid(points)


def estimate_surface_area_grid(points: np.ndarray, grid_size: float = None) -> float:
    """
    Estimate surface area using grid-based method.
    
    Divides the point cloud into a grid and estimates local surface area
    for each cell, then sums them up.
    
    Args:
        points: (N, 3) array of XYZ coordinates
        grid_size: Size of grid cells (auto-computed if None)
        
    Returns:
        Estimated surface area
    """
    if len(points) < 3:
        return 0.0
    
    # Compute point density and estimate grid size
    if grid_size is None:
        # Use k-nearest neighbors to estimate local density
        from scipy.spatial import cKDTree
        tree = cKDTree(points)
        # Sample a subset for efficiency
        sample_size = min(1000, len(points))
        sample_indices = np.random.choice(len(points), sample_size, replace=False)
        sample_points = points[sample_indices]
        
        # Find distances to nearest neighbors
        distances, _ = tree.query(sample_points, k=6)
        mean_spacing = np.mean(distances[:, 1:])  # Exclude self
        grid_size = mean_spacing * 3
    
    # Create 2D grid projection (assuming tunnel axis is roughly along one axis)
    # Find principal axes
    centered = points - points.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    
    # Project onto the two largest principal components
    proj_axes = eigenvectors[:, 1:]  # Two largest
    projected_2d = centered @ proj_axes
    
    # Grid-based area estimation
    min_xy = projected_2d.min(axis=0)
    max_xy = projected_2d.max(axis=0)
    
    nx = max(1, int((max_xy[0] - min_xy[0]) / grid_size))
    ny = max(1, int((max_xy[1] - min_xy[1]) / grid_size))
    
    # Count occupied cells
    grid_indices_x = np.clip(((projected_2d[:, 0] - min_xy[0]) / grid_size).astype(int), 0, nx-1)
    grid_indices_y = np.clip(((projected_2d[:, 1] - min_xy[1]) / grid_size).astype(int), 0, ny-1)
    
    occupied = set(zip(grid_indices_x, grid_indices_y))
    cell_area = grid_size ** 2
    
    # Apply correction factor for 3D surface (typically 1.1-1.3 for curved surfaces)
    correction_factor = 1.15
    
    return len(occupied) * cell_area * correction_factor


def estimate_surface_area_triangulation(points: np.ndarray) -> float:
    """
    Estimate surface area using Delaunay triangulation.
    
    This method creates a triangulated surface from the points
    and sums the areas of all triangles.
    
    Args:
        points: (N, 3) array of XYZ coordinates
        
    Returns:
        Estimated surface area
    """
    if len(points) < 4:
        return 0.0
    
    try:
        # Use Open3D for better surface reconstruction if available
        import open3d as o3d
        
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        
        # Estimate normals
        pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=0.1, max_nn=30))
        pcd.orient_normals_consistent_tangent_plane(k=15)
        
        # Ball pivoting or Poisson reconstruction
        radii = [0.005, 0.01, 0.02, 0.04]
        mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_ball_pivoting(
            pcd, o3d.utility.DoubleVector(radii))
        
        if len(mesh.triangles) > 0:
            return mesh.get_surface_area()
        
    except ImportError:
        pass
    except Exception as e:
        warnings.warn(f"Open3D triangulation failed: {e}")
    
    # Fallback to convex hull
    return estimate_surface_area_alpha_shape(points)


def calculate_area_and_volume(points: np.ndarray, 
                              distances: np.ndarray,
                              method: str = "grid") -> CalculationResult:
    """
    Calculate surface area and volume from point cloud.
    
    Volume is calculated as: Surface Area × Mean Thickness
    
    Args:
        points: (N, 3) array of XYZ coordinates (assumed to be in meters)
        distances: (N,) array of thickness values in mm
        method: Area calculation method ("grid", "hull", "triangulation")
        
    Returns:
        CalculationResult with area and volume
    """
    if len(points) == 0:
        return CalculationResult(
            surface_area_m2=0,
            volume_m3=0,
            mean_thickness_mm=0,
            min_thickness_mm=0,
            max_thickness_mm=0,
            std_thickness_mm=0,
            num_points=0
        )
    
    # Filter out invalid distance values
    valid_mask = ~np.isnan(distances) & ~np.isinf(distances)
    valid_distances = distances[valid_mask]
    
    if len(valid_distances) == 0:
        valid_distances = np.array([0])
    
    # Calculate surface area based on method
    if method == "hull":
        surface_area = estimate_surface_area_alpha_shape(points)
    elif method == "triangulation":
        surface_area = estimate_surface_area_triangulation(points)
    else:  # grid
        surface_area = estimate_surface_area_grid(points)
    
    # Convert to square meters if needed (assuming input is in meters)
    surface_area_m2 = surface_area
    
    # Calculate mean thickness
    mean_thickness_mm = float(np.mean(valid_distances))
    mean_thickness_m = mean_thickness_mm / 1000.0  # Convert mm to m
    
    # Calculate volume: Area × Thickness
    volume_m3 = surface_area_m2 * mean_thickness_m
    
    return CalculationResult(
        surface_area_m2=surface_area_m2,
        volume_m3=volume_m3,
        mean_thickness_mm=mean_thickness_mm,
        min_thickness_mm=float(np.min(valid_distances)),
        max_thickness_mm=float(np.max(valid_distances)),
        std_thickness_mm=float(np.std(valid_distances)),
        num_points=len(points)
    )


def calculate_thickness_distribution(distances: np.ndarray,
                                    target_min: float,
                                    target_max: float,
                                    num_bins: int = 50) -> ThicknessDistribution:
    """
    Calculate thickness distribution for histogram.
    
    Args:
        distances: Array of thickness values in mm
        target_min: Minimum target thickness (mm)
        target_max: Maximum target thickness (mm)
        num_bins: Number of histogram bins
        
    Returns:
        ThicknessDistribution with histogram data
    """
    # Filter valid values
    valid = distances[~np.isnan(distances) & ~np.isinf(distances)]
    
    if len(valid) == 0:
        return ThicknessDistribution(
            below_target=0,
            within_target=0,
            above_target=0,
            below_target_percent=0,
            within_target_percent=0,
            above_target_percent=0,
            histogram_bins=np.array([]),
            histogram_counts=np.array([]),
            target_min=target_min,
            target_max=target_max
        )
    
    # Count points in each category
    below = np.sum(valid < target_min)
    within = np.sum((valid >= target_min) & (valid <= target_max))
    above = np.sum(valid > target_max)
    
    total = len(valid)
    
    # Create histogram
    hist_min = max(0, valid.min() - 10)
    hist_max = valid.max() + 10
    bins = np.linspace(hist_min, hist_max, num_bins + 1)
    counts, _ = np.histogram(valid, bins=bins)
    
    return ThicknessDistribution(
        below_target=int(below),
        within_target=int(within),
        above_target=int(above),
        below_target_percent=100 * below / total,
        within_target_percent=100 * within / total,
        above_target_percent=100 * above / total,
        histogram_bins=bins,
        histogram_counts=counts,
        target_min=target_min,
        target_max=target_max
    )
