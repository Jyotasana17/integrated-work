from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import event
import logging

from executor.configs.settings import settings

logger = logging.getLogger(__name__)

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# Build engine kwargs based on dialect
_engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# SQLite doesn't support pool_size / max_overflow / pool_timeout
if _is_sqlite:
    # `timeout` makes the driver wait (instead of failing immediately) when the
    # database file is briefly locked by another connection/process.
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
else:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_timeout"] = 30
    # Recycle connections and validate them before use so a restarted/!idle
    # Postgres connection never surfaces as a 500 on a user request.
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 1800

# Create the async engine
engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# ---------------------------------------------------------------------------
# SQLite concurrency hardening.
# Without WAL mode, SQLite serializes all access with a global write lock, so a
# second connection/process (e.g. the API plus its in-process worker pool, or
# two API instances) intermittently fails with "database is locked" /
# "attempt to write a readonly database". WAL allows concurrent readers with a
# writer and `busy_timeout` makes writers wait for the lock instead of erroring.
# NOTE: WAL does NOT make SQLite safe across separate hosts/containers — use
# PostgreSQL for any multi-instance deployment (see DATABASE_URL).
# ---------------------------------------------------------------------------
if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")  # 30s
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
        finally:
            cursor.close()

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Declarative base for models
Base = declarative_base()

async def get_db_session() -> AsyncSession:
    """Dependency for getting async database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
