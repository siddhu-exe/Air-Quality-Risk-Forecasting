"""OpenAQ v3 as a live source. All conversions live in ``src/live/openaq.py`` (pinned and tested)."""
from __future__ import annotations

import pandas as pd
import requests

from src.live import openaq
from src.live.sources.base import SOURCE_COLUMNS, LiveSource, SourceUnavailable


class OpenAQSource(LiveSource):
    name = "openaq"
    tag = openaq.SOURCE_TAG
    verified = True      # hour convention and units verified against the CSVs: docs/TIER_3/openaq_overlap_check.md
    missing = openaq.MISSING_FROM_OPENAQ

    def fetch(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        hours = pd.date_range(start, end, freq="h")
        frames = []
        for station, location_id in openaq.LOCATIONS.items():
            try:
                sensors = openaq.live_sensors(location_id, station)     # raises UnitLabelChanged if labels moved
                raw = {param: openaq.fetch_15min(sensor_id, str(start), str(end + pd.Timedelta(minutes=59)))
                       for param, (sensor_id, _label) in sensors.items()}
            except requests.RequestException as exc:
                raise SourceUnavailable(f"OpenAQ request failed for {station}: {type(exc).__name__}") from None
            frame = openaq.hourly_frame(raw, hours)
            frame = frame.dropna(how="all")
            frames.append(frame.rename_axis("hour").reset_index().assign(station_name=station))
        out = pd.concat(frames, ignore_index=True) if frames else self.empty()
        return out.reindex(columns=SOURCE_COLUMNS)      # columns OpenAQ cannot supply (solar, NH3, ITO weather) stay NaN

    def station_flags(self, station: str) -> dict:
        return dict(openaq.UNVERIFIED_FLAG) if station in openaq.ALIGNMENT_UNVERIFIED_2026 else {}
