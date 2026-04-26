"""Ticker enrichment + price data via yfinance.

All network calls are wrapped in try/except. If yfinance fails (it often
rate-limits or returns empty frames in local dev), we degrade gracefully:
`sector` becomes "Unknown" and beta/correlation computations fall back to
default values.

We also handle cross-listed / Canadian tickers: when the bare symbol cannot
be resolved, we probe ``.TO`` / ``.V`` / ``.NE`` / ``.CN`` suffixes and
remember the canonical yfinance symbol in the enrichment cache. That way
a Wealthsimple CSV that lists ``FLT`` (Volatus Aerospace, TSXV) still
produces useful sector / price data on subsequent analyses.
"""

import asyncio
import contextlib
import logging
import os
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.analysis import Enrichment


logger = get_logger(__name__)

# yfinance chatters on stderr ("$FLT: possibly delisted; no timezone found",
# "1 Failed download: ...") whenever a symbol can't be resolved. We probe a
# handful of suffixes on purpose, so those warnings are noise to us.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)


@contextlib.contextmanager
def _silence_stderr():
    """Temporarily redirect the process stderr fd — yfinance prints to it
    directly in some code paths, so plain logger config doesn't suffice."""
    try:
        saved = os.dup(2)
    except OSError:
        yield
        return
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
        os.close(devnull)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)


# Ordered: bare symbol first, then Canadian exchanges (TSX, TSXV, NEO, CSE).
_SYMBOL_SUFFIXES = ("", ".TO", ".V", ".NE", ".CN")


def _probe_yf_symbol(ticker: str) -> tuple[str | None, dict]:
    """Find the first yfinance symbol variant that returns real metadata.

    Returns (resolved_symbol, info_dict). Resolved symbol is None if every
    variant fails.
    """
    for suffix in _SYMBOL_SUFFIXES:
        candidate = f"{ticker}{suffix}"
        try:
            with _silence_stderr():
                info = yf.Ticker(candidate).info
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(info, dict):
            continue
        # yfinance returns a stub dict with quoteType="NONE" for unresolvable
        # symbols. Anything else (EQUITY, ETF, MUTUALFUND, ...) is real.
        quote_type = (info.get("quoteType") or "").upper()
        if quote_type and quote_type != "NONE":
            return candidate, info
        if info.get("previousClose") is not None or info.get("regularMarketPrice") is not None:
            return candidate, info
    return None, {}


async def enrich_tickers(
    tickers: list[str], db: AsyncSession
) -> tuple[dict[str, dict], dict[str, str]]:
    """Fetch sector/industry for tickers. Cache in DB with 7-day TTL.

    Returns (enrichments, symbol_map) where ``symbol_map`` maps our internal
    ticker to the resolved yfinance symbol (which may carry a suffix like
    ``.V`` for TSXV listings). Tickers we could not resolve map to themselves.
    """

    enrichments: dict[str, dict] = {}
    symbol_map: dict[str, str] = {}
    to_fetch: list[str] = []

    for ticker in tickers:
        row = await db.execute(select(Enrichment).where(Enrichment.ticker == ticker))
        e = row.scalar_one_or_none()
        if e and (datetime.utcnow() - e.fetched_at) < timedelta(days=7):
            enrichments[ticker] = {
                "sector": e.sector or "Unknown",
                "industry": e.industry or "Unknown",
                "market_cap": e.market_cap or 0,
            }
            symbol_map[ticker] = e.yf_symbol or ticker
        else:
            to_fetch.append(ticker)

    for ticker in to_fetch:
        resolved, info = await asyncio.to_thread(_probe_yf_symbol, ticker)
        data = {"sector": "Unknown", "industry": "Unknown", "market_cap": 0}
        if info:
            data = {
                "sector": info.get("sector") or "Unknown",
                "industry": info.get("industry") or "Unknown",
                "market_cap": info.get("marketCap") or 0,
            }

        existing = await db.execute(
            select(Enrichment).where(Enrichment.ticker == ticker)
        )
        e_row = existing.scalar_one_or_none()
        if e_row:
            e_row.sector = data["sector"]
            e_row.industry = data["industry"]
            e_row.market_cap = data["market_cap"]
            e_row.yf_symbol = resolved
            e_row.fetched_at = datetime.utcnow()
        else:
            db.add(
                Enrichment(
                    ticker=ticker,
                    sector=data["sector"],
                    industry=data["industry"],
                    market_cap=data["market_cap"],
                    yf_symbol=resolved,
                )
            )
        enrichments[ticker] = data
        symbol_map[ticker] = resolved or ticker

    await db.commit()
    return enrichments, symbol_map


async def get_benchmark_prices(
    ticker: str, start_date: str, end_date: str
) -> pd.Series | None:
    """Fetch daily Close prices for a benchmark. Returns a Series or None."""

    def _download():
        try:
            with _silence_stderr():
                data = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    auto_adjust=True,
                )
            if data is None or len(data) == 0:
                return None
            close = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            return close
        except Exception as e:  # noqa: BLE001
            logger.warning("benchmark download failed for %s: %s", ticker, e)
            return None

    return await asyncio.to_thread(_download)


async def get_ticker_prices(
    tickers: list[str],
    start_date: str,
    end_date: str,
    symbol_map: dict[str, str] | None = None,
):
    """Bulk-download daily close prices.

    When ``symbol_map`` is provided we download using resolved yfinance
    symbols and then rename the returned DataFrame's outer column level back
    to the internal ticker. That way downstream risk/correlation code keeps
    looking up by the portfolio's real ticker (e.g. ``FLT``) even though we
    actually fetched ``FLT.V``.
    """
    if not tickers:
        return None

    symbol_map = symbol_map or {t: t for t in tickers}
    yf_symbols = [symbol_map.get(t, t) for t in tickers]
    reverse = {symbol_map.get(t, t): t for t in tickers}

    def _download():
        try:
            with _silence_stderr():
                data = yf.download(
                    yf_symbols,
                    start=start_date,
                    end=end_date,
                    progress=False,
                    auto_adjust=True,
                    group_by="ticker",
                )
            if data is None or len(data) == 0:
                return None

            if isinstance(data.columns, pd.MultiIndex):
                data = data.rename(columns=reverse, level=0)
            elif len(tickers) == 1:
                # Single-ticker downloads come back flat; wrap to MultiIndex so
                # downstream code that expects `data[ticker]["Close"]` works.
                internal = tickers[0]
                data = pd.concat({internal: data}, axis=1)

            return data
        except Exception as e:  # noqa: BLE001
            logger.warning(
                "ticker price download failed for symbols=%s: %s", yf_symbols, e
            )
            return None

    return await asyncio.to_thread(_download)
