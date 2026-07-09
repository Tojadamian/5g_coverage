"""
Geographic Study Area and Ground Receiver Grid System

Defines a rectangular study area and generates a grid of ground receiver
locations for 5G coverage evaluation. Includes distance and elevation angle
calculations for satellite-to-ground links.

Physical Models:
    - WGS84 geodetic coordinates
    - Haversine distance formula for great-circle paths
    - Elevation angle from satellite position
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple


# ==================== WGS84 GEODETIC CONSTANTS ====================

EARTH_RADIUS_M = 6371000  # Mean Earth radius in meters
EARTH_EQUATORIAL_RADIUS = 6378137  # WGS84 equatorial radius
EARTH_POLAR_RADIUS = 6356752  # WGS84 polar radius


# ==================== STUDY AREA DEFINITION ====================

@dataclass
class StudyArea:
    """
    Defines rectangular study region for 5G-NTN coverage evaluation.
    
    Attributes:
        center_lat: Center latitude in degrees (-90 to +90)
        center_lon: Center longitude in degrees (-180 to +180)
        width_km: East-West extent in kilometers
        height_km: North-South extent in kilometers
        resolution_m: Grid resolution (spacing between test points)
        min_elevation_deg: Minimum satellite elevation angle for coverage
    """
    center_lat: float
    center_lon: float
    width_km: float
    height_km: float
    resolution_m: int = 1000  # 1 km default resolution
    min_elevation_deg: float = 5.0  # Typical NTN minimum elevation
    
    def __post_init__(self):
        """Validate study area parameters."""
        if not -90 <= self.center_lat <= 90:
            raise ValueError(f"Latitude must be -90 to +90, got {self.center_lat}")
        if not -180 <= self.center_lon <= 180:
            raise ValueError(f"Longitude must be -180 to +180, got {self.center_lon}")
        if self.width_km <= 0 or self.height_km <= 0:
            raise ValueError(f"Width and height must be positive, got {self.width_km}x{self.height_km}")
        if self.resolution_m <= 0:
            raise ValueError(f"Resolution must be positive, got {self.resolution_m}")
        if not 0 <= self.min_elevation_deg <= 90:
            raise ValueError(f"Min elevation must be 0-90 deg, got {self.min_elevation_deg}")
    
    @property
    def bounds_deg(self) -> dict:
        """Return study area bounds in degrees (approximate)."""
        # Simple approximation: 1 degree ≈ 111 km at equator
        lat_offset = self.height_km / 111.0 / 2.0
        lon_offset = self.width_km / 111.0 / 2.0
        
        return {
            "min_lat": self.center_lat - lat_offset,
            "max_lat": self.center_lat + lat_offset,
            "min_lon": self.center_lon - lon_offset,
            "max_lon": self.center_lon + lon_offset,
        }
    
    def generate_receiver_grid(self) -> List[Tuple[float, float]]:
        """
        Generate regular grid of ground receiver locations.
        
        Returns:
            List of (latitude, longitude) tuples in degrees
            
        Notes:
            Uses simple lat/lon grid. For large areas near poles,
            consider more sophisticated geographic projections.
        """
        bounds = self.bounds_deg
        
        # Convert resolution from meters to degrees (rough approximation)
        resolution_deg = self.resolution_m / 111000.0  # meters per degree latitude
        
        # Generate grid
        latitudes = np.arange(bounds["min_lat"], bounds["max_lat"], resolution_deg)
        longitudes = np.arange(bounds["min_lon"], bounds["max_lon"], resolution_deg)
        
        # Create grid points
        grid_points = []
        for lat in latitudes:
            for lon in longitudes:
                # Skip poles region
                if abs(lat) < 85:
                    grid_points.append((lat, lon))
        
        return grid_points


# ==================== GEOMETRIC CALCULATIONS ====================

def haversine_distance(
    lat1_deg: float, lon1_deg: float,
    lat2_deg: float, lon2_deg: float,
) -> float:
    """
    Calculate great-circle distance between two points on Earth.
    
    Uses haversine formula for improved numerical stability at small distances.
    
    Args:
        lat1_deg, lon1_deg: First point coordinates in degrees
        lat2_deg, lon2_deg: Second point coordinates in degrees
        
    Returns:
        Distance in meters
        
    Formula:
        a = sin²(Δlat/2) + cos(lat1)*cos(lat2)*sin²(Δlon/2)
        c = 2*atan2(√a, √(1-a))
        d = R*c
    """
    # Convert to radians
    lat1, lon1 = np.radians(lat1_deg), np.radians(lon1_deg)
    lat2, lon2 = np.radians(lat2_deg), np.radians(lon2_deg)
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    
    distance_m = EARTH_RADIUS_M * c
    return distance_m


def calculate_slant_distance(
    ground_lat_deg: float, ground_lon_deg: float,
    sat_lat_deg: float, sat_lon_deg: float, sat_altitude_m: float,
) -> float:
    """
    Calculate 3D slant distance from ground receiver to satellite.
    
    Args:
        ground_lat_deg, ground_lon_deg: Ground receiver coordinates (degrees)
        sat_lat_deg, sat_lon_deg: Satellite nadir point coordinates (degrees)
        sat_altitude_m: Satellite altitude above Earth surface (meters)
        
    Returns:
        Slant distance in meters
    """
    # Ground distance via haversine
    ground_distance_m = haversine_distance(
        ground_lat_deg, ground_lon_deg,
        sat_lat_deg, sat_lon_deg
    )
    
    # 3D distance using Pythagorean theorem
    # (Assumes Earth is flat locally, valid for distances < 100 km)
    slant_distance = np.sqrt(ground_distance_m**2 + sat_altitude_m**2)
    
    return slant_distance


def calculate_elevation_angle(
    ground_lat_deg: float, ground_lon_deg: float,
    sat_lat_deg: float, sat_lon_deg: float, sat_altitude_m: float,
) -> float:
    """
    Calculate elevation angle from ground receiver to satellite.
    
    Elevation angle is the angle above the horizon (0° = horizon, 90° = zenith).
    
    Args:
        ground_lat_deg, ground_lon_deg: Ground receiver coordinates (degrees)
        sat_lat_deg, sat_lon_deg: Satellite nadir point coordinates (degrees)
        sat_altitude_m: Satellite altitude above Earth surface (meters)
        
    Returns:
        Elevation angle in degrees (0-90)
        
    Notes:
        Uses simple geometry assuming Earth is flat locally.
        For high-precision calculations near poles, use more sophisticated
        geodetic transformations.
    """
    # Ground distance via haversine
    ground_distance_m = haversine_distance(
        ground_lat_deg, ground_lon_deg,
        sat_lat_deg, sat_lon_deg
    )
    
    # Elevation angle from simple geometry
    # tan(elevation) = altitude / ground_distance
    if ground_distance_m == 0:
        # Receiver directly below satellite
        elevation_angle_deg = 90.0
    else:
        elevation_angle_rad = np.arctan2(sat_altitude_m, ground_distance_m)
        elevation_angle_deg = np.degrees(elevation_angle_rad)
    
    # Clamp to valid range
    elevation_angle_deg = np.clip(elevation_angle_deg, 0, 90)
    
    return elevation_angle_deg


def calculate_azimuth_angle(
    ground_lat_deg: float, ground_lon_deg: float,
    sat_lat_deg: float, sat_lon_deg: float,
) -> float:
    """
    Calculate azimuth angle from ground receiver to satellite.
    
    Azimuth is measured clockwise from north (0° = north, 90° = east, etc.).
    
    Args:
        ground_lat_deg, ground_lon_deg: Ground receiver coordinates (degrees)
        sat_lat_deg, sat_lon_deg: Satellite nadir point coordinates (degrees)
        
    Returns:
        Azimuth angle in degrees (0-360)
    """
    lat1 = np.radians(ground_lat_deg)
    lon1 = np.radians(ground_lon_deg)
    lat2 = np.radians(sat_lat_deg)
    lon2 = np.radians(sat_lon_deg)
    
    dlon = lon2 - lon1
    
    # Forward azimuth formula
    y = np.sin(dlon) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    
    azimuth_rad = np.arctan2(y, x)
    azimuth_deg = np.degrees(azimuth_rad)
    
    # Convert to 0-360 range
    azimuth_deg = azimuth_deg % 360
    
    return azimuth_deg


# ==================== COVERAGE ANALYSIS ====================

class GroundReceiverGrid:
    """
    Manages a geographic grid of ground receiver test points.
    
    Provides methods to:
    - Generate receiver locations
    - Calculate satellite geometry for each receiver
    - Filter receivers by visibility (elevation angle)
    - Aggregate coverage statistics
    """
    
    def __init__(self, study_area: StudyArea):
        """
        Initialize receiver grid.
        
        Args:
            study_area: StudyArea instance defining simulation region
        """
        self.study_area = study_area
        self.receiver_locations = self.study_area.generate_receiver_grid()
        
    def get_num_receivers(self) -> int:
        """Return total number of test points in grid."""
        return len(self.receiver_locations)
    
    def get_receiver_geometry(
        self,
        sat_lat_deg: float,
        sat_lon_deg: float,
        sat_altitude_m: float,
    ) -> List[dict]:
        """
        Calculate satellite geometry for all ground receivers.
        
        Args:
            sat_lat_deg, sat_lon_deg: Satellite nadir coordinates (degrees)
            sat_altitude_m: Satellite altitude above Earth surface (meters)
            
        Returns:
            List of dicts with keys:
                - 'index': Receiver index
                - 'lat', 'lon': Receiver coordinates (degrees)
                - 'slant_distance_m': 3D distance to satellite (meters)
                - 'elevation_angle_deg': Elevation angle (0-90 degrees)
                - 'azimuth_angle_deg': Azimuth angle (0-360 degrees)
                - 'visible': Boolean (True if elevation > min_elevation)
        """
        geometry_list = []
        
        for idx, (rx_lat, rx_lon) in enumerate(self.receiver_locations):
            slant_dist = calculate_slant_distance(
                rx_lat, rx_lon,
                sat_lat_deg, sat_lon_deg,
                sat_altitude_m
            )
            
            elev_angle = calculate_elevation_angle(
                rx_lat, rx_lon,
                sat_lat_deg, sat_lon_deg,
                sat_altitude_m
            )
            
            azim_angle = calculate_azimuth_angle(
                rx_lat, rx_lon,
                sat_lat_deg, sat_lon_deg
            )
            
            is_visible = elev_angle >= self.study_area.min_elevation_deg
            
            geometry_list.append({
                'index': idx,
                'lat': rx_lat,
                'lon': rx_lon,
                'slant_distance_m': slant_dist,
                'elevation_angle_deg': elev_angle,
                'azimuth_angle_deg': azim_angle,
                'visible': is_visible,
            })
        
        return geometry_list


if __name__ == "__main__":
    # Self-test: Generate study area and receiver grid
    print("=" * 60)
    print("GEOGRAPHIC STUDY AREA INITIALIZATION")
    print("=" * 60)
    
    # Define study area: 50km x 50km around Central Europe
    study_area = StudyArea(
        center_lat=50.0,  # Central Europe (Prague area)
        center_lon=15.0,
        width_km=50,
        height_km=50,
        resolution_m=5000,  # 5 km spacing
        min_elevation_deg=5.0,
    )
    
    print(f"\nStudy Area Definition:")
    print(f"  Center: {study_area.center_lat}°N, {study_area.center_lon}°E")
    print(f"  Size: {study_area.width_km} km × {study_area.height_km} km")
    print(f"  Resolution: {study_area.resolution_m} m")
    
    bounds = study_area.bounds_deg
    print(f"  Bounds: {bounds['min_lat']:.2f}°-{bounds['max_lat']:.2f}°N, "
          f"{bounds['min_lon']:.2f}°-{bounds['max_lon']:.2f}°E")
    
    # Generate receiver grid
    grid = GroundReceiverGrid(study_area)
    print(f"\nGenerated {grid.get_num_receivers()} ground receiver test points")
    
    # Sample satellite geometry
    sat_lat, sat_lon = 50.0, 15.0  # Satellite passing over study area center
    sat_altitude_m = 540 * 1000  # 540 km LEO altitude
    
    print(f"\nSample Satellite Geometry:")
    print(f"  Satellite position: {sat_lat}°N, {sat_lon}°E at {sat_altitude_m/1000:.0f} km altitude")
    
    geometry = grid.get_receiver_geometry(sat_lat, sat_lon, sat_altitude_m)
    
    # Show statistics
    visible_count = sum(1 for g in geometry if g['visible'])
    print(f"  Visible receivers (elevation > {study_area.min_elevation_deg}°): {visible_count}/{grid.get_num_receivers()}")
    
    # Find coverage extremes
    distances = [g['slant_distance_m'] for g in geometry if g['visible']]
    elevations = [g['elevation_angle_deg'] for g in geometry if g['visible']]
    
    if distances:
        print(f"  Slant distance range: {min(distances)/1000:.0f} - {max(distances)/1000:.0f} km")
        print(f"  Elevation angle range: {min(elevations):.1f}° - {max(elevations):.1f}°")
        
        # Show sample receiver closest to satellite
        closest_idx = np.argmin(distances)
        closest = geometry[closest_idx]
        print(f"\n  Closest visible receiver:")
        print(f"    Location: {closest['lat']:.2f}°N, {closest['lon']:.2f}°E")
        print(f"    Slant distance: {closest['slant_distance_m']/1000:.0f} km")
        print(f"    Elevation: {closest['elevation_angle_deg']:.1f}°")
    
    print("=" * 60)
