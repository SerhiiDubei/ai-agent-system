"""Pytest fixtures — shared across unit + integration tests.

Per N5 + N3 research:
- Testcontainers Postgres з pgvector image для integration tests
- VCR.py cassettes для LLM responses (no real LLM calls in CI default)
- httpx + respx для mocking external APIs (Firecrawl, OpenRouter)
"""

from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from ai_agent_system.db.base import Base
from ai_agent_system.main import app


# ── Postgres з pgvector — integration tests ─────────────
@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Spin up Postgres з pgvector once per test session."""
    with PostgresContainer("pgvector/pgvector:pg16") as pg:
        yield pg


@pytest.fixture(scope="session")
def postgres_url(postgres_container: PostgresContainer) -> str:
    """Async psycopg URL для test container."""
    raw = postgres_container.get_connection_url()
    # testcontainers повертає `postgresql+psycopg2://...` — конвертуємо до psycopg3 async
    return raw.replace("postgresql+psycopg2://", "postgresql+psycopg://")


@pytest_asyncio.fixture
async def db_engine(postgres_url: str):
    """Per-test engine. Creates schema, drops on teardown."""
    engine = create_async_engine(postgres_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Per-test session з rollback."""
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── FastAPI test client ──────────────────────────────────
@pytest.fixture
def client() -> TestClient:
    """Synchronous test client для quick endpoint tests."""
    return TestClient(app)


# ── Markers (configured у pyproject.toml) ────────────────
# pytest -m "not integration"      → unit only
# pytest -m "integration"          → integration only (slower)
# pytest -m "agent_quality"        → agent quality golden tests
# pytest -m "e2e"                  → real LLM, gated
