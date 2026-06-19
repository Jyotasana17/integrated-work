from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
import logging

from executor.configs.settings import settings

logger = logging.getLogger(__name__)

# Build engine kwargs based on dialect
_engine_kwargs = {
    "echo": settings.DEBUG,
    "future": True,
}

# SQLite doesn't support pool_size / max_overflow / pool_timeout
if settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_size"] = 20
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_timeout"] = 30

# Create the async engine
if settings.DATABASE_URL.startswith("postgresql+asyncpg"):
    _engine_kwargs["connect_args"] = {
        "ssl": "require"
    }

engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs
)

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

