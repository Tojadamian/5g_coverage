from dataclasses import dataclass
import json
import time
import requests


@dataclass(frozen=True)
class SatelliteSitePayload:
    site_name: str
    longitude: float
    latitude: float
    altitude_msl_m: float
    antenna_model: str = "3GPP_TR_38.811_PhasedArray"
    frequency_mhz: float = 2100.0
    tx_power_dbm: float = 43.0

    def to_dict(self):
        return {
            "site_name": self.site_name,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "altitude_msl_m": self.altitude_msl_m,
            "antenna_model": self.antenna_model,
            "frequency_mhz": self.frequency_mhz,
            "tx_power_dbm": self.tx_power_dbm,
        }


class HTZPayloadEngine:
    def __init__(self, base_url="http://localhost:8080/api/v1"):
        """Initializes connection parameters for the ATDI HTZ instance."""
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _reliable_post(self, endpoint, payload_dict, req_timeout, max_retries=4):
        """
        Internal method: Sends data to HTZ with exponential backoff if the server is busy.
        Prevents simulation crashes during heavy 3D matrix computations.
        """
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    endpoint,
                    data=json.dumps(payload_dict),
                    headers=self.headers,
                    timeout=req_timeout,
                )
                response.raise_for_status() # Throws HTTPError for bad responses (4xx or 5xx)
                return response
            except requests.exceptions.RequestException as exc:
                wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s, 8s
                print(f"[API WARNING] HTZ Server hiccup: {exc}.")
                print(f" -> Retrying in {wait_time}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
        
        print("[API CRITICAL] HTZ Engine failed to respond after maximum retries.")
        return None

    def build_satellite_payload(self, site_name, longitude, latitude, altitude_km):
        """Builds the HTZ JSON payload for a satellite-fed vector site."""
        return SatelliteSitePayload(
            site_name=site_name,
            longitude=longitude,
            latitude=latitude,
            altitude_msl_m=altitude_km * 1000,
        )

    def push_satellite_position(self, payload):
        """Sends satellite coordinates to create or update a mobile vector station in HTZ."""
        endpoint = f"{self.base_url}/vectorsite"
        payload_dict = payload.to_dict() if hasattr(payload, "to_dict") else payload
        
        response = self._reliable_post(endpoint, payload_dict, req_timeout=10)
        
        if response and response.status_code in [200, 201]:
            print(f"[HTZ SUCCESS] Updated position for {payload_dict['site_name']} on engine map.")
            return True

        print(f"[HTZ ERROR] Server rejected station creation or failed entirely.")
        return False

    def trigger_coverage_calculation(self, site_name, clear_matrix=True):
        """Tells HTZ to execute the deterministic RF ray-tracing or ITU matrix computation."""
        endpoint = f"{self.base_url}/coverage/calculate"
        calculation_config = {
            "target_site": site_name,
            "propagation_model": "ITU-R_P.618-13",
            "clear_previous": clear_matrix,
            "resolution_meter": 30,
        }
        
        response = self._reliable_post(endpoint, calculation_config, req_timeout=30)
        
        if response and response.status_code == 200:
            print(f"[HTZ SUCCESS] Matrix coverage calculation complete for {site_name}.")
            return response.json()
            
        print("[HTZ ERROR] Coverage calculation failed.")
        return None