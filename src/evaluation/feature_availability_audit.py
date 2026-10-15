"""Feature-availability audit for the live pipeline (decision D1, option A). Validation window only.

Question: the frozen models were trained with every station input present. Live, some inputs will be
missing or come from another source. How much skill vs persistence is lost?

Scenarios (the same frozen models, features rebuilt through the shared ``compute_feature_frame``):
  baseline            all inputs from station sensors, as trained
  openaq_filled       OpenAQ primary: no solar radiation anywhere, no weather at ITO; the gaps are filled from
                      Open-Meteo (ERA5 here, as a stand-in for the live analysis feed)
  openaq_unfilled     the same gaps left empty (what happens if we do nothing)
  datagovin_filled    data.gov.in primary: no NOx, no station weather; weather from Open-Meteo, NOx missing
  datagovin_unfilled  the same, weather also left empty

Rules: only rows in the validation window (2025-09-01 .. 2025-10-31) are scored; the module refuses to run if any
row at or after the test start sneaks in. Nothing is trained or tuned. The 24h hybrid needs only scikit-learn;
the 1h/6h LightGBM models need ``lightgbm`` (Colab) and are skipped, loudly, when it is missing.

Caveats written into the report: ERA5 is reanalysis, not the live forecast/analysis feed; the stored 1h/6h models were
trained on the database-built matrix while this audit rebuilds features from the raw CSVs (the report prints how closely
the two agree); the validation window is a calmer season than the winter test window.

    python -m src.evaluation.feature_availability_audit [--horizons 24 1 6]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src.features.build_features import _stations_frame, compute_feature_frame, load_caaqms_offline
from src.models.phase_6c_refinement import construct_causal_long_horizon_features
from src.models.splits import KST, TEST_START, VAL_END, VAL_START

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_extended.parquet"
WEATHER_PATH = REPO_ROOT / "data" / "processed" / "exogenous_weather.parquet"
OUT_DIR = REPO_ROOT / "reports" / "modeling" / "live_audit"

HISTORY_START = pd.Timestamp("2025-05-01", tz=KST)  # raw data loaded from here
FEATURES_FROM = pd.Timestamp("2025-07-01", tz=KST)  # rows built from here so multi-day lags have history
# live_readings column -> (Open-Meteo column, multiplier to our unit). Open-Meteo returns wind in km/h by default
# (the ERA5 fetch never sets wind_speed_unit), our station sensors report m/s.
WEATHER_FILL = {
    "temperature": ("temperature_2m", 1.0),
    "humidity": ("relative_humidity_2m", 1.0),
    "wind_speed": ("wind_speed_10m", 1.0 / 3.6),
    "solar_radiation": ("shortwave_radiation", 1.0),
}
OPENAQ_GAPS = {"*": ["solar_radiation"], "ITO": ["temperature", "humidity", "wind_speed"]}
DATAGOVIN_GAPS = {"*": ["nox", "temperature", "humidity", "wind_speed", "solar_radiation"]}
SCENARIOS = {
    "baseline": ("all station inputs, as trained", {}, False),
    "openaq_filled": (
        "OpenAQ primary; no solar anywhere, no ITO weather; gaps filled from Open-Meteo",
        OPENAQ_GAPS,
        True,
    ),
    "openaq_unfilled": ("OpenAQ primary; the same gaps left empty", OPENAQ_GAPS, False),
    "datagovin_filled": ("data.gov.in primary; NOx missing, weather from Open-Meteo", DATAGOVIN_GAPS, True),
    "datagovin_unfilled": ("data.gov.in primary; NOx and weather all missing", DATAGOVIN_GAPS, False),
}
LABEL_LOOKAHEAD_H = 24
N_BOOT = 1000
SEED = 42


def apply_scenario(caaqms: pd.DataFrame, gaps: dict, fill: bool, weather: pd.DataFrame | None) -> pd.DataFrame:
    """Return a copy of the station telemetry with the scenario's inputs removed (and optionally refilled)."""
    out = caaqms.copy()
    masked: dict[str, set] = {}
    for who, columns in gaps.items():
        rows = np.ones(len(out), dtype=bool) if who == "*" else (out["station_name"] == who).to_numpy()
        for column in columns:
            out.loc[rows, column] = np.nan
            masked.setdefault(column, set()).add(who)
    if fill and weather is not None:
        merged = out[["station_name", "timestamp"]].merge(weather, on=["station_name", "timestamp"], how="left")
        for column, (source, factor) in WEATHER_FILL.items():
            if column not in masked:
                continue
            rows = (
                np.ones(len(out), dtype=bool)
                if "*" in masked[column]
                else out["station_name"].isin(masked[column]).to_numpy()
            )
            out.loc[rows, column] = (
                (merged.loc[rows.nonzero()[0], source].to_numpy() * factor) if rows.any() else np.nan
            )
    return out


def load_weather() -> pd.DataFrame:
    weather = pd.read_parquet(WEATHER_PATH)
    weather["timestamp"] = pd.to_datetime(weather["timestamp"]).dt.tz_localize(KST)
    return weather[["station_name", "timestamp", *[v[0] for v in WEATHER_FILL.values()]]]


def day_block_bootstrap(day_ids: np.ndarray, per_row: dict[str, np.ndarray], n_boot: int = N_BOOT, seed: int = SEED):
    """Resample whole days; return the per-day sums so callers can form any ratio. Shapes: (days,)."""
    days, inverse = np.unique(day_ids, return_inverse=True)
    sums = {k: np.bincount(inverse, weights=v, minlength=len(days)) for k, v in per_row.items()}
    counts = np.bincount(inverse, minlength=len(days)).astype(float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(days), size=(n_boot, len(days)))
    return sums, counts, draws


def evaluate(frame: pd.DataFrame, prediction: np.ndarray, base_prediction: np.ndarray, target: str) -> dict:
    y, persist = frame[target].to_numpy(float), frame["aqi_curr"].to_numpy(float)
    err_s, err_b, err_p = np.abs(prediction - y), np.abs(base_prediction - y), np.abs(persist - y)
    day = frame["timestamp"].dt.strftime("%Y-%m-%d").to_numpy()
    sums, counts, draws = day_block_bootstrap(day, {"s": err_s, "b": err_b, "p": err_p})
    n = counts[draws].sum(axis=1)
    mae_s, mae_p = sums["s"][draws].sum(axis=1) / n, sums["p"][draws].sum(axis=1) / n
    skill = 1 - mae_s / mae_p
    d_mae = (sums["s"][draws].sum(axis=1) - sums["b"][draws].sum(axis=1)) / n
    point = {"n": len(frame), "mae": err_s.mean(), "mae_persistence": err_p.mean(), "mae_baseline": err_b.mean()}
    point["skill_mae"] = 1 - point["mae"] / point["mae_persistence"]
    point["delta_mae_vs_baseline"] = point["mae"] - point["mae_baseline"]
    return {
        **point,
        "skill_ci_lo": float(np.percentile(skill, 2.5)),
        "skill_ci_hi": float(np.percentile(skill, 97.5)),
        "delta_mae_ci_lo": float(np.percentile(d_mae, 2.5)),
        "delta_mae_ci_hi": float(np.percentile(d_mae, 97.5)),
    }


# --------------------------------------------------------------------------- models
def _select(frame: pd.DataFrame, keys: list) -> pd.DataFrame:
    return frame.set_index(["station_id", "timestamp"]).loc[keys]


def predict_24h(frame: pd.DataFrame, keys: list) -> np.ndarray:
    """The frozen 50/50 hybrid: 0.5 x persistence + 0.5 x Ridge on the 49 refined features.

    ``frame`` is the full built frame (from before the window) so the multi-day lags have their history;
    ``keys`` picks the (station_id, timestamp) rows to score.
    """
    folder = REPO_ROOT / "models" / "24h" / "final"
    ridge, scaler, imputer = (
        joblib.load(folder / f)
        for f in ("24h_final_model.joblib", "scaler_final_24h.joblib", "imputer_final_24h.joblib")
    )
    columns = joblib.load(folder / "feature_names_final.joblib")
    chosen = _select(construct_causal_long_horizon_features(frame), keys)
    ridge_part = ridge.predict(scaler.transform(imputer.transform(chosen[columns])))
    return 0.5 * chosen["aqi_curr"].to_numpy(float) + 0.5 * ridge_part


def predict_lgb(frame: pd.DataFrame, keys: list, horizon: int) -> np.ndarray:
    model = joblib.load(REPO_ROOT / "models" / f"lgb_model_{horizon}h_v1.joblib")
    chosen = _select(frame, keys).reset_index()
    for name in frame["station_name"].unique():
        chosen[f"station_{name.replace(' ', '_')}"] = (chosen["station_name"] == name).astype(float)
    names = (
        model.feature_name() if hasattr(model, "feature_name") else model.feature_name_
    )  # the stored models are lightgbm.Booster
    return model.predict(chosen[list(names)])


# --------------------------------------------------------------------------- run
def build_frames(scenarios: list[str]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    stored = pd.read_parquet(FEATURES_PATH)
    stored["timestamp"] = pd.to_datetime(stored["timestamp"]).dt.tz_convert(KST)
    aqi = (
        stored[["station_id", "station_name", "timestamp", "aqi_curr", "aqi_source"]]
        .rename(columns={"aqi_curr": "aqi_value"})
        .dropna(subset=["aqi_value"])
    )
    caaqms = load_caaqms_offline(HISTORY_START, VAL_END.floor("h"))
    weather = load_weather()
    frames = {}
    for name in scenarios:
        _, gaps, fill = SCENARIOS[name]
        # The index runs 24 h past the window so the last day's issue times keep their 24h-ahead label, as in Tier 2
        # (9,590 validation rows). Features still stop at VAL_END; only labels reach into Nov 1 (see the reconciliation).
        frames[name] = compute_feature_frame(
            _stations_frame(),
            apply_scenario(caaqms, gaps, fill, weather),
            aqi,
            HISTORY_START,
            VAL_END.floor("h") + pd.Timedelta(hours=LABEL_LOOKAHEAD_H),
            FEATURES_FROM,
            VAL_END,
        )
    return frames, stored


def _row_metrics(label: str, y, model, persistence) -> dict:
    mae, p = float(np.abs(model - y).mean()), float(np.abs(persistence - y).mean())
    return {"row_set": label, "n": len(y), "model_mae": mae, "persistence_mae": p, "skill_mae": 1 - mae / p}


def reconcile_24h(rows: pd.DataFrame, rebuilt: np.ndarray) -> tuple[pd.DataFrame, float]:
    """Compare the audit baseline with Tier 2's stored validation predictions (frozen 24h model, and the extended model).

    ``rows`` are the audit's scored rows (aligned with ``rebuilt``). Returns the table and the max |audit - stored|.
    """
    folder = REPO_ROOT / "reports" / "modeling" / "24h" / "final"
    out, max_diff = [], float("nan")
    frozen = pd.read_parquet(folder / "val_predictions.parquet")
    frozen["timestamp"] = pd.to_datetime(frozen["timestamp"]).dt.tz_convert(KST)
    out.append(
        _row_metrics(
            "Tier 2 stored frozen predictions, all validation rows",
            frozen.target_aqi_24h.to_numpy(float),
            frozen.prediction_hybrid_6c_winning.to_numpy(float),
            frozen.prediction_naive_persistence.to_numpy(float),
        )
    )
    mine = (
        rows[["station_id", "timestamp"]]
        .assign(rebuilt=rebuilt)
        .merge(frozen, on=["station_id", "timestamp"], how="inner")
    )
    out.append(
        _row_metrics(
            "Audit baseline (rebuilt features, frozen model), same rows",
            mine.target_aqi_24h.to_numpy(float),
            mine.rebuilt.to_numpy(float),
            mine.prediction_naive_persistence.to_numpy(float),
        )
    )
    max_diff = float((mine.rebuilt - mine.prediction_hybrid_6c_winning).abs().max())
    strict = mine[mine.timestamp + pd.Timedelta(hours=24) <= VAL_END]
    out.append(
        _row_metrics(
            "Audit baseline, strict: label also inside the validation window",
            strict.target_aqi_24h.to_numpy(float),
            strict.rebuilt.to_numpy(float),
            strict.prediction_naive_persistence.to_numpy(float),
        )
    )
    ext_path = folder / "val_predictions_extended.parquet"
    if ext_path.exists():
        ext = pd.read_parquet(ext_path)
        out.append(
            _row_metrics(
                "Tier 2 EXTENDED model (trained with 2024 data; a different model), all rows",
                ext.target_aqi_24h.to_numpy(float),
                ext.prediction_hybrid_6c_winning.to_numpy(float),
                ext.prediction_naive_persistence.to_numpy(float),
            )
        )
    return pd.DataFrame(out), max_diff


def fidelity(frame: pd.DataFrame, stored: pd.DataFrame) -> dict:
    """How closely the rebuilt baseline matches the stored matrix on validation rows."""
    keys = ["station_id", "timestamp"]
    val = frame[(frame.timestamp >= VAL_START)]
    joined = val.merge(stored, on=keys, suffixes=("", "_stored"))
    shared = [
        c for c in val.columns if c not in keys and f"{c}_stored" in joined and pd.api.types.is_float_dtype(val[c])
    ]
    close = np.mean(
        [np.isclose(joined[c], joined[f"{c}_stored"], rtol=1e-6, atol=1e-6, equal_nan=True).mean() for c in shared]
    )
    return {"rows": len(joined), "columns": len(shared), "share_of_cells_equal": float(close)}


def main(horizons: list[int]) -> int:
    frames, stored = build_frames(list(SCENARIOS))
    for name, frame in frames.items():  # hard guard: validation only
        if len(frame) and frame.timestamp.max() >= TEST_START:
            raise SystemExit(f"{name}: rows at or after the test start; this audit must stay in validation")
    fid = fidelity(frames["baseline"], stored)

    results, reconciliation, max_diff = [], None, None
    for horizon in horizons:
        if horizon in (1, 6):
            try:
                import lightgbm  # noqa: F401
            except ImportError:
                print(f"skipping {horizon}h: lightgbm is not installed (run on Colab)")
                continue
        predict = predict_24h if horizon == 24 else (lambda f, k, h=horizon: predict_lgb(f, k, h))
        target = f"target_aqi_{horizon}h"
        base_rows = frames["baseline"]
        base_rows = base_rows[
            (base_rows.timestamp >= VAL_START) & base_rows[target].notna() & base_rows.aqi_curr.notna()
        ]
        keys = list(zip(base_rows.station_id, base_rows.timestamp))
        base_pred = predict(frames["baseline"], keys)
        if horizon == 24:
            reconciliation, max_diff = reconcile_24h(base_rows, base_pred)
            if not max_diff <= 1e-6:
                raise SystemExit(
                    f"audit baseline differs from the stored Tier 2 validation predictions (max {max_diff:.6f}); fix before use"
                )
        # "all" keeps every row Tier 2 scored (the stored-prediction guard above runs on these); "strict" keeps only rows whose
        # label also lies inside the validation window, i.e. drops the last `horizon` hours before the test start.
        strict = (base_rows.timestamp + pd.Timedelta(hours=horizon) <= VAL_END).to_numpy()
        for name, frame in frames.items():
            pred = predict(frame, keys)
            for row_set, mask in (("all", np.ones(len(base_rows), bool)), ("strict", strict)):
                res = evaluate(base_rows[mask], pred[mask], base_pred[mask], target)
                results.append(
                    {
                        "horizon": f"{horizon}h",
                        "row_set": row_set,
                        "scenario": name,
                        "description": SCENARIOS[name][0],
                        **res,
                    }
                )
        print(f"done {horizon}h", flush=True)

    table = pd.DataFrame(results)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_DIR / "feature_availability_audit.csv", index=False)
    write_report(table, fid, reconciliation, max_diff)
    print(
        table[["horizon", "row_set", "scenario", "n", "mae", "mae_persistence", "skill_mae", "delta_mae_vs_baseline"]]
        .round(3)
        .to_string(index=False)
    )
    return 0


def write_report(
    table: pd.DataFrame, fid: dict, reconciliation: pd.DataFrame | None = None, max_diff: float | None = None
) -> None:
    lines = [
        "# Feature-availability audit (decision D1), validation window only",
        "",
        f"Window {VAL_START:%Y-%m-%d} .. {VAL_END:%Y-%m-%d}. Frozen models, nothing trained or tuned. Generated by",
        "`src/evaluation/feature_availability_audit.py`; numbers come from `feature_availability_audit.csv`.",
        f"Fidelity of the rebuilt baseline features against the stored matrix: {fid['share_of_cells_equal']:.4f} of cells equal over {fid['rows']:,} rows x {fid['columns']} columns.",
        "",
        "Skill = 1 - MAE_model / MAE_persistence. CIs are 95% day-block bootstrap (1,000 resamples).",
        "Delta MAE is the scenario minus the baseline on the same rows (positive = worse).",
        "",
        "`all` = every validation row Tier 2 scored (the stored-prediction guard runs on these); `strict` = only rows whose label",
        "also lies inside the validation window (drops the last `horizon` hours of October).",
        "",
        "| Horizon | Rows scored | Scenario | Rows | MAE | Persistence MAE | Skill | Skill 95% CI | Delta MAE vs baseline | Delta 95% CI |",
        "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: | ---: | :---: |",
    ]
    for r in table.itertuples():
        lines.append(
            f"| {r.horizon} | {r.row_set} | {r.scenario} | {r.n:,} | {r.mae:.3f} | {r.mae_persistence:.3f} | {r.skill_mae:+.3f} | "
            f"[{r.skill_ci_lo:+.3f}, {r.skill_ci_hi:+.3f}] | {r.delta_mae_vs_baseline:+.3f} | [{r.delta_mae_ci_lo:+.3f}, {r.delta_mae_ci_hi:+.3f}] |"
        )
    if reconciliation is not None:
        lines += [
            "",
            "## Baseline reconciliation with Tier 2 (24h, validation)",
            "",
            "The audit baseline reproduces Tier 2's stored frozen-model validation predictions "
            f"(max absolute difference per row {max_diff:.6f}); the audit refuses to run otherwise. "
            "Same frozen imputer, scaler and Ridge; no embargo or refit is involved because nothing is trained.",
            "",
            "| Row set | Rows | Model MAE | Persistence MAE | Skill |",
            "| :--- | ---: | ---: | ---: | ---: |",
        ]
        lines += [
            f"| {r.row_set} | {r.n:,} | {r.model_mae:.3f} | {r.persistence_mae:.3f} | {r.skill_mae:+.4f} |"
            for r in reconciliation.itertuples()
        ]
        lines += [
            "",
            "The strict row set drops the last day of October (issue times 2025-10-31, labels on 2025-11-01), which is the "
            "hardest day in the window; the default row set keeps it, as Tier 2 did. Its labels are the first test-window day.",
        ]
        reconciliation.to_csv(OUT_DIR / "baseline_reconciliation_24h.csv", index=False)
    lines += ["", "Scenario definitions:", ""] + [f"- `{k}`: {v[0]}" for k, v in SCENARIOS.items()]
    (OUT_DIR / "feature_availability_audit.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--horizons", nargs="+", type=int, default=[24, 1, 6], choices=[1, 6, 24])
    sys.exit(main(parser.parse_args().horizons))
