"""Database access for the forecast job. Same connection helper as the ingest (``DATABASE_URL``), same rules: no DELETE,
SQL text asserted by tests. A dry run connects with ``DATABASE_URL_READONLY`` (the ``api_readonly`` role cannot write)."""

from __future__ import annotations

import json

import pandas as pd

from src.live import models as model_mod
from src.live.qc import VALUE_COLUMNS
from src.live.store import Store

SELECT_READINGS = f"""
select station_id, ts, {", ".join(VALUE_COLUMNS)}, weather_source, qc_flags
from aq.live_readings where station_id = any(%s) and ts > %s and ts <= %s order by station_id, ts
"""
SELECT_AQI = "select station_id, ts, aqi from aq.live_aqi where station_id = any(%s) and ts > %s and ts <= %s order by station_id, ts"
SELECT_NEWEST_AQI = "select max(ts) from aq.live_aqi"
UPSERT_MODEL = """
insert into aq.model_registry (model_version, model_name, horizon, target, file, sha256, training_window, metrics_source, library_versions, active)
values (%s, %s, %s, 'aqi', %s, %s, %s, %s, %s, true)
on conflict (model_version) do update set sha256 = excluded.sha256, file = excluded.file, library_versions = excluded.library_versions, active = true
"""
#: a forecast is immutable once written for (issue_time, station, horizon, target): re-running an hour never changes what was published
INSERT_FORECASTS = """
insert into aq.forecasts (issue_time, target_time, station_id, horizon, target, model_version, y_hat, y_persistence) values %s
on conflict (issue_time, station_id, horizon, target) do nothing
"""


class ForecastStore(Store):
    def newest_aqi_hour(self) -> pd.Timestamp | None:
        self._cur.execute(SELECT_NEWEST_AQI)
        value = self._cur.fetchone()[0]
        return None if value is None else pd.Timestamp(value).tz_convert("Asia/Kolkata")

    def read_history(
        self, station_ids: list[int], since: pd.Timestamp, until: pd.Timestamp
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """(readings, aqi) for ``since < ts <= until``, DB-shaped (see ``forecast.to_inputs``)."""
        args = (list(station_ids), since, until)
        self._cur.execute(SELECT_READINGS, args)
        readings = pd.DataFrame(
            self._cur.fetchall(), columns=["station_id", "ts", *VALUE_COLUMNS, "weather_source", "qc_flags"]
        )
        self._cur.execute(SELECT_AQI, args)
        aqi = pd.DataFrame(self._cur.fetchall(), columns=["station_id", "ts", "aqi"])
        return readings, aqi

    def register_models(self, hashes: dict[str, str], library_versions: dict) -> int:
        for horizon, files in model_mod.ARTIFACTS.items():
            self._cur.execute(
                UPSERT_MODEL,
                (
                    model_mod.VERSIONS[horizon],
                    model_mod.NAMES[horizon],
                    horizon,
                    files["model"],
                    hashes[files["model"]],
                    model_mod.TRAINING_WINDOW,
                    model_mod.METRICS_SOURCE,
                    json.dumps(library_versions),
                ),
            )
        return len(model_mod.ARTIFACTS)

    def insert_forecasts(self, rows: pd.DataFrame) -> int:
        from psycopg2.extras import execute_values

        values = [
            (
                r.issue_time.to_pydatetime(),
                r.target_time.to_pydatetime(),
                int(r.station_id),
                int(r.horizon),
                r.target,
                r.model_version,
                float(r.y_hat),
                float(r.y_persistence),
            )
            for r in rows.itertuples()
        ]
        if values:
            execute_values(self._cur, INSERT_FORECASTS, values, page_size=500)
        return self._cur.rowcount if values else 0
