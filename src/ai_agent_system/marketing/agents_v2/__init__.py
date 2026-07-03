"""Phase 5 agents — built as systems, not single prompts.

Each v2 agent lives in agents/<agent_name>/ at the project root and is composed
of multiple knowledge files: identity + beliefs + workflow + frameworks +
market_segments + golden_sets + persona templates.

The loader (system_loader.py) assembles these into a single rich system_prompt
at runtime, conditionally based on the brief's niche signals.

Migration plan:
  - Phase 5b: customer_insights_v2 ships as a parallel implementation;
    legacy customer_insights stays unchanged for fallback.
  - Phase 5c: same pattern applied to voice_message, media_planner,
    audience_strategist, conversion_architect, hypothesis_generator,
    hypothesis_judge.
  - Eventually legacy `prompts/<agent>/v1.md` is retired.
"""

from ai_agent_system.marketing.agents_v2.customer_insights_v2 import (
    run_customer_insights_v2,
)
from ai_agent_system.marketing.agents_v2.system_loader import (
    AgentSystem,
    load_agent_system,
    select_routing,
)

__all__ = [
    "run_customer_insights_v2",
    "AgentSystem",
    "load_agent_system",
    "select_routing",
]
