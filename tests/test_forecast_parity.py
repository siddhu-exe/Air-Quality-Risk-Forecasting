"""Parity of the live forecast path with the stored backtest predictions (needs the git-ignored training files)."""

import pytest

from src.live import models as model_mod
from src.live import parity

pytestmark = pytest.mark.skipif(
    not parity.inputs_available(), reason="raw CSVs / features_extended.parquet are not in this checkout"
)


@pytest.fixture(scope="module")
def history():
    return parity.load_history()


def _compare(horizon, history, models, times=4):
    readings, aqi = history
    for label, path, column in parity.STORED[horizon]:
        yield label, parity.compare(horizon, label, path, column, readings, aqi, models, times, seed=3)


def test_24h_hybrid_reproduces_the_stored_predictions(history):
    models = model_mod.load(horizons=(24,))
    for label, detail in _compare(24, history, models):
        assert len(detail) > 10 and detail["abs_diff"].max() <= parity.TOLERANCE, label


@pytest.mark.parametrize("horizon", [1, 6])
def test_lightgbm_models_reproduce_the_stored_predictions_when_the_rolling_start_matches(history, horizon):
    pytest.importorskip("lightgbm")
    models = model_mod.load(horizons=(horizon,))
    readings, aqi = history
    label, path, column = parity.STORED[horizon][0]
    detail = parity.compare(
        horizon, label, path, column, readings, aqi, models, 4, seed=3, variant="rolling from training start"
    )
    assert len(detail) > 10 and detail["abs_diff"].max() <= parity.TOLERANCE
