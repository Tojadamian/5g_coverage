"""
Unit tests for geographic study area module

Tests grid generation, coordinate conversions, and geometric calculations.
"""

import pytest
import numpy as np
from study_area import (
    StudyArea,
    GroundReceiverGrid,
    haversine_distance,
    calculate_slant_distance,
    calculate_elevation_angle,
    calculate_azimuth_angle,
)


class TestStudyAreaDefinition:
    """Test study area initialization and validation."""
    
    def test_study_area_valid_initialization(self):
        """Test valid study area creation."""
        area = StudyArea(
            center_lat=50.0,
            center_lon=15.0,
            width_km=50,
            height_km=50,
            resolution_m=1000,
        )
        assert area.center_lat == 50.0
        assert area.width_km == 50
    
    def test_study_area_invalid_latitude(self):
        """Test that invalid latitude raises error."""
        with pytest.raises(ValueError):
            StudyArea(center_lat=91.0, center_lon=0, width_km=50, height_km=50)
        with pytest.raises(ValueError):
            StudyArea(center_lat=-91.0, center_lon=0, width_km=50, height_km=50)
    
    def test_study_area_invalid_longitude(self):
        """Test that invalid longitude raises error."""
        with pytest.raises(ValueError):
            StudyArea(center_lat=0, center_lon=181.0, width_km=50, height_km=50)
        with pytest.raises(ValueError):
            StudyArea(center_lat=0, center_lon=-181.0, width_km=50, height_km=50)
    
    def test_study_area_invalid_dimensions(self):
        """Test that invalid dimensions raise error."""
        with pytest.raises(ValueError):
            StudyArea(center_lat=0, center_lon=0, width_km=0, height_km=50)
        with pytest.raises(ValueError):
            StudyArea(center_lat=0, center_lon=0, width_km=50, height_km=-50)
    
    def test_study_area_bounds(self):
        """Test that bounds calculation is reasonable."""
        area = StudyArea(center_lat=50.0, center_lon=15.0, width_km=50, height_km=50)
        bounds = area.bounds_deg
        
        # Check that bounds are symmetric around center
        assert bounds['min_lat'] < 50.0 < bounds['max_lat']
        assert bounds['min_lon'] < 15.0 < bounds['max_lon']
        
        # Approximate: 50 km / 111 km per degree ≈ 0.45°
        assert abs((bounds['max_lat'] - bounds['min_lat']) - 0.45) < 0.1


class TestGridGeneration:
    """Test receiver grid generation."""
    
    def test_grid_generation_count(self):
        """Test that grid generates expected number of points."""
        area = StudyArea(
            center_lat=50.0,
            center_lon=15.0,
            width_km=50,
            height_km=50,
            resolution_m=5000,  # 5 km spacing
        )
        grid = GroundReceiverGrid(area)
        
        # 50 km / 5 km = 10 x 10 = ~100 points (approximately)
        num_receivers = grid.get_num_receivers()
        assert 80 < num_receivers < 120, f"Got {num_receivers} receivers, expected ~100"
    
    def test_grid_generation_within_bounds(self):
        """Test that all grid points are within bounds."""
        area = StudyArea(
            center_lat=50.0,
            center_lon=15.0,
            width_km=50,
            height_km=50,
            resolution_m=5000,
        )
        grid = GroundReceiverGrid(area)
        bounds = area.bounds_deg
        
        for lat, lon in grid.receiver_locations:
            assert bounds['min_lat'] <= lat <= bounds['max_lat']
            assert bounds['min_lon'] <= lon <= bounds['max_lon']
    
    def test_grid_higher_resolution_more_points(self):
        """Test that finer resolution generates more points."""
        area1 = StudyArea(
            center_lat=50.0, center_lon=15.0,
            width_km=50, height_km=50,
            resolution_m=5000,
        )
        area2 = StudyArea(
            center_lat=50.0, center_lon=15.0,
            width_km=50, height_km=50,
            resolution_m=2500,  # Half resolution
        )
        grid1 = GroundReceiverGrid(area1)
        grid2 = GroundReceiverGrid(area2)
        
        # Halving resolution should increase point count by ~4x
        ratio = grid2.get_num_receivers() / grid1.get_num_receivers()
        assert 3.5 < ratio < 4.5, f"Resolution scaling ratio {ratio} unexpected"


class TestDistanceCalculations:
    """Test geographic distance calculations."""
    
    def test_haversine_same_point_zero_distance(self):
        """Test that distance to same point is zero."""
        dist = haversine_distance(50.0, 15.0, 50.0, 15.0)
        assert dist < 1, "Distance to same point should be near zero"
    
    def test_haversine_known_distance_prague_to_london(self):
        """Test against known distance (Prague to London ~1000 km)."""
        # Prague: 50.08°N, 14.44°E
        # London: 51.51°N, -0.13°W
        dist_m = haversine_distance(50.08, 14.44, 51.51, -0.13)
        dist_km = dist_m / 1000
        
        # Expect approximately 1000 km ±50 km
        assert 950 < dist_km < 1050, f"Prague-London distance {dist_km} km out of range"
    
    def test_haversine_symmetry(self):
        """Test that distance is symmetric (A to B = B to A)."""
        dist1 = haversine_distance(50.0, 15.0, 51.0, 16.0)
        dist2 = haversine_distance(51.0, 16.0, 50.0, 15.0)
        assert abs(dist1 - dist2) < 1, "Distance should be symmetric"
    
    def test_slant_distance_greater_than_horizontal(self):
        """Test that slant distance exceeds horizontal distance."""
        # Horizontal distance (satellite directly overhead)
        slant = calculate_slant_distance(50.0, 15.0, 50.0, 15.0, 540e3)
        horizontal = 0  # Direct overhead
        
        # Slant should be approximately the altitude (540 km)
        assert abs(slant - 540e3) < 1e3, "Slant distance should equal altitude when overhead"
    
    def test_slant_distance_geometry_correctness(self):
        """Test slant distance Pythagorean relationship."""
        # Point 100 km away horizontally, satellite at 540 km altitude
        slant = calculate_slant_distance(50.0, 15.0, 50.0, 14.1, 540e3)  # ~100 km away
        horizontal = haversine_distance(50.0, 15.0, 50.0, 14.1)
        
        # Verify: slant^2 = horizontal^2 + altitude^2
        expected_slant = np.sqrt(horizontal**2 + (540e3)**2)
        assert abs(slant - expected_slant) < 1e3, "Slant distance geometry incorrect"


class TestElevationAngleCalculation:
    """Test elevation angle calculations."""
    
    def test_elevation_angle_directly_overhead(self):
        """Test that directly overhead gives 90° elevation."""
        elev = calculate_elevation_angle(50.0, 15.0, 50.0, 15.0, 540e3)
        assert abs(elev - 90.0) < 0.1, "Directly overhead should be ~90°"
    
    def test_elevation_angle_horizon(self):
        """Test that horizon grazing gives low elevation."""
        # Point very far away (Earth curvature matters, but for rough test):
        # ~10000 km away at 540 km altitude should give very low angle
        elev = calculate_elevation_angle(50.0, 15.0, 50.0, 115.0, 540e3)  # ~9000 km away
        assert elev < 10, f"Far away should have low elevation, got {elev}°"
    
    def test_elevation_angle_bounds(self):
        """Test that elevation angle is always 0-90°."""
        test_cases = [
            (50.0, 15.0, 50.0, 15.0, 540e3),  # Overhead
            (50.0, 15.0, 51.0, 16.0, 540e3),  # Nearby
            (50.0, 15.0, 0.0, 0.0, 540e3),     # Far
        ]
        for lat1, lon1, lat2, lon2, alt_m in test_cases:
            elev = calculate_elevation_angle(lat1, lon1, lat2, lon2, alt_m)
            assert 0 <= elev <= 90, f"Elevation {elev}° out of valid range"
    
    def test_elevation_angle_increases_closer(self):
        """Test that elevation angle increases when closer."""
        # Same longitude, varying latitude separation
        elev_close = calculate_elevation_angle(50.0, 15.0, 50.2, 15.0, 540e3)
        elev_far = calculate_elevation_angle(50.0, 15.0, 51.0, 15.0, 540e3)
        assert elev_close > elev_far, "Closer should have higher elevation"


class TestAzimuthAngleCalculation:
    """Test azimuth angle calculations."""
    
    def test_azimuth_due_north(self):
        """Test azimuth to point due north."""
        # Point directly north (same longitude)
        azim = calculate_azimuth_angle(50.0, 15.0, 51.0, 15.0)
        assert abs(azim - 0) < 5 or abs(azim - 360) < 5, "Due north should be 0° or 360°"
    
    def test_azimuth_due_east(self):
        """Test azimuth to point due east."""
        # Point directly east (same latitude, higher longitude)
        azim = calculate_azimuth_angle(50.0, 15.0, 50.0, 16.0)
        assert abs(azim - 90) < 5, "Due east should be ~90°"
    
    def test_azimuth_due_south(self):
        """Test azimuth to point due south."""
        azim = calculate_azimuth_angle(50.0, 15.0, 49.0, 15.0)
        assert abs(azim - 180) < 5, "Due south should be ~180°"
    
    def test_azimuth_due_west(self):
        """Test azimuth to point due west."""
        azim = calculate_azimuth_angle(50.0, 15.0, 50.0, 14.0)
        assert abs(azim - 270) < 5, "Due west should be ~270°"
    
    def test_azimuth_range(self):
        """Test that azimuth is always 0-360°."""
        for lat_offset in np.linspace(-1, 1, 5):
            for lon_offset in np.linspace(-1, 1, 5):
                azim = calculate_azimuth_angle(50.0, 15.0, 50.0 + lat_offset, 15.0 + lon_offset)
                assert 0 <= azim <= 360, f"Azimuth {azim}° out of range"


class TestGroundReceiverGridGeometry:
    """Test receiver geometry calculations."""
    
    def test_receiver_geometry_all_receivers(self):
        """Test that geometry is calculated for all receivers."""
        area = StudyArea(
            center_lat=50.0, center_lon=15.0,
            width_km=50, height_km=50,
            resolution_m=5000,
        )
        grid = GroundReceiverGrid(area)
        geometry = grid.get_receiver_geometry(50.0, 15.0, 540e3)
        
        assert len(geometry) == grid.get_num_receivers()
    
    def test_receiver_geometry_fields(self):
        """Test that geometry has all required fields."""
        area = StudyArea(center_lat=50.0, center_lon=15.0, width_km=50, height_km=50)
        grid = GroundReceiverGrid(area)
        geometry = grid.get_receiver_geometry(50.0, 15.0, 540e3)
        
        required_fields = ['index', 'lat', 'lon', 'slant_distance_m', 'elevation_angle_deg', 'azimuth_angle_deg', 'visible']
        
        for geom in geometry:
            for field in required_fields:
                assert field in geom, f"Missing field: {field}"
    
    def test_receiver_geometry_visibility_threshold(self):
        """Test that visibility correctly applies elevation threshold."""
        area = StudyArea(
            center_lat=50.0, center_lon=15.0,
            width_km=50, height_km=50,
            min_elevation_deg=10.0,
        )
        grid = GroundReceiverGrid(area)
        geometry = grid.get_receiver_geometry(50.0, 15.0, 540e3)
        
        for geom in geometry:
            if geom['elevation_angle_deg'] >= 10.0:
                assert geom['visible'], "Should be visible"
            else:
                assert not geom['visible'], "Should not be visible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
