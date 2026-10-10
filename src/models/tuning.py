"""Compute profiles and a validation-only hyper-parameter search for the Tier 2 scripts.

Select a profile with the ``T2_PROFILE`` environment variable (the Colab notebook sets it):

  standard  the configuration behind the accepted results (default; fixed GBM settings)
  max       more compute: random hyper-parameter search plus validation-chosen iteration
            counts and 10x more bootstrap resamples. Results go to ``<out>/max/``.
  smoke     seconds-long run that only checks the code paths. Results go to ``<out>/smoke/``.

Rules that do not change with the profile: every choice (variant, calendar features,
hyper-parameters, number of boosting iterations) is made on validation only, test is
scored once, and the default configuration is always one of the candidates, so on
validation the search can only match or improve the default.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

PROFILE_ENV = "T2_PROFILE"

# Equal to scikit-learn's defaults except learning_rate / max_leaf_nodes, i.e. the settings
# the "standard" profile uses, so a search that picks it reproduces the standard result.
DEFAULT_CONFIG = {
    "learning_rate": 0.05,
    "max_leaf_nodes": 31,
    "min_samples_leaf": 20,
    "l2_regularization": 0.0,
    "max_features": 1.0,
}
SEARCH_SPACE = {
    "learning_rate": [0.02, 0.03, 0.05, 0.08, 0.1],
    "max_leaf_nodes": [15, 31, 63, 127],
    "min_samples_leaf": [20, 50, 100, 200],
    "l2_regularization": [0.0, 1.0, 10.0, 100.0],
    "max_features": [0.5, 0.7, 1.0],
}
PROFILES = {
    "standard": {"n_boot": 1000, "n_search": 0, "pm25_max_iter": 400,
                 "quantile_max_iter": 400, "ablation_max_iter": 300},
    "max": {"n_boot": 10000, "n_search": 10, "pm25_max_iter": 1000,
            "quantile_max_iter": 1000, "ablation_max_iter": 600},
    "smoke": {"n_boot": 20, "n_search": 2, "pm25_max_iter": 30,
              "quantile_max_iter": 30, "ablation_max_iter": 30},
}


def profile_name() -> str:
    name = os.environ.get(PROFILE_ENV, "standard").strip().lower() or "standard"
    if name not in PROFILES:
        raise ValueError(f"{PROFILE_ENV}={name!r} is not one of {sorted(PROFILES)}")
    return name


def get_profile() -> dict:
    name = profile_name()
    return {"name": name, **PROFILES[name]}


def is_standard() -> bool:
    return profile_name() == "standard"


def out_dir(base: Path) -> Path:
    """``base`` for the standard profile, ``base/<profile>`` otherwise (never clobbers accepted results)."""
    name = profile_name()
    return Path(base) if name == "standard" else Path(base) / name


def search_configs(n_search: int, seed: int = 42) -> list[dict]:
    """The default config followed by ``n_search`` distinct random configs (deterministic)."""
    rng = np.random.default_rng(seed)
    configs = [dict(DEFAULT_CONFIG)]
    seen = {tuple(sorted(DEFAULT_CONFIG.items()))}
    attempts = 0
    while len(configs) < n_search + 1 and attempts < 1000:
        attempts += 1
        cfg = {k: v[int(rng.integers(len(v)))] for k, v in SEARCH_SPACE.items()}
        key = tuple(sorted(cfg.items()))
        if key not in seen:
            seen.add(key)
            configs.append(cfg)
    return configs
