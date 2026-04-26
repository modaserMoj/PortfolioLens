"""Broker-agnostic CSV trade parser.

We do not care which broker produced the file. We only care that, somewhere
in the CSV, there are columns that describe trades: a ticker, an action
(BUY/SELL), a quantity, a price, and a date. Everything else is either
optional (fees, currency, total amount) or noise.

Mapping CSV columns to our semantic fields is done in three stages:

1.  **Preprocess** multi-section CSVs (IBKR-style "Trades,Header,..." /
    "Trades,Data,..." layouts) by extracting only the trade section.

2.  **Synonym matching** — normalize column names (lowercase, strip
    non-alphanumerics) and match against a dictionary of known synonyms for
    each semantic field. This resolves ~99% of real-world broker exports.

3.  **LLM fallback** — when synonym matching leaves required fields unmapped
    and an OpenAI key is configured, send the header + a few sample rows to
    the model and ask it to produce the mapping JSON. This makes the parser
    work on arbitrary/unknown broker formats without code changes.

Action detection has its own strategy ladder because different brokers encode
direction differently:

* A single column named ``Action`` / ``Type`` / ``Side`` / ``Buy/Sell``.
* A split ``activity_type`` + ``activity_sub_type`` pair (Wealthsimple).
* The sign of the quantity column (IBKR: +50 means buy, −25 means sell).
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any

from app.core.logging import get_logger


logger = get_logger(__name__)

REQUIRED_FIELDS = ("ticker", "quantity", "price", "trade_date")

FIELD_SYNONYMS: dict[str, list[str]] = {
    "ticker": [
        "symbol",
        "ticker",
        "stock",
        "instrument",
        "security",
        "securitysymbol",
        "securityid",
    ],
    "quantity": [
        "quantity",
        "qty",
        "shares",
        "units",
        "filledquantity",
        "executedquantity",
        "sharequantity",
    ],
    "price": [
        "price",
        "unitprice",
        "tprice",
        "executionprice",
        "execprice",
        "fillprice",
        "tradeprice",
        "averageprice",
        "avgprice",
    ],
    "total_amount": [
        "amount",
        "grossamount",
        "netamount",
        "netcashamount",
        "proceeds",
        "total",
        "value",
        "notional",
        "tradevalue",
    ],
    "fees": [
        "commission",
        "commissions",
        "fee",
        "fees",
        "commfee",
        "brokerage",
    ],
    "currency": ["currency", "ccy", "curr"],
    "trade_date": [
        "tradedate",
        "transactiondate",
        "datetime",
        "executiondate",
        "date",
        "settlementdate",
    ],
    "action": ["action", "side", "buysell", "direction", "tradetype", "type"],
    "activity_type": ["activitytype", "eventtype", "transactiontype"],
    "activity_subtype": ["activitysubtype", "subtype"],
}

BUY_TOKENS = {"buy", "bought", "b", "purchase", "purchased"}
SELL_TOKENS = {"sell", "sold", "s", "sale"}


def _norm(col: str) -> str:
    return "".join(ch for ch in (col or "").lower() if ch.isalnum())


def _to_float(raw: Any, default: float = 0.0) -> float:
    if raw is None:
        return default
    s = str(raw).replace(",", "").replace("$", "").strip()
    if s == "" or s == "--":
        return default
    try:
        return float(s)
    except ValueError:
        return default


def _parse_date(raw: str) -> datetime:
    raw = (raw or "").strip().strip('"')
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d, %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(raw)


def _preprocess_sections(text: str) -> tuple[str, str | None]:
    """Extract a flat CSV from multi-section broker exports.

    IBKR Activity Statements embed multiple "tables" keyed by first column
    (``Statement``, ``Trades``, ``Open Positions``...). We grab just the
    ``Trades`` section and rewrite it as a normal CSV.

    Returns (flat_csv_text, detected_format_label_or_none).
    """
    if "Trades,Header," not in text[:8000]:
        return text, None

    header: list[str] | None = None
    rows: list[list[str]] = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if not row or len(row) < 2 or row[0] != "Trades":
            continue
        if row[1] == "Header":
            header = row[2:]
        elif row[1] == "Data" and header is not None:
            data = row[2:]
            if len(data) < len(header):
                data = data + [""] * (len(header) - len(data))
            rows.append(data[: len(header)])

    if not header or not rows:
        return text, None

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue(), "Interactive Brokers"


def _guess_format_label(headers_norm: set[str], text: str) -> str:
    if "Trades,Header," in text[:8000]:
        return "Interactive Brokers"
    if {"transactiondate", "activitytype", "activitysubtype"} <= headers_norm:
        return "Wealthsimple"
    if {"date", "type", "ticker"} <= headers_norm and "action" not in headers_norm:
        return "Wealthsimple (legacy)"
    if {"transactiondate", "action", "netamount"} <= headers_norm:
        return "Questrade"
    return "Custom CSV"


def _build_mapping(fieldnames: list[str]) -> dict[str, str]:
    """Map semantic field -> original column name via synonym matching."""
    norm_to_original = {_norm(f): f for f in fieldnames if f is not None}
    mapping: dict[str, str] = {}
    for sem, syns in FIELD_SYNONYMS.items():
        for syn in syns:
            if syn in norm_to_original:
                mapping[sem] = norm_to_original[syn]
                break
    return mapping


def _ai_repair_mapping(
    header: list[str], sample_rows: list[dict[str, Any]]
) -> dict[str, str]:
    """Ask an LLM to fill in missing semantic->column mappings."""
    try:
        from app.core.config import settings

        if not settings.OPENAI_API_KEY:
            return {}

        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        payload = {
            "columns": header,
            "sample_rows": sample_rows[:5],
        }
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You map columns in a stock-brokerage trade-history CSV "
                        "to a fixed schema. Reply with JSON only. Use the EXACT "
                        "column names from the input. Omit keys you cannot map. "
                        "Schema keys: ticker, quantity, price, total_amount, "
                        "fees, currency, trade_date, action, activity_type, "
                        "activity_subtype."
                    ),
                },
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=300,
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        return {k: v for k, v in data.items() if isinstance(v, str) and v in header}
    except Exception as e:  # noqa: BLE001
        logger.warning("AI mapping fallback failed: %s", e)
        return {}


def _extract_action(row: dict[str, Any], mapping: dict[str, str]) -> str | None:
    # Strategy 1 (most specific): activity_type + activity_subtype pair.
    # This handles Wealthsimple-style exports where `activity_type=Trade` +
    # `activity_sub_type=BUY/SELL` is the source of truth, and a separate
    # `direction` (LONG/SHORT) column would otherwise mislead us.
    if "activity_type" in mapping and "activity_subtype" in mapping:
        activity = str(row.get(mapping["activity_type"], "") or "").strip().lower()
        if activity and activity != "trade":
            return None
        sub = str(row.get(mapping["activity_subtype"], "") or "").strip().lower()
        if sub in BUY_TOKENS:
            return "BUY"
        if sub in SELL_TOKENS:
            return "SELL"
        return None

    # Strategy 2: a single action/type/side column with BUY/SELL values.
    if "action" in mapping:
        val = str(row.get(mapping["action"], "") or "").strip().lower()
        if val in BUY_TOKENS:
            return "BUY"
        if val in SELL_TOKENS:
            return "SELL"
        return None

    # Strategy 3 (last resort): infer from sign of quantity.
    if "quantity" in mapping:
        qty = _to_float(row.get(mapping["quantity"], ""))
        if qty > 0:
            return "BUY"
        if qty < 0:
            return "SELL"

    return None


def _extract_trade(
    row: dict[str, Any], mapping: dict[str, str]
) -> tuple[dict[str, Any] | None, str | None]:
    """Return (trade_dict, skip_reason). Reason is None on success."""
    ticker = str(row.get(mapping.get("ticker", ""), "") or "").strip()
    if not ticker:
        return None, "no_ticker"
    ticker = ticker.split(" - ")[0].strip().upper()
    if not ticker:
        return None, "no_ticker"

    action = _extract_action(row, mapping)
    if action not in ("BUY", "SELL"):
        return None, "non_trade_action"

    qty = abs(_to_float(row.get(mapping.get("quantity", ""), 0)))
    if qty == 0:
        return None, "zero_quantity"

    price = _to_float(row.get(mapping.get("price", ""), 0))
    total = abs(_to_float(row.get(mapping.get("total_amount", ""), 0)))
    if total == 0 and price > 0:
        total = qty * price

    fees = abs(_to_float(row.get(mapping.get("fees", ""), 0)))
    currency = str(row.get(mapping.get("currency", ""), "") or "USD").strip() or "USD"

    date_raw = str(row.get(mapping.get("trade_date", ""), "") or "").strip()
    if not date_raw:
        return None, "no_date"
    try:
        trade_date = _parse_date(date_raw)
    except Exception:
        return None, "bad_date"

    return {
        "ticker": ticker,
        "action": action,
        "quantity": qty,
        "price": price,
        "total_amount": total,
        "fees": fees,
        "currency": currency[:3] if len(currency) >= 3 else currency,
        "trade_date": trade_date,
        "raw": dict(row),
    }, None


class GenericCSVParser:
    """Extract trades from any broker-style flat CSV."""

    def parse(self, csv_text: str) -> tuple[list[dict[str, Any]], str]:
        """Return (trades, detected_format_label)."""
        flat_text, preprocess_label = _preprocess_sections(csv_text)

        reader = csv.DictReader(io.StringIO(flat_text))
        fieldnames = [f for f in (reader.fieldnames or []) if f is not None]
        rows = [dict(r) for r in reader]

        headers_norm = {_norm(f) for f in fieldnames}
        format_label = preprocess_label or _guess_format_label(headers_norm, csv_text)

        logger.info(
            "parse: format=%s rows=%d columns=%s",
            format_label,
            len(rows),
            fieldnames,
        )

        mapping = _build_mapping(fieldnames)

        missing = [f for f in REQUIRED_FIELDS if f not in mapping]
        has_action_route = (
            "action" in mapping
            or ("activity_type" in mapping and "activity_subtype" in mapping)
            or "quantity" in mapping
        )
        if missing or not has_action_route:
            logger.info(
                "parse: synonym mapping incomplete (missing=%s, has_action_route=%s) "
                "— invoking AI fallback",
                missing,
                has_action_route,
            )
            ai_mapping = _ai_repair_mapping(fieldnames, rows[:5])
            for k, v in ai_mapping.items():
                mapping.setdefault(k, v)

        logger.info("parse: semantic mapping resolved to %s", mapping)

        trades: list[dict[str, Any]] = []
        skip_counts: dict[str, int] = {}
        for row in rows:
            trade, reason = _extract_trade(row, mapping)
            if trade is not None:
                trades.append(trade)
            else:
                skip_counts[reason or "unknown"] = skip_counts.get(reason or "unknown", 0) + 1

        logger.info(
            "parse: extracted %d trade(s) from %d row(s); skip reasons=%s",
            len(trades),
            len(rows),
            skip_counts,
        )

        return trades, format_label
