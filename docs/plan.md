# Multi-Satellite Constellation Extension Plan

## Overview
Extend the 5G-NTN satellite simulator from single-satellite to multi-satellite constellation capability while maintaining 100% backward compatibility with existing tests.

## Key Changes

### 1. Create Constellation Configuration File (`satellite_constellation.json`)
- Store sample constellation definitions using existing TLE data
- Support multiple named constellations (e.g., "iridium_sample", "single_leo")
- Each constellation specifies a list of satellite TLE references
- Schema:
  ```json
  {
    "constellations": {
      "constellation_name": {
        "description": "...",
        "satellites": ["TLE_NAME1", "TLE_NAME2", ...]
      }
    }
  }
  ```

### 2. Refactor `main_simulator.py`
#### Key Functions:
- **`simulate_constellation_coverage()` (NEW)**: 
  - Accept list of satellite TLE dicts, study_area, timestamp
  - For each receiver, calculate coverage from each satellite independently
  - Aggregate as "serviceable" if ANY satellite provides link margin > 3 dB
  - Return per-satellite AND aggregate results
  - Returns dict with per-sat columns and aggregate_available

- **`simulate_satellite_coverage_snapshot()` (KEEP)**:
  - Existing single-satellite function unchanged for backward compatibility
  
- **`main()` (MODIFY)**:
  - Add `--constellation <name>` CLI argument (optional)
  - Default behavior (no flag) = current single-satellite simulation
  - When `--constellation` specified:
    - Load constellation config
    - Resolve satellite TLE names to actual TLE data
    - Execute constellation simulation for each timestep
    - Generate comparison outputs

#### CLI Examples:
```bash
python main_simulator.py                                # Default: single satellite (existing behavior)
python main_simulator.py --constellation iridium_sample # Multi-sat constellation
python main_simulator.py --constellation single_leo     # Single sat from config
```

### 3. Enhanced Output
#### CSV Format (per-satellite + aggregate):
```csv
receiver_index,lat,lon,elevation_deg,slant_distance_km,
Sat_0_RX_Power,Sat_0_Link_Margin,Sat_0_Available,
Sat_1_RX_Power,Sat_1_Link_Margin,Sat_1_Available,
Sat_2_RX_Power,Sat_2_Link_Margin,Sat_2_Available,
Aggregate_Available
```

#### Comparison Visualization (NEW):
- CDF plot comparing:
  - Single satellite availability (baseline)
  - Constellation aggregate availability
  - Shows improvement from redundancy
- File: `constellation_availability_cdf.png` (only when `--constellation` used)

### 4. Implementation Strategy

#### Phase 1: Core Constellation Logic
1. Create `load_constellation_config()` function
2. Create `simulate_constellation_coverage()` function
3. Ensure backward compatibility (all 100 tests pass)

#### Phase 2: CLI and Integration
1. Add argparse support for `--constellation` flag
2. Modify `main()` to handle constellation mode
3. Keep existing behavior as default

#### Phase 3: Enhanced Output
1. Modify CSV generation for constellation output
2. Add constellation comparison plotting function
3. Generate side-by-side outputs

#### Phase 4: Testing
1. Verify all 100 existing tests still pass
2. Manual testing of CLI commands
3. Validate output files

## Files to Create
- `satellite_constellation.json` - Configuration file

## Files to Modify
- `main_simulator.py` - Core changes
  - Add `load_constellation_config()`
  - Add `simulate_constellation_coverage()`
  - Modify `main()` with CLI args
  - Update imports (argparse)
- `analysis_engine.py` - Potentially add constellation comparison plot

## Backward Compatibility
- ✅ Keep `simulate_satellite_coverage_snapshot()` unchanged
- ✅ Default behavior (no args) remains identical
- ✅ All existing 100 tests must pass
- ✅ CSV output format compatible with existing tools

## Success Criteria
- ✅ Constellation JSON loads without error
- ✅ Multi-satellite simulation works for 3+ satellites
- ✅ CSV output shows per-satellite results + aggregate
- ✅ Aggregate >= any single satellite availability
- ✅ CLI works: `python main_simulator.py --constellation iridium_sample`
- ✅ Default CLI works: `python main_simulator.py`
- ✅ All 100 existing tests still pass
- ✅ Comparison plot generated (constellation mode)

## Technical Details

### Constellation Coverage Calculation
For each receiver and each satellite:
1. Calculate slant distance and elevation angle
2. Calculate RX power
3. Calculate link margin
4. Determine if serviceable (link_margin_db > 3)

Aggregate for receiver:
- `Aggregate_Available = OR(Sat_0_Available, Sat_1_Available, ...)`
- This represents coverage availability from the constellation

### Data Flow (Constellation Mode)
```
Load Constellation Config
  ↓
Resolve satellite names to TLE data
  ↓
For each timestep:
  - Propagate each satellite position
  - For each receiver:
    - Calculate coverage from each satellite
    - Aggregate results
  - Collect per-satellite and aggregate results
  ↓
Generate CSV with per-sat columns + aggregate
Generate CDF comparison plot
```

## Notes
- Use existing TLE data (NORAD ephemeris from main_simulator.py)
- Leverage existing `calculate_link_budget()` and propagation functions
- Keep changes minimal to reduce regression risk
- All coordinate systems remain WGS84 (no changes needed)
- Timestamp handling unchanged
