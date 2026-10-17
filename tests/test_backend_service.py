"""API response rules on a fake repository: no database, no web framework."""

from datetime import UTC, datetime, timedelta

import pytest

from backend.app import cpcb
from backend.app.service import NotFound, Service
from backend.app.settings import Settings

NOW = datetime(2026, 10, 15, 12, 30, tzinfo=UTC)
ISSUE = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
STATIONS = {3: "Anand Vihar", 6: "ITO"}


class FakeRepo:
    def __init__(self, **over):
        self.data = {
            "newest_reading": ISSUE,
            "aqi": {3: 250.0, 6: 320.0},
            "aqi_ts": {3: ISSUE, 6: ISSUE},
            "forecasts": [],
            "run": {"details": {}},
            "skill": [],
            "ping": True,
            **over,
        }

    def stations(self):
        return [
            {"station_id": i, "station_name": n, "latitude": 28.6, "longitude": 77.2, "coords_approximate": True}
            for i, n in STATIONS.items()
        ]

    def latest_aqi(self):
        return {i: {"station_id": i, "ts": self.data["aqi_ts"][i], "aqi": v} for i, v in self.data["aqi"].items()}

    def latest_readings(self):
        return {
            3: {
                "station_id": 3,
                "ts": ISSUE,
                "pm25": 120.0,
                "pm10": 200.0,
                "co": 1.2,
                "temperature": 25.0,
                "humidity": None,
                "wind_speed": None,
                "solar_radiation": None,
            }
        }

    def latest_pm25(self):
        return {3: {"station_id": 3, "ts": ISSUE, "pm25": 120.0}}

    def history(self, station_id, target, since):
        return [(ISSUE - timedelta(hours=h), 100.0 + h) for h in (2, 1, 0)]

    def latest_forecasts(self, since):
        return self.data["forecasts"]

    def latest_run(self):
        return self.data["run"]

    def skill(self, since):
        return self.data["skill"]

    def jobs(self):
        return [{"job": "forecast", "status": "success", "last_run_at": ISSUE}]

    def hourly_presence(self, since):
        return {3: {since + timedelta(hours=h) for h in range(0, 24, 2)}}

    def forecast_station_hours(self, since):
        return 12

    def registry(self):
        return [
            {
                "model_version": "aqi-6h-lgb-live-v1",
                "model_name": "LightGBM",
                "horizon": 6,
                "target": "aqi",
                "sha256": "ab" * 32,
            }
        ]

    def ingest_runs(self, since):
        return self.data.get("ingest_runs", [])

    def newest_reading(self):
        return self.data["newest_reading"]

    def newest_forecast(self):
        return ISSUE

    def ping(self):
        if not self.data["ping"]:
            raise RuntimeError("down")
        return True


def row(station, key, y_hat, issue=ISSUE):
    target, horizon = key.split("_")
    hours = int(horizon[:-1])
    return {
        "station_id": station,
        "horizon": hours,
        "target": target,
        "issue_time": issue,
        "target_time": issue + timedelta(hours=hours),
        "y_hat": y_hat,
        "y_persistence": 250.0,
        "y_window_update": 240.0 if target == "aqi" else None,
        "model_version": f"{key}-v1",
    }


def service(repo, tmp_path=None):
    return Service(repo, Settings(), lambda: NOW, tmp_path or Service.__init__.__defaults__[0])


def forecast_of(overview, station_name, product):
    station = next(s for s in overview.stations if s.name == station_name)
    return next(f for f in station.forecasts if f.product == product)


def test_categories_and_grap_bands():
    assert cpcb.category(50) == "Good" and cpcb.category(200) == "Moderate" and cpcb.category(201) == "Poor"
    assert cpcb.category(400) == "Very Poor" and cpcb.category(401) == "Severe"
    assert [cpcb.grap_stage(v) for v in (200, 201, 300, 301, 400, 401, 450, 451, 500)] == [
        None,
        "I",
        "I",
        "II",
        "II",
        "III",
        "III",
        "IV",
        "IV",
    ]


def test_a_forecast_carries_its_frozen_references():
    repo = FakeRepo(forecasts=[row(3, "aqi_6h", 300.0), row(3, "aqi_1h", 251.0), row(3, "pm25_6h", 150.0)])
    overview = service(repo).overview()
    six = forecast_of(overview, "Anand Vihar", "aqi_6h")
    assert six.status == "ok" and six.value == 300.0 and six.persistence == 250.0 and six.window_update == 240.0
    assert six.category == "Poor" and six.model_version == "aqi_6h-v1" and six.kind == "model"
    one = forecast_of(overview, "Anand Vihar", "aqi_1h")
    assert one.kind == "rule" and "24h-window update" in one.label
    pm = forecast_of(overview, "Anand Vihar", "pm25_6h")
    assert pm.window_update is None and pm.category is None


def test_the_24h_aqi_forecast_is_labelled_experimental():
    repo = FakeRepo(forecasts=[row(3, "aqi_24h", 260.0)])
    day = forecast_of(service(repo).overview(), "Anand Vihar", "aqi_24h")
    assert day.experimental and "about as accurate as assuming no change" in day.label and day.persistence == 250.0


def test_a_station_without_a_forecast_says_why_never_a_blank_or_a_number():
    details = {
        "skipped": {"ITO": "stale: newest reading is 5.2 h older than the issue hour (limit 3 h)"},
        "skipped_products": {"Anand Vihar/pm25_1h": "no current pm25 value at the issue hour"},
    }
    repo = FakeRepo(
        forecasts=[
            row(3, "aqi_6h", 300.0),
            row(3, "aqi_1h", 251.0),
            row(3, "aqi_24h", 260.0),
            row(3, "pm25_6h", 150.0),
        ],
        run={"details": details},
    )
    overview = service(repo).overview()
    ito = forecast_of(overview, "ITO", "aqi_6h")
    assert ito.status == "unavailable" and ito.value is None and ito.reason.startswith("stale")
    dropped = forecast_of(overview, "Anand Vihar", "pm25_1h")
    assert dropped.status == "unavailable" and dropped.reason == "no current pm25 value at the issue hour"
    unexplained = forecast_of(service(FakeRepo(forecasts=[row(3, "aqi_6h", 300.0)])).overview(), "ITO", "aqi_6h")
    assert unexplained.status == "unavailable" and "no forecast was issued" in unexplained.reason
    assert overview.network.stations_forecast == 1


def test_a_forecast_from_an_older_run_is_not_shown_as_current():
    old = row(6, "aqi_6h", 310.0, issue=ISSUE - timedelta(hours=1))
    overview = service(FakeRepo(forecasts=[row(3, "aqi_6h", 300.0), old])).overview()
    assert forecast_of(overview, "ITO", "aqi_6h").status == "unavailable"


def test_when_the_forecast_job_has_stopped_every_product_is_unavailable_with_that_reason():
    stale = ISSUE - timedelta(hours=9)
    overview = service(FakeRepo(forecasts=[row(3, "aqi_6h", 300.0, issue=stale)])).overview()
    first = forecast_of(overview, "Anand Vihar", "aqi_6h")
    assert first.status == "unavailable" and "has not run recently" in first.reason
    assert forecast_of(service(FakeRepo()).overview(), "ITO", "aqi_1h").reason.endswith(
        "no forecast has been issued yet)"
    )


def test_pm25_24h_is_withheld_by_policy():
    out = service(FakeRepo()).station_forecast("3", "pm25")
    assert [f.product for f in out.forecasts] == ["pm25_1h", "pm25_6h", "pm25_24h"]
    assert out.forecasts[2].status == "withheld" and out.forecasts[2].value is None
    assert [f.product for f in service(FakeRepo()).station_forecast("3", "aqi").forecasts] == [
        "aqi_1h",
        "aqi_6h",
        "aqi_24h",
    ]


def test_station_detail_has_history_pollutants_and_null_weather_when_absent():
    out = service(FakeRepo()).station_forecast("3", "aqi")
    assert [p.value for p in out.history] == [102.0, 101.0, 100.0]
    assert {p.key for p in out.pollutants} == {"pm25", "pm10", "co"} and out.weather is not None
    assert {p.key: p.unit for p in out.pollutants}["co"] == "mg/m³"
    with pytest.raises(NotFound):
        service(FakeRepo()).station_forecast("99", "aqi")
    with pytest.raises(NotFound):
        service(FakeRepo()).station_forecast("abc", "aqi")


def test_staleness_follows_the_newest_reading():
    fresh = service(FakeRepo()).overview()
    assert not fresh.stale and fresh.network.stations_with_data == 2 and fresh.network.mean_aqi_now == 285.0
    old = ISSUE - timedelta(hours=8)
    stale = service(FakeRepo(newest_reading=old, aqi_ts={3: old, 6: old})).overview()
    assert stale.stale and stale.network.stations_with_data == 0 and stale.network.mean_aqi_now is None
    assert all(s.now is not None and s.now.stale for s in stale.stations)


def test_health_degrades_instead_of_failing_when_the_database_is_down():
    ok = service(FakeRepo()).health()
    assert ok.status == "ok" and ok.jobs[0].job == "forecast"
    down = service(FakeRepo(ping=False)).health()
    assert down.status == "degraded" and down.stale and down.data_as_of is None


def test_grap_stage_is_indicative_and_uses_current_values_and_the_6h_model():
    repo = FakeRepo(forecasts=[row(3, "aqi_6h", 410.0), row(3, "aqi_24h", 380.0)])
    out = service(repo).grap()
    assert out.stage_indicated_now == "I" and out.network_mean_aqi_now == 285.0
    assert "not an official advisory" in out.disclaimer
    by_name = {s.name: s for s in out.stations}
    assert (
        by_name["Anand Vihar"].stage_now == "I"
        and by_name["Anand Vihar"].stage_6h == "III"
        and by_name["ITO"].stage_now == "II"
    )
    assert by_name["Anand Vihar"].forecast_24h == 380.0 and by_name["Anand Vihar"].persistence == 250.0
    assert by_name["ITO"].forecast_6h is None and by_name["ITO"].stage_6h is None
    assert [s.now_count for s in out.stages] == [1, 1, 0, 0] and [s.forecast_6h_count for s in out.stages] == [
        0,
        0,
        1,
        0,
    ]


def test_model_health_reports_both_references_and_freshness_flags():
    skill = [
        {
            "horizon": 6,
            "target": "aqi",
            "window_end": datetime(2026, 10, d).date(),
            "n": 300 + d,
            "skill_mae": 0.1 * d,
            "skill_vs_window_update": 0.05,
        }
        for d in (13, 14)
    ]
    out = service(FakeRepo(skill=skill)).model_health()
    six = next(s for s in out.skill if s.product == "aqi_6h")
    assert six.current_vs_persistence == pytest.approx(1.4) and six.current_vs_window_update == 0.05 and six.n == 314
    assert next(s for s in out.skill if s.product == "pm25_6h").current_vs_persistence is None
    assert next(s for s in out.skill if s.product == "pm25_1h").skill_vs_window_update == []
    anand = next(f for f in out.freshness if f.name == "Anand Vihar")
    assert len(anand.hourly) == 24 and any(anand.hourly) and not all(anand.hourly)
    ito = next(f for f in out.freshness if f.name == "ITO")
    assert ito.note == "no readings yet" and not any(ito.hourly)
    assert out.forecast_coverage == pytest.approx(12 / 48) and out.models[0].horizon == "6h"


def test_backtest_reads_the_report_files(tmp_path):
    (tmp_path / "modeling" / "live_retrain").mkdir(parents=True)
    (tmp_path / "modeling" / "live_retrain" / "window_update_baseline.csv").write_text(
        "horizon,split,n,wu_vs_persistence,wu_vs_persistence_lo,wu_vs_persistence_hi,model_vs_persistence,model_vs_persistence_lo,model_vs_persistence_hi,model_vs_window_update,model_vs_window_update_lo,model_vs_window_update_hi\n"
        "1h,test,100,0.55,0.5,0.6,0.34,0.3,0.4,-0.46,-0.5,-0.4\n"
        "6h,test,100,0.01,-0.1,0.1,0.30,0.24,0.35,0.30,0.24,0.35\n"
        "24h,test,100,-0.49,-0.6,-0.3,0.09,0.05,0.12,0.39,0.3,0.46\n"
        "1h,val,90,0.4,0.3,0.5,0.3,0.2,0.4,-0.3,-0.4,-0.2\n"
    )
    out = service(FakeRepo(), tmp_path).backtest()
    by = {e.product: e for e in out.evidence}
    assert (
        by["aqi_1h"].skill_vs_persistence == 0.55 and by["aqi_1h"].skill_vs_window_update is None
    )  # the rule is the reference
    assert by["aqi_6h"].skill_vs_window_update == 0.30 and by["aqi_24h"].skill_vs_window_update is None
    assert len(out.evidence) == 3 and service(FakeRepo(), tmp_path / "missing").backtest().evidence == []


def test_the_shipped_report_files_parse():
    out = service(FakeRepo()).backtest()
    products = {(e.product, e.window.split()[0]) for e in out.evidence}
    assert {("aqi_1h", "test"), ("aqi_6h", "test"), ("pm25_6h", "test"), ("aqi_6h", "replay")} <= products
    assert all(e.product != "pm25_24h" for e in out.evidence)


def test_model_health_reports_how_far_behind_the_source_is_per_day():
    runs = [
        {
            "started_at": datetime(2026, 10, 14, 9, 10, tzinfo=UTC),
            "status": "failed",
            "details": {"source_used": "openaq", "age_hours": {"A": 40.0, "B": 44.0, "C": 41.0}},
        },
        {
            "started_at": datetime(2026, 10, 14, 10, 10, tzinfo=UTC),
            "status": "failed",
            "details": {"source_used": "openaq", "age_hours": {"A": 39.0, "B": 43.0, "C": 40.0}},
        },
        {
            "started_at": datetime(2026, 10, 15, 9, 10, tzinfo=UTC),
            "status": "success",
            "details": {"source_used": "openaq", "age_hours": {"A": 1.0, "B": 2.0, "C": 1.5}},
        },
        {
            "started_at": datetime(2026, 10, 15, 10, 10, tzinfo=UTC),
            "status": "failed",
            "details": {},
        },  # nothing read: no lag sample
    ]
    lag = service(FakeRepo(ingest_runs=runs)).model_health().source_lag
    assert lag.source == "openaq" and [d.day for d in lag.daily] == ["2026-10-14", "2026-10-15"]
    assert lag.daily[0].median_hours == 40.5 and lag.daily[0].max_hours == 44.0 and lag.daily[0].runs == 2
    assert lag.daily[1].median_hours == 1.5 and lag.daily[1].runs == 1
    assert lag.newest_reading_at == ISSUE and lag.current_max_hours == pytest.approx(-0.5, abs=1.0)


def test_source_lag_is_empty_not_an_error_before_any_ingest_ran():
    lag = service(FakeRepo()).model_health().source_lag
    assert lag.daily == [] and lag.source is None


def test_a_stopped_forecast_job_still_shows_the_last_issued_forecast_marked_as_history():
    stale = ISSUE - timedelta(hours=9)
    overview = service(FakeRepo(forecasts=[row(3, "aqi_6h", 300.0, issue=stale)])).overview()
    f = forecast_of(overview, "Anand Vihar", "aqi_6h")
    assert f.status == "unavailable" and f.value is None  # never a number for now
    assert f.last_issued is not None and f.last_issued.value == 300.0 and f.last_issued.issued_at == stale
    assert f"newest forecast issued {stale:%Y-%m-%d %H:%M}" in f.reason
    assert forecast_of(overview, "ITO", "aqi_6h").last_issued is None  # nothing was ever issued for ITO


def test_a_current_forecast_carries_no_last_issued_block():
    overview = service(FakeRepo(forecasts=[row(3, "aqi_6h", 300.0)])).overview()
    ok = forecast_of(overview, "Anand Vihar", "aqi_6h")
    assert ok.status == "ok" and ok.last_issued is None
