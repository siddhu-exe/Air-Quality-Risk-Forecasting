"""Connectivity and schema probe for the live data sources, meant to run on a GitHub runner.

It answers, from the machine that will actually run the hourly job:
  * can api.data.gov.in be reached at all (TCP/TLS/HTTP), and from which country does the runner egress?
  * with the API key: what do the real records look like (fields, station spellings, pollutants,
    last_update format) for Delhi?
  * how fresh is OpenAQ for one Delhi station?

It is informational: it exits 0 whenever it ran to the end, whatever the sources said. API keys are read
from the environment, sent only to their own service, and masked in everything printed or written.
Trigger: workflow_dispatch only (.github/workflows/probe-sources.yml).
"""

from __future__ import annotations

import os
import socket
import sys
import time
from datetime import UTC, datetime

import requests

DGI_HOST = "api.data.gov.in"
DGI_URL = f"https://{DGI_HOST}/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
OPENAQ_LOCATION = "https://api.openaq.org/v3/locations/17"  # R K Puram, CPCB provider
OUR_STATIONS = ["Anand Vihar", "Bawana", "Dwarka-Sector 8", "ITO", "Jahangirpuri", "Punjabi Bagh", "R K Puram"]
TIMEOUT = 40

LINES: list[str] = []


def redact(text: str, secrets: list[str]) -> str:
    """Replace every non-empty secret in ``text`` with ``***``."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def emit(line: str = "", secrets: list[str] | None = None) -> None:
    line = redact(line, secrets or [])
    print(line, flush=True)
    LINES.append(line)


def egress_country() -> str:
    try:
        return requests.get("https://ipinfo.io/country", timeout=15).text.strip()
    except requests.RequestException as exc:
        return f"unknown ({type(exc).__name__})"


def tcp_probe(host: str, port: int = 443) -> str:
    started = time.monotonic()
    try:
        socket.create_connection((host, port), timeout=20).close()
        return f"TCP connect OK in {time.monotonic() - started:.1f}s"
    except OSError as exc:
        return f"TCP connect FAILED after {time.monotonic() - started:.1f}s: {type(exc).__name__}"


def probe_data_gov_in(key: str) -> None:
    emit("## data.gov.in")
    emit(f"- {DGI_HOST}: {tcp_probe(DGI_HOST)}")
    try:
        started = time.monotonic()
        resp = requests.get(f"https://{DGI_HOST}/", timeout=TIMEOUT)
        emit(f"- GET / (no key): HTTP {resp.status_code} in {time.monotonic() - started:.1f}s")
    except requests.RequestException as exc:
        emit(f"- GET / (no key): {type(exc).__name__}")
    if not key:
        emit("- DATA_GOV_IN_API_KEY not set: skipping the keyed request")
        return
    params = {"api-key": key, "format": "json", "limit": 500, "filters[city]": "Delhi"}
    try:
        started = time.monotonic()
        resp = requests.get(DGI_URL, params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        emit(f"- keyed request failed: {type(exc).__name__}: {redact(str(exc), [key])[:200]}", [key])
        return
    emit(
        f"- keyed request: HTTP {resp.status_code} in {time.monotonic() - started:.1f}s, {len(resp.content)} bytes, "
        f"content-type {resp.headers.get('content-type')}"
    )
    for header in ("x-ratelimit-limit", "x-ratelimit-remaining", "retry-after"):
        if header in resp.headers:
            emit(f"- header {header}: {resp.headers[header]}")
    try:
        body = resp.json()
    except ValueError:
        emit(f"- response is not JSON: {redact(resp.text[:200], [key])!r}", [key])
        return
    records = body.get("records", [])
    emit(
        f"- top-level keys: {sorted(body)}; total={body.get('total')} count={body.get('count')} returned={len(records)}"
    )
    if not records:
        return
    emit(f"- record keys: {sorted(records[0])}")
    emit(f"- distinct pollutant_id: {sorted({r.get('pollutant_id') for r in records})}")
    emit(f"- last_update samples: {sorted({r.get('last_update') for r in records})[:4]}")
    names = sorted({r.get("station") for r in records})
    emit(f"- Delhi stations in feed: {len(names)}")
    for ours in OUR_STATIONS:
        matches = [n for n in names if ours.lower().split("-")[0].strip() in (n or "").lower()]
        emit(f"  - {ours}: {matches or 'NOT FOUND'}")
    sample = [r for r in records if "r k puram" in (r.get("station") or "").lower()][:8]
    for r in sample:
        emit(
            "  - sample "
            + ", ".join(
                f"{k}={r.get(k)}"
                for k in ("station", "pollutant_id", "pollutant_min", "pollutant_max", "pollutant_avg", "last_update")
            )
        )


def probe_openaq(key: str) -> None:
    emit("## OpenAQ")
    if not key:
        emit("- OPENAQ_API_KEY not set: skipped")
        return
    try:
        resp = requests.get(OPENAQ_LOCATION, headers={"X-API-Key": key}, timeout=TIMEOUT)
        resp.raise_for_status()
        last = datetime.fromisoformat(resp.json()["results"][0]["datetimeLast"]["utc"].replace("Z", "+00:00"))
        age = (datetime.now(UTC) - last).total_seconds() / 3600
        emit(f"- R K Puram newest value: {last:%Y-%m-%d %H:%M} UTC, {age:.1f} hours old")
    except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
        emit(f"- request failed: {type(exc).__name__}", [key])


def main() -> int:
    keys = [os.environ.get("DATA_GOV_IN_API_KEY", "").strip(), os.environ.get("OPENAQ_API_KEY", "").strip()]
    emit(f"# Source probe {datetime.now(UTC):%Y-%m-%d %H:%M} UTC")
    emit(f"- runner egress country: {egress_country()}")
    probe_data_gov_in(keys[0])
    probe_openaq(keys[1])
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(LINES) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
