import os
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

# --- Initialization ---
app = FastAPI(title="VayuRisk AI API", version="1.0.0")

# Enable CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict this in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base path relative to this file's location (assuming backend/ is in root)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# --- In-Memory Data Cache ---
# We load the data once when the server starts to keep API responses fast.
data_cache = {}

@app.on_event("startup")
async def load_data():
    """Load all necessary Parquet and CSV files into memory on startup."""
    print("Loading data into memory...")
    try:
        # Forecasts
        data_cache['1h'] = pd.read_parquet(os.path.join(REPORTS_DIR, "classification", "1h", "classified_predictions.parquet"))
        data_cache['6h'] = pd.read_parquet(os.path.join(REPORTS_DIR, "classification", "6h", "classified_predictions.parquet"))
        data_cache['24h'] = pd.read_parquet(os.path.join(REPORTS_DIR, "classification", "24h", "classified_predictions.parquet"))

        # Causal Impact (Diwali)
        data_cache['diwali_hourly'] = pd.read_csv(os.path.join(REPORTS_DIR, "causal", "diwali_hourly_timeseries.csv"))

        # Thresholds
        data_cache['threshold_sweep'] = pd.read_csv(os.path.join(REPORTS_DIR, "classification", "metrics", "cost_threshold_sweep_24h.csv"))
        data_cache['operating_points'] = pd.read_csv(os.path.join(REPORTS_DIR, "classification", "metrics", "threshold_operating_points_comparison.csv"))

        # Episodes
        data_cache['episodes'] = pd.read_csv(os.path.join(REPORTS_DIR, "classification", "episodes", "grap_episode_lead_times.csv"))
        print("Data loaded successfully!")
    except Exception as e:
        print(f"Error loading data: {e}")

# --- API Endpoints ---

@app.get("/api/stations")
async def get_stations():
    """Return a list of all unique monitoring stations."""
    if '1h' not in data_cache:
        raise HTTPException(status_code=503, detail="Data not available")

    # Get unique stations from 1h data
    df = data_cache['1h']
    stations = df['station_name'].unique().tolist()

    # Format to match frontend mock shape
    return [
        {"id": stat, "name": stat, "status": "LIVE"}
        for stat in sorted(stations)
    ]

@app.get("/api/forecasts")
async def get_forecasts(horizon: str = Query("1h", regex="^(1h|6h|24h)$"), station: Optional[str] = "ALL"):
    """
    Get multi-step forecasts for a specific horizon (1h, 6h, or 24h).
    """
    if horizon not in data_cache:
        raise HTTPException(status_code=503, detail="Data not available")

    df = data_cache[horizon]

    # Filter by station if provided and not "ALL"
    if station and station != "ALL":
        df = df[df['station_name'] == station]

    # We’ll return a subset of the most recent ~100 records for the frontend chart to keep payload size small
    # Ensure it's sorted by timestamp, then take the last N rows per station or overall
    df_sorted = df.sort_values(by="timestamp")

    # Basic pagination/clipping for frontend performance
    records = df_sorted.tail(500).to_dict(orient="records")
    return records

@app.get("/api/causal/diwali")
async def get_diwali_causal():
    """Return the Diwali timeseries data."""
    if 'diwali_hourly' not in data_cache:
        raise HTTPException(status_code=503, detail="Data not available")

    return data_cache['diwali_hourly'].to_dict(orient="records")

@app.get("/api/thresholds/sweep")
async def get_threshold_sweep():
    """Return the cost-sensitive threshold parameter sweep dataset."""
    if 'threshold_sweep' not in data_cache:
        raise HTTPException(status_code=503, detail="Data not available")

    return data_cache['threshold_sweep'].to_dict(orient="records")

@app.get("/api/thresholds/operating-points")
async def get_operating_points():
    """Return the confusion matrix metrics and cost comparisons at different thresholds."""
    if 'operating_points' not in data_cache:
        raise HTTPException(status_code=503, detail="Data not available")

    return data_cache['operating_points'].to_dict(orient="records")

@app.get("/api/episodes")
async def get_episodes():
    """Return GRAP episode lead times."""
    if 'episodes' not in data_cache:
        raise HTTPException(status_code=503, detail="Data not available")

    return data_cache['episodes'].to_dict(orient="records")

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "data_loaded": "1h" in data_cache}
