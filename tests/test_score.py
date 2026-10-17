"""Scoring, rolling skill and alert rules on synthetic data: no database, no network."""

import json

import numpy as np
import pandas as pd
import pytest

from src.live import score

T0 = pd.Timestamp("2026-09-01 00:00", tz="Asia/Kolkata")


def matured(n=60, target="aqi", model_err=1.0, persistence_err=2.0, wu_err=1.5, seed=0):
    rng = np.random.default_rng(seed)
    times = [T0 + pd.Timedelta(hours=int(h)) for h in rng.integers(0, 24 * 30, n)]
    actual = rng.uniform(80, 300, n)
    return pd.DataFrame(
        {
            "forecast_id": np.arange(n),
            "station_id": rng.choice([3, 6], n),
            "horizon": 6,
            "target": target,
            "target_time": times,
            "actual": actual,
            "y_hat": actual + model_err * rng.choice([-1, 1], n),
            "y_persistence": actual + persistence_err * rng.choice([-1, 1], n),
            "y_window_update": actual + wu_err * rng.choice([-1, 1], n) if target == "aqi" else np.nan,
        }
    )


def test_errors_use_the_stored_references_and_drop_rows_without_an_actual():
    frame = matured(10)
    frame.loc[0, "actual"] = np.nan
    scored = score.score_frame(frame)
    assert len(scored) == 9 and scored.abs_err.eq(1.0).all() and scored.abs_err_persistence.eq(2.0).all()
    assert scored.abs_err_window_update.eq(1.5).all()


def test_pm25_rows_have_no_window_update_error_and_no_severe_flag():
    scored = score.score_frame(matured(10, target="pm25"))
    assert scored.abs_err_window_update.isna().all() and scored.severe_actual.isna().all()
    aqi = score.score_frame(matured(10))
    assert aqi.severe_actual.isin([True, False]).all()


def test_skill_is_one_minus_the_mae_ratio_against_each_reference():
    table = score.product_skill(score.score_frame(matured()), n_boot=50)
    row = table.iloc[0]
    assert row.skill_vs_persistence == pytest.approx(1 - 1.0 / 2.0)
    assert row.skill_vs_window_update == pytest.approx(1 - 1.0 / 1.5)
    assert row.skill_vs_persistence_lo <= row.skill_vs_persistence <= row.skill_vs_persistence_hi
    pm25 = score.product_skill(score.score_frame(matured(target="pm25")), n_boot=50).iloc[0]
    assert "skill_vs_window_update" not in pm25.index or pd.isna(pm25.get("skill_vs_window_update"))


def test_rolling_rows_pool_and_split_by_station_and_skip_thin_windows():
    scored = score.score_frame(matured(200))
    rows = score.rolling_rows(scored, pd.Timestamp("2026-09-30"))
    pooled = [r for r in rows if r[0] is None]
    assert len(pooled) == 1 and pooled[0][5] == 200
    assert pooled[0][8] == pytest.approx(0.5) and pooled[0][10] == pytest.approx(1 - 1.0 / 1.5)
    assert {r[0] for r in rows} == {None, 3, 6}
    assert score.rolling_rows(score.score_frame(matured(10)), pd.Timestamp("2026-09-30")) == []


def history(skill_values, vs_wu=None, horizon=6, target="aqi"):
    days = pd.date_range("2026-10-01", periods=len(skill_values)).date
    return pd.DataFrame(
        {
            "horizon": horizon,
            "target": target,
            "window_end": days,
            "skill_mae": skill_values,
            "skill_vs_window_update": vs_wu if vs_wu is not None else skill_values,
            "n": 500,
        }
    )


def runs(*statuses, job="forecast"):
    return pd.DataFrame(
        {"job": job, "status": statuses, "started_at": pd.date_range("2026-10-01", periods=len(statuses))[::-1]}
    )


def test_seven_negative_days_in_a_row_alert_and_a_recovery_resets_the_streak():
    assert score.evaluate_alerts(history([-0.1] * 7), runs("success"))[0].key == "skill-aqi-6h"
    assert score.evaluate_alerts(history([-0.1] * 6), runs("success")) == []
    assert score.evaluate_alerts(history([-0.1] * 5 + [0.02, -0.1]), runs("success")) == []
    assert score.evaluate_alerts(history([-0.1] * 6 + [np.nan]), runs("success")) == []


def test_a_model_worse_than_the_rule_alerts_even_when_it_beats_persistence():
    alerts = score.evaluate_alerts(history([0.2] * 7, vs_wu=[-0.05] * 7), runs("success"))
    assert [a.key for a in alerts] == ["skill-vs-rule-aqi-6h"]
    pm25 = score.evaluate_alerts(history([0.2] * 7, vs_wu=[-0.05] * 7, target="pm25"), runs("success"))
    assert pm25 == []  # PM2.5 has no window-update reference
    one_hour = score.evaluate_alerts(history([0.2] * 7, vs_wu=[-0.05] * 7, horizon=24), runs("success"))
    assert one_hour == []  # the rule is only a reference at 1h and 6h


def test_three_failed_runs_in_a_row_alert_per_job():
    assert score.evaluate_alerts(history([0.1] * 7), runs("failed", "failed", "failed"))[0].key == "job-forecast"
    assert score.evaluate_alerts(history([0.1] * 7), runs("failed", "failed", "success")) == []
    assert score.evaluate_alerts(history([0.1] * 7), runs("failed", "failed")) == []


def test_stale_runs_never_raise_an_alert():
    """A lagging source makes ingest and forecast record 'stale' every hour; that is a data condition, not a failing job."""
    nothing_scored = history([0.1]).iloc[0:0]  # no forecasts issued yet, so no skill rows
    for job in ("ingest", "forecast"):
        assert score.evaluate_alerts(nothing_scored, runs(*["stale"] * 24, job=job)) == []
    assert score.evaluate_alerts(history([0.1] * 7), runs("stale", "stale", "stale")) == []
    # 'stale' is not 'failed': it also breaks a streak of failures, so only three real failures in a row alert
    assert score.evaluate_alerts(history([0.1] * 7), runs("failed", "stale", "failed", "failed")) == []
    assert (
        score.evaluate_alerts(history([0.1] * 7), runs("failed", "failed", "failed", "stale"))[0].key == "job-forecast"
    )


def test_issue_is_opened_once_and_then_refreshed(monkeypatch):
    calls = []

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def read(self):
            return json.dumps(self.payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    existing = []

    def fake_urlopen(request, timeout):
        calls.append((request.get_method(), request.full_url))
        if request.get_method() == "GET":
            return Response(existing)
        if request.full_url.endswith("/issues"):
            existing.append({"number": 5, "title": json.loads(request.data)["title"]})
        return Response({})

    monkeypatch.setattr(score.urllib.request, "urlopen", fake_urlopen)
    alert = score.Alert("skill-aqi-6h", "Model health: AQI 6h", "body")
    assert score.open_or_refresh_issue(alert, "o/r", "token") == "opened"
    assert score.open_or_refresh_issue(alert, "o/r", "token") == "refreshed"
    assert ("POST", "https://api.github.com/repos/o/r/issues/5/comments") in calls


def test_sql_is_insert_only_and_scores_only_matured_forecasts_with_an_actual():
    for text in (score.SELECT_MATURED, score.INSERT_SCORES, score.UPSERT_SKILL, score.SELECT_SCORES):
        assert "delete" not in text.lower() and "truncate" not in text.lower()
    assert "on conflict (forecast_id) do nothing" in score.INSERT_SCORES and "returning 1" in score.INSERT_SCORES
    assert (
        "target_time + interval '1 hour' <= %s" in score.SELECT_MATURED
        and "s.forecast_id is null" in score.SELECT_MATURED
    )
    assert "run_type = %s" in score.SELECT_MATURED


def test_score_workflow_runs_nightly_as_a_live_run_with_issues_on():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".github/workflows/score.yml").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert 'cron: "40 20 * * *"' in code and "workflow_dispatch" in code
    assert "inputs.run_type || 'live'" in code and "github.event_name == 'schedule' || inputs.open_issues" in code
    assert "issues: write" in code and "python -m src.live.score" in code
