from typing import Any

import numpy as np
import pandas as pd


def _extract_close_series(ticker_prices, ticker: str) -> pd.Series | None:
    """yfinance returns different shapes depending on single vs multi-ticker
    downloads. Normalize to a Close price Series or return None on failure."""
    try:
        if ticker_prices is None or len(ticker_prices) == 0:
            return None
        if isinstance(ticker_prices, pd.Series):
            return ticker_prices
        if isinstance(ticker_prices, pd.DataFrame):
            # Multi-index columns: (ticker, field)
            if isinstance(ticker_prices.columns, pd.MultiIndex):
                try:
                    return ticker_prices[ticker]["Close"]
                except Exception:
                    try:
                        return ticker_prices["Close"][ticker]
                    except Exception:
                        return None
            # Flat columns — probably single ticker
            if "Close" in ticker_prices.columns:
                return ticker_prices["Close"]
            if ticker in ticker_prices.columns:
                return ticker_prices[ticker]
        return None
    except Exception:
        return None


def compute_risk(
    trades: list[dict[str, Any]],
    enrichments: dict[str, dict],
    benchmark_prices: pd.Series | None,
    ticker_prices,
    risk_free_rate: float = 0.05,
) -> dict:
    # --- Sector exposure & top holdings ----------------------------------
    sector_capital: dict[str, float] = {}
    ticker_capital: dict[str, float] = {}
    total_capital = 0.0

    for t in trades:
        if t["action"] != "BUY":
            continue
        capital = float(t["quantity"]) * float(t["price"])
        sector = enrichments.get(t["ticker"], {}).get("sector") or "Unknown"
        sector_capital[sector] = sector_capital.get(sector, 0.0) + capital
        ticker_capital[t["ticker"]] = ticker_capital.get(t["ticker"], 0.0) + capital
        total_capital += capital

    sector_exposure = (
        {s: round(c / total_capital, 4) for s, c in sector_capital.items()}
        if total_capital > 0
        else {}
    )

    top_holdings = sorted(
        [
            {"ticker": k, "weight": round(v / total_capital, 4) if total_capital > 0 else 0.0}
            for k, v in ticker_capital.items()
        ],
        key=lambda x: x["weight"],
        reverse=True,
    )[:10]

    # HHI
    all_weights = (
        [v / total_capital for v in ticker_capital.values()] if total_capital > 0 else []
    )
    hhi = sum(w * w for w in all_weights) if all_weights else 0.0
    if hhi < 0.15:
        concentration_level = "low"
    elif hhi < 0.25:
        concentration_level = "moderate"
    else:
        concentration_level = "high"

    # --- Beta / Alpha ----------------------------------------------------
    beta = 1.0
    alpha = 0.0
    try:
        if benchmark_prices is not None and len(benchmark_prices) > 10:
            if isinstance(benchmark_prices, pd.DataFrame):
                bench_series = (
                    benchmark_prices["Close"]
                    if "Close" in benchmark_prices.columns
                    else benchmark_prices.iloc[:, 0]
                )
            else:
                bench_series = benchmark_prices
            bench_returns = bench_series.pct_change().dropna()
            bench_returns.index = pd.to_datetime(bench_returns.index)

            portfolio_returns = pd.Series(0.0, index=bench_returns.index)
            used_weight = 0.0
            for h in top_holdings:
                ticker = h["ticker"]
                w = h["weight"]
                t_close = _extract_close_series(ticker_prices, ticker)
                if t_close is None or len(t_close) < 5:
                    continue
                t_returns = t_close.pct_change().dropna()
                t_returns.index = pd.to_datetime(t_returns.index)
                common = portfolio_returns.index.intersection(t_returns.index)
                if len(common) == 0:
                    continue
                portfolio_returns.loc[common] = (
                    portfolio_returns.loc[common].values + t_returns.loc[common].values * w
                )
                used_weight += w

            common = portfolio_returns.index.intersection(bench_returns.index)
            if len(common) > 10 and used_weight > 0:
                X = bench_returns.loc[common].values.astype(float).flatten()
                Y = portfolio_returns.loc[common].values.astype(float).flatten()
                var_x = float(np.var(X))
                if var_x > 1e-12:
                    cov_xy = float(np.cov(Y, X, ddof=0)[0][1])
                    beta = cov_xy / var_x
                ann_port = float(np.mean(Y)) * 252
                ann_bench = float(np.mean(X)) * 252
                alpha = ann_port - (risk_free_rate + beta * (ann_bench - risk_free_rate))
    except Exception:
        beta = 1.0
        alpha = 0.0

    # --- Correlation matrix (top 5) --------------------------------------
    correlation_matrix = {"tickers": [], "matrix": []}
    try:
        top5 = [h["ticker"] for h in top_holdings[:5]]
        returns_df = pd.DataFrame()
        for ticker in top5:
            c = _extract_close_series(ticker_prices, ticker)
            if c is None or len(c) < 5:
                continue
            returns_df[ticker] = c.pct_change()
        returns_df = returns_df.dropna(how="all")
        if len(returns_df.columns) >= 2:
            corr = returns_df.corr()
            correlation_matrix = {
                "tickers": list(corr.columns),
                "matrix": [
                    [round(float(v) if pd.notna(v) else 0.0, 2) for v in row]
                    for row in corr.values
                ],
            }
    except Exception:
        pass

    return {
        "sector_exposure": sector_exposure,
        "concentration_hhi": round(hhi, 4),
        "concentration_level": concentration_level,
        "portfolio_beta": round(float(beta), 2),
        "alpha_annualized": round(float(alpha) * 100.0, 2),
        "top_holdings": top_holdings,
        "correlation_matrix": correlation_matrix,
    }
