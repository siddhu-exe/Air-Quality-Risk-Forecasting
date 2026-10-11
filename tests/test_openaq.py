"""Pins what was learned about OpenAQ so a silent upstream change breaks a test, not the data.

Evidence and method: docs/TIER_3/openaq_overlap_check.md. No network: HTTP is mocked and the
conversion checks use a real captured day (tests/fixtures/openaq_rkpuram_2026-08-25.json) next to
the project's own CSV values for the same hours.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.live import openaq
from src.live.openaq import (
    ALIGNMENT_UNVERIFIED_2026, EXPECTED_UNIT_LABELS, PARAM_TO_COLUMN, UNIT_FACTOR, UnitLabelChanged,
    check_unit_labels, hourly_frame, slots_to_hourly,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "openaq_rkpuram_2026-08-25.json").read_text())


def _raw(param):
    rows = FIXTURE["raw"][param]
    return pd.DataFrame({"from": pd.to_datetime([r[0] for r in rows]), "to": pd.to_datetime([r[1] for r in rows]),
                         "value": [r[2] for r in rows]})


def _csv(param):
    return pd.Series({pd.Timestamp(k): v for k, v in FIXTURE["csv"][param].items()})


def _mae_pct(param, factor=None, offset=None):
    ref = _csv(param)
    got = slots_to_hourly(
        _raw(param), ref.index,
        openaq.SLOT_START_OFFSET_MIN.get(param, 0) if offset is None else offset,
        UNIT_FACTOR.get(param, 1.0) if factor is None else factor,
    )
    pair = pd.concat([got.rename("o"), ref.rename("c")], axis=1).dropna()
    assert len(pair) >= 15
    return 100 * (pair.o - pair.c).abs().mean() / pair.c.abs().mean()


# ---------------------------------------------------------------- the hour convention + units
@pytest.mark.parametrize("param,limit", [("pm25", 3.0), ("no2", 4.0), ("nox", 4.0), ("co", 3.0),
                                         ("temperature", 1.0), ("relativehumidity", 1.5)])
def test_hourly_conversion_matches_our_csv_on_a_real_day(param, limit):
    assert _mae_pct(param) < limit


def test_nox_must_be_multiplied_by_1000_despite_the_ppb_label():
    assert UNIT_FACTOR["nox"] == 1000.0
    assert _mae_pct("nox", factor=1.0) > 90          # without the factor the data would be ~1000x too small


def test_no_conversion_for_gases_labelled_ppb():
    # NO2, SO2 and CO carry a 'ppb' label but already equal our ug/m3 / mg/m3 numbers
    assert set(UNIT_FACTOR) == {"nox"}
    for gas in ("no2", "so2", "co"):
        assert EXPECTED_UNIT_LABELS[gas] == "ppb"
    assert _mae_pct("no2") < 4.0 and _mae_pct("co") < 3.0
    assert _mae_pct("no2", factor=1.88) > 50          # the "textbook" ppb->ug/m3 factor would be wrong


def test_hour_label_is_the_mean_of_the_four_slots_starting_at_the_hour():
    raw = pd.DataFrame({"from": pd.to_datetime(["2026-01-01 05:00", "2026-01-01 05:15", "2026-01-01 05:30", "2026-01-01 05:45"]),
                        "to": pd.to_datetime(["2026-01-01 05:15", "2026-01-01 05:30", "2026-01-01 05:45", "2026-01-01 06:00"]),
                        "value": [10.0, 20.0, 30.0, 40.0]})
    hour = pd.DatetimeIndex(["2026-01-01 05:00", "2026-01-01 06:00"])
    got = slots_to_hourly(raw, hour)
    assert got.iloc[0] == 25.0 and np.isnan(got.iloc[1])       # the 06:00 hour has no slots: NaN, not extrapolated
    assert slots_to_hourly(raw, hour[:1], start_offset_min=-15).isna().all()  # temperature/RH window starts 15 min earlier


def test_incomplete_hour_is_nan_not_a_partial_average():
    raw = pd.DataFrame({"from": pd.to_datetime(["2026-01-01 05:00", "2026-01-01 05:15", "2026-01-01 05:30"]),
                        "to": pd.to_datetime(["2026-01-01 05:15", "2026-01-01 05:30", "2026-01-01 05:45"]),
                        "value": [1.0, 2.0, 3.0]})
    assert slots_to_hourly(raw, pd.DatetimeIndex(["2026-01-01 05:00"])).isna().all()


def test_hourly_frame_uses_live_readings_column_names_and_applies_only_the_nox_factor():
    idx = pd.DatetimeIndex([FIXTURE["csv"]["nox"] and pd.Timestamp(next(iter(FIXTURE["csv"]["nox"])))])
    frame = hourly_frame({"nox": _raw("nox"), "no2": _raw("no2"), "relativehumidity": _raw("relativehumidity")}, idx)
    assert set(frame.columns) == {"nox", "no2", "humidity"}
    assert frame["nox"].iloc[0] > 1.0 and frame["no2"].iloc[0] > 1.0   # nox in ppb now (was ~0.1 ppm)


# ---------------------------------------------------------------- pinned unit labels
def test_every_converted_parameter_has_a_pinned_label_and_a_column():
    assert set(EXPECTED_UNIT_LABELS) == set(PARAM_TO_COLUMN)


def test_matching_labels_pass():
    check_unit_labels("X", {p: (1, u) for p, u in EXPECTED_UNIT_LABELS.items()})


@pytest.mark.parametrize("param,new_label", [("no2", "µg/m³"), ("co", "mg/m³"), ("nox", "ppm"), ("so2", "µg/m³")])
def test_upstream_label_fix_raises_instead_of_silently_changing_the_data(param, new_label):
    sensors = {p: (1, u) for p, u in EXPECTED_UNIT_LABELS.items()}
    sensors[param] = (1, new_label)
    with pytest.raises(UnitLabelChanged, match="re-run"):
        check_unit_labels("X", sensors)


# ---------------------------------------------------------------- sensor selection (mocked HTTP)
def test_live_sensor_is_the_highest_id_per_parameter(monkeypatch):
    listing = {"results": [
        {"id": 35, "parameter": {"name": "pm25", "units": "µg/m³"}},          # stopped in 2018
        {"id": 12234787, "parameter": {"name": "pm25", "units": "µg/m³"}},
        {"id": 36, "parameter": {"name": "no2", "units": "µg/m³"}},           # old feed, different label
        {"id": 12234784, "parameter": {"name": "no2", "units": "ppb"}},
        {"id": 5, "parameter": {"name": "no", "units": "ppb"}},               # not a model input
    ]}
    monkeypatch.setattr(openaq, "get", lambda path, **kw: listing)
    got = openaq.live_sensors(17, "R K Puram")
    assert got["pm25"] == (12234787, "µg/m³") and got["no2"] == (12234784, "ppb") and "no" not in got


def test_fetch_is_chunked_below_the_page_limit(monkeypatch):
    calls = []

    def fake_get(path, **kw):
        calls.append(kw)
        return {"results": []}

    monkeypatch.setattr(openaq, "get", fake_get)
    openaq.fetch_15min(1, "2026-09-01", "2026-10-07")
    assert len(calls) >= 4
    for kw in calls:
        span = pd.Timestamp(kw["datetime_to"]) - pd.Timestamp(kw["datetime_from"])
        assert span <= pd.Timedelta(days=openaq.CHUNK_DAYS) and kw["limit"] == 1000


def test_api_key_is_only_sent_as_a_header(monkeypatch):
    seen = {}

    class Resp:
        status_code, headers = 200, {}
        def raise_for_status(self): pass
        def json(self): return {"results": []}

    def fake_requests_get(url, headers=None, params=None, timeout=None):
        seen.update(url=url, headers=headers, params=params)
        return Resp()

    monkeypatch.setenv("OPENAQ_API_KEY", "TOPSECRET")
    monkeypatch.setattr(openaq.requests, "get", fake_requests_get)
    openaq.get("/locations/17")
    assert seen["headers"] == {"X-API-Key": "TOPSECRET"}
    assert "TOPSECRET" not in seen["url"] and "TOPSECRET" not in str(seen["params"])


# ---------------------------------------------------------------- known gaps
def test_dwarka_2026_alignment_is_flagged_unverified():
    assert ALIGNMENT_UNVERIFIED_2026 == {"Dwarka-Sector 8"}
    assert openaq.UNVERIFIED_FLAG == {"_alignment": "unverified_2026"}


def test_documented_gaps_in_openaq_coverage():
    assert "solar_radiation" in openaq.MISSING_FROM_OPENAQ["all stations"]
    assert set(openaq.MISSING_FROM_OPENAQ["ITO"]) == {"temperature", "humidity", "wind_speed"}


def test_location_ids_are_the_cpcb_provider_ones():
    assert openaq.LOCATIONS == {"Anand Vihar": 235, "Bawana": 8472, "Dwarka-Sector 8": 6931, "ITO": 5613,
                                "Jahangirpuri": 8235, "Punjabi Bagh": 50, "R K Puram": 17}
