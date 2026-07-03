"""Shared FastAPI dependencies — singletons для router/cost_sink/kill_switch."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_agent_system.config import settings
from ai_agent_system.db.session import async_session_factory, get_session
from ai_agent_system.llm.cost_sink import CostSink
from ai_agent_system.llm.kill_switch import KillSwitch
from ai_agent_system.llm.router import LlmRouter
from ai_agent_system.llm.routing_config import get_routing_config


async def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    """Validate X-Internal-Key header for service-to-service calls."""
    if x_internal_key != settings.internal_api_key.get_secret_value():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal key")


# Alias for consistent naming across routers
get_db = get_session


@lru_cache(maxsize=1)
def get_cost_sink() -> CostSink:
    return CostSink(async_session_factory)


@lru_cache(maxsize=1)
def get_kill_switch() -> KillSwitch:
    return KillSwitch(async_session_factory)


@lru_cache(maxsize=1)
def get_llm_router() -> LlmRouter:
    return LlmRouter(
        routing_config=get_routing_config(),
        cost_sink=get_cost_sink(),
        kill_switch=get_kill_switch(),
    )
