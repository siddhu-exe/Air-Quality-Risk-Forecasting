"""Side check: calibrate recomputed AQI to the official scale, feed the FROZEN models, score on validation.

The frozen models were trained on the official AQI; the live pipeline recomputes AQI, which sits ~5.5 points higher on average.
Alternative to retraining: map the recomputed series onto the official scale and keep the frozen models. The map is fitted on the
training window only (2025-01-01 .. 2025-08-31, where both series exist), as a monotone isotonic regression on the hourly AQI pairs;
validation (2025-09-01 .. 2025-10-31) is only scored, the test window is never read. Nothing is trained except that one map.

Two bases for the same frozen predictions:
  official     labels and persistence are the stored official AQI (how well calibrated-recomputed inputs stand in for official ones)
  calibrated   labels and persistence are the calibrated recomputed AQI (what the live pipeline would score against if it calibrated)

Use of the result: the calibration is adopted only if its validation skill beats the live-consistent retrain's validation skill
(src/models/live_retrain.py). That comparison is made by the person reading docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md.

    python -m src.evaluation.calibration_side_check [--horizons 24 1 6]
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

from src.evaluation.feature_availability_audit import (
    FEATURES_FROM,
    FEATURES_PATH,
    HISTORY_START,
    LABEL_LOOKAHEAD_H,
    OUT_DIR,
    evaluate,
    predict_24h,
    predict_lgb,
)
from src.features.build_features import _stations_frame, compute_feature_frame, load_caaqms_offline
from src.features.build_live_matrix import recomputed_aqi
from src.live.qc import apply_qc
from src.models.splits import KST, TEST_START, VAL_END, VAL_START

FIT_START, FIT_END = pd.Timestamp("2025-01-01", tz=KST), pd.Timestamp("2025-08-31 23:00", tz=KST)


def fit_calibration(recomputed: pd.DataFrame, official: pd.DataFrame) -> tuple[IsotonicRegression, pd.DataFrame]:
    keys = ["station_id", "timestamp"]
    pairs = recomputed.merge(official, on=keys, suffixes=("_recomputed", "_official")).dropna()
    train = pairs[(pairs.timestamp >= FIT_START) & (pairs.timestamp <= FIT_END)]
    iso = IsotonicRegression(increasing=True, out_of_bounds="clip").fit(train["aqi_value_recomputed"], train["aqi_value_official"])
    rows = []
    for name, part in (("fit window 2025-01..08", train), ("validation 2025-09..10", pairs[(pairs.timestamp >= VAL_START) & (pairs.timestamp <= VAL_END)])):
        before = part["aqi_value_recomputed"] - part["aqi_value_official"]
        after = iso.predict(part["aqi_value_recomputed"]) - part["aqi_value_official"]
        rows.append({"rows": name, "n": len(part), "mae_before": before.abs().mean(), "bias_before": before.mean(),
                     "mae_after": np.abs(after).mean(), "bias_after": float(np.mean(after))})
    return iso, pd.DataFrame(rows)


def main(horizons: list[int]) -> int:
    stored = pd.read_parquet(FEATURES_PATH)
    stored["timestamp"] = pd.to_datetime(stored["timestamp"]).dt.tz_convert(KST)
    official = stored.loc[stored.aqi_source == "official", ["station_id", "station_name", "timestamp", "aqi_curr"]].rename(columns={"aqi_curr": "aqi_value"}).dropna()
    stored_aqi = stored[["station_id", "station_name", "timestamp", "aqi_curr", "aqi_source"]].rename(columns={"aqi_curr": "aqi_value"}).dropna(subset=["aqi_value"])

    caaqms, _ = apply_qc(load_caaqms_offline(FIT_START - pd.Timedelta(days=2), VAL_END.floor("h")))
    recomputed = recomputed_aqi(caaqms)
    iso, fit_table = fit_calibration(recomputed[["station_id", "timestamp", "aqi_value"]], official[["station_id", "timestamp", "aqi_value"]])
    calibrated = recomputed.assign(aqi_value=iso.predict(recomputed["aqi_value"]))

    end = VAL_END.floor("h") + pd.Timedelta(hours=LABEL_LOOKAHEAD_H)
    raw = caaqms[caaqms.timestamp >= HISTORY_START]
    frames = {name: compute_feature_frame(_stations_frame(), raw, aqi, HISTORY_START, end, FEATURES_FROM, VAL_END)
              for name, aqi in (("baseline", stored_aqi), ("calibrated", calibrated))}
    for name, frame in frames.items():
        if len(frame) and frame.timestamp.max() >= TEST_START:
            raise SystemExit(f"{name}: rows at or after the test start")

    results = []
    for horizon in horizons:
        if horizon in (1, 6):
            try:
                import lightgbm  # noqa: F401
            except ImportError:
                print(f"skipping {horizon}h: lightgbm is not installed")
                continue
        predict = predict_24h if horizon == 24 else (lambda f, k, h=horizon: predict_lgb(f, k, h))
        target = f"target_aqi_{horizon}h"
        base = frames["baseline"]
        base = base[(base.timestamp >= VAL_START) & base[target].notna() & base.aqi_curr.notna()]
        keys = list(zip(base.station_id, base.timestamp))
        calib = frames["calibrated"].set_index(["station_id", "timestamp"]).reindex(keys).reset_index()
        ok = (calib[target].notna() & calib.aqi_curr.notna()).to_numpy()
        keys_ok = [k for k, f in zip(keys, ok) if f]
        base_ok, calib_ok = base[ok], calib[ok]
        base_pred, calib_pred = predict(frames["baseline"], keys_ok), predict(frames["calibrated"], keys_ok)
        strict = (base_ok.timestamp + pd.Timedelta(hours=horizon) <= VAL_END).to_numpy()
        for row_set, mask in (("all", np.ones(len(base_ok), bool)), ("strict", strict)):
            results.append({"horizon": f"{horizon}h", "basis": "official (baseline, frozen models on official inputs)", "row_set": row_set, "scenario": "baseline",
                            **evaluate(base_ok[mask], base_pred[mask], base_pred[mask], target)})
            results.append({"horizon": f"{horizon}h", "basis": "official", "row_set": row_set, "scenario": "calibrated inputs",
                            **evaluate(base_ok[mask], calib_pred[mask], base_pred[mask], target)})
            results.append({"horizon": f"{horizon}h", "basis": "calibrated", "row_set": row_set, "scenario": "calibrated inputs",
                            **evaluate(calib_ok[mask], calib_pred[mask], base_pred[mask], target)})
        print(f"done {horizon}h", flush=True)

    table = pd.DataFrame(results)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_DIR / "calibration_side_check.csv", index=False)
    fit_table.to_csv(OUT_DIR / "calibration_side_check_fit.csv", index=False)
    lines = ["# Side check: recomputed AQI calibrated to the official scale, frozen models, validation only", "",
             "Generated by `src/evaluation/calibration_side_check.py`; numbers come from `calibration_side_check.csv`. The isotonic map is fitted on",
             "2025-01-01 .. 2025-08-31 only; the test window is not read. Skill = 1 - MAE_model / MAE_persistence; CIs 95% day-block bootstrap (1,000 resamples).",
             "Delta MAE is vs the frozen models on the official inputs (positive = worse). See the module docstring for the two bases.", "",
             "## The calibration map (hourly AQI pairs, recomputed vs official)", "",
             "| Rows | n | MAE before | Bias before | MAE after | Bias after |", "| :--- | ---: | ---: | ---: | ---: | ---: |"]
    lines += [f"| {r.rows} | {r.n:,} | {r.mae_before:.2f} | {r.bias_before:+.2f} | {r.mae_after:.2f} | {r.bias_after:+.2f} |" for r in fit_table.itertuples()]
    lines += ["", "## Frozen models on calibrated inputs", "",
              "| Horizon | Basis | Rows scored | Scenario | Rows | MAE | Persistence MAE | Skill | Skill 95% CI | Delta MAE | Delta 95% CI |",
              "| :--- | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: | ---: | :---: |"]
    lines += [f"| {r.horizon} | {r.basis} | {r.row_set} | {r.scenario} | {r.n:,} | {r.mae:.3f} | {r.mae_persistence:.3f} | {r.skill_mae:+.3f} | "
              f"[{r.skill_ci_lo:+.3f}, {r.skill_ci_hi:+.3f}] | {r.delta_mae_vs_baseline:+.3f} | [{r.delta_mae_ci_lo:+.3f}, {r.delta_mae_ci_hi:+.3f}] |" for r in table.itertuples()]
    (OUT_DIR / "calibration_side_check.md").write_text("\n".join(lines) + "\n")
    print(fit_table.round(3).to_string(index=False))
    print(table[["horizon", "basis", "row_set", "scenario", "n", "mae", "mae_persistence", "skill_mae", "skill_ci_lo", "skill_ci_hi", "delta_mae_vs_baseline"]].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizons", nargs="+", type=int, default=[24, 1, 6], choices=[1, 6, 24])
    sys.exit(main(parser.parse_args().horizons))
