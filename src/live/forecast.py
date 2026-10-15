"""Hourly forecast job: read recent history from the database, build features with the SAME code that built the
training matrix, score the frozen models, write ``aq.forecasts``.

    python -m src.live.forecast                          # production: DATABASE_URL, issue hour = newest complete AQI hour
    python -m src.live.forecast --dry-run                # read the DB, print what would be written, write nothing
    python -m src.live.forecast --issue-time "2026-10-07 12:00" --dry-run     # replay a historical hour

Products (``[forecast]`` in config/live.toml, ADR 0006): AQI 1h = rule-based window-update persistence, AQI 6h/24h and
PM2.5 1h/6h = live-consistent models trained on recomputed AQI (``src/live/serving.py``).

Design rules (docs/TIER_3/PLAN.md section 4):
  * features come from ``compute_feature_frame`` (shared with training) plus the 24h model's multi-day features;
  * a station is SKIPPED, with the reason in ``job_runs.details``, never imputed: stale, no AQI at the issue hour,
    too little AQI history, a whole required feature group missing, or too many core features missing;
  * groups the D1 audit showed the models tolerate (station weather, solar, NOx) may be absent; weather cells filled from
    Open-Meteo are masked when ``weather_fill = "none"`` (the audit showed filling hurt the 1h/6h models);
  * models hash-verified against config/live_model_hashes.json; ``y_persistence`` (the current value of the target) is
    written on every row;
  * no 24h PM2.5, no intervals, no P(severe): refused by the config (ADR 0006).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.features.build_features import _stations_frame, compute_feature_frame
from src.features.compute_cpcb_aqi import POLLUTANTS, ROLLING_WINDOW_HOURS, STATION_IDS, hourly_aqi_series
from src.live import serving
from src.live.log import configure as configure_logging
from src.live.log import get_logger
from src.live.qc import WEATHER_ALL
from src.live.rules import window_update_estimate

KST = "Asia/Kolkata"
RULE_HISTORY_HOURS = 48  # hourly AQI history the rule reads: the 24h window plus the 8h CO/O3 smoothing
RULE_CONSISTENCY_TOLERANCE = 0.01
HISTORY_HOURS = (
    408  # hours read per station: 168 earlier AQI rows for the 24h features + 168 h lags + room for AQI gaps
)
WINDOW_HOURS = (
    336  # window handed to the feature builder (14 days); rows with an AQI inside it must number >= MIN_HISTORY_ROWS
)
MIN_HISTORY_ROWS = 169  # the 24h model reads the row 168 positions back
STALE_AFTER_HOURS = 3.0
GATE_PATH = Path(__file__).resolve().parents[2] / "config" / "forecast_gate.json"

#: feature-name prefixes of the groups the D1 audit showed can be absent (NOx; station weather; solar radiation)
AUDITED_ABSENT_PREFIXES = ("nox_", "temp_", "humidity_", "wind_speed_", "solar_rad_")
#: required groups: if one is missing for the WHOLE history window the model's inputs are not what it was trained on
REQUIRED_GROUPS = {
    "aqi": ("aqi_",),
    "pm25": ("pm25_",),
    "pm10": ("pm10_",),
    "no2": ("no2_",),
    "so2": ("so2_",),
    "co": ("co_",),
    "o3": ("o3_",),
}

READING_VALUE_COLUMNS = [
    "pm25",
    "pm10",
    "no2",
    "nox",
    "nh3",
    "so2",
    "co",
    "o3",
    "temperature",
    "humidity",
    "wind_speed",
    "solar_radiation",
]

log = get_logger(__name__)


def load_gate(path: Path = GATE_PATH) -> dict:
    return json.loads(path.read_text())


# --------------------------------------------------------------------------- inputs
def mask_filled_weather(readings: pd.DataFrame, weather_fill: str) -> pd.DataFrame:
    """With ``weather_fill = "none"`` every weather cell whose qc_flags say ``filled:*`` becomes NaN, so the models only
    see station/source measurements. The stored values stay in the database for display; this works on a copy."""
    out = readings.copy()
    if weather_fill == "none" and "qc_flags" in out:
        for column in WEATHER_ALL:
            flagged = out["qc_flags"].map(
                lambda flags, c=column: isinstance(flags, dict) and str(flags.get(c, "")).startswith("filled:")
            )
            out.loc[flagged, column] = np.nan
    return out


def to_inputs(
    readings: pd.DataFrame, aqi: pd.DataFrame, weather_fill: str = "none"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """DB-shaped frames -> the (caaqms_df, aqi_df) the feature builder takes. ``readings``: station_id, ts, values..., qc_flags;
    ``aqi``: station_id, ts, aqi. Timestamps become tz-aware Asia/Kolkata in a ``timestamp`` column."""
    names = {v: k for k, v in STATION_IDS.items()}
    readings = mask_filled_weather(readings, weather_fill)
    caaqms = readings.drop(
        columns=[c for c in ("qc_flags", "weather_source", "source", "ingested_at") if c in readings]
    ).copy()
    for column in READING_VALUE_COLUMNS:
        if column not in caaqms:
            caaqms[column] = np.nan
    caaqms["timestamp"] = pd.to_datetime(caaqms.pop("ts"), utc=True).dt.tz_convert(KST)
    caaqms["station_name"] = caaqms["station_id"].map(names)
    aqi_ts = pd.to_datetime(aqi["ts"], utc=True).dt.tz_convert(KST).reset_index(drop=True)
    aqi_df = pd.DataFrame(
        {
            "station_id": aqi["station_id"].to_numpy(),
            "station_name": aqi["station_id"].map(names).to_numpy(),
            "timestamp": aqi_ts,
            "aqi_value": aqi["aqi"].to_numpy(float),
            "aqi_source": "recomputed_live",
        }
    )
    return caaqms, aqi_df


# --------------------------------------------------------------------------- features
def add_long_horizon(frame: pd.DataFrame) -> pd.DataFrame:
    """The 24h model's multi-day features: the training function ``construct_causal_long_horizon_features`` applied to the
    feature rows that have an AQI, exactly as Phase 6C / Tier 2 did.

    Those shifts and rolling windows are ROW-based (n rows back), not hour-based: in a window with AQI gaps a "96 h lag" reaches
    further back than 96 h. The frozen model was trained and scored that way, so serving must do the same to reproduce it;
    the parity test (stored predictions, 1e-6) fails if this is changed to hour-based lags. It needs 168 earlier rows."""
    from src.models.phase_6c_refinement import construct_causal_long_horizon_features

    return construct_causal_long_horizon_features(frame)


def _as_kst(issue_time: Any) -> pd.Timestamp:
    issue = pd.Timestamp(issue_time)
    return issue.tz_localize(KST) if issue.tzinfo is None else issue.tz_convert(KST)


def build_frames(caaqms: pd.DataFrame, aqi: pd.DataFrame, issue_time: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(base, featured). ``base`` = feature rows (every row with an AQI) over the window ending at the issue hour, from the
    shared training feature builder; ``featured`` = ``base`` plus the 24h model's multi-day features on the full hourly grid.
    Data after the issue hour is dropped first, so a replay of a past hour cannot see its own future."""
    issue = _as_kst(issue_time)
    start = issue - pd.Timedelta(hours=WINDOW_HOURS)
    caaqms, aqi = caaqms[caaqms["timestamp"] <= issue], aqi[aqi["timestamp"] <= issue]
    with contextlib.redirect_stdout(io.StringIO()):  # the shared builder prints a progress line per station
        base = compute_feature_frame(
            _stations_frame(), caaqms, aqi, issue - pd.Timedelta(hours=HISTORY_HOURS), issue, start, issue
        )
    return base, (add_long_horizon(base) if len(base) else base)


# --------------------------------------------------------------------------- skip rules
@dataclass
class StationVerdict:
    station: str
    ok: bool
    reason: str | None = None
    notes: dict = field(default_factory=dict)


def _required_group_absent(history: pd.DataFrame, feature_names: set[str]) -> str | None:
    """Name of a required group that has no value anywhere in the station's window (its lag/rolling features cannot be real)."""
    for group, prefixes in REQUIRED_GROUPS.items():
        columns = [c for c in history.columns if c.startswith(prefixes) and c in feature_names]
        if columns and history[columns].isna().all().all():
            return group
    return None


def core_missing_share(row: pd.Series, feature_names: list[str]) -> float:
    core = [c for c in feature_names if not c.startswith("station_") and not c.startswith(AUDITED_ABSENT_PREFIXES)]
    return float(row[core].isna().mean()) if core else 0.0


def assess_station(
    station: str,
    row: pd.Series | None,
    history: pd.DataFrame,
    latest_reading: pd.Timestamp | None,
    issue: pd.Timestamp,
    models: serving.Serving,
    gate: dict,
    stale_after_hours: float = STALE_AFTER_HOURS,
) -> StationVerdict:
    """Decide whether ``station`` may be forecast at ``issue``. ``history`` = the station's feature rows over the window
    (rows with an AQI); ``row`` = its feature row at the issue hour, if any."""
    if latest_reading is None:
        return StationVerdict(station, False, "no readings in the database")
    age = (issue - latest_reading).total_seconds() / 3600
    if age > stale_after_hours:
        return StationVerdict(
            station,
            False,
            f"stale: newest reading is {age:.1f} h older than the issue hour (limit {stale_after_hours:g} h)",
        )
    if row is None or pd.isna(row.get("aqi_curr")):
        return StationVerdict(station, False, "current AQI missing at the issue hour")
    needed = {name for names in models.features.values() for name in names}
    absent = _required_group_absent(history, needed)
    if absent:
        return StationVerdict(
            station, False, f"required feature group '{absent}' is missing for the whole history window"
        )
    if len(history) < MIN_HISTORY_ROWS:
        return StationVerdict(
            station,
            False,
            f"insufficient history: {len(history)} hourly AQI rows in the last {WINDOW_HOURS} h, need {MIN_HISTORY_ROWS}",
        )
    worst = max((core_missing_share(row, names) for names in models.features.values()), default=0.0)
    if worst > gate["max_core_missing_share"]:
        return StationVerdict(
            station,
            False,
            f"{worst:.1%} of the core features are missing (validation limit {gate['max_core_missing_share']:.1%})",
        )
    absent_audited = [
        p.rstrip("_")
        for p in AUDITED_ABSENT_PREFIXES
        if (cols := [c for c in needed if c.startswith(p) and c in row.index]) and row[cols].isna().all()
    ]
    return StationVerdict(
        station, True, None, {"audited_groups_absent": absent_audited, "core_missing_share": round(worst, 4)}
    )


# --------------------------------------------------------------------------- forecasting
def forecast_rows(
    caaqms: pd.DataFrame,
    aqi: pd.DataFrame,
    issue_time: pd.Timestamp,
    models: serving.Serving,
    gate: dict,
    latest_readings: dict | None = None,
    stale_after_hours: float = STALE_AFTER_HOURS,
) -> tuple[pd.DataFrame, list[StationVerdict]]:
    """Forecast every eligible station at ``issue_time``. Returns (rows for aq.forecasts, one verdict per station)."""
    issue = _as_kst(issue_time)
    caaqms = caaqms[caaqms["timestamp"] <= issue]
    base, featured = build_frames(caaqms, aqi, issue)
    if latest_readings is None:
        latest_readings = (
            caaqms.dropna(subset=READING_VALUE_COLUMNS, how="all").groupby("station_name")["timestamp"].max().to_dict()
        )
    verdicts, keep, rule_values = [], [], {}
    for name, station_id in sorted(STATION_IDS.items(), key=lambda kv: kv[1]):
        history = base[base["station_name"] == name] if len(base) else base
        at_issue = (
            featured[(featured["station_name"] == name) & (featured["timestamp"] == issue)]
            if len(featured)
            else featured
        )
        row = at_issue.iloc[0] if len(at_issue) and pd.notna(at_issue.iloc[0]["aqi_curr"]) else None
        verdict = assess_station(name, row, history, latest_readings.get(name), issue, models, gate, stale_after_hours)
        verdicts.append(verdict)
        if verdict.ok:
            keep.append(at_issue.iloc[0])
            if models.has("aqi_1h"):
                value, why = rule_value(caaqms, name, issue, float(at_issue.iloc[0]["aqi_curr"]))
                if value is None:
                    verdict.notes["aqi_1h_skipped"] = why
                else:
                    rule_values[name] = value
    if not keep:
        return pd.DataFrame(
            columns=[
                "issue_time",
                "target_time",
                "station_id",
                "station_name",
                "horizon",
                "target",
                "model_version",
                "y_hat",
                "y_persistence",
            ]
        ), verdicts
    return assemble(pd.DataFrame(keep).reset_index(drop=True), issue, models, rule_values), verdicts


def rule_value(caaqms: pd.DataFrame, station: str, issue: pd.Timestamp, aqi_curr: float) -> tuple[float | None, str]:
    """The 1h rule at ``issue`` for one station, from its stored pollutant readings: (value, "") or (None, reason).

    Needs the current hourly AQI and 16 valid hours in the 24h window. The hourly series must also reproduce the stored
    AQI at the issue hour, so a rule value never rests on different data than the AQI shown beside it."""
    index = pd.date_range(end=issue, periods=RULE_HISTORY_HOURS, freq="h")
    own = caaqms[(caaqms["station_name"] == station) & (caaqms["timestamp"].isin(index))]
    series = own.drop_duplicates("timestamp", keep="last").set_index("timestamp")[POLLUTANTS].reindex(index)
    hourly = hourly_aqi_series(series)
    value = window_update_estimate(hourly, 1).iloc[-1]
    if pd.isna(value):
        return None, "no valid current hourly AQI, or fewer than 16 valid hours in the 24h window"
    rebuilt = hourly.rolling(ROLLING_WINDOW_HOURS, min_periods=16).mean().iloc[-1]
    if pd.isna(rebuilt) or abs(rebuilt - aqi_curr) > RULE_CONSISTENCY_TOLERANCE:
        return None, f"hourly AQI rebuilds {rebuilt:.2f}, stored AQI is {aqi_curr:.2f}"
    return float(value), ""


def assemble(
    rows: pd.DataFrame, issue: pd.Timestamp, models: serving.Serving, rule_values: dict[str, float] | None = None
) -> pd.DataFrame:
    """Every enabled product for feature ``rows`` (one per station, all at ``issue``), shaped like ``aq.forecasts``.
    The rule covers only stations whose hourly AQI passed ``rule_value``; a product whose
    forecast or persistence value is not finite for a station (for example PM2.5 missing at the issue hour) is dropped for that station."""
    out = []
    for spec in models.specs:
        if spec.kind == "rule":
            part = rows[rows["station_name"].isin(rule_values or {})]
            y_hat = part["station_name"].map(rule_values).to_numpy(float)
        else:
            part, y_hat = rows, serving.predict(models, spec.key, rows)
        out.append(
            pd.DataFrame(
                {
                    "issue_time": issue,
                    "target_time": issue + pd.Timedelta(hours=spec.horizon),
                    "station_id": part["station_id"].astype(int).to_numpy(),
                    "station_name": part["station_name"].to_numpy(),
                    "horizon": spec.horizon,
                    "target": spec.target,
                    "model_version": spec.version,
                    "y_hat": y_hat,
                    "y_persistence": serving.persistence(spec, part),
                }
            )
        )
    forecasts = pd.concat(out, ignore_index=True)
    finite = np.isfinite(forecasts[["y_hat", "y_persistence"]].to_numpy(float)).all(axis=1)
    return forecasts[finite].reset_index(drop=True)  # e.g. no current PM2.5: no PM2.5 forecast, never a NaN row


def summarize(verdicts: list[StationVerdict]) -> dict:
    return {
        "forecast": [v.station for v in verdicts if v.ok],
        "skipped": {v.station: v.reason for v in verdicts if not v.ok},
        "notes": {v.station: v.notes for v in verdicts if v.ok},
    }


def classify_run(verdicts: list[StationVerdict]) -> str:
    done = sum(v.ok for v in verdicts)
    return "failed" if done == 0 else ("success" if done == len(verdicts) else "partial")


# --------------------------------------------------------------------------- the job
def library_versions() -> dict:
    import sklearn

    out = {"pandas": pd.__version__, "numpy": np.__version__, "scikit-learn": sklearn.__version__}
    try:
        import lightgbm

        out["lightgbm"] = lightgbm.__version__
    except ModuleNotFoundError:
        pass
    return out


def run(
    store: Any,
    models: serving.Serving,
    gate: dict,
    hashes: dict,
    *,
    issue_time: pd.Timestamp | None = None,
    now: pd.Timestamp | None = None,
    weather_fill: str = "none",
    stale_after_hours: float = STALE_AFTER_HOURS,
    dry_run: bool = False,
) -> dict:
    """Read history, forecast, write. ``store`` needs ``newest_aqi_hour``, ``read_history`` and (unless ``dry_run``) the write methods."""
    now = _as_kst(now) if now is not None else pd.Timestamp.now(tz=KST)
    run_id = 0 if dry_run else store.start_run("forecast")
    details: dict = {
        "dry_run": dry_run,
        "weather_fill": weather_fill,
        "gate": gate["max_core_missing_share"],
        "models": {spec.key: spec.version for spec in models.specs},
    }
    written, error, status = 0, None, "failed"
    try:
        if issue_time is None:
            newest = store.newest_aqi_hour()
            if newest is None:
                raise LookupError("no AQI rows in the database")
            issue_time = newest
            age = (now - (issue_time + pd.Timedelta(hours=1))).total_seconds() / 3600
            if age > stale_after_hours:
                raise LookupError(
                    f"newest AQI hour {issue_time} is {age:.1f} h old (limit {stale_after_hours:g} h): nothing fresh to forecast from"
                )
        issue = _as_kst(issue_time)
        details["issue_time"] = str(issue)
        readings, aqi = store.read_history(
            sorted(STATION_IDS.values()), issue - pd.Timedelta(hours=HISTORY_HOURS), issue
        )
        details["history_rows"] = {"readings": len(readings), "aqi": len(aqi)}
        caaqms, aqi_df = to_inputs(readings, aqi, weather_fill)
        rows, verdicts = forecast_rows(caaqms, aqi_df, issue, models, gate, stale_after_hours=stale_after_hours)
        details.update(summarize(verdicts))
        status = classify_run(verdicts)
        if len(rows) and not dry_run:
            store.register_models(models.specs, hashes, library_versions())
            written = store.insert_forecasts(rows)
        elif len(rows):
            written = 0
        if status == "failed":
            error = (
                "no station could be forecast: " + "; ".join(f"{k}: {v}" for k, v in details["skipped"].items())[:500]
            )
    except LookupError as exc:
        error = str(exc)
    except Exception as exc:  # record a short, key-free message and re-raise
        if not dry_run:
            store.finish_run(run_id, "failed", written, type(exc).__name__, details)
        raise
    if not dry_run:
        store.finish_run(run_id, status, written, error, details)
    return {"status": status, "rows": written, "error": error, "details": details, "forecasts": locals().get("rows")}


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    from src.live.config import load_config, load_forecast_config
    from src.live.forecast_store import ForecastStore

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="read-only role, nothing written; prints the forecasts")
    parser.add_argument("--issue-time", help="replay this hour label (Asia/Kolkata), e.g. '2026-10-07 12:00'")
    args = parser.parse_args(argv)
    cfg = load_config()
    forecast_cfg = load_forecast_config()
    specs = serving.enabled_specs(forecast_cfg)
    hashes = serving.verify(specs)  # raises ModelHashMismatch: the job must not run on a changed artifact
    models = serving.load(forecast_cfg, check=False)
    with ForecastStore("DATABASE_URL_READONLY" if args.dry_run else "DATABASE_URL") as store:
        result = run(
            store,
            models,
            load_gate(),
            hashes,
            issue_time=pd.Timestamp(args.issue_time) if args.issue_time else None,
            weather_fill=cfg.weather_fill,
            stale_after_hours=cfg.stale_after_hours,
            dry_run=args.dry_run,
        )
    frame = result["forecasts"]
    if args.dry_run and frame is not None and len(frame):
        print(
            frame.assign(y_hat=frame.y_hat.round(1), y_persistence=frame.y_persistence.round(1))[
                ["station_name", "horizon", "issue_time", "target_time", "y_hat", "y_persistence"]
            ].to_string(index=False)
        )
    d = result["details"]
    log.info(
        "status=%s rows=%s issue=%s forecast=%s/7 skipped=%s error=%s",
        result["status"],
        result["rows"],
        d.get("issue_time"),
        len(d.get("forecast", [])),
        d.get("skipped", {}),
        result["error"],
    )
    return 0 if result["status"] in ("success", "partial") else 1


if __name__ == "__main__":
    sys.exit(main())
