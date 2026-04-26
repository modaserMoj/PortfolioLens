from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"timeout": 30} if _is_sqlite else {},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):  # noqa: ANN001
        # Reduce write-lock failures in dev: allow readers during writes (WAL)
        # and wait for lock release instead of failing immediately.
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=30000;")
        cursor.close()


async def get_db():
    async with async_session() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Used for local dev when not running Alembic.

    Also applies a few tiny idempotent column adds so existing SQLite dev
    databases pick up new nullable columns without a manual wipe. In
    production this is Alembic's job.
    """
    from app.models import analysis as _a  # noqa: F401
    from app.models import portfolio as _p  # noqa: F401
    from sqlalchemy import text

    async with engine.begin() as conn:
        if _is_sqlite:
            # Re-assert pragmatic defaults on startup for existing files.
            await conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            await conn.exec_driver_sql("PRAGMA synchronous=NORMAL;")
            await conn.exec_driver_sql("PRAGMA busy_timeout=30000;")
        await conn.run_sync(Base.metadata.create_all)

        # Best-effort column adds for dev convenience.
        for stmt in (
            "ALTER TABLE enrichments ADD COLUMN yf_symbol VARCHAR(30)",
        ):
            try:
                await conn.execute(text(stmt))
            except Exception:  # noqa: BLE001 — column likely already exists
                pass
