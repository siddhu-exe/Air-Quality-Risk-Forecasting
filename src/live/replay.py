"""Replay: re-forecast past hours from the stored readings, exactly as the hourly job would have, and score them.

    python -m src.live.replay --start 2026-09-01 --end 2026-10-07                 # read-only: forecast, score, report
    python -m src.live.replay --start 2026-09-01 --end 2026-10-07 --write         # also store the forecasts (run_type 'replay')

Each issue hour sees only data up to that hour (``forecast.forecast_rows`` cuts the history), runs through the same skip
rules and features, and serves the products in ``config/live.toml``. A replay is a code-path and sanity check on stored
data, not a live result: the stored readings may have been revised since the hour passed, and the forecasts are tagged
``run_type = 'replay'`` so model health and the API (``run_type = 'live'``) never mix them in.

Scores use the stored actuals (AQI at the target hour, PM2.5 reading at the target hour) and the references stored with
each forecast row (``y_persistence``, ``y_window_update``); skill is reported with 95% day-block bootstrap CIs.
Without ``--write`` the database is opened with the read-only role and nothing is written.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.features.compute_cpcb_aqi import STATION_IDS
from src.live import forecast, serving
from src.live.config import load_config, load_forecast_config
from src.live.forecast import HISTORY_HOURS, KST
from src.live.forecast_store import ForecastStore
from src.live.log import configure as configure_logging
from src.live.log import get_logger
from src.live.score import product_skill, score_frame

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "live"
SELECT_ACTUAL_AQI = "select station_id, ts, aqi as actual from aq.live_aqi where ts > %s and ts <= %s"
SELECT_ACTUAL_PM25 = (
    "select station_id, ts, pm25 as actual from aq.live_readings where pm25 is not null and ts > %s and ts <= %s"
)

LABEL = {"aqi": "AQI", "pm25": "PM2.5"}
log = get_logger(__name__)


def issue_hours(start: str, end: str) -> list[pd.Timestamp]:
    """Hour labels from ``start`` 00:00 through ``end`` 23:00 (Asia/Kolkata)."""
    first = pd.Timestamp(start, tz=KST)
    last = pd.Timestamp(end, tz=KST) + pd.Timedelta(hours=23)
    return list(pd.date_range(first, last, freq="h"))


def read_actuals(store: ForecastStore, since: pd.Timestamp, until: pd.Timestamp) -> pd.DataFrame:
    """Stored actuals for every target the products can have: (station_id, target, target_time, actual)."""
    frames = []
    for target, sql in (("aqi", SELECT_ACTUAL_AQI), ("pm25", SELECT_ACTUAL_PM25)):
        store._cur.execute(sql, (since.to_pydatetime(), until.to_pydatetime()))
        frame = pd.DataFrame(store._cur.fetchall(), columns=["station_id", "target_time", "actual"])
        frame["target"] = target
        frames.append(frame)
    out = pd.concat(frames, ignore_index=True)
    out["target_time"] = pd.to_datetime(out["target_time"], utc=True).dt.tz_convert(KST)
    return out


def replay(
    store: ForecastStore, hours: list[pd.Timestamp], models: serving.Serving, gate: dict, weather_fill: str = "none"
) -> tuple[pd.DataFrame, dict]:
    """Forecast every hour in ``hours`` from history read once. Returns (forecast rows, summary of skips)."""
    since, until = hours[0] - pd.Timedelta(hours=HISTORY_HOURS), hours[-1]
    readings, aqi = store.read_history(sorted(STATION_IDS.values()), since, until)
    caaqms, aqi_df = forecast.to_inputs(readings, aqi, weather_fill)
    frames, skipped_stations, skipped_products, empty_hours = [], {}, {}, 0
    started = time.time()
    for position, issue in enumerate(hours, start=1):
        rows, verdicts = forecast.forecast_rows(caaqms, aqi_df, issue, models, gate, run_type="replay")
        summary = forecast.summarize(verdicts)
        for reason in summary["skipped"].values():
            kind = _reason_kind(reason)
            skipped_stations[kind] = skipped_stations.get(kind, 0) + 1
        for key in summary["skipped_products"]:
            product = key.split("/")[1]
            skipped_products[product] = skipped_products.get(product, 0) + 1
        empty_hours += int(len(rows) == 0)
        frames.append(rows)
        if position % 50 == 0:
            log.info("replayed %s/%s hours (%.0fs)", position, len(hours), time.time() - started)
    forecasts = pd.concat([f for f in frames if len(f)], ignore_index=True)
    forecasts["forecast_id"] = np.arange(len(forecasts))
    return forecasts, {
        "hours": len(hours),
        "hours_without_any_forecast": empty_hours,
        "station_hours_skipped_by_reason": skipped_stations,
        "product_station_hours_dropped": skipped_products,
    }


def _reason_kind(reason: str) -> str:
    """A skip reason without its numbers, so the report groups them."""
    if "core features are missing" in reason:
        return "core features missing above the validation gate"
    return reason.split(":")[0]


def score_replay(forecasts: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Join forecasts with the stored actual at their target hour; forecasts whose target hour has no actual stay unscored."""
    joined = forecasts.merge(actuals, on=["station_id", "target", "target_time"], how="left")
    return score_frame(joined)


def coverage(forecasts: pd.DataFrame, scored: pd.DataFrame, hours: list[pd.Timestamp]) -> pd.DataFrame:
    possible = len(hours) * len(STATION_IDS)
    rows = []
    for (target, horizon), part in forecasts.groupby(["target", "horizon"]):
        done = scored[(scored["target"] == target) & (scored["horizon"] == horizon)]
        rows.append(
            {
                "target": target,
                "horizon": int(horizon),
                "station_hours": possible,
                "forecast": len(part),
                "forecast_share": len(part) / possible,
                "scored": len(done),
            }
        )
    return pd.DataFrame(rows)


def write_report(table: pd.DataFrame, cover: pd.DataFrame, summary: dict, start: str, end: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"replay_{start}_{end}"
    merged = table.merge(cover[["target", "horizon", "station_hours", "forecast", "scored"]], on=["target", "horizon"])
    merged.to_csv(out_dir / f"{stem}.csv", index=False)

    def ci(row: pd.Series, name: str) -> str:
        return f"{row[name]:+.3f} [{row[name + '_lo']:+.3f}, {row[name + '_hi']:+.3f}]"

    lines = [
        f"# Replay {start} .. {end} (run_type 'replay')",
        "",
        "Generated by `python -m src.live.replay`; every number comes from the CSV beside this file. The forecasts are re-made hour by hour "
        "from the stored readings with the production code and scored against the stored actuals. This is a sanity check on stored data, "
        "not a live result. Skill = 1 - MAE_model / MAE_reference with 95% day-block bootstrap CIs; the references are the ones stored with each forecast row.",
        "",
        "| Product | Scored | Days | MAE | Persistence MAE | Skill vs persistence | Window-update MAE | Skill vs window-update |",
        "| :--- | ---: | ---: | ---: | ---: | :---: | ---: | :---: |",
    ]
    for _, r in merged.iterrows():
        wu_mae = f"{r['mae_window_update']:.2f}" if pd.notna(r.get("mae_window_update")) else "n/a"
        wu_skill = ci(r, "skill_vs_window_update") if pd.notna(r.get("skill_vs_window_update")) else "n/a"
        lines.append(
            f"| {LABEL[r['target']]} {int(r['horizon'])}h | {int(r['scored']):,} | {int(r['days'])} | {r['mae_model']:.2f} | "
            f"{r['mae_persistence']:.2f} | {ci(r, 'skill_vs_persistence')} | {wu_mae} | {wu_skill} |"
        )
    lines += [
        "",
        f"Issue hours replayed: {summary['hours']}; hours with no forecast at all: {summary['hours_without_any_forecast']}.",
        f"Station-hours skipped, by reason: `{summary['station_hours_skipped_by_reason']}`. "
        f"Products dropped for a station (station-hours): `{summary['product_station_hours_dropped']}`.",
        "",
        "| Product | Station-hours possible | Forecast | Scored |",
        "| :--- | ---: | ---: | ---: |",
    ]
    lines += [
        f"| {LABEL[r.target]} {r.horizon}h | {r.station_hours:,} | {r.forecast:,} | {r.scored:,} |"
        for r in cover.itertuples()
    ]
    path = out_dir / f"{stem}.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", required=True, help="first issue day, e.g. 2026-09-01")
    parser.add_argument("--end", required=True, help="last issue day, e.g. 2026-10-07")
    parser.add_argument("--write", action="store_true", help="store the forecasts with run_type 'replay' (writer role)")
    parser.add_argument("--limit-hours", type=int, help="only the first N hours (timing and code-path checks)")
    args = parser.parse_args(argv)
    config = load_forecast_config()
    models = serving.load(config)
    hashes = serving.verify(models.specs)
    hours = issue_hours(args.start, args.end)[: args.limit_hours]
    gate = forecast.load_gate()
    with ForecastStore("DATABASE_URL_READONLY") as reader:
        forecasts, summary = replay(reader, hours, models, gate, load_config().weather_fill)
        actuals = read_actuals(reader, hours[0], hours[-1] + pd.Timedelta(hours=25))
    scored = score_replay(forecasts, actuals)
    table, cover = product_skill(scored), coverage(forecasts, scored, hours)
    if args.limit_hours is None:
        path = write_report(table, cover, summary, args.start, args.end, REPORT_DIR)
        log.info("wrote %s", path)
    print(table.round(3).to_string(index=False))
    print(cover.round(3).to_string(index=False))
    print(summary)
    if args.write:
        with ForecastStore("DATABASE_URL") as writer:
            run_id = writer.start_run("forecast", "replay")
            writer.register_models(models.specs, hashes, forecast.library_versions())
            written = writer.insert_forecasts(forecasts)
            writer.finish_run(
                run_id,
                "success",
                written,
                None,
                {"run_type": "replay", "start": args.start, "end": args.end, **summary},
            )
        log.info("stored %s replay forecasts", written)
    return 0


if __name__ == "__main__":
    sys.exit(main())
