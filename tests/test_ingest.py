"""Ingest flow and weather fill with a fake store and fake sources. Mocked only: no network, no database."""
import numpy as np
import pandas as pd
import pytest

from src.live import ingest, store
from src.live import weather as wx
from src.live.config import IngestConfig
from src.live.sources.base import SOURCE_COLUMNS, LiveSource, SourceUnavailable

STATIONS = ["Anand Vihar", "Bawana", "Dwarka-Sector 8", "ITO", "Jahangirpuri", "Punjabi Bagh", "R K Puram"]
NOW = pd.Timestamp("2026-10-11 14:10", tz="Asia/Kolkata")     # newest complete hour label: 13:00


def synthetic(hours, stations=STATIONS, **overrides):
    rows = []
    for station in stations:
        for hour in hours:
            row = {"station_name": station, "hour": hour, "pm25": 120.0, "pm10": 200.0, "no2": 40.0, "so2": 8.0, "co": 1.2, "o3": 30.0,
                   "nox": 60.0, "nh3": np.nan, "temperature": np.nan if station == "ITO" else 30.0, "humidity": np.nan if station == "ITO" else 50.0,
                   "wind_speed": np.nan if station == "ITO" else 1.5, "solar_radiation": np.nan}
            row.update(overrides)
            rows.append(row)
    return pd.DataFrame(rows, columns=SOURCE_COLUMNS)


def make_source(frame=None, *, error=None, verified=True, name="openaq", tag="openaq", flags=None):
    """A LiveSource subclass (a class, as the registry factory returns instances of it)."""
    class Fake(LiveSource):
        def fetch(self, start, end):
            if error:
                raise error
            return frame[(frame.hour >= start) & (frame.hour <= end)] if frame is not None else self.empty()

        def station_flags(self, station):
            return (flags or {}).get(station, {})

    Fake.name, Fake.tag, Fake.verified, Fake.missing = name, tag, verified, {}
    return Fake


class FakeStore:
    def __init__(self, history=None):
        self.runs, self.readings, self.aqi, self.history = {}, [], [], history
        self._next = 0

    def start_run(self, job):
        self._next += 1
        self.runs[self._next] = {"job": job, "status": "running"}
        return self._next

    def finish_run(self, run_id, status, rows, error, details):
        self.runs[run_id].update(status=status, rows=rows, error=error, details=details)

    def upsert_readings(self, readings):
        self.readings.append(readings)
        return len(readings)

    def recent_pollutants(self, station_ids, since):
        if self.history is not None:
            return self.history
        return store.NullStore().recent_pollutants(station_ids, since)

    def upsert_aqi(self, aqi):
        self.aqi.append(aqi)
        return len(aqi)

    @property
    def last_run(self):
        return self.runs[max(self.runs)]


def weather_stub():
    hours = pd.date_range("2026-10-09", "2026-10-12", freq="h")
    return pd.DataFrame([{"station_name": s, "hour": h, "temperature": 25.0, "humidity": 60.0, "wind_speed": 2.0, "solar_radiation": 300.0}
                         for s in STATIONS for h in hours])


def cfg(**kw):
    return IngestConfig(**{"source": "openaq", "weather_fill": "none", **kw})


def hours(n=6):
    end = pd.Timestamp("2026-10-11 13:00")
    return pd.date_range(end - pd.Timedelta(hours=n - 1), end, freq="h")


def run(frame, config=None, st=None, **kw):
    st = st or FakeStore()
    source = make_source(frame, **kw)
    result = ingest.run(config or cfg(), st, now=NOW, factory=lambda name: source(), weather_fetch=weather_stub)
    return result, st


# ------------------------------------------------------------------ outcomes
def test_all_stations_fresh_is_success_and_everything_is_written_and_logged():
    result, st = run(synthetic(hours()))
    assert result["status"] == "success" and result["rows"] == 7 * 6
    assert st.last_run["status"] == "success" and st.last_run["job"] == "ingest"
    assert st.last_run["details"]["source_used"] == "openaq" and len(st.last_run["details"]["fresh_stations"]) == 7
    assert set(st.readings[0].source) == {"openaq"} and st.readings[0].qc_flags.map(dict).notna().all()


def test_a_stale_station_makes_the_run_partial_and_a_fully_stale_feed_makes_it_failed():
    fresh = synthetic(hours(), stations=STATIONS[:-1])
    old = synthetic(pd.date_range("2026-10-11 05:00", "2026-10-11 07:00", freq="h"), stations=["R K Puram"])
    result, st = run(pd.concat([fresh, old]))
    assert result["status"] == "partial" and "R K Puram" in st.last_run["details"]["stale_stations"]
    result, st = run(synthetic(pd.date_range("2026-10-11 05:00", "2026-10-11 07:00", freq="h")))
    assert result["status"] == "failed"                         # OpenAQ frozen at an old time: fail loudly, do not call it success
    assert len(st.last_run["details"]["fresh_stations"]) == 0 if "fresh_stations" in st.last_run["details"] else True


def test_station_with_no_rows_at_all_counts_as_stale():
    result, st = run(synthetic(hours(), stations=STATIONS[:-1]))
    assert result["status"] == "partial" and st.last_run["details"]["stale_stations"]["R K Puram"] is None


def test_age_is_measured_to_the_end_of_the_hour():
    status, info = ingest.classify(synthetic(hours()).set_index("hour").assign(), NOW, 3.0) if False else (None, None)
    rows = synthetic([pd.Timestamp("2026-10-11 13:00")]).set_index("hour")
    status, info = ingest.classify(rows, NOW, 3.0)
    assert info["age_hours"]["Bawana"] == pytest.approx(10 / 60, abs=0.01)        # hour 13:00 ended at 14:00; now 14:10


# ------------------------------------------------------------------ source switching and failures
def test_the_fallback_is_used_only_when_the_primary_fails():
    primary = make_source(error=SourceUnavailable("primary down"), name="data_gov_in", tag="data.gov.in")
    backup = make_source(synthetic(hours()))
    result = ingest.run(cfg(source="data_gov_in", fallback="openaq"), (st := FakeStore()), now=NOW,
                        factory=lambda n: (primary if n == "data_gov_in" else backup)())
    assert result["status"] == "success" and result["details"]["source_used"] == "openaq"
    assert any("fallback 'openaq' used" in n for n in result["details"]["notes"])


def test_the_fallback_is_not_touched_when_the_primary_works():
    called = []
    backup = make_source(synthetic(hours()))
    primary = make_source(synthetic(hours()), name="data_gov_in", tag="data.gov.in")
    ingest.run(cfg(source="data_gov_in", fallback="openaq", allow_unverified=True), FakeStore(), now=NOW,
               factory=lambda n: called.append(n) or (primary if n == "data_gov_in" else backup)())
    assert called == ["data_gov_in"]


def test_both_sources_down_fails_with_a_message_and_writes_nothing():
    down = lambda: make_source(error=SourceUnavailable("nope"))()
    result = ingest.run(cfg(fallback="data_gov_in", allow_unverified=True), (st := FakeStore()), now=NOW, factory=lambda n: down())
    assert result["status"] == "failed" and st.readings == [] and "nope" in result["error"]
    assert st.last_run["status"] == "failed"


def test_an_unverified_source_is_refused_unless_explicitly_allowed():
    frame = synthetic(hours(), nox=np.nan)
    result, st = run(frame, cfg(source="data_gov_in"), verified=False, name="data_gov_in", tag="data.gov.in")
    assert result["status"] == "failed" and "not verified" in result["error"] and st.readings == []
    result, st = run(frame, cfg(source="data_gov_in", allow_unverified=True), verified=False, name="data_gov_in", tag="data.gov.in")
    assert result["status"] == "success" and set(st.readings[0].source) == {"data.gov.in"}


def test_a_probable_unit_change_fails_the_run_and_nothing_is_written():
    result, st = run(synthetic(hours(), nox=150000.0))
    assert result["status"] == "failed" and "unit or scale change" in result["error"] and st.readings == []


def test_isolated_sentinels_are_nullified_not_fatal():
    frame = synthetic(hours())
    frame.loc[3, "pm25"] = -9999
    result, st = run(frame)
    assert result["status"] == "success"
    written = st.readings[0]
    assert written.pm25.isna().sum() == 1 and st.last_run["details"]["qc_flagged_cells"] == {"pm25": 1}


def test_unexpected_errors_are_recorded_then_raised():
    class Boom(FakeStore):
        def upsert_readings(self, readings):
            raise RuntimeError("db exploded")
    st = Boom()
    with pytest.raises(RuntimeError):
        ingest.run(cfg(), st, now=NOW, factory=lambda n: make_source(synthetic(hours()))(), weather_fetch=weather_stub)
    assert st.last_run["status"] == "failed" and st.last_run["error"] == "RuntimeError"


# ------------------------------------------------------------------ weather fill
def test_weather_gaps_are_filled_from_open_meteo_and_marked():
    result, st = run(synthetic(hours()), cfg(weather_fill="open-meteo"))
    rows = st.readings[0]
    ito = rows[rows.station_name == "ITO"]
    assert (ito.temperature == 25.0).all() and (ito.weather_source == "open-meteo").all()
    assert all(f.get("temperature") == "filled:open-meteo" for f in ito.qc_flags)
    bawana = rows[rows.station_name == "Bawana"]
    assert (bawana.temperature == 30.0).all()                               # station sensor values are never replaced
    assert (bawana.solar_radiation == 300.0).all() and (bawana.weather_source == "mixed").all()
    assert st.last_run["details"]["weather"] == "open-meteo"


def test_weather_fill_can_be_switched_off():
    result, st = run(synthetic(hours()), cfg(weather_fill="none"))
    rows = st.readings[0]
    assert rows.solar_radiation.isna().all() and rows[rows.station_name == "ITO"].weather_source.isna().all()


def test_a_weather_outage_does_not_fail_the_ingest():
    def down():
        raise RuntimeError("open-meteo 429")
    st = FakeStore()
    result = ingest.run(cfg(weather_fill="open-meteo"), st, now=NOW, factory=lambda n: make_source(synthetic(hours()))(), weather_fetch=down)
    assert result["status"] == "success" and result["details"]["weather"].startswith("unavailable")


def test_open_meteo_request_asks_for_wind_in_metres_per_second_and_uses_the_retry_helper():
    seen = []

    class Resp:
        def json(self): return {"hourly": {"time": ["2026-10-11T12:00", "2026-10-11T13:00"], "temperature_2m": [30.0, 31.0],
                                           "relative_humidity_2m": [50, 49], "wind_speed_10m": [2.0, 2.5], "shortwave_radiation": [400.0, 380.0]}}

    def fake_get(url, params, **kw):
        seen.append((url, params, kw))
        return Resp()
    frame = wx.fetch_recent({"ITO": (28.6, 77.2), "Bawana": (28.7, 77.0)}, get=fake_get, sleep=lambda s: None)
    assert len(seen) == 2 and seen[0][0] == wx.FORECAST_URL
    assert seen[0][1]["wind_speed_unit"] == "ms" and seen[0][1]["past_days"] == 3 and seen[0][1]["timezone"] == "Asia/Kolkata"
    assert seen[0][2]["max_attempts"] == 3
    assert set(frame.columns) == {"station_name", "hour", "temperature", "humidity", "wind_speed", "solar_radiation"} and len(frame) == 4


# ------------------------------------------------------------------ AQI and the store
def test_aqi_is_recomputed_from_stored_history_plus_the_new_rows():
    history_hours = pd.date_range("2026-10-09 12:00", "2026-10-11 07:00", freq="h")
    hist = synthetic(history_hours, nh3=5.0).drop(columns=["nox", "temperature", "humidity", "wind_speed", "solar_radiation"])
    hist["station_id"] = hist.station_name.map({s: i for s, i in ingest.STATION_IDS.items()})
    st = FakeStore(history=hist.drop(columns="station_name"))
    result, st = run(synthetic(hours()), st=st)
    assert result["details"]["aqi_rows"] > 0 and st.aqi[0].aqi.between(0, 500).all()
    assert st.aqi[0].hour.min() >= pd.Timestamp("2026-10-11 08:00")        # only the fetched window is re-written


def test_dry_run_store_touches_nothing():
    result, _ = run(synthetic(hours()), st=store.NullStore())
    assert result["status"] == "success" and result["rows"] == 42


def test_store_sql_refreshes_only_rows_of_the_same_source_and_never_deletes():
    sql = store.UPSERT_READINGS_SAME_SOURCE.lower()
    assert "on conflict (station_id, ts) do update" in sql and "where aq.live_readings.source = excluded.source" in sql
    assert "delete" not in sql and "delete" not in store.UPSERT_AQI.lower()


def test_main_exit_code_follows_the_run_status(monkeypatch):
    for status, code in (("success", 0), ("partial", 0), ("failed", 1)):
        monkeypatch.setattr(ingest, "run", lambda cfg, st, status=status: {"status": status, "rows": 0, "error": None, "details": {}})
        assert ingest.main(["--dry-run"]) == code


def test_a_scale_error_at_one_station_is_nullified_and_flagged_but_does_not_fail_the_run():
    frame = synthetic(hours())
    frame.loc[frame.station_name == "Bawana", "nox"] = 150000.0         # 6 of 42 values: a sensor problem, not a source-wide change
    result, st = run(frame)
    assert result["status"] == "success"
    rows = st.readings[0]
    assert rows[rows.station_name == "Bawana"].nox.isna().all() and rows[rows.station_name != "Bawana"].nox.notna().all()
    assert st.last_run["details"]["qc_flagged_cells"]["nox"] == 6
