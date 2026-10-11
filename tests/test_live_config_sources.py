"""Live config and the two sources behind one interface. Mocked HTTP only: no network, no database."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import requests

from src.live import config as cfgmod
from src.live import openaq
from src.live.sources import REGISTRY, DataGovInSource, LiveSource, OpenAQSource, SourceNotVerified, SourceUnavailable, get_source
from src.live.sources import data_gov_in as dgi
from src.live.sources.base import SOURCE_COLUMNS


# ------------------------------------------------------------------ config
def _toml(tmp_path, body='[ingest]\nsource = "openaq"\n'):
    path = tmp_path / "live.toml"
    path.write_text(body)
    return path


def test_the_repository_config_loads_and_defaults_to_openaq():
    cfg = cfgmod.load_config(env={})
    assert cfg.source == "openaq" and cfg.allow_unverified is False and cfg.weather_fill == "open-meteo"


def test_environment_overrides_the_file_and_blank_variables_are_ignored(tmp_path):
    path = _toml(tmp_path)
    assert cfgmod.load_config(path, {"LIVE_SOURCE": "data_gov_in"}).source == "data_gov_in"
    assert cfgmod.load_config(path, {"LIVE_SOURCE": "  ", "LIVE_FALLBACK": ""}).source == "openaq"
    assert cfgmod.load_config(path, {"LIVE_ALLOW_UNVERIFIED": "true"}).allow_unverified is True
    assert cfgmod.load_config(path, {"LIVE_LOOKBACK_HOURS": "12"}).lookback_hours == 12


@pytest.mark.parametrize("env", [{"LIVE_SOURCE": "mystery"}, {"LIVE_FALLBACK": "openaq"}, {"LIVE_WEATHER_FILL": "gfs"},
                                 {"LIVE_LOOKBACK_HOURS": "0"}, {"LIVE_LOOKBACK_HOURS": "500"}])
def test_invalid_settings_are_rejected(tmp_path, env):
    with pytest.raises(cfgmod.ConfigError):
        cfgmod.load_config(_toml(tmp_path), env)


def test_unknown_keys_in_the_file_are_rejected(tmp_path):
    with pytest.raises(cfgmod.ConfigError, match="unknown settings"):
        cfgmod.load_config(_toml(tmp_path, '[ingest]\nsource = "openaq"\ntypo_key = 1\n'), {})


# ------------------------------------------------------------------ one interface
def test_registry_has_both_sources_behind_the_same_interface():
    assert set(REGISTRY) == {"openaq", "data_gov_in"}
    for name, cls in REGISTRY.items():
        assert issubclass(cls, LiveSource) and cls.name == name and get_source(name).name == name
    assert OpenAQSource.tag == "openaq" and DataGovInSource.tag == "data.gov.in"
    with pytest.raises(ValueError, match="unknown source"):
        get_source("nope")


def test_verification_status_is_explicit_and_enforced():
    assert OpenAQSource.verified is True
    assert DataGovInSource.verified is False                 # until a real response has been read
    with pytest.raises(SourceNotVerified):
        DataGovInSource(api_key="k").require_verified(allow_unverified=False)
    DataGovInSource(api_key="k").require_verified(allow_unverified=True)
    OpenAQSource().require_verified(False)


def test_documented_gaps_per_source():
    assert "solar_radiation" in OpenAQSource.missing["all stations"]
    assert {"nox", "temperature", "humidity", "wind_speed", "solar_radiation"} <= set(DataGovInSource.missing["all stations"])


# ------------------------------------------------------------------ OpenAQ source
def _fake_openaq(monkeypatch, labels=None):
    slots = pd.date_range("2026-10-11 08:00", periods=4 * 6, freq="15min")
    raw = lambda v: pd.DataFrame({"from": slots, "to": slots + pd.Timedelta(minutes=15), "value": v})
    sensors = {"pm25": (1, "µg/m³"), "no2": (2, "ppb"), "nox": (3, "ppb"), "temperature": (4, "c")}
    values = {1: 100.0, 2: 40.0, 3: 0.08, 4: 31.0}
    monkeypatch.setattr(openaq, "live_sensors", lambda loc, station="": labels or sensors)
    monkeypatch.setattr(openaq, "fetch_15min", lambda sid, start, end: raw(values[sid]))


def test_openaq_source_returns_the_canonical_frame_in_training_units(monkeypatch):
    _fake_openaq(monkeypatch)
    frame = OpenAQSource().fetch(pd.Timestamp("2026-10-11 08:00"), pd.Timestamp("2026-10-11 10:00"))
    assert list(frame.columns)[:2] == ["station_name", "hour"] and set(SOURCE_COLUMNS) <= set(frame.columns)
    assert set(frame.station_name) == set(openaq.LOCATIONS)
    row = frame[(frame.station_name == "R K Puram") & (frame.hour == pd.Timestamp("2026-10-11 09:00"))].iloc[0]
    assert row.pm25 == 100.0 and row.no2 == 40.0 and row.nox == pytest.approx(80.0)     # 0.08 ppm -> 80 ppb
    assert row.temperature == pytest.approx(31.0)


def test_openaq_station_flags_only_mark_dwarka():
    s = OpenAQSource()
    assert s.station_flags("Dwarka-Sector 8") == {"_alignment": "unverified_2026"} and s.station_flags("ITO") == {}


def test_a_changed_openaq_unit_label_stops_the_ingest_source(monkeypatch):
    def boom(loc, station=""):
        raise openaq.UnitLabelChanged("labels moved")
    monkeypatch.setattr(openaq, "live_sensors", boom)
    with pytest.raises(openaq.UnitLabelChanged):
        OpenAQSource().fetch(pd.Timestamp("2026-10-11 08:00"), pd.Timestamp("2026-10-11 09:00"))


def test_openaq_network_failure_becomes_source_unavailable_without_details(monkeypatch):
    def down(loc, station=""):
        raise requests.ConnectionError("https://api.openaq.org/...?key=SECRET")
    monkeypatch.setattr(openaq, "live_sensors", down)
    with pytest.raises(SourceUnavailable) as err:
        OpenAQSource().fetch(pd.Timestamp("2026-10-11 08:00"), pd.Timestamp("2026-10-11 09:00"))
    assert "SECRET" not in str(err.value)


# ------------------------------------------------------------------ data.gov.in source (documented fields only)
def _record(station, pollutant, avg, stamp="11-10-2026 14:00:00"):
    return {"country": "India", "state": "Delhi", "city": "Delhi", "station": station, "last_update": stamp,
            "pollutant_id": pollutant, "pollutant_min": "10", "pollutant_max": "300", "pollutant_avg": avg}


def test_parse_records_pivots_pollutants_maps_stations_and_handles_NA():
    records = [_record("R K Puram, Delhi - DPCC", "PM2.5", "123"), _record("R K Puram, Delhi - DPCC", "OZONE", "NA"),
               _record("R K Puram, Delhi - DPCC", "CO", "1.4"), _record("ITO, Delhi - CPCB", "PM10", "210"),
               _record("Civil Lines, Delhi - IMD", "PM2.5", "88"),                 # not one of our stations
               _record("R K Puram, Delhi - DPCC", "BENZENE", "1")]                 # not a model input
    frame = dgi.parse_records(records)
    assert set(frame.station_name) == {"R K Puram", "ITO"}
    rk = frame[frame.station_name == "R K Puram"].iloc[0]
    assert rk.pm25 == 123.0 and rk.co == 1.4 and np.isnan(rk.o3)
    assert frame[frame.station_name == "ITO"].iloc[0].pm10 == 210.0


def test_the_hour_label_rule_is_an_explicit_unverified_guess():
    frame = dgi.parse_records([_record("ITO, Delhi - CPCB", "PM10", "1", "11-10-2026 14:00:00")])
    expected = pd.Timestamp("2026-10-11 13:00") if dgi.HOUR_ENDS_AT_LAST_UPDATE else pd.Timestamp("2026-10-11 14:00")
    assert frame.hour.iloc[0] == expected
    assert DataGovInSource.verified is False and "NOT VERIFIED" in dgi.__doc__


@pytest.mark.parametrize("name,expected", [("Anand Vihar, Delhi - DPCC", "Anand Vihar"), ("Jahangirpuri, Delhi - DPCC\t", "Jahangirpuri"),
                                           ("Dwarka-Sector 8, Delhi - DPCC", "Dwarka-Sector 8"), ("Dwarka-Sector 8", "Dwarka-Sector 8"),
                                           ("NSIT Dwarka, Delhi - CPCB", None), ("", None)])
def test_station_name_mapping(name, expected):
    assert dgi.station_for_feed_name(name) == expected


class _Session:
    def __init__(self, payload=None, error=None):
        self.payload, self.error, self.calls = payload, error, []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        if self.error:
            raise self.error

        class R:
            def raise_for_status(s): pass
            def json(s): return self_payload
        self_payload = self.payload
        return R()


def test_data_gov_in_fetch_filters_to_the_requested_hours():
    session = _Session({"records": [_record("ITO, Delhi - CPCB", "PM10", "1", "11-10-2026 14:00:00")]})
    source = DataGovInSource(api_key="KEY", session=session)
    got = source.fetch(pd.Timestamp("2026-10-11 13:00"), pd.Timestamp("2026-10-11 13:00"))
    assert len(got) == 1 and session.calls[0][1]["filters[city]"] == "Delhi"
    assert len(source.fetch(pd.Timestamp("2026-10-11 06:00"), pd.Timestamp("2026-10-11 07:00"))) == 0


def test_data_gov_in_failures_never_leak_the_key():
    error = requests.ConnectionError("HTTPSConnectionPool: /resource/x?api-key=SUPERSECRET&format=json")
    with pytest.raises(SourceUnavailable) as err:
        DataGovInSource(api_key="SUPERSECRET", session=_Session(error=error)).fetch(pd.Timestamp("2026-10-11 06:00"), pd.Timestamp("2026-10-11 07:00"))
    assert "SUPERSECRET" not in str(err.value)
    with pytest.raises(SourceUnavailable, match="not set"):
        DataGovInSource(api_key="").fetch(pd.Timestamp("2026-10-11 06:00"), pd.Timestamp("2026-10-11 07:00"))


def test_data_gov_in_cannot_supply_nox_or_weather():
    frame = dgi.parse_records([_record("ITO, Delhi - CPCB", "PM10", "1")])
    assert frame[["nox", "temperature", "humidity", "wind_speed", "solar_radiation"]].isna().all().all()


def test_workflow_and_requirements_files_exist_for_the_ingest():
    root = Path(__file__).resolve().parents[1]
    text = (root / ".github/workflows/ingest.yml").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "workflow_dispatch" in code and "schedule:" not in code       # manual only until a source is fresh from a runner
    assert "group: ingest" in text and "cancel-in-progress: false" in text
    assert "pull_request" not in text and "contents: read" in text
    for secret in ("DATABASE_URL", "DATA_GOV_IN_API_KEY", "OPENAQ_API_KEY"):
        assert f"secrets.{secret}" in text
    assert "inputs.source || vars.LIVE_SOURCE" in text and "python -m src.live.ingest" in text
    assert (root / "requirements-live.txt").exists()
