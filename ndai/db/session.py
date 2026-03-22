"""Database session management."""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ndai.config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI route handlers."""
    async with async_session() as session:
        yield session


@asynccontextmanager
async def get_db_context() -> AsyncSession:
    """Standalone async context manager for background tasks.

    Unlike get_db() (a FastAPI dependency generator), this can be used with
    ``async with get_db_context() as session:`` outside of request scope.
    """
    async with async_session() as session:
        yield session


async def dispose_engine():
    """Dispose the engine (for test cleanup)."""
    await engine.dispose()
