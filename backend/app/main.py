"""FastAPI application: ``GET /api/v1/*``, read-only, backed by the live database.

uvicorn backend.app.main:app --port 8000        # run from the repo root; needs DATABASE_URL_READONLY
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app import models
from backend.app.repository import PgRepository, Repository
from backend.app.service import NotFound, Service
from backend.app.settings import Settings

log = logging.getLogger("api")


class RepositoryHolder:
    """Opens the database connection pool on first use, so a cold start answers /health without waiting for it."""

    def __init__(self, settings: Settings, repo: Repository | None = None) -> None:
        self.settings, self._repo = settings, repo

    def get(self) -> Repository:
        if self._repo is None:
            if not self.settings.database_url:
                raise RuntimeError("DATABASE_URL_READONLY is not set")
            self._repo = PgRepository(self.settings.database_url, self.settings.statement_timeout_ms)
        return self._repo


class LazyRepository:
    """Looks like a Repository but opens the connection pool on the first query, so routes that need no data (/backtest)
    and a cold start never wait for, or fail on, the database."""

    def __init__(self, holder: RepositoryHolder) -> None:
        self._holder = holder

    def __getattr__(self, name: str) -> Any:
        return getattr(self._holder.get(), name)


def create_app(
    settings: Settings | None = None,
    repo: Repository | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    holder = RepositoryHolder(settings, repo)
    now = clock or (lambda: datetime.now(UTC))
    app = FastAPI(
        title="Delhi air quality forecast API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json"
    )

    def service() -> Service:
        return Service(LazyRepository(holder), settings, now)  # type: ignore[arg-type]

    @app.middleware("http")
    async def cache_headers(request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        if request.method == "GET" and response.status_code == 200 and request.url.path.startswith("/api/v1/"):
            no_cache = request.url.path.endswith("/health")
            response.headers["Cache-Control"] = "no-store" if no_cache else f"public, max-age={settings.cache_seconds}"
        return response

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": f"unknown station '{exc}'"}, status_code=404)

    @app.middleware("http")
    async def unavailable(request: Request, call_next: Callable) -> Response:
        # A catch-all `exception_handler(Exception)` runs in Starlette's outermost layer, outside CORSMiddleware, so its 503
        # would reach the browser without Access-Control-Allow-Origin and show up as a CORS error that hides the real status.
        # Catching here keeps the response inside the CORS layer. The message names the exception type only: a driver
        # error can echo connection details.
        try:
            return await call_next(request)
        except Exception as exc:
            log.error("request failed: %s", type(exc).__name__)
            return JSONResponse({"detail": "the forecast service cannot reach its database right now"}, status_code=503)

    # added last = outermost: every response, errors included, passes through it
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins),
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health", response_model=models.Health, response_model_by_alias=True)
    def health() -> models.Health:
        return service().health()

    @app.get("/api/v1/overview", response_model=models.Overview, response_model_by_alias=True)
    def overview() -> models.Overview:
        return service().overview()

    @app.get("/api/v1/stations", response_model=models.Stations, response_model_by_alias=True)
    def stations() -> models.Stations:
        return service().stations()

    @app.get(
        "/api/v1/stations/{station_id}/forecast", response_model=models.StationForecast, response_model_by_alias=True
    )
    def station_forecast(station_id: str, target: Literal["aqi", "pm25"] = Query("aqi")) -> models.StationForecast:
        return service().station_forecast(station_id, target)

    @app.get("/api/v1/alerts/grap", response_model=models.GrapAlerts, response_model_by_alias=True)
    def grap() -> models.GrapAlerts:
        return service().grap()

    @app.get("/api/v1/model-health", response_model=models.ModelHealth, response_model_by_alias=True)
    def model_health() -> models.ModelHealth:
        return service().model_health()

    @app.get("/api/v1/backtest", response_model=models.Backtest, response_model_by_alias=True)
    def backtest() -> models.Backtest:
        return service().backtest()

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {"service": "delhi-air-quality-forecast", "docs": "/api/docs", "health": "/api/v1/health"}

    return app


app = create_app()
