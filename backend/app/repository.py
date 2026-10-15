"""Read-only database access. The API connects with the ``api_readonly`` role and runs SELECTs only (asserted in tests)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

SELECT_STATIONS = (
    "select station_id, station_name, latitude, longitude, coords_approximate from aq.stations order by station_id"
)
SELECT_LATEST_AQI = "select distinct on (station_id) station_id, ts, aqi from aq.live_aqi order by station_id, ts desc"
SELECT_LATEST_READINGS = """
select distinct on (station_id) station_id, ts, pm25, pm10, no2, so2, nh3, co, o3, temperature, humidity, wind_speed,
       solar_radiation
from aq.live_readings order by station_id, ts desc
"""
SELECT_LATEST_PM25 = """
select distinct on (station_id) station_id, ts, pm25 from aq.live_readings where pm25 is not null
order by station_id, ts desc
"""
SELECT_HISTORY_AQI = "select ts, aqi from aq.live_aqi where station_id = %s and ts > %s order by ts"
SELECT_HISTORY_PM25 = (
    "select ts, pm25 from aq.live_readings where station_id = %s and pm25 is not null and ts > %s order by ts"
)
SELECT_LATEST_FORECASTS = """
select distinct on (station_id, horizon, target) station_id, horizon, target, issue_time, target_time, y_hat,
       y_persistence, y_window_update, model_version
from aq.forecasts where run_type = 'live' and issue_time > %s
order by station_id, horizon, target, issue_time desc
"""
SELECT_LATEST_RUN = """
select status, started_at, finished_at, details from aq.job_runs
where job = 'forecast' and run_type = 'live' order by started_at desc limit 1
"""
SELECT_SKILL = """
select horizon, target, window_end, n, skill_mae, skill_vs_window_update from aq.skill_rolling
where station_id is null and window_days = 30 and window_end >= %s order by horizon, target, window_end
"""
SELECT_JOBS = """
select distinct on (job) job, status, coalesce(finished_at, started_at) as last_run_at from aq.job_runs
where run_type = 'live' order by job, started_at desc
"""
SELECT_HOURLY_PRESENCE = (
    "select station_id, date_trunc('hour', ts) as hour from aq.live_readings where ts > %s group by 1, 2"
)
SELECT_FORECAST_STATION_HOURS = (
    "select count(distinct (issue_time, station_id)) from aq.forecasts where run_type = 'live' and issue_time > %s"
)
SELECT_REGISTRY = "select model_version, model_name, horizon, target, sha256 from aq.model_registry where active order by horizon, target"
SELECT_INGEST_RUNS = """
select started_at, status, details from aq.job_runs
where job = 'ingest' and run_type = 'live' and started_at > %s order by started_at
"""
SELECT_NEWEST_READING = "select max(ts) from aq.live_readings"
SELECT_NEWEST_FORECAST = "select max(issue_time) from aq.forecasts where run_type = 'live'"
ALL_QUERIES = [v for k, v in dict(globals()).items() if k.startswith("SELECT_")]


class Repository(Protocol):
    """What the service layer reads. Rows are plain dicts so the service has no database dependency."""

    def stations(self) -> list[dict]: ...
    def latest_aqi(self) -> dict[int, dict]: ...
    def latest_readings(self) -> dict[int, dict]: ...
    def latest_pm25(self) -> dict[int, dict]: ...
    def history(self, station_id: int, target: str, since: datetime) -> list[tuple[datetime, float]]: ...
    def latest_forecasts(self, since: datetime) -> list[dict]: ...
    def latest_run(self) -> dict | None: ...
    def skill(self, since: datetime) -> list[dict]: ...
    def jobs(self) -> list[dict]: ...
    def hourly_presence(self, since: datetime) -> dict[int, set[datetime]]: ...
    def forecast_station_hours(self, since: datetime) -> int: ...
    def registry(self) -> list[dict]: ...
    def ingest_runs(self, since: datetime) -> list[dict]: ...
    def newest_reading(self) -> datetime | None: ...
    def newest_forecast(self) -> datetime | None: ...
    def ping(self) -> bool: ...


class PgRepository:
    """psycopg2 implementation over a small thread-safe pool; every query runs in a read-only transaction."""

    def __init__(self, database_url: str, statement_timeout_ms: int = 8000, maxconn: int = 4) -> None:
        from psycopg2.pool import ThreadedConnectionPool

        self._pool = ThreadedConnectionPool(
            1,
            maxconn,
            database_url,
            connect_timeout=10,
            options=f"-c statement_timeout={int(statement_timeout_ms)} -c default_transaction_read_only=on",
        )

    def _rows(self, sql: str, args: tuple = ()) -> list[dict]:
        from psycopg2.extras import RealDictCursor

        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, args)
                rows = [dict(r) for r in cur.fetchall()]
            conn.rollback()  # nothing to commit; leaves the pooled connection clean
            return rows
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def _scalar(self, sql: str, args: tuple = ()) -> Any:
        rows = self._rows(sql, args)
        return next(iter(rows[0].values())) if rows else None

    def stations(self) -> list[dict]:
        return self._rows(SELECT_STATIONS)

    def latest_aqi(self) -> dict[int, dict]:
        return {r["station_id"]: r for r in self._rows(SELECT_LATEST_AQI)}

    def latest_readings(self) -> dict[int, dict]:
        return {r["station_id"]: r for r in self._rows(SELECT_LATEST_READINGS)}

    def latest_pm25(self) -> dict[int, dict]:
        return {r["station_id"]: r for r in self._rows(SELECT_LATEST_PM25)}

    def history(self, station_id: int, target: str, since: datetime) -> list[tuple[datetime, float]]:
        sql, column = (SELECT_HISTORY_AQI, "aqi") if target == "aqi" else (SELECT_HISTORY_PM25, "pm25")
        return [(r["ts"], float(r[column])) for r in self._rows(sql, (station_id, since))]

    def latest_forecasts(self, since: datetime) -> list[dict]:
        return self._rows(SELECT_LATEST_FORECASTS, (since,))

    def latest_run(self) -> dict | None:
        rows = self._rows(SELECT_LATEST_RUN)
        return rows[0] if rows else None

    def skill(self, since: datetime) -> list[dict]:
        return self._rows(SELECT_SKILL, (since.date(),))

    def jobs(self) -> list[dict]:
        return self._rows(SELECT_JOBS)

    def hourly_presence(self, since: datetime) -> dict[int, set[datetime]]:
        out: dict[int, set[datetime]] = {}
        for r in self._rows(SELECT_HOURLY_PRESENCE, (since,)):
            out.setdefault(r["station_id"], set()).add(r["hour"])
        return out

    def forecast_station_hours(self, since: datetime) -> int:
        return int(self._scalar(SELECT_FORECAST_STATION_HOURS, (since,)) or 0)

    def registry(self) -> list[dict]:
        return self._rows(SELECT_REGISTRY)

    def ingest_runs(self, since: datetime) -> list[dict]:
        return self._rows(SELECT_INGEST_RUNS, (since,))

    def newest_reading(self) -> datetime | None:
        return self._scalar(SELECT_NEWEST_READING)

    def newest_forecast(self) -> datetime | None:
        return self._scalar(SELECT_NEWEST_FORECAST)

    def ping(self) -> bool:
        return self._scalar("select 1") == 1
