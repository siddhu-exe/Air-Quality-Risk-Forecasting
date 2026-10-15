"""WAQI shadow mode: conversion, partial failure, offset detection, and the isolation guarantees. No network, no database."""

import numpy as np
import pandas as pd
import pytest

from src.live import shadow_compare, waqi_shadow
from src.live.epa_aqi import from_aqi
from src.live.sources import waqi

FEED = {
    "idx": 2553,
    "time": {"iso": "2026-10-15T15:00:00+05:30"},
    "iaqi": {"pm25": {"v": 173}, "pm10": {"v": 120}, "t": {"v": 25}, "o3": {"v": 40}},
}


def test_a_feed_becomes_a_shadow_row_with_back_converted_concentrations():
    row = waqi_shadow.feed_row("Anand Vihar", FEED)
    assert row["ts"] == pd.Timestamp("2026-10-15 15:00", tz="Asia/Kolkata") and row["waqi_time"] == row["ts"]
    assert row["pm25"] == pytest.approx(
        float(from_aqi("pm25", [173])[0]), abs=1e-9
    )  # AQI 173 <-> 100 ug/m3 on WAQI's scale
    assert np.isnan(row["no2"]) and np.isnan(row["co"])  # pollutants the feed does not carry stay empty
    assert row["raw_iaqi"] == {"pm25": 173.0, "pm10": 120.0, "o3": 40.0}  # weather keys (t) are not pollutants


def test_the_feed_time_is_floored_to_the_hour_label():
    feed = {**FEED, "time": {"iso": "2026-10-15T15:40:00+05:30"}}
    row = waqi_shadow.feed_row("ITO", feed)
    assert row["ts"].minute == 0 and row["waqi_time"].minute == 40


def test_one_failing_station_does_not_stop_the_others_and_no_token_is_recorded():
    token = "SECRET-TOKEN-123"

    def fetch(uid, key):
        if uid == waqi.MAPPING["Bawana"][0]:
            raise OSError(f"https://api.waqi.info/feed/@{uid}/?token={key} timed out")
        return FEED

    rows, errors = waqi_shadow.fetch_rows(token, fetch)
    assert len(rows) == len(waqi.MAPPING) - 1 and errors == {"Bawana": "OSError"}
    assert token not in str(errors)


def pair(offset_hours, n=48, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    hours = pd.date_range("2026-10-01", periods=n, freq="h")
    truth = pd.Series(rng.uniform(50, 300, n), index=hours)
    primary = pd.DataFrame({"station_id": 6, "ts": hours, **{p: truth.to_numpy() for p in waqi.POLLUTANTS}})
    shifted = truth.shift(-offset_hours).dropna()  # shadow hour S carries the primary value of hour S + offset
    shadow = pd.DataFrame(
        {
            "station_id": 6,
            "ts": shifted.index,
            **{p: shifted.to_numpy() + noise * rng.standard_normal(len(shifted)) for p in waqi.POLLUTANTS},
        }
    )
    return shadow, primary


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_the_comparison_finds_the_hour_offset_between_the_sources(offset):
    shadow, primary = pair(offset)
    best = shadow_compare.best_lag(shadow_compare.compare(shadow, primary))
    assert set(best.lag_hours) == {offset} and (best.mae < 1e-9).all()


def test_noise_shows_up_as_error_and_thin_overlap_is_not_summarised():
    shadow, primary = pair(0, noise=20.0)
    table = shadow_compare.compare(shadow, primary)
    zero = table[table.lag_hours == 0]
    assert (zero.mae > 5).all() and (zero["corr"] < 1).all() and set(zero.pollutant) == set(waqi.POLLUTANTS)
    assert shadow_compare.compare(shadow.head(5), primary).empty


def test_the_shadow_table_is_isolated_from_forecasts_and_the_api():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    migration = (root / "db/migrations/009_shadow_readings.sql").read_text()
    code = "\n".join(line for line in migration.splitlines() if not line.lstrip().startswith("--"))
    assert "revoke all on aq.shadow_readings from public, anon, authenticated, api_readonly" in code
    assert "to api_readonly" not in code and "grant select, insert, update on aq.shadow_readings to job_writer" in code
    assert "enable row level security" in code
    # no reader of live data mentions the shadow table
    for module in (
        "src/live/forecast.py",
        "src/live/forecast_store.py",
        "src/live/score.py",
        "backend/app/repository.py",
        "backend/app/service.py",
    ):
        assert "shadow_readings" not in (root / module).read_text(), module
    assert (
        "'openaq'" in waqi_shadow.SELECT_PRIMARY
        and "delete" not in (waqi_shadow.UPSERT_SHADOW + waqi_shadow.SELECT_SHADOW).lower()
    )


def test_the_shadow_workflow_runs_hourly_and_only_reads_the_waqi_token():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".github/workflows/shadow-waqi.yml").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert 'cron: "20 * * * *"' in code and "WAQI_API_TOKEN" in code and "python -m src.live.waqi_shadow" in code
    assert "DATABASE_URL_READONLY" not in code and "contents: read" in code
