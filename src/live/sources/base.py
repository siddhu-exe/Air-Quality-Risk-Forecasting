"""The one interface every live data source implements.

A source returns hourly rows in **training units and the training hour convention** (hour label T = the hour
starting at T, local Asia/Kolkata, naive), before QC. Everything after that (QC, weather fill, upsert, AQI) is
source-independent, so switching source is a config value.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import pandas as pd

from src.live.qc import VALUE_COLUMNS

SOURCE_COLUMNS = ["station_name", "hour", *VALUE_COLUMNS]


class SourceNotVerified(RuntimeError):
    """The source's hour convention/units have not been checked against real data yet."""


class SourceUnavailable(RuntimeError):
    """The source could not be reached or returned something unusable (message never contains a key)."""


class LiveSource(ABC):
    name: ClassVar[str]  # config value
    tag: ClassVar[str]  # value stored in live_readings.source
    #: False until the hour convention and units were verified against real data.
    verified: ClassVar[bool] = True
    #: what the source cannot supply at all (documented, tested; the audit decides how to cope)
    missing: ClassVar[dict] = {}

    @abstractmethod
    def fetch(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Rows for hour labels in [start, end] (naive local), columns ``SOURCE_COLUMNS``; no QC, no DB."""

    def station_flags(self, station: str) -> dict:
        """Constant flags to store in ``qc_flags`` for every row of a station (e.g. unverified alignment)."""
        return {}

    @staticmethod
    def empty() -> pd.DataFrame:
        return pd.DataFrame(columns=SOURCE_COLUMNS)

    def require_verified(self, allow_unverified: bool) -> None:
        if not self.verified and not allow_unverified:
            raise SourceNotVerified(
                f"source '{self.name}' is not verified against real data (hour convention / units); "
                "run the probe, check the fields, set verified, or pass allow_unverified for a dry run"
            )
