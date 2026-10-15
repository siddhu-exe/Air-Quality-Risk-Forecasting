"""Settings from environment variables (never logged)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default="", repr=False)  # DATABASE_URL_READONLY; the API holds no write credential
    frontend_origins: tuple[str, ...] = ()
    stale_after_hours: float = 3.0
    cache_seconds: int = 60
    statement_timeout_ms: int = 8000

    @classmethod
    def from_env(cls, env: dict | None = None) -> Settings:
        env = os.environ if env is None else env
        origins = tuple(o.strip().rstrip("/") for o in env.get("FRONTEND_ORIGIN", "").split(",") if o.strip())
        return cls(
            database_url=env.get("DATABASE_URL_READONLY", ""),
            frontend_origins=origins,
            stale_after_hours=float(env.get("STALE_AFTER_HOURS", "3")),
            cache_seconds=int(env.get("CACHE_SECONDS", "60")),
        )
