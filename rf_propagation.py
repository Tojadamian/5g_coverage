"""
RF Propagation Engine for 5G-NTN Satellite Link Analysis

Refactored for High-Performance NumPy Vectorization. 
All functions now accept either scalar floats or massive N-dimensional NumPy arrays, 
eliminating the need for standard Python `for` loops in the main orchestrator.

Physical Models:
    Free-space path loss: PL(dB) = 20*log10(4πd/λ)
    Atmospheric effects per ITU-R P.618 (rain fade, oxygen absorption)
    Antenna gain: G(θ) = directional 3GPP phased array pattern
    Doppler Shift: fd = (v/c) * f * cos(θ)
"""

import numpy as np

# ==================== RF CONSTANTS ====================

SPEED_OF_LIGHT = 3e8  # m/s
BOLTZMANN_CONSTANT = 1.380649e-23  # J/K
REFERENCE_TEMPERATURE = 290  # Kelvin
REFERENCE_IMPEDANCE = 50  # Ohms

# 5G S-Band operational parameters (ITU-R P.618 band)
FREQ_S_BAND_MHZ = 2100.0
FREQ_S_BAND_HZ = FREQ_S_BAND_MHZ * 1e6
WAVELENGTH_S_BAND = SPEED_OF_LIGHT / FREQ_S_BAND_HZ
TYPICAL_LEO_VELOCITY_KM_S = 7.56 # Typical orbital velocity for 540km altitude

# Atmospheric model parameters
OXYGEN_ABSORPTION_COEFF = 0.00035  # dB/km at 2100 MHz (ITU-R P.676)
RAIN_RATE_PERCENTILE = 0.01  # 0.01% of year (99.99% availability reference)
RAIN_ATTENUATION_COEFF = 0.4  # dB/(mm/hr) for S-Band


# ==================== KINEMATIC CALCULATIONS ====================

def calculate_doppler_shift(
    velocity_km_s: float = TYPICAL_LEO_VELOCITY_KM_S, 
    frequency_hz: float = FREQ_S_BAND_HZ, 
    elevation_angle_deg=0.0
):
    """
    Calculates the Doppler shift frequency offset. Vectorized for arrays.
    """
    elevation_angle_deg = np.asarray(elevation_angle_deg)
    # Clamp extreme values for safety across large matrices
    elevation_angle_deg = np.clip(elevation_angle_deg, 0, 90)
        
    speed_of_light_km_s = SPEED_OF_LIGHT / 1000.0
    theta_rad = np.radians(elevation_angle_deg)
    
    shift_hz = (velocity_km_s / speed_of_light_km_s) * frequency_hz * np.cos(theta_rad)
    return shift_hz


# ==================== PATH LOSS CALCULATIONS ====================

def calculate_free_space_path_loss(distance_m, frequency_hz: float):
    """
    Calculate free-space path loss using Friis equation. Vectorized.
    """
    distance_m = np.asarray(distance_m)
    # Prevent divide-by-zero or log(0) in large array calculations
    distance_safe = np.maximum(distance_m, 1.0) 
    
    path_loss_db = 20 * np.log10(4 * np.pi * distance_safe * frequency_hz / SPEED_OF_LIGHT)
    return path_loss_db


def calculate_oxygen_absorption(distance_km, frequency_hz: float = FREQ_S_BAND_HZ):
    """
    Calculate atmospheric oxygen absorption loss. Vectorized for distance arrays.
    """
    distance_km = np.asarray(distance_km)
    distance_safe = np.maximum(distance_km, 0.0)
    
    if frequency_hz < 1e9:  
        coeff = 0.0005
    elif frequency_hz < 10e9:  
        coeff = OXYGEN_ABSORPTION_COEFF
    else:  
        coeff = 0.002
        
    return distance_safe * coeff
    

def calculate_rain_fade(elevation_angle_deg, rain_rate_mmhr: float = 1.0):
    """
    Estimate rain fade attenuation using ITU-R P.618 model. Vectorized.
    """
    elevation_angle_deg = np.asarray(elevation_angle_deg)
    
    # Vectorized equivalent of "if el < 5: 5 else: el"
    eff_elevation = np.maximum(elevation_angle_deg, 5.0)
    slant_factor = 1.0 / np.sin(np.radians(eff_elevation))
    
    alpha = RAIN_ATTENUATION_COEFF
    beta = 0.95
    
    rain_attenuation_horizontal = alpha * (rain_rate_mmhr ** beta)
    rain_attenuation_slant = rain_attenuation_horizontal * slant_factor
    
    return rain_attenuation_slant


# ==================== ANTENNA GAIN PATTERNS ====================

def calculate_antenna_gain_3gpp(
    elevation_angle_deg, 
    azimuth_angle_deg=0.0,
    boresight_elevation_deg=90.0
):
    """
    Calculate antenna gain using 3GPP pattern. Fully vectorized using np.where.
    """
    elevation_angle_deg = np.asarray(elevation_angle_deg)
    phi = np.radians(np.asarray(azimuth_angle_deg))
    
    gain_peak_dbi = 18.0
    beamwidth_half_power = 30.0
    
    el_offset = np.abs(elevation_angle_deg - boresight_elevation_deg)
    
    # Gain Calculation: Inside the main beam
    gain_db_in_beam = gain_peak_dbi * np.cos(np.radians(el_offset / beamwidth_half_power * 90.0))
    
    # Gain Calculation: Outside the main beam (sidelobes)
    el_offset_safe = np.where(el_offset == 0, 0.001, el_offset)
    sidelobe_atten_db = 20 * np.log10(el_offset_safe / beamwidth_half_power)
    gain_db_out_of_beam = np.maximum(-20.0, -sidelobe_atten_db)
    
    # Vectorized conditional application
    gain_db = np.where(el_offset < beamwidth_half_power, gain_db_in_beam, gain_db_out_of_beam)
    
    # Azimuth rolloff
    az_rolloff_val = 20 * np.log10(np.maximum(np.cos(phi / 2.0), 0.0001))
    azimuth_rolloff = np.where(np.abs(phi) < np.pi, az_rolloff_val, -20.0)
    
    total_gain = gain_db + np.maximum(-3.0, azimuth_rolloff)
    
    return total_gain


def calculate_receiver_antenna_gain(elevation_angle_deg):
    """
    Calculate receiver (ground) antenna gain. Vectorized.
    """
    elevation_angle_deg = np.asarray(elevation_angle_deg)
    
    safe_el = np.maximum(elevation_angle_deg, 0.001)
    masking_loss = np.where(safe_el > 0, 10 * np.log10(safe_el / 10.0), -20.0)
    
    # If elevation >= 10, gain is 0. If less, apply masking loss
    gain_dbi = np.where(elevation_angle_deg < 10, masking_loss, 0.0)
    
    return gain_dbi


# ==================== COMPLETE LINK BUDGET ====================

def calculate_received_power(
    tx_power_dbm,
    tx_antenna_gain_dbi,
    rx_antenna_gain_dbi,
    distance_m,
    elevation_angle_deg,
    frequency_hz: float = FREQ_S_BAND_HZ,
    rain_rate_mmhr: float = 0.0,
    atmospheric_loss_enabled: bool = True,
):
    """
    Calculate received power at ground receiver using complete link budget. Vectorized.
    """
    distance_m = np.asarray(distance_m)
    elevation_angle_deg = np.asarray(elevation_angle_deg)
    
    path_loss_db = calculate_free_space_path_loss(distance_m, frequency_hz)
    
    atmospheric_loss_db = 0.0
    if atmospheric_loss_enabled:
        eff_el = np.maximum(elevation_angle_deg, 0.001)
        slant_path_km = np.where(elevation_angle_deg > 0, 10.0 / np.sin(np.radians(eff_el)), 10.0)
        
        oxygen_loss_db = calculate_oxygen_absorption(slant_path_km, frequency_hz)
        rain_loss_db = calculate_rain_fade(elevation_angle_deg, rain_rate_mmhr)
        atmospheric_loss_db = oxygen_loss_db + rain_loss_db
    
    received_power_dbm = (
        tx_power_dbm
        + tx_antenna_gain_dbi
        + rx_antenna_gain_dbi
        - path_loss_db
        - atmospheric_loss_db
    )
    
    return received_power_dbm


# ==================== UTILITY FUNCTIONS ====================

def dbm_to_watts(power_dbm):
    return 10 ** ((np.asarray(power_dbm) - 30) / 10.0)

def watts_to_dbm(power_watts):
    return 10 * np.log10(np.asarray(power_watts) * 1000.0)

def calculate_signal_to_noise_ratio(
    received_power_dbm,
    noise_figure_db: float = 7.0,
    bandwidth_hz: float = 20e6,
):
    received_power_dbm = np.asarray(received_power_dbm)
    noise_power_dbm = -174 + noise_figure_db + 10 * np.log10(bandwidth_hz)
    snr_db = received_power_dbm - noise_power_dbm
    return snr_db


if __name__ == "__main__":
    # Self-test: Calculate realistic 5G-NTN link budget (Still supports scalar floats seamlessly)
    print("=" * 60)
    print("5G-NTN SATELLITE LINK BUDGET CALCULATION (VECTORIZED)")
    print("=" * 60)
    
    tx_power_dbm = 43.0
    satellite_altitude_km = 540
    distance_m = np.sqrt((satellite_altitude_km * 1000) ** 2 + (100e3) ** 2)
    elevation_angle_deg = 30.0
    
    tx_gain = calculate_antenna_gain_3gpp(elevation_angle_deg)
    rx_gain = calculate_receiver_antenna_gain(elevation_angle_deg)
    
    rx_power_clear = calculate_received_power(
        tx_power_dbm=tx_power_dbm,
        tx_antenna_gain_dbi=tx_gain,
        rx_antenna_gain_dbi=rx_gain,
        distance_m=distance_m,
        elevation_angle_deg=elevation_angle_deg,
        rain_rate_mmhr=0.0,
    )
    
    snr_clear = calculate_signal_to_noise_ratio(rx_power_clear)
    doppler_hz = calculate_doppler_shift(elevation_angle_deg=elevation_angle_deg)
    
    print(f"\\nGeometry & Kinematics:")
    print(f"  Ground range: ~{distance_m/1000:.0f} km")
    print(f"  Doppler Shift: {float(doppler_hz)/1000:.2f} kHz")
    print(f"\\nAntenna Gains:")
    print(f"  TX (satellite) gain: {float(tx_gain):.1f} dBi")
    print(f"\\nLink Budget:")
    print(f"  RX Power: {float(rx_power_clear):.1f} dBm")
    print(f"  SNR: {float(snr_clear):.1f} dB")
    print("=" * 60)