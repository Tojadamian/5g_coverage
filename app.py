from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import subprocess
import os
import logging

# Set up logging instead of print()
logging.basicConfig(level=logging.INFO)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global state to track what the background engine is doing
sim_state = {"status": "idle", "message": "Ready."}

def execute_physics_engine(constellation: str):
    """Runs the heavy math in the background so the server doesn't freeze."""
    global sim_state
    sim_state["status"] = "running"
    sim_state["message"] = f"Simulating {constellation}... (Crunching millions of link budgets)"
    logging.info(f"Started background job for {constellation}")
    
    try:
        subprocess.run(
            ["python", "main_simulator.py", "--constellation", constellation],
            check=True, 
            capture_output=True, 
            text=True
        )
        sim_state["status"] = "success"
        sim_state["message"] = f"Simulation Complete for {constellation}!"
        logging.info("Background job finished successfully.")
    except subprocess.CalledProcessError as e:
        sim_state["status"] = "error"
        sim_state["message"] = "Simulation failed. Check terminal logs."
        logging.error(f"Engine failed: {e.stderr}")

@app.get("/")
def serve_dashboard():
    return FileResponse("static/index.html")

@app.get("/api/run")
def run_simulation(constellation: str, background_tasks: BackgroundTasks):
    """Instantly returns a success message while handing the work to a background thread."""
    global sim_state
    
    # Prevent clicking the button twice and running two simulations at once
    if sim_state["status"] == "running":
        return {"status": "error", "message": "Engine is already running!"}
    
    # Hand the heavy lifting to the background
    background_tasks.add_task(execute_physics_engine, constellation)
    return {"status": "started", "message": "Job sent to background."}

@app.get("/api/status")
def get_status():
    """The browser calls this every 2 seconds to see if the math is done."""
    return sim_state

@app.get("/api/data")
def get_timeline_data():
    file_path = "ntn_orbital_timeline.csv"
    if not os.path.exists(file_path):
        return {"error": "No data found."}
    
    df = pd.read_csv(file_path)
    return {"timeline": df.to_dict(orient="records")}