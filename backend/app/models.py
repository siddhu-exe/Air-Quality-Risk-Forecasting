"""Response models of ``GET /api/v1/*`` (JSON keys are camelCase).

Every live response carries ``dataAsOf`` (newest reading behind it), ``generatedAt`` (server clock) and ``stale``
(newest reading older than the limit). A forecast is either ``ok`` with its values and its plain-persistence reference,
or ``unavailable`` with the reason, or ``withheld`` by policy; there is never a blank or substitute number.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Meta(Model):
    data_as_of: datetime | None
    generated_at: datetime
    stale: bool


Target = Literal["aqi", "pm25"]
Horizon = Literal["1h", "6h", "24h"]


class Forecast(Model):
    """One product (target x horizon) for one station."""

    product: str
    target: Target
    horizon: Horizon
    label: str
    kind: Literal["rule", "model"]
    experimental: bool
    status: Literal["ok", "unavailable", "withheld"]
    reason: str | None = None
    issued_at: datetime | None = None
    valid_at: datetime | None = None
    value: float | None = None
    category: str | None = None
    #: plain persistence (the current value copied forward), frozen when the forecast was issued
    persistence: float | None = None
    #: window-update persistence (AQI only), frozen at issue time
    window_update: float | None = None
    model_version: str | None = None


class Current(Model):
    value: float
    category: str | None
    at: datetime
    stale: bool


class StationBase(Model):
    id: str
    name: str
    lat: float | None
    lon: float | None
    coords_approximate: bool


class OverviewStation(StationBase):
    now: Current | None
    forecasts: list[Forecast]


class Network(Model):
    stations_with_data: int
    stations_total: int
    mean_aqi_now: float | None
    category_now: str | None
    stations_forecast: int  # stations with at least one forecast in the latest run


class Overview(Meta):
    issued_at: datetime | None
    network: Network
    stations: list[OverviewStation]


class StationSummary(StationBase):
    aqi_now: float | None
    category_now: str | None
    pm25_now: float | None
    last_reading_at: datetime | None
    stale: bool


class Stations(Meta):
    stations: list[StationSummary]


class SeriesPoint(Model):
    t: datetime
    value: float


class Pollutant(Model):
    key: str
    concentration: float
    unit: str


class Weather(Model):
    temperature_c: float | None
    wind_ms: float | None
    humidity_pct: float | None
    solar_wm2: float | None


class StationInfo(Model):
    id: str
    name: str


class StationForecast(Meta):
    station: StationInfo
    target: Target
    history: list[SeriesPoint]
    forecasts: list[Forecast]
    pollutants: list[Pollutant]
    weather: Weather | None


class GrapStageInfo(Model):
    stage: Literal["I", "II", "III", "IV"]
    label: str
    min: int
    max: int | None
    now_count: int
    forecast_6h_count: int


class GrapStation(Model):
    station_id: str
    name: str
    now: float | None
    stage_now: str | None
    forecast_6h: float | None
    stage_6h: str | None
    forecast_24h: float | None  # experimental; always shown with persistence
    persistence: float | None


class GrapAlerts(Meta):
    disclaimer: str
    network_mean_aqi_now: float | None
    stage_indicated_now: str | None
    stages: list[GrapStageInfo]
    stations: list[GrapStation]


class SkillSeries(Model):
    product: str
    label: str
    horizon: Horizon
    target: Target
    window_end: list[str]
    skill_vs_persistence: list[float | None]
    skill_vs_window_update: list[float | None]
    current_vs_persistence: float | None
    current_vs_window_update: float | None
    n: int | None


class Freshness(Model):
    station_id: str
    name: str
    last_reading_at: datetime | None
    hourly: list[bool]
    note: str | None


class Job(Model):
    job: str
    status: str
    last_run_at: datetime | None


class RegisteredModel(Model):
    version: str
    name: str
    target: Target
    horizon: Horizon
    sha256: str


class LagDay(Model):
    day: str
    median_hours: float
    max_hours: float
    runs: int


class SourceLag(Model):
    """How far behind the data source is: the age of each station's newest reading, as seen by every ingest run."""

    source: str | None
    newest_reading_at: datetime | None
    current_median_hours: float | None
    current_max_hours: float | None
    daily: list[LagDay]


class ModelHealth(Meta):
    skill: list[SkillSeries]
    source_lag: SourceLag
    forecast_coverage: float | None  # share of station-hours with at least one forecast in the last 24 issue hours
    freshness: list[Freshness]
    jobs: list[Job]
    models: list[RegisteredModel]


class Health(Meta):
    status: Literal["ok", "degraded"]
    newest_reading_at: datetime | None
    newest_forecast_at: datetime | None
    jobs: list[Job]


class Evidence(Model):
    product: str
    label: str
    window: str
    n: int | None
    skill_vs_persistence: float
    skill_vs_persistence_lo: float | None
    skill_vs_persistence_hi: float | None
    skill_vs_window_update: float | None
    skill_vs_window_update_lo: float | None
    skill_vs_window_update_hi: float | None


class Backtest(Model):
    note: str
    evidence: list[Evidence]
