"""
Unit tests for HTZ RF planning software client module.

Tests satellite site payload creation, serialization, HTTP integration,
and error handling for ATDI HTZ RF calculation engine connectivity.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests

from htz_client import SatelliteSitePayload, HTZPayloadEngine


class TestSatelliteSitePayload:
    """Test SatelliteSitePayload dataclass creation and serialization."""

    def test_payload_with_all_fields(self):
        """Test creating payload with all fields specified."""
        payload = SatelliteSitePayload(
            site_name="INSAT-4B",
            longitude=55.5,
            latitude=0.0,
            altitude_msl_m=36000.0,
            antenna_model="3GPP_TR_38.811_PhasedArray",
            frequency_mhz=28000.0,
            tx_power_dbm=50.0,
        )
        assert payload.site_name == "INSAT-4B"
        assert payload.longitude == 55.5
        assert payload.latitude == 0.0
        assert payload.altitude_msl_m == 36000.0
        assert payload.antenna_model == "3GPP_TR_38.811_PhasedArray"
        assert payload.frequency_mhz == 28000.0
        assert payload.tx_power_dbm == 50.0

    def test_payload_with_default_fields(self):
        """Test creating payload with default field values."""
        payload = SatelliteSitePayload(
            site_name="LEO-Satellite",
            longitude=-75.0,
            latitude=45.0,
            altitude_msl_m=500000.0,
        )
        assert payload.site_name == "LEO-Satellite"
        assert payload.longitude == -75.0
        assert payload.latitude == 45.0
        assert payload.altitude_msl_m == 500000.0
        # Verify defaults
        assert payload.antenna_model == "3GPP_TR_38.811_PhasedArray"
        assert payload.frequency_mhz == 2100.0
        assert payload.tx_power_dbm == 43.0

    def test_payload_to_dict_all_seven_fields_present(self):
        """Test that to_dict() includes all 7 required fields."""
        payload = SatelliteSitePayload(
            site_name="Test-Satellite",
            longitude=10.0,
            latitude=20.0,
            altitude_msl_m=35786000.0,
            antenna_model="Custom_Antenna",
            frequency_mhz=12000.0,
            tx_power_dbm=45.0,
        )
        payload_dict = payload.to_dict()
        
        # Verify all 7 fields are present
        expected_fields = {
            "site_name",
            "longitude",
            "latitude",
            "altitude_msl_m",
            "antenna_model",
            "frequency_mhz",
            "tx_power_dbm",
        }
        assert set(payload_dict.keys()) == expected_fields
        assert len(payload_dict) == 7

    def test_payload_to_dict_values_correct(self):
        """Test that to_dict() returns correct values."""
        payload = SatelliteSitePayload(
            site_name="GEO-Satellite",
            longitude=0.0,
            latitude=5.0,
            altitude_msl_m=35786000.0,
            antenna_model="Test_Model",
            frequency_mhz=11000.0,
            tx_power_dbm=42.0,
        )
        payload_dict = payload.to_dict()
        
        assert payload_dict["site_name"] == "GEO-Satellite"
        assert payload_dict["longitude"] == 0.0
        assert payload_dict["latitude"] == 5.0
        assert payload_dict["altitude_msl_m"] == 35786000.0
        assert payload_dict["antenna_model"] == "Test_Model"
        assert payload_dict["frequency_mhz"] == 11000.0
        assert payload_dict["tx_power_dbm"] == 42.0

    def test_payload_to_dict_serializable_to_json(self):
        """Test that to_dict() output is JSON serializable."""
        payload = SatelliteSitePayload(
            site_name="JSON-Test",
            longitude=45.5,
            latitude=-20.5,
            altitude_msl_m=400000.0,
        )
        payload_dict = payload.to_dict()
        
        # Should not raise an exception
        json_str = json.dumps(payload_dict)
        assert json_str is not None
        
        # Verify round-trip
        deserialized = json.loads(json_str)
        assert deserialized["site_name"] == "JSON-Test"

    def test_payload_frozen_immutability(self):
        """Test that dataclass is frozen (immutable)."""
        payload = SatelliteSitePayload(
            site_name="Immutable-Test",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        # Attempting to modify should raise an error
        with pytest.raises(Exception):  # FrozenInstanceError
            payload.site_name = "Modified"

    def test_payload_coordinate_boundaries(self):
        """Test payload creation with extreme valid coordinates."""
        # North pole
        payload_north = SatelliteSitePayload(
            site_name="NorthPole",
            longitude=0.0,
            latitude=90.0,
            altitude_msl_m=35786000.0,
        )
        assert payload_north.latitude == 90.0
        
        # South pole
        payload_south = SatelliteSitePayload(
            site_name="SouthPole",
            longitude=0.0,
            latitude=-90.0,
            altitude_msl_m=35786000.0,
        )
        assert payload_south.latitude == -90.0
        
        # Date line
        payload_dateline = SatelliteSitePayload(
            site_name="DateLine",
            longitude=180.0,
            latitude=0.0,
            altitude_msl_m=35786000.0,
        )
        assert payload_dateline.longitude == 180.0

    def test_payload_zero_altitude(self):
        """Test payload with zero altitude (sea level)."""
        payload = SatelliteSitePayload(
            site_name="SeaLevel",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=0.0,
        )
        assert payload.altitude_msl_m == 0.0

    def test_payload_negative_altitude(self):
        """Test payload with negative altitude (below sea level)."""
        payload = SatelliteSitePayload(
            site_name="BelowSeaLevel",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=-100.0,
        )
        assert payload.altitude_msl_m == -100.0


class TestHTZPayloadEngineInitialization:
    """Test HTZPayloadEngine initialization and configuration."""

    def test_default_initialization(self):
        """Test initialization with default parameters."""
        engine = HTZPayloadEngine()
        assert engine.base_url == "http://localhost:8080/api/v1"
        assert engine.headers["Content-Type"] == "application/json"
        assert engine.headers["Accept"] == "application/json"

    def test_custom_base_url_initialization(self):
        """Test initialization with custom base URL."""
        custom_url = "https://htz.example.com/api/v2"
        engine = HTZPayloadEngine(base_url=custom_url)
        assert engine.base_url == custom_url

    def test_headers_configuration(self):
        """Test that headers are correctly configured."""
        engine = HTZPayloadEngine()
        assert "Content-Type" in engine.headers
        assert "Accept" in engine.headers
        assert engine.headers["Content-Type"] == "application/json"
        assert engine.headers["Accept"] == "application/json"
        assert len(engine.headers) == 2


class TestBuildSatellitePayload:
    """Test build_satellite_payload method."""

    def test_build_payload_basic(self):
        """Test basic payload building."""
        engine = HTZPayloadEngine()
        payload = engine.build_satellite_payload(
            site_name="TestSat",
            longitude=0.0,
            latitude=0.0,
            altitude_km=36.0,
        )
        
        assert isinstance(payload, SatelliteSitePayload)
        assert payload.site_name == "TestSat"
        assert payload.longitude == 0.0
        assert payload.latitude == 0.0

    def test_build_payload_altitude_conversion_km_to_m(self):
        """Test that altitude is correctly converted from km to m."""
        engine = HTZPayloadEngine()
        payload = engine.build_satellite_payload(
            site_name="Altitude-Test",
            longitude=0.0,
            latitude=0.0,
            altitude_km=36.0,
        )
        
        # 36 km should be converted to 36000 m
        assert payload.altitude_msl_m == 36000.0

    def test_build_payload_altitude_conversion_leo(self):
        """Test altitude conversion for LEO satellite (500 km)."""
        engine = HTZPayloadEngine()
        payload = engine.build_satellite_payload(
            site_name="LEO-Sat",
            longitude=0.0,
            latitude=0.0,
            altitude_km=500.0,
        )
        
        assert payload.altitude_msl_m == 500000.0

    def test_build_payload_altitude_conversion_geo(self):
        """Test altitude conversion for GEO satellite (35786 km)."""
        engine = HTZPayloadEngine()
        payload = engine.build_satellite_payload(
            site_name="GEO-Sat",
            longitude=0.0,
            latitude=0.0,
            altitude_km=35786.0,
        )
        
        assert payload.altitude_msl_m == 35786000.0

    def test_build_payload_inherits_defaults(self):
        """Test that built payload inherits default antenna/frequency/power."""
        engine = HTZPayloadEngine()
        payload = engine.build_satellite_payload(
            site_name="Default-Test",
            longitude=50.0,
            latitude=25.0,
            altitude_km=10.0,
        )
        
        # Check defaults are applied
        assert payload.antenna_model == "3GPP_TR_38.811_PhasedArray"
        assert payload.frequency_mhz == 2100.0
        assert payload.tx_power_dbm == 43.0

    def test_build_payload_with_negative_altitude(self):
        """Test building payload with negative altitude."""
        engine = HTZPayloadEngine()
        payload = engine.build_satellite_payload(
            site_name="Underground",
            longitude=0.0,
            latitude=0.0,
            altitude_km=-0.1,  # 100 meters below sea level
        )
        
        assert payload.altitude_msl_m == -100.0


class TestPushSatellitePositionSuccess:
    """Test push_satellite_position with successful responses."""

    @patch("htz_client.requests.post")
    def test_push_position_success_200(self, mock_post):
        """Test successful push with 200 status code."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="Test-Sat",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is True
        mock_post.assert_called_once()

    @patch("htz_client.requests.post")
    def test_push_position_success_201(self, mock_post):
        """Test successful push with 201 status code."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="Created-Sat",
            longitude=10.0,
            latitude=20.0,
            altitude_msl_m=35786000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is True

    @patch("htz_client.requests.post")
    def test_push_position_endpoint_url(self, mock_post):
        """Test that correct endpoint URL is called."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine(base_url="http://test.local:9090/api/v1")
        payload = SatelliteSitePayload(
            site_name="URL-Test",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        engine.push_satellite_position(payload)
        
        # Verify the correct endpoint was called
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://test.local:9090/api/v1/vectorsite"

    @patch("htz_client.requests.post")
    def test_push_position_payload_serialization(self, mock_post):
        """Test that payload is correctly serialized to JSON."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="Serial-Test",
            longitude=15.5,
            latitude=45.5,
            altitude_msl_m=35786000.0,
            antenna_model="Custom_Antenna",
            frequency_mhz=11000.0,
            tx_power_dbm=48.0,
        )
        
        engine.push_satellite_position(payload)
        
        # Verify payload was serialized correctly
        call_args = mock_post.call_args
        sent_data = call_args[1]["data"]
        sent_dict = json.loads(sent_data)
        
        assert sent_dict["site_name"] == "Serial-Test"
        assert sent_dict["longitude"] == 15.5
        assert sent_dict["latitude"] == 45.5
        assert sent_dict["altitude_msl_m"] == 35786000.0
        assert sent_dict["antenna_model"] == "Custom_Antenna"
        assert sent_dict["frequency_mhz"] == 11000.0
        assert sent_dict["tx_power_dbm"] == 48.0

    @patch("htz_client.requests.post")
    def test_push_position_headers(self, mock_post):
        """Test that correct headers are sent."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="Header-Test",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        engine.push_satellite_position(payload)
        
        # Verify headers
        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        assert headers["Content-Type"] == "application/json"
        assert headers["Accept"] == "application/json"

    @patch("htz_client.requests.post")
    def test_push_position_timeout(self, mock_post):
        """Test that timeout is set."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="Timeout-Test",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        engine.push_satellite_position(payload)
        
        # Verify timeout is 10 seconds
        call_args = mock_post.call_args
        assert call_args[1]["timeout"] == 10


class TestPushSatellitePositionFailure:
    """Test push_satellite_position with failure responses."""

    @patch("htz_client.requests.post")
    def test_push_position_failure_400(self, mock_post):
        """Test failed push with 400 bad request."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="BadRequest",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False

    @patch("htz_client.requests.post")
    def test_push_position_failure_401(self, mock_post):
        """Test failed push with 401 unauthorized."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="Unauthorized",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False

    @patch("htz_client.requests.post")
    def test_push_position_failure_404(self, mock_post):
        """Test failed push with 404 not found."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="NotFound",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False

    @patch("htz_client.requests.post")
    def test_push_position_failure_500(self, mock_post):
        """Test failed push with 500 internal server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="ServerError",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False

    @patch("htz_client.requests.post")
    def test_push_position_failure_503(self, mock_post):
        """Test failed push with 503 service unavailable."""
        mock_response = Mock()
        mock_response.status_code = 503
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="ServiceUnavailable",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False


class TestPushSatellitePositionExceptions:
    """Test push_satellite_position with connection errors."""

    @patch("htz_client.requests.post")
    def test_push_position_connection_timeout(self, mock_post):
        """Test connection timeout exception."""
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="Timeout",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False

    @patch("htz_client.requests.post")
    def test_push_position_connection_error(self, mock_post):
        """Test connection error exception."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Unable to connect")
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="ConnectionError",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False

    @patch("htz_client.requests.post")
    def test_push_position_request_exception(self, mock_post):
        """Test generic request exception."""
        mock_post.side_effect = requests.exceptions.RequestException("Generic error")
        
        engine = HTZPayloadEngine()
        payload = SatelliteSitePayload(
            site_name="RequestError",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        
        result = engine.push_satellite_position(payload)
        
        assert result is False

    @patch("htz_client.requests.post")
    def test_push_position_dict_fallback(self, mock_post):
        """Test that dict payload is handled if to_dict() is missing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        dict_payload = {
            "site_name": "Dict-Test",
            "longitude": 0.0,
            "latitude": 0.0,
            "altitude_msl_m": 36000.0,
        }
        
        result = engine.push_satellite_position(dict_payload)
        
        assert result is True
        mock_post.assert_called_once()


class TestTriggerCoverageCalculation:
    """Test trigger_coverage_calculation method."""

    @patch("htz_client.requests.post")
    def test_coverage_calculation_success(self, mock_post):
        """Test successful coverage calculation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "complete",
            "coverage_area_km2": 15000.0,
        }
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        result = engine.trigger_coverage_calculation("TestSat")
        
        assert result is not None
        assert result["status"] == "complete"
        assert result["coverage_area_km2"] == 15000.0

    @patch("htz_client.requests.post")
    def test_coverage_calculation_endpoint_url(self, mock_post):
        """Test that correct coverage calculation endpoint is called."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine(base_url="http://htz.local/api/v1")
        engine.trigger_coverage_calculation("TestSat")
        
        call_args = mock_post.call_args
        assert call_args[0][0] == "http://htz.local/api/v1/coverage/calculate"

    @patch("htz_client.requests.post")
    def test_coverage_calculation_payload(self, mock_post):
        """Test that coverage calculation payload is correct."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        engine.trigger_coverage_calculation(
            "TestSat",
            clear_matrix=True,
        )
        
        call_args = mock_post.call_args
        sent_data = json.loads(call_args[1]["data"])
        
        assert sent_data["target_site"] == "TestSat"
        assert sent_data["propagation_model"] == "ITU-R_P.618-13"
        assert sent_data["clear_previous"] is True
        assert sent_data["resolution_meter"] == 30

    @patch("htz_client.requests.post")
    def test_coverage_calculation_clear_matrix_false(self, mock_post):
        """Test coverage calculation with clear_matrix=False."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        engine.trigger_coverage_calculation(
            "TestSat",
            clear_matrix=False,
        )
        
        call_args = mock_post.call_args
        sent_data = json.loads(call_args[1]["data"])
        
        assert sent_data["clear_previous"] is False

    @patch("htz_client.requests.post")
    def test_coverage_calculation_timeout(self, mock_post):
        """Test that coverage calculation uses correct timeout."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        engine.trigger_coverage_calculation("TestSat")
        
        call_args = mock_post.call_args
        assert call_args[1]["timeout"] == 30

    @patch("htz_client.requests.post")
    def test_coverage_calculation_failure_non_200(self, mock_post):
        """Test coverage calculation with non-200 status code."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        result = engine.trigger_coverage_calculation("TestSat")
        
        assert result is None

    @patch("htz_client.requests.post")
    def test_coverage_calculation_exception_returns_none(self, mock_post):
        """Test coverage calculation with exception returns None."""
        mock_post.side_effect = requests.exceptions.RequestException("Error")
        
        engine = HTZPayloadEngine()
        result = engine.trigger_coverage_calculation("TestSat")
        
        assert result is None

    @patch("htz_client.requests.post")
    def test_coverage_calculation_timeout_exception(self, mock_post):
        """Test coverage calculation with timeout exception."""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")
        
        engine = HTZPayloadEngine()
        result = engine.trigger_coverage_calculation("TestSat")
        
        assert result is None


class TestPayloadValidation:
    """Test payload validation for coordinate bounds and parameter ranges."""

    def test_coordinate_longitude_range(self):
        """Test that longitude accepts valid range [-180, 180]."""
        # Valid longitudes
        payload1 = SatelliteSitePayload(
            site_name="ValidLon1",
            longitude=-180.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        assert payload1.longitude == -180.0
        
        payload2 = SatelliteSitePayload(
            site_name="ValidLon2",
            longitude=180.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
        )
        assert payload2.longitude == 180.0

    def test_coordinate_latitude_range(self):
        """Test that latitude accepts valid range [-90, 90]."""
        payload1 = SatelliteSitePayload(
            site_name="ValidLat1",
            longitude=0.0,
            latitude=-90.0,
            altitude_msl_m=36000.0,
        )
        assert payload1.latitude == -90.0
        
        payload2 = SatelliteSitePayload(
            site_name="ValidLat2",
            longitude=0.0,
            latitude=90.0,
            altitude_msl_m=36000.0,
        )
        assert payload2.latitude == 90.0

    def test_altitude_positive_for_satellite(self):
        """Test typical positive satellite altitude."""
        payload = SatelliteSitePayload(
            site_name="GEOSat",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=35786000.0,
        )
        assert payload.altitude_msl_m > 0

    def test_power_reasonable_range(self):
        """Test TX power in reasonable range for satellites."""
        # Low power
        payload1 = SatelliteSitePayload(
            site_name="LowPower",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
            tx_power_dbm=10.0,
        )
        assert 0 < payload1.tx_power_dbm < 60

        # High power
        payload2 = SatelliteSitePayload(
            site_name="HighPower",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
            tx_power_dbm=55.0,
        )
        assert 0 < payload2.tx_power_dbm < 60

    def test_frequency_reasonable_range(self):
        """Test frequency in reasonable range for satellite communications."""
        # C-band (4/6 GHz)
        payload1 = SatelliteSitePayload(
            site_name="CBand",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
            frequency_mhz=6000.0,
        )
        assert payload1.frequency_mhz > 1000

        # Ka-band (30 GHz)
        payload2 = SatelliteSitePayload(
            site_name="KaBand",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
            frequency_mhz=30000.0,
        )
        assert payload2.frequency_mhz > 1000

    def test_multiple_sites_payload_independence(self):
        """Test that multiple payloads don't interfere with each other."""
        payload1 = SatelliteSitePayload(
            site_name="Sat1",
            longitude=0.0,
            latitude=0.0,
            altitude_msl_m=36000.0,
            frequency_mhz=12000.0,
        )
        
        payload2 = SatelliteSitePayload(
            site_name="Sat2",
            longitude=90.0,
            latitude=45.0,
            altitude_msl_m=500000.0,
            frequency_mhz=28000.0,
        )
        
        # Verify they remain independent
        assert payload1.site_name == "Sat1"
        assert payload2.site_name == "Sat2"
        assert payload1.frequency_mhz != payload2.frequency_mhz


class TestIntegrationScenarios:
    """Test complete workflows combining multiple components."""

    @patch("htz_client.requests.post")
    def test_full_workflow_geo_satellite(self, mock_post):
        """Test complete workflow for GEO satellite position update."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Create engine
        engine = HTZPayloadEngine()
        
        # Build payload
        payload = engine.build_satellite_payload(
            site_name="INSAT-4A",
            longitude=55.5,
            latitude=0.0,
            altitude_km=35786.0,
        )
        
        # Verify payload contents
        assert payload.site_name == "INSAT-4A"
        assert payload.altitude_msl_m == 35786000.0
        
        # Push to server
        result = engine.push_satellite_position(payload)
        
        assert result is True

    @patch("htz_client.requests.post")
    def test_full_workflow_leo_satellite_with_coverage(self, mock_post):
        """Test complete workflow for LEO satellite with coverage calc."""
        # Mock responses
        position_response = Mock()
        position_response.status_code = 200
        
        coverage_response = Mock()
        coverage_response.status_code = 200
        coverage_response.json.return_value = {
            "status": "complete",
            "coverage_area_km2": 5000.0,
        }
        
        mock_post.side_effect = [position_response, coverage_response]
        
        # Create engine
        engine = HTZPayloadEngine()
        
        # Build LEO satellite
        payload = engine.build_satellite_payload(
            site_name="Starlink-001",
            longitude=-100.0,
            latitude=40.0,
            altitude_km=550.0,
        )
        
        # Push position
        push_result = engine.push_satellite_position(payload)
        assert push_result is True
        
        # Trigger coverage calculation
        coverage_result = engine.trigger_coverage_calculation("Starlink-001")
        assert coverage_result is not None

    @patch("htz_client.requests.post")
    def test_multiple_satellites_update(self, mock_post):
        """Test updating positions for multiple satellites."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        engine = HTZPayloadEngine()
        
        satellites = [
            ("Sat-1", 0.0, 0.0, 35786.0),
            ("Sat-2", 90.0, 0.0, 35786.0),
            ("Sat-3", 180.0, 0.0, 35786.0),
        ]
        
        for site_name, lon, lat, alt_km in satellites:
            payload = engine.build_satellite_payload(
                site_name=site_name,
                longitude=lon,
                latitude=lat,
                altitude_km=alt_km,
            )
            result = engine.push_satellite_position(payload)
            assert result is True
        
        # Verify all three were called
        assert mock_post.call_count == 3
