"""Voice & Message Strategist (Conversion Copywriter) — Wave 2 agent.

Depends on Customer Insights output (personas + audience_psychology_summary).

Responsibility: extract the message architecture every other agent / hypothesis
generator will use — value prop, hook variations, headline angles tagged
by awareness stage, banned cliches, verbatim voice examples.

Input: Brief + CustomerInsightsOutput
Output: VoiceMessageOutput
"""

from __future__ import annotations

import logging

from ai_agent_system.marketing.agents._base import (
    load_character_card,
    run_with_fallback,
)
from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.page_context import (
    PageContext,
    render_page_context_for_prompt,
)
from ai_agent_system.marketing.sub_schemas import (
    CustomerInsightsOutput,
    VoiceMessageOutput,
)
from ai_agent_system.observability.agent_logger import RunLogger
from ai_agent_system.observability.config_loader import AgentsConfig

log = logging.getLogger(__name__)

AGENT_NAME = "voice_message"


def _build_user_prompt(
    brief: MarketingBrief,
    insights: CustomerInsightsOutput,
    page_context: PageContext | None,
) -> str:
    personas_summary = "\n".join(
        f"  - {p.name} (role={p.role}, JTBD={p.primary_job!r})"
        for p in insights.personas
    )

    page_block = ""
    if page_context:
        page_block = (
            f"\n\nEXISTING PAGE COPY — tear this down. Identify what is lazy, generic, "
            f"or brand-decoration. Your headline_angles should outperform the current "
            f"copy on the page below. Cite specific weak phrases in your rationale.\n\n"
            f"{render_page_context_for_prompt(page_context)}\n"
        )

    return (
        f"BRIEF:\n{brief.brief}\n\n"
        f"METADATA:\n"
        f"- niche: {brief.niche}\n"
        f"- traffic_source_primary: {brief.traffic_source_primary}\n"
        f"- page_goal: {brief.page_goal}\n\n"
        f"PERSONAS (from Customer Insights — use as raw material):\n"
        f"{personas_summary}\n\n"
        f"AUDIENCE PSYCHOLOGY:\n{insights.audience_psychology_summary}\n\n"
        f"AGGREGATE PAIN POINTS (top {len(insights.pain_points_aggregate)}):\n"
        + "\n".join(f"  - {p.label}: {p.description}" for p in insights.pain_points_aggregate)
        + page_block
        + "\n\n"
        f"Generate the VoiceMessageOutput JSON now. "
        f"Use verbatim voice from personas where possible. "
        f"Tag each headline_angle with the correct awareness_stage."
        + (
            "\n\nWith page captured: your voice_examples should include 1-2 verbatim "
            "phrases lifted directly from the existing page copy (so we can see what "
            "the current page already says vs what your new angles propose)."
            if page_context else ""
        )
    )


async def run_voice_message(
    brief: MarketingBrief,
    insights: CustomerInsightsOutput,
    *,
    run_logger: RunLogger,
    cfg: AgentsConfig,
    page_context: PageContext | None = None,
) -> VoiceMessageOutput:
    agent_cfg = cfg.get_agent(AGENT_NAME)
    prompt_version = cfg.prompt_versions.get(AGENT_NAME, "v1")
    system_prompt = load_character_card(AGENT_NAME, prompt_version)
    user_prompt = _build_user_prompt(brief, insights, page_context)

    inv = run_logger.start_agent(
        AGENT_NAME,
        input_full={
            "brief": brief.model_dump(),
            "personas_count": len(insights.personas),
            "page_context": (
                page_context.short_summary() if page_context else "none"
            ),
        },
        config_used=agent_cfg.model_dump(),
    )
    try:
        output = await run_with_fallback(
            agent_name=AGENT_NAME,
            config=agent_cfg,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_type=VoiceMessageOutput,
            invocation_logger=inv,
        )
        inv.complete(
            succeeded=True,
            output_full=output.model_dump(),
            output_summary=(
                f"{len(output.hook_variations)} hooks, "
                f"{len(output.headline_angles)} angles, "
                f"value_prop={output.primary_value_prop[:60]!r}"
            ),
        )
        return output
    except Exception as e:
        inv.complete(succeeded=False, final_error=f"{type(e).__name__}: {e}")
        raise
