# mappings.py
# Constants and mappings for the Air Quality Phase 1 ETL

# Map raw CSV columns to Canonical DB columns
CSV_COLUMN_MAPPING = {
    "Timestamp": "ts",
    "PM2.5 (µg/m³)": "pm25",
    "PM10 (µg/m³)": "pm10",
    "NO (µg/m³)": "no_ugm3",
    "NO2 (µg/m³)": "no2_ugm3",
    "NOx (ppb)": "nox_ppb",
    "NH3 (µg/m³)": "nh3_ugm3",
    "SO2 (µg/m³)": "so2_ugm3",
    "CO (mg/m³)": "co_mgm3",
    "Ozone (µg/m³)": "ozone_ugm3",
    "Benzene (µg/m³)": "benzene_ugm3",
    "Toluene (µg/m³)": "toluene_ugm3",
    "Xylene (µg/m³)": "xylene_ugm3",
    "O Xylene (µg/m³)": "o_xylene_ugm3",
    "Eth-Benzene (µg/m³)": "eth_benzene_ugm3",
    "MP-Xylene (µg/m³)": "mp_xylene_ugm3",
    "AT (°C)": "temp_c",
    "RH (%)": "rh_pct",
    "WS (m/s)": "ws_ms",
    "WD (deg)": "wd_deg",
    "RF (mm)": "rf_mm",
    "TOT-RF (mm)": "tot_rf_mm",
    "SR (W/mt2)": "sr_wm2",
    "BP (mmHg)": "bp_mmhg",
    "VWS (m/s)": "vws_ms",
}

# The expected columns for the CAAQMS DB Table (excluding internal keys)
CAAQMS_DB_COLUMNS = list(CSV_COLUMN_MAPPING.values())

# Sentinel values to be mapped to NULL (NaN)
SENTINEL_VALUES = {-999, -99, 999, 9999, -9999, 9, -9}

# Physical bounds for numeric variables
# Tuple: (min_valid, max_valid)
PHYSICAL_BOUNDS = {
    "rh_pct": (0, 100),
    "wd_deg": (0, 360),
    # Most pollutant concentrations shouldn't be materially negative.
    "pm25": (0, None),
    "pm10": (0, None),
    "no_ugm3": (0, None),
    "no2_ugm3": (0, None),
    "nox_ppb": (0, None),
    "nh3_ugm3": (0, None),
    "so2_ugm3": (0, None),
    "co_mgm3": (0, None),
    "ozone_ugm3": (0, None),
    "benzene_ugm3": (0, None),
    "toluene_ugm3": (0, None),
    "xylene_ugm3": (0, None),
    "o_xylene_ugm3": (0, None),
    "eth_benzene_ugm3": (0, None),
    "mp_xylene_ugm3": (0, None),
    "rf_mm": (0, None),
    "tot_rf_mm": (0, None),
    "ws_ms": (0, None),
    "sr_wm2": (0, None),
}

def clean_station_name(raw_name: str) -> tuple[str, str, str]:
    """
    Parses a raw folder name into canonical components.
    E.g., "Jahangirpuri, Delhi - DPCC\t"
    Returns: (Cleaned Name, City, Operator)
    """
    clean = raw_name.strip()
    # Typical format: Name, City - Operator
    # e.g., "ITO, Delhi - CPCB"

    city = "Delhi"
    operator = "Unknown"

    if ", " in clean:
        parts = clean.split(", ", 1)
        name_part = parts[0].strip()
        rest = parts[1]

        if " - " in rest:
            city_part, operator_part = rest.split(" - ", 1)
            city = city_part.strip()
            operator = operator_part.strip()
        else:
            name_part = clean

        return name_part, city, operator

    return clean, city, operator
