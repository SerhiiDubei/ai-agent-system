"""Database layer — SQLAlchemy session + base + models.

Per N3 + N5 + N10 research:
- SQLAlchemy 2.0 declarative
- psycopg3 binary
- pgvector через pgvector-python
- Java will eventually own Flyway migrations (when integrated); for standalone — Python owns Alembic
"""

from ai_agent_system.db.base import Base
from ai_agent_system.db.session import async_session_factory, engine, get_session

__all__ = ["Base", "engine", "async_session_factory", "get_session"]
