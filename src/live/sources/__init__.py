"""Live data sources behind one interface (see ``base.LiveSource``). Pick one by name from the config."""

from __future__ import annotations

from src.live.sources.base import LiveSource, SourceNotVerified, SourceStale, SourceUnavailable
from src.live.sources.data_gov_in import DataGovInSource
from src.live.sources.openaq_source import OpenAQSource

REGISTRY: dict[str, type[LiveSource]] = {OpenAQSource.name: OpenAQSource, DataGovInSource.name: DataGovInSource}


def get_source(name: str) -> LiveSource:
    try:
        return REGISTRY[name]()
    except KeyError:
        raise ValueError(f"unknown source {name!r}; choose one of {sorted(REGISTRY)}") from None


__all__ = [
    "LiveSource",
    "SourceNotVerified",
    "SourceStale",
    "SourceUnavailable",
    "OpenAQSource",
    "DataGovInSource",
    "REGISTRY",
    "get_source",
]
