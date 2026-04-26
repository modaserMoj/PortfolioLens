from datetime import datetime, timedelta

from app.analytics.behavioral import compute_behavioral
from app.analytics.clustering import compute_clustering
from app.analytics.performance import compute_performance
from app.analytics.risk import compute_risk


def _mk_trade(ticker, action, qty, price, date, fees=0.0):
    return {
        "ticker": ticker,
        "action": action,
        "quantity": qty,
        "price": price,
        "total_amount": qty * price,
        "fees": fees,
        "trade_date": date,
        "currency": "USD",
    }


def _sample_trades():
    base = datetime(2024, 1, 2, 10, 0)
    return [
        _mk_trade("AAPL", "BUY", 10, 150.0, base),
        _mk_trade("AAPL", "SELL", 10, 165.0, base + timedelta(days=10)),  # +$150
        _mk_trade("MSFT", "BUY", 5, 300.0, base + timedelta(days=3)),
        _mk_trade("MSFT", "SELL", 5, 290.0, base + timedelta(days=40)),  # -$50
        _mk_trade("NVDA", "BUY", 2, 500.0, base + timedelta(days=5)),
        _mk_trade("NVDA", "SELL", 2, 600.0, base + timedelta(days=20)),  # +$200
    ]


def test_performance_basic():
    perf = compute_performance(_sample_trades(), benchmark_prices=None, risk_free_rate=0.05)
    # Total capital = 10*150 + 5*300 + 2*500 = 1500 + 1500 + 1000 = 4000
    # PnL = 150 - 50 + 200 = 300 -> 300/4000 = 7.5%
    assert perf["total_trades_closed"] == 3
    assert perf["total_return_pct"] == 7.5
    assert perf["win_rate_pct"] == 66.7  # 2/3
    assert len(perf["equity_curve"]) > 0


def test_behavioral_winners_vs_losers():
    perf = compute_performance(_sample_trades(), None, 0.05)
    closed = perf["_closed_trades"]
    behav = compute_behavioral(_sample_trades(), closed)
    assert behav["disposition_effect"]["avg_days_hold_winners"] > 0
    # The loser (MSFT) is held 40 days, winners 10 and 15 days
    assert behav["disposition_effect"]["avg_days_hold_losers"] >= behav[
        "disposition_effect"
    ]["avg_days_hold_winners"]


def test_risk_sector_exposure_sums_to_one():
    trades = _sample_trades()
    enrichments = {
        "AAPL": {"sector": "Technology"},
        "MSFT": {"sector": "Technology"},
        "NVDA": {"sector": "Technology"},
    }
    risk = compute_risk(trades, enrichments, None, None)
    assert abs(sum(risk["sector_exposure"].values()) - 1.0) < 1e-6
    assert risk["sector_exposure"]["Technology"] == 1.0
    assert risk["top_holdings"][0]["ticker"] in ("AAPL", "MSFT", "NVDA")


def test_clustering_returns_empty_for_few_trades():
    # Only 3 closed trades — below threshold of 6
    perf = compute_performance(_sample_trades(), None, 0.05)
    closed = perf["_closed_trades"]
    cl = compute_clustering(closed, {})
    assert cl["n_clusters"] == 0
    assert cl["clusters"] == []


def test_clustering_works_with_enough_trades():
    base = datetime(2024, 1, 2, 10, 0)
    trades = []
    # 10 round trips
    for i in range(10):
        d = base + timedelta(days=i * 3)
        trades.append(_mk_trade("AAPL", "BUY", 10, 150 + i, d))
        trades.append(_mk_trade("AAPL", "SELL", 10, 150 + i + (i % 3), d + timedelta(days=2)))
    perf = compute_performance(trades, None, 0.05)
    closed = perf["_closed_trades"]
    cl = compute_clustering(closed, {"AAPL": {"sector": "Technology"}})
    assert cl["n_clusters"] >= 2
    assert len(cl["scatter_data"]) == len(closed)
