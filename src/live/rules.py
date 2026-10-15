"""Rule-based forecasts that need no fitted model.

``window_update_estimate`` is the 1h AQI forecast the live service publishes ("rule-based (24h-window update)").
The live AQI is a trailing 24h mean of an hourly AQI ``H``, so

    AQI(t+h) = AQI(t) + sum_{k=1..h} (H(t+k) - H(t+k-24)) / 24

and every ``H(t+k-24)`` leaving the window is known at ``t``. The rule keeps the known hours that stay in the target's
window, assumes the ``h`` entering hours equal the current hourly value ``H(t)``, and recomputes the mean with the same
minimum-valid-hours rule as ``compute_aqi``. Nothing is fitted. On the 2025-11..12 test window it scores +0.553 against
plain persistence at 1h and no better than persistence at 6h (docs/TIER_3/LIVE_CONSISTENT_RETRAIN.md, ADR 0006).
"""

from __future__ import annotations

import pandas as pd

from src.features.compute_cpcb_aqi import MIN_VALID_HOURS, ROLLING_WINDOW_HOURS

AQI_1H_VERSION = "aqi-1h-window-update-v1"
AQI_1H_NAME = "Rule-based (24h-window update) 1h AQI"


def window_update_estimate(hourly: pd.Series, horizon: int) -> pd.Series:
    """Window-update persistence for ``AQI(t+horizon)`` at every ``t`` of one station's gap-free hourly series.

    Known part: the ``24 - horizon`` newest hours that stay in the target's window; the other ``horizon`` hours are
    filled with the current hourly value. NaN when the current hour is missing or fewer than ``MIN_VALID_HOURS`` valid.
    """
    keep = ROLLING_WINDOW_HOURS - horizon
    if keep > 0:
        known_sum = hourly.rolling(keep, min_periods=1).sum().fillna(0.0)
        known_n = hourly.rolling(keep, min_periods=1).count()
    else:
        known_sum, known_n = pd.Series(0.0, index=hourly.index), pd.Series(0.0, index=hourly.index)
    total = known_sum + horizon * hourly
    count = known_n + horizon
    return (total / count).where(hourly.notna() & (count >= MIN_VALID_HOURS))
