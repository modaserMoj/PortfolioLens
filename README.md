# PortfolioLens

AI-powered portfolio analytics. Upload a brokerage trade history CSV, get
FIFO-matched performance metrics, risk decomposition, behavioral analysis,
K-means trade clustering, and an AI-written narrative of your trading habits.

## Features

- **Multi-broker CSV parsers** — Interactive Brokers, Wealthsimple, Questrade
- **Performance** — Total/annualized return, Sharpe, Sortino, max drawdown, win rate, equity curve, monthly heatmap
- **Risk** — Sector exposure, HHI concentration, portfolio beta & alpha vs SPY, top-holdings correlation matrix
- **Behavioral** — Avg/median holding period, trade frequency, position sizing, day-of-week pattern, disposition effect
- **Clustering** — K-means (auto-k via silhouette) over (holding days, return, size, sector, day-of-week) with PCA 2D scatter
- **AI Insights** — GPT-4o-mini narrative + findings, **with automatic rule-based fallback when no API key is configured**

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async), pandas/numpy, scikit-learn, yfinance, OpenAI
- **Frontend:** React 18 + TypeScript, Vite, Tailwind CSS, Recharts, TanStack Query
- **DB:** SQLite (default, zero setup) — Postgres supported via `DATABASE_URL`

---

## Local Development — Windows (PowerShell)

Prerequisites: Python 3.11+ and Node.js 20+.

### 1. Backend

```powershell
cd portfoliolens\backend

# Create & activate venv
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install deps
pip install -r requirements.txt

# Optional: drop a .env file (the app runs fine without it)
copy .env.example .env

# Start the API (auto-creates SQLite tables on startup)
uvicorn app.main:app --reload --port 8000
```

API is now at `http://localhost:8000` (docs: `http://localhost:8000/docs`).

### 2. Frontend

Open a second terminal:

```powershell
cd portfoliolens\frontend
npm install
npm run dev
```

App is now at `http://localhost:5173`. The Vite dev server proxies `/api/*` to `localhost:8000`, so just open the page and start uploading.

### 3. Generate the sample CSV (one-time)

To populate the "Download sample" link on the upload page with a realistic
synthetic dataset:

```powershell
cd portfoliolens\backend
.venv\Scripts\Activate.ps1
python -m scripts.generate_sample > ..\frontend\public\sample_trades.csv
```

Then refresh the upload page and click "Download sample trade history".

---

## Running Tests

```powershell
cd portfoliolens\backend
.venv\Scripts\Activate.ps1
pytest -v
```

Tests cover parsers (IBKR/Wealthsimple/Questrade), analytics (performance,
behavioral, risk, clustering), and the full upload → analyze → analytics →
insights HTTP flow (external services mocked).

---

## Configuration (`.env`)

All values are optional; defaults work out of the box.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./portfoliolens.db` | Async SQLA URL |
| `OPENAI_API_KEY` | _(empty)_ | If set, insights use GPT-4o-mini. Otherwise a deterministic rule-based summarizer runs. |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated CORS whitelist |
| `RISK_FREE_RATE` | `0.05` | Used for Sharpe / Sortino / alpha |
| `BENCHMARK_TICKER` | `SPY` | Benchmark for beta/alpha |

### Switching to Postgres

```env
DATABASE_URL=postgresql+asyncpg://portfoliolens:portfoliolens@localhost:5432/portfoliolens
```

The app will `CREATE TABLE IF NOT EXISTS` on startup either way.

---

## Architecture

```
CSV upload
   │
   ▼
Parser (ibkr | wealthsimple | questrade)
   │
   ▼
DB (portfolios + trades)
   │
   ▼
Pipeline (POST /analyze)
   │
   ├── Enrichment    — yfinance sector / industry (7-day cache)
   ├── Prices        — yfinance daily close for SPY + tickers
   ├── Performance   — FIFO matching → Sharpe / drawdown / equity curve
   ├── Risk          — sector / HHI / beta / alpha / correlation
   ├── Behavioral    — holding time / frequency / disposition effect
   ├── Clustering    — K-means + PCA, auto-k via silhouette
   └── Summarizer    — OpenAI (or rule-based fallback)
   │
   ▼
DB (analytics_results + insights)
   │
   ▼
Frontend (Dashboard / Risk / Trades / Insights)
```

The key data flow is the `_closed_trades` pass-through: `performance.py`
computes FIFO-matched buy/sell pairs and hands them to `behavioral.py` and
`clustering.py` via `pipeline.py`.

---

## Project Layout

```
portfoliolens/
├── backend/
│   ├── app/
│   │   ├── api/routes/        upload.py, portfolio.py, analytics.py, insights.py
│   │   ├── analytics/         performance, risk, behavioral, clustering
│   │   ├── core/              config, database
│   │   ├── llm/               summarizer (OpenAI + rule-based)
│   │   ├── models/            portfolio, analysis (SQLAlchemy)
│   │   ├── parsers/           base, ibkr, wealthsimple, questrade
│   │   ├── schemas/           Pydantic request/response
│   │   ├── services/          enrichment, pipeline
│   │   └── main.py
│   ├── scripts/generate_sample.py
│   ├── tests/                 parsers, analytics, api
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.ts
│   │   ├── components/        Navbar, MetricCard, charts/*
│   │   ├── hooks/usePortfolio.ts
│   │   ├── pages/             Upload, Dashboard, Risk, Trades, Insights
│   │   └── types/index.ts
│   └── package.json
└── README.md
```

---

## Notes & Troubleshooting

- **yfinance rate limits.** yfinance occasionally returns empty frames or
  rate-limits. When that happens, `sector` falls back to "Unknown" and the
  beta/correlation computations use defaults — the pipeline does not fail.
- **First analyze is slow.** yfinance calls dominate the first run for a new
  ticker set; subsequent runs use the 7-day enrichment cache in the DB.
- **SQLite file.** The DB lives at `backend/portfoliolens.db`. Delete it to
  reset state.
- **No OpenAI key?** The rule-based summarizer produces deterministic, numeric
  insights; the UI looks identical.
