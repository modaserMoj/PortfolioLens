"""Central logging configuration.

All module logs flow through this. Using Python's standard library so we get:
- Consistent formatting alongside uvicorn's access logs.
- Per-module log levels via LOG_LEVEL / MODULE_LOG_LEVELS env vars.
- A single place to add handlers (file, JSON, Sentry, etc.) later.

Usage in any module:

    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("something happened")
"""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False

_DEFAULT_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DEFAULT_DATEFMT = "%H:%M:%S"


def configure_logging(level: str | None = None) -> None:
    """Configure root logging. Idempotent — safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    level_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    level_value = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT, datefmt=_DEFAULT_DATEFMT))

    root = logging.getLogger()
    root.setLevel(level_value)
    # Remove pre-existing handlers (uvicorn installs its own stderr handler on
    # the root logger under --reload; leaving it in place causes duplicate
    # lines for every log call).
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)

    # App logger defaults — chatty during development is fine.
    logging.getLogger("app").setLevel(level_value)

    # Silence yfinance's stderr chatter (we probe symbols on purpose, so its
    # "possibly delisted" warnings are noise).
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger, configuring root on first call."""
    configure_logging()
    return logging.getLogger(name)
