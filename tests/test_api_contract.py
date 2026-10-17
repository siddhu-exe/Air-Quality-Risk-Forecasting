"""API <-> frontend contract: every endpoint's JSON is pinned in frontend/src/api/contract/ and the frontend's
zod schemas parse those same files (frontend/src/api/contract.test.ts), so a key the API spells differently from the
schema fails one of the two suites.

After an intentional change to a response shape, regenerate the files:  UPDATE_API_CONTRACT=1 pytest tests/test_api_contract.py
"""

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from tests.test_backend_api import client  # noqa: E402

CONTRACT_DIR = Path(__file__).resolve().parents[1] / "frontend" / "src" / "api" / "contract"
ENDPOINTS = {
    "health": "/api/v1/health",
    "overview": "/api/v1/overview",
    "stations": "/api/v1/stations",
    "station_forecast_aqi": "/api/v1/stations/3/forecast?target=aqi",
    "station_forecast_pm25": "/api/v1/stations/3/forecast?target=pm25",
    "grap_alerts": "/api/v1/alerts/grap",
    "model_health": "/api/v1/model-health",
    "backtest": "/api/v1/backtest",
}


@pytest.mark.parametrize("name", ENDPOINTS)
def test_endpoint_json_matches_the_pinned_contract_file(name):
    response = client().get(ENDPOINTS[name])
    assert response.status_code == 200
    body = response.json()
    path = CONTRACT_DIR / f"{name}.json"
    if os.environ.get("UPDATE_API_CONTRACT"):
        path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n")
    assert path.exists(), f"{path.name} missing: run with UPDATE_API_CONTRACT=1"
    assert body == json.loads(path.read_text()), f"{name}: the API response changed; regenerate the contract files"
