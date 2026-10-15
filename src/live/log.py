"""One logging setup for the live jobs: timestamped lines on stderr, so Actions logs and local runs look the same."""

from __future__ import annotations

import logging
import sys

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure(level: int = logging.INFO) -> None:
    """Configure the root logger once; safe to call from every ``main()``."""
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
