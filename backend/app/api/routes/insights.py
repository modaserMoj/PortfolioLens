from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.analysis import Insight
from app.schemas.analytics import InsightResponse


router = APIRouter()


@router.get(
    "/portfolio/{portfolio_id}/insights", response_model=InsightResponse
)
async def get_insights(portfolio_id: UUID, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Insight)
        .where(Insight.portfolio_id == portfolio_id)
        .order_by(Insight.generated_at.desc())
    )
    insight = res.scalars().first()
    if not insight:
        raise HTTPException(
            status_code=404,
            detail="No insights found. Run POST /analyze first.",
        )

    findings = insight.key_findings or {}
    return InsightResponse(
        summary="",
        key_findings=findings.get("findings", []),
        doing_well=findings.get("doing_well", ""),
        costing_money=findings.get("costing_money", ""),
        generated_at=insight.generated_at,
    )
