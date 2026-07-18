"""
5G-NTN Satellite Network Simulator - Main Orchestration Engine

Coordinates the complete simulation pipeline:
1. Orbital propagation (Skyfield/SGP4) - satellite position tracking
2. Geographic study area - ground receiver grid generation
3. RF propagation - deterministic path loss calculation
4. Link budget analysis - service availability determination
5. Coverage analytics - aggregated statistics and visualization
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import os
import sys
import json
import time
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from skyfield.api import EarthSatellite, Loader

from rf_propagation import (
    calculate_received_power,
    calculate_antenna_gain_3gpp,
    calculate_receiver_antenna_gain,
    calculate_doppler_shift,       
    TYPICAL_LEO_VELOCITY_KM_S,     
    FREQ_S_BAND_HZ,
)
from study_area import StudyArea, GroundReceiverGrid
from link_budget import calculate_link_budget, calculate_link_budget_vectorized, generate_link_budget_report, print_link_budget_summary
from analysis_engine import generate_coverage_analytics
from htz_client import HTZPayloadEngine

BANNER = """
╔═══════════════════════════════════════════════════════════════════════╗
║           5G-NTN TIME-SERIES COVERAGE SIMULATION ENGINE               ║
║     Next-Generation Non-Terrestrial Network (NTN) Satellite Analysis  ║
╚═══════════════════════════════════════════════════════════════════════╝
"""

# Satellite TLE (Two-Line Element) - Real NORAD ephemeris data
TLE_LINE1 = "1 52949U 22067A   26155.19792824 -.00001084  00000-0 -54657-4 0  9997"
TLE_LINE2 = "2 52949  53.2181 290.1345 0001323  97.1245 262.9992 15.08779434218846"
SITE_NAME = "NTN-LEO-SAT"
SIMULATION_SITE = "LEO_5G_NodeB"

# 5G Satellite Transmitter Parameters (3GPP TR 38.811)
TX_POWER_DBM = 43.0
FREQUENCY_HZ = FREQ_S_BAND_HZ
RAIN_RATE_MMHR = 0.0

# =====================================================================
# THESIS CONFIGURATION PARAMETERS
# =====================================================================

ENABLE_DOPPLER_PRECOMPENSATION = True

# Study Area Configuration: Lodz University of Technology (TUL) Campus
STUDY_AREA_CONFIG = {
    "center_lat": 51.7470,    
    "center_lon": 19.4553,    
    "width_km": 3,            
    "height_km": 3,           
    "resolution_m": 50,       # HIGH FIDELITY ENABLED
    "min_elevation_deg": 5.0,
}

START_TIME = datetime.now(timezone.utc)
TIME_STEP_MINUTES = 1         
TOTAL_STEPS = 60              

# =====================================================================


def build_satellite_tracker():
    try:
        load = Loader('./satellite_data')
        ts = load.timescale()
        satellite = EarthSatellite(TLE_LINE1, TLE_LINE2, SITE_NAME, ts)
        return ts, satellite
    except Exception as exc:
        print(f"[ERROR] Failed to initialize satellite tracker: {exc}")
        raise

def propagate_satellite_position(ts, satellite, current_time):
    skyfield_time = ts.utc(
        current_time.year, current_time.month, current_time.day,
        current_time.hour, current_time.minute, current_time.second,
    )
    geocentric = satellite.at(skyfield_time)
    subpoint = geocentric.subpoint()
    return (subpoint.latitude.degrees, subpoint.longitude.degrees, subpoint.elevation.km)

def load_constellation_config(config_file: str = "satellite_constellation.json") -> Dict:
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Config failed: {e}")
        raise

def simulate_constellation_coverage_snapshot(
    satellites: List[Dict], ts, current_time,
    ground_receiver_grid: GroundReceiverGrid, constellation_name: str = "constellation",
) -> List[dict]:
    sat_objects = []
    for sat_config in satellites:
        try:
            sat = EarthSatellite(sat_config['tle_line1'], sat_config['tle_line2'], sat_config['name'], ts)
            sat_objects.append((sat_config['name'], sat))
        except Exception as e: 
            print(f"  [WARNING] Failed to load {sat_config['name']}: {e}")
            continue
        
    if not sat_objects: return []
    
    # Extract structural arrays of the campus ONCE
    geometry = ground_receiver_grid.get_receiver_geometry(0, 0, 0)
    receiver_idx = np.array([g['index'] for g in geometry])
    rx_lat = np.array([g['lat'] for g in geometry])
    rx_lon = np.array([g['lon'] for g in geometry])
    num_receivers = len(receiver_idx)
    
    aggregate_available = np.zeros(num_receivers, dtype=bool)
    
    snapshot_data = {
        'receiver_index': receiver_idx,
        'lat': rx_lat,
        'lon': rx_lon,
        'num_satellites': np.full(num_receivers, len(sat_objects))
    }
    
    for sat_name, satellite in sat_objects:
        sat_lat, sat_lon, sat_altitude_km = propagate_satellite_position(ts, satellite, current_time)
        sat_altitude_m = sat_altitude_km * 1000
        
        # Extract dynamic geometry relative to satellite position
        sat_geometry = ground_receiver_grid.get_receiver_geometry(sat_lat, sat_lon, sat_altitude_m)
        slant_distance_m = np.array([g['slant_distance_m'] for g in sat_geometry])
        elevation_angle_deg = np.array([g['elevation_angle_deg'] for g in sat_geometry])
        
        # Vectorized RF Physics (Processes all 3,660 receivers at once)
        tx_antenna_gain = calculate_antenna_gain_3gpp(elevation_angle_deg, boresight_elevation_deg=elevation_angle_deg)
        rx_antenna_gain = calculate_receiver_antenna_gain(elevation_angle_deg)
        
        rx_power_dbm = calculate_received_power(
            TX_POWER_DBM, tx_antenna_gain, rx_antenna_gain,
            slant_distance_m, elevation_angle_deg,
            FREQUENCY_HZ, RAIN_RATE_MMHR, True
        )
        
        physical_doppler_hz = calculate_doppler_shift(TYPICAL_LEO_VELOCITY_KM_S, FREQUENCY_HZ, elevation_angle_deg)
        applied_doppler_hz = np.full_like(physical_doppler_hz, 500.0) if ENABLE_DOPPLER_PRECOMPENSATION else physical_doppler_hz
        
        # Vectorized Link Budget Validation
        lb = calculate_link_budget_vectorized(
            receiver_idx, rx_lat, rx_lon, rx_power_dbm, tx_antenna_gain, rx_antenna_gain,
            np.zeros(num_receivers), np.zeros(num_receivers), TX_POWER_DBM,
            elevation_angle_deg, "QPSK_CR_1_4", applied_doppler_hz
        )
        
        snapshot_data[f"{sat_name}_rx_power_dbm"] = rx_power_dbm
        snapshot_data[f"{sat_name}_link_margin_db"] = lb['link_margin_db']
        snapshot_data[f"{sat_name}_available"] = lb['is_serviceable']
        snapshot_data[f"{sat_name}_elevation_deg"] = elevation_angle_deg
        snapshot_data[f"{sat_name}_slant_distance_km"] = slant_distance_m / 1000.0
        snapshot_data[f"{sat_name}_doppler_hz"] = applied_doppler_hz
        snapshot_data[f"{sat_name}_outage_reason"] = lb['outage_reason']
        
        aggregate_available = aggregate_available | lb['is_serviceable']
    
    snapshot_data['aggregate_available'] = aggregate_available
    
    # Re-pack arrays into CSV-friendly records list
    records = []
    for i in range(num_receivers):
        record = {}
        for key, arr in snapshot_data.items():
            record[key] = arr[i]
        records.append(record)
    
    return records


def simulate_satellite_coverage_snapshot(
    sat_lat: float, sat_lon: float, sat_altitude_km: float, ground_receiver_grid: GroundReceiverGrid,
) -> List[dict]:
    sat_altitude_m = sat_altitude_km * 1000
    geometry = ground_receiver_grid.get_receiver_geometry(sat_lat, sat_lon, sat_altitude_m)
    
    receiver_idx = np.array([g['index'] for g in geometry])
    rx_lat = np.array([g['lat'] for g in geometry])
    rx_lon = np.array([g['lon'] for g in geometry])
    slant_distance_m = np.array([g['slant_distance_m'] for g in geometry])
    elevation_angle_deg = np.array([g['elevation_angle_deg'] for g in geometry])
    num_receivers = len(receiver_idx)
    
    tx_antenna_gain = calculate_antenna_gain_3gpp(elevation_angle_deg, boresight_elevation_deg=elevation_angle_deg)
    rx_antenna_gain = calculate_receiver_antenna_gain(elevation_angle_deg)
    
    rx_power_dbm = calculate_received_power(TX_POWER_DBM, tx_antenna_gain, rx_antenna_gain, slant_distance_m, elevation_angle_deg, FREQUENCY_HZ, RAIN_RATE_MMHR, True)
    
    physical_doppler_hz = calculate_doppler_shift(TYPICAL_LEO_VELOCITY_KM_S, FREQUENCY_HZ, elevation_angle_deg)
    applied_doppler_hz = np.full_like(physical_doppler_hz, 500.0) if ENABLE_DOPPLER_PRECOMPENSATION else physical_doppler_hz
    
    lb = calculate_link_budget_vectorized(
        receiver_idx, rx_lat, rx_lon, rx_power_dbm, tx_antenna_gain, rx_antenna_gain,
        np.zeros(num_receivers), np.zeros(num_receivers), TX_POWER_DBM,
        elevation_angle_deg, "QPSK_CR_1_4", applied_doppler_hz
    )
    
    records = []
    for i in range(num_receivers):
        records.append({
            'receiver_index': receiver_idx[i], 'lat': rx_lat[i], 'lon': rx_lon[i],
            'elevation_deg': elevation_angle_deg[i], 'slant_distance_km': slant_distance_m[i] / 1000.0,
            'rx_power_dbm': rx_power_dbm[i], 'link_margin_db': lb['link_margin_db'][i],
            'snr_db': lb['snr_db'][i], 'doppler_shift_hz': applied_doppler_hz[i],
            'outage_reason': lb['outage_reason'][i], 'serviceable': lb['is_serviceable'][i],
        })
    return records


def generate_constellation_comparison_plot(
    single_sat_availability: np.ndarray, constellation_availability: np.ndarray, output_file: str = "constellation_availability_cdf.png",
) -> None:
    sorted_single = np.sort(single_sat_availability)
    sorted_const = np.sort(constellation_availability)
    y_vals = np.arange(1, len(sorted_single) + 1) / len(sorted_single)
    
    plt.figure(figsize=(10, 6))
    plt.plot(sorted_single, y_vals, marker='.', linestyle='-', color='#1f77b4', label='Single Satellite', linewidth=2, markersize=4, alpha=0.7)
    plt.plot(sorted_const, y_vals, marker='s', linestyle='-', color='#ff7f0e', label='Constellation (Aggregate)', linewidth=2, markersize=4, alpha=0.7)
    
    plt.title("Service Availability: Single Satellite vs. Constellation", fontsize=12, fontweight='bold')
    plt.xlabel("Availability (Fraction of Simulation Time)", fontsize=11)
    plt.ylabel("CDF (Fraction of Coverage Area)", fontsize=11)
    plt.grid(True, which="both", ls="--", alpha=0.3)
    plt.legend(loc="lower right", fontsize=10)
    plt.xlim([-0.05, 1.05])
    plt.ylim([0, 1.05])
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"  ✓ Generated: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="5G-NTN Satellite Network Simulator")
    parser.add_argument('--constellation', type=str, default=None)
    args = parser.parse_args()
    constellation_mode = args.constellation is not None
    
    print(BANNER)
    print("[1/4] INITIALIZATION PHASE")
    print("─" * 70)
    
    if constellation_mode:
        print(f"  ⭐ CONSTELLATION MODE: {args.constellation}")
        config = load_constellation_config()
        if args.constellation not in config.get('constellations', {}):
            print(f"[ERROR] Constellation '{args.constellation}' not found in config")
            sys.exit(1)
        
        constellation_def = config['constellations'][args.constellation]
        satellites = constellation_def['satellites']
        print(f"  ✓ Loaded constellation: {args.constellation}")
        print(f"    Satellites: {len(satellites)}")
    else:
        print("  ⚪ SINGLE SATELLITE MODE (default)")
        ts, satellite = build_satellite_tracker()
        print("  ✓ Satellite orbital tracker initialized")
    
    print(f"  ✓ Doppler Pre-Compensation: {'ACTIVE' if ENABLE_DOPPLER_PRECOMPENSATION else 'DISABLED'}")
    
    study_area = StudyArea(
        center_lat=STUDY_AREA_CONFIG["center_lat"],
        center_lon=STUDY_AREA_CONFIG["center_lon"],
        width_km=STUDY_AREA_CONFIG["width_km"],
        height_km=STUDY_AREA_CONFIG["height_km"],
        resolution_m=STUDY_AREA_CONFIG["resolution_m"],
        min_elevation_deg=STUDY_AREA_CONFIG["min_elevation_deg"],
    )
    ground_grid = GroundReceiverGrid(study_area)
    print(f"  ✓ TUL Campus initialized: {STUDY_AREA_CONFIG['width_km']}×{STUDY_AREA_CONFIG['height_km']} km")
    print(f"    Total receivers ({STUDY_AREA_CONFIG['resolution_m']}m res): {ground_grid.get_num_receivers()}")
    
    if constellation_mode:
        load = Loader('./satellite_data')
        ts = load.timescale()
    
    print("\n[2/4] ORBITAL COVERAGE SWEEP")
    print("─" * 70)
    print(f"  Simulating {TOTAL_STEPS} timesteps ({TOTAL_STEPS * TIME_STEP_MINUTES} minutes)")
    print(f"  Vectorized Math Engine Active - Calculating {TOTAL_STEPS * ground_grid.get_num_receivers() * (len(satellites) if constellation_mode else 1):,} link budgets...")
    
    all_coverage_data = []
    step_summaries = []
    
    for step in range(TOTAL_STEPS):
        current_sim_time = START_TIME + timedelta(minutes=step * TIME_STEP_MINUTES)
        
        if constellation_mode:
            coverage_snapshot = simulate_constellation_coverage_snapshot(satellites, ts, current_sim_time, ground_grid, args.constellation)
            available_count = sum(1 for c in coverage_snapshot if c.get('aggregate_available', False))
        else:
            sat_lat, sat_lon, sat_altitude_km = propagate_satellite_position(ts, satellite, current_sim_time)
            coverage_snapshot = simulate_satellite_coverage_snapshot(sat_lat, sat_lon, sat_altitude_km, ground_grid)
            available_count = sum(1 for c in coverage_snapshot if c['serviceable'])
        
        all_coverage_data.extend(coverage_snapshot)
        availability_pct = (available_count / len(coverage_snapshot)) * 100 if coverage_snapshot else 0
        
        step_summaries.append({
            'step': step + 1,
            'time_utc': current_sim_time.strftime("%H:%M:%S"),
            'available_receivers': available_count,
            'total_receivers': len(coverage_snapshot),
            'availability_pct': availability_pct,
        })
        
        if (step + 1) % 1 == 0:
            print(f"  [{step + 1:2d}/{TOTAL_STEPS}] {current_sim_time.strftime('%H:%M UTC')} | Availability: {availability_pct:.1f}%")
        
    print(f"  ✓ Orbital sweep complete: {len(all_coverage_data):,} coverage points collected")
    
    print("\n[3/4] LINK BUDGET ANALYSIS")
    print("─" * 70)
    df_coverage = pd.DataFrame(all_coverage_data)
    
    if not constellation_mode:
        # Fast sampling to prevent Pandas iteration bottleneck on massive datasets
        df_sample = df_coverage.sample(min(1000, len(df_coverage)))
        report = generate_link_budget_report(
            [calculate_link_budget(
                receiver_index=row['receiver_index'], receiver_lat=row['lat'], receiver_lon=row['lon'],
                received_power_dbm=row['rx_power_dbm'], tx_antenna_gain_dbi=0, rx_antenna_gain_dbi=0,
                path_loss_db=0, atmospheric_loss_db=0, tx_power_dbm=TX_POWER_DBM,
                elevation_angle_deg=row['elevation_deg'], mcs_key="QPSK_CR_1_4",
                doppler_shift_hz=row.get('doppler_shift_hz', 0.0) 
            ) for _, row in df_sample.iterrows()]
        )
        print_link_budget_summary(report)
    else:
        print(f"  ✓ Constellation coverage analysis complete")
        print(f"    Aggregate availability: {df_coverage['aggregate_available'].mean()*100:.1f}%")
    
    print("\n[4/4] VISUALIZATION & OUTPUT")
    print("─" * 70)
    
    if constellation_mode:
        csv_filename = f"constellation_{args.constellation}_analysis.csv"
        df_coverage.to_csv(csv_filename, index=False)
        print(f"  ✓ Generated: {csv_filename}")
        
        if len(satellites) > 1:
            single_sat_name = satellites[0].get('name', '')
            if f"{single_sat_name}_available" in df_coverage.columns:
                single_sat_avail = df_coverage[f"{single_sat_name}_available"].values.astype(float)
                constellation_avail = df_coverage['aggregate_available'].values.astype(float)
                
                generate_constellation_comparison_plot(
                    single_sat_avail,
                    constellation_avail,
                    f"constellation_{args.constellation}_comparison.png"
                )
                print(f"    Single satellite (baseline): {single_sat_name}")
                print(f"    Availability gain: {(constellation_avail.mean() - single_sat_avail.mean())*100:.1f}%")
    else:
        all_rx_powers = df_coverage['rx_power_dbm'].values
        metrics = generate_coverage_analytics(all_rx_powers)
        print(f"  ✓ Generated: ntn_coverage_cdf.png")
        csv_filename = "ntn_coverage_analysis.csv"
        df_coverage.to_csv(csv_filename, index=False)
        print(f"  ✓ Generated: {csv_filename}")
    
    df_timeline = pd.DataFrame(step_summaries)
    timeline_filename = "ntn_orbital_timeline.csv"
    df_timeline.to_csv(timeline_filename, index=False)
    print(f"  ✓ Generated: {timeline_filename}")
    
    print("\n" + "=" * 70)
    print("SIMULATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()