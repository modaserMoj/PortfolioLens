"""Public parser entry point.

We intentionally do not model brokers as first-class objects any more. The
only operation callers need is "give me the trades in this CSV", and the
generic parser handles every broker we have seen plus unknown formats via
synonym matching + an LLM fallback.
"""

from __future__ import annotations

from typing import Any

from app.parsers.generic import GenericCSVParser


def parse_any(csv_text: str) -> tuple[list[dict[str, Any]], str]:
    """Extract trades from any CSV export. Returns (trades, format_label)."""
    return GenericCSVParser().parse(csv_text)
