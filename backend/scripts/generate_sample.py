"""Generate a synthetic IBKR-format activity CSV for demo/testing.

Bakes in realistic behavioral patterns:
  * Tech overtrading (more trades in AAPL/MSFT/NVDA/GOOGL/AMZN).
  * Disposition effect (losers held longer than winners).
  * Some occasional big winners to create spread in returns.

Usage:
    python -m scripts.generate_sample                 # writes to ../frontend/public/sample_trades.csv
    python -m scripts.generate_sample path/to/out.csv # writes to a custom path
"""

from __future__ import annotations

import csv
import io
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path


random.seed(42)

TICKERS: dict[str, tuple[str, float, float]] = {
    "AAPL": ("Technology", 170, 195),
    "MSFT": ("Technology", 380, 430),
    "NVDA": ("Technology", 450, 850),
    "GOOGL": ("Technology", 130, 175),
    "AMZN": ("Technology", 145, 190),
    "JPM": ("Financials", 170, 210),
    "BAC": ("Financials", 30, 38),
    "V": ("Financials", 260, 290),
    "JNJ": ("Healthcare", 150, 170),
    "UNH": ("Healthcare", 480, 550),
    "PFE": ("Healthcare", 26, 32),
    "XOM": ("Energy", 100, 118),
    "CVX": ("Energy", 145, 165),
    "KO": ("Consumer Staples", 58, 65),
    "PG": ("Consumer Staples", 155, 170),
    "HD": ("Consumer Discretionary", 340, 390),
}
TECH_TICKERS = [t for t, v in TICKERS.items() if v[0] == "Technology"]


def generate(out) -> None:
    writer = csv.writer(out, lineterminator="\n")

    writer.writerow(
        [
            "Trades",
            "Header",
            "DataDiscriminator",
            "Asset Category",
            "Currency",
            "Symbol",
            "Date/Time",
            "Quantity",
            "T. Price",
            "C. Price",
            "Proceeds",
            "Comm/Fee",
            "Basis",
            "Realized P/L",
            "MTM P/L",
            "Code",
        ]
    )

    start = datetime(2024, 1, 2, 9, 30)
    holdings: dict[str, list[tuple[float, float, datetime]]] = {}
    trade_count = 0

    for day_offset in range(220):
        date = start + timedelta(days=day_offset)
        if date.weekday() >= 5:
            continue

        n_trades = random.choices([0, 1, 2, 3], weights=[0.25, 0.4, 0.25, 0.1])[0]

        for _ in range(n_trades):
            ticker = random.choice(list(TICKERS.keys()))
            # Tech overtrading bias
            if random.random() < 0.35:
                ticker = random.choice(TECH_TICKERS)
            _, low, high = TICKERS[ticker]

            price = round(random.uniform(low, high), 2)
            time_str = (
                f"{date.strftime('%Y-%m-%d')} "
                f"{random.randint(9, 15):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}"
            )

            if ticker in holdings and holdings[ticker] and random.random() < 0.45:
                # SELL candidate: FIFO
                qty, buy_price, buy_date = holdings[ticker][0]
                # Disposition effect: hold losers longer
                if price < buy_price and random.random() < 0.65:
                    continue  # refuse to take the loss today
                holdings[ticker].pop(0)
                proceeds = round(qty * price, 2)
                comm = round(random.uniform(0.5, 2.0), 2)
                basis = round(qty * buy_price, 2)
                rpnl = round(proceeds - basis - comm, 2)
                writer.writerow(
                    [
                        "Trades",
                        "Data",
                        "Order",
                        "Stocks",
                        "USD",
                        ticker,
                        time_str,
                        -qty,
                        price,
                        price,
                        proceeds,
                        -comm,
                        basis,
                        rpnl,
                        0,
                        "O",
                    ]
                )
                trade_count += 1
            else:
                # BUY
                qty = random.choice([5, 10, 15, 20, 25, 50, 100])
                proceeds = round(-qty * price, 2)
                comm = round(random.uniform(0.5, 2.0), 2)
                holdings.setdefault(ticker, []).append((qty, price, date))
                writer.writerow(
                    [
                        "Trades",
                        "Data",
                        "Order",
                        "Stocks",
                        "USD",
                        ticker,
                        time_str,
                        qty,
                        price,
                        price,
                        proceeds,
                        -comm,
                        0,
                        0,
                        0,
                        "O",
                    ]
                )
                trade_count += 1

    print(f"# Generated {trade_count} trades", file=sys.stderr)


def _default_output_path() -> Path:
    here = Path(__file__).resolve().parent
    # backend/scripts/ -> backend/ -> repo root/frontend/public/sample_trades.csv
    return here.parent.parent / "frontend" / "public" / "sample_trades.csv"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        out_path = Path(sys.argv[1])
    else:
        out_path = _default_output_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    generate(buf)
    out_path.write_text(buf.getvalue(), encoding="utf-8", newline="")
    print(f"Wrote {out_path}", file=sys.stderr)
