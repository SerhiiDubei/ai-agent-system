"""LLM Gateway — N10.

Per research:
- Bare openai.AsyncOpenAI з base_url override → OpenRouter (NO LiteLLM)
- Per-operation routing via YAML
- Cost tracking per call + daily rollup
- Kill-switch via Postgres bool + 5s TTL cache
- LangSmith one-line integration via wrap_openai
"""

from ai_agent_system.llm.exceptions import (
    BudgetExceededException,
    KillSwitchActiveException,
    OperationNotConfiguredException,
)
from ai_agent_system.llm.kill_switch import KillSwitch
from ai_agent_system.llm.router import LlmRouter
from ai_agent_system.llm.routing_config import RoutingConfig

__all__ = [
    "BudgetExceededException",
    "KillSwitch",
    "KillSwitchActiveException",
    "LlmRouter",
    "OperationNotConfiguredException",
    "RoutingConfig",
]
