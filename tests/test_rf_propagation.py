"""
Unit tests for RF propagation module

Tests path loss calculations, antenna gain models, and link budget
calculations against known ITU-R reference values and physical constants.
"""

import pytest
import numpy as np
from rf_propagation import (
    calculate_free_space_path_loss,
    calculate_oxygen_absorption,
    calculate_rain_fade,
    calculate_antenna_gain_3gpp,
    calculate_receiver_antenna_gain,
    calculate_received_power,
    calculate_signal_to_noise_ratio,
    dbm_to_watts,
    watts_to_dbm,
    SPEED_OF_LIGHT,
    FREQ_S_BAND_HZ,
    WAVELENGTH_S_BAND,
)


class TestPathLossCalculations:
    """Test Friis transmission equation and path loss calculations."""
    
    def test_freespace_path_loss_valid_inputs(self):
        """Test path loss calculation with valid inputs."""
        # At 1 km distance, 2100 MHz, expect ~98-99 dB
        loss = calculate_free_space_path_loss(1000, FREQ_S_BAND_HZ)
        assert 98 <= loss <= 100, f"Path loss {loss} dB not in expected range"
    
    def test_freespace_path_loss_doubling_distance(self):
        """Test that doubling distance increases loss by ~6 dB."""
        loss1 = calculate_free_space_path_loss(1000, FREQ_S_BAND_HZ)
        loss2 = calculate_free_space_path_loss(2000, FREQ_S_BAND_HZ)
        # Friis: loss increases 20*log10(2) ≈ 6.02 dB per doubling
        assert 5.9 < (loss2 - loss1) < 6.1, "Path loss scaling incorrect"
    
    def test_freespace_path_loss_doubling_frequency(self):
        """Test that doubling frequency increases loss by ~6 dB."""
        loss1 = calculate_free_space_path_loss(1000, FREQ_S_BAND_HZ)
        loss2 = calculate_free_space_path_loss(1000, FREQ_S_BAND_HZ * 2)
        # Friis: loss increases 20*log10(2) ≈ 6.02 dB
        assert 5.9 < (loss2 - loss1) < 6.1, "Frequency scaling incorrect"
    
    def test_freespace_path_loss_invalid_distance(self):
        """Test that invalid distance raises error."""
        with pytest.raises(ValueError):
            calculate_free_space_path_loss(-1000, FREQ_S_BAND_HZ)
        with pytest.raises(ValueError):
            calculate_free_space_path_loss(0, FREQ_S_BAND_HZ)
    
    def test_freespace_path_loss_invalid_frequency(self):
        """Test that invalid frequency raises error."""
        with pytest.raises(ValueError):
            calculate_free_space_path_loss(1000, -FREQ_S_BAND_HZ)
        with pytest.raises(ValueError):
            calculate_free_space_path_loss(1000, 0)


class TestAtmosphericModels:
    """Test atmospheric absorption and rain fade models."""
    
    def test_oxygen_absorption_positive(self):
        """Test that oxygen absorption returns positive attenuation."""
        atten = calculate_oxygen_absorption(100, FREQ_S_BAND_HZ)
        assert atten > 0, "Oxygen absorption should be positive"
    
    def test_oxygen_absorption_zero_distance(self):
        """Test that zero distance has zero absorption."""
        atten = calculate_oxygen_absorption(0, FREQ_S_BAND_HZ)
        assert atten == 0, "Zero distance should have zero absorption"
    
    def test_rain_fade_negative_elevation(self):
        """Test that negative elevation raises error."""
        with pytest.raises(ValueError):
            calculate_rain_fade(-10.0)
    
    def test_rain_fade_above_90_degrees(self):
        """Test that elevation > 90 raises error."""
        with pytest.raises(ValueError):
            calculate_rain_fade(91.0)
    
    def test_rain_fade_low_elevation_higher_loss(self):
        """Test that lower elevation angles have higher rain fade."""
        rain5 = calculate_rain_fade(5.0, rain_rate_mmhr=5.0)
        rain45 = calculate_rain_fade(45.0, rain_rate_mmhr=5.0)
        assert rain5 > rain45, "Low elevation should have more rain loss"
    
    def test_rain_fade_more_rain_higher_loss(self):
        """Test that higher rain rates increase fade."""
        rain1 = calculate_rain_fade(30.0, rain_rate_mmhr=1.0)
        rain5 = calculate_rain_fade(30.0, rain_rate_mmhr=5.0)
        assert rain5 > rain1, "Higher rain rate should increase loss"


class TestAntennaGainModels:
    """Test 3GPP antenna gain patterns."""
    
    def test_antenna_gain_3gpp_peak_at_zenith(self):
        """Test that TX antenna gain peaks at zenith (90°)."""
        gains = [calculate_antenna_gain_3gpp(el) for el in [0, 30, 60, 90]]
        assert gains[-1] == max(gains), "Peak gain should be at zenith"
    
    def test_antenna_gain_3gpp_symmetric_rolloff(self):
        """Test that gain pattern has reasonable rolloff."""
        gain_30 = calculate_antenna_gain_3gpp(60.0)  # 30° off-axis
        gain_60 = calculate_antenna_gain_3gpp(30.0)  # 60° off-axis
        assert gain_30 > gain_60, "Off-axis gain should decrease with angle"
    
    def test_antenna_gain_3gpp_negative_valid(self):
        """Test that gains can be negative (sidelobe region)."""
        gain_0 = calculate_antenna_gain_3gpp(0.0)
        assert gain_0 < 0, "Horizon-grazing should have negative gain"
    
    def test_receiver_antenna_gain_omnidirectional(self):
        """Test that receiver antenna is roughly omnidirectional."""
        gains = [calculate_receiver_antenna_gain(el) for el in [10, 30, 60, 90]]
        # Should vary minimally (omnidirectional)
        assert np.std(gains) < 3, "RX antenna should be relatively omnidirectional"
    
    def test_antenna_gain_invalid_elevation(self):
        """Test that invalid elevation raises error."""
        with pytest.raises(ValueError):
            calculate_antenna_gain_3gpp(-1.0)
        with pytest.raises(ValueError):
            calculate_antenna_gain_3gpp(91.0)


class TestReceivedPowerCalculation:
    """Test complete link budget received power calculation."""
    
    def test_received_power_basic_calculation(self):
        """Test that received power calculation produces reasonable values."""
        # Typical 5G-NTN scenario: 540 km altitude, ~30° elevation
        # Expect RX power in range -100 to -130 dBm
        rx_power = calculate_received_power(
            tx_power_dbm=43.0,
            tx_antenna_gain_dbi=-6.0,  # Off-zenith
            rx_antenna_gain_dbi=0.0,
            distance_m=650e3,  # ~650 km slant distance
            elevation_angle_deg=30.0,
            frequency_hz=FREQ_S_BAND_HZ,
            rain_rate_mmhr=0.0,
        )
        assert -130 < rx_power < -100, f"RX power {rx_power} dBm out of expected range"
    
    def test_received_power_invalid_distance(self):
        """Test that invalid distance raises error."""
        with pytest.raises(ValueError):
            calculate_received_power(
                tx_power_dbm=43.0,
                tx_antenna_gain_dbi=0.0,
                rx_antenna_gain_dbi=0.0,
                distance_m=-1,
                elevation_angle_deg=30.0,
            )
    
    def test_received_power_with_rain_lower(self):
        """Test that rain fade reduces received power."""
        rx_clear = calculate_received_power(
            tx_power_dbm=43.0,
            tx_antenna_gain_dbi=0.0,
            rx_antenna_gain_dbi=0.0,
            distance_m=650e3,
            elevation_angle_deg=30.0,
            rain_rate_mmhr=0.0,
        )
        rx_rain = calculate_received_power(
            tx_power_dbm=43.0,
            tx_antenna_gain_dbi=0.0,
            rx_antenna_gain_dbi=0.0,
            distance_m=650e3,
            elevation_angle_deg=30.0,
            rain_rate_mmhr=5.0,
        )
        assert rx_rain < rx_clear, "Rain should decrease RX power"


class TestSNRCalculation:
    """Test SNR calculation."""
    
    def test_snr_positive_signal(self):
        """Test SNR with strong signal."""
        snr = calculate_signal_to_noise_ratio(received_power_dbm=-90.0)
        assert snr > 0, "Strong signal should have positive SNR"
    
    def test_snr_weak_signal(self):
        """Test SNR with weak signal."""
        snr = calculate_signal_to_noise_ratio(received_power_dbm=-150.0)
        assert snr < 0, "Weak signal should have negative SNR"
    
    def test_snr_affects_noise_figure(self):
        """Test that higher noise figure decreases SNR."""
        snr_low_nf = calculate_signal_to_noise_ratio(received_power_dbm=-100.0, noise_figure_db=5.0)
        snr_high_nf = calculate_signal_to_noise_ratio(received_power_dbm=-100.0, noise_figure_db=10.0)
        assert snr_low_nf > snr_high_nf, "Lower noise figure should improve SNR"


class TestPowerConversions:
    """Test power unit conversions."""
    
    def test_dbm_to_watts_reference(self):
        """Test conversion: 0 dBm = 1 mW."""
        watts = dbm_to_watts(0)
        assert abs(watts - 0.001) < 1e-6, "0 dBm should equal 1 mW"
    
    def test_watts_to_dbm_reference(self):
        """Test conversion: 1 mW = 0 dBm."""
        dbm = watts_to_dbm(0.001)
        assert abs(dbm - 0.0) < 0.01, "1 mW should equal 0 dBm"
    
    def test_power_conversion_roundtrip(self):
        """Test that conversion roundtrip is accurate."""
        original_dbm = -50.0
        watts = dbm_to_watts(original_dbm)
        recovered_dbm = watts_to_dbm(watts)
        assert abs(recovered_dbm - original_dbm) < 0.01, "Roundtrip conversion error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
