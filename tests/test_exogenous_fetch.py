"""Rate-limit handling for the Open-Meteo / FIRMS fetchers (no network: requests are mocked)."""
import numpy as np
import pandas as pd
import pytest
import requests

from src.features import exogenous_drivers as ed


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def _install(monkeypatch, responses):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(ed.requests, "get", fake_get)
    return calls


def test_minutely_429_is_retried_after_waiting(monkeypatch):
    waits = []
    calls = _install(monkeypatch, [
        FakeResponse(429, {"reason": "Minutely API request limit exceeded."}),
        FakeResponse(200, {"ok": 1}),
    ])
    response = ed._get_with_retry("http://x", sleep=waits.append)
    assert response.status_code == 200 and len(calls) == 2
    assert waits and waits[0] >= 65


def test_retry_after_header_is_honoured(monkeypatch):
    waits = []
    _install(monkeypatch, [FakeResponse(429, {}, {"Retry-After": "30"}), FakeResponse(200)])
    ed._get_with_retry("http://x", sleep=waits.append)
    assert 30 <= waits[0] < 34


def test_hourly_or_daily_quota_stops_immediately(monkeypatch):
    calls = _install(monkeypatch, [FakeResponse(429, {"reason": "Hourly API request limit exceeded."})])
    with pytest.raises(ed.RateLimitExhausted):
        ed._get_with_retry("http://x", sleep=lambda s: None)
    assert len(calls) == 1


def test_network_error_is_retried(monkeypatch):
    _install(monkeypatch, [requests.ConnectionError("boom"), FakeResponse(200)])
    assert ed._get_with_retry("http://x", sleep=lambda s: None).status_code == 200


def test_other_4xx_fails_fast(monkeypatch):
    calls = _install(monkeypatch, [FakeResponse(404, {"reason": "nope"})])
    with pytest.raises(requests.HTTPError):
        ed._get_with_retry("http://x", sleep=lambda s: None)
    assert len(calls) == 1


def test_gives_up_after_max_attempts(monkeypatch):
    _install(monkeypatch, [FakeResponse(503, {"reason": "busy"}) for _ in range(3)])
    with pytest.raises(RuntimeError, match="gave up after 3"):
        ed._get_with_retry("http://x", max_attempts=3, sleep=lambda s: None)


def test_year_chunks_cover_range_without_overlap():
    assert ed._year_chunks("2024-01-01", "2025-12-31") == [
        ("2024-01-01", "2024-12-31"), ("2025-01-01", "2025-12-31")]
    assert ed._year_chunks("2024-06-15", "2025-02-01") == [
        ("2024-06-15", "2024-12-31"), ("2025-01-01", "2025-02-01")]


def test_weather_fetch_is_sequential_cached_and_resumable(monkeypatch, tmp_path):
    monkeypatch.setattr(ed, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(ed.time, "sleep", lambda s: None)
    fetched = []

    def fake_chunk(station, lat, lon, s, e):
        fetched.append((station, s, e))
        ts = pd.date_range(s, periods=48, freq="h")
        frame = pd.DataFrame({"timestamp": ts, "station_name": station})
        for var in ed.HOURLY_VARS:
            frame[var] = np.arange(48, dtype=float)
        return frame

    monkeypatch.setattr(ed, "_fetch_station_chunk", fake_chunk)
    first = ed.fetch_open_meteo_weather("2024-01-01", "2025-12-31")
    assert len(fetched) == len(ed.STATION_COORDS) * 2          # one request per station-year
    assert {"wind_u", "wind_v"} <= set(first.columns)

    fetched.clear()
    second = ed.fetch_open_meteo_weather("2024-01-01", "2025-12-31")
    assert fetched == []                                       # rerun makes no requests
    assert len(second) == len(first)

    ed.fetch_open_meteo_weather("2024-01-01", "2025-12-31", refresh=True)
    assert len(fetched) == len(ed.STATION_COORDS) * 2          # --refresh refetches
