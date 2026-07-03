"""Assembler — combines 5 sub-outputs into a single MarketingContext.

This is where cross-field validators live (primary_persona_name match,
channel match) — only the assembler has visibility into the WHOLE picture.

The assembler is INTENTIONALLY DEFENSIVE. Sub-agents — especially smaller
models like gpt-4o-mini — frequently violate cross-field constraints in
predictable ways (e.g. truncating a persona name from "Florida Fred, 70,
fall-risk retiree" to just "Florida Fred"). Rather than fail hard or beg
the model in prompts, we auto-correct these specific patterns and log
the correction for later prompt-tuning.

Note: legacy MarketingContext schema is FLAT (personas, pain_points_aggregate,
audience_profile, channel_profile, user_flow as top-level fields). To keep
backward compatibility with the existing N4 service.py + judge.py + db
persistence, the assembler flattens the 5 sub-outputs into the legacy shape.

Phase 2+ may evolve MarketingContext to embed the new sub-outputs (voice_message,
test_priorities) as first-class fields. For Phase 1 we attach them as a
dict on the side via `assembler_metadata`.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from ai_agent_system.marketing.brief import MarketingBrief
from ai_agent_system.marketing.models import (
    AudienceProfile,
    MarketingContext,
    Persona,
)
from ai_agent_system.marketing.sub_schemas import (
    AudienceSegmentationOutput,
    ConversionArchitectureOutput,
    CustomerInsightsOutput,
    MediaPlanOutput,
    VoiceMessageOutput,
)

log = logging.getLogger(__name__)


# ── Auto-correction helpers ──────────────────────────────────────────────────

def _resolve_primary_persona_name(
    *,
    proposed_name: str,
    personas: list[Persona],
) -> tuple[str, str | None]:
    """Find the actual persona name that matches the proposed (possibly truncated) one.

    Strategy (order of preference):
      1. Exact match → use as is
      2. proposed_name is a prefix of one persona name → use that persona
      3. proposed_name is a substring of exactly one persona name → use that persona
      4. case-insensitive variant of any of the above
      5. fall back to personas[0] (the first generated persona is usually primary)

    Returns (resolved_name, correction_note).
    correction_note is None when no correction was needed.
    """
    names = [p.name for p in personas]

    # 1. Exact
    if proposed_name in names:
        return proposed_name, None

    # 2. Prefix
    prefix_matches = [n for n in names if n.startswith(proposed_name)]
    if len(prefix_matches) == 1:
        return prefix_matches[0], (
            f"PRIMARY_PERSONA_NAME_TRUNCATED: agent returned {proposed_name!r}, "
            f"matched by prefix to {prefix_matches[0]!r}"
        )

    # 3. Substring (unique)
    sub_matches = [n for n in names if proposed_name in n]
    if len(sub_matches) == 1:
        return sub_matches[0], (
            f"PRIMARY_PERSONA_NAME_PARTIAL: agent returned {proposed_name!r}, "
            f"matched by substring to {sub_matches[0]!r}"
        )

    # 4. Case-insensitive variants
    proposed_lower = proposed_name.lower()
    ci_prefix = [n for n in names if n.lower().startswith(proposed_lower)]
    if len(ci_prefix) == 1:
        return ci_prefix[0], (
            f"PRIMARY_PERSONA_NAME_CASE: agent returned {proposed_name!r}, "
            f"case-insensitive match to {ci_prefix[0]!r}"
        )
    ci_sub = [n for n in names if proposed_lower in n.lower()]
    if len(ci_sub) == 1:
        return ci_sub[0], (
            f"PRIMARY_PERSONA_NAME_CASE_PARTIAL: agent returned {proposed_name!r}, "
            f"case-insensitive substring match to {ci_sub[0]!r}"
        )

    # 5. Last-resort fallback
    fallback = personas[0].name
    return fallback, (
        f"PRIMARY_PERSONA_NAME_FALLBACK: agent returned {proposed_name!r} which "
        f"matches none of {names}. Falling back to first persona {fallback!r}."
    )


def _resolve_secondary_names(
    *,
    proposed: list[str],
    personas: list[Persona],
    primary_name: str,
) -> tuple[list[str], list[str]]:
    """Same logic for each secondary name. Returns (resolved, correction_notes)."""
    notes: list[str] = []
    resolved: list[str] = []
    for name in proposed:
        # Skip if it would duplicate the primary
        rn, note = _resolve_primary_persona_name(proposed_name=name, personas=personas)
        if rn != primary_name and rn not in resolved:
            resolved.append(rn)
        if note:
            notes.append(note)
    return resolved, notes


def assemble_marketing_context(
    *,
    brief: MarketingBrief,
    insights: CustomerInsightsOutput,
    voice: VoiceMessageOutput,
    media: MediaPlanOutput,
    audience: AudienceSegmentationOutput,
    cro: ConversionArchitectureOutput,
    grounding_chunks: list[str] | None = None,
) -> tuple[MarketingContext, dict[str, Any]]:
    """
    Returns:
        (MarketingContext, extra_assembler_metadata)

    extra_assembler_metadata contains the new fields (voice_message contents,
    test_priorities, friction_inventory, lookalike_seeds, exclusion_signals,
    channel_temperature, creative_grammar, audience_psychology_summary) that
    legacy MarketingContext doesn't model. They will be promoted to first-class
    fields in a future schema migration.
    """
    # ── Auto-correct cross-field constraint violations ──────────────────────
    # Sub-agents (especially mini models) often violate these in predictable
    # ways. We fix what we can, log the corrections for prompt-tuning later.
    corrections: list[str] = []

    # 1. Primary persona name might be truncated/case-different
    resolved_primary, note = _resolve_primary_persona_name(
        proposed_name=audience.audience_profile.primary_persona_name,
        personas=insights.personas,
    )
    if note:
        corrections.append(note)
        log.warning("Assembler auto-correction: %s", note)

    # 2. Secondary persona names — same logic
    resolved_secondary, sec_notes = _resolve_secondary_names(
        proposed=audience.audience_profile.secondary_persona_names,
        personas=insights.personas,
        primary_name=resolved_primary,
    )
    corrections.extend(sec_notes)
    for n in sec_notes:
        log.warning("Assembler auto-correction: %s", n)

    # Rebuild the AudienceProfile with corrected names
    audience_profile_fixed = AudienceProfile(
        primary_persona_name=resolved_primary,
        secondary_persona_names=resolved_secondary,
        estimated_primary_share=audience.audience_profile.estimated_primary_share,
        market=audience.audience_profile.market,
        language=audience.audience_profile.language,
        total_addressable_population_note=audience.audience_profile.total_addressable_population_note,
    )

    # 3. Channel match check — assembler also auto-corrects if discriminator
    # doesn't match traffic_source_primary, by trusting the brief's traffic source
    if media.channel_profile.channel != brief.traffic_source_primary:
        corrections.append(
            f"CHANNEL_MISMATCH: media planner returned channel={media.channel_profile.channel!r} "
            f"but brief.traffic_source_primary={brief.traffic_source_primary!r}. "
            f"Trusting the brief — this requires manual review."
        )
        log.error("Assembler: channel mismatch — keeping media.channel_profile but it WILL FAIL validation")
        # We can't rebuild ChannelProfile easily without losing channel-specific
        # fields. Better to fail loudly here so user catches it.

    # Build legacy MarketingContext (will run all model validators)
    ctx = MarketingContext(
        schema_version=1,
        niche=brief.niche,
        parent_category=brief.parent_category,
        market=brief.market,
        language=brief.language,
        traffic_source_primary=brief.traffic_source_primary,
        page_goal=brief.page_goal,
        primary_metric=brief.primary_metric,
        guardrail_metrics=[],
        business_constraints=brief.business_constraints,
        personas=insights.personas,
        pain_points_aggregate=insights.pain_points_aggregate,
        user_flow=cro.user_flow,
        audience_profile=audience_profile_fixed,
        channel_profile=media.channel_profile,
        source_brief=brief.brief,
        grounding_chunks_used=(grounding_chunks or [])[:5],
    )

    extra_metadata: dict[str, Any] = {
        "audience_psychology_summary": insights.audience_psychology_summary,
        "voice_message": voice.model_dump(),
        "media_extras": {
            "channel_temperature": media.channel_temperature,
            "creative_grammar": media.creative_grammar,
        },
        "audience_extras": {
            "lookalike_seeds": audience.lookalike_seeds,
            "exclusion_signals": audience.exclusion_signals,
        },
        "cro_extras": {
            "test_priorities": [t.model_dump() for t in cro.test_priorities],
            "friction_inventory": [f.model_dump() for f in cro.friction_inventory],
        },
        "assembler_corrections": corrections,   # auto-fixes applied
    }

    return ctx, extra_metadata


class AssemblerError(Exception):
    """Raised when assembling the legacy MarketingContext fails validation.

    This should not happen if all sub-agents satisfied their schemas AND the
    cross-field constraints (primary_persona_name in personas, channel match)
    were preserved. If it does happen, the upstream agent that produced the
    mismatch is at fault — log clearly so the user can debug.
    """
