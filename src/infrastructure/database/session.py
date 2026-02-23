import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)

_global_engine: Optional[AsyncEngine] = None
_global_session_maker: Optional[async_sessionmaker] = None
_engine_lock = asyncio.Lock()


async def initialize_global_pool(database_url: Optional[str] = None) -> None:
    global _global_engine, _global_session_maker

    async with _engine_lock:
        if _global_engine is not None:
            logger.warning("Global database pool already initialized")
            return

        raw_url = database_url or settings.database_url
        if raw_url.startswith("postgresql://") and not raw_url.startswith(
            "postgresql+asyncpg://"
        ):
            db_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        else:
            db_url = raw_url

        _global_engine = create_async_engine(
            db_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=settings.db_pool_recycle,
            pool_timeout=settings.db_pool_timeout,
            echo=False,
        )

        _global_session_maker = async_sessionmaker(
            _global_engine, expire_on_commit=False, class_=AsyncSession
        )

        logger.info(
            "Global database pool initialized",
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            total_connections=settings.db_pool_size + settings.db_max_overflow,
        )


async def close_global_pool() -> None:
    global _global_engine, _global_session_maker

    async with _engine_lock:
        if _global_engine is None:
            logger.warning("Global database pool not initialized")
            return

        await _global_engine.dispose()
        _global_engine = None
        _global_session_maker = None

        logger.info("Global database pool closed")


def get_global_engine() -> AsyncEngine:
    if _global_engine is None:
        raise RuntimeError(
            "Global database pool not initialized. Call initialize_global_pool() first."
        )
    return _global_engine


def get_connection_from_pool() -> AsyncConnection:
    engine = get_global_engine()
    return engine.connect()


def get_global_session_maker() -> async_sessionmaker:
    if _global_session_maker is None:
        raise RuntimeError(
            "Global database pool not initialized. Call initialize_global_pool() first."
        )
    return _global_session_maker


def get_session_from_pool():
    session_maker = get_global_session_maker()
    return session_maker()


async def get_session_from_pool_dependency():
    async with get_session_from_pool() as session:
        yield session
