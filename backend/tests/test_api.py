from unittest.mock import patch

import pytest

from tests.test_parsers import IBKR_SAMPLE


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_upload_rejects_empty_csv(client):
    r = await client.post(
        "/api/upload",
        files={"file": ("empty.csv", b"not,a,trade\nthing,,\n", "text/csv")},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_upload_auto_detects_and_returns_format(client):
    r = await client.post(
        "/api/upload",
        files={"file": ("trades.csv", IBKR_SAMPLE.encode(), "text/csv")},
        data={"name": "AutoDetect"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trade_count"] == 3
    assert body["detected_format"] == "Interactive Brokers"


@pytest.mark.asyncio
async def test_full_pipeline(client):
    r = await client.post(
        "/api/upload",
        files={"file": ("trades.csv", IBKR_SAMPLE.encode(), "text/csv")},
        data={"name": "Test"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["trade_count"] == 3
    pid = data["portfolio_id"]

    r2 = await client.get(f"/api/portfolio/{pid}")
    assert r2.status_code == 200
    assert r2.json()["trade_count"] == 3

    r3 = await client.get(f"/api/portfolio/{pid}/trades")
    assert r3.status_code == 200
    assert r3.json()["total"] == 3

    async def fake_benchmark(*_a, **_kw):
        return None

    async def fake_ticker_prices(*_a, **_kw):
        return None

    async def fake_enrich(tickers, _db):
        enrichments = {
            t: {"sector": "Technology", "industry": "Tech", "market_cap": 0}
            for t in tickers
        }
        symbol_map = {t: t for t in tickers}
        return enrichments, symbol_map

    with patch("app.services.pipeline.enrich_tickers", fake_enrich), patch(
        "app.services.pipeline.get_benchmark_prices", fake_benchmark
    ), patch("app.services.pipeline.get_ticker_prices", fake_ticker_prices):
        r4 = await client.post(f"/api/portfolio/{pid}/analyze")
        assert r4.status_code == 200, r4.text
        assert r4.json()["status"] == "complete"

    r5 = await client.get(f"/api/portfolio/{pid}/analytics")
    assert r5.status_code == 200
    body = r5.json()
    for key in ("performance", "risk", "behavioral", "clustering"):
        assert key in body

    r6 = await client.get(f"/api/portfolio/{pid}/insights")
    assert r6.status_code == 200
    ins = r6.json()
    assert ins["summary"]
    assert isinstance(ins["key_findings"], list)
