"""LLM-powered insight summarizer.

If OPENAI_API_KEY is missing we transparently fall back to a rule-based
summarizer so the whole pipeline still produces useful output for local
development without an API key.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_DEBUG_LOG = Path(__file__).resolve().parents[2] / "tmp" / "brave_debug_log.json"


SYSTEM_PROMPT = (
    "You are a portfolio analyst writing candid, specific assessments of "
    "retail investors' trading behavior. Reference actual numbers. Don't be "
    "generic. Be direct, actionable, and keep each finding under 2 sentences."
)


def _build_user_prompt(
    performance: dict,
    risk: dict,
    behavioral: dict,
    clustering: dict,
    closed_trades: list[dict[str, Any]],
) -> str:
    compact_trades = [
        {
            "ticker": t.get("ticker"),
            "buy_date": str(t.get("buy_date")),
            "sell_date": str(t.get("sell_date")),
            "return_pct": round(float(t.get("return_pct", 0) or 0), 2),
            "holding_days": int(float(t.get("holding_days", 0) or 0)),
        }
        for t in closed_trades[:50]
    ]
    return f"""Analyze this retail investor's trading history and provide a candid assessment.

PERFORMANCE METRICS:
- Total Return: {performance.get('total_return_pct', 0)}%
- Annualized Return: {performance.get('annualized_return_pct', 0)}%
- Sharpe Ratio: {performance.get('sharpe_ratio', 0)}
- Sortino Ratio: {performance.get('sortino_ratio', 0)}
- Max Drawdown: {performance.get('max_drawdown_pct', 0)}%
- Win Rate: {performance.get('win_rate_pct', 0)}%
- Total Closed Trades: {performance.get('total_trades_closed', 0)}

RISK PROFILE:
- Sector Exposure: {json.dumps(risk.get('sector_exposure', {}))}
- Concentration (HHI): {risk.get('concentration_hhi', 0)} ({risk.get('concentration_level', 'unknown')})
- Portfolio Beta: {risk.get('portfolio_beta', 0)}
- Alpha: {risk.get('alpha_annualized', 0)}%
- Top Holdings: {json.dumps(risk.get('top_holdings', [])[:5])}

BEHAVIORAL ANALYSIS:
- Avg Holding Period: {behavioral.get('avg_holding_days', 0)} days
- Trade Frequency: {behavioral.get('trade_frequency_per_month', 0)} trades/month
- Max Position Size: {behavioral.get('max_position_size_pct', 0)}%
- Overtrading: {behavioral.get('overtrading_flag', False)}
- Disposition Effect: Holds winners {behavioral.get('disposition_effect', {}).get('avg_days_hold_winners', 0)} days vs losers {behavioral.get('disposition_effect', {}).get('avg_days_hold_losers', 0)} days

TRADE CLUSTERS:
{json.dumps(clustering.get('clusters', []), indent=2)}

RECENT CLOSED TRADES:
{json.dumps(compact_trades, indent=2)}

Respond in this exact JSON format:
{{
  "summary": "",
  "findings": [
    "Ticker/date example where they likely sold too early + what signal could have helped",
    "Ticker/date example where they held a loser too long + what risk control could have helped",
    "Ticker/date example of poor entry timing + what setup confirmation could have helped"
  ],
  "doing_well": "",
  "costing_money": ""
}}"""


def _fmt_date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _pick_trade_instances(
    closed_trades: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    if not closed_trades:
        return None, None, None

    winners = [t for t in closed_trades if float(t.get("return_pct", 0) or 0) > 0]
    losers = [t for t in closed_trades if float(t.get("return_pct", 0) or 0) < 0]
    short_losers = [
        t
        for t in losers
        if int(float(t.get("holding_days", 0) or 0)) <= 7
    ]

    early_sell = None
    if winners:
        early_sell = sorted(
            winners,
            key=lambda t: (float(t.get("return_pct", 0) or 0), int(float(t.get("holding_days", 0) or 0))),
        )[0]

    late_loser = None
    if losers:
        late_loser = sorted(
            losers,
            key=lambda t: (int(float(t.get("holding_days", 0) or 0)), -float(t.get("return_pct", 0) or 0)),
            reverse=True,
        )[0]

    bad_entry = None
    if short_losers:
        bad_entry = sorted(
            short_losers,
            key=lambda t: float(t.get("return_pct", 0) or 0),
        )[0]
    elif losers:
        bad_entry = sorted(losers, key=lambda t: float(t.get("return_pct", 0) or 0))[0]

    return early_sell, late_loser, bad_entry


async def _fetch_brave_event(trade: dict[str, Any], scenario: str) -> dict[str, str] | None:
    if not settings.BRAVE_API_KEY:
        return None

    ticker = str(trade.get("ticker") or "").upper()
    anchor_date = _fmt_date(trade.get("buy_date"))
    if scenario == "late_loser":
        anchor_date = _fmt_date(trade.get("sell_date"))
    query = (
        f"{ticker} earnings OR lawsuit OR guidance OR downgrade OR investigation "
        f"around {anchor_date}"
    )
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": settings.BRAVE_API_KEY,
    }
    params = {"q": query, "count": 8, "search_lang": "en"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(BRAVE_SEARCH_URL, headers=headers, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("Brave search failed for %s (%s)", ticker, e)
        return None

    # TEMP DEBUG: persist Brave raw responses so we can inspect relevance/ranking
    # behavior on the next runs.
    try:
        BRAVE_DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing: list[dict[str, Any]] = []
        if BRAVE_DEBUG_LOG.exists():
            existing = json.loads(BRAVE_DEBUG_LOG.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        existing.append(
            {
                "logged_at": datetime.utcnow().isoformat(),
                "scenario": scenario,
                "ticker": ticker,
                "anchor_date": anchor_date,
                "query": query,
                "payload": payload,
            }
        )
        BRAVE_DEBUG_LOG.write_text(
            json.dumps(existing, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to write Brave debug log (%s)", e)

    candidates = (payload.get("web") or {}).get("results") or []
    if not candidates:
        return None

    for item in candidates:
        title = str(item.get("title") or "").strip()
        desc = str(item.get("description") or "").strip()
        url = str(item.get("url") or "").strip()
        if not title or not url:
            continue
        text = f"{title} {desc}".lower()
        if ticker.lower() not in text:
            continue
        if not any(
            keyword in text
            for keyword in [
                "earnings",
                "guidance",
                "lawsuit",
                "investigation",
                "downgrade",
                "regulator",
                "antitrust",
                "sec",
            ]
        ):
            continue
        return {"title": title, "description": desc, "url": url}
    return None


async def _event_confidence(
    trade: dict[str, Any], scenario: str, event: dict[str, str]
) -> str:
    if not settings.OPENAI_API_KEY:
        # Heuristic fallback when LLM unavailable.
        return "medium" if event.get("title") else "low"
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        prompt = (
            "Rate whether this event is relevant to this trade decision. "
            "Return JSON: {\"confidence\":\"low|medium|high\",\"reason\":\"...\"}.\n"
            f"Scenario: {scenario}\n"
            f"Trade: ticker={trade.get('ticker')}, buy={_fmt_date(trade.get('buy_date'))}, "
            f"sell={_fmt_date(trade.get('sell_date'))}, return={trade.get('return_pct')}, "
            f"holding_days={trade.get('holding_days')}\n"
            f"Event title: {event.get('title')}\n"
            f"Event snippet: {event.get('description')}\n"
            f"Event url: {event.get('url')}"
        )
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You evaluate news relevance for trading decisions."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=120,
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        conf = str(parsed.get("confidence") or "low").lower()
        return conf if conf in {"low", "medium", "high"} else "low"
    except Exception as e:  # noqa: BLE001
        logger.warning("Event confidence scoring failed (%s)", e)
        return "low"


async def _build_coaching_instances(closed_trades: list[dict[str, Any]]) -> list[str]:
    early_sell, late_loser, bad_entry = _pick_trade_instances(closed_trades)
    if not any([early_sell, late_loser, bad_entry]):
        return []

    scenarios: list[tuple[str, dict[str, Any] | None]] = [
        ("early_sell", early_sell),
        ("late_loser", late_loser),
        ("bad_entry", bad_entry),
    ]
    insights: list[str] = []

    for scenario, trade in scenarios:
        if not trade:
            continue
        event = await _fetch_brave_event(trade, scenario)
        confidence = "low"
        if event:
            confidence = await _event_confidence(trade, scenario, event)

        if scenario == "early_sell":
            base = (
                f"{trade.get('ticker')} ({_fmt_date(trade.get('buy_date'))} -> {_fmt_date(trade.get('sell_date'))}) "
                f"closed at +{float(trade.get('return_pct', 0) or 0):.1f}% after "
                f"{int(float(trade.get('holding_days', 0) or 0))}d, likely taking profit too early."
            )
            if event and confidence in {"medium", "high"}:
                insights.append(
                    f"{base} Around that time, news to watch was: \"{event.get('title')}\". "
                    "Because this was a major update, waiting for market reaction after the announcement may have helped timing."
                )
            else:
                insights.append(
                    f"{base} No medium-confidence event signal was found for that date window, "
                    "so using a simple rule (hold while price trend remains stable) could have helped."
                )
        elif scenario == "late_loser":
            base = (
                f"{trade.get('ticker')} ({_fmt_date(trade.get('buy_date'))} -> {_fmt_date(trade.get('sell_date'))}) "
                f"ended at {float(trade.get('return_pct', 0) or 0):.1f}% after "
                f"{int(float(trade.get('holding_days', 0) or 0))}d, suggesting a late loss exit."
            )
            if event and confidence in {"medium", "high"}:
                insights.append(
                    f"{base} A relevant warning around then was: \"{event.get('title')}\". "
                    "That kind of headline can raise downside risk, so reducing size or exiting earlier would have been safer."
                )
            else:
                insights.append(
                    f"{base} No medium-confidence event signal was found for that date window, "
                    "so a predefined max-loss rule could have limited damage earlier."
                )
        else:
            base = (
                f"{trade.get('ticker')} entry on {_fmt_date(trade.get('buy_date'))} reversed to "
                f"{float(trade.get('return_pct', 0) or 0):.1f}% in "
                f"{int(float(trade.get('holding_days', 0) or 0))}d, pointing to weak entry timing."
            )
            if event and confidence in {"medium", "high"}:
                insights.append(
                    f"{base} One event in that window was: \"{event.get('title')}\". "
                    "Waiting until after that event was resolved could have reduced uncertainty before entry."
                )
            else:
                insights.append(
                    f"{base} No medium-confidence event signal was found for that date window, "
                    "so waiting for price to stabilize before entering could have improved timing."
                )

    return insights[:3]


def _rule_based_insight(
    performance: dict,
    risk: dict,
    behavioral: dict,
    clustering: dict,
    closed_trades: list[dict[str, Any]],
) -> dict[str, Any]:
    """Deterministic, number-referencing summary used when no API key is set."""

    total_ret = performance.get("total_return_pct", 0)
    ann = performance.get("annualized_return_pct", 0)
    sharpe = performance.get("sharpe_ratio", 0)
    win = performance.get("win_rate_pct", 0)
    dd = performance.get("max_drawdown_pct", 0)
    n_closed = performance.get("total_trades_closed", 0)

    conc = risk.get("concentration_hhi", 0)
    conc_level = risk.get("concentration_level", "unknown")
    sectors = risk.get("sector_exposure", {})
    top_sector = (
        max(sectors, key=sectors.get) if sectors else "—"
    )
    top_sector_pct = round((sectors.get(top_sector, 0) * 100), 1) if sectors else 0
    beta = risk.get("portfolio_beta", 0)
    alpha = risk.get("alpha_annualized", 0)

    freq = behavioral.get("trade_frequency_per_month", 0)
    max_pos = behavioral.get("max_position_size_pct", 0)
    disp = behavioral.get("disposition_effect", {}) or {}
    avg_w = disp.get("avg_days_hold_winners", 0)
    avg_l = disp.get("avg_days_hold_losers", 0)

    findings = [
        "Generating concrete trade-level coaching requires either event-backed lookup or AI summarization. Enable AI and regenerate insights.",
        "Generating concrete trade-level coaching requires either event-backed lookup or AI summarization. Enable AI and regenerate insights.",
        "Generating concrete trade-level coaching requires either event-backed lookup or AI summarization. Enable AI and regenerate insights.",
    ]

    if alpha > 0 and win >= 50:
        doing_well = (
            f"Generating {alpha:+.1f}% alpha with a {win:.0f}% win rate shows "
            "selection skill, not just market exposure."
        )
    elif sharpe >= 1:
        doing_well = (
            f"Sharpe of {sharpe:.2f} indicates returns are well-calibrated "
            "to the risk taken."
        )
    else:
        doing_well = (
            f"Discipline around position sizing (max {max_pos:.1f}%) keeps any "
            "one trade from blowing up the book."
        )

    if disp.get("flag"):
        costing_money = (
            f"Riding losers for {avg_l:.0f} days vs winners for {avg_w:.0f} "
            "days inverts the 'cut losses, let winners run' rule — the single "
            "most fixable leak."
        )
    elif dd > 15:
        costing_money = (
            f"A -{dd:.1f}% drawdown ate into returns; tighter stops or smaller "
            "sizing during losing streaks would mechanically limit damage."
        )
    elif alpha < 0:
        costing_money = (
            f"{alpha:+.1f}% alpha vs SPY means active picks are lagging a "
            "passive ETF — consider simply buying the index for the core book."
        )
    else:
        costing_money = (
            f"Trading {freq:.1f}x/month generates friction (fees + slippage) "
            "that compounds against returns over time."
        )

    return {
        "summary": "",
        "findings": findings,
        "doing_well": doing_well,
        "costing_money": costing_money,
    }


async def generate_insight(
    performance: dict,
    risk: dict,
    behavioral: dict,
    clustering: dict,
    closed_trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Primary entry point. Uses OpenAI if configured, else rule-based."""

    closed_trades = closed_trades or []
    findings = await _build_coaching_instances(closed_trades)
    if not settings.OPENAI_API_KEY:
        out = _rule_based_insight(
            performance, risk, behavioral, clustering, closed_trades
        )
        out["findings"] = findings
        return out

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        user_prompt = _build_user_prompt(
            performance, risk, behavioral, clustering, closed_trades
        )
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=1000,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        # Force Insights page shape: no summary paragraph, event-grounded findings only.
        parsed["summary"] = ""
        parsed["findings"] = findings
        return parsed
    except Exception as e:  # noqa: BLE001
        logger.warning("OpenAI call failed (%s); falling back to rule-based", e)
        out = _rule_based_insight(
            performance, risk, behavioral, clustering, closed_trades
        )
        out["findings"] = findings
        return out
