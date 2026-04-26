from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis import AnalyticsResult
from app.models.portfolio import Portfolio
from app.schemas.analytics import (
    AnalyzeResponse,
    BehavioralMetrics,
    ComparisonMetric,
    ClusteringMetrics,
    FullAnalyticsResponse,
    MetricDelta,
    PerformanceMetrics,
    ProgressResponse,
    RiskMetrics,
)
from app.services.pipeline import run_analytics_pipeline


router = APIRouter()


def _metric_delta(previous: float, current: float, better_when_lower: bool) -> MetricDelta:
    delta = round(current - previous, 1)
    if abs(delta) < 0.05:
        direction = "unchanged"
    elif better_when_lower:
        direction = "improved" if delta < 0 else "worsened"
    else:
        direction = "improved" if delta > 0 else "worsened"
    return MetricDelta(
        previous=round(previous, 1),
        current=round(current, 1),
        delta=delta,
        direction=direction,
    )


def _comparison_metric(
    key: str,
    label: str,
    unit: str,
    previous: float,
    current: float,
    better_when_lower: bool,
) -> ComparisonMetric:
    delta = _metric_delta(previous, current, better_when_lower)
    return ComparisonMetric(
        key=key,
        label=label,
        unit=unit,
        previous=delta.previous,
        current=delta.current,
        delta=delta.delta,
        direction=delta.direction,
    )


def _build_progress_summary(
    metrics: list[ComparisonMetric],
) -> str:
    improved = [m for m in metrics if m.direction == "improved"]
    worsened = [m for m in metrics if m.direction == "worsened"]

    if not improved and not worsened:
        return "No meaningful change versus your previous period across comparison metrics."

    improved_sorted = sorted(improved, key=lambda m: abs(m.delta), reverse=True)
    worsened_sorted = sorted(worsened, key=lambda m: abs(m.delta), reverse=True)

    parts: list[str] = []
    if improved_sorted:
        top = ", ".join(m.label for m in improved_sorted[:2])
        parts.append(f"Biggest improvements: {top}.")
    if worsened_sorted:
        top = ", ".join(m.label for m in worsened_sorted[:2])
        parts.append(f"Watchouts: {top} moved in the wrong direction.")
    return " ".join(parts)


@router.post("/portfolio/{portfolio_id}/analyze", response_model=AnalyzeResponse)
async def analyze_portfolio(portfolio_id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    portfolio = res.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    await run_analytics_pipeline(portfolio_id, db)
    return AnalyzeResponse(status="complete", portfolio_id=str(portfolio_id))


@router.get(
    "/portfolio/{portfolio_id}/analytics",
    response_model=FullAnalyticsResponse,
)
async def get_analytics(portfolio_id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(AnalyticsResult).where(AnalyticsResult.portfolio_id == portfolio_id)
    )
    rows = {r.analysis_type: r.result_data for r in res.scalars().all()}

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No analytics found. Run POST /analyze first.",
        )

    return FullAnalyticsResponse(
        performance=PerformanceMetrics(**(rows.get("performance") or {})),
        risk=RiskMetrics(**(rows.get("risk") or {})),
        behavioral=BehavioralMetrics(**(rows.get("behavioral") or {})),
        clustering=ClusteringMetrics(**(rows.get("clustering") or {})),
    )


@router.get(
    "/portfolio/{portfolio_id}/progress",
    response_model=ProgressResponse,
)
async def get_progress(
    portfolio_id: UUID,
    previous_portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    portfolio_res = await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    current_portfolio = portfolio_res.scalar_one_or_none()
    previous_res = await db.execute(
        select(Portfolio).where(Portfolio.id == previous_portfolio_id)
    )
    previous_portfolio = previous_res.scalar_one_or_none()
    if not current_portfolio or not previous_portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    async def fetch_rows(target_id: UUID) -> dict[str, dict]:
        res = await db.execute(
            select(AnalyticsResult).where(AnalyticsResult.portfolio_id == target_id)
        )
        rows = {r.analysis_type: r.result_data for r in res.scalars().all()}
        if not rows:
            await run_analytics_pipeline(target_id, db)
            rerun = await db.execute(
                select(AnalyticsResult).where(AnalyticsResult.portfolio_id == target_id)
            )
            rows = {r.analysis_type: r.result_data for r in rerun.scalars().all()}
        return rows

    current_rows = await fetch_rows(portfolio_id)
    previous_rows = await fetch_rows(previous_portfolio_id)
    current_behav = current_rows.get("behavioral") or {}
    previous_behav = previous_rows.get("behavioral") or {}

    current_gap = float(
        (current_behav.get("disposition_effect") or {}).get("avg_days_hold_losers", 0) or 0
    ) - float(
        (current_behav.get("disposition_effect") or {}).get("avg_days_hold_winners", 0) or 0
    )
    previous_gap = float(
        (previous_behav.get("disposition_effect") or {}).get("avg_days_hold_losers", 0) or 0
    ) - float(
        (previous_behav.get("disposition_effect") or {}).get("avg_days_hold_winners", 0) or 0
    )

    current_perf = current_rows.get("performance") or {}
    previous_perf = previous_rows.get("performance") or {}
    current_risk = current_rows.get("risk") or {}
    previous_risk = previous_rows.get("risk") or {}

    metrics = [
        _comparison_metric(
            key="total_return_pct",
            label="Total Return",
            unit="%",
            previous=float(previous_perf.get("total_return_pct", 0) or 0),
            current=float(current_perf.get("total_return_pct", 0) or 0),
            better_when_lower=False,
        ),
        _comparison_metric(
            key="sharpe_ratio",
            label="Sharpe Ratio",
            unit="",
            previous=float(previous_perf.get("sharpe_ratio", 0) or 0),
            current=float(current_perf.get("sharpe_ratio", 0) or 0),
            better_when_lower=False,
        ),
        _comparison_metric(
            key="win_rate_pct",
            label="Win Rate",
            unit="%",
            previous=float(previous_perf.get("win_rate_pct", 0) or 0),
            current=float(current_perf.get("win_rate_pct", 0) or 0),
            better_when_lower=False,
        ),
        _comparison_metric(
            key="max_drawdown_pct",
            label="Max Drawdown",
            unit="%",
            previous=float(previous_perf.get("max_drawdown_pct", 0) or 0),
            current=float(current_perf.get("max_drawdown_pct", 0) or 0),
            better_when_lower=True,
        ),
        _comparison_metric(
            key="avg_holding_days",
            label="Avg Holding Days",
            unit="d",
            previous=float(previous_behav.get("avg_holding_days", 0) or 0),
            current=float(current_behav.get("avg_holding_days", 0) or 0),
            better_when_lower=False,
        ),
        _comparison_metric(
            key="trade_frequency_per_month",
            label="Trades / Month",
            unit="",
            previous=float(previous_behav.get("trade_frequency_per_month", 0) or 0),
            current=float(current_behav.get("trade_frequency_per_month", 0) or 0),
            better_when_lower=True,
        ),
        _comparison_metric(
            key="losers_vs_winners_hold_gap",
            label="Losers-Winners Hold Gap",
            unit="d",
            previous=previous_gap,
            current=current_gap,
            better_when_lower=True,
        ),
        _comparison_metric(
            key="max_position_size_pct",
            label="Max Position Size",
            unit="%",
            previous=float(previous_behav.get("max_position_size_pct", 0) or 0),
            current=float(current_behav.get("max_position_size_pct", 0) or 0),
            better_when_lower=True,
        ),
        _comparison_metric(
            key="concentration_hhi",
            label="Concentration (HHI)",
            unit="",
            previous=float(previous_risk.get("concentration_hhi", 0) or 0),
            current=float(current_risk.get("concentration_hhi", 0) or 0),
            better_when_lower=True,
        ),
    ]

    summary = _build_progress_summary(metrics)

    return ProgressResponse(
        current_portfolio_id=str(portfolio_id),
        previous_portfolio_id=str(previous_portfolio_id),
        comparison_label=f"{previous_portfolio.name} -> {current_portfolio.name}",
        metrics=metrics,
        summary=summary,
    )
