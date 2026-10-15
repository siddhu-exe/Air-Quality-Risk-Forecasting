"""Database access for the live jobs and the API.

Connection strings come only from the environment (``DATABASE_URL`` for the jobs,
``DATABASE_URL_READONLY`` for the API); a local ``.env`` is loaded if present. They are
never printed or logged. Errors that could echo the URL are re-raised without it.
"""

from __future__ import annotations

import os
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit

import psycopg2

try:  # a .env file is a local convenience; CI and Azure inject real env vars
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

WRITER_VAR = "DATABASE_URL"
READONLY_VAR = "DATABASE_URL_READONLY"


class DatabaseConfigError(RuntimeError):
    """Raised when a connection string is missing or unusable (never includes its value)."""


_RESERVED = set("@:/?#[] +%")


def _classify(driver_message: str) -> str:
    """Map a libpq error to a fixed message that cannot contain URL fragments."""
    m = driver_message.lower()
    if (
        "invalid integer value" in m
        or "could not translate host name" in m
        or "invalid uri" in m
        or 'missing "="' in m
        or "invalid connection option" in m
    ):
        return (
            "the URL is malformed; percent-encode reserved characters in the password "
            "(@ : / ? # [ ] + space %) or use a password of letters and digits only"
        )
    if "tenant or user not found" in m:
        return "pooler user not found; the user must be '<role>.<project-ref>'"
    if "password authentication failed" in m or "authentication failed" in m:
        return "authentication failed (wrong role or password)"
    if "timeout" in m or "timed out" in m:
        return "connection timed out"
    if "ssl" in m:
        return "SSL negotiation failed"
    if "connection refused" in m or "could not connect" in m or "network is unreachable" in m:
        return "server unreachable (host/port)"
    return "connection failed (details withheld so no credential is echoed)"


def describe_url(var: str = WRITER_VAR) -> dict:
    """Shape of a connection URL for debugging, never including the password itself."""
    url = get_url(var)
    scheme, _, rest = url.partition("://")
    userinfo, at, hostpart = rest.rpartition("@")
    user, _, password = userinfo.partition(":")
    host_and_port, _, tail = hostpart.partition("/")
    host, _, port = host_and_port.partition(":")
    return {
        "scheme": scheme,
        "has_userinfo": bool(at),
        "user": user,  # a role name like job_writer.<project-ref>: not a secret
        "has_password": bool(password),
        "password_length": len(password),
        "password_has_reserved_chars": sorted(c for c in password if c in _RESERVED),
        "host": host,
        "port": port,
        "database": tail.split("?")[0],
    }


def get_url(var: str = WRITER_VAR) -> str:
    url = os.environ.get(var, "").strip()
    if not url:
        raise DatabaseConfigError(f"{var} is not set (see .env.example)")
    if not url.startswith(("postgresql://", "postgres://")):
        raise DatabaseConfigError(f"{var} must be a postgresql:// URL")
    return url


@contextmanager
def connect(var: str = WRITER_VAR) -> Iterator[psycopg2.extensions.connection]:
    """Open a pooler connection, commit on success, roll back on error, always close."""
    url = get_url(var)
    extra = {}
    if os.environ.get("FORCE_IPV4") == "1":
        # Some dev networks (IPv6 NAT64) hang for minutes on the IPv6 address; pin the IPv4 one.
        try:
            extra["hostaddr"] = socket.getaddrinfo(urlsplit(url).hostname, None, socket.AF_INET)[0][4][0]
        except (socket.gaierror, IndexError, TypeError):
            pass
    try:
        conn = psycopg2.connect(url, connect_timeout=15, **extra)
    except psycopg2.Error as exc:
        # libpq error text can quote pieces of the URL (including the password when the URL is
        # malformed), so it is never forwarded: only a fixed, classified message is raised.
        raise DatabaseConfigError(f"could not connect using {var}: {_classify(str(exc))}") from None
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
