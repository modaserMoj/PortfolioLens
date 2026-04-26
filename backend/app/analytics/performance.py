from collections import defaultdict, deque
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def _empty_performance() -> dict:
    return {
        "total_return_pct": 0.0,
        "annualized_return_pct": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "max_drawdown_pct": 0.0,
        "max_drawdown_start": "",
        "max_drawdown_end": "",
        "win_rate_pct": 0.0,
        "total_trades_closed": 0,
        "equity_curve": [],
        "monthly_returns": [],
        "_closed_trades": [],
    }


def compute_performance(
    trades: list[dict[str, Any]],
    benchmark_prices: pd.Series | None,
    risk_free_rate: float,
) -> dict:
    """FIFO trade matching + standard performance metrics.

    Returns a dict matching PerformanceMetrics with an extra `_closed_trades`
    key that downstream modules (behavioral, clustering) consume.
    """

    if not trades:
        return _empty_performance()

    # --- Step 1: FIFO matching of BUY/SELL pairs -------------------------
    closed_trades: list[dict[str, Any]] = []
    buy_queues: dict[str, deque] = defaultdict(deque)

    sorted_trades = sorted(trades, key=lambda t: t["trade_date"])

    for t in sorted_trades:
        ticker = t["ticker"]
        if t["action"] == "BUY":
            buy_queues[ticker].append(
                {
                    "quantity": float(t["quantity"]),
                    "price": float(t["price"]),
                    "date": t["trade_date"],
                    "fees": float(t.get("fees", 0)),
                }
            )
        elif t["action"] == "SELL":
            remaining = float(t["quantity"])
            sell_price = float(t["price"])
            sell_fees = float(t.get("fees", 0))
            sell_qty_total = max(remaining, 1e-9)
            while remaining > 1e-9 and buy_queues[ticker]:
                buy = buy_queues[ticker][0]
                matched = min(remaining, buy["quantity"])
                # Allocate fees proportionally
                fee_alloc = sell_fees * (matched / sell_qty_total)
                pnl = matched * (sell_price - buy["price"]) - fee_alloc
                return_pct = (
                    (sell_price - buy["price"]) / buy["price"] * 100.0
                    if buy["price"] > 0
                    else 0.0
                )
                closed_trades.append(
                    {
                        "ticker": ticker,
                        "buy_date": buy["date"],
                        "sell_date": t["trade_date"],
                        "quantity": matched,
                        "buy_price": buy["price"],
                        "sell_price": sell_price,
                        "pnl": pnl,
                        "return_pct": return_pct,
                        "holding_days": max(
                            (t["trade_date"] - buy["date"]).days, 0
                        ),
                    }
                )
                buy["quantity"] -= matched
                remaining -= matched
                if buy["quantity"] <= 1e-9:
                    buy_queues[ticker].popleft()

    if not closed_trades:
        out = _empty_performance()
        out["_closed_trades"] = []
        return out

    # --- Step 2: Aggregate metrics ---------------------------------------
    total_capital = sum(ct["quantity"] * ct["buy_price"] for ct in closed_trades)
    total_pnl = sum(ct["pnl"] for ct in closed_trades)
    total_return_pct = (total_pnl / total_capital) * 100.0 if total_capital > 0 else 0.0

    all_dates = [ct["buy_date"] for ct in closed_trades] + [
        ct["sell_date"] for ct in closed_trades
    ]
    start_date = min(all_dates)
    end_date = max(all_dates)
    years = max((end_date - start_date).days / 365.25, 1 / 365.25)

    # Geometric annualization
    try:
        if 1 + total_return_pct / 100.0 > 0:
            ann_return = ((1 + total_return_pct / 100.0) ** (1 / years) - 1) * 100.0
        else:
            ann_return = -100.0
    except Exception:
        ann_return = 0.0

    # Daily realized PnL series on business days
    daily_pnl: dict[Any, float] = defaultdict(float)
    for ct in closed_trades:
        d = ct["sell_date"].date() if hasattr(ct["sell_date"], "date") else ct["sell_date"]
        daily_pnl[d] += ct["pnl"]

    date_range = pd.date_range(start=start_date, end=end_date, freq="B")
    if len(date_range) == 0:
        date_range = pd.date_range(start=start_date, end=start_date, freq="D")

    daily_returns = pd.Series(0.0, index=date_range)
    for d, pnl in daily_pnl.items():
        ts = pd.Timestamp(d)
        if ts in daily_returns.index:
            daily_returns.loc[ts] = pnl / total_capital if total_capital > 0 else 0.0
        else:
            # Snap to the nearest available business day
            nearest = daily_returns.index.asof(ts)
            if pd.notna(nearest):
                daily_returns.loc[nearest] += (
                    pnl / total_capital if total_capital > 0 else 0.0
                )

    # Sharpe
    daily_rf = risk_free_rate / 252.0
    excess = daily_returns - daily_rf
    std = float(excess.std())
    sharpe = (float(excess.mean()) / std) * np.sqrt(252) if std > 0 else 0.0

    # Sortino (downside deviation)
    downside = daily_returns[daily_returns < 0]
    d_std = float(downside.std()) if len(downside) > 1 else 0.0
    sortino = (
        (float(daily_returns.mean()) - daily_rf) / d_std * np.sqrt(252)
        if d_std > 0
        else 0.0
    )

    # Max drawdown
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    if drawdown.notna().any() and drawdown.min() < 0:
        max_dd = float(drawdown.min()) * 100.0
        max_dd_end = drawdown.idxmin()
        prior = cumulative.loc[:max_dd_end]
        max_dd_start = prior.idxmax() if len(prior) > 0 else max_dd_end
    else:
        max_dd = 0.0
        max_dd_end = end_date
        max_dd_start = start_date

    # Win rate
    winners = [ct for ct in closed_trades if ct["pnl"] > 0]
    win_rate = len(winners) / len(closed_trades) * 100.0

    # Equity curve starting at total_capital
    equity_curve = []
    running = 0.0
    for d in date_range:
        running += daily_pnl.get(d.date(), 0.0)
        equity_curve.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "value": round(total_capital + running, 2),
            }
        )

    # Monthly returns (percentage points)
    monthly = daily_returns.resample("ME").sum() * 100.0
    monthly_returns = [
        {"year": int(idx.year), "month": int(idx.month), "return_pct": round(float(val), 2)}
        for idx, val in monthly.items()
    ]

    def _fmt_date(d) -> str:
        if hasattr(d, "date"):
            return str(d.date())
        return str(d)

    return {
        "total_return_pct": round(total_return_pct, 2),
        "annualized_return_pct": round(ann_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(abs(max_dd), 2),
        "max_drawdown_start": _fmt_date(max_dd_start),
        "max_drawdown_end": _fmt_date(max_dd_end),
        "win_rate_pct": round(win_rate, 1),
        "total_trades_closed": len(closed_trades),
        "equity_curve": equity_curve,
        "monthly_returns": monthly_returns,
        "_closed_trades": closed_trades,
    }
