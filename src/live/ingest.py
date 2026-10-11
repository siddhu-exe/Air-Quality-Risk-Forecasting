"""Hourly live ingest: fetch the newest hours from the configured source, QC, fill weather gaps, upsert, recompute AQI.

    python -m src.live.ingest                  # production: DATABASE_URL, source from config/live.toml (or LIVE_SOURCE)
    python -m src.live.ingest --dry-run        # fetch + process, print a summary, no database
    python -m src.live.ingest --source data_gov_in --allow-unverified --dry-run

Run status (written to ``aq.job_runs`` and mirrored in the process exit code):
  success  every station has a reading newer than ``stale_after_hours``
  partial  some stations are fresh, some stale
  failed   no fresh station, the source failed, or QC detected a probable unit change
A failed run exits non-zero so the workflow goes red and the monitoring rule (3 failures in a row) can open an issue.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

import pandas as pd

from src.features.compute_cpcb_aqi import POLLUTANTS, STATION_IDS, compute_aqi
from src.live import weather as weather_mod
from src.live.config import IngestConfig, load_config
from src.live.qc import ImplausibleBatch, check_batch, finish_hourly
from src.live.sources import SourceUnavailable, get_source
from src.live.sources.base import LiveSource, SourceNotVerified
from src.live.store import NullStore, Store

KST = "Asia/Kolkata"
AQI_HISTORY_HOURS = 48    # pollutant history read back so the 24 h rolling AQI has its window


def fetch_with_fallback(cfg: IngestConfig, start: pd.Timestamp, end: pd.Timestamp, factory=get_source) -> tuple[pd.DataFrame, LiveSource, list[str]]:
    """Primary source first; the optional fallback only if the primary fails or returns no rows. Returns notes of what happened."""
    notes: list[str] = []
    names = [cfg.source] + ([cfg.fallback] if cfg.fallback else [])
    last_error: Exception | None = None
    for position, name in enumerate(names):
        source = factory(name)
        try:
            source.require_verified(cfg.allow_unverified)
            frame = source.fetch(start, end)
        except (SourceUnavailable, SourceNotVerified) as exc:
            notes.append(f"{name}: {type(exc).__name__}: {exc}")
            last_error = exc
            continue
        if len(frame):
            if position:
                notes.append(f"fallback '{name}' used")
            return frame, source, notes
        notes.append(f"{name}: no rows for {start}..{end}")
    raise SourceUnavailable("; ".join(notes)) from last_error


def build_rows(frame: pd.DataFrame, source: LiveSource, cfg: IngestConfig, weather_fetch=weather_mod.fetch_recent) -> tuple[pd.DataFrame, dict]:
    """QC + weather fill per station. Returns (rows ready for the database, details)."""
    details: dict = {}
    row_flags = [dict() for _ in range(len(frame))]
    frame = frame.reset_index(drop=True)
    if cfg.weather_fill == "open-meteo":
        try:
            frame, row_flags = weather_mod.fill_missing(frame, weather_fetch())
            details["weather"] = "open-meteo"
        except Exception as exc:       # weather is a best-effort fill; the ingest must not fail because of it
            details["weather"] = f"unavailable: {type(exc).__name__}"
    else:
        details["weather"] = "none"
    parts = []
    for station, group in frame.groupby("station_name", sort=True):
        flags = [row_flags[i] for i in group.index]
        parts.append(finish_hourly(group.set_index("hour"), station, source.tag, source.station_flags(station), flags))
    rows = pd.concat([p for p in parts if len(p)]) if any(len(p) for p in parts) else pd.DataFrame()
    if len(rows):
        # Per station an hourly run has only a handful of values per column, too few for the per-frame guard
        # inside finish_hourly; judging the whole batch (all stations) catches a source-wide unit/scale change.
        check_batch(rows, list(rows.qc_flags))
    return rows, details


def recompute_aqi(store, rows: pd.DataFrame, since: pd.Timestamp) -> pd.DataFrame:
    """AQI for the affected stations from stored history plus the new rows (new rows win), for hours >= ``since``."""
    ids = sorted(rows.station_id.unique())
    history = store.recent_pollutants(ids, since - pd.Timedelta(hours=AQI_HISTORY_HOURS))
    new = rows.reset_index()[["station_id", "hour", *POLLUTANTS]]
    both = pd.concat([history[["station_id", "hour", *POLLUTANTS]], new]).drop_duplicates(["station_id", "hour"], keep="last")
    names = {v: k for k, v in STATION_IDS.items()}
    both["station_name"] = both.station_id.map(names)
    both = both.rename(columns={"hour": "Timestamp"}).sort_values(["station_id", "Timestamp"])
    aqi = compute_aqi(both[["station_id", "station_name", "Timestamp", *POLLUTANTS]]).dropna(subset=["aqi_value"])
    aqi = aqi.rename(columns={"timestamp": "hour", "aqi_value": "aqi"})
    return aqi[aqi.hour >= since][["station_id", "hour", "aqi"]]


def classify(rows: pd.DataFrame, now: pd.Timestamp, stale_after_hours: float) -> tuple[str, dict]:
    """status + freshness per station. A reading labelled T covers [T, T+1h), so its age is measured to T + 1 h."""
    newest = rows.reset_index().groupby("station_name")["hour"].max() if len(rows) else pd.Series(dtype="datetime64[ns]")
    ages = {s: round((now.tz_localize(None) - (t + pd.Timedelta(hours=1))).total_seconds() / 3600, 2) for s, t in newest.items()}
    fresh = sorted(s for s, a in ages.items() if a <= stale_after_hours)
    stale = {s: a for s, a in ages.items() if a > stale_after_hours}
    stale.update({s: None for s in STATION_IDS if s not in ages})                      # no reading at all
    status = "failed" if not fresh else ("success" if not stale else "partial")
    return status, {"fresh_stations": fresh, "stale_stations": stale, "age_hours": ages}


def run(cfg: IngestConfig, store, *, now: pd.Timestamp | None = None, factory=get_source, weather_fetch=weather_mod.fetch_recent) -> dict:
    now = now if now is not None else pd.Timestamp.now(tz=KST)
    end = now.tz_localize(None).floor("h") - pd.Timedelta(hours=1)          # newest complete hour label
    start = end - pd.Timedelta(hours=cfg.lookback_hours - 1)
    run_id = store.start_run("ingest")
    details: dict = {"config": {"source": cfg.source, "fallback": cfg.fallback, "lookback_hours": cfg.lookback_hours},
                     "window": [str(start), str(end)]}
    status, error, written = "failed", None, 0
    try:
        frame, source, notes = fetch_with_fallback(cfg, start, end, factory)
        details.update(source_used=source.name, notes=notes, missing_from_source=source.missing)
        rows, extra = build_rows(frame, source, cfg, weather_fetch)
        details.update(extra)
        if rows.empty:
            raise SourceUnavailable("the source returned rows but none had a usable value")
        written = store.upsert_readings(rows)
        aqi = recompute_aqi(store, rows, start)
        details["aqi_rows"] = store.upsert_aqi(aqi)
        details["qc_flagged_cells"] = dict(Counter(k for f in rows.qc_flags for k in f if not k.startswith("_")))
        status, fresh = classify(rows, now, cfg.stale_after_hours)
        details.update(fresh)
    except ImplausibleBatch as exc:
        error, status = f"ImplausibleBatch: {exc}", "failed"
    except (SourceUnavailable, SourceNotVerified) as exc:
        error, status = f"{type(exc).__name__}: {exc}", "failed"
    except Exception as exc:                       # record a short, key-free message and re-raise for the traceback
        store.finish_run(run_id, "failed", written, f"{type(exc).__name__}", details)
        raise
    store.finish_run(run_id, status, written, error, details)
    return {"status": status, "rows": written, "error": error, "details": details}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="no database; print what would be written")
    parser.add_argument("--source", help="override the configured source for this run")
    parser.add_argument("--allow-unverified", action="store_true")
    args = parser.parse_args(argv)
    cfg = load_config()
    overrides = {k: v for k, v in (("source", args.source), ("allow_unverified", True if args.allow_unverified else None)) if v}
    if overrides:
        cfg = IngestConfig(**{**cfg.__dict__, **overrides})
    store = NullStore() if args.dry_run else Store()
    with store:
        result = run(cfg, store)
    print(f"status={result['status']} rows={result['rows']} source={result['details'].get('source_used')} "
          f"fresh={len(result['details'].get('fresh_stations', []))}/7 error={result['error']}")
    return 0 if result["status"] in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
