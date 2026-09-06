#!/usr/bin/env python3
"""
Phase 1 — Raw Data Profiler
============================
Scans all Delhi raw data (CSV + XLSX) under Og Data/Delhi data/
without modifying any source file.

Outputs (all written to the same directory as this script):
  file_inventory.csv
  schema_report.csv
  station_report.csv
  timestamp_report.csv
  missingness_report.csv
  duplicate_report.csv
  numeric_quality_report.csv
  schema_differences.csv
  profiling_summary.md

Run:
  python3 profiling/profile_raw_data.py
"""

import os
import sys
import re
import csv
import json
import traceback
from pathlib import Path
from collections import defaultdict, Counter

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_ROOT = PROJECT_ROOT / "Og Data" / "Delhi data"
OUT_DIR = SCRIPT_DIR

# Sentinel values that often represent "missing" in government data
SENTINEL_VALUES = {-999, -9999, 999, 9999, -99, 99, -9, 9}

# Known pollutant / weather column keyword map (lowercase keyword -> semantic role)
SEMANTIC_MAP = {
    "timestamp": "timestamp",
    "date": "timestamp",
    "time": "timestamp",
    "pm2.5": "PM2.5",
    "pm10": "PM10",
    "no2": "NO2",
    "nox": "NOx",
    " no ": "NO",       # avoid matching NOx / NO2
    "nh3": "NH3",
    "so2": "SO2",
    "ozone": "O3",
    "o3": "O3",
    "co ": "CO",        # trailing space avoids matching 'ozone', 'nox' etc.
    "benzene": "Benzene",
    "toluene": "Toluene",
    "xylene": "Xylene",
    "eth-benzene": "Eth-Benzene",
    "mp-xylene": "MP-Xylene",
    "o xylene": "O-Xylene",
    "at (": "Temp_C",
    "rh (": "RH_pct",
    " ws ": "WindSpeed",
    " wd ": "WindDir",
    " rf ": "Rainfall",
    "tot-rf": "TotalRainfall",
    " sr ": "SolarRad",
    " bp ": "BaroPressure",
    "vws": "VWS",
    "station": "station_id",
    "city": "city",
    "aqi": "AQI",
}


def infer_semantic_role(col_name: str) -> str:
    cn = f" {col_name.lower()} "
    for kw, role in SEMANTIC_MAP.items():
        if kw in cn:
            return role
    return "unknown"


def infer_dtype_label(series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_integer_dtype(series):
        return "int"
    return "object/string"


def safe_sample(series: pd.Series, n: int = 3) -> str:
    vals = series.dropna().head(n).tolist()
    return " | ".join(str(v) for v in vals)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------
def discover_files(root: Path) -> list[dict]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".csv", ".xlsx", ".xls"):
            # Derive station folder name (2 levels up from file)
            parts = path.relative_to(root).parts  # e.g. (station, subfolder, filename)
            station_folder = parts[0] if len(parts) >= 1 else ""
            data_type = parts[1] if len(parts) >= 2 else ""
            files.append(
                {
                    "station_folder": station_folder,
                    "data_type": data_type,
                    "file_path": str(path),
                    "filename": path.name,
                    "extension": path.suffix.lower(),
                    "file_size_bytes": path.stat().st_size,
                }
            )
    return files


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------
def read_csv_file(path: Path) -> tuple[pd.DataFrame | None, str | None]:
    try:
        df = pd.read_csv(path, na_values=["NA", "na", "N/A", "n/a", "--", ""],
                         keep_default_na=True, low_memory=False)
        return df, None
    except Exception as e:
        return None, str(e)


def read_xlsx_file(path: Path) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Returns {sheet_name: df} and {sheet_name: error}."""
    frames, errors = {}, {}
    try:
        xl = pd.ExcelFile(path, engine="openpyxl")
        for sheet in xl.sheet_names:
            try:
                df = xl.parse(sheet, na_values=["NA", "na", "N/A", "n/a", "--", ""],
                               keep_default_na=True)
                frames[sheet] = df
            except Exception as e:
                errors[sheet] = str(e)
    except Exception as e:
        errors["__file__"] = str(e)
    return frames, errors


# ---------------------------------------------------------------------------
# Per-dataframe analysis helpers
# ---------------------------------------------------------------------------
def detect_timestamp_col(df: pd.DataFrame) -> str | None:
    candidates = [c for c in df.columns if "timestamp" in c.lower() or "date" in c.lower() or "time" in c.lower()]
    return candidates[0] if candidates else None


def parse_timestamps(series: pd.Series) -> pd.Series:
    try:
        return pd.to_datetime(series, infer_datetime_format=True, errors="coerce")
    except Exception:
        return pd.Series(pd.NaT, index=series.index)


def gap_analysis(ts: pd.Series, expected_freq_hours: float = 1.0) -> dict:
    ts_sorted = ts.dropna().sort_values().reset_index(drop=True)
    if len(ts_sorted) < 2:
        return {"gap_count": 0, "max_gap_hours": None, "min_gap_hours": None}
    deltas = ts_sorted.diff().dropna().dt.total_seconds() / 3600
    expected = expected_freq_hours
    gaps = deltas[deltas > expected * 1.5]
    return {
        "gap_count": int(len(gaps)),
        "max_gap_hours": float(round(deltas.max(), 2)) if len(deltas) else None,
        "min_gap_hours": float(round(deltas[deltas > 0].min(), 2)) if len(deltas[deltas > 0]) else None,
        "median_interval_hours": float(round(deltas.median(), 4)) if len(deltas) else None,
    }


def numeric_stats(series: pd.Series) -> dict:
    s = pd.to_numeric(series, errors="coerce")
    n_total = len(s)
    n_valid = s.count()
    if n_valid == 0:
        return {k: None for k in ["min", "max", "mean", "median", "n_zeros",
                                   "n_negative", "n_sentinel", "pct_missing"]}
    sentinels = int(s.isin(SENTINEL_VALUES).sum())
    return {
        "min": float(round(s.min(), 4)),
        "max": float(round(s.max(), 4)),
        "mean": float(round(s.mean(), 4)),
        "median": float(round(s.median(), 4)),
        "n_zeros": int((s == 0).sum()),
        "n_negative": int((s < 0).sum()),
        "n_sentinel": sentinels,
        "pct_missing": float(round((n_total - n_valid) / n_total * 100, 2)),
    }


# ---------------------------------------------------------------------------
# Main profiler
# ---------------------------------------------------------------------------
def profile_all() -> None:
    print(f"\n{'='*60}")
    print("  Air Quality Raw Data Profiler — Phase 1")
    print(f"  Data root : {DATA_ROOT}")
    print(f"  Output dir: {OUT_DIR}")
    print(f"{'='*60}\n")

    files_meta = discover_files(DATA_ROOT)
    print(f"Discovered {len(files_meta)} files.\n")

    # -------------------------------------------------------------------
    # Containers for all reports
    # -------------------------------------------------------------------
    inv_rows = []          # file_inventory
    schema_rows = []       # schema_report (one row per column per file)
    ts_rows = []           # timestamp_report
    miss_rows = []         # missingness_report
    dup_rows = []          # duplicate_report
    num_rows = []          # numeric_quality_report

    # For cross-file comparison
    file_column_sets: dict[str, set] = {}   # file_key -> set of column names
    station_presence: dict[str, dict] = defaultdict(dict)   # station -> {file_key: bool}

    summary_stats = {
        "total_files": 0,
        "total_csv": 0,
        "total_xlsx": 0,
        "read_errors": 0,
        "total_rows": 0,
        "ts_min": None,
        "ts_max": None,
        "stations": set(),
    }

    # -------------------------------------------------------------------
    for fmeta in files_meta:
        fpath = Path(fmeta["file_path"])
        ext = fmeta["extension"]
        station_folder = fmeta["station_folder"].strip()  # strip trailing tab etc.
        data_type = fmeta["data_type"]
        file_key = str(fpath.relative_to(DATA_ROOT))
        summary_stats["total_files"] += 1

        print(f"  → {file_key}")

        # ---- read ---------------------------------------------------
        if ext == ".csv":
            summary_stats["total_csv"] += 1
            df_map_raw = {}
            error_map = {}
            df, err = read_csv_file(fpath)
            if err:
                error_map["sheet1"] = err
                summary_stats["read_errors"] += 1
            else:
                df_map_raw["sheet1"] = df
            n_sheets = 1
        else:
            summary_stats["total_xlsx"] += 1
            df_map_raw, error_map = read_xlsx_file(fpath)
            n_sheets = len(df_map_raw) + len(error_map)

        # ---- inventory row ------------------------------------------
        total_rows_this_file = sum(len(d) for d in df_map_raw.values())
        total_cols_this_file = max((len(d.columns) for d in df_map_raw.values()), default=0)
        inv_rows.append(
            {
                "file_key": file_key,
                "station_folder": station_folder,
                "data_type": data_type,
                "filename": fmeta["filename"],
                "extension": ext,
                "file_size_bytes": fmeta["file_size_bytes"],
                "n_sheets": n_sheets,
                "n_rows": total_rows_this_file,
                "n_cols": total_cols_this_file,
                "read_error": "; ".join(error_map.values()) if error_map else "",
            }
        )
        summary_stats["total_rows"] += total_rows_this_file
        summary_stats["stations"].add(station_folder)

        # ---- per-sheet analysis -------------------------------------
        for sheet_name, df in df_map_raw.items():
            sheet_key = f"{file_key}::{sheet_name}"
            cols = list(df.columns)
            file_column_sets[sheet_key] = set(cols)

            ts_col = detect_timestamp_col(df)
            ts_parsed = None

            # ------ timestamp analysis ------
            ts_info = {
                "file_key": file_key,
                "sheet": sheet_name,
                "station_folder": station_folder,
                "ts_col_name": ts_col,
                "ts_format_sample": None,
                "ts_min": None,
                "ts_max": None,
                "n_rows": len(df),
                "n_ts_parsed": 0,
                "n_ts_null": 0,
                "n_ts_duplicates": 0,
                "apparent_freq_hours": None,
                "gap_count": 0,
                "max_gap_hours": None,
                "min_gap_hours": None,
                "median_interval_hours": None,
                "tz_info": "none detected",
            }
            if ts_col:
                ts_parsed = parse_timestamps(df[ts_col])
                n_ok = ts_parsed.notna().sum()
                n_null = ts_parsed.isna().sum()
                ts_info["n_ts_parsed"] = int(n_ok)
                ts_info["n_ts_null"] = int(n_null)
                if n_ok:
                    ts_info["ts_min"] = str(ts_parsed.min())
                    ts_info["ts_max"] = str(ts_parsed.max())
                    # sample format from raw string
                    raw_sample = str(df[ts_col].dropna().iloc[0]) if len(df[ts_col].dropna()) else ""
                    ts_info["ts_format_sample"] = raw_sample
                    # duplicates
                    ts_info["n_ts_duplicates"] = int(ts_parsed.dropna().duplicated().sum())
                    # gap analysis
                    ga = gap_analysis(ts_parsed)
                    ts_info.update(ga)
                    ts_info["apparent_freq_hours"] = ga.get("median_interval_hours")
                    # global range
                    t_min = ts_parsed.min()
                    t_max = ts_parsed.max()
                    if summary_stats["ts_min"] is None or t_min < summary_stats["ts_min"]:
                        summary_stats["ts_min"] = t_min
                    if summary_stats["ts_max"] is None or t_max > summary_stats["ts_max"]:
                        summary_stats["ts_max"] = t_max
            ts_rows.append(ts_info)

            # ------ schema + missingness ----------------------------
            col_names = list(df.columns)
            for col in col_names:
                series = df[col]
                n_total = len(series)
                n_missing = int(series.isna().sum())
                pct_missing = round(n_missing / n_total * 100, 2) if n_total else 0
                role = infer_semantic_role(col)
                dtype_label = infer_dtype_label(series)
                sample = safe_sample(series)

                schema_rows.append(
                    {
                        "file_key": file_key,
                        "sheet": sheet_name,
                        "station_folder": station_folder,
                        "data_type": data_type,
                        "col_name": col,
                        "inferred_dtype": dtype_label,
                        "semantic_role": role,
                        "sample_values": sample,
                        "n_total": n_total,
                        "n_missing": n_missing,
                        "pct_missing": pct_missing,
                        "completely_empty": (n_missing == n_total),
                    }
                )

                miss_rows.append(
                    {
                        "file_key": file_key,
                        "sheet": sheet_name,
                        "station_folder": station_folder,
                        "col_name": col,
                        "n_total": n_total,
                        "n_missing": n_missing,
                        "pct_missing": pct_missing,
                        "completely_empty": (n_missing == n_total),
                    }
                )

                # numeric stats for non-timestamp columns
                if role not in ("timestamp", "station_id", "city", "unknown") and role != "unknown":
                    ns = numeric_stats(series)
                    num_rows.append(
                        {
                            "file_key": file_key,
                            "sheet": sheet_name,
                            "station_folder": station_folder,
                            "col_name": col,
                            "semantic_role": role,
                            **ns,
                        }
                    )

            # ------ duplicates ----------------------------------------
            n_full_dups = int(df.duplicated().sum())
            if ts_col and ts_parsed is not None:
                ts_dups = int(ts_parsed.dropna().duplicated().sum())
            else:
                ts_dups = 0

            dup_rows.append(
                {
                    "file_key": file_key,
                    "sheet": sheet_name,
                    "station_folder": station_folder,
                    "n_rows": len(df),
                    "n_full_duplicate_rows": n_full_dups,
                    "n_timestamp_duplicates": ts_dups,
                    "note": "cross-file overlap checked separately below",
                }
            )

        # station presence tracking
        station_presence[station_folder][file_key] = True

    # -------------------------------------------------------------------
    # Schema differences (cross-file)
    # -------------------------------------------------------------------
    diff_rows = []
    sheet_keys = list(file_column_sets.keys())
    # group by station folder to detect within-station drift
    by_station: dict[str, list] = defaultdict(list)
    for sk in sheet_keys:
        # extract station from file_key (first path component)
        station = sk.split("/")[0].strip()
        by_station[station].append(sk)

    all_col_union = set()
    for cols in file_column_sets.values():
        all_col_union |= cols

    # Compare every file's column set against the union
    reference_cols = None
    reference_key = None
    for sk, cols in file_column_sets.items():
        if reference_cols is None:
            reference_cols = cols
            reference_key = sk
            continue
        added = cols - reference_cols
        removed = reference_cols - cols
        if added or removed:
            diff_rows.append(
                {
                    "reference_file": reference_key,
                    "compared_file": sk,
                    "columns_added_vs_reference": "; ".join(sorted(added)),
                    "columns_removed_vs_reference": "; ".join(sorted(removed)),
                }
            )

    # -------------------------------------------------------------------
    # Station report
    # -------------------------------------------------------------------
    station_rows = []
    # Collect unique station names seen (from inventory)
    station_name_raw = sorted({r["station_folder"] for r in inv_rows})
    # Count files per station
    file_counts = Counter(r["station_folder"] for r in inv_rows)
    ts_by_station: dict[str, dict] = defaultdict(lambda: {"ts_min": None, "ts_max": None})
    for t in ts_rows:
        st = t["station_folder"]
        if t["ts_min"] and (ts_by_station[st]["ts_min"] is None or t["ts_min"] < ts_by_station[st]["ts_min"]):
            ts_by_station[st]["ts_min"] = t["ts_min"]
        if t["ts_max"] and (ts_by_station[st]["ts_max"] is None or t["ts_max"] > ts_by_station[st]["ts_max"]):
            ts_by_station[st]["ts_max"] = t["ts_max"]

    for st in station_name_raw:
        station_rows.append(
            {
                "station_folder": st,
                "n_files": file_counts[st],
                "data_ts_min": ts_by_station[st]["ts_min"],
                "data_ts_max": ts_by_station[st]["ts_max"],
                "note": "Trailing tab in folder name detected" if "\t" in st else "",
            }
        )

    # -------------------------------------------------------------------
    # Write CSVs
    # -------------------------------------------------------------------
    def write_csv(name: str, rows: list[dict]) -> None:
        if not rows:
            print(f"  [WARN] No rows for {name}, skipping.")
            return
        out = OUT_DIR / name
        keys = list(rows[0].keys())
        with open(out, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(rows)
        print(f"  ✓ {name} ({len(rows)} rows)")

    print(f"\nWriting reports to {OUT_DIR} …\n")
    write_csv("file_inventory.csv", inv_rows)
    write_csv("schema_report.csv", schema_rows)
    write_csv("station_report.csv", station_rows)
    write_csv("timestamp_report.csv", ts_rows)
    write_csv("missingness_report.csv", miss_rows)
    write_csv("duplicate_report.csv", dup_rows)
    write_csv("numeric_quality_report.csv", num_rows)
    write_csv("schema_differences.csv", diff_rows)

    # -------------------------------------------------------------------
    # Compute aggregate stats for the summary
    # -------------------------------------------------------------------
    # missingness by semantic role (across all files, pollutant cols only)
    role_miss: dict[str, list] = defaultdict(list)
    for r in schema_rows:
        role = r["semantic_role"]
        if role not in ("unknown", "timestamp", "station_id", "city"):
            role_miss[role].append(r["pct_missing"])

    role_summary_lines = []
    for role in sorted(role_miss):
    	vals = role_miss[role]
    	avg_miss = round(sum(vals) / len(vals), 1)
    	max_miss = round(max(vals), 1)
    	role_summary_lines.append(f"  - **{role}**: avg miss {avg_miss}%, max miss {max_miss}% across {len(vals)} column instances")

    # duplicate summary
    total_full_dups = sum(r["n_full_duplicate_rows"] for r in dup_rows)
    total_ts_dups = sum(r["n_timestamp_duplicates"] for r in dup_rows)

    # timestamp frequencies observed
    freq_vals = [r["apparent_freq_hours"] for r in ts_rows if r["apparent_freq_hours"] is not None]
    unique_freqs = sorted(set(round(f, 2) for f in freq_vals))

    # gap summary
    total_gaps = sum(r["gap_count"] for r in ts_rows if r["gap_count"])
    max_gap = max((r["max_gap_hours"] for r in ts_rows if r["max_gap_hours"]), default=None)

    # schema diffs
    n_schema_diffs = len(diff_rows)

    # completely empty columns
    empty_cols = [(r["file_key"], r["col_name"]) for r in schema_rows if r["completely_empty"]]

    # numeric: negatives and sentinels
    n_neg_instances = sum(1 for r in num_rows if r.get("n_negative", 0) and r["n_negative"] > 0)
    n_sentinel_instances = sum(1 for r in num_rows if r.get("n_sentinel", 0) and r["n_sentinel"] > 0)

    # -------------------------------------------------------------------
    # Write profiling_summary.md
    # -------------------------------------------------------------------
    summary_path = OUT_DIR / "profiling_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# Phase 1 — Profiling Summary\n\n")
        f.write(f"_Generated by `profiling/profile_raw_data.py`_\n\n")
        f.write("---\n\n")

        f.write("## 1. Raw-Data Location Found\n\n")
        f.write(f"```\n{DATA_ROOT}\n```\n\n")

        f.write("## 2. File Inventory\n\n")
        f.write(f"| Metric | Value |\n|---|---|\n")
        f.write(f"| Total files scanned | {summary_stats['total_files']} |\n")
        f.write(f"| CSV files | {summary_stats['total_csv']} |\n")
        f.write(f"| XLSX files | {summary_stats['total_xlsx']} |\n")
        f.write(f"| Read errors | {summary_stats['read_errors']} |\n")
        f.write(f"| Total data rows (all files) | {summary_stats['total_rows']:,} |\n\n")

        f.write("## 3. Date Range\n\n")
        f.write(f"| | Timestamp |\n|---|---|\n")
        f.write(f"| Earliest | {summary_stats['ts_min']} |\n")
        f.write(f"| Latest   | {summary_stats['ts_max']} |\n\n")

        f.write("## 4. Stations Found\n\n")
        f.write(f"**{len(station_rows)} unique station folders** (Delhi data):\n\n")
        for st_r in station_rows:
            note = f" ⚠️ {st_r['note']}" if st_r['note'] else ""
            f.write(f"- `{st_r['station_folder']}`  ({st_r['n_files']} files, "
                    f"{st_r['data_ts_min']} → {st_r['data_ts_max']}){note}\n")
        f.write("\n")

        f.write("## 5. Pollutants / Variables Available\n\n")
        all_roles = sorted({r["semantic_role"] for r in schema_rows
                            if r["semantic_role"] not in ("unknown", "timestamp")})
        f.write(", ".join(f"`{r}`" for r in all_roles) + "\n\n")

        f.write("## 6. Time Resolution\n\n")
        f.write(f"- Observed median intervals (hours): **{unique_freqs}**\n")
        f.write(f"- Total timestamp gaps > 1.5× expected: **{total_gaps}**\n")
        f.write(f"- Largest single gap: **{max_gap} hours**\n\n")

        f.write("## 7. Missingness by Semantic Role\n\n")
        f.write("\n".join(role_summary_lines) + "\n\n")
        if empty_cols:
            f.write(f"**Completely empty columns ({len(empty_cols)} instances):**\n")
            for fk, cn in empty_cols[:30]:
                f.write(f"- `{fk}` → `{cn}`\n")
            if len(empty_cols) > 30:
                f.write(f"- … and {len(empty_cols)-30} more (see schema_report.csv)\n")
        f.write("\n")

        f.write("## 8. Duplicate Issues\n\n")
        f.write(f"- Fully duplicate rows (same file): **{total_full_dups}**\n")
        f.write(f"- Duplicate timestamps within a file: **{total_ts_dups}**\n")
        f.write(f"- Cross-file overlap: not measured at this stage (files are month/year splits — "
                f"overlap possible at boundaries; check timestamp_report.csv ranges).\n\n")

        f.write("## 9. Schema Inconsistencies\n\n")
        f.write(f"- Files with column-set differences vs. reference: **{n_schema_diffs}**\n")
        if diff_rows:
            f.write("- See `schema_differences.csv` for details.\n")
            for d in diff_rows[:10]:
                added = d['columns_added_vs_reference'][:80] or "—"
                removed = d['columns_removed_vs_reference'][:80] or "—"
                f.write(f"  - `{d['compared_file']}`: +[{added}] -[{removed}]\n")
        f.write("\n")

        f.write("## 10. Numeric Quality\n\n")
        f.write(f"- Column × file pairs with **negative values**: {n_neg_instances}\n")
        f.write(f"- Column × file pairs with **sentinel values** ({SENTINEL_VALUES}): {n_sentinel_instances}\n")
        f.write("- See `numeric_quality_report.csv` for per-column min/max/mean/zeros/negatives.\n\n")

        f.write("## 11. Files Requiring Special Handling\n\n")
        f.write("| Issue | Affected |\n|---|---|\n")
        f.write("| Trailing tab in folder name | `Jahangirpuri, Delhi - DPCC\\t` |\n")
        f.write("| Partial-year 2026 CSVs | Anand Vihar, Bawana, ITO, Jahangirpuri, Punjabi Bagh, R K Puram (≈5088 rows) |\n")
        f.write("| Dwarka only has 2023–2025 raw CSVs (no 2026) | Dwarka-Sector 8 |\n")
        f.write("| ITO operated by CPCB (others DPCC) — calibration may differ | ITO |\n")
        f.write("| XLSX files have AQI computed values, not raw pollutants | All AQI Hourly subdirs |\n\n")

        f.write("## 12. Recommended PostgreSQL Schema (based on profiling only)\n\n")
        f.write("""\
### Inference from data only (not a design specification):

**Two source types** were observed:
1. **CAAQMS Raw CSV** — full 24-column pollutant + meteorological measurements, hourly, per station, per year.
2. **AQI Hourly XLSX** — AQI index values (derived), monthly Excel worksheets.

### Proposed table organisation

```sql
-- Dimension: monitoring stations
stations (
    station_id      SERIAL PRIMARY KEY,
    station_name    TEXT NOT NULL,           -- e.g. "Anand Vihar"
    station_folder  TEXT,                    -- raw folder name (kept for traceability)
    city            TEXT,                    -- "Delhi"
    operator        TEXT,                    -- "DPCC" | "CPCB"
    data_from       DATE,
    data_to         DATE
);

-- Fact: CAAQMS hourly raw measurements (one row per station × hour)
caaqms_hourly (
    id              BIGSERIAL PRIMARY KEY,
    station_id      INT REFERENCES stations(station_id),
    ts              TIMESTAMPTZ NOT NULL,    -- stored as UTC; source data is IST (UTC+5:30)
    pm25            NUMERIC(8,2),
    pm10            NUMERIC(8,2),
    no_ugm3         NUMERIC(8,2),
    no2_ugm3        NUMERIC(8,2),
    nox_ppb         NUMERIC(8,2),
    nh3_ugm3        NUMERIC(8,2),
    so2_ugm3        NUMERIC(8,2),
    co_mgm3         NUMERIC(8,4),
    ozone_ugm3      NUMERIC(8,2),
    benzene_ugm3    NUMERIC(8,4),
    toluene_ugm3    NUMERIC(8,4),
    xylene_ugm3     NUMERIC(8,4),
    o_xylene_ugm3   NUMERIC(8,4),
    eth_benzene_ugm3 NUMERIC(8,4),
    mp_xylene_ugm3  NUMERIC(8,4),
    temp_c          NUMERIC(6,2),
    rh_pct          NUMERIC(6,2),
    ws_ms           NUMERIC(6,2),
    wd_deg          NUMERIC(6,2),
    rf_mm           NUMERIC(6,2),
    tot_rf_mm       NUMERIC(6,2),
    sr_wm2          NUMERIC(8,2),
    bp_mmhg         NUMERIC(8,2),
    vws_ms          NUMERIC(6,2),
    source_file     TEXT,                    -- original filename for traceability
    UNIQUE (station_id, ts)
);

-- Fact: AQI Hourly (from XLSX, derived values)
aqi_hourly (
    id              BIGSERIAL PRIMARY KEY,
    station_id      INT REFERENCES stations(station_id),
    ts              TIMESTAMPTZ NOT NULL,
    aqi             NUMERIC(6,1),
    -- add sub-index columns if sheets contain them
    source_file     TEXT,
    UNIQUE (station_id, ts)
);
```

**Key decisions implied by the data:**
- `TIMESTAMPTZ` not `TIMESTAMP` — no timezone info in source, but IST (UTC+5:30) should be applied at load time.
- `NUMERIC` not `FLOAT` — avoids floating-point rounding in a database; matches government data precision.
- `source_file` column on every fact table — critical for traceability given ~100 source files.
- `UNIQUE (station_id, ts)` — enforces deduplication at load; duplicates found in raw must be resolved in the ETL layer, not here.
- Separate `aqi_hourly` table — XLSX AQI files have a different schema and provenance than raw CAAQMS CSVs.
- Do NOT combine both into one table until the column mapping is verified (some stations have NA meteorological columns).
""")

    print(f"  ✓ profiling_summary.md")
    print(f"\n{'='*60}")
    print("  Profiling complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    profile_all()
