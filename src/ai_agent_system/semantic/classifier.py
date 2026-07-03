"""Pydantic AI classifier for semantic role mapping — N2.

Three-tier cascade:
  Tier 1 — claude-sonnet-4.6 (primary, cheap, fast)
  Tier 2 — gpt-4o cross-check (only when Sonnet confidence < threshold)
  Tier 3 — claude-opus-4.6 arbitration (only when Tier 1/2 disagree on primary CTA)

Key design decisions:
  - temperature=0.0 — this is a structured-extraction task, not a generation task
  - retries=2 — Pydantic AI auto-retries when the output fails schema validation
  - BinaryContent for image — LLM receives screenshot + DOM marks JSON simultaneously
  - Marks list in JSON, NOT visual overlays — works whether or not SoM badges exist
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_agent_system.config import settings
from ai_agent_system.semantic.models import DomMark, PageSemanticMap

log = logging.getLogger(__name__)

ARBITRATE_BELOW: float = 0.6  # triggers cross-check when primary confidence falls here

SYSTEM_PROMPT = """\
You are a senior conversion-rate-optimization analyst. You classify
elements of LEAD-GENERATION landing pages (home-improvement services,
dating sites, similar direct-response verticals) into a fixed semantic-role
taxonomy.

You will receive:
1. A screenshot of the rendered page (PNG). Examine it carefully for
   visual hierarchy, colours, whitespace, and element prominence.
2. A JSON list of candidate DOM elements:
   [{mark_id, tag, text, role_attr, href, class_hint}, ...].
   Every mark_id is a unique integer. There are no visual badge overlays
   on the screenshot — use the JSON list as your numbered reference.
3. The viewport (desktop or mobile).

RULES — violations will fail schema validation and trigger automatic retry:
- PRIMARY CTA: the single button/link the page is most clearly driving
  visitors toward. At most ONE per snapshot. If two equally prominent
  buttons exist (e.g., "Get Quote" and "Call Now"), pick the one closest
  to the hero and demote the other to secondary_cta or phone_block.
- HERO IMAGE: the largest above-the-fold visual establishing the offer.
  At most ONE. Background videos count.
- LEAD FORM: any form collecting contact info (name / email / phone / zip)
  for follow-up. Login, search, and newsletter forms do NOT qualify.
- TRUST BLOCK: badges, certifications, "BBB A+", media logos, years in
  business. Distinct from SOCIAL PROOF BLOCK (reviews, stars, customer counts).
- BEFORE_AFTER: paired before/after images showing physical transformation
  (roofing, bathrooms, weight loss, dating-profile improvements).
- Assign roles ONLY to mark_ids that appear in the input JSON.
- confidence < 0.5 → set role to `unknown` unless you have a clear signal.
- Every mark_id in the input MUST appear exactly once in your assignments.
- Be conservative. `unknown` is always preferable to an incorrect label.
"""

_USER_PROMPT_TPL = """\
Viewport: {viewport}
URL: {url}
Page heading summary (from markdown):
{headings}

DOM marks (JSON):
{marks_json}

Classify every mark_id. Return a PageSemanticMap.
"""


def _provider() -> OpenAIProvider:
    return OpenAIProvider(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key.get_secret_value(),
    )


def _build_agent(model_id: str) -> Agent[None, PageSemanticMap]:
    return Agent(
        model=OpenAIModel(model_name=model_id, provider=_provider()),
        output_type=PageSemanticMap,
        system_prompt=SYSTEM_PROMPT,
        model_settings={"temperature": 0.0},
        retries=2,
    )


# Lazy-built per model_id to avoid instantiation overhead at import time
_agents: dict[str, Agent] = {}


def _agent(model_id: str) -> Agent:
    if model_id not in _agents:
        _agents[model_id] = _build_agent(model_id)
    return _agents[model_id]


def _extract_headings(markdown: str, max_chars: int = 400) -> str:
    lines = [ln for ln in markdown.splitlines() if ln.startswith("#")]
    return "\n".join(lines)[:max_chars]


async def _run_classifier(
    *,
    viewport: str,
    url: str,
    markdown: str,
    marks: list[DomMark],
    screenshot_bytes: bytes,
    model_id: str,
    extra_context: Optional[dict] = None,
) -> PageSemanticMap:
    user_msg = _USER_PROMPT_TPL.format(
        viewport=viewport,
        url=url,
        headings=_extract_headings(markdown),
        marks_json=json.dumps(
            [m.model_dump(exclude={"bbox"}) for m in marks],
            ensure_ascii=False,
            indent=2,
        ),
    )
    if extra_context:
        user_msg += (
            f"\n\nArbitration context (two prior models disagreed):\n"
            f"{json.dumps(extra_context, indent=2)}"
        )

    result = await _agent(model_id).run(
        [user_msg, BinaryContent(data=screenshot_bytes, media_type="image/png")]
    )
    return result.output


def _agree_on_primary_cta(a: PageSemanticMap, b: PageSemanticMap) -> bool:
    a_cta = next((x.mark_id for x in a.assignments if x.role == "primary_cta"), None)
    b_cta = next((x.mark_id for x in b.assignments if x.role == "primary_cta"), None)
    return a_cta is not None and a_cta == b_cta


async def classify_snapshot(
    *,
    viewport: str,
    url: str,
    markdown: str,
    marks: list[DomMark],
    screenshot_bytes: bytes,
    primary_model: str = "anthropic/claude-sonnet-4.6",
    fallback_model: str = "openai/gpt-4o",
    arbitration_model: str = "anthropic/claude-opus-4.6",
    arbitrate_below: float = ARBITRATE_BELOW,
) -> tuple[PageSemanticMap, str]:
    """Classify semantic roles for one viewport. Returns (map, model_used).

    Cascade: Sonnet → optional GPT-4o cross-check → optional Opus arbitration.
    In the common case (high confidence) only one LLM call is made.
    """
    common = dict(
        viewport=viewport,
        url=url,
        markdown=markdown,
        marks=marks,
        screenshot_bytes=screenshot_bytes,
    )

    primary = await _run_classifier(**common, model_id=primary_model)

    primary_cta_conf = next(
        (a.confidence for a in primary.assignments if a.role == "primary_cta"), 0.0
    )
    needs_cross_check = (
        primary.archetype_confidence < arbitrate_below or primary_cta_conf < arbitrate_below
    )

    if not needs_cross_check:
        return primary, primary_model

    log.info(
        "semantic:cross_check url=%s viewport=%s archetype_conf=%.2f cta_conf=%.2f",
        url,
        viewport,
        primary.archetype_confidence,
        primary_cta_conf,
    )

    cross = await _run_classifier(**common, model_id=fallback_model)

    if _agree_on_primary_cta(primary, cross):
        return primary, primary_model

    log.info("semantic:arbitration url=%s viewport=%s — models disagree on primary CTA", url, viewport)
    arbitrated = await _run_classifier(
        **common,
        model_id=arbitration_model,
        extra_context={
            "sonnet_says": primary.model_dump(),
            "gpt4o_says": cross.model_dump(),
        },
    )
    return arbitrated, arbitration_model
