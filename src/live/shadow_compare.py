"""WAQI (shadow) against OpenAQ on overlapping hours, per pollutant, at hour offsets -1, 0 and +1.

WAQI's hour convention is not known, so the comparison is made at three offsets: the offset with the smallest error says which
OpenAQ hour a WAQI feed time corresponds to. Pure functions here; the hourly shadow job logs the last day's result and
``python -m src.live.shadow_compare --days 7`` prints the evidence for the fallback decision.

The fallback GATE (ADR 0009) is ``gate()``: one pass/fail summary for "may WAQI be a fallback live source for PM2.5/PM10?",
run weekly by ``waqi-gate.yml`` (``--gate --issue``). Its rules, all fixed here and not tuned on the data that judges them:
  * PM2.5 and PM10 only; the gases are never used. ITO is excluded entirely: WAQI has no ITO monitor, only one 1.9 km away.
  * The overlap is split in time at its median. The hour offset (-1/0/+1) is picked per pollutant on the FIRST half and the
    gate is scored on the SECOND half at that offset.
  * Pollutant passes when the overlap spans >= 7 days, >= 5 stations pass individually, and the stations that pass, pooled,
    have >= 150 paired hours on the second half with corr >= 0.9, |bias| < 10% of the OpenAQ mean and MAE < 20% of the mean.
    (A failing station is out of the forecast anyway, so it does not count against the pool; it is still reported.)
  * The same metrics are applied per station (>= 24 paired hours on the second half). A station that fails either pollutant
    gets no WAQI-based forecast, even when the network gate passes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from src.features.compute_cpcb_aqi import STATION_IDS
from src.live.sources.waqi import POLLUTANTS

LAGS = (-1, 0, 1)
MIN_PAIRS = 12  # fewer overlapping hours than this is not summarised

# ---- the fallback gate (ADR 0009)
GATE_POLLUTANTS = ("pm25", "pm10")
EXCLUDED_STATIONS = ("ITO",)  # WAQI has no ITO monitor; the nearest is a different one 1.9 km away
MIN_OVERLAP_DAYS = 7
MIN_PAIRS_POLLUTANT = 150  # paired hours on the scoring half, pooled over the eligible stations
MIN_STATIONS = 5  # stations that must pass individually for the network to pass
MIN_PAIRS_STATION = 24  # paired hours on the scoring half for a station to be judged at all
MIN_CORR = 0.9
MAX_ABS_BIAS_SHARE = 0.10
MAX_MAE_SHARE = 0.20
LAG_PREFERENCE = (0, -1, 1)  # a tie goes to the offset with no shift


def pair_frame(shadow: pd.DataFrame, primary: pd.DataFrame, lag: int) -> pd.DataFrame:
    """Shadow row at hour S joined with the primary row of the same station at S + lag (columns ``*_s`` / ``*_p``)."""
    shifted = primary.assign(ts=primary["ts"] - pd.Timedelta(hours=lag))  # primary hour S+lag -> key S
    return shadow.merge(shifted, on=["station_id", "ts"], suffixes=("_s", "_p"))


def compare(shadow: pd.DataFrame, primary: pd.DataFrame, lags: tuple[int, ...] = LAGS) -> pd.DataFrame:
    """Per (pollutant, lag): pairs, bias (shadow - primary), MAE, MAE as a share of the primary mean, correlation.

    Both frames have ``station_id``, ``ts`` (hour label) and the pollutant columns. A shadow row at hour S is paired with the
    primary row at S + lag hours of the same station."""
    rows = []
    for lag in lags:
        merged = pair_frame(shadow, primary, lag)
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


# --------------------------------------------------------------------------- the fallback gate
@dataclass
class PairStats:
    pairs: int
    bias: float
    mae: float
    bias_share: float  # bias / OpenAQ mean
    mae_share: float  # MAE / OpenAQ mean
    corr: float

    def passes(self, min_pairs: int) -> bool:
        return bool(
            self.pairs >= min_pairs
            and self.corr >= MIN_CORR
            and abs(self.bias_share) < MAX_ABS_BIAS_SHARE
            and self.mae_share < MAX_MAE_SHARE
        )


@dataclass
class PollutantGate:
    pollutant: str
    lag_hours: int | None = None  # chosen on the first half of the overlap
    lag_first_half_mae_share: dict = field(default_factory=dict)
    pooled_all: PairStats | None = None  # second half, chosen lag, every eligible station (information only)
    pooled: PairStats | None = None  # the same, over the stations that pass individually (this is what is judged)
    stations: dict = field(default_factory=dict)  # station name -> PairStats (second half)
    stations_passing: list = field(default_factory=list)
    passed: bool = False
    reasons: list = field(default_factory=list)


@dataclass
class GateReport:
    passed: bool
    summary: str
    overlap_days: float
    overlap_first: str | None
    overlap_last: str | None
    split_at: str | None
    pollutants: dict = field(default_factory=dict)
    stations_usable: list = field(default_factory=list)  # pass BOTH pollutants; empty unless the network gate passes
    excluded: list = field(default_factory=lambda: list(EXCLUDED_STATIONS))
    reasons: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=str)


def _stats(shadow_values: np.ndarray, primary_values: np.ndarray) -> PairStats:
    s, p = np.asarray(shadow_values, float), np.asarray(primary_values, float)
    mean_p = float(p.mean()) if len(p) else float("nan")
    ok = mean_p > 0
    return PairStats(
        pairs=int(len(p)),
        bias=float((s - p).mean()) if len(p) else float("nan"),
        mae=float(np.abs(s - p).mean()) if len(p) else float("nan"),
        bias_share=float((s - p).mean() / mean_p) if ok else float("nan"),
        mae_share=float(np.abs(s - p).mean() / mean_p) if ok else float("nan"),
        corr=float(np.corrcoef(s, p)[0, 1]) if len(p) > 2 and s.std() > 0 and p.std() > 0 else float("nan"),
    )


def _pairs(merged: pd.DataFrame, pollutant: str) -> pd.DataFrame:
    return merged[["station_id", "ts", f"{pollutant}_s", f"{pollutant}_p"]].dropna()


def gate(shadow: pd.DataFrame, primary: pd.DataFrame) -> GateReport:
    """May WAQI be a fallback live source for PM2.5/PM10? One pass/fail with the evidence behind it (see module docstring)."""
    names = {v: k for k, v in STATION_IDS.items()}
    eligible = {i: n for i, n in names.items() if n not in EXCLUDED_STATIONS}
    shadow = shadow[shadow["station_id"].isin(eligible)]
    primary = primary[primary["station_id"].isin(eligible)]

    by_lag = {lag: pair_frame(shadow, primary, lag) for lag in LAGS}
    # overlap hours, keyed by the SHADOW hour so the split does not depend on the offset being tested
    hours = sorted(
        {ts for merged in by_lag.values() for pollutant in GATE_POLLUTANTS for ts in _pairs(merged, pollutant)["ts"]}
    )
    report = GateReport(False, "", 0.0, None, None, None)
    if not hours:
        report.reasons.append("no overlapping hours between the WAQI shadow rows and OpenAQ")
        report.summary = f"FAIL: {report.reasons[0]}"
        return report
    first, last = hours[0], hours[-1]
    split = hours[len(hours) // 2]
    report.overlap_first, report.overlap_last, report.split_at = str(first), str(last), str(split)
    report.overlap_days = round((last - first).total_seconds() / 86400 + 1 / 24, 2)
    if report.overlap_days < MIN_OVERLAP_DAYS:
        report.reasons.append(f"overlap is {report.overlap_days:.1f} days, need {MIN_OVERLAP_DAYS}")

    for pollutant in GATE_POLLUTANTS:
        result = PollutantGate(pollutant)
        # 1) the offset, chosen once, on the first half only
        for lag in LAG_PREFERENCE:
            half = _pairs(by_lag[lag], pollutant)
            half = half[half["ts"] < split]
            if len(half) >= MIN_PAIRS:
                st = _stats(half[f"{pollutant}_s"], half[f"{pollutant}_p"])
                result.lag_first_half_mae_share[str(lag)] = round(st.mae_share, 4)
        if not result.lag_first_half_mae_share:
            result.reasons.append("too few paired hours on the first half to choose the offset")
            report.pollutants[pollutant] = result
            continue
        result.lag_hours = int(
            min(
                result.lag_first_half_mae_share,
                key=lambda k: (result.lag_first_half_mae_share[k], LAG_PREFERENCE.index(int(k))),
            )
        )
        # 2) the judgement, on the second half, at that offset
        second = _pairs(by_lag[result.lag_hours], pollutant)
        second = second[second["ts"] >= split]
        result.pooled_all = _stats(second[f"{pollutant}_s"], second[f"{pollutant}_p"])
        for station_id, group in second.groupby("station_id"):
            name = eligible[int(station_id)]
            result.stations[name] = _stats(group[f"{pollutant}_s"], group[f"{pollutant}_p"])
        result.stations_passing = sorted(n for n, st in result.stations.items() if st.passes(MIN_PAIRS_STATION))
        passing = second[second["station_id"].map(eligible).isin(result.stations_passing)]
        result.pooled = _stats(passing[f"{pollutant}_s"], passing[f"{pollutant}_p"])
        if not result.pooled.passes(MIN_PAIRS_POLLUTANT):
            result.reasons.append(
                f"pooled over passing stations: {result.pooled.pairs} pairs (need {MIN_PAIRS_POLLUTANT}), corr {result.pooled.corr:.2f} "
                f"(need {MIN_CORR}), bias {result.pooled.bias_share:+.1%} (|.| < {MAX_ABS_BIAS_SHARE:.0%}), "
                f"MAE {result.pooled.mae_share:.1%} (< {MAX_MAE_SHARE:.0%})"
            )
        if len(result.stations_passing) < MIN_STATIONS:
            result.reasons.append(f"{len(result.stations_passing)} stations pass, need {MIN_STATIONS}")
        result.passed = not result.reasons
        report.pollutants[pollutant] = result

    failing = [p for p in GATE_POLLUTANTS if not report.pollutants[p].passed]
    for pollutant in failing:
        report.reasons += [f"{pollutant}: {r}" for r in report.pollutants[pollutant].reasons]
    report.passed = not report.reasons
    if report.passed:
        report.stations_usable = sorted(
            set.intersection(*(set(report.pollutants[p].stations_passing) for p in GATE_POLLUTANTS))
        )
    report.summary = (
        f"PASS: PM2.5/PM10 may be a fallback at {len(report.stations_usable)} stations ({', '.join(report.stations_usable)})"
        if report.passed
        else f"FAIL: {report.reasons[0]}" + (f" (+{len(report.reasons) - 1} more)" if len(report.reasons) > 1 else "")
    )
    return report


def render_markdown(report: GateReport) -> str:
    lines = [
        f"## WAQI fallback gate: {report.summary}",
        "",
        f"Overlap {report.overlap_first or '-'} .. {report.overlap_last or '-'} ({report.overlap_days:.1f} days); offset chosen on hours "
        f"before {report.split_at or '-'}, scored on the rest. Excluded: {', '.join(report.excluded)}. Rules: ADR 0009.",
        "",
    ]
    for pollutant, res in report.pollutants.items():
        lines.append(f"### {pollutant}: {'pass' if res.passed else 'fail'} (offset {res.lag_hours})")
        if res.pooled is not None:
            lines += [
                "",
                "| Scope | Pairs | Corr | Bias % of mean | MAE % of mean | Pass |",
                "| :--- | ---: | ---: | ---: | ---: | :---: |",
                f"| passing stations pooled | {res.pooled.pairs} | {res.pooled.corr:.3f} | {res.pooled.bias_share:+.1%} | {res.pooled.mae_share:.1%} | "
                f"{'yes' if res.pooled.passes(MIN_PAIRS_POLLUTANT) else 'no'} |",
                f"| all eligible pooled (info) | {res.pooled_all.pairs} | {res.pooled_all.corr:.3f} | {res.pooled_all.bias_share:+.1%} | "
                f"{res.pooled_all.mae_share:.1%} | - |",
            ]
            lines += [
                f"| {name} | {st.pairs} | {st.corr:.3f} | {st.bias_share:+.1%} | {st.mae_share:.1%} | "
                f"{'yes' if name in res.stations_passing else 'no'} |"
                for name, st in sorted(res.stations.items())
            ]
        for reason in res.reasons:
            lines.append(f"- {reason}")
        lines.append("")
    if report.reasons and not report.pollutants:
        lines += [f"- {r}" for r in report.reasons]
    elif report.overlap_days < MIN_OVERLAP_DAYS and report.pollutants:
        lines.append(f"- overlap is {report.overlap_days:.1f} days, need {MIN_OVERLAP_DAYS}")
    lines.append(
        "Nothing changes until this passes and the PM-only audit has been reviewed; the site stays in stale mode meanwhile."
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    from src.live.waqi_shadow import ShadowStore

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, help="look-back window (default 7, or 60 with --gate)")
    parser.add_argument(
        "--gate", action="store_true", help="evaluate the fallback gate (PASS/FAIL) instead of the table"
    )
    parser.add_argument("--json", help="with --gate: also write the report as JSON to this path")
    parser.add_argument(
        "--issue", action="store_true", help="with --gate: post the result to a GitHub issue (GITHUB_TOKEN)"
    )
    args = parser.parse_args(argv)
    days = args.days or (60 if args.gate else 7)
    since = pd.Timestamp.now(tz="Asia/Kolkata") - pd.Timedelta(days=days)
    with ShadowStore("DATABASE_URL") as store:
        shadow, primary = store.shadow_since(since), store.primary_since(since - pd.Timedelta(hours=2))
    if args.gate:
        report = gate(shadow, primary)
        body = render_markdown(report)
        print(body)
        if args.json:
            with open(args.json, "w") as handle:
                handle.write(report.to_json())
        if args.issue:
            from src.live.score import Alert, open_or_refresh_issue

            outcome = open_or_refresh_issue(
                Alert("waqi-gate", "WAQI fallback gate, weekly result", body),
                os.environ["GITHUB_REPOSITORY"],
                os.environ["GITHUB_TOKEN"],
            )
            print(f"issue {outcome}")
        return 0  # FAIL is a result, not a broken job: the workflow stays green and the issue carries the verdict
    table = compare(shadow, primary)
    pd.set_option("display.width", 200)
    print(table.round(3).to_string(index=False) if len(table) else "no overlapping hours yet")
    print("\nbest offset per pollutant:")
    print(best_lag(table).round(3).to_string(index=False) if len(table) else "-")
    return 0


if __name__ == "__main__":
    sys.exit(main())
