import json

# Base TLE to use as a template (Altitude ~540km, Inclination 53.2 degrees)
BASE_TLE1 = "1 52949U 22067A   26155.19792824 -.00001084  00000-0 -54657-4 0  9997"
BASE_TLE2 = "2 52949  53.2181 290.1345 0001323  97.1245 262.9992 15.08779434218846"

# Walker Constellation Parameters
TOTAL_PLANES = 6
SATS_PER_PLANE = 10
TOTAL_SATS = TOTAL_PLANES * SATS_PER_PLANE

def format_tle_angle(angle_deg):
    """Formats an angle to perfectly fit the strict TLE spacing"""
    angle_deg = angle_deg % 360.0
    return f"{angle_deg:8.4f}".rjust(8, ' ')

def generate_walker_constellation():
    satellites = []
    
    for plane in range(TOTAL_PLANES):
        # Calculate RAAN (Spacing planes evenly around the Earth's 360 degrees)
        raan = (plane * (360.0 / TOTAL_PLANES)) % 360.0
        
        for sat in range(SATS_PER_PLANE):
            # Calculate Mean Anomaly (Spacing satellites evenly within the plane)
            mean_anomaly = (sat * (360.0 / SATS_PER_PLANE) + (plane * 10.0)) % 360.0
            
            # Reconstruct TLE Line 2 with new RAAN and Mean Anomaly
            new_tle2 = BASE_TLE2[:17] + format_tle_angle(raan) + BASE_TLE2[25:43] + format_tle_angle(mean_anomaly) + BASE_TLE2[51:]
            
            satellites.append({
                "name": f"WALKER_P{plane+1}_S{sat+1}",
                "tle_line1": BASE_TLE1,
                "tle_line2": new_tle2
            })
            
    return satellites

# Load your existing JSON file
try:
    with open("satellite_constellation.json", "r") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {"constellations": {}}

# Add the massive new constellation
config["constellations"]["walker_global"] = {
    "description": f"Walker-Delta Constellation ({TOTAL_PLANES} planes, {SATS_PER_PLANE} sats/plane) for 24/7 Global Coverage",
    "satellites": generate_walker_constellation()
}

# Save it back to the file
with open("satellite_constellation.json", "w") as f:
    json.dump(config, f, indent=2)

print(f"Successfully added {TOTAL_SATS}-satellite 'walker_global' constellation to satellite_constellation.json!")
