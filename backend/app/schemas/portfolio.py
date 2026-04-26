from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticker: str
    action: str
    quantity: float
    price: float
    total_amount: float
    fees: float
    currency: str
    trade_date: datetime
    cluster_id: int | None = None


class PortfolioOut(BaseModel):
    id: UUID
    name: str
    broker: str
    trade_count: int
    tickers: list[str]
    date_range: dict
    created_at: datetime


class UploadResponse(BaseModel):
    portfolio_id: UUID
    trade_count: int
    date_range: dict
    tickers_found: list[str]
    detected_format: str | None = None


class TradeListResponse(BaseModel):
    trades: list[TradeOut]
    total: int
    page: int
