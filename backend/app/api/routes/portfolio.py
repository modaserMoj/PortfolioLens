from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.portfolio import Portfolio, Trade
from app.schemas.portfolio import PortfolioOut, TradeListResponse, TradeOut


router = APIRouter()


@router.get("/portfolio/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio(portfolio_id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    portfolio = res.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    trades_res = await db.execute(select(Trade).where(Trade.portfolio_id == portfolio_id))
    trades = trades_res.scalars().all()

    tickers = sorted({t.ticker for t in trades})
    dates = sorted(t.trade_date for t in trades)

    return PortfolioOut(
        id=portfolio.id,
        name=portfolio.name,
        broker=portfolio.broker,
        trade_count=len(trades),
        tickers=tickers,
        date_range=(
            {"start": dates[0].isoformat(), "end": dates[-1].isoformat()}
            if dates
            else {"start": "", "end": ""}
        ),
        created_at=portfolio.created_at,
    )


@router.get("/portfolio/{portfolio_id}/trades", response_model=TradeListResponse)
async def list_trades(
    portfolio_id: UUID,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    ticker: str | None = None,
    action: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Trade).where(Trade.portfolio_id == portfolio_id)
    count_query = select(func.count(Trade.id)).where(Trade.portfolio_id == portfolio_id)
    if ticker:
        query = query.where(Trade.ticker == ticker.upper())
        count_query = count_query.where(Trade.ticker == ticker.upper())
    if action:
        query = query.where(Trade.action == action.upper())
        count_query = count_query.where(Trade.action == action.upper())

    total = int((await db.execute(count_query)).scalar() or 0)
    query = (
        query.order_by(Trade.trade_date.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    trades = (await db.execute(query)).scalars().all()

    return TradeListResponse(
        trades=[
            TradeOut(
                id=t.id,
                ticker=t.ticker,
                action=t.action,
                quantity=float(t.quantity),
                price=float(t.price),
                total_amount=float(t.total_amount),
                fees=float(t.fees),
                currency=t.currency,
                trade_date=t.trade_date,
            )
            for t in trades
        ],
        total=total,
        page=page,
    )
