# 5G-NTN Satellite Network Coverage Simulator

A production-grade Python simulator for evaluating 5G Non-Terrestrial Network (NTN) coverage using Low Earth Orbit (LEO) satellites. This project combines orbital mechanics, RF propagation physics, 3GPP Release 17 link budget analysis, and exposes a modern REST API via FastAPI.

---

## ✨ Key Features

- **RF Physics Engine:** Calculates free-space path loss (Friis), ITU-R P.618 atmospheric absorption, and 3GPP TR 38.811 phased array antenna gain patterns.
- **Geographic Framework:** Configurable study areas (e.g., 50×50 km) with uniformly-spaced ground receiver grids and highly accurate Haversine distance calculations.
- **Link Budget Analysis:** Incorporates 3GPP Release 17 receiver models, modulation scheme selection (QPSK/16QAM/64QAM), and strict service availability thresholds.
- **Modern REST API:** FastAPI backend for running background simulations, checking status, and fetching constellation data.
- **Extensive Analytics:** Generates Signal Strength Distribution plots (CDF), detailed receiver-level CSVs, and per-step availability metrics.

---

## 🛠 Prerequisites

- **Python 3.10+** (Python 3.12 recommended)
- **Git**

---

## 🚀 Installation

Follow these steps to set up the project on your local machine.

### 1. Clone the Repository

```bash
git clone [https://github.com/Tojadamian/5g_coverage.git](https://github.com/Tojadamian/5g_coverage.git)
cd 5g_coverage
```

### 2. Create a Virtual EnvironmentIt is highly recommended to use a virtual environment to isolate project dependencies.

Windows (PowerShell):
python -m venv .venv
.\.venv\Scripts\activate
macOS / Linux (Bash):
python3 -m venv .venv
source .venv/bin/activate

### 3. Install Dependencies

pip install -r requirements.txt

💻 Running the SimulatorYou can run the simulator either through the modern web API or directly via the CLI. Option A: Running via REST API (FastAPI)1. Generate the Constellation DataFirst, generate the satellite constellation configuration (e.g., the Walker Global constellation):

Bash
python generate_walker.py

Expected output: Successfully added 60-satellite 'walker_global' constellation to satellite_constellation.json!

2. Start the ServerLaunch the Uvicorn server to host the API: Bashpython -m uvicorn app:app --reload
   The server will start at http://127.0.0.1:8000. 3. Interact with the APIRun a Simulation: GET http://127.0.0.1:8000/api/run?constellation=walker_global Check Status: GET http://127.0.0.1:8000/api/status Fetch Data: GET http://127.0.0.1:8000/api/data Option B: Running via CLI (Standalone)If you just want to run a single physical simulation pass without the web server: Bashpython main_simulator.py
   This will generate output files in your project directory (e.g., ntn_coverage_cdf.png, ntn_coverage_analysis.csv). 🏗 Architecture & ModulesModulePurposeapp.pyFastAPI server and API endpoints main_simulator.pyCore orchestration pipeline rf_propagation.pyRF physics layer (Path loss, atmosphere, antenna) study_area.pyGeographic framework and grid generation link_budget.py3GPP link budget calculations generate_walker.pyConstellation payload generation ℹ️ Note: For deeper technical explanations of the physical models and formulas used, refer to TECHNICAL_README.md. ⚙️ ConfigurationTo customize the physical simulation parameters, edit the configuration block inside main_simulator.py: Python# Study area configuration
   STUDY_AREA_CONFIG = {
   "center_lat": 50.0, # Latitude (e.g., Prague)
   "center_lon": 15.0, # Longitude
   "width_km": 50, # Region width
   "height_km": 50, # Region height
   "resolution_m": 2500, # Distance between grid receivers
   }

# Satellite parameters

TX_POWER_DBM = 43.0 # 20 Watts
FREQUENCY_HZ = 2.1e9 # 2100 MHz (S-Band)
🧪 Running TestsThe project includes a comprehensive test suite covering the core physical algorithms. Bashpython -m pytest tests/ -v
(Tests cover RF propagation, path loss, atmospheric modeling, grid generation, distances, and angles)[cite: 1].🐛 TroubleshootingWindows Users: UnicodeEncodeError or UnicodeDecodeErrorIf your simulation crashes with a codec error while attempting to process or print the ASCII banner, it is due to the Windows terminal default cp1252 encoding[cite: 1].Fix: This has been patched by forcing utf-8 on process streams[cite: 1]. If you still experience issues, force the environment encoding in your terminal before running the server[cite: 1]:PowerShell$env:PYTHONIOENCODING="utf-8"
python -m uvicorn app:app --reload
OSError: [Errno 28] No space left on deviceIf the backend background engine fails during the final phase of the simulation, check your local drive storage space. The simulation data structures export large datasets; cleaning up previous ntn_coverage_analysis.csv files or clearing the system Recycle Bin will resolve the write restriction.📚 References3GPP TS 38.811 / TR 38.811: NR and NG-RAN Overall Description (NTN) & Use Cases[cite: 1]ITU-R P.618 / P.676: Propagation in line-of-sight systems & Atmospheric attenuation[cite: 1]Core Libraries: Skyfield (Orbital mechanics), FastAPI (REST API), NumPy, Pandas, Matplotlib[cite: 1].Author: Damian Stochla[cite: 1]Version: 1.1.0[cite: 1]License: Academic use - please cite this project if used in research or thesis work[cite: 1].
