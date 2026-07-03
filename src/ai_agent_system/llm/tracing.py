"""LangSmith tracing integration.

Per N10 research:
- One-line: wrap_openai(AsyncOpenAI(...)) — auto-instruments всі calls
- get_trace_id() з current run tree — link to Postgres llm_calls.trace_id
- Logfire alternative recorded in PARKING_LOT (cheaper at scale)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ai_agent_system.config import settings

if TYPE_CHECKING:
    from openai import AsyncOpenAI

log = logging.getLogger(__name__)


def wrap_with_langsmith(client: "AsyncOpenAI") -> "AsyncOpenAI":
    """Wrap OpenAI client з LangSmith auto-instrumentation якщо enabled.

    Returns wrapped client (or original якщо disabled).
    Per N10: this is THE one-line setup.
    """
    if not settings.langsmith_tracing:
        log.info("LangSmith tracing disabled (LANGSMITH_TRACING=false)")
        return client

    api_key = settings.langsmith_api_key.get_secret_value()
    if not api_key:
        log.warning("LANGSMITH_TRACING=true but LANGSMITH_API_KEY empty — disabling")
        return client

    try:
        from langsmith.wrappers import wrap_openai
    except ImportError:
        log.warning("langsmith not installed — tracing disabled")
        return client

    wrapped = wrap_openai(client)
    log.info(
        "LangSmith tracing enabled (project=%s, sampling=%.2f)",
        settings.langsmith_project,
        settings.langsmith_sampling_rate,
    )
    return wrapped


def get_current_trace_id() -> str | None:
    """Return LangSmith trace_id для linkage у llm_calls.trace_id.

    Returns None якщо no active LangSmith run (or langsmith not installed).
    """
    if not settings.langsmith_tracing:
        return None

    try:
        from langsmith import get_current_run_tree
    except ImportError:
        return None

    try:
        run = get_current_run_tree()
        return str(run.id) if run else None
    except Exception as exc:  # noqa: BLE001 — never let tracing break a real call
        log.debug("get_current_trace_id failed: %s", exc)
        return None
