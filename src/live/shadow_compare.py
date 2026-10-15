"""WAQI (shadow) against OpenAQ on overlapping hours, per pollutant, at hour offsets -1, 0 and +1.

WAQI's hour convention is not known, so the comparison is made at three offsets: the offset with the smallest error says which
OpenAQ hour a WAQI feed time corresponds to. Pure functions here; the hourly shadow job logs the last day's result and
``python -m src.live.shadow_compare --days 7`` prints the evidence for the fallback decision.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from src.live.sources.waqi import POLLUTANTS

LAGS = (-1, 0, 1)
MIN_PAIRS = 12  # fewer overlapping hours than this is not summarised


def compare(shadow: pd.DataFrame, primary: pd.DataFrame, lags: tuple[int, ...] = LAGS) -> pd.DataFrame:
    """Per (pollutant, lag): pairs, bias (shadow - primary), MAE, MAE as a share of the primary mean, correlation.

    Both frames have ``station_id``, ``ts`` (hour label) and the pollutant columns. A shadow row at hour S is paired with the
    primary row at S + lag hours of the same station."""
    rows = []
    for lag in lags:
        shifted = primary.assign(ts=primary["ts"] - pd.Timedelta(hours=lag))  # primary hour S+lag -> key S
        merged = shadow.merge(shifted, on=["station_id", "ts"], suffixes=("_s", "_p"))
        for pollutant in POLLUTANTS:
            pair = merged[[f"{pollutant}_s", f"{pollutant}_p"]].dropna()
            if len(pair) < MIN_PAIRS:
                continue
            s, p = pair.iloc[:, 0].to_numpy(float), pair.iloc[:, 1].to_numpy(float)
            mean_p = float(p.mean())
            rows.append(
                {
                    "pollutant": pollutant,
                    "lag_hours": lag,
                    "pairs": len(pair),
                    "bias": float((s - p).mean()),
                    "mae": float(np.abs(s - p).mean()),
                    "mae_share_of_mean": float(np.abs(s - p).mean() / mean_p) if mean_p > 0 else float("nan"),
                    "corr": float(np.corrcoef(s, p)[0, 1]) if s.std() > 0 and p.std() > 0 else float("nan"),
                }
            )
    return pd.DataFrame(rows, columns=["pollutant", "lag_hours", "pairs", "bias", "mae", "mae_share_of_mean", "corr"])


def best_lag(table: pd.DataFrame) -> pd.DataFrame:
    """The offset with the smallest relative error for each pollutant."""
    if table.empty:
        return table
    return table.loc[table.groupby("pollutant")["mae_share_of_mean"].idxmin()].reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    from src.live.waqi_shadow import ShadowStore

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args(argv)
    since = pd.Timestamp.now(tz="Asia/Kolkata") - pd.Timedelta(days=args.days)
    with ShadowStore("DATABASE_URL") as store:
        shadow, primary = store.shadow_since(since), store.primary_since(since - pd.Timedelta(hours=2))
    table = compare(shadow, primary)
    pd.set_option("display.width", 200)
    print(table.round(3).to_string(index=False) if len(table) else "no overlapping hours yet")
    print("\nbest offset per pollutant:")
    print(best_lag(table).round(3).to_string(index=False) if len(table) else "-")
    return 0


if __name__ == "__main__":
    sys.exit(main())
