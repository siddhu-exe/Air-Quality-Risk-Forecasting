"""Cell-level QC shared by the backfill and the live ingest."""

import numpy as np
import pandas as pd
import pytest

from src.live.qc import ImplausibleBatch, apply_qc, check_batch


def _frame(**cols):
    return pd.DataFrame(cols)


def test_sentinel_nullifies_the_cell_not_the_row():
    clean, flags = apply_qc(_frame(pm25=[50.0, -9999.0, 70.0], no2=[10.0, 20.0, 30.0]))
    assert len(clean) == 3 and np.isnan(clean.pm25.iloc[1])
    assert clean.no2.tolist() == [10.0, 20.0, 30.0]  # other cells of the same row survive
    assert flags[1] == {"pm25": "sentinel"} and flags[0] == {} and flags[2] == {}


def test_negative_pollutant_and_humidity_out_of_range_are_bounds_violations():
    clean, flags = apply_qc(_frame(pm25=[-3.0, 5.0], humidity=[101.0, 50.0]))
    assert np.isnan(clean.pm25.iloc[0]) and np.isnan(clean.humidity.iloc[0])
    assert flags[0] == {"pm25": "bounds", "humidity": "bounds"}


def test_a_1000x_scale_error_is_flagged_implausible():
    clean, flags = apply_qc(_frame(nox=[150.0, 150000.0]))
    assert clean.nox.iloc[0] == 150.0 and np.isnan(clean.nox.iloc[1]) and flags[1] == {"nox": "implausible"}


def test_real_extremes_from_the_training_csvs_pass():
    clean, flags = apply_qc(
        _frame(pm25=[998.0], pm10=[1000.0], nox=[499.0], co=[9.76], o3=[932.0], temperature=[49.8], wind_speed=[36.6])
    )
    assert flags == [{}] and clean.notna().all().all()


def test_input_frame_is_not_modified():
    frame = _frame(pm25=[-9999.0])
    apply_qc(frame)
    assert frame.pm25.iloc[0] == -9999.0


def test_batch_with_many_implausible_values_raises_a_unit_change_warning():
    frame = _frame(nox=[100000.0] * 30 + [200.0] * 10)
    clean, flags = apply_qc(frame)
    with pytest.raises(ImplausibleBatch, match="unit or scale change"):
        check_batch(clean, flags)


def test_isolated_glitches_do_not_raise():
    values = [100.0] * 95 + [90000.0] * 5
    clean, flags = apply_qc(_frame(pm25=values))
    check_batch(clean, flags)  # 5% implausible: a sensor glitch, not a unit change
