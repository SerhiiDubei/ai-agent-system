"""SQLAlchemy async session factory + engine.

Per N3 + N5 research:
- Async engine з asyncpg-style behavior через psycopg3 async
- Pool size + max_overflow tunable via env
- Session per-request via FastAPI Depends pattern
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ai_agent_system.config import settings

# psycopg3 async URL conversion (postgresql+psycopg → postgresql+psycopg_async)
# psycopg3 supports both sync і async з тим самим driver name when using AsyncEngine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    echo=settings.is_dev and settings.app_log_level == "DEBUG",
)


async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields scoped async session per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
