"""
train_quantile_forecast.py
===========================
Probabilistic 24h AQI forecasts (improvement plan T2.5).

Provides:
  * quantile regressors (alpha = 0.1, 0.5, 0.9) for target_aqi_24h;
  * split-conformal widening of the 80% interval, calibrated on validation
    (finite-sample corrected), next to a persistence + empirical-error-band baseline;
  * a reliability table + diagram and Brier score for P(AQI >= 401), compared
    against a persistence-based probability (training rate conditioned on the
    current AQI), a constant-rate reference, and a day-block bootstrap CI on the
    Brier difference.

Model selection is chronological and uses validation only:
  * number of boosting iterations per model = argmin of validation pinball loss
    (quantile models) / validation Brier (classifier) over ``staged_predict``;
    the previous version used scikit-learn's *random* 10% hold-out, which leaks
    neighbouring hours of an autocorrelated series into the stopping rule;
  * calendar features with / without = lower summed validation pinball loss.
Training rows are embargoed by 24h before the validation window.

Compute profiles (``T2_PROFILE``, ``src/models/tuning.py``): ``standard`` is the fixed configuration
behind the accepted results; ``max`` additionally runs a random hyper-parameter search per quantile
and for the classifier (default config always a candidate, chosen on validation pinball / Brier,
iterations from ``staged_predict``) and uses 10x more bootstrap resamples. Written to ``probabilistic/max/``.

Estimator: HistGradientBoosting with quantile / log-loss objectives (LightGBM is
not installed in the local venv; the Colab notebook can swap it in).

Outputs
-------
  reports/modeling/probabilistic/[<profile>/]quantile_metrics.csv / .md
  reports/modeling/probabilistic/[<profile>/]reliability_severe.csv / .png
  reports/modeling/probabilistic/[<profile>/]probabilistic_metrics.json
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import (  # noqa: E402
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)

from src.models.splits import assign_split, model_feature_columns, training_rows  # noqa: E402
from src.models.tuning import DEFAULT_CONFIG, get_profile, out_dir, search_configs  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "data" / "processed" / "features_extended.parquet"
PROFILE = get_profile()
OUT_DIR = out_dir(REPO_ROOT / "reports" / "modeling" / "probabilistic")
TARGET = "target_aqi_24h"
SEVERE = 401.0
ALPHAS = [0.1, 0.5, 0.9]
MAX_ITER = PROFILE["quantile_max_iter"]
TARGET_COVERAGE = 0.80
N_BOOT = PROFILE["n_boot"]
SEED = 42


def pinball(y: np.ndarray, q: np.ndarray, alpha: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1.0) * d)))


def coverage(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean((y >= lo) & (y <= hi)))


def brier(y_bin: np.ndarray, proba: np.ndarray) -> float:
    return float(np.mean((proba - y_bin) ** 2))


def conformal_pad(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, level: float) -> float:
    """Split-conformal (CQR) symmetric pad with the finite-sample quantile level."""
    scores = np.maximum(lo - y, y - hi)
    n = scores.size
    k = math.ceil((n + 1) * level)
    if k > n:
        return float("inf")
    return float(max(np.sort(scores)[k - 1], 0.0))


def reliability_table(y_bin, proba, n_bins=10) -> pd.DataFrame:
    bins = np.clip((proba * n_bins).astype(int), 0, n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = bins == b
        if mask.sum() == 0:
            continue
        rows.append({
            "bin": f"{b / n_bins:.1f}-{(b + 1) / n_bins:.1f}",
            "n": int(mask.sum()),
            "mean_predicted": round(float(proba[mask].mean()), 4),
            "observed_rate": round(float(y_bin[mask].mean()), 4),
        })
    return pd.DataFrame(rows)


def fit_quantile(train, val, cols, alpha, cfg=None):
    """Fit a quantile GBM; pick the iteration count on validation pinball loss."""
    cfg = DEFAULT_CONFIG if cfg is None else cfg
    model = HistGradientBoostingRegressor(
        loss="quantile", quantile=alpha, max_iter=MAX_ITER, early_stopping=False,
        random_state=42, **cfg,
    ).fit(train[cols], train[TARGET])
    y_val = val[TARGET].values
    losses = [pinball(y_val, p, alpha) for p in model.staged_predict(val[cols])]
    best = int(np.argmin(losses))
    return model, best, float(losses[best])


def staged_at(model, frame, cols, index):
    for i, pred in enumerate(model.staged_predict(frame[cols])):
        if i == index:
            return pred
    raise IndexError(index)


def fit_classifier(train_x, y_train, val_x, y_val, cfg=None):
    """Fit the severe-exceedance classifier; pick the iteration count on validation Brier."""
    cfg = DEFAULT_CONFIG if cfg is None else cfg
    clf = HistGradientBoostingClassifier(
        max_iter=MAX_ITER, early_stopping=False, random_state=42, **cfg,
    ).fit(train_x, y_train)
    briers = [brier(y_val, p[:, 1]) for p in clf.staged_predict_proba(val_x)]
    best = int(np.argmin(briers))
    return clf, best, float(briers[best])


def block_bootstrap_brier_diff(y_bin, p_model, p_base, days, n_boot, seed):
    rng = np.random.default_rng(seed)
    unique = np.unique(days)
    by_day = {d: np.flatnonzero(days == d) for d in unique}
    diffs = []
    for _ in range(n_boot):
        idx = np.concatenate([by_day[d] for d in rng.choice(unique, unique.size, replace=True)])
        diffs.append(brier(y_bin[idx], p_model[idx]) - brier(y_bin[idx], p_base[idx]))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


def plot_reliability(rel_model, rel_persist, path: Path) -> None:
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw={"width_ratios": [3, 2]})
    ax.plot([0, 1], [0, 1], "--", color="grey", label="perfect calibration")
    for rel, label, color in ((rel_model, "GBM classifier", "#d62728"),
                              (rel_persist, "persistence-based", "#1f77b4")):
        ax.plot(rel["mean_predicted"], rel["observed_rate"], "o-", color=color, label=label)
    ax.set_xlabel("mean predicted P(AQI >= 401)")
    ax.set_ylabel("observed frequency (test)")
    ax.set_title("Reliability: P(AQI >= 401) at 24h")
    ax.legend()
    ax.grid(alpha=0.3)
    width = 0.4
    x = np.arange(len(rel_model))
    ax2.bar(x - width / 2, rel_model["n"], width, color="#d62728", label="GBM classifier")
    pb = rel_persist.set_index("bin")["n"].reindex(rel_model["bin"]).fillna(0).values
    ax2.bar(x + width / 2, pb, width, color="#1f77b4", label="persistence-based")
    ax2.set_xticks(x)
    ax2.set_xticklabels(rel_model["bin"], rotation=60, fontsize=7)
    ax2.set_ylabel("test rows per bin")
    ax2.set_title("Forecast distribution")
    ax2.legend(fontsize=7)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main() -> None:
    frame = pd.read_parquet(FEATURES_PATH)
    frame["split"] = assign_split(frame["timestamp"])
    frame = frame.dropna(subset=[TARGET])
    train = training_rows(frame)
    val = frame[frame["split"] == "val"]
    test = frame[frame["split"] == "test"]
    y_val, y_test = val[TARGET].values, test[TARGET].values

    # --- quantile models: choose calendar on summed validation pinball loss -------------
    fits = {}
    for use_cal in (True, False):
        cols = model_feature_columns(frame, drop_calendar=not use_cal)
        per_alpha = {a: fit_quantile(train, val, cols, a) for a in ALPHAS}
        total = sum(v[2] for v in per_alpha.values())
        fits[use_cal] = (cols, per_alpha, total)
        print(f"calendar={use_cal}: {len(cols)} features, summed val pinball {total:.3f}", flush=True)
    use_cal = min(fits, key=lambda k: fits[k][2])
    cols, per_alpha, _ = fits[use_cal]
    print(f"selected calendar={use_cal}; best iterations "
          f"{ {a: v[1] + 1 for a, v in per_alpha.items()} }", flush=True)

    # non-standard profiles: random hyper-parameter search per quantile (validation pinball loss)
    best_params = {str(a): dict(DEFAULT_CONFIG) for a in ALPHAS}
    for a in ALPHAS if PROFILE["n_search"] else []:
        for n, cfg in enumerate(search_configs(PROFILE["n_search"])[1:], start=1):
            cand = fit_quantile(train, val, cols, a, cfg)
            improved = cand[2] < per_alpha[a][2]
            print(f"[q{a}] search {n}/{PROFILE['n_search']} {cfg} -> val pinball {cand[2]:.3f}"
                  f"{'  *' if improved else ''}", flush=True)
            if improved:
                per_alpha[a] = cand
                best_params[str(a)] = cfg

    preds = {a: {"val": staged_at(m, val, cols, best), "test": staged_at(m, test, cols, best)}
             for a, (m, best, _) in per_alpha.items()}
    # enforce monotone quantiles (independent fits can cross)
    for split in ("val", "test"):
        stack = np.sort(np.vstack([preds[a][split] for a in ALPHAS]), axis=0)
        for i, a in enumerate(ALPHAS):
            preds[a][split] = stack[i]

    # --- conformal interval + persistence-band baseline ---------------------------------
    pad = conformal_pad(y_val, preds[0.1]["val"], preds[0.9]["val"], TARGET_COVERAGE)
    resid_train = train[TARGET].values - train["aqi_curr"].values
    r_lo, r_hi = np.quantile(resid_train, [0.1, 0.9])
    band = {s: (p["aqi_curr"].values + r_lo, p["aqi_curr"].values + r_hi)
            for s, p in (("val", val), ("test", test))}
    band_pad = conformal_pad(y_val, *band["val"], TARGET_COVERAGE)

    rows = []
    for split, y in (("val", y_val), ("test", y_test)):
        lo, hi = preds[0.1][split], preds[0.9][split]
        b_lo, b_hi = band[split]
        rows.append({
            "split": split, "n": int(len(y)),
            "raw_80pct_coverage": round(coverage(y, lo, hi), 4),
            "conformal_80pct_coverage": round(coverage(y, lo - pad, hi + pad), 4),
            "conformal_pad": round(pad, 3),
            "raw_mean_width": round(float(np.mean(hi - lo)), 2),
            "conformal_mean_width": round(float(np.mean(hi - lo + 2 * pad)), 2),
            "persistence_band_coverage": round(coverage(y, b_lo - band_pad, b_hi + band_pad), 4),
            "persistence_band_mean_width": round(float(np.mean(b_hi - b_lo + 2 * band_pad)), 2),
        })
        print(f"[{split}] raw cov {rows[-1]['raw_80pct_coverage']:.3f} -> conformal "
              f"{rows[-1]['conformal_80pct_coverage']:.3f} (pad {pad:.2f}, width "
              f"{rows[-1]['conformal_mean_width']:.1f}); persistence band cov "
              f"{rows[-1]['persistence_band_coverage']:.3f} width {rows[-1]['persistence_band_mean_width']:.1f}")
    coverage_table = pd.DataFrame(rows)

    median_mae = float(np.mean(np.abs(preds[0.5]["test"] - y_test)))
    persistence_mae = float(np.mean(np.abs(test["aqi_curr"].values - y_test)))
    pinball_test = {str(a): round(pinball(y_test, preds[a]["test"], a), 3) for a in ALPHAS}

    # --- P(AQI >= 401): classifier iterations chosen on validation Brier -----------------
    y_bin_train = (train[TARGET].values >= SEVERE).astype(int)
    y_bin_val = (y_val >= SEVERE).astype(int)
    y_bin_test = (y_test >= SEVERE).astype(int)
    clf, best_clf, best_brier = fit_classifier(train[cols], y_bin_train, val[cols], y_bin_val)
    clf_params = dict(DEFAULT_CONFIG)
    for n, cfg in enumerate(search_configs(PROFILE["n_search"])[1:] if PROFILE["n_search"] else [], start=1):
        cand = fit_classifier(train[cols], y_bin_train, val[cols], y_bin_val, cfg)
        improved = cand[2] < best_brier
        print(f"[clf] search {n}/{PROFILE['n_search']} {cfg} -> val Brier {cand[2]:.4f}"
              f"{'  *' if improved else ''}", flush=True)
        if improved:
            clf, best_clf, best_brier = cand
            clf_params = cfg
    proba = None
    for i, p in enumerate(clf.staged_predict_proba(test[cols])):
        if i == best_clf:
            proba = p[:, 1]
            break

    curr = train["aqi_curr"].values
    base_rate = float(y_bin_train.mean())

    def persistence_proba(values):
        out = np.empty(len(values))
        for i, c in enumerate(values):
            near = np.abs(curr - c) <= 25
            out[i] = y_bin_train[near].mean() if near.any() else base_rate
        return out

    persist_proba = persistence_proba(test["aqi_curr"].values)
    rel_model = reliability_table(y_bin_test, proba)
    rel_persist = reliability_table(y_bin_test, persist_proba)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rel_model.to_csv(OUT_DIR / "reliability_severe.csv", index=False)
    rel_persist.to_csv(OUT_DIR / "reliability_severe_persistence.csv", index=False)
    plot_reliability(rel_model, rel_persist, OUT_DIR / "reliability_severe.png")

    days = pd.to_datetime(test["timestamp"]).dt.date.values
    diff_lo, diff_hi = block_bootstrap_brier_diff(y_bin_test, proba, persist_proba, days, N_BOOT, SEED)
    metrics = {
        "target": TARGET,
        "profile": PROFILE["name"],
        "n_boot": N_BOOT,
        "severe_threshold": SEVERE,
        "selected_calendar_features": bool(use_cal),
        "best_iterations": {str(a): v[1] + 1 for a, v in per_alpha.items()} | {"classifier": best_clf + 1},
        "best_params": best_params | {"classifier": clf_params},
        "embargo_hours": 24,
        "test_severe_rate": round(float(y_bin_test.mean()), 4),
        "train_severe_rate": round(base_rate, 4),
        "val_severe_rate": round(float(y_bin_val.mean()), 4),
        "brier_model": round(brier(y_bin_test, proba), 4),
        "brier_persistence": round(brier(y_bin_test, persist_proba), 4),
        "brier_constant_train_rate": round(brier(y_bin_test, np.full(len(y_bin_test), base_rate)), 4),
        "brier_diff_model_minus_persistence_ci95": [round(diff_lo, 4), round(diff_hi, 4)],
        "median_forecast_mae_test": round(median_mae, 3),
        "persistence_mae_test": round(persistence_mae, 3),
        "median_forecast_mae_skill": round(1 - median_mae / persistence_mae, 4),
        "pinball_test": pinball_test,
        "coverage": rows,
    }
    (OUT_DIR / "probabilistic_metrics.json").write_text(json.dumps(metrics, indent=2))
    coverage_table.to_csv(OUT_DIR / "quantile_metrics.csv", index=False)

    lines = [
        "# Probabilistic 24h AQI forecast metrics",
        "",
        "Quantile regressors (alpha = 0.1 / 0.5 / 0.9) plus split-conformal calibration of",
        "the 80% interval on validation (finite-sample corrected). Target: `target_aqi_24h`.",
        f"Profile: `{PROFILE['name']}`. Iteration counts"
        + (" and hyper-parameters" if PROFILE["n_search"] else "")
        + " are chosen chronologically on validation; 24h train embargo.",
        "The persistence band is `aqi_now` + empirical 10-90% train residual quantiles,",
        "conformally padded the same way.",
        "",
        "## 80% interval coverage and sharpness",
        "",
        "| Split | N | Raw cov. | Conformal cov. | Pad | Raw width | Conformal width | Persist.-band cov. | Persist.-band width |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        lines.append(
            f"| {r['split']} | {r['n']:,} | {r['raw_80pct_coverage']:.3f} | "
            f"{r['conformal_80pct_coverage']:.3f} | {r['conformal_pad']} | {r['raw_mean_width']} | "
            f"{r['conformal_mean_width']} | {r['persistence_band_coverage']:.3f} | "
            f"{r['persistence_band_mean_width']} |"
        )
    lines += [
        "",
        "## Median forecast (test)",
        "",
        f"- Median-model MAE **{median_mae:.2f}** vs persistence **{persistence_mae:.2f}** "
        f"(skill {metrics['median_forecast_mae_skill']:+.4f}); pinball loss {pinball_test}.",
        "",
        "## P(AQI >= 401) calibration (test)",
        "",
        f"- Severe rate: train {base_rate:.4f}, val {metrics['val_severe_rate']:.4f}, "
        f"**test {metrics['test_severe_rate']:.4f}**",
        f"- Brier score, GBM classifier: **{metrics['brier_model']}**",
        f"- Brier score, persistence-based: **{metrics['brier_persistence']}**",
        f"- Brier score, constant train rate: {metrics['brier_constant_train_rate']}",
        f"- Brier difference (model - persistence), 95% day-block CI: "
        f"[{diff_lo:+.4f}, {diff_hi:+.4f}] (negative = model better)",
        "",
        "Reliability: `reliability_severe.csv` / `reliability_severe_persistence.csv`, diagram in",
        "`reliability_severe.png`.",
    ]
    (OUT_DIR / "quantile_metrics.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: metrics[k] for k in (
        "test_severe_rate", "brier_model", "brier_persistence",
        "brier_constant_train_rate", "median_forecast_mae_skill")}, indent=2))
    print(f"Wrote {OUT_DIR / 'quantile_metrics.md'}")


if __name__ == "__main__":
    main()
