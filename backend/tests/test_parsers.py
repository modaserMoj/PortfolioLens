from datetime import datetime

from app.parsers.base import parse_any


IBKR_SAMPLE = """Statement,Header,Field Name,Field Value
Statement,Data,BrokerName,Interactive Brokers

Trades,Header,DataDiscriminator,Asset Category,Currency,Symbol,Date/Time,Quantity,T. Price,C. Price,Proceeds,Comm/Fee,Basis,Realized P/L,MTM P/L,Code
Trades,Data,Order,Stocks,USD,AAPL,"2024-01-15 09:30:00",50,185.50,186.00,-9275.00,-1.00,9000.00,0.00,25.00,O
Trades,Data,Order,Stocks,USD,AAPL,"2024-02-10 10:15:00",-25,195.00,195.50,4875.00,-1.00,4637.50,236.50,12.50,O
Trades,Data,Order,Stocks,USD,MSFT,"2024-03-01 14:45:00",10,400.00,400.50,-4000.00,-0.75,3800.00,0.00,5.00,O
"""

WS_LEGACY_SAMPLE = """Date,Type,Ticker,Description,Quantity,Price,Amount,Currency,Account
2024-03-15,buy,AAPL,Apple Inc,10,175.50,-1755.00,USD,TFSA
2024-04-02,sell,AAPL,Apple Inc,10,182.30,1823.00,USD,TFSA
2024-04-05,dividend,AAPL,Apple Inc,0,0,2.40,USD,TFSA
"""

WS_MODERN_SAMPLE = """transaction_date,settlement_date,account_id,account_type,activity_type,activity_sub_type,direction,symbol,name,currency,quantity,unit_price,commission,net_cash_amount
2025-05-06,2025-05-06,HQ23BSZ06CAD,Non-registered,Trade,SELL,LONG,RBLX,Roblox Corporation (Class A),CAD,-10,98.04,0,980.42
2025-05-14,,HQ23BSZ06CAD,Non-registered,Interest,,,,,CAD,0.01,,,0.01
2025-07-03,,HQ23BSZ06CAD,Non-registered,Dividend,,,NVDA,NVIDIA Corp,CAD,0.08,,,0.08
2025-05-06,2025-05-06,HQ6QR23K2CAD,TFSA,Trade,BUY,LONG,AMD,Advanced Micro Devices Inc.,CAD,15,142.47,0,-2137.12
2025-08-13,2025-08-13,HQ6QR23K2CAD,TFSA,Trade,BUY,LONG,RR,Richtech Robotics Inc.,CAD,700,2.88,0.5,-2019.98
"""

QT_SAMPLE = """Transaction Date,Settlement Date,Action,Symbol,Description,Quantity,Price,Gross Amount,Commission,Net Amount,Currency,Account Type
2024-02-10,2024-02-14,Buy,AAPL - Apple Inc,Apple Inc,15,178.25,-2673.75,-4.95,-2678.70,USD,Margin
2024-03-05,2024-03-07,Sell,AAPL - Apple Inc,Apple Inc,15,190.00,2850.00,-4.95,2845.05,USD,Margin
2024-03-10,2024-03-12,Dividend,AAPL - Apple Inc,Apple Inc,0,0,5.25,0,5.25,USD,Margin
"""

CUSTOM_UNKNOWN_SAMPLE = """Trade Date,Stock,Side,Shares,Fill Price,Brokerage
2024-05-01,TSLA,BUY,12,172.30,1.50
2024-06-14,TSLA,sell,12,188.45,1.50
2024-07-01,NVDA,BUY,4,128.00,0
"""


def test_ibkr_multi_section_csv_is_parsed():
    trades, fmt = parse_any(IBKR_SAMPLE)
    assert fmt == "Interactive Brokers"
    assert len(trades) == 3

    first = trades[0]
    assert first["ticker"] == "AAPL"
    assert first["action"] == "BUY"
    assert first["quantity"] == 50
    assert first["price"] == 185.50
    assert first["fees"] == 1.00
    assert isinstance(first["trade_date"], datetime)
    assert trades[1]["action"] == "SELL"
    assert trades[1]["quantity"] == 25


def test_wealthsimple_legacy_headers_are_understood():
    trades, fmt = parse_any(WS_LEGACY_SAMPLE)
    assert "Wealthsimple" in fmt
    assert len(trades) == 2
    assert trades[0]["action"] == "BUY"
    assert trades[1]["action"] == "SELL"
    assert trades[0]["ticker"] == "AAPL"


def test_wealthsimple_modern_export_uses_activity_type_and_subtype():
    trades, fmt = parse_any(WS_MODERN_SAMPLE)
    assert fmt == "Wealthsimple"
    assert len(trades) == 3

    sell = trades[0]
    assert sell["ticker"] == "RBLX"
    assert sell["action"] == "SELL"
    assert sell["quantity"] == 10
    assert sell["price"] == 98.04
    assert sell["currency"] == "CAD"

    buy = trades[1]
    assert buy["ticker"] == "AMD"
    assert buy["action"] == "BUY"
    assert buy["quantity"] == 15
    assert buy["total_amount"] == 2137.12

    rr = trades[2]
    assert rr["ticker"] == "RR"
    assert rr["fees"] == 0.5


def test_questrade_sample_parses_with_symbol_normalization():
    trades, fmt = parse_any(QT_SAMPLE)
    assert fmt == "Questrade"
    assert len(trades) == 2
    assert trades[0]["ticker"] == "AAPL"
    assert trades[0]["action"] == "BUY"
    assert trades[0]["fees"] == 4.95
    assert trades[1]["action"] == "SELL"


def test_unknown_broker_with_plausible_synonyms_still_parses():
    """A broker we've never heard of, with a different column vocabulary.

    Columns used: Trade Date (->trade_date), Stock (->ticker), Side (->action),
    Shares (->quantity), Fill Price (->price), Brokerage (->fees). None of
    these are broker-specific and there's no hard-coded parser for them.
    """
    trades, fmt = parse_any(CUSTOM_UNKNOWN_SAMPLE)
    assert fmt == "Custom CSV"
    assert len(trades) == 3
    assert [t["ticker"] for t in trades] == ["TSLA", "TSLA", "NVDA"]
    assert [t["action"] for t in trades] == ["BUY", "SELL", "BUY"]
    assert trades[0]["quantity"] == 12
    assert trades[0]["price"] == 172.30
    assert trades[0]["fees"] == 1.50
