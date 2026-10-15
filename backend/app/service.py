"""Builds the API responses from repository rows. No framework and no database in here, so every rule is unit-tested.

Rules (ADR 0006): a station/product either has a forecast from the latest forecast run or is ``unavailable`` with the
reason the job recorded; PM2.5 24h is ``withheld``; AQI 1h is a rule, AQI 24h is experimental and always carries plain
persistence. Persistence and window-update references are the values frozen on the forecast row, never re-derived.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from backend.app import cpcb, models
from backend.app.repository import Repository
from backend.app.settings import Settings

REPORTS_DIR = Path(__file__).resolve().parents[2] / "reports"
HISTORY_HOURS = 72
FORECAST_LOOKBACK_HOURS = 12  # newest forecast considered; older means the job has stopped
NO_FORECAST_REASON = "no forecast was issued for this product in the latest run"


class NotFound(LookupError):
    pass


@dataclass(frozen=True)
class Product:
    key: str
    target: str
    hours: int
    label: str
    kind: str
    experimental: bool = False

    @property
    def horizon(self) -> str:
        return f"{self.hours}h"


PRODUCTS = [
    Product("aqi_1h", "aqi", 1, "Rule-based (24h-window update)", "rule"),
    Product("aqi_6h", "aqi", 6, "Model", "model"),
    Product("aqi_24h", "aqi", 24, "Experimental: about as accurate as assuming no change", "model", experimental=True),
    Product("pm25_1h", "pm25", 1, "Model", "model"),
    Product("pm25_6h", "pm25", 6, "Model", "model"),
]
PM25_24H = Product("pm25_24h", "pm25", 24, "Not published", "model")
PRODUCT_BY_KEY = {p.key: p for p in [*PRODUCTS, PM25_24H]}


def _num(value: object) -> float | None:
    return None if value is None else float(value)


class Service:
    def __init__(
        self,
        repo: Repository,
        settings: Settings,
        clock: Callable[[], datetime],
        reports_dir: Path = REPORTS_DIR,
    ) -> None:
        self.repo, self.settings, self.clock, self.reports_dir = repo, settings, clock, reports_dir

    # ------------------------------------------------------------------ shared
    def _age_hours(self, ts: datetime, now: datetime) -> float:
        """A reading labelled T covers [T, T+1h), so its age is measured to T + 1 h."""
        return (now - (ts + timedelta(hours=1))).total_seconds() / 3600

    def _meta(self, now: datetime) -> dict:
        newest = self.repo.newest_reading()
        stale = newest is None or self._age_hours(newest, now) > self.settings.stale_after_hours
        return {"data_as_of": newest, "generated_at": now, "stale": stale}

    def _stations(self) -> dict[int, dict]:
        return {s["station_id"]: s for s in self.repo.stations()}

    def _forecast_context(self, now: datetime) -> dict:
        rows = self.repo.latest_forecasts(now - timedelta(hours=FORECAST_LOOKBACK_HOURS))
        current = max((r["issue_time"] for r in rows), default=None)
        run = self.repo.latest_run() or {}
        details = run.get("details") or {}
        return {
            "rows": {(r["station_id"], f"{r['target']}_{r['horizon']}h"): r for r in rows},
            "issue": current,
            "details": details if isinstance(details, dict) else {},
            "job_stale": current is None or (now - current) > timedelta(hours=self.settings.stale_after_hours + 1),
        }

    def _forecast(self, product: Product, station: dict, ctx: dict) -> models.Forecast:
        base = {
            "product": product.key,
            "target": product.target,
            "horizon": product.horizon,
            "label": product.label,
            "kind": product.kind,
            "experimental": product.experimental,
        }
        if product is PM25_24H:
            return models.Forecast(
                **base, status="withheld", reason="No 24h PM2.5 forecast is published: it does not beat persistence."
            )
        row = ctx["rows"].get((station["station_id"], product.key))
        if ctx["job_stale"]:
            when = (
                "no forecast has been issued yet"
                if ctx["issue"] is None
                else f"newest forecast issued {ctx['issue']:%Y-%m-%d %H:%M}"
            )
            return models.Forecast(
                **base, status="unavailable", reason=f"the forecast job has not run recently ({when})"
            )
        if row is None or row["issue_time"] != ctx["issue"]:
            return models.Forecast(**base, status="unavailable", reason=self._reason(product, station, ctx["details"]))
        value = float(row["y_hat"])
        return models.Forecast(
            **base,
            status="ok",
            issued_at=row["issue_time"],
            valid_at=row["target_time"],
            value=value,
            category=cpcb.category(value) if product.target == "aqi" else None,
            persistence=_num(row["y_persistence"]),
            window_update=_num(row["y_window_update"]) if product.target == "aqi" else None,
            model_version=row["model_version"],
        )

    @staticmethod
    def _reason(product: Product, station: dict, details: dict) -> str:
        name = station["station_name"]
        dropped = details.get("skipped_products") or {}
        skipped = details.get("skipped") or {}
        notes = (details.get("notes") or {}).get(name) or {}
        return (
            dropped.get(f"{name}/{product.key}")
            or skipped.get(name)
            or notes.get(f"{product.key}_skipped")
            or NO_FORECAST_REASON
        )

    def _current(self, station_id: int, latest: dict[int, dict], now: datetime) -> models.Current | None:
        row = latest.get(station_id)
        if row is None:
            return None
        value = float(row["aqi"])
        return models.Current(
            value=value,
            category=cpcb.category(value),
            at=row["ts"],
            stale=self._age_hours(row["ts"], now) > self.settings.stale_after_hours,
        )

    @staticmethod
    def _base(station: dict) -> dict:
        return {
            "id": str(station["station_id"]),
            "name": station["station_name"],
            "lat": _num(station["latitude"]),
            "lon": _num(station["longitude"]),
            "coords_approximate": bool(station["coords_approximate"]),
        }

    # ------------------------------------------------------------------ endpoints
    def health(self) -> models.Health:
        now = self.clock()
        try:
            reachable = self.repo.ping()
        except Exception:  # noqa: BLE001 - any database failure means degraded, never an error page
            reachable = False
        meta = self._meta(now) if reachable else {"data_as_of": None, "generated_at": now, "stale": True}
        jobs = self._jobs() if reachable else []
        newest_forecast = self.repo.newest_forecast() if reachable else None
        return models.Health(
            **meta,
            status="ok" if reachable and not meta["stale"] else "degraded",
            newest_reading_at=meta["data_as_of"],
            newest_forecast_at=newest_forecast,
            jobs=jobs,
        )

    def _jobs(self) -> list[models.Job]:
        return [models.Job(job=j["job"], status=j["status"], last_run_at=j["last_run_at"]) for j in self.repo.jobs()]

    def overview(self) -> models.Overview:
        now = self.clock()
        stations, latest, ctx = self._stations(), self.repo.latest_aqi(), self._forecast_context(now)
        items, fresh = [], []
        for sid, station in stations.items():
            current = self._current(sid, latest, now)
            if current is not None and not current.stale:
                fresh.append(current.value)
            items.append(
                models.OverviewStation(
                    **self._base(station),
                    now=current,
                    forecasts=[self._forecast(p, station, ctx) for p in PRODUCTS],
                )
            )
        mean = sum(fresh) / len(fresh) if fresh else None
        forecast_stations = sum(any(f.status == "ok" for f in s.forecasts) for s in items)
        return models.Overview(
            **self._meta(now),
            issued_at=ctx["issue"],
            network=models.Network(
                stations_with_data=len(fresh),
                stations_total=len(stations),
                mean_aqi_now=mean,
                category_now=None if mean is None else cpcb.category(mean),
                stations_forecast=forecast_stations,
            ),
            stations=items,
        )

    def stations(self) -> models.Stations:
        now = self.clock()
        stations, latest, readings, pm25 = (
            self._stations(),
            self.repo.latest_aqi(),
            self.repo.latest_readings(),
            self.repo.latest_pm25(),
        )
        out = []
        for sid, station in stations.items():
            current = self._current(sid, latest, now)
            seen = readings.get(sid)
            out.append(
                models.StationSummary(
                    **self._base(station),
                    aqi_now=None if current is None else current.value,
                    category_now=None if current is None else current.category,
                    pm25_now=_num(pm25[sid]["pm25"]) if sid in pm25 else None,
                    last_reading_at=None if seen is None else seen["ts"],
                    stale=current is None or current.stale,
                )
            )
        return models.Stations(**self._meta(now), stations=out)

    def station_forecast(self, station_id: str, target: str) -> models.StationForecast:
        if target not in ("aqi", "pm25"):
            raise ValueError("target must be 'aqi' or 'pm25'")
        now = self.clock()
        stations = self._stations()
        try:
            sid = int(station_id)
        except ValueError as exc:
            raise NotFound(station_id) from exc
        if sid not in stations:
            raise NotFound(station_id)
        station, ctx = stations[sid], self._forecast_context(now)
        products = [p for p in PRODUCTS if p.target == target] + ([PM25_24H] if target == "pm25" else [])
        history = self.repo.history(sid, target, now - timedelta(hours=HISTORY_HOURS))
        reading = self.repo.latest_readings().get(sid) or {}
        pollutants = [
            models.Pollutant(key=k, concentration=float(reading[k]), unit=cpcb.UNITS[k])
            for k in cpcb.POLLUTANT_KEYS
            if reading.get(k) is not None
        ]
        weather = models.Weather(
            temperature_c=_num(reading.get("temperature")),
            wind_ms=_num(reading.get("wind_speed")),
            humidity_pct=_num(reading.get("humidity")),
            solar_wm2=_num(reading.get("solar_radiation")),
        )
        has_weather = any(v is not None for v in weather.model_dump().values())
        return models.StationForecast(
            **self._meta(now),
            station=models.StationInfo(id=str(sid), name=station["station_name"]),
            target=target,
            history=[models.SeriesPoint(t=t, value=v) for t, v in history],
            forecasts=[self._forecast(p, station, ctx) for p in products],
            pollutants=pollutants,
            weather=weather if has_weather else None,
        )

    def grap(self) -> models.GrapAlerts:
        now = self.clock()
        stations, latest, ctx = self._stations(), self.repo.latest_aqi(), self._forecast_context(now)
        rows, now_values = [], []
        for sid, station in stations.items():
            current = self._current(sid, latest, now)
            value = None if current is None or current.stale else current.value
            if value is not None:
                now_values.append(value)
            six = self._forecast(PRODUCT_BY_KEY["aqi_6h"], station, ctx)
            day = self._forecast(PRODUCT_BY_KEY["aqi_24h"], station, ctx)
            rows.append(
                models.GrapStation(
                    station_id=str(sid),
                    name=station["station_name"],
                    now=value,
                    stage_now=None if value is None else cpcb.grap_stage(value),
                    forecast_6h=six.value,
                    stage_6h=None if six.value is None else cpcb.grap_stage(six.value),
                    forecast_24h=day.value,
                    persistence=day.persistence,
                )
            )
        mean = sum(now_values) / len(now_values) if now_values else None
        return models.GrapAlerts(
            **self._meta(now),
            disclaimer="Indicative only, not an official advisory. Stages follow the CAQM GRAP bands (to be re-verified before launch); the 24h forecast is experimental.",
            network_mean_aqi_now=mean,
            stage_indicated_now=None if mean is None else cpcb.grap_stage(mean),
            stages=[
                models.GrapStageInfo(
                    stage=stage,
                    label=label,
                    min=low,
                    max=high,
                    now_count=sum(r.stage_now == stage for r in rows),
                    forecast_6h_count=sum(r.stage_6h == stage for r in rows),
                )
                for stage, label, low, high in cpcb.GRAP_STAGES
            ],
            stations=rows,
        )

    def model_health(self) -> models.ModelHealth:
        now = self.clock()
        stations = self._stations()
        by_key: dict[tuple[str, int], list[dict]] = {}
        for row in self.repo.skill(now - timedelta(days=30)):
            by_key.setdefault((row["target"], int(row["horizon"])), []).append(row)
        skill = []
        for p in PRODUCTS:
            series = by_key.get((p.target, p.hours), [])
            vs_p = [_num(r["skill_mae"]) for r in series]
            vs_w = [_num(r["skill_vs_window_update"]) for r in series]
            skill.append(
                models.SkillSeries(
                    product=p.key,
                    label=p.label,
                    horizon=p.horizon,
                    target=p.target,
                    window_end=[str(r["window_end"]) for r in series],
                    skill_vs_persistence=vs_p,
                    skill_vs_window_update=vs_w if p.target == "aqi" else [None] * len(series),
                    current_vs_persistence=vs_p[-1] if vs_p else None,
                    current_vs_window_update=vs_w[-1] if vs_w and p.target == "aqi" else None,
                    n=int(series[-1]["n"]) if series else None,
                )
            )
        slots = [(now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=h)) for h in range(24, 0, -1)]
        present = self.repo.hourly_presence(slots[0])
        readings = self.repo.latest_readings()
        freshness = []
        for sid, station in stations.items():
            seen = readings.get(sid)
            age = None if seen is None else self._age_hours(seen["ts"], now)
            freshness.append(
                models.Freshness(
                    station_id=str(sid),
                    name=station["station_name"],
                    last_reading_at=None if seen is None else seen["ts"],
                    hourly=[slot in present.get(sid, set()) for slot in slots],
                    note=None
                    if age is not None and age <= self.settings.stale_after_hours
                    else ("no readings yet" if age is None else f"no reading for {age:.0f} h"),
                )
            )
        possible = 24 * len(stations)
        issued = self.repo.forecast_station_hours(now - timedelta(hours=24))
        return models.ModelHealth(
            **self._meta(now),
            skill=skill,
            forecast_coverage=min(1.0, issued / possible) if possible else None,
            freshness=freshness,
            jobs=self._jobs(),
            models=[
                models.RegisteredModel(
                    version=m["model_version"],
                    name=m["model_name"],
                    target=m["target"],
                    horizon=f"{int(m['horizon'])}h",
                    sha256=m["sha256"],
                )
                for m in self.repo.registry()
            ],
        )

    # ------------------------------------------------------------------ static evidence
    def backtest(self) -> models.Backtest:
        evidence = self._evidence()
        return models.Backtest(
            note="Skill = 1 - MAE_model / MAE_reference with 95% day-block bootstrap intervals, from the files in reports/. "
            "The test window is Nov-Dec 2025 (scored once); the replay re-forecasts Sep-Oct 2026 from stored readings.",
            evidence=evidence,
        )

    def _read(self, relative: str) -> list[dict]:
        path = self.reports_dir / relative
        if not path.exists():
            return []
        with path.open(newline="") as handle:
            return list(csv.DictReader(handle))

    def _evidence(self) -> list[models.Evidence]:
        def f(row: dict, key: str) -> float | None:
            value = row.get(key)
            return None if value in (None, "", "nan", "NaN") else float(value)

        out: list[models.Evidence] = []
        window_test = "test 2025-11-01..2025-12-31"
        for row in self._read("modeling/live_retrain/window_update_baseline.csv"):
            if row["split"] != "test":
                continue
            key = f"aqi_{row['horizon']}"
            product = PRODUCT_BY_KEY.get(key)
            if product is None:
                continue
            if key == "aqi_1h":  # the published 1h product is the rule itself
                skill, lo, hi = (
                    f(row, "wu_vs_persistence"),
                    f(row, "wu_vs_persistence_lo"),
                    f(row, "wu_vs_persistence_hi"),
                )
                vs = (None, None, None)
            else:
                skill, lo, hi = (
                    f(row, "model_vs_persistence"),
                    f(row, "model_vs_persistence_lo"),
                    f(row, "model_vs_persistence_hi"),
                )
                vs = (
                    (
                        f(row, "model_vs_window_update"),
                        f(row, "model_vs_window_update_lo"),
                        f(row, "model_vs_window_update_hi"),
                    )
                    if key == "aqi_6h"
                    else (None, None, None)  # a flat-hour assumption over 24 h is not a fair comparator
                )
            out.append(self._evidence_row(product, window_test, int(row["n"]), (skill, lo, hi), vs))
        for row in self._read("modeling/live_pm25/pm25_forecast_metrics.csv"):
            product = PRODUCT_BY_KEY.get(f"pm25_{row['horizon']}")
            if row["split"] == "test" and product is not None and product is not PM25_24H:
                out.append(
                    self._evidence_row(
                        product,
                        window_test,
                        int(row["n"]),
                        (f(row, "skill_mae"), f(row, "skill_mae_ci_lo"), f(row, "skill_mae_ci_hi")),
                        (None, None, None),
                    )
                )
        for row in self._read("live/replay_2026-09-01_2026-10-07.csv"):
            product = PRODUCT_BY_KEY.get(f"{row['target']}_{row['horizon']}h")
            if product is None:
                continue
            vs = (
                f(row, "skill_vs_window_update"),
                f(row, "skill_vs_window_update_lo"),
                f(row, "skill_vs_window_update_hi"),
            )
            out.append(
                self._evidence_row(
                    product,
                    "replay 2026-09-01..2026-10-07",
                    int(row["scored"]),
                    (
                        f(row, "skill_vs_persistence"),
                        f(row, "skill_vs_persistence_lo"),
                        f(row, "skill_vs_persistence_hi"),
                    ),
                    vs if product.target == "aqi" and product.key != "aqi_1h" else (None, None, None),
                )
            )
        return out

    @staticmethod
    def _evidence_row(product: Product, window: str, n: int, p: tuple, w: tuple) -> models.Evidence:
        return models.Evidence(
            product=product.key,
            label=product.label,
            window=window,
            n=n,
            skill_vs_persistence=p[0],
            skill_vs_persistence_lo=p[1],
            skill_vs_persistence_hi=p[2],
            skill_vs_window_update=w[0],
            skill_vs_window_update_lo=w[1],
            skill_vs_window_update_hi=w[2],
        )
