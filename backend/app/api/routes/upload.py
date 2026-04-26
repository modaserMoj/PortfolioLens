from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.portfolio import Portfolio, Trade
from app.parsers.base import parse_any
from app.schemas.portfolio import UploadResponse


router = APIRouter()
logger = get_logger(__name__)


@router.post("/upload", response_model=UploadResponse)
async def upload_portfolio(
    file: UploadFile = File(...),
    name: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
):
    auto_name = (
        (name or "").strip()
        or Path((file.filename or "My Portfolio")).stem.strip()
        or "My Portfolio"
    )
    raw = await file.read()
    logger.info(
        "upload received: filename=%s size=%d bytes name=%r",
        file.filename,
        len(raw),
        auto_name,
    )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
            logger.warning("upload %s: utf-8 decode failed, used latin-1", file.filename)
        except UnicodeDecodeError:
            logger.error("upload %s: could not decode as utf-8 or latin-1", file.filename)
            raise HTTPException(status_code=400, detail="File must be a text CSV.")

    try:
        trades_data, format_label = parse_any(text)
    except Exception as e:  # noqa: BLE001
        logger.exception("upload %s: parser crashed", file.filename)
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {e}")

    if not trades_data:
        logger.warning(
            "upload %s: parser returned 0 trades (detected format=%s)",
            file.filename,
            format_label,
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"No trades found in CSV (detected format: {format_label}). "
                "We could not identify BUY/SELL rows with ticker, quantity, "
                "price, and date columns."
            ),
        )

    portfolio = Portfolio(name=auto_name, broker=format_label)
    db.add(portfolio)
    await db.flush()

    trade_objects: list[Trade] = []
    skipped_bad_action = 0
    skipped_no_ticker = 0
    for t in trades_data:
        trade = Trade(
            portfolio_id=portfolio.id,
            ticker=(t["ticker"] or "").upper().strip(),
            action=(t["action"] or "").upper().strip(),
            quantity=abs(float(t["quantity"])),
            price=float(t["price"]),
            total_amount=float(t["total_amount"]),
            fees=float(t.get("fees", 0) or 0),
            currency=(t.get("currency") or "USD")[:3],
            trade_date=t["trade_date"],
            raw_data=t.get("raw"),
        )
        if not trade.ticker:
            skipped_no_ticker += 1
            continue
        if trade.action not in ("BUY", "SELL"):
            skipped_bad_action += 1
            continue
        trade_objects.append(trade)
        db.add(trade)

    if not trade_objects:
        logger.warning(
            "upload %s: 0 BUY/SELL rows after validation (format=%s, "
            "skipped_no_ticker=%d, skipped_bad_action=%d)",
            file.filename,
            format_label,
            skipped_no_ticker,
            skipped_bad_action,
        )
        raise HTTPException(
            status_code=400,
            detail="CSV parsed but produced no BUY/SELL rows.",
        )

    await db.commit()
    await db.refresh(portfolio)

    tickers = sorted({t.ticker for t in trade_objects})
    dates = sorted(t.trade_date for t in trade_objects)
    n_buys = sum(1 for t in trade_objects if t.action == "BUY")
    n_sells = sum(1 for t in trade_objects if t.action == "SELL")

    logger.info(
        "upload %s: portfolio=%s format=%s trades=%d (BUY=%d SELL=%d) "
        "tickers=%d range=%s..%s skipped_no_ticker=%d skipped_bad_action=%d",
        file.filename,
        portfolio.id,
        format_label,
        len(trade_objects),
        n_buys,
        n_sells,
        len(tickers),
        dates[0].date(),
        dates[-1].date(),
        skipped_no_ticker,
        skipped_bad_action,
    )

    # Surface the common "SELL with no prior BUY in this file" case early, so
    # the user isn't mystified when performance metrics later show as zero.
    sell_tickers = {t.ticker for t in trade_objects if t.action == "SELL"}
    buy_tickers = {t.ticker for t in trade_objects if t.action == "BUY"}
    orphan_sells = sorted(sell_tickers - buy_tickers)
    if orphan_sells:
        logger.warning(
            "upload %s: %d SELL ticker(s) have no prior BUY in this CSV: %s. "
            "FIFO matching will skip these, so performance metrics may be all "
            "zero. Re-export including earlier history to fix.",
            file.filename,
            len(orphan_sells),
            orphan_sells,
        )

    return UploadResponse(
        portfolio_id=portfolio.id,
        trade_count=len(trade_objects),
        date_range={
            "start": dates[0].isoformat(),
            "end": dates[-1].isoformat(),
        },
        tickers_found=tickers,
        detected_format=format_label,
    )
