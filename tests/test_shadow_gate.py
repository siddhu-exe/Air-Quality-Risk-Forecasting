"""The WAQI fallback gate (ADR 0009): thresholds, the split-half offset rule, per-station verdicts, ITO excluded, the report."""

import numpy as np
import pandas as pd
import pytest

from src.features.compute_cpcb_aqi import STATION_IDS
from src.live import shadow_compare as sc
from src.live.sources.waqi import POLLUTANTS

START = pd.Timestamp("2026-10-01 00:00")


def signal(rng: np.random.Generator, hours: int) -> np.ndarray:
    t = np.arange(hours)
    walk = np.cumsum(rng.normal(0, 8, hours))
    return 150 + 70 * np.sin(2 * np.pi * t / 24 + rng.uniform(0, 6)) + walk - walk.mean()


def frames(days=10, lag=0, lag_second_half=None, noise=6.0, bias=1.0, bad=(), seed=1):
    """OpenAQ (primary) hourly for every station; WAQI (shadow) = primary at S + lag, with noise/bias. ``bad``: stations whose
    WAQI feed is unrelated noise. ``lag_second_half``: a different offset after the middle of the overlap."""
    rng = np.random.default_rng(seed)
    hours = days * 24
    index = pd.date_range(START, periods=hours + 3, freq="h")
    prim, shad = [], []
    for name, sid in STATION_IDS.items():
        series = np.clip(signal(rng, hours + 3), 5, None)
        p = pd.DataFrame({"station_id": sid, "ts": index, **{c: np.nan for c in POLLUTANTS}})
        p["pm25"], p["pm10"] = series, series * 1.8
        prim.append(p)
        cut = hours // 2
        values = []
        for h in range(hours):
            use = lag if (lag_second_half is None or h < cut) else lag_second_half
            values.append(series[h + use + (1 if use < 0 else 0)] if use >= 0 else series[max(h + use, 0)])
        values = np.array(values) * bias + rng.normal(0, noise, hours)
        if name in bad:
            values = np.clip(rng.normal(150, 70, hours), 5, None)
        s = pd.DataFrame({"station_id": sid, "ts": index[:hours], **{c: np.nan for c in POLLUTANTS}})
        s["pm25"], s["pm10"] = values, values * 1.8
        shad.append(s)
    return pd.concat(shad, ignore_index=True), pd.concat(prim, ignore_index=True)


def test_clean_agreement_over_ten_days_passes_and_lists_the_usable_stations():
    report = sc.gate(*frames())
    assert report.passed and report.summary.startswith("PASS")
    assert "ITO" not in report.stations_usable and len(report.stations_usable) == 6
    assert report.overlap_days >= 7 and report.reasons == []
    assert all(report.pollutants[p].lag_hours == 0 for p in sc.GATE_POLLUTANTS)


def test_too_short_an_overlap_fails_even_when_the_values_agree():
    report = sc.gate(*frames(days=4))
    assert not report.passed and any("need 7" in r for r in report.reasons)


def test_no_overlap_is_a_clear_fail_not_an_error():
    shadow, primary = frames()
    primary["ts"] = primary["ts"] - pd.Timedelta(days=60)
    report = sc.gate(shadow, primary)
    assert not report.passed and "no overlapping hours" in report.summary and report.pollutants == {}
    assert not sc.gate(shadow.head(0), primary.head(0)).passed


@pytest.mark.parametrize("bias,field", [(1.25, "bias"), (0.7, "bias")])
def test_a_biased_feed_fails_on_bias(bias, field):
    report = sc.gate(*frames(bias=bias))
    assert not report.passed and any("bias" in r for r in report.reasons)


def test_a_noisy_feed_fails_on_mae_or_corr():
    report = sc.gate(*frames(noise=90.0))
    assert not report.passed


def test_the_offset_is_chosen_on_the_first_half_and_judged_on_the_second():
    # WAQI is one hour late for the whole overlap -> offset +1 is picked and passes
    report = sc.gate(*frames(lag=1))
    assert report.passed and report.pollutants["pm25"].lag_hours == 1
    # the offset changes in the second half: the first half still picks 0, so the second half is scored at 0 and does NOT get
    # rescued by the offset that would have fitted the data being judged
    report = sc.gate(*frames(lag=0, lag_second_half=1, noise=1.0))
    assert report.pollutants["pm25"].lag_hours == 0
    assert report.pollutants["pm25"].pooled_all.mae_share > report.pollutants["pm25"].lag_first_half_mae_share["0"]


def test_one_bad_station_loses_its_forecast_but_the_network_can_still_pass():
    report = sc.gate(*frames(bad=("Bawana",)))
    assert report.passed  # 5 of the 6 eligible stations pass
    assert "Bawana" not in report.stations_usable and len(report.stations_usable) == 5


def test_two_bad_stations_fail_the_network_gate_and_nothing_is_usable():
    report = sc.gate(*frames(bad=("Bawana", "Anand Vihar")))
    assert not report.passed and report.stations_usable == [] and any("stations pass" in r for r in report.reasons)


def test_ito_is_ignored_even_when_its_feed_is_garbage_or_perfect():
    shadow, primary = frames(bad=("ITO",))
    assert sc.gate(shadow, primary).passed  # a bad ITO feed does not count against the network
    report = sc.gate(*frames())
    assert "ITO" not in report.pollutants["pm25"].stations and "ITO" in report.excluded
    # and a perfect ITO feed cannot rescue a network that has only 4 good eligible stations
    shadow, primary = frames(bad=("Bawana", "Anand Vihar"))
    assert not sc.gate(shadow, primary).passed


def test_the_gases_play_no_part():
    shadow, primary = frames()
    for gas in ("no2", "so2", "co", "o3"):
        shadow[gas], primary[gas] = 1.0, 500.0  # wildly different, and must not matter
    assert sc.gate(shadow, primary).passed


def test_markdown_and_json_carry_the_verdict():
    report = sc.gate(*frames())
    text = sc.render_markdown(report)
    assert "WAQI fallback gate: PASS" in text and "pm25" in text and "Excluded: ITO" in text
    assert '"passed": true' in report.to_json()
    failed = sc.render_markdown(sc.gate(*frames(days=3)))
    assert "FAIL" in failed and "need 7" in failed


def test_the_cli_returns_zero_on_fail_so_the_weekly_workflow_stays_green(monkeypatch, capsys):
    shadow, primary = frames(days=3)

    class FakeStore:
        def __init__(self, *_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def shadow_since(self, since, source="waqi_backconverted"):
            return shadow

        def primary_since(self, since):
            return primary

    monkeypatch.setattr("src.live.waqi_shadow.ShadowStore", FakeStore)
    assert sc.main(["--gate"]) == 0
    assert "FAIL" in capsys.readouterr().out


def test_the_weekly_workflow_posts_to_an_issue_and_stays_isolated():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".github/workflows/waqi-gate.yml").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert 'cron: "30 4 * * 1"' in code and "issues: write" in code and "contents: read" in code
    assert "python -m src.live.shadow_compare --gate --issue" in code
    assert (
        "DATABASE_URL_READONLY" not in code and "WAQI_API_TOKEN" not in code
    )  # reads stored rows only, never calls WAQI


# ---- Google (ADR 0010): the same rules, six pollutants, ITO judged like any other station
GAS_RATIO = {"no2": 0.3, "so2": 0.05, "co": 0.01, "o3": 0.4}


def google_frames(**kwargs):
    shadow, primary = frames(**kwargs)
    for gas, ratio in GAS_RATIO.items():
        primary[gas] = primary["pm25"] * ratio
        shadow[gas] = shadow["pm25"] * ratio
    return shadow, primary


def test_google_gate_judges_all_six_pollutants_and_includes_ito():
    report = sc.gate(*google_frames(), sc.GOOGLE_SPEC)
    assert report.passed and set(report.pollutants) == set(sc.GOOGLE_SPEC.pollutants)
    assert "ITO" in report.stations_usable and len(report.stations_usable) == 7
    assert report.subsets["pm_only"]["passed"] and report.excluded == []
    assert "Google Air Quality gate: PASS" in sc.render_markdown(report)


def test_google_gate_fails_when_one_gas_disagrees_but_reports_the_pm_subset_separately():
    shadow, primary = google_frames()
    shadow["no2"] = 1.0  # wildly different from the reference at every station
    report = sc.gate(shadow, primary, sc.GOOGLE_SPEC)
    assert not report.passed and not report.pollutants["no2"].passed
    assert report.pollutants["pm25"].passed and report.subsets["pm_only"]["passed"]
    assert report.stations_usable == []  # nothing is usable for the models unless every pollutant passes


def test_the_default_spec_is_still_the_waqi_pm_only_gate():
    report = sc.gate(*frames())
    assert report.name == "WAQI fallback gate" and set(report.pollutants) == {"pm25", "pm10"}
    assert report.excluded == ["ITO"]


def test_the_history_endpoint_is_gated_apart_with_the_same_rules():
    spec = sc.SPECS["google_history"]
    assert spec.source == "google_history" and spec.pollutants == sc.GOOGLE_SPEC.pollutants
    assert sc.gate(*google_frames(), spec).name == "Google Air Quality gate (history)"
