"""Observability layer — agent logging, run inspection, parameterized configs.

Three-level hierarchy mirrors how the system actually works:

    Run (one end-to-end user request, e.g. "draft context for homeiq.io")
      └─ Agent Invocation (one specialist's turn, e.g. "PersonaCrafter at 13:42")
           └─ LLM Call (one HTTP call, possibly retried, possibly failed validation)

Every event at every level is logged. Reading the logs answers questions like:
  - "Why did Customer Insights pick this persona over that one?"
  - "How much did one homeiq.io draft cost end-to-end?"
  - "Which agent has the highest validation-failure rate?"
"""

from ai_agent_system.observability.agent_logger import (
    AgentLogger,
    RunLogger,
    get_agent_logger,
)
from ai_agent_system.observability.models import (
    LogEvent,
    EventType,
    LLMCallRecord,
    AgentInvocationRecord,
)

__all__ = [
    "AgentLogger",
    "RunLogger",
    "get_agent_logger",
    "LogEvent",
    "EventType",
    "LLMCallRecord",
    "AgentInvocationRecord",
]
