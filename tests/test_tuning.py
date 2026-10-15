"""Tests for the Tier 2 compute profiles (src/models/tuning.py)."""

from pathlib import Path

import pytest

from src.models import tuning


def test_default_profile_is_standard(monkeypatch):
    monkeypatch.delenv(tuning.PROFILE_ENV, raising=False)
    assert tuning.profile_name() == "standard"
    assert tuning.is_standard()
    assert tuning.get_profile()["n_search"] == 0


def test_unknown_profile_raises(monkeypatch):
    monkeypatch.setenv(tuning.PROFILE_ENV, "turbo")
    with pytest.raises(ValueError):
        tuning.profile_name()


def test_out_dir_never_overwrites_standard_results(monkeypatch):
    base = Path("reports/modeling/pm25")
    monkeypatch.setenv(tuning.PROFILE_ENV, "standard")
    assert tuning.out_dir(base) == base
    monkeypatch.setenv(tuning.PROFILE_ENV, "max")
    assert tuning.out_dir(base) == base / "max"


def test_search_configs_start_with_default_and_are_distinct_and_deterministic():
    a = tuning.search_configs(10)
    b = tuning.search_configs(10)
    assert a == b
    assert a[0] == tuning.DEFAULT_CONFIG
    assert len(a) == 11
    assert len({tuple(sorted(c.items())) for c in a}) == 11
    for cfg in a:
        for key, value in cfg.items():
            assert value in tuning.SEARCH_SPACE[key]


def test_max_profile_does_more_work_than_standard():
    std, mx = tuning.PROFILES["standard"], tuning.PROFILES["max"]
    assert mx["n_boot"] > std["n_boot"]
    assert mx["n_search"] > std["n_search"]
    assert mx["pm25_max_iter"] > std["pm25_max_iter"]
