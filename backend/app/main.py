from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analytics, insights, portfolio, upload
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # Create tables if they don't exist (local dev convenience).
    # In production, Alembic would own schema migrations.
    await init_db()
    logger.info("PortfolioLens API ready (env=%s)", settings.APP_ENV)
    yield


app = FastAPI(title="PortfolioLens API", version="1.0.0", lifespan=lifespan)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(portfolio.router, prefix="/api", tags=["portfolio"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
app.include_router(insights.router, prefix="/api", tags=["insights"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"service": "PortfolioLens API", "docs": "/docs", "health": "/api/health"}
