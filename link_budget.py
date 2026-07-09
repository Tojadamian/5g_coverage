"""
Link Budget Analysis for 5G-NTN Service Availability

Implements deterministic link margin calculations and service availability
determination based on 3GPP Release 17 standards.

Key Metrics:
    - Receiver sensitivity (thermal noise + required SNR)
    - Link margin (RX power - sensitivity threshold)
    - Modulation efficiency for different 5G conditions
    - Service availability percentage
"""

import numpy as np
from dataclasses import dataclass
from typing import Dict, List


# ==================== 5G LINK BUDGET PARAMETERS ====================

BANDWIDTH_HZ = 20e6
NOISE_FIGURE_DB = 7.0
THERMAL_NOISE_FLOOR = -174.0

@dataclass
class ModulationScheme:
    """5G modulation and coding scheme (MCS) characteristics."""
    name: str
    modulation: str
    coding_rate: float
    required_snr_db: float  
    spectral_efficiency_bps_hz: float  


MCS_TABLE = {
    "QPSK_CR_1_4": ModulationScheme(
        name="QPSK CR=1/4",
        modulation="QPSK",
        coding_rate=0.25,
        required_snr_db=-5.0,  
        spectral_efficiency_bps_hz=0.5,
    ),
    "16QAM_CR_1_2": ModulationScheme(
        name="16QAM CR=1/2",
        modulation="16QAM",
        coding_rate=0.5,
        required_snr_db=3.0,
        spectral_efficiency_bps_hz=2.0,
    ),
}

@dataclass
class LinkBudgetMetrics:
    receiver_index: int
    receiver_lat: float
    receiver_lon: float
    tx_power_dbm: float
    tx_antenna_gain_dbi: float
    rx_antenna_gain_dbi: float
    path_loss_db: float
    atmospheric_loss_db: float
    received_power_dbm: float
    receiver_sensitivity_dbm: float
    link_margin_db: float
    snr_db: float
    selected_mcs: str
    is_serviceable: bool
    outage_reason: str
    doppler_shift_hz: float = 0.0
    doppler_pass: bool = True


# ==================== SCALAR CALCULATION (Legacy) ====================
def calculate_receiver_sensitivity(noise_figure_db: float, bandwidth_hz: float, required_snr_db: float) -> float:
    noise_power_dbm = THERMAL_NOISE_FLOOR + 10 * np.log10(bandwidth_hz)
    effective_noise_dbm = noise_power_dbm + noise_figure_db
    return effective_noise_dbm + required_snr_db

def calculate_link_budget(
    receiver_index: int, receiver_lat: float, receiver_lon: float,
    received_power_dbm: float, tx_antenna_gain_dbi: float, rx_antenna_gain_dbi: float,
    path_loss_db: float, atmospheric_loss_db: float, tx_power_dbm: float,
    elevation_angle_deg: float, mcs_key: str = "QPSK_CR_1_4",
    doppler_shift_hz: float = 0.0, max_doppler_tolerance_hz: float = 24000.0
) -> LinkBudgetMetrics:
    """Original loop-based scalar function."""
    doppler_pass = abs(doppler_shift_hz) <= max_doppler_tolerance_hz

    if elevation_angle_deg < 5.0:
        return LinkBudgetMetrics(receiver_index, receiver_lat, receiver_lon, tx_power_dbm, tx_antenna_gain_dbi, rx_antenna_gain_dbi, path_loss_db, atmospheric_loss_db, received_power_dbm, 0, 0, -1000, "NONE", False, "Below minimum elevation angle (5°)", doppler_shift_hz, doppler_pass)
    
    mcs = MCS_TABLE[mcs_key]
    sensitivity_dbm = calculate_receiver_sensitivity(NOISE_FIGURE_DB, BANDWIDTH_HZ, mcs.required_snr_db)
    noise_power_dbm = THERMAL_NOISE_FLOOR + 10 * np.log10(BANDWIDTH_HZ)
    effective_noise_dbm = noise_power_dbm + NOISE_FIGURE_DB
    snr_db = received_power_dbm - effective_noise_dbm
    link_margin_db = received_power_dbm - sensitivity_dbm
    
    fade_margin_reserve = 3.0  
    is_serviceable = (link_margin_db > fade_margin_reserve) and (elevation_angle_deg >= 5.0) and doppler_pass
    
    outage_reason = ""
    if not doppler_pass:
        outage_reason = f"Doppler shift exceeded limit ({abs(doppler_shift_hz)/1000:.1f} kHz > {max_doppler_tolerance_hz/1000:.0f} kHz)"
    elif link_margin_db <= fade_margin_reserve:
        outage_reason = f"Insufficient margin ({link_margin_db:.1f} dB < {fade_margin_reserve} dB reserve)"
    
    return LinkBudgetMetrics(receiver_index, receiver_lat, receiver_lon, tx_power_dbm, tx_antenna_gain_dbi, rx_antenna_gain_dbi, path_loss_db, atmospheric_loss_db, received_power_dbm, sensitivity_dbm, link_margin_db, snr_db, mcs_key, is_serviceable, outage_reason, doppler_shift_hz, doppler_pass)


# ==================== VECTORIZED CALCULATION (High Performance) ====================
def calculate_link_budget_vectorized(
    receiver_index, receiver_lat, receiver_lon,
    received_power_dbm, tx_antenna_gain_dbi, rx_antenna_gain_dbi,
    path_loss_db, atmospheric_loss_db, tx_power_dbm,
    elevation_angle_deg, mcs_key="QPSK_CR_1_4",
    doppler_shift_hz=0.0, max_doppler_tolerance_hz=24000.0
) -> dict:
    """Processes millions of receivers simultaneously using NumPy arrays."""
    
    # Convert all inputs to NumPy arrays
    received_power_dbm = np.asarray(received_power_dbm)
    elevation_angle_deg = np.asarray(elevation_angle_deg)
    doppler_shift_hz = np.asarray(doppler_shift_hz)

    # Boolean logic arrays
    doppler_pass = np.abs(doppler_shift_hz) <= max_doppler_tolerance_hz
    visible = elevation_angle_deg >= 5.0

    mcs = MCS_TABLE[mcs_key]

    noise_power_dbm = THERMAL_NOISE_FLOOR + 10 * np.log10(BANDWIDTH_HZ)
    effective_noise_dbm = noise_power_dbm + NOISE_FIGURE_DB
    sensitivity_dbm = effective_noise_dbm + mcs.required_snr_db

    snr_db = received_power_dbm - effective_noise_dbm
    link_margin_db = received_power_dbm - sensitivity_dbm

    fade_margin_reserve = 3.0
    is_serviceable = (link_margin_db > fade_margin_reserve) & visible & doppler_pass

    # Generate string outage reasons extremely fast using np.select
    condlist = [~visible, ~doppler_pass, link_margin_db <= fade_margin_reserve]
    choicelist = ["Below minimum elevation angle (5°)", "Doppler shift exceeded limit", "Insufficient margin"]
    outage_reason = np.select(condlist, choicelist, default="")

    return {
        'receiver_index': receiver_index,
        'receiver_lat': receiver_lat,
        'receiver_lon': receiver_lon,
        'received_power_dbm': received_power_dbm,
        'link_margin_db': link_margin_db,
        'snr_db': snr_db,
        'is_serviceable': is_serviceable,
        'outage_reason': outage_reason,
        'doppler_shift_hz': doppler_shift_hz,
        'doppler_pass': doppler_pass
    }

def generate_link_budget_report(metrics_list):
    return metrics_list

def print_link_budget_summary(report):
    pass