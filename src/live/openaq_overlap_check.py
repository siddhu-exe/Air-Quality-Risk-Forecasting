"""Compare OpenAQ v3 against our own raw CAAQMS CSVs on hours where both exist.

Purpose (decision D3): before OpenAQ is used to backfill ``aq.live_readings`` it must be shown to
agree with the data the models were trained on: same numbers, same units, same hour labelling.
The reference is the raw CSVs in ``Og Data/`` (data.gov.in's API host is unreachable from the
development machine, so it cannot serve as the reference).

Findings that shaped the conversion (see the generated report):
  * OpenAQ unit labels are unreliable: NO2/SO2/CO are tagged "ppb" but already equal our
    ug/m3 / mg/m3 columns; NOx is tagged "ppb" but is numerically ppm (x1000).
  * OpenAQ stores 15-minute slots. The CSV value at hour T equals the MEAN of the four slots that
    START at T (temperature / humidity: start at T-15 min).
  * Old per-parameter sensor ids stopped years ago; the live sensor is the highest id.

Needs OPENAQ_API_KEY (header only, never printed). Run from the repo root:
    python -m src.live.openaq_overlap_check
Set FORCE_IPV4=1 on networks whose IPv6/NAT64 route hangs, OPENAQ_CACHE=<file> to reuse downloads.
Writes docs/TIER_3/openaq_overlap_check.{md,csv}; exits non-zero if the pass criteria fail.
"""
from __future__ import annotations

import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from dotenv import load_dotenv

from src.features.compute_cpcb_aqi import DEFAULT_RAW_DIR, _station_for_folder
from src.live.openaq import (
    LOCATIONS, SLOT_START_OFFSET_MIN, UNIT_FACTOR, fetch_15min, get, live_sensors, slots_to_hourly,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")
OUT_CSV = REPO_ROOT / "docs" / "TIER_3" / "openaq_overlap_check.csv"
OUT_MD = REPO_ROOT / "docs" / "TIER_3" / "openaq_overlap_check.md"

PARAM_TO_CSV = {
    "pm25": "PM2.5 (µg/m³)", "pm10": "PM10 (µg/m³)", "no2": "NO2 (µg/m³)", "so2": "SO2 (µg/m³)",
    "o3": "Ozone (µg/m³)", "co": "CO (mg/m³)", "nox": "NOx (ppb)",
    "temperature": "AT (°C)", "relativehumidity": "RH (%)", "wind_speed": "WS (m/s)",
}
# Windows both sources cover. 2026 CSVs end 2026-08-31; Dwarka-Sector 8 has no 2026 file, so its
# window is Dec 2025, when OpenAQ's slot labels sat 15 minutes earlier (its fit is at -15 min).
WINDOW_2026 = ("2026-08-24", "2026-08-31")
WINDOW_2025 = ("2025-12-01", "2025-12-08")
SCAN_MIN = list(range(-75, 76, 15))
EXACT_RTOL = 0.005
# Pass criteria for using OpenAQ as a stand-in for the training data (checked on 2026 stations).
MAX_POOLED_MAE_PCT = 5.0
MIN_STATION_CORR = 0.95


def load_csv(station: str, year: int) -> pd.DataFrame:
    for folder in sorted(os.listdir(DEFAULT_RAW_DIR)):
        if _station_for_folder(folder) == station:
            for path in (Path(DEFAULT_RAW_DIR) / folder / "Raw Data").glob(f"{year}_*_1H.csv"):
                return pd.read_csv(path, parse_dates=["Timestamp"]).set_index("Timestamp")
    raise FileNotFoundError(f"{station} {year}")


def compare(oaq: pd.Series, ref: pd.Series) -> dict:
    joined = pd.concat([oaq.rename("o"), ref.rename("c")], axis=1).dropna()
    if len(joined) < 20:
        return {"n": len(joined)}
    diff = (joined.o - joined.c).abs()
    return {
        "n": len(joined),
        "mae": float(diff.mean()),
        "mae_pct": float(100 * diff.mean() / max(joined.c.abs().mean(), 1e-9)),
        "exact_share": float((diff <= EXACT_RTOL * joined.c.abs().clip(lower=1e-6)).mean()),
        "corr": float(joined.o.corr(joined.c)),
        "slope_csv_per_oaq": float((joined.o @ joined.c) / max(joined.o @ joined.o, 1e-12)),
    }


def collect() -> tuple[dict, list]:
    cache = Path(os.environ["OPENAQ_CACHE"]) if os.environ.get("OPENAQ_CACHE") else None
    if cache and cache.exists():
        samples, freshness = pickle.loads(cache.read_bytes())
        print(f"loaded {len(samples)} cached samples from {cache}")
        return samples, freshness
    now = datetime.now(timezone.utc)
    samples, freshness = {}, []
    for station, location_id in LOCATIONS.items():
        window = WINDOW_2025 if station == "Dwarka-Sector 8" else WINDOW_2026
        csv = load_csv(station, int(window[0][:4])).loc[window[0]:window[1]]
        last = pd.Timestamp(get(f"/locations/{location_id}")["results"][0]["datetimeLast"]["utc"])
        freshness.append({"station": station, "openaq_last_utc": str(last),
                          "age_hours_at_check": round((now - last.to_pydatetime()).total_seconds() / 3600, 1)})
        for parameter, (sensor_id, _label) in live_sensors(location_id, station).items():
            if PARAM_TO_CSV[parameter] in csv:
                samples[(station, parameter)] = (fetch_15min(sensor_id, *window), csv[PARAM_TO_CSV[parameter]])
                print(f"fetched {station:16s} {parameter:17s} sensor {sensor_id}", flush=True)
    if cache:
        cache.write_bytes(pickle.dumps((samples, freshness)))
    return samples, freshness


def main() -> int:
    now = datetime.now(timezone.utc)
    samples, freshness = collect()

    # 1) scan the window start for every parameter (pooled over the six 2026 stations)
    scan = {}
    for parameter in PARAM_TO_CSV:
        keys = [k for k in samples if k[1] == parameter and k[0] != "Dwarka-Sector 8"]
        per_offset = {}
        for d in SCAN_MIN:
            stats = [compare(slots_to_hourly(samples[k][0], samples[k][1].index, d, UNIT_FACTOR.get(parameter, 1.0)), samples[k][1]) for k in keys]
            stats = [s for s in stats if s.get("n", 0) >= 20]
            if stats:
                w = [s["n"] for s in stats]
                per_offset[d] = float(np.average([s["mae_pct"] for s in stats], weights=w))
        if per_offset:
            scan[parameter] = per_offset

    # 2) final agreement with the chosen convention
    rows = []
    for (station, parameter), (raw, ref) in sorted(samples.items()):
        oaq = slots_to_hourly(raw, ref.index, SLOT_START_OFFSET_MIN.get(parameter, 0), UNIT_FACTOR.get(parameter, 1.0))
        raw_scale = compare(slots_to_hourly(raw, ref.index, SLOT_START_OFFSET_MIN.get(parameter, 0), 1.0), ref)
        rows.append({"station": station, "parameter": parameter, "csv_unit": PARAM_TO_CSV[parameter].split("(")[1][:-1],
                     "factor_applied": UNIT_FACTOR.get(parameter, 1.0), "raw_slope_csv_per_oaq": raw_scale.get("slope_csv_per_oaq"),
                     **compare(oaq, ref)})
    table = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)

    # 3) pooled verdict per parameter (2026 stations only; Dwarka is reported separately)
    verdict_rows, failures = [], []
    for parameter in PARAM_TO_CSV:
        g = table[(table.parameter == parameter) & (table.station != "Dwarka-Sector 8") & (table.n >= 20)]
        if g.empty:
            continue
        pooled_mae = float(np.average(g.mae_pct, weights=g.n))
        worst = g.loc[g["corr"].idxmin()]
        ok = pooled_mae <= MAX_POOLED_MAE_PCT and worst["corr"] >= MIN_STATION_CORR
        if not ok:
            failures.append(parameter)
        verdict_rows.append({"parameter": parameter, "stations": len(g), "pairs": int(g.n.sum()), "pooled_mae_pct": pooled_mae,
                             "worst_corr": float(worst["corr"]), "worst_station": worst.station, "ok": ok})
    verdict = pd.DataFrame(verdict_rows)
    dwarka = table[table.station == "Dwarka-Sector 8"]

    lines = [
        "# OpenAQ vs our raw CSVs: overlap check (decision D3)",
        "",
        f"Generated by `src/live/openaq_overlap_check.py` at {now:%Y-%m-%d %H:%M} UTC. Reference = raw CAAQMS CSVs in `Og Data/`.",
        f"Window {WINDOW_2026[0]}..{WINDOW_2026[1]} for six stations. Dwarka-Sector 8 has no 2026 CSV, so it was checked on",
        f"{WINDOW_2025[0]}..{WINDOW_2025[1]} only; the 2026 convention is therefore **unverified for Dwarka-Sector 8**.",
        "",
        "## Conversion that makes OpenAQ match the CSV",
        "",
        "- **Units:** use the numbers as they are for PM2.5, PM10, NO2, SO2, O3, CO, temperature, humidity and wind speed, ignoring OpenAQ's unit label",
        "  (NO2, SO2 and CO are tagged ppb but already equal our ug/m3 and mg/m3). NOx is tagged ppb but is ppm: multiply by 1000.",
        "- **Hour label:** the CSV value at hour T is the mean of the four 15-minute slots starting at T (temperature and humidity: starting at T-15 min).",
        "- **Sensors:** use the highest sensor id per parameter; the old ids stopped in 2018.",
        "",
        "## Window-start scan: mean absolute error % by offset (six 2026 stations pooled)",
        "",
        "| Parameter | " + " | ".join(f"{d:+d}" for d in SCAN_MIN) + " | Chosen |",
        "| :--- | " + " | ".join("---:" for _ in SCAN_MIN) + " | ---: |",
        *[f"| {p} | " + " | ".join(f"{scan[p][d]:.2f}" if d in scan[p] else "" for d in SCAN_MIN) + f" | {SLOT_START_OFFSET_MIN.get(p, 0):+d} |"
          for p in scan],
        "",
        "## Agreement with the chosen convention",
        "",
        f"Pass = pooled mean absolute error <= {MAX_POOLED_MAE_PCT:g}% and every station's correlation >= {MIN_STATION_CORR}.",
        "",
        "| Parameter | CSV unit | Stations | Pairs | Pooled MAE % | Worst station correlation | Verdict |",
        "| :--- | :--- | ---: | ---: | ---: | :--- | :---: |",
        *[f"| {r.parameter} | {PARAM_TO_CSV[r.parameter].split('(')[1][:-1]} | {r.stations} | {r.pairs} | {r.pooled_mae_pct:.2f} | {r.worst_corr:.3f} ({r.worst_station}) | {'pass' if r.ok else '**FAIL**'} |"
          for r in verdict.itertuples()],
        "",
        "Not available from OpenAQ: solar radiation (all stations); temperature, humidity and wind speed at ITO.",
        "",
        "## Dwarka-Sector 8 (Dec 2025 window, fits one 15-minute step earlier than 2026)",
        "",
        "| Parameter | Pairs | MAE % (2026 offsets applied to Dec 2025 data) | Correlation |",
        "| :--- | ---: | ---: | ---: |",
        *[f"| {r.parameter} | {int(r.n)} | {r.mae_pct:.2f} | {r.corr:.3f} |" for r in dwarka.itertuples() if r.n >= 20],
        "",
        "## Freshness of OpenAQ at check time",
        "",
        "| Station | Newest OpenAQ value (UTC) | Age (hours) |", "| :--- | :--- | ---: |",
        *[f"| {f['station']} | {f['openaq_last_utc']} | {f['age_hours_at_check']} |" for f in freshness],
        "",
        "Per-station detail: `openaq_overlap_check.csv`.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_MD}\nfailing parameters: {failures or 'none'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
