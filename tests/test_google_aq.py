"""Google Air Quality shadow client and job (ADR 0010). Mocked only: no network, no database."""

import pandas as pd
import pytest

from src.live import google_shadow as gs
from src.live.sources import google_aq as g

# trimmed from a real currentConditions response (R K Puram, 2026-10-25 11:00Z)
CURRENT = {
    "dateTime": "2026-10-25T11:00:00Z",
    "regionCode": "in",
    "indexes": [
        {"code": "ind_cpcb", "displayName": "NAQI (IN)", "aqi": 201, "dominantPollutant": "pm25"},
        {"code": "uaqi", "displayName": "Universal AQI", "aqi": 23, "dominantPollutant": "pm10"},
    ],
    "pollutants": [
        {"code": "pm10", "concentration": {"value": 179, "units": g.UG}},
        {"code": "pm25", "concentration": {"value": 74, "units": g.UG}},
        {"code": "no2", "concentration": {"value": 13.93, "units": g.PPB}},
        {"code": "o3", "concentration": {"value": 72.79, "units": g.PPB}},
        {"code": "co", "concentration": {"value": 901.64, "units": g.PPB}},
        {"code": "so2", "concentration": {"value": 7.8, "units": g.PPB}},
        {"code": "nh3", "concentration": {"value": 45.78, "units": g.PPB}},
    ],
}


class Response:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload or {}

    def json(self):
        return self._payload


def test_pm_is_kept_and_gases_are_converted_to_the_units_of_live_readings():
    row = g.hour_row("R K Puram", CURRENT)
    assert (row["pm25"], row["pm10"]) == (74.0, 179.0)
    assert row["no2"] == pytest.approx(13.93 * 46.0055 / 24.45)  # ug/m3
    assert row["co"] == pytest.approx(901.64 * 28.010 / 24.45 / 1000)  # mg/m3
    assert row["o3"] == pytest.approx(72.79 * 47.9982 / 24.45) and row["so2"] == pytest.approx(7.8 * 64.066 / 24.45)


def test_the_utc_hour_maps_to_the_ist_hour_it_falls_in():
    row = g.hour_row("R K Puram", CURRENT)
    assert row["ts"] == pd.Timestamp("2026-10-25 16:00")  # 11:00Z is 16:30 IST
    assert row["waqi_time"] == pd.Timestamp("2026-10-25 16:30", tz="Asia/Kolkata")


def test_the_cpcb_index_and_the_universal_index_are_stored_apart():
    raw = g.hour_row("R K Puram", CURRENT)["raw_iaqi"]
    assert raw["indexes"] == {"ind_cpcb": 201, "uaqi": 23}
    assert raw["pollutants"]["nh3"] == 45.78  # kept raw: NH3 has no OpenAQ reference, so it is not a gate column


def test_a_changed_unit_label_is_refused_not_silently_converted():
    bad = {**CURRENT, "pollutants": [{"code": "no2", "concentration": {"value": 20, "units": g.UG}}]}
    with pytest.raises(g.UnitLabelChanged):
        g.hour_row("R K Puram", bad)


def test_missing_pollutants_are_blank_not_zero():
    row = g.hour_row("R K Puram", {**CURRENT, "pollutants": [CURRENT["pollutants"][1]]})
    assert row["pm25"] == 74.0 and pd.isna(row["no2"]) and pd.isna(row["co"])


def test_every_request_attempt_is_counted_and_the_budget_is_a_hard_stop():
    budget = g.RequestBudget(2)
    calls = []
    post = lambda url, **kw: calls.append(url) or Response(200, {})  # noqa: E731
    g.lookup("/x", {}, "k", budget, post=post)
    g.lookup("/x", {}, "k", budget, post=post)
    with pytest.raises(g.BudgetExceeded):
        g.lookup("/x", {}, "k", budget, post=post)
    assert len(calls) == 2 and budget.used == 2


def test_retries_count_against_the_budget_and_the_error_never_carries_the_key_or_body():
    budget = g.RequestBudget(10)
    post = lambda url, **kw: Response(403, {"error": {"message": "secret-key-abc"}})  # noqa: E731
    with pytest.raises(g.GoogleError) as err:
        g.lookup("/x", {}, "secret-key-abc", budget, post=post)
    assert "secret-key-abc" not in str(err.value) and budget.used == 1  # 403 is not retried
    flaky = iter([Response(503), Response(429), Response(200, {"ok": 1})])
    assert g.lookup("/x", {}, "k", g.RequestBudget(10), post=lambda *a, **kw: next(flaky), sleep=lambda s: None) == {
        "ok": 1
    }


def test_the_key_goes_in_a_header_never_the_url():
    seen = {}

    def post(url, json, headers, timeout):
        seen.update(url=url, headers=headers)
        return Response(200, {})

    g.lookup("/currentConditions:lookup", {}, "KEY123", g.RequestBudget(1), post=post)
    assert "KEY123" not in seen["url"] and seen["headers"] == {"X-Goog-Api-Key": "KEY123"}


def test_history_follows_page_tokens_and_asks_for_the_local_index():
    bodies = []
    pages = iter([{"hoursInfo": [CURRENT], "nextPageToken": "t1"}, {"hoursInfo": [CURRENT, CURRENT]}])

    def post(url, json, headers, timeout):
        bodies.append(json)
        return Response(200, next(pages))

    out = list(g.history(28.5, 77.1, "k", g.RequestBudget(5), 720, post=post))
    assert len(out) == 3 and bodies[1]["pageToken"] == "t1" and bodies[0]["pageSize"] == g.PAGE_SIZE
    assert bodies[0]["customLocalAqis"] == [{"regionCode": "IN", "aqi": "ind_cpcb"}]
    assert g.pages_needed(720) == 5 and g.pages_needed(168) == 1 and g.pages_needed(169) == 2


class FakeStore:
    def __init__(self, today=0):
        self.today, self.upserts, self.runs = today, [], []

    def stations(self):
        return {"R K Puram": (9, 28.56, 77.18), "ITO": (6, 28.62, 77.24)}

    def requests_today(self):
        return self.today

    def start_run(self, job):
        return 1

    def finish_run(self, run_id, status, rows, error, details):
        self.runs.append((status, rows, details))

    def upsert_shadow(self, rows, ids, source):
        self.upserts.append((len(rows), source, ids))
        return len(rows)


def patch_current(monkeypatch):
    monkeypatch.setattr(g, "current", lambda lat, lon, key, budget, **kw: (budget.spend(), [CURRENT])[1])


def test_a_run_writes_rows_tagged_google_and_records_the_requests_it_used(monkeypatch):
    patch_current(monkeypatch)
    store = FakeStore()
    result = gs.run(store, "k")
    assert result["status"] == "success" and store.upserts == [(2, "google", {"R K Puram": 9, "ITO": 6})]
    assert store.runs[-1][2]["requests"] == 2 and store.runs[-1][2]["source"] == "google"


def test_history_is_stored_under_its_own_tag_apart_from_the_live_rows(monkeypatch):
    monkeypatch.setattr(g, "history", lambda lat, lon, key, budget, hours, **kw: (budget.spend(), [CURRENT])[1])
    store = FakeStore()
    gs.run(store, "k", history_days=7)
    assert store.upserts[0][1] == "google_history" and store.runs[-1][2]["source"] == "google"


def test_a_run_over_its_request_limit_or_the_daily_cap_never_calls_the_api(monkeypatch):
    called = []
    monkeypatch.setattr(g, "current", lambda *a, **kw: called.append(1))
    with pytest.raises(g.BudgetExceeded):
        gs.run(FakeStore(), "k", history_days=30, max_requests=5)  # 2 stations x 5 pages = 10
    with pytest.raises(g.BudgetExceeded):
        gs.run(FakeStore(today=gs.DAILY_REQUEST_CAP - 1), "k")
    assert not called


def test_a_dry_run_writes_nothing(monkeypatch):
    patch_current(monkeypatch)
    store = FakeStore()
    result = gs.run(store, "k", dry_run=True)
    assert result["rows"] == 0 and not store.upserts and not store.runs
