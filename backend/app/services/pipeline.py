"""End-to-end analytics pipeline orchestrator."""

import time
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.behavioral import compute_behavioral
from app.analytics.clustering import compute_clustering
from app.analytics.performance import compute_performance
from app.analytics.risk import compute_risk
from app.core.config import settings
from app.core.logging import get_logger
from app.llm.summarizer import generate_insight
from app.models.analysis import AnalyticsResult, Insight
from app.models.portfolio import Trade
from app.services.enrichment import (
    enrich_tickers,
    get_benchmark_prices,
    get_ticker_prices,
)


logger = get_logger(__name__)


async def run_analytics_pipeline(portfolio_id: UUID, db: AsyncSession) -> None:
    t0 = time.perf_counter()
    logger.info("pipeline start portfolio=%s", portfolio_id)

    # 1. Load trades
    result = await db.execute(
        select(Trade)
        .where(Trade.portfolio_id == portfolio_id)
        .order_by(Trade.trade_date)
    )
    trades_orm = result.scalars().all()

    trades = [
        {
            "ticker": t.ticker,
            "action": t.action,
            "quantity": float(t.quantity),
            "price": float(t.price),
            "total_amount": float(t.total_amount),
            "fees": float(t.fees),
            "trade_date": t.trade_date,
            "currency": t.currency,
        }
        for t in trades_orm
    ]
    if not trades:
        logger.warning("pipeline portfolio=%s has no trades; aborting", portfolio_id)
        return

    n_buys = sum(1 for t in trades if t["action"] == "BUY")
    n_sells = sum(1 for t in trades if t["action"] == "SELL")
    tickers = sorted({t["ticker"] for t in trades})
    logger.info(
        "pipeline portfolio=%s loaded %d trades (BUY=%d SELL=%d) across %d ticker(s)",
        portfolio_id,
        len(trades),
        n_buys,
        n_sells,
        len(tickers),
    )

    # 2. Enrich (also resolves yfinance symbol variants for cross-listed
    #    tickers like TSX/TSXV names that need a `.TO` / `.V` suffix).
    t_enrich = time.perf_counter()
    enrichments, symbol_map = await enrich_tickers(tickers, db)
    unresolved = [t for t in tickers if not symbol_map.get(t)]
    logger.info(
        "pipeline enrichment done in %.2fs (resolved=%d unresolved=%s)",
        time.perf_counter() - t_enrich,
        len(tickers) - len(unresolved),
        unresolved,
    )

    # 3. Prices (widen the window slightly to catch returns on boundary days)
    start_dt = min(t["trade_date"] for t in trades)
    end_dt = max(t["trade_date"] for t in trades) + timedelta(days=1)
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = end_dt.strftime("%Y-%m-%d")

    t_prices = time.perf_counter()
    benchmark_prices = await get_benchmark_prices(
        settings.BENCHMARK_TICKER, start_date, end_date
    )
    ticker_prices = await get_ticker_prices(
        tickers, start_date, end_date, symbol_map=symbol_map
    )
    logger.info(
        "pipeline prices fetched in %.2fs (benchmark=%s rows=%d, ticker_prices=%s)",
        time.perf_counter() - t_prices,
        settings.BENCHMARK_TICKER,
        0 if benchmark_prices is None else len(benchmark_prices),
        "yes" if ticker_prices is not None else "no",
    )

    # 4. Performance
    perf = compute_performance(trades, benchmark_prices, settings.RISK_FREE_RATE)
    closed_trades = perf.pop("_closed_trades", [])
    logger.info(
        "pipeline performance: closed_trades=%d total_return=%s%% sharpe=%s win_rate=%s%%",
        len(closed_trades),
        perf.get("total_return_pct"),
        perf.get("sharpe_ratio"),
        perf.get("win_rate_pct"),
    )

    # Loud warning if SELLs couldn't be matched by FIFO — the single most
    # common reason a valid CSV produces all-zero performance metrics.
    if n_sells > 0 and not closed_trades:
        sell_tickers = {t["ticker"] for t in trades if t["action"] == "SELL"}
        buy_tickers = {t["ticker"] for t in trades if t["action"] == "BUY"}
        orphan = sorted(sell_tickers - buy_tickers)
        logger.warning(
            "pipeline portfolio=%s: %d SELL row(s) produced 0 closed trades via FIFO. "
            "SELL tickers without a prior BUY in this file: %s. "
            "Performance metrics will be zero. Re-export including earlier "
            "buy history to see real returns.",
            portfolio_id,
            n_sells,
            orphan or "(none — sells preceded buys chronologically?)",
        )

    # 5. Risk
    risk = compute_risk(
        trades, enrichments, benchmark_prices, ticker_prices, settings.RISK_FREE_RATE
    )
    logger.info(
        "pipeline risk: hhi=%s level=%s beta=%s alpha=%s%% top_holdings=%d",
        risk.get("concentration_hhi"),
        risk.get("concentration_level"),
        risk.get("portfolio_beta"),
        risk.get("alpha_annualized"),
        len(risk.get("top_holdings", [])),
    )

    # 6. Behavioral
    behav = compute_behavioral(trades, closed_trades)
    logger.info(
        "pipeline behavioral: avg_holding=%s days freq=%s/mo overtrading=%s",
        behav.get("avg_holding_days"),
        behav.get("trade_frequency_per_month"),
        behav.get("overtrading_flag"),
    )

    # 7. Clustering
    clust = compute_clustering(closed_trades, enrichments)
    logger.info(
        "pipeline clustering: clusters=%d",
        len(clust.get("clusters", []) if isinstance(clust, dict) else []),
    )

    # 8. Persist analytics
    await db.execute(
        delete(AnalyticsResult).where(AnalyticsResult.portfolio_id == portfolio_id)
    )
    for atype, data in [
        ("performance", perf),
        ("risk", risk),
        ("behavioral", behav),
        ("clustering", clust),
    ]:
        db.add(
            AnalyticsResult(
                portfolio_id=portfolio_id, analysis_type=atype, result_data=data
            )
        )

    # 9. Insight (never fatal)
    try:
        insight_data = await generate_insight(perf, risk, behav, clust, closed_trades)
        await db.execute(delete(Insight).where(Insight.portfolio_id == portfolio_id))
        db.add(
            Insight(
                portfolio_id=portfolio_id,
                insight_text=insight_data.get("summary", ""),
                key_findings={
                    "findings": insight_data.get("findings", []),
                    "doing_well": insight_data.get("doing_well", ""),
                    "costing_money": insight_data.get("costing_money", ""),
                },
            )
        )
    except Exception:  # noqa: BLE001
        logger.exception("pipeline insight generation failed")

    await db.commit()
    logger.info(
        "pipeline done portfolio=%s in %.2fs",
        portfolio_id,
        time.perf_counter() - t0,
    )
