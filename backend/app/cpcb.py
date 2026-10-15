"""CPCB AQI categories and the GRAP stages the API reports.

GRAP stage bands follow the CAQM scheme (Stage I Poor, II Very Poor, III Severe, IV Severe+).
TODO(verify): the bands against the current CAQM GRAP order before any public launch; the API labels them "indicative, not an official advisory".
"""

from __future__ import annotations

CATEGORIES = [(50, "Good"), (100, "Satisfactory"), (200, "Moderate"), (300, "Poor"), (400, "Very Poor")]
TOP_CATEGORY = "Severe"
SEVERE_AQI = 401

#: (stage, label, lowest AQI, highest AQI or None for open-ended)
GRAP_STAGES: list[tuple[str, str, int, int | None]] = [
    ("I", "Poor", 201, 300),
    ("II", "Very Poor", 301, 400),
    ("III", "Severe", 401, 450),
    ("IV", "Severe+", 451, None),
]

UNITS = {"pm25": "µg/m³", "pm10": "µg/m³", "no2": "µg/m³", "so2": "µg/m³", "nh3": "µg/m³", "o3": "µg/m³", "co": "mg/m³"}
POLLUTANT_KEYS = ["pm25", "pm10", "no2", "co", "o3", "so2"]


def category(aqi: float) -> str:
    for upper, name in CATEGORIES:
        if aqi <= upper:
            return name
    return TOP_CATEGORY


def grap_stage(aqi: float) -> str | None:
    """Indicative GRAP stage for an AQI value, or None below Stage I."""
    value = int(aqi)  # AQI is reported as a whole number
    for stage, _, low, high in GRAP_STAGES:
        if value >= low and (high is None or value <= high):
            return stage
    return None
