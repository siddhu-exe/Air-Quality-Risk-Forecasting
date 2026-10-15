import pandas as pd

from src.live import parity_live


def test_summary_counts_rows_over_tolerance_and_ignores_withheld_values(tmp_path):
    t = pd.Timestamp("2025-11-01", tz="Asia/Kolkata")
    detail = pd.DataFrame(
        {
            "product": "aqi_6h",
            "reference": "retrain predictions (test)",
            "variant": "live path",
            "issue_time": [t, t, t],
            "abs_diff": [0.0, 2e-6, float("nan")],
        }
    )
    summary = parity_live.summarize(detail)
    assert summary.rows.iloc[0] == 3 and summary.compared.iloc[0] == 2 and summary.rows_over_tolerance.iloc[0] == 1
    parity_live.write_report(summary, tmp_path)
    assert "| aqi_6h |" in (tmp_path / "parity_live_report.md").read_text()
