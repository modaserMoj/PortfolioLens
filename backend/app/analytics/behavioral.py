from collections import defaultdict
from typing import Any

import numpy as np


_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _empty() -> dict:
    return {
        "avg_holding_days": 0.0,
        "median_holding_days": 0.0,
        "trade_frequency_per_month": 0.0,
        "avg_position_size_pct": 0.0,
        "max_position_size_pct": 0.0,
        "overtrading_flag": False,
        "overtrading_detail": None,
        "day_of_week_distribution": {},
        "disposition_effect": {
            "avg_days_hold_winners": 0.0,
            "avg_days_hold_losers": 0.0,
            "flag": False,
        },
    }


def compute_behavioral(
    trades: list[dict[str, Any]], closed_trades: list[dict[str, Any]]
) -> dict:
    if not trades:
        return _empty()

    # Holding periods
    if closed_trades:
        hold_days = [ct["holding_days"] for ct in closed_trades]
        avg_hold = float(np.mean(hold_days))
        median_hold = float(np.median(hold_days))
    else:
        avg_hold = 0.0
        median_hold = 0.0

    # Trade frequency (per month)
    dates = sorted(
        {
            t["trade_date"].date() if hasattr(t["trade_date"], "date") else t["trade_date"]
            for t in trades
        }
    )
    if len(dates) >= 2:
        months = max((dates[-1] - dates[0]).days / 30.44, 1.0)
        freq = len(trades) / months
    else:
        freq = float(len(trades))

    # Position sizing (as % of total BUY capital)
    total_capital = sum(
        float(t["quantity"]) * float(t["price"]) for t in trades if t["action"] == "BUY"
    )
    position_sizes: list[float] = []
    if total_capital > 0:
        for t in trades:
            if t["action"] == "BUY":
                pct = (float(t["quantity"]) * float(t["price"])) / total_capital * 100.0
                position_sizes.append(pct)

    avg_pos = float(np.mean(position_sizes)) if position_sizes else 0.0
    max_pos = float(np.max(position_sizes)) if position_sizes else 0.0

    # Overtrading: high frequency AND sub-40% win rate
    if closed_trades:
        win_rate = sum(1 for ct in closed_trades if ct["pnl"] > 0) / len(closed_trades)
    else:
        win_rate = 0.0
    overtrading_flag = freq > 20 and win_rate < 0.4
    overtrading_detail = None
    if overtrading_flag:
        overtrading_detail = (
            f"Trading {freq:.1f} times/month with a {win_rate*100:.0f}% win rate — "
            "frequency is outrunning edge."
        )

    # Day-of-week distribution
    dow: dict[str, int] = defaultdict(int)
    for t in trades:
        d = t["trade_date"]
        if hasattr(d, "weekday"):
            dow[_DAYS[d.weekday()]] += 1

    # Disposition effect: winners vs losers holding time
    winners = [ct for ct in closed_trades if ct["pnl"] > 0]
    losers = [ct for ct in closed_trades if ct["pnl"] <= 0]
    avg_w = float(np.mean([w["holding_days"] for w in winners])) if winners else 0.0
    avg_l = float(np.mean([l["holding_days"] for l in losers])) if losers else 0.0
    disposition_flag = avg_l > avg_w * 1.5 and len(losers) > 3

    return {
        "avg_holding_days": round(avg_hold, 1),
        "median_holding_days": round(median_hold, 1),
        "trade_frequency_per_month": round(freq, 1),
        "avg_position_size_pct": round(avg_pos, 2),
        "max_position_size_pct": round(max_pos, 2),
        "overtrading_flag": bool(overtrading_flag),
        "overtrading_detail": overtrading_detail,
        "day_of_week_distribution": dict(dow),
        "disposition_effect": {
            "avg_days_hold_winners": round(avg_w, 1),
            "avg_days_hold_losers": round(avg_l, 1),
            "flag": bool(disposition_flag),
        },
    }
