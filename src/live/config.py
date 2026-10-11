"""Live pipeline settings: ``config/live.toml`` with environment-variable overrides.

Switching the live source is a config change, not a code change: edit ``source`` in the file, set the
``LIVE_SOURCE`` repository variable, or pick it when dispatching the ingest workflow.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "live.toml"
VALID_SOURCES = ("openaq", "data_gov_in")
VALID_WEATHER = ("open-meteo", "none")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class IngestConfig:
    source: str = "openaq"
    fallback: str = ""
    lookback_hours: int = 6
    stale_after_hours: float = 3.0
    weather_display: str = "open-meteo"   # ingest stores Open-Meteo values in empty weather cells (tagged), for the app to display
    weather_fill: str = "none"            # what the MODELS see: "none" = station/source cells only, filled cells are masked
    allow_unverified: bool = False

    def __post_init__(self):
        for name, value in (("source", self.source), ("fallback", self.fallback)):
            if value and value not in VALID_SOURCES:
                raise ConfigError(f"{name}={value!r}: must be one of {VALID_SOURCES}" + (" or empty" if name == "fallback" else ""))
        if not self.source:
            raise ConfigError("source must be set")
        if self.fallback == self.source:
            raise ConfigError("fallback must differ from source")
        for name, value in (("weather_display", self.weather_display), ("weather_fill", self.weather_fill)):
            if value not in VALID_WEATHER:
                raise ConfigError(f"{name}={value!r}: must be one of {VALID_WEATHER}")
        if not 1 <= self.lookback_hours <= 72:
            raise ConfigError("lookback_hours must be between 1 and 72")
        if self.stale_after_hours <= 0:
            raise ConfigError("stale_after_hours must be positive")


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_config(path: Path = CONFIG_PATH, env: dict | None = None) -> IngestConfig:
    """File values first, then environment overrides (empty variables are ignored)."""
    env = os.environ if env is None else env
    values = {}
    if path.exists():
        values = dict(tomllib.loads(path.read_text()).get("ingest", {}))
    mapping = {"LIVE_SOURCE": "source", "LIVE_FALLBACK": "fallback", "LIVE_LOOKBACK_HOURS": "lookback_hours",
               "LIVE_WEATHER_FILL": "weather_fill", "LIVE_WEATHER_DISPLAY": "weather_display",
               "LIVE_ALLOW_UNVERIFIED": "allow_unverified"}
    for variable, key in mapping.items():
        if env.get(variable, "").strip():
            values[key] = env[variable].strip()
    unknown = set(values) - set(IngestConfig.__dataclass_fields__)
    if unknown:
        raise ConfigError(f"unknown settings: {sorted(unknown)}")
    if "lookback_hours" in values:
        values["lookback_hours"] = int(values["lookback_hours"])
    if "stale_after_hours" in values:
        values["stale_after_hours"] = float(values["stale_after_hours"])
    if "allow_unverified" in values and isinstance(values["allow_unverified"], str):
        values["allow_unverified"] = _truthy(values["allow_unverified"])
    return IngestConfig(**values)
