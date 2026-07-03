"""N6 + N7 — Hypothesis Generator and Hypothesis Judge.

N6 consumes MarketingContext + extras + page_context → 3-6 A/B test plans.
N7 consumes those plans + original context → ship/iterate/kill verdicts per plan.
"""

from ai_agent_system.hypotheses.judge_schemas import (
    HypothesisJudgeOutput,
    JudgeVerdict,
    JudgeVerdictType,
)
from ai_agent_system.hypotheses.schemas import (
    ABTestPlan,
    HypothesisGeneratorOutput,
    SuccessCriterion,
    TestVariant,
)

__all__ = [
    "ABTestPlan",
    "HypothesisGeneratorOutput",
    "SuccessCriterion",
    "TestVariant",
    "HypothesisJudgeOutput",
    "JudgeVerdict",
    "JudgeVerdictType",
]
