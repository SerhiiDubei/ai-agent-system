"""5 character-driven sub-agents that decompose the legacy monolithic drafter.

Wave 1 (parallel — no inter-dependencies):
  - customer_insights      → personas + pain points + audience psychology
  - media_planner          → channel profile + creative grammar
  - conversion_architect   → user flow + test priorities + friction inventory

Wave 2 (parallel — depend on Wave 1):
  - voice_message          → uses customer_insights output
  - audience_strategist    → uses customer_insights + media_planner output

Wave 3:
  - assembler              → flattens 5 sub-outputs into MarketingContext
"""

from ai_agent_system.marketing.agents.customer_insights import run_customer_insights
from ai_agent_system.marketing.agents.voice_message import run_voice_message
from ai_agent_system.marketing.agents.media_planner import run_media_planner
from ai_agent_system.marketing.agents.audience_strategist import run_audience_strategist
from ai_agent_system.marketing.agents.conversion_architect import run_conversion_architect

__all__ = [
    "run_customer_insights",
    "run_voice_message",
    "run_media_planner",
    "run_audience_strategist",
    "run_conversion_architect",
]
