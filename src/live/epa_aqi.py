"""US-EPA per-pollutant AQI conversion, as WAQI (aqicn.org) publishes it in ``iaqi``, and its inverse.

WAQI's ``iaqi`` carries an integer US-EPA sub-index per pollutant, not a concentration. To use it as a station reading we
convert back: concentration -> AQI (rounded to an integer, capped at 500) -> concentration. This module is the pure maths;
it knows nothing about WAQI's HTTP API.

Scale. WAQI interpolates continuously through knots (it does not step per EPA band). The PM2.5 knots below are the ones
printed on https://aqicn.org/calculator/ (0, 12, 35.5, 55.5, 150.5, 250.5, 350.5, 500.5 -> AQI 0, 50, 100, 150, 200, 300,
400, 500) and reproduce its published conversion table (e.g. 35 -> 99, 60 -> 152, 80 -> 163, 100 -> 173); the tests pin that.
This is the 2012 EPA PM2.5 scale, not the 2024 revision. The PM10/NO2/SO2/CO/O3 knots follow the same construction (the upper
edge of each EPA band, plus one unit of the band resolution) from the EPA Technical Assistance Document, EPA-454/B-18-007,
Table 5; they are NOT checked against WAQI output yet (TODO: compare with live ``iaqi`` once the token is in place).
O3 uses the 8-hour table up to AQI 300 and the 1-hour table above it (an approximation, only reached above 0.2 ppm).

Units. Our stored concentrations are ug/m3 (CO in mg/m3). EPA works in ppb/ppm at 25 C and 1 atm (molar volume 24.45 L/mol).
TODO: confirm which reference temperature WAQI uses for Indian stations; at 25 C the conversion is the EPA one.
"""

from __future__ import annotations

import numpy as np

AQI_KNOTS = np.array([0, 50, 100, 150, 200, 300, 400, 500], dtype=float)
MOLAR_VOLUME_L = 24.45  # 25 C, 1 atm
MOLAR_MASS = {"no2": 46.0055, "so2": 64.066, "o3": 47.998, "co": 28.01}

# concentration knots in the EPA unit of each pollutant
CONC_KNOTS = {
    "pm25": [0, 12, 35.5, 55.5, 150.5, 250.5, 350.5, 500.5],  # ug/m3
    "pm10": [0, 55, 155, 255, 355, 425, 505, 605],  # ug/m3
    "no2": [0, 54, 101, 361, 650, 1250, 1650, 2050],  # ppb
    "so2": [0, 36, 76, 186, 305, 605, 805, 1005],  # ppb
    "co": [0, 4.5, 9.5, 12.5, 15.5, 30.5, 40.5, 50.5],  # ppm
    "o3": [0, 0.055, 0.071, 0.086, 0.106, 0.201, 0.505, 0.605],  # ppm
}
POLLUTANTS = tuple(CONC_KNOTS)
# our stored unit -> EPA unit: multiply by this
_TO_EPA = {
    "pm25": 1.0,
    "pm10": 1.0,
    "no2": MOLAR_VOLUME_L / MOLAR_MASS["no2"],  # ug/m3 -> ppb
    "so2": MOLAR_VOLUME_L / MOLAR_MASS["so2"],  # ug/m3 -> ppb
    "co": MOLAR_VOLUME_L / MOLAR_MASS["co"],  # mg/m3 -> ppm
    "o3": MOLAR_VOLUME_L / MOLAR_MASS["o3"] / 1000.0,  # ug/m3 -> ppm
}
AQI_MAX = 500


def to_aqi(pollutant: str, concentration) -> np.ndarray:
    """Concentration in our stored unit -> integer US-EPA AQI (NaN stays NaN), rounded half up, capped at 500."""
    values = np.asarray(concentration, dtype=float) * _TO_EPA[pollutant]
    index = np.interp(values, CONC_KNOTS[pollutant], AQI_KNOTS, left=0.0, right=float(AQI_MAX))
    out = np.minimum(np.floor(index + 0.5), AQI_MAX)
    out[np.isnan(values)] = np.nan
    return out


def from_aqi(pollutant: str, aqi) -> np.ndarray:
    """Integer US-EPA AQI -> concentration in our stored unit (the knot-linear inverse; NaN stays NaN)."""
    values = np.minimum(np.asarray(aqi, dtype=float), AQI_MAX)
    conc = np.interp(values, AQI_KNOTS, CONC_KNOTS[pollutant])
    conc = conc / _TO_EPA[pollutant]
    conc[np.isnan(values)] = np.nan
    return conc


def roundtrip(pollutant: str, concentration) -> np.ndarray:
    """What a consumer of WAQI's integer ``iaqi`` recovers from a true concentration."""
    return from_aqi(pollutant, to_aqi(pollutant, concentration))
