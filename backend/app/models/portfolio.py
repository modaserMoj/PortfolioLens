import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Numeric, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    broker: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trades: Mapped[list["Trade"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    portfolio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("portfolios.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(10))  # "BUY" | "SELL"
    quantity: Mapped[float] = mapped_column(Numeric(16, 6))
    price: Mapped[float] = mapped_column(Numeric(16, 6))
    total_amount: Mapped[float] = mapped_column(Numeric(16, 2))
    fees: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    trade_date: Mapped[datetime] = mapped_column(DateTime)
    raw_data: Mapped[dict] = mapped_column(JSON, nullable=True)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="trades")
