"""Score matured forecasts, keep the rolling skill table current, and apply the alert rules.

    python -m src.live.score                       # score what has matured, refresh skill_rolling (run_type live)
    python -m src.live.score --run-type replay     # the same for replayed hours
    python -m src.live.score --issues              # also open/refresh GitHub issues (needs GITHUB_TOKEN, runs in Actions)

Rules this module follows:
  * references are the ones stored with each forecast (``y_persistence``, ``y_window_update``): scoring never re-derives
    them, because readings can be revised after the forecast was written;
  * a forecast is scored once its target hour is over (``target_time + 1 h <= now``) and the actual is stored;
  * the actual is the stored AQI at ``target_time`` for AQI forecasts and the stored PM2.5 reading for PM2.5 forecasts;
  * nothing is ever deleted; ``forecast_scores`` is insert-only (``on conflict do nothing``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.evaluation.build_metrics_table import block_bootstrap
from src.live.log import configure as configure_logging
from src.live.log import get_logger
from src.live.store import Store

KST = "Asia/Kolkata"
WINDOW_DAYS = 30
SEVERE_AQI = 401.0
MIN_WINDOW_ROWS = 20  # a window with fewer scored forecasts is not summarised (its skill would be noise)
N_BOOT, SEED = 1000, 42
ALERT_DAYS = 7  # consecutive daily windows with negative skill before an issue is opened
ALERT_FAILED_RUNS = 3
ISSUE_LABEL = "model-health"

log = get_logger(__name__)

SELECT_MATURED = """
select f.id as forecast_id, f.station_id, f.horizon, f.target, f.target_time, f.y_hat, f.y_persistence, f.y_window_update,
       case when f.target = 'aqi' then a.aqi else r.pm25 end as actual
from aq.forecasts f
left join aq.forecast_scores s on s.forecast_id = f.id
left join aq.live_aqi a on f.target = 'aqi' and a.station_id = f.station_id and a.ts = f.target_time
left join aq.live_readings r on f.target = 'pm25' and r.station_id = f.station_id and r.ts = f.target_time
where s.forecast_id is null and f.run_type = %s and f.target_time + interval '1 hour' <= %s
  and (case when f.target = 'aqi' then a.aqi else r.pm25 end) is not null
order by f.target_time, f.station_id, f.horizon, f.target
"""
INSERT_SCORES = """
insert into aq.forecast_scores (forecast_id, station_id, horizon, target, target_time, actual, abs_err,
                                abs_err_persistence, abs_err_window_update, in_interval, severe_actual)
values %s
on conflict (forecast_id) do nothing
returning 1
"""
SELECT_SCORES = """
select s.forecast_id, s.station_id, s.horizon, s.target, s.target_time, s.actual, s.abs_err, s.abs_err_persistence,
       s.abs_err_window_update
from aq.forecast_scores s join aq.forecasts f on f.id = s.forecast_id
where f.run_type = %s and s.target_time >= %s
order by s.target_time
"""
UPSERT_SKILL = """
insert into aq.skill_rolling (station_id, horizon, target, window_end, window_days, n, mae_model,
                              mae_persistence, skill_mae, mae_window_update, skill_vs_window_update)
values %s
on conflict on constraint skill_rolling_key do update set n = excluded.n, mae_model = excluded.mae_model,
  mae_persistence = excluded.mae_persistence, skill_mae = excluded.skill_mae,
  mae_window_update = excluded.mae_window_update, skill_vs_window_update = excluded.skill_vs_window_update,
  computed_at = now()
"""
SELECT_SKILL = """
select horizon, target, window_end, skill_mae, skill_vs_window_update, n
from aq.skill_rolling
where station_id is null and window_days = %s and window_end >= %s
order by horizon, target, window_end
"""
SELECT_RECENT_RUNS = """
select job, status, started_at from aq.job_runs where run_type = 'live' and job = any(%s) order by started_at desc limit 50
"""


# --------------------------------------------------------------------------- pure scoring
def score_frame(matured: pd.DataFrame) -> pd.DataFrame:
    """Errors for forecasts joined with their actuals. Input columns: forecast_id, station_id, horizon, target,
    target_time, y_hat, y_persistence, y_window_update, actual. Rows without an actual are dropped, never filled."""
    frame = matured.dropna(subset=["actual"]).copy()
    actual = frame["actual"].astype(float)
    frame["abs_err"] = (frame["y_hat"].astype(float) - actual).abs()
    frame["abs_err_persistence"] = (frame["y_persistence"].astype(float) - actual).abs()
    frame["abs_err_window_update"] = (frame["y_window_update"].astype(float) - actual).abs()  # NaN for PM2.5
    frame["severe_actual"] = np.where(frame["target"] == "aqi", actual >= SEVERE_AQI, None)
    return frame


def day_of(target_time: pd.Series) -> pd.Series:
    return pd.to_datetime(target_time, utc=True).dt.tz_convert(KST).dt.date


def skill(model_mae: float, reference_mae: float) -> float:
    return float(1.0 - model_mae / reference_mae) if reference_mae > 0 else float("nan")


def product_skill(scores: pd.DataFrame, n_boot: int = N_BOOT) -> pd.DataFrame:
    """Per (target, horizon): MAE of the model and of each stored reference, skill against each with 95% day-block CIs.
    ``scores`` needs the columns of ``score_frame`` output plus ``actual``, ``y_hat``, ``y_persistence``, ``y_window_update``."""
    rows = []
    for (target, horizon), part in scores.groupby(["target", "horizon"]):
        y, hat = part["actual"].to_numpy(float), part["y_hat"].to_numpy(float)
        persistence = part["y_persistence"].to_numpy(float)
        days = day_of(part["target_time"]).to_numpy()
        record = {
            "target": target,
            "horizon": int(horizon),
            "n": len(part),
            "days": int(pd.Series(days).nunique()),
            "mae_model": float(np.abs(hat - y).mean()),
            "mae_persistence": float(np.abs(persistence - y).mean()),
        }
        record["skill_vs_persistence"] = skill(record["mae_model"], record["mae_persistence"])
        ci = block_bootstrap(y, hat, persistence, days, n_boot, SEED)
        record["skill_vs_persistence_lo"], record["skill_vs_persistence_hi"] = (
            ci["skill_mae_ci_lo"],
            ci["skill_mae_ci_hi"],
        )
        if target == "aqi":
            wu = part["y_window_update"].to_numpy(float)
            record["mae_window_update"] = float(np.abs(wu - y).mean())
            record["skill_vs_window_update"] = skill(record["mae_model"], record["mae_window_update"])
            ci = block_bootstrap(y, hat, wu, days, n_boot, SEED)
            record["skill_vs_window_update_lo"], record["skill_vs_window_update_hi"] = (
                ci["skill_mae_ci_lo"],
                ci["skill_mae_ci_hi"],
            )
        rows.append(record)
    return pd.DataFrame(rows)


def rolling_rows(scores: pd.DataFrame, window_end: pd.Timestamp, window_days: int = WINDOW_DAYS) -> list[tuple]:
    """``aq.skill_rolling`` rows (pooled over stations and per station) for the window ending on ``window_end`` (a date)."""
    days = pd.Series(day_of(scores["target_time"]).to_numpy())
    end = pd.Timestamp(window_end).date()
    start = (pd.Timestamp(window_end) - pd.Timedelta(days=window_days - 1)).date()
    window = scores[((days >= start) & (days <= end)).to_numpy()]
    out = []
    for station in [None, *sorted(window["station_id"].unique())]:
        part = window if station is None else window[window["station_id"] == station]
        for (target, horizon), group in part.groupby(["target", "horizon"]):
            if len(group) < MIN_WINDOW_ROWS:
                continue
            mae_model, mae_persistence = group["abs_err"].mean(), group["abs_err_persistence"].mean()
            mae_wu = group["abs_err_window_update"].mean() if target == "aqi" else None
            out.append(
                (
                    None if station is None else int(station),
                    int(horizon),
                    target,
                    end,
                    window_days,
                    int(len(group)),
                    float(mae_model),
                    float(mae_persistence),
                    skill(mae_model, mae_persistence),
                    None if mae_wu is None else float(mae_wu),
                    None if mae_wu is None else skill(mae_model, mae_wu),
                )
            )
    return out


# --------------------------------------------------------------------------- alert rules
@dataclass(frozen=True)
class Alert:
    key: str  # stable id; the issue title carries it so a rerun refreshes the same issue
    title: str
    body: str


def _trailing_negative_days(series: pd.Series) -> int:
    """Consecutive days at the end of a date-ordered series whose value is below zero (NaN stops the streak)."""
    count = 0
    for value in reversed(series.tolist()):
        if value is None or pd.isna(value) or value >= 0:
            break
        count += 1
    return count


def evaluate_alerts(
    skill_history: pd.DataFrame, runs: pd.DataFrame, days: int = ALERT_DAYS, failures: int = ALERT_FAILED_RUNS
) -> list[Alert]:
    """Alerts from the pooled daily rolling skill and the job history.

    * a published product whose skill against plain persistence is below zero for ``days`` consecutive days;
    * an AQI product whose skill against window-update persistence is below zero for ``days`` consecutive days
      (the model is then worse than the rule it should beat);
    * a job whose last ``failures`` runs all failed.
    ``skill_history``: horizon, target, window_end, skill_mae, skill_vs_window_update. ``runs``: job, status, started_at."""
    alerts: list[Alert] = []
    for (target, horizon), group in skill_history.sort_values("window_end").groupby(["target", "horizon"]):
        if _trailing_negative_days(group["skill_mae"]) >= days:
            alerts.append(
                Alert(
                    f"skill-{target}-{horizon}h",
                    f"Model health: {target.upper()} {horizon}h skill below zero for {days} days",
                    f"Rolling {WINDOW_DAYS}-day MAE skill against plain persistence has been negative for {days} consecutive days "
                    f"(latest {group['skill_mae'].iloc[-1]:+.3f}, n={int(group['n'].iloc[-1])}).",
                )
            )
        if target == "aqi" and horizon in (1, 6) and _trailing_negative_days(group["skill_vs_window_update"]) >= days:
            alerts.append(
                Alert(
                    f"skill-vs-rule-aqi-{horizon}h",
                    f"Model health: AQI {horizon}h worse than window-update persistence for {days} days",
                    f"Rolling {WINDOW_DAYS}-day MAE skill against window-update persistence has been negative for {days} "
                    f"consecutive days (latest {group['skill_vs_window_update'].iloc[-1]:+.3f}).",
                )
            )
    for job, group in runs.sort_values("started_at", ascending=False).groupby("job"):
        last = group["status"].head(failures).tolist()
        if len(last) == failures and all(s == "failed" for s in last):
            alerts.append(
                Alert(
                    f"job-{job}",
                    f"Job failing: {job} failed its last {failures} runs",
                    f"The last {failures} `{job}` runs ended in status failed (newest {group['started_at'].iloc[0]}). "
                    "Details are in `aq.job_runs.details` for those runs.",
                )
            )
    return alerts


def open_or_refresh_issue(alert: Alert, repo: str, token: str, label: str = ISSUE_LABEL) -> str:
    """Open an issue for ``alert`` or comment on the open one with the same key. Returns "opened" or "refreshed"."""
    base = f"https://api.github.com/repos/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    def call(method: str, url: str, payload: dict | None = None) -> object:
        request = urllib.request.Request(
            url, data=None if payload is None else json.dumps(payload).encode(), headers=headers, method=method
        )
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https GitHub API URL
            return json.loads(response.read() or b"null")

    marker = f"[{alert.key}]"
    open_issues = call("GET", f"{base}/issues?state=open&labels={label}&per_page=100")
    existing = next((i for i in open_issues if marker in i["title"]), None)
    if existing:
        call("POST", f"{base}/issues/{existing['number']}/comments", {"body": alert.body})
        return "refreshed"
    call("POST", f"{base}/issues", {"title": f"{alert.title} {marker}", "body": alert.body, "labels": [label]})
    return "opened"


# --------------------------------------------------------------------------- store and job
class ScoreStore(Store):
    def matured(self, run_type: str, now: pd.Timestamp) -> pd.DataFrame:
        self._cur.execute(SELECT_MATURED, (run_type, now.to_pydatetime()))
        columns = [c.name for c in self._cur.description]
        return pd.DataFrame(self._cur.fetchall(), columns=columns)

    def insert_scores(self, scores: pd.DataFrame) -> int:
        from psycopg2.extras import execute_values

        def cell(value: object) -> object:
            return None if value is None or (isinstance(value, float) and np.isnan(value)) else value

        values = [
            (
                int(r.forecast_id),
                int(r.station_id),
                int(r.horizon),
                r.target,
                r.target_time.to_pydatetime() if hasattr(r.target_time, "to_pydatetime") else r.target_time,
                float(r.actual),
                float(r.abs_err),
                float(r.abs_err_persistence),
                cell(r.abs_err_window_update),
                None,
                None if r.severe_actual is None else bool(r.severe_actual),
            )
            for r in scores.itertuples()
        ]
        return len(execute_values(self._cur, INSERT_SCORES, values, page_size=500, fetch=True)) if values else 0

    def scores_since(self, run_type: str, since: pd.Timestamp) -> pd.DataFrame:
        self._cur.execute(SELECT_SCORES, (run_type, since.to_pydatetime()))
        columns = [c.name for c in self._cur.description]
        frame = pd.DataFrame(self._cur.fetchall(), columns=columns)
        return frame

    def upsert_skill(self, rows: list[tuple]) -> int:
        from psycopg2.extras import execute_values

        if rows:
            execute_values(self._cur, UPSERT_SKILL, rows, page_size=500)
        return len(rows)

    def skill_history(self, since: pd.Timestamp) -> pd.DataFrame:
        self._cur.execute(SELECT_SKILL, (WINDOW_DAYS, since.date()))
        return pd.DataFrame(
            self._cur.fetchall(),
            columns=["horizon", "target", "window_end", "skill_mae", "skill_vs_window_update", "n"],
        )

    def recent_runs(self) -> pd.DataFrame:
        self._cur.execute(SELECT_RECENT_RUNS, (["ingest", "forecast", "score"],))
        return pd.DataFrame(self._cur.fetchall(), columns=["job", "status", "started_at"])


def run(
    store: ScoreStore, now: pd.Timestamp, run_type: str = "live", issues: bool = False, repo: str = "", token: str = ""
) -> dict:
    run_id = store.start_run("score", run_type)
    details: dict = {"run_type": run_type}
    written, error, status = 0, None, "failed"
    try:
        matured = store.matured(run_type, now)
        scores = score_frame(matured)
        written = store.insert_scores(scores)
        details["matured"], details["scored"] = len(matured), written
        window_start = now - pd.Timedelta(days=2 * WINDOW_DAYS)
        history = store.scores_since(run_type, window_start)
        if len(history) and run_type == "live":  # replays are reported from files, not the rolling table
            history = history.assign(abs_err_window_update=history["abs_err_window_update"].astype(float))
            end = pd.Timestamp(now).tz_convert(KST).normalize().tz_localize(None)
            for offset in range(WINDOW_DAYS):
                store.upsert_skill(rolling_rows(history, end - pd.Timedelta(days=offset)))
        if issues and run_type == "live":
            alerts = evaluate_alerts(store.skill_history(now - pd.Timedelta(days=WINDOW_DAYS)), store.recent_runs())
            details["alerts"] = [a.key for a in alerts]
            details["issues"] = {a.key: open_or_refresh_issue(a, repo, token) for a in alerts}
        status = "success"
    except Exception as exc:  # record a short, key-free message and re-raise
        store.finish_run(run_id, "failed", written, type(exc).__name__, details)
        raise
    store.finish_run(run_id, status, written, error, details)
    return {"status": status, "scored": written, "details": details}


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-type", choices=["live", "replay"], default="live")
    parser.add_argument("--issues", action="store_true", help="open/refresh GitHub issues for alerts (live only)")
    args = parser.parse_args(argv)
    with ScoreStore() as store:
        result = run(
            store,
            pd.Timestamp.now(tz=KST),
            args.run_type,
            args.issues,
            os.environ.get("GITHUB_REPOSITORY", ""),
            os.environ.get("GITHUB_TOKEN", ""),
        )
    log.info("status=%s scored=%s details=%s", result["status"], result["scored"], result["details"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
