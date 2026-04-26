import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, BigInteger, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Enrichment(Base):
    __tablename__ = "enrichments"

    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    market_cap: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Canonical yfinance symbol (e.g. FLT -> FLT.V). None if unresolved.
    yf_symbol: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnalyticsResult(Base):
    __tablename__ = "analytics_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"))
    analysis_type: Mapped[str] = mapped_column(String(50))
    result_data: Mapped[dict] = mapped_column(JSON)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"))
    insight_text: Mapped[str] = mapped_column(Text)
    key_findings: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
