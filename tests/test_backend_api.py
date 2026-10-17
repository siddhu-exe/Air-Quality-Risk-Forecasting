"""HTTP layer: routes, camelCase JSON, caching, CORS and error handling, on the fake repository."""

import re

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from backend.app.main import create_app  # noqa: E402
from backend.app.settings import Settings  # noqa: E402
from tests.test_backend_service import NOW, FakeRepo, row  # noqa: E402

ORIGIN = "https://delhi-air.example.app"


def client(repo=None, **settings):
    app = create_app(
        Settings(frontend_origins=(ORIGIN,), **settings),
        repo or FakeRepo(forecasts=[row(3, "aqi_6h", 300.0)]),
        lambda: NOW,
    )
    return TestClient(app, raise_server_exceptions=False)


def test_every_documented_route_answers_200_with_camel_case_keys():
    c = client()
    for path in (
        "/api/v1/health",
        "/api/v1/overview",
        "/api/v1/stations",
        "/api/v1/stations/3/forecast?target=aqi",
        "/api/v1/stations/3/forecast?target=pm25",
        "/api/v1/alerts/grap",
        "/api/v1/model-health",
        "/api/v1/backtest",
    ):
        response = c.get(path)
        assert response.status_code == 200, path
        assert "dataAsOf" in response.json() or path.endswith("backtest"), path
    body = c.get("/api/v1/overview").json()
    assert body["stations"][0]["forecasts"][1]["windowUpdate"] == 240.0 and "window_update" not in str(body)


def test_unknown_station_and_bad_target_are_client_errors():
    c = client()
    assert c.get("/api/v1/stations/99/forecast").status_code == 404
    assert c.get("/api/v1/stations/3/forecast?target=no2").status_code == 422


def test_caching_headers_and_cors_are_restricted_to_the_frontend_origin():
    c = client(cache_seconds=60)
    assert c.get("/api/v1/overview").headers["cache-control"] == "public, max-age=60"
    assert c.get("/api/v1/health").headers["cache-control"] == "no-store"
    allowed = c.get("/api/v1/overview", headers={"Origin": ORIGIN})
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    blocked = c.get("/api/v1/overview", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_a_database_failure_is_a_503_that_leaks_nothing():
    class Broken(FakeRepo):
        def stations(self):
            raise RuntimeError("could not connect to server: host=secret.example password=hunter2")

    response = client(Broken()).get("/api/v1/overview")
    assert response.status_code == 503
    assert "hunter2" not in response.text and "secret.example" not in response.text


def test_health_reports_degraded_not_an_error_when_the_database_is_down():
    response = client(FakeRepo(ping=False)).get("/api/v1/health")
    assert response.status_code == 200 and response.json()["status"] == "degraded"


def test_the_api_only_reads():
    from backend.app import repository

    for sql in repository.ALL_QUERIES:
        text = sql.strip().lower()
        assert text.startswith("select"), sql
        assert not re.search(r"\b(insert|update|delete|truncate|drop|alter)\b", text), (
            sql
        )  # \b: window_update is a column
    assert repository.ALL_QUERIES and "run_type = 'live'" in repository.SELECT_LATEST_FORECASTS


def test_no_write_credential_or_models_are_needed(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert Settings.from_env(
        {"DATABASE_URL_READONLY": "x", "FRONTEND_ORIGIN": f"{ORIGIN}/, http://localhost:5173"}
    ).frontend_origins == (
        ORIGIN,
        "http://localhost:5173",
    )


def test_deploy_workflow_is_manual_only_and_uses_oidc_not_a_stored_password():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / ".github/workflows/deploy-backend.yml").read_text()
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    assert "workflow_dispatch" in code and "schedule:" not in code
    assert not re.search(
        r"^  (push|pull_request):", code, re.M
    )  # no automatic trigger yet (docker's `push: true` is not one)
    assert (
        "id-token: write" in code
        and "azure/login@v2" in code
        and "client-secret" not in code
        and "AZURE_CREDENTIALS" not in code
    )
    assert "packages: write" in code and "if: inputs.deploy" in code
    assert "vars.FRONTEND_ORIGIN" in code and '--set-env-vars "FRONTEND_ORIGIN=' in code
    assert '"DATABASE_URL_READONLY=secretref:database-url-readonly"' in code


def test_preflight_from_the_allowed_origin_is_answered_and_a_random_origin_is_not():
    c = client()
    ask = {"Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "content-type"}
    ok = c.options("/api/v1/overview", headers={"Origin": ORIGIN, **ask})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == ORIGIN
    other = c.options("/api/v1/overview", headers={"Origin": "https://evil.example", **ask})
    assert other.status_code == 400 and "access-control-allow-origin" not in other.headers


def test_error_responses_carry_cors_headers_for_the_allowed_origin_only():
    """A 503 (database unreachable) without the header reaches the browser as a CORS error that hides the real status."""

    class Broken(FakeRepo):
        def latest_forecasts(self, *args, **kwargs):
            raise RuntimeError("connection refused")

    c = client(Broken())
    for path in ("/api/v1/overview", "/api/v1/stations/99/forecast"):
        allowed = c.get(path, headers={"Origin": ORIGIN})
        assert allowed.status_code in (404, 503) and allowed.headers["access-control-allow-origin"] == ORIGIN, path
        other = c.get(path, headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in other.headers, path
    assert c.get("/api/v1/overview", headers={"Origin": ORIGIN}).status_code == 503


def test_backtest_needs_no_database():
    app = create_app(Settings(frontend_origins=(ORIGIN,)), None, lambda: NOW)  # no repo, no DATABASE_URL_READONLY
    c = TestClient(app, raise_server_exceptions=False)
    assert c.get("/api/v1/backtest").status_code == 200
    assert c.get("/api/v1/overview").status_code == 503
