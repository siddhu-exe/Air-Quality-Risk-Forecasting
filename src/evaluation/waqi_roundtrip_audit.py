"""WAQI back-conversion audit (validation window only; nothing is trained or tuned).

Question: WAQI (api.waqi.info) publishes per-pollutant US-EPA AQI values (``iaqi``), not concentrations, and has no NOx.
If we convert them back to concentrations and feed the frozen models, how much skill vs persistence is left?

Scenarios (same frozen models, features rebuilt through the shared ``compute_feature_frame``; AQI recomputed from the
pollutants with ``compute_aqi``, exactly as the live ingest does):
  baseline            station sensors and the stored AQI, as trained
  control_recomputed  station sensors, AQI recomputed (isolates the AQI-recompute effect from everything below)
  masked_exact        no NOx/NO/NH3, no station weather or solar (``weather_fill = "none"``), concentrations exact
                      (isolates the effect of the missing inputs from the effect of the conversion)
  waqi_roundtrip      as masked_exact, and PM2.5/PM10/NO2/SO2/CO/O3 pass through concentration -> integer EPA AQI -> concentration
  waqi_epa_averaged   as waqi_roundtrip, but the value converted is what EPA defines for the real-time index: NowCast for
                      PM2.5/PM10, 8-hour mean for CO/O3, hourly for NO2/SO2. ASSUMPTION about what WAQI publishes; to be
                      checked against live ``iaqi`` (see docs/TIER_3/WAQI_AUDIT.md). It is the stress case.

Skill = 1 - MAE_model / MAE_persistence, persistence always the TRUE aqi_curr (same denominator as the D1 audit). CIs are
95% day-block bootstrap (1,000 resamples). ``all`` = every validation row Tier 2 scored, ``strict`` = label also inside
the window.

    python -m src.evaluation.waqi_roundtrip_audit [--horizons 24 1 6]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from src.evaluation.feature_availability_audit import (
    FEATURES_FROM, FEATURES_PATH, HISTORY_START, LABEL_LOOKAHEAD_H, OUT_DIR, evaluate, fidelity, predict_24h, predict_lgb, reconcile_24h,
)
from src.features.build_features import _stations_frame, compute_feature_frame, load_caaqms_offline
from src.features.compute_cpcb_aqi import POLLUTANTS as AQI_POLLUTANTS, compute_aqi
from src.live.epa_aqi import POLLUTANTS as WAQI_POLLUTANTS, roundtrip
from src.models.splits import TEST_START, VAL_END, VAL_START

DROPPED = ["nox", "no", "nh3", "temperature", "humidity", "wind_speed", "solar_radiation"]
NOWCAST_POLLUTANTS = ("pm25", "pm10")
EIGHT_HOUR = ("co", "o3")
SCENARIOS = {
    "baseline": "station sensors, stored AQI, as trained",
    "control_recomputed": "station sensors; AQI recomputed from the pollutants (as the live ingest does)",
    "masked_exact": "no NOx/NO/NH3, no weather or solar (weather_fill none); concentrations exact",
    "waqi_roundtrip": "masked_exact + concentration -> integer US-EPA AQI -> concentration (instantaneous)",
    "waqi_epa_averaged": "waqi_roundtrip on EPA-averaged values: NowCast PM, 8h CO/O3, 1h NO2/SO2 (assumption, stress case)",
}


def nowcast(series: pd.Series, floor: float = 0.5) -> pd.Series:
    """EPA NowCast of an hourly series: weighted 12-hour mean, weight factor max(min/max, 0.5); needs 2 of the last 3 hours."""
    lags = np.column_stack([series.shift(i).to_numpy(float) for i in range(12)])
    valid = ~np.isnan(lags)
    with np.errstate(invalid="ignore", divide="ignore"):
        hi, lo = np.nanmax(np.where(valid, lags, np.nan), axis=1), np.nanmin(np.where(valid, lags, np.nan), axis=1)
        weight = np.where(hi > 0, lo / hi, 1.0)
        weight = np.clip(weight, floor, 1.0)
        powers = weight[:, None] ** np.arange(12)[None, :]
        out = np.nansum(np.where(valid, lags, 0.0) * powers, axis=1) / np.nansum(np.where(valid, powers, 0.0), axis=1)
    out[valid[:, :3].sum(axis=1) < 2] = np.nan
    return pd.Series(out, index=series.index)


def _per_station(caaqms: pd.DataFrame, column: str, fn) -> pd.Series:
    out = pd.Series(np.nan, index=caaqms.index)
    for _, idx in caaqms.groupby("station_id").groups.items():
        sub = caaqms.loc[idx].sort_values("timestamp")
        sub = sub.set_index("timestamp")[column]
        sub = sub[~sub.index.duplicated(keep="last")].asfreq("h")
        res = fn(sub)
        out.loc[idx] = caaqms.loc[idx, "timestamp"].map(res).to_numpy()
    return out


def degrade(caaqms: pd.DataFrame, scenario: str) -> pd.DataFrame:
    out = caaqms.copy()
    if scenario in ("baseline", "control_recomputed"):
        return out
    out[DROPPED] = np.nan
    if scenario == "masked_exact":
        return out
    for pollutant in WAQI_POLLUTANTS:
        values = out[pollutant]
        if scenario == "waqi_epa_averaged":
            if pollutant in NOWCAST_POLLUTANTS:
                values = _per_station(out, pollutant, nowcast)
            elif pollutant in EIGHT_HOUR:
                values = _per_station(out, pollutant, lambda s: s.rolling(8, min_periods=6).mean())
        out[pollutant] = roundtrip(pollutant, values.to_numpy(float))
    return out


def recompute(caaqms: pd.DataFrame) -> pd.DataFrame:
    raw = caaqms.drop_duplicates(["station_id", "timestamp"]).rename(columns={"timestamp": "Timestamp"})
    raw = raw[["station_id", "station_name", "Timestamp", *AQI_POLLUTANTS]].sort_values(["station_id", "Timestamp"])
    aqi = compute_aqi(raw).dropna(subset=["aqi_value"])
    return aqi.assign(aqi_source="recomputed")


def build_frames(names: list[str]) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame]:
    features = pd.read_parquet(FEATURES_PATH)
    features["timestamp"] = pd.to_datetime(features["timestamp"]).dt.tz_convert(VAL_START.tz)
    stored_aqi = features[["station_id", "station_name", "timestamp", "aqi_curr", "aqi_source"]].rename(columns={"aqi_curr": "aqi_value"}).dropna(subset=["aqi_value"])
    raw = load_caaqms_offline(HISTORY_START, VAL_END.floor("h"))
    frames, inputs = {}, {}
    for name in names:
        degraded = degrade(raw, name)
        aqi = stored_aqi if name == "baseline" else recompute(degraded)
        inputs[name] = degraded
        frames[name] = compute_feature_frame(
            _stations_frame(), degraded, aqi, HISTORY_START, VAL_END.floor("h") + pd.Timedelta(hours=LABEL_LOOKAHEAD_H), FEATURES_FROM, VAL_END,
        )
        print(f"built {name}", flush=True)
    return frames, inputs, features, raw


def input_error(raw: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """How far each scenario's pollutant values sit from the true hourly concentration (validation window)."""
    window = (raw.timestamp >= VAL_START) & (raw.timestamp <= VAL_END)
    rows = []
    for name in ("waqi_roundtrip", "waqi_epa_averaged"):
        deg = inputs[name]
        for pollutant in WAQI_POLLUTANTS:
            truth, got = raw.loc[window, pollutant].to_numpy(float), deg.loc[window, pollutant].to_numpy(float)
            both = ~np.isnan(truth) & ~np.isnan(got)
            rows.append({"scenario": name, "pollutant": pollutant, "n": int(both.sum()), "unit": "mg/m3" if pollutant == "co" else "ug/m3",
                         "mean_true": truth[both].mean(), "mae": np.abs(got[both] - truth[both]).mean(),
                         "mae_pct_of_mean": 100 * np.abs(got[both] - truth[both]).mean() / truth[both].mean(),
                         "bias": (got[both] - truth[both]).mean(), "share_missing_after": float(np.isnan(got[~np.isnan(truth)]).mean())})
    return pd.DataFrame(rows)


def aqi_error(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    keys = ["station_id", "timestamp"]
    base = frames["baseline"].loc[lambda f: f.timestamp >= VAL_START, [*keys, "aqi_curr"]]
    rows = []
    for name, frame in frames.items():
        joined = base.merge(frame[[*keys, "aqi_curr"]], on=keys, suffixes=("", "_s")).dropna()
        rows.append({"scenario": name, "n": len(joined), "aqi_curr_mae_vs_stored": float((joined.aqi_curr_s - joined.aqi_curr).abs().mean()),
                     "aqi_curr_bias": float((joined.aqi_curr_s - joined.aqi_curr).mean())})
    return pd.DataFrame(rows)


def main(horizons: list[int]) -> int:
    frames, inputs, stored, raw = build_frames(list(SCENARIOS))
    for name, frame in frames.items():
        if len(frame) and frame.timestamp.max() >= TEST_START:
            raise SystemExit(f"{name}: rows at or after the test start; this audit must stay in validation")
    fid = fidelity(frames["baseline"], stored)

    results, reconciliation, max_diff = [], None, None
    dropped_rows: dict = {}
    for horizon in horizons:
        if horizon in (1, 6):
            try:
                import lightgbm  # noqa: F401
            except ImportError:
                print(f"skipping {horizon}h: lightgbm is not installed")
                continue
        predict = predict_24h if horizon == 24 else (lambda f, k, h=horizon: predict_lgb(f, k, h))
        target = f"target_aqi_{horizon}h"
        base_rows = frames["baseline"]
        base_rows = base_rows[(base_rows.timestamp >= VAL_START) & base_rows[target].notna() & base_rows.aqi_curr.notna()]
        keys = list(zip(base_rows.station_id, base_rows.timestamp))
        base_pred = predict(frames["baseline"], keys)
        if horizon == 24:
            reconciliation, max_diff = reconcile_24h(base_rows, base_pred)
            if not max_diff <= 1e-6:
                raise SystemExit(f"baseline differs from stored Tier 2 predictions (max {max_diff:.6f}); fix before use")
        # rows the scenario frames lost (recomputed AQI missing there) are dropped from EVERY scenario so all compare on the same rows
        common = set(keys)
        for frame in frames.values():
            common &= set(zip(frame.station_id, frame.timestamp))
        print(f"{horizon}h: {len(keys) - len(common)} of {len(keys)} baseline rows absent from a scenario frame; scoring {len(common)}", flush=True)
        keep = np.array([k in common for k in keys])
        base_rows, base_pred, keys = base_rows[keep], base_pred[keep], [k for k, f in zip(keys, keep) if f]
        dropped_rows[f"{horizon}h"] = int((~keep).sum())
        strict = (base_rows.timestamp + pd.Timedelta(hours=horizon) <= VAL_END).to_numpy()
        preds = {}
        for name, frame in frames.items():
            pred = preds[name] = predict(frame, keys)
            for row_set, mask in (("all", np.ones(len(base_rows), bool)), ("strict", strict)):
                res = evaluate(base_rows[mask], pred[mask], base_pred[mask], target)
                results.append({"horizon": f"{horizon}h", "basis": "official", "row_set": row_set, "scenario": name, "description": SCENARIOS[name], **res})
        # own basis: labels and persistence come from each scenario's own AQI (what the live pipeline scores against);
        # the delta is against control_recomputed, the same AQI definition with nothing degraded
        for name, frame in frames.items():
            if name == "baseline":
                continue
            sel = frame.set_index(["station_id", "timestamp"]).loc[keys].reset_index()
            ok = (sel[target].notna() & sel.aqi_curr.notna()).to_numpy()
            for row_set, mask in (("all", ok), ("strict", ok & strict)):
                res = evaluate(sel[mask], preds[name][mask], preds["control_recomputed"][mask], target)
                results.append({"horizon": f"{horizon}h", "basis": "own", "row_set": row_set, "scenario": name, "description": SCENARIOS[name], **res})
        print(f"done {horizon}h", flush=True)

    table, in_err, aqi_err = pd.DataFrame(results), input_error(raw, inputs), aqi_error(frames)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_DIR / "waqi_roundtrip_audit.csv", index=False)
    in_err.to_csv(OUT_DIR / "waqi_roundtrip_input_error.csv", index=False)
    aqi_err.to_csv(OUT_DIR / "waqi_roundtrip_aqi_error.csv", index=False)
    write_report(table, in_err, aqi_err, fid, reconciliation, max_diff)
    print(table[["horizon", "basis", "row_set", "scenario", "n", "mae", "mae_persistence", "skill_mae", "skill_ci_lo", "skill_ci_hi", "delta_mae_vs_baseline"]].round(3).to_string(index=False))
    print(aqi_err.round(3).to_string(index=False))
    print(in_err.round(3).to_string(index=False))
    return 0


def write_report(table, in_err, aqi_err, fid, reconciliation, max_diff) -> None:
    lines = [
        "# WAQI back-conversion audit, validation window only", "",
        f"Window {VAL_START:%Y-%m-%d} .. {VAL_END:%Y-%m-%d}. Frozen models, nothing trained or tuned. Generated by",
        "`src/evaluation/waqi_roundtrip_audit.py`; every number below comes from the CSVs next to this file.",
        f"Fidelity of the rebuilt baseline features against the stored matrix: {fid['share_of_cells_equal']:.4f} of cells equal over {fid['rows']:,} rows x {fid['columns']} columns.", "",
        "Skill = 1 - MAE_model / MAE_persistence (persistence is the true `aqi_curr`). CIs: 95% day-block bootstrap (1,000 resamples).",
        "Delta MAE = scenario minus baseline on the same rows (positive = worse). Basis `official`: labels and persistence are the stored official AQI;",
        "basis `own`: labels and persistence are the scenario's own recomputed AQI (what the live pipeline scores against) and the delta is vs `control_recomputed`.", "",
        "| Horizon | Basis | Rows scored | Scenario | Rows | MAE | Persistence MAE | Skill | Skill 95% CI | Delta MAE vs baseline | Delta 95% CI |",
        "| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: | ---: | :---: |",
    ]
    for r in table.itertuples():
        lines.append(f"| {r.horizon} | {r.basis} | {r.row_set} | {r.scenario} | {r.n:,} | {r.mae:.3f} | {r.mae_persistence:.3f} | {r.skill_mae:+.3f} | "
                     f"[{r.skill_ci_lo:+.3f}, {r.skill_ci_hi:+.3f}] | {r.delta_mae_vs_baseline:+.3f} | [{r.delta_mae_ci_lo:+.3f}, {r.delta_mae_ci_hi:+.3f}] |")
    lines += ["", "## AQI carried into the features (`aqi_curr`) versus the stored AQI", "",
              "| Scenario | Rows | MAE | Bias |", "| :--- | ---: | ---: | ---: |"]
    lines += [f"| {r.scenario} | {r.n:,} | {r.aqi_curr_mae_vs_stored:.3f} | {r.aqi_curr_bias:+.3f} |" for r in aqi_err.itertuples()]
    lines += ["", "## Pollutant inputs versus the true hourly concentration", "",
              "| Scenario | Pollutant | Unit | Rows | Mean | MAE | MAE % of mean | Bias | Share missing after |", "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    lines += [f"| {r.scenario} | {r.pollutant} | {r.unit} | {r.n:,} | {r.mean_true:.2f} | {r.mae:.3f} | {r.mae_pct_of_mean:.1f}% | {r.bias:+.3f} | {r.share_missing_after:.3f} |" for r in in_err.itertuples()]
    if reconciliation is not None:
        lines += ["", "## Baseline reconciliation with Tier 2 (24h)", "",
                  f"Max absolute difference to the stored frozen-model validation predictions: {max_diff:.2e}.", "",
                  "| Row set | Rows | Model MAE | Persistence MAE | Skill |", "| :--- | ---: | ---: | ---: | ---: |"]
        lines += [f"| {r.row_set} | {r.n:,} | {r.model_mae:.3f} | {r.persistence_mae:.3f} | {r.skill_mae:+.4f} |" for r in reconciliation.itertuples()]
    lines += ["", "Scenario definitions:", ""] + [f"- `{k}`: {v}" for k, v in SCENARIOS.items()]
    (OUT_DIR / "waqi_roundtrip_audit.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizons", nargs="+", type=int, default=[24, 1, 6], choices=[1, 6, 24])
    sys.exit(main(parser.parse_args().horizons))
