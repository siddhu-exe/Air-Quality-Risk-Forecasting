"""Stall escalation decisions and issue calls. Mocked only: no network, no database."""

import pandas as pd
import pytest

from src.live import stall_watch as sw

NOW = pd.Timestamp("2026-10-25 16:00")


@pytest.mark.parametrize(
    "age, issue_open, expected",
    [
        (None, False, "open"),  # no data at all
        (49.0, False, "open"),
        (49.0, True, "refresh"),  # already open: update, never a second issue
        (47.9, False, "none"),  # lagging but under the threshold
        (47.9, True, "none"),  # open issue stays open until the source is actually fresh
        (10.0, True, "none"),  # hovering below the threshold must not flap the issue
        (2.5, True, "close"),
        (2.5, False, "none"),
    ],
)
def test_decide(age, issue_open, expected):
    assert sw.decide(age, issue_open, stale_after=3.0) == expected


def test_age_counts_to_the_end_of_the_readings_hour():
    assert sw.age_hours(pd.Timestamp("2026-10-23 20:00"), NOW) == 43.0
    assert sw.age_hours(None, NOW) is None


def test_body_lists_every_station_with_its_age():
    text = sw.body({"ITO": pd.Timestamp("2026-10-22 12:00"), "Bawana": None}, NOW, 48.0)
    assert "| ITO | 2026-10-22 12:00 | 75.0 |" in text and "| Bawana | no reading | - |" in text


def test_main_opens_updates_and_closes_the_issue(monkeypatch):
    calls = []
    monkeypatch.setattr(
        sw,
        "github_call",
        lambda token, method, url, payload=None: calls.append((method, url.split("/repos/")[1], payload)),
    )
    monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    stale = {"ITO": pd.Timestamp.now(tz=sw.KST).tz_localize(None) - pd.Timedelta(hours=100)}
    fresh = {"ITO": pd.Timestamp.now(tz=sw.KST).tz_localize(None) - pd.Timedelta(hours=2)}
    monkeypatch.setattr(sw, "newest_per_station", lambda: stale)
    monkeypatch.setattr(sw, "find_open_issue", lambda *a, **k: None)
    sw.main([])
    assert calls[-1][0] == "POST" and calls[-1][1] == "o/r/issues" and calls[-1][2]["labels"] == [sw.LABEL]
    monkeypatch.setattr(sw, "find_open_issue", lambda *a, **k: {"number": 7})
    sw.main([])
    assert calls[-1][:2] == ("PATCH", "o/r/issues/7") and "state" not in calls[-1][2]
    monkeypatch.setattr(sw, "newest_per_station", lambda: fresh)
    sw.main([])
    assert calls[-2][:2] == ("POST", "o/r/issues/7/comments") and calls[-1] == (
        "PATCH",
        "o/r/issues/7",
        {"state": "closed"},
    )
